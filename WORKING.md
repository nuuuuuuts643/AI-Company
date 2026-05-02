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

**今セッション (Code) で完了** (2026-05-02 08:43〜 JST):
- ✅ **T2026-0502-A** — PR #122 作成。両 SLI workflow (`freshness-check.yml` / `fetcher-health-check.yml`) の `steps:` 先頭に `actions/checkout@v4` を追加。根本原因: checkout なしで `scripts/*.py` を呼んでいた。merge 後の schedule run 2 連続 success で完了確認
- ✅ **T2026-0501-M** — PR #118 (within-run dedup + entity pattern + Jaccard) は CI 待ち中 → auto-merge 待ち
- ✅ **PR branch 更新問題** — `auto-update-branches.yml` で恒久対処済み

**次セッション (Dispatch / Code 問わず) でやること**:
1. **T2026-0502-A** 🟠 PR #122 merge 後 — schedule run (毎時 07分 / 23分) 2 連続 success を確認してタスク完了処理
2. **T2026-0502-B** 🟡 (lifecycle Lambda 健全性) — `handler.py:64/:93` の SK 引数を FilterExpression → KeyConditionExpression に修正
3. **T2026-0501-K** 🟡 (フェーズ2) — `lambda/processor/proc_ai.py` の `_STORY_PROMPT_RULES` keyPoint ◎例 をエンタメ+テック差し替え。T2026-0502-A 解消後に着手
4. (フェーズ2 完了条件達成までフェーズ3/4/5 タスクは凍結)

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
| [Cowork] T2026-0502-G 実機検証 + T2026-0502-A/B 起票 (docs only) | Cowork | WORKING.md, TASKS.md, HISTORY.md | 2026-05-02 08:04 | no |
| [Code] auto-update-branches CI再発火 恒久対処 | Code | .github/workflows/auto-update-branches.yml, .github/workflows/ci.yml, .github/workflows/meta-doc-guard.yml | 2026-05-02 09:10 JST | yes |
