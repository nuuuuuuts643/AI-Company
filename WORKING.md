# 着手中タスク（複数セッション間の作業競合管理）

> **このファイルのみで管理する。CLAUDE.md の「現在着手中」セクションは廃止。**
> タスク開始・完了のたびに即 `git add WORKING.md && git commit -m "wip/done: ..." && git push` する。

---

## ⚠️ セッション種別ルール（2026-04-27 追加）

このファイルは **Claude Code（Mac/CLI）と Cowork（スマホ/デスクトップアプリ）の両方が書き込む**。

- **Claude Code** が起動時に `cat WORKING.md` をチェックする際、Cowork の行も同様に衝突判定すること
- **Cowork** もタスク開始時にこのファイルに書き込み、完了時に削除する
- 種別は `[種別]` プレフィックスで区別する

| 種別プレフィックス | 意味 |
|---|---|
| `[Code]` | Claude Code タスク（コードタスク、CLI） |
| `[Cowork]` | Cowork セッション（スマホ・デスクトップアプリ） |

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

| タスク名 | 種別 | 変更予定ファイル | 開始 JST |
|---|---|---|---|
| [Code] T021 fetcher高速化 | Code | lambda/fetcher/handler.py | 2026-04-26 14:00 |
| [Cowork] サイト価値可視化 | Cowork | frontend/index.html, frontend/js/app.js | 2026-04-27 15:00 |

---

## 現在着手中

| タスク名 | 種別 | 変更予定ファイル | 開始 JST |
|---|---|---|---|
| [Code] 作業1 processor手動invoke + 作業2 T213 pending queue優先度修正 | Code | lambda/processor/proc_ai.py | 2026-04-27 19:30 |
| [Cowork] T211 [2] uniqueSourceCount>=2フィルタ強化 | Cowork | projects/P003-news-timeline/lambda/fetcher/handler.py | 2026-04-27 19:35 |
