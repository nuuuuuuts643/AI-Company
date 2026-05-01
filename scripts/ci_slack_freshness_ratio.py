#!/usr/bin/env python3
"""Build Slack payload for freshness-check recent-ratio alert (SLI 12).

Env: RATIO, RECENT, TOTAL, MISSING
Usage: RATIO=... python3 scripts/ci_slack_freshness_ratio.py
"""
import json
import os

text = (
    "\U0001f6a8 *Flotopic <24h トピック比率 異常 (SLI 12)*\n"
    f"• <24h トピック: `{os.environ['RECENT']} / {os.environ['TOTAL']}` = `{os.environ['RATIO']}%` (閾値 10%)\n"
    f"• lastArticleAt 欠損: `{os.environ['MISSING']}` 件\n"
    "• 新規記事が DDB に流入していない疑い (fetcher / processor の silent fail)\n"
    "• 対処: ① CloudWatch p003-fetcher の最新ログ確認 ② DDB の lastArticleAt 分布を直接確認 ③ RSS フィード生存確認\n"
    "\n_T2026-0430-F success-but-stale 検出 (PR #46 で発覚した 3日停滞 再発防止)_"
)
print(json.dumps({"text": text, "username": "Flotopic Recent Ratio Monitor", "icon_emoji": ":rotating_light:"}))
