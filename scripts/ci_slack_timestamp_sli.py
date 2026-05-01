#!/usr/bin/env python3
"""Build Slack payload for SLI-timestamp Unix-second infiltration alert.

Env: STATUS, BAD, TOTAL, DETAILS, ICON
Usage: STATUS=... python3 scripts/ci_slack_timestamp_sli.py
"""
import json
import os

text = (
    "⚠️ *Flotopic SLI-timestamp (Unix秒 infiltration)*\n"
    f"• status: `{os.environ['STATUS']}`\n"
    f"• bad: {os.environ['BAD']} / total: {os.environ['TOTAL']} (warn>=1 / error>=5)\n"
    f"• detail: {os.environ.get('DETAILS') or '-'}\n"
    "• 対象フィールド: predictionMadeAt / createdAt / storyTimeline[*].at\n"
    "• 対処: proc_ai.py / handler.py の書き込み箇所を確認、ISO で書くべきフィールドに Unix 秒が混入している箇所を特定\n"
    "\n_T2026-0501-TS: SNAP timestamp 混在による 1970 年表示事故の再発防止 SLI_"
)
print(json.dumps({"text": text, "username": "Flotopic Timestamp Monitor", "icon_emoji": os.environ.get("ICON", ":warning:")}))
