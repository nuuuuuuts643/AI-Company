#!/bin/bash
# .claude/worktrees/ 配下の stale worktree を検出・削除する。
# 用途: session_bootstrap.sh から --dry-run で呼び出す（自動削除はしない）。
#       手動メンテで `bash scripts/cleanup_stale_worktrees.sh` 実行で削除。
#
# stale 判定:
#   1. worktree が `.claude/worktrees/` 配下である（main worktree は対象外）
#   2. WORKING.md に worktree 名 / ブランチ名を含む `[Code]` エントリが無い
#   3. worktree の最終活動時刻（git admin dir + worktree dir の mtime の最大値）
#      が現在から 8 時間以上前
#
# 削除挙動:
#   - uncommitted changes があるツリーは skip して報告（force 削除はしない）
#   - 削除は `git worktree remove --force <path>`（worktree のみ削除、ブランチは残る）
#   - 削除した worktree 名は `[CLEANUP_WORKTREE] removed: <name>` としてログ出力
#
# フラグ:
#   --dry-run : 削除せず一覧のみ表示

set -u

DRY_RUN=0
case " $* " in *" --dry-run "*) DRY_RUN=1 ;; esac

REPO="${REPO:-}"
if [ -z "$REPO" ]; then
  GIT_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel 2>/dev/null || true)"
  # 現在地が worktree の場合、common dir 経由で main worktree のパスを取得する
  if [ -n "$GIT_ROOT" ]; then
    COMMON_DIR="$(git -C "$GIT_ROOT" rev-parse --git-common-dir 2>/dev/null || true)"
    if [ -n "$COMMON_DIR" ]; then
      MAIN_WT="$(cd "$COMMON_DIR/.." 2>/dev/null && pwd)"
      [ -n "$MAIN_WT" ] && [ -d "$MAIN_WT" ] && REPO="$MAIN_WT"
    fi
  fi
  [ -z "$REPO" ] && [ -d "$HOME/ai-company" ] && REPO="$HOME/ai-company"
fi
[ -d "$REPO" ] || { echo "❌ repo not found (REPO=$REPO)"; exit 1; }
# canonical path に揃える（macOS の /tmp ↔ /private/tmp 等の symlink 差異吸収）
REPO="$(cd "$REPO" && pwd -P)"

WORKTREES_DIR="$REPO/.claude/worktrees"
WORKING_MD="$REPO/WORKING.md"

if [ ! -d "$WORKTREES_DIR" ]; then
  exit 0
fi

if [ ! -f "$WORKING_MD" ]; then
  echo "⚠️ WORKING.md not found at $WORKING_MD; aborting (safety guard)" >&2
  exit 1
fi

NOW=$(date +%s)
THRESHOLD=$((NOW - 8 * 3600))

# 自身が動いている worktree は絶対に削除しない（safety guard）
SELF_PATH=""
SELF_GIT_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel 2>/dev/null || true)"
case "$SELF_GIT_ROOT" in
  "$WORKTREES_DIR"/*) SELF_PATH="$SELF_GIT_ROOT" ;;
esac

# stat の OS 差異 (BSD: -f %m / GNU: -c %Y) を吸収
_mtime() {
  stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null || echo 0
}

# worktree の最終活動時刻（epoch）を取得
# git admin dir (.git/worktrees/<name>/{HEAD,index,logs/HEAD}) と
# worktree dir 自体の mtime の最大値を返す
_latest_activity() {
  local wpath="$1"
  local wname
  wname="$(basename "$wpath")"
  local admin_dir="$REPO/.git/worktrees/$wname"
  local latest=0 m
  if [ -d "$admin_dir" ]; then
    for f in "$admin_dir/HEAD" "$admin_dir/index" "$admin_dir/logs/HEAD"; do
      [ -f "$f" ] || continue
      m=$(_mtime "$f")
      [ "$m" -gt "$latest" ] 2>/dev/null && latest=$m
    done
  fi
  if [ -d "$wpath" ]; then
    m=$(_mtime "$wpath")
    [ "$m" -gt "$latest" ] 2>/dev/null && latest=$m
  fi
  echo "$latest"
}

removed=0
skipped=0
kept=0

# --porcelain 出力をパース。worktree / branch 行を組にして処理する
# 一時ファイル経由で while ループのスコープ問題を回避
TMP_LIST=$(mktemp)
trap 'rm -f "$TMP_LIST"' EXIT

git worktree list --porcelain 2>/dev/null | awk '
  /^worktree / { wpath=substr($0, 10); wbranch="" }
  /^branch /   { wbranch=substr($0, 8) }
  /^detached/  { wbranch="(detached)" }
  /^$/         { if (wpath) print wpath "|" wbranch; wpath="" }
  END          { if (wpath) print wpath "|" wbranch }
' > "$TMP_LIST"

while IFS='|' read -r wpath wbranch; do
  [ -z "$wpath" ] && continue
  case "$wpath" in
    "$WORKTREES_DIR"/*) ;;
    *) continue ;;  # main worktree など対象外
  esac

  wname="$(basename "$wpath")"
  wbranch_short="${wbranch#refs/heads/}"

  # 自分自身は絶対に削除しない
  if [ -n "$SELF_PATH" ] && [ "$wpath" = "$SELF_PATH" ]; then
    kept=$((kept + 1))
    continue
  fi

  # WORKING.md に worktree 名 / ブランチ名を含む [Code] 行があれば skip（active 扱い）
  if grep -F "$wname" "$WORKING_MD" 2>/dev/null | grep -q '\[Code\]'; then
    kept=$((kept + 1))
    continue
  fi
  if [ -n "$wbranch_short" ] && [ "$wbranch_short" != "(detached)" ]; then
    if grep -F "$wbranch_short" "$WORKING_MD" 2>/dev/null | grep -q '\[Code\]'; then
      kept=$((kept + 1))
      continue
    fi
  fi

  latest=$(_latest_activity "$wpath")
  if [ "$latest" -gt "$THRESHOLD" ] 2>/dev/null; then
    kept=$((kept + 1))
    continue
  fi

  # uncommitted changes チェック（safety: force 削除で work を失わない）
  # NOTE: `git status` は index の lazy stat refresh で index mtime を書き換えてしまうため、
  # 次回起動時の mtime ベース stale 判定が常に false になる side-effect がある。
  # diff-index + ls-files で代替する（これらは index 不変 — 検証済み）。
  if [ -d "$wpath" ]; then
    dirty=""
    git -C "$wpath" diff-index --quiet HEAD -- 2>/dev/null || dirty="modified"
    if [ -z "$dirty" ]; then
      if [ -n "$(git -C "$wpath" ls-files --others --exclude-standard 2>/dev/null | head -1)" ]; then
        dirty="untracked"
      fi
    fi
    if [ -n "$dirty" ]; then
      echo "[CLEANUP_WORKTREE] skip (uncommitted: $dirty): $wname (branch: $wbranch_short)"
      skipped=$((skipped + 1))
      continue
    fi
  fi

  if [ "$DRY_RUN" = "1" ]; then
    echo "[CLEANUP_WORKTREE] would remove: $wname (branch: $wbranch_short)"
    removed=$((removed + 1))
  else
    if git -C "$REPO" worktree remove --force "$wpath" 2>/dev/null; then
      echo "[CLEANUP_WORKTREE] removed: $wname (branch: $wbranch_short, kept)"
      removed=$((removed + 1))
    else
      echo "[CLEANUP_WORKTREE] failed: $wname (branch: $wbranch_short)"
      skipped=$((skipped + 1))
    fi
  fi
done < "$TMP_LIST"

if [ "$DRY_RUN" = "1" ]; then
  echo "[CLEANUP_WORKTREE] summary (dry-run): would-remove=$removed skipped=$skipped kept=$kept"
else
  echo "[CLEANUP_WORKTREE] summary: removed=$removed skipped=$skipped kept=$kept"
fi
exit 0
