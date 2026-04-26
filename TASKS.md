# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 未着手（実装待ち）

取得手順: `git pull --rebase && cat TASKS.md` で確認後、WORKING.md に宣言して着手。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T019 | 中 | **SES本番アクセス申請後のLambda環境変数設定**（PO手動） | — | 2026-04-26 |
| T131 | 中 | **storymap.html 二重フッター削除** — Line 252-254 に旧フッター（プライバシーリンク1本のみ）が残存。Line 600 の `<footer class="site-footer">` が正規。ユーザーにフッターが2回表示される。根本原因: site-footer 追加時に旧フッターが削除されなかった。修正: 旧フッター3行（Line 252-254）を削除する。 | `frontend/storymap.html` | 2026-04-26 |
| T132 | 低 | **storymap.html ブランチカードのエンティティタグ dark mode 未対応** — `renderBranchCard()` Line 393 で `background:#eff6ff;color:#2563eb;` をハードコード。ダークモード背景（`#13141f`）上でライトブルー背景が浮いて視覚ノイズになる。修正: inline style を CSS クラス `.sm-entity-tag` に移動し `[data-theme="dark"] .sm-entity-tag { background:rgba(37,99,235,.18); color:#93c5fd; }` を追加。 | `frontend/storymap.html` | 2026-04-26 |
| T056 | 低 | **フォロー/フォロワー機能**（将来・ユーザー増えてから） | — | 2026-04-26 |
| T109 | 低 | **アフィリエイト: トピック内容に合わせた関連商品表示（将来）** — 現状はジャンル固定キーワードで検索。AI要約生成時に商品検索クエリも同時生成してDynamoDBに保存し、トピックページに関連商品として表示できれば収益性向上。AI処理コスト増になるため収益化フェーズで検討 | `lambda/processor/proc_ai.py`, `frontend/js/affiliate.js` | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
