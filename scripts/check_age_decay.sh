#!/bin/bash
# T2026-0429-J: ランキングの age decay が効いているか観測する SLI チェック。
#
# 何を見るか:
#   topics.json を fetch して
#   - 全 topic 数 N
#   - lastUpdated 欠落 / NaN な topic 数 missing
#   - 24h 超 topic 数 stale
#   - 72h 超 topic 数 exiled
#   を出す。閾値:
#     * missing/N > 5%       → exit 2 (age decay フォールバックが頻発する状態 = 物理ガード欠如)
#     * stale_visible_ratio > 50%  → exit 1 (古いトピックが上位 30 件にどれくらい出るか — 警告)
#
# 使い方:
#   bash scripts/check_age_decay.sh             # 本番 https://flotopic.com/api/topics.json
#   bash scripts/check_age_decay.sh /path.json  # ローカルファイル
set -euo pipefail
SRC="${1:-https://flotopic.com/api/topics.json}"
if [[ "$SRC" =~ ^https?:// ]]; then
  TMP=$(mktemp)
  trap 'rm -f $TMP' EXIT
  curl -fsS "$SRC" -o "$TMP"
  PATH_JSON="$TMP"
else
  PATH_JSON="$SRC"
fi
python3 - "$PATH_JSON" <<'PY'
import json, sys, time
from datetime import datetime
path = sys.argv[1]
with open(path) as f:
    data = json.load(f)
topics = data.get('topics', data) if isinstance(data, dict) else data
N = len(topics)
if N == 0:
    print('NO TOPICS', file=sys.stderr); sys.exit(2)
now = time.time()
missing = stale = exiled = 0
ages = []
for t in topics:
    lu = t.get('lastUpdated')
    if not lu:
        missing += 1; continue
    try:
        dt = datetime.fromisoformat(str(lu).replace('Z','+00:00'))
        h = (now - dt.timestamp())/3600
        ages.append(h)
        if h >= 72: exiled += 1
        elif h >= 24: stale += 1
    except Exception:
        missing += 1
top30 = sorted(ages, reverse=False)[:30] if ages else []
top30_stale = sum(1 for h in top30 if h >= 24)
miss_pct = round(missing/N*100, 1)
stale_pct = round(stale/N*100, 1)
exile_pct = round(exiled/N*100, 1)
top30_stale_pct = round((top30_stale/len(top30) if top30 else 0)*100, 1)
print(f'N={N} missing={missing}({miss_pct}%) stale_24h+={stale}({stale_pct}%) exiled_72h+={exiled}({exile_pct}%) top30_stale={top30_stale_pct}%')
rc = 0
if miss_pct > 5.0:
    print(f'ERROR: lastUpdated 欠落率 {miss_pct}% > 5% — age decay フォールバックが頻発している', file=sys.stderr)
    rc = max(rc, 2)
if top30_stale_pct > 50.0:
    print(f'WARN: 上位30件のうち24h超が {top30_stale_pct}% > 50% — age decay 効力低下の疑い', file=sys.stderr)
    rc = max(rc, 1)
sys.exit(rc)
PY
