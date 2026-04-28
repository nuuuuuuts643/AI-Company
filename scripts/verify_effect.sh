#!/usr/bin/env bash
# scripts/verify_effect.sh <fix_type> [args]
#
# 「修正した」と「改善した」を区別するための効果検証ディスパッチャ。
# Verified 行に含めて commit する想定。
#
# 使い方:
#   bash scripts/verify_effect.sh ai_quality              # keyPoint/perspectives 充填率を本番で計測
#   bash scripts/verify_effect.sh ai_quality http://localhost:8000/topics.json
#   bash scripts/verify_effect.sh mobile_layout           # puppeteer で 375px 横スクロール検査
#   bash scripts/verify_effect.sh mobile                  # mobile_layout の別名
#   bash scripts/verify_effect.sh freshness               # topics.json updatedAt が 90 分以内
#   bash scripts/verify_effect.sh all                     # ai_quality + freshness を順に実行 (mobile は除く: 重い)
#
# 標準出力:
#   Verified-Effect: <fix_type> <metric>=<value> <PASS|FAIL> @ <JST timestamp>
#
# exit code:
#   0  : PASS
#   1  : FAIL (閾値割れ)
#   2  : 実行エラー (依存不足・URL 不達)
#
# Verified 行への組み込み例:
#   git commit -m "fix(P003): T999 keyPoint 充填率改善
#
#   $(bash scripts/verify_effect.sh ai_quality)
#   "

set -u

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

FIX_TYPE="${1:-}"
shift || true

JST_TS=$(TZ=Asia/Tokyo date "+%Y-%m-%dT%H:%M%z")

if [ -z "$FIX_TYPE" ]; then
  cat >&2 <<EOF
usage: $0 <fix_type> [args]

fix_type:
  ai_quality      [topics_url]   aiGenerated=True 母集団の keyPoint>=50% / perspectives>=60% で PASS
  mobile_layout   [pages_csv]    375px 幅で横スクロール無し (PASS) — puppeteer 必要
  mobile                         mobile_layout の別名
  freshness       [topics_url]   topics.json updatedAt が 90 分以内 (PASS)
  empty_topics    [base_url]     topics.json の detail JSON 欠損率 0% / articleCount<2 率 0%
  all                            ai_quality + freshness をまとめて実行 (mobile は除く)

Verified-Effect 行を stdout に出力。閾値未達は exit 1。
EOF
  exit 2
fi

# ──────────────────────────────────────────────────────────────────
case "$FIX_TYPE" in
  ai_quality)
    URL="${1:-https://flotopic.com/api/topics.json}"
    # aiGenerated=True 母集団に対する充填率。閾値: keyPoint>=50%, perspectives>=60% (T2026-0428-Y)
    KP_THRESHOLD="${AI_QUALITY_KP_THRESHOLD:-50}"
    PV_THRESHOLD="${AI_QUALITY_PV_THRESHOLD:-60}"
    if ! command -v jq >/dev/null 2>&1; then
      echo "[verify_effect] jq 必要 (brew install jq)" >&2
      exit 2
    fi
    TMP=$(mktemp)
    trap 'rm -f "$TMP"' EXIT
    if ! curl -fsSL -m 30 "$URL" -o "$TMP"; then
      echo "[verify_effect] curl 失敗: $URL" >&2
      exit 2
    fi
    # topics.json は { "topics": [...], ... } 形式 / 配列形式どちらにも対応。
    # 母集団は aiGenerated=True のみ — 「AI 要約は走ったが必須フィールドが空 (success-but-empty)」を検出する設計。
    TOTAL=$(jq '[(.topics // .)[] | select(.aiGenerated == true)] | length' "$TMP" 2>/dev/null)
    if [ -z "$TOTAL" ] || [ "$TOTAL" = "null" ]; then
      echo "[verify_effect] topics 取得不能" >&2
      exit 2
    fi
    if [ "$TOTAL" = "0" ]; then
      echo "Verified-Effect: ai_quality aiGenerated=0 keyPoint=N/A perspectives=N/A SKIP @ ${JST_TS}"
      exit 0
    fi
    KP_FILLED=$(jq '[(.topics // .)[] | select(.aiGenerated == true) | select(.keyPoint != null and (.keyPoint | tostring | length) > 0)] | length' "$TMP")
    PV_FILLED=$(jq '[(.topics // .)[] | select(.aiGenerated == true) | select(.perspectives != null and (.perspectives | length // 0) > 0)] | length' "$TMP")
    KP_PCT=$(awk -v a="$KP_FILLED" -v b="$TOTAL" 'BEGIN{ if(b>0) printf "%.1f", a/b*100; else print "0.0" }')
    PV_PCT=$(awk -v a="$PV_FILLED" -v b="$TOTAL" 'BEGIN{ if(b>0) printf "%.1f", a/b*100; else print "0.0" }')
    KP_PASS=$(awk -v p="$KP_PCT" -v t="$KP_THRESHOLD" 'BEGIN{ if(p+0 >= t+0) print "PASS"; else print "FAIL" }')
    PV_PASS=$(awk -v p="$PV_PCT" -v t="$PV_THRESHOLD" 'BEGIN{ if(p+0 >= t+0) print "PASS"; else print "FAIL" }')
    if [ "$KP_PASS" = "PASS" ] && [ "$PV_PASS" = "PASS" ]; then PASS="PASS"; else PASS="FAIL"; fi
    echo "Verified-Effect: ai_quality keyPoint=${KP_PCT}%(${KP_FILLED}/${TOTAL}) perspectives=${PV_PCT}%(${PV_FILLED}/${TOTAL}) thresholds=kp${KP_THRESHOLD}/pv${PV_THRESHOLD} ${PASS} @ ${JST_TS}"
    [ "$PASS" = "PASS" ] || exit 1
    exit 0
    ;;

  all)
    # ai_quality と freshness を順に実行。mobile は puppeteer 必須のためデフォルトで除外
    PASS_COUNT=0
    FAIL_COUNT=0
    ERR_COUNT=0
    echo "=== verify_effect.sh all (ai_quality + freshness) ==="
    bash "$0" ai_quality
    case $? in
      0) PASS_COUNT=$((PASS_COUNT+1)) ;;
      1) FAIL_COUNT=$((FAIL_COUNT+1)) ;;
      *) ERR_COUNT=$((ERR_COUNT+1)) ;;
    esac
    bash "$0" freshness
    case $? in
      0) PASS_COUNT=$((PASS_COUNT+1)) ;;
      1) FAIL_COUNT=$((FAIL_COUNT+1)) ;;
      *) ERR_COUNT=$((ERR_COUNT+1)) ;;
    esac
    echo "=== 結果: PASS=${PASS_COUNT} FAIL=${FAIL_COUNT} ERROR=${ERR_COUNT} @ ${JST_TS} ==="
    if [ $FAIL_COUNT -gt 0 ]; then exit 1; fi
    if [ $ERR_COUNT -gt 0 ]; then exit 2; fi
    exit 0
    ;;

  mobile|mobile_layout)
    PAGES_ARG=""
    if [ -n "${1:-}" ]; then PAGES_ARG="--pages=$1"; fi
    if ! command -v node >/dev/null 2>&1; then
      echo "[verify_effect] node 必要" >&2
      exit 2
    fi
    OUT=$(node "$REPO_ROOT/scripts/check_mobile_layout.js" $PAGES_ARG 2>&1)
    RC=$?
    echo "$OUT"
    if [ $RC -eq 0 ]; then
      RESULT="PASS"
    elif [ $RC -eq 1 ]; then
      RESULT="FAIL"
    else
      RESULT="ERROR"
    fi
    # 詳細は OUT に出ているので、Verified-Effect は要約のみ
    PAGE_COUNT=$(echo "$OUT" | grep -cE '^[✅❌] ' || true)
    OVERFLOW_COUNT=$(echo "$OUT" | grep -cE '^❌ ' || true)
    echo "Verified-Effect: mobile_layout viewport=375px pages=${PAGE_COUNT} overflow=${OVERFLOW_COUNT} ${RESULT} @ ${JST_TS}"
    [ "$RESULT" = "PASS" ] || exit 1
    exit 0
    ;;

  empty_topics)
    # T2026-0428-AK: topics.json の各トピックに対して
    #   1. detail JSON (api/topic/{tid}.json) が S3 に存在する
    #   2. articleCount >= 2
    # を物理確認。両方 0% 違反で PASS。
    BASE="${1:-https://flotopic.com}"
    EMPTY_THRESHOLD_PCT="${EMPTY_TOPICS_THRESHOLD_PCT:-0}"
    if ! command -v jq >/dev/null 2>&1; then
      echo "[verify_effect] jq 必要" >&2
      exit 2
    fi
    TMP=$(mktemp)
    trap 'rm -f "$TMP"' EXIT
    if ! curl -fsSL -m 30 "$BASE/api/topics.json" -o "$TMP"; then
      echo "[verify_effect] curl 失敗: $BASE/api/topics.json" >&2
      exit 2
    fi
    TOTAL=$(jq '[(.topics // .)[]] | length' "$TMP" 2>/dev/null)
    if [ -z "$TOTAL" ] || [ "$TOTAL" = "null" ] || [ "$TOTAL" = "0" ]; then
      echo "Verified-Effect: empty_topics topics=0 SKIP @ ${JST_TS}"
      exit 0
    fi
    LOW_COUNT=$(jq '[(.topics // .)[] | select((.articleCount // 0) < 2)] | length' "$TMP")
    # detail JSON 欠損数: 各 topicId に対して HEAD リクエスト
    TIDS=$(jq -r '(.topics // .)[] | .topicId' "$TMP")
    MISSING=0
    CHECKED=0
    for TID in $TIDS; do
      CHECKED=$((CHECKED+1))
      STATUS=$(curl -s -o /dev/null -w '%{http_code}' -m 10 -I "$BASE/api/topic/${TID}.json")
      if [ "$STATUS" != "200" ]; then
        MISSING=$((MISSING+1))
      fi
    done
    LOW_PCT=$(awk -v a="$LOW_COUNT" -v b="$TOTAL" 'BEGIN{ if(b>0) printf "%.1f", a/b*100; else print "0.0" }')
    MISS_PCT=$(awk -v a="$MISSING" -v b="$CHECKED" 'BEGIN{ if(b>0) printf "%.1f", a/b*100; else print "0.0" }')
    LOW_PASS=$(awk -v p="$LOW_PCT" -v t="$EMPTY_THRESHOLD_PCT" 'BEGIN{ if(p+0 <= t+0) print "PASS"; else print "FAIL" }')
    MISS_PASS=$(awk -v p="$MISS_PCT" -v t="$EMPTY_THRESHOLD_PCT" 'BEGIN{ if(p+0 <= t+0) print "PASS"; else print "FAIL" }')
    if [ "$LOW_PASS" = "PASS" ] && [ "$MISS_PASS" = "PASS" ]; then PASS="PASS"; else PASS="FAIL"; fi
    echo "Verified-Effect: empty_topics articleCount<2=${LOW_PCT}%(${LOW_COUNT}/${TOTAL}) detail_missing=${MISS_PCT}%(${MISSING}/${CHECKED}) threshold=${EMPTY_THRESHOLD_PCT}% ${PASS} @ ${JST_TS}"
    [ "$PASS" = "PASS" ] || exit 1
    exit 0
    ;;

  freshness)
    URL="${1:-https://flotopic.com/api/topics.json}"
    THRESHOLD_MIN="${FRESHNESS_THRESHOLD_MIN:-90}"
    if ! command -v jq >/dev/null 2>&1; then
      echo "[verify_effect] jq 必要" >&2
      exit 2
    fi
    TMP=$(mktemp)
    trap 'rm -f "$TMP"' EXIT
    if ! curl -fsSL -m 30 "$URL" -o "$TMP"; then
      echo "[verify_effect] curl 失敗: $URL" >&2
      exit 2
    fi
    UPDATED_AT=$(jq -r '.updatedAt // .updated_at // empty' "$TMP")
    if [ -z "$UPDATED_AT" ] || [ "$UPDATED_AT" = "null" ]; then
      echo "[verify_effect] updatedAt フィールドが取得できない" >&2
      exit 2
    fi
    NOW_EPOCH=$(date -u +%s)
    # ISO 8601 → epoch (Linux: date -d / Mac: date -j)
    if date -u -d "$UPDATED_AT" +%s >/dev/null 2>&1; then
      UPDATED_EPOCH=$(date -u -d "$UPDATED_AT" +%s)
    else
      # macOS BSD date: 'YYYY-MM-DDTHH:MM:SSZ' → '%Y-%m-%dT%H:%M:%SZ'
      CLEAN=$(echo "$UPDATED_AT" | sed -E 's/\.[0-9]+//;s/(\+|-)[0-9]{2}:?[0-9]{2}/Z/')
      UPDATED_EPOCH=$(date -u -j -f "%Y-%m-%dT%H:%M:%SZ" "$CLEAN" +%s 2>/dev/null || echo "")
    fi
    if [ -z "$UPDATED_EPOCH" ]; then
      echo "[verify_effect] updatedAt parse 失敗: $UPDATED_AT" >&2
      exit 2
    fi
    DIFF_MIN=$(( (NOW_EPOCH - UPDATED_EPOCH) / 60 ))
    PASS=$(awk -v d="$DIFF_MIN" -v t="$THRESHOLD_MIN" 'BEGIN{ if(d+0 <= t+0) print "PASS"; else print "FAIL" }')
    echo "Verified-Effect: freshness updatedAt=${UPDATED_AT} age_min=${DIFF_MIN} threshold_min=${THRESHOLD_MIN} ${PASS} @ ${JST_TS}"
    [ "$PASS" = "PASS" ] || exit 1
    exit 0
    ;;

  *)
    echo "[verify_effect] unknown fix_type: $FIX_TYPE" >&2
    exit 2
    ;;
esac
