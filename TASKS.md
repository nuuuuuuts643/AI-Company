# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 未着手（実装待ち）

取得手順: `git pull --rebase && cat TASKS.md` で確認後、WORKING.md に宣言して着手。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T149 | 高 | **AI要約なし新着トピックがカードに「処理中」バッジなしで上位表示されUX低下** — 根本原因: `renderTopicCard()` が `pendingAI=true` または `aiGenerated=false && !generatedSummary` のトピックに対して特別なUI表示をしない。影響: 速報トピックが要約なしのまま上位に来てユーザーが内容を読めず「壊れている」と感じる。修正方法: `app.js` の `renderTopicCard()` でカードに「🤖 AI分析中...」バッジを追加（`pendingAI=true` または `!meta.aiGenerated && !meta.generatedSummary` の場合）。詳細ページでは T146 が修正対応。ランキング変更は行わない（速報を隠すと本末転倒）。 | `frontend/app.js`, `frontend/style.css` | 2026-04-26 |
| T150 | 高 | **初回訪問時のonboardingがなくサービスの価値が1秒で伝わらない** — 根本原因: index.html の hero テキストが `「今話題になっていること、まるごとわかる。」` のみで、AIがニュースを分析して何が面白いのかが不明。初回ユーザーはトピックカードの意味（記事N件・スコア・ストーリーフェーズ）が分からないまま離脱する可能性が高い。修正方法: (1) ページ上部に「AIがニュースをまとめ・トレンドを可視化」などの副見出しを追加 (2) トピックカードの「スコア」「記事N件」「フェーズバッジ」に初回のみ表示するツールチップ or 簡易説明テキストを追加。localStorage で「説明表示済み」フラグを管理。 | `frontend/index.html`, `frontend/app.js`, `frontend/style.css` | 2026-04-26 |
| T146 | 高 | **旧summaryトピック103件がdetailページで「AI分析を生成中」を誤表示** — 根本原因: `detail.js:219` の `const hasSummary = summary && meta.aiGenerated` が `aiGenerated=None/False` のトピック（旧extractive summary保有）をブロック。影響: カードでsummaryが見えるのにdetailページでは「⏳ AI分析を生成中」が表示される（21%のトピックで発生、特にarticleCount平均6.4件の活発トピック）。修正方法: `hasSummary` 条件を `!!summary` に変更し、`isFullAI = summary && meta.aiGenerated` を別変数にして summaryMode 分岐を調整。`aiGenerated=False` でも `generatedSummary` があれば summaryMode='minimal' で表示する。バグ再発防止ルール確認: フォールバックではなくDynamoDB既存データの表示改善。違反なし。 | `frontend/detail.js` | 2026-04-26 |
| T056 | 低 | **フォロー/フォロワー機能**（将来・ユーザー増えてから） | — | 2026-04-26 |
| T109 | 低 | **アフィリエイト: トピック内容に合わせた関連商品表示（将来）** — 現状はジャンル固定キーワードで検索。AI要約生成時に商品検索クエリも同時生成してDynamoDBに保存し、トピックページに関連商品として表示できれば収益性向下。AI処理コスト増になるため収益化フェーズで検討 | `lambda/processor/proc_ai.py`, `frontend/js/affiliate.js` | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
