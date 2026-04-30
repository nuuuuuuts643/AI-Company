#!/bin/bash
# T264: cleanup_stale_worktrees.sh の dry-run 動作テスト
# - tempdir に test repo を作る → 8h+ 前 mtime の worktree を 1 つ作る
# - dry-run 実行で「would remove」が 1 件出ること、実削除されないこと
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TARGET_SCRIPT="$REPO_ROOT/scripts/cleanup_stale_worktrees.sh"

[ -x "$TARGET_SCRIPT" ] || { echo "❌ target script not executable: $TARGET_SCRIPT"; exit 1; }

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# テスト用 repo セットアップ
cd "$TMP"
git init -q -b main
git config user.email test@test.local
git config user.name test
echo init > README.md
git add README.md
git commit -q -m init

# WORKING.md 作成（active 行ナシで「全 worktree が stale」になる前提）
cat > WORKING.md <<'EOF'
# WORKING

## 現在着手中

| タスク名 | 種別 | 変更予定ファイル | 開始 JST | needs-push |
|---|---|---|---|---|
EOF

# .claude/worktrees/ 配下に stale worktree を 1 つ作る
mkdir -p .claude/worktrees
git worktree add -q -b test-stale-branch .claude/worktrees/test-stale-wt
# 8h+ 前に mtime を巻き戻す（macOS / Linux 両対応）
# _latest_activity が見る: worktree dir / admin dir の HEAD / index / logs/HEAD
touch -t 202501010000 .claude/worktrees/test-stale-wt
for f in HEAD index logs/HEAD; do
  [ -f .git/worktrees/test-stale-wt/$f ] && touch -t 202501010000 .git/worktrees/test-stale-wt/$f
done

# REPO 環境変数を渡して dry-run 実行
out=$(REPO="$TMP" bash "$TARGET_SCRIPT" --dry-run 2>&1)

echo "$out" | grep -q "would remove: test-stale-wt" || {
  echo "❌ FAIL: stale worktree was not flagged as would-remove"
  echo "--- output ---"
  echo "$out"
  exit 1
}

# 実削除されていないこと（dry-run の保証）
[ -d "$TMP/.claude/worktrees/test-stale-wt" ] || {
  echo "❌ FAIL: dry-run actually deleted the worktree"
  exit 1
}

# summary 行が出ていること
echo "$out" | grep -q "summary (dry-run)" || {
  echo "❌ FAIL: summary line missing"
  echo "--- output ---"
  echo "$out"
  exit 1
}

echo "✅ test_cleanup_stale_worktrees: PASS"
exit 0
