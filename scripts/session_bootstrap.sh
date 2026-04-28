#!/bin/bash
# AI-Company セッション起動チェック（Code/Cowork 共通）
# 用途: 各セッションが冒頭で 1 回だけ呼ぶ。冪等。
# 仕様: CLAUDE.md「セッション開始時に必ず最初に実行すること」を 1 コマンドに集約。
#
# やること:
#   1. git lock / rebase-merge を _garbage に退避（FUSE rm 不可環境向け）
#   2. ローカル変更を sync commit して remote と同期（push）
#   3. CLAUDE.md の最近の commit を表示（変更検知）
#   4. WORKING.md の stale (8h 超) 行を自動削除
#   5. TASKS.md の取消線済み (`~~T...~~`) 行を HISTORY.md に集約移動
#   6. needs-push:yes が WORKING.md に残っていれば最優先で警告
#   7. 1 行サマリ「✅ 起動チェック完了」を出力
#
# 失敗してもセッション続行できるよう、各ステップは ` || true ` で吸収する。

set -u

# ---- 0. --dry-run フラグ検知（T2026-0428-K）----
# CI で REPO 検出 / JST 表示 / WORKING.md 未来日付 stale 検出ロジックを
# git push / commit / file mutation なしで物理 test するためのモード。
# 副作用ある操作（lock 退避・git pull/push/commit・triage_tasks 実行）を全 skip し、
# 読み取り専用の検査だけ走らせて exit code を返す。
DRY_RUN=0
case " $* " in *" --dry-run "*) DRY_RUN=1 ;; esac

# REPO 検出（優先度順）:
#   1. 環境変数 REPO （明示指定があれば最優先）
#   2. Mac 標準 path （Code セッション）
#   3. Cowork VM mount path （session ID は毎回変わるため glob で検出）
# 過去の bug: ハードコードされた session ID (`/sessions/<old-id>/mnt/...`) が
# 新セッションでは存在せず「❌ repo not found」で起動チェック自体が失敗した。
# 修正: glob で `/sessions/*/mnt/ai-company` を探索し、最初に見つかったものを使う。
REPO="${REPO:-}"
if [ -z "$REPO" ] || [ ! -d "$REPO" ]; then
  REPO=""
  if [ -d "/Users/OWNER/ai-company" ]; then
    REPO="/Users/OWNER/ai-company"
  else
    # Cowork VM 環境: session ID は不定なので glob で発見
    for cand in /sessions/*/mnt/ai-company; do
      if [ -d "$cand" ]; then
        REPO="$cand"
        break
      fi
    done
  fi
fi
[ -d "$REPO" ] || { echo "❌ repo not found (REPO=$REPO)"; exit 1; }
cd "$REPO"

if [ "$DRY_RUN" = "0" ]; then
  mkdir -p .git/_garbage 2>/dev/null
fi

# ---- 1. lock / rebase-merge 退避（堅牢化）----
# FUSE 環境では rm が permission denied なので mv で _garbage に逃がす。
# mv も失敗する場合があるため複数回トライ。
# DRY_RUN=1 では mutation せず、ロックの存在のみ報告する。
if [ "$DRY_RUN" = "1" ]; then
  for lock in .git/index.lock .git/HEAD.lock .git/objects/maintenance.lock .git/rebase-merge .git/rebase-apply; do
    [ -e "$lock" ] && echo "[DRY-RUN] would relocate: $lock"
  done
else
  for i in 1 2 3; do
    found_any=0
    for lock in .git/index.lock .git/HEAD.lock .git/objects/maintenance.lock; do
      [ -e "$lock" ] || continue
      found_any=1
      mv "$lock" ".git/_garbage/$(basename $lock).$(date +%s%N)" 2>/dev/null || true
    done
    if [ -d .git/rebase-merge ]; then
      found_any=1
      mv .git/rebase-merge ".git/_garbage/rebase-merge.$(date +%s%N)" 2>/dev/null || true
    fi
    if [ -d .git/rebase-apply ]; then
      found_any=1
      mv .git/rebase-apply ".git/_garbage/rebase-apply.$(date +%s%N)" 2>/dev/null || true
    fi
    [ "$found_any" -eq 0 ] && break
    sleep 1
  done
fi

# ---- 2. sync commit & pull --no-rebase & push ----
# rebase 系の中断を作らないため pull は merge 戦略で固定。
#
# FUSE 環境では git fetch/pull/push が以下の "harmless noise" を吐く:
#   - "may have crashed in this repository earlier:" / "remove the file manually to continue."
#   - "warning: unable to unlink '...': Operation not permitted"
#   - "! refs/remotes/origin/main: unable to update local ref"
# これらは _garbage 退避ロジックで実害ゼロ。Claude のコンテキストを汚染するだけなので
# grep -v で物理的に弾く (LANG=C で英語固定。i18n 環境でも安定)。
# 実害ある warning/error は素通しする (フィルタは substring 一致のみ・正規表現使わない)。
_strip_fuse_noise() {
  # FUSE 環境 + 並行セッション起因の "実害ゼロ noise" のみ落とす。
  # 実害ある warning/error (push 失敗・auth・network など) は通すこと。
  # 追加する場合は「実害が無い・mv/_garbage で吸収済」と確認してから入れる。
  LANG=C grep -v -e 'may have crashed in this repository earlier' \
                 -e 'remove the file manually to continue' \
                 -e "warning: unable to unlink" \
                 -e ': unable to update local ref' \
                 -e "an editor opened by 'git commit'" \
                 -e 'are terminated then try again' \
                 -e 'Another git process seems to be running' \
                 -e "error: cannot lock ref 'refs/remotes/" \
                 -e "error: update_ref failed for ref 'refs/remotes/" \
                 -e "Unable to create '.*\.lock': File exists" \
    | sed -E '/^[[:space:]]*$/d; /^ \! .*unable to update local ref/d' \
    || true
}
if [ "$DRY_RUN" = "1" ]; then
  echo "[DRY-RUN] skip: git add/commit/pull/push"
else
  git add -A 2>/dev/null
  if ! git diff --cached --quiet 2>/dev/null; then
    git commit -m "chore: bootstrap sync $(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M JST')" 2>/dev/null || true
  fi
  git pull --no-rebase --no-edit origin main 2>&1 | _strip_fuse_noise | tail -2 || true
  mv .git/index.lock .git/_garbage/ 2>/dev/null
  git push 2>&1 | _strip_fuse_noise | tail -2 || true
fi

# ---- 3. CLAUDE.md 変更検知 ----
LATEST_CLAUDE=$(git log --oneline -1 -- CLAUDE.md 2>/dev/null || echo "(none)")

# ---- 3b. product-direction.md 表示 ----
# セッション切れで方針が消える問題への恒久対策。毎回フルテキストを表示し、
# Claude が起動直後に現在のプロダクト方針を必ずコンテキストに入れる。
if [ -f "docs/product-direction.md" ]; then
  echo ""
  echo "=== 現在のプロダクト方針 (docs/product-direction.md) ==="
  cat docs/product-direction.md
  echo "======================================================="
fi

# ---- 3c. project-phases.md 表示 (現在フェーズ・完了条件の確認) ----
# タスク単位の管理に加え、案件・機能要件 (Epic) の階層を毎回確認する。
if [ -f "docs/project-phases.md" ]; then
  echo ""
  echo "=== プロジェクト・フェーズ階層 (docs/project-phases.md 先頭30行) ==="
  head -30 docs/project-phases.md
  echo "==================================================================="
fi

# ---- 4. WORKING.md 8h stale 自動削除 ----
# DRY_RUN=1 では triage 実行を skip（mutation 回避）。WORKING.md の存在のみ確認。
if [ "$DRY_RUN" = "1" ]; then
  if [ -f WORKING.md ]; then
    echo "[DRY-RUN] WORKING.md exists ($(wc -l < WORKING.md) lines) — would run triage_tasks.py --clean-working-md"
  fi
else
  if [ -f WORKING.md ] && [ -x scripts/triage_tasks.py ]; then
    python3 scripts/triage_tasks.py --clean-working-md 2>/dev/null || true
  fi
fi

# ---- 5. TASKS.md 取消線→HISTORY.md ----
if [ "$DRY_RUN" = "1" ]; then
  if [ -f TASKS.md ]; then
    echo "[DRY-RUN] TASKS.md exists ($(wc -l < TASKS.md) lines) — would run triage_tasks.py --triage-tasks"
  fi
else
  if [ -f TASKS.md ] && [ -x scripts/triage_tasks.py ]; then
    python3 scripts/triage_tasks.py --triage-tasks 2>/dev/null || true
  fi
fi

# ---- 5b. (HISTORY 確認要) 行を HISTORY.md と突合して自動取消線化 (T2026-0428-H) ----
# 「実装済の可能性あり (HISTORY 確認要)」のままタスク再起票 anti-pattern を物理化対策。
# scheduled-task の発見偏重バイアス対策の一環 (lessons-learned 2026-04-28 由来)。
if [ "$DRY_RUN" = "0" ]; then
  if [ -f TASKS.md ] && [ -f HISTORY.md ] && [ -x scripts/triage_implemented_likely.py ]; then
    python3 scripts/triage_implemented_likely.py 2>/dev/null || true
  fi
fi

# ---- 6. needs-push 警告 ----
# 「現在着手中」セクションのテーブル本体行のうち、最終セルが yes のものだけを拾う。
# 説明文・引用・記入フォーマット例 を誤検出しないよう awk で厳密化する。
# (旧: `grep -nE 'needs-push.*\<yes\>'` は規則の解説文を毎回拾い、警告がノイズで埋没していた)
NEEDS_PUSH=$(awk '
  /^## 現在着手中/        { in_sec=1; next }
  /^## /                  { in_sec=0 }
  in_sec && /^\|/ && /\| *yes( *\| *)?$/ { printf "%d:%s\n", NR, $0 }
' WORKING.md 2>/dev/null || true)

# ---- 6b. 並行タスク行カウント (T2026-0428-X / P0-STABLE-C / T2026-0428-BB) ----
# 「現在着手中」テーブル本体行だけを数える。ヘッダ行 (`| タスク名 |...`) と
# 区切り行 (`|---|---|`) を除外して、本物のタスク行のみカウント。
# 2026-04-28 PM (T2026-0428-BB): [Code] 並走 ≥2 を WARNING ではなく ERROR で出すように昇格。
# Dispatch 同時 1 件ルール (CLAUDE.md ⚡ Cowork↔Code 連携セクション「セッション並走ルール」) を物理担保。
CONCURRENT_TASKS=$(awk '
  /^## 現在着手中/        { in_sec=1; next }
  /^## /                  { in_sec=0 }
  in_sec && /^\|/ && !/^\| *タスク名/ && !/^\|[ \-]*\|[ \-]*\|/ { count++ }
  END { print count + 0 }
' WORKING.md 2>/dev/null || echo 0)

# [Code] プレフィックス行のみカウント — Dispatch 並走ルール用
CODE_CONCURRENT=$(awk '
  /^## 現在着手中/        { in_sec=1; next }
  /^## /                  { in_sec=0 }
  in_sec && /^\| *\[Code\]/ { count++ }
  END { print count + 0 }
' WORKING.md 2>/dev/null || echo 0)

# ---- 6c. コードセッション名規則 WARN (T2026-0428-BF) ----
# WORKING.md の [Code] 行のタスク名が空抽象タイトル（「作業」「調査」「タスク」「着手」単体等）
# だった場合、何を commit するかが不明確のまま走り出すため WARN する。
# project-phases.md §C 「コードセッション名規則の徹底」を物理担保。
ABSTRACT_TITLES=$(awk -F'|' '
  /^## 現在着手中/        { in_sec=1; next }
  /^## /                  { in_sec=0 }
  in_sec && /^\| *\[Code\]/ {
    name=$2
    gsub(/^[ \t]+|[ \t]+$/, "", name)
    # [Code] プレフィックスを除去して中身チェック
    sub(/^\[Code\][ 　]*/, "", name)
    # 抽象語のみ or 5 文字以下 or 「作業/調査/タスク/着手/wip/test/対応/確認/対応中」のみ
    if (length(name) <= 5) { print name; next }
    if (name ~ /^(作業|調査|タスク|着手|wip|WIP|test|TEST|対応|確認|対応中|チェック|修正)([ 　:：]|$)/) { print name; next }
    if (name ~ /^(作業|調査|タスク|着手|wip|WIP|test|TEST|対応|確認|対応中|チェック|修正)$/) { print name }
  }
' WORKING.md 2>/dev/null || true)

# ---- 6.5 schedule-task モード検知 ----
# `SCHEDULE_TASK=1` または引数 `--schedule` を渡された場合、
# scheduled-task-protocol.md と最優先 unblocked タスク 1 件を強調表示する。
# Claude が起動チェック直後にこの 1 件を見るため、発見前に実装着手を考えさせる狙い。
SCHED=0
case " $* " in *" --schedule "*) SCHED=1 ;; esac
[ "${SCHEDULE_TASK:-0}" = "1" ] && SCHED=1

# 最優先 unblocked task: TASKS.md「🔥 今週やること」テーブルの先頭から ~~ で取消線化
# されていない最初の行を抽出する（簡易ヒューリスティック）。
TOP_TASK=""
if [ -f TASKS.md ]; then
  TOP_TASK=$(awk '
    /^## 🔥/ { in_main=1; next }
    /^## / && in_main { exit }
    in_main && /^\| *T[0-9A-Za-z\-]+ *\|/ && $0 !~ /~~T/ { print; exit }
  ' TASKS.md 2>/dev/null || true)
fi

# 確定済み決定の期限チェック
bash "$(dirname "$0")/check_decisions.sh" || true

# ---- 6.6 繰り返し失敗パターン検出 (T2026-0429-D) ----
# 目的: 「POがたまたま git 見たら同じエラーが繰り返されてた」を物理検出。
# 仕様: gh CLI で workflow run 連続失敗、HISTORY.md でカテゴリ偏り。
# 制約: 各 script は内部で gh 不在 / HISTORY.md 不在を吸収し exit 0 で抜ける。
#       時間予算は両方合計 ~3 秒以内 (gh は TIMEOUT_SEC=4 で打ち切り)。
REPEAT_FAIL=$(bash "$(dirname "$0")/detect_repeated_failures.sh" 2>/dev/null || true)
TASK_PATTERN=$(bash "$(dirname "$0")/analyze_task_patterns.sh" 2>/dev/null || true)

# ---- 7. サマリ出力 ----
echo "─────────────────────────────────────────"
if [ "$DRY_RUN" = "1" ]; then
  echo "✅ [DRY-RUN] 起動チェック完了 ($(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M JST'))"
  echo "  REPO=$REPO"
else
  echo "✅ 起動チェック完了 ($(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M JST'))"
fi
echo "  CLAUDE.md latest: $LATEST_CLAUDE"
if [ -n "$NEEDS_PUSH" ]; then
  echo "  ⚠️ needs-push 滞留:"
  echo "$NEEDS_PUSH" | sed 's/^/    /'
fi
if [ "${CONCURRENT_TASKS:-0}" -ge 3 ]; then
  echo "  ⚠️ WORKING.md 並行タスク行 ${CONCURRENT_TASKS} 件 (≥3) — lock 競合・重複作業の可能性。各行の開始JST/needs-push を確認すること"
fi
# コードセッション名規則 WARN (T2026-0428-BF)
if [ -n "$ABSTRACT_TITLES" ]; then
  echo "  ⚠️ WARN: [Code] セッション名が抽象的すぎる行を検出"
  echo "$ABSTRACT_TITLES" | sed 's/^/      → /'
  echo "     セッション名は「何を commit するか」が一目で分かる名前にする"
  echo "     ✅ 例: 「CI 構文チェック fix」「T2026-0428-BD 形骸化 grep CI」"
  echo "     ❌ 例: 「調査」「作業」「タスク」「対応」"
fi
# Dispatch 並走ルール: [Code] が同時 2 件以上は ERROR (T2026-0428-BB)
if [ "${CODE_CONCURRENT:-0}" -ge 2 ]; then
  echo "  ❌ ERROR: WORKING.md [Code] セッションが ${CODE_CONCURRENT} 件並走中 (≥2)"
  echo "     Dispatch ルール: コードセッションは同時 1 件まで (CLAUDE.md ⚡ Cowork↔Code 連携セクション)"
  echo "     対応: 完了済みセッション行を削除 → push してから新規セッション開始"
  # 環境変数 ALLOW_CONCURRENT_CODE=1 で bypass 可能 (緊急のみ)
  if [ "${ALLOW_CONCURRENT_CODE:-0}" != "1" ]; then
    echo "     bypass (緊急のみ): ALLOW_CONCURRENT_CODE=1 bash scripts/session_bootstrap.sh"
    BOOTSTRAP_EXIT=1
  fi
fi
if [ "$SCHED" = "1" ]; then
  echo ""
  echo "  📋 schedule-task モード:"
  echo "    1. cat docs/rules/scheduled-task-protocol.md を必ず読んでから動く"
  echo "    2. 探索 → 実装 1 件以上 → 報告（フェーズ順序固定）"
  echo "    3. commit message に [Schedule-KPI] implemented=N created=M closed=K queue_delta=±X 行を含める（commit-msg hook で物理強制）"
  if [ -n "$TOP_TASK" ]; then
    echo ""
    echo "  🎯 最優先 unblocked タスク (このセッションで実装候補):"
    echo "$TOP_TASK" | sed 's/^/    /'
  fi
fi
# T2026-0429-D: 繰り返し失敗の自動可視化 (gh / HISTORY.md ベース)
if [ -n "${REPEAT_FAIL:-}" ]; then
  echo "$REPEAT_FAIL" | sed 's/^/  /'
fi
if [ -n "${TASK_PATTERN:-}" ]; then
  echo "$TASK_PATTERN" | sed 's/^/  /'
fi
echo "  次の TASKS.md 着手: cat TASKS.md で未着手を確認"
echo "─────────────────────────────────────────"

# Dispatch 並走 ERROR が出ていれば exit 1 で物理ブロック (T2026-0428-BB)
if [ "${BOOTSTRAP_EXIT:-0}" -ne 0 ]; then
  exit "$BOOTSTRAP_EXIT"
fi
exit 0
