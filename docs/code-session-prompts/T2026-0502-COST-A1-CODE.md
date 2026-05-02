# Code セッション起動 prompt: T2026-0502-COST-A1-CODE

> 用途: Cowork デスクトップから Code セッションを起動する際にコピペで使う。
> 関連: docs/cost-reduction-plan-2026-05-02.md §8、TASKS.md T2026-0502-COST-A1 / -A1-CODE
> 推奨モデル: **Sonnet** (1 PR 完結・deploy.sh 編集 + 後続の AWS delete 操作)
> 想定所要: 30 分

---

## prompt 本文 (これを Code セッションに渡す)

```
TASKS.md の T2026-0502-COST-A1-CODE を読んで実装してください。

## 目的

未使用 DynamoDB テーブル 4 個 (ai-company-memory / ai-company-x-posts / ai-company-agent-status / ai-company-audit) の運用整理。
※ Cowork セッション (2026-05-02 21:18 JST) で describe-table 検証済み。3 個は Items=0 or 微小、audit は ResourceNotFoundException。

## 罠の存在

projects/P003-news-timeline/deploy.sh L69-80 が毎 deploy で ai-company-agent-status を create-table している。
**deploy.sh を先に修正しないと、delete-table 後の次回 deploy で復活する**。

## 手順

1. 現在 main 同期 + 新 branch 切る
   git checkout main && git pull --rebase origin main
   git checkout -b chore/T2026-0502-COST-A1-CODE

2. projects/P003-news-timeline/deploy.sh の以下を編集:
   - L69-80 の `# ---- 1c. DynamoDB (エージェントステータス) ----` ブロック全体を削除
   - L156 の IAM policy Resource 配列から 4 ARN を削除:
     - arn:aws:dynamodb:ap-northeast-1:${ACCOUNT_ID}:table/ai-company-memory
     - arn:aws:dynamodb:ap-northeast-1:${ACCOUNT_ID}:table/ai-company-x-posts
     - arn:aws:dynamodb:ap-northeast-1:${ACCOUNT_ID}:table/ai-company-agent-status
     - arn:aws:dynamodb:ap-northeast-1:${ACCOUNT_ID}:table/ai-company-audit
   - **注意**: arn:aws:dynamodb:ap-northeast-1:${ACCOUNT_ID}:table/ai-company-bluesky-posts は **残す** (稼働中)

3. ローカルで構文チェック
   bash -n projects/P003-news-timeline/deploy.sh

4. WORKING.md に [Code] 行を追記して push
   | [Code] T2026-0502-COST-A1-CODE deploy.sh 整理 | Code | projects/P003-news-timeline/deploy.sh | <開始JST> | yes |

5. commit + PR
   git add projects/P003-news-timeline/deploy.sh WORKING.md
   git commit -m "chore: T2026-0502-COST-A1-CODE 未使用 DynamoDB 4 個の deploy.sh 整理

ai-company-{memory,x-posts,agent-status,audit} を deploy.sh から削除:
- L69-80 の agent-status create-table ブロック削除
- L156 IAM policy Resource 配列から 4 ARN 削除
ai-company-bluesky-posts は維持。

事前検証 (Cowork 2026-05-02 21:18 JST):
- memory: 2 items / 353 bytes (微小)
- x-posts: 0 items
- agent-status: 0 items (deploy.sh が毎回作る罠)
- audit: 既に存在しない (NotFound)

Verified-Effect-Pending: deploy 実行 + 手動 delete-table 後 24h で
3 テーブル全て describe-table が ResourceNotFoundException 返すこと
Eval-Due: 2026-05-09"
   git push -u origin HEAD
   gh pr create --fill

6. PR auto-merge & deploy 完了を確認 (gh run list --workflow=deploy-lambdas.yml --limit=1 が success)

7. **慎重に** 実 delete-table を実行 (1 つずつ確認しながら):
   aws dynamodb delete-table --table-name ai-company-memory --region ap-northeast-1
   aws dynamodb describe-table --table-name ai-company-memory --region ap-northeast-1
   # → ResourceNotFoundException を確認したら次へ

   aws dynamodb delete-table --table-name ai-company-x-posts --region ap-northeast-1
   aws dynamodb describe-table --table-name ai-company-x-posts --region ap-northeast-1

   aws dynamodb delete-table --table-name ai-company-agent-status --region ap-northeast-1
   aws dynamodb describe-table --table-name ai-company-agent-status --region ap-northeast-1

   # ai-company-audit は既に存在しないので skip

8. WORKING.md から自分の行を削除
9. done.sh T2026-0502-COST-A1-CODE で完了処理 (Verified-Effect 行付き)
10. HISTORY.md に記録 + TASKS.md の T2026-0502-COST-A1-CODE を取消線

## 完了条件

- deploy.sh L69-80 ブロック削除済 + IAM policy 4 ARN 削除済 (PR merge 済)
- 3 テーブル describe-table が ResourceNotFoundException
- WORKING.md / TASKS.md 反映済

## 注意

- agent-status は今日 (2026-05-02) 10:32 JST に再作成された痕跡あり。delete 前に必ず deploy.sh 修正を merge して deploy 完了確認すること
- bluesky-posts は **稼働中**。誤削除しないこと
- 削除実行は 1 テーブルずつ確認しながら。バッチ処理しない
```

---

## チェックリスト (Code セッション完了報告に含めるもの)

- [ ] PR URL
- [ ] CI green 確認 (gh run list)
- [ ] deploy.sh 編集差分 (-1c. DynamoDB ブロック削除 / -4 ARN)
- [ ] delete-table 3 回の実行ログ (memory / x-posts / agent-status)
- [ ] describe-table での NotFound 確認結果
- [ ] WORKING.md / TASKS.md / HISTORY.md 更新差分
