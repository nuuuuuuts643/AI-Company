#!/usr/bin/env python3
"""Send a text message to Slack via webhook.

Reads SLACK_WEBHOOK_URL from environment.
Usage: python3 scripts/ci_slack_send.py "message text"
"""
import json
import os
import sys
import urllib.request

text = sys.argv[1]
webhook = os.environ["SLACK_WEBHOOK_URL"]
data = json.dumps({"text": text}).encode("utf-8")
req = urllib.request.Request(
    webhook, data=data, headers={"Content-Type": "application/json"}
)
urllib.request.urlopen(req)
