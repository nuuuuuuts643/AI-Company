#!/bin/bash
# setup-cloudfront-headers.sh
# CloudFront ディストリビューションにセキュリティヘッダーポリシーを追加するスクリプト

set -e

# .env.production から CF_DISTRIBUTION_ID を読み込む（存在する場合）
if [ -f "$(dirname "$0")/../.env.production" ]; then
  source "$(dirname "$0")/../.env.production"
  echo "[INFO] .env.production を読み込みました"
fi

# CF_DISTRIBUTION_ID が未設定の場合は引数またはエラー
if [ -z "$CF_DISTRIBUTION_ID" ]; then
  if [ -n "$1" ]; then
    CF_DISTRIBUTION_ID="$1"
    echo "[INFO] 引数から CF_DISTRIBUTION_ID を取得: $CF_DISTRIBUTION_ID"
  else
    echo "[ERROR] CF_DISTRIBUTION_ID が設定されていません。"
    echo "  使用法: CF_DISTRIBUTION_ID=EXAMPLEID bash $0"
    echo "  または: bash $0 EXAMPLEID"
    echo "  または: .env.production に CF_DISTRIBUTION_ID=... を記述してください"
    exit 1
  fi
fi

REGION="${AWS_DEFAULT_REGION:-us-east-1}"
POLICY_NAME="flotopic-security-headers-$(date +%Y%m%d)"

echo ""
echo "=== CloudFront セキュリティヘッダーポリシー作成 ==="
echo "ディストリビューション ID : $CF_DISTRIBUTION_ID"
echo "リージョン               : $REGION"
echo "ポリシー名               : $POLICY_NAME"
echo ""

# ----------------------------------------------------------------
# Step 1: レスポンスヘッダーポリシーを作成
# ----------------------------------------------------------------
echo "[1/3] レスポンスヘッダーポリシーを作成中..."

POLICY_CONFIG=$(cat <<EOF
{
  "Name": "${POLICY_NAME}",
  "Comment": "Flotopic security headers policy",
  "SecurityHeadersConfig": {
    "StrictTransportSecurity": {
      "Override": true,
      "IncludeSubdomains": true,
      "Preload": false,
      "AccessControlMaxAgeSec": 31536000
    },
    "ContentTypeOptions": {
      "Override": true
    },
    "FrameOptions": {
      "Override": true,
      "FrameOption": "DENY"
    },
    "XSSProtection": {
      "Override": true,
      "Protection": true,
      "ModeBlock": true
    },
    "ReferrerPolicy": {
      "Override": true,
      "ReferrerPolicy": "strict-origin-when-cross-origin"
    },
    "ContentSecurityPolicy": {
      "Override": true,
      "ContentSecurityPolicy": "default-src 'self' https: data: 'unsafe-inline' 'unsafe-eval'"
    }
  },
  "CustomHeadersConfig": {
    "Quantity": 0,
    "Items": []
  }
}
EOF
)

POLICY_RESPONSE=$(aws cloudfront create-response-headers-policy \
  --response-headers-policy-config "$POLICY_CONFIG" \
  --output json)

POLICY_ID=$(echo "$POLICY_RESPONSE" | python3 -c "import json,sys; print(json.load(sys.stdin)['ResponseHeadersPolicy']['Id'])")
echo "[OK] ポリシー作成完了: ID = $POLICY_ID"

# ----------------------------------------------------------------
# Step 2: 既存のディストリビューション設定を取得
# ----------------------------------------------------------------
echo "[2/3] ディストリビューション設定を取得中..."

DIST_RESPONSE=$(aws cloudfront get-distribution-config \
  --id "$CF_DISTRIBUTION_ID" \
  --output json)

ETAG=$(echo "$DIST_RESPONSE" | python3 -c "import json,sys; print(json.load(sys.stdin)['ETag'])")
DIST_CONFIG=$(echo "$DIST_RESPONSE" | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin)['DistributionConfig']))")

echo "[OK] ETag 取得: $ETAG"

# ----------------------------------------------------------------
# Step 3: Default Cache Behavior にポリシーを適用して更新
# ----------------------------------------------------------------
echo "[3/3] ディストリビューションを更新中..."

UPDATED_CONFIG=$(echo "$DIST_CONFIG" | python3 -c "
import json, sys
config = json.load(sys.stdin)
policy_id = '${POLICY_ID}'

# DefaultCacheBehavior にポリシーを追加
config['DefaultCacheBehavior']['ResponseHeadersPolicyId'] = policy_id

# CacheBehaviors にも適用（存在する場合）
if 'CacheBehaviors' in config and config['CacheBehaviors'].get('Quantity', 0) > 0:
    for cb in config['CacheBehaviors'].get('Items', []):
        cb['ResponseHeadersPolicyId'] = policy_id

print(json.dumps(config))
")

aws cloudfront update-distribution \
  --id "$CF_DISTRIBUTION_ID" \
  --if-match "$ETAG" \
  --distribution-config "$UPDATED_CONFIG" \
  --output json > /dev/null

echo "[OK] ディストリビューション更新完了"

# ----------------------------------------------------------------
# 完了メッセージ
# ----------------------------------------------------------------
echo ""
echo "=== 完了 ==="
echo "セキュリティヘッダーポリシー ID : $POLICY_ID"
echo "適用先ディストリビューション   : $CF_DISTRIBUTION_ID"
echo ""
echo "適用済みヘッダー:"
echo "  Strict-Transport-Security : max-age=31536000; includeSubDomains"
echo "  X-Content-Type-Options    : nosniff"
echo "  X-Frame-Options           : DENY"
echo "  X-XSS-Protection          : 1; mode=block"
echo "  Referrer-Policy           : strict-origin-when-cross-origin"
echo "  Content-Security-Policy   : default-src 'self' https: data: 'unsafe-inline' 'unsafe-eval'"
echo ""
echo "CloudFrontの反映には最大15分かかる場合があります。"
echo "確認: https://console.aws.amazon.com/cloudfront/home#distribution-settings:$CF_DISTRIBUTION_ID"
