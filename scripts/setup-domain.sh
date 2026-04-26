#!/bin/bash
# flotopic.com ドメイン完全セットアップスクリプト
# 実行前提: aws configure 済み、flotopic.com をSquarespaceで取得済み
# 実行方法: bash scripts/setup-domain.sh

set -e

DOMAIN="flotopic.com"
S3_BUCKET="p003-news-946554699567"
S3_WEBSITE_ENDPOINT="p003-news-946554699567.s3-website-ap-northeast-1.amazonaws.com"
REGION="ap-northeast-1"

echo "======================================"
echo " flotopic.com セットアップ開始"
echo "======================================"

# ─────────────────────────────────────────
# STEP 1: Route 53 ホストゾーン作成
# ─────────────────────────────────────────
echo ""
echo "[STEP 1] Route 53 ホストゾーン作成..."

HOSTED_ZONE=$(aws route53 create-hosted-zone \
  --name "$DOMAIN" \
  --caller-reference "flotopic-$(date +%s)" \
  --query 'HostedZone.Id' \
  --output text 2>/dev/null || true)

if [ -z "$HOSTED_ZONE" ]; then
  echo "  → ホストゾーンが既に存在する可能性があります。既存を取得..."
  HOSTED_ZONE=$(aws route53 list-hosted-zones-by-name \
    --dns-name "$DOMAIN" \
    --query 'HostedZones[0].Id' \
    --output text)
fi

ZONE_ID=$(echo "$HOSTED_ZONE" | sed 's|/hostedzone/||')
echo "  ✅ Zone ID: $ZONE_ID"

# ネームサーバー取得
echo ""
echo "[重要] Squarespaceのネームサーバーを以下に変更してください："
aws route53 get-hosted-zone --id "$ZONE_ID" \
  --query 'DelegationSet.NameServers' \
  --output text | tr '\t' '\n' | sed 's/^/  → /'

echo ""
echo "  Squarespace管理画面 → DNS → ネームサーバー → カスタム → 上記4つを入力"
echo ""
read -p "ネームサーバーの変更が完了したらEnterを押してください（後でやる場合もEnterでOK）..." _

# ─────────────────────────────────────────
# STEP 2: ACM SSL証明書 (us-east-1 固定)
# ─────────────────────────────────────────
echo ""
echo "[STEP 2] SSL証明書リクエスト (us-east-1)..."

CERT_ARN=$(aws acm request-certificate \
  --domain-name "$DOMAIN" \
  --subject-alternative-names "www.$DOMAIN" \
  --validation-method DNS \
  --region us-east-1 \
  --query 'CertificateArn' \
  --output text)

echo "  ✅ 証明書ARN: $CERT_ARN"
echo "  DNS検証レコードを取得中（30秒待機）..."
sleep 30

# DNS検証レコードをRoute 53に自動追加
VALIDATION_RECORDS=$(aws acm describe-certificate \
  --certificate-arn "$CERT_ARN" \
  --region us-east-1 \
  --query 'Certificate.DomainValidationOptions[*].ResourceRecord' \
  --output json)

echo "$VALIDATION_RECORDS" | python3 -c "
import json, sys, subprocess, time

records = json.load(sys.stdin)
zone_id = '$ZONE_ID'

for r in records:
    if not r:
        continue
    name = r.get('Name', '')
    value = r.get('Value', '')
    if not name or not value:
        continue

    change_batch = {
        'Changes': [{
            'Action': 'UPSERT',
            'ResourceRecordSet': {
                'Name': name,
                'Type': 'CNAME',
                'TTL': 300,
                'ResourceRecords': [{'Value': value}]
            }
        }]
    }

    import json as j
    batch_str = j.dumps(change_batch)
    result = subprocess.run([
        'aws', 'route53', 'change-resource-record-sets',
        '--hosted-zone-id', zone_id,
        '--change-batch', batch_str
    ], capture_output=True, text=True)

    if result.returncode == 0:
        print(f'  ✅ DNS検証レコード追加: {name}')
    else:
        print(f'  ⚠️ エラー: {result.stderr}')
"

echo ""
echo "  証明書の検証中... (最大10分かかります)"
echo "  バックグラウンドで進めるため先に進みます。"

# ─────────────────────────────────────────
# STEP 3: CloudFront ディストリビューション作成
# ─────────────────────────────────────────
echo ""
echo "[STEP 3] CloudFront ディストリビューション作成..."

# 証明書が有効になるまで待機（最大10分）
echo "  証明書の検証待機中..."
for i in $(seq 1 20); do
  STATUS=$(aws acm describe-certificate \
    --certificate-arn "$CERT_ARN" \
    --region us-east-1 \
    --query 'Certificate.Status' \
    --output text)
  echo "  [${i}/20] 状態: $STATUS"
  if [ "$STATUS" = "ISSUED" ]; then
    echo "  ✅ 証明書が有効になりました"
    break
  fi
  sleep 30
done

# CloudFront 設定
CF_CONFIG=$(cat <<EOF
{
  "CallerReference": "flotopic-cf-$(date +%s)",
  "Aliases": {
    "Quantity": 2,
    "Items": ["$DOMAIN", "www.$DOMAIN"]
  },
  "DefaultRootObject": "index.html",
  "Origins": {
    "Quantity": 1,
    "Items": [{
      "Id": "S3-$S3_BUCKET",
      "DomainName": "$S3_WEBSITE_ENDPOINT",
      "CustomOriginConfig": {
        "HTTPPort": 80,
        "HTTPSPort": 443,
        "OriginProtocolPolicy": "http-only"
      }
    }]
  },
  "DefaultCacheBehavior": {
    "TargetOriginId": "S3-$S3_BUCKET",
    "ViewerProtocolPolicy": "redirect-to-https",
    "CachePolicyId": "658327ea-f89d-4fab-a63d-7e88639e58f6",
    "Compress": true,
    "AllowedMethods": {
      "Quantity": 2,
      "Items": ["GET", "HEAD"]
    }
  },
  "CustomErrorResponses": {
    "Quantity": 1,
    "Items": [{
      "ErrorCode": 404,
      "ResponsePagePath": "/index.html",
      "ResponseCode": "200",
      "ErrorCachingMinTTL": 0
    }]
  },
  "Comment": "flotopic.com",
  "Enabled": true,
  "HttpVersion": "http2",
  "ViewerCertificate": {
    "ACMCertificateArn": "$CERT_ARN",
    "SSLSupportMethod": "sni-only",
    "MinimumProtocolVersion": "TLSv1.2_2021"
  }
}
EOF
)

CF_RESULT=$(aws cloudfront create-distribution \
  --distribution-config "$CF_CONFIG" \
  --query 'Distribution.[Id,DomainName]' \
  --output text)

CF_ID=$(echo "$CF_RESULT" | awk '{print $1}')
CF_DOMAIN=$(echo "$CF_RESULT" | awk '{print $2}')

echo "  ✅ CloudFront ID: $CF_ID"
echo "  ✅ CloudFront Domain: $CF_DOMAIN"

# ─────────────────────────────────────────
# STEP 4: Route 53 Aレコード（CloudFrontへ）
# ─────────────────────────────────────────
echo ""
echo "[STEP 4] Route 53 DNSレコード設定..."

# CF の Hosted Zone ID (固定値)
CF_HOSTED_ZONE_ID="Z2FDTNDATAQYW2"

aws route53 change-resource-record-sets \
  --hosted-zone-id "$ZONE_ID" \
  --change-batch "{
    \"Changes\": [
      {
        \"Action\": \"UPSERT\",
        \"ResourceRecordSet\": {
          \"Name\": \"$DOMAIN\",
          \"Type\": \"A\",
          \"AliasTarget\": {
            \"HostedZoneId\": \"$CF_HOSTED_ZONE_ID\",
            \"DNSName\": \"$CF_DOMAIN\",
            \"EvaluateTargetHealth\": false
          }
        }
      },
      {
        \"Action\": \"UPSERT\",
        \"ResourceRecordSet\": {
          \"Name\": \"www.$DOMAIN\",
          \"Type\": \"A\",
          \"AliasTarget\": {
            \"HostedZoneId\": \"$CF_HOSTED_ZONE_ID\",
            \"DNSName\": \"$CF_DOMAIN\",
            \"EvaluateTargetHealth\": false
          }
        }
      }
    ]
  }" > /dev/null

echo "  ✅ flotopic.com → CloudFront 設定完了"
echo "  ✅ www.flotopic.com → CloudFront 設定完了"

# ─────────────────────────────────────────
# STEP 5: S3バケットポリシー更新（CloudFront許可）
# ─────────────────────────────────────────
echo ""
echo "[STEP 5] S3バケットポリシー確認..."
echo "  → S3 Static Website Hostingのため既存設定で動作します"

# ─────────────────────────────────────────
# 完了報告
# ─────────────────────────────────────────
echo ""
echo "======================================"
echo " ✅ セットアップ完了"
echo "======================================"
echo ""
echo "CloudFront ID   : $CF_ID"
echo "CloudFront Domain: $CF_DOMAIN"
echo "Route 53 Zone ID: $ZONE_ID"
echo ""
echo "【次のステップ】"
echo "1. SquarespaceのネームサーバーをRoute 53のNSに変更（済みなら不要）"
echo "2. DNS反映に最大48時間かかります（通常数時間）"
echo "3. 反映後 https://flotopic.com でアクセス確認"
echo ""
echo "CloudFrontのデプロイに15分ほどかかります。"
echo "確認: aws cloudfront get-distribution --id $CF_ID --query 'Distribution.Status'"
echo ""

# CF IDをファイルに保存
echo "CF_DISTRIBUTION_ID=$CF_ID" >> .env.production
echo "CF_DOMAIN=$CF_DOMAIN" >> .env.production
echo "ZONE_ID=$ZONE_ID" >> .env.production

echo "設定値を .env.production に保存しました。"
