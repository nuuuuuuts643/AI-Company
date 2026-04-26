# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 未着手（実装待ち）

取得手順: `git pull --rebase && cat TASKS.md` で確認後、WORKING.md に宣言して着手。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T019 | 中 | **SES本番アクセス申請後のLambda環境変数設定**（ナオヤ手動） | — | 2026-04-26 |
| T136 | 低 | **index.html・topic.html・mypage.html のヘッダー認証ボタンがダークモード未対応** — 3ファイルのインライン`<style>`が`.auth-user-name { color: #737373 }`・`.auth-btn:hover { background: #f5f5f5 }`をハードコード。style.cssの`var(--text-primary)`より後に来るため上書きされる。ダークモードで①ユーザー名が低コントラスト（#737373 on #13141f ≈ 3.7:1, WCAG AA未満）②hover時に白灰色ボックスが暗い背景に浮く。**修正方針**: 各ファイルのインライン`<style>`末尾に`[data-theme="dark"] .auth-user-name { color: var(--text-secondary); }`と`[data-theme="dark"] .auth-btn:hover { background: rgba(255,255,255,.08); border-color: rgba(255,255,255,.2); }`を追加（3ファイル同じ修正）。検証: ダークモードでログイン状態のヘッダーを確認しユーザー名が読めること、hover時に白ボックスが出ないこと。 | `frontend/index.html`, `frontend/topic.html`, `frontend/mypage.html` | 2026-04-26 |
| T056 | 低 | **フォロー/フォロワー機能**（将来・ユーザー増えてから） | — | 2026-04-26 |
| T109 | 低 | **アフィリエイト: トピック内容に合わせた関連商品表示（将来）** — 現状はジャンル固定キーワードで検索。AI要約生成時に商品検索クエリも同時生成してDynamoDBに保存し、トピックページに関連商品として表示できれば収益性向上。AI処理コスト増になるため収益化フェーズで検討 | `lambda/processor/proc_ai.py`, `frontend/js/affiliate.js` | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
