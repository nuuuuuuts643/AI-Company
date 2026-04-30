"""keyPoint プロンプト・no-retry 仕様の物理ガード。

経緯:
  T2026-0429-J で「200〜300 字物語固定」を強く指示し、minLength=100 のハード下限を入れたが、
  本番 SLI は 2/92 = 2.17% のまま停滞 (2026-04-30 観測)。LLM が無理に 200 字を埋めると
  「一般論で水増し」する症状が発生し、品質が逆に悪化していた。

T-keypoint-prompt (2026-04-30) でフェーズ判定方式へ転換:
  1) _STORY_PROMPT_RULES / _SYSTEM_PROMPT を「フェーズ判定 (記事数) で書き方を変える」方式に書き換え
     - 記事 1 件 = 初動フェーズ: 3 要素 (何が起きたか / なぜ重要か / 今後)
     - 記事 2 件以上 = 変化フェーズ: 4 文構成 (今回の変化 / 以前の状況 / 追加情報 / 意味・今後)
  2) worked example を「関税」「日銀」など具体的な変化を起点にしたものへ差し替え
  3) schema の minLength を 100 → 0 に変更 (「書けない場合は空文字を返す」エスケープを許容)
  4) 100 字以上必須は description / prompt 側のガイドとして残し、書ける場合のみ適用
  5) 旧 retry ロジックは撤去のまま (T2026-0429-J)。再生成によるコスト 2x 増は許容しない

このテストでは API を mock し、以下を物理確認する:
  - generate_story (minimal/standard/full) は **常に 1 回しか _call_claude_tool を呼ばない** (no-retry)
  - keyPoint 短縮時でも結果は dict で返る (None ではなく best effort)
  - worked example (「関税」「日銀」) とフェーズ判定文言が _STORY_PROMPT_RULES に存在
  - schema の minLength=0 (空文字を許容) が維持されていること

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
    """T-keypoint-prompt (2026-04-30): schema の keyPoint は minLength=0 (空文字を許容)。
    PO指示「『何が変わったのか』が書けない場合は生成しない」を物理化するため、
    schema 上は空文字を valid とし、品質ガイドは prompt 側に置く。"""

    def test_minimal_schema_allows_empty(self):
        schema = proc_ai._build_story_schema('minimal')
        self.assertEqual(schema['properties']['keyPoint'].get('minLength'), 0)

    def test_standard_schema_allows_empty(self):
        schema = proc_ai._build_story_schema('standard')
        self.assertEqual(schema['properties']['keyPoint'].get('minLength'), 0)

    def test_full_schema_allows_empty(self):
        schema = proc_ai._build_story_schema('full')
        self.assertEqual(schema['properties']['keyPoint'].get('minLength'), 0)


class PromptHardRequirementTest(unittest.TestCase):
    """_SYSTEM_PROMPT / _STORY_PROMPT_RULES にフェーズ判定とハード要件の文言が含まれていること。"""

    def test_system_prompt_mentions_100chars(self):
        # 100 字以上必須 (書ける場合) のガイドが prompt 側に残っていること。
        self.assertIn('100 字', proc_ai._SYSTEM_PROMPT)

    def test_story_rules_mentions_phase_decision(self):
        # フェーズ判定 (記事数で書き方を変える) の文言があること。
        self.assertIn('フェーズ', proc_ai._STORY_PROMPT_RULES)


class PromptWorkedExampleTest(unittest.TestCase):
    """T-keypoint-prompt (2026-04-30): _STORY_PROMPT_RULES に新しい worked example が埋め込まれていること。

    旧 worked example (「世界モデル」251 字の物語) は「一般論で水増し」誘導の原因となったため撤去。
    新 worked example は「関税」「日銀」などの具体的な変化を起点にしたものへ差し替え。"""

    def test_story_rules_contains_good_example_initial_phase(self):
        # 初動フェーズの良い例 (関税発動) がプロンプトに埋まっていること。
        self.assertIn('60%の追加関税', proc_ai._STORY_PROMPT_RULES)

    def test_story_rules_contains_good_example_change_phase(self):
        # 変化フェーズの良い例 (日銀利上げ) がプロンプトに埋まっていること。
        self.assertIn('利上げ幅を0.25%から0.5%', proc_ai._STORY_PROMPT_RULES)

    def test_story_rules_contains_bad_example_marker(self):
        # 「悪い例」表記が含まれており、対比形式で示されていること。
        self.assertIn('悪い例', proc_ai._STORY_PROMPT_RULES)

    def test_story_rules_mentions_initial_phase_structure(self):
        # 初動フェーズの 3 要素構造 (何が起きたか / なぜ重要か / 今後どうなりそうか) を明示。
        self.assertIn('初動フェーズ', proc_ai._STORY_PROMPT_RULES)
        self.assertIn('何が起きたか', proc_ai._STORY_PROMPT_RULES)

    def test_story_rules_mentions_change_phase_structure(self):
        # 変化フェーズの 4 文構成 (今回の変化 / 以前の状況 / 追加情報 / 意味・今後) を明示。
        self.assertIn('変化フェーズ', proc_ai._STORY_PROMPT_RULES)
        self.assertIn('今回の変化', proc_ai._STORY_PROMPT_RULES)

    def test_story_rules_allows_empty_when_unwritable(self):
        # 「書けない場合は空文字」のエスケープが prompt に書かれていること。
        self.assertIn('空文字', proc_ai._STORY_PROMPT_RULES)


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
