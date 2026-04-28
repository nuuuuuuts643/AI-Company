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
exit $EXIT_CODE
