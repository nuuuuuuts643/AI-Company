# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 未着手（実装待ち）

取得手順: `git pull --rebase && cat TASKS.md` で確認後、WORKING.md に宣言して着手。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T019 | 中 | **SES本番アクセス申請後のLambda環境変数設定**。AWSコンソール → Lambda `p003-contact` → 環境変数 → `TO_EMAIL` に受信メールアドレスを設定。SES本番承認後に実施（ナオヤ手動） | — | 2026-04-26 |
| T021 | 高 | **fetcher実行時間削減（384秒→目標60秒）**。T017のO(n²)修正後も384秒かかっている。RSSフェッチの並列化（asyncio/concurrent.futures）またはDynamoDBバッチ書き込み最適化が必要。CloudWatchで各フェーズのタイムスタンプを追加して真のボトルネックを特定すること | lambda/fetcher/handler.py | 2026-04-26 |
| T022 | 中 | **モバイル広告（忍者AdMax）表示調査・修正**。スマホでtopic.htmlを開いても728×90広告が見えない。CSS scale(0.44)は正しいが広告スクリプト自体がモバイルで未配信の可能性あり。320×50のモバイル用広告枠を別途追加することを検討 | frontend/topic.html, frontend/style.css | 2026-04-26 |
| T023 | 中 | **UIコピー改善**。ボトムナビの「ふりかえり」など平凡な言葉をよりクールな表現に変更。対象ファイル: contact.html・legacy.html・privacy.html・catchup.html（「ふりかえり」→「クロニクル」「軌跡」「経緯」等を検討）。catchup.htmlのヒーロー文言も含めて全体的に見直す | frontend/contact.html, legacy.html, privacy.html, catchup.html | 2026-04-26 |
| T024 | 中 | **閲覧履歴クラウド同期**。現在はlocalStorage（20件上限）のみで端末をまたいで消える。Googleログイン済みユーザーはDynamoDB（flotopic-favorites と同テーブルまたは専用テーブル）に保存・復元する。favorites Lambdaと同様の実装パターンで対応可能 | lambda/favorites/handler.py, frontend/app.js, frontend/mypage.html | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
