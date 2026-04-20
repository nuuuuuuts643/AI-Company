import json
import os
import re
import hashlib
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key

TABLE_NAME = os.environ.get('TABLE_NAME', 'p003-topics')
REGION     = os.environ.get('REGION', 'ap-northeast-1')

dynamodb = boto3.resource('dynamodb', region_name=REGION)
table    = dynamodb.Table(TABLE_NAME)

RSS_FEEDS = [
    'https://www3.nhk.or.jp/rss/news/cat0.xml',
    'https://news.yahoo.co.jp/rss/topics/top-picks.xml',
    'https://feeds.bbci.co.uk/news/rss.xml',
    'https://rss.cnn.com/rss/edition.rss',
]

JACCARD_THRESHOLD = 0.3


def normalize(text):
    text = re.sub(r'[【】「」『』（）()\[\]！？!?\s\u3000]+', ' ', text.lower())
    return {w for w in text.split() if len(w) > 1}


def jaccard(a, b):
    sa, sb = normalize(a), normalize(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def fetch_rss(url):
    articles = []
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'NewsTimeline/1.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read()
        root = ET.fromstring(content)
        for item in root.findall('.//item'):
            title   = (item.findtext('title')       or '').strip()
            link    = (item.findtext('link')         or '').strip()
            pubdate = (item.findtext('pubDate')      or '').strip()
            desc    = (item.findtext('description')  or '').strip()[:200]
            if title and link:
                articles.append({
                    'title':   title,
                    'url':     link,
                    'pubDate': pubdate,
                    'desc':    desc,
                    'source':  url.split('/')[2],
                })
    except Exception as e:
        print(f'RSS fetch error [{url}]: {e}')
    return articles


def cluster(articles):
    groups  = []
    used    = [False] * len(articles)
    for i, a in enumerate(articles):
        if used[i]:
            continue
        g = [a]
        used[i] = True
        for j in range(i + 1, len(articles)):
            if not used[j] and jaccard(a['title'], articles[j]['title']) >= JACCARD_THRESHOLD:
                g.append(articles[j])
                used[j] = True
        groups.append(g)
    return groups


def topic_id(title):
    return hashlib.md5(title.encode()).hexdigest()[:16]


def recent_counts(tid, n=5):
    try:
        r = table.query(
            KeyConditionExpression=Key('topicId').eq(tid) & Key('SK').begins_with('SNAP#'),
            ScanIndexForward=False,
            Limit=n,
            ProjectionExpression='articleCount',
        )
        return [item['articleCount'] for item in r.get('Items', [])]
    except Exception:
        return []


def status(history, current):
    counts = list(reversed(history)) + [current]
    if len(counts) < 2:
        return 'rising'
    diff = counts[-1] - counts[0]
    if diff > 0:
        return 'rising'
    if diff < -1:
        return 'declining'
    return 'peak'


def lambda_handler(event, context):
    all_articles = []
    for url in RSS_FEEDS:
        fetched = fetch_rss(url)
        all_articles.extend(fetched)
        print(f'{url}: {len(fetched)} articles')

    print(f'Total articles: {len(all_articles)}')
    groups = cluster(all_articles)
    print(f'Topics: {len(groups)}')

    now       = datetime.now(timezone.utc)
    ts_key    = now.strftime('%Y%m%dT%H%M%SZ')
    ts_iso    = now.isoformat()

    for g in groups:
        rep  = g[0]
        tid  = topic_id(rep['title'])
        cnt  = len(g)
        hist = recent_counts(tid)
        st   = status(hist, cnt)

        table.put_item(Item={
            'topicId':     tid,
            'SK':          'META',
            'title':       rep['title'],
            'status':      st,
            'articleCount': cnt,
            'lastUpdated': ts_iso,
            'sources':     list({a['source'] for a in g}),
        })

        table.put_item(Item={
            'topicId':     tid,
            'SK':          f'SNAP#{ts_key}',
            'articleCount': cnt,
            'timestamp':   ts_iso,
            'articles': [
                {'title': a['title'], 'url': a['url'],
                 'source': a['source'], 'pubDate': a['pubDate']}
                for a in g[:20]
            ],
        })

    return {
        'statusCode': 200,
        'body': json.dumps({'articles': len(all_articles), 'topics': len(groups), 'ts': ts_key}),
    }
