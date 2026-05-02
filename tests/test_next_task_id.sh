#!/usr/bin/env bash
# tests/test_next_task_id.sh
# next_task_id.sh の同日 ID 重複チェック機能を検証

set -u

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# テスト用の独立した repo を作成
TEST_DIR=$(mktemp -d)
trap "rm -rf $TEST_DIR" EXIT

# テスト repo 内に scripts/ をコピー
mkdir -p "$TEST_DIR/scripts"
cp "$REPO_ROOT/scripts/next_task_id.sh" "$TEST_DIR/scripts/"

cd "$TEST_DIR"
git init -q
git config user.name "Test User"
git config user.email "test@example.com"

# ファイル初期化
touch TASKS.md HISTORY.md WORKING.md
mkdir -p docs

pass=0
fail=0

# テスト 1: 何もない場合 → A を返す
echo "TEST1: No existing IDs → should return A"
TODAY="$(TZ=Asia/Tokyo date '+%Y-%m%d')"
RESULT=$(bash ./scripts/next_task_id.sh)
if [[ "$RESULT" == "T${TODAY}-A" ]]; then
  echo "✅ PASS"
  ((pass++))
else
  echo "❌ FAIL: got $RESULT, expected T${TODAY}-A"
  ((fail++))
fi

# テスト 2: TASKS.md に A が存在 → B を返す
echo "TEST2: ID in TASKS.md → should skip to B"
echo "T${TODAY}-A some task" >> TASKS.md
RESULT=$(bash ./scripts/next_task_id.sh)
if [[ "$RESULT" == "T${TODAY}-B" ]]; then
  echo "✅ PASS"
  ((pass++))
else
  echo "❌ FAIL: got $RESULT, expected T${TODAY}-B"
  ((fail++))
fi

# テスト 3: HISTORY.md に B が存在 → C を返す
echo "TEST3: ID in HISTORY.md → should skip to C"
echo "T${TODAY}-B completed" >> HISTORY.md
RESULT=$(bash ./scripts/next_task_id.sh)
if [[ "$RESULT" == "T${TODAY}-C" ]]; then
  echo "✅ PASS"
  ((pass++))
else
  echo "❌ FAIL: got $RESULT, expected T${TODAY}-C"
  ((fail++))
fi

# テスト 4: git log に C が存在 → D を返す
echo "TEST4: ID in git log → should skip to D"
git add -A && git commit -q -m "fix: T${TODAY}-C some fix" || true
RESULT=$(bash ./scripts/next_task_id.sh)
if [[ "$RESULT" == "T${TODAY}-D" ]]; then
  echo "✅ PASS"
  ((pass++))
else
  echo "❌ FAIL: got $RESULT, expected T${TODAY}-D"
  ((fail++))
fi

# テスト 5: 複数 ID が同時に使用中 → 最初の空き ID を返す
echo "TEST5: Multiple IDs in use → should return first available"
echo "T${TODAY}-D task" >> TASKS.md
echo "T${TODAY}-E task" >> TASKS.md
git add -A && git commit -q -m "chore: T${TODAY}-F something" || true
RESULT=$(bash ./scripts/next_task_id.sh)
if [[ "$RESULT" == "T${TODAY}-G" ]]; then
  echo "✅ PASS"
  ((pass++))
else
  echo "❌ FAIL: got $RESULT, expected T${TODAY}-G"
  ((fail++))
fi

# テスト 6: WORKING.md に ID が存在 → スキップ
echo "TEST6: ID in WORKING.md → should skip"
echo "T${TODAY}-G in progress" >> WORKING.md
RESULT=$(bash ./scripts/next_task_id.sh)
if [[ "$RESULT" == "T${TODAY}-H" ]]; then
  echo "✅ PASS"
  ((pass++))
else
  echo "❌ FAIL: got $RESULT, expected T${TODAY}-H"
  ((fail++))
fi

echo ""
echo "Results: $pass passed, $fail failed"
exit $fail
