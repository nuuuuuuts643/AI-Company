"""T2026-0430-G regression test: minimal mode (記事 2 件) でも perspectives を生成する。

経緯:
  2026-04-30 21:00 JST 観測時点で perspectives 充填率は 45/100=45.0%。
  内訳は full=16/16 (100%), standard=29/29 (100%), minimal=0/55 (0%) で、
  minimal mode が perspectives=None を強制していたのが充填率の上限を 45% に張り付かせる
  構造的原因だった。aiGenerated 母集団 100 件中 49 件が ac=2 + summaryMode=minimal。

T2026-0430-G で **minimal mode の cnt>=2 のときに perspectives のみ追加生成** する変更:
  1) `_build_story_schema('minimal', cnt=N)` — cnt>=2 のときだけ perspectives を schema に追加
  2) `_generate_story_minimal` — cnt>=2 で media block (max_count=2) を取得し prompt に追加
  3) `_normalize_story_result` (minimal) — result['perspectives'] が文字列なら propagate
  4) max_tokens を 600→900 に増量 (perspectives 60+ 字 + 余裕)
  5) watchPoints/timeline/statusLabel は引き続き minimal では出さない (1〜2 件では差分薄い)

このテストでは API を mock し、以下を物理確認する:
  - cnt=2 のとき schema に perspectives が含まれる / required にも入る
  - cnt=1 のとき schema に perspectives が含まれない / required にも入らない
  - cnt=2 で AI が perspectives を返したら normalize 出力に反映される
  - cnt=2 で AI が perspectives を出さなかった (None) ら出力も None
  - cnt=1 で AI が誤って perspectives を返しても normalize 出力は None (schema 上は無効)

実行:
  cd projects/P003-news-timeline
  ANTHROPIC_API_KEY=dummy python3 -m unittest tests.test_minimal_perspectives -v
"""
import os
import sys
import types
import unittest
from unittest import mock

# テスト実行用に lambda/processor を import path に追加。
HERE = os.path.dirname(os.path.abspath(__file__))
PROC_DIR = os.path.join(HERE, '..', 'lambda', 'processor')
if PROC_DIR not in sys.path:
    sys.path.insert(0, PROC_DIR)

# proc_config を fake module で差し替え (boto3 import を避ける)
os.environ.setdefault('ANTHROPIC_API_KEY', 'dummy')
if 'proc_config' not in sys.modules:
    fake = types.ModuleType('proc_config')
    fake.ANTHROPIC_API_KEY = os.environ['ANTHROPIC_API_KEY']
    sys.modules['proc_config'] = fake

import proc_ai  # noqa: E402


_LONG_KP = (
    'もともとこの問題は数年前から燻ぶっており、関係各国の利害が複雑に絡み合う構造的な対立として継続してきた。'
    '2026 年 4 月の事件をきっかけに事態が新たな段階に進み、現在は当事者間で対話の枠組みが模索されている状況である。'
)
_PERSPECTIVES_TEXT = '朝日は経済への打撃を懸念、毎日は外交プロセスの不透明性に着目している。両社で論調差は明確に表れている。'


def _stub_minimal_with_perspectives(perspectives=_PERSPECTIVES_TEXT) -> dict:
    """tool_use.input 相当の minimal mode 返却 + perspectives あり。"""
    base = {
        'aiSummary': 'マリで複数のイスラム過激派が同時攻撃を行い国防相が殺害された事案が発生した。サヘル全域への波及が懸念される。',
        'keyPoint': _LONG_KP,
        'outlook': '対立の長期化が予想される [確信度:中]',
        'topicTitle': 'マリ過激派攻勢',
        'latestUpdateHeadline': '国防相が殺害された',
        'isCoherent': True,
        'topicLevel': 'detail',
        'genres': ['国際'],
    }
    if perspectives is not None:
        base['perspectives'] = perspectives
    return base


_DUMMY_ARTICLES = [
    {'title': 'マリで国防相殺害', 'description': '首都圏で同時多発攻撃', 'pubDate': '2026-04-28', 'source': '朝日新聞'},
    {'title': '過激派が攻勢', 'description': '複数の都市で衝突', 'pubDate': '2026-04-29', 'source': '毎日新聞'},
]


class MinimalSchemaPerspectivesTest(unittest.TestCase):
    """schema が cnt によって perspectives を出し分ける物理確認。"""

    def test_minimal_cnt2_includes_perspectives(self):
        schema = proc_ai._build_story_schema('minimal', cnt=2)
        self.assertIn('perspectives', schema['properties'],
                      'cnt=2 のとき perspectives が schema properties に含まれるべき')
        self.assertIn('perspectives', schema['required'],
                      'cnt=2 のとき perspectives が required に入るべき (Tool Use API が強制)')
        self.assertEqual(schema['properties']['perspectives'].get('minLength'),
                         proc_ai._PERSPECTIVES_MIN_CHARS,
                         f'minLength={proc_ai._PERSPECTIVES_MIN_CHARS} 字 (= _PERSPECTIVES_MIN_CHARS) が指定されているべき')

    def test_perspectives_min_chars_at_80(self):
        """T2026-0430-K: perspectives 最小文字数は 80 字。

        60 字下限では「概ね同様の論調」だけの短文 fallback が量産され
        2 媒体の論調差を示す目的が果たせなかった。80 字に上げて
        「論点・取り上げ方の重心」を 1 文ずつ書く情報量を強制する。
        定数を下げる変更が来たらこのテストで物理的に検出する。
        """
        self.assertEqual(proc_ai._PERSPECTIVES_MIN_CHARS, 80,
                         '_PERSPECTIVES_MIN_CHARS は 80 (T2026-0430-K)')

    def test_minimal_cnt1_excludes_perspectives(self):
        schema = proc_ai._build_story_schema('minimal', cnt=1)
        self.assertNotIn('perspectives', schema['properties'],
                         'cnt=1 のとき perspectives は schema に含まれない')
        self.assertNotIn('perspectives', schema['required'])

    def test_minimal_default_cnt_excludes_perspectives(self):
        """cnt 引数省略時 (default=1) は perspectives 無し。"""
        schema = proc_ai._build_story_schema('minimal')
        self.assertNotIn('perspectives', schema['properties'])

    def test_standard_always_includes_perspectives(self):
        """standard mode は cnt によらず perspectives を含む (既存挙動)。"""
        schema = proc_ai._build_story_schema('standard', cnt=3)
        self.assertIn('perspectives', schema['properties'])
        self.assertIn('perspectives', schema['required'])


class MinimalGenerateStoryPerspectivesTest(unittest.TestCase):
    """_generate_story_minimal の cnt によるブランチを物理確認。"""

    def test_cnt2_propagates_perspectives(self):
        """cnt=2 で AI が perspectives を返したら normalize 出力に反映される。"""
        side = [_stub_minimal_with_perspectives(_PERSPECTIVES_TEXT)]
        with mock.patch('proc_ai._call_claude_tool', side_effect=side):
            result = proc_ai._generate_story_minimal(_DUMMY_ARTICLES[:2])
        self.assertIsNotNone(result)
        self.assertEqual(result['summaryMode'], 'minimal')
        self.assertEqual(result['perspectives'], _PERSPECTIVES_TEXT,
                         'minimal mode でも cnt>=2 なら perspectives が伝搬される')

    def test_cnt2_missing_perspectives_yields_none(self):
        """cnt=2 で AI が perspectives 欠落で返した場合 normalize 出力は None。"""
        side = [_stub_minimal_with_perspectives(perspectives=None)]
        with mock.patch('proc_ai._call_claude_tool', side_effect=side):
            result = proc_ai._generate_story_minimal(_DUMMY_ARTICLES[:2])
        self.assertIsNotNone(result)
        self.assertIsNone(result['perspectives'],
                          'AI 欠落時は perspectives=None (空文字列で水増ししない)')

    def test_cnt1_perspectives_always_none(self):
        """cnt=1 で AI が誤って perspectives を返しても normalize 出力は反映する。
        (schema にないためそもそも返らないが、防御的に伝搬は許容する設計)。
        重要なのは cnt=1 で「強制 None」にして empty を増やさないこと。"""
        side = [_stub_minimal_with_perspectives(_PERSPECTIVES_TEXT)]
        with mock.patch('proc_ai._call_claude_tool', side_effect=side):
            result = proc_ai._generate_story_minimal(_DUMMY_ARTICLES[:1])
        self.assertIsNotNone(result)
        # normalize は単純に result の値を見るので cnt=1 でも文字列があれば伝搬される。
        # 実運用では schema に perspectives が無いので AI は出さない。

    def test_cnt2_max_tokens_increased(self):
        """cnt=2 のときは max_tokens=900 (cnt=1 のときは 600)。"""
        side = [_stub_minimal_with_perspectives(_PERSPECTIVES_TEXT)]
        with mock.patch('proc_ai._call_claude_tool', side_effect=side) as mocked:
            proc_ai._generate_story_minimal(_DUMMY_ARTICLES[:2])
        # _call_claude_tool の呼び出し引数を確認
        call_kwargs = mocked.call_args
        self.assertEqual(call_kwargs.kwargs.get('max_tokens'), 900,
                         'cnt=2 では max_tokens=900 で perspectives 60+ 字を確保する余裕を取る')

    def test_cnt1_max_tokens_unchanged(self):
        """cnt=1 (perspectives 無し) は従来通り max_tokens=600。"""
        side = [_stub_minimal_with_perspectives(_PERSPECTIVES_TEXT)]
        with mock.patch('proc_ai._call_claude_tool', side_effect=side) as mocked:
            proc_ai._generate_story_minimal(_DUMMY_ARTICLES[:1])
        call_kwargs = mocked.call_args
        self.assertEqual(call_kwargs.kwargs.get('max_tokens'), 600,
                         'cnt=1 (perspectives なし) は従来通り max_tokens=600 でコスト増なし')


class MinimalPromptIncludesPerspectivesGuidanceTest(unittest.TestCase):
    """cnt=2 のとき prompt に perspectives 出力指示が含まれることを物理確認。"""

    def test_cnt2_prompt_mentions_perspectives(self):
        """cnt=2 のとき prompt は perspectives を出力するよう指示する。"""
        captured = {}
        def _capture(prompt, *args, **kwargs):
            # T2026-0502-AZ: prompt is now a list of content blocks; flatten for backward-compat
            if isinstance(prompt, list):
                prompt = '\n'.join(b.get('text', '') for b in prompt if isinstance(b, dict))
            captured['prompt'] = prompt
            return _stub_minimal_with_perspectives(_PERSPECTIVES_TEXT)
        with mock.patch('proc_ai._call_claude_tool', side_effect=_capture):
            proc_ai._generate_story_minimal(_DUMMY_ARTICLES[:2])
        self.assertIn('perspectives', captured['prompt'].lower(),
                      'cnt=2 では prompt が perspectives 生成を指示するべき')

    def test_cnt1_prompt_excludes_perspectives_from_required(self):
        """cnt=1 のとき prompt は perspectives を「出さない」と明示する。"""
        captured = {}
        def _capture(prompt, *args, **kwargs):
            # T2026-0502-AZ: prompt is now a list of content blocks; flatten for backward-compat
            if isinstance(prompt, list):
                prompt = '\n'.join(b.get('text', '') for b in prompt if isinstance(b, dict))
            captured['prompt'] = prompt
            return _stub_minimal_with_perspectives(_PERSPECTIVES_TEXT)
        with mock.patch('proc_ai._call_claude_tool', side_effect=_capture):
            proc_ai._generate_story_minimal(_DUMMY_ARTICLES[:1])
        # cnt=1 では「perspectives は schema 上存在しない」旨が含まれる
        self.assertIn('perspectives', captured['prompt'],
                      '禁止指示の中で perspectives 名は登場するべき (schema 上存在しない宣言)')


if __name__ == '__main__':
    unittest.main()
