#!/bin/bash
# check_lessons_landings.sh — T2026-0428-BC
# CI script to validate that all mitigations in docs/lessons-learned.md
# 横展開チェックリスト are actually implemented in the repo.

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LESSONS_FILE="${REPO_ROOT}/docs/lessons-learned.md"
PYTHON_SCRIPT=$(mktemp)

cat > "$PYTHON_SCRIPT" << 'PYTHON_EOF'
import sys
import re
import os

repo_root = sys.argv[1]
lessons_file = sys.argv[2]

with open(lessons_file) as f:
    content = f.read()

# Find the checklist section
match = re.search(
    r'### 横展開チェックリスト（過去仕組み的対策の landing 検証ルーチン・新設）.*?'
    r'\n\n\| 対策名.*?\n\|---', 
    content, 
    re.DOTALL
)

if not match:
    print("⚠️  チェックリスト表が見つかりません", file=sys.stderr)
    sys.exit(0)

# Find all table rows after the separator
lines = content[match.end():].split('\n')
failed = 0
checked = 0

for line in lines:
    if not line.startswith('|') or '---' in line:
        if line.strip() == '':
            break
        continue

    # Simple regex split on |
    parts = [p.strip() for p in line.split('|')]
    if len(parts) < 5:
        continue

    file_path = parts[3] if len(parts) > 3 else ''
    status = parts[4] if len(parts) > 4 else ''

    if not file_path or status == '✗':
        continue

    # First try extracting from backticks
    backtick_match = re.search(r'`([^`]+)`', file_path)
    if backtick_match:
        clean = backtick_match.group(1)
    else:
        clean = file_path

    # Remove line range suffixes (e.g., ":215-248", ":L286-313")
    clean = re.sub(r':[0-9L\-]+$', '', clean)
    # Remove parenthetical info
    clean = re.sub(r' \(.*?\)', '', clean)
    
    clean = clean.strip()
    if not clean:
        continue

    target = f"{repo_root}/{clean}"
    if not os.path.exists(target):
        print(f"❌ Missing: {clean}", file=sys.stderr)
        failed += 1
    elif clean.startswith('scripts/') and os.path.getsize(target) == 0:
        print(f"❌ Empty: {clean}", file=sys.stderr)
        failed += 1
    else:
        print(f"✅ {clean}")
        checked += 1

if failed > 0:
    print(f"\n❌ {failed} mitigation(s) not implemented", file=sys.stderr)
    sys.exit(1)

if checked > 0:
    print(f"\n✅ All {checked} validated")
else:
    print("⚠️  No active mitigations found")
PYTHON_EOF

python3 "$PYTHON_SCRIPT" "$REPO_ROOT" "$LESSONS_FILE"
EXIT_CODE=$?

rm -f "$PYTHON_SCRIPT"

if [ $EXIT_CODE -ne 0 ]; then
  exit $EXIT_CODE
fi

# PR #159 landing 検証: session_bootstrap.sh に PIPESTATUS[0] と BOOTSTRAP_EXIT=1 が両方含まれる
if ! grep -q 'PIPESTATUS\[0\]' "$REPO_ROOT/scripts/session_bootstrap.sh"; then
  echo "❌ PR #159: PIPESTATUS[0] not found in session_bootstrap.sh" >&2
  exit 1
fi
if ! grep -q 'BOOTSTRAP_EXIT=1' "$REPO_ROOT/scripts/session_bootstrap.sh"; then
  echo "❌ PR #159: BOOTSTRAP_EXIT=1 not found in session_bootstrap.sh" >&2
  exit 1
fi
echo "✅ PR #159: session_bootstrap.sh landing verified"

# PR #160 landing 検証: install_hooks.sh に pre-push hook 設置ブロックが含まれる
if ! grep -q 'pre-push' "$REPO_ROOT/scripts/install_hooks.sh"; then
  echo "❌ PR #160: pre-push hook block not found in install_hooks.sh" >&2
  exit 1
fi
echo "✅ PR #160: install_hooks.sh landing verified"

# T2026-0502-DEPLOY-WATCHDOG landing 検証:
# 1) check_lambda_freshness.sh が存在して空でないこと
if [ ! -f "$REPO_ROOT/scripts/check_lambda_freshness.sh" ]; then
  echo "❌ T2026-0502-DEPLOY-WATCHDOG: scripts/check_lambda_freshness.sh not found" >&2
  exit 1
fi
if [ ! -s "$REPO_ROOT/scripts/check_lambda_freshness.sh" ]; then
  echo "❌ T2026-0502-DEPLOY-WATCHDOG: scripts/check_lambda_freshness.sh is empty" >&2
  exit 1
fi
echo "✅ T2026-0502-DEPLOY-WATCHDOG: scripts/check_lambda_freshness.sh landing verified"

# 2) deploy-trigger-watchdog.yml が存在すること
if [ ! -f "$REPO_ROOT/.github/workflows/deploy-trigger-watchdog.yml" ]; then
  echo "❌ T2026-0502-DEPLOY-WATCHDOG: .github/workflows/deploy-trigger-watchdog.yml not found" >&2
  exit 1
fi
echo "✅ T2026-0502-DEPLOY-WATCHDOG: deploy-trigger-watchdog.yml landing verified"

# 3) lambda-freshness-monitor.yml が存在すること
if [ ! -f "$REPO_ROOT/.github/workflows/lambda-freshness-monitor.yml" ]; then
  echo "❌ T2026-0502-DEPLOY-WATCHDOG: .github/workflows/lambda-freshness-monitor.yml not found" >&2
  exit 1
fi
echo "✅ T2026-0502-DEPLOY-WATCHDOG: lambda-freshness-monitor.yml landing verified"

# 4) tests/test_lambda_freshness.sh が存在すること
if [ ! -f "$REPO_ROOT/tests/test_lambda_freshness.sh" ]; then
  echo "❌ T2026-0502-DEPLOY-WATCHDOG: tests/test_lambda_freshness.sh not found" >&2
  exit 1
fi
echo "✅ T2026-0502-DEPLOY-WATCHDOG: tests/test_lambda_freshness.sh landing verified"

# T2026-0502-MU-FOLLOWUP-ARCHIVED landing 検証: archived high-value 救済ロジック
# 1) quality_heal.py の archived 除外が高価値条件付きに変更されていること
if ! grep -q 'T2026-0502-MU-FOLLOWUP-ARCHIVED' "$REPO_ROOT/scripts/quality_heal.py"; then
  echo "❌ T2026-0502-MU-FOLLOWUP-ARCHIVED: rescue comment not found in scripts/quality_heal.py" >&2
  exit 1
fi
if ! grep -q 'ac >= 6 and score >= 100' "$REPO_ROOT/scripts/quality_heal.py"; then
  echo "❌ T2026-0502-MU-FOLLOWUP-ARCHIVED: high-value threshold not found in scripts/quality_heal.py" >&2
  exit 1
fi
echo "✅ T2026-0502-MU-FOLLOWUP-ARCHIVED: quality_heal.py archived rescue landing verified"

# 2) 境界テストが存在すること
if [ ! -f "$REPO_ROOT/tests/test_quality_heal_mode_upgrade.py" ]; then
  echo "❌ T2026-0502-MU-FOLLOWUP-ARCHIVED: tests/test_quality_heal_mode_upgrade.py not found" >&2
  exit 1
fi
echo "✅ T2026-0502-MU-FOLLOWUP-ARCHIVED: tests/test_quality_heal_mode_upgrade.py landing verified"

exit 0
