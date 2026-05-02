#!/bin/bash
set -e

# check_post_deploy.sh: post-deploy-verify workflow 構造化検証
# 用途: CI ゲート + ローカルテスト
# 検証項目: (1) deploy-lambdas.yml に post-deploy-verify job がない (2) post-deploy-verify.yml が workflow_run trigger を持つ

WF_DIR=".github/workflows"
DEPLOY_FILE="$WF_DIR/deploy-lambdas.yml"
VERIFY_FILE="$WF_DIR/post-deploy-verify.yml"

# (1) deploy-lambdas.yml に post-deploy-verify job がないことを確認
if grep -q "^  post-deploy-verify:" "$DEPLOY_FILE"; then
    echo "❌ ERROR: post-deploy-verify job が $DEPLOY_FILE に残っている"
    echo "         → deploy workflow conclusion が post-deploy-verify 失敗で誤解を招く"
    exit 1
fi

# (2) post-deploy-verify.yml が workflow_run trigger を持つことを確認
if [ ! -f "$VERIFY_FILE" ]; then
    echo "❌ ERROR: $VERIFY_FILE が存在しない"
    exit 1
fi

if ! grep -q "workflow_run:" "$VERIFY_FILE"; then
    echo "❌ ERROR: $VERIFY_FILE に workflow_run trigger がない"
    echo "         → deploy-lambdas.yml 完了後に自動起動されない"
    exit 1
fi

if ! grep -q "workflows: \[Lambda デプロイ（全関数）\]" "$VERIFY_FILE"; then
    echo "❌ ERROR: $VERIFY_FILE が 'Lambda デプロイ（全関数）' を trigger していない"
    exit 1
fi

if ! grep -q "continue-on-error: true" "$VERIFY_FILE"; then
    echo "⚠️  WARNING: post-deploy-verify.yml に 'continue-on-error: true' がない"
    echo "           → 失敗時に独立ワークフロー内で停止するがよい"
    echo "           → 念のため確認してください"
fi

echo "✅ post-deploy-verify workflow 構造化検証 OK"
echo "   - deploy-lambdas.yml: post-deploy-verify job なし"
echo "   - post-deploy-verify.yml: workflow_run trigger ✓"
