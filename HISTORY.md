# 完了タスク履歴 (HISTORY)

> このファイルは TASKS.md から取消線済み行を集約する場所。
> `session_bootstrap.sh` が定期的に TASKS.md の `~~T...~~` 行を本ファイルに移動する。
> 詳細な振り返り・なぜなぜは `docs/lessons-learned.md` に書く。本ファイルは事実の年表のみ。

---

## 2026-05-02

### T2026-0502-G — fetcher Lambda 停止 → 恒久対処 + 実機検証完了

**起きていたこと**: 2026-05-02 朝 (JST) 起床時、topics.json の `updatedAt` が 407 分 (6.7h) stale。鮮度モニタ + fetcher-health-check.yml が 3 連続 failure。ユーザーには古い情報が見え続けていた。

**調査と恒久対処** (Eng Claude / Code セッション・01:55〜02:10 JST):
- CloudWatch Logs で 2 連鎖バグを特定:
  - `[dynamo-batch] Float types are not supported. Use Decimal types instead.` (7/8 chunks 失敗)
  - `UnboundLocalError: cannot access local variable 'current_run_tids'` で Lambda クラッシュ → S3 publish 走らず
- 恒久対処:
  - `_dynamo_safe(obj)` 層防御を `lambda/fetcher/handler.py` に追加 (再帰的 float→Decimal 変換)
  - `current_run_tids = set(current_run_metas.keys())` を lifecycle ループ前 (行~1082) で早期定義
  - `merge_audit.py` の `detect_mismerge_signals` で `maxGapDays` を `int(max_gap // 86400000)` に統一 (float 排除)
- PR #114 作成 → auto-merge.yml が squash merge (02:06 UTC) → Lambda 自動デプロイ

**実機検証** (Cowork Dispatch / P003 自走・08:04〜08:15 JST):
- topics.json 鮮度: 27.7分 (90分閾値内 ✅)
- CloudWatch メトリクス FetcherSavedArticles 過去 3h: 7 datapoints, sum=178件 (22-31件/run)
- 30min cron 6 回連続 healthy
- **ユーザー被害解消 ✅**

**残課題**: 完了条件②「fetcher-health-check.yml 連続success 2回」は SLI workflow 自体が false-failure を返す別問題のため未達 → 新規 T2026-0502-A として切り出し (Eng Claude エスカレーション)。

**横展開**:
- `docs/lessons-learned.md` L1432〜 に Why1〜Why5 + 横展開チェックリスト 4 行追記
- 残 1 行: processor Lambda の `proc_storage.py` にも `_dynamo_safe` 相当を適用 (次セッション以降)

**関連 PR**: #114 (実装) / #110 (auto-merge.yml: T2026-0501-N 完了で連鎖デプロイの自動化が landing 済だったため無人完走できた)

---

### T2026-0501-N — PR auto-merge workflow

**完了** (2026-05-02 01:30 JST、PR #110 merged、commit 2760533f)

`.github/workflows/auto-merge.yml` で `pull_request` イベントに連動し `gh pr merge --auto --squash --delete-branch` を発動。draft PR 除外 + 作成者がリポジトリ owner と一致する PR のみ。

**Verified-Effect (2026-05-02 02:06 UTC)**: PR #114 (T2026-0502-G fetcher 修正) を Eng Claude が作成→ auto-merge.yml が squash merge を発動→ Lambda 自動デプロイ→ topics.json 復旧、の連鎖が無人で完走した実績で確認。

---

> このファイルは新しいエントリほど上に追記する。月単位でセクション区切り。
