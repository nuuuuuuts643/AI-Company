#!/usr/bin/env python3
"""Compute minutes since UPDATED_AT ISO timestamp.

Prints integer minutes elapsed, or -1 on parse error.
Usage: UPDATED_AT="2026-05-01T12:00:00Z" python3 scripts/ci_freshness_diff_min.py
"""
import datetime as dt
import os

ua = os.environ["UPDATED_AT"]
try:
    t = dt.datetime.fromisoformat(ua.replace("Z", "+00:00"))
    now = dt.datetime.now(dt.timezone.utc)
    print(int((now - t).total_seconds() // 60))
except Exception:
    print(-1)
