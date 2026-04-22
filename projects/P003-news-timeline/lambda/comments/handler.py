"""
P003 コメント掲示板 Lambda
- GET  /comments/{topicId}   → コメント一覧取得（最新100件）
- POST /comments/{topicId}   → コメント投稿（Google 認証必須）

スパム対策:
  1. 本文 200 文字以内
  2. Google idToken 検証 → userId でレートリミット（1分に max_per_minute 投稿）
  3. ニックネームは Google アカウント名を使用（匿名不可）
  4. NGワードフィルター
  5. Banユーザーチェック
  6. アナリティクスイベント記録

セキュリティ関数はミドルウェア相当のコードをインライン実装
（Lambda Layer 不使用のためインライン統合）

DynamoDB テーブル: ai-company-comments
  PK=topicId / SK=timestamp#uuid8   … 実際のコメント
  PK=__rl__  / SK=userId_hash       … レートリミット（TTL 付き）
"""

import base64
import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

TABLE_NAME         = os.environ.get('COMMENTS_TABLE', 'ai-company-comments')
REGION             = os.environ.get('REGION', 'ap-northeast-1')
MAX_BODY_LEN       = 200
MAX_NICK_LEN       = 30
MAX_PER_TOPIC      = 100
GOOGLE_TOKENINFO_URL = 'https://oauth2.googleapis.com/tokeninfo?id_token='

# セキュリティ関連テーブル
RATE_TABLE      = 'flotopic-rate-limits'
USERS_TABLE     = 'flotopic-users'
ANALYTICS_TABLE = 'flotopic-analytics'

dynamodb = boto3.resource('dynamodb', region_name=REGION)
table    = dynamodb.Table(TABLE_NAME)


# ── CORS ヘッダー ────────────────────────────────────────────────

CORS_HEADERS = {
    'Content-Type':                 'application/json; charset=utf-8',
    'Access-Control-Allow-Origin':  'https://flotopic.com',
    'Access-Control-Allow-Methods': 'GET,POST,DELETE,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
    'Access-Control-Max-Age':       '86400',
}


def resp(code: int, body: dict):
    return {
        'statusCode': code,
        'headers':    CORS_HEADERS,
        'body':       json.dumps(body, ensure_ascii=False, default=str),
    }


def hash_str(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]


# ── セキュリティ関数（middleware 相当・インライン実装） ────────────

MAX_BODY_BYTES = 4096  # 4KB

def check_request_size(event):
    """リクエストボディが 4KB 以内かチェック。"""
    body = event.get('body') or ''
    return len(body.encode('utf-8')) <= MAX_BODY_BYTES


def check_rate_limit(identifier, action, max_per_minute=10):
    """
    DynamoDB を使った IP/userId レート制限。
    identifier: IP or userId
    action: 'comment', 'auth', 'favorite'
    Returns True if allowed, False if rate limited.
    """
    try:
        rl_table = dynamodb.Table(RATE_TABLE)
        now = int(time.time())
        window_key = f"{identifier}#{action}#{now // 60}"

        result = rl_table.update_item(
            Key={'pk': window_key},
            UpdateExpression='ADD #cnt :one SET #ttl = :ttl',
            ExpressionAttributeNames={'#cnt': 'count', '#ttl': 'ttl'},
            ExpressionAttributeValues={':one': 1, ':ttl': now + 120},
            ReturnValues='UPDATED_NEW',
        )
        count = int(result['Attributes']['count'])
        return count <= max_per_minute
    except Exception as e:
        print(f'Rate limit check error: {e}')
        return True  # エラー時は通す


def is_banned(user_id: str) -> bool:
    """flotopic-users テーブルで banned フラグを確認する。"""
    try:
        u_table = dynamodb.Table(USERS_TABLE)
        result = u_table.get_item(Key={'userId': user_id})
        item = result.get('Item', {})
        return bool(item.get('banned', False))
    except Exception:
        return False


NG_WORDS = [
    # 暴力的表現
    '死ね', '殺す', '爆破', 'テロ', '爆弾',
    # スパム
    'http://', 'https://', 'bit.ly', 'tinyurl',
    # 個人情報誘導
    'LINE ID', 'LINE@', 'discord.gg',
]


def contains_ng_word(text: str) -> bool:
    """NGワードを含む場合 True を返す。"""
    lower = text.lower()
    for ng in NG_WORDS:
        if ng.lower() in lower:
            return True
    return False


def record_event(user_id: str, event_type: str, topic_id: str = None, metadata: dict = None):
    """
    アナリティクスイベントを DynamoDB に記録する。
    event_type: 'view', 'favorite', 'unfavorite', 'comment', 'search'
    """
    try:
        a_table = dynamodb.Table(ANALYTICS_TABLE)
        now = int(time.time())
        item = {
            'userId':    user_id,
            'sk':        f'{event_type}#{now}#{topic_id or ""}',
            'eventType': event_type,
            'topicId':   topic_id or '',
            'timestamp': now,
            'ttl':       now + 90 * 86400,  # 90日保持
        }
        if metadata:
            item['metadata'] = metadata
        a_table.put_item(Item=item)
    except Exception as e:
        print(f'Analytics record error: {e}')


# ── Google IDトークン検証 ─────────────────────────────────────────

def verify_google_token(id_token: str) -> dict | None:
    """Google tokeninfo エンドポイントでトークンを検証する。"""
    try:
        url = GOOGLE_TOKENINFO_URL + id_token
        with urlopen(url, timeout=5) as response:
            payload = json.loads(response.read().decode('utf-8'))
        if 'sub' not in payload or 'email' not in payload:
            return None
        # 有効期限チェック
        if int(payload.get('exp', 0)) < time.time():
            return None
        return payload
    except (HTTPError, URLError, json.JSONDecodeError):
        return None


# ── コメント取得 ──────────────────────────────────────────────────

def get_comments(topic_id: str) -> list:
    r = table.query(
        KeyConditionExpression=Key('topicId').eq(topic_id),
        ScanIndexForward=False,
        Limit=MAX_PER_TOPIC,
    )
    hidden = {'userId', 'ttl'}
    return [{k: v for k, v in item.items() if k not in hidden}
            for item in r.get('Items', [])]


# ── コメント投稿 ──────────────────────────────────────────────────

def post_comment(topic_id: str, body_text: str, nickname: str, user_id: str) -> dict:
    now    = datetime.now(timezone.utc)
    ts_str = now.strftime('%Y%m%dT%H%M%S') + f'{now.microsecond // 1000:03d}Z'
    sk     = f'{ts_str}#{uuid.uuid4().hex[:8]}'

    item = {
        'topicId':   topic_id,
        'SK':        sk,
        'nickname':  nickname[:MAX_NICK_LEN] if nickname else '匿名',
        'body':      body_text,
        'createdAt': now.isoformat(),
        'userId':    hash_str(user_id),          # ハッシュ化して保存
        'ttl':       int(time.time()) + 60 * 60 * 24 * 30,  # 30 日 TTL
    }
    table.put_item(Item=item)

    return {k: v for k, v in item.items() if k not in ('userId', 'ttl')}


# ── エントリポイント ──────────────────────────────────────────────

def lambda_handler(event, context):
    method = (event.get('requestContext', {})
                   .get('http', {})
                   .get('method', 'GET'))
    path   = event.get('rawPath', '/')

    # CORS プリフライト
    if method == 'OPTIONS':
        return resp(200, {})

    # リクエストサイズチェック
    if not check_request_size(event):
        return resp(413, {'error': 'リクエストが大きすぎます'})

    # パス解析: /comments/{topicId}
    parts = [p for p in path.split('/') if p]
    if len(parts) < 2 or parts[0] != 'comments':
        return resp(404, {'error': 'not found'})

    topic_id = parts[1]

    # ── GET: コメント一覧 ─────────────────────────────────────────
    if method == 'GET':
        comments = get_comments(topic_id)
        return resp(200, {'topicId': topic_id, 'comments': comments})

    # ── POST: コメント投稿 ────────────────────────────────────────
    if method == 'POST':
        # ボディ解析
        try:
            raw = event.get('body') or '{}'
            if event.get('isBase64Encoded'):
                raw = base64.b64decode(raw).decode('utf-8')
            data = json.loads(raw)
        except Exception:
            return resp(400, {'error': 'リクエストの形式が不正です'})

        id_token      = (data.get('idToken')  or '').strip()
        body_text     = (data.get('body')     or '').strip()
        topic_id_body = (data.get('topicId') or topic_id).strip()

        # Google 認証が必須
        if not id_token:
            return resp(401, {'error': 'コメントするにはGoogleでログインしてください'})

        google_payload = verify_google_token(id_token)
        if not google_payload:
            return resp(401, {'error': 'トークンの検証に失敗しました。再ログインしてください'})

        user_id  = google_payload.get('sub', '')
        nickname = google_payload.get('name', '') or google_payload.get('email', '匿名')

        # Banチェック
        if is_banned(user_id):
            return resp(403, {'error': 'このアカウントはご利用いただけません'})

        # バリデーション
        if not body_text:
            return resp(400, {'error': 'コメント本文を入力してください'})
        if len(body_text) > MAX_BODY_LEN:
            return resp(400, {'error': f'コメントは{MAX_BODY_LEN}文字以内で入力してください'})

        # NGワードチェック
        if contains_ng_word(body_text):
            return resp(400, {'error': '不適切な表現が含まれています'})

        # レートリミット（userId ベース、1分に3投稿まで）
        if not check_rate_limit(user_id, 'comment', max_per_minute=3):
            return resp(429, {'error': '短時間に多くの投稿はできません。しばらくお待ちください'})

        # IP ベースのレートリミット（1分に10投稿まで）
        ip = (event.get('requestContext', {})
                   .get('http', {})
                   .get('sourceIp', 'unknown'))
        if not check_rate_limit(ip, 'comment', max_per_minute=10):
            return resp(429, {'error': '短時間に多くのリクエストがありました。しばらくお待ちください'})

        comment = post_comment(topic_id_body, body_text, nickname, user_id)

        # アナリティクス記録（投稿成功後）
        record_event(user_id, 'comment', topic_id=topic_id_body)

        return resp(201, {'comment': comment})

    return resp(405, {'error': 'method not allowed'})
