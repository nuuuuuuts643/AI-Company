#!/usr/bin/env python3
"""Print ISO timestamp for 2 hours ago in UTC.

Fallback for environments where `date -u -d '2 hours ago'` is not available (macOS).
Usage: python3 scripts/ci_utc_2h_ago.py
"""
import datetime as dt

print((dt.datetime.utcnow() - dt.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ"))
