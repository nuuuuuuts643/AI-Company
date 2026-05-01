#!/usr/bin/env python3
"""Build Slack payload for quality-heal job failure.

No env vars needed (failure notification has no dynamic data).
Usage: python3 scripts/ci_slack_quality_heal.py
"""
import json

text = (
    "\U0001f6a8 *quality_heal job 失敗*\n"
    "• .github/workflows/quality-heal.yml\n"
    "• 詳細: GitHub Actions ログ参照\n"
)
print(json.dumps({"text": text, "username": "Quality Heal Monitor", "icon_emoji": ":rotating_light:"}))
