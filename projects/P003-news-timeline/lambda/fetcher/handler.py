import json
import os
import re
import hashlib
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

TABLE_NAME = os.environ.get('TABLE_NAME', 'p003-topics')
S3_BUCKET  = os.environ.get('S3_BUCKET', '')
REGION     = os.environ.get('REGION', 'ap-northeast-1')

dynamodb = boto3.resource('dynamodb', region_name=REGION)
table    = dynamodb.Table(TABLE_NAME)
s3       = boto3.client('s3', region_name=REGION)

RSS_FEEDS = [
    {'url': 'https://www3.nhk.or.jp/rss/news/cat0.xml',                      'genre': '総合',        'lang': 'ja'},
    {'url': 'https://news.yahoo.co.jp/rss/topics/top-picks.xml',             'genre': '総合',        'lang': 'ja'},
    {'url': 'https://news.yahoo.co.jp/rss/topics/politics.xml',              'genre': '政治',        'lang': 'ja'},
    {'url': 'https://news.yahoo.co.jp/rss/topics/business.xml',              'genre': 'ビジネス',    'lang': 'ja'},
    {'url': 'https://news.yahoo.co.jp/rss/topics/it.xml',                    'genre': 'テクノロジー', 'lang': 'ja'},
    {'url': 'https://news.yahoo.co.jp/rss/topics/sports.xml',                'genre': 'スポーツ',    'lang': 'ja'},
    {'url': 'https://news.yahoo.co.jp/rss/topics/entertainment.xml',         'genre': 'エンタメ',    'lang': 'ja'},
    {'url': 'https://news.yahoo.co.jp/rss/topics/science.xml',               'genre': '科学',        'lang': 'ja'},
    {'url': 'https://news.yahoo.co.jp/rss/topics/world.xml',                 'genre': '国際',        'lang': 'ja'},
    {'url': 'https://feeds.bbci.co.uk/news/world/rss.xml',                   'genre': '国際',        'lang': 'en'},
    {'url': 'https://feeds.bbci.co.uk/news/technology/rss.xml',              'genre': 'テクノロジー', 'lang': 'en'},
    {'url': 'https://feeds.bbci.co.uk/news/business/rss.xml',                'genre': 'ビジネス',    'lang': 'en'},
    {'url': 'https://feeds.bbci.co.uk/sport/rss.xml',                        'genre': 'スポーツ',    'lang': 'en'},
    {'url': 'https://feeds.bbci.co.uk/news/science_and_environment/rss.xml', 'genre': '科学',        'lang': 'en'},
    {'url': 'https://feeds.bbci.co.uk/news/health/rss.xml',                  'genre': '健康',        'lang': 'en'},
    {'url': 'https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml',  'genre': 'エンタメ',    'lang': 'en'},
]

JACCARD_THRESHOLD = 0.3

STOP_WORDS = {
    # 日本語助詞・助動詞
    'は','が','を','に','の','と','で','も','や','か','へ','より','から','まで',
    'という','として','による','において','について','した','する','して',
    'された','される','てい','ます','です','だっ','ある','いる','なっ','れる',
    # 英語
    'the','a','an','is','are','was','were','be','been','of','in','to','for',
    'on','at','by','with','as','from','that','this','it','its','and','or',
    'but','not','have','has','had','will','would','could','should','says',
    'said','new','more','after','over','after','about','up','out','two',
    'into','than','he','she','his','her','they','we','you','i',
}


def normalize(text):
    text = re.sub(r'[【】「」『』（）()\[\]！？!?\s\u3000・]+', ' ', text.lower())
    return {w for w in text.split() if len(w) > 1}


def jaccard(a, b):
    sa, sb = normalize(a), normalize(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def topic_fingerprint(articles):
    """記事群から安定したキーワード指紋を生成 → トピックIDに使う"""
    counter = Counter()
    for a in articles:
        words = normalize(a['title']) - STOP_WORDS
        counter.update(w for w in words if len(w) > 2)
    top = sorted(w for w, _ in counter.most_common(10) if counter[w] >= 1)[:5]
    if not top:
        # フォールバック：最初の記事タイトルをそのまま使用
        top = [articles[0]['title'][:30]]
    return hashlib.md5(' '.join(top).encode()).hexdigest()[:16]


def fetch_rss(feed):
    articles = []
    url, genre, lang = feed['url'], feed['genre'], feed.get('lang', 'ja')
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'NewsTimeline/1.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read()
        root = ET.fromstring(content)
        for item in root.findall('.//item'):
            title   = (item.findtext('title')   or '').strip()
            link    = (item.findtext('link')     or '').strip()
            pubdate = (item.findtext('pubDate')  or '').strip()
            if title and link:
                articles.append({
                    'title':   title, 'url': link,
                    'pubDate': pubdate, 'genre': genre,
                    'lang':    lang,
                    'source':  url.split('/')[2],
                })
    except Exception as e:
        print(f'RSS error [{url}]: {e}')
    return articles


def cluster(articles):
    groups, used = [], [False] * len(articles)
    for i, a in enumerate(articles):
        if used[i]: continue
        g = [a]; used[i] = True
        for j in range(i + 1, len(articles)):
            if not used[j] and jaccard(a['title'], articles[j]['title']) >= JACCARD_THRESHOLD:
                g.append(articles[j]); used[j] = True
        groups.append(g)
    return groups


def dominant_genre(articles):
    return Counter(a['genre'] for a in articles).most_common(1)[0][0]


def dominant_lang(articles):
    return Counter(a.get('lang', 'ja') for a in articles).most_common(1)[0][0]


def source_count(articles):
    """何メディアが報道したか（真の重複排除）"""
    return len({a['source'] for a in articles})


def hatena_count(url):
    """はてなブックマーク数を取得（日本語記事用・失敗時は0）"""
    try:
        api = 'https://b.hatena.ne.jp/entry/jsonlite/?url=' + urllib.parse.quote(url, safe='')
        req = urllib.request.Request(api, headers={'User-Agent': 'NewsTimeline/1.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        return int(data.get('count') or 0)
    except Exception:
        return 0


def calc_score(articles):
    """バズスコア = メディア数×10 + はてブ数（日本語記事のみ）"""
    media = source_count(articles)
    hb    = 0
    jp_articles = [a for a in articles if '.jp' in a['source'] or 'nhk' in a['source']]
    for a in jp_articles[:3]:  # 上位3記事だけ取得（速度優先）
        hb += hatena_count(a['url'])
    return media * 10 + hb, media, hb


def recent_counts(tid, n=5):
    try:
        r = table.query(
            KeyConditionExpression=Key('topicId').eq(tid) & Key('SK').begins_with('SNAP#'),
            ScanIndexForward=False, Limit=n,
            ProjectionExpression='articleCount',
        )
        return [int(item['articleCount']) for item in r.get('Items', [])]
    except Exception:
        return []


def calc_status(history, current):
    counts = list(reversed(history)) + [current]
    if len(counts) < 2: return 'rising'
    diff = counts[-1] - counts[0]
    if diff > 0:  return 'rising'
    if diff < -1: return 'declining'
    return 'peak'


def dec_convert(obj):
    if isinstance(obj, Decimal): return int(obj)
    raise TypeError


def get_all_topics():
    items, kwargs = [], {
        'FilterExpression': 'SK = :m',
        'ExpressionAttributeValues': {':m': 'META'},
        'ProjectionExpression': 'topicId,title,#s,articleCount,lastUpdated,genre,#l,score,mediaCount,hatenaCount',
        'ExpressionAttributeNames': {'#s': 'status', '#l': 'lang'},
    }
    while True:
        r = table.scan(**kwargs)
        items.extend(r.get('Items', []))
        if not r.get('LastEvaluatedKey'): break
        kwargs['ExclusiveStartKey'] = r['LastEvaluatedKey']
    items.sort(key=lambda x: int(x.get('score', 0) or 0), reverse=True)
    return items


def get_topic_detail(tid):
    r     = table.query(KeyConditionExpression=Key('topicId').eq(tid))
    items = r.get('Items', [])
    meta  = next((i for i in items if i['SK'] == 'META'), None)
    snaps = sorted([i for i in items if i['SK'].startswith('SNAP#')], key=lambda x: x['SK'])
    return meta, snaps


def write_s3(key, data):
    if not S3_BUCKET: return
    s3.put_object(
        Bucket=S3_BUCKET, Key=key,
        Body=json.dumps(data, default=dec_convert, ensure_ascii=False).encode('utf-8'),
        ContentType='application/json', CacheControl='max-age=60',
    )


def lambda_handler(event, context):
    all_articles = []
    for feed in RSS_FEEDS:
        fetched = fetch_rss(feed)
        all_articles.extend(fetched)
        print(f'[{feed["genre"]}] {feed["url"].split("/")[2]}: {len(fetched)}件')

    print(f'合計: {len(all_articles)}記事')
    groups = cluster(all_articles)
    print(f'トピック数: {len(groups)}')

    now    = datetime.now(timezone.utc)
    ts_key = now.strftime('%Y%m%dT%H%M%SZ')
    ts_iso = now.isoformat()

    saved_ids = []
    for g in groups:
        tid   = topic_fingerprint(g)          # 安定IDに変更
        cnt   = len(g)
        genre = dominant_genre(g)
        lang  = dominant_lang(g)
        hist  = recent_counts(tid)
        st    = calc_status(hist, cnt)
        score, media, hb = calc_score(g)

        table.put_item(Item={
            'topicId':      tid,
            'SK':           'META',
            'title':        g[0]['title'],
            'status':       st,
            'genre':        genre,
            'lang':         lang,
            'articleCount': cnt,
            'mediaCount':   media,
            'hatenaCount':  hb,
            'score':        score,
            'lastUpdated':  ts_iso,
            'sources':      list({a['source'] for a in g}),
        })
        table.put_item(Item={
            'topicId':      tid,
            'SK':           f'SNAP#{ts_key}',
            'articleCount': cnt,
            'score':        score,
            'hatenaCount':  hb,
            'mediaCount':   media,
            'timestamp':    ts_iso,
            'articles': [
                {'title': a['title'], 'url': a['url'],
                 'source': a['source'], 'pubDate': a['pubDate']}
                for a in g[:20]
            ],
        })
        saved_ids.append(tid)

    if S3_BUCKET:
        topics = get_all_topics()
        write_s3('api/topics.json', {'topics': topics, 'updatedAt': ts_iso})
        for tid in saved_ids:
            meta, snaps = get_topic_detail(tid)
            if meta:
                write_s3(f'api/topic/{tid}.json', {
                    'meta': meta,
                    'timeline': [
                        {'timestamp': s['timestamp'],
                         'articleCount': s['articleCount'],
                         'score': s.get('score', 0),
                         'articles': s.get('articles', [])}
                        for s in snaps
                    ],
                })
        print('S3書き出し完了')

    return {'statusCode': 200,
            'body': json.dumps({'articles': len(all_articles), 'topics': len(groups), 'ts': ts_key})}
