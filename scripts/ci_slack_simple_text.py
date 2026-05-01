#!/usr/bin/env python3
"""Wrap MSG env var as a minimal Slack JSON payload.

Env: MSG
Usage: MSG="some text" python3 scripts/ci_slack_simple_text.py
"""
import json
import os

print(json.dumps({"text": os.environ["MSG"]}))
