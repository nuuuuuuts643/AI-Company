#!/bin/bash
set -e

REGION="ap-northeast-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
FUNCTION_NAME="ai-company-slack-bot"
ROLE="p003-lambda-role"  # P003で作成済みのロールを流用

echo "======================================="
echo "  P004 Slack Bot デプロイ"
echo "======================================="

# 環境変数確認
if [ -z "$GITHUB_TOKEN" ] || [ -z "$SLACK_BOT_TOKEN" ] || [ -z "$SLACK_WEBHOOK" ]; then
  echo "エラー: 以下の環境変数が必要です"
  echo "  GITHUB_TOKEN=ghp_..."
  echo "  SLACK_BOT_TOKEN=xoxb-..."
  echo "  SLACK_WEBHOOK=https://hooks.slack.com/..."
  exit 1
fi

ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE}"
ENV_VARS="Variables={GITHUB_TOKEN=${GITHUB_TOKEN},SLACK_BOT_TOKEN=${SLACK_BOT_TOKEN},SLACK_WEBHOOK=${SLACK_WEBHOOK}}"

echo "[1/3] Lambda パッケージ作成..."
cd lambda
zip -q function.zip handler.py
echo "  -> 完了"

echo "[2/3] Lambda デプロイ..."
aws lambda create-function \
  --function-name "$FUNCTION_NAME" \
  --runtime python3.12 \
  --role "$ROLE_ARN" \
  --handler handler.lambda_handler \
  --zip-file fileb://function.zip \
  --timeout 30 --memory-size 128 \
  --environment "$ENV_VARS" \
  --region "$REGION" 2>/dev/null \
  && echo "  -> 新規作成完了" \
  || {
    aws lambda update-function-code --function-name "$FUNCTION_NAME" --zip-file fileb://function.zip --region "$REGION" > /dev/null
    aws lambda wait function-updated --function-name "$FUNCTION_NAME" --region "$REGION"
    aws lambda update-function-configuration --function-name "$FUNCTION_NAME" --environment "$ENV_VARS" --region "$REGION" > /dev/null
    echo "  -> 更新完了"
  }
rm function.zip
cd ..

echo "[3/3] Function URL 作成..."
aws lambda wait function-active --function-name "$FUNCTION_NAME" --region "$REGION"

BOT_URL=$(aws lambda get-function-url-config \
  --function-name "$FUNCTION_NAME" --region "$REGION" \
  --query FunctionUrl --output text 2>/dev/null) || BOT_URL=""

if [ -z "$BOT_URL" ] || [ "$BOT_URL" = "None" ]; then
  BOT_URL=$(aws lambda create-function-url-config \
    --function-name "$FUNCTION_NAME" \
    --auth-type NONE \
    --cors '{"AllowOrigins":["*"],"AllowMethods":["POST"],"AllowHeaders":["*"]}' \
    --region "$REGION" \
    --query FunctionUrl --output text)
fi

aws lambda add-permission \
  --function-name "$FUNCTION_NAME" \
  --statement-id AllowPublicAccess \
  --action lambda:InvokeFunctionUrl \
  --principal "*" \
  --function-url-auth-type NONE \
  --region "$REGION" 2>/dev/null || true

echo ""
echo "======================================="
echo "  デプロイ完了"
echo "======================================="
echo "  Bot URL: $BOT_URL"
echo ""
echo "次のステップ:"
echo "  1. https://api.slack.com/apps でSlash Commandを設定"
echo "  2. Request URL に上記Bot URLを設定"
echo "  3. コマンド名: /ai"
echo "======================================="
