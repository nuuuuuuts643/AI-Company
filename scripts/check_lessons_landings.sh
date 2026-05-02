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

# PR #159 landing 検証 (T2026-0502-PHYSICAL-GUARD-AUDIT で grep 強化):
# 単に変数を取得しているだけでなく、失敗時に BOOTSTRAP_EXIT に流す経路が
# session_bootstrap.sh に書かれていることまで verify する。
# 旧: PIPESTATUS[0] / BOOTSTRAP_EXIT=1 が同ファイルに含まれることだけ検査 → 取得だけして
#     未使用でも pass する弱い grep。今回 _git_pull_status / _git_push_status の
#     条件分岐パターンまで要求する。
SBS="$REPO_ROOT/scripts/session_bootstrap.sh"
if ! grep -q 'PIPESTATUS\[0\]' "$SBS"; then
  echo "❌ PR #159: PIPESTATUS[0] not found in session_bootstrap.sh" >&2
  exit 1
fi
if ! grep -q 'BOOTSTRAP_EXIT=1' "$SBS"; then
  echo "❌ PR #159: BOOTSTRAP_EXIT=1 not found in session_bootstrap.sh" >&2
  exit 1
fi
# git pull / git push の失敗を BOOTSTRAP_EXIT に流す条件分岐があるか
if ! grep -qE '_git_(pull|push)_status.*-ne[ ]+0' "$SBS"; then
  echo "❌ PR #159: _git_pull_status / _git_push_status の失敗時 exit 経路が見つかりません" >&2
  echo "   期待: if [ \"\$_git_pull_status\" -ne 0 ]; then BOOTSTRAP_EXIT=1; fi のような分岐" >&2
  exit 1
fi
echo "✅ PR #159: session_bootstrap.sh landing verified (PIPESTATUS + exit 経路)"

# PR #160 landing 検証 (T2026-0502-PHYSICAL-GUARD-AUDIT で grep 強化):
# 旧: install_hooks.sh に 'pre-push' という文字列が含まれるかだけ → placeholder
#     `exit 0` でも pass。今回 main 直 push を実 reject するロジックの存在まで verify する。
INSH="$REPO_ROOT/scripts/install_hooks.sh"
if ! grep -q 'pre-push' "$INSH"; then
  echo "❌ PR #160: pre-push hook block not found in install_hooks.sh" >&2
  exit 1
fi
# install_hooks.sh の pre-push ブロック内で main 直 push を物理 reject する痕跡があるか
# 期待: refs/heads/main の判定 + exit 1 経路 + ALLOW_MAIN_PUSH escape の3要素
if ! grep -q 'refs/heads/main' "$INSH"; then
  echo "❌ PR #160: install_hooks.sh の pre-push に refs/heads/main 判定がありません (placeholder のままの可能性)" >&2
  exit 1
fi
if ! grep -qE 'ALLOW_MAIN_PUSH' "$INSH"; then
  echo "❌ PR #160: install_hooks.sh の pre-push に ALLOW_MAIN_PUSH escape がありません" >&2
  exit 1
fi
# 既存 .git/hooks/pre-push (実 install されているもの) も同条件で確認
HOOK_PP="$REPO_ROOT/.git/hooks/pre-push"
if [ -f "$HOOK_PP" ]; then
  if ! grep -q 'refs/heads/main' "$HOOK_PP"; then
    echo "❌ PR #160: .git/hooks/pre-push が placeholder のまま (refs/heads/main 判定なし)" >&2
    echo "   修復: bash scripts/install_hooks.sh を実行" >&2
    exit 1
  fi
fi
echo "✅ PR #160: install_hooks.sh + .git/hooks/pre-push landing verified (main 直 push reject ロジック含む)"

# T2026-0502-DEPLOY-WATCHDOG landing 検証 (T2026-0502-BL で存在チェックから内容 grep に強化):
# 1) check_lambda_freshness.sh が存在し、実装特徴文字列 THRESHOLD_SEC を含むこと
if [ ! -f "$REPO_ROOT/scripts/check_lambda_freshness.sh" ]; then
  echo "❌ T2026-0502-DEPLOY-WATCHDOG: scripts/check_lambda_freshness.sh not found" >&2
  exit 1
fi
if ! grep -q 'THRESHOLD_SEC' "$REPO_ROOT/scripts/check_lambda_freshness.sh"; then
  echo "❌ T2026-0502-DEPLOY-WATCHDOG: check_lambda_freshness.sh は placeholder の可能性 (THRESHOLD_SEC なし)" >&2
  exit 1
fi
echo "✅ T2026-0502-DEPLOY-WATCHDOG: scripts/check_lambda_freshness.sh landing verified (THRESHOLD_SEC 含む)"

# 2) deploy-trigger-watchdog.yml が存在し、deploy-lambdas への参照を含むこと
if [ ! -f "$REPO_ROOT/.github/workflows/deploy-trigger-watchdog.yml" ]; then
  echo "❌ T2026-0502-DEPLOY-WATCHDOG: .github/workflows/deploy-trigger-watchdog.yml not found" >&2
  exit 1
fi
if ! grep -q 'deploy-lambdas' "$REPO_ROOT/.github/workflows/deploy-trigger-watchdog.yml"; then
  echo "❌ T2026-0502-DEPLOY-WATCHDOG: deploy-trigger-watchdog.yml は placeholder の可能性 (deploy-lambdas 参照なし)" >&2
  exit 1
fi
echo "✅ T2026-0502-DEPLOY-WATCHDOG: deploy-trigger-watchdog.yml landing verified (deploy-lambdas 参照含む)"

# 3) lambda-freshness-monitor.yml が存在し、check_lambda_freshness スクリプトを呼ぶこと
if [ ! -f "$REPO_ROOT/.github/workflows/lambda-freshness-monitor.yml" ]; then
  echo "❌ T2026-0502-DEPLOY-WATCHDOG: .github/workflows/lambda-freshness-monitor.yml not found" >&2
  exit 1
fi
if ! grep -q 'check_lambda_freshness' "$REPO_ROOT/.github/workflows/lambda-freshness-monitor.yml"; then
  echo "❌ T2026-0502-DEPLOY-WATCHDOG: lambda-freshness-monitor.yml は placeholder の可能性 (check_lambda_freshness 参照なし)" >&2
  exit 1
fi
echo "✅ T2026-0502-DEPLOY-WATCHDOG: lambda-freshness-monitor.yml landing verified (check_lambda_freshness 参照含む)"

# 4) tests/test_lambda_freshness.sh が存在し、実際のテストロジックを含むこと
if [ ! -f "$REPO_ROOT/tests/test_lambda_freshness.sh" ]; then
  echo "❌ T2026-0502-DEPLOY-WATCHDOG: tests/test_lambda_freshness.sh not found" >&2
  exit 1
fi
if ! grep -q 'check_lambda_freshness.sh' "$REPO_ROOT/tests/test_lambda_freshness.sh"; then
  echo "❌ T2026-0502-DEPLOY-WATCHDOG: test_lambda_freshness.sh は placeholder の可能性 (check_lambda_freshness.sh 参照なし)" >&2
  exit 1
fi
echo "✅ T2026-0502-DEPLOY-WATCHDOG: tests/test_lambda_freshness.sh landing verified (check_lambda_freshness.sh 参照含む)"

# T2026-0502-MU-FOLLOWUP landing 検証: find_mode_mismatch_topics が quality_heal.py に実装済みであること
if ! grep -q 'find_mode_mismatch_topics' "$REPO_ROOT/scripts/quality_heal.py"; then
  echo "❌ T2026-0502-MU-FOLLOWUP: find_mode_mismatch_topics not found in scripts/quality_heal.py" >&2
  exit 1
fi
echo "✅ T2026-0502-MU-FOLLOWUP: find_mode_mismatch_topics landing verified"

# T2026-0502-MU-FOLLOWUP landing 検証: test_quality_heal_mode_upgrade.py が存在し、find_mode_mismatch_topics のテストを含むこと
if [ ! -f "$REPO_ROOT/tests/test_quality_heal_mode_upgrade.py" ]; then
  echo "❌ T2026-0502-MU-FOLLOWUP: tests/test_quality_heal_mode_upgrade.py not found" >&2
  exit 1
fi
if ! grep -q 'find_mode_mismatch_topics' "$REPO_ROOT/tests/test_quality_heal_mode_upgrade.py"; then
  echo "❌ T2026-0502-MU-FOLLOWUP: test_quality_heal_mode_upgrade.py は placeholder の可能性 (find_mode_mismatch_topics テストなし)" >&2
  exit 1
fi
echo "✅ T2026-0502-MU-FOLLOWUP: tests/test_quality_heal_mode_upgrade.py landing verified (find_mode_mismatch_topics テスト含む)"

# T2026-0502-WORKFLOW-DEP-PHYSICAL landing 検証 (T2026-0502-BL で内容 grep を追加):
# workflow YAML が repo に存在しない script を参照している commit miss を CI で物理 reject する
# ガードの存在を verify。本ガード自体が消されたら check_lessons_landings.sh が fail する。
# T2026-0502-LANDING-CHECK-RELAX (2026-05-02 23:30 JST): 旧 [ ! -x ] は PR #315 (950a5f6) で
# executable bit なしで commit された後 main で連続 CI 失敗を誘発した。
# lint-yaml-logic.yml は `bash scripts/...` で起動するため executable bit は機能要件ではなく、
# ガード本来の意図 (script の存在保証) は -f で満たせる。
if [ ! -f "$REPO_ROOT/scripts/ci_check_workflow_script_refs.sh" ]; then
  echo "❌ T2026-0502-WORKFLOW-DEP-PHYSICAL: scripts/ci_check_workflow_script_refs.sh not found" >&2
  exit 1
fi
# script 中に workflow ref 検出ロジックの実装特徴文字列があること (placeholder reject)
if ! grep -qE 'python3\?|bash.*scripts/' "$REPO_ROOT/scripts/ci_check_workflow_script_refs.sh"; then
  echo "❌ T2026-0502-WORKFLOW-DEP-PHYSICAL: ci_check_workflow_script_refs.sh は placeholder の可能性 (python3?/bash パターン検出ロジックなし)" >&2
  exit 1
fi
if ! grep -q 'ci_check_workflow_script_refs.sh' "$REPO_ROOT/.github/workflows/lint-yaml-logic.yml"; then
  echo "❌ T2026-0502-WORKFLOW-DEP-PHYSICAL: lint-yaml-logic.yml does not call ci_check_workflow_script_refs.sh" >&2
  exit 1
fi
echo "✅ T2026-0502-WORKFLOW-DEP-PHYSICAL: workflow ref check landed (script content + workflow step)"

# T2026-0502-WORKFLOW-DEP-PHYSICAL landing 検証 (2026-05-02 22:55 JST):
# workflow YAML が repo に存在しない script を参照している commit miss を CI で物理 reject する
# ガードの存在を verify。本ガード自体が消されたら check_lessons_landings.sh が fail する。
# T2026-0502-LANDING-CHECK-RELAX (2026-05-02 23:30 JST): 旧 [ ! -x ] は PR #315 (950a5f6) で
# executable bit なしで commit された後 main で連続 CI 失敗を誘発した。
# lint-yaml-logic.yml は `bash scripts/...` で起動するため executable bit は機能要件ではなく、
# ガード本来の意図 (script の存在保証) は -f で満たせる。
if [ ! -f "$REPO_ROOT/scripts/ci_check_workflow_script_refs.sh" ]; then
  echo "❌ T2026-0502-WORKFLOW-DEP-PHYSICAL: scripts/ci_check_workflow_script_refs.sh not found" >&2
  exit 1
fi
if ! grep -q 'ci_check_workflow_script_refs.sh' "$REPO_ROOT/.github/workflows/lint-yaml-logic.yml"; then
  echo "❌ T2026-0502-WORKFLOW-DEP-PHYSICAL: lint-yaml-logic.yml does not call ci_check_workflow_script_refs.sh" >&2
  exit 1
fi
echo "✅ T2026-0502-WORKFLOW-DEP-PHYSICAL: workflow ref check landed (script + workflow step)"

exit 0
