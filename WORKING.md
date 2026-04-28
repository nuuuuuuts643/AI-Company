# 着手中タスク（複数セッション間の作業競合管理）

> **このファイルのみで管理する。CLAUDE.md の「現在着手中」セクションは廃止。**
> タスク開始・完了のたびに即 `git add WORKING.md && git commit -m "wip/done: ..." && git push` する。

---

## 🟢 Dispatch 継続性 (Cowork コンテキスト引き継ぎ用)

> **目的**: Dispatch のコンテキストが切れても次のセッションが状態を引き継げるよう、
> 現在進行中フェーズ・直近のナオヤ指示・次のアクションを常に最新化する。
> 1 セクション 5 行以内・全部書き換え可。

**現在のフェーズ**: **フェーズ2（AI品質改善）進行中** — PR #10 マージ済 + T2026-0429-KP 根本対策 landed（効果検証中）
**直近のナオヤ指示** (2026-04-29): 「p003巡回を自律的に動かせ」「完成度上げてくれ」
**次のアクション**: **T2026-0429-KP3 Code セッション要起動** — **2026-04-29 06:10 JST 自律巡回 SLI 実測** (topics.json updatedAt=2026-04-28T17:05Z=JST 02:05?要確認, count=105): ① keyPoint **100字以上 2/105=1.9%**（前回 2/101=1.9% から **完全動かず**）② keyPoint **空でない 94/105=89.5%** ③ 文字数分布 **21–50字に 83件 (79%) 集中**、51–99字 3件、100+ 2件、1-20字 6件 ④ storyPhase 発端率(ac≥3) **2/48=4.2%**（前回 6.2% → 改善・目標 10% 未満既達継続）⑤ verdict 0 件継続。**第3層原因確定**: T2026-0429-KP (5e55d7d) と c8cfb07 (quality_heal 1-99字再処理) と 06:00 JST quality_heal cron 後でも 100字以上が動かない → **proc_ai.py プロンプトが「100字以上」を強制してない** が確定。**起動推奨タスク**: T2026-0429-KP3（proc_ai.py プロンプト minLength:100 強化）+ 同ファイル衝突する T2026-0428-E（4軸化）も同時実施を強く推奨。**コスト試算**: 既存 aiGenerated=True 全件再処理が必要なら 1068件 × $0.0023 ≈ $2.46 → 承認可能範囲。**現状**: WORKING.md `[Code]` 行 0 件 → 新規起動可。
**最終更新**: 2026-04-29 06:10 JST 自律巡回（quality_heal cron 後 SLI 実測・100字以上動かず確定 / proc_ai.py プロンプト強化が必要 / 次セッションで Code 起動推奨）

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
- ナオヤとの会話・分析・計画立案
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
| [Code] T237 AI coverage 根本原因調査 + T2026-0429-A velocityScoreバッジ + T2026-0428-Q success-but-empty スキャン | 調査・実装 | projects/P003-news-timeline/lambda/processor/proc_storage.py, proc_ai.py, frontend/app.js, style.css, scripts/scan_success_but_empty.py | 2026-04-29T07:08 JST | needs-push: yes |
