#!/usr/bin/env bash
# scripts/verified_line.sh <url> [<expect_substring>]
# 出力: "Verified: <url>:<http_status>:<JST_timestamp>"
#
# 使い方:
#   git commit -m "fix: T999 hoge" -m "$(bash scripts/verified_line.sh https://flotopic.com/api/topics.json)"
#
# 第2引数 expect_substring が指定された場合、レスポンス本文に含まれていなければ
# stderr に警告を出すが exit はしない（commit は通る）。

set -u

URL="${1:-}"
EXPECT="${2:-}"

if [ -z "$URL" ]; then
  echo "usage: $0 <url> [<expect_substring>]" >&2
  exit 2
fi

# HTTP status を取得（タイムアウト 15 秒）
STATUS=$(curl -o /tmp/verified_body.$$ -s -w "%{http_code}" -m 15 "$URL" 2>/dev/null || echo "000")

# JST タイムスタンプ
TS=$(TZ=Asia/Tokyo date "+%Y-%m-%dT%H:%M%z")

echo "Verified: ${URL}:${STATUS}:${TS}"

# expect_substring が指定されていれば本文を確認
if [ -n "$EXPECT" ] && [ -f /tmp/verified_body.$$ ]; then
  if ! grep -q "$EXPECT" /tmp/verified_body.$$; then
    echo "⚠️  expect substring '$EXPECT' not found in response body" >&2
  fi
fi

rm -f /tmp/verified_body.$$
exit 0
