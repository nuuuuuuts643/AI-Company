#!/usr/bin/env python3
"""Build Slack payload for env-scripts dry-run CI failure alert.

Env: RUN_URL
Usage: RUN_URL=... python3 scripts/ci_slack_env_dryrun.py
"""
import json
import os

text = (
    "\U0001f6a8 *env-scripts dry-run CI 失敗* (T2026-0428-K)\n"
    f"• run: {os.environ['RUN_URL']}\n"
    "• session_bootstrap.sh の REPO/JST/WORKING.md/git-status/stale 検出ロジックのいずれかが壊れた可能性\n"
    "• 前回ハマった bug: session-id ハードコード / UTC を JST と誤ラベル\n"
    "• 対応: ログを確認し scripts/session_bootstrap.sh を修正"
)
print(json.dumps({"text": text, "username": "env-scripts dry-run", "icon_emoji": ":warning:"}))
