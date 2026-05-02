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

# E2-2 (2026-04-28 PM): proc_storage.py の KEYPOINT_MIN_LENGTH と一致させる。
# proc_storage 側は不十分扱いで再処理対象化するが、quality_heal が _is_empty しか
# 見ていないと「短い keyPoint」を pending_ai.json に投入しない。
# 結果、aiGenerated=True で短い keyPoint のトピックは再処理キューに入らず滞留した
# (本番 100 件 / 1-99 字、99 件は pendingAI=False のまま固着)。
KEYPOINT_MIN_LENGTH = 100

# T2026-0502-MU-FOLLOWUP: handler.py:_expected_mode / _is_mode_upgrade と完全一致させる。
# Lambda 側が source-of-truth。閾値変更時は lambda/processor/handler.py と両方を同期すること。
_MODE_RANK = {'minimal': 0, 'standard': 1, 'full': 2}


def _expected_mode(cnt: int) -> str:
    """handler.py:_expected_mode と同期。cnt から期待 summaryMode を返す。"""
    if cnt <= 2:
        return 'minimal'
    if cnt <= 5:
        return 'standard'
    return 'full'


def _is_mode_upgrade(current: str, expected: str) -> bool:
    """handler.py:_is_mode_upgrade と同期。昇格方向のみ True。"""
    if current not in _MODE_RANK or expected not in _MODE_RANK:
        return False
    return _MODE_RANK[expected] > _MODE_RANK[current]


def _is_empty(v):
    if v is None:
        return True
    if isinstance(v, str) and not v.strip():
        return True
    if isinstance(v, (list, dict)) and len(v) == 0:
        return True
    return False


def _is_keypoint_inadequate(v):
    """proc_storage.py._is_keypoint_inadequate と同等。
    空 / 100 字未満を「不十分」と判定する。"""
    if _is_empty(v):
        return True
    if isinstance(v, str) and len(v.strip()) < KEYPOINT_MIN_LENGTH:
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
    """品質劣化トピックを抽出。重要度 (articleCount DESC, score DESC) でソートして返す。

    T2026-0428-AW: pending_ai.json は append 順だが、processor 側 _sort_key で
    最終順序が決まる (score DESC が支配的)。それでもキューに早く入る方が
    1サイクル目で拾われる確率が上がるため、ここでも降順で投入する。
    """
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
        try:
            score = int(m.get('score', 0) or 0)
        except (ValueError, TypeError):
            score = 0
        # archived/legacy/deleted は触らない (lifecycle Lambda の管轄)
        lifecycle = m.get('lifecycleStatus', '')
        if lifecycle in ('archived', 'legacy', 'deleted'):
            continue

        reasons = []
        # E2-2 (2026-04-28 PM): 空だけでなく 100 字未満の短い keyPoint も再処理対象に含める。
        # proc_storage.py 側の `_is_keypoint_inadequate` と一致させ、aiGenerated=True で
        # 短い keyPoint (1-99 字) が pendingAI=False のまま放置される問題を解消する。
        if _is_keypoint_inadequate(m.get('keyPoint')):
            kp = m.get('keyPoint')
            if _is_empty(kp):
                reasons.append('keyPoint空')
            else:
                reasons.append(f'keyPoint短い({len(str(kp).strip())}字<100)')
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
                              'title': (m.get('title') or '')[:40],
                              'ac': ac, 'sv': sv, 'score': score})
            for r in reasons:
                reasons_counter[r] += 1

    unhealthy.sort(key=lambda u: (-u['ac'], -u['score']))
    return unhealthy, reasons_counter


def find_mode_mismatch_topics(metas):
    """aiGenerated=True かつ summaryMode が articleCount 期待値より低いトピックを検出。

    T2026-0502-MU-FOLLOWUP: PR #162 は processor 内の needs_story 判定 (下流) のみ
    修正したが、pendingAI=null のトピックは pending queue に入らないため上流で拾えない。
    本関数は scan 済みの metas を再利用して upgrade 候補を発見し (二重 DDB scan 禁止)、
    mark_for_reprocess で pendingAI=True にセットすることで次の processor 実行で処理される。

    _expected_mode / _is_mode_upgrade は handler.py と論理完全一致。閾値変更時は同期必須。
    """
    mismatches = []
    for m in metas:
        tid = m.get('topicId')
        if not tid:
            continue
        if not m.get('aiGenerated'):
            continue
        if m.get('pendingAI') is True:
            continue  # 既にキューイング済み、二重キューイング防止
        current_mode = m.get('summaryMode')
        if not current_mode:
            continue  # summaryMode 未設定はスキップ (別の heal ルートで対処)
        lifecycle = m.get('lifecycleStatus', '')
        if lifecycle in ('archived', 'legacy', 'deleted'):
            continue
        try:
            ac = int(m.get('articleCount', 0) or 0)
        except (ValueError, TypeError):
            ac = 0
        if ac < 2:
            continue  # フロント非表示なので heal 対象外
        try:
            score = int(m.get('score', 0) or 0)
        except (ValueError, TypeError):
            score = 0

        expected = _expected_mode(ac)
        if not _is_mode_upgrade(current_mode, expected):
            continue

        print(f'[mode-upgrade-rescue] tid={tid} from={current_mode} to={expected} cnt={ac}')
        mismatches.append({
            'topicId': tid,
            'reasons': [f'mode-upgrade:{current_mode}→{expected}(cnt={ac})'],
            'title': (m.get('title') or '')[:40],
            'ac': ac, 'sv': 0, 'score': score,
        })

    mismatches.sort(key=lambda u: (-u['ac'], -u['score']))
    return mismatches


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
    """既存 pending_ai.json に tids を追加 (重複排除)。
    T2026-0428-AW: 新規 unhealthy IDs は **先頭** に挿入。
    最終的な処理順序は processor 側 _sort_key で決まるが、pending_ai.json
    そのものを iterate するパスに対しては前方が有利 (DDB GetItem ループの
    早期に登場する)。"""
    try:
        try:
            resp = s3.get_object(Bucket=bucket, Key='api/pending_ai.json')
            cur = json.loads(resp['Body'].read())
            cur_ids = list(cur.get('topicIds', []))
        except Exception:
            cur_ids = []
        # tids 先頭 + 既存 cur_ids、重複排除 (dict.fromkeys は最初に出た順を保つ)
        merged = list(dict.fromkeys(list(tids) + cur_ids))
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

    mode_mismatches = find_mode_mismatch_topics(metas)
    print(f'[quality_heal] mode upgrade 候補検出: {len(mode_mismatches)} 件')
    existing_tids = {u['topicId'] for u in unhealthy}
    new_mismatches = [m for m in mode_mismatches if m['topicId'] not in existing_tids]
    if new_mismatches:
        print(f'[quality_heal] うち品質劣化未登録: {len(new_mismatches)} 件 → 追加')
        unhealthy.extend(new_mismatches)
        unhealthy.sort(key=lambda u: (-u['ac'], -u['score']))

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
