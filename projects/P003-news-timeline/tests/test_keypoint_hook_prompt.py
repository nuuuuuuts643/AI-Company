"""T2026-0501-B: keyPoint フック型プロンプト改修の回帰 + boundary テスト。

PO FB「トピックが無難すぎる・表題に惹きがない」を受け、keyPoint を
読者の「え、なんで？」「自分にどう関係する？」を引き出すフック型に改修した
(proc_ai.py T2026-0501-B)。

このテストでは:
  1) keyPoint description に「フック型 4 原則」キーフレーズが含まれること
  2) _STORY_PROMPT_RULES に「フック型 4 原則」ブロックが含まれること
  3) _GENRE_KEYPOINT_HINTS の各ヒントに「逆説ヒント」が含まれること
  4) _build_keypoint_genre_hint に「フック型優先」指示が含まれること
  5) boundary tests: None / empty string / 未知ジャンル でも crash しないこと
  6) _build_story_schema に cnt=0 を渡しても crash しないこと

実行:
  cd projects/P003-news-timeline
  ANTHROPIC_API_KEY=dummy python3 -m unittest tests.test_keypoint_hook_prompt -v
"""
import os
import sys
import types
import unittest

os.environ.setdefault('ANTHROPIC_API_KEY', 'sk-ant-dummy-for-test')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'lambda', 'processor'))

if 'proc_config' not in sys.modules:
    fake = types.ModuleType('proc_config')
    fake.ANTHROPIC_API_KEY = os.environ['ANTHROPIC_API_KEY']
    sys.modules['proc_config'] = fake

import proc_ai  # noqa: E402

_VALID_GENRES = (
    '政治', 'ビジネス', '株・金融', 'テクノロジー', '科学', '健康',
    '国際', '社会', 'スポーツ', 'エンタメ', 'くらし', 'グルメ', 'ファッション', '総合',
)


class KeyPointDescriptionHookTest(unittest.TestCase):
    """_build_story_schema の keyPoint description にフック型指示が含まれること。"""

    def _get_kp_desc(self, mode='standard'):
        schema = proc_ai._build_story_schema(mode)
        return schema['properties']['keyPoint'].get('description', '')

    def test_hook_principle_in_description(self):
        """フック型4原則の文言が keyPoint description に含まれる。"""
        desc = self._get_kp_desc()
        self.assertIn('フック型', desc)

    def test_surprise_reversal_in_description(self):
        """驚き・逆説の具体表現例が含まれる。"""
        desc = self._get_kp_desc()
        self.assertIn('〇〇なのに〇〇', desc)

    def test_reader_impact_in_description(self):
        """読者への影響明示が含まれる。"""
        desc = self._get_kp_desc()
        self.assertIn('読者への影響', desc)

    def test_structural_reason_in_description(self):
        """「なぜなら〜」「背景には〜」の構造提示が含まれる。"""
        desc = self._get_kp_desc()
        self.assertIn('背景には〜', desc)

    def test_min_length_still_zero(self):
        """schema の keyPoint は minLength=0 を維持（PO 指示: 書けない場合は生成しない）。"""
        schema = proc_ai._build_story_schema('standard')
        self.assertEqual(schema['properties']['keyPoint'].get('minLength'), 0)

    def test_no_future_outlook_in_keypoint_description(self):
        """T2026-0501-G: keyPoint description に「今後どうなりそうか」が含まれないこと。

        outlook フィールドと内容重複するため keyPoint から除外した。
        """
        desc = self._get_kp_desc()
        self.assertNotIn('今後どうなりそうか', desc)

    def test_structural_background_in_keypoint_description(self):
        """T2026-0501-G: 初動③が「なぜこうなったか・構造的背景」になっていること。"""
        desc = self._get_kp_desc()
        self.assertIn('なぜこうなったか・構造的背景', desc)

    def test_outlook_role_prohibition_in_description(self):
        """T2026-0501-G: keyPoint description に outlook の役割禁止文が含まれること。"""
        desc = self._get_kp_desc()
        self.assertIn('outlook の役割', desc)

    def test_all_modes_have_hook_description(self):
        """minimal/standard/full 全モードで同じフック型 description が含まれる。"""
        for mode in ('minimal', 'standard', 'full'):
            desc = self._get_kp_desc(mode)
            self.assertIn('フック型', desc, f'{mode} モードの description にフック型が欠落')


class StoryPromptRulesHookTest(unittest.TestCase):
    """_STORY_PROMPT_RULES にフック型4原則が含まれること（既存テスト文字列も維持）。"""

    def test_hook_4_principles_in_rules(self):
        self.assertIn('フック型 4 原則', proc_ai._STORY_PROMPT_RULES)

    def test_surprise_reversal_example_in_rules(self):
        self.assertIn('〇〇なのに〇〇', proc_ai._STORY_PROMPT_RULES)

    def test_reader_impact_in_rules(self):
        self.assertIn('読者への影響', proc_ai._STORY_PROMPT_RULES)

    def test_why_because_structure_in_rules(self):
        self.assertIn('背景には〜', proc_ai._STORY_PROMPT_RULES)

    def test_change_phase_4th_line_is_reader_impact(self):
        """変化フェーズの 4 文目が「読者への影響」になっていること。"""
        self.assertIn('4 文目: 読者への影響', proc_ai._STORY_PROMPT_RULES)

    def test_no_future_outlook_in_rules_phase1(self):
        """T2026-0501-G: _STORY_PROMPT_RULES の初動③が outlook と重複する文言を含まないこと。"""
        self.assertNotIn('③ 今後どうなりそうか', proc_ai._STORY_PROMPT_RULES)

    def test_structural_background_in_rules(self):
        """T2026-0501-G: _STORY_PROMPT_RULES の初動③が「構造的背景」になっていること。"""
        self.assertIn('③ なぜこうなったか・構造的背景', proc_ai._STORY_PROMPT_RULES)

    def test_outlook_role_prohibition_in_rules(self):
        """T2026-0501-G: 禁止（共通）に「outlook の役割」が含まれること。"""
        self.assertIn('outlook の役割', proc_ai._STORY_PROMPT_RULES)


class GenreHintsHookTest(unittest.TestCase):
    """_GENRE_KEYPOINT_HINTS の各ヒントに逆説ヒントが追加されていること。"""

    def test_each_genre_has_reversal_hint(self):
        """全ジャンルのヒントに「逆説ヒント:」が含まれる。"""
        for genre in _VALID_GENRES:
            hint = proc_ai._GENRE_KEYPOINT_HINTS.get(genre, '')
            self.assertIn('逆説ヒント', hint, f'{genre} の逆説ヒントが欠落')

    def test_anchor_phrase_still_present(self):
        """既存テストが要求する anchor 句 '中心数値/固有名詞に据える' が全ジャンルで維持されている。"""
        anchor = '中心数値/固有名詞に据える'
        for genre in _VALID_GENRES:
            hint = proc_ai._GENRE_KEYPOINT_HINTS.get(genre, '')
            self.assertIn(anchor, hint, f'{genre} の anchor 句が欠落')


class BuildKeyPointGenreHintHookTest(unittest.TestCase):
    """_build_keypoint_genre_hint にフック型優先指示が含まれること。"""

    def test_hook_priority_in_block(self):
        """生成ブロックに「フック型優先」が含まれる。"""
        block = proc_ai._build_keypoint_genre_hint('政治')
        self.assertIn('フック型優先', block)

    def test_surprise_reversal_examples_in_block(self):
        """「〇〇なのに〇〇」「実は〜」「意外にも〜」が含まれる。"""
        block = proc_ai._build_keypoint_genre_hint('健康')
        self.assertIn('〇〇なのに〇〇', block)
        self.assertIn('実は〜', block)
        self.assertIn('意外にも〜', block)


class BoundaryTest(unittest.TestCase):
    """boundary conditions: None / 空文字 / 未知ジャンル / cnt=0 でも crash しないこと。"""

    def test_genre_hint_with_none_no_crash(self):
        """genre=None でも KeyError / AttributeError せず文字列を返す。"""
        block = proc_ai._build_keypoint_genre_hint(None)
        self.assertIsInstance(block, str)
        self.assertTrue(block.strip())

    def test_genre_hint_with_empty_string_no_crash(self):
        """genre='' でも crash しない（空文字は None と同様に総合フォールバック）。"""
        block = proc_ai._build_keypoint_genre_hint('')
        self.assertIsInstance(block, str)
        self.assertTrue(block.strip())

    def test_genre_hint_with_unknown_genre_no_crash(self):
        """未知ジャンルでも crash しない。"""
        block = proc_ai._build_keypoint_genre_hint('宇宙')
        self.assertIsInstance(block, str)
        self.assertTrue(block.strip())

    def test_build_story_schema_cnt_zero_no_crash(self):
        """cnt=0 を渡しても KeyError / ZeroDivisionError せず schema を返す。"""
        schema = proc_ai._build_story_schema('minimal', cnt=0)
        self.assertIn('keyPoint', schema['properties'])

    def test_build_story_schema_cnt_none_no_crash(self):
        """cnt 省略（デフォルト=1）でも正常動作する。"""
        schema = proc_ai._build_story_schema('standard')
        self.assertIn('keyPoint', schema['properties'])

    def test_keypoint_too_short_with_none(self):
        """_keypoint_too_short(None) は True (inadequate) を返す。"""
        self.assertTrue(proc_ai._keypoint_too_short(None))

    def test_keypoint_too_short_with_empty(self):
        """_keypoint_too_short('') は True を返す。"""
        self.assertTrue(proc_ai._keypoint_too_short(''))

    def test_keypoint_too_short_with_int(self):
        """str 以外の型（int）も True (inadequate) を返す。"""
        self.assertTrue(proc_ai._keypoint_too_short(0))

    def test_genre_hint_all_known_genres_non_empty(self):
        """全 known ジャンルで空文字を返さない。"""
        for genre in _VALID_GENRES:
            block = proc_ai._build_keypoint_genre_hint(genre)
            self.assertTrue(block.strip(), f'{genre} で空ブロックが返った')


if __name__ == '__main__':
    unittest.main(verbosity=2)
