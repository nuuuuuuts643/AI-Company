#!/usr/bin/env python3
"""T2026-0428-AO: bulk_heal.sh から呼ばれる heal キュー投入実装。

モード:
  all          全可視トピック (topics.json) を pendingAI=True
  no-keypoint  keyPoint 空のトピックだけ
  old-schema   schemaVersion < PROCESSOR_SCHEMA_VERSION のトピック

T2026-0428-AO 重要原則:
  pendingAI フラグだけセット。既存 AI フィールドは絶対に上書きしない。
  processor 側 (incremental モード) が不足フィールドだけ補完する。
"""
import json
import os
import sys

import boto3
from boto3.dynamodb.conditions import Attr

REGION = 'ap-northeast-1'
TABLE = 'p003-topics'
PROCESSOR_SCHEMA_VERSION = 3
S3_BUCKET = os.environ.get('S3_BUCKET', 'p003-news-946554699567')


def _is_empty(v):
    if v is None:
        return True
    if isinstance(v, str) and not v.strip():
        return True
    if isinstance(v, (list, dict)) and len(v) == 0:
        return True
    return False


def _scan_meta(table):
    items = []
    kwargs = {'FilterExpression': Attr('SK').eq('META')}
    while True:
        r = table.scan(**kwargs)
        items.extend(r.get('Items', []))
        last = r.get('LastEvaluatedKey')
        if not last:
            break
        kwargs['ExclusiveStartKey'] = last
    return items


def _load_visible_tids(s3, bucket):
    try:
        resp = s3.get_object(Bucket=bucket, Key='api/topics.json')
        data = json.loads(resp['Body'].read())
        topics = data.get('topics', []) if isinstance(data, dict) else (data or [])
        return {t.get('topicId') for t in topics if t.get('topicId')}
    except Exception:
        return set()


def _filter_targets(metas, mode, visible_tids):
    targets = []
    for m in metas:
        tid = m.get('topicId')
        if not tid:
            continue
        try:
            ac = int(m.get('articleCount', 0) or 0)
        except (ValueError, TypeError):
            ac = 0
        if ac < 2:
            continue
        lifecycle = m.get('lifecycleStatus', '')
        if lifecycle in ('archived', 'legacy', 'deleted'):
            continue
        try:
            sv = int(m.get('schemaVersion', 0) or 0)
        except (ValueError, TypeError):
            sv = 0

        if mode == 'all':
            if tid in visible_tids:
                targets.append(tid)
        elif mode == 'no-keypoint':
            if _is_empty(m.get('keyPoint')):
                targets.append(tid)
        elif mode == 'old-schema':
            if sv < PROCESSOR_SCHEMA_VERSION:
                targets.append(tid)
    return targets


def _mark(table, tid):
    try:
        table.update_item(
            Key={'topicId': tid, 'SK': 'META'},
            UpdateExpression='SET pendingAI = :p',
            ConditionExpression='attribute_exists(topicId)',
            ExpressionAttributeValues={':p': True},
        )
        return True
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return False
    except Exception as e:
        print(f'[bulk_heal] mark error tid={tid}: {e}', file=sys.stderr)
        return False


def _update_pending_json(s3, bucket, tids):
    try:
        try:
            r = s3.get_object(Bucket=bucket, Key='api/pending_ai.json')
            cur = list(json.loads(r['Body'].read()).get('topicIds', []))
        except Exception:
            cur = []
        merged = list(dict.fromkeys(cur + list(tids)))
        s3.put_object(
            Bucket=bucket, Key='api/pending_ai.json',
            Body=json.dumps({'topicIds': merged}).encode('utf-8'),
            ContentType='application/json',
        )
        return len(cur), len(merged)
    except Exception as e:
        print(f'[bulk_heal] pending_ai.json 更新失敗: {e}', file=sys.stderr)
        return None, None


def main():
    if len(sys.argv) < 2:
        print('Usage: bulk_heal_python.py {all|no-keypoint|old-schema} [--apply]', file=sys.stderr)
        return 2
    mode = sys.argv[1]
    apply = '--apply' in sys.argv

    if mode not in ('all', 'no-keypoint', 'old-schema'):
        print(f'Unknown mode: {mode}', file=sys.stderr)
        return 2

    dynamo = boto3.resource('dynamodb', region_name=REGION)
    table = dynamo.Table(TABLE)
    s3 = boto3.client('s3', region_name=REGION)

    print(f'[bulk_heal] mode={mode} apply={apply}')
    metas = _scan_meta(table)
    print(f'[bulk_heal] META 取得: {len(metas)} 件')
    visible_tids = _load_visible_tids(s3, S3_BUCKET) if mode == 'all' else set()
    if mode == 'all':
        print(f'[bulk_heal] visible (topics.json): {len(visible_tids)} 件')

    targets = _filter_targets(metas, mode, visible_tids)
    print(f'[bulk_heal] heal 対象: {len(targets)} 件')

    if not targets:
        print('[bulk_heal] 対象なし。終了。')
        return 0

    print('[bulk_heal] 先頭 5 件:')
    for t in targets[:5]:
        print(f'  - {t}')

    if not apply:
        print('[bulk_heal] dry-run のみ。APPLY=1 で実行。')
        return 0

    ok = 0
    queued = []
    for tid in targets:
        if _mark(table, tid):
            ok += 1
            queued.append(tid)
    print(f'[bulk_heal] pendingAI=True セット完了: {ok} 件')
    if queued:
        b, a = _update_pending_json(s3, S3_BUCKET, queued)
        if b is not None:
            print(f'[bulk_heal] pending_ai.json: {b} → {a} 件')
    return 0


if __name__ == '__main__':
    sys.exit(main())
