# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 未着手（実装待ち）

取得手順: `git pull --rebase && cat TASKS.md` で確認後、WORKING.md に宣言して着手。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T019 | 中 | **SES本番アクセス申請後のLambda環境変数設定**（PO手動） | — | 2026-04-26 |
| T053 | 中 | **CloudFlare Analytics設定（PO手動）**。cf-analytics LambdaにCF_API_TOKEN・CF_ACCOUNT_IDを設定するとadmin PVグラフが動く。手順: ①Cloudflare→My Profile→API Tokens→Create Token（Analytics:Read権限）②AWS Lambda `flotopic-cf-analytics` の環境変数に`CF_API_TOKEN`と`CF_ACCOUNT_ID`を追加（アカウントIDはCloudflareダッシュボードURLの/accounts/以降） | — | 2026-04-26 |
| T056 | 低 | **フォロー/フォロワー機能**（将来・ユーザー増えてから） | — | 2026-04-26 |
| T057 | 中 | **admin.htmlに収益データ表示追加**。忍者AdMax/Amazon/楽天のダッシュボードリンクカード一覧。AdSense審査通過後も拡張可 | `frontend/admin.html` | 2026-04-26 |
| T058 | 低 | **frontend/ICONS-NEEDED.md削除**。開発ドキュメントがS3公開配信中 | `frontend/ICONS-NEEDED.md` | 2026-04-26 |
| T059 | 中 | **auth.jsログインモーダルの「@メンション通知」文言修正**。未実装機能を約束している。実装済み特典（履歴/お気に入り）に差し替える | `frontend/js/auth.js` | 2026-04-26 |
| T060 | 低 | **twitter-card.pngをogp.pngに統合**。完全に同一ファイル(MD5一致・各148KB)。twitter-card.pngを削除してディスク/転送コスト削減 | `frontend/twitter-card.png` | 2026-04-26 |
| T061 | 中 | **manifest.json PWAショートカット`/?filter=rising`を修正**。app.jsが`?filter`URLパラメータを解析していないためPWAショートカットが機能しない | `frontend/app.js` | 2026-04-26 |
| T063 | 低 | **CLAUDE.md肥大化対策**。「次フェーズのタスク」セクションの`~~完了済み~~`15件を削除。480行→350行目安 | `CLAUDE.md` | 2026-04-26 |
| T064 | 低 | **config.jsのAmazon/もしもアフィリエイトコメント修正**。`// 例: 'flotopic-22'`など設定済みなのに「例：」と書いてある誤解を招くコメントを削除 | `frontend/config.js` | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
