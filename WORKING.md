# 着手中タスク（複数セッション間の作業競合管理）

> **このファイルのみで管理する。CLAUDE.md の「現在着手中」セクションは廃止。**
> タスク開始・完了のたびに即 `git add WORKING.md && git commit -m "wip/done: ..." && git push` する。

---

## タスク開始前（毎回必須）

```bash
git pull --rebase origin main
git log --oneline -5 -- CLAUDE.md   # 変更があれば CLAUDE.md を再読してから続行
cat WORKING.md                       # 重複ファイルがあればそのタスクはスキップ
```

重複なし → このファイルに追記 → 即 push して他セッションに宣言する。

## タスク完了後（毎回必須）

```bash
# 1. このファイルから自分の行を削除
# 2. 全変更を commit & push
git add -A && git commit -m "done: [タスク名]" && git push
```

---

## 記入フォーマット

| タスク名 | 変更予定ファイル | 開始 JST |
|---|---|---|
| T021 fetcher高速化 | lambda/fetcher/handler.py | 2026-04-26 14:00 |
| 例: OGP改善 | frontend/detail.js | 2026-04-26 15:00 |

---

## 現在着手中

| タスク名 | 変更予定ファイル | 開始 JST |
|---|---|---|
| T182 CLAUDE.md 原因分析ルール追記 | CLAUDE.md | 2026-04-27 08:45 |
| T176 モバイルUI崩れ修正 | frontend/style.css, frontend/index.html | 2026-04-27 08:00 |
| T177 admin.html ジャンル修正 | frontend/admin.html | 2026-04-27 08:30 |
| T181 comments/favorites topicId検証 | lambda/comments/handler.py, lambda/favorites/handler.py | 2026-04-27 08:30 |
| T172 detail.js imageUrl esc() | projects/P003-news-timeline/frontend/detail.js | 2026-04-27 |
| T173 utils.js CONFIG drift | projects/P003-news-timeline/frontend/js/utils.js, tests/utils.test.js | 2026-04-27 |
| T174 tracker topicId validation | projects/P003-news-timeline/lambda/tracker/handler.py | 2026-04-27 |
