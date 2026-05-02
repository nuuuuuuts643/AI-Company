#!/usr/bin/env bash
# scripts/check_seo_regression.sh
#
# T2026-0502-AQ (2026-05-02): 主要ページに noindex が入る変更を CI で物理 reject
# T2026-0502-BI (2026-05-02): canonical 二重URL / JSON-LD 妥当性 / dynamic 内部リンク
#                              の構造的 SEO regression を物理 reject に拡張
#
# 背景:
#   - AQ: T2026-0502-ADSENSE-FIX (4/28) で frontend/topic.html / catchup.html に
#         noindex を入れたところ Cloudflare PV 260→20 (1/10) に急減
#         (docs/lessons-learned.md T2026-0502-AQ-NOINDEX-REGRESSION)
#   - BI: 静的SEO HTML (topics/X.html) と動的SPA (topic.html?id=X) が両方 indexable
#         で canonical が破綻していた。内部リンクは全て dynamic を指し、初期 canonical
#         は "topic.html" (id 無し) の単独URL。Google が全 ID を topic.html に統合
#         する重複URLとして処理 → ページランク分散 + indexing 不安定
#         (docs/lessons-learned.md T2026-0502-BI-SEO-CANONICAL-DUPLICATE)
#
# このスクリプトが reject するパターン:
#   1. INDEXABLE_PAGES に noindex が入る (AQ)
#   2. frontend/ の JS/HTML に topic.html?id= 形式の dynamic 内部リンクが残る (BI)
#      → 例外: admin.html / legacy.html (どちらも noindex 済 or 開発用)
#   3. proc_storage.py の生成 JSON-LD で @type が "Article" (BI)
#      → "NewsArticle" 必須 (news-sitemap と整合)
#   4. proc_storage.py の生成 JSON-LD で dateModified が date-only "YYYY-MM-DD" (BI)
#      → 完全 ISO 8601 必須 (Google が "modified < published" と誤読する)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# ─────────────────────────────────────────────
# Rule 1 (AQ): noindex 混入 reject
# ─────────────────────────────────────────────
INDEXABLE_PAGES=(
  "projects/P003-news-timeline/frontend/index.html"
  "projects/P003-news-timeline/frontend/topic.html"
  "projects/P003-news-timeline/frontend/catchup.html"
  "projects/P003-news-timeline/frontend/storymap.html"
  "projects/P003-news-timeline/frontend/about.html"
  "projects/P003-news-timeline/frontend/contact.html"
  "projects/P003-news-timeline/frontend/terms.html"
)

violations_aq=()
for page in "${INDEXABLE_PAGES[@]}"; do
  if [[ -f "$page" ]]; then
    if grep -Eq '<meta[[:space:]]+name="robots"[[:space:]]+content="[^"]*noindex' "$page" 2>/dev/null; then
      violations_aq+=("$page")
    fi
  fi
done

# ─────────────────────────────────────────────
# Rule 2 (BI): dynamic 内部リンク禁止
#   admin.html / legacy.html / detail.js が _自分自身_ を更新するための
#   document.title 等は対象外 (URL リンクのみ)。
# ─────────────────────────────────────────────
DYNAMIC_LINK_SCAN_DIRS=(
  "projects/P003-news-timeline/frontend"
)
DYNAMIC_LINK_EXCLUDE_RE='^(.*/(admin|legacy)\.html|.*/node_modules/.*)$'

violations_bi_link=()
while IFS= read -r line; do
  file="${line%%:*}"
  if [[ "$file" =~ $DYNAMIC_LINK_EXCLUDE_RE ]]; then continue; fi
  violations_bi_link+=("$line")
done < <(
  for d in "${DYNAMIC_LINK_SCAN_DIRS[@]}"; do
    [[ -d "$d" ]] || continue
    grep -rnE 'href[[:space:]]*=[[:space:]]*[`"'"'"']?[^`"'"'"' ]*topic\.html\?id=' "$d" \
      --include="*.html" --include="*.js" 2>/dev/null || true
  done
)

# ─────────────────────────────────────────────
# Rule 3 (BI): proc_storage.py の生成 JSON-LD は NewsArticle
# ─────────────────────────────────────────────
PROC_STORAGE="projects/P003-news-timeline/lambda/processor/proc_storage.py"
violations_bi_schema=()
if [[ -f "$PROC_STORAGE" ]]; then
  # generate_static_topic_html 関数の本体だけを切り出す。
  # 注: awk '/start/,/end/' は start と end が同じパターンに被ると start 行で
  #     即終了するので、明示的に flag で制御する。
  func_body="$(awk '
    /^def generate_static_topic_html/ { in_func=1; next }
    in_func && /^def [a-zA-Z_]/ { in_func=0 }
    in_func { print }
  ' "$PROC_STORAGE")"
  if printf '%s\n' "$func_body" | grep -E "['\"]@type['\"][[:space:]]*:[[:space:]]*['\"]Article['\"]" >/dev/null 2>&1; then
    violations_bi_schema+=("$PROC_STORAGE: @type が \"Article\" (\"NewsArticle\" 必須)")
  fi
fi

# ─────────────────────────────────────────────
# Rule 4 (BI): dateModified は完全 ISO 8601
#   生成コード内で 'dateModified': last_upd 等 date-only 変数の利用を検出
# ─────────────────────────────────────────────
violations_bi_date=()
if [[ -f "$PROC_STORAGE" ]]; then
  # generate_static_topic_html 内で dateModified が `last_upd`(date-only) を直接使うのは禁止。
  # 期待形: dateModified に full ISO ('%Y-%m-%dT%H:%M:%SZ') が入る変数 (_dm_iso 等) を使う。
  # 検出: dateModified の右辺が last_upd / date-only 文字列リテラル
  if printf '%s\n' "$func_body" | grep -E "['\"]dateModified['\"][[:space:]]*:[[:space:]]*last_upd[[:space:]]*[,\}]" >/dev/null 2>&1; then
    violations_bi_date+=("$PROC_STORAGE: dateModified に date-only 変数 last_upd を直接使用 (full ISO の _dm_iso 等を使う)")
  fi
  if printf '%s\n' "$func_body" | grep -E "['\"]dateModified['\"][[:space:]]*:[[:space:]]*['\"]?[0-9]{4}-[0-9]{2}-[0-9]{2}['\"]?[[:space:]]*[,\}]" >/dev/null 2>&1; then
    violations_bi_date+=("$PROC_STORAGE: dateModified に date-only リテラル ('YYYY-MM-DD')")
  fi
fi

# ─────────────────────────────────────────────
# 集計 & 出力
# ─────────────────────────────────────────────
total_violations=$(( ${#violations_aq[@]} + ${#violations_bi_link[@]} + ${#violations_bi_schema[@]} + ${#violations_bi_date[@]} ))

if (( total_violations > 0 )); then
  echo "[check_seo_regression] ❌ ERROR: SEO regression を検出しました" >&2
  echo "" >&2

  if (( ${#violations_aq[@]} > 0 )); then
    echo "── Rule 1 (T2026-0502-AQ): 主要ページに noindex" >&2
    for v in "${violations_aq[@]}"; do echo "  - $v" >&2; done
    echo "  ※ AdSense 対策で noindex を入れる前に lessons-learned.md T2026-0502-AQ を読むこと" >&2
    echo "" >&2
  fi

  if (( ${#violations_bi_link[@]} > 0 )); then
    echo "── Rule 2 (T2026-0502-BI): dynamic 内部リンク混入 (topic.html?id=)" >&2
    for v in "${violations_bi_link[@]}"; do echo "  - $v" >&2; done
    echo "  ※ 静的 URL に統一: topics/\${tid}.html を使う" >&2
    echo "  ※ 多重防御: cf-redirect-function.js が 301 で吸収するが、内部リンクは静的を一次とする" >&2
    echo "" >&2
  fi

  if (( ${#violations_bi_schema[@]} > 0 )); then
    echo "── Rule 3 (T2026-0502-BI): JSON-LD @type が Article (NewsArticle 必須)" >&2
    for v in "${violations_bi_schema[@]}"; do echo "  - $v" >&2; done
    echo "  ※ news-sitemap.xml が news として宣言しているため、ページ側も NewsArticle 必須" >&2
    echo "" >&2
  fi

  if (( ${#violations_bi_date[@]} > 0 )); then
    echo "── Rule 4 (T2026-0502-BI): dateModified が date-only" >&2
    for v in "${violations_bi_date[@]}"; do echo "  - $v" >&2; done
    echo "  ※ 完全 ISO 8601 ('%Y-%m-%dT%H:%M:%SZ') にする" >&2
    echo "  ※ date-only だと Google が 00:00:00Z 解釈で 'modified < published' と誤読する" >&2
    echo "" >&2
  fi

  echo "詳細: docs/lessons-learned.md (T2026-0502-AQ / T2026-0502-BI セクション)" >&2
  exit 1
fi

echo "[check_seo_regression] ✅ OK: noindex / dynamic-link / @type=NewsArticle / dateModified=ISO8601 すべて健全"
exit 0
