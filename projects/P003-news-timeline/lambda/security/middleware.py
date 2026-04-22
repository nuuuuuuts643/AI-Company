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
    'Access-Control-Allow-Methods': 'GET,POST,DELETE,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
    'Access-Control-Max-Age': '86400',
}

def cors_response(status, body):
    return {'statusCode': status, 'headers': CORS_HEADERS, 'body': json.dumps(body, ensure_ascii=False)}

def error(status, msg):
    return cors_response(status, {'error': msg})

# ===== リクエストサイズ制限 =====
MAX_BODY_BYTES = 4096  # 4KB

def check_request_size(event):
    body = event.get('body') or ''
    if len(body.encode('utf-8')) > MAX_BODY_BYTES:
        return False
    return True

# ===== IPレート制限 (DynamoDB) =====
RATE_TABLE = 'flotopic-rate-limits'

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
