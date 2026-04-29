# ⚡ セッション開始時に必ず最初に実行すること

```bash
bash /Users/murakaminaoya/ai-company/scripts/session_bootstrap.sh
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

## ⚡ 起動後の自動タスク実行

**実行前に必ず**: `docs/project-phases.md` で現在フェーズと完了条件を確認 → `cat /Users/murakaminaoya/ai-company/TASKS.md` で未着手を取得 → **現在フェーズに紐付くタスクを優先**して実行する。各セクション直下の `<!-- フェーズN -->` コメントが帰属判断の根拠。フェーズ1 完了条件未達のうちは、フェーズ2/3 のタスクは原則着手しない（ナオヤ明示指示があれば例外）。

各タスクで以下を順守:

1. **WORKING.md の stale (8h 超) を削除**
2. **WORKING.md に自分の行を追記してから push**（記載なしでコード変更禁止 — 物理ルール）
   ```
   | [Code|Cowork] <タスクID> <タスク名> | <種別> | <変更予定ファイル> | <開始JST> |
   ```
3. **実装する**
4. **完了したら WORKING.md から自分の行を削除し commit & push**

ナオヤから新指示があれば優先。未着手なし → 「タスクなし、待機中」と報告して待機。

---

## ⚡ 絶対ルール（最低限・全プロジェクト共通）

> 物理 = CI / hook / scripts で物理ガードあり / 観測 = SLI・cron で外部観測あり / 思想 = テキストルールのみ（運用判断に依存）。
> 思想ルールは「気を付ける」と同じ強度しかない。物理化できる対策は物理化する（global-baseline §6）。

| ルール | 内容 | 強度 |
|---|---|---|
| **完了 = 動作確認済み + 効果検証済み** | `done.sh <task_id> <verify_target>` + `verify_effect.sh <fix_type>` (`ai_quality` / `mobile_layout` / `freshness` / `empty_topics`) で改善を数値で確認。閾値未達は未完了 | 物理 |
| **Verified 行 commit 必須** | `feat:` `fix:` `perf:` には `Verified:` 行（commit-msg hook で reject）。効果検証時は `Verified-Effect:` も。helper: `verified_line.sh` / `verify_effect.sh` | 物理 |
| **同名ファイル並行編集禁止** | WORKING.md 宣言なしで触らない。8h TTL 自動削除＋needs-push 滞留警告は session_bootstrap.sh | 物理 |
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
| **deploy.sh は直接実行しない** | デプロイは GitHub Actions 任せ。インフラ新規作成のみ例外でナオヤ確認 | 思想 |

### 中断ルール（2026-04-28 PM 制定）

| 規則 | 内容 |
|---|---|
| **完了まで走る** | コードセッションは完了まで走り切る。「止める？再開する？」をナオヤに聞かない |
| **中断条件** | 中断してナオヤに確認するのは「**実装の前提が根本的に変わった場合**」のみ。文言の好み・デザインの揺らぎは中断理由にしない |
| **金がかかる場合** | 例外: 新規 AWS リソース作成 / API 課金 / 不可逆操作（DB drop 等）は事前確認 |

---

## ⚡ 完了の流れ

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

**Dispatch（Cowork スマホ/デスクトップ）= ナオヤから指示を受け取り、コードセッションをキューで管理し、完了を報告する。判断は最小化する。**

両方が同一リポジトリに git push する。役割分担:

**Code（Claude Code/CLI）**:
- `lambda/` `frontend/` `scripts/` `.github/` のコード変更
- テスト実行・Lambda 手動 invoke・デプロイ確認
- TASKS.md ステータス更新（実装完了後）

**Cowork / Dispatch（スマホ・デスクトップ）**:
- `CLAUDE.md` `WORKING.md` `TASKS.md` `HISTORY.md` のドキュメント更新
- CloudWatch 確認・S3 データ参照・ステータス報告
- ナオヤとの会話・分析・計画立案
- コードファイル編集も可（WORKING.md 明記してから）
- git 操作も可（push 前に lock 退避: `mv .git/*.lock .git/_garbage/`）

### セッション並走ルール（2026-04-28 PM 制定・物理ルール）

| 規則 | 内容 |
|---|---|
| **同時起動上限** | Dispatch から起動するコードセッション = **同時 1 件まで**（Dispatch 自身含め 2 件以内）。新規タスクは前セッション完了までキューに積む |
| **完了まで走る** | コードセッションは完了まで走り切ってから報告する。「止める？再開する？」を Dispatch がナオヤに聞かない |
| **中断条件** | 中断してナオヤに確認するのは「**実装の前提が根本的に変わった場合**」のみ。それ以外は判断コストゼロで完走 |
| **セッション名規則** | コードセッション名は「**何を commit するか**」が一目で分かる名前。✅「CI 構文チェック fix」 ❌「調査」「作業」 |
| **物理担保** | `session_bootstrap.sh` が `[Code]` 行 2 件以上を ERROR で出す（既存 WARN を ERROR 化）。WORKING.md の並走 ≥2 件常態化はフェーズ 1 完了の阻害要因 |

> Cowork が実装〜push まで完結できる構造。lock 退避で競合を回避する。Dispatch 運用安定はフェーズ 1 完了条件 §C（`docs/project-phases.md`）。

### 時間待ち確認はスケジューラーに渡す（2026-04-29 制定）

**効果検証や データ伝播待ちで Dispatch / Code セッションを開いたままにしない。スケジューラー（`anthropic-skills:schedule` / scheduled task / GitHub Actions cron）に「次回実行時に SLI を再測定し閾値未達なら TASKS.md に次アクションを積む」routine を仕掛けて、セッションは即クローズする。詳細・引き継ぎ手順は `docs/rules/global-baseline.md` §10。**

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
- URL の確認・デプロイ確認は自分でやる（ナオヤに聞かない）
- 「書きました」「やります」の宣言は信用されない。ファイル存在が証拠
- 空報告禁止
- 実装した≠動いている。実際にエンドユーザーが使えて初めて完了
