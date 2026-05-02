"""
test_entity_hierarchy.py — T2026-0502-U-V3 entity hierarchy の unit test。

新しい false-split 事例が見つかったら:
  1. ここに 1 ケース追加
  2. lambda/fetcher/config.py の ENTITY_HIERARCHY に dict 1 行追加
CI で regression を物理担保する。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'fetcher'))
from text_utils import hierarchy_aware_overlap


class TestEntityHierarchy(unittest.TestCase):

    def test_europe_subsumes_germany(self):
        """T2026-0501-M 元事例: 欧州駐留米軍 vs ドイツ駐留米軍。"""
        a = {'欧州', 'トランプ', '米軍'}
        b = {'ドイツ', 'トランプ', '米軍'}
        overlap = hierarchy_aware_overlap(a, b)
        self.assertIn('欧州', overlap, '欧州⊃ドイツ で hit すべき')
        self.assertGreaterEqual(len(overlap), 3, 'shared >=3 で同一事件と判定可能')

    def test_kanto_subsumes_tokyo(self):
        a = {'関東', '気象庁', '大雨'}
        b = {'東京', '気象庁', '大雨'}
        overlap = hierarchy_aware_overlap(a, b)
        self.assertIn('関東', overlap)

    def test_government_subsumes_ministry(self):
        a = {'政府', '改革'}
        b = {'財務省', '改革'}
        overlap = hierarchy_aware_overlap(a, b)
        self.assertIn('政府', overlap)

    def test_no_false_match_us_vs_japan(self):
        """米国 GDP vs 日本 GDP は別事件のまま (hierarchy で誤マージしない)。"""
        a = {'米国', 'GDP', '速報値'}
        b = {'日本', 'GDP', '速報値'}
        overlap = hierarchy_aware_overlap(a, b)
        # 米国 と 日本 は親子関係でない → overlap は GDP, 速報値 のみ
        self.assertNotIn('米国', overlap)
        self.assertNotIn('日本', overlap)

    def test_g7_member_pairs_no_match(self):
        """G7 加盟国同士は別主体 → 誤マージしない。"""
        a = {'米国', '関税'}
        b = {'ドイツ', '関税'}
        overlap = hierarchy_aware_overlap(a, b)
        # 親 (G7) は entities_a/b に含まれていないので加わらない
        self.assertEqual(overlap, {'関税'}, '主体違いは G7 経由で誤マージしないこと')

    def test_empty_returns_empty(self):
        self.assertEqual(hierarchy_aware_overlap(set(), set()), set())
        self.assertEqual(hierarchy_aware_overlap({'a'}, set()), set())


if __name__ == '__main__':
    unittest.main()
