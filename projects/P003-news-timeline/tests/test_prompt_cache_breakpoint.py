#!/usr/bin/env python3
"""tests/test_prompt_cache_breakpoint.py — T2026-0502-AZ

`_generate_story_minimal/standard/full` が Anthropic prompt caching の
user-side breakpoint を正しい位置に設定していることを検証する。

設計方針:
  - _call_claude_tool をモックして渡された prompt (list of content blocks) を検査
  - cache_control: ephemeral ブロックが存在すること
  - cache_control ブロックが article data (headlines) を含まないこと
  - article data (headlines) が cache_control なしの最後のブロックにあること
  - 全3モード (minimal / standard / full) で同一の不変条件を assert

不変条件:
  T2026-0502-AZ で導入した user-side cache breakpoint が壊れた瞬間に CI で検知できる。
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

_LAMBDA_PROCESSOR = os.path.join(
    os.path.dirname(__file__), '..', 'lambda', 'processor'
)
sys.path.insert(0, _LAMBDA_PROCESSOR)

import proc_ai  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_articles(n: int) -> list[dict]:
    return [
        {
            'title': f'テスト記事{i+1}',
            'description': f'概要テキスト{i+1}',
            'url': f'https://example.com/{i+1}',
            'publishedAt': '2026-05-03T12:00:00Z',
            'source': {'name': f'テストメディア{i+1}'},
        }
        for i in range(n)
    ]


# keyPoint が 100字以上でないと _process_keypoint_quality が retry call を出す。
# retry の prompt は str (string) なので captured['prompt'] を上書きする。
# 100字以上の固定文字列で mock することでキャッシュ検証対象の call だけ残す。
_KP_LONG = 'テストキーポイント具体的な変化と数字固有名詞を含む' * 6  # ~150 chars, ≥100


def _get_cached_block(prompt: list[dict]) -> dict | None:
    """cache_control: ephemeral を持つブロックを返す。"""
    for block in prompt:
        if isinstance(block, dict) and block.get('cache_control') == {'type': 'ephemeral'}:
            return block
    return None


def _get_dynamic_block(prompt: list[dict]) -> dict | None:
    """cache_control を持たない最後のブロック (article data) を返す。"""
    for block in reversed(prompt):
        if isinstance(block, dict) and 'cache_control' not in block:
            return block
    return None


# ---------------------------------------------------------------------------
# 共通アサーション
# ---------------------------------------------------------------------------

def _assert_cache_structure(prompt: list[dict], mode: str, genre: str):
    """prompt が正しい 2-block 構造を持つことを検証する。"""
    assert isinstance(prompt, list), f'{mode}: prompt must be a list, got {type(prompt)}'
    assert len(prompt) >= 2, f'{mode}: prompt must have ≥2 blocks, got {len(prompt)}'

    cached = _get_cached_block(prompt)
    assert cached is not None, f'{mode}: no cache_control block found'
    assert cached.get('type') == 'text', f'{mode}: cached block must be type=text'

    dynamic = _get_dynamic_block(prompt)
    assert dynamic is not None, f'{mode}: no dynamic (non-cached) block found'
    assert dynamic.get('type') == 'text', f'{mode}: dynamic block must be type=text'

    # article data は dynamic block にあること
    dynamic_text = dynamic.get('text', '')
    assert '記事情報' in dynamic_text, \
        f'{mode}: "記事情報" must be in dynamic block, not cached block'
    assert 'テスト記事1' in dynamic_text, \
        f'{mode}: headlines must be in dynamic block'

    # article data は cached block に含まれないこと
    cached_text = cached.get('text', '')
    assert 'テスト記事1' not in cached_text, \
        f'{mode}: headlines must NOT be in cached block'
    assert '記事情報' not in cached_text, \
        f'{mode}: "記事情報" header must NOT be in cached block'

    # genre hint が cached block にあること (genre-specific caching の核心)
    if genre:
        assert genre in cached_text, \
            f'{mode}: genre={genre} label must appear in cached block'


# ---------------------------------------------------------------------------
# _generate_story_minimal
# ---------------------------------------------------------------------------

class TestMinimalCacheBreakpoint(unittest.TestCase):

    def _run_minimal(self, n: int, genre: str | None = None) -> list[dict]:
        articles = _make_articles(n)
        captured = {}

        def fake_call_claude_tool(prompt, *args, **kwargs):
            captured['prompt'] = prompt
            return {
                'aiSummary': 'テスト要約',
                'keyPoint': _KP_LONG,
                'outlook': 'テスト展望 [確信度:中]',
                'topicTitle': 'テストトピック',
                'latestUpdateHeadline': 'テスト見出しが発表された',
                'isCoherent': True,
                'topicLevel': 'sub',
                'genres': [genre or '総合'],
            }

        with patch.object(proc_ai, '_call_claude_tool', side_effect=fake_call_claude_tool):
            with patch.object(proc_ai, '_build_media_comparison_block', return_value=''):
                proc_ai._generate_story_minimal(articles, genre=genre)

        return captured.get('prompt', [])

    def test_minimal_1_article_has_cache_block(self):
        prompt = self._run_minimal(1, genre='政治')
        _assert_cache_structure(prompt, 'minimal(n=1)', '政治')

    def test_minimal_2_articles_has_cache_block(self):
        prompt = self._run_minimal(2, genre='ビジネス')
        _assert_cache_structure(prompt, 'minimal(n=2)', 'ビジネス')

    def test_minimal_none_genre_has_cache_block(self):
        prompt = self._run_minimal(1, genre=None)
        assert isinstance(prompt, list) and len(prompt) >= 2

    def test_minimal_cached_block_has_keypoint_genre_hint(self):
        prompt = self._run_minimal(1, genre='テクノロジー')
        cached = _get_cached_block(prompt)
        assert cached is not None
        assert 'テクノロジー' in cached['text'], \
            'cached block must contain genre-specific keypoint hint'

    def test_minimal_cached_block_has_outlook_hint(self):
        prompt = self._run_minimal(1, genre='国際')
        cached = _get_cached_block(prompt)
        assert cached is not None
        assert 'outlook' in cached['text'] or 'T2026-0501-G' in cached['text'], \
            'cached block must contain outlook actor hint'

    def test_minimal_dynamic_block_has_mode_header(self):
        prompt = self._run_minimal(1, genre='社会')
        dynamic = _get_dynamic_block(prompt)
        assert dynamic is not None
        assert 'minimal' in dynamic['text'], \
            'dynamic block must contain mode header'


# ---------------------------------------------------------------------------
# _generate_story_standard
# ---------------------------------------------------------------------------

class TestStandardCacheBreakpoint(unittest.TestCase):

    def _run_standard(self, n: int, genre: str | None = None) -> list[dict]:
        articles = _make_articles(n)
        captured = {}

        def fake_call_claude_tool(prompt, *args, **kwargs):
            captured['prompt'] = prompt
            return {
                'aiSummary': 'テスト要約',
                'keyPoint': _KP_LONG,
                'outlook': 'テスト展望 [確信度:中]',
                'topicTitle': 'テストトピック',
                'latestUpdateHeadline': 'テスト見出しが発表された',
                'isCoherent': True,
                'topicLevel': 'sub',
                'genres': [genre or '総合'],
                'phase': '拡散',
                'statusLabel': '進行中',
                'watchPoints': 'テスト注目ポイント①テスト②テスト',
                'perspectives': 'テスト視点A は〜 テスト視点B は〜',
                'timeline': [],
            }

        with patch.object(proc_ai, '_call_claude_tool', side_effect=fake_call_claude_tool):
            with patch.object(proc_ai, '_build_media_comparison_block', return_value=''):
                proc_ai._generate_story_standard(articles, n, genre=genre)

        return captured.get('prompt', [])

    def test_standard_has_cache_block(self):
        prompt = self._run_standard(3, genre='株・金融')
        _assert_cache_structure(prompt, 'standard(n=3)', '株・金融')

    def test_standard_cached_block_excludes_cnt(self):
        """cnt は dynamic block にのみ現れ、cached block には含まれない。"""
        prompt = self._run_standard(4, genre='科学')
        cached = _get_cached_block(prompt)
        assert cached is not None
        # モードラベルに cnt が入っていないこと
        assert '(記事 4 件)' not in cached['text'], \
            'cnt must NOT appear in cached block — would break cache for different article counts'

    def test_standard_cached_block_has_causal_hint_for_supported_genre(self):
        """causal chain hint (T2026-0502-AE) が cached block に入っていること。"""
        prompt = self._run_standard(3, genre='国際')
        cached = _get_cached_block(prompt)
        assert cached is not None
        assert 'T2026-0502-AE' in cached['text'] or 'aiSummary causal chain' in cached['text'], \
            'causal chain hint must be in cached block for 国際 genre'

    def test_standard_cached_block_has_keypoint_examples_for_supported_genre(self):
        """T2026-0501-K の few-shot examples が cached block に入っていること。"""
        prompt = self._run_standard(3, genre='エンタメ')
        cached = _get_cached_block(prompt)
        assert cached is not None
        # _GENRE_KEYPOINT_EXAMPLES['エンタメ'] には '◎ 良い例' が含まれる
        assert '◎ 良い例' in cached['text'], \
            'few-shot examples (T2026-0501-K) must be in cached block'

    def test_standard_same_genre_produces_identical_cached_block(self):
        """同一 genre で2回呼ぶと cached block が完全一致すること (cache hit の前提条件)。"""
        prompt1 = self._run_standard(3, genre='ビジネス')
        prompt2 = self._run_standard(5, genre='ビジネス')
        cached1 = _get_cached_block(prompt1)
        cached2 = _get_cached_block(prompt2)
        assert cached1 is not None and cached2 is not None
        assert cached1['text'] == cached2['text'], \
            'cached block must be identical for same genre regardless of cnt'

    def test_standard_different_genres_produce_different_cached_blocks(self):
        """異なる genre では cached block が異なること (cache miss は想定通り)。"""
        prompt_a = self._run_standard(3, genre='政治')
        prompt_b = self._run_standard(3, genre='スポーツ')
        cached_a = _get_cached_block(prompt_a)
        cached_b = _get_cached_block(prompt_b)
        assert cached_a is not None and cached_b is not None
        assert cached_a['text'] != cached_b['text'], \
            'different genres must produce different cached blocks'


# ---------------------------------------------------------------------------
# _generate_story_full
# ---------------------------------------------------------------------------

class TestFullCacheBreakpoint(unittest.TestCase):

    def _run_full(self, n: int, genre: str | None = None) -> list[dict]:
        articles = _make_articles(n)
        captured = {}

        def fake_call_claude_tool(prompt, *args, **kwargs):
            captured['prompt'] = prompt
            return {
                'aiSummary': 'テスト要約',
                'keyPoint': _KP_LONG,
                'outlook': 'テスト展望 [確信度:中]',
                'topicTitle': 'テストトピック',
                'latestUpdateHeadline': 'テスト見出しが発表された',
                'isCoherent': True,
                'topicLevel': 'major',
                'genres': [genre or '総合'],
                'phase': '拡散',
                'statusLabel': '進行中',
                'watchPoints': 'テスト注目ポイント①テスト②テスト',
                'perspectives': 'テスト視点A は〜 テスト視点B は〜',
                'timeline': [],
                'forecast': 'テスト予測 [確信度:中]',
                'causalChain': [],
            }

        with patch.object(proc_ai, '_call_claude_tool', side_effect=fake_call_claude_tool):
            with patch.object(proc_ai, '_build_media_comparison_block', return_value=''):
                proc_ai._generate_story_full(articles, n, genre=genre)

        return captured.get('prompt', [])

    def test_full_has_cache_block(self):
        prompt = self._run_full(7, genre='健康')
        _assert_cache_structure(prompt, 'full(n=7)', '健康')

    def test_full_cached_block_excludes_cnt(self):
        prompt = self._run_full(8, genre='社会')
        cached = _get_cached_block(prompt)
        assert cached is not None
        assert '(記事 8 件)' not in cached['text'], \
            'cnt must NOT appear in cached block'

    def test_full_cached_block_has_mandatory_checklst(self):
        """full モードの【最重要】ブロックが cached block に含まれること。"""
        prompt = self._run_full(6, genre='国際')
        cached = _get_cached_block(prompt)
        assert cached is not None
        assert '最重要' in cached['text'], \
            '【最重要】block must be in cached block'

    def test_full_same_genre_produces_identical_cached_block(self):
        """同一 genre・異なる cnt で cached block が一致すること。"""
        prompt1 = self._run_full(6, genre='テクノロジー')
        prompt2 = self._run_full(10, genre='テクノロジー')
        cached1 = _get_cached_block(prompt1)
        cached2 = _get_cached_block(prompt2)
        assert cached1 is not None and cached2 is not None
        assert cached1['text'] == cached2['text'], \
            'cached block must be identical for same genre regardless of cnt'

    def test_full_cached_block_has_causal_outlook_hint(self):
        """causal outlook hint (T2026-0501-OL2) が cached block にあること。"""
        prompt = self._run_full(6, genre='株・金融')
        cached = _get_cached_block(prompt)
        assert cached is not None
        assert 'T2026-0501-OL2' in cached['text'] or '波及先' in cached['text'], \
            'causal outlook hint must be in cached block'


# ---------------------------------------------------------------------------
# 全モード共通: cache_control 構造の不変条件
# ---------------------------------------------------------------------------

class TestAllModesCacheInvariant(unittest.TestCase):
    """全3モードで共通する最低保証。"""

    def _run_mode(self, mode: str, n: int, genre: str):
        articles = _make_articles(n)
        captured = {}

        base_result = {
            'aiSummary': 'テスト要約',
            'keyPoint': _KP_LONG,
            'outlook': 'テスト展望 [確信度:中]',
            'topicTitle': 'テストトピック',
            'latestUpdateHeadline': 'テスト見出しが発表された',
            'isCoherent': True,
            'topicLevel': 'sub',
            'genres': [genre],
        }
        if mode in ('standard', 'full'):
            base_result.update({
                'phase': '拡散',
                'statusLabel': '進行中',
                'watchPoints': 'テスト注目ポイント①テスト②テスト',
                'perspectives': 'テスト視点A は〜 テスト視点B は〜',
                'timeline': [],
            })
        if mode == 'full':
            base_result.update({'forecast': 'テスト [確信度:中]', 'causalChain': []})

        def fake_call(prompt, *args, **kwargs):
            captured['prompt'] = prompt
            return base_result

        with patch.object(proc_ai, '_call_claude_tool', side_effect=fake_call):
            with patch.object(proc_ai, '_build_media_comparison_block', return_value=''):
                if mode == 'minimal':
                    proc_ai._generate_story_minimal(articles, genre=genre)
                elif mode == 'standard':
                    proc_ai._generate_story_standard(articles, n, genre=genre)
                else:
                    proc_ai._generate_story_full(articles, n, genre=genre)

        return captured.get('prompt', [])

    def test_all_modes_return_list_prompt(self):
        for mode, n in [('minimal', 1), ('standard', 3), ('full', 6)]:
            with self.subTest(mode=mode):
                prompt = self._run_mode(mode, n, '政治')
                self.assertIsInstance(prompt, list,
                    f'{mode}: prompt must be list for cache_control support')

    def test_all_modes_have_exactly_two_blocks(self):
        for mode, n in [('minimal', 2), ('standard', 4), ('full', 7)]:
            with self.subTest(mode=mode):
                prompt = self._run_mode(mode, n, 'ビジネス')
                self.assertEqual(len(prompt), 2,
                    f'{mode}: expected exactly 2 content blocks')

    def test_all_modes_first_block_has_cache_control(self):
        for mode, n in [('minimal', 1), ('standard', 3), ('full', 6)]:
            with self.subTest(mode=mode):
                prompt = self._run_mode(mode, n, '国際')
                first = prompt[0] if prompt else {}
                self.assertEqual(first.get('cache_control'), {'type': 'ephemeral'},
                    f'{mode}: first block must have cache_control: ephemeral')

    def test_all_modes_last_block_has_no_cache_control(self):
        for mode, n in [('minimal', 1), ('standard', 3), ('full', 6)]:
            with self.subTest(mode=mode):
                prompt = self._run_mode(mode, n, '科学')
                last = prompt[-1] if prompt else {}
                self.assertNotIn('cache_control', last,
                    f'{mode}: last (dynamic) block must NOT have cache_control')

    def test_all_modes_article_data_in_last_block(self):
        for mode, n in [('minimal', 1), ('standard', 3), ('full', 6)]:
            with self.subTest(mode=mode):
                prompt = self._run_mode(mode, n, 'テクノロジー')
                last_text = (prompt[-1] if prompt else {}).get('text', '')
                self.assertIn('テスト記事1', last_text,
                    f'{mode}: article headline must be in last (dynamic) block')


if __name__ == '__main__':
    unittest.main()
