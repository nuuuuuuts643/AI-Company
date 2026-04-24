"""
Flotopic セキュリティミドルウェア
全Lambdaで共通使用するセキュリティ関数群
"""
import json
import hashlib
import time
import os
import urllib.request

import boto3
from boto3.dynamodb.conditions import Key, Attr

REGION = os.environ.get('REGION', 'ap-northeast-1')
dynamodb = boto3.resource('dynamodb', region_name=REGION)

# ===== CORS ヘッダー =====
CORS_HEADERS = {
    'Access-Control-Allow-Origin': 'https://flotopic.com',
    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
    'Access-Control-Max-Age': '86400',
}

def cors_response(status, body, extra_headers=None):
    headers = dict(CORS_HEADERS)
    if extra_headers:
        headers.update(extra_headers)
    return {'statusCode': status, 'headers': headers, 'body': json.dumps(body, ensure_ascii=False)}

def error(status, msg):
    return cors_response(status, {'error': msg})

def rate_limit_response(retry_after=60):
    """HTTP 429 Too Many Requests + Retry-After ヘッダー"""
    return cors_response(
        429,
        {'error': 'Too Many Requests. Please wait before retrying.', 'retryAfter': retry_after},
        extra_headers={'Retry-After': str(retry_after)},
    )

# ===== リクエストサイズ制限 =====
MAX_BODY_BYTES = 4096  # 4KB

def check_request_size(event):
    body = event.get('body') or ''
    if len(body.encode('utf-8')) > MAX_BODY_BYTES:
        return False
    return True

# ===== IPレート制限 (DynamoDB) =====
RATE_TABLE = 'flotopic-rate-limits'

# デフォルト上限値
DEFAULT_COMMENT_MAX_PER_MINUTE = 5     # コメント: 1分間に5件まで
DEFAULT_API_MAX_PER_MINUTE = 60        # 汎用API: 1分間に60リクエストまで
COMMENT_THROTTLE_SECONDS = 30          # コメント連投ブロック: 30秒以内の再投稿を禁止

def check_rate_limit(identifier, action, max_per_minute=10):
    """
    identifier: IP or userId
    action: 'comment', 'auth', 'favorite'
    max_per_minute: 最大リクエスト数/分
    Returns True if allowed, False if rate limited
    """
    try:
        table = dynamodb.Table(RATE_TABLE)
        now = int(time.time())
        window_key = f"{identifier}#{action}#{now // 60}"

        resp = table.update_item(
            Key={'pk': window_key},
            UpdateExpression='ADD #cnt :one SET #ttl = :ttl',
            ExpressionAttributeNames={'#cnt': 'count', '#ttl': 'ttl'},
            ExpressionAttributeValues={':one': 1, ':ttl': now + 120},
            ReturnValues='UPDATED_NEW',
        )
        count = int(resp['Attributes']['count'])
        return count <= max_per_minute
    except Exception as e:
        print(f'Rate limit check error: {e}')
        return True  # エラー時は通す

def check_comment_throttle(identifier):
    """
    コメント連投ブロック: 同一IP/ユーザーから30秒以内の再投稿を禁止。
    Returns True if allowed (30秒以上経過 or 初回), False if throttled.
    """
    try:
        table = dynamodb.Table(RATE_TABLE)
        now = int(time.time())
        throttle_key = f"{identifier}#comment_throttle"

        resp = table.get_item(Key={'pk': throttle_key})
        item = resp.get('Item')
        if item:
            last_post_time = int(item.get('lastPost', 0))
            if now - last_post_time < COMMENT_THROTTLE_SECONDS:
                return False  # 30秒未満 → ブロック

        # 最終投稿時刻を更新
        table.put_item(Item={
            'pk': throttle_key,
            'lastPost': now,
            'ttl': now + COMMENT_THROTTLE_SECONDS + 10,
        })
        return True
    except Exception as e:
        print(f'Comment throttle check error: {e}')
        return True  # エラー時は通す

def check_api_rate_limit(identifier, action='api'):
    """
    汎用APIレート制限: 同一IPから1分間に60リクエスト超でブロック。
    Returns True if allowed, False if rate limited.
    """
    return check_rate_limit(identifier, action, max_per_minute=DEFAULT_API_MAX_PER_MINUTE)

def get_client_ip(event):
    """
    Lambda Function URL / API Gateway からクライアントIPを取得。
    X-Forwarded-For → requestContext.http.sourceIp の順で試みる。
    """
    headers = event.get('headers') or {}
    xff = headers.get('x-forwarded-for') or headers.get('X-Forwarded-For', '')
    if xff:
        return xff.split(',')[0].strip()
    # Function URL
    ctx = event.get('requestContext', {})
    http_ctx = ctx.get('http', {})
    return http_ctx.get('sourceIp', 'unknown')

# ===== Google IDトークン検証 =====
def verify_google_token(id_token):
    """
    Google tokeninfo APIでIDトークンを検証。
    Returns: payload dict or None
    """
    try:
        url = f'https://oauth2.googleapis.com/tokeninfo?id_token={id_token}'
        with urllib.request.urlopen(url, timeout=5) as resp:
            payload = json.loads(resp.read())
        # 有効期限チェック
        if int(payload.get('exp', 0)) < time.time():
            return None
        return payload
    except Exception as e:
        print(f'Token verification error: {e}')
        return None

# ===== Banリスト確認 =====
USERS_TABLE = 'flotopic-users'

def is_banned(user_id):
    try:
        table = dynamodb.Table(USERS_TABLE)
        resp = table.get_item(Key={'userId': user_id})
        item = resp.get('Item', {})
        return item.get('banned', False)
    except Exception:
        return False

# ===== NGワードフィルター =====
NG_WORDS = [
    # 基本的な差別語・暴力的表現
    '死ね', '殺す', '爆破', 'テロ', '爆弾',
    # スパム的表現
    'http://', 'https://', 'bit.ly', 'tinyurl',
    # 個人情報誘導
    'LINE ID', 'LINE@', 'discord.gg',
]

def contains_ng_word(text):
    lower = text.lower()
    for ng in NG_WORDS:
        if ng.lower() in lower:
            return True
    return False

# ===== ユーザー行動記録 =====
ANALYTICS_TABLE = 'flotopic-analytics'

def record_event(user_id, event_type, topic_id=None, metadata=None):
    """
    event_type: 'view', 'favorite', 'unfavorite', 'comment', 'search'
    """
    try:
        table = dynamodb.Table(ANALYTICS_TABLE)
        now = int(time.time())
        item = {
            'userId': user_id,
            'sk': f'{event_type}#{now}#{topic_id or ""}',
            'eventType': event_type,
            'topicId': topic_id or '',
            'timestamp': now,
            'ttl': now + 90 * 86400,  # 90日保持
        }
        if metadata:
            item['metadata'] = metadata
        table.put_item(Item=item)
    except Exception as e:
        print(f'Analytics record error: {e}')
