# 着手中タスク（複数セッション間の作業競合管理）

> **このファイルのみで管理する。CLAUDE.md の「現在着手中」セクションは廃止。**
> タスク開始・完了のたびに即 `git add WORKING.md && git commit -m "wip/done: ..." && git push` する。

---

## 🟢 Dispatch 継続性 (Cowork コンテキスト引き継ぎ用)

> **目的**: Dispatch のコンテキストが切れても次のセッションが状態を引き継げるよう、
> 現在進行中フェーズ・直近のPO指示・次のアクションを常に最新化する。
> 1 セクション 5 行以内・全部書き換え可。

**現在のフェーズ**: **フェーズ2（AI品質改善）進行中** — T237/T2026-0429-KP3/T2026-0429-B/T2026-0429-D 全マージ済 (#13/#14/#16)。WORKING.md 着手中テーブル空 = `[Code]` 行 0 件。
**直近のPO指示** (2026-04-29): 「p003巡回を自律的に動かせ」「完成度上げてくれ」
**次のアクション**: **CASE B 該当だが新規 Code 起動見送り — cron 反映待ちフェーズ**。**2026-04-29 09:11 JST 自律巡回 SLI 実測** (topics-full.json updatedAt=**2026-04-29T00:05Z=JST 09:05・約 6 分前**, count=109): ① keyPoint 100字以上 **2/109=1.8%**（前回 1.9% から横ばい・**KP3 retry 効果未反映**）② keyPoint 空でない 93/109=85.3% ③ 文字数分布 21–50字 82件・51–99字 3件・100+ 2件・1-20字 6件・空 16 ④ storyPhase 発端率(ac≥3) **4/52=7.7%**（目標 <10% 既達継続・前回 4.2%→7.7%）⑤ phase 分布(ac≥3): 拡散 28/ピーク 5/現在地 4/発端 4/none 11 ⑥ schemaVersion≥3 **39/109=35.8%**（前回 32/105=30.5% → 緩やか増加）⑦ statusLabel/watchPoints/perspectives 37/109,37/109,38/109・outlook 93/109 ⑧ predictions frontend export 0 件継続。**前回懸念解消**: topics-full.json updatedAt 停滞 5h → 解消 (6分前更新)・regenerate 復旧確認。**判断**: KP3 (proc_ai.py minLength:100 retry) + T237 (fetcher_trigger backfill) は約 2h 以内マージで cron 1〜2 サイクル分しか経過していない。新規 Code 起動より 6h 後再観測で効果評価。改善ゼロなら T2026-0429-KP4 候補（既存 keyPoint <100字 トピックの reprocess、コスト試算 109 件 × $0.0023 ≈ $0.25 上限・要PO確認）。並行候補: T2026-0428-E (4軸化) は schemaVersion≥3 が 35.8% で緩慢、T2026-0429-A (velocityScore 可視化・UI) は課金リスクなし即着手可。
**最終更新**: 2026-04-29 09:11 JST 自律巡回（CASE B 該当・Code 行 0 件 / KP3+T237 マージ済 cron 反映待ち / topics-full.json 6分前更新で停滞解消 / 6h 後再観測で keyPoint 効果評価 / ゼロなら KP4 reprocess 提案）

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
