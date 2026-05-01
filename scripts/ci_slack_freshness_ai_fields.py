#!/usr/bin/env python3
"""Build Slack payload for freshness-check AI-fields semi-broken alert (SLI 8/9/4).

Env: WARNINGS, KP, PERSP, START
Usage: WARNINGS=... python3 scripts/ci_slack_freshness_ai_fields.py
"""
import json
import os

text = (
    "⚠️ *Flotopic AI フィールド半壊検出 (success-but-empty)*\n"
    f"• 警告: `{os.environ['WARNINGS']}`\n"
    f"• keyPoint 充填: `{os.environ['KP']}%` (閾値 70%)\n"
    f"• perspectives: `{os.environ['PERSP']}%` (閾値 60%)\n"
    f"• storyPhase 発端: `{os.environ['START']}%` (閾値 50%)\n"
    "\n_aiGenerated=True でも必須フィールドが空の半壊状態を検出 (SLI 8/9/4)_"
)
print(json.dumps({"text": text, "username": "Flotopic AI Fields Monitor", "icon_emoji": ":warning:"}))
