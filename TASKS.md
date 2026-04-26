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
| T057 | 中 | **admin.htmlに収益データ表示セクション追加**。忍者AdMax・Amazon/楽天アフィリエイトの収益をリンクカードで一覧表示。AdSense審査通過後も追加できる設計にする | `frontend/admin.html` | 2026-04-26 |
| T058 | 低 | **frontend/ICONS-NEEDED.md を削除**。開発ドキュメントがS3に公開配信されている | `frontend/ICONS-NEEDED.md` | 2026-04-26 |
| T059 | 中 | **auth.jsログインモーダル「@メンション通知」文言を修正**。@メンションは未実装。実装済み特典（履歴・お気に入り）に差し替える | `frontend/js/auth.js` | 2026-04-26 |
| T060 | 低 | **twitter-card.pngを削除（ogp.pngと同一・148KB×2の重複）**。全HTMLのtwitter:imageは既にogp.pngを参照済みなので削除のみでOK | `frontend/twitter-card.png` | 2026-04-26 |
| T061 | 中 | **manifest.json PWAショートカット「急上昇」が機能しない**。app.jsが`?filter=rising`URLパラメータを解析していない。初期化時に`?filter`を読んでcurrentStatusにセットする | `frontend/app.js` | 2026-04-26 |
| T063 | 低 | **CLAUDE.md肥大化対策**。「次フェーズのタスク」セクションの`~~完了済み~~`15件を削除。「Amazonアソシエイト申請（PO手動）」など完了済み手動タスクの記述を整理。480行→350行目安 | `CLAUDE.md` | 2026-04-26 |
| T064 | 低 | **config.jsのAmazon/もしもアフィリエイトコメント修正**。`// 例: 'flotopic-22'`など設定済みなのに「例：」と書いてある誤解を招くコメントを削除 | `frontend/config.js` | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
