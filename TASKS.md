# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 未着手（実装待ち）

取得手順: `git pull --rebase && cat TASKS.md` で確認後、WORKING.md に宣言して着手。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T014 | 中 | **processor 4x/day → 2x/day に削減（コスト削減）**。cron(0 22,3,9,15 \* \* ? \*) → cron(0 22,10 \* \* ? \*)（JST 7:00/19:00）に変更。Claude API 月$1.2節約。`aws events put-rule --name p003-processor-schedule --schedule-expression "cron(0 22,10 * * ? *)" --region ap-northeast-1` で更新 | AWS EventBridge（deploy.sh 参考のみ） | 2026-04-26 |
| T015 | 高 | **アフィリエイト広告表示義務（景品表示法）リーガル対応**。Amazon等追加時に必須。①topic.htmlのウィジェット枠に「広告」表記追加②privacy.htmlにアフィリエイト参加旨を記載③tokushoho.htmlの `[TODO: 氏名を記入]` をナオヤが記入（本名必要・Claude不可）。①②はClaude実施可 | frontend/topic.html, frontend/privacy.html | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
