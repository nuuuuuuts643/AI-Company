#!/usr/bin/env python3
"""Build Slack payload for qualitative-eval workflow result.

Env: STATUS, OVERALL
Usage: STATUS=... OVERALL=... python3 scripts/ci_slack_qualitative_eval.py
"""
import json
import os

status = os.environ.get("STATUS", "unknown")
icon = ":bar_chart:" if status == "success" else ":warning:"
text = (
    f"{icon} *Flotopic AI 定性評価 (週次)*\n"
    f"• 状態: `{status}`\n"
    f"• 総合スコア: `{os.environ.get('OVERALL', '?')}`\n"
    "• 詳細: docs/quality-scores.md\n"
    "\n_T2026-0501-C scripts/qualitative_eval.sh — 充填率では拾えない「惹き・深さ・独自性」を Claude Haiku に評価させる_"
)
print(json.dumps({"text": text, "username": "Flotopic Quality Monitor", "icon_emoji": ":sparkles:"}))
