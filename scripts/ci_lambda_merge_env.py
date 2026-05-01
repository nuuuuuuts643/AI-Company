#!/usr/bin/env python3
"""Merge EXISTING_ENV with ANTHROPIC_API_KEY for Lambda update-function-configuration.

Output: comma-separated key=value pairs (AWS CLI --environment Variables format).
Usage: EXISTING_ENV="$EXISTING_ENV" ANTHROPIC_API_KEY="$KEY" python3 scripts/ci_lambda_merge_env.py
"""
import json
import os

env = json.loads(os.environ.get("EXISTING_ENV") or "{}") or {}
env["ANTHROPIC_API_KEY"] = os.environ.get("ANTHROPIC_API_KEY", "")
print(",".join(f"{k}={v}" for k, v in env.items()))
