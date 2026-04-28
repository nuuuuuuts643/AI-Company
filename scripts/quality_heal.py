#!/usr/bin/env python3
"""T2026-0428-AO: 品質監視 cron。DynamoDB 全トピックをスキャンし、品質劣化を検出した
トピックを needs_ai_processing=True (pendingAI=True) にセットする。

検出条件:
  1. keyPoint が null/空
  2. articleCount = 0 または欠落 (空トピック → 即削除候補・別途 cleanup スクリプトで処理)
  3. schemaVersion < PROCESSOR_SCHEMA_VERSION (古いスキーマで処理されたトピック)
  4. statusLabel/watchPoints が articleCount>=3 で空 (現スキーマ必須)

T2026-0428-AO 重要原則:
  本スクリプトは pendingAI=True フラグだけセットする。AI フィールドは絶対に上書きしない。
  既存の良いデータは processor (incremental モード) が保持し、不足分のみ補完する。

実行:
  dry-run: python3 scripts/quality_heal.py
  実行:    python3 scripts/quality_heal.py --apply

GitHub Actions 日次ジョブとして登録 (.github/workflows/quality-heal.yml)。
"""
import argparse
import json
import os
import sys
from collections import Counter

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


def scan_meta_with_quality_issues(table):
    """全 META をスキャンして品質劣化のあるトピックを返す。
    DynamoDB 側で軽くフィルタしつつ、最終判定はクライアント側で行う。"""
    items = []
    kwargs = {
        'FilterExpression': Attr('SK').eq('META'),
    }
    while True:
        r = table.scan(**kwargs)
        items.extend(r.get('Items', []))
        last = r.get('LastEvaluatedKey')
        if not last:
            break
        kwargs['ExclusiveStartKey'] = last
    return items


def find_unhealthy(metas):
    """品質劣化トピックを抽出。"""
    unhealthy = []
    reasons_counter = Counter()
    for m in metas:
        tid = m.get('topicId')
        if not tid:
            continue
        try:
            ac = int(m.get('articleCount', 0) or 0)
        except (ValueError, TypeError):
            ac = 0
        # ac<2 はフロントで非表示なので heal 対象外 (processor もスキップする)
        if ac < 2:
            continue
        try:
            sv = int(m.get('schemaVersion', 0) or 0)
        except (ValueError, TypeError):
            sv = 0
        # archived/legacy/deleted は触らない (lifecycle Lambda の管轄)
        lifecycle = m.get('lifecycleStatus', '')
        if lifecycle in ('archived', 'legacy', 'deleted'):
            continue

        reasons = []
        if _is_empty(m.get('keyPoint')):
            reasons.append('keyPoint空')
        if sv < PROCESSOR_SCHEMA_VERSION:
            reasons.append(f'schemaVersion={sv}<{PROCESSOR_SCHEMA_VERSION}')
        if ac >= 3:
            if _is_empty(m.get('statusLabel')):
                reasons.append('statusLabel空')
            if _is_empty(m.get('watchPoints')):
                reasons.append('watchPoints空')
            if _is_empty(m.get('storyTimeline')):
                reasons.append('storyTimeline空')
            if _is_empty(m.get('storyPhase')):
                reasons.append('storyPhase空')

        if reasons:
            unhealthy.append({'topicId': tid, 'reasons': reasons,
                              'title': (m.get('title') or '')[:40], 'ac': ac, 'sv': sv})
            for r in reasons:
                reasons_counter[r] += 1

    return unhealthy, reasons_counter


def mark_for_reprocess(table, tid):
    """pendingAI=True だけセット。既存 AI フィールドは絶対に上書きしない。"""
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
        print(f'[quality_heal] mark error tid={tid}: {e}', file=sys.stderr)
        return False


def update_pending_ai_json(s3, bucket, tids):
    """既存 pending_ai.json に tids を追加 (重複排除)。"""
    try:
        try:
            resp = s3.get_object(Bucket=bucket, Key='api/pending_ai.json')
            cur = json.loads(resp['Body'].read())
            cur_ids = list(cur.get('topicIds', []))
        except Exception:
            cur_ids = []
        merged = list(dict.fromkeys(cur_ids + list(tids)))
        s3.put_object(
            Bucket=bucket, Key='api/pending_ai.json',
            Body=json.dumps({'topicIds': merged}).encode('utf-8'),
            ContentType='application/json',
        )
        return len(cur_ids), len(merged)
    except Exception as e:
        print(f'[quality_heal] pending_ai.json 更新失敗: {e}', file=sys.stderr)
        return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='実行 (デフォルト dry-run)')
    ap.add_argument('--limit', type=int, default=0, help='処理件数上限 (0=無制限)')
    ap.add_argument('--bucket', default=S3_BUCKET)
    args = ap.parse_args()

    dynamo = boto3.resource('dynamodb', region_name=REGION)
    table = dynamo.Table(TABLE)
    s3 = boto3.client('s3', region_name=REGION)

    print('[quality_heal] DynamoDB スキャン中...')
    metas = scan_meta_with_quality_issues(table)
    print(f'[quality_heal] META 取得: {len(metas)} 件')

    unhealthy, reasons_counter = find_unhealthy(metas)
    print(f'[quality_heal] 品質劣化検出: {len(unhealthy)} 件')
    print('[quality_heal] 理由別集計:')
    for r, c in reasons_counter.most_common():
        print(f'  {r}: {c}')

    if args.limit and len(unhealthy) > args.limit:
        print(f'[quality_heal] limit={args.limit} を超過。先頭 {args.limit} 件のみ処理。')
        unhealthy = unhealthy[:args.limit]

    if not unhealthy:
        print('[quality_heal] クリーン。終了。')
        return 0

    print('[quality_heal] 先頭 5 件サンプル:')
    for u in unhealthy[:5]:
        print(f'  - {u["topicId"][:12]}... ac={u["ac"]} sv={u["sv"]} reasons={u["reasons"]} | {u["title"]}')

    if not args.apply:
        print('[quality_heal] dry-run のみ。--apply で実行。')
        return 0

    marked = 0
    queued_tids = []
    for u in unhealthy:
        if mark_for_reprocess(table, u['topicId']):
            marked += 1
            queued_tids.append(u['topicId'])
    print(f'[quality_heal] pendingAI=True セット完了: {marked} 件')

    if queued_tids:
        before, after = update_pending_ai_json(s3, args.bucket, queued_tids)
        if before is not None:
            print(f'[quality_heal] pending_ai.json: {before} → {after} 件')

    return 0


if __name__ == '__main__':
    sys.exit(main())
