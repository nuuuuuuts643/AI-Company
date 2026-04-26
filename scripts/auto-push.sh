#!/bin/bash
# auto-push.sh
# ai-companyフォルダの変更を検知して自動git push

REPO_DIR="$HOME/ai-company"
LOG="$HOME/ai-company/logs/auto-push.log"
LOCK="/tmp/auto-push.lock"

mkdir -p "$HOME/ai-company/logs"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG"
}

push_changes() {
  # 多重実行防止
  if [ -f "$LOCK" ]; then
    return
  fi
  touch "$LOCK"

  cd "$REPO_DIR" || exit 1

  # 変更があるか確認
  if git diff --quiet && git diff --staged --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
    rm -f "$LOCK"
    return
  fi

  # .claude/ の一時ファイルは除外
  git add -A -- ':!.claude/scheduled_tasks.lock' ':!**/*.lock' ':!**/function.zip' 2>/dev/null

  # ステージング済みの変更があれば commit + push
  if ! git diff --staged --quiet; then
    CHANGED=$(git diff --staged --name-only | head -5 | tr '\n' ' ')
    git commit -m "auto: $CHANGED$(date '+%H:%M')" >> "$LOG" 2>&1

    # pull --rebase でコンフリクト防止してからpush
    git pull --rebase origin main >> "$LOG" 2>&1 || {
      log "⚠️ rebase失敗 - abort して再試行待ち"
      git rebase --abort 2>/dev/null
      rm -f "$LOCK"
      return
    }
    git push origin main >> "$LOG" 2>&1 && log "✅ push完了: $CHANGED" || log "❌ push失敗"
  fi

  rm -f "$LOCK"
}

log "🚀 auto-push 起動 (監視: $REPO_DIR)"

# fswatch でフォルダ変更を監視
# 変更後3秒待ってからpush（連続変更をまとめる）
fswatch -o \
  --exclude '\.git/' \
  --exclude '\.lock$' \
  --exclude 'function\.zip$' \
  --exclude 'node_modules/' \
  "$REPO_DIR" | while read -r count; do
    sleep 3
    push_changes
done
