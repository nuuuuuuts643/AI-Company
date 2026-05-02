import json
import os
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

TABLE_NAME = os.environ.get('TABLE_NAME', 'p003-topics')
REGION     = os.environ.get('REGION', 'ap-northeast-1')

dynamodb = boto3.resource('dynamodb', region_name=REGION)
table    = dynamodb.Table(TABLE_NAME)


def dec(obj):
    if isinstance(obj, Decimal):
        f = float(obj)
        return int(f) if f == int(f) else f
    raise TypeError


def resp(code, body):
    return {
        'statusCode': code,
        'headers': {
            'Content-Type': 'application/json; charset=utf-8',
            'Access-Control-Allow-Origin': '*',
        },
        'body': json.dumps(body, default=dec, ensure_ascii=False),
    }


def all_topics():
    items = []
    # SK(sort key) は FilterExpression に使用不可 → 全件 Scan して Python 側で絞る
    kwargs = {
        'ProjectionExpression': 'topicId, title, #s, articleCount, articleCountDelta, lastUpdated, sources, SK',
        'ExpressionAttributeNames': {'#s': 'status'},
    }
    while True:
        r = table.scan(**kwargs)
        items.extend(item for item in r.get('Items', []) if item.get('SK') == 'META')
        last = r.get('LastEvaluatedKey')
        if not last:
            break
        kwargs['ExclusiveStartKey'] = last
    items.sort(key=lambda x: x.get('lastUpdated', ''), reverse=True)
    return items


def topic_detail(topic_id):
    items = []
    kwargs = {'KeyConditionExpression': Key('topicId').eq(topic_id)}
    while True:
        r = table.query(**kwargs)
        items.extend(r.get('Items', []))
        last = r.get('LastEvaluatedKey')
        if not last:
            break
        kwargs['ExclusiveStartKey'] = last
    meta  = next((i for i in items if i['SK'] == 'META'), None)
    snaps = sorted([i for i in items if i['SK'].startswith('SNAP#')], key=lambda x: x['SK'])
    return meta, snaps


def lambda_handler(event, context):
    path   = event.get('rawPath', '/')
    method = event.get('requestContext', {}).get('http', {}).get('method', 'GET')

    if method == 'OPTIONS':
        return resp(200, {})

    if path in ('/', '/topics'):
        return resp(200, {'topics': all_topics()})

    if path.startswith('/topic/'):
        tid = path.split('/')[-1]
        meta, snaps = topic_detail(tid)
        if not meta:
            return resp(404, {'error': 'not found'})
        _INTERNAL = {'SK', 'pendingAI', 'ttl'}
        pub_meta = {k: v for k, v in meta.items() if k not in _INTERNAL}
        return resp(200, {
            'meta': pub_meta,
            'timeline': [
                {
                    'timestamp':    s['timestamp'],
                    'articleCount': s['articleCount'],
                    'articles':     s.get('articles', []),
                }
                for s in snaps
            ],
        })

    return resp(404, {'error': 'not found'})
