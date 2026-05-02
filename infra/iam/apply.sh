#!/usr/bin/env bash
# T2026-0502-IAM-DEPLOY-FIX: GitHub Actions OIDC role の inline policy を
# git tracked JSON ファイルから AWS に同期する apply script。
#
# 使い方:
#   bash infra/iam/apply.sh           # 全 role 同期
#   bash infra/iam/apply.sh --dry-run # diff のみ表示 (apply はしない)
#
# 前提:
#   - jq がインストールされている (json minify + _meta strip 用)
#   - aws cli が ap-northeast-1 に対して iam:PutRolePolicy 権限を持つ
#   - infra/iam/policies/<policy-name>.json に _meta.role_name と _meta.policy_name が記載
#
# 設計原則 (恒久対処):
#   - source of truth は git tracked JSON のみ
#   - AWS console 直接編集は禁止 (drift 検出は別途 CI で実装予定)
#   - _meta フィールドは AWS には送らず apply script で strip
set -euo pipefail

DRY_RUN=false
if [ "${1:-}" = "--dry-run" ]; then
  DRY_RUN=true
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
POLICY_DIR="$SCRIPT_DIR/policies"

if [ ! -d "$POLICY_DIR" ]; then
  echo "[ERROR] policy directory not found: $POLICY_DIR" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "[ERROR] jq is required (used for _meta strip + json minify)" >&2
  exit 2
fi

if ! command -v aws >/dev/null 2>&1; then
  echo "[ERROR] aws cli is required" >&2
  exit 2
fi

shopt -s nullglob
for policy_file in "$POLICY_DIR"/*.json; do
  echo "=== $(basename "$policy_file") ==="
  ROLE_NAME=$(jq -r '._meta.role_name // empty' "$policy_file")
  POLICY_NAME=$(jq -r '._meta.policy_name // empty' "$policy_file")

  if [ -z "$ROLE_NAME" ] || [ -z "$POLICY_NAME" ]; then
    echo "[ERROR] $policy_file: _meta.role_name and _meta.policy_name are required" >&2
    exit 3
  fi

  # _meta を strip して minify した JSON を作る
  STRIPPED=$(jq 'del(._meta)' "$policy_file")

  echo "  role:   $ROLE_NAME"
  echo "  policy: $POLICY_NAME"
  echo "  size:   $(echo "$STRIPPED" | wc -c) bytes"

  if [ "$DRY_RUN" = "true" ]; then
    echo "  [DRY-RUN] would apply (compact preview):"
    echo "$STRIPPED" | jq -c '.' | head -c 200
    echo "..."
    echo ""
    continue
  fi

  # 既存 policy との diff (informational only)
  EXISTING=$(aws iam get-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-name "$POLICY_NAME" \
    --query "PolicyDocument" \
    --output json 2>/dev/null || echo "{}")

  EXISTING_NORM=$(echo "$EXISTING" | jq -S '.')
  NEW_NORM=$(echo "$STRIPPED" | jq -S '.')

  if [ "$EXISTING_NORM" = "$NEW_NORM" ]; then
    echo "  [SKIP] no diff"
    echo ""
    continue
  fi

  echo "  [DIFF] applying..."
  aws iam put-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-name "$POLICY_NAME" \
    --policy-document "$STRIPPED" >/dev/null
  echo "  [OK] applied to $ROLE_NAME / $POLICY_NAME"
  echo ""
done

echo "=== done ==="
