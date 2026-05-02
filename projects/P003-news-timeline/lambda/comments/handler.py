# T2026-0502-PATH-FILTER-AUDIT verify: pull_request trigger test
"""
P003 コメント掲示板 Lambda
- GET  /comments/{topicId}         → コメント一覧取得（最新100件）
- POST /comments/{topicId}         → コメント投稿（Google 認証必須、引用コメント対応）
- PUT  /comments/like              → いいね/バッド更新（冪等性: likedBy/dislikedBy Set）
- GET  /user/{handle}/comments     → ユーザー公開コメント履歴（プロフィール用）
- GET  /notifications/{handle}     → @mention通知一覧
- PUT  /notifications/{handle}/read→ 通知全既読

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
from decimal import Decimal
from urllib.parse import unquote
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

TABLE_NAME         = os.environ.get('COMMENTS_TABLE', 'ai-company-comments')
NOTIF_TABLE        = os.environ.get('NOTIF_TABLE', 'flotopic-notifications')
TOPICS_TABLE       = os.environ.get('TABLE_NAME', 'p003-topics')
REGION             = os.environ.get('REGION', 'ap-northeast-1')
S3_BUCKET          = os.environ.get('S3_BUCKET', 'p003-news-946554699567')
CLOUDFRONT_DOMAIN  = os.environ.get('CLOUDFRONT_DOMAIN', 'flotopic.com')
MAX_BODY_LEN       = 200
MAX_NICK_LEN       = 30
MAX_PER_TOPIC      = 100
GOOGLE_TOKENINFO_URL = 'https://oauth2.googleapis.com/tokeninfo?id_token='
GOOGLE_CLIENT_ID     = os.environ.get('GOOGLE_CLIENT_ID', '')

AVATAR_KEY_PREFIX = 'avatars/'
AVATAR_PRESIGN_TTL = 300

ALLOWED_AVATAR_PREFIXES = (
    'https://lh3.googleusercontent.com/',
    'https://flotopic.com/avatars/',
)

RATE_TABLE      = 'flotopic-rate-limits'
USERS_TABLE     = 'flotopic-users'
ANALYTICS_TABLE = 'flotopic-analytics'

MENTION_RE = re.compile(r'@([A-Za-z0-9_]{1,20})')

dynamodb      = boto3.resource('dynamodb', region_name=REGION)
table         = dynamodb.Table(TABLE_NAME)
notif_table   = dynamodb.Table(NOTIF_TABLE)
topics_table  = dynamodb.Table(TOPICS_TABLE)
s3_client     = boto3.client('s3', region_name=REGION)


def increment_topic_comment_count(topic_id: str):
    """トピックの commentCount をインクリメント（流行スコア用）"""
    try:
        topics_table.update_item(
            Key={'topicId': topic_id, 'SK': 'META'},
            UpdateExpression='ADD commentCount :one',
            ConditionExpression='attribute_exists(topicId)',
            ExpressionAttributeValues={':one': 1},
        )
    except ClientError as e:
        if e.response['Error']['Code'] != 'ConditionalCheckFailedException':
            print(f'increment_topic_comment_count error: {e}')
    except Exception as e:
        print(f'increment_topic_comment_count error: {e}')


# ── CORS ヘッダー ────────────────────────────────────────────────
# T2026-0502-SEC8 (2026-05-02): CORS Allow-Origin を `*` から自社ドメインに固定。
# CSRF 増幅・悪意あるサイトからの fetch を防ぐ。
_ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get(
        'ALLOWED_ORIGINS',
        'https://flotopic.com,https://www.flotopic.com'
    ).split(',') if o.strip()
]


def _resolve_origin(event) -> str:
    headers = (event or {}).get('headers') or {}
    raw = headers.get('origin') or headers.get('Origin') or ''
    if raw in _ALLOWED_ORIGINS:
        return raw
    return _ALLOWED_ORIGINS[0] if _ALLOWED_ORIGINS else 'https://flotopic.com'


def cors_headers(event=None):
    return {
        'Content-Type':                 'application/json; charset=utf-8',
        'Access-Control-Allow-Origin':  _resolve_origin(event),
        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type,Authorization',
        'Access-Control-Max-Age':       '86400',
        'Vary':                         'Origin',
    }

# 後方互換の定数 (古い参照用・event なし default)
CORS_HEADERS = cors_headers()


def _json_serial(obj):
    if isinstance(obj, Decimal):
        f = float(obj)
        return int(f) if f == int(f) else f
    return str(obj)


def resp(code: int, body: dict, event=None):
    return {
        'statusCode': code,
        'headers':    cors_headers(event),
        'body':       json.dumps(body, ensure_ascii=False, default=_json_serial),
    }


def hash_str(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]


# ── セキュリティ関数（middleware 相当・インライン実装） ────────────

MAX_BODY_BYTES = 4096  # 4KB

def check_request_size(event):
    """リクエストボディが 4KB 以内かチェック。"""
    body = event.get('body') or ''
    return len(body.encode('utf-8')) <= MAX_BODY_BYTES


def check_rate_limit(identifier, action, max_per_minute=10, fail_closed: bool = False):
    """
    DynamoDB を使った IP/userId レート制限。
    identifier: IP or userId
    action: 'comment', 'auth', 'favorite'
    fail_closed: T2026-0502-SEC15 (2026-05-02) — 旧実装はエラー時に通す (fail-open) だったため、
                 攻撃者が rate-limits テーブルへの IAM 権限を剥がして全制限解除可能だった。
                 重要書き込み (comments POST 等) では fail_closed=True にすること。
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
        # T2026-0502-SEC15: 例外時の挙動を fail_closed フラグで制御。
        # CloudWatch metric filter で `[SEC15]` を観測対象に追加すること。
        print(f'[SEC15] Rate limit check error (fail_closed={fail_closed}): {type(e).__name__}: {e}')
        return not fail_closed


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
        if GOOGLE_CLIENT_ID and payload.get('aud') != GOOGLE_CLIENT_ID:
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
                 handle: str = '', avatar_url: str = '',
                 quoted_comment_id: str = '', quoted_handle: str = '',
                 quoted_text: str = '') -> dict:
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
        'userId':     user_id,
        'userIdHash': hash_str(user_id),
        'likeCount':  0,
        'dislikeCount': 0,
        'ttl':        int(time.time()) + 60 * 60 * 24 * 30,
    }
    if handle:
        item['handle'] = handle
    if avatar_url:
        item['avatarUrl'] = avatar_url
    # 引用コメントフィールド
    if quoted_comment_id:
        item['quotedCommentId'] = quoted_comment_id
    if quoted_handle:
        item['quotedHandle'] = quoted_handle
    if quoted_text:
        item['quotedText'] = quoted_text[:100]

    table.put_item(Item=item)

    # @mention通知 + トピック流行スコア更新
    notify_mentions(body_text, handle, nickname, topic_id, sk)
    increment_topic_comment_count(topic_id)

    return {k: v for k, v in item.items() if k not in ('userId', 'ttl')}


# ── いいね更新 ────────────────────────────────────────────────────

HANDLE_RE = re.compile(r'^[A-Za-z0-9_]{1,20}$')


def handle_like(event) -> dict:
    """
    PUT /comments/like?topicId=xxx&commentId=yyy[&type=like|dislike|unlike|undislike]
    Body: {"idToken": "<Google ID token>"}  ← T2026-0502-SEC6: 必須
    like/dislike: ADD count, ADD to set (冪等: already-in-set で弾く)
    unlike/undislike: ADD count -1, DELETE from set (冪等: not-in-set で弾く)

    T2026-0502-SEC6 (2026-05-02): 旧実装は client から userHash クエリをそのまま信用していた。
    userHash は sha256(userId)[:16] の決定的ハッシュなので、任意 userId が分かれば誰でも
    他人として like/dislike を打てた。本実装では idToken を verify_google_token で検証 →
    server side で hash_str(payload.sub) を計算して使う。
    後方互換: 旧 client が送る ?userHash= は無視 (server 側 hash と一致する保証がない)。
    """
    qs         = event.get('queryStringParameters') or {}
    topic_id   = (qs.get('topicId')   or '').strip()
    comment_id = (qs.get('commentId') or '').strip()
    like_type  = (qs.get('type')      or 'like').strip()

    if like_type not in ('like', 'dislike', 'unlike', 'undislike'):
        like_type = 'like'
    if not topic_id or not comment_id:
        return resp(400, {'error': 'topicId, commentId が必要です'})

    # T2026-0502-SEC6: idToken 必須
    try:
        raw = event.get('body') or '{}'
        if event.get('isBase64Encoded'):
            raw = base64.b64decode(raw).decode('utf-8')
        body_data = json.loads(raw)
    except Exception:
        body_data = {}
    id_token = (body_data.get('idToken') or '').strip()
    if not id_token:
        return resp(401, {'error': '認証が必要です'})
    payload = verify_google_token(id_token)
    if not payload:
        return resp(401, {'error': 'トークンの検証に失敗しました'})
    user_id = payload.get('sub', '')
    if not user_id:
        return resp(401, {'error': 'トークンに sub がありません'})
    user_hash = hash_str(user_id)  # server side で計算 (16 hex chars)

    is_undo     = like_type in ('unlike', 'undislike')
    base_type   = 'like'     if like_type in ('like', 'unlike') else 'dislike'
    count_field = 'likeCount'    if base_type == 'like' else 'dislikeCount'
    set_field   = 'likedBy'      if base_type == 'like' else 'dislikedBy'

    if is_undo:
        try:
            result = table.update_item(
                Key={'topicId': topic_id, 'SK': comment_id},
                UpdateExpression=f'ADD {count_field} :neg_one DELETE {set_field} :uset',
                ConditionExpression=f'attribute_exists(topicId) AND contains({set_field}, :uhash)',
                ExpressionAttributeValues={
                    ':neg_one': -1,
                    ':uset':    {user_hash},
                    ':uhash':   user_hash,
                },
                ReturnValues='ALL_NEW',
            )
            attrs = result['Attributes']
            return resp(200, {
                'likeCount':    max(0, int(attrs.get('likeCount', 0))),
                'dislikeCount': max(0, int(attrs.get('dislikeCount', 0))),
                'type': base_type, 'acted': True, 'action': 'undo',
            })
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                return resp(200, {'type': base_type, 'acted': False, 'alreadyActed': False})
            print(f'handle_like undo error: {e}')
            return resp(500, {'error': 'リアクション取消に失敗しました'})
        except Exception as e:
            print(f'handle_like undo error: {e}')
            return resp(500, {'error': 'リアクション取消に失敗しました'})

    try:
        result = table.update_item(
            Key={'topicId': topic_id, 'SK': comment_id},
            UpdateExpression=f'ADD {count_field} :one, {set_field} :uset',
            ConditionExpression=(
                f'attribute_exists(topicId) AND NOT contains({set_field}, :uhash)'
            ),
            ExpressionAttributeValues={
                ':one':   1,
                ':uset':  {user_hash},
                ':uhash': user_hash,
            },
            ReturnValues='ALL_NEW',
        )
        attrs = result['Attributes']
        return resp(200, {
            'likeCount':    int(attrs.get('likeCount', 0)),
            'dislikeCount': int(attrs.get('dislikeCount', 0)),
            'type': like_type, 'acted': True,
        })
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            try:
                r = table.get_item(Key={'topicId': topic_id, 'SK': comment_id})
                item = r.get('Item', {})
                return resp(200, {
                    'likeCount':    int(item.get('likeCount', 0)),
                    'dislikeCount': int(item.get('dislikeCount', 0)),
                    'type': like_type, 'acted': False, 'alreadyActed': True,
                })
            except Exception:
                return resp(200, {'likeCount': 0, 'dislikeCount': 0, 'type': like_type, 'acted': False})
        print(f'handle_like error: {e}')
        return resp(500, {'error': 'リアクションの更新に失敗しました'})
    except Exception as e:
        print(f'handle_like error: {e}')
        return resp(500, {'error': 'リアクションの更新に失敗しました'})


# ── アバターアップロード URL 生成 ─────────────────────────────────

def _bearer_id_token(event) -> str:
    """Authorization: Bearer <idToken> ヘッダーを取り出す。空なら ''。"""
    headers = event.get('headers') or {}
    auth = headers.get('authorization') or headers.get('Authorization') or ''
    if not auth.startswith('Bearer '):
        return ''
    return auth[7:].strip()


def handle_avatar_upload_url(event) -> dict:
    """
    GET /avatar/upload-url?userId=xxx
    Authorization: Bearer <Google ID token> 必須 (T2026-0502-SEC5)。
    S3 Presigned PUT URL を生成して返す。
    レスポンス: {"uploadUrl": "...", "avatarUrl": "https://flotopic.com/avatars/xxx.jpg"}

    T2026-0502-SEC5 (2026-05-02): 旧実装は Google ID トークン検証なしで任意の userId を受け取り、
    任意ユーザーのアバターを上書きできた (IDOR + 任意 image アップロード経由 XSS リスク)。
    手順: Authorization Bearer の idToken を verify_google_token で検証 → token.sub == userId 強制。
    """
    qs      = event.get('queryStringParameters') or {}
    user_id = (qs.get('userId') or '').strip()

    if not user_id:
        return resp(400, {'error': 'userId が必要です'})

    # T2026-0502-SEC5: 認証必須 — Authorization: Bearer <idToken>
    id_token = _bearer_id_token(event)
    if not id_token:
        return resp(401, {'error': '認証が必要です'})
    payload = verify_google_token(id_token)
    if not payload:
        return resp(401, {'error': 'トークンの検証に失敗しました'})
    if payload.get('sub') != user_id:
        return resp(403, {'error': 'userId とトークンが一致しません'})

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
        print(f'[ERROR] handle_avatar_upload_url: {type(e).__name__}: {e}')
        return resp(500, {'error': 'アップロードURLの生成に失敗しました'})


# ── @メンション通知 ───────────────────────────────────────────────

def extract_mentions(text: str) -> list:
    return list(set(MENTION_RE.findall(text)))


def notify_mentions(body_text: str, from_handle: str, from_nick: str,
                    topic_id: str, comment_sk: str):
    """本文から@handleを抽出してDynamoDB通知を作成する。"""
    if not from_handle:
        return
    mentions = extract_mentions(body_text)
    if not mentions:
        return
    now = datetime.now(timezone.utc)
    excerpt = body_text[:80] + ('…' if len(body_text) > 80 else '')
    for handle in mentions:
        if handle.lower() == from_handle.lower():
            continue  # 自己メンション無視
        try:
            sk = now.strftime('%Y%m%dT%H%M%S') + f'#{uuid.uuid4().hex[:8]}'
            notif_table.put_item(Item={
                'handle':     handle,
                'SK':         sk,
                'fromHandle': from_handle,
                'fromNick':   from_nick,
                'topicId':    topic_id,
                'commentId':  comment_sk,
                'excerpt':    excerpt,
                'read':       False,
                'createdAt':  now.isoformat(),
                'ttl':        int(time.time()) + 30 * 86400,
            })
        except Exception as e:
            print(f'notify_mentions error: {e}')


# ── ユーザーコメント履歴（プロフィール用） ────────────────────────

def get_user_comments(handle: str) -> list:
    """handle のコメント履歴を返す（scan + filter、全件ページネーション）。"""
    try:
        kwargs = {
            'FilterExpression': Attr('handle').eq(handle),
            'ProjectionExpression': (
                'topicId, SK, #bd, createdAt, likeCount, dislikeCount, '
                '#nick, quotedHandle, quotedText'
            ),
            'ExpressionAttributeNames': {'#bd': 'body', '#nick': 'nickname'},
        }
        items = []
        while True:
            result = table.scan(**kwargs)
            items.extend(result.get('Items', []))
            last = result.get('LastEvaluatedKey')
            if not last:
                break
            kwargs['ExclusiveStartKey'] = last
        items.sort(key=lambda x: x.get('createdAt', ''), reverse=True)
        for item in items:
            item['commentId'] = item.pop('SK', '')
        return items[:50]
    except Exception as e:
        print(f'get_user_comments error: {e}')
        return []


# ── 通知 ─────────────────────────────────────────────────────────

def get_notifications(handle: str) -> list:
    try:
        result = notif_table.query(
            KeyConditionExpression=Key('handle').eq(handle),
            ScanIndexForward=False,
            Limit=50,
        )
        return result.get('Items', [])
    except Exception as e:
        print(f'get_notifications error: {e}')
        return []


def mark_notifications_read(handle: str):
    try:
        result = notif_table.query(
            KeyConditionExpression=Key('handle').eq(handle),
            FilterExpression=Attr('read').eq(False),
            ProjectionExpression='handle, SK',
        )
        for item in result.get('Items', []):
            notif_table.update_item(
                Key={'handle': item['handle'], 'SK': item['SK']},
                UpdateExpression='SET #r = :t',
                ExpressionAttributeNames={'#r': 'read'},
                ExpressionAttributeValues={':t': True},
            )
    except Exception as e:
        print(f'mark_notifications_read error: {e}')


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

    # ── GET /user/{handle}/comments ──────────────────────────────────
    if method == 'GET' and len(parts) >= 3 and parts[0] == 'user' and parts[2] == 'comments':
        handle_param = parts[1]
        if not HANDLE_RE.match(handle_param):
            return resp(400, {'error': '不正なhandle形式です'})
        comments = get_user_comments(handle_param)
        return resp(200, {'handle': handle_param, 'comments': comments, 'count': len(comments)})

    # ── GET /notifications/{handle} ───────────────────────────────────
    if method == 'GET' and len(parts) >= 2 and parts[0] == 'notifications':
        handle_param = parts[1]
        if not HANDLE_RE.match(handle_param):
            return resp(400, {'error': '不正なhandle形式です'})
        notifs = get_notifications(handle_param)
        unread = sum(1 for n in notifs if not n.get('read'))
        return resp(200, {'handle': handle_param, 'notifications': notifs, 'unread': unread})

    # ── PUT /notifications/{handle}/read ─────────────────────────────
    if method == 'PUT' and len(parts) >= 3 and parts[0] == 'notifications' and parts[2] == 'read':
        handle_param = parts[1]
        if not HANDLE_RE.match(handle_param):
            return resp(400, {'error': '不正なhandle形式です'})
        try:
            body_data = json.loads(event.get('body') or '{}')
        except Exception:
            body_data = {}
        id_token = (body_data.get('idToken') or '').strip()
        user_id  = (body_data.get('userId')  or '').strip()
        if id_token and user_id:
            g_payload = verify_google_token(id_token)
            if not g_payload or g_payload.get('sub') != user_id:
                return resp(401, {'error': 'トークンの検証に失敗しました'})
            try:
                u = dynamodb.Table(USERS_TABLE).get_item(Key={'userId': user_id}).get('Item', {})
                if u.get('handle', '').lower() != handle_param.lower():
                    return resp(403, {'error': 'handleが一致しません'})
            except Exception as e:
                print(f'notifications/read auth error: {e}')
                return resp(500, {'error': 'サーバーエラー'})
        mark_notifications_read(handle_param)
        return resp(200, {'status': 'ok'})

    if len(parts) < 2 or parts[0] != 'comments':
        return resp(404, {'error': 'not found'})

    # ── PUT /comments/like ───────────────────────────────────────
    if method == 'PUT' and parts[1] == 'like':
        return handle_like(event)

    topic_id = parts[1]
    if not re.match(r'^[0-9a-f]{16}$', topic_id):
        return resp(400, {'error': 'invalid topicId'})
    comment_id = unquote(parts[2]) if len(parts) >= 3 else None

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
        # T2026-0502-SEC15: 重要書き込みなので fail_closed=True
        if not check_rate_limit(user_id, 'comment', max_per_minute=3, fail_closed=True):
            return resp(429, {'error': '短時間に多くの投稿はできません。しばらくお待ちください'})

        # IP ベースのレートリミット（1分に10投稿まで）
        ip = (event.get('requestContext', {})
                   .get('http', {})
                   .get('sourceIp', 'unknown'))
        if not check_rate_limit(ip, 'comment', max_per_minute=10, fail_closed=True):
            return resp(429, {'error': '短時間に多くのリクエストがありました。しばらくお待ちください'})

        # 引用コメント（optional）
        quoted_comment_id = (data.get('quotedCommentId') or '').strip()[:64]
        quoted_handle     = (data.get('quotedHandle')    or '').strip()[:20]
        quoted_text       = (data.get('quotedText')      or '').strip()[:100]

        comment = post_comment(topic_id_body, body_text, nickname, user_id,
                               handle=client_handle, avatar_url=client_avatar,
                               quoted_comment_id=quoted_comment_id,
                               quoted_handle=quoted_handle,
                               quoted_text=quoted_text)

        # アナリティクス記録（投稿成功後）
        record_event(user_id, 'comment', topic_id=topic_id_body)

        return resp(201, {'comment': comment})

    return resp(405, {'error': 'method not allowed'})
