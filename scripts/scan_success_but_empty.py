#!/usr/bin/env python3
"""T2026-0428-Q: success-but-empty スキャン。

proc_ai.py が「成功」を返したが、結果として keyPoint が短い／空のままの
トピックを DynamoDB スキャンで集計し、コンソールに出力する。

検出パターン:
  - aiGenerated = True (proc_ai が成功扱いで終了)
  - かつ keyPoint が以下のいずれか
      * 空 (None / '' / 空白のみ)
      * 1 〜 KEYPOINT_MIN_LENGTH-1 字 (schema 違反扱い)

意義:
  proc_ai.py は schema minLength=100 を指定し、_retry_short_keypoint で
  100 字未満 keyPoint の再生成を 1 度だけ試みる。それでも短いまま採用された
  ものを「success-but-empty」として観測することで、retry の効果を実測する。
  数値が下がっていれば retry が効いている、横這いなら根本対策が必要。

出力:
  件数 / topicId サンプル / keyPoint 長分布 / mode (minimal/standard/full) 別内訳

実行:
  python3 scripts/scan_success_but_empty.py
  python3 scripts/scan_success_but_empty.py --bucket-only   # S3 topics.json から直接 (DDB 権限不要)
  python3 scripts/scan_success_but_empty.py --json          # JSON 出力 (CI/SLI 取り込み用)
"""
import argparse
import json
import os
import sys
from collections import Counter

REGION = 'ap-northeast-1'
TABLE = 'p003-topics'
S3_BUCKET = os.environ.get('S3_BUCKET', 'p003-news-946554699567')

# proc_storage.py.KEYPOINT_MIN_LENGTH と同期 (100 字未満を不十分扱い)
KEYPOINT_MIN_LENGTH = 100


def _length(v):
    if v is None:
        return 0
    if not isinstance(v, str):
        return 0
    return len(v.strip())


def _classify(L):
    if L == 0:
        return 'empty'
    if L < 20:
        return '1-19'
    if L < 50:
        return '20-49'
    if L < KEYPOINT_MIN_LENGTH:
        return f'50-{KEYPOINT_MIN_LENGTH - 1}'
    if L < 200:
        return f'{KEYPOINT_MIN_LENGTH}-199'
    return '200+'


def scan_from_dynamodb():
    import boto3
    from boto3.dynamodb.conditions import Attr
    ddb = boto3.resource('dynamodb', region_name=REGION)
    table = ddb.Table(TABLE)

    items = []
    kwargs = {
        'FilterExpression': Attr('SK').eq('META') & Attr('aiGenerated').eq(True),
        'ProjectionExpression': 'topicId,keyPoint,summaryMode,articleCount,aiGeneratedAt',
    }
    while True:
        r = table.scan(**kwargs)
        items.extend(r.get('Items', []))
        if not r.get('LastEvaluatedKey'):
            break
        kwargs['ExclusiveStartKey'] = r['LastEvaluatedKey']
    return items


def scan_from_s3():
    import boto3
    s3 = boto3.client('s3', region_name=REGION)
    obj = s3.get_object(Bucket=S3_BUCKET, Key='api/topics.json')
    data = json.loads(obj['Body'].read())
    topics = data.get('topics', data) if isinstance(data, dict) else data
    return [t for t in topics if t.get('aiGenerated')]


def analyze(items):
    total = len(items)
    short = []
    by_bucket = Counter()
    by_mode = Counter()
    by_mode_short = Counter()

    for it in items:
        kp = it.get('keyPoint')
        L = _length(kp)
        bucket = _classify(L)
        by_bucket[bucket] += 1
        mode = it.get('summaryMode') or 'unknown'
        by_mode[mode] += 1
        if L < KEYPOINT_MIN_LENGTH:
            short.append((it.get('topicId', '')[:8], L, mode,
                          int(it.get('articleCount', 0) or 0),
                          (kp or '')[:60]))
            by_mode_short[mode] += 1

    return {
        'total_aiGenerated': total,
        'success_but_empty_count': len(short),
        'success_but_empty_rate': round(100.0 * len(short) / total, 2) if total else 0.0,
        'length_distribution': dict(by_bucket),
        'by_mode': dict(by_mode),
        'by_mode_short': dict(by_mode_short),
        'samples': short[:10],
    }


def print_human(report):
    print('=== success-but-empty スキャン結果 ===')
    print(f'aiGenerated=True 全体: {report["total_aiGenerated"]} 件')
    print(f'うち keyPoint < {KEYPOINT_MIN_LENGTH} 字: '
          f'{report["success_but_empty_count"]} 件 '
          f'({report["success_but_empty_rate"]}%)')
    print()
    print('keyPoint 長分布:')
    for k in ('empty', '1-19', '20-49', f'50-{KEYPOINT_MIN_LENGTH - 1}',
              f'{KEYPOINT_MIN_LENGTH}-199', '200+'):
        v = report['length_distribution'].get(k, 0)
        bar = '█' * min(40, v)
        print(f'  {k:>8}: {v:>4} {bar}')
    print()
    print('mode 別:')
    for mode, total in sorted(report['by_mode'].items()):
        short = report['by_mode_short'].get(mode, 0)
        rate = round(100.0 * short / total, 1) if total else 0.0
        print(f'  {mode:>10}: {short:>3} short / {total:>3} total ({rate}%)')
    print()
    if report['samples']:
        print(f'short keyPoint sample (先頭 {len(report["samples"])} 件):')
        for tid, L, mode, ac, kp in report['samples']:
            print(f'  - {tid} L={L:>3} mode={mode:>8} ac={ac:>2} kp={kp!r}')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--bucket-only', action='store_true',
                   help='S3 topics.json から直接読む (DDB scan 不要・権限省略)')
    p.add_argument('--json', action='store_true',
                   help='JSON 出力 (CI/SLI 取り込み用)')
    args = p.parse_args()

    try:
        items = scan_from_s3() if args.bucket_only else scan_from_dynamodb()
    except Exception as e:
        print(f'[scan_success_but_empty] エラー: {e}', file=sys.stderr)
        sys.exit(1)

    report = analyze(items)
    if args.json:
        # samples は出力しない (PII 風の文章なので CI ログ汚染を避ける)
        out = {k: v for k, v in report.items() if k != 'samples'}
        print(json.dumps(out, ensure_ascii=False))
    else:
        print_human(report)


if __name__ == '__main__':
    main()
