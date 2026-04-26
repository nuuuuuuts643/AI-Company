# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 未着手（実装待ち）

取得手順: `git pull --rebase && cat TASKS.md` で確認後、WORKING.md に宣言して着手。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T019 | 中 | **SES本番アクセス申請後のLambda環境変数設定**。AWSコンソール → Lambda `p003-contact` → 環境変数 → `TO_EMAIL` に受信メールアドレスを設定。SES本番承認後に実施（ナオヤ手動） | — | 2026-04-26 |
| T040 | 高 | **APIエラーのサイレント黙殺修正**。`loadTopics()`など複数の`fetch()`で`.catch(() => {})`がありネットワークエラーが無視されて空白画面になる。`showErrorBanner()`または`showToast()`でユーザーに通知するようにキャッチポイントを整備 | frontend/app.js | 2026-04-26 |
| T041 | 高 | **フィルター変更時に検索キーワードが残存するバグ修正**。ジャンル・ステータスフィルター変更後にpreviousSearchが保持されたまま絞り込まれる。フィルター変更時に`searchInput.value=''`と`currentSearch=''`をリセットするか、検索+フィルターの組み合わせを正しく処理する | frontend/app.js | 2026-04-26 |
| T042 | 中 | **モバイルキーボード表示時のレイアウト崩れ修正**。CSS `100vh`がモバイル仮想キーボード表示時に変動してbottom-nav・スティッキーCTAバーが隠れる。`height: 100dvh`または`env(keyboard-inset-height)`対応に切り替え | frontend/style.css | 2026-04-26 |
| T043 | 中 | **トップページのOGP動的更新**。index.htmlのog:description等はジャンルフィルター変更時に更新されない。ジャンル変更時に`<meta property="og:description">`をジャンル名・急上昇件数を含む内容に動的書き換え | frontend/index.html, frontend/app.js | 2026-04-26 |
| T044 | 低 | **複数トースト重なり防止**。`toggleFavorite()`や通信エラー時に連打するとトーストが複数スタックして見苦しい。新しいtoast表示前に既存のものをクリアするキューまたはdebounce処理を追加 | frontend/app.js, frontend/style.css | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
