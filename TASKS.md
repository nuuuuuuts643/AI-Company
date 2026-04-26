# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 未着手（実装待ち）

取得手順: `git pull --rebase && cat TASKS.md` で確認後、WORKING.md に宣言して着手。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T014 | 中 | **processor 4x/day → 2x/day に削減（コスト削減）**。cron(0 22,3,9,15 \* \* ? \*) → cron(0 22,10 \* \* ? \*)（JST 7:00/19:00）に変更。Claude API 月$1.2節約。`aws events put-rule --name p003-processor-schedule --schedule-expression "cron(0 22,10 * * ? *)" --region ap-northeast-1` で更新 | AWS EventBridge（deploy.sh 参考のみ） | 2026-04-26 |
| T017 | 高 | **fetcher Lambda O(n²)処理を削減（実行時間229秒→目標60秒）**。`lambda/fetcher/handler.py` L433 の `topics_active = sorted(...)[:1000]` を `[:500]` に変更。さらに `text_utils.py` の `find_related_topics()`（L244）と `detect_topic_hierarchy()`（L311）を inverted-index 方式に変換（単語→トピックリストのdictで O(n·k)に削減）。CloudWatchログで `O(n²)処理対象: 1000件 / 全1987件` / `Duration: 229329.73 ms` を確認済み | lambda/fetcher/handler.py, lambda/fetcher/text_utils.py | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
