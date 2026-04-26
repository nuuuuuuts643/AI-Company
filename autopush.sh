#!/bin/bash
# autopush.sh — ローカルコミットを自動でGitHubにpushする
# launchd から30分ごとに呼ばれる

REPO="/Users/OWNER/ai-company"
LOG="$REPO/autopush.log"

cd "$REPO" || exit 1

# pushするコミットがなければ何もしない
UNPUSHED=$(git log origin/main..HEAD --oneline 2>/dev/null | wc -l | tr -d ' ')

if [ "$UNPUSHED" -eq 0 ]; then
  exit 0
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') pushing $UNPUSHED commit(s)..." >> "$LOG"

# rebaseしてからpush（他セッションのコミットと整合）
git pull --rebase origin main >> "$LOG" 2>&1
git push origin main >> "$LOG" 2>&1

if [ $? -eq 0 ]; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') push OK" >> "$LOG"
else
  echo "$(date '+%Y-%m-%d %H:%M:%S') push FAILED (will retry in 30min)" >> "$LOG"
fi

# ログが1000行超えたら古い行を削除
tail -500 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
