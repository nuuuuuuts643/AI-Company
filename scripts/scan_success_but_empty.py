#!/usr/bin/env python3
"""T2026-0428-Q: success-but-empty 横展開スキャン。

「処理は成功扱いだが結果が空 (aiGenerated=True かつ keyPoint 空 など)」のような、
SLI が見落としがちなアンチパターンを 7 観点で同時検査する。

検査項目:
  ① fetcher articleCount=0 サイクル        — TODO (CloudWatch Logs 連携が必要)
  ② processor processed_topics=0 サイクル   — TODO (CloudWatch Logs 連携が必要)
  ③ topics.json: aiGenerated=True かつ keyPoint 空/短い        — S3 検査
  ④ topics.json: aiGenerated=True かつ perspectives 空/短い    — S3 検査
  ⑤ topics.json: lastArticleAt が 24h 以内 / 全 aiGenerated=True (freshness)
  ⑥ .github/workflows: `if: false` / `continue-on-error: true` 列挙
  ⑦ topics.json: aiGenerated=False の placeholder 風 (meta-only) トピック数

①② は CloudWatch Logs に直接アクセスする実装が大きいため本スクリプトでは省略。
代わりに既存ワークフロー (fetcher-health-check.yml / sli-keypoint-fill-rate.yml)
が SLI として alerts を出している。

実行例:
  python3 scripts/scan_success_but_empty.py
  python3 scripts/scan_success_but_empty.py --json    # CI/SLI 取り込み用
  python3 scripts/scan_success_but_empty.py --check keypoint  # 単一項目のみ
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path

REGION = 'ap-northeast-1'
TABLE = 'p003-topics'
S3_BUCKET = os.environ.get('S3_BUCKET', 'p003-news-946554699567')
TOPICS_URL = os.environ.get('TOPICS_URL', 'https://flotopic.com/api/topics.json')

KEYPOINT_MIN_LENGTH = 100
PERSPECTIVES_MIN_LENGTH = 80
FRESHNESS_WINDOW_SEC = 24 * 3600

WORKFLOWS_DIR = Path(__file__).resolve().parent.parent / '.github' / 'workflows'


def _length(v):
    if v is None or not isinstance(v, str):
        return 0
    return len(v.strip())


def _classify(L, threshold):
    if L == 0:
        return 'empty'
    if L < 20:
        return '1-19'
    if L < 50:
        return '20-49'
    if L < threshold:
        return f'50-{threshold - 1}'
    if L < 200:
        return f'{threshold}-199'
    return '200+'


def fetch_topics():
    """topics 一覧を取得する。

    優先順位: TOPICS_URL (公開 CDN) → boto3 で S3 直 GET。
    """
    last_err = None
    try:
        req = urllib.request.Request(TOPICS_URL, headers={'User-Agent': 'scan_success_but_empty'})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
        topics = data.get('topics', data) if isinstance(data, dict) else data
        return topics, f'http:{TOPICS_URL}'
    except Exception as e:
        last_err = e

    try:
        import boto3  # type: ignore
        s3 = boto3.client('s3', region_name=REGION)
        obj = s3.get_object(Bucket=S3_BUCKET, Key='api/topics.json')
        data = json.loads(obj['Body'].read())
        topics = data.get('topics', data) if isinstance(data, dict) else data
        return topics, f's3:{S3_BUCKET}/api/topics.json'
    except Exception as e:
        last_err = e

    raise RuntimeError(f'topics.json 取得失敗: {last_err}')


# ---------------------------------------------------------------------------
# 個別チェック
# ---------------------------------------------------------------------------

def check_keypoint(topics):
    """③ aiGenerated=True かつ keyPoint < KEYPOINT_MIN_LENGTH。"""
    ai = [t for t in topics if t.get('aiGenerated')]
    short = []
    by_bucket = Counter()
    by_mode = Counter()
    by_mode_short = Counter()
    for t in ai:
        kp = t.get('keyPoint')
        L = _length(kp)
        by_bucket[_classify(L, KEYPOINT_MIN_LENGTH)] += 1
        mode = t.get('summaryMode') or 'unknown'
        by_mode[mode] += 1
        if L < KEYPOINT_MIN_LENGTH:
            short.append({
                'topicId': str(t.get('topicId', ''))[:8],
                'length': L,
                'mode': mode,
                'articleCount': int(t.get('articleCount', 0) or 0),
                'preview': (kp or '')[:60],
            })
            by_mode_short[mode] += 1
    return {
        'name': '③ keyPoint',
        'total': len(ai),
        'bad': len(short),
        'rate': round(100.0 * len(short) / len(ai), 2) if ai else 0.0,
        'threshold': KEYPOINT_MIN_LENGTH,
        'distribution': dict(by_bucket),
        'by_mode': dict(by_mode),
        'by_mode_bad': dict(by_mode_short),
        'samples': short[:10],
    }


def check_perspectives(topics):
    """④ aiGenerated=True かつ perspectives < PERSPECTIVES_MIN_LENGTH。"""
    ai = [t for t in topics if t.get('aiGenerated')]
    short = []
    by_bucket = Counter()
    for t in ai:
        p = t.get('perspectives')
        L = _length(p)
        by_bucket[_classify(L, PERSPECTIVES_MIN_LENGTH)] += 1
        if L < PERSPECTIVES_MIN_LENGTH:
            short.append({
                'topicId': str(t.get('topicId', ''))[:8],
                'length': L,
                'preview': (p or '')[:60] if isinstance(p, str) else str(p)[:60],
            })
    return {
        'name': '④ perspectives',
        'total': len(ai),
        'bad': len(short),
        'rate': round(100.0 * len(short) / len(ai), 2) if ai else 0.0,
        'threshold': PERSPECTIVES_MIN_LENGTH,
        'distribution': dict(by_bucket),
        'samples': short[:10],
    }


def check_freshness(topics, now=None):
    """⑤ lastArticleAt が 24h 以内 / aiGenerated=True 全体。

    fresh_rate が低い (例 < 60%) と「AI 生成済みだが古い記事しか紐付いていない」
    トピックが滞留していることを意味する。"""
    now = now or int(time.time())
    ai = [t for t in topics if t.get('aiGenerated')]
    fresh = []
    stale = []
    for t in ai:
        last = t.get('lastArticleAt')
        try:
            ts = int(last) if last is not None else 0
        except (TypeError, ValueError):
            ts = 0
        if ts > 0 and (now - ts) <= FRESHNESS_WINDOW_SEC:
            fresh.append(t)
        else:
            stale.append({
                'topicId': str(t.get('topicId', ''))[:8],
                'lastArticleAt': ts,
                'age_hours': round((now - ts) / 3600.0, 1) if ts else None,
                'articleCount': int(t.get('articleCount', 0) or 0),
            })
    rate = round(100.0 * len(fresh) / len(ai), 2) if ai else 0.0
    return {
        'name': '⑤ freshness 24h',
        'total': len(ai),
        'fresh': len(fresh),
        'stale': len(stale),
        'fresh_rate': rate,
        'samples_stale': stale[:10],
    }


def check_meta_only(topics):
    """⑦ aiGenerated=False の placeholder 風トピック (T260 改修の事後検証)。

    T260 で proc_storage が META=2フィールドのみで保存する経路は塞いだはずだが、
    過去の DB 残存や fetcher 経由で aiGenerated=False のままのトピック数を観測する。
    """
    not_ai = [t for t in topics if not t.get('aiGenerated')]
    placeholder = []
    for t in not_ai:
        title = (t.get('title') or t.get('generatedTitle') or '').strip()
        kp = (t.get('keyPoint') or '').strip()
        per = (t.get('perspectives') or '').strip() if isinstance(t.get('perspectives'), str) else ''
        if not title and not kp and not per:
            placeholder.append({
                'topicId': str(t.get('topicId', ''))[:8],
                'articleCount': int(t.get('articleCount', 0) or 0),
            })
    return {
        'name': '⑦ aiGenerated=False placeholder',
        'total_topics': len(topics),
        'aiGenerated_false': len(not_ai),
        'placeholder': len(placeholder),
        'samples': placeholder[:10],
    }


_SKIP_PATTERNS = [
    (re.compile(r'^\s*if\s*:\s*false\b', re.IGNORECASE), 'if:false'),
    (re.compile(r'^\s*continue-on-error\s*:\s*true\b', re.IGNORECASE), 'continue-on-error:true'),
]


def check_workflows():
    """⑥ .github/workflows/ で `if: false` / `continue-on-error: true` を列挙。"""
    findings = []
    if not WORKFLOWS_DIR.is_dir():
        return {
            'name': '⑥ CI green-but-skipped',
            'workflows_scanned': 0,
            'findings': findings,
            'count': 0,
        }
    yml_files = sorted(WORKFLOWS_DIR.glob('*.y*ml'))
    for yml in yml_files:
        try:
            lines = yml.read_text(encoding='utf-8').splitlines()
        except Exception:
            continue
        for i, line in enumerate(lines, start=1):
            for pat, label in _SKIP_PATTERNS:
                if pat.search(line):
                    findings.append({
                        'file': str(yml.relative_to(WORKFLOWS_DIR.parent.parent)),
                        'line': i,
                        'pattern': label,
                        'text': line.strip()[:120],
                    })
    return {
        'name': '⑥ CI green-but-skipped',
        'workflows_scanned': len(yml_files),
        'findings': findings,
        'count': len(findings),
    }


def check_log_cycles_todo(label):
    """①② CloudWatch Logs ベースの検査は本スクリプトでは未実装。

    既存の以下ワークフローで等価な観測がされている:
      - .github/workflows/fetcher-health-check.yml (saved_articles=0 検知)
      - .github/workflows/sli-keypoint-fill-rate.yml (processor 出力検証)
    """
    return {
        'name': label,
        'status': 'TODO',
        'note': 'CloudWatch Logs 連携未実装。fetcher-health-check.yml / sli-keypoint-fill-rate.yml で等価観測あり。',
    }


# ---------------------------------------------------------------------------
# 出力
# ---------------------------------------------------------------------------

def _row(name, status, detail):
    return f'  {name:<38} {status:<10} {detail}'


def print_human(report):
    print('=== T2026-0428-Q success-but-empty 横展開スキャン ===')
    print(f'topics source: {report.get("source", "n/a")}')
    print()
    print(_row('項目', 'status', '内訳'))
    print('  ' + '-' * 80)

    fetcher = report['fetcher']
    print(_row(fetcher['name'], 'TODO', fetcher.get('note', '')))
    processor = report['processor']
    print(_row(processor['name'], 'TODO', processor.get('note', '')))

    kp = report['keypoint']
    kp_status = 'OK' if kp['rate'] < 5.0 else ('WARN' if kp['rate'] < 20.0 else 'NG')
    print(_row(kp['name'], kp_status, f'{kp["bad"]}/{kp["total"]} ({kp["rate"]}%) < {kp["threshold"]}字'))

    per = report['perspectives']
    per_status = 'OK' if per['rate'] < 5.0 else ('WARN' if per['rate'] < 20.0 else 'NG')
    print(_row(per['name'], per_status, f'{per["bad"]}/{per["total"]} ({per["rate"]}%) < {per["threshold"]}字'))

    fr = report['freshness']
    fr_status = 'OK' if fr['fresh_rate'] >= 60.0 else ('WARN' if fr['fresh_rate'] >= 30.0 else 'NG')
    print(_row(fr['name'], fr_status, f'fresh {fr["fresh"]}/{fr["total"]} ({fr["fresh_rate"]}%) stale={fr["stale"]}'))

    ci = report['workflows']
    ci_status = 'OK' if ci['count'] == 0 else 'WARN'
    print(_row(ci['name'], ci_status, f'{ci["count"]} hits / {ci["workflows_scanned"]} workflows'))

    mo = report['meta_only']
    mo_status = 'OK' if mo['placeholder'] == 0 else ('WARN' if mo['placeholder'] < 5 else 'NG')
    print(_row(mo['name'], mo_status, f'placeholder={mo["placeholder"]} / aiGen=False={mo["aiGenerated_false"]} / 全 {mo["total_topics"]}'))

    print()
    print('--- 詳細 ---')
    print(f'\n[③ keyPoint] 長分布:')
    for k in ('empty', '1-19', '20-49', f'50-{KEYPOINT_MIN_LENGTH - 1}', f'{KEYPOINT_MIN_LENGTH}-199', '200+'):
        v = kp['distribution'].get(k, 0)
        bar = '█' * min(40, v)
        print(f'  {k:>8}: {v:>4} {bar}')
    if kp['samples']:
        print('  short keyPoint sample:')
        for s in kp['samples'][:5]:
            print(f'    - {s["topicId"]} L={s["length"]:>3} mode={s["mode"]:>8} ac={s["articleCount"]} preview={s["preview"]!r}')

    print(f'\n[④ perspectives] 長分布:')
    for k in ('empty', '1-19', '20-49', f'50-{PERSPECTIVES_MIN_LENGTH - 1}', f'{PERSPECTIVES_MIN_LENGTH}-199', '200+'):
        v = per['distribution'].get(k, 0)
        bar = '█' * min(40, v)
        print(f'  {k:>8}: {v:>4} {bar}')
    if per['samples']:
        print('  short perspectives sample:')
        for s in per['samples'][:5]:
            print(f'    - {s["topicId"]} L={s["length"]:>3} preview={s["preview"]!r}')

    if fr['samples_stale']:
        print(f'\n[⑤ freshness] stale sample:')
        for s in fr['samples_stale'][:5]:
            ah = s['age_hours']
            print(f'    - {s["topicId"]} age={ah}h ac={s["articleCount"]}')

    if ci['findings']:
        print(f'\n[⑥ workflows] hits:')
        for f in ci['findings']:
            print(f'    - {f["file"]}:{f["line"]} [{f["pattern"]}] {f["text"]}')

    if mo['samples']:
        print(f'\n[⑦ meta-only] sample:')
        for s in mo['samples'][:5]:
            print(f'    - {s["topicId"]} ac={s["articleCount"]}')


def print_json(report):
    out = {}
    for k, v in report.items():
        if isinstance(v, dict):
            out[k] = {kk: vv for kk, vv in v.items() if not kk.startswith('samples')}
        else:
            out[k] = v
    print(json.dumps(out, ensure_ascii=False))


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

CHECKS = ('keypoint', 'perspectives', 'freshness', 'workflows', 'meta_only', 'fetcher', 'processor')


def compute_status(report):
    """CI/Slack 用に ok/warn/ng を判定する。"""
    kp = float(report.get('keypoint', {}).get('rate', 0) or 0)
    per = float(report.get('perspectives', {}).get('rate', 0) or 0)
    fresh = float(report.get('freshness', {}).get('fresh_rate', 100) or 100)
    hits = int(report.get('workflows', {}).get('count', 0) or 0)
    ph = int(report.get('meta_only', {}).get('placeholder', 0) or 0)
    if ph > 0 or kp >= 50 or per >= 50 or fresh < 30:
        status = 'ng'
    elif kp >= 20 or per >= 20 or fresh < 60:
        status = 'warn'
    else:
        status = 'ok'
    return {
        'status': status,
        'kp_rate': kp,
        'per_rate': per,
        'fresh_rate': fresh,
        'ci_hits': hits,
        'placeholder': ph,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--json', action='store_true', help='JSON 出力 (CI/SLI 取り込み用)')
    p.add_argument('--ci-status', action='store_true',
                   help='STATUS=... 形式 (eval / GITHUB_OUTPUT 用)')
    p.add_argument('--check', choices=CHECKS, help='個別チェックのみ実行')
    args = p.parse_args()

    try:
        topics, source = fetch_topics()
    except Exception as e:
        print(f'[scan_success_but_empty] topics.json 取得失敗: {e}', file=sys.stderr)
        sys.exit(1)

    only = args.check
    report = {'source': source}
    report['fetcher'] = check_log_cycles_todo('① fetcher articleCount=0 サイクル') if (not only or only == 'fetcher') else None
    report['processor'] = check_log_cycles_todo('② processor processed=0 サイクル') if (not only or only == 'processor') else None
    report['keypoint'] = check_keypoint(topics) if (not only or only == 'keypoint') else None
    report['perspectives'] = check_perspectives(topics) if (not only or only == 'perspectives') else None
    report['freshness'] = check_freshness(topics) if (not only or only == 'freshness') else None
    report['workflows'] = check_workflows() if (not only or only == 'workflows') else None
    report['meta_only'] = check_meta_only(topics) if (not only or only == 'meta_only') else None

    if args.ci_status:
        s = compute_status(report)
        # shell 側で `eval "$(... --ci-status)"` で取り込めるよう KEY=VALUE で出力
        for k, v in s.items():
            print(f'{k.upper()}={v}')
        return

    if args.json:
        clean = {k: v for k, v in report.items() if v is not None}
        print_json(clean)
    else:
        if only:
            print(json.dumps(report.get(only), ensure_ascii=False, indent=2))
        else:
            print_human(report)


if __name__ == '__main__':
    main()
