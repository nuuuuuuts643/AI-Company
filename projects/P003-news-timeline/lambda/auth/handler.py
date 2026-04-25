"""
P003 Auth Lambda
- POST /auth  → Google ID トークン検証 + ユーザー作成/取得/profile更新
  body: { idToken, handle?, ageGroup?, gender? }
  response: { userId, name, picture, handle, ageGroup, gender, token }

DynamoDB テーブル: flotopic-users
  PK=userId (Google sub)
  fields: email, name, picture, handle, ageGroup, gender, createdAt
"""

import base64
import json
import os
import re
from datetime import datetime, timezone
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

import boto3
from botocore.exceptions import ClientError

TABLE_NAME   = os.environ.get('USERS_TABLE', 'flotopic-users')
REGION       = os.environ.get('REGION', 'ap-northeast-1')
TOKENINFO_URL = 'https://oauth2.googleapis.com/tokeninfo?id_token='
HANDLE_RE    = re.compile(r'^[A-Za-z0-9_]{1,20}$')
VALID_AGE_GROUPS = {'10代未満', '10代', '20代', '30代', '40代', '50代', '60代以上', ''}
VALID_GENDERS    = {'male', 'female', 'other', 'prefer_not', ''}

dynamodb = boto3.resource('dynamodb', region_name=REGION)
table    = dynamodb.Table(TABLE_NAME)


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
    try:
        with urlopen(TOKENINFO_URL + id_token, timeout=5) as response:
            payload = json.loads(response.read().decode('utf-8'))
        if 'sub' not in payload or 'email' not in payload:
            return None
        return payload
    except (HTTPError, URLError, json.JSONDecodeError):
        return None


def get_or_create_user(payload: dict, new_handle: str = '',
                       new_age: str = '', new_gender: str = '') -> dict:
    """DynamoDB からユーザーを取得 or 作成。プロフィールが渡されたら更新する。"""
    user_id = payload['sub']
    now_iso = datetime.now(timezone.utc).isoformat()
    valid_handle = new_handle if (new_handle and HANDLE_RE.match(new_handle)) else ''
    valid_age    = new_age    if new_age    in VALID_AGE_GROUPS else ''
    valid_gender = new_gender if new_gender in VALID_GENDERS    else ''

    try:
        result = table.get_item(Key={'userId': user_id})
        existing = result.get('Item')
        if existing:
            expr = 'SET #n = :n, picture = :p, email = :e'
            vals = {
                ':n': payload.get('name', ''),
                ':p': payload.get('picture', ''),
                ':e': payload.get('email', ''),
            }
            names = {'#n': 'name'}
            if valid_handle:
                expr += ', handle = :h'
                vals[':h'] = valid_handle
            if valid_age:
                expr += ', ageGroup = :ag'
                vals[':ag'] = valid_age
            if valid_gender:
                expr += ', gender = :gd'
                vals[':gd'] = valid_gender
            table.update_item(
                Key={'userId': user_id},
                UpdateExpression=expr,
                ExpressionAttributeNames=names,
                ExpressionAttributeValues=vals,
            )
            existing['name']    = payload.get('name', existing.get('name', ''))
            existing['picture'] = payload.get('picture', existing.get('picture', ''))
            if valid_handle: existing['handle']   = valid_handle
            if valid_age:    existing['ageGroup'] = valid_age
            if valid_gender: existing['gender']   = valid_gender
            return existing
    except ClientError:
        pass

    item = {
        'userId':    user_id,
        'email':     payload.get('email', ''),
        'name':      payload.get('name', ''),
        'picture':   payload.get('picture', ''),
        'createdAt': now_iso,
    }
    if valid_handle: item['handle']   = valid_handle
    if valid_age:    item['ageGroup'] = valid_age
    if valid_gender: item['gender']   = valid_gender
    table.put_item(Item=item)
    return item


def lambda_handler(event, context):
    method = (event.get('requestContext', {})
                   .get('http', {})
                   .get('method', 'POST'))

    if method == 'OPTIONS':
        return resp(200, {})

    if method != 'POST':
        return resp(405, {'error': 'method not allowed'})

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

    payload = verify_google_token(id_token)
    if not payload:
        return resp(401, {'error': 'トークンの検証に失敗しました'})

    new_handle = (data.get('handle')   or '').strip()
    new_age    = (data.get('ageGroup') or '').strip()
    new_gender = (data.get('gender')   or '').strip()
    try:
        user = get_or_create_user(payload, new_handle, new_age, new_gender)
    except Exception as e:
        return resp(500, {'error': 'ユーザーの処理に失敗しました', 'detail': str(e)})

    return resp(200, {
        'userId':   user['userId'],
        'name':     user.get('name', ''),
        'picture':  user.get('picture', ''),
        'handle':   user.get('handle', ''),
        'ageGroup': user.get('ageGroup', ''),
        'gender':   user.get('gender', ''),
        'token':    id_token,
    })
