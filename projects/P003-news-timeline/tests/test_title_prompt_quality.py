"""T2026-0501-C: generate_title プロンプトに「角度・緊張感」誘導と
リーガル制約・ジャンルヒントが残っているかの回帰テスト。

PO 指摘 (2026-05-01):
  - 「タイトルが平坦で惹きがない」→ 角度+緊張感プロンプト追加
  - 「正確性・名誉毀損リスク」→ リーガル制約プロンプト追加
  - 「ジャンル別プロンプト分岐の足場」→ generate_title(articles, genre) 引数追加

プロンプトが将来「無難な要約」に薄まらないよう、キーフレーズが残っていることを物理ガードする。

実行:
  cd projects/P003-news-timeline
  ANTHROPIC_API_KEY=dummy python3 tests/test_title_prompt_quality.py -v
"""
import json
import os
import sys
import types
import unittest
from unittest import mock

os.environ.setdefault('ANTHROPIC_API_KEY', '***REDACTED-SEC3***')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'lambda', 'processor'))

if 'proc_config' not in sys.modules:
    fake = types.ModuleType('proc_config')
    fake.ANTHROPIC_API_KEY = os.environ['ANTHROPIC_API_KEY']
    sys.modules['proc_config'] = fake

import proc_ai  # noqa: E402


class _FakeResponse:
    def __init__(self, body):
        self._body = body if isinstance(body, bytes) else json.dumps(body).encode('utf-8')

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body


class TitlePromptQualityTest(unittest.TestCase):
    """generate_title が Claude API に送るプロンプトの中身を検証する。"""

    @staticmethod
    def _capture_prompt(articles, genre=None):
        captured = {}

        def fake_urlopen(req, *a, **kw):
            payload = json.loads(req.data.decode('utf-8'))
            captured['prompt'] = payload['messages'][0]['content']
            return _FakeResponse({'content': [{'text': 'ダミータイトル、市場に衝撃の反応'}]})

        with mock.patch('proc_ai.urllib.request.urlopen', side_effect=fake_urlopen):
            with mock.patch('proc_ai.time.sleep', return_value=None):
                proc_ai.generate_title(articles, genre=genre)
        return captured.get('prompt', '')

    def test_prompt_includes_tension_guidance(self):
        """プロンプトに「角度と緊張感」「続きを読みたい」が含まれている (回帰防止)。"""
        prompt = self._capture_prompt([{'title': 'テスト記事1'}, {'title': 'テスト記事2'}])
        self.assertIn('続きを読みたい', prompt, 'hook 文言が削除されている')
        self.assertIn('角度と緊張感', prompt, 'tension 誘導が削除されている')

    def test_prompt_forbids_flat_endings(self):
        """禁止表現 (〜が発表 / 〜を決定 / 〜まとめ / 〜の動き) が明示されている。"""
        prompt = self._capture_prompt([{'title': '何か'}])
        for forbidden in ('〜が発表', '〜を決定', '〜まとめ', '〜の動き'):
            self.assertIn(forbidden, prompt, f'禁止パターン {forbidden} が抜けた')

    def test_prompt_includes_concrete_bad_to_good_examples(self):
        """❌→✅ の改善例ペアが残っている。プロンプトの「教師信号」の核。"""
        prompt = self._capture_prompt([{'title': 'X'}])
        self.assertIn('米GDP、予想割れ2.0%', prompt, 'GDP 改善例が消失')
        self.assertIn('電撃決定', prompt, '電撃決定 例が消失')

    def test_prompt_demands_numbers_when_present(self):
        """数字を入れる指示が残っている (惹きの最大要因)。"""
        prompt = self._capture_prompt([{'title': 'X'}])
        self.assertIn('数字があれば必ず入れる', prompt)

    def test_prompt_includes_legal_constraints(self):
        """T2026-0501-C: リーガル制約 (名誉毀損・推測禁止) がプロンプトに含まれる。"""
        prompt = self._capture_prompt([{'title': 'X'}])
        self.assertIn('名誉毀損', prompt, '名誉毀損禁止文言が消失')
        self.assertIn('推測で書かない', prompt, '推測禁止文言が消失')
        # 「煽りと角度の区別」が明示されていること
        self.assertIn('角度', prompt)
        self.assertIn('煽り', prompt)

    def test_prompt_uses_genre_hint_when_provided(self):
        """T2026-0501-C: genre 引数を渡したときに該当ヒントがプロンプトに注入される。"""
        prompt_politics = self._capture_prompt([{'title': 'X'}], genre='政治')
        self.assertIn('政治', prompt_politics)
        self.assertIn('対立軸', prompt_politics)

        prompt_finance = self._capture_prompt([{'title': 'X'}], genre='株・金融')
        self.assertIn('株・金融', prompt_finance)
        self.assertIn('価格', prompt_finance)

    def test_prompt_falls_back_to_general_when_genre_none(self):
        """genre=None のときは「総合」ヒントが使われる (KeyError しない)。"""
        prompt = self._capture_prompt([{'title': 'X'}], genre=None)
        self.assertIn('総合', prompt)

    def test_prompt_falls_back_to_general_for_unknown_genre(self):
        """未登録ジャンルが来ても「総合」ヒントにフォールバックして死なない。"""
        prompt = self._capture_prompt([{'title': 'X'}], genre='未知ジャンル')
        # ヒントセクションが「総合」ヒント文に解決される
        self.assertIn('事実の意外性', prompt)

    def test_validation_still_rejects_refusal_responses(self):
        """プロンプト改修で _REFUSAL 検証ロジックが壊れていないこと。"""
        def fake_urlopen(req, *a, **kw):
            return _FakeResponse({'content': [{'text': '申し訳ありませんが提供できません'}]})

        with mock.patch('proc_ai.urllib.request.urlopen', side_effect=fake_urlopen):
            with mock.patch('proc_ai.time.sleep', return_value=None):
                result = proc_ai.generate_title([{'title': 'X'}])
        self.assertIsNone(result, '拒否応答が None に潰されない')

    def test_compelling_title_passes_validation(self):
        """惹きあり改善例タイトル(角度+数字+二段構造)が validation を通過する。"""
        compelling = '米GDP、予想割れ2.0%——市場の利下げ観測が動く'

        def fake_urlopen(req, *a, **kw):
            return _FakeResponse({'content': [{'text': compelling}]})

        with mock.patch('proc_ai.urllib.request.urlopen', side_effect=fake_urlopen):
            with mock.patch('proc_ai.time.sleep', return_value=None):
                result = proc_ai.generate_title([{'title': 'X'}])
        self.assertEqual(result, compelling)


class PerspectiveActorHintTest(unittest.TestCase):
    """T2026-0501-C-2: ジャンル別 perspectives アクター指定が user prompt に注入されること。"""

    def test_actor_hint_for_politics(self):
        block = proc_ai._build_perspective_actor_hint('政治')
        self.assertIn('与党', block)
        self.assertIn('野党', block)
        self.assertIn('市民', block)
        # 媒体名固定の落とし穴を回避していることを明示する文言
        self.assertIn('最終手段', block)

    def test_actor_hint_for_finance(self):
        block = proc_ai._build_perspective_actor_hint('株・金融')
        self.assertIn('機関投資家', block)
        self.assertIn('中央銀行', block)

    def test_actor_hint_for_tech(self):
        block = proc_ai._build_perspective_actor_hint('テクノロジー')
        self.assertIn('開発者', block)
        self.assertIn('規制当局', block)
        self.assertIn('エンドユーザー', block)

    def test_actor_hint_falls_back_for_none(self):
        block = proc_ai._build_perspective_actor_hint(None)
        # 「総合」 actors にフォールバック
        self.assertIn('当事者', block)
        self.assertIn('関係省庁', block)

    def test_actor_hint_falls_back_for_unknown_genre(self):
        block = proc_ai._build_perspective_actor_hint('未知ジャンル')
        self.assertIn('当事者', block)

    def test_actor_hint_always_returns_block(self):
        """空文字を返さない (空だと user prompt が崩れる)。"""
        for g in (None, '', '政治', '不明', '株・金融'):
            block = proc_ai._build_perspective_actor_hint(g)
            self.assertTrue(len(block) > 50, f'genre={g!r} のブロックが短すぎる: {block!r}')


class OutlookActorHintTest(unittest.TestCase):
    """T2026-0501-G: outlook 生成プロンプトに「読者ペルソナ」+「視点アクター」+「条件付き仮説」が
    必ず含まれる回帰テスト。

    PO 指摘 (2026-05-01):
      - outlook が「〜に注目が集まる」「動向を見守る」の当たり障りない観測に終始
      - 「このトピックを読むのがどういう人間か」という読者ペルソナ視点が欠落
      - 「外れたら困る」のリスク回避で具体性が落ちる

    プロンプトが将来「無難な観測」に薄まらないよう、キーフレーズが残っていることを物理ガード。
    """

    def test_outlook_hint_for_finance_includes_investor_persona(self):
        block = proc_ai._build_outlook_actor_hint('株・金融')
        # 読者ペルソナ
        self.assertIn('投資家', block)
        # 視点アクター集合
        self.assertIn('機関投資家', block)
        # 条件付き仮説の語彙
        self.assertIn('もし', block)
        # 時間軸の語彙
        self.assertIn('時間軸', block)
        # 確信度タグ
        self.assertIn('確信度', block)

    def test_outlook_hint_for_politics_includes_policy_watcher_persona(self):
        block = proc_ai._build_outlook_actor_hint('政治')
        # 読者ペルソナ: 政策ウォッチャー or ビジネスマン
        self.assertTrue('政策ウォッチャー' in block or 'ビジネス' in block,
                        f'政治の読者ペルソナ語彙が含まれていない: {block!r}')
        # 視点アクター
        self.assertIn('与党', block)
        self.assertIn('野党', block)

    def test_outlook_hint_for_international_includes_business_layer_persona(self):
        block = proc_ai._build_outlook_actor_hint('国際')
        # 読者ペルソナ: 海外ビジネス層
        self.assertIn('ビジネス', block)
        # 視点アクター
        self.assertIn('当事国', block)

    def test_outlook_hint_falls_back_for_none_and_unknown(self):
        for g in (None, '', '未知ジャンル', '存在しないジャンル'):
            block = proc_ai._build_outlook_actor_hint(g)
            # 総合 reader persona / actor にフォールバック
            self.assertIn('一般読者', block, f'genre={g!r} で総合 reader persona にフォールバックしていない')
            self.assertIn('当事者', block)

    def test_outlook_hint_forbids_safe_observation_phrases(self):
        """『動向に注目』『見守る』のような逃げ文を禁止する旨が含まれる。"""
        block = proc_ai._build_outlook_actor_hint('政治')
        # 禁止語をプロンプト内で名指ししているか
        self.assertIn('動向', block)
        self.assertIn('見守る', block)
        # 外れ許容のメッセージ
        self.assertIn('外れる', block)

    def test_outlook_hint_includes_legal_constraints(self):
        """名誉毀損・記事外事実の作り上げ禁止が残っている。"""
        block = proc_ai._build_outlook_actor_hint('ビジネス')
        self.assertIn('名誉毀損', block)
        self.assertIn('捏造', block)

    def test_outlook_hint_always_returns_block(self):
        """空文字を返さない (空だと user prompt が崩れる)。"""
        for g in (None, '', '政治', '不明', '株・金融', 'テクノロジー', '健康', '国際'):
            block = proc_ai._build_outlook_actor_hint(g)
            self.assertTrue(len(block) > 200, f'genre={g!r} のブロックが短すぎる: len={len(block)}')

    def test_reader_personas_cover_all_valid_genres(self):
        """_GENRE_READER_PERSONAS が _VALID_GENRE_SET 全てをカバーしている。
        欠落するとフォールバックが発生して読者ペルソナが薄まるため物理ガード。"""
        for g in proc_ai._VALID_GENRE_SET:
            self.assertIn(g, proc_ai._GENRE_READER_PERSONAS,
                          f'_GENRE_READER_PERSONAS に {g!r} が欠落')

    def test_outlook_hint_injected_in_minimal_prompt(self):
        """_generate_story_minimal が user prompt に outlook hint を注入している (Tool Use 経由)。"""
        captured = {}

        def fake_call_tool(prompt, tool_name, schema, **kw):
            captured['prompt'] = prompt
            return {
                'aiSummary': 'ダミー要約。これは何が起きたか。これは何を意味するか。',
                'keyPoint': 'a' * 110,
                'outlook': '個人投資家から見れば、今週中に利下げ観測が後退すれば短期で利確タイミングが来る可能性が高い [確信度:中]',
                'topicTitle': 'ダミートピック',
                'latestUpdateHeadline': 'ダミーが発表した',
                'isCoherent': True,
                'topicLevel': 'detail',
                'genres': ['株・金融'],
            }

        with mock.patch('proc_ai._call_claude_tool', side_effect=fake_call_tool):
            with mock.patch('proc_ai._process_keypoint_quality'):
                proc_ai._generate_story_minimal(
                    [{'title': '日経平均が上昇', 'pubDate': '2026-05-01'}],
                    genre='株・金融',
                )
        self.assertIn('outlook 生成方針 (T2026-0501-G)', captured.get('prompt', ''))
        self.assertIn('投資家', captured['prompt'])

    def test_outlook_hint_injected_in_standard_prompt(self):
        """_generate_story_standard が user prompt に outlook hint を注入している。"""
        captured = {}

        def fake_call_tool(prompt, tool_name, schema, **kw):
            captured['prompt'] = prompt
            return {
                'aiSummary': 'ダミー要約。これは何が起きたか。これは何を意味するか。',
                'keyPoint': 'b' * 110,
                'outlook': 'ビジネス側から見れば、年内解散で関連業界に直撃する可能性が高い [確信度:中]',
                'topicTitle': 'ダミートピック',
                'latestUpdateHeadline': 'ダミーが発表した',
                'isCoherent': True,
                'topicLevel': 'sub',
                'genres': ['政治'],
                'statusLabel': '進行中',
                'watchPoints': '①与党の動き ②野党の対応 ③市場の反応',
                'perspectives': '与党は〜、野党は〜、市民は〜',
                'phase': '拡散',
                'timeline': [],
            }

        with mock.patch('proc_ai._call_claude_tool', side_effect=fake_call_tool):
            with mock.patch('proc_ai._process_keypoint_quality'):
                with mock.patch('proc_ai._build_media_comparison_block', return_value=''):
                    proc_ai._generate_story_standard(
                        [{'title': f'政治記事 {i}', 'pubDate': '2026-05-01'} for i in range(4)],
                        cnt=4, genre='政治',
                    )
        self.assertIn('outlook 生成方針 (T2026-0501-G)', captured.get('prompt', ''))
        self.assertIn('政策ウォッチャー', captured['prompt'])

    def test_outlook_hint_injected_in_full_prompt(self):
        """_generate_story_full が user prompt に outlook hint を注入している。"""
        captured = {}

        def fake_call_tool(prompt, tool_name, schema, **kw):
            captured['prompt'] = prompt
            return {
                'aiSummary': 'ダミー要約。これは何が起きたか。これは何を意味するか。',
                'keyPoint': 'c' * 110,
                'outlook': '日本の輸出企業から見れば、3ヶ月以内にサプライチェーン見直し圧力が顕在化する可能性が高い [確信度:中]',
                'topicTitle': '国際情勢',
                'latestUpdateHeadline': '関税が再強化された',
                'isCoherent': True,
                'topicLevel': 'major',
                'genres': ['国際'],
                'statusLabel': '進行中',
                'watchPoints': '①関税の動き ②各国の対応 ③市場の反応',
                'perspectives': '当事国は〜、周辺国は〜、国際機関は〜',
                'phase': '拡散',
                'timeline': [],
                'forecast': 'ダミー予想 [確信度:中]',
            }

        with mock.patch('proc_ai._call_claude_tool', side_effect=fake_call_tool):
            with mock.patch('proc_ai._process_keypoint_quality'):
                with mock.patch('proc_ai._build_media_comparison_block', return_value=''):
                    proc_ai._generate_story_full(
                        [{'title': f'国際記事 {i}', 'pubDate': '2026-05-01'} for i in range(7)],
                        cnt=7, genre='国際',
                    )
        self.assertIn('outlook 生成方針 (T2026-0501-G)', captured.get('prompt', ''))
        # 国際の reader persona = 海外ビジネス層
        self.assertIn('海外', captured['prompt'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
