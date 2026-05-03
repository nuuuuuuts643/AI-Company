import json
import os
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

TABLE_NAME = os.environ.get('TABLE_NAME', 'p003-topics')
REGION     = os.environ.get('REGION', 'ap-northeast-1')
S3_BUCKET  = os.environ.get('S3_BUCKET', '')

dynamodb = boto3.resource('dynamodb', region_name=REGION)
table    = dynamodb.Table(TABLE_NAME)
s3       = boto3.client('s3', region_name=REGION) if S3_BUCKET else None


def dec(obj):
    if isinstance(obj, Decimal):
        f = float(obj)
        return int(f) if f == int(f) else f
    raise TypeError


# T2026-0502-SEC8 (2026-05-02): CORS Allow-Origin を `*` から自社ドメインに固定。
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


def resp(code, body, event=None):
    return {
        'statusCode': code,
        'headers': {
            'Content-Type': 'application/json; charset=utf-8',
            'Access-Control-Allow-Origin': _resolve_origin(event),
            'Vary': 'Origin',
        },
        'body': json.dumps(body, default=dec, ensure_ascii=False),
    }


def all_topics():
    # T2026-STEP2: S3 のみ（DDB フォールバック削除）。S3 失敗時は例外を raise し呼び出し元が 503 を返す。
    if not S3_BUCKET or not s3:
        raise RuntimeError('S3_BUCKET not configured')
    obj = s3.get_object(Bucket=S3_BUCKET, Key='api/topics-card.json')
    data = json.loads(obj['Body'].read())
    return data.get('topics', [])


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
        try:
            return resp(200, {'topics': all_topics()})
        except Exception as e:
            print(f'[ERROR] all_topics failed: {e}')
            return resp(503, {'error': 'service unavailable'})

    if path.startswith('/topic/'):
        tid = path.split('/')[-1]
        # COST-C1: S3優先・api/topic/{tid}.jsonが存在する場合はDDBクエリを省略。
        if S3_BUCKET and s3:
            try:
                obj = s3.get_object(Bucket=S3_BUCKET, Key=f'api/topic/{tid}.json')
                return resp(200, json.loads(obj['Body'].read()))
            except s3.exceptions.NoSuchKey:
                pass
            except Exception as e:
                print(f'[WARN] /topic/{tid} S3 read failed, falling back to DDB: {e}')
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
