import json
import os
import re
import time
import boto3
from datetime import datetime, timezone
from decimal import Decimal

TABLE_NAME = os.environ.get('TABLE_NAME', 'p003-topics')
REGION     = os.environ.get('REGION', 'ap-northeast-1')
dynamodb   = boto3.resource('dynamodb', region_name=REGION)
table      = dynamodb.Table(TABLE_NAME)

# T2026-0502-SEC8 (2026-05-02): CORS Allow-Origin を `*` から自社ドメインに固定。
_ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get(
        'ALLOWED_ORIGINS',
        'https://flotopic.com,https://www.flotopic.com'
    ).split(',') if o.strip()
]


def _cors(event=None):
    headers = (event or {}).get('headers') or {}
    raw = headers.get('origin') or headers.get('Origin') or ''
    origin = raw if raw in _ALLOWED_ORIGINS else (_ALLOWED_ORIGINS[0] if _ALLOWED_ORIGINS else 'https://flotopic.com')
    return {
        'Access-Control-Allow-Origin': origin,
        'Access-Control-Allow-Methods': 'POST,OPTIONS',
        'Access-Control-Allow-Headers': 'content-type',
        'Vary': 'Origin',
    }


def lambda_handler(event, context):
    method = event.get('requestContext', {}).get('http', {}).get('method', '')
    cors = _cors(event)
    if method == 'OPTIONS':
        return {'statusCode': 200, 'headers': cors, 'body': ''}
    try:
        body = json.loads(event.get('body') or '{}')
        tid = body.get('topicId', '')
        if not tid:
            return {'statusCode': 400, 'headers': cors, 'body': 'missing topicId'}
        if not re.match(r'^[0-9a-f]{16}$', tid):
            return {'statusCode': 400, 'headers': cors, 'body': 'invalid topicId'}
        date = datetime.now(timezone.utc).strftime('%Y%m%d')
        ttl_ts = int(time.time()) + 90 * 86400
        table.update_item(
            Key={'topicId': tid, 'SK': f'VIEW#{date}'},
            UpdateExpression='ADD #c :one SET #d = :date, #ttl = :ttl',
            ExpressionAttributeNames={'#c': 'count', '#d': 'date', '#ttl': 'ttl'},
            ExpressionAttributeValues={':one': Decimal('1'), ':date': date, ':ttl': Decimal(str(ttl_ts))},
        )
        return {'statusCode': 200, 'headers': cors, 'body': json.dumps({'ok': True})}
    except Exception as e:
        # T2026-0502-SEC16: 内部例外メッセージを返さず固定文言に。
        print(f'[ERROR] Tracker: {type(e).__name__}: {e}')
        return {'statusCode': 500, 'headers': cors, 'body': json.dumps({'error': 'tracker error'})}
