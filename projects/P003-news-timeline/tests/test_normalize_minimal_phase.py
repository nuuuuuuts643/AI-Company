"""T2026-0429-G regression test: minimal regime (articleCount<=2 or summaryMode='minimal') の
レガシー storyPhase を正規化して None に戻す物理ガード。

背景:
  T219 (2026-04-28) で minimal mode の AI 出力 phase=None に変更したが、それ以前に
  「発端」固定で書き込まれた DDB レコードが永続化していた。AI 再生成は articleCount>=3
  でしか走らないため、ac=2 のままの 49 件が「発端」のまま放置 (本番 2026-04-30 計測:
  全 126 件中 53/126=42.1% が発端、うち ac=2 + summaryMode=minimal が 49 件)。

  読み出しパス (S3 出力) で legacy 値を物理的に剥がす normalize_minimal_phase を導入し、
  generate_topics_card_json と handler.py の topics_pub 構築で適用する。

実行:
  cd projects/P003-news-timeline
  python3 -m unittest tests.test_normalize_minimal_phase -v
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'lambda', 'processor'))

os.environ.setdefault('S3_BUCKET', 'test-bucket')
os.environ.setdefault('AWS_REGION', 'ap-northeast-1')

import proc_storage  # noqa: E402

normalize = proc_storage.normalize_minimal_phase
gen_card = proc_storage.generate_topics_card_json


class TestNormalizeMinimalPhase(unittest.TestCase):
    """単体: normalize_minimal_phase の各境界条件。"""

    # --- minimal regime: storyPhase をクリアする ---
    def test_ac1_with_phase_hatten_cleared(self):
        item = {'topicId': 't1', 'articleCount': 1, 'storyPhase': '発端'}
        out = normalize(item)
        self.assertIsNone(out['storyPhase'])

    def test_ac2_with_phase_hatten_cleared(self):
        item = {'topicId': 't2', 'articleCount': 2, 'storyPhase': '発端'}
        out = normalize(item)
        self.assertIsNone(out['storyPhase'])

    def test_ac0_with_phase_cleared(self):
        item = {'topicId': 't0', 'articleCount': 0, 'storyPhase': '発端'}
        out = normalize(item)
        self.assertIsNone(out['storyPhase'])

    def test_summary_mode_minimal_overrides_ac(self):
        """summaryMode='minimal' が立っていれば articleCount に関わらずクリア。"""
        item = {'topicId': 't', 'articleCount': 5, 'summaryMode': 'minimal', 'storyPhase': '発端'}
        out = normalize(item)
        self.assertIsNone(out['storyPhase'])

    def test_minimal_with_phase_other_than_hatten_also_cleared(self):
        """legacy が '発端' 以外 (拡散等) でも minimal regime では phase 概念がないので剥がす。"""
        item = {'topicId': 't', 'articleCount': 2, 'storyPhase': '拡散'}
        out = normalize(item)
        self.assertIsNone(out['storyPhase'])

    # --- 非 minimal: 触らない ---
    def test_ac3_phase_kept(self):
        item = {'topicId': 't3', 'articleCount': 3, 'storyPhase': '拡散'}
        out = normalize(item)
        self.assertEqual(out['storyPhase'], '拡散')

    def test_ac10_phase_kept(self):
        item = {'topicId': 't10', 'articleCount': 10, 'storyPhase': 'ピーク', 'summaryMode': 'full'}
        out = normalize(item)
        self.assertEqual(out['storyPhase'], 'ピーク')

    def test_ac3_with_hatten_kept(self):
        """ac>=3 で '発端' は別経路 (needs_ai_processing) で AI 再生成されるため、
        normalizer は触らない (responsibility separation)。"""
        item = {'topicId': 't', 'articleCount': 3, 'storyPhase': '発端'}
        out = normalize(item)
        self.assertEqual(out['storyPhase'], '発端')

    # --- 既に None or 空: 影響なし ---
    def test_minimal_with_phase_none_unchanged(self):
        item = {'topicId': 't', 'articleCount': 1, 'storyPhase': None}
        out = normalize(item)
        self.assertIsNone(out['storyPhase'])

    def test_minimal_without_phase_field_unchanged(self):
        item = {'topicId': 't', 'articleCount': 1}
        out = normalize(item)
        # storyPhase キーが追加されないこと
        self.assertNotIn('storyPhase', out)

    def test_minimal_with_phase_empty_string_unchanged(self):
        """空文字は falsy として既に「未生成」扱いなので触らない (二度書きノイズ回避)。"""
        item = {'topicId': 't', 'articleCount': 1, 'storyPhase': ''}
        out = normalize(item)
        # 空文字のまま (None に書き換えない・既に表示されない)
        self.assertEqual(out['storyPhase'], '')

    # --- 異常系: 型エラー耐性 ---
    def test_ac_non_numeric_treated_as_zero(self):
        """articleCount が文字列 '2' でも数値として解釈される。'abc' は 0 扱い (=minimal)。"""
        item = {'topicId': 't', 'articleCount': 'abc', 'storyPhase': '発端'}
        out = normalize(item)
        self.assertIsNone(out['storyPhase'])

    def test_ac_string_numeric(self):
        item = {'topicId': 't', 'articleCount': '2', 'storyPhase': '発端'}
        out = normalize(item)
        self.assertIsNone(out['storyPhase'])

    def test_ac_string_numeric_3_kept(self):
        item = {'topicId': 't', 'articleCount': '3', 'storyPhase': '発端'}
        out = normalize(item)
        self.assertEqual(out['storyPhase'], '発端')

    def test_ac_none_treated_as_zero(self):
        item = {'topicId': 't', 'articleCount': None, 'storyPhase': '発端'}
        out = normalize(item)
        self.assertIsNone(out['storyPhase'])

    def test_non_dict_returned_unchanged(self):
        self.assertEqual(normalize(None), None)
        self.assertEqual(normalize('string'), 'string')
        self.assertEqual(normalize(123), 123)

    # --- 副作用: 元 dict を変更しない ---
    def test_input_not_mutated(self):
        item = {'topicId': 't', 'articleCount': 2, 'storyPhase': '発端'}
        normalize(item)
        self.assertEqual(item['storyPhase'], '発端', '入力 dict は in-place 変更されないこと')

    def test_no_copy_when_no_change(self):
        """変更不要なら同一オブジェクトを返す (cheap path)。"""
        item = {'topicId': 't', 'articleCount': 5, 'storyPhase': '拡散'}
        out = normalize(item)
        self.assertIs(out, item)


class TestGenerateTopicsCardJsonNormalization(unittest.TestCase):
    """統合: generate_topics_card_json が card 化前に normalizer を適用する。"""

    def test_card_clears_legacy_minimal_hatten(self):
        topics_pub = [
            {'topicId': 'a', 'articleCount': 2, 'summaryMode': 'minimal', 'storyPhase': '発端', 'title': 'A'},
            {'topicId': 'b', 'articleCount': 5, 'summaryMode': 'standard', 'storyPhase': '拡散', 'title': 'B'},
            {'topicId': 'c', 'articleCount': 1, 'storyPhase': '発端', 'title': 'C'},
        ]
        result = gen_card(topics_pub, '2026-04-30T20:00:00Z')
        cards = {c['topicId']: c for c in result['topics']}
        self.assertIsNone(cards['a']['storyPhase'])  # minimal: 剥がす
        self.assertEqual(cards['b']['storyPhase'], '拡散')  # standard: 保持
        self.assertIsNone(cards['c']['storyPhase'])  # ac=1: 剥がす

    def test_card_input_topics_not_mutated(self):
        """card 生成は入力 topics_pub を変更しない (in-place 副作用なし)。"""
        topics_pub = [
            {'topicId': 'a', 'articleCount': 2, 'summaryMode': 'minimal', 'storyPhase': '発端'},
        ]
        gen_card(topics_pub, '2026-04-30T20:00:00Z')
        self.assertEqual(topics_pub[0]['storyPhase'], '発端')

    def test_card_count_unchanged(self):
        """normalize は count を変えない (filter ではない)。"""
        topics_pub = [
            {'topicId': str(i), 'articleCount': 2, 'storyPhase': '発端'} for i in range(10)
        ]
        result = gen_card(topics_pub, 'now')
        self.assertEqual(result['count'], 10)
        self.assertEqual(len(result['topics']), 10)

    def test_card_payload_shape(self):
        topics_pub = [{'topicId': 'a', 'articleCount': 3, 'storyPhase': '拡散', 'title': 'T'}]
        result = gen_card(topics_pub, '2026-04-30T20:00:00Z')
        self.assertIn('topics', result)
        self.assertIn('updatedAt', result)
        self.assertIn('count', result)
        self.assertEqual(result['updatedAt'], '2026-04-30T20:00:00Z')


if __name__ == '__main__':
    unittest.main()
