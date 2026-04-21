#\!/bin/bash
# AI-Company 一括デプロイ
# 使い方: bash deploy-all.sh
set -e

echo "======================================"
echo "  AI-Company 一括デプロイ"
echo "======================================"

# 1. git push
echo ""
echo "[1/3] GitHubに全変更をpush..."
cd "$(dirname "$0")"
git add -A
git diff --cached --quiet || git commit -m "$(date +%Y-%m-%d): CEO system + P003 UI + security fixes"
git push
echo "  ✅ push完了"

# 2. P003フロントエンドをS3にデプロイ
echo ""
echo "[2/3] P003フロントエンドをS3にデプロイ..."
aws s3 sync projects/P003-news-timeline/frontend/ \
  s3://p003-news-946554699567/ \
  --region ap-northeast-1 \
  --delete
echo "  ✅ S3デプロイ完了"
echo "  確認URL: http://p003-news-946554699567.s3-website-ap-northeast-1.amazonaws.com"

# 3. Lambda稼働確認
echo ""
echo "[3/3] Lambda稼働確認..."
STATE=$(aws lambda get-function-configuration \
  --function-name p003-fetcher \
  --region ap-northeast-1 \
  --query 'State' --output text 2>/dev/null || echo "ERROR")

if [ "$STATE" = "Active" ]; then
  echo "  ✅ Lambda: 稼働中"
else
  echo "  ❌ Lambda状態: $STATE（要確認）"
fi

RULE=$(aws events describe-rule \
  --name p003-fetcher-schedule \
  --region ap-northeast-1 \
  --query 'State' --output text 2>/dev/null || echo "ERROR")

if [ "$RULE" = "ENABLED" ]; then
  echo "  ✅ EventBridge: 30分ごとのスケジュール稼働中"
else
  echo "  ❌ EventBridgeルール状態: $RULE（要確認）"
fi

echo ""
echo "======================================"
echo "  完了"
echo "  明朝9時にSlackに秘書報告が届きます"
echo "======================================"
