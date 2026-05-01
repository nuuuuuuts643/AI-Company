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

**今セッション (Eng Claude / Code セッション・T2026-0502-G) で完了** (2026-05-02 01:55〜02:10 JST):
- ✅ session_bootstrap.sh + merge conflict 解消 (WORKING.md + cowork_commit.py)
- ✅ CloudWatch Logs 調査: `[dynamo-batch] Float types are not supported` (7/8 chunks) + `UnboundLocalError: current_run_tids` の2連鎖バグを特定
- ✅ 恒久対処実装: `_dynamo_safe(obj)` 層防御 + `current_run_tids` 早期定義 + `merge_audit.py` float排除
- ✅ PR #114 作成 + auto-merge 設定済み。CI通過後 Lambda デプロイ → 次の 30分 cron で修復予定
- ✅ lessons-learned.md T2026-0502-G Why1〜Why5 + 横展開チェックリスト追記

**🔄 T2026-0502-G 完了待ち (自動デプロイ後の確認が必要):**
- PR #114 auto-merge: CI通過後に squash merge → GitHub Actions が Lambda デプロイ
- 次回 fetcher cron (~17:33 UTC = 02:33 JST): topics.json updatedAt が更新されるはず
- freshness-check.yml (18:23 UTC tick) で success を確認してから done.sh T2026-0502-G を実行

**⚠️ p003-haiku alert (2026-05-02 22:13 UTC)**: flotopic-lifecycle Lambda で `ValidationException: Filter Expression can only contain non-primary key attributes: Primary key attribute: SK` が直近24hで複数回発生 (handler.py:64 delete_snaps / :93 delete_old_snaps)。SK は KeyConditionExpression で指定すべきところ FilterExpression に入っている。修正タスクを TASKS.md に起票要 (他5 Lambda は ERROR ゼロ)。

**次セッション (Dispatch または p003-haiku で確認後) でやること** (PR→CI→merge→done.sh 必須):
1. **T2026-0502-G 完了確認**: `curl -s https://flotopic.com/api/topics.json | python3 -c "import json,sys,datetime;d=json.load(sys.stdin);print(d['updatedAt'])"` で updatedAt < 90分を確認 → `bash done.sh T2026-0502-G https://flotopic.com/api/topics.json`
2. **T2026-0501-K** 🔴 (フェーズ2 直撃) — `lambda/processor/proc_ai.py` の `_STORY_PROMPT_RULES` 内 keyPoint ◎例をエンタメ + テックに差し替え
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
- `lambda/`・`frontend/`・`scripts/`・`.github/` のコード変更（Mac ファイルシステム依存）
- ローカルテスト実行 (pytest / npm test)
- デプロイ確認・gh CLI 操作
- TASKS.md のステータス更新（実装完了後）

**Cowork がやること**:
- `CLAUDE.md`・`WORKING.md`・`TASKS.md`・`HISTORY.md` のドキュメント更新
- **AWS MCP 経由 (`mcp__awslabs_aws-mcp-server__call_aws`) で AWS 運用操作** (Lambda/CloudWatch/DynamoDB/S3/EventBridge)
  - 障害調査 (logs filter-log-events / metrics get-metric-statistics / lambda get-function-configuration)
  - 効果検証 (Errors/Invocations 集計・SLI 実測)
  - 設定確認 (events list-rules / lambda list-functions)
  - **禁止**: `update-function-code` / `delete-*` / 不可逆な write 操作 → Eng Claude 領域
- POとの会話・分析・計画立案
- **コードファイルの編集もOK**（WORKING.mdに [Cowork] 行を明記してから着手）
- **git操作もOK** — FUSE で `git CLI` が詰まる場合は `scripts/cowork_commit.py` で GitHub API 経由 PR

> Coworkが運用観測〜PR作成まで完結できる。AWS MCP + cowork_commit.py で FUSE 制約を物理的に迂回する。

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
| [Code] T2026-0501-M 重複トピック検出・マージ恒久対処 | Code | lambda/fetcher/config.py, lambda/fetcher/handler.py, lambda/fetcher/ai_merge_judge.py | 2026-05-02 JST | yes |
