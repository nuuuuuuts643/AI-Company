"""T2026-0428-O regression test: proc_storage._apply_tier0_budget で
articles>=10 × aiGenerated=False のトピック (Tier-0) が必ず先頭に固定されることを保証する。

背景:
  T213 の 4段階優先度ソート後でも、Tier-0 内で articleCount の重みが弱く
  小規模クラスタが先に処理されて大規模が放置される事象が観測された
  (本番 2026-04-28 05:13 JST: articles=19/15 の cluster が aiGenerated=False のまま放置)。
  commit 894dd1d / 4d62cbc で _apply_tier0_budget 導入。
  本テストは恒久回帰防止用 (handler.py の Phase A wallclock guard と対で機能)。

実行:
  cd projects/P003-news-timeline
  python3 -m unittest tests.test_tier0_budget -v
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'lambda', 'processor'))

os.environ.setdefault('S3_BUCKET', 'test-bucket')
os.environ.setdefault('AWS_REGION', 'ap-northeast-1')

import proc_storage  # noqa: E402

apply_t0 = proc_storage._apply_tier0_budget


def _topic(tid, ac, ai_gen=False):
    return {'topicId': tid, 'articleCount': ac, 'aiGenerated': ai_gen}


class Tier0BudgetTest(unittest.TestCase):
    def test_empty_list_passthrough(self):
        self.assertEqual(apply_t0([]), [])

    def test_no_tier0_preserves_order(self):
        items = [_topic('a', 3), _topic('b', 5, ai_gen=True), _topic('c', 1)]
        out = apply_t0(items)
        self.assertEqual([t['topicId'] for t in out], ['a', 'b', 'c'])

    def test_tier0_promoted_to_front(self):
        """articleCount>=10 × aiGenerated=False が先頭に固定される"""
        items = [
            _topic('small1', 3),
            _topic('big_done', 19, ai_gen=True),  # 大規模だが処理済み → Tier-0 ではない
            _topic('small2', 5),
            _topic('big_pending', 15),            # ★ Tier-0
            _topic('small3', 2),
        ]
        out = apply_t0(items)
        self.assertEqual(out[0]['topicId'], 'big_pending')
        # 残り 4 件は元の順序を保つ
        self.assertEqual(
            [t['topicId'] for t in out[1:]],
            ['small1', 'big_done', 'small2', 'small3'],
        )

    def test_multiple_tier0_all_to_front_in_original_order(self):
        items = [
            _topic('m', 3),
            _topic('big_a', 19),  # ★ Tier-0
            _topic('s', 1),
            _topic('big_b', 15),  # ★ Tier-0
            _topic('big_c', 11),  # ★ Tier-0
            _topic('aiGen_big', 20, ai_gen=True),  # 処理済み → 非 Tier-0
        ]
        out = apply_t0(items)
        # 先頭 3 件は Tier-0 が元順で並ぶ
        self.assertEqual([t['topicId'] for t in out[:3]], ['big_a', 'big_b', 'big_c'])
        # 残り 3 件は非 Tier-0 が元順で並ぶ
        self.assertEqual([t['topicId'] for t in out[3:]], ['m', 's', 'aiGen_big'])

    def test_articles_exactly_10_qualifies(self):
        """articleCount==10 (境界値) も Tier-0 として扱われる"""
        items = [_topic('small', 3), _topic('boundary', 10)]
        out = apply_t0(items)
        self.assertEqual(out[0]['topicId'], 'boundary')

    def test_articles_9_does_not_qualify(self):
        """articleCount==9 (境界直下) は Tier-0 ではない"""
        items = [_topic('small', 3), _topic('almost', 9)]
        out = apply_t0(items)
        self.assertEqual([t['topicId'] for t in out], ['small', 'almost'])

    def test_aigenerated_true_disqualifies(self):
        """aiGenerated=True なら articleCount に関わらず Tier-0 ではない"""
        items = [_topic('small', 3), _topic('big_done', 100, ai_gen=True)]
        out = apply_t0(items)
        self.assertEqual([t['topicId'] for t in out], ['small', 'big_done'])

    def test_budget_caps_tier0_count(self):
        """budget 引数で Tier-0 採用件数を制限できる (デフォルト 100 はほぼ実質全件)"""
        items = [_topic(f't{i}', 12) for i in range(5)]
        out = apply_t0(items, budget=2)
        # 先頭 2 件は budget 内で Tier-0 採用、残り 3 件は rest 側で順序保持
        self.assertEqual([t['topicId'] for t in out[:2]], ['t0', 't1'])
        self.assertEqual([t['topicId'] for t in out[2:]], ['t2', 't3', 't4'])

    def test_invalid_articlecount_treated_as_zero(self):
        """articleCount が文字列・None でも例外を出さず非 Tier-0 扱い"""
        items = [
            {'topicId': 'a', 'articleCount': 'not-a-number'},
            {'topicId': 'b', 'articleCount': None},
            _topic('big', 12),  # ★ Tier-0
        ]
        out = apply_t0(items)
        self.assertEqual(out[0]['topicId'], 'big')


if __name__ == '__main__':
    unittest.main()
