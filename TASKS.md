# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 未着手（実装待ち）

取得手順: `git pull --rebase && cat TASKS.md` で確認後、WORKING.md に宣言して着手。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T019 | 中 | **SES本番アクセス申請後のLambda環境変数設定**（PO手動） | — | 2026-04-26 |
| T047 | 高 | **「クロニクル/しばらくぶり」→「リワインド」統一 + legacy.html廃止統合**。catchup.html全体・全ナビHTML・about.html・sw.js更新。完了条件: ナビに「リワインド」1本のみ、legacy.htmlがcatchup.htmlに飛ぶ | 全ナビHTML, `frontend/catchup.html`, `frontend/legacy.html`, `frontend/sw.js` | 2026-04-26 |
| T048 | 高 | **ファビコン修正（SVG→PNG優先）**。全10HTMLで`<link rel="icon" type="image/svg+xml" href="/icon-flotopic.svg">`がPNGより前に書かれているためブラウザが青波SVGを使う。SVGリンクを削除してPNG（ドロップロゴ）を使わせる。完了条件: ブラウザタブにdropletアイコンが表示される | 全HTMLファイル（index/catchup/topic/mypage/about/contact/terms/privacy/profile/storymap） | 2026-04-26 |
| T049 | 中 | **ジャンル表記揺れ修正**。DynamoDB内「ファッション・美容」→「ファッション」に一括更新スクリプト実行 | `lambda/processor/` | 2026-04-26 |
| T050 | 中 | **ノイズトピックフィルタリング強化**。fetcherのNGキーワードに「攻略」「レシピ」「料理一覧」等追加。完了条件: topics.jsonにゲーム攻略・レシピ系トピックが出なくなる | `lambda/fetcher/config.py` | 2026-04-26 |
| T053 | 中 | **CloudFlare Analytics設定（PO手動）**。cf-analytics LambdaにCF_API_TOKEN・CF_ACCOUNT_IDを設定するとadmin PVグラフが動く。手順: ①Cloudflare→My Profile→API Tokens→Create Token（Analytics:Read権限）②AWS Lambda `flotopic-cf-analytics` の環境変数に`CF_API_TOKEN`と`CF_ACCOUNT_ID`を追加（アカウントIDはCloudflareダッシュボードURLの/accounts/以降） | — | 2026-04-26 |
| T054 | 中 | **Admin「AI要約100%」誤表示修正**。`admin.html`L348の`aiDone`計算が`generatedSummary \|\| generatedTitle`になっているためタイトルだけで100%になる。`generatedSummary`単体でカウントするよう修正 | `frontend/admin.html` | 2026-04-26 |
| T055 | 低 | **storyTimeline detail画面表示確認と実装**。DynamoDB・個別topic JSONに保存済みだがフロントで表示されているか未確認 | `frontend/topic.html` | 2026-04-26 |
| T056 | 低 | **フォロー/フォロワー機能**（将来・ユーザー増えてから） | — | 2026-04-26 |
| T057 | 中 | **admin.htmlに収益データ表示セクション追加**。現在adminに収益が見えない。忍者AdMax・Amazon/楽天アフィリエイトの収益をiframe埋め込みまたはリンクカードで一覧表示。AdSense審査通過後も追加できる設計にする | `frontend/admin.html` | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
