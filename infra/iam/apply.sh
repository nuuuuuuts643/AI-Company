#!/usr/bin/env bash
# T2026-0502-IAM-DEPLOY-FIX / T2026-0502-IAM-DRIFT-FIX2:
# GitHub Actions OIDC role の inline policy を git tracked JSON ファイルから AWS に同期する。
#
# 使い方:
#   bash infra/iam/apply.sh           # 全 role 同期 + post-apply 自己検証
#   bash infra/iam/apply.sh --dry-run # diff のみ表示 (apply はしない)
#   bash infra/iam/apply.sh --check   # drift 検出のみ (apply しない・exit 1 if drift)
#
# 前提:
#   - jq + python3 がインストールされている
#   - aws cli が ap-northeast-1 に対して iam:PutRolePolicy / iam:GetRolePolicy 権限を持つ
#   - infra/iam/policies/<policy-name>.json に _meta.role_name と _meta.policy_name が記載
#
# 設計原則 (恒久対処):
#   - source of truth は git tracked JSON のみ
#   - canonicalize は scripts/iam_canon.py で完全 recursive sort_keys (drift CI と同一ロジック)
#   - apply 後は必ず drift check で「適用結果 = git 期待」を物理確認 (post-apply self-check)
#   - AWS console 直接編集 + `aws iam put-role-policy` 直接呼び出しは pre-commit hook で禁止
set -euo pipefail

MODE="apply"
case "${1:-}" in
  --dry-run) MODE="dry-run" ;;
  --check)   MODE="check"   ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
POLICY_DIR="$SCRIPT_DIR/policies"
CANON="$REPO_ROOT/scripts/iam_canon.py"

if [ ! -d "$POLICY_DIR" ]; then
  echo "[ERROR] policy directory not found: $POLICY_DIR" >&2
  exit 1
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "[ERROR] jq is required" >&2
  exit 2
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "[ERROR] python3 is required" >&2
  exit 2
fi
if ! command -v aws >/dev/null 2>&1; then
  echo "[ERROR] aws cli is required" >&2
  exit 2
fi
if [ ! -f "$CANON" ]; then
  echo "[ERROR] $CANON missing" >&2
  exit 2
fi

# 共通 canonicalize: drift CI と同じロジック (Python json.dumps(sort_keys=True, separators=(',',':')))。
canon() { python3 "$CANON"; }

shopt -s nullglob
ANY_DRIFT=0
APPLY_FAILED=0
for policy_file in "$POLICY_DIR"/*.json; do
  echo "=== $(basename "$policy_file") ==="
  ROLE_NAME=$(jq -r '._meta.role_name // empty' "$policy_file")
  POLICY_NAME=$(jq -r '._meta.policy_name // empty' "$policy_file")

  if [ -z "$ROLE_NAME" ] || [ -z "$POLICY_NAME" ]; then
    echo "[ERROR] $policy_file: _meta.role_name / _meta.policy_name 必須" >&2
    exit 3
  fi

  STRIPPED=$(jq 'del(._meta)' "$policy_file")
  DESIRED=$(echo "$STRIPPED" | canon)
  ACTUAL=$(aws iam get-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-name "$POLICY_NAME" \
    --query "PolicyDocument" \
    --output json 2>/dev/null | canon || echo "{}")

  echo "  role:   $ROLE_NAME"
  echo "  policy: $POLICY_NAME"

  if [ "$DESIRED" = "$ACTUAL" ]; then
    echo "  [OK] no drift"
    echo ""
    continue
  fi

  ANY_DRIFT=1
  echo "  [DRIFT] git desired ≠ AWS actual"

  case "$MODE" in
    dry-run)
      echo "  [DRY-RUN] would apply"
      ;;
    check)
      echo "  [CHECK] drift 検出 (apply しない)"
      ;;
    apply)
      echo "  [APPLY] put-role-policy ..."
      if ! aws iam put-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-name "$POLICY_NAME" \
        --policy-document "$STRIPPED" >/dev/null; then
        echo "  [ERROR] put-role-policy failed for $ROLE_NAME / $POLICY_NAME" >&2
        APPLY_FAILED=1
        continue
      fi
      # post-apply self-check: 即座に AWS から取り直して canon 比較
      AFTER=$(aws iam get-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-name "$POLICY_NAME" \
        --query "PolicyDocument" \
        --output json 2>/dev/null | canon || echo "{}")
      if [ "$DESIRED" = "$AFTER" ]; then
        echo "  [VERIFIED] applied + post-apply check OK"
      else
        echo "  [ERROR] post-apply check FAILED for $ROLE_NAME / $POLICY_NAME" >&2
        APPLY_FAILED=1
      fi
      ;;
  esac
  echo ""
done

echo "=== done (mode=$MODE drift=$ANY_DRIFT apply_failed=$APPLY_FAILED) ==="

if [ "$MODE" = "check" ] && [ "$ANY_DRIFT" -eq 1 ]; then
  exit 1
fi
if [ "$MODE" = "apply" ] && [ "$APPLY_FAILED" -eq 1 ]; then
  exit 1
fi
exit 0
