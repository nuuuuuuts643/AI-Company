#!/usr/bin/env python3
"""T2026-0502-IAM-DRIFT-FIX2: IAM drift CI で drift 検出時に最初の不一致位置を出力する debug helper。

env で受け取る:
  DESIRED_VAR: git tracked policy (canonicalized JSON 文字列)
  ACTUAL_VAR : AWS 現在 policy (canonicalized JSON 文字列)

呼び出し: iam-policy-drift-check.yml の drift detection step から。
"""
import os

d = os.environ.get('DESIRED_VAR', '')
a = os.environ.get('ACTUAL_VAR', '')
for i, (x, y) in enumerate(zip(d, a)):
    if x != y:
        print(f'first diff at offset {i}:')
        ctx = max(0, i - 30)
        print(f'  desired: ...{d[ctx:i]}[{x}]{d[i + 1:i + 50]}...')
        print(f'  actual:  ...{a[ctx:i]}[{y}]{a[i + 1:i + 50]}...')
        break
if len(d) != len(a):
    print(f'length mismatch: desired={len(d)} actual={len(a)}')
