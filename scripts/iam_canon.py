#!/usr/bin/env python3
"""T2026-0502-IAM-DRIFT-FIX2: IAM policy JSON を sort_keys=True で recursive 正規化する。

stdin から JSON を読み、sort_keys=True + separators=(',', ':') で minify した文字列を stdout 出力。
AWS canonicalize 後の representation と 1:1 一致確認するため、jq -S の浅い recursive sort 起因の
偽陽性 drift を排除する目的 (T2026-0502-IAM-DRIFT-FIX2 由来)。

呼び出し: iam-policy-drift-check.yml の drift detection step + apply.sh から (将来統一)。
"""
import json
import sys

obj = json.load(sys.stdin)
print(json.dumps(obj, sort_keys=True, separators=(',', ':')))
