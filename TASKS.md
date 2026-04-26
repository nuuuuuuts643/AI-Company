# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 未着手（実装待ち）

取得手順: `git pull --rebase && cat TASKS.md` で確認後、WORKING.md に宣言して着手。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T008 | 中 | **長期停滞トピックのarchived化**。velocityScore=0 かつ 30日以上 active のトピックを lifecycle で archived にする。ARCHIVE_DAYS 調整または score_utils.py に停滞判定追加 | lambda/lifecycle/handler.py または lambda/fetcher/score_utils.py | 2026-04-26 |
| T010 | 高 | **tokushoho.html を再リダイレクト化**。commit 56e1be6 が廃止済みページを完全版に復活させた。noindex リダイレクトに戻す。再発防止のため CLAUDE.md に明記 | frontend/tokushoho.html, CLAUDE.md | 2026-04-26 |
| T011 | 高 | **`get_topic_detail()` 無制限クエリ修正**。`table.query()` の Limit なし全件読み込みを `get_item(META)` + `query(Limit=30,ScanIndexForward=False)` の2ステップに変更。DynamoDB読み取りコストを月$10超→大幅削減 | lambda/fetcher/storage.py | 2026-04-26 |
| T012 | 中 | **S3 topic ファイル書き込みを差分のみに変更**。processor が毎回 ~324件を無条件 PUT → ETag(MD5)比較で変更なしはスキップ。月 $1.98 のS3書き込みコスト削減 | lambda/processor/proc_storage.py | 2026-04-26 |
| T013 | 高 | **Bluesky エージェント3問題修正**。①DynamoDB フルスキャン→S3 topics.json読み取りに変更（月$2.5削減）②velocityScore の `int()` → `float()` キャスト修正（Decimal精度損失でトピック選定崩壊）③投稿リンクが空表示になる問題→S3 api/topic/{id}.json 存在確認してなければスキップ | scripts/bluesky_agent.py | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
