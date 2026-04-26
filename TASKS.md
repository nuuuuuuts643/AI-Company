# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 未着手（実装待ち）

取得手順: `git pull --rebase && cat TASKS.md` で確認後、WORKING.md に宣言して着手。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T019 | 中 | **SES本番アクセス申請後のLambda環境変数設定**（ナオヤ手動） | — | 2026-04-26 |
| T053 | 中 | **CloudFlare Analytics設定（ナオヤ手動）**。cf-analytics LambdaにCF_API_TOKEN・CF_ACCOUNT_IDを設定するとadmin PVグラフが動く。手順: ①Cloudflare→My Profile→API Tokens→Create Token（Analytics:Read権限）②AWS Lambda `flotopic-cf-analytics` の環境変数に`CF_API_TOKEN`と`CF_ACCOUNT_ID`を追加（アカウントIDはCloudflareダッシュボードURLの/accounts/以降） | — | 2026-04-26 |
| T056 | 低 | **フォロー/フォロワー機能**（将来・ユーザー増えてから） | — | 2026-04-26 |
| T057 | 中 | **admin.htmlに収益データ表示セクション追加**。現在adminに収益が見えない。忍者AdMax・Amazon/楽天アフィリエイトの収益をiframe埋め込みまたはリンクカードで一覧表示。AdSense審査通過後も追加できる設計にする | `frontend/admin.html` | 2026-04-26 |
| T058 | 低 | **ICONS-NEEDED.md を frontend/ から削除**。開発ドキュメントがS3に公開配信されている。削除後sw.jsのキャッシュリストにないため問題なし | `frontend/ICONS-NEEDED.md` | 2026-04-26 |
| T059 | 中 | **auth.js 未実装Web Push文言の修正**。ログインモーダルに「🔔 急上昇・続報の通知を受け取る」表示があるがWeb Pushは未実装。文言を「お気に入りの同期・閲覧履歴の引き継ぎ」に変更する。完了条件: 実装していない機能を約束する文言が消える | `frontend/js/auth.js` | 2026-04-26 |
| T060 | 低 | **twitter-card.pngはogp.pngと同一ファイル（MD5一致）**。同じ148KBのファイルが2つ存在。twitter-card.pngを削除しOGP metaタグでogp.pngを使うよう統一。全HTMLのmeta twitter:imageをogp.pngに統一確認すること | `frontend/twitter-card.png`, 全HTML | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
