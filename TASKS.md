# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 未着手（実装待ち）

取得手順: `git pull --rebase && cat TASKS.md` で確認後、WORKING.md に宣言して着手。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T019 | 中 | **SES本番アクセス申請後のLambda環境変数設定**（PO手動） | — | 2026-04-26 |
| T045 | 高 | **アバター保存「保存中...」固まりバグ修正**。`uploadAvatarBlob`のfetchにAbortController+30秒タイムアウト追加。catchブロックで必ずsaveBtnをリセット | `frontend/mypage.html` | 2026-04-26 |
| T046 | 高 | **検索時はジャンルフィルターを全ジャンル対象にリセット**。`setupSearch()`のinputハンドラ冒頭で`currentGenre='総合'; buildFilters();`を追加。完了条件: ①ジャンル選択中に検索→全ジャンルから結果が出る ②検索クリア後は総合に戻る | `frontend/app.js` | 2026-04-26 |
| T047 | 高 | **「クロニクル/しばらくぶり」→「リワインド」統一 + legacy.html廃止統合**。①catchup.htmlのタイトル・h1・OGP・JSON-LDをすべて「リワインド」に変更 ②index.htmlのボタン「しばらくぶり？」→「リワインド」に変更 ③legacy.htmlを廃止（catchup.htmlにリダイレクト、noindex設定）④全ページナビの「クロニクル」「アーカイブ(legacy.html)」→「リワインド(catchup.html)」に統一 ⑤about.html・sw.jsのキャッシュリスト・sitemap等も更新。完了条件: ナビに「リワインド」1本のみ存在し、legacy.htmlアクセスでcatchup.htmlに飛ぶ | `frontend/catchup.html`, `frontend/legacy.html`, `frontend/index.html`, 全ナビHTML, `frontend/sw.js` | 2026-04-26 |
| T048 | 中 | **ジャンル表記揺れ修正**。DynamoDB内の`genre`/`genres`フィールドで「ファッション・美容」となっているトピックを「ファッション」に一括更新するワンタイムスクリプトをprocessorかlifecycleに追加して実行。UIのGENRES配列は既に「ファッション」なのでデータ側を合わせる。完了条件: topics.jsonのジャンル一覧に「ファッション・美容」が出なくなる | `lambda/processor/` または `lambda/lifecycle/` | 2026-04-26 |
| T049 | 中 | **ログインモーダルの「🔔 通知」文言修正**。`auth.js` L130「急上昇・続報の通知を受け取る」→「@メンション通知・コメント返信を受け取る」に変更（Web Push未実装なので実態に合わせる） | `frontend/js/auth.js` | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
