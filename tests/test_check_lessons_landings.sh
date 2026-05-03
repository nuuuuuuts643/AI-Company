#!/usr/bin/env bash
# tests/test_check_lessons_landings.sh — T2026-0502-BL
#
# check_lessons_landings.sh の各 landing grep が placeholder ファイルを reject し、
# 実装済みファイルを pass することを検証。
#
# テスト戦略:
#   1. 各 landing の grep パターンを placeholder (#!/bin/bash\nexit 0 のみ) に適用 → 失敗を assert
#   2. 各 landing の grep パターンを実際のファイルに適用 → 成功を assert
#   3. check_lessons_landings.sh 全体を実行して exit 0 を確認 (regression guard)
#
# Exit codes:
#   0: all tests passed
#   1: one or more tests failed

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0

pass() { echo "✅ $1"; PASS=$((PASS + 1)); }
fail() { echo "❌ $1"; FAIL=$((FAIL + 1)); }

# placeholder: 実装なしの shell script
PLACEHOLDER=$(mktemp)
cat > "$PLACEHOLDER" <<'EOF'
#!/bin/bash
# placeholder — implements nothing
exit 0
EOF
trap 'rm -f "$PLACEHOLDER"' EXIT

echo "=== check_lessons_landings.sh landing grep 強化テスト (T2026-0502-BL) ==="
echo ""

# ---------------------------------------------------------------------------
# 1. PR #159: session_bootstrap.sh の BOOTSTRAP_EXIT=1 / PIPESTATUS[0]
# ---------------------------------------------------------------------------
SBS="$REPO_ROOT/scripts/session_bootstrap.sh"
echo "--- PR #159: session_bootstrap.sh ---"

if grep -q 'PIPESTATUS\[0\]' "$SBS"; then
  pass "PR#159: PIPESTATUS[0] exists in session_bootstrap.sh"
else
  fail "PR#159: PIPESTATUS[0] missing in session_bootstrap.sh"
fi

if ! grep -q 'PIPESTATUS\[0\]' "$PLACEHOLDER"; then
  pass "PR#159: placeholder correctly lacks PIPESTATUS[0] (grep rejects placeholder)"
else
  fail "PR#159: placeholder unexpectedly contains PIPESTATUS[0]"
fi

if grep -q 'BOOTSTRAP_EXIT=1' "$SBS"; then
  pass "PR#159: BOOTSTRAP_EXIT=1 exists in session_bootstrap.sh"
else
  fail "PR#159: BOOTSTRAP_EXIT=1 missing in session_bootstrap.sh"
fi

if ! grep -q 'BOOTSTRAP_EXIT=1' "$PLACEHOLDER"; then
  pass "PR#159: placeholder correctly lacks BOOTSTRAP_EXIT=1 (grep rejects placeholder)"
else
  fail "PR#159: placeholder unexpectedly contains BOOTSTRAP_EXIT=1"
fi

if grep -qE '_git_(pull|push)_status.*-ne[ ]+0' "$SBS"; then
  pass "PR#159: _git_pull/push_status exit 経路 exists in session_bootstrap.sh"
else
  fail "PR#159: _git_pull/push_status exit 経路 missing in session_bootstrap.sh"
fi

if ! grep -qE '_git_(pull|push)_status.*-ne[ ]+0' "$PLACEHOLDER"; then
  pass "PR#159: placeholder correctly lacks _git_*_status exit 経路 (grep rejects placeholder)"
else
  fail "PR#159: placeholder unexpectedly contains _git_*_status exit 経路"
fi

echo ""

# ---------------------------------------------------------------------------
# 2. PR #160: install_hooks.sh の refs/heads/main / ALLOW_MAIN_PUSH
# ---------------------------------------------------------------------------
INSH="$REPO_ROOT/scripts/install_hooks.sh"
echo "--- PR #160: install_hooks.sh ---"

if grep -q 'refs/heads/main' "$INSH"; then
  pass "PR#160: refs/heads/main exists in install_hooks.sh"
else
  fail "PR#160: refs/heads/main missing in install_hooks.sh"
fi

if ! grep -q 'refs/heads/main' "$PLACEHOLDER"; then
  pass "PR#160: placeholder correctly lacks refs/heads/main (grep rejects placeholder)"
else
  fail "PR#160: placeholder unexpectedly contains refs/heads/main"
fi

if grep -q 'ALLOW_MAIN_PUSH' "$INSH"; then
  pass "PR#160: ALLOW_MAIN_PUSH exists in install_hooks.sh"
else
  fail "PR#160: ALLOW_MAIN_PUSH missing in install_hooks.sh"
fi

if ! grep -q 'ALLOW_MAIN_PUSH' "$PLACEHOLDER"; then
  pass "PR#160: placeholder correctly lacks ALLOW_MAIN_PUSH (grep rejects placeholder)"
else
  fail "PR#160: placeholder unexpectedly contains ALLOW_MAIN_PUSH"
fi

echo ""

# ---------------------------------------------------------------------------
# 3. T2026-0502-DEPLOY-WATCHDOG: check_lambda_freshness.sh の THRESHOLD_SEC
# ---------------------------------------------------------------------------
CLF="$REPO_ROOT/scripts/check_lambda_freshness.sh"
echo "--- T2026-0502-DEPLOY-WATCHDOG: check_lambda_freshness.sh ---"

if grep -q 'THRESHOLD_SEC' "$CLF"; then
  pass "DEPLOY-WATCHDOG: THRESHOLD_SEC exists in check_lambda_freshness.sh"
else
  fail "DEPLOY-WATCHDOG: THRESHOLD_SEC missing in check_lambda_freshness.sh"
fi

if ! grep -q 'THRESHOLD_SEC' "$PLACEHOLDER"; then
  pass "DEPLOY-WATCHDOG: placeholder correctly lacks THRESHOLD_SEC (grep rejects placeholder)"
else
  fail "DEPLOY-WATCHDOG: placeholder unexpectedly contains THRESHOLD_SEC"
fi

echo ""

# ---------------------------------------------------------------------------
# 4. T2026-0502-DEPLOY-WATCHDOG: deploy-trigger-watchdog.yml の deploy-lambdas 参照
# ---------------------------------------------------------------------------
DTW="$REPO_ROOT/.github/workflows/deploy-trigger-watchdog.yml"
echo "--- T2026-0502-DEPLOY-WATCHDOG: deploy-trigger-watchdog.yml ---"

if grep -q 'deploy-lambdas' "$DTW"; then
  pass "DEPLOY-WATCHDOG: deploy-lambdas reference exists in deploy-trigger-watchdog.yml"
else
  fail "DEPLOY-WATCHDOG: deploy-lambdas reference missing in deploy-trigger-watchdog.yml"
fi

PLACEHOLDER_YML=$(mktemp)
cat > "$PLACEHOLDER_YML" <<'EOF'
name: placeholder
on: workflow_dispatch
jobs:
  placeholder:
    runs-on: ubuntu-latest
    steps:
      - run: echo "placeholder"
EOF
trap 'rm -f "$PLACEHOLDER" "$PLACEHOLDER_YML"' EXIT

if ! grep -q 'deploy-lambdas' "$PLACEHOLDER_YML"; then
  pass "DEPLOY-WATCHDOG: placeholder yml correctly lacks deploy-lambdas (grep rejects placeholder)"
else
  fail "DEPLOY-WATCHDOG: placeholder yml unexpectedly contains deploy-lambdas"
fi

echo ""

# ---------------------------------------------------------------------------
# 5. T2026-0502-DEPLOY-WATCHDOG: lambda-freshness-monitor.yml の check_lambda_freshness 参照
# ---------------------------------------------------------------------------
LFM="$REPO_ROOT/.github/workflows/lambda-freshness-monitor.yml"
echo "--- T2026-0502-DEPLOY-WATCHDOG: lambda-freshness-monitor.yml ---"

if grep -q 'check_lambda_freshness' "$LFM"; then
  pass "DEPLOY-WATCHDOG: check_lambda_freshness reference exists in lambda-freshness-monitor.yml"
else
  fail "DEPLOY-WATCHDOG: check_lambda_freshness reference missing in lambda-freshness-monitor.yml"
fi

if ! grep -q 'check_lambda_freshness' "$PLACEHOLDER_YML"; then
  pass "DEPLOY-WATCHDOG: placeholder yml correctly lacks check_lambda_freshness (grep rejects placeholder)"
else
  fail "DEPLOY-WATCHDOG: placeholder yml unexpectedly contains check_lambda_freshness"
fi

echo ""

# ---------------------------------------------------------------------------
# 6. T2026-0502-DEPLOY-WATCHDOG: tests/test_lambda_freshness.sh の check_lambda_freshness.sh 参照
# ---------------------------------------------------------------------------
TLF="$REPO_ROOT/tests/test_lambda_freshness.sh"
echo "--- T2026-0502-DEPLOY-WATCHDOG: tests/test_lambda_freshness.sh ---"

if grep -q 'check_lambda_freshness.sh' "$TLF"; then
  pass "DEPLOY-WATCHDOG: check_lambda_freshness.sh reference exists in test_lambda_freshness.sh"
else
  fail "DEPLOY-WATCHDOG: check_lambda_freshness.sh reference missing in test_lambda_freshness.sh"
fi

if ! grep -q 'check_lambda_freshness.sh' "$PLACEHOLDER"; then
  pass "DEPLOY-WATCHDOG: placeholder correctly lacks check_lambda_freshness.sh reference (grep rejects placeholder)"
else
  fail "DEPLOY-WATCHDOG: placeholder unexpectedly contains check_lambda_freshness.sh reference"
fi

echo ""

# ---------------------------------------------------------------------------
# 7. T2026-0502-MU-FOLLOWUP: quality_heal.py の find_mode_mismatch_topics
# ---------------------------------------------------------------------------
QHP="$REPO_ROOT/scripts/quality_heal.py"
echo "--- T2026-0502-MU-FOLLOWUP: quality_heal.py ---"

if grep -q 'find_mode_mismatch_topics' "$QHP"; then
  pass "MU-FOLLOWUP: find_mode_mismatch_topics exists in quality_heal.py"
else
  fail "MU-FOLLOWUP: find_mode_mismatch_topics missing in quality_heal.py"
fi

if ! grep -q 'find_mode_mismatch_topics' "$PLACEHOLDER"; then
  pass "MU-FOLLOWUP: placeholder correctly lacks find_mode_mismatch_topics (grep rejects placeholder)"
else
  fail "MU-FOLLOWUP: placeholder unexpectedly contains find_mode_mismatch_topics"
fi

echo ""

# ---------------------------------------------------------------------------
# 8. T2026-0502-MU-FOLLOWUP: test_quality_heal_mode_upgrade.py の find_mode_mismatch_topics テスト
# ---------------------------------------------------------------------------
TQHM="$REPO_ROOT/tests/test_quality_heal_mode_upgrade.py"
echo "--- T2026-0502-MU-FOLLOWUP: test_quality_heal_mode_upgrade.py ---"

if grep -q 'find_mode_mismatch_topics' "$TQHM"; then
  pass "MU-FOLLOWUP: find_mode_mismatch_topics test exists in test_quality_heal_mode_upgrade.py"
else
  fail "MU-FOLLOWUP: find_mode_mismatch_topics test missing in test_quality_heal_mode_upgrade.py"
fi

PLACEHOLDER_PY=$(mktemp)
cat > "$PLACEHOLDER_PY" <<'EOF'
# placeholder test file
def test_placeholder():
    pass
EOF
trap 'rm -f "$PLACEHOLDER" "$PLACEHOLDER_YML" "$PLACEHOLDER_PY"' EXIT

if ! grep -q 'find_mode_mismatch_topics' "$PLACEHOLDER_PY"; then
  pass "MU-FOLLOWUP: placeholder py correctly lacks find_mode_mismatch_topics test (grep rejects placeholder)"
else
  fail "MU-FOLLOWUP: placeholder py unexpectedly contains find_mode_mismatch_topics"
fi

echo ""

# ---------------------------------------------------------------------------
# 9. T2026-0502-WORKFLOW-DEP-PHYSICAL: ci_check_workflow_script_refs.sh の実装パターン
# ---------------------------------------------------------------------------
CWS="$REPO_ROOT/scripts/ci_check_workflow_script_refs.sh"
echo "--- T2026-0502-WORKFLOW-DEP-PHYSICAL: ci_check_workflow_script_refs.sh ---"

if grep -qE 'python3\?|bash.*scripts/' "$CWS"; then
  pass "WORKFLOW-DEP-PHYSICAL: workflow ref detection pattern exists in ci_check_workflow_script_refs.sh"
else
  fail "WORKFLOW-DEP-PHYSICAL: workflow ref detection pattern missing in ci_check_workflow_script_refs.sh"
fi

if ! grep -qE 'python3\?|bash.*scripts/' "$PLACEHOLDER"; then
  pass "WORKFLOW-DEP-PHYSICAL: placeholder correctly lacks workflow ref detection pattern (grep rejects placeholder)"
else
  fail "WORKFLOW-DEP-PHYSICAL: placeholder unexpectedly contains workflow ref detection pattern"
fi

echo ""

# ---------------------------------------------------------------------------
# 10. Regression guard: check_lessons_landings.sh 全体が exit 0 で終わること
# ---------------------------------------------------------------------------
echo "--- Regression guard: check_lessons_landings.sh 全体実行 ---"

if bash "$REPO_ROOT/scripts/check_lessons_landings.sh" > /dev/null 2>&1; then
  pass "check_lessons_landings.sh exits 0 (all landings verified)"
else
  fail "check_lessons_landings.sh exits non-zero — landing check failed"
  echo "  詳細:" >&2
  bash "$REPO_ROOT/scripts/check_lessons_landings.sh" >&2 || true
fi

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="

[ $FAIL -eq 0 ] || exit 1
