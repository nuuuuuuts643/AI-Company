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
| T139 | 低 | **mypage.html の@メンション通知エリアが暗色モードで白背景ボックス表示** — 根本原因: line 1245 `background:#fafafa`（未読通知行）とline 1248 `background:#f8fafc`（引用テキストボックス）がinline styleのため`[data-theme="dark"]` CSSに勝つ。ログイン済みユーザーが暗色モードで通知を見ると、暗い背景に白いボックスが突出して見づらい。また line 1316 `border:1px solid #e2e8f0` の「履歴を全削除」ボタンも暗色モードでほぼ不可視になる。修正方法: 通知行にCSSクラスを追加（`.notif-item`等）し `[data-theme="dark"] .notif-item { background: var(--bg-card); border-color: var(--border); }` `[data-theme="dark"] .notif-excerpt { background: var(--surface); color: var(--text-secondary); }` `[data-theme="dark"] #clear-history-btn { border-color: var(--border); color: var(--text-muted); }` を定義してinline styleを置き換える | `frontend/mypage.html` | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
