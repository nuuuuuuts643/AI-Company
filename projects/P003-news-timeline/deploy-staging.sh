#!/bin/bash
# ===== Flotopic ステージングデプロイ =====
# ローカルから手動でステージングに反映したい場合に使う
# home PC で実行: bash projects/P003-news-timeline/deploy-staging.sh

set -e

REGION="ap-northeast-1"
STAGING_BUCKET="p003-news-staging-946554699567"
PROD_BUCKET="p003-news-946554699567"
STAGING_URL="http://${STAGING_BUCKET}.s3-website-${REGION}.amazonaws.com"

echo "=== Flotopic ステージングデプロイ ==="
echo "STAGING: ${STAGING_URL}"
echo ""

# --- バケット作成（初回のみ） ---
echo "[1/4] ステージングバケット確認..."
aws s3api create-bucket \
  --bucket "${STAGING_BUCKET}" \
  --region "${REGION}" \
  --create-bucket-configuration LocationConstraint="${REGION}" \
  2>/dev/null && echo "  バケット作成" || echo "  バケット既存"

aws s3 website "s3://${STAGING_BUCKET}" \
  --index-document index.html \
  --error-document index.html

aws s3api put-bucket-policy \
  --bucket "${STAGING_BUCKET}" \
  --policy "{
    \"Version\":\"2012-10-17\",
    \"Statement\":[{
      \"Effect\":\"Allow\",
      \"Principal\":\"*\",
      \"Action\":\"s3:GetObject\",
      \"Resource\":\"arn:aws:s3:::${STAGING_BUCKET}/*\"
    }]
  }" 2>/dev/null || true

aws s3api delete-public-access-block \
  --bucket "${STAGING_BUCKET}" 2>/dev/null || true

# --- config.js 生成（ステージング用） ---
echo "[2/4] config.js 生成（ステージング設定）..."
FRONTEND_DIR="projects/P003-news-timeline/frontend"

# 本番の API_BASE を流用（バックエンドは共有）
EXISTING_API_BASE=$(grep -oP "(?<=API_BASE\s*=\s*')[^']*" "${FRONTEND_DIR}/config.js" 2>/dev/null || echo "")
EXISTING_COMMENTS_URL=$(grep -oP "(?<=COMMENTS_URL\s*=\s*')[^']*" "${FRONTEND_DIR}/config.js" 2>/dev/null || echo "")
EXISTING_ANALYTICS_URL=$(grep -oP "(?<=ANALYTICS_URL\s*=\s*')[^']*" "${FRONTEND_DIR}/config.js" 2>/dev/null || echo "")
EXISTING_CLIENT_ID=$(grep -oP "(?<=GOOGLE_CLIENT_ID\s*=\s*')[^']*" "${FRONTEND_DIR}/config.js" 2>/dev/null || echo "")

cat > /tmp/staging-config.js << EOF
// === ステージング設定（自動生成） ===
const API_BASE         = '${EXISTING_API_BASE}';
const COMMENTS_URL     = '${EXISTING_COMMENTS_URL}';
const ANALYTICS_URL    = '${EXISTING_ANALYTICS_URL}';
const GOOGLE_CLIENT_ID = '${EXISTING_CLIENT_ID}';
EOF

# --- フロントエンド同期 ---
echo "[3/4] フロントエンド → ステージングS3..."
cp /tmp/staging-config.js "${FRONTEND_DIR}/config.js.staging.tmp"

aws s3 sync "${FRONTEND_DIR}/" "s3://${STAGING_BUCKET}/" \
  --region "${REGION}" \
  --exclude "config.js" \
  --exclude "api/*" \
  --cache-control "no-cache, no-store"

# config.jsだけステージング版をアップロード
aws s3 cp /tmp/staging-config.js "s3://${STAGING_BUCKET}/config.js" \
  --region "${REGION}" \
  --cache-control "no-cache, no-store"

rm -f "${FRONTEND_DIR}/config.js.staging.tmp" /tmp/staging-config.js

# --- 構文チェック（デプロイ前確認） ---
echo "[4/4] 構文チェック..."
ERRORS=0
for f in "${FRONTEND_DIR}"/*.js; do
  node --check "$f" 2>&1 && echo "  ✅ $f" || { echo "  ❌ $f"; ERRORS=$((ERRORS+1)); }
done
for f in projects/P003-news-timeline/lambda/*/handler.py; do
  python3 -m py_compile "$f" && echo "  ✅ $f" || { echo "  ❌ $f"; ERRORS=$((ERRORS+1)); }
done

echo ""
echo "=================================="
if [ $ERRORS -gt 0 ]; then
  echo "❌ 構文エラーあり（${ERRORS}件）— 本番デプロイ前に修正してください"
  exit 1
fi
echo "✅ ステージングデプロイ完了"
echo ""
echo "🔗 確認URL: ${STAGING_URL}"
echo ""
echo "本番に反映するには:"
echo "  git checkout main && git merge staging && git push"
echo "  bash projects/P003-news-timeline/deploy.sh"
