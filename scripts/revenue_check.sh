#!/usr/bin/env bash
# 収益・PV週次チェックスクリプト (T2026-0430-REV)
# 実行: bash scripts/revenue_check.sh [--json] [--base-url https://flotopic.com]
#
# 目的: 品質改善 (keyPoint / perspectives 充填率 など) が
#       PV → 忍者AdMax 収益に繋がっているかを週次で観測する。
# 観測項目:
#   ① CloudFront / Cloudflare アクセスログから週間PV (cf-analytics.json 経由)
#   ② DynamoDB 直近1週間の topicCount / aiGenerated 件数
#   ③ docs/revenue-log.md の最新エントリ日付 (転記滞留検知)
# 週次 .github/workflows/revenue-sli.yml から呼ばれる。
set -uo pipefail

BASE_URL="https://flotopic.com"
JSON_MODE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --json) JSON_MODE=1; shift ;;
    --base-url) BASE_URL="$2"; shift 2 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REVENUE_LOG="${REPO_ROOT}/docs/revenue-log.md"
API_BASE="${BASE_URL}/api"

# ── ① cf-analytics.json から週間PV ─────────────────────────────────
cf_json=$(curl -sS --max-time 15 "${API_BASE}/cf-analytics.json" 2>/dev/null || echo "")
if [ -z "$cf_json" ]; then
  PV_7D="-1"
  PV_STATUS="error"
  PV_DETAIL="cf-analytics.json 取得失敗"
else
  read -r PV_7D PV_DETAIL < <(printf '%s' "$cf_json" | python3 -c "
import sys, json
try:
    d = json.loads(sys.stdin.read())
    cf = d.get('cf') or d.get('cfAnalytics') or d
    pv = cf.get('totalPv7d')
    if pv is None:
        pv = sum(x.get('count', 0) for x in cf.get('daily', []) or [])
    daily = cf.get('daily') or []
    days = len([x for x in daily if x.get('count', 0) > 0])
    print(f'{int(pv)} {days}日分')
except Exception as e:
    print(f'-1 parse_error:{e}')
" 2>/dev/null || echo "-1 parse_failed")
  if [ "$PV_7D" = "-1" ]; then
    PV_STATUS="error"
  elif [ "$PV_7D" -lt 50 ]; then
    PV_STATUS="warn"
  else
    PV_STATUS="ok"
  fi
fi

# ── ② DynamoDB 直近1週間の aiGenerated 件数 (boto3 利用可能なら) ──
TOPIC_TOTAL="-1"
AI_GENERATED_7D="-1"
DDB_STATUS="skipped"
DDB_DETAIL="boto3 / AWS credentials 未確認"
if python3 -c "import boto3" >/dev/null 2>&1 && [ -n "${AWS_ACCESS_KEY_ID:-}" ]; then
  DDB_OUT=$(python3 - <<'PY' 2>/dev/null || echo "error -1 -1"
import os, sys
from datetime import datetime, timedelta, timezone
import boto3
from boto3.dynamodb.conditions import Attr

REGION = os.environ.get('AWS_DEFAULT_REGION', 'ap-northeast-1')
TABLE = 'p003-topics'
cutoff_7d = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

try:
    ddb = boto3.resource('dynamodb', region_name=REGION).Table(TABLE)
    total = 0
    ai_7d = 0
    kw = {
        'FilterExpression': Attr('SK').eq('META'),
        'ProjectionExpression': 'aiGeneratedAt, lifecycleStatus, articleCount',
    }
    while True:
        r = ddb.scan(**kw)
        for it in r.get('Items', []):
            ls = it.get('lifecycleStatus') or 'active'
            if ls in ('archived', 'legacy', 'deleted'):
                continue
            total += 1
            ag = it.get('aiGeneratedAt')
            if ag and str(ag) >= cutoff_7d:
                ai_7d += 1
        if not r.get('LastEvaluatedKey'):
            break
        kw['ExclusiveStartKey'] = r['LastEvaluatedKey']
    print(f'ok {total} {ai_7d}')
except Exception as e:
    print(f'error -1 -1 {e}')
PY
)
  read -r DDB_STATUS TOPIC_TOTAL AI_GENERATED_7D _DDB_REST <<<"$DDB_OUT"
  DDB_DETAIL="META total=${TOPIC_TOTAL} aiGenerated_7d=${AI_GENERATED_7D}"
  if [ "$DDB_STATUS" != "ok" ]; then
    DDB_DETAIL="DDB scan 失敗: ${_DDB_REST:-unknown}"
  fi
fi

# ── ③ docs/revenue-log.md の最新エントリ確認 ─────────────────────
LOG_LATEST_DATE=""
LOG_AGE_DAYS="-1"
LOG_STATUS="missing"
if [ -f "$REVENUE_LOG" ]; then
  # | 2026-04-W4 | のような週ラベル or | 2026-04-30 | のような日付を拾う
  LOG_LATEST_DATE=$(python3 - <<PY
import re, sys
from datetime import date, datetime, timedelta
try:
    with open("${REVENUE_LOG}", encoding='utf-8') as f:
        text = f.read()
    # ISO 日付
    iso = re.findall(r'\b(20\d{2}-\d{2}-\d{2})\b', text)
    weekly = re.findall(r'\b(20\d{2})-(\d{2})-W(\d)\b', text)
    cands = []
    for d in iso:
        try: cands.append(datetime.fromisoformat(d).date())
        except: pass
    for y,m,w in weekly:
        # 週番号 W4 → その月の Nth 週末（おおまかに day=N*7、月末超えは 28 にクリップ）
        try:
            cands.append(date(int(y), int(m), min(28, int(w)*7)))
        except: pass
    if not cands:
        print('')
    else:
        print(max(cands).isoformat())
except Exception:
    print('')
PY
)
  if [ -n "$LOG_LATEST_DATE" ]; then
    LOG_AGE_DAYS=$(python3 -c "
from datetime import date, datetime
d = datetime.fromisoformat('${LOG_LATEST_DATE}').date()
print((date.today() - d).days)
")
    if [ "$LOG_AGE_DAYS" -le 7 ]; then
      LOG_STATUS="fresh"
    elif [ "$LOG_AGE_DAYS" -le 14 ]; then
      LOG_STATUS="stale"
    else
      LOG_STATUS="overdue"
    fi
  else
    LOG_STATUS="empty"
  fi
fi

# ── 出力 ─────────────────────────────────────────────────────────
if [ "$JSON_MODE" = "1" ]; then
  python3 - <<PY
import json
print(json.dumps({
  'base_url': '${BASE_URL}',
  'pv': {
    'status': '${PV_STATUS}',
    'totalPv7d': int('${PV_7D}'),
    'detail': '${PV_DETAIL}'.replace('\\n',' '),
  },
  'ddb': {
    'status': '${DDB_STATUS}',
    'topicTotal': int('${TOPIC_TOTAL}'),
    'aiGenerated7d': int('${AI_GENERATED_7D}'),
    'detail': '${DDB_DETAIL}'.replace('\\n',' '),
  },
  'revenueLog': {
    'status': '${LOG_STATUS}',
    'latestDate': '${LOG_LATEST_DATE}',
    'ageDays': int('${LOG_AGE_DAYS}'),
    'path': 'docs/revenue-log.md',
  },
}, ensure_ascii=False, indent=2))
PY
else
  cat <<EOF
=== 収益・PV週次チェック (revenue_check.sh) ===
[PV]   status=${PV_STATUS} totalPv7d=${PV_7D} (${PV_DETAIL})
[DDB]  status=${DDB_STATUS} ${DDB_DETAIL}
[LOG]  status=${LOG_STATUS} latest=${LOG_LATEST_DATE:-none} age=${LOG_AGE_DAYS}d (docs/revenue-log.md)
EOF
fi

# 終了コード: PV取得失敗 or LOG が overdue (8日以上) なら 1
if [ "$PV_STATUS" = "error" ] || [ "$LOG_STATUS" = "overdue" ] || [ "$LOG_STATUS" = "missing" ] || [ "$LOG_STATUS" = "empty" ]; then
  exit 1
fi
exit 0
