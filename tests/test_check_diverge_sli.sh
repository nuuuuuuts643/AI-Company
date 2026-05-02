#!/usr/bin/env bash
# tests/test_check_diverge_sli.sh — T2026-0502-DIVERGE-SLI
# check_diverge_sli.sh の境界テスト (0/1/2/5 commits ahead)
#
# Exit codes:
#   0: all tests passed
#   1: one or more tests failed

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CHECK_SCRIPT="$REPO_ROOT/scripts/check_diverge_sli.sh"

PASS=0
FAIL=0

# テスト用に独立した git リポジトリを作成してコミット数を再現する
setup_repo() {
  local dir="$1"
  local ahead="$2"

  git -C "$dir" init -q
  git -C "$dir" config user.email "test@test"
  git -C "$dir" config user.name "test"

  # base commit
  touch "$dir/base.txt"
  git -C "$dir" add base.txt
  git -C "$dir" commit -q -m "base"

  # origin/main として扱う ref を作成 (bare でなく refs/remotes/origin/main をシミュレート)
  git -C "$dir" branch -q -f origin_main HEAD
  # refs/remotes/origin/main に貼る
  git -C "$dir" update-ref refs/remotes/origin/main HEAD

  # ahead コミットを追加
  for i in $(seq 1 "$ahead"); do
    echo "$i" >> "$dir/file_${i}.txt"
    git -C "$dir" add "file_${i}.txt"
    git -C "$dir" commit -q -m "commit $i"
  done
}

run_test() {
  local name="$1"
  local ahead="$2"
  local expected_exit="$3"

  local tmp_dir
  tmp_dir=$(mktemp -d)
  setup_repo "$tmp_dir" "$ahead"

  local actual_exit=0
  local out
  out=$(DIVERGE_BASE=refs/remotes/origin/main bash "$CHECK_SCRIPT" 2>/dev/null) || actual_exit=$?

  rm -rf "$tmp_dir"

  if [ "$actual_exit" -eq "$expected_exit" ]; then
    echo "  ✅ $name: ahead=$ahead → exit=$actual_exit"
    PASS=$((PASS + 1))
  else
    echo "  ❌ $name: ahead=$ahead → expected exit=$expected_exit, got exit=$actual_exit"
    FAIL=$((FAIL + 1))
  fi
}

run_test_with_count() {
  local name="$1"
  local ahead="$2"
  local expected_exit="$3"
  local expected_count="$4"

  local tmp_dir
  tmp_dir=$(mktemp -d)
  setup_repo "$tmp_dir" "$ahead"

  local actual_exit=0
  local out
  out=$(cd "$tmp_dir" && DIVERGE_BASE=refs/remotes/origin/main bash "$CHECK_SCRIPT" 2>/dev/null) || actual_exit=$?

  # diverge_count= の値を確認
  local count
  count=$(echo "$out" | grep "diverge_count=" | cut -d= -f2)

  rm -rf "$tmp_dir"

  local ok=true
  if [ "$actual_exit" -ne "$expected_exit" ]; then
    echo "  ❌ $name: exit expected=$expected_exit, got=$actual_exit"
    ok=false
  fi
  if [ "$count" != "$expected_count" ]; then
    echo "  ❌ $name: count expected=$expected_count, got=$count"
    ok=false
  fi
  if $ok; then
    echo "  ✅ $name: ahead=$ahead, diverge_count=$count, exit=$actual_exit"
    PASS=$((PASS + 1))
  else
    FAIL=$((FAIL + 1))
  fi
}

echo "=== test_check_diverge_sli.sh 境界テスト ==="
echo ""

run_test_with_count "0 commits ahead → exit 0 (正常)" 0 0 "0"
run_test_with_count "1 commit ahead  → exit 0 (正常)" 1 0 "1"
run_test_with_count "2 commits ahead → exit 1 (WARN)" 2 1 "2"
run_test_with_count "5 commits ahead → exit 2 (ERROR)" 5 2 "5"

# git repo なし → exit 3
test_no_git() {
  local name="$1"
  local tmp_dir
  tmp_dir=$(mktemp -d)
  local actual_exit=0
  (cd "$tmp_dir" && bash "$CHECK_SCRIPT" 2>/dev/null) || actual_exit=$?
  rm -rf "$tmp_dir"
  if [ "$actual_exit" -eq 3 ]; then
    echo "  ✅ $name: exit=3"
    PASS=$((PASS + 1))
  else
    echo "  ❌ $name: expected exit=3, got=$actual_exit"
    FAIL=$((FAIL + 1))
  fi
}
test_no_git "git repo なし → exit 3"

echo ""
echo "=== 結果: $PASS 件合格 / $FAIL 件失敗 ==="
[ "$FAIL" -eq 0 ]
