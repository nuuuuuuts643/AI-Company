import json
import os
import time
import boto3
from datetime import datetime, timezone
from decimal import Decimal

TABLE_NAME = os.environ.get('TABLE_NAME', 'p003-topics')
REGION     = os.environ.get('REGION', 'ap-northeast-1')
dynamodb   = boto3.resource('dynamodb', region_name=REGION)
table      = dynamodb.Table(TABLE_NAME)

CORS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST,OPTIONS',
    'Access-Control-Allow-Headers': 'content-type',
}


def lambda_handler(event, context):
    method = event.get('requestContext', {}).get('http', {}).get('method', '')
    if method == 'OPTIONS':
        return {'statusCode': 200, 'headers': CORS, 'body': ''}
    try:
        body = json.loads(event.get('body') or '{}')
        tid = body.get('topicId', '')
        if not tid:
            return {'statusCode': 400, 'headers': CORS, 'body': 'missing topicId'}
        date = datetime.now(timezone.utc).strftime('%Y%m%d')
        ttl_ts = int(time.time()) + 90 * 86400
        table.update_item(
            Key={'topicId': tid, 'SK': f'VIEW#{date}'},
            UpdateExpression='ADD #c :one SET #d = :date, #ttl = :ttl',
            ExpressionAttributeNames={'#c': 'count', '#d': 'date', '#ttl': 'ttl'},
            ExpressionAttributeValues={':one': Decimal('1'), ':date': date, ':ttl': Decimal(str(ttl_ts))},
        )
        return {'statusCode': 200, 'headers': CORS, 'body': json.dumps({'ok': True})}
    except Exception as e:
        print(f'Tracker error: {e}')
        return {'statusCode': 500, 'headers': CORS, 'body': str(e)}
