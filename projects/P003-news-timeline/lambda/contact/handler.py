"""
Flotopic お問い合わせフォーム Lambda
- POST /contact           → DynamoDB保存 + SES通知（設定済みの場合のみ）
- GET  /contacts          → 管理者用一覧取得（Google IDトークン認証必須）
- POST /contacts/resolve  → 管理者用 archived化（Google IDトークン認証必須）
- 同一トピックへの削除依頼が3件以上 → トピックを自動archived化

入力:
  { "name": str, "email": str, "category": str, "message": str, "topicId": str(任意), "honeypot": str }
"""

import hashlib
import json
import os
import re
import time
import urllib.request
import uuid

import boto3
from boto3.dynamodb.conditions import Key

SES_REGION    = os.environ.get('SES_REGION', 'us-east-1')
FROM_EMAIL    = os.environ.get('FROM_EMAIL', 'contact@flotopic.com')
TO_EMAIL      = os.environ.get('TO_EMAIL', '')
CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'flotopic-contacts')
TOPICS_TABLE   = os.environ.get('TOPICS_TABLE', 'p003-topics')
AUTO_ARCHIVE_THRESHOLD = int(os.environ.get('AUTO_ARCHIVE_THRESHOLD', '3'))
ADMIN_EMAIL    = os.environ.get('ADMIN_EMAIL', '')  # T224 (2026-04-28): デフォルトに個人メール直書き禁止 (CLAUDE.md 絶対ルール5)。Lambda 環境変数で必ず設定する。未設定なら admin API は 503 で塞ぐ。
GOOGLE_TOKENINFO_URL = 'https://oauth2.googleapis.com/tokeninfo?id_token='

dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-1')
contacts = dynamodb.Table(CONTACTS_TABLE)
topics   = dynamodb.Table(TOPICS_TABLE)

CATEGORIES = {
    'copyright': '著作権侵害申告',
    'privacy':   'プライバシー・削除依頼',
    'error':     '誤情報・内容指摘',
    'media':     'メディア掲載除外申請',
    'other':     'その他',
}

DELETION_CATEGORIES = {'copyright', 'privacy', 'media'}

# T228 (2026-04-28): IP ハッシュベースのレート制限
# - 5分3件: バースト送信 (同一フォーム連投・誤クリック含む) を抑制
# - 1日10件: 同一 IP からの大量送信 (DynamoDB 増殖 + SES コスト増 + 管理ノイズ) を防御
# fail-open: テーブル未作成・権限欠如・DynamoDB エラーは制限スルー (送信は通す)
RATE_LIMIT_TABLE = os.environ.get('RATE_LIMIT_TABLE', 'flotopic-rate-limits')
_rate_limits     = dynamodb.Table(RATE_LIMIT_TABLE)


def _client_ip(event) -> str:
    rc = (event or {}).get('requestContext', {}) or {}
    http = rc.get('http', {}) or {}
    return (http.get('sourceIp') or rc.get('identity', {}).get('sourceIp') or '0.0.0.0')


def _ip_hash(event) -> str:
    """生 IP は保存せずハッシュで管理。プライバシー配慮 + 同一 IP 識別だけは可能。"""
    ip = _client_ip(event)
    salt = os.environ.get('IP_HASH_SALT', 'flotopic-contact')
    return hashlib.sha256(f'{salt}:{ip}'.encode('utf-8')).hexdigest()[:24]


def check_contact_rate_limit(ip_hash: str, window_seconds: int, max_in_window: int, label: str) -> bool:
    """flotopic-rate-limits を使った時間窓カウンタ。Returns True=allowed / False=denied。

    pk = `contact#<label>#<ip_hash>#w<window>#b<bucket>` で衝突回避。
    ttl = 窓終了時刻 + 60s。
    例外時は True (fail-open) で送信を止めない。
    """
    try:
        now    = int(time.time())
        bucket = now // window_seconds
        pk     = f'contact#{label}#{ip_hash}#w{window_seconds}#b{bucket}'
        result = _rate_limits.update_item(
            Key={'pk': pk},
            UpdateExpression='ADD #cnt :one SET #ttl = :ttl',
            ExpressionAttributeNames={'#cnt': 'count', '#ttl': 'ttl'},
            ExpressionAttributeValues={':one': 1, ':ttl': now + window_seconds + 60},
            ReturnValues='UPDATED_NEW',
        )
        count = int(result['Attributes']['count'])
        return count <= max_in_window
    except Exception as e:
        print(f'[contact rate-limit] {label} fail-open due to: {e}')
        return True


def verify_admin_token(event) -> bool:
    """Authorization ヘッダーの Google ID トークンを検証し admin メールか確認する。

    T224 (2026-04-28): ADMIN_EMAIL が未設定の場合は admin 機能を物理的に塞ぐ。
    これにより default 値で個人メールがハードコードされていても再発しない安全策。
    """
    if not ADMIN_EMAIL:
        print('verify_admin_token: ADMIN_EMAIL not configured. admin機能はOFF。')
        return False
    headers = event.get('headers') or {}
    auth = headers.get('authorization') or headers.get('Authorization') or ''
    if not auth.startswith('Bearer '):
        return False
    id_token = auth[7:].strip()
    if not id_token:
        return False
    try:
        url = GOOGLE_TOKENINFO_URL + urllib.request.quote(id_token, safe='')
        with urllib.request.urlopen(url, timeout=5) as r:
            payload = json.loads(r.read())
        return payload.get('email') == ADMIN_EMAIL and payload.get('email_verified') in ('true', True)
    except Exception as e:
        print(f'verify_admin_token error: {e}')
        return False


def resp(code, msg):
    return {
        'statusCode': code,
        'headers': {
            'Content-Type': 'application/json; charset=utf-8',
            'Access-Control-Allow-Origin': 'https://flotopic.com',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
        },
        'body': json.dumps({'message': msg}, ensure_ascii=False),
    }


def validate(data):
    name     = (data.get('name') or '').strip()[:100]
    email    = (data.get('email') or '').strip()[:200]
    category = (data.get('category') or '').strip()
    message  = (data.get('message') or '').strip()[:2000]
    topic_id = (data.get('topicId') or '').strip()[:100]

    if not name:
        return None, 'お名前を入力してください'
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        return None, 'メールアドレスの形式が正しくありません'
    if category not in CATEGORIES:
        return None, '問い合わせ種別が不正です'
    if len(message) < 10:
        return None, 'メッセージは10文字以上入力してください'

    return {
        'name': name,
        'email': email,
        'category': category,
        'message': message,
        'topicId': topic_id,
    }, None


def save_to_dynamodb(data):
    contact_id = str(uuid.uuid4())
    now = int(time.time())
    contacts.put_item(Item={
        'contactId': contact_id,
        'category':  data['category'],
        'createdAt': now,
        'email':     data['email'],
        'name':      data['name'],
        'message':   data['message'],
        'topicId':   data['topicId'],
        'status':    'pending',
        'ttl':       now + 90 * 86400,  # 90日で自動削除
    })
    return contact_id


def check_auto_archive(category, topic_id):
    """同一トピックへの削除系申告が閾値以上 → 自動archived化"""
    if category not in DELETION_CATEGORIES or not topic_id:
        return False

    result = contacts.query(
        IndexName='category-createdAt-index',
        KeyConditionExpression=Key('category').eq(category),
        FilterExpression=boto3.dynamodb.conditions.Attr('topicId').eq(topic_id)
            & boto3.dynamodb.conditions.Attr('status').eq('pending'),
    )
    count = result.get('Count', 0)

    if count >= AUTO_ARCHIVE_THRESHOLD:
        try:
            topics.update_item(
                Key={'topicId': topic_id, 'SK': 'META'},
                UpdateExpression='SET lifecycleStatus = :s, archivedReason = :r, archivedAt = :t',
                ExpressionAttributeValues={
                    ':s': 'archived',
                    ':r': f'auto:{category}:{count}件申告',
                    ':t': int(time.time()),
                },
                ConditionExpression=boto3.dynamodb.conditions.Attr('topicId').exists(),
            )
            print(f'自動archived: {topic_id} ({category} {count}件)')
            return True
        except Exception as e:
            print(f'auto-archive失敗: {e}')
    return False


def send_ses_notification(data, contact_id):
    """SES設定済みの場合のみ通知メールを送信"""
    if not TO_EMAIL:
        return
    try:
        ses = boto3.client('ses', region_name=SES_REGION)
        category_label = CATEGORIES[data['category']]
        body_text = f"""Flotopic お問い合わせ (ID: {contact_id})

■ 種別: {category_label}
■ トピックID: {data['topicId'] or '未指定'}
■ メッセージ:
{data['message']}

---
管理画面: https://flotopic.com/admin.html
"""
        ses.send_email(
            Source=FROM_EMAIL,
            Destination={'ToAddresses': [TO_EMAIL]},
            Message={
                'Subject': {'Data': f'[Flotopic] {category_label}', 'Charset': 'UTF-8'},
                'Body':    {'Text': {'Data': body_text, 'Charset': 'UTF-8'}},
            },
            ReplyToAddresses=[data['email']],
        )
    except Exception as e:
        # T2026-0502-S: print 一行を [ERROR] プレフィックス付きにし CloudWatch Logs metric filter で観測可能化。
        # 以前は silent print で過去 1 度 IAM AccessDenied が握り潰されていた (4/26 13:13)。
        print(f'[ERROR] SES send (notification) failed: {e}')


# T2026-0428-Z: カテゴリ別返信テンプレート（ADMIN_EMAIL宛ドラフト用）
_DRAFT_TEMPLATES = {
    'copyright': (
        '著作権に関するご申告を確認しました。'
        '内容を精査のうえ、48時間以内に対応いたします。'
        '問題が確認された場合は速やかに該当コンテンツを削除いたします。'
    ),
    'privacy': (
        'プライバシー・削除依頼を確認しました。'
        'ご指摘の情報を精査し、確認次第速やかに対応いたします。'
    ),
    'error': (
        '誤情報・内容に関するご指摘を確認しました。'
        '内容を精査のうえ修正対応いたします。'
        'ご報告いただきありがとうございます。'
    ),
    'media': (
        'メディア掲載除外申請を確認しました。'
        '内容を精査し、確認次第ご連絡いたします。'
    ),
    'other': (
        'お問い合わせを確認しました。'
        '内容を確認のうえ、改めてご連絡いたします。'
    ),
}


def send_draft_to_admin(data: dict, contact_id: str):
    """お問い合わせ受信時にカテゴリ別返信テンプレートを含むドラフトを ADMIN_EMAIL 宛に送信。
    ADMIN_EMAIL 宛のみなので SES sandbox 環境でも動作する。
    T2026-0428-Z: 自動対応ドラフト機能。
    """
    if not ADMIN_EMAIL:
        print('send_draft_to_admin: ADMIN_EMAIL 未設定のためスキップ')
        return
    try:
        import datetime
        ses = boto3.client('ses', region_name=SES_REGION)
        category_label = CATEGORIES.get(data['category'], data['category'])
        template = _DRAFT_TEMPLATES.get(data['category'], _DRAFT_TEMPLATES['other'])
        now_jst = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')

        body_text = f"""[Flotopic要対応] 新規お問い合わせ (ID: {contact_id})

━━━━ 受信情報 ━━━━
種別     : {category_label}
送信者   : {data['name']} <{data['email']}>
トピックID: {data['topicId'] or '未指定'}
受信日時 : {now_jst}

━━━━ メッセージ全文 ━━━━
{data['message']}

━━━━ 返信テンプレート案 ━━━━
（以下を参考に {data['name']} 様 <{data['email']}> 宛に返信してください）

{data['name']} 様

この度はFlotopicへのお問い合わせありがとうございます。

{template}

引き続きFlotopicをよろしくお願いいたします。

Flotopic 運営チーム

━━━━━━━━━━━━━━━━━━
管理画面で対応済みにする: https://flotopic.com/admin.html
━━━━━━━━━━━━━━━━━━
"""
        ses.send_email(
            Source=FROM_EMAIL,
            Destination={'ToAddresses': [ADMIN_EMAIL]},
            Message={
                'Subject': {
                    'Data': f'[Flotopic要対応] {category_label} - {data["name"]}様より',
                    'Charset': 'UTF-8',
                },
                'Body': {'Text': {'Data': body_text, 'Charset': 'UTF-8'}},
            },
            ReplyToAddresses=[data['email']],
        )
        print(f'send_draft_to_admin: sent to {ADMIN_EMAIL} (contact_id={contact_id})')
    except Exception as e:
        # T2026-0502-S: 同 metric filter で観測可能にする統一プレフィックス。
        print(f'[ERROR] SES send (draft) failed: {e}')


def list_contacts(limit=100) -> list:
    """flotopic-contacts テーブルから未対応件を取得して返す。
    T2026-0428-Z: resolved 済みを除外して未対応のみ返す。
    """
    result = contacts.scan(
        Limit=limit,
        FilterExpression=(
            boto3.dynamodb.conditions.Attr('status').exists()
            & boto3.dynamodb.conditions.Attr('status').ne('resolved')
        ),
    )
    items = result.get('Items', [])
    items.sort(key=lambda x: x.get('createdAt', 0), reverse=True)
    return items[:limit]


def resolve_contact(contact_id: str, topic_id: str, action: str) -> bool:
    """問い合わせを resolved にし、必要に応じてトピックをarchived化する。"""
    if action == 'archive' and topic_id:
        try:
            topics.update_item(
                Key={'topicId': topic_id, 'SK': 'META'},
                UpdateExpression='SET lifecycleStatus = :s, archivedReason = :r, archivedAt = :t',
                ExpressionAttributeValues={
                    ':s': 'archived',
                    ':r': 'admin:manual',
                    ':t': int(time.time()),
                },
                ConditionExpression=boto3.dynamodb.conditions.Attr('topicId').exists(),
            )
        except Exception as e:
            print(f'resolve_contact archive失敗: {e}')
    if contact_id:
        try:
            contacts.update_item(
                Key={'contactId': contact_id},
                UpdateExpression='SET #s = :r',
                ExpressionAttributeNames={'#s': 'status'},
                ExpressionAttributeValues={':r': 'resolved'},
            )
        except Exception as e:
            print(f'resolve_contact status更新失敗: {e}')
    return True


def resp_json(code, body_dict):
    return {
        'statusCode': code,
        'headers': {
            'Content-Type': 'application/json; charset=utf-8',
            'Access-Control-Allow-Origin': 'https://flotopic.com',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
        },
        'body': json.dumps(body_dict, ensure_ascii=False, default=str),
    }


def lambda_handler(event, context):
    method = event.get('requestContext', {}).get('http', {}).get('method', '')
    raw_path = event.get('rawPath', '') or event.get('path', '')

    if method == 'OPTIONS':
        return resp(200, 'ok')

    # ── 管理者向けエンドポイント ──────────────────────────────────────
    if raw_path in ('/contacts', '/contacts/') and method == 'GET':
        if not verify_admin_token(event):
            return resp(403, '認証が必要です')
        items = list_contacts()
        return resp_json(200, {'contacts': items})

    if raw_path in ('/contacts/resolve',) and method == 'POST':
        if not verify_admin_token(event):
            return resp(403, '認証が必要です')
        try:
            body = json.loads(event.get('body') or '{}')
        except json.JSONDecodeError:
            return resp(400, 'リクエストが不正です')
        contact_id = (body.get('contactId') or '').strip()
        topic_id   = (body.get('topicId')   or '').strip()
        action     = (body.get('action')    or 'resolve').strip()
        resolve_contact(contact_id, topic_id, action)
        return resp(200, '完了しました')

    # ── 公開エンドポイント: POST /contact ─────────────────────────────
    if method != 'POST':
        return resp(405, 'Method Not Allowed')

    try:
        body = json.loads(event.get('body') or '{}')
    except json.JSONDecodeError:
        return resp(400, 'リクエストが不正です')

    # T228 (2026-04-28): honeypot は first line of defense (静かに 200 返してスキャンを進めさせる)
    if body.get('website'):
        return resp(200, '送信しました')

    # T228: IP ハッシュベースのレート制限。5分3件 + 1日10件の二段ガード。
    ip_hash = _ip_hash(event)
    if not check_contact_rate_limit(ip_hash, 300, 3, 'burst'):
        print(f'[contact] rate limit hit (burst 5min/3) ip_hash={ip_hash}')
        return resp(429, '短時間に多くの送信が検出されました。5分ほど時間を空けて再度お試しください。')
    if not check_contact_rate_limit(ip_hash, 86400, 10, 'daily'):
        print(f'[contact] rate limit hit (daily 24h/10) ip_hash={ip_hash}')
        return resp(429, '本日の送信回数上限に達しました。明日以降に再度お試しください。')

    data, err = validate(body)
    if err:
        return resp(400, err)

    contact_id = save_to_dynamodb(data)
    check_auto_archive(data['category'], data['topicId'])
    send_ses_notification(data, contact_id)
    send_draft_to_admin(data, contact_id)  # T2026-0428-Z: カテゴリ別ドラフトを ADMIN_EMAIL 宛に送信

    return resp(200, '送信しました。内容を確認次第、対応いたします。')
