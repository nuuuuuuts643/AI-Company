#!/bin/bash
# scripts/check_lambda_freshness.sh — T2026-0502-DEPLOY-WATCHDOG
# Lambda の lastModified と直近 lambda commit time を比較し、
# 30min 超の乖離があれば exit 1 + 警告メッセージ。
#
# 使い方:
#   bash scripts/check_lambda_freshness.sh [function-name] [lambda-path-glob]
#   bash scripts/check_lambda_freshness.sh  # デフォルト: p003-processor / projects/P003-news-timeline/lambda/
#
# 終了コード:
#   0: 30分以内 (正常)
#   1: 30分超 (deploy lag 検知)
#   2: 設定エラー (AWS CLI 未設定など)

set -uo pipefail

FUNCTION_NAME="${1:-p003-processor}"
LAMBDA_PATH="${2:-projects/P003-news-timeline/lambda/}"
THRESHOLD_SEC=1800  # 30 minutes

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# --- 1. main HEAD での lambda 最新 commit time (unix epoch) ---
COMMIT_TIME=$(git -C "$REPO_ROOT" log -1 --format="%ct" -- "$LAMBDA_PATH" 2>&1)
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ] || [ -z "$COMMIT_TIME" ]; then
  echo "[WARN] git log failed or no commits found for $LAMBDA_PATH (exit=$EXIT_CODE)" >&2
  echo "       COMMIT_TIME='$COMMIT_TIME'" >&2
  # commit なし = lambda コードが変更されていない = 問題なし
  echo "[OK] No lambda commits found; skipping freshness check."
  exit 0
fi

echo "[INFO] Latest lambda commit time: $(date -r "$COMMIT_TIME" '+%Y-%m-%d %H:%M:%S %Z' 2>/dev/null || echo "$COMMIT_TIME epoch") ($COMMIT_TIME)"

# --- 2. Lambda lastModified 取得 ---
LAMBDA_LAST_MODIFIED=$(aws lambda get-function-configuration \
  --function-name "$FUNCTION_NAME" \
  --region ap-northeast-1 \
  --query 'LastModified' \
  --output text 2>&1)
AWS_EXIT=$?
if [ $AWS_EXIT -ne 0 ]; then
  echo "[ERROR] aws lambda get-function-configuration failed (exit=$AWS_EXIT): $LAMBDA_LAST_MODIFIED" >&2
  exit 2
fi

# LastModified は "2026-05-01T10:30:00.000+0000" 形式
LAMBDA_TS=$(python3 -c "
import sys
from datetime import datetime, timezone
s = '$LAMBDA_LAST_MODIFIED'
for fmt in ('%Y-%m-%dT%H:%M:%S.%f%z', '%Y-%m-%dT%H:%M:%S%z'):
    try:
        dt = datetime.strptime(s, fmt)
        print(int(dt.timestamp()))
        sys.exit(0)
    except ValueError:
        pass
print(-1)
" 2>&1)
PY_EXIT=${PIPESTATUS[0]}
if [ $PY_EXIT -ne 0 ] || [ "$LAMBDA_TS" = "-1" ]; then
  echo "[ERROR] Failed to parse Lambda lastModified: '$LAMBDA_LAST_MODIFIED'" >&2
  exit 2
fi

echo "[INFO] Lambda lastModified: $LAMBDA_LAST_MODIFIED ($LAMBDA_TS)"

# --- 3. 差分計算 ---
DIFF_SEC=$(( LAMBDA_TS - COMMIT_TIME ))
DIFF_MIN=$(( DIFF_SEC / 60 ))

echo "[INFO] Lambda deploy lag: ${DIFF_MIN}min (commit=$COMMIT_TIME, lambda_updated=$LAMBDA_TS, diff=${DIFF_SEC}s)"

if [ $DIFF_SEC -ge $THRESHOLD_SEC ] || [ $DIFF_SEC -lt $(( -THRESHOLD_SEC )) ]; then
  echo "[WARN] Deploy lag ${DIFF_MIN}min exceeds threshold $(( THRESHOLD_SEC / 60 ))min for $FUNCTION_NAME" >&2
  echo "[WARN] Lambda may not have been deployed after the last lambda commit." >&2
  exit 1
fi

echo "[OK] Lambda freshness OK (lag=${DIFF_MIN}min, threshold=$(( THRESHOLD_SEC / 60 ))min)"
exit 0
