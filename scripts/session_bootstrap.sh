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
git add -A 2>/dev/null
if ! git diff --cached --quiet 2>/dev/null; then
  git commit -m "chore: bootstrap sync $(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M JST')" 2>/dev/null || true
fi
git pull --no-rebase --no-edit origin main 2>&1 | _strip_fuse_noise | tail -2 || true
mv .git/index.lock .git/_garbage/ 2>/dev/null
git push 2>&1 | _strip_fuse_noise | tail -2 || true

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

# ---- 4. WORKING.md 8h stale 自動削除 ----
if [ -f WORKING.md ] && [ -x scripts/triage_tasks.py ]; then
  python3 scripts/triage_tasks.py --clean-working-md 2>/dev/null || true
fi

# ---- 5. TASKS.md 取消線→HISTORY.md ----
if [ -f TASKS.md ] && [ -x scripts/triage_tasks.py ]; then
  python3 scripts/triage_tasks.py --triage-tasks 2>/dev/null || true
fi

# ---- 5b. (HISTORY 確認要) 行を HISTORY.md と突合して自動取消線化 (T2026-0428-H) ----
# 「実装済の可能性あり (HISTORY 確認要)」のままタスク再起票 anti-pattern を物理化対策。
# scheduled-task の発見偏重バイアス対策の一環 (lessons-learned 2026-04-28 由来)。
if [ -f TASKS.md ] && [ -f HISTORY.md ] && [ -x scripts/triage_implemented_likely.py ]; then
  python3 scripts/triage_implemented_likely.py 2>/dev/null || true
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

# ---- 6b. 並行タスク行 ≥3 警告 (T2026-0428-X / P0-STABLE-C) ----
# 「現在着手中」テーブル本体行だけを数える。ヘッダ行 (`| タスク名 |...`) と
# 区切り行 (`|---|---|`) を除外して、本物のタスク行のみカウント。
# ≥3 で lock 競合・重複作業の早期検知警告を出す。
CONCURRENT_TASKS=$(awk '
  /^## 現在着手中/        { in_sec=1; next }
  /^## /                  { in_sec=0 }
  in_sec && /^\|/ && !/^\| *タスク名/ && !/^\|[ \-]*\|[ \-]*\|/ { count++ }
  END { print count + 0 }
' WORKING.md 2>/dev/null || echo 0)

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

# ---- 7. サマリ出力 ----
echo "─────────────────────────────────────────"
echo "✅ 起動チェック完了 ($(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M JST'))"
echo "  CLAUDE.md latest: $LATEST_CLAUDE"
if [ -n "$NEEDS_PUSH" ]; then
  echo "  ⚠️ needs-push 滞留:"
  echo "$NEEDS_PUSH" | sed 's/^/    /'
fi
if [ "${CONCURRENT_TASKS:-0}" -ge 3 ]; then
  echo "  ⚠️ WORKING.md 並行タスク行 ${CONCURRENT_TASKS} 件 (≥3) — lock 競合・重複作業の可能性。各行の開始JST/needs-push を確認すること"
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
