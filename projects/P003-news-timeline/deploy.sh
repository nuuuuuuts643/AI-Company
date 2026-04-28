#!/bin/bash
# P003 News Timeline - 一発デプロイスクリプト
set -e

# スクリプトの場所を基準にCWDを固定（どこから呼ばれても正しいパスで動く）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

REGION="ap-northeast-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
TABLE="p003-topics"
COMMENTS_TABLE="ai-company-comments"
BUCKET="p003-news-${ACCOUNT_ID}"
FETCHER="p003-fetcher"
PROCESSOR="p003-processor"
API_FN="p003-api"
COMMENTS_FN="p003-comments"
ROLE="p003-lambda-role"
ENV_VARS="Variables={TABLE_NAME=${TABLE},REGION=${REGION},SITE_URL=https://flotopic.com,S3_BUCKET=${BUCKET}}"
COMMENTS_ENV_VARS="Variables={COMMENTS_TABLE=${COMMENTS_TABLE},REGION=${REGION},S3_BUCKET=${BUCKET},CLOUDFRONT_DOMAIN=flotopic.com}"

echo ""
echo "======================================="
echo "  P003 News Timeline デプロイ開始"
echo "  アカウントID : $ACCOUNT_ID"
echo "  リージョン   : $REGION"
echo "======================================="
echo ""

# ---- 1. DynamoDB (ニューストピック) ----
echo "[1/8] DynamoDB テーブル作成..."
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

# ---- 1b. DynamoDB (コメント) ----
echo "  -> コメントテーブル作成..."
aws dynamodb create-table \
  --table-name "$COMMENTS_TABLE" \
  --attribute-definitions \
    AttributeName=topicId,AttributeType=S \
    AttributeName=SK,AttributeType=S \
  --key-schema \
    AttributeName=topicId,KeyType=HASH \
    AttributeName=SK,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --region "$REGION" 2>/dev/null \
  && {
    echo "  -> コメントテーブル作成完了"
    # TTL 有効化（レートリミット & コメント自動削除）
    sleep 5
    aws dynamodb update-time-to-live \
      --table-name "$COMMENTS_TABLE" \
      --time-to-live-specification "Enabled=true,AttributeName=ttl" \
      --region "$REGION" > /dev/null 2>&1 \
      && echo "  -> TTL 有効化完了" || echo "  -> TTL 設定スキップ"
  } \
  || echo "  -> コメントテーブル既に存在（スキップ）"

# ---- 1c. DynamoDB PITR有効化 ----
# データ破損・誤削除からの復元保険（35日間のポイントインタイムリカバリ）
aws dynamodb update-continuous-backups \
  --table-name "$TABLE" \
  --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true \
  --region "$REGION" 2>/dev/null && echo "✅ PITR有効化済み" || echo "⚠️ PITR設定スキップ（テーブル未作成かも）"

# ---- 2. S3 ----
echo "[2/8] S3 バケット作成..."
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
  --website-configuration '{"IndexDocument":{"Suffix":"index.html"},"ErrorDocument":{"Key":"404.html"}}'
echo "  -> 静的サイトホスティング設定完了"

# S3 CORS設定（アバター画像の直接PUTアップロードに必要）
aws s3api put-bucket-cors --bucket "$BUCKET" --cors-configuration '{
  "CORSRules": [
    {
      "AllowedHeaders": ["*"],
      "AllowedMethods": ["PUT"],
      "AllowedOrigins": ["https://flotopic.com"],
      "ExposeHeaders": ["ETag"],
      "MaxAgeSeconds": 3600
    },
    {
      "AllowedHeaders": ["*"],
      "AllowedMethods": ["GET"],
      "AllowedOrigins": ["*"],
      "MaxAgeSeconds": 86400
    }
  ]
}'
echo "  -> S3 CORS設定完了（アバターPUT許可）"

# ---- 3. IAM ロール ----
echo "[3/8] Lambda 実行ロール作成..."
aws iam create-role \
  --role-name "$ROLE" \
  --assume-role-policy-document '{
    "Version":"2012-10-17",
    "Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]
  }' 2>/dev/null \
  && echo "  -> 作成完了" \
  || echo "  -> 既に存在（スキップ）"

# 基本実行ロールのみアタッチ（DynamoDB/S3はインラインポリシーで最小権限管理）
aws iam attach-role-policy --role-name "$ROLE" \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole 2>/dev/null || true

# 最小権限インラインポリシーを常に上書き適用（FullAccessを使わない）
aws iam put-role-policy \
  --role-name "$ROLE" \
  --policy-name flotopic-least-privilege \
  --policy-document '{
    "Version":"2012-10-17",
    "Statement":[
      {"Sid":"DynamoDBSpecificTables","Effect":"Allow",
       "Action":["dynamodb:GetItem","dynamodb:PutItem","dynamodb:UpdateItem","dynamodb:DeleteItem","dynamodb:Query","dynamodb:Scan","dynamodb:BatchGetItem","dynamodb:BatchWriteItem","dynamodb:DescribeTable","dynamodb:ConditionCheckItem"],
       "Resource":["arn:aws:dynamodb:ap-northeast-1:'"${ACCOUNT_ID}"':table/p003-topics","arn:aws:dynamodb:ap-northeast-1:'"${ACCOUNT_ID}"':table/p003-topics/index/*","arn:aws:dynamodb:ap-northeast-1:'"${ACCOUNT_ID}"':table/ai-company-comments","arn:aws:dynamodb:ap-northeast-1:'"${ACCOUNT_ID}"':table/ai-company-comments/index/*","arn:aws:dynamodb:ap-northeast-1:'"${ACCOUNT_ID}"':table/ai-company-memory","arn:aws:dynamodb:ap-northeast-1:'"${ACCOUNT_ID}"':table/ai-company-x-posts","arn:aws:dynamodb:ap-northeast-1:'"${ACCOUNT_ID}"':table/ai-company-bluesky-posts","arn:aws:dynamodb:ap-northeast-1:'"${ACCOUNT_ID}"':table/ai-company-agent-status","arn:aws:dynamodb:ap-northeast-1:'"${ACCOUNT_ID}"':table/ai-company-audit","arn:aws:dynamodb:ap-northeast-1:'"${ACCOUNT_ID}"':table/flotopic-analytics","arn:aws:dynamodb:ap-northeast-1:'"${ACCOUNT_ID}"':table/flotopic-favorites","arn:aws:dynamodb:ap-northeast-1:'"${ACCOUNT_ID}"':table/flotopic-rate-limits","arn:aws:dynamodb:ap-northeast-1:'"${ACCOUNT_ID}"':table/flotopic-users"]},
      {"Sid":"S3SpecificBucket","Effect":"Allow",
       "Action":["s3:GetObject","s3:PutObject","s3:DeleteObject","s3:ListBucket","s3:GetBucketLocation"],
       "Resource":["arn:aws:s3:::p003-news-946554699567","arn:aws:s3:::p003-news-946554699567/*","arn:aws:s3:::p003-news-staging-946554699567","arn:aws:s3:::p003-news-staging-946554699567/*"]},
      {"Sid":"CloudWatchMetrics","Effect":"Allow",
       "Action":["cloudwatch:GetMetricStatistics","cloudwatch:PutMetricData"],
       "Resource":"*"},
      {"Sid":"ProcessorDLQ","Effect":"Allow",
       "Action":"sqs:SendMessage",
       "Resource":"arn:aws:sqs:ap-northeast-1:'"${ACCOUNT_ID}"':p003-processor-dlq"}
    ]
  }' 2>/dev/null && echo "  -> 最小権限ポリシー適用済み" || true

# FullAccessが残っていたら剥がす（移行期対応）
aws iam detach-role-policy --role-name "$ROLE" \
  --policy-arn arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess 2>/dev/null || true
aws iam detach-role-policy --role-name "$ROLE" \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess 2>/dev/null || true

echo "  -> IAMロール反映待ち（15秒）..."
sleep 15
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE}"

# ---- 4. Fetcher Lambda ----
echo "[4/8] Fetcher Lambda デプロイ..."
cd lambda/fetcher
zip -q function.zip *.py
aws lambda create-function \
  --function-name "$FETCHER" \
  --runtime python3.12 \
  --role "$ROLE_ARN" \
  --handler handler.lambda_handler \
  --zip-file fileb://function.zip \
  --timeout 900 --memory-size 512 \
  --environment "$ENV_VARS" \
  --region "$REGION" 2>/dev/null \
  && echo "  -> 新規作成完了" \
  || {
    aws lambda update-function-code --function-name "$FETCHER" --zip-file fileb://function.zip --region "$REGION" > /dev/null
    aws lambda wait function-updated --function-name "$FETCHER" --region "$REGION"
    aws lambda update-function-configuration --function-name "$FETCHER" --timeout 900 --memory-size 512 --environment "$ENV_VARS" --region "$REGION" > /dev/null
    echo "  -> 更新完了"
  }
# リトライ0設定（タイムアウト時の連鎖リトライ防止）
aws lambda put-function-event-invoke-config --function-name "$FETCHER" \
  --maximum-retry-attempts 0 --maximum-event-age-in-seconds 300 --region "$REGION" > /dev/null
rm function.zip
cd ../..

# ---- 5. API Lambda ----
echo "[5/8] API Lambda デプロイ..."
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

# ---- 6. Comments Lambda ----
echo "[6/8] Comments Lambda デプロイ..."
cd lambda/comments
zip -q function.zip handler.py
aws lambda create-function \
  --function-name "$COMMENTS_FN" \
  --runtime python3.12 \
  --role "$ROLE_ARN" \
  --handler handler.lambda_handler \
  --zip-file fileb://function.zip \
  --timeout 10 --memory-size 128 \
  --environment "$COMMENTS_ENV_VARS" \
  --region "$REGION" 2>/dev/null \
  && echo "  -> 新規作成完了" \
  || {
    aws lambda update-function-code --function-name "$COMMENTS_FN" --zip-file fileb://function.zip --region "$REGION" > /dev/null
    aws lambda wait function-updated --function-name "$COMMENTS_FN" --region "$REGION"
    aws lambda update-function-configuration --function-name "$COMMENTS_FN" --timeout 10 --memory-size 128 --environment "$COMMENTS_ENV_VARS" --region "$REGION" > /dev/null
    echo "  -> 更新完了"
  }
rm function.zip
cd ../..

# Comments Function URL
echo "  -> Comments Function URL 設定..."
aws lambda wait function-updated --function-name "$COMMENTS_FN" --region "$REGION" 2>/dev/null || true
aws lambda wait function-active  --function-name "$COMMENTS_FN" --region "$REGION"

COMMENTS_URL=$(aws lambda get-function-url-config \
  --function-name "$COMMENTS_FN" --region "$REGION" \
  --query FunctionUrl --output text 2>/dev/null) || COMMENTS_URL=""

if [ -z "$COMMENTS_URL" ] || [ "$COMMENTS_URL" = "None" ]; then
  COMMENTS_URL=$(aws lambda create-function-url-config \
    --function-name "$COMMENTS_FN" \
    --auth-type NONE \
    --cors '{"AllowOrigins":["*"],"AllowMethods":["GET","POST"],"AllowHeaders":["Content-Type"]}' \
    --region "$REGION" \
    --query FunctionUrl --output text)
  echo "  -> 新規作成: $COMMENTS_URL"
else
  echo "  -> 既存URLを使用: $COMMENTS_URL"
fi

aws lambda add-permission \
  --function-name "$COMMENTS_FN" \
  --statement-id AllowPublicAccess \
  --action lambda:InvokeFunctionUrl \
  --principal "*" \
  --function-url-auth-type NONE \
  --region "$REGION" 2>/dev/null || true

echo "  -> Comments URL: $COMMENTS_URL"

# ---- 4b. Processor Lambda ----
# ANTHROPIC_API_KEY: 環境変数に設定されていればそれを使い、なければLambdaの現在値を保持
_CURRENT_ANTHROPIC=$(aws lambda get-function-configuration \
  --function-name "$PROCESSOR" --region "$REGION" \
  --query 'Environment.Variables.ANTHROPIC_API_KEY' --output text 2>/dev/null || echo "")
_EFFECTIVE_ANTHROPIC="${ANTHROPIC_API_KEY:-$_CURRENT_ANTHROPIC}"
if [ -n "$_EFFECTIVE_ANTHROPIC" ] && [ "$_EFFECTIVE_ANTHROPIC" != "None" ]; then
  PROCESSOR_ENV_VARS="Variables={TABLE_NAME=${TABLE},S3_BUCKET=${BUCKET},REGION=${REGION},SITE_URL=https://flotopic.com,ANTHROPIC_API_KEY=${_EFFECTIVE_ANTHROPIC}}"
  echo "  -> ANTHROPIC_API_KEY: 設定済み"
else
  PROCESSOR_ENV_VARS="Variables={TABLE_NAME=${TABLE},S3_BUCKET=${BUCKET},REGION=${REGION},SITE_URL=https://flotopic.com}"
  echo "  ⚠️  ANTHROPIC_API_KEY 未設定 — AI要約が動きません。手動で設定してください。"
fi
echo "[4b] Processor Lambda デプロイ（バッチAI処理）..."
cd lambda/processor
zip -q function.zip *.py
aws lambda create-function \
  --function-name "$PROCESSOR" \
  --runtime python3.12 \
  --role "$ROLE_ARN" \
  --handler handler.lambda_handler \
  --zip-file fileb://function.zip \
  --timeout 900 --memory-size 512 \
  --environment "$PROCESSOR_ENV_VARS" \
  --region "$REGION" 2>/dev/null \
  && echo "  -> 新規作成完了" \
  || {
    aws lambda update-function-code --function-name "$PROCESSOR" --zip-file fileb://function.zip --region "$REGION" > /dev/null
    aws lambda wait function-updated --function-name "$PROCESSOR" --region "$REGION"
    aws lambda update-function-configuration --function-name "$PROCESSOR" --timeout 900 --memory-size 512 --environment "$PROCESSOR_ENV_VARS" --region "$REGION" > /dev/null
    echo "  -> 更新完了"
  }
# DLQ設定（AI要約失敗時のサイレント消失を防止）
aws lambda put-function-event-invoke-config --function-name "$PROCESSOR" \
  --maximum-retry-attempts 1 --region "$REGION" > /dev/null
aws lambda update-function-configuration --function-name "$PROCESSOR" \
  --dead-letter-config TargetArn="arn:aws:sqs:${REGION}:${ACCOUNT_ID}:p003-processor-dlq" \
  --region "$REGION" > /dev/null 2>&1 || true
rm function.zip
cd ../..

# ---- 7. EventBridge ----
echo "[7/8] EventBridge スケジュール設定..."

# Fetcher: 30分ごと（2026-04-25 5分→30分に修正、p003-scheduleは削除済み）
FETCHER_RULE_ARN=$(aws events put-rule \
  --name "p003-fetcher-schedule" \
  --schedule-expression "rate(30 minutes)" \
  --state ENABLED \
  --region "$REGION" \
  --query RuleArn --output text)

FETCHER_ARN="arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:${FETCHER}"
aws lambda add-permission \
  --function-name "$FETCHER" \
  --statement-id AllowEventBridgeFetcher \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn "$FETCHER_RULE_ARN" \
  --region "$REGION" 2>/dev/null || true

# 既存ターゲットを全削除してから再登録（重複ターゲット防止）
# --output json で確実にID一覧取得し、個別に削除する
_EXISTING_IDS=$(aws events list-targets-by-rule --rule "p003-fetcher-schedule" \
  --region "$REGION" --query 'Targets[].Id' --output json 2>/dev/null \
  | python3 -c "import json,sys; ids=json.load(sys.stdin); print(' '.join(ids))" 2>/dev/null || echo "")
if [ -n "$_EXISTING_IDS" ]; then
  aws events remove-targets --rule "p003-fetcher-schedule" \
    --ids $_EXISTING_IDS --region "$REGION" > /dev/null 2>&1 || true
fi
aws events put-targets \
  --rule "p003-fetcher-schedule" \
  --targets "Id=1,Arn=${FETCHER_ARN}" \
  --region "$REGION" > /dev/null
echo "  -> Fetcher: 30分ごとの自動実行を設定完了"

# Processor: 1日2回 JST 08:00 / 17:00 (2026-04-29 コスト削減のため日中2回に変更)
# UTC換算: 23:00 / 08:00（JST = UTC+9）
# 即時処理は fetcher が新規トピック作成時に invoke (maxApiCalls=10) で別途走る
# cron(分 時 日 月 曜 年) ← AWS EventBridge書式
PROCESSOR_RULE_ARN=$(aws events put-rule \
  --name "p003-processor-schedule" \
  --schedule-expression "cron(0 23,8 * * ? *)" \
  --state ENABLED \
  --region "$REGION" \
  --query RuleArn --output text)

PROCESSOR_ARN="arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:${PROCESSOR}"
aws lambda add-permission \
  --function-name "$PROCESSOR" \
  --statement-id AllowEventBridgeProcessor \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn "$PROCESSOR_RULE_ARN" \
  --region "$REGION" 2>/dev/null || true

aws events put-targets \
  --rule "p003-processor-schedule" \
  --targets "Id=1,Arn=${PROCESSOR_ARN}" \
  --region "$REGION" > /dev/null
echo "  -> Processor: JST 8:00/17:00 の自動実行を設定完了 (UTC 23:00/08:00)"

# ---- 8. フロントエンド (config.js は全Lambda URL確定後に書き込み) ----
echo "[8/8] フロントエンドデプロイの準備..."
SITE_URL="https://flotopic.com"



# ---- 6b. Auth Lambda ----
AUTH_FN="flotopic-auth"
AUTH_ENV_VARS="Variables={REGION=${REGION},TABLE_NAME=${TABLE}}"
echo "[6b] Auth Lambda デプロイ..."
cd lambda/auth
zip -q function.zip handler.py
aws lambda create-function \
  --function-name "$AUTH_FN" \
  --runtime python3.12 \
  --role "$ROLE_ARN" \
  --handler handler.lambda_handler \
  --zip-file fileb://function.zip \
  --timeout 10 --memory-size 128 \
  --environment "$AUTH_ENV_VARS" \
  --region "$REGION" 2>/dev/null \
  && echo "  -> 新規作成完了" \
  || {
    aws lambda update-function-code --function-name "$AUTH_FN" --zip-file fileb://function.zip --region "$REGION" > /dev/null
    aws lambda wait function-updated --function-name "$AUTH_FN" --region "$REGION"
    aws lambda update-function-configuration --function-name "$AUTH_FN" --timeout 10 --memory-size 128 --environment "$AUTH_ENV_VARS" --region "$REGION" > /dev/null
    echo "  -> 更新完了"
  }
rm function.zip
cd ../..

# Auth Function URL
echo "  -> Auth Function URL 設定..."
aws lambda wait function-updated --function-name "$AUTH_FN" --region "$REGION" 2>/dev/null || true
aws lambda wait function-active  --function-name "$AUTH_FN" --region "$REGION"

AUTH_URL=$(aws lambda get-function-url-config \
  --function-name "$AUTH_FN" --region "$REGION" \
  --query FunctionUrl --output text 2>/dev/null) || AUTH_URL=""

if [ -z "$AUTH_URL" ] || [ "$AUTH_URL" = "None" ]; then
  AUTH_URL=$(aws lambda create-function-url-config \
    --function-name "$AUTH_FN" \
    --auth-type NONE \
    --cors '{"AllowOrigins":["*"],"AllowMethods":["POST"],"AllowHeaders":["Content-Type","Authorization"]}' \
    --region "$REGION" \
    --query FunctionUrl --output text)
  echo "  -> 新規作成: $AUTH_URL"
else
  echo "  -> 既存URLを使用: $AUTH_URL"
fi

aws lambda add-permission \
  --function-name "$AUTH_FN" \
  --statement-id AllowPublicAccess \
  --action lambda:InvokeFunctionUrl \
  --principal "*" \
  --function-url-auth-type NONE \
  --region "$REGION" 2>/dev/null || true

echo "  -> Auth URL: $AUTH_URL"

# ---- 6c. Favorites Lambda ----
FAVORITES_FN="flotopic-favorites"
FAVORITES_TABLE="flotopic-favorites"
FAVORITES_ENV_VARS="Variables={REGION=${REGION},FAVORITES_TABLE=${FAVORITES_TABLE}}"
echo "[6c] Favorites Lambda デプロイ..."
cd lambda/favorites
zip -q function.zip handler.py
aws lambda create-function \
  --function-name "$FAVORITES_FN" \
  --runtime python3.12 \
  --role "$ROLE_ARN" \
  --handler handler.lambda_handler \
  --zip-file fileb://function.zip \
  --timeout 10 --memory-size 128 \
  --environment "$FAVORITES_ENV_VARS" \
  --region "$REGION" 2>/dev/null \
  && echo "  -> 新規作成完了" \
  || {
    aws lambda update-function-code --function-name "$FAVORITES_FN" --zip-file fileb://function.zip --region "$REGION" > /dev/null
    aws lambda wait function-updated --function-name "$FAVORITES_FN" --region "$REGION"
    aws lambda update-function-configuration --function-name "$FAVORITES_FN" --timeout 10 --memory-size 128 --environment "$FAVORITES_ENV_VARS" --region "$REGION" > /dev/null
    echo "  -> 更新完了"
  }
rm function.zip
cd ../..

# Favorites Function URL
echo "  -> Favorites Function URL 設定..."
aws lambda wait function-updated --function-name "$FAVORITES_FN" --region "$REGION" 2>/dev/null || true
aws lambda wait function-active  --function-name "$FAVORITES_FN" --region "$REGION"

FAVORITES_URL=$(aws lambda get-function-url-config \
  --function-name "$FAVORITES_FN" --region "$REGION" \
  --query FunctionUrl --output text 2>/dev/null) || FAVORITES_URL=""

if [ -z "$FAVORITES_URL" ] || [ "$FAVORITES_URL" = "None" ]; then
  FAVORITES_URL=$(aws lambda create-function-url-config \
    --function-name "$FAVORITES_FN" \
    --auth-type NONE \
    --cors '{"AllowOrigins":["*"],"AllowMethods":["GET","POST","DELETE"],"AllowHeaders":["Content-Type","Authorization"]}' \
    --region "$REGION" \
    --query FunctionUrl --output text)
  echo "  -> 新規作成: $FAVORITES_URL"
else
  echo "  -> 既存URLを使用: $FAVORITES_URL"
fi

aws lambda add-permission \
  --function-name "$FAVORITES_FN" \
  --statement-id AllowPublicAccess \
  --action lambda:InvokeFunctionUrl \
  --principal "*" \
  --function-url-auth-type NONE \
  --region "$REGION" 2>/dev/null || true

echo "  -> Favorites URL: $FAVORITES_URL"

# ---- 6d. Analytics Lambda ----
ANALYTICS_FN="flotopic-analytics"
ANALYTICS_TABLE="flotopic-analytics"
ANALYTICS_ENV_VARS="Variables={REGION=${REGION},ANALYTICS_TABLE=${ANALYTICS_TABLE},S3_BUCKET=${BUCKET}}"
echo "[6d] Analytics Lambda デプロイ..."
cd lambda/analytics
zip -q function.zip handler.py
aws lambda create-function \
  --function-name "$ANALYTICS_FN" \
  --runtime python3.12 \
  --role "$ROLE_ARN" \
  --handler handler.lambda_handler \
  --zip-file fileb://function.zip \
  --timeout 10 --memory-size 128 \
  --environment "$ANALYTICS_ENV_VARS" \
  --region "$REGION" 2>/dev/null \
  && echo "  -> 新規作成完了" \
  || {
    aws lambda update-function-code --function-name "$ANALYTICS_FN" --zip-file fileb://function.zip --region "$REGION" > /dev/null
    aws lambda wait function-updated --function-name "$ANALYTICS_FN" --region "$REGION"
    aws lambda update-function-configuration --function-name "$ANALYTICS_FN" --timeout 10 --memory-size 128 --environment "$ANALYTICS_ENV_VARS" --region "$REGION" > /dev/null
    echo "  -> 更新完了"
  }
rm function.zip
cd ../..

# Analytics Function URL
echo "  -> Analytics Function URL 設定..."
aws lambda wait function-updated --function-name "$ANALYTICS_FN" --region "$REGION" 2>/dev/null || true
aws lambda wait function-active  --function-name "$ANALYTICS_FN" --region "$REGION"

ANALYTICS_URL=$(aws lambda get-function-url-config \
  --function-name "$ANALYTICS_FN" --region "$REGION" \
  --query FunctionUrl --output text 2>/dev/null) || ANALYTICS_URL=""

if [ -z "$ANALYTICS_URL" ] || [ "$ANALYTICS_URL" = "None" ]; then
  ANALYTICS_URL=$(aws lambda create-function-url-config \
    --function-name "$ANALYTICS_FN" \
    --auth-type NONE \
    --cors '{"AllowOrigins":["https://flotopic.com"],"AllowMethods":["GET","POST","OPTIONS"],"AllowHeaders":["Content-Type","Authorization"]}' \
    --region "$REGION" \
    --query FunctionUrl --output text)
  echo "  -> 新規作成: $ANALYTICS_URL"
else
  # 既存URLのCORSをGETも許可するように更新
  aws lambda update-function-url-config \
    --function-name "$ANALYTICS_FN" \
    --cors '{"AllowOrigins":["https://flotopic.com"],"AllowMethods":["GET","POST","OPTIONS"],"AllowHeaders":["Content-Type","Authorization"]}' \
    --region "$REGION" > /dev/null 2>&1 || true
  echo "  -> 既存URLを使用（CORS更新済み）: $ANALYTICS_URL"
fi

aws lambda add-permission \
  --function-name "$ANALYTICS_FN" \
  --statement-id AllowPublicAccess \
  --action lambda:InvokeFunctionUrl \
  --principal "*" \
  --function-url-auth-type NONE \
  --region "$REGION" 2>/dev/null || true

echo "  -> Analytics URL: $ANALYTICS_URL"

# ---- 6e. CF Analytics Lambda（S3キャッシュ書き込み用、URL不要） ----
CF_ANALYTICS_FN="flotopic-cf-analytics"
CF_ANALYTICS_ENV="Variables={REGION=${REGION},S3_BUCKET=${BUCKET},USERS_TABLE=flotopic-users,COMMENTS_TABLE=ai-company-comments,FAVORITES_TABLE=flotopic-favorites,CF_SITE_TAG=577678a8a0064a499f6f0ba0a117fd4d}"
echo "[6e] CF Analytics Lambda デプロイ..."
cd lambda/cf-analytics
zip -q function.zip handler.py
aws lambda create-function \
  --function-name "$CF_ANALYTICS_FN" \
  --runtime python3.12 \
  --role "$ROLE_ARN" \
  --handler handler.lambda_handler \
  --zip-file fileb://function.zip \
  --timeout 30 --memory-size 256 \
  --environment "$CF_ANALYTICS_ENV" \
  --region "$REGION" 2>/dev/null \
  && echo "  -> 新規作成完了" \
  || {
    aws lambda update-function-code --function-name "$CF_ANALYTICS_FN" --zip-file fileb://function.zip --region "$REGION" > /dev/null
    aws lambda wait function-updated --function-name "$CF_ANALYTICS_FN" --region "$REGION"
    aws lambda update-function-configuration --function-name "$CF_ANALYTICS_FN" --timeout 30 --memory-size 256 --environment "$CF_ANALYTICS_ENV" --region "$REGION" > /dev/null
    echo "  -> 更新完了"
  }
rm function.zip
cd ../..

# EventBridge で毎日 22:00 UTC (7:00 JST) に実行
CF_RULE_NAME="flotopic-cf-analytics-daily"
aws events put-rule \
  --name "$CF_RULE_NAME" \
  --schedule-expression "cron(0 22 * * ? *)" \
  --state ENABLED \
  --region "$REGION" > /dev/null 2>&1 || true
CF_ANALYTICS_ARN=$(aws lambda get-function --function-name "$CF_ANALYTICS_FN" --region "$REGION" --query 'Configuration.FunctionArn' --output text)
aws lambda add-permission \
  --function-name "$CF_ANALYTICS_FN" \
  --statement-id EventBridgeCfAnalytics \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --region "$REGION" 2>/dev/null || true
aws events put-targets \
  --rule "$CF_RULE_NAME" \
  --targets "Id=1,Arn=${CF_ANALYTICS_ARN}" \
  --region "$REGION" > /dev/null 2>&1 || true
echo "  -> EventBridge スケジュール設定完了（毎日 7:00 JST）"

# config.js はリポジトリの静的ファイルを使用（deploy.shでは生成しない）
# 編集する場合は frontend/config.js を直接変更してコミットすること
echo "  -> config.js: リポジトリ版を使用（API Gateway: x73mzc0v06）"

# ---- deploy-security.sh でDynamoDBテーブル作成 ----
echo "[後処理] セキュリティ用DynamoDBテーブル作成..."
bash "$(dirname "$0")/deploy-security.sh" || echo "  -> deploy-security.sh 実行失敗（手動確認が必要）"

# ---- フロントエンドをS3にアップロード ----
echo "[フロントエンド] S3にアップロード..."
aws s3 sync frontend/ "s3://${BUCKET}/" --exclude "api/*" \
  --cache-control "no-cache, must-revalidate"

# HTMLファイルは no-cache で明示的に上書き（ブラウザキャッシュ対策）
echo "  -> HTMLファイルを no-cache で上書き..."
for html_file in frontend/*.html; do
  fname=$(basename "$html_file")
  aws s3 cp "$html_file" "s3://${BUCKET}/${fname}" \
    --content-type "text/html; charset=utf-8" \
    --cache-control "no-cache, must-revalidate" --region "$REGION"
done

# SEOファイルを正しい Content-Type で明示的にアップロード
echo "  -> SEOファイルを Content-Type 指定でアップロード..."
aws s3 cp frontend/robots.txt  "s3://${BUCKET}/robots.txt"  \
  --content-type "text/plain" --cache-control "public, max-age=86400" --region "$REGION"
aws s3 cp frontend/sitemap.xml "s3://${BUCKET}/sitemap.xml" \
  --content-type "application/xml" --cache-control "public, max-age=3600" --region "$REGION"
aws s3 cp frontend/ogp.png     "s3://${BUCKET}/ogp.png"     \
  --content-type "image/png"  --cache-control "public, max-age=604800" --region "$REGION"
aws s3 cp frontend/ads.txt "s3://${BUCKET}/ads.txt" \
  --content-type "text/plain" --cache-control "public, max-age=86400" --region "$REGION"
echo "  -> robots.txt / sitemap.xml / ogp.png / ads.txt アップロード完了"
aws s3 cp frontend/404.html "s3://${BUCKET}/404.html" \
  --content-type "text/html" --cache-control "public, max-age=300" --region "$REGION"
echo "  -> 404.html アップロード完了"
# sw.js は常に no-store（ブラウザキャッシュ禁止）でアップロード → SW更新が即反映される
aws s3 cp frontend/sw.js "s3://${BUCKET}/sw.js" \
  --content-type "application/javascript" --cache-control "no-store, no-cache, must-revalidate" --region "$REGION"
echo "  -> sw.js (no-cache) アップロード完了"

# ---- Lambda 同時実行数制限（DDoS/コスト防衛） ----
echo "  -> Lambda 同時実行数制限を設定..."
aws lambda put-function-concurrency \
  --function-name "$COMMENTS_FN" \
  --reserved-concurrent-executions 20 \
  --region "$REGION" > /dev/null 2>&1 && echo "  -> $COMMENTS_FN: max 20" || true
aws lambda put-function-concurrency \
  --function-name "$AUTH_FN" \
  --reserved-concurrent-executions 10 \
  --region "$REGION" > /dev/null 2>&1 && echo "  -> $AUTH_FN: max 10" || true
aws lambda put-function-concurrency \
  --function-name "$ANALYTICS_FN" \
  --reserved-concurrent-executions 10 \
  --region "$REGION" > /dev/null 2>&1 && echo "  -> $ANALYTICS_FN: max 10" || true
aws lambda put-function-concurrency \
  --function-name "$FAVORITES_FN" \
  --reserved-concurrent-executions 20 \
  --region "$REGION" > /dev/null 2>&1 && echo "  -> $FAVORITES_FN: max 20" || true
echo "  -> 同時実行数制限設定完了"

# ---- 6e. Lifecycle Lambda ----
LIFECYCLE_FN="flotopic-lifecycle"
if [ -n "${SLACK_WEBHOOK}" ]; then
  LIFECYCLE_ENV_VARS="Variables={REGION=${REGION},TABLE_NAME=${TABLE},SLACK_WEBHOOK=${SLACK_WEBHOOK}}"
else
  LIFECYCLE_ENV_VARS="Variables={REGION=${REGION},TABLE_NAME=${TABLE}}"
fi
echo "[6e] Lifecycle Lambda デプロイ..."
cd lambda/lifecycle
zip -q function.zip handler.py
aws lambda create-function \
  --function-name "$LIFECYCLE_FN" \
  --runtime python3.12 \
  --role "$ROLE_ARN" \
  --handler handler.lambda_handler \
  --zip-file fileb://function.zip \
  --timeout 900 --memory-size 256 \
  --environment "$LIFECYCLE_ENV_VARS" \
  --region "$REGION" 2>/dev/null \
  && echo "  -> 新規作成完了" \
  || {
    aws lambda update-function-code --function-name "$LIFECYCLE_FN" --zip-file fileb://function.zip --region "$REGION" > /dev/null
    aws lambda wait function-updated --function-name "$LIFECYCLE_FN" --region "$REGION"
    aws lambda update-function-configuration --function-name "$LIFECYCLE_FN" --timeout 900 --memory-size 256 --environment "$LIFECYCLE_ENV_VARS" --region "$REGION" > /dev/null
    echo "  -> 更新完了"
  }
rm function.zip
cd ../..

# EventBridge ルール（毎週月曜 02:00 UTC = 11:00 JST）
aws events put-rule \
  --name "flotopic-lifecycle-weekly" \
  --schedule-expression "cron(0 2 ? * MON *)" \
  --state ENABLED \
  --region "$REGION" > /dev/null 2>&1 && echo "  -> EventBridge ルール設定完了" || true

LIFECYCLE_ARN=$(aws lambda get-function \
  --function-name "$LIFECYCLE_FN" --region "$REGION" \
  --query Configuration.FunctionArn --output text 2>/dev/null) || LIFECYCLE_ARN=""

if [ -n "$LIFECYCLE_ARN" ]; then
  aws lambda add-permission \
    --function-name "$LIFECYCLE_FN" \
    --statement-id AllowEventBridgeInvoke \
    --action lambda:InvokeFunction \
    --principal events.amazonaws.com \
    --region "$REGION" 2>/dev/null || true

  RULE_ARN=$(aws events describe-rule \
    --name "flotopic-lifecycle-weekly" --region "$REGION" \
    --query RuleArn --output text 2>/dev/null) || RULE_ARN=""

  if [ -n "$RULE_ARN" ]; then
    aws events put-targets \
      --rule "flotopic-lifecycle-weekly" \
      --targets "Id=lifecycle-target,Arn=${LIFECYCLE_ARN}" \
      --region "$REGION" > /dev/null 2>&1 && echo "  -> EventBridge → Lifecycle Lambda ターゲット設定完了" || true
  fi
fi

echo ""
echo "======================================="
echo "  デプロイ完了！"
echo "======================================="
echo "  サイトURL      : $SITE_URL"
echo "  API URL        : $API_URL"
echo "  Comments URL   : $COMMENTS_URL"
echo "  Auth URL       : $AUTH_URL"
echo "  Favorites URL  : $FAVORITES_URL"
echo "  Analytics URL  : $ANALYTICS_URL"
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

# ===== デプロイ後 自動検証 =====
echo ""
echo "======================================="
echo "  デプロイ後 自動検証"
echo "======================================="
VERIFY_FAIL=0

# 1. CDN上のconfig.jsがAPI Gateway URLを使っているか確認
CONFIG_CHECK=$(/usr/bin/curl -sf "https://flotopic.com/config.js" 2>/dev/null | grep -c "x73mzc0v06" || echo 0)
if [ "$CONFIG_CHECK" -ge 1 ]; then
  echo "  [OK] config.js: API Gateway URL"
else
  echo "  [NG] config.js: Lambda URL が混入している!"
  VERIFY_FAIL=1
fi

# 2. topics.json が取得できるか
TOPIC_COUNT=$(/usr/bin/curl -sf "https://flotopic.com/api/topics.json" 2>/dev/null | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('topics',[])))" 2>/dev/null || echo 0)
if [ "$TOPIC_COUNT" -gt 0 ]; then
  echo "  [OK] topics.json: ${TOPIC_COUNT}件"
else
  echo "  [NG] topics.json: 取得失敗"
  VERIFY_FAIL=1
fi

# 3. API Gateway コメント/お気に入りが応答するか
GW="https://x73mzc0v06.execute-api.ap-northeast-1.amazonaws.com"
COMMENTS_STATUS=$(/usr/bin/curl -s -o /dev/null -w "%{http_code}" -m 5 "$GW/comments/test" -H "Origin: https://flotopic.com")
FAVS_STATUS=$(/usr/bin/curl -s -o /dev/null -w "%{http_code}" -m 5 "$GW/favorites/test" -H "Origin: https://flotopic.com")

[ "$COMMENTS_STATUS" -lt 500 ] && echo "  [OK] GET /comments: $COMMENTS_STATUS" || { echo "  [NG] GET /comments: $COMMENTS_STATUS"; VERIFY_FAIL=1; }
[ "$FAVS_STATUS" -lt 500 ]    && echo "  [OK] GET /favorites: $FAVS_STATUS"  || { echo "  [NG] GET /favorites: $FAVS_STATUS";  VERIFY_FAIL=1; }

# 4. sw.js のバージョン
SW_VER=$(/usr/bin/curl -sf "https://flotopic.com/sw.js" 2>/dev/null | head -1 | grep -o "flotopic-v[0-9]*" || echo "不明")
echo "  [--] sw.js: $SW_VER"

echo ""
if [ $VERIFY_FAIL -eq 0 ]; then
  echo "  ✅ 全チェック通過"
else
  echo "  ❌ 失敗項目あり — 上記を確認してください"
  exit 1
fi
