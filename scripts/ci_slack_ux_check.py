#!/usr/bin/env python3
"""Build Slack payload for ux-check weekly result.

Env: RC, UX_SCORE, PREV_SCORE, KP100, CHILD_AVG, DELTA_PCT, INDEX_TIME
Usage: RC=... UX_SCORE=... python3 scripts/ci_slack_ux_check.py
"""
import json
import os

rc = os.environ.get("RC", "0")
ux = os.environ.get("UX_SCORE", "?")
prev = os.environ.get("PREV_SCORE", "?")

delta_str = ""
try:
    if ux != "?" and prev != "?":
        d = float(ux) - float(prev)
        arrow = "⬆" if d > 0.005 else ("⬇" if d < -0.005 else "→")
        delta_str = f" ({arrow}{d:+.2f} vs 前週 {prev})"
except ValueError:
    pass

icon = ":bar_chart:" if rc == "0" else ":warning:"
status_label = "OK" if rc == "0" else "レイアウト WARN"
text = (
    f"{icon} *Flotopic UX 定量評価 (週次)*\n"
    f"• 状態: `{status_label}`\n"
    f"• UX スコア: `{ux}/5`{delta_str}\n"
    f"• keyPoint≥100字: `{os.environ.get('KP100', '?')}`\n"
    f"• 関連トピック平均: `{os.environ.get('CHILD_AVG', '?')}件`\n"
    f"• 続報率: `{os.environ.get('DELTA_PCT', '?')}`\n"
    f"• TTFB(/): `{os.environ.get('INDEX_TIME', '?')}`\n"
    "• 詳細: docs/ux-scores.md\n"
    "\n_T2026-0430-UX scripts/ux_check.sh — 情報密度・関連密度・モバイル表示・応答性の週次 SLI_"
)
print(json.dumps({"text": text, "username": "Flotopic UX Monitor", "icon_emoji": ":sparkles:"}))
