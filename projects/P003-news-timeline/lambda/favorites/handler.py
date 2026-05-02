"""
P003 お気に入り + 閲覧履歴 Lambda
- GET    /favorites/{userId}   → ユーザーのお気に入りトピックID一覧
- POST   /favorites            → お気に入り追加 {userId, idToken, topicId}
- DELETE /favorites            → お気に入り削除 {userId, idToken, topicId}
- GET    /history/{userId}     → 閲覧履歴一覧（最新20件）
- POST   /history              → 閲覧履歴追加 {userId, idToken, topicId, title, viewedAt}
- DELETE /history              → 閲覧履歴削除 {userId, idToken, topicId?} topicId省略=全削除
- DELETE /user                 → アカウント全データ削除 {userId, idToken}
- GET    /prefs/{userId}       → ジャンル設定取得
- PUT    /prefs                → ジャンル設定保存 {userId, idToken, genre}

書き込み操作は Google idToken を検証してから実行する。

DynamoDB テーブル: flotopic-favorites
  favorites: PK=userId / SK=topicId          fields: createdAt
  history:   PK=userId / SK=HISTORY#{topicId} fields: title, viewedAt, ttl
  prefs:     PK=userId / SK=PREFS#genre       fields: genre
"""

import base64
import json
import os
import re
from datetime import datetime, timezone
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

TABLE_NAME        = os.environ.get('FAVORITES_TABLE', 'flotopic-favorites')
TOPICS_TABLE      = os.environ.get('TABLE_NAME', 'p003-topics')
REGION            = os.environ.get('REGION', 'ap-northeast-1')
GOOGLE_TOKENINFO_URL = 'https://oauth2.googleapis.com/tokeninfo?id_token='
GOOGLE_CLIENT_ID  = os.environ.get('GOOGLE_CLIENT_ID', '')
HISTORY_SK_PREFIX = 'HISTORY#'
HISTORY_TTL_DAYS  = 30
PREFS_SK_GENRE    = 'PREFS#genre'

dynamodb     = boto3.resource('dynamodb', region_name=REGION)
table        = dynamodb.Table(TABLE_NAME)
topics_table = dynamodb.Table(TOPICS_TABLE)


def update_topic_fav_count(topic_id: str, delta: int):
    """トピックの favoriteCount を±1（流行スコア用）"""
    try:
        if delta > 0:
            topics_table.update_item(
                Key={'topicId': topic_id, 'SK': 'META'},
                UpdateExpression='ADD favoriteCount :d',
                ConditionExpression='attribute_exists(topicId)',
                ExpressionAttributeValues={':d': delta},
            )
        else:
            # 0未満にならないよう条件付きデクリメント
            topics_table.update_item(
                Key={'topicId': topic_id, 'SK': 'META'},
                UpdateExpression='ADD favoriteCount :d',
                ConditionExpression='attribute_exists(favoriteCount) AND favoriteCount > :zero',
                ExpressionAttributeValues={':d': delta, ':zero': 0},
            )
    except ClientError as e:
        if e.response['Error']['Code'] != 'ConditionalCheckFailedException':
            print(f'update_topic_fav_count error: {e}')
    except Exception as e:
        print(f'update_topic_fav_count error: {e}')


# ── ヘルパー ─────────────────────────────────────────────────────

def _cors_headers():
    return {
        'Content-Type':                 'application/json; charset=utf-8',
        'Access-Control-Allow-Origin':  '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
    }


def _make_response(status: int, payload: dict, headers=None) -> dict:
    """PayloadFormatVersion 2.0 準拠レスポンス (statusCode=int, body=str)"""
    return {
        'statusCode': int(status),
        'headers':    headers if headers is not None else _cors_headers(),
        'body':       json.dumps(payload, ensure_ascii=False, default=str),
    }


def resp(code: int, body: dict):
    return _make_response(code, body)


def verify_google_token(id_token: str):
    """Google tokeninfo で ID トークンを検証し、ペイロードを返す。失敗は None。"""
    try:
        url = GOOGLE_TOKENINFO_URL + id_token
        with urlopen(url, timeout=5) as response:
            payload = json.loads(response.read().decode('utf-8'))
        if 'sub' not in payload:
            return None
        if GOOGLE_CLIENT_ID and payload.get('aud') != GOOGLE_CLIENT_ID:
            return None
        return payload
    except (HTTPError, URLError, json.JSONDecodeError):
        return None


def parse_body(event: dict) -> dict:
    try:
        raw = event.get('body') or '{}'
        if event.get('isBase64Encoded'):
            raw = base64.b64decode(raw).decode('utf-8')
        return json.loads(raw)
    except Exception:
        return {}


# ── お気に入り一覧取得 ────────────────────────────────────────────

def get_favorites(user_id: str) -> list:
    items = []
    kwargs = {
        'KeyConditionExpression': Key('userId').eq(user_id),
        'FilterExpression': ~(Attr('topicId').begins_with('HISTORY#') | Attr('topicId').begins_with('PREFS#')),
        'ProjectionExpression': 'topicId, createdAt',
    }
    while True:
        r = table.query(**kwargs)
        items.extend(r.get('Items', []))
        last = r.get('LastEvaluatedKey')
        if not last:
            break
        kwargs['ExclusiveStartKey'] = last
    return items


# ── お気に入り追加 ────────────────────────────────────────────────

def add_favorite(user_id: str, topic_id: str):
    now_iso = datetime.now(timezone.utc).isoformat()
    table.put_item(Item={
        'userId':    user_id,
        'topicId':   topic_id,
        'createdAt': now_iso,
    })
    update_topic_fav_count(topic_id, 1)


# ── お気に入り削除 ────────────────────────────────────────────────

def remove_favorite(user_id: str, topic_id: str):
    table.delete_item(Key={'userId': user_id, 'topicId': topic_id})
    update_topic_fav_count(topic_id, -1)


# ── ユーザー全データ削除 ──────────────────────────────────────────

def delete_all_user_data(user_id: str):
    items = get_favorites(user_id)
    history_items = get_history(user_id)
    with table.batch_writer() as batch:
        for item in items:
            batch.delete_item(Key={'userId': user_id, 'topicId': item['topicId']})
        for item in history_items:
            batch.delete_item(Key={'userId': user_id, 'topicId': HISTORY_SK_PREFIX + item['topicId']})
        batch.delete_item(Key={'userId': user_id, 'topicId': PREFS_SK_GENRE})


# ── 閲覧履歴 ─────────────────────────────────────────────────────

def _history_ttl() -> int:
    return int(datetime.now(timezone.utc).timestamp()) + HISTORY_TTL_DAYS * 86400


def get_history(user_id: str) -> list:
    r = table.query(
        KeyConditionExpression=Key('userId').eq(user_id) & Key('topicId').begins_with(HISTORY_SK_PREFIX),
        ProjectionExpression='topicId, title, viewedAt',
        ScanIndexForward=False,
        Limit=200,
    )
    items = r.get('Items', [])
    for item in items:
        item['topicId'] = item['topicId'][len(HISTORY_SK_PREFIX):]
    return items


def add_history_item(user_id: str, topic_id: str, title: str, viewed_at: str):
    table.put_item(Item={
        'userId':   user_id,
        'topicId':  HISTORY_SK_PREFIX + topic_id,
        'title':    title,
        'viewedAt': viewed_at,
        'ttl':      _history_ttl(),
    })


def remove_history_item(user_id: str, topic_id: str):
    table.delete_item(Key={'userId': user_id, 'topicId': HISTORY_SK_PREFIX + topic_id})


def clear_history(user_id: str):
    items = get_history(user_id)
    with table.batch_writer() as batch:
        for item in items:
            batch.delete_item(Key={'userId': user_id, 'topicId': HISTORY_SK_PREFIX + item['topicId']})


def get_prefs(user_id: str) -> dict:
    r = table.get_item(Key={'userId': user_id, 'topicId': PREFS_SK_GENRE})
    item = r.get('Item', {})
    return {'genre': item.get('genre')} if item else {}


def save_prefs(user_id: str, genre: str):
    table.put_item(Item={'userId': user_id, 'topicId': PREFS_SK_GENRE, 'genre': genre})


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

    # ── GET /favorites/{userId} or GET /history/{userId} or GET /prefs/{userId} ──
    if method == 'GET':
        if len(parts) < 2:
            return resp(400, {'error': 'userId が必要です'})
        resource, user_id = parts[0], parts[1]
        try:
            if resource == 'history':
                items = get_history(user_id)
                return resp(200, {'userId': user_id, 'history': items})
            elif resource == 'favorites':
                items = get_favorites(user_id)
                return resp(200, {'userId': user_id, 'favorites': items})
            elif resource == 'prefs':
                prefs = get_prefs(user_id)
                return resp(200, {'userId': user_id, **prefs})
            else:
                return resp(404, {'error': 'not found'})
        except Exception as e:
            print(f'[ERROR] GET {resource}/{user_id}: {type(e).__name__}: {e}')
            return _make_response(500, {'error': '取得に失敗しました', 'detail': str(e)})

    # ── DELETE /user : アカウント全データ削除 ────────────────────
    if method == 'DELETE' and len(parts) >= 1 and parts[0] == 'user':
        data = parse_body(event)
        user_id  = (data.get('userId')  or '').strip()
        id_token = (data.get('idToken') or '').strip()
        if not user_id or not id_token:
            return resp(400, {'error': 'userId, idToken は必須です'})
        payload = verify_google_token(id_token)
        if not payload or payload.get('sub') != user_id:
            return resp(401, {'error': 'トークンの検証に失敗しました'})
        try:
            delete_all_user_data(user_id)
            return _make_response(200, {'status': 'deleted', 'userId': user_id})
        except Exception as e:
            print(f'[ERROR] DELETE user/{user_id}: {type(e).__name__}: {e}')
            return _make_response(500, {'error': 'データ削除に失敗しました', 'detail': str(e)})

    # ── POST /history : 閲覧履歴追加 ─────────────────────────────
    if method == 'POST' and len(parts) >= 1 and parts[0] == 'history':
        data = parse_body(event)
        user_id   = (data.get('userId')   or '').strip()
        id_token  = (data.get('idToken')  or '').strip()
        topic_id  = (data.get('topicId')  or '').strip()
        title     = (data.get('title')    or '').strip()
        viewed_at = (data.get('viewedAt') or datetime.now(timezone.utc).isoformat()).strip()
        if not user_id or not id_token or not topic_id:
            return resp(400, {'error': 'userId, idToken, topicId は必須です'})
        payload = verify_google_token(id_token)
        if not payload or payload.get('sub') != user_id:
            return resp(401, {'error': 'トークンの検証に失敗しました'})
        try:
            add_history_item(user_id, topic_id, title, viewed_at)
            return _make_response(200, {'status': 'added', 'topicId': topic_id})
        except Exception as e:
            print(f'[ERROR] POST history/{user_id}/{topic_id}: {type(e).__name__}: {e}')
            return _make_response(500, {'error': '履歴追加に失敗しました', 'detail': str(e)})

    # ── DELETE /history : 閲覧履歴削除 (topicId省略=全削除) ───────
    if method == 'DELETE' and len(parts) >= 1 and parts[0] == 'history':
        data = parse_body(event)
        user_id  = (data.get('userId')  or '').strip()
        id_token = (data.get('idToken') or '').strip()
        topic_id = (data.get('topicId') or '').strip()
        if not user_id or not id_token:
            return resp(400, {'error': 'userId, idToken は必須です'})
        payload = verify_google_token(id_token)
        if not payload or payload.get('sub') != user_id:
            return resp(401, {'error': 'トークンの検証に失敗しました'})
        try:
            if topic_id:
                remove_history_item(user_id, topic_id)
                return _make_response(200, {'status': 'removed', 'topicId': topic_id})
            else:
                clear_history(user_id)
                return _make_response(200, {'status': 'cleared', 'userId': user_id})
        except Exception as e:
            print(f'[ERROR] DELETE history/{user_id}: {type(e).__name__}: {e}')
            return _make_response(500, {'error': '履歴削除に失敗しました', 'detail': str(e)})

    # ── PUT /prefs: ジャンル設定保存 ─────────────────────────────
    if method == 'PUT' and len(parts) >= 1 and parts[0] == 'prefs':
        data = parse_body(event)
        user_id  = (data.get('userId')  or '').strip()
        id_token = (data.get('idToken') or '').strip()
        genre    = (data.get('genre')   or '').strip()
        if not user_id or not id_token or not genre:
            return resp(400, {'error': 'userId, idToken, genre は必須です'})
        payload = verify_google_token(id_token)
        if not payload or payload.get('sub') != user_id:
            return resp(401, {'error': 'トークンの検証に失敗しました'})
        try:
            save_prefs(user_id, genre)
            return _make_response(200, {'status': 'saved', 'genre': genre})
        except Exception as e:
            print(f'[ERROR] PUT prefs/{user_id}: {type(e).__name__}: {e}')
            return _make_response(500, {'error': '設定保存に失敗しました', 'detail': str(e)})

    # ── POST / DELETE /favorites: 認証付き書き込み ───────────────
    if method in ('POST', 'DELETE'):
        data = parse_body(event)
        if not data:
            return resp(400, {'error': 'リクエストの形式が不正です'})

        user_id  = (data.get('userId')  or '').strip()
        id_token = (data.get('idToken') or '').strip()
        topic_id = (data.get('topicId') or '').strip()

        if not user_id or not id_token or not topic_id:
            return resp(400, {'error': 'userId, idToken, topicId は必須です'})
        if not re.match(r'^[0-9a-f]{16}$', topic_id):
            return resp(400, {'error': 'invalid topicId'})

        # Google トークン検証
        payload = verify_google_token(id_token)
        if not payload:
            return resp(401, {'error': 'トークンの検証に失敗しました'})

        # トークン内の sub と userId が一致するか確認
        if payload.get('sub') != user_id:
            return resp(403, {'error': 'userId とトークンが一致しません'})

        try:
            if method == 'POST':
                add_favorite(user_id, topic_id)
                return _make_response(200, {'status': 'added', 'userId': user_id, 'topicId': topic_id})
            else:  # DELETE
                remove_favorite(user_id, topic_id)
                return _make_response(200, {'status': 'removed', 'userId': user_id, 'topicId': topic_id})
        except Exception as e:
            print(f'[ERROR] {method} favorites/{user_id}/{topic_id}: {type(e).__name__}: {e}')
            return _make_response(500, {'error': 'お気に入りの更新に失敗しました', 'detail': str(e)})

    return resp(405, {'error': 'method not allowed'})
