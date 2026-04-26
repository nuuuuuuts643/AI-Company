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
| T003 | 中 | **MAX_API_CALLS を 25→35 に再調整**。pending=202件（2026-04-26 03:00時点）。25×4=100件/日では完消化まで2日かかる。35×4=140件/日なら1.5日。トークン削減は維持しつつバックログ消化を加速 | lambda/processor/proc_config.py | 2026-04-26 |
| T004 | 低 | **セッション自動ロール判定の追加**（PO指示）。CLAUDE.md のセッション開始時に「WORKING.mdに何も書かれていない場合はfinderロールで動作する / 書かれている場合は空きタスクを取るimplementerロールで動作する」というルールを追加。人間が毎回ロール指定しなくても自律的に役割を判断できるようにする | CLAUDE.md | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
