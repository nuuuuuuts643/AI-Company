# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 未着手（実装待ち）

取得手順: `git pull --rebase && cat TASKS.md` で確認後、WORKING.md に宣言して着手。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T004 | 低 | **セッション自動ロール判定の追加**（ナオヤ指示）。CLAUDE.md のセッション開始時に「WORKING.mdに何も書かれていない場合はfinderロールで動作する / 書かれている場合は空きタスクを取るimplementerロールで動作する」というルールを追加。人間が毎回ロール指定しなくても自律的に役割を判断できるようにする | CLAUDE.md | 2026-04-26 |
| T008 | 中 | **長期停滞トピックのarchived化**: 30日以上前 かつ velocityScore=0 のトピック5件がlifecycleStatus=activeのまま（北朝鮮ミサイル362日, 原発新興235日など）。lifecycle Lambda の閾値か fetcher の compute_lifecycle_status を修正して自動archived化 | lambda/fetcher/score_utils.py または lambda/lifecycle/handler.py | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
