# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 未着手（実装待ち）

取得手順: `git pull --rebase && cat TASKS.md` で確認後、WORKING.md に宣言して着手。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T019 | 中 | **SES本番アクセス申請後のLambda環境変数設定**（PO手動） | — | 2026-04-26 |
| T121 | 高 | **catchup.htmlのダークテーマ固定を修正** — ライトモードで使っているユーザーがリワインドページを開くと突然ダーク画面になりテーマが統一されない。根本原因: catchup.htmlのカスタムCSSがハードコードのダーク色（`#1a1f3a`, `#0f1629`, `#1e2540`等）で`[data-theme="dark"]`条件分岐なし。**修正方針**: style.cssの既存CSS変数（`--bg-primary`, `--card-bg`, `--text-primary`等）を確認してからcatchup.htmlのカスタムCSSをCSS変数化 + `[data-theme="dark"]`での暗色上書きパターンに変更。ヒーローセクションのグラデーション背景は両テーマ対応にする。検証: ライト/ダーク両モードで表示確認 | `frontend/catchup.html`, `frontend/style.css`(参照のみ) | 2026-04-26 |
| T122 | 中 | **アフィリエイトウィジェットで「広告」ラベルが2重表示** — topic.htmlの`.affiliate-header`内に`<span class="affiliate-label">広告</span>`があり、さらにaffiliate.jsがlinksEl内に`<p class="affiliate-label">広告</p>`を追加注入するため「広告」が2回表示される。根本原因: affiliate.js line 68の冒頭に重複ラベルを書いてしまっている。**修正方針**: `affiliate.js` line 68の`<p class="affiliate-label">広告</p>`部分を削除するだけ。HTMLのaffiliateヘッダー側の`<span class="affiliate-label">広告</span>`を正として残す。検証: topic.htmlでアフィリエイトセクションが「広告」1回だけ表示されること | `frontend/js/affiliate.js` | 2026-04-26 |
| T123 | 中 | **コメント「いいね取消」がページリロードで元に戻る** — いいね取消（unlike）がDynamoDB側でデクリメントされないため、取消後にリロードするとカウントが元の数に戻る。根本原因: comments.js line 218コメント「DynamoDB側でのデクリメントは今フェーズでは省略（フロントのみ）」。修正方針: unlikeの場合もAPI呼び出しを追加。既存エンドポイント `PUT /comments/like?...&type=unlike` もしくは `DELETE /comments/like?...` を使用（バックエンドがどちらをサポートするか先に`GET /comments/like`のLambdaを確認してから実装）。楽観的UI（即時カウント変更）は維持したままAPIを非同期で呼ぶ | `frontend/js/comments.js`, `lambda/`(API確認要) | 2026-04-26 |
| T056 | 低 | **フォロー/フォロワー機能**（将来・ユーザー増えてから） | — | 2026-04-26 |
| T109 | 低 | **アフィリエイト: トピック内容に合わせた関連商品表示（将来）** — 現状はジャンル固定キーワードで検索。AI要約生成時に商品検索クエリも同時生成してDynamoDBに保存し、トピックページに関連商品として表示できれば収益性向上。AI処理コスト増になるため収益化フェーズで検討 | `lambda/processor/proc_ai.py`, `frontend/js/affiliate.js` | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
