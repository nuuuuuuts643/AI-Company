#!/bin/bash
# P003 News Timeline - 一発デプロイスクリプト
set -e

REGION="ap-northeast-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
TABLE="p003-topics"
BUCKET="p003-news-${ACCOUNT_ID}"
FETCHER="p003-fetcher"
API_FN="p003-api"
ROLE="p003-lambda-role"
ENV_VARS="Variables={TABLE_NAME=${TABLE},REGION=${REGION}}"

echo ""
echo "======================================="
echo "  P003 News Timeline デプロイ開始"
echo "  アカウントID : $ACCOUNT_ID"
echo "  リージョン   : $REGION"
echo "======================================="
echo ""

# ---- 1. DynamoDB ----
echo "[1/7] DynamoDB テーブル作成..."
aws dynamodb create-table \
  --table-name "$TABLE" \
  --attribute-definitions \
    AttributeName=topicId,AttributeType=S \
    AttributeName=SK,AttributeType=S \
  --key-schema \
    AttributeName=topicId,KeyType=HASH \
    AttributeName=SK,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --region "$REGION" 2>/dev/null \
  && echo "  -> 作成完了" \
  || echo "  -> 既に存在（スキップ）"

# ---- 2. S3 ----
echo "[2/7] S3 バケット作成..."
aws s3api create-bucket \
  --bucket "$BUCKET" \
  --region "$REGION" \
  --create-bucket-configuration LocationConstraint="$REGION" 2>/dev/null \
  && echo "  -> 作成完了" \
  || echo "  -> 既に存在（スキップ）"

aws s3api delete-public-access-block --bucket "$BUCKET" 2>/dev/null || true
aws s3api put-bucket-policy --bucket "$BUCKET" --policy "{
  \"Version\": \"2012-10-17\",
  \"Statement\": [{
    \"Effect\": \"Allow\",
    \"Principal\": \"*\",
    \"Action\": \"s3:GetObject\",
    \"Resource\": \"arn:aws:s3:::${BUCKET}/*\"
  }]
}"
aws s3api put-bucket-website --bucket "$BUCKET" \
  --website-configuration '{"IndexDocument":{"Suffix":"index.html"},"ErrorDocument":{"Key":"index.html"}}'
echo "  -> 静的サイトホスティング設定完了"

# ---- 3. IAM ロール ----
echo "[3/7] Lambda 実行ロール作成..."
aws iam create-role \
  --role-name "$ROLE" \
  --assume-role-policy-document '{
    "Version":"2012-10-17",
    "Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]
  }' 2>/dev/null \
  && echo "  -> 作成完了" \
  || echo "  -> 既に存在（スキップ）"

for POLICY in \
  arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess \
  arn:aws:iam::aws:policy/AmazonS3FullAccess \
  arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
do
  aws iam attach-role-policy --role-name "$ROLE" --policy-arn "$POLICY" 2>/dev/null || true
done

echo "  -> IAMロール反映待ち（15秒）..."
sleep 15
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE}"

# ---- 4. Fetcher Lambda ----
echo "[4/7] Fetcher Lambda デプロイ..."
cd lambda/fetcher
zip -q function.zip handler.py
aws lambda create-function \
  --function-name "$FETCHER" \
  --runtime python3.12 \
  --role "$ROLE_ARN" \
  --handler handler.lambda_handler \
  --zip-file fileb://function.zip \
  --timeout 120 --memory-size 256 \
  --environment "$ENV_VARS" \
  --region "$REGION" 2>/dev/null \
  && echo "  -> 新規作成完了" \
  || {
    aws lambda update-function-code --function-name "$FETCHER" --zip-file fileb://function.zip --region "$REGION" > /dev/null
    aws lambda wait function-updated --function-name "$FETCHER" --region "$REGION"
    aws lambda update-function-configuration --function-name "$FETCHER" --timeout 120 --memory-size 256 --environment "$ENV_VARS" --region "$REGION" > /dev/null
    echo "  -> 更新完了"
  }
rm function.zip
cd ../..

# ---- 5. API Lambda ----
echo "[5/7] API Lambda デプロイ..."
cd lambda/api
zip -q function.zip handler.py
aws lambda create-function \
  --function-name "$API_FN" \
  --runtime python3.12 \
  --role "$ROLE_ARN" \
  --handler handler.lambda_handler \
  --zip-file fileb://function.zip \
  --timeout 30 --memory-size 128 \
  --environment "$ENV_VARS" \
  --region "$REGION" 2>/dev/null \
  && echo "  -> 新規作成完了" \
  || {
    aws lambda update-function-code --function-name "$API_FN" --zip-file fileb://function.zip --region "$REGION" > /dev/null
    aws lambda wait function-updated --function-name "$API_FN" --region "$REGION"
    aws lambda update-function-configuration --function-name "$API_FN" --timeout 30 --memory-size 128 --environment "$ENV_VARS" --region "$REGION" > /dev/null
    echo "  -> 更新完了"
  }
rm function.zip
cd ../..

# Function URL: 既存確認→なければ作成
echo "  -> Function URL 設定..."
aws lambda wait function-updated --function-name "$API_FN" --region "$REGION" 2>/dev/null || true
aws lambda wait function-active  --function-name "$API_FN" --region "$REGION"

API_URL=$(aws lambda get-function-url-config \
  --function-name "$API_FN" --region "$REGION" \
  --query FunctionUrl --output text 2>/dev/null) || API_URL=""

if [ -z "$API_URL" ] || [ "$API_URL" = "None" ]; then
  API_URL=$(aws lambda create-function-url-config \
    --function-name "$API_FN" \
    --auth-type NONE \
    --cors '{"AllowOrigins":["*"],"AllowMethods":["*"],"AllowHeaders":["*"]}' \
    --region "$REGION" \
    --query FunctionUrl --output text)
  echo "  -> 新規作成: $API_URL"
else
  echo "  -> 既存URLを使用: $API_URL"
fi

aws lambda add-permission \
  --function-name "$API_FN" \
  --statement-id AllowPublicAccess \
  --action lambda:InvokeFunctionUrl \
  --principal "*" \
  --function-url-auth-type NONE \
  --region "$REGION" 2>/dev/null || true

echo "  -> API URL: $API_URL"

# ---- 6. EventBridge ----
echo "[6/7] EventBridge スケジュール設定..."
RULE_ARN=$(aws events put-rule \
  --name "p003-schedule" \
  --schedule-expression "rate(30 minutes)" \
  --state ENABLED \
  --region "$REGION" \
  --query RuleArn --output text)

FETCHER_ARN="arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:${FETCHER}"
aws lambda add-permission \
  --function-name "$FETCHER" \
  --statement-id AllowEventBridge \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn "$RULE_ARN" \
  --region "$REGION" 2>/dev/null || true

aws events put-targets \
  --rule "p003-schedule" \
  --targets "Id=1,Arn=${FETCHER_ARN}" \
  --region "$REGION" > /dev/null
echo "  -> 30分ごとの自動実行を設定完了"

# ---- 7. フロントエンド ----
echo "[7/7] フロントエンドをアップロード..."
echo "const API_BASE = '${API_URL}';" > frontend/config.js
aws s3 sync frontend/ "s3://${BUCKET}/" --delete

SITE_URL="http://${BUCKET}.s3-website-${REGION}.amazonaws.com"

echo ""
echo "======================================="
echo "  デプロイ完了！"
echo "======================================="
echo "  サイトURL : $SITE_URL"
echo "  API URL   : $API_URL"
echo ""
echo "  最初のニュース取得を実行中..."
aws lambda invoke \
  --function-name "$FETCHER" \
  --region "$REGION" \
  /tmp/p003-response.json > /dev/null
cat /tmp/p003-response.json
echo ""
echo "  30秒後にサイトURLをブラウザで開いてください。"
echo "  以降は30分ごとに自動更新されます。"
