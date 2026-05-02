#!/usr/bin/env python3
"""
Reject python3 -c / python -c inline logic in .github/workflows/*.yml

Uses YAML structural parsing (yaml.safe_load) to definitively identify
inline python logic by:
- Parsing YAML as structured data (not text search)
- Checking ONLY 'run' and 'script' key values
- Ignoring comments, string values in other keys, heredoc content

Exit 1 if violations found; 0 if clean.
"""
import sys
import os
import re
import glob
from pathlib import Path
try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Install with: pip install PyYAML", file=sys.stderr)
    sys.exit(2)

VIOLATIONS = []
EXCLUDED_FILES = {"lint-yaml-logic.yml", ".github/workflows/lint-yaml-logic.yml"}

def check_yaml_file(filepath):
    """Parse YAML file and check for inline python logic in run/script keys."""
    try:
        with open(filepath, 'r') as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        # Skip files that can't be parsed
        return

    if not isinstance(data, dict):
        return

    # Walk through the YAML structure looking for jobs
    jobs = data.get('jobs', {})
    if not isinstance(jobs, dict):
        return

    for job_name, job_config in jobs.items():
        if not isinstance(job_config, dict):
            continue

        # Check steps in the job
        steps = job_config.get('steps', [])
        if not isinstance(steps, list):
            continue

        for step_idx, step in enumerate(steps):
            if not isinstance(step, dict):
                continue

            # Check 'run' and 'script' keys
            for key in ['run', 'script']:
                value = step.get(key)
                if value is None:
                    continue

                # Value should be a string
                if not isinstance(value, str):
                    continue

                # Check for inline python logic
                if re.search(r'python3\s+-c|python\s+-c', value):
                    rel_path = os.path.relpath(filepath)
                    VIOLATIONS.append(f"{rel_path}:  job={job_name}, step={step_idx}, key={key}")

def main():
    """Main entry point."""
    # Find all workflow YAML files
    workflow_files = glob.glob(".github/workflows/*.yml")

    if not workflow_files:
        print("✅ No workflow YAML files found")
        return 0

    # Check each file
    for filepath in sorted(workflow_files):
        # Skip excluded files
        if any(excluded in filepath for excluded in EXCLUDED_FILES):
            continue

        check_yaml_file(filepath)

    # Report violations
    if VIOLATIONS:
        print("❌ YAML内のインラインPythonロジックを禁止します:")
        for violation in VIOLATIONS:
            print(violation)
        print("")
        print("scripts/ に移してから呼び出してください")
        return 1

    print("✅ YAMLインラインロジックなし")
    return 0

if __name__ == '__main__':
    sys.exit(main())
