# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 未着手（実装待ち）

取得手順: `git pull --rebase && cat TASKS.md` で確認後、WORKING.md に宣言して着手。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T001 | 高 | **fetcher: save_seen_articles の二重呼び出し修正**。handler.py:221 で処理前に保存→クラッシュ時に記事が再処理されない。221行目を削除し619行目（処理完了後）だけ残す | lambda/fetcher/handler.py | 2026-04-26 |
| T002 | 中 | **topics.json サイズ削減: generatedSummary を120文字に切り詰め**。現状 183KB=31%。カード表示はcleanSummary()で切り詰めて表示するのでフル不要。詳細ページはapi/topic/{id}.jsonから取得済み。fetcher/processor両方の topics.json 書き出し時に [:120] 切り詰めを追加 | lambda/fetcher/handler.py, lambda/processor/handler.py | 2026-04-26 |
| ~~T003~~ | ~~中~~ | ~~MAX_API_CALLS 25→35~~  **完了済み**（別セッションが実装） | — | 2026-04-26 |
| T004 | 低 | **セッション自動ロール判定の追加**（ナオヤ指示）。CLAUDE.md のセッション開始時に「WORKING.mdに何も書かれていない場合はfinderロールで動作する / 書かれている場合は空きタスクを取るimplementerロールで動作する」というルールを追加。人間が毎回ロール指定しなくても自律的に役割を判断できるようにする | CLAUDE.md | 2026-04-26 |

| T005 | 高 | **モバイル広告CSS修正**: `transform: scale(0.44) translateX(-50%)` + `margin-left:50%` の組み合わせで广告が左にはみ出す。left edge = 187.5 - 364 = -176.5px（画面外）。`transform-origin: top center` + flexboxセンタリングに変更（`display:flex;justify-content:center` on wrapper、ad要素に `transform:scale(0.44);transform-origin:top center;flex-shrink:0`）| frontend/style.css | 2026-04-26 |
| T006 | 高 | **同一イベント重複クラスタリング問題**: トランプ晩餐会銃撃事件が6トピックに分裂（「銃撃事件」「大きな音」「発砲」「晩餐会」など表現違いで別クラスタ）。cluster_utils.py の topic_fingerprint / cluster 関数でイベント同一性判定を強化する。類義語マッチングかJaccard閾値の調整 | lambda/fetcher/cluster_utils.py | 2026-04-26 |
| T007 | 中 | **AIサマリーに文脈説明を追加（ナオヤ指摘）**: 「スターリンク」等のカタカナ固有名詞が前提知識なしに登場して読者が混乱。proc_ai.py の各プロンプトに「固有名詞・企業名・サービス名は初出時に1文で説明を加える（例: スターリンク（SpaceXの衛星インターネットサービス）が〜）」ルールを追加 | lambda/processor/proc_ai.py | 2026-04-26 |
| T008 | 中 | **長期停滞トピックのarchived化**: 30日以上前 かつ velocityScore=0 のトピック5件がlifecycleStatus=activeのまま（北朝鮮ミサイル362日, 原発新興235日など）。lifecycle Lambda の閾値か fetcher の compute_lifecycle_status を修正して自動archived化 | lambda/fetcher/score_utils.py または lambda/lifecycle/handler.py | 2026-04-26 |
| T009 | 中 | **ランキング・アフィリエイト記事フィルタ強化**: 「おすすめ人気ランキング」「徹底比較」「買ったら辛かった」等のブログ/広告記事が3件混入。fetcher/filters.py の `_DIGEST_SKIP_PATS` に `r'おすすめ.*ランキング'` `r'徹底比較'` `r'買ったら辛'` を追加 | lambda/fetcher/filters.py | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
