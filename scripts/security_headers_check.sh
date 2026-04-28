#!/usr/bin/env bash
# scripts/security_headers_check.sh
#
# SLI 7: セキュリティヘッダ外部観測
# https://flotopic.com/ の HTTP response header を curl で取得し、
# 必須ヘッダ 5 種が全て付与されているかを物理検証する。
#
# 必須ヘッダ:
#   - strict-transport-security
#   - x-frame-options
#   - x-content-type-options
#   - referrer-policy
#   - permissions-policy
#
# 1 つでも欠落・空文字なら exit 1 + 欠落ヘッダ名を STDERR に出す。
# CI から呼ばれる想定 (.github/workflows/security-headers-check.yml)。
#
# 設計根拠:
#   - CloudFront response headers policy は管理画面で消える/上書きされる事故が起きうる。
#   - lambda 内部 metric では拾えない (CloudFront 層の設定変更だから)。
#   - 「外部から見える壊れ方」を 1 つの物理ゲートで検出する SLI。
#   - docs/sli-slo.md SLI 7 の実装本体。
#
# 参考: lessons-learned 2026-04-28「success-but-empty を CloudWatch では拾えない」

set -euo pipefail

URL="${1:-https://flotopic.com/}"

REQUIRED_HEADERS=(
  "strict-transport-security"
  "x-frame-options"
  "x-content-type-options"
  "referrer-policy"
  "permissions-policy"
)

echo "[security-headers-check] target=${URL}"
echo "[security-headers-check] timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# curl の output を一時ファイルに保存
TMP_HDR="$(mktemp)"
trap 'rm -f "$TMP_HDR"' EXIT

# -s: silent / -I: HEAD / -L: follow redirect / --max-time: タイムアウト
HTTP_CODE=$(curl -s -I -L --max-time 15 -o "$TMP_HDR" -w "%{http_code}" "$URL" || echo "000")

echo "[security-headers-check] http_code=${HTTP_CODE}"

if [[ "$HTTP_CODE" != "200" ]]; then
  echo "ERROR: HTTP code is not 200 (got ${HTTP_CODE}). cannot evaluate headers." >&2
  exit 2
fi

MISSING=()
for header in "${REQUIRED_HEADERS[@]}"; do
  # 大文字小文字無視・行頭一致
  if grep -iqE "^${header}:" "$TMP_HDR"; then
    value=$(grep -iE "^${header}:" "$TMP_HDR" | head -1 | sed -E "s/^[^:]+:[[:space:]]*//I" | tr -d '\r\n')
    if [[ -z "$value" ]]; then
      echo "  ❌ ${header}: <empty>"
      MISSING+=("$header(empty)")
    else
      echo "  ✅ ${header}: ${value}"
    fi
  else
    echo "  ❌ ${header}: <missing>"
    MISSING+=("$header")
  fi
done

if [[ ${#MISSING[@]} -gt 0 ]]; then
  echo ""
  echo "[security-headers-check] FAIL: missing/empty headers: ${MISSING[*]}" >&2
  exit 1
fi

echo ""
echo "[security-headers-check] PASS: all 5 required headers present"
exit 0
