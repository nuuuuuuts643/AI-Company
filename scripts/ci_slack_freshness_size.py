#!/usr/bin/env python3
"""Build Slack payload for freshness-check topics.json size alert.

Env: KB
Usage: KB=... python3 scripts/ci_slack_freshness_size.py
"""
import json
import os

text = (
    "⚠️ *Flotopic topics.json サイズ超過*\n"
    f"• 現在: `{os.environ['KB']} KB` (閾値 250 KB)\n"
    "• モバイル初回表示帯域コスト増加。topics-card.json 切替 (T2026-0428-F Step2) 着手検討\n"
    "\n_T2026-0428-F freshness-check.yml サイズ観測_"
)
print(json.dumps({"text": text, "username": "Flotopic Size Monitor", "icon_emoji": ":warning:"}))
