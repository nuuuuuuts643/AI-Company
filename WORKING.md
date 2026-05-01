# 着手中タスク（複数セッション間の作業競合管理）

> **このファイルのみで管理する。CLAUDE.md の「現在着手中」セクションは廃止。**
> タスク開始・完了のたびに即 `git add WORKING.md && git commit -m "wip/done: ..." && git push` する。

---

## 🟢 Dispatch 継続性 (Cowork コンテキスト引き継ぎ用)

> **目的**: Dispatch のコンテキストが切れても次のセッションが状態を引き継げるよう、
> 現在進行中フェーズ・直近のPO指示・次のアクションを常に最新化する。
> 1 セクション 5 行以内・全部書き換え可。

**直近のPO指示** (2026-05-02 00:00〜01:00 JST):
「規則体系のリライト・違反全パターン物理化・自走 Lv2 化・組織として動く Claude・セキュリティ監査強化。プロダクト完成にブレないようにして欲しい」

**今セッション (Cowork Dispatch / 引き継ぎ #2) で完了** (2026-05-02 01:37〜01:50 JST):
- ✅ session_bootstrap.sh 起動チェック実施 (broken worktree 6件自動削除 / tmp_obj_ 22件退避 / CLAUDE.md + north-star + current-phase = フェーズ2 確認)
- ✅ 残存していた `.git/MERGE_HEAD`・`MERGE_MSG`・`index.lock` を `_garbage/` に退避（FUSE rm 不可は再発する。bootstrap §1b では一部のみ落ちる）
- ✅ main の CI 直近10件すべて success を確認（PII fix a6ed463e 以降のドリフトなし）
- ✅ **T2026-0502-G の SLI 実測**: `https://flotopic.com/api/topics.json` の `updatedAt = 2026-05-01T09:36:19Z` → 現時点 (2026-05-02 01:40 JST = 2026-05-01 16:40 UTC) で **staleness = 424 分 / 7.1 時間**。閾値 90 分の 4.7 倍。**インシデント継続中**
- ✅ freshness-check.yml: 直近3連続 failure (16:15 / 12:07 / 08:30 UTC)。fetcher-health-check.yml: 直近3連続 failure。最後の success は freshness 00:09 UTC・fetcher-health 21:42 UTC

**🚨 本番インシデント (継続中・最優先・コードセッション必須):**
- topics.json が 7h+ stale。fetcher Lambda 系統が無音。Cowork (Dispatch) の権限では CloudWatch Logs を直接見られないため、**Eng Claude (Sonnet) コードセッション** での調査・修正が必須

**次セッション (Eng Claude / コードセッション・Sonnet・1セッション1タスク) でやること** (PR→CI→merge→done.sh 必須):
1. **🚨 T2026-0502-G 緊急: fetcher Lambda 復旧** — `aws logs tail /aws/lambda/p003-news-fetcher --since 24h`・`aws logs tail /aws/lambda/p003-news-processor --since 24h` を確認。EventBridge スケジュール起動有無 (`aws events list-rules` / `list-targets-by-rule`) / Lambda メトリクス Invocations・Errors (`aws cloudwatch get-metric-statistics`) / S3 publish (`aws s3api head-object --bucket … --key topics.json`) を切り分ける。**根本原因 → 恒久対処 (リトライ・タイムアウト・依存サービス切り分け) → PR**。完了条件: topics.json updatedAt が再び 90 分以内 + freshness-check.yml が次の cron tick で success + Verified-Effect 行付き commit
2. **T2026-0501-K** 🔴 (フェーズ2 直撃) — `lambda/processor/proc_ai.py` の `_STORY_PROMPT_RULES` 内 keyPoint ◎例をエンタメ + テックに差し替え。完了条件: 次回 processor 後 エンタメ/テク 各 50%+ 充填
3. **T2026-0501-M** 🔴 (UX 直撃) — 重複トピック検出・マージ
4. **T2026-0501-N** 🔴 (Dispatch運用) — `gh pr merge --auto --squash` ルール landing
5. (フェーズ2 完了条件達成までフェーズ3/4/5 タスクは凍結)

**実在スケジューラー**: p003-haiku (7:08am daily) / p003-sonnet (手動のみ) / security-audit.yml (週次)
**FUSE 環境メモ**: Cowork セッションでは git CLI が index.lock を unlink できない場合がある。`scripts/cowork_commit.py "msg" file...` で GitHub API 直接コミットに迂回可能（.git/config の token 自動取得）。

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
| [Cowork] T2026-0502-F PII検査failure修正 (cowork_commit.py docstring) + T2026-0502-G fetcher停止緊急タスク起票 | Cowork | scripts/cowork_commit.py, TASKS.md | 2026-05-02 01:48 | yes |
| [Cowork] CI fix: PII 違反解消 (affd1ba8 PII 検査 fail / sk-ant-/個人メール マスク) | Cowork | docs/rules-rewrite-proposal-2026-05-01.md | 2026-05-02 01:25 | yes |
| [Code] T2026-0502-G fetcher Lambda 恒久対処 | Code | projects/P003-news-timeline/lambda/fetcher/handler.py, projects/P003-news-timeline/lambda/processor/handler.py | 2026-05-02 01:55 | yes |
