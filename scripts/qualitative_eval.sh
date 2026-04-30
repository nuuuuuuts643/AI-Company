#!/usr/bin/env bash
# AI 生成物の定性評価スクリプト (T2026-0501-C)
# 実行: bash scripts/qualitative_eval.sh [--n 10] [--base-url https://flotopic.com] [--md docs/quality-scores.md]
#
# 目的: SLI (充填率) では拾えない「面白さ・惹き・独自性」を Claude Haiku に評価させ、
#   改善が機能しているかを数値でトラッキングする。週次で .github/workflows/qualitative-eval.yml
#   から呼ばれ、スコア推移を docs/quality-scores.md に append する。
#
# PO 指示 (2026-05-01):
#   - 本番 topics-card.json からランダム N 件を取得
#   - 各トピックを Claude (Haiku) に title/keyPoint/perspectives 各 1〜5 点で採点
#   - ジャンル別にスコア集計し docs/quality-scores.md に append
#   - 失敗時 (API key 無し / 取得失敗 等) は exit 1 にして CI を赤くする
set -uo pipefail

BASE_URL="https://flotopic.com"
SAMPLE_N=10
MD_OUT="docs/quality-scores.md"
DRY_RUN=0
SEED="${SEED:-}"  # テストや再現性目的で固定可

while [ $# -gt 0 ]; do
  case "$1" in
    --n) SAMPLE_N="$2"; shift 2 ;;
    --base-url) BASE_URL="$2"; shift 2 ;;
    --md) MD_OUT="$2"; shift 2 ;;
    --seed) SEED="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help)
      sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "::error::ANTHROPIC_API_KEY 未設定。env var に Claude API キーをセットして再実行してください。" >&2
  exit 1
fi

API_BASE="${BASE_URL}/api"
CARD_URL="${API_BASE}/topics-card.json"

echo "─────────────────────────────────────────"
echo "AI 定性評価 (T2026-0501-C)"
echo "  base_url:  ${BASE_URL}"
echo "  sample_n:  ${SAMPLE_N}"
echo "  md_out:    ${MD_OUT}"
echo "  seed:      ${SEED:-<random>}"
echo "─────────────────────────────────────────"

# ── ① topics-card.json 取得 ──────────────────────────────────────
CARD_JSON=$(curl -sS --max-time 15 "${CARD_URL}" 2>/dev/null || echo "")
if [ -z "${CARD_JSON}" ]; then
  echo "::error::topics-card.json 取得失敗: ${CARD_URL}" >&2
  exit 1
fi

# ── ② Python 本体: サンプル抽出 → Claude 評価 → 集計 → MD 追記 ──────
ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
SAMPLE_N="${SAMPLE_N}" \
MD_OUT="${MD_OUT}" \
SEED="${SEED}" \
DRY_RUN="${DRY_RUN}" \
CARD_JSON="${CARD_JSON}" \
python3 <<'PYEOF'
import json
import os
import random
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

API_KEY  = os.environ['ANTHROPIC_API_KEY']
SAMPLE_N = int(os.environ.get('SAMPLE_N', '10'))
MD_OUT   = os.environ.get('MD_OUT', 'docs/quality-scores.md')
SEED_RAW = os.environ.get('SEED', '').strip()
DRY_RUN  = os.environ.get('DRY_RUN', '0') == '1'
CARD     = os.environ['CARD_JSON']

JST = timezone(timedelta(hours=9))
NOW = datetime.now(JST)
TODAY = NOW.strftime('%Y-%m-%d')
TODAY_TS = NOW.strftime('%Y-%m-%d %H:%M JST')

if SEED_RAW:
    try:
        random.seed(int(SEED_RAW))
    except ValueError:
        random.seed(SEED_RAW)

try:
    data = json.loads(CARD)
except json.JSONDecodeError as e:
    print(f'::error::topics-card.json パース失敗: {e}', file=sys.stderr)
    sys.exit(1)

topics = data.get('topics', []) or []
ai_topics = [
    t for t in topics
    if t.get('aiGenerated')
    and (t.get('keyPoint') or '').strip()
    and (t.get('generatedTitle') or t.get('title'))
]
if len(ai_topics) < SAMPLE_N:
    print(f'::warning::AI処理済みtopic={len(ai_topics)}件 (sample_n={SAMPLE_N}). 全件評価する')
    sample = ai_topics
else:
    sample = random.sample(ai_topics, SAMPLE_N)

print(f'評価対象: {len(sample)} 件 (全 ai_generated={len(ai_topics)}, 全topic={len(topics)})')


def call_claude_eval(prompt, retries=3):
    """Claude Haiku で JSON 評価レスポンスを取得。tool_use API ではなく content[0].text で受ける。
    リトライは 5xx / 429 / network のみ。4xx は即終了。"""
    payload = {
        'model': 'claude-haiku-4-5-20251001',
        'max_tokens': 400,
        'messages': [{'role': 'user', 'content': prompt}],
    }
    body = json.dumps(payload).encode('utf-8')
    headers = {
        'x-api-key': API_KEY,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json',
    }
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                'https://api.anthropic.com/v1/messages',
                data=body, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=20) as resp:
                resp_data = json.loads(resp.read().decode('utf-8'))
            text = resp_data['content'][0]['text']
            # Claude が ```json ... ``` で包んでくる場合の除去
            m = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
            if m:
                text = m.group(1)
            else:
                m2 = re.search(r'\{[\s\S]*\}', text)
                if m2:
                    text = m2.group(0)
            return json.loads(text)
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (429, 500, 502, 503, 504):
                wait = 2 ** attempt
                print(f'  Claude HTTP {e.code} 待機 {wait}s (attempt {attempt+1}/{retries})')
                time.sleep(wait)
                continue
            print(f'  Claude HTTP {e.code} 即終了: {e}')
            return None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last_err = e
            wait = 2 ** attempt
            print(f'  Claude error {type(e).__name__}: {e} 待機 {wait}s')
            time.sleep(wait)
    print(f'  Claude exhausted: {last_err}')
    return None


def build_prompt(t: dict) -> str:
    title    = (t.get('generatedTitle') or t.get('title') or '').strip()
    keypoint = (t.get('keyPoint') or '').strip()[:600]
    persps   = t.get('perspectives') or []
    persps_text = '\n'.join(f'- {p.get("name","")}: {p.get("comment","")[:200]}' for p in persps[:5]) or '(なし)'
    genre = t.get('genre') or (t.get('genres') or ['総合'])[0]

    return (
        '以下のAIニュース要約の品質を評価してください。\n'
        '評価軸 (各1〜5点、必ず整数):\n'
        '  - title_score:       タイトルの惹き (1=平坦な要約, 3=普通, 5=思わず読みたくなる見出し)\n'
        '  - keypoint_score:    keyPoint の深さ (1=表面的な事実, 3=要約レベル, 5=なぜ重要かが伝わる)\n'
        '  - perspectives_score: perspectives の独自性 (1=同じ事の繰り返し, 3=部分的に違う, 5=各社視点が明確に異なる)\n\n'
        '回答は JSON のみ。マークダウンや前置きは不要。\n'
        '形式:\n'
        '{\n'
        '  "title_score": <int>,\n'
        '  "keypoint_score": <int>,\n'
        '  "perspectives_score": <int>,\n'
        '  "title_comment": "<タイトルへの一言、30字以内>",\n'
        '  "overall_comment": "<全体への一言、50字以内>"\n'
        '}\n\n'
        f'【ジャンル】: {genre}\n'
        f'【タイトル】: {title}\n\n'
        f'【keyPoint】:\n{keypoint}\n\n'
        f'【perspectives】:\n{persps_text}\n'
    )


# ── 評価実行 ───────────────────────────────────────────────────
results = []
for i, t in enumerate(sample, 1):
    tid = (t.get('id') or t.get('tid') or '')[:8]
    title = (t.get('generatedTitle') or t.get('title') or '')[:30]
    genre = t.get('genre') or (t.get('genres') or ['総合'])[0]
    print(f'[{i}/{len(sample)}] {tid} ({genre}) {title}...')
    if DRY_RUN:
        results.append({
            'tid': tid, 'genre': genre, 'title': title,
            'title_score': 0, 'keypoint_score': 0, 'perspectives_score': 0,
            'title_comment': '(dry-run)', 'overall_comment': '(dry-run)',
        })
        continue
    prompt = build_prompt(t)
    parsed = call_claude_eval(prompt)
    if not parsed:
        print(f'  → 評価失敗 (skip)')
        continue
    try:
        results.append({
            'tid':   tid,
            'genre': genre,
            'title': title,
            'title_score':       int(parsed.get('title_score', 0)),
            'keypoint_score':    int(parsed.get('keypoint_score', 0)),
            'perspectives_score': int(parsed.get('perspectives_score', 0)),
            'title_comment':     str(parsed.get('title_comment', ''))[:60],
            'overall_comment':   str(parsed.get('overall_comment', ''))[:80],
        })
        print(f'  → t={parsed.get("title_score")} kp={parsed.get("keypoint_score")} p={parsed.get("perspectives_score")}')
    except (TypeError, ValueError) as e:
        print(f'  → スキーマ違反: {e}')
    time.sleep(0.5)  # API rate limit 緩和

if not results:
    print('::error::有効な評価が0件。API/データを確認してください。', file=sys.stderr)
    sys.exit(1)

# ── 集計 ───────────────────────────────────────────────────────
def avg(xs):
    xs = [x for x in xs if isinstance(x, (int, float)) and x > 0]
    return round(sum(xs) / len(xs), 2) if xs else 0.0

t_avg  = avg(r['title_score']        for r in results)
kp_avg = avg(r['keypoint_score']     for r in results)
p_avg  = avg(r['perspectives_score'] for r in results)
overall = round((t_avg + kp_avg + p_avg) / 3, 2)

# ジャンル別集計 (PO 指示 2026-05-01: ジャンル列を追加)
by_genre = {}
for r in results:
    g = r['genre']
    by_genre.setdefault(g, []).append(r)
genre_rows = []
for g, rs in sorted(by_genre.items(), key=lambda kv: -len(kv[1])):
    genre_rows.append({
        'genre':  g,
        'n':      len(rs),
        't_avg':  avg(r['title_score']        for r in rs),
        'kp_avg': avg(r['keypoint_score']     for r in rs),
        'p_avg':  avg(r['perspectives_score'] for r in rs),
    })

print('')
print('─────────────────────────────────────────')
print(f'総合スコア: {overall} / 5  (n={len(results)})')
print(f'  title:        {t_avg}')
print(f'  keypoint:     {kp_avg}')
print(f'  perspectives: {p_avg}')
print('  ジャンル別:')
for gr in genre_rows:
    print(f'    {gr["genre"]:8s} n={gr["n"]:2d}  t={gr["t_avg"]:.2f} kp={gr["kp_avg"]:.2f} p={gr["p_avg"]:.2f}')
print('─────────────────────────────────────────')

# ── MD 追記 ────────────────────────────────────────────────────
if DRY_RUN:
    print(f'(dry-run: {MD_OUT} には書き込まない)')
    sys.exit(0)

md_dir = os.path.dirname(MD_OUT)
if md_dir:
    os.makedirs(md_dir, exist_ok=True)

header_block = (
    '# AI 品質スコア (定性評価)\n\n'
    '> T2026-0501-C: SLI(充填率) では拾えない「惹き・深さ・独自性」を Claude Haiku に評価させた結果。\n'
    '> 週次 .github/workflows/qualitative-eval.yml が自動実行し append する。\n'
    '> 各スコアは 1〜5 点 (5 が最良)。低下傾向はプロンプト/データ品質の劣化シグナル。\n\n'
    '## スコア推移 (新しいものが上)\n\n'
    '| 日時 (JST) | n | title | keyPoint | perspectives | 総合 | ジャンル別 (上位3) |\n'
    '|---|---:|---:|---:|---:|---:|---|\n'
)

# 既存ファイルを読み、ヘッダー以下の表を保持しつつ先頭に新行を入れる
existing_rows = []
if os.path.isfile(MD_OUT):
    with open(MD_OUT, encoding='utf-8') as f:
        body = f.read()
    # 既存の表行 (パイプ + 日付プレフィックス) を抽出
    for line in body.splitlines():
        if re.match(r'^\| 20\d{2}-\d{2}-\d{2}', line):
            existing_rows.append(line)

genre_summary = ' / '.join(
    f"{gr['genre']}({gr['n']}: t{gr['t_avg']:.1f}/kp{gr['kp_avg']:.1f}/p{gr['p_avg']:.1f})"
    for gr in genre_rows[:3]
)

new_row = (
    f'| {TODAY_TS} | {len(results)} | {t_avg} | {kp_avg} | {p_avg} | {overall} | {genre_summary} |'
)

# ── 詳細セクション (最新スナップショットのみ。古い詳細は履歴の表で代替) ──
detail_block_lines = [
    '\n## 最新スナップショット詳細 ' + TODAY_TS + '\n',
    '### ジャンル別\n',
    '| ジャンル | n | title | keyPoint | perspectives |',
    '|---|---:|---:|---:|---:|',
]
for gr in genre_rows:
    detail_block_lines.append(
        f"| {gr['genre']} | {gr['n']} | {gr['t_avg']} | {gr['kp_avg']} | {gr['p_avg']} |"
    )
detail_block_lines += [
    '\n### サンプル別 (上位コメント抜粋)\n',
    '| tid | ジャンル | title | t | kp | p | コメント |',
    '|---|---|---|---:|---:|---:|---|',
]
for r in results[:20]:
    safe_title   = r['title'].replace('|', '/')
    safe_comment = (r['overall_comment'] or r['title_comment']).replace('|', '/')
    detail_block_lines.append(
        f"| {r['tid']} | {r['genre']} | {safe_title} | {r['title_score']} | "
        f"{r['keypoint_score']} | {r['perspectives_score']} | {safe_comment} |"
    )
detail_block = '\n'.join(detail_block_lines) + '\n'

# 表は新行を先頭に積み、既存行は最大 200 行残す
table_rows = [new_row] + existing_rows[:200]
out = header_block + '\n'.join(table_rows) + '\n' + detail_block

with open(MD_OUT, 'w', encoding='utf-8') as f:
    f.write(out)
print(f'wrote {MD_OUT} ({len(table_rows)} 行)')
PYEOF
PY_RC=$?

if [ "$PY_RC" -ne 0 ]; then
  echo "::error::qualitative_eval Python 部失敗 rc=${PY_RC}" >&2
  exit "$PY_RC"
fi

echo "✅ qualitative_eval 完了"
