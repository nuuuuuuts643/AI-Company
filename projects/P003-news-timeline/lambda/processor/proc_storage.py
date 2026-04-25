"""DynamoDB / S3 アクセス層と Slack 通知。"""
import json
import urllib.request
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor, as_completed

from boto3.dynamodb.conditions import Key

from proc_config import S3_BUCKET, SLACK_WEBHOOK, TOPICS_S3_CAP, table, s3


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
        for tid in pending_ids[:max_topics * 2]:
            try:
                r = table.get_item(
                    Key={'topicId': tid, 'SK': 'META'},
                    ProjectionExpression='topicId,title,articleCount,score,velocityScore,generatedTitle,generatedSummary,storyTimeline,storyPhase,aiGenerated,pendingAI',
                )
                item = r.get('Item')
                if item and needs_ai_processing(item):
                    items.append(item)
            except Exception:
                pass
        items.sort(key=lambda x: int(x.get('score', 0) or 0), reverse=True)
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


def _cap_topics(items):
    items.sort(key=lambda x: int(x.get('score', 0) or 0), reverse=True)
    return items[:TOPICS_S3_CAP]


def get_all_topics_for_s3():
    """S3のtopics.jsonから読む（DynamoDBフルスキャン不要）。TOPICS_S3_CAP件にキャップ。"""
    if S3_BUCKET:
        try:
            resp = s3.get_object(Bucket=S3_BUCKET, Key='api/topics.json')
            data = json.loads(resp['Body'].read())
            items = data.get('topics', [])
            if items:
                return _cap_topics(items)
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
    return _cap_topics(items)


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
        meta['pendingAI'] = False
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
