# 着手中タスク（複数セッション間の作業競合管理）

> **このファイルのみで管理する。CLAUDE.md の「現在着手中」セクションは廃止。**
> タスク開始・完了のたびに即 `git add WORKING.md && git commit -m "wip/done: ..." && git push` する。

---

## 🟢 Dispatch 継続性 (Cowork コンテキスト引き継ぎ用)

> **目的**: Dispatch のコンテキストが切れても次のセッションが状態を引き継げるよう、
> 現在進行中フェーズ・直近のPO指示・次のアクションを常に最新化する。
> 1 セクション 5 行以内・全部書き換え可。

**現在のフェーズ**: **フェーズ2（AI品質改善）進行中** — T237/T2026-0429-A/T2026-0428-Q Code セッション稼働中（07:08 JST 開始）
**直近のPO指示** (2026-04-29): 「p003巡回を自律的に動かせ」「完成度上げてくれ」
**次のアクション**: **CASE A — Code セッション完了待ち**。**2026-04-29 07:09 JST 自律巡回 SLI 実測** (topics-full.json updatedAt=**2026-04-28T17:05Z=JST 02:05・約 5h 停滞**, count=105): ① keyPoint 100字以上 **2/105=1.9%**（前回 06:10 JST と完全同一 = データ更新自体が動いてない）② keyPoint 空でない 94/105=89.5% ③ 文字数分布 21–50字に 83件 (79%) 集中・51–99字 3件・100+ 2件・1-20字 6件 ④ storyPhase 発端率(ac≥3) **2/48=4.2%**（目標 <10% 既達継続）⑤ phase 分布: 拡散 28/拡散優位、ピーク 5、現在地 4、発端 2、none 9 ⑥ schemaVersion≥3 32/105、statusLabel 37/105、watchPoints 37/105、perspectives 38/105、outlook 94/105 ⑦ judge_prediction 0 件継続。**新規発見**: topics-full.json `updatedAt` が 5 時間更新されていない → regenerateSitemap または processor の処理停止疑い。**起動中タスクとは別軸**でPO指示後の次セッションで T2026-0429-KP3（proc_ai.py プロンプト minLength:100 強化）+ T2026-0428-E（4軸化）+ topics.json 停滞調査が候補。新規起動禁止（CASE A 物理ルール）。
**最終更新**: 2026-04-29 07:09 JST 自律巡回（CASE A: Code 行 1 件稼働中・新規起動禁止 / SLI 完全同値 / topics-full.json 5h 停滞検知 / regenerateSitemap または processor 停止疑い・次サイクルで要観測）

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

## ⚠️ エントリー自動失効ルール（恒久ルール・2026-04-28 制定）

**開始JSTから8時間を超えたエントリーは無効（stale）とみなす。**

- `bash scripts/session_bootstrap.sh` が起動時に自動削除する（手動不要）
- スクリプト失敗時のみ手動で行を削除して push

> 理由: セッションがクラッシュ/タイムアウトした場合、完了処理が走らずエントリーが残り続ける。手動掃除に頼ると発見が遅れる。8時間TTLで自動的に解消する。

## ⚠️ needs-push カラム（恒久ルール・2026-04-28 制定）

**コードファイルを編集する Cowork セッションは `needs-push: yes` を立てる。**

- `lambda/` `frontend/` `scripts/` `.github/` を変更したら必ず `yes`
- push 完了後に行を消すか `no` に書き換える
- 起動チェックスクリプトが `needs-push.*yes` を grep して滞留警告を出す
- 文書だけの変更（`*.md`）では立てなくてよい

> 理由: 「Cowork で実装→push 失敗→Code 起動まで滞留」の事故を物理ゲートで防ぐ（lessons-learned: 2026-04-28 連携の構造的欠陥より）。

## ⚠️ セッション役割分担（恒久定義・2026-04-28 制定）

**Code（Claude Code）がやること**:
- `lambda/`・`frontend/`・`scripts/`・`.github/` のコード変更
- テスト実行・Lambda手動invoke・デプロイ確認
- TASKS.md のステータス更新（実装完了後）

**Cowork がやること**:
- `CLAUDE.md`・`WORKING.md`・`TASKS.md`・`HISTORY.md` のドキュメント更新
- CloudWatch確認・S3データ参照・ステータス報告
- POとの会話・分析・計画立案
- **コードファイルの編集もOK**（WORKING.mdに [Cowork] 行を明記してから着手）
- **git操作もOK** — push前に `rm -f .git/index.lock .git/HEAD.lock` を実行してから git add/commit/push する

> Coworkが実装からpushまで完結できる。lockファイル削除で競合を回避する。

---

## タスク開始前（毎回必須）

```bash
git pull --rebase origin main
git log --oneline -5 -- CLAUDE.md   # 変更があれば CLAUDE.md を再読してから続行
cat WORKING.md                       # staleエントリー（8時間超）は削除してから確認
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

| タスク名 | 種別 | 変更予定ファイル | 開始 JST | needs-push |
|---|---|---|---|---|

> code 編集を含むセッションは必ず `needs-push: yes`。push 後は `no` に切り替える or 行を削除する。

---

## 現在着手中

| タスク名 | 種別 | 変更予定ファイル | 開始 JST | needs-push |
|---|---|---|---|---|
| [Code] T225 tokushoho.html 削除 + CI 不在チェック | code | projects/P003-news-timeline/frontend/tokushoho.html, .github/workflows/ci.yml | 2026-04-29 09:18 JST | yes |
| [Code] T2026-0429-A velocityScore フロント可視化 | code | projects/P003-news-timeline/frontend/app.js, projects/P003-news-timeline/frontend/style.css | 2026-04-29 09:18 JST | yes |
