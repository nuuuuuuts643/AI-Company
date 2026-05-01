#!/usr/bin/env python3
"""Build Slack payload for fetcher-health-check workflow.

Env: STATUS, SUM, START_TIME, END_TIME, LOG_URL, ALARM_URL
Usage: STATUS=... python3 scripts/ci_slack_fetcher_health.py
"""
import json
import os

status = os.environ["STATUS"]
headline = (
    "\U0001f6a8 *Flotopic fetcher が 2 時間 0 件保存*"
    if status == "zero_articles"
    else "⚠️ *Flotopic fetcher メトリクス欠損*"
)
text = (
    f"{headline}\n"
    f"• status: `{status}`\n"
    f"• 過去2h saved_articles 合計: `{os.environ['SUM']}` 件\n"
    f"• 観測窓: {os.environ['START_TIME']} 〜 {os.environ['END_TIME']}\n"
    f"• fetcher ログ: {os.environ['LOG_URL']}\n"
    f"• Alarm: {os.environ['ALARM_URL']}\n"
    "\n_T2026-0430-H fetcher-health-check.yml からの通知 (CloudWatch Alarm と並走)_"
)
print(json.dumps({"text": text, "username": "Flotopic Fetcher Monitor", "icon_emoji": ":rotating_light:"}))
