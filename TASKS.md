# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 未着手（実装待ち）

取得手順: `git pull --rebase && cat TASKS.md` で確認後、WORKING.md に宣言して着手。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T019 | 中 | **SES本番アクセス申請後のLambda環境変数設定**。AWSコンソール → Lambda `p003-contact` → 環境変数 → `TO_EMAIL` に受信メールアドレスを設定。SES本番承認後に実施（PO手動） | — | 2026-04-26 |
| T027 | 高 | **モバイル専用広告枠追加（320×50）**。admax-id=`570fe6c87677ba7c5417119c60ca979d`取得済み。index.html・topic.htmlにモバイル専用スロット追加、既存728×90は`@media(min-width:768px)`のみ表示に変更。shinobiスクリプトはページ1回のみ読み込む点に注意 | frontend/index.html, topic.html, style.css | 2026-04-26 |
| T028 | 高 | **グルメ・ファッションをGENRESフィルターに追加**。fetcher config.pyにはグルメ(6フィード)・ファッション(5フィード)があるがapp.jsのGENRESリストに未追加。フィルターUIに表示されずトピックが埋もれている。app.js L72とlegacy.htmlのGENRESに2ジャンル追加するだけ | frontend/app.js, legacy.html | 2026-04-26 |
| T029 | 中 | **legacy.html・catchup.html・mypage.htmlに広告追加**。現在admax広告はindex.html・topic.htmlのみで他3ページは広告ゼロ。shinobiスクリプトとad-728-scale-wrapperを追加。実装時はファイル分割・保守性を意識（広告コンポーネントをjsで共通化も検討）| frontend/legacy.html, catchup.html, mypage.html | 2026-04-26 |
| T030 | 中 | **トレンド可視化強化**。「どれが流行か分かりにくい」課題。velocityスコアをカードに視覚表示（バー・色・サイズ差）し一目でトレンドが分かるUIに改善。既存の🔥ストリップを補完する形で実装 | frontend/app.js, style.css | 2026-04-26 |
| T031 | 低 | **ファイル分割・保守性向上**。app.js(大)・detail.js(大)が肥大化。広告・アフィリエイト・通知・履歴など機能別にjsファイルを分割し、将来の拡張・テストを容易にする。実装時に段階的に分割 | frontend/app.js, detail.js | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
