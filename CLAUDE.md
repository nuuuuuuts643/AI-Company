# ⚡ セッション開始時に必ず最初に実行すること

```bash
bash ~/ai-company/scripts/session_bootstrap.sh
```

これ 1 本で以下が走る（詳細は `docs/rules/global-baseline.md` §3）:

1. git lock / rebase-merge 退避（FUSE rm 不可対応）
2. sync commit + pull (`--no-rebase`) + push
3. `CLAUDE.md` の最近の commit を表示（変更があれば本ファイルを再読してから続行）
4. `docs/product-direction.md` 全文 + `docs/project-phases.md` 先頭30行（**現在フェーズと完了条件**）を表示
5. `WORKING.md` 8h 超 stale 自動削除
6. `TASKS.md` の取消線済み行を `HISTORY.md` に集約移動
7. `needs-push: yes` 滞留警告
8. 1 行サマリ出力

スクリプトが完了サマリを出したら「✅ 起動チェック完了」と報告して着手に進む。

---

## ⚡ Dispatch / Cowork 起動時（毎回必須・行動前に実行）

```
1. WORKING.md の「Dispatch継続性」セクションを読む（状態把握）
2. `cat WORKING.md | grep "\[Code\]"` で [Code] 行を確認 → 1件以上あれば新規コードセッション起動禁止
3. `gh run list --branch main --limit 3` で直近 CI がすべて green であることを確認 → 失敗があれば先に修正セッションを起動してから次タスクへ
4. 前セッション報告に ERROR/WARN 残存があれば先に解消させる
5. コードセッションへのプロンプトに「PR→CI→merge→done.sh」を必ず明記
6. 完了後: WORKING.md Dispatch継続性セクションを最新状態に書き換えて push
```

### ⚠️ Dispatch 絶対禁止パターン（思想ではなく禁止リスト・2026-05-01 制定）

| 禁止行為 | 代わりにすること |
|---|---|
| 手動 invoke を提案する | スケジューラー（p003-haiku/p003-sonnet）に委ねる |
| コードを読まずにパラメータを埋めてプロンプトを送る | 該当ファイルを Read してから書く |
| 実機確認なしで「完了」と報告する | flotopic.com でブラウザ確認してから報告する |
| 効果検証なしで「完了」と報告する | SLI数値の変化を確認するか、スケジューラーに委ねてから報告する |
| CI失敗・ルール違反・stale エントリーに気づいて無視する | 気づいたら即対処またはTASKS.mdに積む |
| Dispatchセッションを長期継続して判断を続ける | 往復20回を超えたらWORKING.mdにDispatch継続性を書き込みセッションを切り替える |

---

## ⚡ 起動後の自動タスク実行

**実行前に必ず**: `docs/project-phases.md` で現在フェーズと完了条件を確認 → `cat ~/ai-company/TASKS.md` で未着手を取得 → **現在フェーズに紐付くタスクを優先**して実行する。各セクション直下の `<!-- フェーズN -->` コメントが帰属判断の根拠。フェーズ1 完了条件未達のうちは、フェーズ2/3 のタスクは原則着手しない（PO 明示指示があれば例外）。

各タスクで以下を順守:

1. **WORKING.md の stale (8h 超) を削除**
2. **WORKING.md に自分の行を追記してから push**（記載なしでコード変更禁止 — 物理ルール）
   ```
   | [Code|Cowork] <タスクID> <タスク名> | <種別> | <変更予定ファイル> | <開始JST> |
   ```
3. **実装する**
4. **完了したら WORKING.md から自分の行を削除し commit & push**

POから新指示があれば優先。未着手なし → 「タスクなし、待機中」と報告して待機。

---

## ⚡ 絶対ルール（最低限・全プロジェクト共通）

> 物理 = CI / hook / scripts で物理ガードあり / 観測 = SLI・cron で外部観測あり / 思想 = テキストルールのみ（運用判断に依存）。
> 思想ルールは「気を付ける」と同じ強度しかない。物理化できる対策は物理化する（global-baseline §6）。

| ルール | 内容 | 強度 |
|---|---|---|
| **完了 = 動作確認済み + 効果検証済み** | `done.sh <task_id> <verify_target>` + `verify_effect.sh <fix_type>` (`ai_quality` / `mobile_layout` / `freshness` / `empty_topics`) で改善を数値で確認。閾値未達は未完了 | 物理 |
| **Verified 行 commit 必須** | `feat:` `fix:` `perf:` には `Verified:` 行（commit-msg hook で reject）。helper: `verified_line.sh` | 物理 |
| **Verified-Effect 行 commit 必須 (T2026-0502-AA)** | `feat:` `fix:` `perf:` には `Verified-Effect:` か `Verified-Effect-Skip:` か `Verified-Effect-Pending:` のどれかを必須（commit-msg hook で reject）。「完了=動作確認+効果検証」を物理化。Skip は理由 (build artifact / test fixture 等) 明示。Pending は `Eval-Due` 日付明示。2026-05-02 Cowork が「PR 出した=完了」誤認 4 回繰り返した対策 | 物理 |
| **同名ファイル並行編集禁止** | WORKING.md 宣言なしで触らない。8h TTL 自動削除＋needs-push 滞留警告は session_bootstrap.sh | 観測 (commit reject ではない) |
| **scriptタグ defer/async 禁止** | chart.js / config.js / app.js / detail.js。CI で物理ブロック | 物理 |
| **PII / secrets コード直書き禁止** | env var か AWS Secrets Manager 必須。CI で `sk-ant-` / `AKIA` grep 検出 | 物理 |
| **CLAUDE.md は 250 行以内** | CI で物理ガード。超えたら `lessons-learned.md` / `rules/` / `system-status.md` に外出し | 物理 |
| **タスクID 採番** | `bash scripts/next_task_id.sh`。CI で重複検出 (`triage_tasks.py --check-duplicate-task-ids`) | 物理 |
| **schedule-task は [Schedule-KPI] 必須** | commit-msg hook で `implemented=N created=M closed=K queue_delta=±X` 行を必須化 | 物理 |
| **AI 4 軸キーワード保持** | about.html に「状況解説」「各社の見解」「これからの注目ポイント」が残ること。CI content-drift-guard で物理ブロック | 物理 |
| **freshness / 充填率の SLI** | freshness-check.yml SLI 1〜11 (updatedAt / keyPoint / perspectives / outlook / sitemap_reach 等)。閾値割れで Slack | 観測 |
| **Lambda 主ループ wallclock guard** | 外部 API 呼び出しループは `context.get_remaining_time_in_millis()` で break | 思想 |
| **新規 formatter は boundary test 同梱** | 0/null/undefined/NaN/未来日付を全部 assert | 思想 |
| **新規外部システム統合の3ステップ** | ①公式ドキュメント通読 ②外部が独立に読みに来る全ファイルをリスト化 ③外部管理画面で「Verified」確認 | 思想 |
| **対症療法ではなく根本原因** | band-aid より API 設計修正 | 思想 |
| **なぜなぜは構造化 + 横展開チェックリスト追記** | Why1〜Why5 + 仕組み的対策 3 つ以上 + `docs/lessons-learned.md` の「横展開チェックリスト」表に 1 行追加（実装ファイルパスを書く）。CI `check_lessons_landings.sh` で landing 物理検証 | 物理 |
| **deploy.sh は直接実行しない** | デプロイは GitHub Actions 任せ。インフラ新規作成のみ例外でPO確認 | 思想 |
| **アドホックAPI呼び出し禁止** | flotopic.com APIはスケジューラー（p003-haiku/p003-sonnet）経由のみ。セッション内でのcurl/fetch確認は禁止。効果測定はスケジューラーに委ねてセッション即クローズ | 思想 |
| **main 直 push 禁止 (T2026-0502-M / -PHYSICAL-GUARD-AUDIT)** | `git push origin main` は `.git/hooks/pre-push` で物理拒否（PR #160 で「物理化 ✅」と記録されたまま実装は placeholder だったのを 2026-05-02 に実 reject 化）。実コード変更は必ず branch + PR。bootstrap sync の chore: commit のみ `ALLOW_MAIN_PUSH=1` で escape。緊急 bypass `git push --no-verify` 使用時は WORKING.md に理由＋`Verified-Effect:` 必須 | 物理 |
| **git エラー黙殺禁止 (T2026-0502-M / -PHYSICAL-GUARD-AUDIT)** | scripts 内の `git pull` / `git push` は `\|\| true` + `tail -N` で終了コードを捨てない。`PIPESTATUS[0]` で捕捉し `if [ "$_git_*_status" -ne 0 ]` で `BOOTSTRAP_EXIT=1` に流して末尾で exit 1（PR #159 で「物理化 ✅」と記録されたまま実装は変数取得のみだったのを 2026-05-02 に実 exit 経路化）。FUSE noise filter (`_strip_fuse_noise`) は維持。`check_lessons_landings.sh` が exit 経路まで grep 検証 | 物理 |

### 中断ルール（2026-04-28 PM 制定）

| 規則 | 内容 |
|---|---|
| **完了まで走る** | コードセッションは完了まで走り切る。「止める？再開する？」をPOに聞かない |
| **中断条件** | 中断してPOに確認するのは「**実装の前提が根本的に変わった場合**」のみ。文言の好み・デザインの揺らぎは中断理由にしない |
| **金がかかる場合** | 例外: 新規 AWS リソース作成 / API 課金 / 不可逆操作（DB drop 等）は事前確認 |

### コスト規律ルール（2026-05-02 PM 制定・T2026-0502-COST-DISCIPLINE / -PHYSICAL）

> 背景: T2026-0502-SEC-AUDIT 後の効果検証で Cowork が deploy-lambdas.yml を **3回 workflow_dispatch・GHA minutes 浪費 + AWS API を 8 回 polling** で「再試行すれば直る」期待で叩き続け、構造的失敗を診断しないまま PO トークンも消費した事故。最初は思想ルールで導入したが PO から「物理ガードできないのか」指摘 → 物理化。

| 規則 | 内容 | 強度 |
|---|---|---|
| **workflow_dispatch は wrapper 必須** | `bash scripts/gh_workflow_dispatch.sh <workflow>` 経由でのみ dispatch 可。直接 `curl -X POST .../actions/workflows/<wf>/dispatches` は **pre-commit hook で reject**。wrapper は同一セッション 2 回 + 直近 main 連続失敗で 3 回目を exit 1 | **物理 (pre-commit + wrapper)** |
| **polling パターン物理 reject** | `sleep N && curl` / `sleep N && aws lambda` / `for i in {1..N}; do curl/aws ... done` を含む code は **pre-commit hook で reject**。1 回確認 + schedule (`p003-haiku` 朝7:08) 委ね。bypass = `git commit --no-verify` (要 WORKING.md 記録) | **物理 (pre-commit)** |
| **AWS list/get 系も連投禁止** | `lambda list-functions` / `get-function-configuration` を **同一セッション 5 回まで**。同じ情報を再取得して状態が変わっていないか確認するのは無駄 (一度取って判断する) | 思想 (実装は Cowork 自身の自覚に依存。violation は session_info MCP の transcript で可視化される) |
| **「金がかかる」の自覚** | GitHub Actions minutes / Anthropic Claude tokens / AWS API call (個別は安いが累積) すべて課金。Cowork が「念のため確認」を多用する癖を出さない | 思想 |
| **代替手段**: 失敗の根本原因がわからない時 | (1) TASKS.md に「<workflow> N 回連続 failure・原因不明」エントリーを書く / (2) WORKING.md に Dispatch 継続性として記録 / (3) Code セッション or PO 手動操作に handoff / (4) スケジュール `p003-haiku` (毎朝) に観察を委ねる | 思想 |

**物理ガード実装**:
- `scripts/gh_workflow_dispatch.sh` — workflow_dispatch wrapper (セッション内 max 2 回 + 直近 main 連続失敗 detection)
- `.git/hooks/pre-commit` — `curl -X POST .../dispatches` / `sleep N && curl` / `for i in N do curl/aws` のいずれかを含む staged diff を reject
- `scripts/install_hooks.sh` — pre-commit hook installer に上記パターン追加

---

## ⚡ 完了の流れ

0. **設定値・スケジュール・仕様を変更した場合、`docs/system-status.md` と関連コメント（handler.py 先頭・detail.js・deploy.sh 等）を同時に更新する（後回し禁止）**。CI `docs-sync-check.yml` は 30日 stale + cron 不一致検出のみ（observation）。「同時更新を強制」する物理ガードは未実装 — PR テンプレチェックリストで運用補完
1. 完了タスクを `HISTORY.md` に追記。CLAUDE.md には1行痕跡のみ
2. `bash done.sh <task_id> <verify_target>` で動作確認込みで完了処理
3. commit メッセージに `Verified: <url>:<status>:<timestamp>` 行を含める

---

## ⚡ 規則の置き場所（責務別ファイル）

| ファイル | 内容 |
|---|---|
| `CLAUDE.md` (本ファイル) | 起動チェック・絶対ルール（250 行以内） |
| `docs/rules/global-baseline.md` | **全プロダクト共通の前提条件**（P002/P006 等で再利用） |
| `docs/lessons-learned.md` | なぜなぜ事例集（append-only・Why1〜Why5 + 仕組み的対策） |
| `docs/system-status.md` | プロジェクト状態スナップショット（毎セッション必読） |
| `docs/rules/bug-prevention.md` | 再発防止ルール表（パターン×ルール） |
| `docs/rules/design-mistakes.md` | 設計ミスパターン集 |
| `docs/rules/quality-process.md` | 品質改善の進め方（finder/implementer 共通） |
| `docs/rules/user-context-check.md` | 実装前ユーザー文脈チェック（4つの問い） |
| `docs/rules/legal-policy.md` | 法的・規約方針（引用・クロール・一次情報バッジ） |
| `docs/flotopic-vision-roadmap.md` | プロダクトビジョン |
| `docs/product-direction.md` | 現在のプロダクト方針（毎セッション必読・session_bootstrap.sh が起動時に全文表示） |
| `docs/project-phases.md` | フェーズ定義・機能要件 (Epic) マップ・現在地（毎セッション必読・session_bootstrap.sh が起動時に先頭30行表示） |

タスク開始時に CLAUDE.md → global-baseline.md → system-status.md → product-direction.md → project-phases.md の 5 つを確認し、必要に応じて他を参照する。

---

## ⚡ Cowork ↔ Code 連携ルール

**Dispatch（Cowork スマホ/デスクトップ）= POから指示を受け取り、コードセッションをキューで管理し、完了を報告する。判断は最小化する。**

両方が同一リポジトリに git push する。役割分担:

**Code（Claude Code/CLI）**:
- `lambda/` `frontend/` `scripts/` `.github/` のコード変更（Mac ファイルシステム依存）
- ローカルテスト実行（pytest 等・Mac 環境必要）
- デプロイ確認（GitHub Actions と連動）
- TASKS.md ステータス更新（実装完了後）

**Cowork / Dispatch（スマホ・デスクトップ）**:
- `CLAUDE.md` `WORKING.md` `TASKS.md` `HISTORY.md` のドキュメント更新
- **AWS MCP 経由で Lambda / CloudWatch / DynamoDB / S3 / EventBridge の運用操作**
  - `mcp__awslabs_aws-mcp-server__call_aws` で `aws sts / lambda / cloudwatch / logs / events / s3 / dynamodb` 等
  - read 全般可・write 系は invoke / メトリクス取得 / 設定参照は OK・**Lambda コード書換 (`update-function-code`) や DB 破壊 (`delete-table`) は禁止**
  - 例: 障害調査・効果検証 (Errors / Invocations 集計) ・スケジュール確認 (`events list-rules`) は Cowork で完結
- POとの会話・分析・計画立案
- コードファイル編集も可（WORKING.md 明記してから・FUSE 経由で write 可能・unlink 不可は無視）
- git 操作も可（FUSE で `git CLI` が詰まる場合は `scripts/cowork_commit.py` で GitHub API 経由 PR）

**詳細**: `docs/rules/cowork-aws-policy.md`（AWS MCP / git 役割分離・多重防御原則・IAM Deny 物理化候補）

### セッション並走ルール（2026-04-28 PM 制定・物理ルール）

| 規則 | 内容 |
|---|---|
| **同時起動上限** | Dispatch から起動するコードセッション = **同時 1 件まで**（Dispatch 自身含め 2 件以内）。新規タスクは前セッション完了までキューに積む |
| **1セッション1タスク厳守** | 1つのコードセッションに渡すタスクは必ず1件のみ。「タスク1: …、タスク2: …」は絶対禁止。2件以上ある場合は順番にセッションを起動する |
| **完了まで走る** | コードセッションは完了まで走り切ってから報告する。「止める？再開する？」を Dispatch がPOに聞かない |
| **中断条件** | 中断してPOに確認するのは「**実装の前提が根本的に変わった場合**」のみ。それ以外は判断コストゼロで完走 |
| **セッション名規則** | コードセッション名は「**何を commit するか**」が一目で分かる名前。✅「CI 構文チェック fix」 ❌「調査」「作業」 |
| **物理担保** | `session_bootstrap.sh` が `[Code]` 行 2 件以上を ERROR で出す（既存 WARN を ERROR 化）。WORKING.md の並走 ≥2 件常態化はフェーズ 1 完了の阻害要因 |

### コードセッションのモデル選択ルール（2026-05-01 制定）

**Dispatch が `start_code_task` を呼ぶ際、必ず `model` パラメータを明示する。Opus はデフォルト禁止。**

| モデル | 用途 |
|---|---|
| **Haiku** | TASKS.md 更新・git 操作・ドキュメント修正・1ファイルの軽微なバグ修正 |
| **Sonnet** | 機能実装・アルゴリズム変更・複数ファイル修正・テスト追加（**原則これを使う**） |
| **Opus** | 複雑な設計判断・多システム連携・アーキテクチャ変更など Sonnet では精度が足りないと判断した場合。使う際は理由を報告する |

スケジュールタスクも同様: `p003-haiku`（Haiku）/ `p003-sonnet`（Sonnet）を目的に応じて使い分ける。

> Cowork が実装〜push まで完結できる構造。lock 退避で競合を回避する。Dispatch 運用安定はフェーズ 1 完了条件 §C（`docs/project-phases.md`）。

### 時間待ち確認はスケジューラーに渡す（2026-04-29 制定）

**効果検証や データ伝播待ちで Dispatch / Code セッションを開いたままにしない。以下のスケジュールタスクに委ねてセッションは即クローズする。詳細・引き継ぎ手順は `docs/rules/global-baseline.md` §10。**

| タスク | モデル | 用途 |
|---|---|---|
| `p003-haiku` | Haiku | 朝7時1回。CloudWatch エラー確認・未マージPR確認。外部API呼び出しなし |
| `p003-sonnet` | Sonnet | 手動起動。SLI実測・根本原因分析・コードセッション起動判断 |

**スケジュールタスクの使い方（2種類）**:
1. **効果検証待ち**: PR merge 後「N時間後に SLI を再測定して TASKS.md に結果を積む」one-time task を登録して即クローズ
2. **定常監視**: `p003-haiku` が毎朝確認。異常があれば WORKING.md に記録

**スケジュールタスク定期精査**: 月1回、不要・重複タスクを棚卸しして削除する（2026-05-01 制定）。`p003-sonnet` を使って手動で実施。

### CI 待ちは即クローズ（物理ルール・2026-04-30 追加）

**PR を出したらコードセッションを即 exit する。Monitor ツールで CI 完了を待つな。**
- **PR 作成前に `gh run list --branch <branch> --limit 3` で既存 CI 失敗がないことを必ず確認する。失敗がある場合は先に修正してから PR を作成する**
- CI 結果確認はスケジューラーまたは次回 session_bootstrap.sh に任せる
- 「CI pending → Monitor でポーリング」はコンテキスト消費 + コスト増の禁止パターン
- 違反例: CI 待ち中に Monitor を呼ぶ / gh pr checks をループする / 既存 CI 失敗を無視して PR を出す

---

## ⚡ Team Operating Rules

**完了条件**: build/compile 通過 + 主要機能動作確認 + 全テストパス + フロントは本番 URL で目視 + Verified 行付き commit。

**完了報告ルール**: 「できた」の前に①エラーログ確認②動作確認③警告修正。自力で直せない場合は「ここで詰まっている」と報告する。

**共通原則**: 実装だけで完了扱いにしない。UI/文言を勝手に省略しない。自力で直せるエラーは直して再実行する。空報告禁止。証拠（ファイル変更・ログ・スクリーンショット）を必ず示す。

---

## ⚡ プロジェクト状態 → `docs/system-status.md`

> 詳細スナップショット・残タスク・将来アイデアは外出し。

**現在着手中** → `WORKING.md`
**完了済み** → `HISTORY.md`
**未着手キュー** → `TASKS.md`

---

## ⚡ 絶対ルール（毎セッション遵守）

- 決まったことは会話で終わらせず即ファイルに書く
- URL の確認・デプロイ確認は自分でやる（POに聞かない）
- 「書きました」「やります」の宣言は信用されない。ファイル存在が証拠
- 空報告禁止
- 実装した≠動いている。実際にエンドユーザーが使えて初めて完了
