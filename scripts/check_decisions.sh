#!/usr/bin/env bash
# decisions.yamlの期限切れ決定を検出してsession_bootstrapに警告を出す
set -euo pipefail

DECISIONS_FILE="$(dirname "$0")/../decisions.yaml"
TODAY=$(date +%Y-%m-%d)

if [[ ! -f "$DECISIONS_FILE" ]]; then
  exit 0
fi

# python3でyaml解析（PyYAMLなしでも動くシンプル実装）
python3 - <<PYEOF
import sys
import re
from datetime import datetime, timedelta

with open("$DECISIONS_FILE") as f:
    content = f.read()

today = datetime.strptime("$TODAY", "%Y-%m-%d")

# 簡易パース: decided_at と recheck_after_days を抽出
blocks = re.split(r'\s*-\s+id:', content)[1:]
expired = []

for block in blocks:
    id_match = re.search(r'^(\S+)', block)
    title_match = re.search(r'title:\s*"?([^"\n]+)"?', block)
    decided_match = re.search(r'decided_at:\s*"?(\d{4}-\d{2}-\d{2})"?', block)
    days_match = re.search(r'recheck_after_days:\s*(\d+)', block)

    if not all([id_match, title_match, decided_match, days_match]):
        continue

    d_id = id_match.group(1).strip()
    title = title_match.group(1).strip()
    decided = datetime.strptime(decided_match.group(1), "%Y-%m-%d")
    days = int(days_match.group(1))
    expires = decided + timedelta(days=days)

    if today >= expires:
        expired.append((d_id, title, decided_match.group(1), days))

if expired:
    print("⚠️  【要再確認】以下の決定が期限を超えています:")
    for d_id, title, decided, days in expired:
        print(f"   {d_id}: {title}")
        print(f"        (決定日: {decided}, 再確認周期: {days}日)")
    print("   → docs/rules/ または decisions.yaml を確認し、decided_atを更新してください")
    sys.exit(1)
else:
    print("✅ decisions.yaml: 全決定が有効期限内")
    sys.exit(0)
PYEOF
