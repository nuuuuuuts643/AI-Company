#!/usr/bin/env python3
"""Parse a Lambda LastModified timestamp string to Unix epoch seconds.

Usage: python3 scripts/parse_lambda_timestamp.py <timestamp_string>
Prints the epoch integer, or -1 on parse failure.
"""
import sys
from datetime import datetime

s = sys.argv[1] if len(sys.argv) > 1 else ''
for fmt in ('%Y-%m-%dT%H:%M:%S.%f%z', '%Y-%m-%dT%H:%M:%S%z'):
    try:
        dt = datetime.strptime(s, fmt)
        print(int(dt.timestamp()))
        break
    except ValueError:
        continue
else:
    print(-1)
