#!/usr/bin/env python3
"""
T2026-0502-Z: SLI 16-19 — ユーザーアクティビティメトリクス

SLI-16: DAU  (Daily Active Users)   直近24h のユニークユーザー数
SLI-17: WAU  (Weekly Active Users)  直近7日のユニークユーザー数
SLI-18: 再訪率 = DAU の中で前日も来たユーザーの割合
SLI-19: 平均滞在時間 (セッション終了イベント未実装のため N/A)

データソース:
    DynamoDB テーブル p003-topics の ANALYTICS#USER_DAY パーティション。
    SK: YYYYMMDD#<fingerprint16hex>  TTL: 9日

出力 (stdout + $GITHUB_OUTPUT):
    key=value 形式。GitHub Actions から --dry-run なしで呼ぶ場合は
    TABLE_NAME / REGION 環境変数を設定すること。

使い方:
    python3 scripts/sli_user_metrics.py              # live DynamoDB
    python3 scripts/sli_user_metrics.py --dry-run    # モック出力 (DynamoDB 不要)
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

TABLE = os.environ.get('TABLE_NAME', 'p003-topics')
REGION = os.environ.get('REGION', 'ap-northeast-1')
ANALYTICS_PK = 'ANALYTICS#USER_DAY'

DAU_WARN_THRESHOLD = 1
WAU_WARN_THRESHOLD = 3


def emit(key: str, value) -> None:
    print(f'{key}={value}')
    gh_out = os.environ.get('GITHUB_OUTPUT')
    if gh_out:
        with open(gh_out, 'a') as f:
            f.write(f'{key}={value}\n')


def _query_day_fps(table, day: str) -> set[str]:
    from boto3.dynamodb.conditions import Key
    fps: set[str] = set()
    kwargs = {
        'KeyConditionExpression': Key('topicId').eq(ANALYTICS_PK) & Key('SK').begins_with(f'{day}#'),
        'ProjectionExpression': 'SK',
    }
    while True:
        resp = table.query(**kwargs)
        for item in resp.get('Items', []):
            sk = item['SK']
            if '#' in sk:
                fps.add(sk.split('#', 1)[1])
        last = resp.get('LastEvaluatedKey')
        if not last:
            break
        kwargs['ExclusiveStartKey'] = last
    return fps


def run_live() -> int:
    import boto3
    ddb = boto3.resource('dynamodb', region_name=REGION)
    table = ddb.Table(TABLE)

    now = datetime.now(timezone.utc)
    today = now.strftime('%Y%m%d')
    yesterday = (now - timedelta(days=1)).strftime('%Y%m%d')

    users_by_day: dict[str, set[str]] = {}
    for i in range(7):
        day = (now - timedelta(days=i)).strftime('%Y%m%d')
        users_by_day[day] = _query_day_fps(table, day)

    today_fps = users_by_day.get(today, set())
    yesterday_fps = users_by_day.get(yesterday, set())
    all_fps: set[str] = set()
    for fps in users_by_day.values():
        all_fps |= fps

    dau = len(today_fps)
    wau = len(all_fps)
    return_rate = round(len(today_fps & yesterday_fps) / max(len(today_fps), 1), 3)

    dau_status = 'ok' if dau >= DAU_WARN_THRESHOLD else 'warn'
    wau_status = 'ok' if wau >= WAU_WARN_THRESHOLD else 'warn'

    emit('dau', dau)
    emit('wau', wau)
    emit('return_rate', return_rate)
    emit('avg_session_min', 'n/a')
    emit('dau_status', dau_status)
    emit('wau_status', wau_status)
    emit('status', 'warn' if dau_status == 'warn' or wau_status == 'warn' else 'ok')

    print(
        f'[sli_user_metrics] dau={dau}({dau_status}) wau={wau}({wau_status}) '
        f'return_rate={return_rate}',
        file=sys.stderr,
    )
    return 0


def run_dry() -> int:
    emit('dau', 5)
    emit('wau', 18)
    emit('return_rate', 0.200)
    emit('avg_session_min', 'n/a')
    emit('dau_status', 'ok')
    emit('wau_status', 'ok')
    emit('status', 'ok')
    print('[sli_user_metrics] --dry-run: mock output', file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='SLI 16-19 user activity metrics')
    parser.add_argument('--dry-run', action='store_true', help='mock output (no DynamoDB)')
    args = parser.parse_args()

    if args.dry_run:
        return run_dry()

    try:
        return run_live()
    except Exception as e:
        print(f'[sli_user_metrics] ERROR: {e}', file=sys.stderr)
        emit('dau', -1)
        emit('wau', -1)
        emit('return_rate', -1)
        emit('avg_session_min', 'n/a')
        emit('dau_status', 'skipped')
        emit('wau_status', 'skipped')
        emit('status', 'skipped')
        return 0


if __name__ == '__main__':
    sys.exit(main())
