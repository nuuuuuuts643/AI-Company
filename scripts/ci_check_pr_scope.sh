#!/bin/bash
# PRの変更ファイル数をカウントし、10件以上の場合にCI失敗させる
set -euo pipefail

THRESHOLD=10
FILE_COUNT=$(git diff --name-only "origin/main...HEAD" 2>/dev/null | wc -l | tr -d ' ')

echo "変更ファイル数: ${FILE_COUNT}"

if [ "${FILE_COUNT}" -ge "${THRESHOLD}" ]; then
  echo "::error::変更ファイル数が ${FILE_COUNT} 件です（上限 $((THRESHOLD - 1)) 件）。PRを分割してください。広範囲変更の場合は PR 説明に理由を明記した上でリポジトリ管理者が --no-verify で例外対応してください。"
  exit 1
fi

echo "✅ 変更ファイル数 ${FILE_COUNT} 件 — OK"
