#!/usr/bin/env python3
"""Extract a value from a JSON file by dot-separated key path.

Usage: python3 scripts/ci_json_extract.py FILE KEY [FALLBACK]
  FILE     path to JSON file
  KEY      dot-separated key path, e.g. "pv.totalPv7d"
  FALLBACK value to print on error (default: -1)

Exit 0 always (fallback on any parse/key error).
"""
import json
import sys

file_path = sys.argv[1]
key_path = sys.argv[2]
fallback = sys.argv[3] if len(sys.argv) > 3 else "-1"

try:
    with open(file_path) as f:
        d = json.load(f)
    for k in key_path.split("."):
        d = d[k]
    print(d)
except Exception:
    print(fallback)
