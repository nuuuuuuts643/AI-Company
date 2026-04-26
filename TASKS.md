# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 未着手（実装待ち）

取得手順: `git pull --rebase && cat TASKS.md` で確認後、WORKING.md に宣言して着手。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T019 | 中 | **SES本番アクセス申請後のLambda環境変数設定**。AWSコンソール → Lambda `p003-contact` → 環境変数 → `TO_EMAIL` に受信メールアドレスを設定。SES本番承認後に実施（ナオヤ手動） | — | 2026-04-26 |
| T022 | 中 | **モバイル広告（忍者AdMax）表示調査・修正**。スマホでtopic.htmlを開いても728×90広告が見えない。CSS scale(0.44)は正しいが広告スクリプト自体がモバイルで未配信の可能性あり。320×50のモバイル用広告枠を別途追加することを検討 | frontend/topic.html, frontend/style.css | 2026-04-26 |
| T023 | 中 | **UIコピー改善**。ボトムナビの「ふりかえり」など平凡な言葉をよりクールな表現に変更。対象ファイル: contact.html・legacy.html・privacy.html・catchup.html（「ふりかえり」→「クロニクル」「軌跡」「経緯」等を検討）。catchup.htmlのヒーロー文言も含めて全体的に見直す | frontend/contact.html, legacy.html, privacy.html, catchup.html | 2026-04-26 |
| T024 | 中 | **閲覧履歴クラウド同期**。現在はlocalStorage（20件上限）のみで端末をまたいで消える。Googleログイン済みユーザーはDynamoDB（flotopic-favorites と同テーブルまたは専用テーブル）に保存・復元する。favorites Lambdaと同様の実装パターンで対応可能 | lambda/favorites/handler.py, frontend/app.js, frontend/mypage.html | 2026-04-26 |
| T025 | 高 | **【リーガル】privacy.html アフィリエイト記載更新**。今日もしもアフィリエイト（Yahoo!ショッピング含む）を追加したが、privacy.htmlの「広告・アフィリエイト」セクションにもしもアフィリエイト・Yahoo!ショッピングの記載がない。薬機法・景表法上のリスク回避のため即対応 | frontend/privacy.html | 2026-04-26 |
| T027 | 高 | **モバイル専用広告枠追加（320×50）**。728×90をscale縮小してもAdMaxがモバイルに未配信の可能性。忍者AdMaxダッシュボードで320×50用IDを新規発行後、index.html・topic.htmlにモバイル専用スロットを追加。既存728×90はPC表示のみに限定する | frontend/index.html, topic.html, style.css | 2026-04-26 |
| T028 | 高 | **グルメ・ファッションをGENRESフィルターに追加**。fetcher config.pyにはグルメ(6フィード)・ファッション(5フィード)があるがapp.jsのGENRESリストに未追加。フィルターUIに表示されずトピックが埋もれている。app.js L72とlegacy.htmlのGENRESに2ジャンル追加するだけ | frontend/app.js, legacy.html | 2026-04-26 |
| T029 | 中 | **legacy.html・catchup.html・mypage.htmlに広告追加**。現在admax広告はindex.html・topic.htmlのみで他3ページは広告ゼロ。shinobiスクリプトとad-728-scale-wrapperを追加。実装時はファイル分割・保守性を意識（広告コンポーネントをjsで共通化も検討）| frontend/legacy.html, catchup.html, mypage.html | 2026-04-26 |
| T030 | 中 | **トレンド可視化強化**。「どれが流行か分かりにくい」課題。velocityスコアをカードに視覚表示（バー・色・サイズ差）し一目でトレンドが分かるUIに改善。既存の🔥ストリップを補完する形で実装 | frontend/app.js, style.css | 2026-04-26 |
| T031 | 低 | **ファイル分割・保守性向上**。app.js(大)・detail.js(大)が肥大化。広告・アフィリエイト・通知・履歴など機能別にjsファイルを分割し、将来の拡張・テストを容易にする。実装時に段階的に分割 | frontend/app.js, detail.js | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
