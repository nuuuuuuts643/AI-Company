#!/bin/bash
# T2026-0502-H boundary test: scripts/conflict_check.sh
# 仕様: shared docs (CLAUDE.md / WORKING.md / TASKS.md / HISTORY.md / docs/lessons-learned.md)
#       が UU 状態だったら exit 1。コードファイル UU のみ or UU 0 件は exit 0。
# mock: CONFLICT_CHECK_GIT_STATUS_OUTPUT 環境変数で git status --porcelain 出力を注入。
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TARGET_SCRIPT="$REPO_ROOT/scripts/conflict_check.sh"

[ -x "$TARGET_SCRIPT" ] || { echo "❌ target script not executable: $TARGET_SCRIPT"; exit 1; }

PASS=0
FAIL=0

# helper: case <name> <expected_exit> <git_status_output>
run_case() {
  local name="$1"
  local expected="$2"
  local input="$3"
  local actual_exit
  local stderr_output

  # script を mock で起動。stdout は捨てて stderr を取る。
  stderr_output=$(CONFLICT_CHECK_GIT_STATUS_OUTPUT="$input" bash "$TARGET_SCRIPT" 2>&1 >/dev/null)
  actual_exit=$?

  if [ "$actual_exit" = "$expected" ]; then
    echo "  ✅ $name (exit=$actual_exit)"
    PASS=$((PASS + 1))
  else
    echo "  ❌ $name (expected exit=$expected, got=$actual_exit)"
    echo "     --- stderr ---"
    echo "$stderr_output" | sed 's/^/     /'
    FAIL=$((FAIL + 1))
  fi
}

# helper: case + assert stderr contains substring
run_case_with_msg() {
  local name="$1"
  local expected="$2"
  local input="$3"
  local needle="$4"
  local actual_exit
  local stderr_output

  stderr_output=$(CONFLICT_CHECK_GIT_STATUS_OUTPUT="$input" bash "$TARGET_SCRIPT" 2>&1 >/dev/null)
  actual_exit=$?

  if [ "$actual_exit" = "$expected" ] && echo "$stderr_output" | grep -q "$needle"; then
    echo "  ✅ $name (exit=$actual_exit, stderr contains '$needle')"
    PASS=$((PASS + 1))
  else
    echo "  ❌ $name (expected exit=$expected with '$needle', got exit=$actual_exit)"
    echo "     --- stderr ---"
    echo "$stderr_output" | sed 's/^/     /'
    FAIL=$((FAIL + 1))
  fi
}

echo "=== test_conflict_check.sh ==="

# Case 1: UU 0 件 → exit 0
run_case "case1: UU 0 件" "0" ""

# Case 2: UU に CLAUDE.md だけ含む → exit 1
run_case_with_msg "case2: UU CLAUDE.md だけ" "1" "UU CLAUDE.md" "CLAUDE.md"

# Case 3: UU に lambda/foo.py のみ → exit 0 (shared docs 含まない)
run_case "case3: UU lambda/foo.py のみ" "0" "UU lambda/foo.py"

# Case 4: UU に WORKING.md と lambda/foo.py 両方 → exit 1 (shared docs 1 件でも stop)
run_case_with_msg "case4: UU WORKING.md + lambda/foo.py" "1" "UU WORKING.md
UU lambda/foo.py" "WORKING.md"

# Case 5: UU に docs/lessons-learned.md → exit 1
run_case_with_msg "case5: UU docs/lessons-learned.md" "1" "UU docs/lessons-learned.md" "lessons-learned.md"

# Case 6: 通常 modified ( M ) は無視 → exit 0 (UU 状態じゃない)
run_case "case6: M (modified) のみ → 無視" "0" " M CLAUDE.md
 M WORKING.md"

# Case 7: TASKS.md と HISTORY.md 両方 UU → exit 1 + どちらも報告
run_case_with_msg "case7: TASKS.md + HISTORY.md UU 同時" "1" "UU TASKS.md
UU HISTORY.md" "TASKS.md"

# Case 8: ERROR メッセージに 'docs/rules/conflict-resolution.md' リファレンスが含まれること
run_case_with_msg "case8: ERROR にルール文書リファレンス" "1" "UU CLAUDE.md" "docs/rules/conflict-resolution.md"

# Case 9: ERROR メッセージに 'upstream 採用禁止' 注意書きが含まれること
run_case_with_msg "case9: ERROR に upstream 採用禁止" "1" "UU CLAUDE.md" "upstream 採用禁止"

echo "---"
echo "Pass: $PASS / Fail: $FAIL"
[ "$FAIL" -eq 0 ] && echo "✅ test_conflict_check: PASS" && exit 0
echo "❌ test_conflict_check: FAIL" && exit 1
