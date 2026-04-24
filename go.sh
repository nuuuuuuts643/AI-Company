#!/bin/bash
# Flotopic 一発デプロイスクリプト
set -e

cd /Users/murakaminaoya/ai-company

echo "🔄 git sync..."
rm -f .git/index.lock
git add -A
git commit -m "chore: sync $(date '+%Y-%m-%d %H:%M')" || echo "nothing to commit"
git push || echo "push failed, continuing"

echo "🚀 deploying..."
bash projects/P003-news-timeline/deploy.sh

echo "✅ 完了"
