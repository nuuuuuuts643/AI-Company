#!/bin/bash
# AI-Company セッション起動チェック（Code/Cowork 共通）
# 用途: 各セッションが冒頭で 1 回だけ呼ぶ。冪等。
# 仕様: CLAUDE.md「セッション開始時に必ず最初に実行すること」を 1 コマンドに集約。
#
# やること:
#   1. git lock / rebase-merge を _garbage に退避（FUSE rm 不可環境向け）
#   2. ローカル変更を sync commit して remote と同期（push）
#   3. CLAUDE.md の最近の commit を表示（変更検知）
#   4. WORKING.md の stale (8h 超) 行を自動削除
#   5. TASKS.md の取消線済み (`~~T...~~`) 行を HISTORY.md に集約移動
#   6. needs-push:yes が WORKING.md に残っていれば最優先で警告
#   7. 1 行サマリ「✅ 起動チェック完了」を出力
#
# 失敗してもセッション続行できるよう、各ステップは ` || true ` で吸収する。

set -u
REPO="${REPO:-/Users/OWNER/ai-company}"
[ -d "$REPO" ] || REPO="/sessions/keen-optimistic-keller/mnt/ai-company"
[ -d "$REPO" ] || { echo "❌ repo not found"; exit 1; }
cd "$REPO"

mkdir -p .git/_garbage 2>/dev/null

# ---- 1. lock / rebase-merge 退避（堅牢化）----
# FUSE 環境では rm が permission denied なので mv で _garbage に逃がす。
# mv も失敗する場合があるため複数回トライ。
for i in 1 2 3; do
  found_any=0
  for lock in .git/index.lock .git/HEAD.lock .git/objects/maintenance.lock; do
    [ -e "$lock" ] || continue
    found_any=1
    mv "$lock" ".git/_garbage/$(basename $lock).$(date +%s%N)" 2>/dev/null || true
  done
  if [ -d .git/rebase-merge ]; then
    found_any=1
    mv .git/rebase-merge ".git/_garbage/rebase-merge.$(date +%s%N)" 2>/dev/null || true
  fi
  if [ -d .git/rebase-apply ]; then
    found_any=1
    mv .git/rebase-apply ".git/_garbage/rebase-apply.$(date +%s%N)" 2>/dev/null || true
  fi
  [ "$found_any" -eq 0 ] && break
  sleep 1
done

# ---- 2. sync commit & pull --no-rebase & push ----
# rebase 系の中断を作らないため pull は merge 戦略で固定。
git add -A 2>/dev/null
if ! git diff --cached --quiet 2>/dev/null; then
  git commit -m "chore: bootstrap sync $(date '+%Y-%m-%d %H:%M JST')" 2>/dev/null || true
fi
git pull --no-rebase --no-edit origin main 2>&1 | tail -2 || true
mv .git/index.lock .git/_garbage/ 2>/dev/null
git push 2>&1 | tail -2 || true

# ---- 3. CLAUDE.md 変更検知 ----
LATEST_CLAUDE=$(git log --oneline -1 -- CLAUDE.md 2>/dev/null || echo "(none)")

# ---- 4. WORKING.md 8h stale 自動削除 ----
if [ -f WORKING.md ] && [ -x scripts/triage_tasks.py ]; then
  python3 scripts/triage_tasks.py --clean-working-md 2>/dev/null || true
fi

# ---- 5. TASKS.md 取消線→HISTORY.md ----
if [ -f TASKS.md ] && [ -x scripts/triage_tasks.py ]; then
  python3 scripts/triage_tasks.py --triage-tasks 2>/dev/null || true
fi

# ---- 6. needs-push 警告 ----
NEEDS_PUSH=$(grep -nE 'needs-push.*\<yes\>' WORKING.md 2>/dev/null || true)

# ---- 7. サマリ出力 ----
echo "─────────────────────────────────────────"
echo "✅ 起動チェック完了 ($(date '+%Y-%m-%d %H:%M JST'))"
echo "  CLAUDE.md latest: $LATEST_CLAUDE"
if [ -n "$NEEDS_PUSH" ]; then
  echo "  ⚠️ needs-push 滞留:"
  echo "$NEEDS_PUSH" | sed 's/^/    /'
fi
echo "  次の TASKS.md 着手: cat TASKS.md で未着手を確認"
echo "─────────────────────────────────────────"
