#!/usr/bin/env bash
# scripts/check_seo_regression.sh
#
# T2026-0502-AQ (2026-05-02): 主要ページに noindex が入る変更を CI で物理 reject
# T2026-0502-BI (2026-05-02): canonical 二重URL / JSON-LD 妥当性 を物理 reject に拡張
# T2026-0502-BI-REVERT (2026-05-02): Rule 2 (dynamic 内部リンク禁止) は UX 破壊だったため削除。
#                                     ユーザー向け SPA topic.html?id=X は復活させる。
# T2026-0502-BI-PERMANENT (2026-05-02): 役割分離の再発防止物理ガードを追加。
#                                        Rule 5 (動的SPA内部リンク強制 = 静的 topics/X.html リンク禁止)
#                                        Rule 6 (topic.html に SPA UX 要素必須)
#                                        Rule 7 (topic.html の初期 canonical=id 無し topic.html 禁止)
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
#   - PERMANENT: 「次に同じ事故を起こさない」物理ガードを追加。役割分離 (動的=ユーザー UX
#         一次・静的=Googlebot SEO 一次) を CI で強制する。
#         詳細 → docs/rules/dynamic-vs-static-url.md
#
# このスクリプトが reject するパターン:
#   1. INDEXABLE_PAGES に noindex が入る (AQ Rule 1)
#   2. proc_storage.py の生成 JSON-LD で @type が "Article" (BI Rule 3)
#      → "NewsArticle" 必須 (news-sitemap と整合)
#   3. proc_storage.py の生成 JSON-LD で dateModified が date-only "YYYY-MM-DD" (BI Rule 4)
#      → 完全 ISO 8601 必須 (Google が "modified < published" と誤読する)
#   4. frontend の内部リンクが静的 topics/X.html (= Googlebot 向け薄ページ) を指す (PERMANENT Rule 5)
#      → ユーザー導線は動的 topic.html?id=X (full UX) を指す。share/canonical URL は除外。
#   5. topic.html から SPA UX 要素が消える (PERMANENT Rule 6)
#      → #comments-section / #topic-fav-btn / #related-articles / #discovery-section /
#        #parent-topic-link のいずれかが欠けたら reject
#   6. topic.html の初期 <link rel="canonical"> が id 無し "topic.html" を指す (PERMANENT Rule 7)
#      → 「全 ID を topic.html 単独に統合する duplicate URL シグナル」を Google に送る誤設計

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# ─────────────────────────────────────────────
# Rule 1 (AQ): noindex 混入 reject
# ─────────────────────────────────────────────
INDEXABLE_PAGES=(
  "projects/P003-news-timeline/frontend/index.html"
  # topic.html は T2026-0502-BI-REDESIGN (2026-05-03) で noindex 追加済み。
  # 静的 topics/{id}.html が indexed 済みの今、動的 SPA に noindex を入れることで
  # "Duplicate, Google chose different canonical" を解消する。
  # catchup.html / storymap.html は引き続き indexable のまま。
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
# Rule 5 (BI-PERMANENT): 動的 SPA 内部リンク強制 (静的 topics/X.html 内部リンク禁止)
#   ユーザー導線は動的 topic.html?id=X (full UX) を指すこと。
#   静的 topics/X.html は Googlebot 向け SEO 専用なのでユーザー導線にしない。
#   除外: ①share/canonical 用の `https://flotopic.com/topics/...` 絶対 URL は OK
#         ②admin/legacy.html (開発用)
#         ③`topics/index.html` `topics-card.json` `topics.json` 等の固定 path は別物 (検索 grep で除外)
#         ④node_modules/ は除外
# ─────────────────────────────────────────────
DYNAMIC_LINK_SCAN_DIRS=(
  "projects/P003-news-timeline/frontend"
)
STATIC_LINK_EXCLUDE_RE='^(.*/(admin|legacy)\.html|.*/node_modules/.*)$'

violations_static_link=()
while IFS= read -r line; do
  file="${line%%:*}"
  if [[ "$file" =~ $STATIC_LINK_EXCLUDE_RE ]]; then continue; fi
  violations_static_link+=("$line")
done < <(
  for d in "${DYNAMIC_LINK_SCAN_DIRS[@]}"; do
    [[ -d "$d" ]] || continue
    # 内部リンク `href="topics/${...}.html"` (or 'topics/...html' literal) を検出
    # share/canonical 用の `https://flotopic.com/topics/...` は除外する (絶対 URL は SEO 一次への意図的参照)
    grep -rnE 'href[[:space:]]*=[[:space:]]*[`"'"'"']topics/[^`"'"'"' ]*\.html' "$d" \
      --include="*.html" --include="*.js" 2>/dev/null || true
  done
)

# ─────────────────────────────────────────────
# Rule 6 (BI-PERMANENT): topic.html に SPA UX 要素必須
#   ユーザー導線が動的 SPA に向く以上、SPA に UX 要素 (コメント / お気に入り / 関連記事 /
#   Discovery / 親トピックリンク) が必ず存在しなければ「役割分離違反 = UX 破壊」になる。
# ─────────────────────────────────────────────
TOPIC_HTML="projects/P003-news-timeline/frontend/topic.html"
REQUIRED_SPA_ELEMENTS=(
  'id="comments-section"'
  'id="topic-fav-btn"'
  'id="related-articles"'
  'id="discovery-section"'
  'id="parent-topic-link"'
)

violations_spa_ux=()
if [[ -f "$TOPIC_HTML" ]]; then
  for elem in "${REQUIRED_SPA_ELEMENTS[@]}"; do
    if ! grep -qF "$elem" "$TOPIC_HTML"; then
      violations_spa_ux+=("$TOPIC_HTML: 必須 SPA UX 要素 '$elem' が消えている")
    fi
  done
fi

# ─────────────────────────────────────────────
# Rule 7 (BI-PERMANENT): topic.html の初期 canonical が id 無し "topic.html" 禁止
#   理由: Googlebot 初回 fetch (JS rendering 前) で「全 ID が topic.html 単独 URL に統合される
#         duplicate URL シグナル」を送ることになる。
#   期待: 初期 href="" (空) で出して、JS が topicId 確定後に `topics/${id}.html` を inject。
# ─────────────────────────────────────────────
violations_initial_canonical=()
if [[ -f "$TOPIC_HTML" ]]; then
  # `<link rel="canonical" ... href="...topic.html..." (id クエリ無し or 末尾 topic.html)` を検出
  # 許容: href="" (空) / href が含まれない / href="topic.html?id=" (id クエリ込み・通常無いが念のため許容)
  if grep -E '<link[^>]*rel=["'"'"']canonical["'"'"'][^>]*href=["'"'"'][^"'"'"']*topic\.html(["'"'"']|#)' "$TOPIC_HTML" >/dev/null 2>&1; then
    # ただし href="topic.html?id=" は許容
    if ! grep -E '<link[^>]*rel=["'"'"']canonical["'"'"'][^>]*href=["'"'"'][^"'"'"']*topic\.html\?id=' "$TOPIC_HTML" >/dev/null 2>&1; then
      violations_initial_canonical+=("$TOPIC_HTML: 初期 <link rel=\"canonical\"> が id 無し \"topic.html\" を指している (Google が duplicate URL と誤解する)")
    fi
  fi
fi

# ─────────────────────────────────────────────
# Rule 8 (BI-CACHE-FIX): HTML の Cache-Control が "no-store" を含むこと
#   理由: スマホで PR merge 後の UX 復旧反映遅れ事故 (T2026-0502-BI-REVERT 後 PO 報告)
#         の構造対処。no-cache は ETag check race / SW 経由 cache fallback で古い
#         HTML が返る隙間あり → no-store でブラウザ・SW どちらも cache 不可を物理保証。
#   検査対象: .github/workflows/deploy-p003.yml の HTML sync 部分 + projects/P003-news-timeline/deploy.sh
# ─────────────────────────────────────────────
violations_html_cache=()

# .github/workflows/deploy-p003.yml で HTML aws s3 sync の cache-control が no-store を含むか
DEPLOY_YAML=".github/workflows/deploy-p003.yml"
if [[ -f "$DEPLOY_YAML" ]]; then
  # 「--include "*.html"」を含むブロックの周辺で cache-control が no-store を含まなければ violation
  # awk で *.html sync ブロック切り出し → cache-control 行抽出 → no-store 含むかチェック
  html_cc=$(awk '
    /--include[[:space:]]+"\*\.html"/ { in_html_sync=1 }
    in_html_sync && /--cache-control/ {
      match($0, /"[^"]+"/)
      if (RSTART > 0) {
        cc = substr($0, RSTART+1, RLENGTH-2)
        print cc
        in_html_sync = 0
      }
    }
    in_html_sync && /\\$/ { next }
    in_html_sync && !/\\$/ && !/--cache-control/ { in_html_sync = 0 }
  ' "$DEPLOY_YAML")
  if [[ -n "$html_cc" ]] && ! echo "$html_cc" | grep -q "no-store"; then
    violations_html_cache+=("$DEPLOY_YAML: HTML sync の cache-control \"$html_cc\" に no-store が含まれていない")
  fi
fi

# projects/P003-news-timeline/deploy.sh の HTML cp ブロック
DEPLOY_SH="projects/P003-news-timeline/deploy.sh"
if [[ -f "$DEPLOY_SH" ]]; then
  # for html_file in frontend/*.html ループの cp で cache-control が no-store を含むか
  if grep -B2 -A4 'for html_file in frontend/\*.html' "$DEPLOY_SH" | grep -E -- '--cache-control' | grep -v "no-store" >/dev/null 2>&1; then
    violations_html_cache+=("$DEPLOY_SH: frontend/*.html ループの cache-control に no-store が含まれていない")
  fi
fi

# ─────────────────────────────────────────────
# 集計 & 出力
# ─────────────────────────────────────────────
total_violations=$((
  ${#violations_aq[@]} +
  ${#violations_bi_schema[@]} +
  ${#violations_bi_date[@]} +
  ${#violations_static_link[@]} +
  ${#violations_spa_ux[@]} +
  ${#violations_initial_canonical[@]} +
  ${#violations_html_cache[@]}
))

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

  if (( ${#violations_static_link[@]} > 0 )); then
    echo "── Rule 5 (T2026-0502-BI-PERMANENT): 内部リンクが静的 topics/X.html を指している (動的SPA topic.html?id=X 必須)" >&2
    for v in "${violations_static_link[@]}"; do echo "  - $v" >&2; done
    echo "  ※ 静的 topics/X.html は Googlebot 向け SEO 専用 (薄い AI まとめ)。" >&2
    echo "  ※ ユーザー導線は動的 topic.html?id=X (full UX) に統一する。" >&2
    echo "  ※ 詳細 → docs/rules/dynamic-vs-static-url.md" >&2
    echo "" >&2
  fi

  if (( ${#violations_spa_ux[@]} > 0 )); then
    echo "── Rule 6 (T2026-0502-BI-PERMANENT): topic.html から SPA UX 要素が消えた" >&2
    for v in "${violations_spa_ux[@]}"; do echo "  - $v" >&2; done
    echo "  ※ 動的 SPA topic.html はユーザー向け full UX 一次。" >&2
    echo "  ※ コメント / お気に入り / 関連記事 / Discovery / 親トピックリンクは必須。" >&2
    echo "  ※ どれかを削除する設計変更を行う前に PO 確認 + lessons-learned T2026-0502-BI-REVERT 参照" >&2
    echo "" >&2
  fi

  if (( ${#violations_initial_canonical[@]} > 0 )); then
    echo "── Rule 7 (T2026-0502-BI-PERMANENT): topic.html の初期 canonical が id 無し \"topic.html\" を指している" >&2
    for v in "${violations_initial_canonical[@]}"; do echo "  - $v" >&2; done
    echo "  ※ 期待: <link rel=\"canonical\" id=\"canonical-url\" href=\"\"> (空) で出して、JS が topicId 確定後に inject" >&2
    echo "  ※ id 無し canonical は 'duplicate URL シグナル' を Google に送る誤設計" >&2
    echo "" >&2
  fi

  if (( ${#violations_html_cache[@]} > 0 )); then
    echo "── Rule 8 (T2026-0502-BI-CACHE-FIX): HTML の Cache-Control に no-store が含まれていない" >&2
    for v in "${violations_html_cache[@]}"; do echo "  - $v" >&2; done
    echo "  ※ 期待: HTML を 'no-store, no-cache, must-revalidate' で配信 (ブラウザ・SW どちらも cache 不可)" >&2
    echo "  ※ no-cache は ETag check race / SW 経由 cache fallback で古い HTML が返る隙間あり" >&2
    echo "  ※ T2026-0502-BI-REVERT 後 PO スマホで UX 復旧反映遅れた事故の構造対処" >&2
    echo "" >&2
  fi

  echo "詳細: docs/lessons-learned.md (T2026-0502-AQ / T2026-0502-BI / T2026-0502-BI-REVERT / T2026-0502-BI-CACHE-FIX)" >&2
  echo "      docs/rules/dynamic-vs-static-url.md (役割分離 doc)" >&2
  exit 1
fi

echo "[check_seo_regression] ✅ OK: noindex / @type=NewsArticle / dateModified=ISO8601 / 動的SPA内部リンク / SPA UX 要素 / 初期 canonical / HTML no-store すべて健全"
exit 0
