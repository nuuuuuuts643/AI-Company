# Global Baseline — 全プロダクト共通の前提条件

> このファイルは P003 Flotopic / P002 Flutter ゲーム / 将来 P006 等、**全プロダクトで共通**の絶対ルール集。
> 各プロダクトの `CLAUDE.md` から `docs/rules/global-baseline.md` を参照する形で再利用する。
> ナオヤから繰り返し言われている「前提条件」を 1 ファイルに集約。
> ルールの長文化を避けるため、**理由は最小限・形式は表**に統一する。

最終更新: 2026-04-28

---

## 1. 振る舞いの絶対ルール（ナオヤ宣言由来）

| ルール | 内容 |
|---|---|
| 言語 | 日本語で対応。簡潔・誠実・媚びない |
| 根本原因 | 対症療法ではなく根本原因を直す。足回りで誤魔化さない |
| 完了の定義 | push しただけは未完了。本番 URL / CloudWatch / 実機で動作確認した状態のみ「完了」 |
| 変更前の依存確認 | コード変更前に「このファイルが何に依存されているか」を口に出す。言えなければ変更しない |
| 並行編集禁止 | 同名ファイルを WORKING.md 宣言なしで触らない |
| PII / secret 直書き禁止 | env var か AWS Secrets Manager 必須 |
| なぜなぜ分析 | 問題発生時 Why1〜Why5 + 仕組み的対策 3 つ以上を `docs/lessons-learned.md` に追記。テーブル 1 行は再発防止と呼ばない |
| 仕組み的対策の質 | 「外部観測（SLI / metric / 警告）」または「物理ゲート（CI / hook / scripts）」を最低 1 つ含む |
| 仕組み的対策の landing 検証 | 新規対策を書いたら `docs/lessons-learned.md` 末尾の「横展開チェックリスト」表に 1 行追加（実装ファイルパス必須）。CI `check_lessons_landings.sh` で repo に該当ファイルが存在するか物理検査。**「書いただけで動いていない」対策の fossilize を物理的に防ぐ** |

---

## 2. ドキュメント構成（1 リポジトリ標準）

| ファイル | 役割 | 上限 |
|---|---|---|
| `CLAUDE.md` | 起動チェック + 絶対ルール本体 | **250 行**（CI で物理ガード） |
| `docs/rules/global-baseline.md` | 本ファイル。全プロダクト共通の前提 | — |
| `docs/lessons-learned.md` | なぜなぜ事例集（append-only） | — |
| `docs/system-status.md` | プロジェクト状態スナップショット | 200 行目安 |
| `docs/rules/*.md` | 領域別ルール（バグ防止・設計ミス等） | 各 100 行目安 |
| `TASKS.md` | 未着手キュー（取消線済みは triage で HISTORY へ自動移動） | — |
| `WORKING.md` | 着手中（needs-push カラム必須） | — |
| `HISTORY.md` | 完了済み（参照専用・append-only） | — |

> ルール表が長くなりすぎたら専門ファイルへ移し、CLAUDE.md からはリンクで参照する。

---

## 3. 起動チェック（毎セッション必須）

```bash
bash scripts/session_bootstrap.sh
```

これ 1 本で以下が走る:

1. git lock / rebase-merge を `_garbage/` に退避（FUSE rm 不可環境対応）
2. ローカル変更を sync commit & pull (`--no-rebase` 固定で中断作らない) & push
3. `CLAUDE.md` の最近の commit を表示（変更検知 → 再読指示）
4. `WORKING.md` の 8h 超 stale 行を自動削除
5. `TASKS.md` の取消線済み行を `HISTORY.md` に集約移動
6. `WORKING.md` 内の `needs-push: yes` 滞留があれば最優先警告
7. 1 行サマリ「✅ 起動チェック完了」

> 既存の長い手動 bash ブロックは廃止し、このスクリプト 1 本に集約。

---

## 4. commit / push の物理ゲート

| 対象 | 仕組み |
|---|---|
| `feat:` / `fix:` / `perf:` の commit | `Verified: <url>:<status>:<JST_timestamp>` 行必須。`commit-msg` hook で reject |
| `wip:` `docs:` `chore:` etc. | Verified 不要（互換のためスキップ）|
| AdSense pub-id ↔ ads.txt 整合 | `pre-commit` hook で物理 reject |
| 旧フェーズ表記 / 旧 4 セクション | `pre-commit` hook で物理 reject |
| タスク ID 重複（TASKS.md） | `python3 scripts/triage_tasks.py --check-duplicate-task-ids` で CI 検出（exit 1）|
| CLAUDE.md 250 行超過 | CI で物理ガード |

hook インストール: `bash scripts/install_hooks.sh`（clone 直後 1 回）。

---

## 5. WORKING.md 必須カラム

| カラム | 役割 |
|---|---|
| タスク名 | `[Code]` または `[Cowork]` プレフィックス + ID + 短い説明 |
| 種別 | `Code` / `Cowork` |
| 変更予定ファイル | パスをカンマ区切り（並行編集競合検知のキー） |
| 開始 JST | `YYYY-MM-DD HH:MM`（8h TTL の判定キー）|
| needs-push | `yes` / `no`（コード変更を含むなら `yes`、push 後 `no`）|

---

## 6. AI が動きやすくなるための原則

| 原則 | 理由 |
|---|---|
| ルールは表で書く | LLM はテーブル形式の方が遵守率が高い。長文の散文ルールは無視されやすい |
| 「気を付ける」は禁止 | 仕組み的対策に「注意する」「気を付ける」は書かない。CI / hook / metric / SLI / scripts のいずれかで物理化する |
| 1 ステップ 1 動作 | 「A して B して C する」を 1 行に押し込まない。LLM は途中 step を端折る |
| 例を 1 つ必ず添える | 抽象ルールには「✅ 良い例」「❌ 悪い例」をペアで書く |
| 起動コストを下げる | CLAUDE.md は 250 行・必読は 4 ファイル以内・サマリは bootstrap が 1 行で出す |
| 同じ規則を 2 箇所に書かない | 重複は drift の原因。CLAUDE.md とこのファイルの両方に同じ表を書かない |

---

## 7. 全プロダクト共通の DO / DON'T

**DO**:
- 不確実な作業前に依存ファイルを声に出す
- 完了報告に証跡（URL / status / log path）を必ず添える
- 8h 超のセッションは WORKING.md に残さない
- なぜなぜは Why1〜Why5 + 仕組み的対策 3 つ以上で書く

**DON'T**:
- push しただけで「完了」と報告
- ルールを散文で書く（表形式に統一）
- 同じタスク ID を別件に再利用（衝突回避）
- 「Cowork は git を叩かない」運用に戻す（push 滞留が起きるため失敗済み）

---

## 8. ナオヤの前提条件（全プロダクト共通・繰り返し発言から抽出）

| 前提 | 適用方針 |
|---|---|
| ルールの長文化は読まれない | 新規ルールは表 1 行 or 既存表に追記。散文で 5 行以上書かない |
| 効果が見えない間は保留 | 「念のためルール追加」は禁止。実装した結果が観測されてから次の手を打つ |
| 無理して更新しない | 「ルール検討してください」と頼まれても、効果が見えない案は **追加せず保留と報告** で良い。空更新で CLAUDE.md / global-baseline を肥大化させない |
| うまく行ってない場合はすぐ戻す | 仕組み化変更は 1 commit / 1 ファイル単位で reversible に保つ。複数ファイル束ねた巨大変更は禁止 |
| AI の動きやすさを優先 | 起動時に読む量を減らす・冒頭に置く・物理ゲートで縛る（テキストで縛らない） |
| ルールは汎用形で書く | 「P003 で…」「flotopic.com で…」など特定プロダクト名/URL を本ファイルに書かない。固有ルールはプロダクト側 (`CLAUDE.md` / `docs/P00x-*.md`) へ |
| 全プロダクト共通の前提は本ファイルに集約 | ナオヤから繰り返し言われた事は本表 §1 / §6 / §8 に追記する。CLAUDE.md には固有ルールのみ |

---

## 9. プロダクト固有ルールへの参照

各プロダクトの `CLAUDE.md` は本ファイルを参照しつつ、固有ルールを追加する。

| プロダクト | CLAUDE.md | 固有ルール先 |
|---|---|---|
| P003 Flotopic | `~/ai-company/CLAUDE.md` | `docs/rules/bug-prevention.md` `docs/rules/design-mistakes.md` |
| P002 Flutter | `projects/P002-flutter-game/briefing.md` | （未整備）|

---

## 10. 時間待ち確認はスケジューラーに渡す（2026-04-29 制定）

**実装完了後、効果が出るまで時間を要する確認は Dispatch / Code セッションで待機しない。スケジューラー（scheduled task）に引き継いで自動化する。**

| 規則 | 内容 |
|---|---|
| **対象** | 充填率改善・データ伝播・A/B テスト計測・SLI 反映待ち・cron 駆動の処理結果待ち等、「効果が出るまでに分〜時間オーダーで待ちが発生する確認」全般 |
| **禁止** | Dispatch / Code セッションを開いたまま `sleep` / 監視ループ / 手動 polling で待機すること。セッション枠を時間待ちに使わない |
| **引き継ぎ手順** | ① 確認したい SLI / 閾値 / 次アクション条件を `docs/system-status.md`（または該当 runbook）に明記 → ② スケジューラー（`anthropic-skills:schedule` / `mcp__scheduled-tasks` / GitHub Actions cron 等）に「次回実行時にこの確認を走らせる」routine を登録 → ③ Dispatch セッションは「実装→引き継ぎ→完了報告」で即クローズ |
| **自律ループ化** | スケジューラー実行で閾値未達と判明した場合、確認ジョブが `TASKS.md` に次アクションを 1 行積む。これにより人手介入なしで「実装→効果検証→次手」のループが回る |
| **完了の定義** | 効果検証は時間がかかるため、実装＋引き継ぎ登録＋ナオヤへの報告の 3 点が揃った時点で当該タスクは「完了」扱い。効果検証結果の確認は別タスクとしてスケジューラー側で発火する |

> **理由**: 「効果が出るまで Dispatch を起動したままにしておく」運用は (a) セッション並走上限を圧迫する (b) コンテキストが切れて引き継ぎ漏れる (c) ナオヤが追加指示できない、の 3 重に詰まる。スケジューラーに渡せば人と AI の双方が手を空けられる。
> **適用例**: 「proc_ai プロンプト変更後、次回 cron 起動で keyPoint 100字以上率が上がるか」を見るなら、Dispatch を閉じ、scheduled task に「次回 freshness-check 実行後に SLI を再測定し、閾値未達なら T2026-XXXX-Y を TASKS.md に積む」routine を仕掛ける。

---

## 改訂履歴

- **2026-04-29** §10 「時間待ち確認はスケジューラーに渡す」追加（Dispatch セッション枠を時間待ちで詰まらせない）
- **2026-04-28 PM (v3)** §1 に「仕組み的対策の landing 検証（横展開チェックリスト）」追加。書いた対策の fossilize を物理的に防ぐ
- **2026-04-28 (v2)** §8/§9 順序バグ修正 + §8 にナオヤ前提 2 行追記（汎用形要請・無理して更新しない）
- **2026-04-28** 初版（schedule-task で運用ルール仕組み化に伴い分離）
