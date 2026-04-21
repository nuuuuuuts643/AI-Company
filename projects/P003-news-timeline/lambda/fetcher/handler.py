import json
import os
import re
import hashlib
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from email.utils import parsedate_tz, mktime_tz

import boto3
from boto3.dynamodb.conditions import Key

TABLE_NAME        = os.environ.get('TABLE_NAME', 'p003-topics')
S3_BUCKET         = os.environ.get('S3_BUCKET', '')
REGION            = os.environ.get('REGION', 'ap-northeast-1')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

dynamodb = boto3.resource('dynamodb', region_name=REGION)
table    = dynamodb.Table(TABLE_NAME)
s3       = boto3.client('s3', region_name=REGION)

RSS_FEEDS = [
    # Google News（日本語・カテゴリ別）
    {'url': 'https://news.google.com/rss/headlines/section/topic/NATION?hl=ja&gl=JP&ceid=JP:ja',         'genre': '総合'},
    {'url': 'https://news.google.com/rss/headlines/section/topic/POLITICS?hl=ja&gl=JP&ceid=JP:ja',       'genre': '政治'},
    {'url': 'https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=ja&gl=JP&ceid=JP:ja',       'genre': 'ビジネス'},
    {'url': 'https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=ja&gl=JP&ceid=JP:ja',     'genre': 'テクノロジー'},
    {'url': 'https://news.google.com/rss/headlines/section/topic/SPORTS?hl=ja&gl=JP&ceid=JP:ja',         'genre': 'スポーツ'},
    {'url': 'https://news.google.com/rss/headlines/section/topic/ENTERTAINMENT?hl=ja&gl=JP&ceid=JP:ja',  'genre': 'エンタメ'},
    {'url': 'https://news.google.com/rss/headlines/section/topic/SCIENCE?hl=ja&gl=JP&ceid=JP:ja',        'genre': '科学'},
    {'url': 'https://news.google.com/rss/headlines/section/topic/HEALTH?hl=ja&gl=JP&ceid=JP:ja',         'genre': '健康'},
    {'url': 'https://news.google.com/rss/headlines/section/topic/WORLD?hl=ja&gl=JP&ceid=JP:ja',          'genre': '国際'},
    # ライブドアニュース（補完）
    {'url': 'https://news.livedoor.com/topics/rss/dom.xml', 'genre': '総合'},
    {'url': 'https://news.livedoor.com/topics/rss/ent.xml', 'genre': 'エンタメ'},
    {'url': 'https://news.livedoor.com/topics/rss/spo.xml', 'genre': 'スポーツ'},
    {'url': 'https://news.livedoor.com/topics/rss/int.xml', 'genre': '国際'},
    # テクノロジー系
    {'url': 'https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml', 'genre': 'テクノロジー'},
    {'url': 'https://gigazine.net/news/rss_2.0/',                 'genre': 'テクノロジー'},
    {'url': 'https://ascii.jp/rss.xml',                           'genre': 'テクノロジー'},
    # ビジネス
    {'url': 'https://toyokeizai.net/list/feed/rss', 'genre': 'ビジネス'},
    # 株・金融（Google News検索RSS）
    {'url': 'https://news.google.com/rss/search?q=%E6%A0%AA%E4%BE%A1+%E6%97%A5%E6%9C%AC&hl=ja&gl=JP&ceid=JP:ja',    'genre': '株・金融'},
    {'url': 'https://news.google.com/rss/search?q=%E6%97%A5%E9%8A%80+%E9%87%91%E5%88%A9+%E7%82%BA%E6%9B%BF&hl=ja&gl=JP&ceid=JP:ja', 'genre': '株・金融'},
    {'url': 'https://news.google.com/rss/search?q=%E6%B1%BA%E7%AE%97+%E4%B8%8A%E5%A0%B4+%E6%A0%AA%E5%BC%8F&hl=ja&gl=JP&ceid=JP:ja', 'genre': '株・金融'},
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


MEDIA_NS = {
    'media':   'http://search.yahoo.com/mrss/',
    'content': 'http://purl.org/rss/1.0/modules/content/',
}

def extract_rss_image(item):
    """RSSアイテムからメディア画像URLを抽出"""
    mc = item.find('media:content', MEDIA_NS)
    if mc is not None and mc.get('url') and mc.get('medium', '') in ('image', ''):
        return mc.get('url')
    mt = item.find('media:thumbnail', MEDIA_NS)
    if mt is not None and mt.get('url'):
        return mt.get('url')
    enc = item.find('enclosure')
    if enc is not None and enc.get('type', '').startswith('image'):
        return enc.get('url')
    return None


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
            img     = extract_rss_image(item)
            if title and link:
                articles.append({
                    'title':    title, 'url': link,
                    'pubDate':  pubdate, 'genre': genre,
                    'lang':     lang,
                    'source':   url.split('/')[2],
                    'imageUrl': img,
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


GENRE_KEYWORDS = {
    '株・金融': ['株価','日経平均','円安','円高','為替','金利','日銀','決算','上場','株式','NISA','投資','FRB','ダウ','ナスダック','債券','利上げ','利下げ'],
    '政治':    ['国会','首相','総理','大臣','選挙','与党','野党','自民','政府','閣議','議員','内閣','知事','官房'],
    'スポーツ':  ['野球','サッカー','テニス','ゴルフ','バスケ','陸上','水泳','五輪','オリンピック','ワールドカップ','Ｊリーグ','プロ野球','NFL','NBA','相撲','ラグビー'],
    '健康':    ['病院','医療','がん','薬','治療','ワクチン','感染','医師','手術','診断','症状','厚生労働'],
    '科学':    ['宇宙','NASA','JAXA','研究','発見','論文','気候','地震','火山','iPS','ゲノム'],
    'エンタメ':  ['映画','俳優','女優','歌手','アイドル','芸能','ドラマ','アニメ','マンガ','コンサート','紅白','グラミー'],
    'テクノロジー':['AI','人工知能','ChatGPT','iPhone','Android','スマホ','クラウド','サイバー','半導体','アプリ','ソフトウェア','データセンター','量子'],
    'ビジネス':  ['売上','利益','赤字','黒字','買収','合併','リストラ','上半期','通期','業績','IPO','スタートアップ'],
    '国際':    ['米国','アメリカ','中国','ロシア','ウクライナ','EU','NATO','国連','外相','首脳','制裁','イラン','イスラエル','中東','北朝鮮','台湾'],
}

# 同義語正規化（クラスタリング精度向上）
SYNONYMS = {
    'アメリカ':'米国','米':'米国','usa':'米国','us':'米国',
    '総理':'首相','内閣総理大臣':'首相',
    '円相場':'為替','ドル円':'為替',
    '利上げ':'金利','利下げ':'金利',
    'オリンピック':'五輪','olympic':'五輪',
    'chatgpt':'ai','gpt':'ai','claude':'ai','gemini':'ai',
}

def normalize(text):
    text = re.sub(r'[【】「」『』（）()\[\]！？!?\s\u3000・]+', ' ', text.lower())
    words = set()
    for w in text.split():
        if len(w) > 1:
            words.add(SYNONYMS.get(w, w))
    return words


def dominant_genres(articles, max_genres=2):
    """最大2ジャンルを返す。スコア上位のジャンルを採用"""
    all_titles = ' '.join(a['title'] for a in articles)
    scores = {}
    for genre, keywords in GENRE_KEYWORDS.items():
        hit = sum(1 for kw in keywords if kw in all_titles)
        if hit >= 2:
            scores[genre] = hit
    if scores:
        top = sorted(scores, key=scores.get, reverse=True)[:max_genres]
        return top
    # キーワード不足時はRSSフィードのジャンル集計で決定
    return [Counter(a['genre'] for a in articles).most_common(1)[0][0]]


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


def sort_by_pubdate(articles):
    def get_ts(a):
        try:
            tpl = parsedate_tz(a.get('pubDate', ''))
            return mktime_tz(tpl) if tpl else 0
        except Exception:
            return 0
    return sorted(articles, key=get_ts, reverse=True)


def fetch_ogp_image(url):
    """記事URLからOGP画像URLを取得（2秒タイムアウト、失敗時はNone）"""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'NewsTimeline/1.0'})
        with urllib.request.urlopen(req, timeout=2) as resp:
            html = resp.read(16384).decode('utf-8', errors='ignore')
        # property="og:image" content="..."
        m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
        if m: return m.group(1)
        # content="..." property="og:image"
        m = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html, re.I)
        if m: return m.group(1)
    except Exception:
        pass
    return None


def generate_title(articles):
    """Claude APIで記事群の文脈を読んで簡潔なタイトルを生成（初回のみ呼ばれる）"""
    if not ANTHROPIC_API_KEY:
        return None
    headlines = '\n'.join(a['title'] for a in articles[:10])
    prompt = (
        '以下は同じニューストピックを報じた見出し一覧です。\n'
        'このトピックを表す簡潔な日本語タイトルを15文字以内で1つだけ答えてください。\n'
        '説明・句読点・かぎかっこ不要。タイトルのみ出力。\n\n'
        f'見出し:\n{headlines}'
    )
    try:
        body = json.dumps({
            'model': 'claude-haiku-4-5-20251001',
            'max_tokens': 30,
            'messages': [{'role': 'user', 'content': prompt}],
        }).encode('utf-8')
        req = urllib.request.Request(
            'https://api.anthropic.com/v1/messages',
            data=body,
            headers={
                'x-api-key': ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        return data['content'][0]['text'].strip()
    except Exception as e:
        print(f'Title generation error: {e}')
        return None


def generate_summary(articles):
    """Claude APIでトピックの要約を3〜4文で生成（初回のみ呼ばれる）"""
    if not ANTHROPIC_API_KEY:
        return None
    headlines = '\n'.join(a['title'] for a in articles[:15])
    prompt = (
        '以下は同じニューストピックを報じた見出し一覧です。\n'
        'このトピックの概要を分かりやすく2〜3文で要約してください。\n'
        '日本語で150字以内にまとめてください。箇条書き不要。自然な文章のみ出力。\n\n'
        f'見出し:\n{headlines}'
    )
    try:
        body = json.dumps({
            'model': 'claude-haiku-4-5-20251001',
            'max_tokens': 200,
            'messages': [{'role': 'user', 'content': prompt}],
        }).encode('utf-8')
        req = urllib.request.Request(
            'https://api.anthropic.com/v1/messages',
            data=body,
            headers={
                'x-api-key': ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read())
        return data['content'][0]['text'].strip()
    except Exception as e:
        print(f'Summary generation error: {e}')
        return None


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
        'ProjectionExpression': 'topicId,title,generatedTitle,generatedSummary,imageUrl,#s,articleCount,lastUpdated,genre,genres,#l,score,mediaCount,hatenaCount',
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
    views = sorted([i for i in items if i['SK'].startswith('VIEW#')], key=lambda x: x['SK'])
    return meta, snaps, views


def cleanup_stale(now):
    """72h以上更新なく低スコアのトピックを削除。人気だったもの(score>=30)は保持。"""
    cutoff = (now - timedelta(hours=72)).isoformat()
    kwargs = {
        'FilterExpression': 'SK = :m AND lastUpdated < :cut',
        'ExpressionAttributeValues': {':m': 'META', ':cut': cutoff},
        'ProjectionExpression': 'topicId, score',
    }
    stale = []
    while True:
        r = table.scan(**kwargs)
        stale.extend(r.get('Items', []))
        if not r.get('LastEvaluatedKey'): break
        kwargs['ExclusiveStartKey'] = r['LastEvaluatedKey']

    deleted = 0
    for item in stale:
        if int(item.get('score', 0) or 0) >= 30:
            continue  # 流行したトピックは保持
        tid = item['topicId']
        all_items = table.query(KeyConditionExpression=Key('topicId').eq(tid)).get('Items', [])
        with table.batch_writer() as batch:
            for i in all_items:
                batch.delete_item(Key={'topicId': i['topicId'], 'SK': i['SK']})
        deleted += 1
    if deleted:
        print(f'Cleanup: {deleted}件削除')


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
    ogp_fetched = 0  # OGP取得は上位20トピックまで
    for g in groups:
        tid    = topic_fingerprint(g)
        cnt    = len(g)
        genres = dominant_genres(g)
        genre  = genres[0]   # 後方互換用プライマリ
        lang   = dominant_lang(g)
        hist  = recent_counts(tid)
        st    = calc_status(hist, cnt)
        score, media, hb = calc_score(g)

        # 既存データを再利用、なければ今回生成
        existing = table.get_item(Key={'topicId': tid, 'SK': 'META'}).get('Item', {})
        gen_title = existing.get('generatedTitle')
        if not gen_title and cnt >= 2:
            gen_title = generate_title(g)

        gen_summary = existing.get('generatedSummary')
        if not gen_summary and cnt >= 3:
            gen_summary = generate_summary(g)

        # 画像URL: RSSメディアタグ → OGPフォールバック（上位スコアのトピックのみ）
        image_url = existing.get('imageUrl') or next(
            (a.get('imageUrl') for a in g if a.get('imageUrl')), None
        )
        if not image_url and cnt >= 2 and ogp_fetched < 20:
            jp_urls = [a['url'] for a in g if '.jp' in a.get('source', '')]
            check_urls = jp_urls[:2] + [a['url'] for a in g[:3] if a['url'] not in jp_urls]
            for u in check_urls[:3]:
                image_url = fetch_ogp_image(u)
                if image_url:
                    ogp_fetched += 1
                    break

        item = {
            'topicId':          tid,
            'SK':               'META',
            'title':            g[0]['title'],
            'generatedTitle':   gen_title or g[0]['title'],
            'status':           st,
            'genre':            genre,
            'genres':           genres,
            'lang':             lang,
            'articleCount':     cnt,
            'mediaCount':       media,
            'hatenaCount':      hb,
            'score':            score,
            'lastUpdated':      ts_iso,
            'sources':          list({a['source'] for a in g}),
        }
        if gen_summary: item['generatedSummary'] = gen_summary
        if image_url:   item['imageUrl'] = image_url
        table.put_item(Item=item)
        table.put_item(Item={
            'topicId':      tid,
            'SK':           f'SNAP#{ts_key}',
            'articleCount': cnt,
            'score':        score,
            'hatenaCount':  hb,
            'mediaCount':   media,
            'timestamp':    ts_iso,
            'articles': sort_by_pubdate(list({
                a['source']: {
                    'title': a['title'], 'url': a['url'],
                    'source': a['source'], 'pubDate': a['pubDate'],
                } for a in g  # ソースごとに最初の1記事のみ
            }.values()))[:20],
        })
        saved_ids.append(tid)

    if S3_BUCKET:
        topics = get_all_topics()
        write_s3('api/topics.json', {'topics': topics, 'updatedAt': ts_iso})
        for tid in saved_ids:
            meta, snaps, views = get_topic_detail(tid)
            if meta:
                write_s3(f'api/topic/{tid}.json', {
                    'meta': meta,
                    'timeline': [
                        {'timestamp': s['timestamp'],
                         'articleCount': s['articleCount'],
                         'score': s.get('score', 0),
                         'hatenaCount': s.get('hatenaCount', 0),
                         'articles': s.get('articles', [])}
                        for s in snaps
                    ],
                    'views': [
                        {'date': v['date'], 'count': int(v.get('count', 0))}
                        for v in views
                    ],
                })
        print('S3書き出し完了')

    cleanup_stale(now)

    return {'statusCode': 200,
            'body': json.dumps({'articles': len(all_articles), 'topics': len(groups), 'ts': ts_key})}
