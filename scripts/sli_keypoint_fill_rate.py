#!/usr/bin/env python3
"""T2026-0428-BG: SLI-keypoint-fill-rate — DynamoDB scan による keyPoint 充填率観測。

目的:
    pending_ai.json: 40 → 950 件 遡及キュー投入 (T2026-0428-AW) の効果を外部観測する。
    既存 SLI 8 (freshness-check.yml の AI フィールド充填率) は topics.json (articleCount>=3
    の公開対象のみ) を見るため、DB 全体の真の状態が見えない。本 SLI は DynamoDB を直接
    scan し、ac>=2 の全 META に対する keyPoint 充填率を計算する。

仕様:
    入力: なし (DynamoDB scan)
    対象: SK=META, lifecycleStatus not in (archived/legacy/deleted), articleCount>=2
    出力: stdout に key=value 形式 (GitHub Actions $GITHUB_OUTPUT 用)。
          - kp_fill_rate=<float>
          - eligible_total=<int>
          - kp_filled=<int>
          - status=ok|warn|error|skipped
    終了コード: 0 = OK, 1 = ERROR (rate <= 5%), warn は exit 0 (continue-on-error 想定)

閾値 (T2026-0428-BG 実装時 現在値 10.02% を基準):
    - rate >  10.0%: ok      (改善傾向)
    - rate <= 10.0%: warn    (現状停滞)
    - rate <=  5.0%: error   (パイプライン壊滅)

コスト:
    DynamoDB on-demand: scan 1 回あたり ~1000 RCU 程度想定 (META 件数依存)。
    hourly 実行で月 ~720 scan = 数十円規模。Lambda/Anthropic は呼ばない。
"""
from __future__ import annotations

import os
import sys

import boto3
from boto3.dynamodb.conditions import Attr

REGION = 'ap-northeast-1'
TABLE = 'p003-topics'

WARN_THRESHOLD = 10.0
ERROR_THRESHOLD = 5.0


def _is_empty(v) -> bool:
    if v is None:
        return True
    if isinstance(v, str) and not v.strip():
        return True
    if isinstance(v, (list, dict)) and len(v) == 0:
        return True
    return False


def scan_meta(table) -> list[dict]:
    items: list[dict] = []
    kwargs = {'FilterExpression': Attr('SK').eq('META')}
    while True:
        r = table.scan(**kwargs)
        items.extend(r.get('Items', []))
        last = r.get('LastEvaluatedKey')
        if not last:
            break
        kwargs['ExclusiveStartKey'] = last
    return items


def compute_fill_rate(metas: list[dict]) -> tuple[int, int, float]:
    eligible = 0
    filled = 0
    for m in metas:
        if m.get('lifecycleStatus') in ('archived', 'legacy', 'deleted'):
            continue
        try:
            ac = int(m.get('articleCount', 0) or 0)
        except (ValueError, TypeError):
            ac = 0
        if ac < 2:
            continue
        eligible += 1
        if not _is_empty(m.get('keyPoint')):
            filled += 1
    rate = (filled * 100.0 / eligible) if eligible > 0 else 0.0
    return eligible, filled, rate


def emit(key: str, value) -> None:
    """stdout (人読み) と $GITHUB_OUTPUT (CI 連携) 両方に書く。"""
    print(f'{key}={value}')
    gh_out = os.environ.get('GITHUB_OUTPUT')
    if gh_out:
        with open(gh_out, 'a') as f:
            f.write(f'{key}={value}\n')


def main() -> int:
    try:
        ddb = boto3.resource('dynamodb', region_name=REGION)
        table = ddb.Table(TABLE)
        metas = scan_meta(table)
    except Exception as e:
        print(f'[sli_keypoint_fill_rate] scan failed: {e}', file=sys.stderr)
        emit('status', 'skipped')
        emit('kp_fill_rate', '-1')
        emit('eligible_total', '0')
        emit('kp_filled', '0')
        return 0  # skip ではジョブを赤くしない (continue-on-error 同等)

    eligible, filled, rate = compute_fill_rate(metas)

    if eligible == 0:
        status = 'skipped'
    elif rate <= ERROR_THRESHOLD:
        status = 'error'
    elif rate <= WARN_THRESHOLD:
        status = 'warn'
    else:
        status = 'ok'

    emit('status', status)
    emit('kp_fill_rate', f'{rate:.2f}')
    emit('eligible_total', eligible)
    emit('kp_filled', filled)

    print(
        f'[sli_keypoint_fill_rate] eligible={eligible} filled={filled} '
        f'rate={rate:.2f}% status={status}',
        file=sys.stderr,
    )
    return 1 if status == 'error' else 0


if __name__ == '__main__':
    sys.exit(main())
