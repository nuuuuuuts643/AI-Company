#!/usr/bin/env python3
"""Print the next scheduled processor run time in JST ISO format.

Scheduled hours (JST): 1, 7, 13, 19 (wraps to next day at 1).
Usage: python3 scripts/ci_next_jst_schedule.py
"""
import datetime as dt

jst = dt.timezone(dt.timedelta(hours=9))
now = dt.datetime.now(jst)
for h in (1, 7, 13, 19, 25):
    hh = h % 24
    target = now.replace(hour=hh, minute=0, second=0, microsecond=0)
    if h >= 24:
        target = target + dt.timedelta(days=1)
    if target > now:
        print(target.isoformat())
        break
