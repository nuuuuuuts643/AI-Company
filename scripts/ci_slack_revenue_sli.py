#!/usr/bin/env python3
"""Build Slack payload for revenue-sli stale log alert.

Env: LOG_ST, LOG_DATE, LOG_AGE, PV, PV_ST, ICON
Usage: LOG_ST=... python3 scripts/ci_slack_revenue_sli.py
"""
import json
import os

text = (
    "💰 *Flotopic 収益ログ転記滞留*\n"
    f"• log_status: `{os.environ['LOG_ST']}` (最終: {os.environ.get('LOG_DATE') or '未記録'} / {os.environ['LOG_AGE']}日前)\n"
    f"• 今週の PV(7d): `{os.environ['PV']}` ({os.environ['PV_ST']})\n"
    "• 対処: 忍者AdMax (https://admax.ninja/) を開いて先週分を docs/revenue-log.md に転記\n"
    "• なぜ重要: 品質改善 (keyPoint/perspectives) が収益に繋がってるか測れなくなる\n"
    "\n_T2026-0430-REV scripts/revenue_check.sh — 週次収益SLI_"
)
print(json.dumps({"text": text, "username": "Flotopic Revenue Monitor", "icon_emoji": os.environ.get("ICON", ":warning:")}))
