#!/usr/bin/env bash
# tests/test_lambda_freshness.sh — T2026-0502-DEPLOY-WATCHDOG
# check_lambda_freshness.sh の境界テスト
#
# 注: このテストは AWS CLI を呼ばず、aws コマンドをモックする。
#     git log もモックして時刻を制御する。
#
# Exit codes:
#   0: all tests passed
#   1: one or more tests failed

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CHECK_SCRIPT="$REPO_ROOT/scripts/check_lambda_freshness.sh"

PASS=0
FAIL=0

# --- ヘルパー ---
pass() { echo "✅ $1"; PASS=$(( PASS + 1 )); }
fail() { echo "❌ $1"; FAIL=$(( FAIL + 1 )); }

# --- AWS CLI / git を PATH 前に差し込むモックディレクトリ ---
MOCK_DIR=$(mktemp -d)
trap 'rm -rf "$MOCK_DIR"' EXIT

# モック aws コマンド生成
make_aws_mock() {
  local last_modified="$1"
  cat > "$MOCK_DIR/aws" << EOF
#!/bin/bash
# モック aws: lambda get-function-configuration → LastModified を返す
if [[ "\$*" == *"get-function-configuration"* ]]; then
  echo "$last_modified"
  exit 0
fi
# その他のサブコマンドは素通り (実際の aws には呼ばない)
exit 0
EOF
  chmod +x "$MOCK_DIR/aws"
}

# モック git コマンド生成 (commit time を epoch で返す)
make_git_mock() {
  local commit_time="$1"
  cat > "$MOCK_DIR/git" << EOF
#!/bin/bash
# モック git: log -1 --format=%ct → commit time を返す
if [[ "\$*" == *"log"* && "\$*" == *"%ct"* ]]; then
  echo "$commit_time"
  exit 0
fi
# その他は実 git へ委譲
$(which git) "\$@"
EOF
  chmod +x "$MOCK_DIR/git"
}

run_check() {
  local commit_epoch="$1"
  local lambda_modified="$2"
  PATH="$MOCK_DIR:$PATH" bash "$CHECK_SCRIPT" p003-processor projects/P003-news-timeline/lambda/
}

# --- テスト本体 ---

# テスト 1: lag = 0min (commit と lambda 同時) → exit 0
TEST_NAME="lag=0min → exit 0"
NOW=$(date +%s)
make_git_mock "$NOW"
# Lambda は commit と同時刻
LAMBDA_TS_STR=$(python3 -c "from datetime import datetime,timezone; print(datetime.fromtimestamp($NOW, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000+0000'))")
make_aws_mock "$LAMBDA_TS_STR"
if PATH="$MOCK_DIR:$PATH" bash "$CHECK_SCRIPT" p003-processor projects/P003-news-timeline/lambda/ > /dev/null 2>&1; then
  pass "$TEST_NAME"
else
  fail "$TEST_NAME (exit=$?)"
fi

# テスト 2: lag = 29min → exit 0 (閾値以内)
TEST_NAME="lag=29min → exit 0"
NOW=$(date +%s)
COMMIT_TIME=$(( NOW - 1740 ))  # 29 minutes ago (commit)
make_git_mock "$COMMIT_TIME"
LAMBDA_TS=$(( NOW ))  # Lambda は NOW (commit より 29min 後)
LAMBDA_TS_STR=$(python3 -c "from datetime import datetime,timezone; print(datetime.fromtimestamp($LAMBDA_TS, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000+0000'))")
make_aws_mock "$LAMBDA_TS_STR"
if PATH="$MOCK_DIR:$PATH" bash "$CHECK_SCRIPT" p003-processor projects/P003-news-timeline/lambda/ > /dev/null 2>&1; then
  pass "$TEST_NAME"
else
  fail "$TEST_NAME (exit=$?)"
fi

# テスト 3: lag = 31min → exit 1 (閾値超)
TEST_NAME="lag=31min → exit 1"
NOW=$(date +%s)
COMMIT_TIME=$(( NOW - 1860 ))  # 31 minutes ago (commit)
make_git_mock "$COMMIT_TIME"
LAMBDA_TS=$NOW  # Lambda は今 (commit より 31min 後 = 遅い)
LAMBDA_TS_STR=$(python3 -c "from datetime import datetime,timezone; print(datetime.fromtimestamp($LAMBDA_TS, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000+0000'))")
make_aws_mock "$LAMBDA_TS_STR"
if PATH="$MOCK_DIR:$PATH" bash "$CHECK_SCRIPT" p003-processor projects/P003-news-timeline/lambda/ > /dev/null 2>&1; then
  fail "$TEST_NAME (expected exit 1, got 0)"
else
  ACTUAL_EXIT=$?
  if [ $ACTUAL_EXIT -eq 1 ]; then
    pass "$TEST_NAME"
  else
    fail "$TEST_NAME (expected exit 1, got $ACTUAL_EXIT)"
  fi
fi

# テスト 4: lag = 120min (deploy が全く走っていないケース) → exit 1
TEST_NAME="lag=120min → exit 1"
NOW=$(date +%s)
COMMIT_TIME=$(( NOW - 7200 ))  # 120 minutes ago (commit)
make_git_mock "$COMMIT_TIME"
LAMBDA_TS=$(( NOW - 3600 ))  # Lambda は 60min 前 (commit より 60min 古い = lag 60min)
LAMBDA_TS_STR=$(python3 -c "from datetime import datetime,timezone; print(datetime.fromtimestamp($LAMBDA_TS, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000+0000'))")
make_aws_mock "$LAMBDA_TS_STR"
if PATH="$MOCK_DIR:$PATH" bash "$CHECK_SCRIPT" p003-processor projects/P003-news-timeline/lambda/ > /dev/null 2>&1; then
  fail "$TEST_NAME (expected exit 1, got 0)"
else
  ACTUAL_EXIT=$?
  if [ $ACTUAL_EXIT -eq 1 ]; then
    pass "$TEST_NAME"
  else
    fail "$TEST_NAME (expected exit 1, got $ACTUAL_EXIT)"
  fi
fi

# テスト 5: AWS CLI エラー → exit 2
TEST_NAME="AWS CLI error → exit 2"
NOW=$(date +%s)
make_git_mock "$NOW"
# aws コマンドをエラー返しにする
cat > "$MOCK_DIR/aws" << 'EOF'
#!/bin/bash
if [[ "$*" == *"get-function-configuration"* ]]; then
  echo "An error occurred (ResourceNotFoundException)" >&2
  exit 1
fi
exit 0
EOF
chmod +x "$MOCK_DIR/aws"
PATH="$MOCK_DIR:$PATH" bash "$CHECK_SCRIPT" p003-processor projects/P003-news-timeline/lambda/ > /dev/null 2>&1
ACTUAL_EXIT=$?
if [ $ACTUAL_EXIT -eq 2 ]; then
  pass "$TEST_NAME"
else
  fail "$TEST_NAME (expected exit 2, got $ACTUAL_EXIT)"
fi

# テスト 6: git log が空 (lambda コードの変更なし) → exit 0
TEST_NAME="no lambda commits → exit 0"
make_git_mock ""  # 空の commit time
# aws mock は任意
make_aws_mock "2026-01-01T00:00:00.000+0000"
if PATH="$MOCK_DIR:$PATH" bash "$CHECK_SCRIPT" p003-processor projects/P003-news-timeline/lambda/ > /dev/null 2>&1; then
  pass "$TEST_NAME"
else
  fail "$TEST_NAME (exit=$?)"
fi

# --- サマリー ---
echo ""
echo "Results: $PASS passed, $FAIL failed"
if [ $FAIL -gt 0 ]; then
  exit 1
fi
exit 0
