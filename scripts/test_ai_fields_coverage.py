#!/usr/bin/env python3
"""check_ai_fields_coverage.py の境界値テスト (T256 再発防止 SLI)。

「proc_ai に新フィールドを追加 → handler.ai_updates / proc_storage.update_topic_with_ai
 のどちらか or 両方への propagation を忘れた」状態で CI が必ず落ちることを保証する。
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

from check_ai_fields_coverage import (  # noqa: E402
    STORAGE_ONLY,
    check,
    extract_normalize_output_keys,
    _is_referenced,
)


# 小さな proc_ai.py 模擬テンプレート (str.replace 方式で組み立て)。
def _build_proc_ai_src(minimal_extra: str = '', standard_extra: str = '') -> str:
    return (
        '"""fake proc_ai for tests."""\n\n'
        'def _normalize_story_result(result, mode):\n'
        "    if mode == 'minimal':\n"
        '        return {\n'
        "            'aiSummary': str(result.get('aiSummary') or ''),\n"
        f'            {minimal_extra}\n'
        '        }\n'
        '    out = {\n'
        "        'aiSummary': str(result.get('aiSummary') or ''),\n"
        "        'keyPoint':  str(result.get('keyPoint') or ''),\n"
        "        'phase':     result.get('phase'),\n"
        f'        {standard_extra}\n'
        '    }\n'
        '    return out\n'
    )


def _build_storage_src(extra: str = '') -> str:
    return (
        'def update_topic_with_ai(tid, gen_title, gen_story, ai_succeeded=False):\n'
        "    if gen_story.get('aiSummary'):\n"
        "        write(gen_story['aiSummary'])\n"
        "    if gen_story.get('keyPoint'):\n"
        "        write(gen_story['keyPoint'])\n"
        "    if gen_story.get('phase'):\n"
        "        write(gen_story['phase'])\n"
        f'    {extra}\n'
    )


def _build_handler_src(extra: str = '') -> str:
    return (
        'def build_ai_updates(gen_story):\n'
        '    ai_updates = {\n'
        "        'generatedSummary': gen_story['aiSummary'] if gen_story else None,\n"
        "        'keyPoint':         gen_story.get('keyPoint') if gen_story else None,\n"
        "        'storyPhase':       gen_story['phase'] if gen_story else None,\n"
        f'        {extra}\n'
        '    }\n'
        '    return ai_updates\n'
    )


def _write_temp_dir(proc_ai_src: str, storage_src: str, handler_src: str) -> Path:
    d = Path(tempfile.mkdtemp(prefix='aifield_'))
    (d / 'proc_ai.py').write_text(proc_ai_src, encoding='utf-8')
    (d / 'proc_storage.py').write_text(storage_src, encoding='utf-8')
    (d / 'handler.py').write_text(handler_src, encoding='utf-8')
    return d


class IsReferencedTest(unittest.TestCase):
    def test_get_single_quote(self):
        self.assertTrue(_is_referenced("x = gen_story.get('keyPoint')", 'keyPoint'))

    def test_get_double_quote(self):
        self.assertTrue(_is_referenced('x = gen_story.get("keyPoint")', 'keyPoint'))

    def test_subscript(self):
        self.assertTrue(_is_referenced("x = gen_story['keyPoint']", 'keyPoint'))

    def test_subscript_double_quote(self):
        self.assertTrue(_is_referenced('x = gen_story["keyPoint"]', 'keyPoint'))

    def test_unrelated_dict_not_match(self):
        # other_dict.get('keyPoint') は対象外 (gen_story 限定)。
        self.assertFalse(_is_referenced("x = other.get('keyPoint')", 'keyPoint'))

    def test_substring_not_match(self):
        # keyPoint は keyPointLength に substring match させない。
        self.assertFalse(
            _is_referenced("x = gen_story.get('keyPointLength')", 'someUnrelated')
        )

    def test_partial_key_isolated(self):
        # 'keyPoint' が 'keyPointLength' の一部であっても、検索キーが 'keyPoint' のときは
        # gen_story.get('keyPointLength') を hit させない (完全一致のため)。
        src = "x = gen_story.get('keyPointLength')"
        self.assertFalse(_is_referenced(src, 'keyPoint'))


class ExtractNormalizeKeysTest(unittest.TestCase):
    def test_extract_union_minimal_and_standard(self):
        src = _build_proc_ai_src(
            minimal_extra="'minOnly': 'm',",
            standard_extra="'stdOnly': 's',",
        )
        d = _write_temp_dir(src, '', '')
        try:
            keys = extract_normalize_output_keys(d / 'proc_ai.py')
            self.assertIn('aiSummary', keys)
            self.assertIn('keyPoint', keys)
            self.assertIn('phase', keys)
            self.assertIn('minOnly', keys)
            self.assertIn('stdOnly', keys)
        finally:
            import shutil
            shutil.rmtree(d, ignore_errors=True)


class CheckIntegrationTest(unittest.TestCase):
    """T256 のコアテスト: 新フィールド追加 → どちらか propagate 忘れで CI が落ちる。"""

    def _make(self, proc_ai_extra_minimal: str, proc_ai_extra_standard: str,
              storage_extra: str, handler_extra: str) -> Path:
        proc_ai_src = _build_proc_ai_src(
            minimal_extra=proc_ai_extra_minimal,
            standard_extra=proc_ai_extra_standard,
        )
        storage_src = _build_storage_src(extra=storage_extra)
        handler_src = _build_handler_src(extra=handler_extra)
        return _write_temp_dir(proc_ai_src, storage_src, handler_src)

    def test_baseline_passes(self):
        """3 フィールド (aiSummary / keyPoint / phase) がどちらにもあれば OK。"""
        d = self._make('', '', '', '')
        try:
            keys, sm, hm = check(d / 'proc_ai.py', d / 'proc_storage.py', d / 'handler.py')
            self.assertEqual(set(keys), {'aiSummary', 'keyPoint', 'phase'})
            self.assertEqual(sm, [])
            self.assertEqual(hm, [])
        finally:
            import shutil
            shutil.rmtree(d, ignore_errors=True)

    def test_t249_pattern_keypoint_missing_in_handler_caught(self):
        """T249 そのもの: proc_ai は brandNew を出すが handler 側に追加していない."""
        d = self._make(
            proc_ai_extra_minimal="'brandNew': result.get('brandNew'),",
            proc_ai_extra_standard="'brandNew': result.get('brandNew'),",
            # storage には追加した
            storage_extra="if gen_story.get('brandNew'): write(gen_story['brandNew'])",
            # handler は追加し忘れ → ここで CI が落ちる必要がある
            handler_extra='',
        )
        try:
            keys, sm, hm = check(d / 'proc_ai.py', d / 'proc_storage.py', d / 'handler.py')
            self.assertIn('brandNew', keys)
            self.assertEqual(sm, [])
            self.assertIn('brandNew', hm)
        finally:
            import shutil
            shutil.rmtree(d, ignore_errors=True)

    def test_storage_layer_missing_caught(self):
        """逆パターン: handler には書いたが proc_storage に書き忘れ."""
        d = self._make(
            proc_ai_extra_minimal="'brandNew': result.get('brandNew'),",
            proc_ai_extra_standard="'brandNew': result.get('brandNew'),",
            storage_extra='',
            handler_extra="'brandNew': gen_story.get('brandNew') if gen_story else None,",
        )
        try:
            keys, sm, hm = check(d / 'proc_ai.py', d / 'proc_storage.py', d / 'handler.py')
            self.assertIn('brandNew', sm)
            self.assertEqual(hm, [])
        finally:
            import shutil
            shutil.rmtree(d, ignore_errors=True)

    def test_storage_only_allowlist_does_not_require_handler(self):
        """STORAGE_ONLY (例: keyPointLength) は handler 欠落を許容する."""
        # allowlist のキー名で proc_ai に追加し、storage だけ書く
        any_storage_only = next(iter(STORAGE_ONLY))
        d = self._make(
            proc_ai_extra_minimal=f"'{any_storage_only}': 0,",
            proc_ai_extra_standard=f"'{any_storage_only}': 0,",
            storage_extra=f"if gen_story.get('{any_storage_only}'): write(gen_story['{any_storage_only}'])",
            handler_extra='',  # 意図的に handler には書かない
        )
        try:
            keys, sm, hm = check(d / 'proc_ai.py', d / 'proc_storage.py', d / 'handler.py')
            self.assertIn(any_storage_only, keys)
            self.assertEqual(sm, [])
            self.assertEqual(hm, [])  # allowlist のため handler 欠落 OK
        finally:
            import shutil
            shutil.rmtree(d, ignore_errors=True)


class RealCodebaseSmokeTest(unittest.TestCase):
    """実コードベースで現状 0 件であることを保証 (regression catch)."""

    def test_current_code_passes(self):
        keys, sm, hm = check()
        self.assertGreater(len(keys), 0)
        self.assertEqual(
            sm, [],
            f'proc_storage.py で参照されていない proc_ai 出力: {sm}'
        )
        self.assertEqual(
            hm, [],
            f'handler.py で参照されていない proc_ai 出力: {hm}'
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)
