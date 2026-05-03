"""T2026-0501-KPG: ジャンル別 keyPoint 角度ヒントが user prompt に注入されているか回帰テスト。

PO 指摘 (2026-05-01) 「ジャンル/トピック単位プロンプト分岐」+ ux-scores.md 計測:
  健康 0% / テクノロジー 12.5% vs 株・金融 76.5% (kp>=100字 充填率) — keyPoint
  生成プロンプトはジャンル横断で同一テンプレ。「中心数値/固有名詞」の角度がジャンル依存
  なため、汎用テンプレでは健康・テックの数字踏み込みが弱くなる。

本テストは:
  1) `_GENRE_KEYPOINT_HINTS` に各ジャンル分の角度ヒントが残っていること
  2) `_build_keypoint_genre_hint(genre)` がジャンル別ブロックを返すこと
     - 政治/株・金融/健康/テクノロジー/国際 で固有のキーフレーズが出ること
     - 未知/None でも『総合』にフォールバックして死なないこと
  3) `_generate_story_minimal` / `_generate_story_standard` / `_generate_story_full`
     が呼ばれた際 user prompt に `_build_keypoint_genre_hint` ブロックが含まれること
  4) `_SYSTEM_PROMPT` (cache 対象) は変更されず、ヒントは user prompt 経由のみで注入されること

実行:
  cd projects/P003-news-timeline
  ANTHROPIC_API_KEY=dummy python3 tests/test_keypoint_genre_hint.py -v
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


_VALID_GENRES = (
    '政治', 'ビジネス', '株・金融', 'テクノロジー', '科学', '健康',
    '国際', '社会', 'スポーツ', 'エンタメ', 'くらし', 'グルメ', 'ファッション', '総合',
)


class GenreKeypointHintsDictTest(unittest.TestCase):
    """`_GENRE_KEYPOINT_HINTS` 辞書の構造ガード。"""

    def test_all_valid_genres_have_hint(self):
        """_VALID_GENRE_SET 全ジャンルにヒントが定義されている (フォールバック前に直接ヒット)。"""
        for genre in _VALID_GENRES:
            self.assertIn(genre, proc_ai._GENRE_KEYPOINT_HINTS,
                          f'{genre} のヒント定義が欠落')

    def test_general_fallback_exists(self):
        """『総合』はフォールバック先のため必ず存在する。"""
        self.assertIn('総合', proc_ai._GENRE_KEYPOINT_HINTS)
        self.assertTrue(proc_ai._GENRE_KEYPOINT_HINTS['総合'].strip())

    def test_each_hint_mentions_central_anchor_phrase(self):
        """各ヒント末尾は『keyPoint の中心数値/固有名詞に据える』形式で統一されている (差分監査用)。"""
        anchor = '中心数値/固有名詞に据える'
        for genre, hint in proc_ai._GENRE_KEYPOINT_HINTS.items():
            self.assertIn(anchor, hint, f'{genre} のヒントに anchor 句が無い')


class BuildKeypointGenreHintTest(unittest.TestCase):
    """`_build_keypoint_genre_hint(genre)` が user prompt 用ブロックを返すか。"""

    def test_block_for_politics(self):
        block = proc_ai._build_keypoint_genre_hint('政治')
        self.assertIn('政治', block)
        self.assertIn('票差', block)
        self.assertIn('支持率', block)

    def test_block_for_finance(self):
        block = proc_ai._build_keypoint_genre_hint('株・金融')
        self.assertIn('株・金融', block)
        self.assertIn('価格%変動', block)
        self.assertIn('予想とのギャップ', block)

    def test_block_for_health(self):
        """健康: 有効率/副作用率/対象患者数/保険適用 を中心に据えるヒントが出る (UX 0% 改善対象)。"""
        block = proc_ai._build_keypoint_genre_hint('健康')
        self.assertIn('健康', block)
        self.assertIn('有効率', block)
        self.assertIn('副作用率', block)
        self.assertIn('保険適用', block)

    def test_block_for_tech(self):
        """テクノロジー: 性能差/採用速度/規制リスクが含まれる (UX 12.5% 改善対象)。"""
        block = proc_ai._build_keypoint_genre_hint('テクノロジー')
        self.assertIn('テクノロジー', block)
        self.assertIn('性能差', block)
        self.assertIn('採用速度', block)

    def test_block_for_international(self):
        block = proc_ai._build_keypoint_genre_hint('国際')
        self.assertIn('国際', block)
        self.assertIn('対立軸', block)
        self.assertIn('為替', block)

    def test_block_for_none_falls_back_to_general(self):
        """genre=None でも『総合』にフォールバックして KeyError しない。"""
        block = proc_ai._build_keypoint_genre_hint(None)
        # 『総合』はラベルではなくフォールバックされた中身で識別する (ラベルは "総合" を出す)
        self.assertIn('総合', block)
        self.assertIn('事実の意外性', block)

    def test_block_for_unknown_falls_back_to_general(self):
        """未知ジャンルでも『総合』ヒント本文にフォールバック (ラベルは未知ジャンル名のまま)。"""
        block = proc_ai._build_keypoint_genre_hint('未知ジャンル')
        # ラベルは渡された文字列がそのまま出るが、ヒント本文は「総合」のフォールバック文。
        self.assertIn('未知ジャンル', block)
        self.assertIn('事実の意外性', block)

    def test_block_forbids_vague_phrases(self):
        """ヒント本文に「数字なし汎用文は禁止」のガード文言が必ず含まれる (惹きの担保)。"""
        block = proc_ai._build_keypoint_genre_hint('政治')
        self.assertIn('動向に注目', block)  # 禁止文言の例示として残っていること
        self.assertIn('禁止', block)

    def test_block_forbids_fabrication(self):
        """記事内に該当数字がない場合の処理が明文化されている (legal 制約)。"""
        block = proc_ai._build_keypoint_genre_hint('健康')
        self.assertIn('記事内に明示なし', block)
        self.assertIn('捏造', block)

    def test_block_is_non_empty_for_all_known_genres(self):
        """全 known ジャンルで空文字を返さない (cache 設計と同じ契約)。"""
        for genre in _VALID_GENRES:
            block = proc_ai._build_keypoint_genre_hint(genre)
            self.assertTrue(block.strip(), f'{genre} で空ブロックが返った')


class _StubFullArticles:
    """`fetch_full_articles` を import 不可にする stub。media_block 取得を空にする。"""

    @staticmethod
    def install(monkeypatch_target):
        monkeypatch_target.fetch_full_articles = None


def _capture_prompts_for_mode(mode, genre, articles):
    """指定 mode の `_generate_story_*` を呼び、Claude tool call の user prompt を捕捉。"""
    captured = {}

    def fake_call(prompt, tool_name, schema, *args, **kwargs):
        # T2026-0502-AZ: prompt is now a list of content blocks; flatten for backward-compat assertions
        if isinstance(prompt, list):
            prompt = '\n'.join(b.get('text', '') for b in prompt if isinstance(b, dict))
        captured['prompt'] = prompt
        captured['system'] = kwargs.get('system') or ''
        # 最低限のフィールドを返して None ガードを通す
        return {
            'aiSummary': 'テスト要約。',
            'keyPoint': 'テスト keyPoint 100字以上のダミー文。' * 4,
            'outlook': 'テスト予想 [確信度:中]',
            'topicTitle': 'テスト',
            'latestUpdateHeadline': 'テスト見出し',
            'isCoherent': True,
            'topicLevel': 'sub',
            'genres': [genre or '総合'],
            'perspectives': '[アクターA] は〜、[アクターB] は〜と論じている。' * 2,
            'phase': '拡散',
        }

    with mock.patch('proc_ai._call_claude_tool', side_effect=fake_call):
        with mock.patch('proc_ai.fetch_full_articles', None):
            if mode == 'minimal':
                proc_ai._generate_story_minimal(articles, genre=genre)
            elif mode == 'standard':
                proc_ai._generate_story_standard(articles, cnt=len(articles), genre=genre)
            elif mode == 'full':
                proc_ai._generate_story_full(articles, cnt=len(articles), genre=genre)
            else:
                raise ValueError(f'unknown mode: {mode}')
    return captured


class HintInjectedInModePromptsTest(unittest.TestCase):
    """3 mode の user prompt に keyPoint genre hint が注入されていること。"""

    @staticmethod
    def _articles(n):
        return [
            {
                'title': f'記事{i}',
                'description': f'概要{i}',
                'pubDate': '2026-05-01T00:00:00Z',
                'source': f'media{i}',
                'link': f'https://example.com/{i}',
            }
            for i in range(n)
        ]

    def test_minimal_mode_includes_keypoint_genre_hint(self):
        cap = _capture_prompts_for_mode('minimal', '健康', self._articles(1))
        prompt = cap.get('prompt', '')
        self.assertIn('keyPoint 角度ヒント', prompt)
        self.assertIn('健康', prompt)
        self.assertIn('有効率', prompt)

    def test_minimal_mode_with_two_articles_still_injects(self):
        """cnt=2 (perspectives 含む minimal) でも hint が抜け落ちない。"""
        cap = _capture_prompts_for_mode('minimal', 'テクノロジー', self._articles(2))
        prompt = cap.get('prompt', '')
        self.assertIn('keyPoint 角度ヒント', prompt)
        self.assertIn('テクノロジー', prompt)
        self.assertIn('性能差', prompt)

    def test_standard_mode_includes_keypoint_genre_hint(self):
        cap = _capture_prompts_for_mode('standard', '株・金融', self._articles(3))
        prompt = cap.get('prompt', '')
        self.assertIn('keyPoint 角度ヒント', prompt)
        self.assertIn('株・金融', prompt)
        self.assertIn('価格%変動', prompt)

    def test_full_mode_includes_keypoint_genre_hint(self):
        cap = _capture_prompts_for_mode('full', '国際', self._articles(6))
        prompt = cap.get('prompt', '')
        self.assertIn('keyPoint 角度ヒント', prompt)
        self.assertIn('国際', prompt)
        self.assertIn('為替', prompt)

    def test_system_prompt_is_unchanged_by_hint(self):
        """system prompt (cache 対象) は genre 違いで同一バイトを保つ (cache 維持の契約)."""
        cap_a = _capture_prompts_for_mode('minimal', '政治', self._articles(1))
        cap_b = _capture_prompts_for_mode('minimal', '健康', self._articles(1))
        self.assertEqual(cap_a['system'], cap_b['system'],
                         'system prompt が genre で変わると prompt cache が壊れる')

    def test_unknown_genre_does_not_break_minimal(self):
        cap = _capture_prompts_for_mode('minimal', '未知ジャンル', self._articles(1))
        prompt = cap.get('prompt', '')
        self.assertIn('keyPoint 角度ヒント', prompt)
        # フォールバック中身 (総合ヒントの本文) が出ていれば成功
        self.assertIn('事実の意外性', prompt)


if __name__ == '__main__':
    unittest.main(verbosity=2)
