# Code/Cowork セッション起動 prompt: T2026-0502-COST-A1-DELETE-TABLE

> 用途: A1-CODE (PR #308) merge 後の **不可逆な delete-table 3 件** を実行する後続セッション
> 関連: TASKS.md `T2026-0502-COST-A1-DELETE-TABLE` (🔴 PO 確認 待ち)・HISTORY.md `T2026-0502-COST-A1-CODE` 完了行
> 推奨: **Cowork セッション (AWS MCP)** または PO 手動操作。Code セッションに渡す場合は Sonnet・15 分。
> 不可逆性: **DB drop = 不可逆操作**。CLAUDE.md「不可逆操作は事前確認」適用。実行前に必ず PO 承認を取る。

---

## 前提状態 (2026-05-02 23:05 JST 検証済)

| 項目 | 状態 |
|---|---|
| PR #308 (deploy.sh から create-table + IAM 4 ARN 削除) | ✅ main `d882db49` に merge 済 |
| PR #309 (D1 §9 追記) | ✅ main `9bf13e45` に merge 済 |
| PR #310 (WORKING/HISTORY/TASKS 同期) | ✅ main `31870428` に merge 済 |
| `ai-company-agent-status` | ACTIVE / Items=0 / Created 2026-05-02 10:32 JST (今日朝の旧 deploy で再作成された痕跡) |
| `ai-company-memory` | ACTIVE / Items=2 / SizeBytes=353 (微小) |
| `ai-company-x-posts` | ACTIVE / Items=0 |
| `ai-company-audit` | ResourceNotFoundException ✅ (元から無い) |
| `ai-company-bluesky-posts` | ACTIVE / Items=97 (**稼働中・誤削除厳禁**) |
| Lambda 全 11 関数 LastModified | 2026-05-02 11:25-11:27 UTC = 20:25-20:27 JST (PR #308 merge **前**の値) |

### ⚠️ 想定外の発見 (要記録)

**`deploy-lambdas.yml` は `deploy.sh` 単独変更ではトリガーされない**:
- path filter は `projects/P003-news-timeline/lambda/**` / `scripts/bluesky_agent.py` / `scripts/_governance_check.py` のみ
- PR #308 は `deploy.sh` のみ変更 → deploy 未発火
- **しかし delete-table は安全**: 次回 deploy が走った時には新 deploy.sh を使うので agent-status は再作成されない (再作成リスクゼロ)

---

## prompt 本文 (これをセッションに渡す)

```
TASKS.md の T2026-0502-COST-A1-DELETE-TABLE を読んで実行してください。

## 目的

A1-CODE PR #308 で deploy.sh から削除済の 3 テーブルを実 delete-table で消す。

## 不可逆性 ⚠️

- DB drop は不可逆操作。CLAUDE.md「不可逆操作は事前確認」適用
- 必ず PO 承認を取ってから実行する
- 1 件ずつ削除 → describe-table で NotFound 確認 → 次へ。バッチ禁止
- `ai-company-bluesky-posts` (Items=97 稼働中) は **絶対に触らない**

## 事前確認

1. PR #308 が main に merge 済であること (`git log --oneline origin/main | grep "T2026-0502-COST-A1-CODE"`)
2. main に PR #310 (cleanup) も merge 済であること
3. 現状の 3 テーブル状態確認:
   aws dynamodb describe-table --table-name ai-company-memory --region ap-northeast-1 --query "Table.{Items:ItemCount,Status:TableStatus}"
   aws dynamodb describe-table --table-name ai-company-x-posts --region ap-northeast-1 --query "Table.{Items:ItemCount,Status:TableStatus}"
   aws dynamodb describe-table --table-name ai-company-agent-status --region ap-northeast-1 --query "Table.{Items:ItemCount,Status:TableStatus}"
   → Items が 2026-05-02 検証時 (memory:2 / x-posts:0 / agent-status:0) と乖離してないこと
4. PO に「3 件 delete-table 実行可否」を直接確認

## 実行手順 (1 件ずつ・順番厳守)

### ① ai-company-memory (Items=2 微小データ)

```bash
aws dynamodb delete-table --table-name ai-company-memory --region ap-northeast-1
# → 数十秒待つ (TableStatus=DELETING)
sleep 10
aws dynamodb describe-table --table-name ai-company-memory --region ap-northeast-1
# → ResourceNotFoundException が出ることを確認
```

確認できたら次へ。

### ② ai-company-x-posts (Items=0)

```bash
aws dynamodb delete-table --table-name ai-company-x-posts --region ap-northeast-1
sleep 10
aws dynamodb describe-table --table-name ai-company-x-posts --region ap-northeast-1
```

### ③ ai-company-agent-status (Items=0・deploy.sh の罠は解消済)

```bash
aws dynamodb delete-table --table-name ai-company-agent-status --region ap-northeast-1
sleep 10
aws dynamodb describe-table --table-name ai-company-agent-status --region ap-northeast-1
```

### ④ ai-company-audit (元から無い)

skip。`describe-table` で NotFound であることだけ最終確認。

### ⑤ bluesky-posts 生存確認 (誤削除なし)

```bash
aws dynamodb describe-table --table-name ai-company-bluesky-posts --region ap-northeast-1 --query "Table.{Items:ItemCount,Status:TableStatus}"
# → ACTIVE / Items=97 前後 が維持されていること
```

## 完了処理

1. WORKING.md から自分の行を削除 (もし追記していれば)
2. HISTORY.md に T2026-0502-COST-A1-DELETE-TABLE 完了エントリー追加:
   - 削除実行時刻・各テーブルの最終 Items 数
   - describe-table NotFound の確認ログ
   - bluesky-posts が無事であった事実
   - **Verified-Effect**: 3 テーブル全て NotFound + bluesky-posts ACTIVE/Items=97
3. TASKS.md で T2026-0502-COST-A1-DELETE-TABLE を取消線:
   `~~T2026-0502-COST-A1-DELETE-TABLE~~ ✅ 削除完了 YYYY-MM-DD HH:MM JST → HISTORY.md`
4. T2026-0502-COST-A1-CODE 行も「全 portion 完了」に書き換えて取消線
5. T2026-0502-COST-A1 (親タスク) も完了取消線
6. PR (`chore:` で良い) で WORKING/HISTORY/TASKS の 3 ファイルを 1 PR に統合
   - `Verified-Effect:` 行を commit メッセージに含める (例: `Verified-Effect: 3 tables describe-table = ResourceNotFoundException at YYYY-MM-DDTHH:MM JST. bluesky-posts ACTIVE/Items=97 confirmed.`)

## 副次タスク (発見した穴を埋める)

**T2026-0502-DEPLOY-PATH-FILTER-AUDIT** を起票する:
- deploy-lambdas.yml の path filter に `projects/P003-news-timeline/deploy.sh` が含まれていない
- 結果: deploy.sh 単独変更で deploy が走らない構造的な穴
- **影響**: 「deploy.sh 修正したつもり」が実機に反映されないままになる罠
- 対処候補:
  (a) path filter に `projects/P003-news-timeline/deploy.sh` を追加
  (b) deploy.sh 変更時は手動 workflow_dispatch を運用ルール化
  (c) deploy.sh の create-table/IAM put-role-policy 部分を Lambda コードと同じ trigger にぶら下げる
- Phase-Impact: 1 運用安定 / Eval-Due: 2026-05-09

## 完了条件

- [ ] memory / x-posts / agent-status = ResourceNotFoundException
- [ ] audit = ResourceNotFoundException (skip 確認)
- [ ] bluesky-posts = ACTIVE / Items=97 維持
- [ ] WORKING/HISTORY/TASKS 3 ファイル PR merge 済
- [ ] commit message に `Verified-Effect:` 行あり
- [ ] T2026-0502-DEPLOY-PATH-FILTER-AUDIT 起票済 (副次タスク)
```

---

## チェックリスト (完了報告に含めるもの)

- [ ] PO 承認の証拠 (Slack / 会話記録 / TASKS.md コメント等)
- [ ] 3 回の `delete-table` 実行ログ (CLI 出力 or AWS MCP 結果)
- [ ] 3 回の `describe-table` NotFound 確認ログ
- [ ] bluesky-posts 生存確認ログ (Items=97 ± 数件)
- [ ] HISTORY.md / TASKS.md / WORKING.md 更新差分の PR URL
- [ ] T2026-0502-DEPLOY-PATH-FILTER-AUDIT 起票の TASKS.md 行追加 PR URL

## 引き継ぎメモ (本セッションでの累積知見)

- **PR #308 / #309 / #310 全 main 着地済** (2026-05-02 23:05 JST 確認)
- **A1-CODE deploy.sh portion** = 完了扱い (HISTORY.md 記録済)
- **D1-INVESTIGATE** = 完了 (§9 landing・PR #309)
- **次の D 系候補**: D1-α (`/topics` API S3 直配信化) の実態調査タスク (T2026-0502-COST-D1-α-INVESTIGATE) を別途起票推奨。`docs/cost-reduction-plan-2026-05-02.md` §9.4 の Step 1 (CloudWatch Logs Insights で `/topics` 直撃分析) が次に動かせる小さい一歩
- **本セッションでスキップした項目**: 効果検証実機確認 (本来は完了条件) → 本タスク完了時にカバーする想定
