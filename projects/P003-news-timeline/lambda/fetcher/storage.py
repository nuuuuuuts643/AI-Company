import json
import os
import re
import time
from datetime import datetime, timezone
from decimal import Decimal

from boto3.dynamodb.conditions import Key

from config import (
    S3_BUCKET, TABLE_NAME,
    SEEN_KEY, SEEN_MAX, SITE_URL, table, s3, dynamodb,
)
from score_utils import apply_time_decay


def dec_convert(obj):
    if isinstance(obj, Decimal):
        return int(obj) if obj == obj.to_integral_value() else float(obj)
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
        'ProjectionExpression': 'topicId,title,generatedTitle,generatedSummary,spreadReason,imageUrl,#s,articleCount,lastUpdated,genre,genres,#l,score,mediaCount,hatenaCount,lastArticleAt,velocityScore,diversityScore,lifecycleStatus,pendingAI,aiGenerated,relatedTopics,sources',
        'ExpressionAttributeNames': {'#s': 'status', '#l': 'lang'},
    }
    while True:
        r = table.scan(**kwargs)
        items.extend(r.get('Items', []))
        if not r.get('LastEvaluatedKey'): break
        kwargs['ExclusiveStartKey'] = r['LastEvaluatedKey']
    items.sort(key=lambda x: int(x.get('score', 0) or 0), reverse=True)
    return items


def validate_topics_exist(topics, skip_tids=None):
    """topics.jsonからDynamoDBに存在しない or 中身がスタブの幽霊エントリを除去する。
    skip_tids: 今回のrunで書いたため確実に存在するtopicIdのset（スキップして高速化）。

    T2026-0428-AE: 「META が存在するか」だけでなく「META が実コンテンツを持つか」も検証。
    具体的には articleCount と lastUpdated が両方揃っているもののみ valid とする。
    旧 force_reset_pending_all() が無条件 update で量産していた
    {topicId, pendingAI, aiGenerated} だけのスタブ META を topics.json から駆除するため。

    T2026-0429-H: ConsistentRead=True を使い、saved_tids も含めて全件検証する。
    背景: handler.py 側の batch_writer 並列書き込みで例外が ThreadPool に閉じ込められ
    f.result() 未呼び出しで silently drop されるケースを観測 (本番 7件/run のゴーストID 永続化)。
    saved_tids を skip すると DDB 書き込み失敗の topicId が topics.json に混入し、processor 側
    (get_topics_by_ids) で「ゴーストID検知 7件/全7件」となり keyPoint 生成が永久に走らなくなる。
    対策: skip_tids の最適化を撤廃し、ConsistentRead=True で just-written 検証も可能にする。
    """
    if not topics:
        return topics
    valid_ids = set()
    stub_dropped = 0
    for i in range(0, len(topics), 100):
        chunk = topics[i:i+100]
        keys  = [{'topicId': t['topicId'], 'SK': 'META'} for t in chunk]
        try:
            resp = dynamodb.batch_get_item(
                RequestItems={TABLE_NAME: {
                    'Keys': keys,
                    'ProjectionExpression': '#tid, articleCount, lastUpdated',
                    'ExpressionAttributeNames': {'#tid': 'topicId'},
                    'ConsistentRead': True,
                }}
            )
            for item in resp.get('Responses', {}).get(TABLE_NAME, []):
                # スタブ META (articleCount/lastUpdated 欠如) は valid にしない
                if 'articleCount' in item and 'lastUpdated' in item:
                    valid_ids.add(item['topicId'])
                else:
                    stub_dropped += 1
        except Exception as e:
            print(f'validate_topics_exist error (chunk {i}): {e}')
            for t in chunk:
                valid_ids.add(t['topicId'])  # エラー時は通す
    if stub_dropped:
        print(f'validate_topics_exist: stub META {stub_dropped}件を除去')
    return [t for t in topics if t['topicId'] in valid_ids]


def get_topic_detail(tid):
    meta_resp = table.get_item(Key={'topicId': tid, 'SK': 'META'})
    meta = meta_resp.get('Item')

    snaps_resp = table.query(
        KeyConditionExpression=Key('topicId').eq(tid) & Key('SK').begins_with('SNAP#'),
        ScanIndexForward=False, Limit=90,
    )
    snaps = sorted(snaps_resp.get('Items', []), key=lambda x: x['SK'])

    views_resp = table.query(
        KeyConditionExpression=Key('topicId').eq(tid) & Key('SK').begins_with('VIEW#'),
        ScanIndexForward=False, Limit=90,
    )
    views = sorted(views_resp.get('Items', []), key=lambda x: x['SK'])

    return meta, snaps, views


def get_latest_snap_articles(tid, max_articles=50):
    """前回 SNAP の articles リストを返す。fetcher で累積マージ用。
    履歴記事数が常に少ない問題への対応(2026-04-27): 各SNAPに前回分の記事もマージしておくことで、
    古い記事がRSSから消えても topic detail の履歴に残るようにする。"""
    try:
        r = table.query(
            KeyConditionExpression=Key('topicId').eq(tid) & Key('SK').begins_with('SNAP#'),
            ScanIndexForward=False, Limit=1,
            ProjectionExpression='articles',
        )
        items = r.get('Items', [])
        if not items:
            return []
        articles = items[0].get('articles', []) or []
        return articles[:max_articles]
    except Exception:
        return []


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

    # 品質フィルタ: active/cooling・記事3件以上・AI生成タイトルあり・株価ティッカー除外
    TICKER_RE = re.compile(r'【\d+[A-Z]?】|：株価|株式情報')
    filtered = [
        t for t in topics
        if t.get('lifecycleStatus', 'active') in ('active', 'cooling', '')
        and int(t.get('articleCount', 0) or 0) >= 3
        and t.get('generatedTitle')
        and not TICKER_RE.search(t.get('generatedTitle', '') + t.get('title', ''))
    ]
    sorted_by_vel = sorted(
        filtered,
        key=lambda x: float(x.get('velocityScore', 0) or 0),
        reverse=True,
    )

    # 同一イベント重複抑制: タイトルのキーワード(3文字以上の単語)が3つ以上共通するトピックは最大2件のみ残す
    _STOP = {'ニュース', '速報', '情報', '中継', '会見', '更新', '記者', '関連'}
    def _key_words(t):
        title = re.sub(r'[【】「」（）！？\[\]\s　・]+', ' ', t.get('generatedTitle', '') + ' ' + t.get('title', ''))
        return {w for w in title.split() if len(w) >= 3 and w not in _STOP}

    deduped, event_counts = [], {}
    for t in sorted_by_vel:
        kw = _key_words(t)
        matched_event = None
        for ev_key, ev_kw in event_counts.items():
            if len(kw & ev_kw) >= 3:
                matched_event = ev_key
                break
        if matched_event is None:
            ev_id = t.get('topicId', '')
            event_counts[ev_id] = kw
            deduped.append((ev_id, t))
        else:
            count = sum(1 for eid, _ in deduped if eid == matched_event)
            if count < 2:
                deduped.append((matched_event, t))
    sorted_topics = [t for _, t in deduped][:20]

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
        summary     = t.get('generatedSummary') or ''
        spread      = t.get('spreadReason') or ''
        full_desc   = (summary + ('　' + spread if spread else '')).strip()
        description = esc(full_desc or t.get('generatedTitle') or t.get('title', ''))
        link        = f'{site_url}/topic.html?id={tid}'
        pub_date    = to_rfc2822(t.get('lastUpdated', updated_at))
        genre       = esc(t.get('genre', ''))
        img_url     = t.get('imageUrl', '')

        enclosure = (
            f'      <enclosure url="{esc(img_url)}" type="image/jpeg" length="0"/>\n'
            if img_url and img_url.startswith('http') else ''
        )

        items_xml += (
            f'    <item>\n'
            f'      <title>{title}</title>\n'
            f'      <description>{description}</description>\n'
            f'      <link>{link}</link>\n'
            f'      <guid isPermaLink="true">{link}</guid>\n'
            f'      <pubDate>{pub_date}</pubDate>\n'
            f'      <category>{genre}</category>\n'
            f'{enclosure}'
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

    static_pages = [
        ('/', '1.0', 'hourly'),
        ('/catchup.html', '0.8', 'daily'),
        ('/about.html',   '0.5', 'monthly'),
        ('/terms.html',   '0.3', 'monthly'),
        ('/privacy.html', '0.3', 'monthly'),
    ]
    urls_xml = ''
    for path, priority, freq in static_pages:
        urls_xml += (
            '  <url>\n'
            f'    <loc>{site_url}{path}</loc>\n'
            f'    <lastmod>{today}</lastmod>\n'
            f'    <changefreq>{freq}</changefreq>\n'
            f'    <priority>{priority}</priority>\n'
            '  </url>\n'
        )

    _TICKER = re.compile(r'【\d+[A-Z]?】|：株価|株式情報')
    for t in topics:
        tid = t.get('topicId', '')
        if not tid:
            continue
        if int(t.get('articleCount', 0) or 0) < 2:
            continue
        if _TICKER.search(t.get('generatedTitle', '') + t.get('title', '')):
            continue
        lastmod  = to_date(t.get('lastUpdated', today))
        # 静的SEO用HTML（Googlebotが直接読める）を使う
        urls_xml += (
            '  <url>\n'
            f'    <loc>{site_url}/topics/{tid}.html</loc>\n'
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
