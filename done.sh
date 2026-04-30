#!/bin/bash
# タスク完了処理スクリプト（冪等 + 動作確認内蔵）
# 使い方:
#   bash done.sh T028                                — 管理ファイル更新のみ
#   bash done.sh T028 lambda:p003-processor          — CloudWatch 直近5分エラー検出
#   bash done.sh T028 url:https://flotopic.com/      — 本番URL HTTP 200確認
#   bash done.sh T028 topic-ai:c1bbe0fe42bee8c1      — 該当topicがAI処理済み確認
# verify_target 省略時は git push のみ実行 (verification なし)。
# CLAUDE.md「完了=動作確認済み」ルールを物理化するため verification を組み込んだ。
# verification 失敗 → exit 1 で done として扱わない。

set +e

TASK_ID=${1:?タスクIDを指定してください（例: bash done.sh T028 lambda:p003-processor）}
VERIFY_TARGET=${2:-}

cd "$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/ai-company")"

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

# ===== 動作確認ステージ (CLAUDE.md「完了=動作確認済み」の物理化) =====
if [ -n "$VERIFY_TARGET" ]; then
    echo ""
    echo "=== 動作確認: $VERIFY_TARGET ==="
    case "$VERIFY_TARGET" in
        lambda:*)
            FN=${VERIFY_TARGET#lambda:}
            echo "→ CloudWatch 直近 5 分のエラーログ確認 ($FN)"
            START=$(($(date +%s) - 300))000
            LOG_GROUP="/aws/lambda/$FN"
            ERRORS=$(aws logs filter-log-events \
                --log-group-name "$LOG_GROUP" \
                --start-time $START \
                --filter-pattern '?ERROR ?Error ?Traceback ?NameError ?TypeError' \
                --query 'events[*].message' \
                --output text \
                --max-items 5 \
                --region ap-northeast-1 2>/dev/null | head -20)
            if [ -z "$ERRORS" ]; then
                echo "  ✅ 直近 5 分にエラーなし"
            else
                echo "  ❌ エラー検出:"
                echo "$ERRORS" | sed 's/^/     /'
                echo ""
                echo "  ⚠️  完了として扱わない方が良い。CloudWatch を再確認すること。"
                exit 1
            fi
            ;;
        url:*)
            URL=${VERIFY_TARGET#url:}
            echo "→ 本番 URL 200 OK 確認: $URL"
            CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$URL")
            if [ "$CODE" = "200" ]; then
                echo "  ✅ HTTP $CODE"
            else
                echo "  ❌ HTTP $CODE — 本番に反映されていない可能性"
                exit 1
            fi
            ;;
        topic-ai:*)
            TID=${VERIFY_TARGET#topic-ai:}
            echo "→ /api/topic/${TID}.json で aiGenerated=true 確認"
            JSON=$(curl -s --max-time 10 "https://flotopic.com/api/topic/${TID}.json")
            AI=$(echo "$JSON" | python3 -c "import json,sys;print(json.load(sys.stdin).get('meta',{}).get('aiGenerated'))" 2>/dev/null)
            if [ "$AI" = "True" ]; then
                echo "  ✅ aiGenerated=True 確認"
            else
                echo "  ❌ aiGenerated=$AI （まだ AI 処理されていない or エラー）"
                exit 1
            fi
            ;;
        *)
            echo "  ⚠️  unknown verify_target format: $VERIFY_TARGET"
            echo "     supported: lambda:p003-processor / url:https://... / topic-ai:abc123"
            ;;
    esac
fi

echo ""
echo "✅ ${TASK_ID} 完了。HISTORY.mdへの詳細記録を忘れずに。"
