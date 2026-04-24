import json
import os
import time
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from boto3.dynamodb.conditions import Key

from config import (
    S3_BUCKET, TABLE_NAME, CACHE_SK_PREFIX, CLAUDE_CALL_CONDITIONS,
    SEEN_KEY, SEEN_MAX, SITE_URL, table, s3,
)
from score_utils import apply_time_decay


def dec_convert(obj):
    if isinstance(obj, Decimal): return int(obj)
    raise TypeError


def write_s3(key, data):
    if not S3_BUCKET: return
    s3.put_object(
        Bucket=S3_BUCKET, Key=key,
        Body=json.dumps(data, default=dec_convert, ensure_ascii=False).encode('utf-8'),
        ContentType='application/json', CacheControl='max-age=60',
    )


def get_all_topics():
    """S3のtopics.jsonから読む（DynamoDBフルスキャンを避けてコスト削減）。"""
    if S3_BUCKET:
        try:
            resp = s3.get_object(Bucket=S3_BUCKET, Key='api/topics.json')
            data = json.loads(resp['Body'].read())
            items = data.get('topics', [])
            if items:
                for item in items:
                    raw_score = int(item.get('score', 0) or 0)
                    last_ts   = int(item.get('lastArticleAt', 0) or 0)
                    item['score'] = apply_time_decay(raw_score, last_ts)
                items.sort(key=lambda x: int(x.get('score', 0) or 0), reverse=True)
                return items
        except s3.exceptions.NoSuchKey:
            pass
        except Exception as e:
            print(f'get_all_topics S3 error: {e}')

    print('get_all_topics: S3未作成のためDynamoDBフォールバック')
    items, kwargs = [], {
        'FilterExpression': 'SK = :m',
        'ExpressionAttributeValues': {':m': 'META'},
        'ProjectionExpression': 'topicId,title,generatedTitle,generatedSummary,imageUrl,#s,articleCount,lastUpdated,genre,genres,#l,score,mediaCount,hatenaCount,lastArticleAt,velocityScore,lifecycleStatus,pendingAI,aiGenerated,relatedTopics,sources',
        'ExpressionAttributeNames': {'#s': 'status', '#l': 'lang'},
    }
    while True:
        r = table.scan(**kwargs)
        items.extend(r.get('Items', []))
        if not r.get('LastEvaluatedKey'): break
        kwargs['ExclusiveStartKey'] = r['LastEvaluatedKey']
    for item in items:
        raw_score = int(item.get('score', 0) or 0)
        last_ts   = int(item.get('lastArticleAt', 0) or 0)
        item['score'] = apply_time_decay(raw_score, last_ts)
    items.sort(key=lambda x: int(x.get('score', 0) or 0), reverse=True)
    return items


def validate_topics_exist(topics, skip_tids=None):
    """topics.jsonからDynamoDBに存在しない幽霊エントリをbatch_get_itemで除去する。
    skip_tids: 今回のrunで書いたため確実に存在するtopicIdのset（スキップして高速化）。
    """
    if not topics:
        return topics
    skip = skip_tids or set()
    to_check = [t for t in topics if t['topicId'] not in skip]
    if not to_check:
        return topics
    valid_ids = set(skip)
    client = table.meta.client
    for i in range(0, len(to_check), 100):
        chunk = to_check[i:i+100]
        keys  = [{'topicId': {'S': t['topicId']}, 'SK': {'S': 'META'}} for t in chunk]
        try:
            resp = client.batch_get_item(
                RequestItems={TABLE_NAME: {'Keys': keys, 'ProjectionExpression': 'topicId'}}
            )
            for item in resp.get('Responses', {}).get(TABLE_NAME, []):
                valid_ids.add(item['topicId']['S'])
        except Exception as e:
            print(f'validate_topics_exist error (chunk {i}): {e}')
            for t in chunk:
                valid_ids.add(t['topicId'])  # エラー時は通す
    return [t for t in topics if t['topicId'] in valid_ids]


def get_topic_detail(tid):
    r     = table.query(KeyConditionExpression=Key('topicId').eq(tid))
    items = r.get('Items', [])
    meta  = next((i for i in items if i['SK'] == 'META'), None)
    snaps = sorted([i for i in items if i['SK'].startswith('SNAP#')], key=lambda x: x['SK'])
    views = sorted([i for i in items if i['SK'].startswith('VIEW#')], key=lambda x: x['SK'])
    return meta, snaps, views


def get_cached_summary(topic_id, articles_hash):
    try:
        resp = table.get_item(Key={
            'topicId': topic_id,
            'SK': f'{CACHE_SK_PREFIX}{articles_hash}'
        })
        item = resp.get('Item')
        if not item:
            return None, None
        cached_at = float(item.get('cachedAtTs', 0))
        if time.time() - cached_at > CLAUDE_CALL_CONDITIONS['cache_ttl_hours'] * 3600:
            return None, None
        return item.get('generatedTitle'), item.get('generatedSummary')
    except Exception as e:
        print(f'get_cached_summary error: {e}')
        return None, None


def save_summary_cache(topic_id, articles_hash, title, summary):
    try:
        now_ts = int(time.time())
        ttl_ts = now_ts + int(CLAUDE_CALL_CONDITIONS['cache_ttl_hours'] * 3600)
        item = {
            'topicId': topic_id,
            'SK': f'{CACHE_SK_PREFIX}{articles_hash}',
            'cachedAtTs': Decimal(str(now_ts)),
            'ttl': Decimal(str(ttl_ts)),
        }
        if title:   item['generatedTitle']   = title
        if summary: item['generatedSummary'] = summary
        table.put_item(Item=item)
    except Exception as e:
        print(f'save_summary_cache error: {e}')


def recent_counts(tid, n=5):
    try:
        r = table.query(
            KeyConditionExpression=Key('topicId').eq(tid) & Key('SK').begins_with('SNAP#'),
            ScanIndexForward=False, Limit=n,
            ProjectionExpression='articleCount, #ts',
            ExpressionAttributeNames={'#ts': 'timestamp'},
        )
        items = r.get('Items', [])
        return [(int(item['articleCount']), item.get('timestamp', '')) for item in items]
    except Exception:
        return []


def calc_velocity(history_with_ts, current_count, now_iso):
    if not history_with_ts:
        return 0
    prev_count, prev_ts = history_with_ts[0]
    if not prev_ts:
        return 0
    try:
        t_now  = datetime.fromisoformat(now_iso.replace('Z', '+00:00'))
        t_prev = datetime.fromisoformat(prev_ts.replace('Z', '+00:00'))
        elapsed_hours = (t_now - t_prev).total_seconds() / 3600.0
        if elapsed_hours < 0.01:
            return 0
        velocity = (current_count - prev_count) / elapsed_hours
        return int(round(velocity * 100))
    except Exception:
        return 0


def load_seen_articles():
    if not S3_BUCKET:
        return set()
    try:
        resp = s3.get_object(Bucket=S3_BUCKET, Key=SEEN_KEY)
        data = json.loads(resp['Body'].read())
        return set(data.get('urls', []))
    except s3.exceptions.NoSuchKey:
        return set()
    except Exception as e:
        print(f'load_seen_articles error: {e}')
        return set()


def save_seen_articles(current_urls: set):
    if not S3_BUCKET:
        return
    url_list = list(current_urls)[:SEEN_MAX]
    try:
        s3.put_object(
            Bucket=S3_BUCKET, Key=SEEN_KEY,
            Body=json.dumps(
                {'urls': url_list, 'savedAt': datetime.now(timezone.utc).isoformat()},
                ensure_ascii=False,
            ).encode('utf-8'),
            ContentType='application/json', CacheControl='no-cache',
        )
    except Exception as e:
        print(f'save_seen_articles error: {e}')


def generate_rss(topics, updated_at):
    if not S3_BUCKET:
        return

    site_url = SITE_URL

    sorted_topics = sorted(
        topics,
        key=lambda x: int(x.get('articleCount', 0) or 0),
        reverse=True,
    )[:20]

    def esc(text):
        if not text:
            return ''
        return (
            str(text)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&apos;')
        )

    def to_rfc2822(iso_str):
        try:
            dt = datetime.fromisoformat(str(iso_str).replace('Z', '+00:00'))
            return dt.strftime('%a, %d %b %Y %H:%M:%S +0000')
        except Exception:
            return datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000')

    items_xml = ''
    for t in sorted_topics:
        tid         = t.get('topicId', '')
        title       = esc(t.get('generatedTitle') or t.get('title', ''))
        description = esc(t.get('generatedSummary') or t.get('generatedTitle') or t.get('title', ''))
        link        = f'{site_url}/topic.html?id={tid}'
        pub_date    = to_rfc2822(t.get('lastUpdated', updated_at))
        genre       = esc(t.get('genre', ''))

        items_xml += (
            f'    <item>\n'
            f'      <title>{title}</title>\n'
            f'      <description>{description}</description>\n'
            f'      <link>{link}</link>\n'
            f'      <guid isPermaLink="true">{link}</guid>\n'
            f'      <pubDate>{pub_date}</pubDate>\n'
            f'      <category>{genre}</category>\n'
            f'    </item>\n'
        )

    now_rfc2822 = to_rfc2822(updated_at)
    rss_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
        '  <channel>\n'
        '    <title>Flotopic</title>\n'
        f'    <link>{site_url}/</link>\n'
        '    <description>話題の流れをAIで追う日本語ニュースまとめ</description>\n'
        '    <language>ja</language>\n'
        f'    <lastBuildDate>{now_rfc2822}</lastBuildDate>\n'
        '    <ttl>30</ttl>\n'
        f'    <atom:link href="{site_url}/rss.xml" rel="self" type="application/rss+xml"/>\n'
        f'{items_xml}'
        '  </channel>\n'
        '</rss>\n'
    )

    try:
        s3.put_object(
            Bucket=S3_BUCKET, Key='rss.xml',
            Body=rss_xml.encode('utf-8'),
            ContentType='application/rss+xml; charset=utf-8',
            CacheControl='max-age=1800',
        )
        print(f'RSS生成完了 ({len(sorted_topics)}件)')
    except Exception as e:
        print(f'RSS生成エラー: {e}')


def generate_sitemap(topics):
    if not S3_BUCKET:
        return

    site_url = SITE_URL

    def to_date(iso_str):
        try:
            dt = datetime.fromisoformat(str(iso_str).replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d')
        except Exception:
            return datetime.now(timezone.utc).strftime('%Y-%m-%d')

    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    urls_xml = (
        '  <url>\n'
        f'    <loc>{site_url}/</loc>\n'
        '    <changefreq>hourly</changefreq>\n'
        '    <priority>1.0</priority>\n'
        '  </url>\n'
    )

    for t in topics:
        tid = t.get('topicId', '')
        if not tid:
            continue
        lastmod  = to_date(t.get('lastUpdated', today))
        urls_xml += (
            '  <url>\n'
            f'    <loc>{site_url}/topic.html?id={tid}</loc>\n'
            f'    <lastmod>{lastmod}</lastmod>\n'
            '    <changefreq>hourly</changefreq>\n'
            '    <priority>0.8</priority>\n'
            '  </url>\n'
        )

    sitemap_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'{urls_xml}'
        '</urlset>\n'
    )

    try:
        s3.put_object(
            Bucket=S3_BUCKET, Key='sitemap.xml',
            Body=sitemap_xml.encode('utf-8'),
            ContentType='application/xml',
            CacheControl='max-age=3600',
        )
        print(f'サイトマップ生成完了 ({len(topics)}件)')
    except Exception as e:
        print(f'サイトマップ生成エラー: {e}')
