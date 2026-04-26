"""
Flotopic お問い合わせフォーム Lambda
- POST /contact → DynamoDB保存 + SES通知（設定済みの場合のみ）
- 同一トピックへの削除依頼が3件以上 → トピックを自動archived化

入力:
  { "name": str, "email": str, "category": str, "message": str, "topicId": str(任意), "honeypot": str }
"""

import json
import os
import re
import time
import uuid

import boto3
from boto3.dynamodb.conditions import Key

SES_REGION    = os.environ.get('SES_REGION', 'us-east-1')
FROM_EMAIL    = os.environ.get('FROM_EMAIL', 'contact@flotopic.com')
TO_EMAIL      = os.environ.get('TO_EMAIL', '')
CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'flotopic-contacts')
TOPICS_TABLE   = os.environ.get('TOPICS_TABLE', 'p003-topics')
AUTO_ARCHIVE_THRESHOLD = int(os.environ.get('AUTO_ARCHIVE_THRESHOLD', '3'))

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
        print(f'SES通知スキップ: {e}')


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

    if body.get('website'):
        return resp(200, '送信しました')

    data, err = validate(body)
    if err:
        return resp(400, err)

    contact_id = save_to_dynamodb(data)
    check_auto_archive(data['category'], data['topicId'])
    send_ses_notification(data, contact_id)

    return resp(200, '送信しました。内容を確認次第、対応いたします。')
