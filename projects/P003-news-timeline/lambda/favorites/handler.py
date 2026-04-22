"""
P003 お気に入り Lambda
- GET    /favorites/{userId}  → ユーザーのお気に入りトピックID一覧
- POST   /favorites           → お気に入り追加 {userId, idToken, topicId}
- DELETE /favorites           → お気に入り削除 {userId, idToken, topicId}

書き込み操作は Google idToken を検証してから実行する。

DynamoDB テーブル: flotopic-favorites
  PK=userId / SK=topicId  fields: createdAt
"""

import base64
import json
import os
from datetime import datetime, timezone
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

TABLE_NAME = os.environ.get('FAVORITES_TABLE', 'flotopic-favorites')
REGION     = os.environ.get('REGION', 'ap-northeast-1')
GOOGLE_TOKENINFO_URL = 'https://oauth2.googleapis.com/tokeninfo?id_token='

dynamodb = boto3.resource('dynamodb', region_name=REGION)
table    = dynamodb.Table(TABLE_NAME)


# ── ヘルパー ─────────────────────────────────────────────────────

def cors_headers():
    return {
        'Content-Type':                 'application/json; charset=utf-8',
        'Access-Control-Allow-Origin':  '*',
        'Access-Control-Allow-Methods': 'GET, POST, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
    }


def resp(code: int, body: dict):
    return {
        'statusCode': code,
        'headers':    cors_headers(),
        'body':       json.dumps(body, ensure_ascii=False, default=str),
    }


def verify_google_token(id_token: str) -> dict | None:
    """Google tokeninfo で ID トークンを検証し、ペイロードを返す。失敗は None。"""
    try:
        url = GOOGLE_TOKENINFO_URL + id_token
        with urlopen(url, timeout=5) as response:
            payload = json.loads(response.read().decode('utf-8'))
        if 'sub' not in payload:
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
    r = table.query(
        KeyConditionExpression=Key('userId').eq(user_id),
        ProjectionExpression='topicId, createdAt',
    )
    return r.get('Items', [])


# ── お気に入り追加 ────────────────────────────────────────────────

def add_favorite(user_id: str, topic_id: str):
    now_iso = datetime.now(timezone.utc).isoformat()
    table.put_item(Item={
        'userId':    user_id,
        'topicId':   topic_id,
        'createdAt': now_iso,
    })


# ── お気に入り削除 ────────────────────────────────────────────────

def remove_favorite(user_id: str, topic_id: str):
    table.delete_item(Key={'userId': user_id, 'topicId': topic_id})


# ── エントリポイント ──────────────────────────────────────────────

def lambda_handler(event, context):
    method = (event.get('requestContext', {})
                   .get('http', {})
                   .get('method', 'GET'))
    path   = event.get('rawPath', '/')

    # CORS プリフライト
    if method == 'OPTIONS':
        return resp(200, {})

    # ── GET /favorites/{userId} ──────────────────────────────────
    if method == 'GET':
        parts = [p for p in path.split('/') if p]
        # /favorites/{userId}
        if len(parts) < 2 or parts[0] != 'favorites':
            return resp(400, {'error': 'userId が必要です'})
        user_id = parts[1]
        try:
            items = get_favorites(user_id)
            return resp(200, {'userId': user_id, 'favorites': items})
        except Exception as e:
            return resp(500, {'error': 'お気に入りの取得に失敗しました', 'detail': str(e)})

    # ── POST / DELETE: 認証付き書き込み ──────────────────────────
    if method in ('POST', 'DELETE'):
        data = parse_body(event)
        if not data:
            return resp(400, {'error': 'リクエストの形式が不正です'})

        user_id  = (data.get('userId')  or '').strip()
        id_token = (data.get('idToken') or '').strip()
        topic_id = (data.get('topicId') or '').strip()

        if not user_id or not id_token or not topic_id:
            return resp(400, {'error': 'userId, idToken, topicId は必須です'})

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
                return resp(200, {'status': 'added', 'userId': user_id, 'topicId': topic_id})
            else:  # DELETE
                remove_favorite(user_id, topic_id)
                return resp(200, {'status': 'removed', 'userId': user_id, 'topicId': topic_id})
        except Exception as e:
            return resp(500, {'error': 'お気に入りの更新に失敗しました', 'detail': str(e)})

    return resp(405, {'error': 'method not allowed'})
