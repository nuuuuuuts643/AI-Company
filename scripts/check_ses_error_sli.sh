#!/bin/bash
# T2026-0502-SES-METRIC-FILTER: SES error rate SLI (SLI 14)
#
# 根本原因: T2026-0502-S (lessons-learned) で `p003-contact` の SES SendEmail が silent fail し
#   1ヶ月気付かれずに放置された。handler.py 側は [ERROR] プレフィックスに昇格済み (PR #180)。
#   本スクリプトはその「外部観測」レイヤー。CloudWatch Logs で直近1時間の出現件数を観測する。
#
# 使い方:
#   bash scripts/check_ses_error_sli.sh                         # 直近 1 時間
#   SES_WINDOW_MIN=60 bash scripts/check_ses_error_sli.sh       # 窓を分単位で指定
#   SES_LOG_GROUP=/aws/lambda/p003-contact bash scripts/check_ses_error_sli.sh
#
# 出力:
#   stdout: ses_error_count=<N>
#   stderr: WARN (1〜4) / ERROR (5以上)
#
# 終了コード:
#   0: 正常 (0 件)
#   1: WARN (1〜4)
#   2: ERROR (5以上)
#   3: aws cli 不在 / 権限不足 / 想定外エラー (fail-open: SLI を赤くしない・別途 ::warning::)

set -uo pipefail

LOG_GROUP="${SES_LOG_GROUP:-/aws/lambda/p003-contact}"
WINDOW_MIN="${SES_WINDOW_MIN:-60}"
REGION="${AWS_REGION:-ap-northeast-1}"
PATTERN='[ERROR] SES send'

if ! command -v aws >/dev/null 2>&1; then
  echo "::warning::check_ses_error_sli: aws cli が見つかりません — fail-open で skip" >&2
  echo "ses_error_count=unknown"
  exit 3
fi

NOW_MS=$(date +%s%3N)
START_MS=$(( NOW_MS - WINDOW_MIN * 60 * 1000 ))

# filter-pattern は CloudWatch Logs 構文。`?term1 ?term2` で OR、リテラルは "..." で囲む。
# `[ERROR] SES send` を全行検索したいので "[ERROR]" と "SES" "send" を AND で組む形にする。
RAW=$(aws logs filter-log-events \
  --region "$REGION" \
  --log-group-name "$LOG_GROUP" \
  --start-time "$START_MS" \
  --filter-pattern '"[ERROR] SES send"' \
  --query 'events[*].message' \
  --output text 2>/dev/null)
RC=$?

if [ "$RC" -ne 0 ]; then
  echo "::warning::check_ses_error_sli: filter-log-events 失敗 (権限不足 or log group 未作成?) — fail-open" >&2
  echo "ses_error_count=unknown"
  exit 3
fi

# RAW が空文字列なら 0 件、改行で件数カウント
if [ -z "$RAW" ]; then
  COUNT=0
else
  COUNT=$(printf '%s\n' "$RAW" | grep -c '\[ERROR\] SES send' || true)
fi

echo "ses_error_count=${COUNT}"

if [ "$COUNT" -ge 5 ]; then
  echo "ERROR: SES send errors ${COUNT} in last ${WINDOW_MIN}min on ${LOG_GROUP} (threshold: 5)" >&2
  exit 2
elif [ "$COUNT" -ge 1 ]; then
  echo "WARN: SES send errors ${COUNT} in last ${WINDOW_MIN}min on ${LOG_GROUP} (threshold WARN: 1, ERROR: 5)" >&2
  exit 1
fi

exit 0
