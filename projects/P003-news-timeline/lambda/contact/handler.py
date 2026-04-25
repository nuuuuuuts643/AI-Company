"""
Flotopic お問い合わせフォーム Lambda
- POST /contact → フォーム内容をSES経由でメール送信

入力:
  { "name": str, "email": str, "category": str, "message": str, "honeypot": str }

honeypot フィールドが空でない場合はスパムとして無視（200を返してボットに気づかせない）
"""

import json
import os
import re

import boto3

SES_REGION  = os.environ.get('SES_REGION', 'us-east-1')
FROM_EMAIL  = os.environ.get('FROM_EMAIL', 'contact@flotopic.com')
TO_EMAIL    = os.environ.get('TO_EMAIL', 'mrkm.naoya643@gmail.com')

ses = boto3.client('ses', region_name=SES_REGION)

CATEGORIES = {
    'copyright': '著作権侵害申告',
    'privacy':   'プライバシー・削除依頼',
    'error':     '誤情報・内容指摘',
    'media':     'メディア掲載除外申請',
    'other':     'その他',
}


def resp(code, msg):
    return {
        'statusCode': code,
        'headers': {
            'Content-Type': 'application/json; charset=utf-8',
            'Access-Control-Allow-Origin': 'https://flotopic.com',
            'Access-Control-Allow-Headers': 'Content-Type',
        },
        'body': json.dumps({'message': msg}, ensure_ascii=False),
    }


def validate(data):
    name    = (data.get('name') or '').strip()[:100]
    email   = (data.get('email') or '').strip()[:200]
    category = (data.get('category') or '').strip()
    message = (data.get('message') or '').strip()[:2000]

    if not name:
        return None, 'お名前を入力してください'
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        return None, 'メールアドレスの形式が正しくありません'
    if category not in CATEGORIES:
        return None, '問い合わせ種別が不正です'
    if len(message) < 10:
        return None, 'メッセージは10文字以上入力してください'

    return {'name': name, 'email': email, 'category': category, 'message': message}, None


def lambda_handler(event, context):
    method = event.get('requestContext', {}).get('http', {}).get('method', '')

    if method == 'OPTIONS':
        return resp(200, 'ok')

    if method != 'POST':
        return resp(405, 'Method Not Allowed')

    try:
        body = json.loads(event.get('body') or '{}')
    except json.JSONDecodeError:
        return resp(400, 'リクエストが不正です')

    # ハニーポット（隠しフィールド）が埋まっていたらスパム
    if body.get('website'):
        return resp(200, '送信しました')

    data, err = validate(body)
    if err:
        return resp(400, err)

    category_label = CATEGORIES[data['category']]
    subject = f"[Flotopic お問い合わせ] {category_label}"
    body_text = f"""Flotopic お問い合わせフォームから送信されました。

■ 種別: {category_label}
■ お名前: {data['name']}
■ メールアドレス: {data['email']}

■ メッセージ:
{data['message']}

---
返信先: {data['email']}
"""

    try:
        ses.send_email(
            Source=FROM_EMAIL,
            Destination={'ToAddresses': [TO_EMAIL]},
            Message={
                'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                'Body':    {'Text': {'Data': body_text, 'Charset': 'UTF-8'}},
            },
            ReplyToAddresses=[data['email']],
        )
    except Exception as e:
        print(f"SES send error: {e}")
        return resp(500, '送信に失敗しました。しばらく後にお試しください。')

    return resp(200, '送信しました。3営業日以内にご連絡いたします。')
