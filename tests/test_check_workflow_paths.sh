#!/usr/bin/env bash
# test_check_workflow_paths.sh — T2026-0502-WORKFLOW-PATH-LINT
# Boundary tests for scripts/check_workflow_paths.sh
#
# Exit codes:
#   0: all tests passed
#   1: one or more tests failed

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CHECK_SCRIPT="$REPO_ROOT/scripts/check_workflow_paths.sh"
FIXTURES_DIR="$SCRIPT_DIR/fixtures/workflow-yml"

PASS=0
FAIL=0

run_test() {
    local name="$1"
    local fixture_file="$2"
    local expected_exit="$3"

    # Run the check script against a temp dir containing only this fixture
    local tmp_dir
    tmp_dir=$(mktemp -d)
    cp "$FIXTURES_DIR/$fixture_file" "$tmp_dir/"

    local actual_exit=0
    WORKFLOW_PATH_CHECK_DIR="$tmp_dir" bash "$CHECK_SCRIPT" > /dev/null 2>&1 || actual_exit=$?
    rm -rf "$tmp_dir"

    if [ "$actual_exit" -eq "$expected_exit" ]; then
        echo "  ✅ $name (exit=$actual_exit)"
        PASS=$((PASS + 1))
    else
        echo "  ❌ $name: expected exit=$expected_exit, got exit=$actual_exit"
        FAIL=$((FAIL + 1))
    fi
}

echo "=== test_check_workflow_paths.sh boundary tests ==="
echo ""

# ケース①: clean workflow → exit 0
run_test "ケース① clean workflow は exit 0" "clean.yml" 0

# ケース②: cd subdir + relative path → exit 1
run_test "ケース② cd subdir + relative scripts/ path は exit 1" "bad_relpath.yml" 1

# ケース③: cd subdir + absolute \$GITHUB_WORKSPACE path → exit 0
run_test "ケース③ cd subdir + \$GITHUB_WORKSPACE 絶対パスは exit 0" "safe_absolute.yml" 0

# ケース④: cd subdir → cd \$GITHUB_WORKSPACE → relative path → exit 0
run_test "ケース④ cd \$GITHUB_WORKSPACE でリセット後の相対パスは exit 0" "safe_cd_workspace.yml" 0

# ケース⑤: cd subdir → cd .. → relative path → exit 1 (false positive OK per spec)
run_test "ケース⑤ cd .. 後の相対パスは exit 1 (false positive 許容)" "bad_dotdot.yml" 1

# ケース⑥: mixed (clean + bad steps) → exit 1
run_test "ケース⑥ 複数 workflow yml 混在で 1 件でも bad → exit 1" "mixed.yml" 1

echo ""
echo "=== 結果: PASS=$PASS FAIL=$FAIL ==="
if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
exit 0
