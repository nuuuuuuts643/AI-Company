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
REPO="${REPO:-/Users/OWNER/ai-company}"
[ -d "$REPO" ] || REPO="/sessions/keen-optimistic-keller/mnt/ai-company"
[ -d "$REPO" ] || { echo "❌ repo not found"; exit 1; }
cd "$REPO"

mkdir -p .git/_garbage 2>/dev/null

# ---- 1. lock / rebase-merge 退避（堅牢化）----
# FUSE 環境では rm が permission denied なので mv で _garbage に逃がす。
# mv も失敗する場合があるため複数回トライ。
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

# ---- 2. sync commit & pull --no-rebase & push ----
# rebase 系の中断を作らないため pull は merge 戦略で固定。
git add -A 2>/dev/null
if ! git diff --cached --quiet 2>/dev/null; then
  git commit -m "chore: bootstrap sync $(date '+%Y-%m-%d %H:%M JST')" 2>/dev/null || true
fi
git pull --no-rebase --no-edit origin main 2>&1 | tail -2 || true
mv .git/index.lock .git/_garbage/ 2>/dev/null
git push 2>&1 | tail -2 || true

# ---- 3. CLAUDE.md 変更検知 ----
LATEST_CLAUDE=$(git log --oneline -1 -- CLAUDE.md 2>/dev/null || echo "(none)")

# ---- 4. WORKING.md 8h stale 自動削除 ----
if [ -f WORKING.md ] && [ -x scripts/triage_tasks.py ]; then
  python3 scripts/triage_tasks.py --clean-working-md 2>/dev/null || true
fi

# ---- 5. TASKS.md 取消線→HISTORY.md ----
if [ -f TASKS.md ] && [ -x scripts/triage_tasks.py ]; then
  python3 scripts/triage_tasks.py --triage-tasks 2>/dev/null || true
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

# ---- 7. サマリ出力 ----
echo "─────────────────────────────────────────"
echo "✅ 起動チェック完了 ($(date '+%Y-%m-%d %H:%M JST'))"
echo "  CLAUDE.md latest: $LATEST_CLAUDE"
if [ -n "$NEEDS_PUSH" ]; then
  echo "  ⚠️ needs-push 滞留:"
  echo "$NEEDS_PUSH" | sed 's/^/    /'
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
echo "  次の TASKS.md 着手: cat TASKS.md で未着手を確認"
echo "─────────────────────────────────────────"
