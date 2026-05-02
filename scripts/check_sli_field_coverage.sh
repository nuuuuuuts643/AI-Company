#!/bin/bash
# T2026-0429-M: SLI フィールド ↔ 実装スキーマ 乖離検出 (物理ガード)
#
# 目的:
#   freshness-check.yml が `t.get('FIELD')` で測定しているフィールド名と、
#   実装側 (proc_ai.py の Tool Use schema + handler.py の ai_updates dict)
#   が実際に topics.json に書き込むフィールド名を突合する。
#   過去事例: SLI 10「background 充填率」が proc_ai 側のフィールド削除に
#   気付かないまま 0% を測り続けた (situation 0% 問題と同型)。
#
# 出力:
#   全部一致 → exit 0
#   1 件以上の乖離 → exit 1 (CI 赤)
#
# 使い方:
#   bash scripts/check_sli_field_coverage.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRESHNESS_YML="$REPO_ROOT/.github/workflows/freshness-check.yml"
PROC_AI_PY="$REPO_ROOT/projects/P003-news-timeline/lambda/processor/proc_ai.py"
HANDLER_PY="$REPO_ROOT/projects/P003-news-timeline/lambda/processor/handler.py"

for f in "$FRESHNESS_YML" "$PROC_AI_PY" "$HANDLER_PY"; do
  if [ ! -f "$f" ]; then
    echo "ERROR: 必要なファイルが見つかりません: $f" >&2
    exit 1
  fi
done

python3 - "$FRESHNESS_YML" "$PROC_AI_PY" "$HANDLER_PY" <<'PY'
import re
import sys

freshness_path, proc_ai_path, handler_path = sys.argv[1], sys.argv[2], sys.argv[3]


def read(p):
    with open(p, encoding='utf-8') as f:
        return f.read()


# ────────────────────────────────────────────────────────────────────
# 1) freshness-check.yml が「topic 単位で参照する」フィールド名を抽出
#    パターン: t.get('FOO')   — for ループ内で各 topic に触っている全箇所
# ────────────────────────────────────────────────────────────────────
freshness_src = read(freshness_path)
# T2026-0502-AQ-FOLLOWUP: 単語境界 \b を追加し `latest.get(...)` `prev.get(...)` 等の
# 末尾 3 文字 `est.get(...)` `rev.get(...)` への誤マッチを防止。
# `t.get('FOO')` は topic 単位の参照のみを対象とする。
measured = set(re.findall(r"\bt\.get\('([a-zA-Z][a-zA-Z0-9_]*)'", freshness_src))

# トップレベル d.get('updatedAt') 等は topic 単位ではないので除外。
# 'topics' は配列キーなので除外。
measured.discard('topics')

# ────────────────────────────────────────────────────────────────────
# 2) proc_ai.py の story schema に出てくるフィールド (Tool Use の input 名)
#    パターン: base_props['FOO'] = {...}   と   'FOO': {'type': ...}
#    (関数 _build_story_schema 内に集約されている)
# ────────────────────────────────────────────────────────────────────
proc_ai_src = read(proc_ai_path)
schema_fields = set()
# base_props['FOO']
schema_fields.update(re.findall(r"base_props\['([a-zA-Z][a-zA-Z0-9_]*)'\]", proc_ai_src))
# dict 直書き: 'FOO': {'type': 'string'  /  'FOO': {'type': ['string', 'null']
schema_fields.update(re.findall(r"'([a-zA-Z][a-zA-Z0-9_]*)':\s*\{\s*'type':", proc_ai_src))

# ────────────────────────────────────────────────────────────────────
# 3) handler.py の ai_updates dict — proc_ai 出力を topics.json フィールド名に
#    リネームしている層。ここの LHS が「最終的に topics.json に乗る AI フィールド」。
# ────────────────────────────────────────────────────────────────────
handler_src = read(handler_path)
m = re.search(r"ai_updates\[tid\]\s*=\s*\{(.+?)\n\s*\}\n", handler_src, re.DOTALL)
ai_updates_keys = set()
if m:
    block = m.group(1)
    ai_updates_keys = set(re.findall(r"'([a-zA-Z][a-zA-Z0-9_]*)'\s*:", block))
else:
    print("ERROR: handler.py で ai_updates[tid] = {...} ブロックが見つからない (regex 要更新)", file=sys.stderr)
    sys.exit(1)

# ────────────────────────────────────────────────────────────────────
# 4) topic builder / proc_storage.py が topics.json に直接乗せる非 AI フィールド
#    (AI 出力経由ではないため、proc_ai schema にも ai_updates にも出てこない)
#    ここに載るフィールドは freshness-check が測ってもよい。
#    過剰許容を防ぐため、最小限の allowlist のみ。
# ────────────────────────────────────────────────────────────────────
BUILDER_FIELDS = {
    'articleCount',     # トピック内記事数 (proc_storage / topic builder)
    'lifecycleStatus',  # active / archived / legacy
    'lastUpdated',      # 最終記事追加時刻
    'lastArticleAt',    # 最新記事 published_ts (epoch sec) — fetcher/handler.py で META に書く非 AI フィールド
    'updatedAt',        # topic 単位の更新時刻 (トップレベルにもある)
    'score',
    'velocityScore',
    'pendingAI',
    'aiGeneratedAt',
}

# ────────────────────────────────────────────────────────────────────
# 5) 突合
# ────────────────────────────────────────────────────────────────────
produced = schema_fields | ai_updates_keys | BUILDER_FIELDS
divergent = sorted(measured - produced)

print('=== SLI フィールド ↔ 実装スキーマ 突合 ===')
print(f'freshness-check.yml で測定: {sorted(measured)}')
print(f'proc_ai schema フィールド数: {len(schema_fields)}')
print(f'handler.py ai_updates キー数: {len(ai_updates_keys)}')
print(f'builder allowlist: {sorted(BUILDER_FIELDS)}')
print()

if divergent:
    print(f'ERROR: SLI field mismatch — {len(divergent)} 件')
    for f in divergent:
        print(f'  - {f!r} は freshness-check.yml で測定されているが、')
        print(f"    proc_ai.py schema にも handler.py の ai_updates にも")
        print(f'    builder allowlist にも存在しない (測定値が常に 0% になる恐れ)')
    print()
    print('対処: 以下のいずれか')
    print('  (a) 実装側に該当フィールドを復元する (proc_ai schema or ai_updates に追加)')
    print('  (b) freshness-check.yml の SLI から該当 t.get(...) を削除する')
    print('  (c) builder 経由で出るフィールドなら本スクリプトの BUILDER_FIELDS に追加する')
    sys.exit(1)

print('OK: all SLI fields present in schema or builder output')
sys.exit(0)
PY
