#!/bin/bash
# PRの変更ファイル数をカウントし、10件以上の場合にGitHub Step Summaryへ警告を出す
set -euo pipefail

THRESHOLD=10
FILE_COUNT=$(git diff --name-only "origin/main...HEAD" 2>/dev/null | wc -l | tr -d ' ')

echo "変更ファイル数: ${FILE_COUNT}"

if [ "${FILE_COUNT}" -ge "${THRESHOLD}" ]; then
  cat >> "${GITHUB_STEP_SUMMARY:-/dev/stderr}" <<EOF

## ⚠️ PR スコープ警告

このPRは **${FILE_COUNT} ファイル** を変更しています。

**${THRESHOLD}ファイル以上の変更は追跡が困難になります。**
1ワークフロー / 1ファイルグループ単位でPRを分割することを検討してください。

> ルール根拠: PR #86 なぜなぜ分析 Why3 — 変更スコープが大きいとどこで壊れたか判断できない
EOF
  echo "::warning::このPRは ${FILE_COUNT} ファイルを変更しています。10件未満への分割を検討してください。"
fi
