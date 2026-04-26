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
| T204 finder: 次の改善点調査 | — | 2026-04-27 |
