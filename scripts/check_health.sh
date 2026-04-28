#!/bin/bash
# 本番ヘルスチェック (T2026-0428-AQ)
# api/health.json を取得し status / keyPoint率 / 空トピック を表示。
# status != ok なら exit 1。
set -euo pipefail

HEALTH=$(curl -fsS https://flotopic.com/api/health.json)
echo "$HEALTH" | python3 -c "
import json, sys
h = json.load(sys.stdin)
print(f\"status: {h['status']}\")
print(f\"topics: {h['topicCount']}\")
print(f\"aiGenerated: {h['aiGeneratedCount']}\")
print(f\"keyPoint率: {h['keyPointRate']}%\")
print(f\"空トピック: {h['zeroArticleCount']}\")
print(f\"更新: {h['generatedAt']}\")
if h['status'] != 'ok':
    sys.exit(1)
"
