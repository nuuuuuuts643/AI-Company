# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 未着手（実装待ち）

取得手順: `git pull --rebase && cat TASKS.md` で確認後、WORKING.md に宣言して着手。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T019 | 中 | **SES本番アクセス申請後のLambda環境変数設定**。AWSコンソール → Lambda `p003-contact` → 環境変数 → `TO_EMAIL` に受信メールアドレスを設定。SES本番承認後に実施（PO手動） | — | 2026-04-26 |
| T029 | 高 | **mypage.htmlに広告追加（残作業）**。legacy.html・catchup.htmlは実装済み。mypage.htmlのみ未対応。shinobiスクリプトとad-728-scale-wrapper（728×90 PC用 + 320×50 SP用）を追加 | frontend/mypage.html | 2026-04-26 |
| T031 | 低 | **ファイル分割・保守性向上**。app.js(大)・detail.js(大)が肥大化。広告・アフィリエイト・通知・履歴など機能別にjsファイルを分割し、将来の拡張・テストを容易にする。実装時に段階的に分割 | frontend/app.js, detail.js | 2026-04-26 |
| T032 | 高 | **CLAUDE.md棚卸し（コンテキスト軽量化）**。P003技術状態スナップショットテーブルが200行超で肥大化。完了済みコンポーネント行をHISTORY.mdへ移動し、現在も変動中の行のみ残す。セッション品質向上・コンテキスト窓の節約が目的 | CLAUDE.md, HISTORY.md | 2026-04-26 |
| T033 | 高 | **SEO対策: AIタイトルのロングテールキーワード改善**。現在のAIタイトルは「〇〇が△△」形式が多い。検索意図に合わせ「〇〇とは」「〇〇の経緯・背景」「〇〇まとめ」形式のタイトルを生成するようプロンプト改修。proc_ai.py の generate_title プロンプトを更新 | lambda/processor/proc_ai.py | 2026-04-26 |
| T034 | 中 | **SEO対策: 内部リンク強化（関連トピック表示改善）**。topic.htmlの「関連トピック」セクションに表示件数が少ない・リンクが目立たない問題。関連トピック4件→6件に増やし、リンクのクリック誘導UIを改善（サムネイル+タイトル+経過時間表示） | frontend/detail.js, style.css | 2026-04-26 |
| T035 | 高 | **天気ウィジェット→急上昇ジャンル表示に置き換え**。天気はFlotopicと無関係。id="weather-widget"エリアを「🔥 今日は〇〇が急上昇（+N件）」の1行表示に変更。topics.jsonのジャンル別velocity最大値を集計するだけ。未ログインでも表示OK | frontend/app.js, style.css | 2026-04-26 |
| T036 | 高 | **閲覧済みカードの視覚化**。localStorageにflotopic_historyがあるのにカード一覧で既読/未読の区別が付かない。既読トピックのカードにopacity:0.65程度のグレーオーバーレイを適用。loadPrefsのhistoryデータを使うだけでAPI不要 | frontend/app.js, style.css | 2026-04-26 |
| T037 | 高 | **ログイン特典を明示するモーダル改善**。未ログイン時にお気に入りボタンを押すと現状ただログインを促すだけ。「ログインするとできること: ①お気に入り保存 ②閲覧履歴をどのデバイスでも同期 ③続報通知」の3点を具体的に示すモーダルに改善 | frontend/js/auth.js | 2026-04-26 |
| T038 | 中 | **ジャンル設定クラウド同期**。ジャンルフィルター設定が現在localStorageのみ。ログインユーザーはDynamoDB flotopic-favoritesのPK=userId/SK=PREFS#genreに保存、ログイン時に復元。✅完了条件: 別ブラウザ/デバイスでログインしたとき同じジャンル選択が復元されること | frontend/app.js, frontend/js/favorites.js, lambda/favorites/handler.py | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
