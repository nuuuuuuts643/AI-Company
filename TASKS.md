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
| T141 | 低 | **detail.js ヒーロー背景画像がHTTP URLのまま混在コンテンツになる** — 根本原因: `detail.js` line 116 `const safeUrl = meta.imageUrl.replace(/'/g, '%27')` でHTTP→HTTPS変換を省略。`app.js` の `safeImgUrl()` はindex.htmlカードで呼ばれるが topic.html のヒーロー背景には呼ばれていない。フェッチャーが記事OGPからHTTP画像URLを取得した場合、HTTPS上で混在コンテンツブロックにより背景画像が表示されない。修正方法: line 116 を `const safeUrl = (typeof safeImgUrl === 'function' ? safeImgUrl(meta.imageUrl) : meta.imageUrl).replace(/'/g, '%27')` に変更する（app.jsはtopic.htmlでdetail.jsより先に読み込まれる） | `frontend/detail.js` | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
