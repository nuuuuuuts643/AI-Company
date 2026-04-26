# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 未着手（実装待ち）

取得手順: `git pull --rebase && cat TASKS.md` で確認後、WORKING.md に宣言して着手。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T017 | 高 | **fetcher Lambda O(n²)処理を削減（実行時間229秒→目標60秒）**。`handler.py` L433 `[:1000]`→`[:500]`。`detect_topic_hierarchy()`（L330）をinverted-index方式に変換（`find_related_topics`は実装済み） | lambda/fetcher/handler.py, lambda/fetcher/text_utils.py | 2026-04-26 |
| T019 | 中 | **SES本番アクセス申請後のLambda環境変数設定**。AWSコンソール → Lambda `p003-contact` → 環境変数 → `TO_EMAIL` に受信メールアドレスを設定。SES本番承認後に実施（ナオヤ手動） | — | 2026-04-26 |
| T020 | 中 | **Amazon/楽天アフィリエイト申請**（ナオヤ手動）。申請後 `config.js` の `AFFILIATE_AMAZON_TAG`・`AFFILIATE_RAKUTEN_ID` に設定するだけで即稼働 | — | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
