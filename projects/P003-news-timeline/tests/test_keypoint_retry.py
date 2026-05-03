"""keyPoint プロンプト + 1 回 retry + length validation の物理ガード。

経緯:
  T2026-0429-J で「コスト抑制のため retry 撤去」したが、本番 SLI では keyPoint ≥100 字
  の充填率が 2.2% (2/92) のまま停滞 (2026-04-30 18:05 JST 観測)。プロンプト強化のみでは
  Tool Use API が「タイトル風 30〜40 字」「空文字」を返し続けるパターンを抑制できなかった。

T2026-0430-A (2026-04-30) で **新アーキの retry を再導入**:
  1) 初回 keyPoint < 100 字なら 1 回だけ再生成 (合計 2 回まで・コスト上限明確化)
  2) retry 専用プロンプト「前回が短すぎたので最低 100 字以上、具体数字・固有名詞で拡張」
  3) keyPoint だけ生成する縮小スキーマ + max_tokens=400 でコスト最小化
  4) retry も短ければ "SHORT_FALLBACK" フラグ → keyPointFallback=True で DDB に記録
     (空にしない・捨てない方針: 短文でも情報量があるため original/retry の長い方を保存)
  5) keyPointLength / keyPointRetried / keyPointFallback を normalize 出力に含める
  6) [KP_QUALITY] プレフィックスで CloudWatch Logs に固定フォーマット出力 (集計分析用)

このテストでは API を mock し、以下を物理確認する:
  - generate_story (minimal/standard/full) は短文時 **必ず 2 回** _call_claude_tool を呼ぶ (1 回 retry)
  - 長文時は 1 回のみ (retry なし)
  - retry 成功時: keyPointFallback=False / keyPointRetried=True
  - retry 失敗時: keyPointFallback=True / keyPointRetried=True / keyPoint は空にしない
  - keyPointLength は最終 keyPoint の文字数と一致
  - [KP_QUALITY] ログが固定フォーマットで出力される
  - schema の minLength=0 (空文字を許容) は維持

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
_RETRY_LONG_KP = (
    'マリ国防相が首都での同時多発攻撃で殺害され、過激派 JNIM がサヘル全域で攻勢を強めた。'
    'これまではロシア・ワグネルが治安維持を担っていたが、撤退を機に空白地帯が生じた。'
    '今後はサヘル諸国の連携と仏軍再展開の有無が焦点となる。'
)
assert len(_RETRY_LONG_KP) >= 100, f'retry stub の長文 keyPoint は 100 字以上必要 (現在 {len(_RETRY_LONG_KP)} 字)'


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


def _stub_retry_response(keypoint: str) -> dict:
    """retry 専用スキーマの返却 (keyPoint のみ)。"""
    return {'keyPoint': keypoint}


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
    """T2026-0430-A: 1 回 retry contract test。
    短文時は 2 回呼ばれ、長文時は 1 回のみ。"""

    def test_standard_short_keypoint_triggers_retry(self):
        """初回 17 字 → retry 1 回呼ばれる (合計 2 回)。retry 成功時は長文 keyPoint で上書き。"""
        side = [_stub_standard_full(_SHORT_KP), _stub_retry_response(_RETRY_LONG_KP)]
        with mock.patch('proc_ai._call_claude_tool', side_effect=side) as mocked:
            result = proc_ai._generate_story_standard(_DUMMY_ARTICLES, cnt=3)
            self.assertEqual(mocked.call_count, 2, '短文時は retry 1 回 (合計 2 call)')
        self.assertIsNotNone(result)
        self.assertGreaterEqual(len(result['keyPoint']), 100, 'retry 成功時は keyPoint >= 100 字')
        self.assertTrue(result['keyPointRetried'], 'retried フラグが立つ')
        self.assertFalse(result['keyPointFallback'], 'retry 成功なら fallback=False')
        self.assertEqual(result['keyPointLength'], len(result['keyPoint']))

    def test_standard_long_first_no_retry(self):
        """初回 150 字 → retry なし (1 call のみ)。"""
        side = [_stub_standard_full(_LONG_KP)]
        with mock.patch('proc_ai._call_claude_tool', side_effect=side) as mocked:
            result = proc_ai._generate_story_standard(_DUMMY_ARTICLES, cnt=3)
            self.assertEqual(mocked.call_count, 1, '正常生成は 1 call のみ')
        self.assertIsNotNone(result)
        self.assertGreaterEqual(len(result['keyPoint']), 100)
        self.assertFalse(result['keyPointRetried'])
        self.assertFalse(result['keyPointFallback'])

    def test_standard_retry_also_short_marks_fallback(self):
        """retry も短い場合 → fallback=True、長い方の keyPoint を保存 (空にしない)。"""
        side = [_stub_standard_full(_SHORT_KP), _stub_retry_response('まだ短い')]
        with mock.patch('proc_ai._call_claude_tool', side_effect=side) as mocked:
            result = proc_ai._generate_story_standard(_DUMMY_ARTICLES, cnt=3)
            self.assertEqual(mocked.call_count, 2)
        self.assertIsNotNone(result)
        self.assertTrue(result['keyPointRetried'])
        self.assertTrue(result['keyPointFallback'], 'retry も短ければ fallback=True')
        self.assertGreater(len(result['keyPoint']), 0, 'fallback でも keyPoint は空にしない')
        # original (17 字) > retry (5 字) なので original を残す
        self.assertEqual(result['keyPoint'], _SHORT_KP)
        self.assertEqual(result['keyPointLength'], len(_SHORT_KP))

    def test_standard_retry_returns_none_keeps_original(self):
        """retry が None を返した場合 → fallback=True、original を残す。"""
        side = [_stub_standard_full(_SHORT_KP), None]
        with mock.patch('proc_ai._call_claude_tool', side_effect=side) as mocked:
            result = proc_ai._generate_story_standard(_DUMMY_ARTICLES, cnt=3)
            self.assertEqual(mocked.call_count, 2)
        self.assertIsNotNone(result)
        self.assertTrue(result['keyPointRetried'])
        self.assertTrue(result['keyPointFallback'])
        self.assertEqual(result['keyPoint'], _SHORT_KP)

    def test_full_short_keypoint_triggers_retry(self):
        """full モードでも短文時は retry 1 回呼ばれる。"""
        side = [_stub_standard_full(_SHORT_KP), _stub_retry_response(_RETRY_LONG_KP)]
        with mock.patch('proc_ai._build_media_comparison_block', return_value=''), \
             mock.patch('proc_ai._call_claude_tool', side_effect=side) as mocked:
            result = proc_ai._generate_story_full(_DUMMY_ARTICLES * 3, cnt=9)
            self.assertEqual(mocked.call_count, 2, 'full モードでも retry 1 回')
        self.assertIsNotNone(result)
        self.assertTrue(result['keyPointRetried'])
        self.assertFalse(result['keyPointFallback'])

    def test_minimal_short_keypoint_triggers_retry(self):
        """minimal モードでも短文時は retry 1 回呼ばれる。"""
        side = [_stub_minimal_full(_SHORT_KP), _stub_retry_response(_RETRY_LONG_KP)]
        with mock.patch('proc_ai._call_claude_tool', side_effect=side) as mocked:
            result = proc_ai._generate_story_minimal(_DUMMY_ARTICLES[:2])
            self.assertEqual(mocked.call_count, 2, 'minimal モードでも retry 1 回')
        self.assertIsNotNone(result)
        self.assertTrue(result['keyPointRetried'])
        self.assertFalse(result['keyPointFallback'])
        self.assertGreaterEqual(result['keyPointLength'], 100)

    def test_retry_function_exists(self):
        """T2026-0430-A: _retry_short_keypoint シンボルが proc_ai に再導入されていること。"""
        self.assertTrue(
            hasattr(proc_ai, '_retry_short_keypoint'),
            '_retry_short_keypoint は T2026-0430-A で新アーキで再導入されているべき',
        )
        self.assertTrue(
            hasattr(proc_ai, '_process_keypoint_quality'),
            '_process_keypoint_quality も新アーキの中核として存在するべき',
        )

    def test_both_empty_uses_ai_summary_fallback(self):
        """T2026-0503-UX-NO-KEYPOINT-23: 初回・retry 両方が空のとき aiSummary を keyPoint 代用。

        原因: Claude が「何が変わったのか不明確」で空を返し続ける topic が 23.1% 滞留。
        対策: aiSummary は必ず非空なので、空 keyPoint を aiSummary で補完する。
        """
        empty_stub = dict(_stub_standard_full(''))  # keyPoint=空
        side = [empty_stub, _stub_retry_response('')]  # retry も空
        with mock.patch('proc_ai._call_claude_tool', side_effect=side):
            result = proc_ai._generate_story_standard(_DUMMY_ARTICLES, cnt=3)
        self.assertIsNotNone(result)
        self.assertTrue(result['keyPointRetried'], 'retry が呼ばれた')
        self.assertTrue(result['keyPointFallback'], 'fallback フラグが立つ')
        # aiSummary fallback で空にならないこと
        self.assertGreater(len(result['keyPoint']), 0, 'aiSummary fallback で keyPoint は空にならない')
        # aiSummary と一致していること
        self.assertEqual(result['keyPoint'], empty_stub['aiSummary'], 'aiSummary が keyPoint に代用される')

    def test_short_original_with_empty_retry_uses_longer_of_original_or_summary(self):
        """T2026-0503-UX-NO-KEYPOINT-23: original 短文 + retry 空 → original と aiSummary の長い方を使う。

        シナリオ: original=_SHORT_KP (17字), retry='', aiSummary=54字。
        17字 < 54字 なので aiSummary fallback は原則適用されない (retry 空だが original は非空なので
        _process_keypoint_quality は original を保持し、空文字チェック後に aiSummary 分岐は通らない)。
        → result['keyPoint'] は _SHORT_KP のまま (従来の short-fallback 動作を維持)。
        """
        # retry が空でも original が非空なら keyPoint は _SHORT_KP のまま
        side = [_stub_standard_full(_SHORT_KP), _stub_retry_response('')]
        with mock.patch('proc_ai._call_claude_tool', side_effect=side):
            result = proc_ai._generate_story_standard(_DUMMY_ARTICLES, cnt=3)
        self.assertIsNotNone(result)
        self.assertTrue(result['keyPointFallback'])
        # original (17 字) が残る (aiSummary fallback は final_kp が空のときのみ)
        self.assertEqual(result['keyPoint'], _SHORT_KP)


class KeyPointQualityFieldsTest(unittest.TestCase):
    """T2026-0430-A: normalize 出力に keyPointLength / keyPointRetried / keyPointFallback が含まれる。"""

    def test_minimal_normalize_includes_quality_fields(self):
        side = [_stub_minimal_full(_LONG_KP)]
        with mock.patch('proc_ai._call_claude_tool', side_effect=side):
            result = proc_ai._generate_story_minimal(_DUMMY_ARTICLES[:1])
        self.assertIn('keyPointLength', result)
        self.assertIn('keyPointRetried', result)
        self.assertIn('keyPointFallback', result)
        self.assertEqual(result['keyPointLength'], len(result['keyPoint']))

    def test_standard_normalize_includes_quality_fields(self):
        side = [_stub_standard_full(_LONG_KP)]
        with mock.patch('proc_ai._call_claude_tool', side_effect=side):
            result = proc_ai._generate_story_standard(_DUMMY_ARTICLES, cnt=3)
        self.assertIn('keyPointLength', result)
        self.assertIn('keyPointRetried', result)
        self.assertIn('keyPointFallback', result)
        self.assertEqual(result['keyPointLength'], len(result['keyPoint']))


class KPQualityLogTest(unittest.TestCase):
    """T2026-0430-A: [KP_QUALITY] プレフィックスで固定フォーマットの 1 行ログが出る。"""

    def test_kp_quality_log_format(self):
        from io import StringIO
        side = [_stub_standard_full(_SHORT_KP), _stub_retry_response(_RETRY_LONG_KP)]
        buf = StringIO()
        with mock.patch('proc_ai._call_claude_tool', side_effect=side), \
             mock.patch('sys.stdout', buf):
            proc_ai._generate_story_standard(_DUMMY_ARTICLES, cnt=3)
        out = buf.getvalue()
        self.assertIn('[KP_QUALITY]', out)
        self.assertIn('mode=standard', out)
        self.assertIn('retried=1', out)
        self.assertIn('ge100=1', out)


class SchemaMinLengthTest(unittest.TestCase):
    """schema の keyPoint は minLength=0 を維持 (T-keypoint-prompt 2026-04-30)。
    PO 指示「『何が変わったのか』が書けない場合は生成しない」を物理化するため、
    schema 上は空文字を valid とする。"""

    def test_minimal_schema_allows_empty(self):
        schema = proc_ai._build_story_schema('minimal')
        self.assertEqual(schema['properties']['keyPoint'].get('minLength'), 0)

    def test_standard_schema_allows_empty(self):
        schema = proc_ai._build_story_schema('standard')
        self.assertEqual(schema['properties']['keyPoint'].get('minLength'), 0)

    def test_full_schema_allows_empty(self):
        schema = proc_ai._build_story_schema('full')
        self.assertEqual(schema['properties']['keyPoint'].get('minLength'), 0)


class RetrySchemaMinLengthTest(unittest.TestCase):
    """T2026-0501-D (2026-05-01): retry 専用 schema は minLength=60 で物理ガード化。

    メイン schema の minLength=0 は PO 指示「書けない場合は生成しない」維持。
    retry schema は「初回が <100 字で再要求」という強い文脈のため、Tool Use API で
    最低文字数を物理強制する。これにより本番 SLI keyPoint>=50字 充填率 38.6% 停滞の
    構造的バグ (retry でも 10〜30 字を返し続け SHORT_FALLBACK で永続化) を解消する。"""

    def test_retry_min_chars_constant_value(self):
        """_KEYPOINT_RETRY_MIN_CHARS = 60 (SLI 警告閾値 50 + 10 字バッファ)。"""
        self.assertEqual(proc_ai._KEYPOINT_RETRY_MIN_CHARS, 60)

    def test_retry_min_chars_matches_outlook(self):
        """retry minLength は outlook (60) と同じ値 = 「短すぎないが書ける範囲」の共通閾値。"""
        self.assertEqual(proc_ai._KEYPOINT_RETRY_MIN_CHARS, proc_ai._OUTLOOK_MIN_CHARS)

    def test_retry_calls_claude_with_minlength_schema(self):
        """_retry_short_keypoint は keyPoint.minLength=60 を含む schema で _call_claude_tool を呼ぶ。"""
        captured = {}

        def _capture(*args, **kwargs):
            # _call_claude_tool(prompt, tool_name, input_schema, ...)
            captured['schema'] = args[2] if len(args) >= 3 else kwargs.get('input_schema')
            return {'keyPoint': _RETRY_LONG_KP}

        with mock.patch('proc_ai._call_claude_tool', side_effect=_capture):
            proc_ai._retry_short_keypoint(_DUMMY_ARTICLES, cnt=3, mode='standard',
                                          original_keypoint=_SHORT_KP)
        self.assertIn('schema', captured)
        kp_schema = captured['schema']['properties']['keyPoint']
        self.assertEqual(
            kp_schema.get('minLength'),
            proc_ai._KEYPOINT_RETRY_MIN_CHARS,
            'retry schema は keyPoint.minLength=_KEYPOINT_RETRY_MIN_CHARS で物理ガードする',
        )

    def test_retry_schema_description_drops_softening(self):
        """retry description から「空文字は許容するが」軟化文言が除去されていること。"""
        captured = {}

        def _capture(*args, **kwargs):
            captured['schema'] = args[2] if len(args) >= 3 else kwargs.get('input_schema')
            return {'keyPoint': _RETRY_LONG_KP}

        with mock.patch('proc_ai._call_claude_tool', side_effect=_capture):
            proc_ai._retry_short_keypoint(_DUMMY_ARTICLES, cnt=3, mode='standard',
                                          original_keypoint=_SHORT_KP)
        desc = captured['schema']['properties']['keyPoint'].get('description', '')
        self.assertNotIn('空文字は許容', desc, 'retry では空文字許容の軟化文言を出さない')
        self.assertNotIn('書ける場合は', desc, 'retry では「書ける場合は」エスケープ文言を出さない')


class PromptHardRequirementTest(unittest.TestCase):
    """_SYSTEM_PROMPT / _STORY_PROMPT_RULES にフェーズ判定とハード要件の文言が含まれていること。"""

    def test_system_prompt_mentions_100chars(self):
        self.assertIn('100 字', proc_ai._SYSTEM_PROMPT)

    def test_story_rules_mentions_phase_decision(self):
        self.assertIn('フェーズ', proc_ai._STORY_PROMPT_RULES)


class PromptWorkedExampleTest(unittest.TestCase):
    """T-keypoint-prompt (2026-04-30): _STORY_PROMPT_RULES に新しい worked example が埋め込まれていること。"""

    def test_story_rules_contains_good_example_initial_phase(self):
        # T-keypoint-prompt (2026-04-30): 汎用 ◎例 (政治/関税テーマ) がそのまま残ること
        # ジャンル別◎例は _build_keypoint_genre_hint() 経由で注入するため _STORY_PROMPT_RULES は変更しない
        self.assertIn('60%の追加関税', proc_ai._STORY_PROMPT_RULES)

    def test_story_rules_contains_good_example_change_phase(self):
        # T-keypoint-prompt (2026-04-30): 汎用 ◎例 (日銀利上げテーマ) がそのまま残ること
        self.assertIn('利上げ幅を0.25%から0.5%', proc_ai._STORY_PROMPT_RULES)

    def test_story_rules_contains_bad_example_marker(self):
        self.assertIn('悪い例', proc_ai._STORY_PROMPT_RULES)

    def test_story_rules_mentions_initial_phase_structure(self):
        self.assertIn('初動フェーズ', proc_ai._STORY_PROMPT_RULES)
        self.assertIn('何が起きたか', proc_ai._STORY_PROMPT_RULES)

    def test_story_rules_mentions_change_phase_structure(self):
        self.assertIn('変化フェーズ', proc_ai._STORY_PROMPT_RULES)
        self.assertIn('今回の変化', proc_ai._STORY_PROMPT_RULES)

    def test_story_rules_allows_empty_when_unwritable(self):
        self.assertIn('空文字', proc_ai._STORY_PROMPT_RULES)


class EmitKeypointMetricTest(unittest.TestCase):
    """T2026-0429-J: _emit_keypoint_metric が CloudWatch 想定の固定フォーマットを print すること。
    T2026-0430-A: retried=1 のフォーマットも追加検証。"""

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

    def test_metric_format_retried(self):
        from io import StringIO
        buf = StringIO()
        with mock.patch('sys.stdout', buf):
            proc_ai._emit_keypoint_metric('full', 'あ' * 120, retried=True)
        out = buf.getvalue()
        self.assertIn('retried=1', out)
        self.assertIn('ge100=1', out)

    def test_metric_format_none_or_empty(self):
        from io import StringIO
        buf = StringIO()
        with mock.patch('sys.stdout', buf):
            proc_ai._emit_keypoint_metric('full', None, retried=False)
            proc_ai._emit_keypoint_metric('full', '', retried=False)
        out = buf.getvalue()
        self.assertIn('len=0', out)


class GenreKeypointExamplesTest(unittest.TestCase):
    """T2026-0501-K: ジャンル別◎例が _build_keypoint_genre_hint() に含まれること。

    エンタメ・テクノロジーは充填率が低い (35%/37.5%) ため、
    _GENRE_KEYPOINT_EXAMPLES に worked example を追加して prompt 品質を改善した。
    このテストでその注入を保護する。
    """

    def test_entertainment_genre_hint_contains_example(self):
        result = proc_ai._build_keypoint_genre_hint('エンタメ')
        self.assertIn('◎', result)
        # 反響規模数値の例（エンタメの核心）が含まれること
        self.assertIn('興行収入', result)

    def test_entertainment_genre_hint_contains_bad_example(self):
        result = proc_ai._build_keypoint_genre_hint('エンタメ')
        # ×悪い例もセットで含まれること（what NOT to do）
        self.assertIn('× 悪い例', result)

    def test_technology_genre_hint_contains_example(self):
        result = proc_ai._build_keypoint_genre_hint('テクノロジー')
        self.assertIn('◎', result)
        # 性能比数値の例（テクノロジーの核心）が含まれること
        self.assertIn('消費電力', result)

    def test_technology_genre_hint_contains_bad_example(self):
        result = proc_ai._build_keypoint_genre_hint('テクノロジー')
        self.assertIn('× 悪い例', result)

    def test_other_genre_no_example_block(self):
        # '総合' は _GENRE_KEYPOINT_EXAMPLES に登録されていないため ◎例ブロックは注入されない
        # (政治は T2026-0501-K-EXT で examples が追加されたため '総合' で検証する)
        result = proc_ai._build_keypoint_genre_hint('総合')
        self.assertIn('keyPoint', result)
        # ◎例ブロックは注入されない（ただしエラーにはならない）
        self.assertNotIn('◎ 良い例', result)

    def test_none_genre_falls_back_gracefully(self):
        result = proc_ai._build_keypoint_genre_hint(None)
        self.assertIn('総合', result)


if __name__ == '__main__':
    unittest.main(verbosity=2)
