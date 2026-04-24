"""
P003 コメント掲示板 Lambda
- GET  /comments/{topicId}   → コメント一覧取得（最新100件）
- POST /comments/{topicId}   → コメント投稿（Google 認証必須）
- PUT  /comments/like        → いいね更新（冪等性: likedBy Set）

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
import re
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
S3_BUCKET          = os.environ.get('S3_BUCKET', 'p003-news-946554699567')
CLOUDFRONT_DOMAIN  = os.environ.get('CLOUDFRONT_DOMAIN', 'flotopic.com')
MAX_BODY_LEN       = 200
MAX_NICK_LEN       = 30
MAX_PER_TOPIC      = 100
GOOGLE_TOKENINFO_URL = 'https://oauth2.googleapis.com/tokeninfo?id_token='

# S3 アバターキープレフィックス
AVATAR_KEY_PREFIX = 'avatars/'
AVATAR_PRESIGN_TTL = 300  # 5分

# 許可するアバターURL プレフィックス
ALLOWED_AVATAR_PREFIXES = (
    'https://lh3.googleusercontent.com/',  # Google プロフィール
    'https://flotopic.com/avatars/',        # Flotopic カスタムアバター
)

# セキュリティ関連テーブル
RATE_TABLE      = 'flotopic-rate-limits'
USERS_TABLE     = 'flotopic-users'
ANALYTICS_TABLE = 'flotopic-analytics'

dynamodb  = boto3.resource('dynamodb', region_name=REGION)
table     = dynamodb.Table(TABLE_NAME)
s3_client = boto3.client('s3', region_name=REGION)


# ── CORS ヘッダー ────────────────────────────────────────────────

CORS_HEADERS = {
    'Content-Type':                 'application/json; charset=utf-8',
    'Access-Control-Allow-Origin':  '*',
    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
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
    items = []
    for item in r.get('Items', []):
        c = {k: v for k, v in item.items() if k not in hidden}
        c['commentId'] = item.get('SK', '')
        items.append(c)
    return items


def delete_comment(topic_id: str, comment_id: str, user_id: str) -> bool:
    """コメントを削除。所有者チェックあり。True=成功, False=権限なし/不在。"""
    try:
        result = table.get_item(Key={'topicId': topic_id, 'SK': comment_id})
        item = result.get('Item')
        if not item:
            return False
        if item.get('userId') != user_id:
            return False
        table.delete_item(Key={'topicId': topic_id, 'SK': comment_id})
        return True
    except Exception as e:
        print(f'delete_comment error: {e}')
        return False


# ── コメント投稿 ──────────────────────────────────────────────────

def post_comment(topic_id: str, body_text: str, nickname: str, user_id: str,
                 handle: str = '', avatar_url: str = '') -> dict:
    now    = datetime.now(timezone.utc)
    ts_str = now.strftime('%Y%m%dT%H%M%S') + f'{now.microsecond // 1000:03d}Z'
    sk     = f'{ts_str}#{uuid.uuid4().hex[:8]}'

    item = {
        'topicId':    topic_id,
        'SK':         sk,
        'commentId':  sk,
        'nickname':   nickname[:MAX_NICK_LEN] if nickname else '匿名',
        'body':       body_text,
        'createdAt':  now.isoformat(),
        'userId':     user_id,               # 生のまま保存（削除権限チェック用）
        'userIdHash': hash_str(user_id),     # フロント表示・本人判定用（短縮ハッシュ）
        'likeCount':  0,
        'ttl':        int(time.time()) + 60 * 60 * 24 * 30,
    }
    # オプションフィールド
    if handle:
        item['handle'] = handle
    if avatar_url:
        item['avatarUrl'] = avatar_url
    table.put_item(Item=item)

    return {k: v for k, v in item.items() if k not in ('userId', 'ttl')}


# ── いいね更新 ────────────────────────────────────────────────────

HANDLE_RE = re.compile(r'^[A-Za-z0-9_]{1,20}$')


def handle_like(event) -> dict:
    """
    PUT /comments/like?topicId=xxx&commentId=yyy&userHash=zzz
    冪等性: likedBy DynamoDB String Set に userHash を ADD。
    既に含まれていれば ConditionalCheckFailed → 現在件数を返す。
    """
    qs = event.get('queryStringParameters') or {}
    topic_id   = (qs.get('topicId')   or '').strip()
    comment_id = (qs.get('commentId') or '').strip()
    user_hash  = (qs.get('userHash')  or '').strip()

    if not topic_id or not comment_id or not user_hash:
        return resp(400, {'error': 'topicId, commentId, userHash が必要です'})

    # userHash は 16文字の hex（クライアントの getMyCommentHash() と同じ形式）
    if len(user_hash) > 32 or not re.match(r'^[0-9a-f]+$', user_hash):
        return resp(400, {'error': 'userHash が不正です'})

    try:
        result = table.update_item(
            Key={'topicId': topic_id, 'SK': comment_id},
            UpdateExpression='ADD likeCount :one, likedBy :user_set',
            ConditionExpression=(
                'attribute_exists(topicId) AND NOT contains(likedBy, :user_hash)'
            ),
            ExpressionAttributeValues={
                ':one':       1,
                ':user_set':  {user_hash},   # DynamoDB String Set
                ':user_hash': user_hash,
            },
            ReturnValues='ALL_NEW',
        )
        like_count = int(result['Attributes'].get('likeCount', 1))
        return resp(200, {'likeCount': like_count, 'liked': True})

    except ClientError as e:
        code = e.response['Error']['Code']
        if code == 'ConditionalCheckFailedException':
            # 既にいいね済み → 現在の件数を返す
            try:
                r  = table.get_item(Key={'topicId': topic_id, 'SK': comment_id})
                lc = int(r.get('Item', {}).get('likeCount', 0))
                return resp(200, {'likeCount': lc, 'liked': False, 'alreadyLiked': True})
            except Exception:
                return resp(200, {'likeCount': 0, 'liked': False, 'alreadyLiked': True})
        print(f'handle_like DynamoDB error: {e}')
        return resp(500, {'error': 'いいねの更新に失敗しました'})
    except Exception as e:
        print(f'handle_like error: {e}')
        return resp(500, {'error': 'いいねの更新に失敗しました'})


# ── アバターアップロード URL 生成 ─────────────────────────────────

def handle_avatar_upload_url(event) -> dict:
    """
    GET /avatar/upload-url?userId=xxx
    S3 Presigned PUT URL を生成して返す。
    レスポンス: {"uploadUrl": "...", "avatarUrl": "https://flotopic.com/avatars/xxx.jpg"}
    """
    qs      = event.get('queryStringParameters') or {}
    user_id = (qs.get('userId') or '').strip()

    if not user_id:
        return resp(400, {'error': 'userId が必要です'})

    # userId を安全なファイル名に変換（英数字・ハイフン・アンダースコアのみ）
    safe_id = re.sub(r'[^A-Za-z0-9_\-]', '_', user_id)[:64]
    key     = f'{AVATAR_KEY_PREFIX}{safe_id}.jpg'

    try:
        upload_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket':      S3_BUCKET,
                'Key':         key,
                'ContentType': 'image/jpeg',
            },
            ExpiresIn=AVATAR_PRESIGN_TTL,
        )
        avatar_url = f'https://{CLOUDFRONT_DOMAIN}/{key}'
        return resp(200, {'uploadUrl': upload_url, 'avatarUrl': avatar_url})

    except Exception as e:
        print(f'handle_avatar_upload_url error: {e}')
        return resp(500, {'error': 'アップロードURLの生成に失敗しました'})


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

    # パス解析: /comments/{topicId} or /comments/{topicId}/{commentId}
    #           /avatar/upload-url
    parts = [p for p in path.split('/') if p]

    # ── GET /avatar/upload-url ───────────────────────────────────────
    if method == 'GET' and len(parts) >= 2 and parts[0] == 'avatar' and parts[1] == 'upload-url':
        return handle_avatar_upload_url(event)

    if len(parts) < 2 or parts[0] != 'comments':
        return resp(404, {'error': 'not found'})

    # ── PUT /comments/like ───────────────────────────────────────
    if method == 'PUT' and parts[1] == 'like':
        return handle_like(event)

    topic_id = parts[1]
    comment_id = parts[2] if len(parts) >= 3 else None

    # ── GET: コメント一覧 ─────────────────────────────────────────
    if method == 'GET':
        comments = get_comments(topic_id)
        return resp(200, {'topicId': topic_id, 'comments': comments})

    # ── DELETE: コメント削除 ─────────────────────────────────────
    if method == 'DELETE':
        if not comment_id:
            return resp(400, {'error': 'commentId が必要です'})
        try:
            raw = event.get('body') or '{}'
            if event.get('isBase64Encoded'):
                raw = base64.b64decode(raw).decode('utf-8')
            data = json.loads(raw)
        except Exception:
            return resp(400, {'error': 'リクエストの形式が不正です'})

        id_token = (data.get('idToken') or '').strip()
        if not id_token:
            return resp(401, {'error': '認証が必要です'})
        google_payload = verify_google_token(id_token)
        if not google_payload:
            return resp(401, {'error': 'トークンの検証に失敗しました'})
        user_id = google_payload.get('sub', '')

        ok = delete_comment(topic_id, comment_id, user_id)
        if not ok:
            return resp(403, {'error': '削除権限がないか、コメントが見つかりません'})
        return resp(200, {'status': 'deleted', 'commentId': comment_id})

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
        client_nick   = (data.get('nickname') or '').strip()  # フロントで設定したニックネーム
        # X風プロフィール（省略可）
        raw_handle    = (data.get('handle')    or '').strip()[:20]
        client_handle = raw_handle if HANDLE_RE.match(raw_handle) else ''
        # avatarUrl は Google CDN または Flotopic CloudFront のみ許可
        raw_avatar    = (data.get('avatarUrl') or '').strip()
        client_avatar = raw_avatar if any(raw_avatar.startswith(p) for p in ALLOWED_AVATAR_PREFIXES) else ''

        # Google 認証が必須
        if not id_token:
            return resp(401, {'error': 'コメントするにはGoogleでログインしてください'})

        google_payload = verify_google_token(id_token)
        if not google_payload:
            return resp(401, {'error': 'トークンの検証に失敗しました。再ログインしてください'})

        user_id  = google_payload.get('sub', '')
        # ニックネーム: クライアント送信値 > Google名 > メール
        google_name = google_payload.get('name', '') or google_payload.get('email', '匿名')
        nickname = client_nick if client_nick else google_name

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

        comment = post_comment(topic_id_body, body_text, nickname, user_id,
                               handle=client_handle, avatar_url=client_avatar)

        # アナリティクス記録（投稿成功後）
        record_event(user_id, 'comment', topic_id=topic_id_body)

        return resp(201, {'comment': comment})

    return resp(405, {'error': 'method not allowed'})
