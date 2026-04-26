# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 未着手（実装待ち）

取得手順: `git pull --rebase && cat TASKS.md` で確認後、WORKING.md に宣言して着手。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T019 | 中 | **SES本番アクセス申請後のLambda環境変数設定**（PO手動） | — | 2026-04-26 |
| T126 | 中 | **トピックページのChart.jsグラフがダークモードで文字・グリッド不可視** — `detail.js`のChart.js設定がグリッド線に`rgba(0,0,0,.06)`（黒の薄い透明）を使用し、ティック/ラベルはChart.js 4デフォルトの`#666`（ダークグレー）のまま。ダークモード時にチャート背景が暗色になるため、グリッド線とラベルがほぼ不可視になる。根本原因: `detail.js` line 368の`grid.color`と、Chart.jsのデフォルトfontColor(`#666`)がライトモード専用。**修正方針**: `buildCharts()`の先頭で`const isDark = document.documentElement.getAttribute('data-theme') === 'dark'`を判定し、①グリッド線: `isDark ? 'rgba(255,255,255,.12)' : 'rgba(0,0,0,.06)'`、②ティック色: `Chart.defaults.color = isDark ? '#9ba3c4' : '#666'`（buildCharts呼び出し前に設定、呼び出し後にリセット）、③テーマ切替時の再描画: `data-theme`属性変更を`MutationObserver`で監視して`buildCharts(currentRange)`を再実行。検証: ダークモードでtopic.htmlを開きグラフのメモリ・グリッドが視認できること | `frontend/detail.js` | 2026-04-26 |
| T127 | 中 | **contact.htmlのフォームがダークモード未対応** — theme.js追加後（T124）、フォーム要素（form container, input, textarea, select, submit button, success message）がすべてハードコードの白背景・黒テキスト（`background:#fff; color:#1e293b; border:1px solid #d1d5db`等）のため、ダークモード使用時に白いフォームが暗いページに浮く。**修正方針**: contact.htmlのカスタムCSSに`[data-theme="dark"]`オーバーライドを追加: フォームcontainer→`background:var(--surface)`, input/textarea/select→`background:var(--surface2); border-color:var(--border); color:var(--text-primary)`, 送信ボタンは既に暗色で問題なし, success message→`background:rgba(34,197,94,0.1); border-color:rgba(34,197,94,0.3); color:#4ade80`。検証: ダークモードでcontact.htmlを開きフォーム全体が暗色で表示されること | `frontend/contact.html` | 2026-04-26 |
| T128 | 低 | **terms.html・privacy.htmlのテキスト色がダークモードで不視認** — `.privacy-container p`と`ul`が`color:#374151`（暗いグレー）で固定されており、ダークモード時に暗背景（#13141f）上でほぼ見えなくなる。同一の問題が2ファイルに存在。**修正方針**: 両ファイルのカスタムCSSに`[data-theme="dark"] .privacy-container p, [data-theme="dark"] .privacy-container ul { color: var(--text-secondary); } [data-theme="dark"] .privacy-container h2 { color: var(--text-primary); } [data-theme="dark"] .privacy-container .updated { color: var(--text-muted); }`を追加。検証: ダークモードで両ページのテキストが読めること | `frontend/terms.html`, `frontend/privacy.html` | 2026-04-26 |
| T056 | 低 | **フォロー/フォロワー機能**（将来・ユーザー増えてから） | — | 2026-04-26 |
| T109 | 低 | **アフィリエイト: トピック内容に合わせた関連商品表示（将来）** — 現状はジャンル固定キーワードで検索。AI要約生成時に商品検索クエリも同時生成してDynamoDBに保存し、トピックページに関連商品として表示できれば収益性向上。AI処理コスト増になるため収益化フェーズで検討 | `lambda/processor/proc_ai.py`, `frontend/js/affiliate.js` | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
