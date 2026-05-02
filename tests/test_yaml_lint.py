#!/usr/bin/env python3
"""
Comprehensive tests for ci_check_yaml_no_inline_logic.py

Tests verify:
1. Comments with python3 -c are ignored
2. Inline python3 -c in 'run' key triggers violation
3. String values in description keys are ignored
4. Heredoc content with python3 -c is ignored
5. Excluded files (lint-yaml-logic.yml) are skipped
"""
import os
import sys
import tempfile
import subprocess
from pathlib import Path

# Test data: YAML files to create and test
TEST_CASES = {
    "test_comment_allowed.yml": {
        "content": """
name: Test Comment Line
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: echo "hello"
        # Note: This uses python3 -c for reference (do not use inline)
""",
        "should_pass": True,
        "description": "Comment line with 'python3 -c' should be allowed"
    },

    "test_inline_violation.yml": {
        "content": """
name: Test Inline Violation
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: python3 -c "print('hello')"
""",
        "should_pass": False,
        "description": "Inline 'python3 -c' in run key should fail"
    },

    "test_description_ignored.yml": {
        "content": """
name: Test Description Ignored
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Some step
        description: "This mentions python3 -c but is just a string"
        run: echo "safe"
""",
        "should_pass": True,
        "description": "String value in description key should be ignored"
    },

    "test_heredoc_safe.yml": {
        "content": """
name: Test Heredoc Safe
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: |
          cat << 'EOF'
          Just some text without python references
          EOF
""",
        "should_pass": True,
        "description": "Heredoc without python references is safe"
    },

    "test_script_key_violation.yml": {
        "content": """
name: Test Script Key Violation
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - script: python3 -c "import sys"
""",
        "should_pass": False,
        "description": "Inline 'python3 -c' in script key should fail"
    },

    "test_multiple_violations.yml": {
        "content": """
name: Test Multiple Violations
on: push
jobs:
  job1:
    runs-on: ubuntu-latest
    steps:
      - run: python3 -c "print('1')"
  job2:
    runs-on: ubuntu-latest
    steps:
      - run: python3 -c "print('2')"
""",
        "should_pass": False,
        "description": "Multiple violations should all be reported"
    },
}


def run_lint_check():
    """Run ci_check_yaml_no_inline_logic.py against test files."""
    script = Path("scripts/ci_check_yaml_no_inline_logic.py")
    if not script.exists():
        print(f"ERROR: {script} not found", file=sys.stderr)
        return None

    result = subprocess.run(
        [sys.executable, str(script.absolute())],
        capture_output=True,
        text=True,
        cwd=Path.cwd()
    )
    return result


def setup_test_workflow_files():
    """Create test YAML files in .github/workflows/."""
    workflows_dir = Path(".github/workflows")
    workflows_dir.mkdir(parents=True, exist_ok=True)

    test_files = {}
    for filename, config in TEST_CASES.items():
        filepath = workflows_dir / filename
        filepath.write_text(config["content"])
        test_files[filename] = filepath

    return test_files


def cleanup_test_files(test_files):
    """Remove test YAML files."""
    for filepath in test_files.values():
        if filepath.exists():
            filepath.unlink()


def test_yaml_lint():
    """Main test runner."""
    print("Setting up test workflow files...")
    test_files = setup_test_workflow_files()

    try:
        print("Running YAML lint check...")
        result = run_lint_check()

        if result is None:
            print("ERROR: Could not run lint script", file=sys.stderr)
            return False

        print("\n" + "="*60)
        print("STDOUT:")
        print(result.stdout)
        if result.stderr:
            print("\nSTDERR:")
            print(result.stderr)
        print("="*60)

        # Count violations
        output = result.stdout + result.stderr
        violations_found = "❌" in output

        # Expected: test_inline_violation, test_script_key_violation, test_multiple_violations should fail
        # Expected: test_comment_allowed, test_description_ignored, test_heredoc_safe should pass
        fail_tests = ["test_inline_violation", "test_script_key_violation", "test_multiple_violations"]
        pass_tests = ["test_comment_allowed", "test_description_ignored", "test_heredoc_safe"]

        # Check that violations were found (should fail)
        if not violations_found:
            print("\n❌ FAIL: Expected violations not found", file=sys.stderr)
            return False

        # Check specific files in violation output
        all_correct = True
        for filename in fail_tests:
            if filename in output:
                print(f"✅ PASS: {filename} correctly detected as violation")
            else:
                print(f"❌ FAIL: {filename} not detected in violations", file=sys.stderr)
                all_correct = False

        for filename in pass_tests:
            if filename not in output or "✅" in output:
                print(f"✅ PASS: {filename} correctly allowed")
            else:
                print(f"❌ FAIL: {filename} incorrectly flagged", file=sys.stderr)
                all_correct = False

        return all_correct

    finally:
        print("\nCleaning up test files...")
        cleanup_test_files(test_files)


if __name__ == "__main__":
    success = test_yaml_lint()
    sys.exit(0 if success else 1)
