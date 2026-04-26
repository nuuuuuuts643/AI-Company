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
| T137 | 低 | **contact.html「メディア・報道機関の方へ」ボックスが暗色モードで黄色表示される** — 根本原因: line 237の `style="border-color:#fde68a;background:#fffbeb;"` inline styleが `[data-theme="dark"] .info-section` CSSルール（特定性0,1,1,0）に勝つ（inline=1,0,0,0）。修正方法: `class="info-section info-section-notice"` を追加してCSS側に `.info-section-notice { border-color:#fde68a; background:#fffbeb; }` + `[data-theme="dark"] .info-section-notice { background: var(--bg-card); border-color: var(--border); }` でinline styleを削除する | `frontend/contact.html` | 2026-04-26 |
| T138 | 低 | **storymap.html のステータスバッジ(.sm-status-badge.active/.cooling)に暗色モードオーバーライドなし** — 根本原因: lines 85-86 `.sm-status-badge.active { background: #dcfce7; color: #16a34a; }` `.sm-status-badge.cooling { background: #fef3c7; color: #92400e; }` にダークモード対応なし。暗色テーマ時に明るい緑・琥珀色バッジが背景と対比し見苦しい。修正: `[data-theme="dark"] .sm-status-badge.active { background: rgba(34,197,94,.15); color: #4ade80; }` `[data-theme="dark"] .sm-status-badge.cooling { background: rgba(245,158,11,.15); color: #fbbf24; }` を追加 | `frontend/storymap.html` | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
