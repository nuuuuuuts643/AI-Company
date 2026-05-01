#!/bin/bash
# Reject python3 -c / python -c inline logic in .github/workflows/*.yml
# Exit 1 if any found (except the lint workflow itself which may reference the pattern in comments).
set -e

FOUND=$(grep -rn "python3 -c\|python -c" .github/workflows/*.yml 2>/dev/null \
  | grep -v "lint-yaml-logic.yml" || true)

if [ -n "$FOUND" ]; then
  echo "❌ YAML内のインラインPythonロジックを禁止します:"
  echo "$FOUND"
  echo ""
  echo "scripts/ に移してから呼び出してください"
  exit 1
fi
echo "✅ YAMLインラインロジックなし"
