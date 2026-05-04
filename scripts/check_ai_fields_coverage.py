#!/usr/bin/env python3
"""T256: AI フィールドの「層を1つ忘れる」を CI で物理検出する。

背景:
    T249 (2026-04-28) で proc_ai.py が生成した keyPoint / backgroundContext が
    handler.py のマージループに含まれておらず DDB に書き込まれない事故。
    手動調査でようやく発見したが、CI で物理検出すれば即落ちていた。

    ai_succeeded ガード以外にも、proc_ai が emit したフィールドが
    handler.ai_updates dict と proc_storage.update_topic_with_ai の双方で
    参照されているか「物理ガード」する仕組みが必要。

仕組み:
    1) proc_ai.py の `_normalize_story_result` を AST で読み、
       return される dict literal のキー一覧 (= gen_story の出力フィールド) を集める。
       minimal / standard / full の return 双方を union する。
    2) 各キーが
        - proc_storage.py の `gen_story.get('K')` or `gen_story['K']` で参照されているか
        - handler.py の `gen_story.get('K')` or `gen_story['K']` で参照されているか
       を grep で確認する。
    3) STORAGE_ONLY 許容リスト (keyPointLength / keyPointRetried / keyPointFallback など、
       観測メタデータで S3 topic file に流さないもの) は handler 側欠落を許容する。
    4) 欠落があれば ERROR + exit 1。

使い方:
    python3 scripts/check_ai_fields_coverage.py
    終了コード: 0 = OK, 1 = 欠落あり

CI 連携:
    .github/workflows/ci.yml の lint-lambda ジョブに追加。
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROC_DIR = REPO_ROOT / 'projects' / 'P003-news-timeline' / 'lambda' / 'processor'
PROC_STORAGE = PROC_DIR / 'proc_storage.py'
HANDLER = PROC_DIR / 'handler.py'


def _find_normalize_source_path(proc_dir: Path) -> Path:
    """_normalize_story_result の定義ファイルを探す。
    T2026-0504-A で proc_ai.py → proc_formatter.py に移動したため両方を確認する。
    """
    for name in ('proc_formatter.py', 'proc_ai.py'):
        p = proc_dir / name
        if p.exists() and '_normalize_story_result' in p.read_text(encoding='utf-8'):
            return p
    return proc_dir / 'proc_ai.py'


PROC_AI = _find_normalize_source_path(PROC_DIR)

# proc_storage 経由で DDB に書くが、S3 topic file (handler.ai_updates) には流さない
# ストレージ専用メタデータ。観測・分析用で UI に出さないため handler 欠落を許容。
STORAGE_ONLY = {
    'keyPointLength',
    'keyPointRetried',
    'keyPointFallback',
}


def extract_normalize_output_keys(path: Path) -> set[str]:
    """`_normalize_story_result` 内の Return Dict literal から key を集める。"""
    tree = ast.parse(path.read_text(encoding='utf-8'))
    target_fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == '_normalize_story_result':
            target_fn = node
            break
    if target_fn is None:
        print(f'ERROR: _normalize_story_result not found in {path}', file=sys.stderr)
        sys.exit(1)

    keys: set[str] = set()
    for sub in ast.walk(target_fn):
        if isinstance(sub, ast.Return) and isinstance(sub.value, ast.Dict):
            for k in sub.value.keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    keys.add(k.value)
        # `out = { ... }` のような中間 dict も拾う (return out 経由で出力されるため)。
        if isinstance(sub, ast.Assign) and isinstance(sub.value, ast.Dict):
            for tgt in sub.targets:
                if isinstance(tgt, ast.Name) and tgt.id in ('out', 'result'):
                    for k in sub.value.keys:
                        if isinstance(k, ast.Constant) and isinstance(k.value, str):
                            keys.add(k.value)
    return keys


def _is_referenced(src: str, key: str) -> bool:
    """src に `gen_story.get('key')` or `gen_story['key']` (シングル/ダブルクォート) があれば True。"""
    pat = (
        r"gen_story\.get\(\s*['\"]" + re.escape(key) + r"['\"]"
        r"|gen_story\[\s*['\"]" + re.escape(key) + r"['\"]\s*\]"
    )
    return re.search(pat, src) is not None


def check(proc_ai_path: Path = PROC_AI,
          proc_storage_path: Path = PROC_STORAGE,
          handler_path: Path = HANDLER) -> tuple[set[str], list[str], list[str]]:
    """テスト容易性のため抽出。 (output_keys, storage_missing, handler_missing) を返す。"""
    output_keys = extract_normalize_output_keys(proc_ai_path)
    storage_src = proc_storage_path.read_text(encoding='utf-8')
    handler_src = handler_path.read_text(encoding='utf-8')

    storage_missing: list[str] = []
    handler_missing: list[str] = []
    for k in sorted(output_keys):
        if not _is_referenced(storage_src, k):
            storage_missing.append(k)
        if k in STORAGE_ONLY:
            continue
        if not _is_referenced(handler_src, k):
            handler_missing.append(k)
    return output_keys, storage_missing, handler_missing


def main() -> int:
    output_keys, storage_missing, handler_missing = check()
    if not output_keys:
        print('ERROR: _normalize_story_result から出力キーを抽出できませんでした', file=sys.stderr)
        return 1

    if not storage_missing and not handler_missing:
        print(f'OK: proc_ai が emit する {len(output_keys)} フィールド全てが '
              f'proc_storage.py と handler.py の双方でマージされています。')
        return 0

    print('=== AI フィールド層抜け検出 ===', file=sys.stderr)
    print(f'対象キー ({len(output_keys)}): {sorted(output_keys)}', file=sys.stderr)
    if storage_missing:
        print(f'\n[ERROR] proc_storage.py で参照されていない proc_ai 出力フィールド:', file=sys.stderr)
        for k in storage_missing:
            print(f'  - {k!r}: `gen_story.get({k!r})` か `gen_story[{k!r}]` を update_topic_with_ai に追加してください',
                  file=sys.stderr)
    if handler_missing:
        print(f'\n[ERROR] handler.py の ai_updates dict で参照されていない proc_ai 出力フィールド:', file=sys.stderr)
        for k in handler_missing:
            allow_hint = '' if k not in STORAGE_ONLY else ' (STORAGE_ONLY allowlist 候補)'
            print(f'  - {k!r}: `gen_story.get({k!r})` を ai_updates に追加してください{allow_hint}',
                  file=sys.stderr)
    print('\n参考: T249 (2026-04-28) keyPoint / backgroundContext merge 漏れ事故の再発防止ガード',
          file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
