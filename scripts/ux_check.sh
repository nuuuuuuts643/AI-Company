#!/usr/bin/env bash
# UX観点の自動検証スクリプト (T2026-0430-UX)
# 実行: bash scripts/ux_check.sh [--json] [--base-url https://flotopic.com]
#
# SLI とは別に「実画面の体験」を機械的にチェックする。
# 週次 .github/workflows/ux-check.yml から呼ばれる。
set -uo pipefail

BASE_URL="https://flotopic.com"
JSON_MODE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --json) JSON_MODE=1; shift ;;
    --base-url) BASE_URL="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,8p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

API_BASE="${BASE_URL}/api"
PASS=()
FAIL=()

record() {
  local name="$1" status="$2" detail="$3"
  if [ "$status" = "PASS" ]; then
    PASS+=("${name}|${detail}")
  else
    FAIL+=("${name}|${detail}")
  fi
  if [ "$JSON_MODE" = "0" ]; then
    if [ "$status" = "PASS" ]; then
      printf "✅ %-32s %s\n" "$name" "$detail"
    else
      printf "❌ %-32s %s\n" "$name" "$detail"
    fi
  fi
}

# ── ① トップページ応答 (<3秒) ────────────────────────────────────────
top_time=$(curl -sS -o /dev/null -w "%{time_total}" "${BASE_URL}/" 2>/dev/null || echo "999")
top_code=$(curl -sS -o /dev/null -w "%{http_code}" "${BASE_URL}/" 2>/dev/null || echo "000")
top_pass=$(awk -v t="$top_time" 'BEGIN{print (t<3.0)?"1":"0"}')
if [ "$top_code" = "200" ] && [ "$top_pass" = "1" ]; then
  record "top_page_response" PASS "http=${top_code} time=${top_time}s (<3.0s)"
else
  record "top_page_response" FAIL "http=${top_code} time=${top_time}s (要 <3.0s)"
fi

# ── ②③ topics-card.json ロード + keyPoint 表示 ────────────────────────
card_json=$(curl -sS "${API_BASE}/topics-card.json" 2>/dev/null || echo "")
if [ -z "$card_json" ]; then
  record "topics_card_exists" FAIL "topics-card.json 取得失敗"
  record "keypoint_present" FAIL "skipped (topics-card 取得失敗)"
else
  counts=$(printf '%s' "$card_json" | python3 -c "
import sys, json
try:
    d = json.loads(sys.stdin.read())
    ts = d.get('topics', [])
    ai_kp = [t for t in ts if t.get('aiGenerated') and (t.get('keyPoint') or '').strip()]
    print(f'{len(ts)} {len(ai_kp)}')
except Exception as e:
    print('0 0')
" 2>/dev/null || echo "0 0")
  total=$(echo "$counts" | awk '{print $1}')
  ai_kp=$(echo "$counts" | awk '{print $2}')
  if [ "$total" -ge 1 ]; then
    record "topics_card_exists" PASS "topics=${total}件"
  else
    record "topics_card_exists" FAIL "topics=0件 (≥1件必要)"
  fi
  if [ "$ai_kp" -ge 1 ]; then
    record "keypoint_present" PASS "aiGenerated+keyPoint=${ai_kp}件"
  else
    record "keypoint_present" FAIL "keyPoint付きAIカード=0件 (≥1件必要)"
  fi
fi

# ── ④ 次トピック導線 (detail.js / app.js に "next" / "次" が含まれること) ──
js_dir="projects/P003-news-timeline/frontend"
if [ -f "${js_dir}/detail.js" ] && [ -f "${js_dir}/app.js" ]; then
  next_hits=$(grep -cE "(次の|next)" "${js_dir}/detail.js" "${js_dir}/app.js" 2>/dev/null | awk -F: '{s+=$2} END{print s+0}')
  if [ "$next_hits" -ge 1 ]; then
    record "next_topic_link" PASS "detail.js+app.js に '次の|next' ${next_hits}件"
  else
    record "next_topic_link" FAIL "次トピック導線テキストなし"
  fi
else
  record "next_topic_link" FAIL "detail.js / app.js が見つからない"
fi

# ── ⑤ モバイル viewport (375px 想定) ────────────────────────────────
index_html=$(curl -sS "${BASE_URL}/" 2>/dev/null || echo "")
if printf '%s' "$index_html" | grep -qE 'name=["'"'"']viewport["'"'"']'; then
  record "mobile_viewport" PASS "viewport meta あり"
else
  record "mobile_viewport" FAIL "viewport meta なし"
fi

# ── ⑥ ページロード完結 (favicon.ico, manifest.json が 200) ─────────
fav_code=$(curl -sS -o /dev/null -w "%{http_code}" "${BASE_URL}/favicon.ico" 2>/dev/null || echo "000")
mani_code=$(curl -sS -o /dev/null -w "%{http_code}" "${BASE_URL}/manifest.json" 2>/dev/null || echo "000")
if [ "$fav_code" = "200" ]; then
  record "favicon_200" PASS "favicon.ico=${fav_code}"
else
  record "favicon_200" FAIL "favicon.ico=${fav_code} (要 200)"
fi
if [ "$mani_code" = "200" ]; then
  record "manifest_200" PASS "manifest.json=${mani_code}"
else
  record "manifest_200" FAIL "manifest.json=${mani_code} (要 200)"
fi

# ── ⑦ 壊れたリンク (index.html 内 ローカル href が 200) ─────────────
broken=""
checked=0
if [ -n "$index_html" ]; then
  links=$(printf '%s' "$index_html" | python3 -c "
import sys, re
html = sys.stdin.read()
hrefs = re.findall(r'href=[\"\\']([^\"\\']+)[\"\\']', html)
out = []
for h in hrefs:
    if h.startswith('#') or h.startswith('mailto:') or h.startswith('javascript:'):
        continue
    if h.startswith('http://') or h.startswith('https://'):
        continue
    if h.startswith('/') or not h.startswith('/'):
        out.append(h)
print('\n'.join(sorted(set(out))))
" 2>/dev/null)
  while IFS= read -r link; do
    [ -z "$link" ] && continue
    if [[ "$link" == /* ]]; then
      url="${BASE_URL}${link}"
    else
      url="${BASE_URL}/${link}"
    fi
    code=$(curl -sS -L -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
    checked=$((checked+1))
    if [ "$code" != "200" ]; then
      broken="${broken}${link}=${code} "
    fi
  done <<< "$links"
fi
if [ -z "$broken" ] && [ "$checked" -ge 1 ]; then
  record "no_broken_links" PASS "index.html 内ローカルlink ${checked}件 全て200"
elif [ "$checked" -eq 0 ]; then
  record "no_broken_links" FAIL "index.html 解析失敗"
else
  record "no_broken_links" FAIL "壊れたlink: ${broken}"
fi

# ── 集計 ─────────────────────────────────────────────────────────
pass_n=${#PASS[@]}
fail_n=${#FAIL[@]}
total_n=$((pass_n + fail_n))

if [ "$JSON_MODE" = "1" ]; then
  python3 <<PYEOF
import json
pass_items = [{"check": p.split("|",1)[0], "detail": p.split("|",1)[1]} for p in $(printf '%s\n' "${PASS[@]:-}" | python3 -c "import sys,json; print(json.dumps([l for l in sys.stdin.read().splitlines() if l]))")]
fail_items = [{"check": p.split("|",1)[0], "detail": p.split("|",1)[1]} for p in $(printf '%s\n' "${FAIL[@]:-}" | python3 -c "import sys,json; print(json.dumps([l for l in sys.stdin.read().splitlines() if l]))")]
print(json.dumps({
    "base_url": "${BASE_URL}",
    "total": ${total_n},
    "passed": ${pass_n},
    "failed": ${fail_n},
    "pass": pass_items,
    "fail": fail_items,
}, ensure_ascii=False, indent=2))
PYEOF
else
  echo "─────────────────────────────────────────"
  echo "結果: ${pass_n}/${total_n} pass, ${fail_n} fail"
fi

[ "$fail_n" -eq 0 ] && exit 0 || exit 1
