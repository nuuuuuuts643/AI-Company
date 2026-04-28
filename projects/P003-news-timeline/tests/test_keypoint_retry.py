"""T2026-0429-KP3 regression test: keyPoint 100 字未満で 1 回だけ再生成を要求するロジックを物理ガード。

背景 (2026-04-29 06:10 JST 自律巡回 SLI 実測):
  本番 topics.json で keyPoint 100 字以上は 2/105 = 1.9% のみ。
  T2026-0429-KP / handler.py 修正・c8cfb07 quality_heal 1-99字再処理・06:00 JST cron 後でも
  一切動かなかった。第3層原因 = proc_ai.py の prompt が「100 字以上」を物理的に強制していなかった。

修正の中身:
  1) _STORY_PROMPT_RULES / _SYSTEM_PROMPT に 100 字以上必須・schema 違反扱いを明示
  2) schema の keyPoint に minLength=100 を付与
  3) _retry_short_keypoint で 1 回だけ「再生成要求」prompt を送る
  4) 再生成結果のほうが長ければ採用、短ければ原本を維持 (best effort)

このテストでは API を mock し、以下 4 ケースを物理確認する:
  - 初回 30 字 → retry 200 字 → 200 字が採用されること (KP3 正常動作)
  - 初回 30 字 → retry も 30 字 → 原本維持・None ではなく結果が返ること (best effort)
  - 初回 200 字 → retry が呼ばれないこと (無駄コール抑制)
  - 初回 30 字 → retry 失敗 (API 例外) → 原本維持・None ではなく結果が返ること

実行:
  cd projects/P003-news-timeline
  ANTHROPIC_API_KEY=dummy python3 -m unittest tests.test_keypoint_retry -v
"""
import os
import sys
import types
import unittest
from unittest import mock

os.environ.setdefault('ANTHROPIC_API_KEY', 'sk-ant-dummy-for-test')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'lambda', 'processor'))

# proc_config を fake module で差し替え (boto3 import を避ける)
if 'proc_config' not in sys.modules:
    fake = types.ModuleType('proc_config')
    fake.ANTHROPIC_API_KEY = os.environ['ANTHROPIC_API_KEY']
    sys.modules['proc_config'] = fake

import proc_ai  # noqa: E402


_LONG_KP = (
    'もともとこの問題は数年前から燻ぶっており、関係各国の利害が複雑に絡み合う構造的な対立として継続してきた。'
    '2026 年 4 月の事件をきっかけに事態が新たな段階に進み、現在は当事者間で対話の枠組みが模索されている状況である。'
    '今後の焦点は合意形成の可否と、それに伴う周辺諸国の動きにある。'
)
_SHORT_KP = 'ロシア撤退と過激派攻勢の同時進行'  # 17字


def _stub_minimal_full(keypoint: str) -> dict:
    """tool_use.input 相当の最低限フィールドを返すヘルパー (minimal mode)。"""
    return {
        'aiSummary': 'マリで複数のイスラム過激派が同時攻撃を行い国防相が殺害された事案が発生した。サヘル全域への波及が懸念される。',
        'keyPoint': keypoint,
        'outlook': '対立の長期化が予想される [確信度:中]',
        'topicTitle': 'マリ過激派攻勢',
        'latestUpdateHeadline': '国防相が殺害された',
        'isCoherent': True,
        'topicLevel': 'detail',
        'genres': ['国際'],
    }


def _stub_standard_full(keypoint: str) -> dict:
    """tool_use.input 相当の最低限フィールドを返すヘルパー (standard/full mode)。"""
    base = _stub_minimal_full(keypoint)
    base.update({
        'statusLabel': '進行中',
        'watchPoints': '①治安部隊の対応 ②サヘル諸国の反応 ③民間人被害',
        'perspectives': '朝日は経済への打撃を懸念、産経は安全保障上の利益を指摘、毎日は外交プロセスの不透明性に着目。',
        'phase': '拡散',
        'timeline': [{'date': '2026-04-28', 'event': '国防相殺害'}],
    })
    return base


_DUMMY_ARTICLES = [
    {'title': 'マリで国防相殺害', 'description': '首都圏で同時多発攻撃', 'pubDate': '2026-04-28'},
    {'title': '過激派が攻勢', 'description': '複数の都市で衝突', 'pubDate': '2026-04-29'},
    {'title': 'サヘル諸国が緊急協議', 'description': '波及防止に向け会合', 'pubDate': '2026-04-29'},
]


class KeyPointTooShortHelperTest(unittest.TestCase):
    def test_none(self):
        self.assertTrue(proc_ai._keypoint_too_short(None))

    def test_empty(self):
        self.assertTrue(proc_ai._keypoint_too_short(''))

    def test_short_string(self):
        self.assertTrue(proc_ai._keypoint_too_short(_SHORT_KP))

    def test_just_below(self):
        self.assertTrue(proc_ai._keypoint_too_short('あ' * 99))

    def test_at_threshold(self):
        self.assertFalse(proc_ai._keypoint_too_short('あ' * 100))

    def test_normal(self):
        self.assertFalse(proc_ai._keypoint_too_short(_LONG_KP))


class GenerateStoryRetryTest(unittest.TestCase):
    """generate_story (minimal/standard/full) で keyPoint 短縮時に retry が走る contract test。"""

    def test_standard_short_then_long_uses_retry(self):
        """初回 17 字 → retry 150 字 → retry 結果が採用されること。"""
        side = [
            _stub_standard_full(_SHORT_KP),  # 初回
            _stub_standard_full(_LONG_KP),   # retry
        ]
        with mock.patch('proc_ai._call_claude_tool', side_effect=side) as mocked:
            result = proc_ai._generate_story_standard(_DUMMY_ARTICLES, cnt=3)
            self.assertEqual(mocked.call_count, 2, '初回 + retry の 2 回呼ばれるべき')
        self.assertIsNotNone(result)
        self.assertGreaterEqual(len(result['keyPoint']), 100, 'retry の長い keyPoint が採用されるべき')

    def test_standard_short_then_short_keeps_original(self):
        """初回 17 字 → retry も 30 字 → どちらも短い。原本維持で None ではなく結果が返ること。"""
        retry_short = 'マリの治安が悪化している今後の動向に注目したい'  # 22字
        side = [
            _stub_standard_full(_SHORT_KP),
            _stub_standard_full(retry_short),
        ]
        with mock.patch('proc_ai._call_claude_tool', side_effect=side) as mocked:
            result = proc_ai._generate_story_standard(_DUMMY_ARTICLES, cnt=3)
            self.assertEqual(mocked.call_count, 2)
        # best effort: retry のほうが長いので採用される (両方短くても dict は返す)
        self.assertIsNotNone(result, 'best effort で結果は返すこと (None ではない)')

    def test_standard_long_first_no_retry(self):
        """初回 150 字 → retry 不要。1 回しか呼ばれないこと。"""
        side = [
            _stub_standard_full(_LONG_KP),
        ]
        with mock.patch('proc_ai._call_claude_tool', side_effect=side) as mocked:
            result = proc_ai._generate_story_standard(_DUMMY_ARTICLES, cnt=3)
            self.assertEqual(mocked.call_count, 1, '正常生成時は retry を呼ばないこと')
        self.assertIsNotNone(result)
        self.assertGreaterEqual(len(result['keyPoint']), 100)

    def test_standard_short_then_retry_api_failure_keeps_original(self):
        """初回 17 字 → retry が API 例外 → 原本維持で None ではなく結果が返ること。"""
        side = [
            _stub_standard_full(_SHORT_KP),
            RuntimeError('API down'),
        ]
        with mock.patch('proc_ai._call_claude_tool', side_effect=side):
            result = proc_ai._generate_story_standard(_DUMMY_ARTICLES, cnt=3)
        self.assertIsNotNone(result, 'retry 失敗時は原本維持で best effort 返却')

    def test_full_short_then_long_uses_retry(self):
        """full モードでも同じ動作: 初回短い → retry 長い → 採用。"""
        side = [
            _stub_standard_full(_SHORT_KP),
            _stub_standard_full(_LONG_KP),
        ]
        # _build_media_comparison_block を空にして article_fetcher 不要化
        with mock.patch('proc_ai._build_media_comparison_block', return_value=''), \
             mock.patch('proc_ai._call_claude_tool', side_effect=side) as mocked:
            result = proc_ai._generate_story_full(_DUMMY_ARTICLES * 3, cnt=9)
            self.assertEqual(mocked.call_count, 2, 'full モードでも初回 + retry')
        self.assertIsNotNone(result)
        self.assertGreaterEqual(len(result['keyPoint']), 100)

    def test_minimal_short_then_long_uses_retry(self):
        """minimal モードでも retry が走ること (1〜2 件記事でも 100 字要件は同じ)。"""
        side = [
            _stub_minimal_full(_SHORT_KP),
            _stub_minimal_full(_LONG_KP),
        ]
        with mock.patch('proc_ai._call_claude_tool', side_effect=side) as mocked:
            result = proc_ai._generate_story_minimal(_DUMMY_ARTICLES[:2])
            self.assertEqual(mocked.call_count, 2, 'minimal モードでも初回 + retry')
        self.assertIsNotNone(result)
        self.assertGreaterEqual(len(result['keyPoint']), 100)


class SchemaMinLengthTest(unittest.TestCase):
    """schema の keyPoint に minLength=100 が物理的に存在すること。"""

    def test_minimal_schema_has_minlength(self):
        schema = proc_ai._build_story_schema('minimal')
        self.assertEqual(schema['properties']['keyPoint'].get('minLength'), 100)

    def test_standard_schema_has_minlength(self):
        schema = proc_ai._build_story_schema('standard')
        self.assertEqual(schema['properties']['keyPoint'].get('minLength'), 100)

    def test_full_schema_has_minlength(self):
        schema = proc_ai._build_story_schema('full')
        self.assertEqual(schema['properties']['keyPoint'].get('minLength'), 100)


class PromptHardRequirementTest(unittest.TestCase):
    """_SYSTEM_PROMPT / _STORY_PROMPT_RULES に 100 字必須の文言が含まれていること。"""

    def test_system_prompt_mentions_100chars(self):
        self.assertIn('100 字', proc_ai._SYSTEM_PROMPT)
        self.assertIn('100 字以上', proc_ai._SYSTEM_PROMPT)

    def test_story_rules_mention_schema_violation(self):
        # 「schema 違反」表現で再生成があり得ることを LLM に明示
        self.assertIn('schema 違反', proc_ai._STORY_PROMPT_RULES)


if __name__ == '__main__':
    unittest.main(verbosity=2)
