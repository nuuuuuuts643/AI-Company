#!/usr/bin/env bash
# scripts/check_seo_regression.sh
#
# T2026-0502-AQ (2026-05-02): 主要ページに noindex が入る変更を CI で物理 reject
# T2026-0502-BI (2026-05-02): canonical 二重URL / JSON-LD 妥当性 を物理 reject に拡張
# T2026-0502-BI-REVERT (2026-05-02): Rule 2 (dynamic 内部リンク禁止) は UX 破壊だったため削除。
#                                     ユーザー向け SPA topic.html?id=X は復活させる。
#
# 背景:
#   - AQ: T2026-0502-ADSENSE-FIX (4/28) で frontend/topic.html / catchup.html に
#         noindex を入れたところ Cloudflare PV 260→20 (1/10) に急減
#         (docs/lessons-learned.md T2026-0502-AQ-NOINDEX-REGRESSION)
#   - BI: 静的SEO HTML (topics/X.html) と動的SPA (topic.html?id=X) が両方 indexable
#         で canonical が破綻していた。当初は内部リンクを静的に統一する方針だったが、
#         静的ページは Googlebot 向け SEO 専用 (薄い AI まとめ) で、ユーザー導線を
#         そこに送ると UX 破壊 (コメント / お気に入り / 関連トピック が消える)。
#         REVERT 後は内部リンクを動的SPA (topic.html?id=X) に戻し、canonical 統一は
#         別経路 (動的ページ noindex / JS canonical 書換) で再設計予定 (T2026-0502-BI-REDESIGN)。
#
# このスクリプトが reject するパターン:
#   1. INDEXABLE_PAGES に noindex が入る (AQ)
#   2. proc_storage.py の生成 JSON-LD で @type が "Article" (BI Rule 3)
#      → "NewsArticle" 必須 (news-sitemap と整合)
#   3. proc_storage.py の生成 JSON-LD で dateModified が date-only "YYYY-MM-DD" (BI Rule 4)
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
# (削除) Rule 2 (BI): dynamic 内部リンク禁止
#   T2026-0502-BI-REVERT で削除。静的 SEO ページ (topics/X.html) はあくまで
#   Googlebot 向け一次ページであり、ユーザー導線を強制的にそこに送ると UX が
#   破壊される (薄い AI まとめページ + AdSense + 関連記事のみ・コメント/お気に入り/
#   関連トピック/ストーリー分岐すべて消える)。canonical 統一は別経路で再設計する。
# ─────────────────────────────────────────────

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
total_violations=$(( ${#violations_aq[@]} + ${#violations_bi_schema[@]} + ${#violations_bi_date[@]} ))

if (( total_violations > 0 )); then
  echo "[check_seo_regression] ❌ ERROR: SEO regression を検出しました" >&2
  echo "" >&2

  if (( ${#violations_aq[@]} > 0 )); then
    echo "── Rule 1 (T2026-0502-AQ): 主要ページに noindex" >&2
    for v in "${violations_aq[@]}"; do echo "  - $v" >&2; done
    echo "  ※ AdSense 対策で noindex を入れる前に lessons-learned.md T2026-0502-AQ を読むこと" >&2
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

echo "[check_seo_regression] ✅ OK: noindex / @type=NewsArticle / dateModified=ISO8601 すべて健全"
exit 0
