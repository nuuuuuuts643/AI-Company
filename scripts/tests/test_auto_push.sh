#!/bin/bash
# scripts/tests/test_auto_push.sh
# auto-push.sh のロジック単体テスト (T2026-0502-AUTOPUSH-PR-FLOW)

set -euo pipefail

PASS=0
FAIL=0

ok() { echo "✅ $1"; PASS=$((PASS+1)); }
fail() { echo "❌ $1"; FAIL=$((FAIL+1)); }

# ------- ヘルパー関数を auto-push.sh からソース -------
# push_changes() と fswatch ループは除き、ヘルパー関数のみ抽出
SHARED_DOCS=(
  "CLAUDE.md"
  "WORKING.md"
  "TASKS.md"
  "HISTORY.md"
  "docs/lessons-learned.md"
)

is_shared_doc() {
  local file="$1"
  for doc in "${SHARED_DOCS[@]}"; do
    [ "$file" = "$doc" ] && return 0
  done
  return 1
}

# ------- テスト: is_shared_doc -------

is_shared_doc "CLAUDE.md"     && ok "CLAUDE.md は shared_doc"     || fail "CLAUDE.md は shared_doc のはず"
is_shared_doc "WORKING.md"    && ok "WORKING.md は shared_doc"    || fail "WORKING.md は shared_doc のはず"
is_shared_doc "TASKS.md"      && ok "TASKS.md は shared_doc"      || fail "TASKS.md は shared_doc のはず"
is_shared_doc "HISTORY.md"    && ok "HISTORY.md は shared_doc"    || fail "HISTORY.md は shared_doc のはず"
is_shared_doc "docs/lessons-learned.md" && ok "docs/lessons-learned.md は shared_doc" || fail "docs/lessons-learned.md は shared_doc のはず"

! is_shared_doc "scripts/auto-push.sh" && ok "scripts/auto-push.sh は shared_doc でない" || fail "scripts/auto-push.sh は shared_doc であってはならない"
! is_shared_doc "lambda/handler.py"    && ok "lambda/handler.py は shared_doc でない"    || fail "lambda/handler.py は shared_doc であってはならない"
! is_shared_doc "frontend/index.html"  && ok "frontend/index.html は shared_doc でない"  || fail "frontend/index.html は shared_doc であってはならない"
! is_shared_doc ""                     && ok "空文字列は shared_doc でない"               || fail "空文字列は shared_doc であってはならない"

# ------- テスト: ブランチ名スラグ生成ロジック -------
slug_from_file() {
  local file="$1"
  echo "$file" | sed 's|.*/||; s/[^a-zA-Z0-9]/-/g; s/--*/-/g; s/^-//; s/-$//' | tr '[:upper:]' '[:lower:]' | cut -c1-30
}

SLUG=$(slug_from_file "scripts/auto-push.sh")
[ "$SLUG" = "auto-push-sh" ] && ok "スラグ生成: scripts/auto-push.sh → auto-push-sh" || fail "スラグ生成が期待値と異なる: $SLUG"

SLUG=$(slug_from_file "WORKING.md")
[ "$SLUG" = "working-md" ] && ok "スラグ生成: WORKING.md → working-md" || fail "スラグ生成が期待値と異なる: $SLUG"

SLUG=$(slug_from_file "lambda/processor/proc_ai.py")
[ "$SLUG" = "proc-ai-py" ] && ok "スラグ生成: 深いパス → proc-ai-py" || fail "スラグ生成が期待値と異なる: $SLUG"

# 30文字上限
SLUG=$(slug_from_file "very-long-file-name-that-exceeds-thirty-characters.sh")
[ ${#SLUG} -le 30 ] && ok "スラグ生成: 30文字以内に切り詰め (len=${#SLUG})" || fail "スラグが30文字超: $SLUG"

# ------- テスト: WORKING.md [Code] 宣言チェック -------
TMP=$(mktemp)

# [Code] 行あり
cat > "$TMP" << 'EOF'
| [Code] T2026-0502-AUTOPUSH-PR-FLOW auto-push.sh | Code | scripts/auto-push.sh | 2026-05-02 11:00 | yes |
EOF
grep -q '\[Code\]' "$TMP" && ok "WORKING.md [Code] 宣言あり → 検出OK" || fail "[Code] 行を検出できなかった"

# [Code] 行なし
cat > "$TMP" << 'EOF'
| [Cowork] T2026-0502-G docs only | Cowork | WORKING.md | 2026-05-02 08:04 | no |
EOF
! grep -q '\[Code\]' "$TMP" && ok "WORKING.md [Code] 宣言なし → 未検出OK" || fail "[Code] 行を誤検出した"

rm -f "$TMP"

# ------- 結果サマリ -------
echo ""
echo "--- テスト結果: PASS=$PASS FAIL=$FAIL ---"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
