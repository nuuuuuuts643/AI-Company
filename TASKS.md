# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 未着手（実装待ち）

取得手順: `git pull --rebase && cat TASKS.md` で確認後、WORKING.md に宣言して着手。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T019 | 中 | **SES本番アクセス申請後のLambda環境変数設定**（ナオヤ手動） | — | 2026-04-26 |
| T056 | 低 | **フォロー/フォロワー機能**（将来・ユーザー増えてから） | — | 2026-04-26 |
| T109 | 低 | **アフィリエイト: トピック内容に合わせた関連商品表示（将来）** — 現状はジャンル固定キーワードで検索。AI要約生成時に商品検索クエリも同時生成してDynamoDBに保存し、トピックページに関連商品として表示できれば収益性向上。AI処理コスト増になるため収益化フェーズで検討 | `lambda/processor/proc_ai.py`, `frontend/js/affiliate.js` | 2026-04-26 |
| T112 | 高 | **リワインド: フィルター基準をfirstArticleAtに変更** — 現状は`lastUpdated >= cutoff`（最終更新日）で判定しているため、fetcherが4回/日走る環境ではほぼ全アクティブトピックが通過し「ホームと同じ」状態になる。`firstArticleAt * 1000 >= cutoff`（トピック誕生日）に変更して「選んだ期間内に生まれた新着トピック」を表示する。ソートのtiebreaker も`lastUpdated`→`firstArticleAt` DESCに変更。ヒーロー説明文「あなたが離れていた間のニュースを…」→「この期間内に初めて出現したトピックをお届けします」に更新。※グリッド2列CSSは本finder sessionで既にcatchup.htmlに適用済み。 | `frontend/catchup.html` | 2026-04-26 |
| T113 | 高 | **カテゴリー分類の精度向上** — Google NewsのRSSフィードはクエリジャンルと無関係な記事を混入させる（例: テクノロジークエリに政治ニュース）。ユーザーがジャンルフィルターを使うと明らかに違うジャンルの記事が表示され信頼を失う。fetcher側で`dominant_genres()`の前段にタイトルキーワードベースのジャンル上書きルールを追加する。例: 「株価」「日経平均」「円高」→強制的に「株・金融」、「首相」「国会」「選挙」→「政治」。`filters.py`または`text_utils.py`に`override_genre_by_title(title)`を実装し`handler.py`のarticle生成後に適用する。 | `lambda/fetcher/filters.py`, `lambda/fetcher/handler.py` | 2026-04-26 |
| T114 | 中 | **ホームのAI要約なしトピックにバッジ表示** — AI要約がないトピックがホームに表示されたとき「処理中」バッジを付けてユーザーに「これは準備中」と伝える。現状は0.80xペナルティで順位を下げるだけで見た目に差がなく「壊れてる？」と思われる。`frontend/app.js`のカード描画部分で`t.generatedSummary`が無い場合に`<span class="badge-processing">処理中</span>`を追加し、CSSで控えめに表示する。 | `frontend/app.js`, `frontend/style.css` or `index.html` 内style | 2026-04-26 |
| T115 | 低 | **velocityスコアの表示をラベル化** — ホーム・リワインドの「velocity 23」は一般ユーザーに意味不明。数値を非表示にして「🔥 急上昇」「📈 上昇中」「→ 通常」など3段階ラベルに置き換える。閾値: velocity>30→急上昇、>10→上昇中、それ以外→表示なし。catchup.htmlの`buildVelocityBar()`とapp.jsの同等ロジックを修正。 | `frontend/catchup.html`, `frontend/app.js` | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
