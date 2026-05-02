#!/usr/bin/env bash
# check_workflow_paths.sh — T2026-0502-WORKFLOW-PATH-LINT
#
# CI script: scan .github/workflows/*.yml for the anti-pattern of calling
# repo-root-relative paths after a `cd <subdir>` within a `run:` block.
#
# Anti-pattern example (caused 18-hour deploy outage on 2026-05-02):
#   cd projects/P003-news-timeline/lambda/fetcher
#   python3 scripts/ci_lambda_merge_env.py   ← relative path, file doesn't exist under fetcher/
#
# Safe patterns:
#   cd subdir && python3 "$GITHUB_WORKSPACE/scripts/foo.py"  ← absolute path
#   cd $GITHUB_WORKSPACE && python3 scripts/foo.py           ← reset to repo root first
#
# Exit codes:
#   0: no anti-patterns detected
#   1: one or more anti-patterns detected
#
# Environment variables:
#   WORKFLOW_PATH_CHECK_TARGETS  — space-separated list of repo-root prefix dirs to check
#                                  (default: scripts/ tests/ docs/ projects/ lambda/ frontend/ tools/)
#   WORKFLOW_PATH_CHECK_DIR      — directory containing workflow .yml files
#                                  (default: .github/workflows relative to repo root)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

WORKFLOW_DIR="${WORKFLOW_PATH_CHECK_DIR:-${REPO_ROOT}/.github/workflows}"
DEFAULT_TARGETS="scripts/ tests/ docs/ projects/ lambda/ frontend/ tools/"
TARGETS="${WORKFLOW_PATH_CHECK_TARGETS:-$DEFAULT_TARGETS}"

PYTHON_SCRIPT=$(mktemp)
trap 'rm -f "$PYTHON_SCRIPT"' EXIT

cat > "$PYTHON_SCRIPT" << 'PYTHON_EOF'
import sys
import re
import os
import glob

workflow_dir = sys.argv[1]
targets_str = sys.argv[2]
target_prefixes = targets_str.split()

# Regex to detect `cd <dest>` where dest is NOT $GITHUB_WORKSPACE or - or ~
# Handles: `cd dir`, `&& cd dir`, `; cd dir`
CD_RE = re.compile(r'(?:^|&&|;)\s*cd\s+(\S+)')

# Regex to detect repo-root-relative path references
# Matches: python3 scripts/foo, bash scripts/foo, source scripts/foo,
#          ./scripts/foo (relative in current dir — less likely but included)
# Does NOT match: python3 "$GITHUB_WORKSPACE/scripts/foo" (has GITHUB_WORKSPACE)
def make_path_re(prefixes):
    alt = '|'.join(re.escape(p) for p in prefixes)
    # Match when preceded by: python3, python, bash, sh, source, ./ or at line start
    return re.compile(
        r'(?:python3?\s+|bash\s+|sh\s+|source\s+|exec\s+|\./)'
        r'(?!' + alt.replace('/', r'[^/]*/') + r')'  # not a longer match
        r'(' + '|'.join(re.escape(p) for p in prefixes) + r')',
        re.IGNORECASE
    )

# Build a simpler check: does the line reference a target prefix that looks like a relative path?
def line_has_relpath(line, prefixes):
    # Skip lines that use $GITHUB_WORKSPACE (absolute anchor)
    if '$GITHUB_WORKSPACE' in line or '${GITHUB_WORKSPACE}' in line:
        return None
    for prefix in prefixes:
        # python3 scripts/foo, bash scripts/foo, source scripts/foo
        m = re.search(
            r'(?:python3?\s+|bash\s+|sh\s+|source\s+)' + re.escape(prefix),
            line
        )
        if m:
            return prefix
    return None

def is_workspace_cd(dest):
    return (
        '$GITHUB_WORKSPACE' in dest
        or '${GITHUB_WORKSPACE}' in dest
        or dest in ('-', '~')
    )

def is_dotdot_cd(dest):
    # cd .. or cd ../.. etc — may or may not return to repo root; we treat as UNSAFE (false positive OK)
    return dest.startswith('..')

issues = []

yml_files = sorted(glob.glob(os.path.join(workflow_dir, '*.yml')))
if not yml_files:
    print(f"No workflow files found in {workflow_dir}", file=sys.stderr)
    sys.exit(0)

for yml_path in yml_files:
    rel_path = os.path.relpath(yml_path)
    with open(yml_path, encoding='utf-8') as f:
        raw_lines = f.readlines()

    lines = [l.rstrip('\n') for l in raw_lines]
    n = len(lines)

    # State machine: detect run: block boundaries, then check cd + relpath within each block
    i = 0
    while i < n:
        line = lines[i]

        # Detect start of a run: block (multiline shell: `run: |` or `run: >` or `run: |-`)
        run_match = re.match(r'^(\s+)run:\s*[|>!-]*\s*$', line)
        if not run_match:
            i += 1
            continue

        run_indent = len(run_match.group(1))
        # The run block body is indented more than run_indent
        # Collect block lines
        block_start = i + 1
        j = block_start
        while j < n:
            bline = lines[j]
            if bline.strip() == '':
                j += 1
                continue
            bline_indent = len(bline) - len(bline.lstrip())
            if bline_indent <= run_indent:
                break
            j += 1
        block_end = j  # exclusive

        # Process the run block lines
        # Track cd state: None = repo root, 'subdir' = inside a subdir
        # If we see `cd $GITHUB_WORKSPACE` or `cd -`, reset to repo root
        cd_stack = []  # list of (block_lineno, dest) to track current state

        for k in range(block_start, block_end):
            bline = lines[k]
            stripped = bline.strip()

            # Handle compound lines: `cd foo && python3 scripts/bar.py`
            # Split on && and ; for analysis
            parts = re.split(r'&&|;', stripped)

            # Accumulated cd state for this line (left to right)
            local_in_subdir = bool(cd_stack)

            for part in parts:
                part = part.strip()
                if not part:
                    continue

                # Check for cd command in this part
                cd_m = re.match(r'cd\s+(\S+)', part)
                if cd_m:
                    dest = cd_m.group(1)
                    # Remove trailing quotes
                    dest = dest.strip('"\'')
                    if is_workspace_cd(dest):
                        cd_stack = []  # reset to repo root
                        local_in_subdir = False
                    elif dest.startswith('..'):
                        # `cd ..` may or may not return to repo root.
                        # Treat as still-in-subdir (false positive OK per spec §ケース⑤).
                        # Only `cd $GITHUB_WORKSPACE` is a safe reset.
                        pass  # local_in_subdir unchanged
                    else:
                        cd_stack.append((k + 1, dest))
                        local_in_subdir = True
                    continue

                # Check for repo-root-relative path reference
                if local_in_subdir:
                    found = line_has_relpath(part, target_prefixes)
                    if found:
                        cd_info = cd_stack[-1] if cd_stack else ('?', '?')
                        issues.append({
                            'file': rel_path,
                            'line': k + 1,
                            'content': stripped,
                            'prefix': found,
                            'cd_line': cd_info[0],
                            'cd_dest': cd_info[1],
                        })

        i = block_end

if not issues:
    print("✅ workflow yml に cd + 相対パス anti-pattern なし")
    sys.exit(0)

print(f"", file=sys.stderr)
print(f"❌ ERROR: workflow yml の cd 後相対パス anti-pattern を {len(issues)} 件検出", file=sys.stderr)
print(f"", file=sys.stderr)
for iss in issues:
    print(f"  ファイル : {iss['file']}", file=sys.stderr)
    print(f"  行番号   : L{iss['line']}", file=sys.stderr)
    print(f"  該当行   : {iss['content']}", file=sys.stderr)
    print(f"  起因 cd  : L{iss['cd_line']} → cd {iss['cd_dest']}", file=sys.stderr)
    print(f"  推奨修正 : \"$GITHUB_WORKSPACE/{iss['prefix']}...\" の絶対パスに変更", file=sys.stderr)
    print(f"", file=sys.stderr)

print("→ `cd <subdir>` 後に repo-root 相対パスを呼ぶと runner に該当ファイルが存在しない。", file=sys.stderr)
print("  修正: python3 \"$GITHUB_WORKSPACE/scripts/foo.py\" のように絶対パス参照にする。", file=sys.stderr)
sys.exit(1)
PYTHON_EOF

echo "=== workflow yml の cd 後相対パス検出 (T2026-0502-WORKFLOW-PATH-LINT) ==="
python3 "$PYTHON_SCRIPT" "$WORKFLOW_DIR" "$TARGETS"
