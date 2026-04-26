# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 未着手（実装待ち）

取得手順: `git pull --rebase && cat TASKS.md` で確認後、WORKING.md に宣言して着手。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T019 | 中 | **SES本番アクセス申請後のLambda環境変数設定**（ナオヤ手動） | — | 2026-04-26 |
| T076 | 高 | **SLACK_WEBHOOK 設定でエラー通知を有効化**（ナオヤ手動） — ①GitHub Secrets に `SLACK_WEBHOOK` を追加（Bluesky・weekly-digest等のGH Actions通知） ②p003-fetcher/processor/lifecycle の Lambda環境変数に `SLACK_WEBHOOK` を追加（スパイク通知・エラー通知）。設定しないとどのコンポーネントが壊れても無音。Slack Incomingウェブフック URL は https://api.slack.com/messaging/webhooks で取得 | — (ナオヤ手動) | 2026-04-26 |
| T077 | 低 | **静的HTMLのJSON-LDに `datePublished`・`author` 追加** — `batch_generate_static_html()` の jsonld生成（proc_storage.py L763-774）に `"datePublished": lastArticleAt のISO文字列` と `"author": {"@type": "Organization", "name": "Flotopic"}` を追加。Article構造化データの補完。Google Search Consoleのリッチリザルト対応に必要 | `lambda/processor/proc_storage.py` | 2026-04-26 |
| T056 | 低 | **フォロー/フォロワー機能**（将来・ユーザー増えてから） | — | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
