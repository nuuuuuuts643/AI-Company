"""
P003 Auth Lambda
- POST /auth  → Google ID トークン検証 + ユーザー作成/取得/profile更新
  body: { idToken, handle?, ageGroup?, gender?, nickname?, interests?, avatarUrl? }
  response: { userId, name, picture, handle, ageGroup, gender, nickname, interests, avatarUrl, token }

DynamoDB テーブル: flotopic-users
  PK=userId (Google sub)
  fields: email, name, picture, handle, ageGroup, gender, nickname, interests, avatarUrl, createdAt
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

TABLE_NAME        = os.environ.get('USERS_TABLE', 'flotopic-users')
REGION            = os.environ.get('REGION', 'ap-northeast-1')
TOKENINFO_URL     = 'https://oauth2.googleapis.com/tokeninfo?id_token='
GOOGLE_CLIENT_ID  = os.environ.get('GOOGLE_CLIENT_ID', '')
HANDLE_RE    = re.compile(r'^[A-Za-z0-9_]{1,20}$')
VALID_AGE_GROUPS = {'10代未満', '10代', '20代', '30代', '40代', '50代', '60代以上', ''}
VALID_GENDERS    = {'male', 'female', 'other', 'prefer_not', ''}

# T227 (2026-04-28): CORS Allow-Origin を `*` から自社ドメインに固定。
# CSRF 増幅リスク削減 (任意の悪性サイトから POST されない)。env で上書き可能 (staging用途等)。
ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get(
        'ALLOWED_ORIGINS',
        'https://flotopic.com,https://www.flotopic.com'
    ).split(',') if o.strip()
]

dynamodb = boto3.resource('dynamodb', region_name=REGION)
table    = dynamodb.Table(TABLE_NAME)


def _resolve_origin(event) -> str:
    """リクエスト Origin ヘッダーが ALLOWED_ORIGINS にあれば echo back、無ければ第一許可ドメインを返す。

    T227 設計: ワイルドカード `*` は使わず、許可リストとの突合で必ず固定値を返す。
    Origin ヘッダーが無い (curl 等) 場合や許可外の場合は、第一許可ドメインで応答 → ブラウザ側 CORS で弾かれる。
    """
    headers = event.get('headers') or {} if isinstance(event, dict) else {}
    raw = headers.get('origin') or headers.get('Origin') or ''
    if raw in ALLOWED_ORIGINS:
        return raw
    return ALLOWED_ORIGINS[0] if ALLOWED_ORIGINS else 'https://flotopic.com'


def cors_headers(event=None):
    return {
        'Content-Type':                 'application/json; charset=utf-8',
        'Access-Control-Allow-Origin':  _resolve_origin(event),
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Vary':                         'Origin',
    }


def resp(code: int, body: dict, event=None):
    return {
        'statusCode': code,
        'headers':    cors_headers(event),
        'body':       json.dumps(body, ensure_ascii=False, default=str),
    }


def verify_google_token(id_token: str) -> dict | None:
    try:
        with urlopen(TOKENINFO_URL + id_token, timeout=5) as response:
            payload = json.loads(response.read().decode('utf-8'))
        if 'sub' not in payload or 'email' not in payload:
            return None
        if GOOGLE_CLIENT_ID and payload.get('aud') != GOOGLE_CLIENT_ID:
            return None
        return payload
    except (HTTPError, URLError, json.JSONDecodeError):
        return None


# T2026-0428-AU: フロント GENRES と processor _VALID_GENRE_SET と完全一致 (14ジャンル)
# 旧「経済・教育・文化・環境」は廃止 (経済→ビジネス, 文化/教育/環境→くらし)。
# 既存ユーザーが旧 genre を持っている場合、frontend 側 _LEGACY_GENRE_MAP で吸収する。
VALID_GENRES = {'総合','政治','ビジネス','株・金融','テクノロジー','スポーツ','エンタメ','科学','健康','国際','くらし','社会','グルメ','ファッション'}


def get_or_create_user(payload: dict, new_handle: str = '',
                       new_age: str = '', new_gender: str = '',
                       new_nickname: str = '', new_interests: list = None,
                       new_avatar_url: str = '') -> dict:
    """DynamoDB からユーザーを取得 or 作成。プロフィールが渡されたら更新する。"""
    user_id = payload['sub']
    now_iso = datetime.now(timezone.utc).isoformat()
    valid_handle    = new_handle   if (new_handle and HANDLE_RE.match(new_handle)) else ''
    valid_age       = new_age      if new_age    in VALID_AGE_GROUPS else ''
    valid_gender    = new_gender   if new_gender in VALID_GENDERS    else ''
    valid_nickname  = new_nickname[:30] if new_nickname else ''
    valid_interests = [g for g in (new_interests or []) if g in VALID_GENRES][:10]
    valid_avatar    = new_avatar_url[:500] if new_avatar_url else ''

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
            if valid_nickname:
                expr += ', nickname = :nk'
                vals[':nk'] = valid_nickname
            if valid_interests:
                expr += ', interests = :in'
                vals[':in'] = valid_interests
            if valid_avatar:
                expr += ', avatarUrl = :av'
                vals[':av'] = valid_avatar
            table.update_item(
                Key={'userId': user_id},
                UpdateExpression=expr,
                ExpressionAttributeNames=names,
                ExpressionAttributeValues=vals,
            )
            existing['name']    = payload.get('name', existing.get('name', ''))
            existing['picture'] = payload.get('picture', existing.get('picture', ''))
            if valid_handle:    existing['handle']    = valid_handle
            if valid_age:       existing['ageGroup']  = valid_age
            if valid_gender:    existing['gender']    = valid_gender
            if valid_nickname:  existing['nickname']  = valid_nickname
            if valid_interests: existing['interests'] = valid_interests
            if valid_avatar:    existing['avatarUrl'] = valid_avatar
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
    if valid_handle:    item['handle']    = valid_handle
    if valid_age:       item['ageGroup']  = valid_age
    if valid_gender:    item['gender']    = valid_gender
    if valid_nickname:  item['nickname']  = valid_nickname
    if valid_interests: item['interests'] = valid_interests
    if valid_avatar:    item['avatarUrl'] = valid_avatar
    table.put_item(Item=item)
    return item


def lambda_handler(event, context):
    method = (event.get('requestContext', {})
                   .get('http', {})
                   .get('method', 'POST'))

    if method == 'OPTIONS':
        return resp(200, {}, event)

    if method != 'POST':
        return resp(405, {'error': 'method not allowed'}, event)

    try:
        raw = event.get('body') or '{}'
        if event.get('isBase64Encoded'):
            raw = base64.b64decode(raw).decode('utf-8')
        data = json.loads(raw)
    except Exception:
        return resp(400, {'error': 'リクエストの形式が不正です'}, event)

    id_token = (data.get('idToken') or '').strip()
    if not id_token:
        return resp(400, {'error': 'idToken が必要です'}, event)

    payload = verify_google_token(id_token)
    if not payload:
        return resp(401, {'error': 'トークンの検証に失敗しました'}, event)

    new_handle    = (data.get('handle')    or '').strip()
    new_age       = (data.get('ageGroup')  or '').strip()
    new_gender    = (data.get('gender')    or '').strip()
    new_nickname  = (data.get('nickname')  or '').strip()
    new_interests = data.get('interests')  # list or None
    new_avatar    = (data.get('avatarUrl') or '').strip()
    if not isinstance(new_interests, list):
        new_interests = None
    try:
        user = get_or_create_user(payload, new_handle, new_age, new_gender,
                                  new_nickname, new_interests, new_avatar)
    except Exception as e:
        print(f'[ERROR] auth/user/{payload.get("sub","?")}: {type(e).__name__}: {e}')
        return resp(500, {'error': 'ユーザーの処理に失敗しました', 'detail': str(e)}, event)

    return resp(200, {
        'userId':    user['userId'],
        'name':      user.get('name', ''),
        'picture':   user.get('picture', ''),
        'handle':    user.get('handle', ''),
        'ageGroup':  user.get('ageGroup', ''),
        'gender':    user.get('gender', ''),
        'nickname':  user.get('nickname', ''),
        'interests': user.get('interests', []),
        'avatarUrl': user.get('avatarUrl', ''),
        'token':     id_token,
    }, event)
