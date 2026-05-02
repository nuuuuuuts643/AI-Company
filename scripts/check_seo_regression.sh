#!/usr/bin/env bash
# scripts/check_seo_regression.sh
# T2026-0502-AQ (2026-05-02): 主要ページに noindex が入る変更を CI で物理 reject
#
# 背景: T2026-0502-ADSENSE-FIX (4/28) で AdSense 薄コンテンツ対策として
# frontend/topic.html / frontend/catchup.html に noindex を入れたところ、
# Cloudflare Web Analytics PV が 4/27 260 → 4/28 20 (1/10) へ急減した。
# Google index から主要ページが抜けたことが原因。
# 薄コンテンツ問題は app.js の renderTopics() で keyPoint<80字 を除外する
# frontend filter で対処済のため noindex は不要。
#
# 詳細: docs/lessons-learned.md T2026-0502-AQ-NOINDEX-REGRESSION セクション
set -euo pipefail

# noindex が入ってはいけない主要ページ (SEO 流入が必要なページ)
INDEXABLE_PAGES=(
  "projects/P003-news-timeline/frontend/index.html"
  "projects/P003-news-timeline/frontend/topic.html"
  "projects/P003-news-timeline/frontend/catchup.html"
  "projects/P003-news-timeline/frontend/storymap.html"
  "projects/P003-news-timeline/frontend/about.html"
  "projects/P003-news-timeline/frontend/contact.html"
  "projects/P003-news-timeline/frontend/terms.html"
)

violations=()
for page in "${INDEXABLE_PAGES[@]}"; do
  if [[ -f "$page" ]]; then
    if grep -Eq '<meta[[:space:]]+name="robots"[[:space:]]+content="[^"]*noindex' "$page" 2>/dev/null; then
      violations+=("$page")
    fi
  fi
done

if [[ ${#violations[@]} -gt 0 ]]; then
  echo "[check_seo_regression] ❌ ERROR: 主要ページに noindex が含まれています (T2026-0502-AQ 再発防止):" >&2
  for v in "${violations[@]}"; do
    echo "  - $v" >&2
  done
  echo "" >&2
  echo "理由: AdSense 対策で noindex を入れた T2026-0502-ADSENSE-FIX が Google index から" >&2
  echo "主要ページを除外し、Cloudflare PV を 1/10 (260→20 PV/day) に急減させた事故 (4/28)。" >&2
  echo "薄コンテンツ問題は app.js の renderTopics() frontend filter で対処済のため noindex は不要。" >&2
  echo "" >&2
  echo "もし意図的に noindex を入れる必要がある場合は:" >&2
  echo "  1. WORKING.md に対応タスク ID と「PV 減少が許容される理由」を明記" >&2
  echo "  2. docs/lessons-learned.md の T2026-0502-AQ セクションに「許容理由」を追記" >&2
  echo "  3. 本スクリプトの INDEXABLE_PAGES から該当ファイルを除外する変更を同 PR で行う" >&2
  exit 1
fi

echo "[check_seo_regression] ✅ OK: 主要 ${#INDEXABLE_PAGES[@]} ページに noindex なし"
exit 0
