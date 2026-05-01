#!/bin/bash
# gen_dispatch_prompt.sh — Dispatch セッション起動プロンプトを自動生成する
# 使い方: bash scripts/gen_dispatch_prompt.sh | pbcopy  (Mac でクリップボードにコピー)
# または:  bash scripts/gen_dispatch_prompt.sh          (標準出力に表示)
#
# 「仕組み」: WORKING.md の Dispatch継続性・TASKS.md の未着手高優先タスクを
#  自動で埋め込み、毎回コピペで使えるプロンプトを生成する。
#  ルールが変わったり完了条件が変わっても、このスクリプトを更新すれば全セッションに反映される。

set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"

# --- Dispatch継続性セクションを抽出 ---
dispatch_section=""
if [ -f "$REPO/WORKING.md" ]; then
  dispatch_section=$(awk '/## 🟢 Dispatch 継続性/,/^---/' "$REPO/WORKING.md" \
    | grep -v "^---" | grep -v "^## 🟢" | grep -v "^>" | sed '/^$/d' | head -10)
fi

# --- TASKS.md から未着手の高・中優先タスクを抽出（🔴/🟡 のみ、先頭3件）---
priority_tasks=""
if [ -f "$REPO/TASKS.md" ]; then
  priority_tasks=$(grep -E "^\| T[0-9]|^\| ~~T" "$REPO/TASKS.md" \
    | grep -v "~~T" \
    | grep -E "🔴|🟡" \
    | head -3 \
    | sed 's/|/│/g' \
    | awk -F'│' '{printf "  - %s: %s\n", $2, $4}' \
    | sed 's/  */ /g')
fi

# --- JST 現在時刻 ---
jst=$(TZ='Asia/Tokyo' date '+%Y-%m-%d %H:%M JST')

# --- プロンプト生成 ---
cat << PROMPT
P003 Dispatch。ルール通りに動いて。

1. session_bootstrap.sh を実行して起動チェックを完了させる
2. WORKING.md の Dispatch継続性セクションで状態を把握する
3. TASKS.md で現フェーズの未着手タスクを確認し、優先順に実行する
4. 確認・報告・承認を求めず、ルールに従って前進する
5. 重大な判断（新規AWS課金・不可逆操作）のみ事前確認する
6. タスク完了後は flotopic.com で実機確認してから「完了」と報告する

--- 現在の状態 (${jst}) ---
PROMPT

if [ -n "$dispatch_section" ]; then
  echo "【Dispatch継続性】"
  echo "$dispatch_section" | head -6
  echo ""
fi

if [ -n "$priority_tasks" ]; then
  echo "【未着手優先タスク（TASKS.md より）】"
  echo "$priority_tasks"
  echo ""
fi

cat << 'FOOTER'
---
※ この状態スナップショットは gen_dispatch_prompt.sh が自動生成。
   ルール変更時は docs/dispatch-session-start.md と本スクリプトを更新する。
FOOTER
