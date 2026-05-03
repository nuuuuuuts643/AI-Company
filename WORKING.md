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

**今セッション (Cowork) で完了** (2026-05-02 09:00〜09:30 JST):
- ✅ **p003-dispatch-auto-v2 本番稼働開始** — 4回/日 (08/13/18/22 JST) Haiku・Slack通知なし・start_code_task不使用版で create + Run now 検証済 (09:18 JST に WORKING.md 自動更新確認)
- ✅ **scheduled-tasks 環境調査** — `start_code_task` は scheduled session 環境では未提供と確認 (probe タスクで実証済 → tmp_logs に結果あり・auto-sync で削除済)
- ✅ **ゾンビ scheduled-tasks クリーンアップ** — description 空の orphan 5 件 (rule-monthly-audit / security-audit-aws / dispatch-auto / eng-permission-probe / fetcher-recovery-verify) PO 削除
- ⚠️ **失敗 + 切り戻し記録** — PR #120/121: 「鮮度モニタの cron 頻度UP+コアタイム除外」依頼を GitHub Actions cron と解釈してしまい revert。実際は scheduled-tasks 自走の話だった。lessons-learned 候補: 「『スケジュール』『cron』『コアタイム』のような複数レイヤー解釈可能語は AskUserQuestion で対象を明示確認」

**次セッション (Dispatch / Code 問わず) でやること**:
1. **p003-dispatch-auto-v2 観察** — 13:00 / 18:00 / 22:00 JST 自然発火を確認。WORKING.md「最新 Dispatch (auto-v2)」行が毎回更新されてるか・コアタイム前 22:00 で適切に止まるか・明朝 07:08 の p003-haiku と衝突しないか
2. **T2026-0501-K** 🟡 (フェーズ2) — `lambda/processor/proc_ai.py` の `_STORY_PROMPT_RULES` keyPoint ◎例 をエンタメ+テック差し替え
3. (フェーズ2 完了条件達成までフェーズ3/4/5 タスクは凍結)

**観察 OK なら次に追加検討するスケジュールタスク（保留中・順番に）**:
- ⭐ #3 `p003-sonnet-weekly-quality` — 週1月曜10:00 Sonnet・SLI実測+品質低下検出時に fix PR の prompt を TASKS.md に積む (~200k トークン/月・効果デカい)
- #2 `p003-security-audit-aws` — 月1 1日09:30 Haiku・AWS MCP read-only でIAM/S3/secrets チェック (~15k/月)
- #1 `p003-rule-monthly-audit` — 月1 1日09:00 Haiku・CLAUDE.md/docs/rules/ 整合性チェック (~10k/月)

**最新 Dispatch (auto-v2)** 2026-05-03 08:01 JST | staleness=25.4min | 過去2h saves=42 | 直近1h errors=0 | 全SLI healthy・異常なし・次回 13:00 JST run まで観測のみ (outcome=A)

**最新 Dispatch (Cowork)** 2026-05-03 10:30 JST PO「Slack通知の絞り込み＋日次keypoint評価スケジュール」→ PR #338 作成済 ✅:
- PR #291 (削減プラン docs) / #293 (A1 検証結果) / #298 (深掘り §8) / #299 (TASKS.md 整合化) merge ✅
- 衝撃の発見: Lambda/API GW/CloudFront/CloudWatch は全て無料枠内 ($0)。実コストの 95% は DynamoDB R/W $6.42 + S3 PUT $2.17。当初プラン A2/A3/A5/B1/B2/B3/B4/C2/C3 は撤回。本命は A1-CODE / D1 / C1 / D2 / D3 / D4。
- 副産物 CI 修正 2 PR: PR #302 (LINT-YAML-FIX2: iam-policy-drift-check.yml の python3 -c → scripts/iam_canon.py) / PR #303 (IAM-CANON-RESCUE: c521a846 不完全 merge で commit 漏れだった iam_canon.py を初 commit) — 両方 effect 確認済 (workflow_dispatch run success)
- 改訂後の現実的削減見立て: 月 $11 → $7 (約 36% カット)。理想ゼロは脱 AWS 必須

**次セッション (Cowork デスクトップ → Code セッション起動推奨)**:
1. **T2026-0502-COST-A1-CODE** (推奨 #1・規律タスク) — `docs/code-session-prompts/T2026-0502-COST-A1-CODE.md` の prompt をコピペで Code セッション起動。deploy.sh L69-80 + IAM policy 4 ARN 削除 → PR → 慎重に 1 つずつ delete-table。Sonnet・30 分。
2. **T2026-0502-COST-D1** (推奨 #2・調査のみ) — `docs/code-session-prompts/T2026-0502-COST-D1-INVESTIGATE.md` の prompt。lambda/ の DDB Read コードパス全網羅 + 1 候補設計案。Sonnet・1〜2 時間。
3. **T2026-0502-Y** (要 Code セッション) — コスト規律 MCP 物理化 (前回未着手)
4. (フェーズ2 完了条件達成までフェーズ3/4/5 タスクは凍結)

**実在スケジューラー**: p003-haiku (7:08am daily) / p003-dispatch-auto-v2 (4x/日 08/13/18/22 JST) / p003-sonnet (手動のみ) / security-audit.yml (週次・GitHub Actions)
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
| [Cowork] T2026-0502-LAMBDA-CRON-GATE-CI 等 5 件残課題 TASKS.md 起票 (深掘り PR #329 横展開) | Cowork | TASKS.md, WORKING.md | 2026-05-03 10:50 JST | no |
| [Cowork] T2026-0502-SEC-VERIFY-1〜5 起票 (動いてるっぽい排除・SEC-AUDIT セッション 70% 確信前提を task 化) | Cowork | TASKS.md | 2026-05-03 11:00 JST | yes |
| [Code] T2026-0502-BC-CRON-FIX EventBridge cron 追加 + handler.py コメント修正 | Code | projects/P003-news-timeline/deploy.sh, lambda/processor/handler.py | 2026-05-03 13:01 JST | yes |
| [Code] T2026-0503-UX-WATCHPOINTS-FILL + T2026-0503-UX-PERSPECTIVES-FILL watchPoints/perspectives 充填率修正 | Code | projects/P003-news-timeline/lambda/processor/proc_ai.py | 2026-05-03 13:30 JST | yes |
<!-- [Cowork] T2026-0502-UX-CARDTITLE 完了 (2026-05-03 00:00 JST): PR #318 merge ✅ + PR #323 (lessons-learned 補完) auto-merge 待ち。実機検証 (flotopic.com) で12/12カード語句完整性 100% 確認・平均長 29字 (修正前 14.2字)。one-time scheduled task p003-verify-cardtitle-fix-20260504 で 2026-05-04 09:00 JST 自動再検証予定 -->
