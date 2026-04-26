# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 未着手（実装待ち）

取得手順: `git pull --rebase && cat TASKS.md` で確認後、WORKING.md に宣言して着手。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T056 | 低 | **フォロー/フォロワー機能**（将来・ユーザー増えてから） | — | 2026-04-26 |
| T109 | 低 | **アフィリエイト: トピック内容に合わせた関連商品表示（将来）** — 現状はジャンル固定キーワードで検索。AI要約生成時に商品検索クエリも同時生成してDynamoDBに保存し、トピックページに関連商品として表示できれば収益性向下。AI処理コスト増になるため収益化フェーズで検討 | `lambda/processor/proc_ai.py`, `frontend/js/affiliate.js` | 2026-04-26 |
| T172 | 低 | **detail.js renderDiscovery: imageUrl を esc() でHTMLエスケープ** — 根本原因: `renderDiscovery()` の `safeThumb` が `src="${safeThumb}"` に直接埋め込まれ `esc()` が未適用（app.js の `renderTopicCard` は `esc(safeImgUrl(t.imageUrl))` と正しくエスケープしている）。実際のimageUrlはS3 URLで実害なしだが一貫性とセキュリティ強化のため修正。修正方法: L739 `safeImgUrl(t.imageUrl)` → `esc(safeImgUrl(t.imageUrl))` に変更。 | `frontend/detail.js` | 2026-04-27 |
| T173 | 低 | **utils.js CONFIG値をapp.jsと同期** — 根本原因: テスト用 `utils.js` の `CONFIG.HOT_STRIP_HOURS: 2` (app.jsは6)・`AD_CARD_INTERVAL: 10` (app.jsは9) が乖離。テストが本番と異なる閾値で通過するためisHotTopic境界テストが不正確。修正方法: utils.js の定数を app.js に合わせ(HOT_STRIP_HOURS:6, AD_CARD_INTERVAL:9)、tests/utils.test.js の検証値も更新。isHotTopic テストは6時間境界に変更。 | `frontend/js/utils.js`, `tests/utils.test.js` | 2026-04-27 |

### 🎯 使いたくなるUX（「また来たい」動線）

> 安定性改善と並行して進める。Flotopicの差別化はストーリー追跡体験にある。それが伝わる動線を作る。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T154 | 中 | **お気に入りトピックへの新展開をWeb Push通知** — 根本原因: お気に入り登録しても次の展開を見に戻る動機がない。修正方法: ServiceWorkerにWeb Push受信を追加。fetcherが既存お気に入りtidへの新記事を検知→DynamoDB notification_queueに積む→Lambda(notifier)が1日2回処理。ユーザー増加後の優先施策。 | `frontend/sw.js`, `frontend/mypage.html`, 新Lambda | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
