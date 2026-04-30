#!/usr/bin/env python3
"""check_decimal_wrap.py の境界値テスト (T2026-0430-D 再発防止 SLI)."""

from __future__ import annotations

import ast
import os
import sys
import tempfile
import unittest
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

from check_decimal_wrap import check_file  # noqa: E402


def _check(src: str) -> list[tuple[int, str, str]]:
    with tempfile.NamedTemporaryFile(
        'w', suffix='.py', delete=False, encoding='utf-8'
    ) as f:
        f.write(src)
        tmp = f.name
    try:
        return [(ln, key, reason) for _, ln, key, reason in check_file(Path(tmp))]
    finally:
        os.unlink(tmp)


class CheckDecimalWrapTest(unittest.TestCase):
    def test_pr46_actual_bug_pattern_is_caught(self):
        """2026-04-27 commit 59eaf649 で混入した実バグそのもの."""
        src = '''
from decimal import Decimal
def f(g, hist, cnt, ts_iso, tid):
    _div_mult = source_diversity_score(g)
    velocity = calc_velocity(hist, cnt, ts_iso)
    velocity_score = calc_velocity_score(g)
    item = {
        "topicId": tid,
        "diversityScore": _div_mult,
        "velocity": Decimal(str(velocity)),
        "velocityScore": Decimal(str(velocity_score)),
    }
'''
        errs = _check(src)
        self.assertTrue(
            any('diversityScore' in e[1] and '_div_mult' in e[2] for e in errs)
        )

    def test_correctly_wrapped_dict_passes(self):
        src = '''
from decimal import Decimal
def f(g, tid):
    _div_mult = source_diversity_score(g)
    item = {
        "topicId": tid,
        "diversityScore": Decimal(str(_div_mult)),
        "velocity": Decimal("0.5"),
    }
'''
        errs = _check(src)
        self.assertEqual(errs, [])

    def test_int_reassignment_is_not_flagged(self):
        """score = apply_time_decay(score) のあと score = int(...) で再代入されたら safe."""
        src = '''
from decimal import Decimal
def f(score, last_ts, _div_mult):
    score = apply_time_decay(score, last_ts)
    score = max(1, int(score * _div_mult))
    velocity = calc_velocity()
    item = {
        "score": score,
        "velocity": Decimal(str(velocity)),
    }
'''
        errs = _check(src)
        self.assertEqual(errs, [], f'score should be int after re-assign, got {errs}')

    def test_literal_float_is_caught(self):
        src = '''
from decimal import Decimal
def f():
    velocity = calc_velocity()
    item = {
        "rate": 0.5,
        "velocity": Decimal(str(velocity)),
    }
'''
        errs = _check(src)
        self.assertTrue(any('rate' in e[1] and 'literal float' in e[2] for e in errs))

    def test_unwrapped_float_function_call_is_caught(self):
        src = '''
from decimal import Decimal
def f(g):
    velocity = calc_velocity()
    item = {
        "diversityScore": source_diversity_score(g),
        "velocity": Decimal(str(velocity)),
    }
'''
        errs = _check(src)
        self.assertTrue(
            any(
                'diversityScore' in e[1] and 'unwrapped' in e[2] and 'source_diversity_score' in e[2]
                for e in errs
            )
        )

    def test_unwrapped_div_binop_is_caught(self):
        src = '''
from decimal import Decimal
def f(a, b):
    velocity = calc_velocity()
    item = {
        "rate": a / b,
        "velocity": Decimal(str(velocity)),
    }
'''
        errs = _check(src)
        self.assertTrue(any('rate' in e[1] and 'Div' in e[2] for e in errs))

    def test_dict_without_decimal_wrap_is_not_inspected(self):
        """Decimal を含まない dict は DDB 行きと判定しないので素通し."""
        src = '''
def f(g):
    _div_mult = source_diversity_score(g)
    just_a_dict = {
        "diversityScore": _div_mult,
        "rate": 0.5,
    }
'''
        errs = _check(src)
        self.assertEqual(errs, [])

    def test_int_wrapped_value_passes(self):
        src = '''
from decimal import Decimal
def f(g):
    velocity = calc_velocity()
    item = {
        "score": int(source_diversity_score(g) * 100),
        "velocity": Decimal(str(velocity)),
    }
'''
        errs = _check(src)
        self.assertEqual(errs, [])

    def test_nested_list_dict_does_not_false_positive(self):
        src = '''
from decimal import Decimal
def f(srcs):
    velocity = calc_velocity()
    item = {
        "sources": list(srcs),
        "trendsData": {k: int(v) for k, v in srcs.items()},
        "velocity": Decimal(str(velocity)),
    }
'''
        errs = _check(src)
        self.assertEqual(errs, [])

    def test_str_constant_passes(self):
        src = '''
from decimal import Decimal
def f(velocity, ts):
    item = {
        "ts": ts,
        "velocity": Decimal(str(velocity)),
    }
'''
        errs = _check(src)
        self.assertEqual(errs, [])

    def test_real_lambda_files_pass(self):
        """現状の lambda コードベースが pass することを物理確認."""
        repo = THIS_DIR.parent
        from check_decimal_wrap import TARGETS, check_file as cf
        all_errs = []
        for t in TARGETS:
            p = repo / t
            if p.exists():
                all_errs.extend(cf(p))
        self.assertEqual(
            all_errs,
            [],
            f'real lambda files have wrap violations: {all_errs}',
        )


if __name__ == '__main__':
    unittest.main()
