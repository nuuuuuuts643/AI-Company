#!/usr/bin/env python3
"""T2026-0429-J: keyPoint 長さ分布検証 — topics.json を取得し ≥100 字 充填率を計測する。

目的:
    proc_ai.py のプロンプト強化 (200〜300 字目標) が本番 keyPoint 出力に効いているかを
    外部から数値で確認する。既存 sli_keypoint_fill_rate.py は「任意長で空でない」充填率
    (= filled/eligible) を見るが、本スクリプトは「≥100 字」充填率と長さ分布を見る。

入力:
    --url <URL>       topics.json の URL (デフォルト https://flotopic.com/api/topics.json)
    --file <path>     ローカル topics.json を直接読む (--url より優先)

出力:
    stdout に key=value 形式 + 人読みサマリ。
        ge100_rate=<float>          # 100 字以上 充填率 (%)
        ge200_rate=<float>          # 200 字以上 充填率 (%) — 目標レンジ
        total=<int>
        ge100=<int>
        ge200=<int>
        avg_len=<float>
        median_len=<int>
        max_len=<int>
        status=ok|warn|error|skipped

閾値 (T2026-0429-J 着手時 実測 ≥100 字 = 2.17%。目標は 70%):
    ge100_rate >= 70.0 → ok
    50.0 <= ge100_rate < 70.0 → warn
    ge100_rate <  50.0 → error

終了コード:
    0 = ok / warn / skipped (continue-on-error 想定)
    1 = error (本番回帰検出)
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import urllib.error
import urllib.request


DEFAULT_URL = 'https://flotopic.com/api/topics.json'
WARN_THRESHOLD = 70.0
ERROR_THRESHOLD = 50.0


def fetch_topics(url: str | None, file: str | None) -> list[dict]:
    if file:
        with open(file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        req = urllib.request.Request(url or DEFAULT_URL, headers={'User-Agent': 'verify_keypoint_length/1.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    if isinstance(data, list):
        return data
    return data.get('topics') or data.get('articles') or []


def compute_distribution(topics: list[dict]) -> dict:
    lens = [len((t.get('keyPoint') or '').strip()) for t in topics]
    total = len(lens)
    if total == 0:
        return {'total': 0}
    ge100 = sum(1 for n in lens if n >= 100)
    ge200 = sum(1 for n in lens if n >= 200)
    return {
        'total': total,
        'ge100': ge100,
        'ge200': ge200,
        'ge100_rate': ge100 * 100.0 / total,
        'ge200_rate': ge200 * 100.0 / total,
        'avg_len': statistics.mean(lens),
        'median_len': int(statistics.median(lens)),
        'max_len': max(lens),
        'min_len': min(lens),
    }


def emit(key: str, value) -> None:
    print(f'{key}={value}')
    gh_out = os.environ.get('GITHUB_OUTPUT')
    if gh_out:
        with open(gh_out, 'a', encoding='utf-8') as f:
            f.write(f'{key}={value}\n')


def classify(rate: float) -> str:
    if rate >= WARN_THRESHOLD:
        return 'ok'
    if rate >= ERROR_THRESHOLD:
        return 'warn'
    return 'error'


def main() -> int:
    parser = argparse.ArgumentParser(description='Verify keyPoint length distribution from topics.json')
    parser.add_argument('--url', default=DEFAULT_URL, help='topics.json URL (default: %(default)s)')
    parser.add_argument('--file', default=None, help='Local topics.json path (overrides --url)')
    args = parser.parse_args()

    try:
        topics = fetch_topics(args.url, args.file)
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        print(f'[verify_keypoint_length] fetch failed: {e}', file=sys.stderr)
        emit('status', 'skipped')
        return 0

    dist = compute_distribution(topics)
    if dist.get('total', 0) == 0:
        emit('status', 'skipped')
        emit('total', 0)
        return 0

    status = classify(dist['ge100_rate'])

    emit('status', status)
    emit('total', dist['total'])
    emit('ge100', dist['ge100'])
    emit('ge200', dist['ge200'])
    emit('ge100_rate', f'{dist["ge100_rate"]:.2f}')
    emit('ge200_rate', f'{dist["ge200_rate"]:.2f}')
    emit('avg_len', f'{dist["avg_len"]:.1f}')
    emit('median_len', dist['median_len'])
    emit('max_len', dist['max_len'])

    print(
        f'\n[verify_keypoint_length] total={dist["total"]} '
        f'ge100={dist["ge100"]} ({dist["ge100_rate"]:.2f}%) '
        f'ge200={dist["ge200"]} ({dist["ge200_rate"]:.2f}%) '
        f'avg={dist["avg_len"]:.1f} median={dist["median_len"]} '
        f'min={dist["min_len"]} max={dist["max_len"]} '
        f'status={status}',
        file=sys.stderr,
    )
    return 1 if status == 'error' else 0


if __name__ == '__main__':
    sys.exit(main())
