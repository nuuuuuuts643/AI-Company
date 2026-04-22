"""
P003 Google Auth Lambda
- POST /auth/google  → Google ID トークンを検証し、ユーザーを作成 or 取得して返す

DynamoDB テーブル: flotopic-users
  PK=userId (Google sub)
  fields: email, name, picture, createdAt
"""

import base64
import json
import os
import time
from datetime import datetime, timezone
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

import boto3
from botocore.exceptions import ClientError

TABLE_NAME = os.environ.get('USERS_TABLE', 'flotopic-users')
REGION     = os.environ.get('REGION', 'ap-northeast-1')
GOOGLE_TOKENINFO_URL = 'https://oauth2.googleapis.com/tokeninfo?id_token='

dynamodb = boto3.resource('dynamodb', region_name=REGION)
table    = dynamodb.Table(TABLE_NAME)


# ── ヘルパー ─────────────────────────────────────────────────────

def cors_headers():
    return {
        'Content-Type':                 'application/json; charset=utf-8',
        'Access-Control-Allow-Origin':  '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
    }


def resp(code: int, body: dict):
    return {
        'statusCode': code,
        'headers':    cors_headers(),
        'body':       json.dumps(body, ensure_ascii=False, default=str),
    }


def verify_google_token(id_token: str) -> dict | None:
    """
    Google tokeninfo エンドポイントで ID トークンを検証する。
    成功したらペイロード dict を返す。失敗したら None を返す。
    """
    try:
        url = GOOGLE_TOKENINFO_URL + id_token
        with urlopen(url, timeout=5) as response:
            payload = json.loads(response.read().decode('utf-8'))
        # 基本フィールドの確認
        if 'sub' not in payload or 'email' not in payload:
            return None
        return payload
    except (HTTPError, URLError, json.JSONDecodeError):
        return None


def get_or_create_user(payload: dict) -> dict:
    """DynamoDB からユーザーを取得、存在しなければ作成する。"""
    user_id = payload['sub']
    now_iso  = datetime.now(timezone.utc).isoformat()

    # 既存ユーザー取得試行
    try:
        result = table.get_item(Key={'userId': user_id})
        existing = result.get('Item')
        if existing:
            # 名前・アイコンが変わっていれば更新
            table.update_item(
                Key={'userId': user_id},
                UpdateExpression='SET #n = :n, picture = :p, email = :e',
                ExpressionAttributeNames={'#n': 'name'},
                ExpressionAttributeValues={
                    ':n': payload.get('name', ''),
                    ':p': payload.get('picture', ''),
                    ':e': payload.get('email', ''),
                },
            )
            existing['name']    = payload.get('name', existing.get('name', ''))
            existing['picture'] = payload.get('picture', existing.get('picture', ''))
            return existing
    except ClientError:
        pass

    # 新規作成
    item = {
        'userId':    user_id,
        'email':     payload.get('email', ''),
        'name':      payload.get('name', ''),
        'picture':   payload.get('picture', ''),
        'createdAt': now_iso,
    }
    table.put_item(Item=item)
    return item


# ── エントリポイント ──────────────────────────────────────────────

def lambda_handler(event, context):
    method = (event.get('requestContext', {})
                   .get('http', {})
                   .get('method', 'POST'))

    # CORS プリフライト
    if method == 'OPTIONS':
        return resp(200, {})

    if method != 'POST':
        return resp(405, {'error': 'method not allowed'})

    # ボディ解析
    try:
        raw = event.get('body') or '{}'
        if event.get('isBase64Encoded'):
            raw = base64.b64decode(raw).decode('utf-8')
        data = json.loads(raw)
    except Exception:
        return resp(400, {'error': 'リクエストの形式が不正です'})

    id_token = (data.get('idToken') or '').strip()
    if not id_token:
        return resp(400, {'error': 'idToken が必要です'})

    # Google トークン検証
    payload = verify_google_token(id_token)
    if not payload:
        return resp(401, {'error': 'トークンの検証に失敗しました'})

    # ユーザー取得 or 作成
    try:
        user = get_or_create_user(payload)
    except Exception as e:
        return resp(500, {'error': 'ユーザーの処理に失敗しました', 'detail': str(e)})

    return resp(200, {
        'userId':  user['userId'],
        'name':    user.get('name', ''),
        'picture': user.get('picture', ''),
        'token':   id_token,
    })
