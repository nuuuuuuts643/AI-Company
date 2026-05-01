#!/usr/bin/env python3
"""Build Slack payload for SLI-keypoint-fill-rate alert.

Env: STATUS, RATE, ELIGIBLE, FILLED, ICON
Usage: STATUS=... python3 scripts/ci_slack_kp_fill_rate.py
"""
import json
import os

text = (
    "⚠️ *Flotopic SLI-keypoint-fill-rate*\n"
    f"• status: `{os.environ['STATUS']}`\n"
    f"• 充填率: `{os.environ['RATE']}%` (warn<=10% / error<=5%)\n"
    f"• filled: {os.environ['FILLED']} / eligible: {os.environ['ELIGIBLE']}\n"
    "• 対象: DynamoDB p003-topics META (articleCount>=2, not archived/legacy/deleted)\n"
    "• 対処: pending_ai.json 投入状況確認 / processor cron ログ参照\n"
    "\n_T2026-0428-BG: 遡及処理 (pending_ai.json 950 件) の効果観測用 SLI / 6h scan_"
)
print(json.dumps({"text": text, "username": "Flotopic keyPoint Fill Monitor", "icon_emoji": os.environ.get("ICON", ":warning:")}))
