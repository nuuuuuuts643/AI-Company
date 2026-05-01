#!/usr/bin/env python3
"""Build Slack payload for freshness-check sitemap URL reachability alert (SLI 11).

Env: OK, NG, TOTAL
Usage: OK=... NG=... TOTAL=... python3 scripts/ci_slack_freshness_sitemap.py
"""
import json
import os

text = (
    "\U0001f6a8 *Flotopic sitemap URL 到達性 NG (SLI 11)*\n"
    f"• sample: {os.environ['TOTAL']} / OK: {os.environ['OK']} / NG: {os.environ['NG']}\n"
    "• news-sitemap.xml に書いた topics/{tid}.html が 200 を返していない\n"
    "• Google Search Console でクロールエラー多発 → Google News 信頼度低下リスク\n"
    "• 対処: processor regenerateStaticHtml を invoke / S3 lifecycle ログ確認"
)
print(json.dumps({"text": text, "username": "Flotopic Sitemap Monitor", "icon_emoji": ":rotating_light:"}))
