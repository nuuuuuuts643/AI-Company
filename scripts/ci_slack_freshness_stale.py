#!/usr/bin/env python3
"""Build Slack payload for freshness-check stale alert.

Env: STATUS, DIFF_MIN, UPDATED_AT, NEXT_JST, INVOKE_LOG_URL
Usage: STATUS=... python3 scripts/ci_slack_freshness_stale.py
"""
import json
import os

text = (
    "\U0001f6a8 *Flotopic topics.json 鮮度警告*\n"
    f"• status: `{os.environ['STATUS']}`\n"
    f"• 最終 updatedAt: `{os.environ['UPDATED_AT']}`\n"
    f"• 経過: `{os.environ['DIFF_MIN']} 分` (閾値 90 分)\n"
    f"• 次回スケジュール JST: {os.environ['NEXT_JST']}\n"
    f"• processor ログ: {os.environ['INVOKE_LOG_URL']}\n"
    "\n_governance worker とは別系統の外部観測 (T263 / freshness-check.yml) からの通知_"
)
print(json.dumps({"text": text, "username": "Flotopic Freshness Monitor", "icon_emoji": ":warning:"}))
