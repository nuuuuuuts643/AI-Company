#!/bin/bash
# ===================================================
# home PC でこのスクリプトを実行するだけで完了
# bash HOME-PC-SETUP.sh
# ===================================================
set -e
cd "$(dirname "$0")"

echo "=== AI-Company セットアップ（home PC） ==="
echo ""

# 1. git ロック解除
echo "[1/5] git ロック解除..."
rm -f .git/index.lock
echo "  ✅ 完了"

# 2. 全変更をコミット
echo "[2/5] 変更をコミット..."
git add -A
git commit -m "feat: ステージング環境・CI・深掘り/拡張UX・ストーリーマップ刷新

追加・変更内容:
- .github/workflows/ci.yml — PR/push時の自動構文チェック
- .github/workflows/deploy-staging.yml — staging自動デプロイ
- deploy-staging.sh — ローカルステージングデプロイ
- frontend/app.js — 深掘り/拡張 Discovery機能
- frontend/storymap.html — カードグリッド1画面設計に刷新
- frontend/style.css — Discoveryスタイル追加
- frontend/topic.html — discovery-section追加
- lambda/fetcher/handler.py — 時間減衰/ベロシティ/階層検出
- lambda/analytics/handler.py — 新規/リピーター判定
- scripts/ceo_run.py — 読者品質分析
- scripts/revenue_agent.py — 収益管理AI
- CLAUDE.md — ブランチ戦略ルール追記" 2>/dev/null || echo "  コミット済み（スキップ）"
echo "  ✅ 完了"

# 3. staging ブランチ作成
echo "[3/5] staging ブランチ作成..."
git branch staging 2>/dev/null || echo "  staging ブランチ既存（スキップ）"
echo "  ✅ 完了"

# 4. main + staging を push
echo "[4/5] GitHub に push..."
git push origin main
git push origin staging
echo "  ✅ 完了"

# 5. P003 S3 デプロイ
echo "[5/5] Flotopic 本番デプロイ..."
bash projects/P003-news-timeline/deploy.sh
echo "  ✅ 完了"

echo ""
echo "========================================="
echo "✅ すべて完了！"
echo ""
echo "次にやること（手動）:"
echo "  1. GitHub → Settings → Branches → Add rule"
echo "     Branch name: main"
echo "     ☑ Require status checks to pass before merging"
echo "     ☑ Require a pull request before merging"
echo ""
echo "  2. flotopic.com CloudFront + SSL:"
echo "     aws configure  # 未設定なら"
echo "     bash scripts/setup-domain.sh"
echo ""
echo "  3. Squarespace でネームサーバーを setup-domain.sh の出力値に変更"
echo "========================================="
