#!/usr/bin/env python3
"""DDB-bound dict literal の float 値が Decimal でラップされているか物理検査。

T2026-0430-D: 2026-04-27 commit 59eaf649 で fetcher/handler.py:584 の
`'diversityScore': _div_mult` が Decimal でラップ漏れし、本番で
"Float types are not supported" エラーで chunk 3/4 失敗 → 新規記事 159件保存失敗 →
topics 88% 72h+ 停滞、という事故を物理的に再発防止する。

ルール:
  - 任意の Dict literal で value のいずれかが `Decimal(...)` でラップされている場合、
    その dict は DDB 行き と判定する (= "DDB-bound dict")。
  - DDB-bound dict 内の各 value について以下を強制:
      * Constant float  → ERROR (literal float)
      * Name で関数スコープ内で float 産出と確定する代入を持つもの → ERROR (bare float var)
      * Call で float-returning 関数 (FLOAT_FUNCS) を直接呼ぶもの → ERROR (unwrapped call)
      * BinOp Div で両辺が constant の場合 → ERROR (float-producing arithmetic)
  - `Decimal(str(...))` / `Decimal(...)` / `int(...)` / `str(...)` / `bool(...)` で
    明示的にラップされていれば pass。
  - Dict / List / Set / Tuple / Comprehension は再帰スキャン。
  - Constant int / str / bool / None / bytes は pass。

対象は lambda 配下の Python のみ。tests / scripts は対象外 (DDB 書き込みしないため)。

Exit:
  - 違反ゼロ → 0
  - 違反あり → 1 (CI で fail)
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

TARGETS = [
    'projects/P003-news-timeline/lambda/fetcher/handler.py',
    'projects/P003-news-timeline/lambda/fetcher/storage.py',
    'projects/P003-news-timeline/lambda/processor/handler.py',
    'projects/P003-news-timeline/lambda/processor/proc_storage.py',
    'projects/P003-news-timeline/lambda/processor/proc_ai.py',
]

FLOAT_FUNCS = {
    'source_diversity_score',
    'calc_velocity',
    'calc_velocity_score',
    'apply_velocity_decay',
    'apply_time_decay',
    'apply_tier_and_diversity_scoring',
    'float',
}

SAFE_WRAP_FUNCS = {'Decimal', 'int', 'str', 'bool', 'len'}


def _is_safe_wrap(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in SAFE_WRAP_FUNCS
    )


def _classify_rhs(rhs: ast.AST) -> str:
    """RHS の型を 'float' / 'safe' / 'unknown' に分類."""
    if isinstance(rhs, ast.Constant):
        if isinstance(rhs.value, float):
            return 'float'
        if isinstance(rhs.value, (int, bool)):
            return 'safe'
        return 'safe'
    if isinstance(rhs, ast.Call):
        if isinstance(rhs.func, ast.Name):
            if rhs.func.id in FLOAT_FUNCS:
                return 'float'
            if rhs.func.id in SAFE_WRAP_FUNCS:
                return 'safe'
        return 'unknown'
    if isinstance(rhs, ast.BinOp):
        if isinstance(rhs.op, ast.Div):
            return 'float'
        return 'unknown'
    return 'unknown'


def _collect_name_classifications(
    funcdef: ast.AST,
) -> dict[str, list[tuple[int, str]]]:
    """funcdef 内の Name 代入を [(lineno, classification)] 形式で集める."""
    by_name: dict[str, list[tuple[int, str]]] = {}
    for node in ast.walk(funcdef):
        if not isinstance(node, ast.Assign):
            continue
        cls = _classify_rhs(node.value)
        for target in node.targets:
            if isinstance(target, ast.Name):
                by_name.setdefault(target.id, []).append((node.lineno, cls))
    for name in by_name:
        by_name[name].sort()
    return by_name


def _is_float_at(name: str, lineno: int, table: dict[str, list[tuple[int, str]]]) -> bool:
    """lineno 直前で name が float であると確定するか判定 (再代入を考慮)."""
    history = table.get(name)
    if not history:
        return False
    last_cls = None
    for ln, cls in history:
        if ln >= lineno:
            break
        last_cls = cls
    return last_cls == 'float'


def _check_dict(
    dnode: ast.Dict,
    name_table: dict[str, list[tuple[int, str]]],
    path: Path,
) -> list[tuple[int, str, str]]:
    has_decimal = any(
        isinstance(v, ast.Call)
        and isinstance(v.func, ast.Name)
        and v.func.id == 'Decimal'
        for v in dnode.values
    )
    if not has_decimal:
        return []
    errors: list[tuple[int, str, str]] = []
    for key_node, val_node in zip(dnode.keys, dnode.values):
        key = (
            key_node.value
            if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str)
            else '?'
        )
        if _is_safe_wrap(val_node):
            continue
        if isinstance(val_node, ast.Constant):
            if isinstance(val_node.value, float):
                errors.append((val_node.lineno, key, 'literal float'))
            continue
        if isinstance(val_node, (ast.Dict, ast.List, ast.Set, ast.Tuple)):
            continue
        if isinstance(
            val_node,
            (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp),
        ):
            continue
        if isinstance(val_node, ast.Name):
            if _is_float_at(val_node.id, val_node.lineno, name_table):
                errors.append(
                    (val_node.lineno, key, f'bare float var "{val_node.id}"')
                )
            continue
        if isinstance(val_node, ast.Call) and isinstance(val_node.func, ast.Name):
            if val_node.func.id in FLOAT_FUNCS:
                errors.append(
                    (
                        val_node.lineno,
                        key,
                        f'unwrapped {val_node.func.id}() call',
                    )
                )
            continue
        if isinstance(val_node, ast.BinOp) and isinstance(val_node.op, ast.Div):
            errors.append((val_node.lineno, key, 'unwrapped Div BinOp'))
            continue
    return errors


def check_file(path: Path) -> list[tuple[Path, int, str, str]]:
    src = path.read_text()
    tree = ast.parse(src, filename=str(path))
    errors: list[tuple[Path, int, str, str]] = []
    for funcdef in ast.walk(tree):
        if not isinstance(funcdef, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        name_table = _collect_name_classifications(funcdef)
        for inner in ast.walk(funcdef):
            if isinstance(inner, ast.Dict):
                for lineno, key, reason in _check_dict(inner, name_table, path):
                    errors.append((path, lineno, key, reason))
    return errors


def main(argv: list[str]) -> int:
    repo = Path(__file__).resolve().parent.parent
    targets = argv[1:] if len(argv) > 1 else TARGETS
    all_errors: list[tuple[Path, int, str, str]] = []
    checked = 0
    for target in targets:
        path = (repo / target) if not Path(target).is_absolute() else Path(target)
        if not path.exists():
            print(f'  skip (missing): {target}')
            continue
        checked += 1
        all_errors.extend(check_file(path))
    if all_errors:
        for path, lineno, key, reason in all_errors:
            rel = path.relative_to(repo) if path.is_absolute() else path
            print(
                f'::error file={rel},line={lineno}::DDB-bound dict field "{key}" '
                f'is {reason}. Wrap with Decimal(str(...)) — '
                f'see docs/lessons-learned.md (T2026-0430-D)'
            )
        print(f'\n[FAIL] {len(all_errors)} float→DDB violations across {checked} files')
        return 1
    print(f'[OK] DDB Decimal wrap check passed ({checked} files)')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
