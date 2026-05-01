#!/usr/bin/env bash
# UX 定量評価スクリプト (T2026-0430-UX)
# 実行: bash scripts/ux_check.sh [--base-url https://flotopic.com] [--md docs/ux-scores.md] [--dry-run] [--json]
#
# 目的: 「ユーザー体験の改善が機能しているか」を週次で数値計測する。
#   定性評価CI (qualitative_eval.sh / PR #69) は AI 出力の品質を見るが、
#   こちらは UX (情報密度・関連トピック密度・モバイル表示・応答速度) を見る。
#   API 呼び出しゼロ (curl + python3 のみ)。
#
# 評価軸:
#   ① 情報密度        : velocityScore>0 の topic 件数
#   ② 関連トピック密度: childTopics の平均/中央値件数 (PR #71 でフロント補完済)
#   ③ keyPoint 密度  : keyPoint>=100字 の比率, 平均文字数
#   ④ 続報バッジ存在 : app.js に「続報あり」「card-continuation-badge」が残っているか
#   ⑤ モバイル崩れ検知: index.html / topic.html / about.html の必須CSSクラス残存
#   ⑥ 応答性          : トップページ TTFB / favicon, manifest 200
#   ⑦ ジャンル別      : 経済 / 政治 / テック 等で ①〜③ の差を可視化
#
# 出力: docs/ux-scores.md に新行を append (新しいものが上)
# 失敗条件 (exit 1): 5xx / 必須CSSクラス欠落 / JSON パース失敗
set -uo pipefail

BASE_URL="https://flotopic.com"
MD_OUT="docs/ux-scores.md"
DRY_RUN=0
JSON_OUT=0

while [ $# -gt 0 ]; do
  case "$1" in
    --base-url) BASE_URL="$2"; shift 2 ;;
    --md) MD_OUT="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --json) JSON_OUT=1; shift ;;
    -h|--help)
      sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

UA='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'

if [ "$JSON_OUT" -eq 0 ]; then
  echo "─────────────────────────────────────────"
  echo "UX 定量評価 (T2026-0430-UX)"
  echo "  base_url: ${BASE_URL}"
  echo "  md_out:   ${MD_OUT}"
  echo "  dry_run:  ${DRY_RUN}"
  echo "─────────────────────────────────────────"
fi

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

# ── ① ページ HTML を fetch (モバイル UA) ────────────────────────
fetch() {
  local path="$1" out="$2"
  curl -sS --max-time 15 -A "$UA" -o "$out" -w '%{http_code} %{time_total}\n' "${BASE_URL}${path}" 2>/dev/null \
    || echo "000 0"
}

read INDEX_CODE INDEX_TIME < <(fetch "/" "$TMPDIR/index.html")
read ABOUT_CODE ABOUT_TIME < <(fetch "/about.html" "$TMPDIR/about.html")
read TOPIC_CODE TOPIC_TIME < <(fetch "/topic.html" "$TMPDIR/topic.html")
read APPJS_CODE APPJS_TIME < <(fetch "/app.js" "$TMPDIR/app.js")
read CARD_CODE  CARD_TIME  < <(fetch "/api/topics-card.json" "$TMPDIR/card.json")
read FAV_CODE   FAV_TIME   < <(fetch "/favicon.ico" "$TMPDIR/favicon.ico")
read MANI_CODE  MANI_TIME  < <(fetch "/manifest.json" "$TMPDIR/manifest.json")

if [ "$JSON_OUT" -eq 0 ]; then
  printf "fetch http (time):\n"
  printf "  %-20s %s (%.2fs)\n" "/"                "$INDEX_CODE" "$INDEX_TIME"
  printf "  %-20s %s (%.2fs)\n" "/about.html"      "$ABOUT_CODE" "$ABOUT_TIME"
  printf "  %-20s %s (%.2fs)\n" "/topic.html"      "$TOPIC_CODE" "$TOPIC_TIME"
  printf "  %-20s %s (%.2fs)\n" "/app.js"          "$APPJS_CODE" "$APPJS_TIME"
  printf "  %-20s %s (%.2fs)\n" "/api/topics-card" "$CARD_CODE"  "$CARD_TIME"
  printf "  %-20s %s (%.2fs)\n" "/favicon.ico"     "$FAV_CODE"   "$FAV_TIME"
  printf "  %-20s %s (%.2fs)\n" "/manifest.json"   "$MANI_CODE"  "$MANI_TIME"
fi

# 必須5ページが 5xx/4xx なら即落ち
critical_fail=0
for code in "$INDEX_CODE" "$ABOUT_CODE" "$TOPIC_CODE" "$APPJS_CODE" "$CARD_CODE"; do
  case "$code" in
    2*) ;;
    *) critical_fail=1 ;;
  esac
done
if [ "$critical_fail" -ne 0 ]; then
  echo "::error::必須ページの fetch に失敗 (5xx/4xx あり)" >&2
  exit 1
fi

# ── ② Python 本体: HTMLクラス検証 + JSON 集計 + MD 追記 ─────
INDEX_HTML="$TMPDIR/index.html" \
ABOUT_HTML="$TMPDIR/about.html" \
TOPIC_HTML="$TMPDIR/topic.html" \
APPJS="$TMPDIR/app.js" \
CARD_JSON="$TMPDIR/card.json" \
INDEX_TIME="$INDEX_TIME" \
TOPIC_TIME="$TOPIC_TIME" \
FAV_CODE="$FAV_CODE" \
MANI_CODE="$MANI_CODE" \
MD_OUT="$MD_OUT" \
DRY_RUN="$DRY_RUN" \
JSON_OUT="$JSON_OUT" \
BASE_URL="$BASE_URL" \
python3 <<'PYEOF'
import json
import os
import re
import sys
import statistics
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
NOW = datetime.now(JST)
TODAY_TS = NOW.strftime('%Y-%m-%d %H:%M JST')

DRY_RUN  = os.environ.get('DRY_RUN',  '0') == '1'
JSON_OUT = os.environ.get('JSON_OUT', '0') == '1'
MD_OUT   = os.environ.get('MD_OUT',   'docs/ux-scores.md')
BASE_URL = os.environ.get('BASE_URL', 'https://flotopic.com')

with open(os.environ['INDEX_HTML'], encoding='utf-8') as f:
    index_html = f.read()
with open(os.environ['ABOUT_HTML'], encoding='utf-8') as f:
    about_html = f.read()
with open(os.environ['TOPIC_HTML'], encoding='utf-8') as f:
    topic_html = f.read()
with open(os.environ['APPJS'], encoding='utf-8') as f:
    app_js = f.read()
with open(os.environ['CARD_JSON'], encoding='utf-8') as f:
    card_raw = f.read()

try:
    INDEX_TIME = float(os.environ.get('INDEX_TIME', '0'))
    TOPIC_TIME = float(os.environ.get('TOPIC_TIME', '0'))
except ValueError:
    INDEX_TIME, TOPIC_TIME = 0.0, 0.0
FAV_CODE  = os.environ.get('FAV_CODE',  '000')
MANI_CODE = os.environ.get('MANI_CODE', '000')

# ── ②-A 必須CSS class / マーカー チェック ──────────────────────
# 「モバイル崩れ検知」: 主要class が消えていれば render が壊れている可能性
required_index = [
    'topic-card-wrapper',
    'header-logo-link',
    'search-bar',
    'theme-toggle-btn',
    'pwa-banner-text',
]
required_topic = [
    'topic-hero',
    'topic-hero-inner',
    'topic-hero-title',
    'topic-share-bar',
    'related-articles',
    'story-timeline-sk',
]
required_about_keywords = [
    # content-drift-guard (.github/workflows/ci.yml) の REQUIRED と同じ 3 軸
    '状況解説',
    '各メディアの見解',
    'これからの注目ポイント',
]
required_appjs = [
    '続報あり',
    'card-continuation-badge',
    'velocity-extreme',
    'velocity-rising',
    'velocity-meter',
]


def check_present(text, terms, label):
    missing = [t for t in terms if t not in text]
    return {'label': label, 'required': len(terms), 'missing': missing}


layout_checks = [
    check_present(index_html, required_index,          'index.html CSSクラス'),
    check_present(topic_html, required_topic,          'topic.html CSSクラス'),
    check_present(about_html, required_about_keywords, 'about.html AI 3軸キーワード'),
    check_present(app_js,     required_appjs,          'app.js UI マーカー'),
]

layout_fail = any(c['missing'] for c in layout_checks)

# viewport meta (モバイル基本要件)
has_viewport = bool(re.search(r'name=["\']viewport["\']', index_html))

# ── ②-B トピックカード JSON 集計 ──────────────────────────────
try:
    card = json.loads(card_raw)
except json.JSONDecodeError as e:
    print(f'::error::topics-card.json パース失敗: {e}', file=sys.stderr)
    sys.exit(1)

topics = card.get('topics', []) or []
n_total = len(topics)
n_velocity_pos = sum(1 for t in topics if (t.get('velocityScore') or 0) > 0)
n_ai = sum(1 for t in topics if t.get('aiGenerated'))
n_kp_100 = sum(1 for t in topics if len((t.get('keyPoint') or '').strip()) >= 100)
n_kp_200 = sum(1 for t in topics if len((t.get('keyPoint') or '').strip()) >= 200)
kp_lengths = [len((t.get('keyPoint') or '').strip()) for t in topics if (t.get('keyPoint') or '').strip()]
kp_avg_len = round(statistics.mean(kp_lengths), 1) if kp_lengths else 0.0
n_delta_pos = sum(1 for t in topics if (t.get('articleCountDelta') or 0) > 0)
n_with_image = sum(1 for t in topics if (t.get('imageUrl') or '').startswith('http'))

# 関連トピック密度
child_counts = [len(t.get('childTopics') or []) for t in topics]
child_with_any = sum(1 for c in child_counts if c >= 1)
child_avg = round(statistics.mean(child_counts), 2) if child_counts else 0.0
child_max = max(child_counts) if child_counts else 0
n_with_parent = sum(1 for t in topics if t.get('parentTopicId'))

# ── ②-C ジャンル別集計 ────────────────────────────────────────
by_genre = {}
for t in topics:
    g = t.get('genre') or (t.get('genres') or ['総合'])[0] or '未分類'
    by_genre.setdefault(g, []).append(t)

genre_rows = []
for g, ts in sorted(by_genre.items(), key=lambda kv: -len(kv[1])):
    n = len(ts)
    kp100 = sum(1 for t in ts if len((t.get('keyPoint') or '').strip()) >= 100)
    children = [len(t.get('childTopics') or []) for t in ts]
    delta_pos = sum(1 for t in ts if (t.get('articleCountDelta') or 0) > 0)
    genre_rows.append({
        'genre': g,
        'n': n,
        'kp100_pct': round(kp100 / n * 100, 1) if n else 0.0,
        'child_avg': round(statistics.mean(children), 2) if children else 0.0,
        'delta_pct': round(delta_pos / n * 100, 1) if n else 0.0,
    })

# ── ②-D UX 総合スコア (5点満点) ───────────────────────────────
def norm(v, low, high):
    if high <= low:
        return 0.0
    return max(0.0, min(1.0, (v - low) / (high - low)))


def perf_norm(t_sec):
    # 高速ほど高得点 (0.5s→1.0, 3.0s→0.0)
    if t_sec <= 0:
        return 0.0
    return max(0.0, min(1.0, (3.0 - t_sec) / 2.5))


score_components = {
    # 閾値は 2026-05-01 ベースライン (n_velocity_pos=39 / kp100=36.8% / child_avg=0.13 / delta=7.5%) を踏まえ、
    # 「baseline=0.3-0.4 / 改善目標=0.7-0.8 / 完成=1.0」になるよう設定。
    # ベースラインが沈んで全部 0 では改善が見えないため、現状を 0 にしない範囲で設定する。
    'info_density':   norm(n_velocity_pos, 20, 200),
    'kp_density':     norm((n_kp_100 / n_total) if n_total else 0.0, 0.20, 0.60),
    'child_density':  norm(child_avg, 0.05, 0.60),
    # T2026-0501-C: HTML nav 要素の有無をボーナス (+0.45) として加算
    'continuation':   round(min(1.0, (0.45 if 'topic-continuation-section' in topic_html else 0.0)
                                   + norm((n_delta_pos / n_total) if n_total else 0.0, 0.05, 0.30)), 3),
    'layout_health':  1.0 if (not layout_fail and has_viewport) else 0.5,
    'response_perf':  perf_norm(INDEX_TIME),
}
ux_score = round(sum(score_components.values()) / len(score_components) * 5, 2)

result = {
    'ts': TODAY_TS,
    'base_url': BASE_URL,
    'ux_score': ux_score,
    'response': {
        'index_sec': round(INDEX_TIME, 3),
        'topic_sec': round(TOPIC_TIME, 3),
        'favicon_code':  FAV_CODE,
        'manifest_code': MANI_CODE,
    },
    'layout': {
        'pass': not layout_fail,
        'has_viewport': has_viewport,
        'checks': layout_checks,
    },
    'topics': {
        'total': n_total,
        'velocityPos': n_velocity_pos,
        'aiGenerated': n_ai,
        'kp100': n_kp_100,
        'kp200': n_kp_200,
        'kp_avg_len': kp_avg_len,
        'kp100_pct':       round(n_kp_100    / n_total * 100, 1) if n_total else 0.0,
        'continuation_pct':round(n_delta_pos / n_total * 100, 1) if n_total else 0.0,
        'with_image_pct':  round(n_with_image/ n_total * 100, 1) if n_total else 0.0,
    },
    'related': {
        'child_avg':       child_avg,
        'child_max':       child_max,
        'has_child_pct':   round(child_with_any / n_total * 100, 1) if n_total else 0.0,
        'with_parent_pct': round(n_with_parent  / n_total * 100, 1) if n_total else 0.0,
    },
    'by_genre': genre_rows,
    'score_components': {k: round(v, 3) for k, v in score_components.items()},
}

if JSON_OUT:
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0)

# ── ②-E 人間向け出力 ─────────────────────────────────────────
print('')
print('─────────────────────────────────────────')
print(f'UX 総合スコア: {ux_score} / 5')
print('  内訳:')
for k, v in score_components.items():
    bar = '█' * int(v * 10) + '░' * (10 - int(v * 10))
    print(f'    {k:14s} {v:.2f} {bar}')
print('')
print('  情報密度:')
print(f'    total topics:        {n_total}')
print(f'    velocity>0:          {n_velocity_pos}')
print(f'    aiGenerated:         {n_ai}')
print(f'    keyPoint>=100字:     {n_kp_100} ({result["topics"]["kp100_pct"]}%)')
print(f'    keyPoint>=200字:     {n_kp_200}')
print(f'    keyPoint 平均文字数: {kp_avg_len}')
print('')
print('  関連トピック密度:')
print(f'    childTopics 平均:    {child_avg} (max={child_max})')
print(f'    childが1件以上:      {child_with_any} ({result["related"]["has_child_pct"]}%)')
print(f'    親トピック有り:      {n_with_parent} ({result["related"]["with_parent_pct"]}%)')
print('')
print('  続報・画像:')
print(f'    articleCountDelta>0: {n_delta_pos} ({result["topics"]["continuation_pct"]}%)')
print(f'    imageUrl 有り:       {n_with_image} ({result["topics"]["with_image_pct"]}%)')
print('')
print('  応答性:')
print(f'    /             {INDEX_TIME:.2f}s')
print(f'    /topic.html   {TOPIC_TIME:.2f}s')
print(f'    /favicon.ico  http={FAV_CODE}')
print(f'    /manifest.json http={MANI_CODE}')
print('')
print('  ジャンル別 (上位8):')
print(f'    {"ジャンル":8s} {"n":>4s} {"kp100%":>8s} {"child":>7s} {"続報%":>7s}')
for gr in genre_rows[:8]:
    print(f'    {gr["genre"]:8s} {gr["n"]:>4d} {gr["kp100_pct"]:>7.1f}% {gr["child_avg"]:>7.2f} {gr["delta_pct"]:>6.1f}%')
print('')
print('  レイアウト健全性:')
print(f'    viewport meta:       {"✅" if has_viewport else "❌"}')
for c in layout_checks:
    if c['missing']:
        print(f'    ❌ {c["label"]} 欠落: {", ".join(c["missing"])}')
    else:
        print(f'    ✅ {c["label"]} ({c["required"]}項目)')
print('─────────────────────────────────────────')

EXIT_AT_END = 1 if (layout_fail or not has_viewport) else 0
if EXIT_AT_END != 0:
    print('::error::レイアウト健全性チェック失敗 (CSSクラス/viewport 欠落)', file=sys.stderr)

# ── ②-F docs/ux-scores.md 追記 ───────────────────────────────
if DRY_RUN:
    print(f'(dry-run: {MD_OUT} には書き込まない)')
    sys.exit(EXIT_AT_END)

md_dir = os.path.dirname(MD_OUT)
if md_dir:
    os.makedirs(md_dir, exist_ok=True)

header_block = (
    '# UX 定量評価スコア\n\n'
    '> T2026-0430-UX: ユーザー体験 (情報密度・関連トピック密度・モバイル表示・応答性) を週次で計測する。\n'
    '> 定性評価 (`docs/quality-scores.md`) は AI 出力の品質を見るが、こちらは「画面に何が出ているか」を見る。\n'
    '> 週次 `.github/workflows/ux-check.yml` が自動実行し append する (毎週月曜 07:30 JST)。\n'
    '> ux_score は 5 点満点 (情報密度 / keyPoint 密度 / 関連密度 / 続報率 / レイアウト健全性 / 応答性 を 0-1 正規化平均)。\n\n'
    '## スコア推移 (新しいものが上)\n\n'
    '| 日時 (JST) | total | velocity>0 | kp≥100% | kp平均 | child平均 | 続報% | layout | TTFB(s) | UXスコア |\n'
    '|---|---:|---:|---:|---:|---:|---:|---|---:|---:|\n'
)

existing_rows = []
if os.path.isfile(MD_OUT):
    with open(MD_OUT, encoding='utf-8') as f:
        body = f.read()
    for line in body.splitlines():
        if re.match(r'^\| 20\d{2}-\d{2}-\d{2}', line):
            existing_rows.append(line)

layout_status = 'OK' if not layout_fail else 'WARN'
new_row = (
    f'| {TODAY_TS} | {n_total} | {n_velocity_pos} | '
    f'{result["topics"]["kp100_pct"]} | {kp_avg_len} | '
    f'{child_avg} | {result["topics"]["continuation_pct"]} | '
    f'{layout_status} | {INDEX_TIME:.2f} | {ux_score} |'
)

# 詳細セクション (最新スナップショットのみ)
detail_lines = [
    '\n## 最新スナップショット詳細 ' + TODAY_TS + '\n',
    '### スコア内訳\n',
    '| 項目 | 値 (0-1) | 意味 |',
    '|---|---:|---|',
    f'| info_density   | {score_components["info_density"]:.3f} | velocityScore>0 の topic 数 (20→200 で 0→1) |',
    f'| kp_density     | {score_components["kp_density"]:.3f}   | keyPoint≥100字 比率 (0.20→0.60 で 0→1) |',
    f'| child_density  | {score_components["child_density"]:.3f} | childTopics 平均件数 (0.05→0.60 で 0→1) |',
    f'| continuation   | {score_components["continuation"]:.3f}  | articleCountDelta>0 比率 (0.05→0.30 で 0→1) |',
    f'| layout_health  | {score_components["layout_health"]:.3f} | 必須CSSクラス + viewport (欠落なら 0.5) |',
    f'| response_perf  | {score_components["response_perf"]:.3f} | / の time_total (0.5s→1.0, 3.0s→0.0) |',
    '\n### ジャンル別\n',
    '| ジャンル | n | keyPoint≥100% | child平均 | 続報% |',
    '|---|---:|---:|---:|---:|',
]
for gr in genre_rows:
    detail_lines.append(
        f'| {gr["genre"]} | {gr["n"]} | {gr["kp100_pct"]} | {gr["child_avg"]} | {gr["delta_pct"]} |'
    )
detail_lines += [
    '\n### レイアウト健全性\n',
    '| 対象 | 必須項目数 | 欠落 |',
    '|---|---:|---|',
]
for c in layout_checks:
    miss = ', '.join(c['missing']) if c['missing'] else '(なし)'
    detail_lines.append(f'| {c["label"]} | {c["required"]} | {miss} |')

detail_lines += [
    '',
    '### 応答性',
    '',
    '| 対象 | 値 |',
    '|---|---|',
    f'| /             | {INDEX_TIME:.2f} s |',
    f'| /topic.html   | {TOPIC_TIME:.2f} s |',
    f'| /favicon.ico  | http {FAV_CODE} |',
    f'| /manifest.json | http {MANI_CODE} |',
]

detail_block = '\n'.join(detail_lines) + '\n'

table_rows = [new_row] + existing_rows[:200]
out = header_block + '\n'.join(table_rows) + '\n' + detail_block

with open(MD_OUT, 'w', encoding='utf-8') as f:
    f.write(out)
print(f'wrote {MD_OUT} ({len(table_rows)} 行)')

sys.exit(EXIT_AT_END)
PYEOF
PY_RC=$?

if [ "$PY_RC" -ne 0 ]; then
  echo "::warning::ux_check Python 部 rc=${PY_RC} (レイアウトWARN は MD 追記済)" >&2
  exit "$PY_RC"
fi

if [ "$JSON_OUT" -eq 0 ]; then
  echo "✅ ux_check 完了"
fi
