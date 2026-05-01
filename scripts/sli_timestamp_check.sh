#!/bin/bash
# T2026-0501-TS: SLI-timestamp — topics.json / topics-card.json の timestamp 系
#  フィールドが Unix秒 (10桁整数) で書かれていないか検出する物理ガード。
#
# 背景:
#   - SNAP[*].timestamp は ISO 文字列、article.publishedAt は Unix 秒整数、
#     predictionMadeAt は ISO と、書き込み元が複数あり、
#     `new Date(v)` を生で呼ぶ JS 側で 1970 年代に解釈される事故が起きていた
#     (cc7f78cd55b81da6 の「スナップショットのタイミングがおかしい」報告)。
#   - フロント側は js/timestamp.js の toMs() で正規化済みだが、書き込み側で
#     ISO 想定のフィールドに Unix 秒が入る『データ汚染』を早期検知する観測 SLI。
#
# 仕様:
#   入力 (環境変数で上書き可):
#     FLOTOPIC_TOPICS_URL          (default: https://flotopic.com/api/topics.json)
#     FLOTOPIC_TOPICS_CARD_URL     (default: https://flotopic.com/api/topics-card.json)
#   観測対象フィールド (ISO 想定 = Unix 秒整数で入っていたら警告):
#     - lastUpdated (※ Unix 秒/ISO 混在許容: lastUpdated は両方の現実があるので除外)
#     - lastArticleAt (※ 同上、除外)
#     - predictionMadeAt  (ISO 想定)
#     - createdAt          (ISO 想定)
#   出力:
#     stdout に key=value (GitHub Actions $GITHUB_OUTPUT 用)
#       status=ok|warn|error|skipped
#       bad_count=<int>
#       total_count=<int>
#   閾値:
#     bad_count = 0           : ok
#     bad_count >= 1          : warn  (Unix 秒の混入を1件でも検出)
#     bad_count >= 5          : error (パイプライン側のリグレッション可能性)
#   依存: curl, jq (どちらも GitHub Actions 標準環境にある)。AWS CLI 不要。
#
# 使い方:
#     bash scripts/sli_timestamp_check.sh
set -u

URL_TOPICS="${FLOTOPIC_TOPICS_URL:-https://flotopic.com/api/topics.json}"
URL_CARD="${FLOTOPIC_TOPICS_CARD_URL:-https://flotopic.com/api/topics-card.json}"

WARN_BAD=1
ERROR_BAD=5

if ! command -v jq >/dev/null 2>&1; then
  echo "::warning::sli_timestamp_check: jq not installed (skip)"
  echo "status=skipped"
  echo "bad_count=-1"
  echo "total_count=0"
  exit 0
fi

TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT

# 取得元はどちらか1つで OK (topics.json を優先、失敗したら topics-card.json)
if curl -fsSL "$URL_TOPICS" -o "$TMP" 2>/dev/null; then
  SRC="$URL_TOPICS"
elif curl -fsSL "$URL_CARD" -o "$TMP" 2>/dev/null; then
  SRC="$URL_CARD"
else
  echo "::warning::sli_timestamp_check: failed to fetch $URL_TOPICS / $URL_CARD"
  echo "status=skipped"
  echo "bad_count=-1"
  echo "total_count=0"
  exit 0
fi

# topics 配列を取り出す。形式は { "topics": [...] } か直接配列のどちらかを許容。
TOPICS_LEN=$(jq '(.topics // .) | length' "$TMP" 2>/dev/null || echo 0)
if [ "${TOPICS_LEN:-0}" -le 0 ]; then
  echo "::warning::sli_timestamp_check: empty topics array in $SRC"
  echo "status=skipped"
  echo "bad_count=-1"
  echo "total_count=0"
  exit 0
fi

# ISO 想定のフィールドが「数値で 1e9 < n < 1e12」(=Unix 秒整数の範囲)
# または「数字だけの文字列」で入っているトピックを数える。
# lastUpdated / lastArticleAt は Unix 秒 / ISO 両方の現実があるため対象外。
FIELDS=("predictionMadeAt" "createdAt")

BAD_TOTAL=0
BAD_DETAILS=""

for FIELD in "${FIELDS[@]}"; do
  COUNT=$(jq -r --arg f "$FIELD" '
    [ (.topics // .)[]
      | select(.[$f] != null)
      | .[$f]
      | select(
          (type == "number" and . > 1000000000 and . < 1000000000000)
          or (type == "string" and test("^[0-9]+$") and (tonumber > 1000000000) and (tonumber < 1000000000000))
        )
    ] | length
  ' "$TMP" 2>/dev/null || echo 0)
  COUNT=${COUNT:-0}
  if [ "$COUNT" -gt 0 ]; then
    BAD_TOTAL=$((BAD_TOTAL + COUNT))
    BAD_DETAILS="${BAD_DETAILS}${FIELD}=${COUNT} "
  fi
done

# storyTimeline[*].at が Unix 秒整数ならカウント (storyTimeline は ISO 想定)
ST_BAD=$(jq -r '
  [ (.topics // .)[]
    | (.storyTimeline // [])[]
    | (.at // empty)
    | select(
        (type == "number" and . > 1000000000 and . < 1000000000000)
        or (type == "string" and test("^[0-9]+$") and (tonumber > 1000000000) and (tonumber < 1000000000000))
      )
  ] | length
' "$TMP" 2>/dev/null || echo 0)
ST_BAD=${ST_BAD:-0}
if [ "$ST_BAD" -gt 0 ]; then
  BAD_TOTAL=$((BAD_TOTAL + ST_BAD))
  BAD_DETAILS="${BAD_DETAILS}storyTimeline.at=${ST_BAD} "
fi

if [ "$BAD_TOTAL" -ge "$ERROR_BAD" ]; then
  STATUS=error
elif [ "$BAD_TOTAL" -ge "$WARN_BAD" ]; then
  STATUS=warn
else
  STATUS=ok
fi

echo "status=${STATUS}"
echo "bad_count=${BAD_TOTAL}"
echo "total_count=${TOPICS_LEN}"
echo "src=${SRC}"
if [ -n "$BAD_DETAILS" ]; then
  echo "bad_details=${BAD_DETAILS}"
fi

# warn は exit 0 (continue-on-error 想定で SLI を止めない)、error も exit 0 で
# Slack 通知に判断を委ねる (workflow 側 if: status==error/warn で別ステップ実行)
exit 0
