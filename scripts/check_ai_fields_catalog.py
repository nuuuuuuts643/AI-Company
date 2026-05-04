#!/usr/bin/env python3
"""T2026-0428-T: AI フィールドカタログと proc_ai.py schema を CI で突合する。

目的:
    proc_ai.py の `_build_story_schema(mode='full')` で宣言されている field 名と、
    docs/ai-fields-catalog.md 先頭フィールド表に列挙された field 名を突合する。
    乖離があれば exit 1 で CI を落とす。

背景:
    新フィールド追加時に「proc_ai.py に追加したがカタログ更新を忘れた」or
    「カタログには書いたが schema 反映漏れ」のドキュメント-実装乖離が発生していた
    (T255 keyPoint / backgroundContext merge 漏れの再発防止)。物理ゲートで防ぐ。

使い方:
    python3 scripts/check_ai_fields_catalog.py
    終了コード: 0 = OK, 1 = 乖離あり

CI 連携:
    .github/workflows/ci.yml の lint-lambda ジョブに追加 (main push 時)。
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROC_AI_DIR = REPO_ROOT / 'projects' / 'P003-news-timeline' / 'lambda' / 'processor'
CATALOG_PATH = REPO_ROOT / 'docs' / 'ai-fields-catalog.md'

# computed フィールド (schema には載らないが ai_updates / topics.json に載る) は乖離扱いから除外する。
# proc_ai が AI 出力を内部 dict に正規化する際に追加するフィールドを許容する。
ALLOW_CATALOG_EXTRA = {
    'summaryMode',  # _normalize_story_result 内で computed
}


def extract_schema_fields() -> set[str]:
    """proc_ai.py の _build_story_schema(mode='full') を import して field 名一覧を抽出。"""
    sys.path.insert(0, str(PROC_AI_DIR))
    # proc_config が boto3 など本番依存を持つ可能性があるため、import 副作用を最小化するため
    # ANTHROPIC_API_KEY / 環境を mock する余地を残しつつ、まずは素直に import を試みる。
    os.environ.setdefault('ANTHROPIC_API_KEY', 'dummy')
    os.environ.setdefault('AWS_REGION', 'ap-northeast-1')
    try:
        import proc_ai  # type: ignore
    except Exception as e:
        print(f'[check_ai_fields_catalog] proc_ai import 失敗: {e}', file=sys.stderr)
        # CI 環境で boto3 等が無い可能性を考慮し、import 失敗時は ast でフォールバック解析する。
        return _extract_via_ast()
    schema = proc_ai._build_story_schema(mode='full')
    return set((schema.get('properties') or {}).keys())


def _extract_via_ast() -> set[str]:
    """import 失敗時のフォールバック: proc_formatter.py をテキストとして読み、_build_story_schema 内の
    base_props に代入されている top-level key のみを拾う。
    T2026-0504-A で _build_story_schema は proc_ai.py → proc_formatter.py に移動。
    timeline.items.properties (date / event / transition 等) のような nested キーは除外する。
    """
    src = (PROC_AI_DIR / 'proc_formatter.py').read_text(encoding='utf-8')
    # _build_story_schema 関数の body を抽出 (次の def まで)。
    m = re.search(r'def _build_story_schema\([^)]*\)[^:]*:\s*\n(.+?)(?=\n(?:def |class )\w)', src, re.DOTALL)
    if not m:
        print('[check_ai_fields_catalog] _build_story_schema が見つかりません', file=sys.stderr)
        sys.exit(1)
    body = m.group(1)
    keys: set[str] = set()
    # 1) base_props['key'] = ... 形式 (top-level 確定)
    keys |= set(re.findall(r"base_props\[\s*'([^']+)'\s*\]\s*=", body))
    # 2) base_props = { 'key': ... } 形式の dict literal を ast で解析。
    init_match = re.search(r'base_props\s*=\s*\{', body)
    if init_match:
        # 対応する閉じ波括弧まで切り出して ast.literal_eval-like に処理する。
        # 安全のため depth count で対応。
        start = init_match.end() - 1  # '{' position
        depth = 0
        end = None
        for i, ch in enumerate(body[start:], start=start):
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end is not None:
            literal = body[start:end + 1]
            # トップレベル key だけ抽出: 1 段ネストの '...': を拾うため、
            # 単純に最初の階層 '\n    \'KEY\': {' パターンを使う。
            # base_props = { 内部はインデント 8 (スペース 8) または 12 を想定。
            for m2 in re.finditer(r"^\s{8}'([A-Za-z_][\w]*)'\s*:\s*", literal, re.MULTILINE):
                keys.add(m2.group(1))
    # 候補から型/構造キーワードを除外 (念のため)。
    keys -= {'type', 'description', 'enum', 'items', 'properties', 'required',
             'minItems', 'maxItems', 'object', 'string', 'array', 'boolean'}
    return keys


def extract_catalog_fields() -> set[str]:
    """docs/ai-fields-catalog.md 先頭フィールド表から `field` 列を抽出。

    形式: `| \`fieldName\` | ... | ... |` を想定する。
    'フィールド一覧' セクションの最初の表のみを対象とする。
    """
    text = CATALOG_PATH.read_text(encoding='utf-8')
    # フィールド一覧セクションの開始を探す。
    section_match = re.search(r'## フィールド一覧[^\n]*\n', text)
    if not section_match:
        print('[check_ai_fields_catalog] docs/ai-fields-catalog.md に「フィールド一覧」セクションが見つかりません', file=sys.stderr)
        sys.exit(1)
    after = text[section_match.end():]
    # 次の ## 見出しまでで打ち切る。
    end_match = re.search(r'\n##\s', after)
    section_body = after if not end_match else after[:end_match.start()]
    fields: set[str] = set()
    # `| \`name\` | ...` 形式をマッチ。ヘッダ行 (| field |) は backtick で囲まれていないので除外される。
    for m in re.finditer(r'^\|\s*`([A-Za-z_][\w]*)`\s*\|', section_body, re.MULTILINE):
        fields.add(m.group(1))
    return fields


def main() -> int:
    schema = extract_schema_fields()
    catalog = extract_catalog_fields()
    if not schema:
        print('[check_ai_fields_catalog] schema field を 1 件も抽出できませんでした', file=sys.stderr)
        return 1
    if not catalog:
        print('[check_ai_fields_catalog] catalog field を 1 件も抽出できませんでした', file=sys.stderr)
        return 1

    missing_in_catalog = schema - catalog
    extra_in_catalog = (catalog - schema) - ALLOW_CATALOG_EXTRA

    print(f'[check_ai_fields_catalog] schema fields ({len(schema)}): {sorted(schema)}')
    print(f'[check_ai_fields_catalog] catalog fields ({len(catalog)}): {sorted(catalog)}')

    errors = 0
    if missing_in_catalog:
        print('::error::proc_ai.py schema にあるが docs/ai-fields-catalog.md フィールド表に無い:', file=sys.stderr)
        for f in sorted(missing_in_catalog):
            print(f'  - {f}', file=sys.stderr)
        errors += 1
    if extra_in_catalog:
        print('::error::docs/ai-fields-catalog.md フィールド表にあるが proc_ai.py schema に無い:', file=sys.stderr)
        for f in sorted(extra_in_catalog):
            print(f'  - {f}', file=sys.stderr)
        errors += 1

    if errors:
        print('[check_ai_fields_catalog] 乖離あり: docs/ai-fields-catalog.md の先頭表を最新の schema に揃えてください', file=sys.stderr)
        return 1
    print('[check_ai_fields_catalog] OK: schema とカタログが一致 (computed 例外あり)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
