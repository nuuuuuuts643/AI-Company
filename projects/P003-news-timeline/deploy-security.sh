#\!/bin/bash
# セキュリティインフラ作成スクリプト

REGION=${AWS_REGION:-ap-northeast-1}

echo "=== flotopic セキュリティインフラ作成 ==="

# Rate limits テーブル (TTL有効)
aws dynamodb create-table \
  --table-name flotopic-rate-limits \
  --attribute-definitions AttributeName=pk,AttributeType=S \
  --key-schema AttributeName=pk,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region $REGION 2>/dev/null || echo "flotopic-rate-limits already exists"

aws dynamodb update-time-to-live \
  --table-name flotopic-rate-limits \
  --time-to-live-specification Enabled=true,AttributeName=ttl \
  --region $REGION 2>/dev/null || true

# Analytics テーブル (TTL有効)
aws dynamodb create-table \
  --table-name flotopic-analytics \
  --attribute-definitions \
    AttributeName=userId,AttributeType=S \
    AttributeName=sk,AttributeType=S \
  --key-schema \
    AttributeName=userId,KeyType=HASH \
    AttributeName=sk,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --region $REGION 2>/dev/null || echo "flotopic-analytics already exists"

aws dynamodb update-time-to-live \
  --table-name flotopic-analytics \
  --time-to-live-specification Enabled=true,AttributeName=ttl \
  --region $REGION 2>/dev/null || true

# flotopic-users テーブル
aws dynamodb create-table \
  --table-name flotopic-users \
  --attribute-definitions AttributeName=userId,AttributeType=S \
  --key-schema AttributeName=userId,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region $REGION 2>/dev/null || echo "flotopic-users already exists"

# flotopic-favorites テーブル
aws dynamodb create-table \
  --table-name flotopic-favorites \
  --attribute-definitions \
    AttributeName=userId,AttributeType=S \
    AttributeName=topicId,AttributeType=S \
  --key-schema \
    AttributeName=userId,KeyType=HASH \
    AttributeName=topicId,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --region $REGION 2>/dev/null || echo "flotopic-favorites already exists"

echo "=== 完了 ==="
echo "Lambda同時実行数制限は各Lambda作成後に設定してください："
echo "aws lambda put-function-concurrency --function-name flotopic-comments --reserved-concurrent-executions 20"
echo "aws lambda put-function-concurrency --function-name flotopic-auth --reserved-concurrent-executions 10"
echo "aws lambda put-function-concurrency --function-name flotopic-analytics --reserved-concurrent-executions 10"
