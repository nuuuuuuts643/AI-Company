"""T2026-0429-J regression test: keyPoint プロンプト強化 + no-retry 仕様の物理ガード。

背景 (2026-04-29 自律巡回 SLI 実測):
  本番 topics.json で keyPoint 100 字以上は 2/92 = 2.17% のみ。平均 35.6 字で
  大半が「タイトル風一行」(例: 19〜36 字)。LLM が aiSummary や latestUpdateHeadline と
  役割を混同しているのが第一原因。

修正の中身 (T2026-0429-J):
  1) _STORY_PROMPT_RULES / _SYSTEM_PROMPT に「200 字以上 300 字以内 (目標)」を最重要要件として強調
  2) _STORY_PROMPT_RULES に worked example (251 字の良い例 + 19/36 字の悪い例) を埋め込み、
     LLM に「目標尺」を物理的に提示する
  3) schema の keyPoint に minLength=100 を付与 (ハード下限・先行修正 KP3 から維持)
  4) ★ 旧 retry ロジック (_retry_short_keypoint) は撤去 — PO指示によりコスト 2x 増を許容しない
  5) ポスト生成で _emit_keypoint_metric が CloudWatch ログにメトリクスを残す (警告のみ)

このテストでは API を mock し、以下を物理確認する:
  - generate_story (minimal/standard/full) は **常に 1 回しか _call_claude_tool を呼ばない** (no-retry)
  - keyPoint 短縮時でも結果は dict で返る (None ではなく best effort)
  - worked example (「世界モデル」) と「200 字以上 300 字以内」が _SYSTEM_PROMPT または _STORY_PROMPT_RULES に存在
  - schema の minLength=100 が維持されていること

実行:
  cd projects/P003-news-timeline
  ANTHROPIC_API_KEY=dummy python3 -m unittest tests.test_keypoint_retry -v
"""
import os
import sys
import types
import unittest
from unittest import mock

os.environ.setdefault('ANTHROPIC_API_KEY', '***REDACTED-SEC3***')

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


class GenerateStoryNoRetryTest(unittest.TestCase):
    """T2026-0429-J: 旧 retry 撤去後の no-retry contract test。
    どのモードでも _call_claude_tool は 1 回しか呼ばれず、コスト増を起こさない。"""

    def test_standard_short_keypoint_no_retry(self):
        """初回 17 字 → retry なし (1 回だけ呼ばれる)。短くても dict で best effort 返却。"""
        side = [_stub_standard_full(_SHORT_KP)]
        with mock.patch('proc_ai._call_claude_tool', side_effect=side) as mocked:
            result = proc_ai._generate_story_standard(_DUMMY_ARTICLES, cnt=3)
            self.assertEqual(mocked.call_count, 1, '再生成は撤去されたので必ず 1 回のみ')
        self.assertIsNotNone(result, '短くても dict は返ること (None ではない)')

    def test_standard_long_first_single_call(self):
        """初回 150 字 → 元々 1 回のはず。回帰検証。"""
        side = [_stub_standard_full(_LONG_KP)]
        with mock.patch('proc_ai._call_claude_tool', side_effect=side) as mocked:
            result = proc_ai._generate_story_standard(_DUMMY_ARTICLES, cnt=3)
            self.assertEqual(mocked.call_count, 1, '正常生成は当然 1 回のみ')
        self.assertIsNotNone(result)
        self.assertGreaterEqual(len(result['keyPoint']), 100)

    def test_full_short_keypoint_no_retry(self):
        """full モードでも no-retry: 1 回のみ呼ばれる。"""
        side = [_stub_standard_full(_SHORT_KP)]
        with mock.patch('proc_ai._build_media_comparison_block', return_value=''), \
             mock.patch('proc_ai._call_claude_tool', side_effect=side) as mocked:
            result = proc_ai._generate_story_full(_DUMMY_ARTICLES * 3, cnt=9)
            self.assertEqual(mocked.call_count, 1, 'full モードでも 1 回のみ')
        self.assertIsNotNone(result)

    def test_minimal_short_keypoint_no_retry(self):
        """minimal モードでも no-retry: 1 回のみ呼ばれる。"""
        side = [_stub_minimal_full(_SHORT_KP)]
        with mock.patch('proc_ai._call_claude_tool', side_effect=side) as mocked:
            result = proc_ai._generate_story_minimal(_DUMMY_ARTICLES[:2])
            self.assertEqual(mocked.call_count, 1, 'minimal モードでも 1 回のみ')
        self.assertIsNotNone(result)

    def test_retry_function_removed(self):
        """旧 _retry_short_keypoint シンボル自体が proc_ai から削除されていること。"""
        self.assertFalse(
            hasattr(proc_ai, '_retry_short_keypoint'),
            '_retry_short_keypoint は T2026-0429-J で撤去されているべき (コスト抑制)',
        )


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

    def test_story_rules_mention_schema_violation(self):
        self.assertIn('schema 違反', proc_ai._STORY_PROMPT_RULES)


class PromptWorkedExampleTest(unittest.TestCase):
    """T2026-0429-J: _STORY_PROMPT_RULES に worked example (良い例 / 悪い例) が埋め込まれていること。"""

    def test_story_rules_contains_good_example_keyword(self):
        # 良い例の本文の一部 (「世界モデル」) がプロンプトに埋まっていることで、
        # LLM に 251 字レンジの目標尺が物理的に提示されている。
        self.assertIn('世界モデル', proc_ai._STORY_PROMPT_RULES)

    def test_story_rules_contains_bad_example_marker(self):
        # 「悪い例」表記が含まれており、対比形式で示されていること。
        self.assertIn('悪い例', proc_ai._STORY_PROMPT_RULES)

    def test_story_rules_target_range_200_300(self):
        # 「200 字以上 300 字以内」を目標として明示。
        self.assertIn('200 字以上 300 字以内', proc_ai._STORY_PROMPT_RULES)


class EmitKeypointMetricTest(unittest.TestCase):
    """T2026-0429-J: _emit_keypoint_metric が CloudWatch 想定の固定フォーマットを print すること。"""

    def test_metric_format_long(self):
        from io import StringIO
        buf = StringIO()
        with mock.patch('sys.stdout', buf):
            proc_ai._emit_keypoint_metric('standard', 'あ' * 250, retried=False)
        out = buf.getvalue()
        self.assertIn('[METRIC] keypoint_len', out)
        self.assertIn('mode=standard', out)
        self.assertIn('len=250', out)
        self.assertIn('ge100=1', out)
        self.assertIn('ge200=1', out)
        self.assertIn('retried=0', out)

    def test_metric_format_short(self):
        from io import StringIO
        buf = StringIO()
        with mock.patch('sys.stdout', buf):
            proc_ai._emit_keypoint_metric('minimal', 'short', retried=False)
        out = buf.getvalue()
        self.assertIn('len=5', out)
        self.assertIn('ge100=0', out)
        self.assertIn('ge200=0', out)

    def test_metric_format_none_or_empty(self):
        from io import StringIO
        buf = StringIO()
        with mock.patch('sys.stdout', buf):
            proc_ai._emit_keypoint_metric('full', None, retried=False)
            proc_ai._emit_keypoint_metric('full', '', retried=False)
        out = buf.getvalue()
        # None / 空文字いずれも len=0 として出力される
        self.assertIn('len=0', out)


if __name__ == '__main__':
    unittest.main(verbosity=2)
