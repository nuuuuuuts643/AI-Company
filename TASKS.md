# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 未着手（実装待ち）

取得手順: `git pull --rebase && cat TASKS.md` で確認後、WORKING.md に宣言して着手。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T019 | 中 | **SES本番アクセス申請後のLambda環境変数設定**（PO手動） | — | 2026-04-26 |
| T123 | 中 | **コメント「いいね取消」がページリロードで元に戻る** — いいね取消（unlike）がDynamoDB側でデクリメントされないため、取消後にリロードするとカウントが元の数に戻る。根本原因: comments.js line 218コメント「DynamoDB側でのデクリメントは今フェーズでは省略（フロントのみ）」。修正方針: unlikeの場合もAPI呼び出しを追加。既存エンドポイント `PUT /comments/like?...&type=unlike` もしくは `DELETE /comments/like?...` を使用（バックエンドがどちらをサポートするか先に`GET /comments/like`のLambdaを確認してから実装）。楽観的UI（即時カウント変更）は維持したままAPIを非同期で呼ぶ | `frontend/js/comments.js`, `lambda/`(API確認要) | 2026-04-26 |
| T124 | 低 | **terms.html / privacy.html / contact.html でダークモードが未適用** — 3ページともtheme.jsを読み込んでいないため`data-theme`属性が設定されず、ダークモード設定のユーザーが見ても常にライトモード表示になる。根本原因: `<head>`にtheme.jsのscriptタグが抜けている（about.htmlは対応済みで比較可能）。**修正方針**: 各ページのstyle.css読み込みの直後に`<script src="js/theme.js"></script>`を1行追加するだけ。検証: 各ページでブラウザのテーマをダークに切り替えて確認 | `frontend/terms.html`, `frontend/privacy.html`, `frontend/contact.html` | 2026-04-26 |
| T125 | 中 | **storymap.htmlのコンテンツカードがダークモード未対応** — storymap.htmlはtheme.jsを読み込んでいて`data-theme`は正しく設定されるが、カスタムCSS内の`.sm-section`（`background:#fff`）・`.sm-branch-card`（`background:#f8fafc; border-color:#e2e8f0`）・`.sm-branch-card-title`（`color:#1e293b`）・`.sm-section-title`（`color:#1e293b`）がハードコード白色のため、ダークモード時に白いカードが浮いて見える。**修正方針**: style.cssの既存CSS変数（`--card-bg`, `--border`, `--text-primary`, `--surface`等）をstorymap.htmlのカスタムCSSに適用。ヒーローセクション（`.sm-hero`）はデザイン上の暗色グラデーションのままでOK。検証: ダークモードでstorymap.htmlを開き、コンテンツカードが適切に暗色表示されること | `frontend/storymap.html`, `frontend/style.css`(参照のみ) | 2026-04-26 |
| T056 | 低 | **フォロー/フォロワー機能**（将来・ユーザー増えてから） | — | 2026-04-26 |
| T109 | 低 | **アフィリエイト: トピック内容に合わせた関連商品表示（将来）** — 現状はジャンル固定キーワードで検索。AI要約生成時に商品検索クエリも同時生成してDynamoDBに保存し、トピックページに関連商品として表示できれば収益性向上。AI処理コスト増になるため収益化フェーズで検討 | `lambda/processor/proc_ai.py`, `frontend/js/affiliate.js` | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
