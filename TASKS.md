# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 未着手（実装待ち）

取得手順: `git pull --rebase && cat TASKS.md` で確認後、WORKING.md に宣言して着手。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T019 | 中 | **SES本番アクセス申請後のLambda環境変数設定**（PO手動） | — | 2026-04-26 |
| T056 | 低 | **フォロー/フォロワー機能**（将来・ユーザー増えてから） | — | 2026-04-26 |
| T109 | 低 | **アフィリエイト: トピック内容に合わせた関連商品表示（将来）** — 現状はジャンル固定キーワードで検索。AI要約生成時に商品検索クエリも同時生成してDynamoDBに保存し、トピックページに関連商品として表示できれば収益性向上。AI処理コスト増になるため収益化フェーズで検討 | `lambda/processor/proc_ai.py`, `frontend/js/affiliate.js` | 2026-04-26 |
| T115 | 低 | **velocityスコアの表示をラベル化** — ホーム・リワインドの「velocity 23」は一般ユーザーに意味不明。数値を非表示にして「🔥 急上昇」「📈 上昇中」「→ 通常」など3段階ラベルに置き換える。閾値: velocity>30→急上昇、>10→上昇中、それ以外→表示なし。catchup.htmlの`buildVelocityBar()`とapp.jsの同等ロジックを修正。 | `frontend/catchup.html`, `frontend/app.js` | 2026-04-26 |
| T117 | 中 | **リワインドページのリンクが静的HTMLページを開く（SPA機能欠如）** — `catchup.html`の`buildCard()`は`topics/${tid}.html`（静的SEO用HTML）にリンク。ホームは`topic.html?id=xxx`（SPA）にリンクしており、SPAにはお気に入り・コメント・閲覧履歴機能がある。リワインドから遷移するとこれらの機能が使えず体験が劣る。修正: `buildCard()`の`url`を`topic.html?id=${tid}`に変更（静的ページはSEO専用と割り切る）。 | `frontend/catchup.html` | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
