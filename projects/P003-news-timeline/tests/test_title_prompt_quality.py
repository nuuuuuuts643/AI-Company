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


if __name__ == '__main__':
    unittest.main(verbosity=2)
