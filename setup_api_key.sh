#!/bin/bash
# APIキーをLambdaとGitHubに一括設定するスクリプト
#
# T2026-0502-SEC-AUDIT (2026-05-02):
#   旧バージョンには live Anthropic API key (`***REDACTED-SEC3***...`) が直書きされていた。
#   当該キーは必ず Anthropic Console (https://console.anthropic.com/settings/keys) で
#   Revoke すること。新キーは env 経由でのみ受け取る (本スクリプトは git ignore 済だが、
#   平文ディスク保管・チャット表示・スクリーン共有経由の漏洩リスクがある)。
#
# 使い方:
#   export ANTHROPIC_API_KEY=sk-ant-api03-xxx
#   bash setup_api_key.sh
set -e

API_KEY="${ANTHROPIC_API_KEY:-}"
REGION="${AWS_REGION:-ap-northeast-1}"

if [ -z "$API_KEY" ]; then
  echo "ERROR: ANTHROPIC_API_KEY env 変数が未設定です。" >&2
  echo "  export ANTHROPIC_API_KEY=sk-ant-api03-xxx を設定してから再実行してください。" >&2
  exit 2
fi

echo "======================================="
echo "  API Key セットアップ"
echo "======================================="

# ---- 1. Lambda (p003-fetcher) ----
echo "[1/2] p003-fetcher にAPIキーを設定中..."
aws lambda update-function-configuration \
  --function-name p003-fetcher \
  --environment "Variables={TABLE_NAME=p003-topics,REGION=${REGION},ANTHROPIC_API_KEY=${API_KEY}}" \
  --region "$REGION" > /dev/null
echo "  -> 完了"

# ---- 2. GitHub Secret ----
echo "[2/2] GitHub Secret を設定中..."

GITHUB_TOKEN=$(aws lambda get-function-configuration \
  --function-name ai-company-slack-bot \
  --region "$REGION" \
  --query 'Environment.Variables.GITHUB_TOKEN' \
  --output text 2>/dev/null)

if [ -z "$GITHUB_TOKEN" ] || [ "$GITHUB_TOKEN" = "None" ]; then
  echo "  -> GitHub Tokenが取得できませんでした"
  echo "  -> 手動でGitHubシークレットを設定してください:"
  echo "     https://github.com/nuuuuuuts643/AI-Company/settings/secrets/actions"
  echo "     名前: ANTHROPIC_API_KEY"
  echo "     値: ${API_KEY}"
else
  REPO="nuuuuuuts643/AI-Company"
  # 公開鍵取得
  PUB_KEY_RESP=$(curl -s -H "Authorization: token ${GITHUB_TOKEN}" \
    "https://api.github.com/repos/${REPO}/actions/secrets/public-key")
  KEY_ID=$(echo "$PUB_KEY_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['key_id'])")
  PUB_KEY=$(echo "$PUB_KEY_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['key'])")

  # シークレットを暗号化してPUT
  ENCRYPTED=$(python3 -c "
import base64, sys
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey
from cryptography.hazmat.bindings._rust import openssl as rust_openssl

# libsodium sealedbox相当をPyNaClなしで実装
import subprocess, json
result = subprocess.run([
  'python3', '-c',
  '''
import base64, json
from nacl.public import PublicKey, SealedBox
pub = PublicKey(base64.b64decode(\"''' + PUB_KEY + '''\"))
box = SealedBox(pub)
enc = box.encrypt(b\"''' + API_KEY + '''\")
print(base64.b64encode(enc).decode())
'''
], capture_output=True, text=True)
print(result.stdout.strip())
" 2>/dev/null)

  if [ -n "$ENCRYPTED" ]; then
    curl -s -X PUT \
      -H "Authorization: token ${GITHUB_TOKEN}" \
      -H "Content-Type: application/json" \
      "https://api.github.com/repos/${REPO}/actions/secrets/ANTHROPIC_API_KEY" \
      -d "{\"encrypted_value\":\"${ENCRYPTED}\",\"key_id\":\"${KEY_ID}\"}" > /dev/null
    echo "  -> 完了"
  else
    echo "  -> 暗号化ライブラリ(PyNaCl)が必要です。手動設定してください:"
    echo "     https://github.com/nuuuuuuts643/AI-Company/settings/secrets/actions"
    echo "     名前: ANTHROPIC_API_KEY"
    echo "     値: ${API_KEY}"
  fi
fi

echo ""
echo "======================================="
echo "  完了！"
echo "  次にLambdaを手動実行して動作確認します"
echo "======================================="
aws lambda invoke \
  --function-name p003-fetcher \
  --region "$REGION" \
  /tmp/p003-test.json > /dev/null && cat /tmp/p003-test.json
echo ""
echo "generatedTitle が入ったトピックが表示されれば成功です"
