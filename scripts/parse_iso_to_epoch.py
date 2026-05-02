#!/usr/bin/env python3
"""
ISO8601 タイムスタンプを Unix epoch (秒) に変換する。

用途: deploy-trigger-watchdog.yml が AWS Lambda の `LastModified`
(ISO8601 形式) を Unix epoch に変換するために使う。

入出力:
  argv[1]: ISO8601 文字列 (例: "2026-05-02T10:21:00.000+0000")
  stdout: Unix epoch (秒)、失敗時は -1
  exit: 0 (常に・呼び出し側でログに残せるよう)

背景: 元は .github/workflows/deploy-trigger-watchdog.yml の
run: block に python3 -c (heredoc) でインライン埋め込みされていたが、
'No inline logic in YAML' (lint-yaml-logic.yml) ルール違反で main CI が
連続 failure していた。スクリプトに切り出すことで CI lint を pass させる。
"""
import sys
from datetime import datetime


def main():
    if len(sys.argv) < 2:
        print(-1)
        return 0
    s = sys.argv[1].strip()
    if not s:
        print(-1)
        return 0
    for fmt in ('%Y-%m-%dT%H:%M:%S.%f%z', '%Y-%m-%dT%H:%M:%S%z'):
        try:
            dt = datetime.strptime(s, fmt)
            print(int(dt.timestamp()))
            return 0
        except ValueError:
            continue
    print(-1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
