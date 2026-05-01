#!/usr/bin/env python3
"""Sum CloudWatch Datapoints from JSON on stdin.

Prints the integer sum, or -1 if no datapoints (MetricFilter not set or Lambda never ran).
Usage: aws cloudwatch get-metric-statistics ... --output json | python3 scripts/ci_cw_sum_datapoints.py
"""
import json
import sys

d = json.load(sys.stdin)
pts = d.get("Datapoints", [])
if not pts:
    print(-1)
else:
    print(int(sum(p["Sum"] for p in pts)))
