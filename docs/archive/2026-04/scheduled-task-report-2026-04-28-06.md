# scheduled-task 報告（2026-04-28 06:15 JST）

> Cowork 自動起動セッション。テーマ: 運用ルール検討。
> ナオヤ前提: 「無理して更新しない」「効果が見えない間は保留」「AI 動きやすさ優先」「うまく行ってない場合はすぐ戻す」。

## フェーズ 1: 探索 — 結論「ほぼ整備済」

本日 02:30〜05:16 の 4 回の schedule-task で以下が既に完了済（重複作成しない）:

| 項目 | 反映先 |
|---|---|
| 267 行の運用ルール提案 | `docs/operation-rules-proposal-2026-04-28.md` |
| 318 行の実装スニペット | `docs/operation-rules-impl-snippets-2026-04-28.md` |
| ナオヤ前提の汎用化 | `docs/rules/global-baseline.md §8` |
| CLAUDE.md 圧縮 | 600+ → 132 行（CI ガード 250） |
| commit-msg hook（KPI 行強制） | `scripts/install_hooks.sh` + `.git/hooks/commit-msg` |
| bootstrap schedule mode | `SCHEDULE_TASK=1 bash scripts/session_bootstrap.sh` |
| 環境スクリプトの session-id glob 化 | `scripts/session_bootstrap.sh` / `triage_tasks.py` |
| AI フィールド充填率 SLI 9 起票 | `T2026-0428-N` |
| Tier-0 大規模クラスタ対策起票 | `T2026-0428-O` |
| `(HISTORY 確認要)` 自動取消線化 | `scripts/triage_implemented_likely.py` |

ナオヤの繰り返し前提は §8 に集約済。CLAUDE.md は 132 行で固定。新規ルール追加は本セッションでは行わない（「無理して更新しない」前提に従う）。

## フェーズ 2: 実装 — 1 件（小・可逆・汎用）

**bootstrap 出力の "FUSE noise 抑止"**

- 対象: `scripts/session_bootstrap.sh`
- 動機: 起動チェックが毎セッションで FUSE 起因の harmless noise（`may have crashed...` / `remove the file manually` / `warning: unable to unlink` / `unable to update local ref` / 並行セッション lock 衝突など）を吐き、Claude のコンテキストを汚染して「何か壊れた？」と誤判定させていた
- 修正: `_strip_fuse_noise()` 関数を追加し、git pull/push 出力から既知の harmless line のみを物理的に弾く（実害ある warning は素通し）。フィルタは substring 一致＋限定 sed 1 本のみで誤検知を最小化
- 効果: 起動サマリ前のノイズ 4-6 行が 0 行に。実行時間影響なし
- ロールバック: 1 commit 単一ファイル。問題あれば `git revert` 1 発で戻る
- 汎用性: P002/P006 等で同 script を使う際にも効く。プロダクト固有ロジック無し

検証: 本セッション内で bootstrap を 3 回連続実行し、各 run で noise 行が消えていることを確認（並行 session 起因の lock collision noise も抑止対象）。

## フェーズ 3: 保留した項目（理由付き）

| 項目 | 保留理由 |
|---|---|
| T212 クラスタリング閾値再設計 | core path（`lambda/fetcher/`）改修。schedule-task では副作用読み切れない。専用 Code セッション要 |
| T191/T192/T193 戦略タスク | ナオヤ判断必須（global-baseline §8「方針タスクは Claude 単独着手禁止」） |
| 追加の運用ルール | 既に整備済。空更新禁止（ナオヤ前提）。次の効果観測まで保留 |
| ドキュメント整理（267行＋318行 報告を archive 化） | 本セッションでは扱わず。読み飛ばしリスクが顕在化したら別タスクで |

## なぜなぜ分析: 「同じ schedule-task が 5 回連続で似た提案を出す」事象

| Why | 答え |
|---|---|
| Why1 なぜ 5 回連続で似た出力？ | 各 schedule-task が独立に「探索 → 提案」を走らせ、前回の提案・実装状況を読み飛ばす |
| Why2 なぜ前回成果を読まない？ | bootstrap が「最優先 unblocked タスク」は出すが、「直近 schedule-task で何を実装したか」を STDOUT に出さない |
| Why3 なぜ実装履歴が出ない？ | `git log --grep "schedule-task"` を bootstrap が走らせていない |
| Why4 なぜ走らせていない？ | scheduled-task-protocol.md の「起動時に過去 anti-pattern を見る」が CLI で物理化されておらず、Claude の自発性に依存 |
| Why5 なぜ自発性に依存？ | protocol の anti-pattern 表に「過去 5 件の schedule-task commit を必ず見る」と書いたが、実行を強制する仕組みが入っていない |

**仕組み的対策（本セッションでは保留・効果観測してから判断）:**

1. （候補）bootstrap schedule mode で `git log --oneline -5 --grep "schedule-task"` を最優先 task の上に表示する。実装は数行
2. （候補）schedule-task の commit message から `[Schedule-KPI] implemented=N` を集計し、直近 3 件で implemented=0 が連続したら STDOUT で警告
3. （候補）本日の重複出力を archive 化して `docs/` 直下から退避（読み飛ばしリスク低減）

→ ナオヤ前提「効果が見えない間は保留」に従い、これらは **次の schedule-task で「実装履歴を読まなかったために重複が起きた」事例が再発したら着手** とする。今回は事例 1 件のみで観測サンプル不足。

## 次のアクション

- ナオヤ判断不要。本 commit で完結
- 次の schedule-task は本ファイル + 上記 protocol を読んでから動く（重複防止）
- bootstrap noise 抑止の効果は次回起動時に自動観測される（noise 行が出なければ成功）

---

**生成元**: Cowork schedule-task (2026-04-28 06:15 JST)
**変更ファイル**: `scripts/session_bootstrap.sh` (+18 -3) / `WORKING.md` / 本ファイル
**Verified**: 本セッション内で `bash scripts/session_bootstrap.sh` を 3 回実行し noise 0 行を確認
