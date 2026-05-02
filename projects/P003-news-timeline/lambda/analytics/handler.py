"""
Flotopic アナリティクス Lambda
- GET /analytics/trending       → 直近24h の view/favorite 数でソートされた topicId リスト
- GET /analytics/user/{userId}  → ユーザー行動サマリー（総閲覧数・お気に入りジャンル・活動時間帯）

集計結果は S3 api/analytics.json にキャッシュ（1時間ごと更新）。
PII は返さない。集計データのみ。

DynamoDB テーブル: flotopic-analytics
  PK=userId / SK=eventType#timestamp#topicId
"""

import json
import os
import time
from collections import defaultdict
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

REGION          = os.environ.get('REGION', 'ap-northeast-1')
ANALYTICS_TABLE = os.environ.get('ANALYTICS_TABLE', 'flotopic-analytics')
S3_BUCKET       = os.environ.get('S3_BUCKET', 'p003-news-946554699567')
CACHE_KEY       = 'api/analytics.json'
CACHE_TTL_SEC   = 3600  # 1時間
GOOGLE_TOKENINFO_URL = 'https://oauth2.googleapis.com/tokeninfo?id_token='
GOOGLE_CLIENT_ID  = os.environ.get('GOOGLE_CLIENT_ID', '')
USERS_TABLE     = os.environ.get('USERS_TABLE', 'flotopic-users')

dynamodb = boto3.resource('dynamodb', region_name=REGION)
s3       = boto3.client('s3', region_name=REGION)

CORS_HEADERS = {
    'Content-Type':                 'application/json; charset=utf-8',
    'Access-Control-Allow-Origin':  'https://flotopic.com',
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
    'Access-Control-Max-Age':       '86400',
}


def _verify_user_or_403(event, user_id: str):
    """T2026-0502-SEC7: Authorization Bearer の Google ID トークンで本人検証。
    Returns: None=OK / dict=エラーレスポンス。"""
    from urllib.request import urlopen
    from urllib.error import URLError, HTTPError
    headers = (event or {}).get('headers') or {}
    auth = headers.get('authorization') or headers.get('Authorization') or ''
    if not auth.startswith('Bearer '):
        return resp(401, {'error': '認証が必要です'})
    id_token = auth[7:].strip()
    if not id_token:
        return resp(401, {'error': '認証が必要です'})
    try:
        with urlopen(GOOGLE_TOKENINFO_URL + id_token, timeout=5) as r:
            payload = json.loads(r.read().decode('utf-8'))
    except (HTTPError, URLError, json.JSONDecodeError):
        return resp(401, {'error': 'トークンの検証に失敗しました'})
    if 'sub' not in payload:
        return resp(401, {'error': 'トークンに sub がありません'})
    if int(payload.get('exp', 0)) < time.time():
        return resp(401, {'error': 'トークンの有効期限切れ'})
    if GOOGLE_CLIENT_ID and payload.get('aud') != GOOGLE_CLIENT_ID:
        return resp(401, {'error': 'audience 不一致'})
    if payload.get('sub') != user_id:
        return resp(403, {'error': 'userId とトークンが一致しません'})
    return None


# ── ヘルパー ─────────────────────────────────────────────────────

def resp(code: int, body: dict):
    return {
        'statusCode': code,
        'headers':    CORS_HEADERS,
        'body':       json.dumps(body, ensure_ascii=False, default=str),
    }


def err(code: int, msg: str):
    return resp(code, {'error': msg})


# ── 新規 / リピーター 判定 ────────────────────────────────────────

def is_new_viewer(user_id: str, topic_id: str) -> bool:
    """Check if this is the first time this user views this topic."""
    try:
        table = dynamodb.Table(ANALYTICS_TABLE)
        response = table.get_item(
            Key={'userId': user_id, 'sk': f'seen#{topic_id}'}
        )
        return 'Item' not in response
    except Exception:
        return True  # assume new on error


def record_topic_seen(user_id: str, topic_id: str, ttl: int):
    """Mark that this user has seen this topic."""
    try:
        table = dynamodb.Table(ANALYTICS_TABLE)
        table.put_item(Item={
            'userId': user_id,
            'sk': f'seen#{topic_id}',
            'topicId': topic_id,
            'seenAt': int(time.time()),
            'ttl': ttl,
        })
    except Exception:
        pass


# ── S3 キャッシュ ─────────────────────────────────────────────────

def get_cached_trending():
    """S3 から trending キャッシュを読む。期限切れまたは存在しない場合は None。"""
    try:
        obj = s3.get_object(Bucket=S3_BUCKET, Key=CACHE_KEY)
        data = json.loads(obj['Body'].read())
        cached_at = data.get('cachedAt', 0)
        if time.time() - cached_at < CACHE_TTL_SEC:
            return data
        return None
    except ClientError:
        return None
    except Exception as e:
        print(f'Cache read error: {e}')
        return None


def save_cached_trending(payload: dict):
    try:
        payload['cachedAt'] = int(time.time())
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=CACHE_KEY,
            Body=json.dumps(payload, ensure_ascii=False),
            ContentType='application/json',
        )
    except Exception as e:
        print(f'Cache write error: {e}')


# ── トレンド集計 ──────────────────────────────────────────────────

def compute_trending():
    """
    flotopic-analytics テーブルを直近24h でスキャンし、
    topicId ごとに view/favorite をカウントしてソートする。
    PII は含まない。
    """
    table   = dynamodb.Table(ANALYTICS_TABLE)
    since   = int(time.time()) - 86400  # 24h 前
    counts  = defaultdict(lambda: {'views': 0, 'favorites': 0, 'total': 0, 'new_viewers': 0})

    # FilterExpression でタイムスタンプを絞る（フルスキャンだが小規模向け）
    paginator_kwargs = {
        'FilterExpression': Attr('timestamp').gte(since) & Attr('topicId').exists(),
    }

    last_key = None
    while True:
        if last_key:
            paginator_kwargs['ExclusiveStartKey'] = last_key
        result = table.scan(**paginator_kwargs)

        for item in result.get('Items', []):
            topic_id   = item.get('topicId', '')
            event_type = item.get('eventType', '')
            if not topic_id:
                continue
            if event_type in ('view', 'topic_click', 'page_view'):
                counts[topic_id]['views'] += 1
                if item.get('isNewViewer'):
                    counts[topic_id]['new_viewers'] += 1
            elif event_type in ('favorite', 'unfavorite'):
                delta = 1 if event_type == 'favorite' else -1
                counts[topic_id]['favorites'] = max(0, counts[topic_id]['favorites'] + delta)
            counts[topic_id]['total'] = counts[topic_id]['views'] + counts[topic_id]['favorites'] * 3

        last_key = result.get('LastEvaluatedKey')
        if not last_key:
            break

    # new_viewer_ratio を付与してスコア順にソート
    trending = []
    for tid, v in counts.items():
        total = v['views']
        new_v = v['new_viewers']
        ratio = round(new_v / total, 2) if total > 0 else 0
        trending.append({
            'topicId': tid,
            'views': total,
            'favorites': v['favorites'],
            'total': v['total'],
            'new_viewers': new_v,
            'new_viewer_ratio': ratio,
        })

    trending = sorted(trending, key=lambda x: x['total'], reverse=True)[:50]  # 上位50件

    return trending


# ── ユーザーサマリー ──────────────────────────────────────────────

def compute_user_summary(user_id: str) -> dict:
    """
    userId のアクティビティを集計する。
    PII（メールアドレス等）は返さない。行動統計のみ。
    """
    table = dynamodb.Table(ANALYTICS_TABLE)

    items = []
    query_kwargs = {'KeyConditionExpression': Key('userId').eq(user_id)}
    while True:
        result = table.query(**query_kwargs)
        items.extend(result.get('Items', []))
        last = result.get('LastEvaluatedKey')
        if not last:
            break
        query_kwargs['ExclusiveStartKey'] = last

    # 集計
    total_views      = 0
    total_comments   = 0
    total_favorites  = 0
    topic_views      = defaultdict(int)
    hour_counts      = defaultdict(int)  # 時間帯別アクティビティ

    for item in items:
        event_type = item.get('eventType', '')
        topic_id   = item.get('topicId', '')
        ts         = int(item.get('timestamp', 0))

        if event_type == 'view':
            total_views += 1
            if topic_id:
                topic_views[topic_id] += 1
        elif event_type == 'comment':
            total_comments += 1
        elif event_type == 'favorite':
            total_favorites += 1

        if ts:
            hour = datetime.fromtimestamp(ts, tz=timezone.utc).hour
            hour_counts[hour] += 1

    # 最も閲覧したトピック上位5件（topicId のみ、コンテンツ情報なし）
    top_topics = sorted(topic_views.items(), key=lambda x: x[1], reverse=True)[:5]

    # 最も活発な時間帯（JST換算: UTC+9）
    active_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    active_hours_jst = [{'hour_jst': (h + 9) % 24, 'count': c} for h, c in active_hours]

    return {
        'userId':        user_id,  # 自分のIDのみ
        'totalViews':    total_views,
        'totalComments': total_comments,
        'totalFavorites': total_favorites,
        'topTopics':     [{'topicId': tid, 'views': cnt} for tid, cnt in top_topics],
        'activeHoursJst': active_hours_jst,
        'recordCount':   len(items),
    }


# ── エントリポイント ──────────────────────────────────────────────

def lambda_handler(event, context):
    method = (event.get('requestContext', {})
                   .get('http', {})
                   .get('method', 'GET'))
    path   = event.get('rawPath', '/')

    # CORS プリフライト
    if method == 'OPTIONS':
        return resp(200, {})

    parts = [p for p in path.split('/') if p]
    # parts[0] == 'analytics'

    # ── POST /analytics/event ────────────────────────────────────
    # Body: {"anonymousId": "...", "topicId": "...", "eventType": "topic_click"|"page_view"}
    if method == 'POST' and len(parts) >= 2 and parts[1] == 'event':
        try:
            body_str = event.get('body') or '{}'
            body = json.loads(body_str)
            anonymous_id = body.get('anonymousId', '')
            topic_id     = body.get('topicId', '')
            event_type   = body.get('eventType', '')

            if not anonymous_id or not topic_id or not event_type:
                return err(400, 'anonymousId, topicId, eventType が必要です')
            if event_type not in ('topic_click', 'page_view'):
                return err(400, '無効な eventType（topic_click または page_view のみ許可）')

            table = dynamodb.Table(ANALYTICS_TABLE)
            ts  = int(time.time())
            ttl = ts + 86400 * 30  # 30日TTL

            new_viewer = is_new_viewer(anonymous_id, topic_id)

            table.put_item(Item={
                'userId':      anonymous_id,
                'sk':          f'{event_type}#{ts}#{topic_id}',
                'topicId':     topic_id,
                'eventType':   event_type,
                'timestamp':   ts,
                'isNewViewer': new_viewer,
                'ttl':         ttl,
            })

            if new_viewer:
                record_topic_seen(anonymous_id, topic_id, ttl)

            return resp(200, {'ok': True, 'isNewViewer': new_viewer})
        except Exception as e:
            print(f'Event record error: {e}')
            return err(500, 'イベント記録に失敗しました')

    if method != 'GET':
        return err(405, 'method not allowed')

    # ── GET /analytics/trending ──────────────────────────────────
    if len(parts) >= 2 and parts[1] == 'trending':
        cached = get_cached_trending()
        if cached:
            return resp(200, cached)

        try:
            trending = compute_trending()
            payload = {
                'trending':  trending,
                'generatedAt': datetime.now(timezone.utc).isoformat(),
            }
            save_cached_trending(payload)
            return resp(200, payload)
        except Exception as e:
            print(f'Trending error: {e}')
            return err(500, 'トレンドの取得に失敗しました')

    # ── GET /analytics/user/{userId} ─────────────────────────────
    # T2026-0502-SEC7: 認証必須化 (旧実装は IDOR で他人の閲覧傾向・アクティブ時間帯が読めた)
    if len(parts) >= 3 and parts[1] == 'user':
        user_id = parts[2]
        if not user_id:
            return err(400, 'userId が必要です')

        # 本人検証
        auth_err = _verify_user_or_403(event, user_id)
        if auth_err is not None:
            return auth_err

        try:
            summary = compute_user_summary(user_id)
            return resp(200, summary)
        except Exception as e:
            print(f'[ERROR] User summary error: {e}')
            return err(500, 'ユーザーサマリーの取得に失敗しました')

    # ── GET /analytics/active ────────────────────────────────────
    # サイト全体の過去30分間ユニーク閲覧者数（anonymousId）+ page_view 総数を返す
    if len(parts) >= 2 and parts[1] == 'active':
        try:
            table = dynamodb.Table(ANALYTICS_TABLE)
            since = int(time.time()) - 1800  # 30分前
            unique_users = set()
            page_views = 0
            scan_kwargs = {
                'FilterExpression': (
                    Attr('eventType').eq('page_view') &
                    Attr('timestamp').gte(since)
                ),
                'ProjectionExpression': 'userId',
            }
            while True:
                result = table.scan(**scan_kwargs)
                for item in result.get('Items', []):
                    uid = item.get('userId')
                    if uid:
                        unique_users.add(uid)
                page_views += len(result.get('Items', []))
                last = result.get('LastEvaluatedKey')
                if not last:
                    break
                scan_kwargs['ExclusiveStartKey'] = last
            return resp(200, {
                'activeUsers30m': len(unique_users),
                'pageViews30m': page_views,
            })
        except Exception as e:
            print(f'Active error: {e}')
            return err(500, 'アクティブ数の取得に失敗しました')

    # ── GET /analytics/views/{topicId} ───────────────────────────
    # 過去30分間の page_view 件数を返す
    if len(parts) >= 3 and parts[1] == 'views':
        topic_id = parts[2]
        if not topic_id or len(topic_id) != 16 or not all(c in '0123456789abcdef' for c in topic_id):
            return err(400, 'invalid topicId')

        try:
            table = dynamodb.Table(ANALYTICS_TABLE)
            since = int(time.time()) - 1800  # 30分前

            count = 0
            scan_kwargs = {
                'FilterExpression': (
                    Attr('topicId').eq(topic_id) &
                    Attr('eventType').eq('page_view') &
                    Attr('timestamp').gte(since)
                ),
                'Select': 'COUNT',
            }
            while True:
                result = table.scan(**scan_kwargs)
                count += result.get('Count', 0)
                last = result.get('LastEvaluatedKey')
                if not last:
                    break
                scan_kwargs['ExclusiveStartKey'] = last

            return resp(200, {'topicId': topic_id, 'views30m': count})
        except Exception as e:
            print(f'Views30m error: {e}')
            return err(500, '閲覧数の取得に失敗しました')

    return err(404, 'not found')
