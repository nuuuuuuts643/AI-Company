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

### 🎯 使いたくなるUX（「また来たい」動線）

> 安定性改善と並行して進める。Flotopicの差別化はストーリー追跡体験にある。それが伝わる動線を作る。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T154 | 中 | **お気に入りトピックへの新展開をWeb Push通知** — 根本原因: お気に入り登録しても次の展開を見に戻る動機がない。修正方法: ServiceWorkerにWeb Push受信を追加。fetcherが既存お気に入りtidへの新記事を検知→DynamoDB notification_queueに積む→Lambda(notifier)が1日2回処理。ユーザー増加後の優先施策。 | `frontend/sw.js`, `frontend/mypage.html`, 新Lambda | 2026-04-26 |
| T176 | 高 | **モバイルUI崩れ調査・修正** — ユーザー報告: z-index修正(f9777be)後もスマホUIが壊れている。根本原因: 未特定。調査ポイント: ①hero-story-preview/onboarding-card/keyword-stripなど直近追加要素がモバイルレイアウトに与える影響 ②overflow-x漏れによる横スクロール発生の有無 ③実機スクショ取得して具体的崩れ箇所を特定。修正方法: 崩れ箇所特定後に最小限CSS修正。 | `frontend/style.css`, `frontend/index.html` | 2026-04-27 |
| T177 | 中 | **admin.html 新ジャンル対応** — グルメ・ファッション・美容ジャンルを追加したが admin.html のジャンル別集計が旧リストのまま。修正方法: admin.html のジャンル一覧を config.js の GENRES と同期させる。 | `frontend/admin.html` | 2026-04-27 |
| T179 | 中 | **グラフと記事数の不一致** — ユーザー報告URL: topic.html?id=4eecff3f2245992b。根本原因: グラフはDynamoDB SNAPテーブルの articleCount（過去スナップショット）を使い、カード表示の「記事N件」はtopics.jsonの articleCount（最新）を使う。lifecycleがSNAPを削除しても topics.json の値は独立して更新されるため両者がずれる。調査: SNAPの最新エントリと topics.json の articleCount を比較。修正方法: グラフの最終データポイント値がtopics.jsonのarticleCountと乖離する場合、topics.jsonの値でグラフの最終点を上書き補正するか、ラベルに「現在N件」を別表示する。 | `frontend/detail.js` | 2026-04-27 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
