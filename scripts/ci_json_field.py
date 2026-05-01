#!/usr/bin/env python3
"""Extract a single top-level field from a JSON file.

Usage: python3 scripts/ci_json_field.py FILE FIELD [FALLBACK]
  FILE     path to JSON file
  FIELD    top-level key name (e.g. "updatedAt")
  FALLBACK value to print if missing/error (default: empty string)

Exit 0 always.
"""
import json
import sys

file_path = sys.argv[1]
field = sys.argv[2]
fallback = sys.argv[3] if len(sys.argv) > 3 else ""

try:
    with open(file_path) as f:
        d = json.load(f)
    print(d.get(field, fallback))
except Exception:
    print(fallback)
