# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 未着手（実装待ち）

取得手順: `git pull --rebase && cat TASKS.md` で確認後、WORKING.md に宣言して着手。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T019 | 中 | **SES本番アクセス申請後のLambda環境変数設定**（ナオヤ手動） | — | 2026-04-26 |
| T056 | 低 | **フォロー/フォロワー機能**（将来・ユーザー増えてから） | — | 2026-04-26 |
| T087 | 高 | **topics.jsonの11件がdetail JSON未存在** 「日経平均6万円突破」「半導体キオクシア」等11件がS3 404。fetcherは`saved_ids∩deduped_tids`のみdetail JSONを書くため、スコア浮上した新規記事なしトピックが永遠に書かれない。詳細ページがタイトルのみ表示になる。修正: processorまたはfetcherでdetail JSON欠損トピックをDynamoDBから補完 | `lambda/processor/proc_storage.py` または `lambda/fetcher/handler.py` | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
