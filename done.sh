#!/bin/bash
# タスク完了処理スクリプト（冪等）
# 使い方: bash done.sh T028
# 何度実行しても同じ結果になる

TASK_ID=${1:?タスクIDを指定してください（例: bash done.sh T028）}

cd /Users/OWNER/ai-company

echo "=== ${TASK_ID} 完了処理開始 ==="

# 最新を取得
git pull --rebase origin main 2>/dev/null || echo "pull failed, continuing"

# WORKING.md と TASKS.md から該当行を削除
sed -i '' "/${TASK_ID}/d" WORKING.md
sed -i '' "/| ${TASK_ID} /d" TASKS.md

# 削除後の状態確認
echo ""
echo "--- WORKING.md 現在着手中 ---"
awk '/## 現在着手中/{p=1} p' WORKING.md | grep "^|" | grep -v "タスク名" || echo "（なし）"

echo ""
echo "--- TASKS.md 残タスク ---"
grep "^| T" TASKS.md || echo "（なし）"

# コミット＆プッシュ
git add WORKING.md TASKS.md
git commit -m "done: ${TASK_ID} 管理ファイル更新" 2>/dev/null || echo "nothing to commit"
git push 2>/dev/null || echo "push failed"

echo ""
echo "✅ ${TASK_ID} 完了。HISTORY.mdへの詳細記録を忘れずに。"
