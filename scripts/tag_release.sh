#!/usr/bin/env bash
# tag_release.sh — リリースタグを打つ
# 形式: vYYYY.MMDD.N（同日に複数リリースがあれば .1 .2 とインクリメント）
set -euo pipefail

DATE=$(TZ=Asia/Tokyo date '+%Y.%m%d')
N=1

while git rev-parse "v${DATE}.${N}" &>/dev/null 2>&1; do
  N=$((N+1))
done

TAG="v${DATE}.${N}"
git tag -a "$TAG" -m "Release $TAG"
git push origin "$TAG"
echo "✅ Tagged: $TAG"
