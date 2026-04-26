# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 未着手（実装待ち）

取得手順: `git pull --rebase && cat TASKS.md` で確認後、WORKING.md に宣言して着手。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T146 | 高 | **旧summaryトピック103件がdetailページで「AI分析を生成中」を誤表示** — 根本原因: `detail.js:219` の `const hasSummary = summary && meta.aiGenerated` が `aiGenerated=None/False` のトピック（旧extractive summary保有）をブロック。影響: カードでsummaryが見えるのにdetailページでは「⏳ AI分析を生成中」が表示される（21%のトピックで発生、特にarticleCount平均6.4件の活発トピック）。修正方法: `hasSummary` 条件を `!!summary` に変更し、`isFullAI = summary && meta.aiGenerated` を別変数にして summaryMode 分岐を調整。`aiGenerated=False` でも `generatedSummary` があれば summaryMode='minimal' で表示する。バグ再発防止ルール確認: フォールバックではなくDynamoDB既存データの表示改善。違反なし。 | `frontend/detail.js` | 2026-04-26 |
| T056 | 低 | **フォロー/フォロワー機能**（将来・ユーザー増えてから） | — | 2026-04-26 |
| T109 | 低 | **アフィリエイト: トピック内容に合わせた関連商品表示（将来）** — 現状はジャンル固定キーワードで検索。AI要約生成時に商品検索クエリも同時生成してDynamoDBに保存し、トピックページに関連商品として表示できれば収益性向下。AI処理コスト増になるため収益化フェーズで検討 | `lambda/processor/proc_ai.py`, `frontend/js/affiliate.js` | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
