#!/bin/bash
# コードセッション並走監視スクリプト
# 用途: GitHub Actions から定期実行 (15分ごと)
# 機能: WORKING.md から [Code] 行をカウント → 2件以上なら exit 1
#
# 使用例:
#   bash scripts/check_concurrent_sessions.sh
#   echo $?  # 0: OK (0-1件), 1: 並走中 (≥2件)

set -u

REPO="${REPO:-.}"
cd "$REPO"

if [ ! -f WORKING.md ]; then
  echo "❌ WORKING.md not found"
  exit 1
fi

# WORKING.md から [Code] 行をカウント
CODE_COUNT=$(awk '
  /^## 現在着手中/        { in_sec=1; next }
  /^## /                  { in_sec=0 }
  in_sec && /^\| *\[Code\]/ { count++ }
  END { print count + 0 }
' WORKING.md)

if [ "$CODE_COUNT" -ge 2 ]; then
  echo "[Code] sessions: $CODE_COUNT (⚠️  ≥2 is concurrent)"
  exit 1
else
  echo "[Code] sessions: $CODE_COUNT (✅ OK)"
  exit 0
fi
