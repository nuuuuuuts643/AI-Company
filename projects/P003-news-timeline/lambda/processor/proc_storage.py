"""DynamoDB / S3 アクセス層と Slack 通知。"""
import json
import re
import urllib.request
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor, as_completed

from boto3.dynamodb.conditions import Key

from proc_config import S3_BUCKET, SLACK_WEBHOOK, TOPICS_S3_CAP, table, s3

_TICKER_RE = re.compile(r'【\d{3,5}[A-Z]?】|：株価|株式情報\b|株価情報\b')


def needs_ai_processing(item):
    """このトピックがAI処理を必要とするかを判定。

    以下のいずれかに該当する場合は処理が必要:
    - aiGenerated=False または未設定
    - storyTimeline が空または未設定（4セクション形式未生成）
    - pendingAI=True（fetcher が新記事を検知してフラグを立てた）
    """
    if item.get('pendingAI'):
        return True
    if not item.get('aiGenerated'):
        return True
    timeline = item.get('storyTimeline')
    if not timeline or (isinstance(timeline, list) and len(timeline) == 0):
        return True
    return False


def get_pending_topics(max_topics=100):
    """S3のpending_ai.jsonからトピックIDを取得し、DynamoDBで個別に取得。"""
    pending_ids = []
    if S3_BUCKET:
        try:
            resp = s3.get_object(Bucket=S3_BUCKET, Key='api/pending_ai.json')
            data = json.loads(resp['Body'].read())
            pending_ids = data.get('topicIds', [])
        except Exception:
            pass

    if pending_ids:
        items = []
        still_pending = []
        # 全IDを走査。削除済み・処理済みIDを取り除く（上限なし）。
        # 収集アイテム数がmax_topics*3を超えても走査を続け、削除済みIDの清掃は常に行う。
        for tid in pending_ids:
            try:
                r = table.get_item(
                    Key={'topicId': tid, 'SK': 'META'},
                    ProjectionExpression='topicId,title,articleCount,score,velocityScore,generatedTitle,generatedSummary,storyTimeline,storyPhase,aiGenerated,pendingAI',
                )
                item = r.get('Item')
                if item and needs_ai_processing(item):
                    still_pending.append(tid)
                    if len(items) < max_topics * 3:
                        items.append(item)
                # 存在しないIDまたは処理済みIDはstill_pendingに追加しない（自動クリーンアップ）
            except Exception:
                still_pending.append(tid)

        # pending_ai.jsonを処理済みIDを除去した状態に更新
        if S3_BUCKET and len(still_pending) < len(pending_ids):
            try:
                s3.put_object(
                    Bucket=S3_BUCKET, Key='api/pending_ai.json',
                    Body=json.dumps({'topicIds': still_pending}),
                    ContentType='application/json',
                )
                print(f'[get_pending_topics] pending_ai.json 更新: {len(pending_ids)} → {len(still_pending)} 件')
            except Exception as e:
                print(f'[get_pending_topics] pending_ai.json 更新失敗: {e}')

        # velocityScore 優先（急上昇中のホットトピックを先に処理）、同値時は score で補助
        items.sort(key=lambda x: (float(x.get('velocityScore', 0) or 0), int(x.get('score', 0) or 0)), reverse=True)
        return items[:max_topics]

    # フォールバック: DynamoDBスキャン（pending_ai.json未作成時のみ）
    print('get_pending_topics: S3未作成のためDynamoDBフォールバック')
    items, kwargs = [], {
        'FilterExpression':        'SK = :m AND pendingAI = :t',
        'ExpressionAttributeValues': {':m': 'META', ':t': True},
        'ProjectionExpression':    'topicId,title,articleCount,score,velocityScore,generatedTitle,generatedSummary,storyTimeline,storyPhase,aiGenerated,pendingAI',
    }
    while True:
        r = table.scan(**kwargs)
        items.extend(r.get('Items', []))
        if not r.get('LastEvaluatedKey'): break
        kwargs['ExclusiveStartKey'] = r['LastEvaluatedKey']
    items.sort(key=lambda x: int(x.get('score', 0) or 0), reverse=True)
    return items[:max_topics]


def get_latest_articles_for_topic(tid):
    """最新SNAPを優先しつつ過去スナップも合わせて最大20件の記事を返す（重複排除済み）。"""
    try:
        r = table.query(
            KeyConditionExpression=Key('topicId').eq(tid) & Key('SK').begins_with('SNAP#'),
            ScanIndexForward=False,
            Limit=5,
        )
        seen_urls = set()
        articles = []
        for item in r.get('Items', []):
            for a in item.get('articles', []):
                url = a.get('url', '')
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    articles.append(a)
                    if len(articles) >= 20:
                        return articles
        return articles
    except Exception as e:
        print(f'get_latest_articles_for_topic error [{tid}]: {e}')
    return []


def update_topic_with_ai(tid, gen_title, gen_story, ai_succeeded=False):
    """Claude 生成タイトル・ストーリーで DynamoDB META を更新。

    Args:
        tid:          トピックID
        gen_title:    str | None — 生成タイトル
        gen_story:    dict | None — {aiSummary, spreadReason, forecast, timeline, phase}
        ai_succeeded: bool — Claude が実際に成功したか（False なら aiGenerated は立てない）
    """
    try:
        # aiGenerated は Claude が実際に成功した時だけ True にする
        # 失敗時に True にしてしまうと次回実行でスキップされてしまう（再発防止）
        update_expr = 'SET pendingAI = :f'
        expr_values = {':f': False}
        if ai_succeeded:
            update_expr += ', aiGenerated = :t'
            expr_values[':t'] = True
        if gen_title:
            update_expr += ', generatedTitle = :title'
            expr_values[':title'] = gen_title
        if gen_story:
            if gen_story.get('aiSummary'):
                update_expr += ', generatedSummary = :summary'
                expr_values[':summary'] = gen_story['aiSummary']
            if gen_story.get('spreadReason'):
                update_expr += ', spreadReason = :sr'
                expr_values[':sr'] = gen_story['spreadReason']
            if gen_story.get('forecast'):
                update_expr += ', forecast = :fc'
                expr_values[':fc'] = gen_story['forecast']
            if gen_story.get('timeline') is not None:
                update_expr += ', storyTimeline = :timeline'
                expr_values[':timeline'] = gen_story['timeline']
            if gen_story.get('phase'):
                update_expr += ', storyPhase = :phase'
                expr_values[':phase'] = gen_story['phase']
        table.update_item(
            Key={'topicId': tid, 'SK': 'META'},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
        )
    except Exception as e:
        print(f'update_topic_with_ai error [{tid}]: {e}')


def _is_ticker_topic(t):
    title = t.get('generatedTitle') or t.get('title') or ''
    return bool(_TICKER_RE.search(title))


def _cap_topics(items):
    filtered = [t for t in items if not _is_ticker_topic(t)]
    filtered.sort(key=lambda x: int(x.get('score', 0) or 0), reverse=True)
    return filtered[:TOPICS_S3_CAP]


def get_all_topics_for_s3():
    """S3のtopics.jsonから読む（DynamoDBフルスキャン不要）。TOPICS_S3_CAP件にキャップ。
    trendingKeywordsを含む既存のメタデータも返す（processorがwrite時に保持するため）。"""
    if S3_BUCKET:
        try:
            resp = s3.get_object(Bucket=S3_BUCKET, Key='api/topics.json')
            data = json.loads(resp['Body'].read())
            items = data.get('topics', [])
            if items:
                return _cap_topics(items), data.get('trendingKeywords', [])
        except Exception as e:
            print(f'get_all_topics_for_s3 S3 error: {e}')
    items, kwargs = [], {
        'FilterExpression': 'SK = :m',
        'ExpressionAttributeValues': {':m': 'META'},
    }
    while True:
        r = table.scan(**kwargs)
        items.extend(r.get('Items', []))
        if not r.get('LastEvaluatedKey'): break
        kwargs['ExclusiveStartKey'] = r['LastEvaluatedKey']
    return _cap_topics(items), []


def dec_convert(obj):
    if isinstance(obj, Decimal):
        return int(obj) if obj == obj.to_integral_value() else float(obj)
    raise TypeError


def write_s3(key, data):
    if not S3_BUCKET:
        return
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=json.dumps(data, default=dec_convert, ensure_ascii=False).encode('utf-8'),
        ContentType='application/json',
        CacheControl='max-age=60',
    )


def update_topic_s3_file(tid, upd):
    """個別トピックS3ファイルのmetaにAIフィールドをマージ（pendingAI解除含む）。"""
    if not S3_BUCKET:
        return
    key = f'api/topic/{tid}.json'
    try:
        resp = s3.get_object(Bucket=S3_BUCKET, Key=key)
        data = json.loads(resp['Body'].read())
        meta = data.get('meta', {})
        meta.pop('pendingAI', None)
        if upd.get('generatedTitle'):
            meta['generatedTitle'] = upd['generatedTitle']
        if upd.get('generatedSummary'):
            meta['generatedSummary'] = upd['generatedSummary']
        if upd.get('storyTimeline') is not None:
            meta['storyTimeline'] = upd['storyTimeline']
        if upd.get('storyPhase'):
            meta['storyPhase'] = upd['storyPhase']
        if upd.get('spreadReason'):
            meta['spreadReason'] = upd['spreadReason']
        if upd.get('forecast'):
            meta['forecast'] = upd['forecast']
        if upd.get('aiGenerated'):
            meta['aiGenerated'] = True
        data['meta'] = meta
        write_s3(key, data)
    except Exception:
        pass


def update_topic_s3_files_parallel(ai_updates, max_workers=5):
    """ai_updatesの全トピックの個別S3ファイルをAIデータで並列更新。"""
    if not ai_updates or not S3_BUCKET:
        return
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(update_topic_s3_file, tid, upd): tid for tid, upd in ai_updates.items()}
        for _ in as_completed(futures):
            pass
    print(f'[Processor] 個別S3ファイル更新完了 ({len(ai_updates)}件)')


def generate_and_upload_rss(topics):
    """上位トピックからRSS 2.0 フィードを生成してS3にアップロード。"""
    if not S3_BUCKET:
        return
    from datetime import datetime
    from email.utils import formatdate
    import time as _time

    active = [t for t in topics if t.get('lifecycleStatus') in ('active', 'cooling', '')]
    active.sort(key=lambda x: float(x.get('velocityScore', 0) or 0), reverse=True)

    # 同一イベント重複抑制: キーワード3つ以上共通するトピックは最大2件のみ
    _STOP = {'ニュース', '速報', '情報', '中継', '会見', '更新'}
    def _kw(t):
        import re as _re
        title = _re.sub(r'[【】「」（）！？\[\]\s　・]+', ' ', t.get('generatedTitle', '') + ' ' + t.get('title', ''))
        return {w for w in title.split() if len(w) >= 3 and w not in _STOP}
    deduped, event_counts = [], {}
    for t in active:
        kw = _kw(t)
        matched = None
        for ev, ev_kw in event_counts.items():
            if len(kw & ev_kw) >= 3:
                matched = ev
                break
        if matched is None:
            ev_id = t.get('topicId', '')
            event_counts[ev_id] = kw
            deduped.append((ev_id, t))
        else:
            if sum(1 for eid, _ in deduped if eid == matched) < 2:
                deduped.append((matched, t))
    top = [t for _, t in deduped][:40]

    def to_rfc822(ts):
        try:
            if not ts:
                return formatdate()
            if isinstance(ts, (int, float)):
                return formatdate(_time.mktime(datetime.utcfromtimestamp(ts).timetuple()))
            return formatdate(_time.mktime(datetime.fromisoformat(str(ts).replace('Z', '+00:00')).timetuple()))
        except Exception:
            return formatdate()

    def xml_escape(s):
        return str(s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

    items = []
    for t in top:
        tid = t.get('topicId', '')
        title = xml_escape(t.get('generatedTitle') or t.get('title') or 'Flotopic')
        desc  = xml_escape((t.get('generatedSummary') or '')[:200])
        link  = f'https://flotopic.com/topic.html?id={tid}'
        pub   = to_rfc822(t.get('lastArticleAt') or t.get('lastUpdated'))
        genre = xml_escape((t.get('genres') or [t.get('genre', '総合')])[0])
        items.append(
            f'  <item>\n'
            f'    <title>{title}</title>\n'
            f'    <link>{link}</link>\n'
            f'    <description>{desc}</description>\n'
            f'    <pubDate>{pub}</pubDate>\n'
            f'    <guid isPermaLink="true">{link}</guid>\n'
            f'    <category>{genre}</category>\n'
            f'  </item>'
        )

    rss = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
        '<channel>\n'
        '  <title>Flotopic — 話題の盛り上がりをAIで追う</title>\n'
        '  <link>https://flotopic.com/</link>\n'
        '  <description>AIがまとめた注目トピックの最新フィード</description>\n'
        '  <language>ja</language>\n'
        '  <ttl>30</ttl>\n'
        f'  <atom:link href="https://flotopic.com/rss.xml" rel="self" type="application/rss+xml"/>\n'
        + '\n'.join(items) + '\n'
        '</channel>\n'
        '</rss>\n'
    )

    try:
        s3.put_object(
            Bucket=S3_BUCKET,
            Key='rss.xml',
            Body=rss.encode('utf-8'),
            ContentType='application/rss+xml',
            CacheControl='max-age=1800',
        )
        print(f'[Processor] rss.xml 更新完了 ({len(top)}件)')
    except Exception as e:
        print(f'[Processor] rss.xml 更新エラー: {e}')


def generate_and_upload_news_sitemap(topics):
    """Google News Sitemap (news sitemap) を生成してS3にアップロード。
    直近2日以内に更新されたactive/coolingトピックのみ対象。
    """
    if not S3_BUCKET:
        return
    from datetime import datetime, timezone, timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(days=2)
    news_topics = []
    for t in topics:
        if t.get('lifecycleStatus') not in ('active', 'cooling'):
            continue
        if not t.get('generatedTitle') and not t.get('title'):
            continue
        raw_ts = t.get('lastArticleAt') or t.get('lastUpdated')
        if not raw_ts:
            continue
        try:
            if isinstance(raw_ts, (int, float)):
                ts = datetime.fromtimestamp(float(raw_ts), tz=timezone.utc)
            else:
                ts = datetime.fromisoformat(str(raw_ts).replace('Z', '+00:00'))
            if ts < cutoff:
                continue
            news_topics.append((t, ts))
        except Exception:
            continue

    news_topics.sort(key=lambda x: x[1], reverse=True)
    news_topics = news_topics[:50]

    def xml_escape(s):
        return str(s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    items = []
    for t, ts in news_topics:
        tid = t.get('topicId', '')
        title = xml_escape(t.get('generatedTitle') or t.get('title', ''))
        pub_iso = ts.strftime('%Y-%m-%dT%H:%M:%S+00:00')
        genres = t.get('genres') or ([t['genre']] if t.get('genre') else ['総合'])
        kw = xml_escape(', '.join(genres[:3]))
        items.append(
            f'  <url>\n'
            f'    <loc>https://flotopic.com/topic.html?id={tid}</loc>\n'
            f'    <news:news>\n'
            f'      <news:publication>\n'
            f'        <news:name>Flotopic</news:name>\n'
            f'        <news:language>ja</news:language>\n'
            f'      </news:publication>\n'
            f'      <news:publication_date>{pub_iso}</news:publication_date>\n'
            f'      <news:title>{title}</news:title>\n'
            f'      <news:keywords>{kw}</news:keywords>\n'
            f'    </news:news>\n'
            f'  </url>'
        )

    ns = 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:news="http://www.google.com/schemas/sitemap-news/0.9"'
    sitemap = f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset {ns}>\n'
    sitemap += '\n'.join(items)
    sitemap += '\n</urlset>\n'

    try:
        s3.put_object(
            Bucket=S3_BUCKET,
            Key='news-sitemap.xml',
            Body=sitemap.encode('utf-8'),
            ContentType='application/xml',
            CacheControl='no-cache, must-revalidate',
        )
        print(f'[Processor] news-sitemap.xml 更新完了 ({len(items)}件)')
    except Exception as e:
        print(f'[Processor] news-sitemap.xml 更新エラー: {e}')


def generate_and_upload_sitemap(topics):
    """topics リストから sitemap.xml を生成して S3 にアップロード。"""
    if not S3_BUCKET:
        return
    from datetime import datetime
    today = datetime.utcnow().strftime('%Y-%m-%d')

    active = [t for t in topics if t.get('lifecycleStatus') in ('active', 'cooling', '')]
    active.sort(key=lambda x: float(x.get('velocityScore', 0) or 0), reverse=True)
    top = active[:200]

    urls = [
        f'  <url>\n    <loc>https://flotopic.com/</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>hourly</changefreq>\n    <priority>1.0</priority>\n  </url>',
        f'  <url>\n    <loc>https://flotopic.com/catchup.html</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>daily</changefreq>\n    <priority>0.8</priority>\n  </url>',
        f'  <url>\n    <loc>https://flotopic.com/legacy.html</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>daily</changefreq>\n    <priority>0.6</priority>\n  </url>',
        f'  <url>\n    <loc>https://flotopic.com/about.html</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>monthly</changefreq>\n    <priority>0.5</priority>\n  </url>',
        f'  <url>\n    <loc>https://flotopic.com/terms.html</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>monthly</changefreq>\n    <priority>0.3</priority>\n  </url>',
        f'  <url>\n    <loc>https://flotopic.com/privacy.html</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>monthly</changefreq>\n    <priority>0.3</priority>\n  </url>',
    ]
    for t in top:
        tid = t.get('topicId', '')
        if not tid:
            continue
        last = (t.get('lastUpdated') or today)[:10]
        urls.append(f'  <url>\n    <loc>https://flotopic.com/topic.html?id={tid}</loc>\n    <lastmod>{last}</lastmod>\n    <changefreq>hourly</changefreq>\n    <priority>0.7</priority>\n  </url>')

    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sitemap += '\n'.join(urls)
    sitemap += '\n</urlset>\n'

    try:
        s3.put_object(
            Bucket=S3_BUCKET,
            Key='sitemap.xml',
            Body=sitemap.encode('utf-8'),
            ContentType='application/xml',
            CacheControl='no-cache, must-revalidate',
        )
        print(f'[Processor] sitemap.xml 更新完了 ({len(top)+6}件)')
    except Exception as e:
        print(f'[Processor] sitemap.xml 更新エラー: {e}')


def notify_slack_error(error_msg: str):
    if not SLACK_WEBHOOK:
        return
    try:
        msg = f'🚨 *Processor エラー*\n{error_msg}'
        body = json.dumps({'text': msg}).encode('utf-8')
        req  = urllib.request.Request(
            SLACK_WEBHOOK, data=body,
            headers={'Content-Type': 'application/json'}, method='POST',
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
    except Exception as e:
        print(f'Slack通知エラー: {e}')
