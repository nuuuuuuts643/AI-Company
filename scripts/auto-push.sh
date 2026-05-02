#!/bin/bash
# auto-push.sh
# ai-companyフォルダの変更を検知して自動PR作成 (main 直 push 禁止 — T2026-0502-AUTOPUSH-PR-FLOW)

REPO_DIR="$HOME/ai-company"
LOG="$HOME/ai-company/logs/auto-push.log"
LOCK="/tmp/auto-push.lock"

mkdir -p "$HOME/ai-company/logs"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG"
}

# 共有ドキュメント（docs-only と判定するファイル群）
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
    if [ "$file" = "$doc" ]; then
      return 0
    fi
  done
  return 1
}

has_code_changes() {
  local staged_files
  staged_files=$(git diff --staged --name-only)
  while IFS= read -r file; do
    [ -z "$file" ] && continue
    if ! is_shared_doc "$file"; then
      return 0
    fi
  done <<< "$staged_files"
  return 1
}

working_md_has_code_declaration() {
  grep -q '\[Code\]' "$REPO_DIR/WORKING.md" 2>/dev/null
}

push_changes() {
  # 多重実行防止
  if [ -f "$LOCK" ]; then
    return
  fi
  touch "$LOCK"

  cd "$REPO_DIR" || { rm -f "$LOCK"; return; }

  # 変更があるか確認
  if git diff --quiet && git diff --staged --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
    rm -f "$LOCK"
    return
  fi

  # .claude/ の一時ファイルは除外してステージング
  git add -A -- ':!.claude/scheduled_tasks.lock' ':!**/*.lock' ':!**/function.zip' 2>/dev/null

  # ステージング済みの変更があれば PR 作成へ
  if git diff --staged --quiet; then
    rm -f "$LOCK"
    return
  fi

  # 実コード変更を含む場合は WORKING.md 宣言を確認
  if has_code_changes; then
    if ! working_md_has_code_declaration; then
      log "❌ 実コード変更を検知したが WORKING.md に [Code] 宣言がない → push 拒否"
      log "   変更ファイル: $(git diff --staged --name-only | tr '\n' ' ')"
      log "   対処: WORKING.md に [Code] 行を追加してから再度ファイルを保存してください"
      git reset HEAD 2>/dev/null
      rm -f "$LOCK"
      return
    fi
    log "⚠️ 実コード変更あり (WORKING.md [Code] 宣言確認済)"
  fi

  # ブランチ名生成: auto/<timestamp>-<first-changed-file-slug>
  FIRST_FILE=$(git diff --staged --name-only | head -1)
  SLUG=$(echo "$FIRST_FILE" | sed 's|.*/||; s/[^a-zA-Z0-9]/-/g; s/--*/-/g; s/^-//; s/-$//' | tr '[:upper:]' '[:lower:]' | cut -c1-30)
  TIMESTAMP=$(date '+%Y%m%d-%H%M%S')
  BRANCH="auto/${TIMESTAMP}-${SLUG:-misc}"

  CHANGED=$(git diff --staged --name-only | head -5 | tr '\n' ' ')
  COMMIT_MSG="auto: ${CHANGED}$(date '+%H:%M')"

  log "🔀 PR フロー開始: branch=$BRANCH changed=$CHANGED"

  # feature ブランチを切ってコミット・プッシュ
  if ! git checkout -b "$BRANCH" 2>> "$LOG"; then
    log "❌ branch 作成失敗: $BRANCH"
    git reset HEAD 2>/dev/null
    rm -f "$LOCK"
    return
  fi

  git commit -m "$COMMIT_MSG" >> "$LOG" 2>&1

  if ! git push origin "$BRANCH" >> "$LOG" 2>&1; then
    log "❌ branch push 失敗: $BRANCH"
    git checkout main 2>/dev/null
    git branch -D "$BRANCH" 2>/dev/null
    rm -f "$LOCK"
    return
  fi

  # PR 作成 (auto-merge.yml が CI green 後に squash merge)
  PR_URL=$(gh pr create \
    --title "auto: $CHANGED" \
    --body "auto-push による自動 PR (T2026-0502-AUTOPUSH-PR-FLOW)

変更ファイル:
$(git log -1 --name-only --pretty=format:'' | grep -v '^$' | sed 's/^/- /')" \
    --base main \
    2>> "$LOG")

  if [ $? -eq 0 ]; then
    log "✅ PR 作成: $PR_URL (branch=$BRANCH)"
  else
    log "❌ PR 作成失敗 (branch=$BRANCH)"
  fi

  # main に戻る
  git checkout main >> "$LOG" 2>&1

  rm -f "$LOCK"
}

log "🚀 auto-push 起動 (監視: $REPO_DIR) — PR フローモード"

# fswatch でフォルダ変更を監視
# 変更後3秒待ってからPR作成（連続変更をまとめる）
fswatch -o \
  --exclude '\.git/' \
  --exclude '\.lock$' \
  --exclude 'function\.zip$' \
  --exclude 'node_modules/' \
  "$REPO_DIR" | while read -r count; do
    sleep 3
    push_changes
done
