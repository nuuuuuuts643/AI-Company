"""T2026-0428-O / T2026-0502-M regression test: proc_storage._apply_tier0_budget で
(ac>=6 OR score>=100) × aiGenerated=False のトピック (Tier-0) が必ず先頭に固定されることを保証する。

背景:
  T213 の 4段階優先度ソート後でも、Tier-0 内で articleCount の重みが弱く
  小規模クラスタが先に処理されて大規模が放置される事象が観測された
  (本番 2026-04-28 05:13 JST: articles=19/15 の cluster が aiGenerated=False のまま放置)。
  commit 894dd1d / 4d62cbc で _apply_tier0_budget 導入。
  本テストは恒久回帰防止用 (handler.py の Phase A wallclock guard と対で機能)。

2026-04-29 追加:
  Tier-0 以外の rest を _sort_by_recency で「新しい順 (updatedAt 降順, tid フォールバック)」に並べ替える。
  MAX_API_CALLS=30/run 予算を最新トピックから優先消費するため。

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
sort_recency = proc_storage._sort_by_recency


def _topic(tid, ac, ai_gen=False, updated_at=None, score=0):
    item = {'topicId': tid, 'articleCount': ac, 'aiGenerated': ai_gen, 'score': score}
    if updated_at is not None:
        item['updatedAt'] = updated_at
    return item


class Tier0BudgetTest(unittest.TestCase):
    def test_empty_list_passthrough(self):
        self.assertEqual(apply_t0([]), [])

    def test_no_tier0_sorts_by_recency(self):
        """Tier-0 なし → rest 全件が updatedAt 降順 (新しい順) に並ぶ"""
        items = [
            _topic('old', 3, updated_at='2026-04-29T00:01:00Z'),
            _topic('mid', 5, ai_gen=True, updated_at='2026-04-29T00:02:00Z'),
            _topic('new', 1, updated_at='2026-04-29T00:03:00Z'),
        ]
        out = apply_t0(items)
        self.assertEqual([t['topicId'] for t in out], ['new', 'mid', 'old'])

    def test_tier0_promoted_with_recency_sorted_rest(self):
        """Tier-0 は先頭固定 / rest は新しい順"""
        items = [
            _topic('small1', 3, updated_at='2026-04-29T00:04:00Z'),
            _topic('big_done', 19, ai_gen=True, updated_at='2026-04-29T00:03:00Z'),
            _topic('small2', 5, updated_at='2026-04-29T00:02:00Z'),
            _topic('big_pending', 15, updated_at='2026-04-29T00:05:00Z'),  # ★ Tier-0
            _topic('small3', 2, updated_at='2026-04-29T00:01:00Z'),
        ]
        out = apply_t0(items)
        self.assertEqual(out[0]['topicId'], 'big_pending')
        # 残り 4 件 (rest) は updatedAt 降順
        self.assertEqual(
            [t['topicId'] for t in out[1:]],
            ['small1', 'big_done', 'small2', 'small3'],
        )

    def test_multiple_tier0_kept_in_original_order(self):
        """Tier-0 部分は元順を保つ (Tier-0 内のソートは行わない)"""
        items = [
            _topic('m', 3, updated_at='2026-04-29T00:03:00Z'),
            _topic('big_a', 19),  # ★ Tier-0
            _topic('s', 1, updated_at='2026-04-29T00:02:00Z'),
            _topic('big_b', 15),  # ★ Tier-0
            _topic('big_c', 11),  # ★ Tier-0
            _topic('aiGen_big', 20, ai_gen=True, updated_at='2026-04-29T00:01:00Z'),
        ]
        out = apply_t0(items)
        # 先頭 3 件は Tier-0 が元順で並ぶ
        self.assertEqual([t['topicId'] for t in out[:3]], ['big_a', 'big_b', 'big_c'])
        # rest は updatedAt 降順 (m > s > aiGen_big)
        self.assertEqual([t['topicId'] for t in out[3:]], ['m', 's', 'aiGen_big'])

    # T2026-0502-M: 新閾値 (ac>=6 or score>=100) 境界テスト
    def test_articles_exactly_6_qualifies(self):
        """T2026-0502-M: articleCount==6 (新下限) は Tier-0"""
        items = [_topic('small', 3), _topic('boundary', 6)]
        out = apply_t0(items)
        self.assertEqual(out[0]['topicId'], 'boundary')

    def test_articles_5_does_not_qualify_without_score(self):
        """T2026-0502-M: articleCount==5 かつ score<100 は Tier-0 外"""
        items = [
            _topic('small', 3, updated_at='2026-04-29T00:01:00Z'),
            _topic('almost', 5, updated_at='2026-04-29T00:02:00Z', score=50),
        ]
        out = apply_t0(items)
        self.assertEqual([t['topicId'] for t in out], ['almost', 'small'])

    def test_score_exactly_100_qualifies(self):
        """T2026-0502-M: score==100 は ac<6 でも Tier-0"""
        items = [_topic('small', 3), _topic('highscore', 2, score=100)]
        out = apply_t0(items)
        self.assertEqual(out[0]['topicId'], 'highscore')

    def test_score_99_does_not_qualify_without_ac(self):
        """T2026-0502-M: score==99 かつ ac<6 は Tier-0 外"""
        items = [
            _topic('small', 3, updated_at='2026-04-29T00:01:00Z'),
            _topic('almost', 2, score=99, updated_at='2026-04-29T00:02:00Z'),
        ]
        out = apply_t0(items)
        self.assertEqual([t['topicId'] for t in out], ['almost', 'small'])

    def test_ac6_or_score100_both_qualify(self):
        """T2026-0502-M: ac>=6 と score>=100 の両方が Tier-0、OR 条件"""
        items = [
            _topic('small', 3, updated_at='2026-04-29T00:01:00Z'),
            _topic('by_ac', 6, updated_at='2026-04-29T00:02:00Z'),
            _topic('by_score', 2, score=100, updated_at='2026-04-29T00:03:00Z'),
        ]
        out = apply_t0(items)
        tier0_ids = {t['topicId'] for t in out[:2]}
        self.assertEqual(tier0_ids, {'by_ac', 'by_score'})

    def test_articles_exactly_10_qualifies(self):
        """articleCount==10 (旧境界値) も引き続き Tier-0"""
        items = [_topic('small', 3), _topic('boundary', 10)]
        out = apply_t0(items)
        self.assertEqual(out[0]['topicId'], 'boundary')

    def test_aigenerated_true_disqualifies(self):
        """aiGenerated=True なら articleCount に関わらず Tier-0 ではない"""
        items = [
            _topic('small', 3, updated_at='2026-04-29T00:01:00Z'),
            _topic('big_done', 100, ai_gen=True, updated_at='2026-04-29T00:02:00Z'),
        ]
        out = apply_t0(items)
        # rest 内で recency 降順 → big_done が先頭
        self.assertEqual([t['topicId'] for t in out], ['big_done', 'small'])

    def test_budget_caps_tier0_count(self):
        """budget 引数で Tier-0 採用件数を制限できる (デフォルト 100 はほぼ実質全件)"""
        # 全件 ac=12 → 全て Tier-0 候補。budget=2 で先頭 2 件のみ Tier-0 採用、残り 3 件は rest。
        items = [_topic(f't{i}', 12, updated_at=f'2026-04-29T00:0{i}:00Z') for i in range(5)]
        out = apply_t0(items, budget=2)
        # Tier-0 採用は元順 (t0, t1)
        self.assertEqual([t['topicId'] for t in out[:2]], ['t0', 't1'])
        # rest=[t2, t3, t4] → recency 降順 → [t4, t3, t2]
        self.assertEqual([t['topicId'] for t in out[2:]], ['t4', 't3', 't2'])

    def test_invalid_articlecount_treated_as_zero(self):
        """articleCount が文字列・None でも例外を出さず非 Tier-0 扱い"""
        items = [
            {'topicId': 'a', 'articleCount': 'not-a-number'},
            {'topicId': 'b', 'articleCount': None},
            _topic('big', 12),  # ★ Tier-0
        ]
        out = apply_t0(items)
        self.assertEqual(out[0]['topicId'], 'big')


class SortByRecencyTest(unittest.TestCase):
    """2026-04-29 追加: rest の recency ソート挙動を境界値で固定する。"""

    def test_empty_returns_empty(self):
        self.assertEqual(sort_recency([]), [])

    def test_updatedat_descending(self):
        """updatedAt 降順 (新しい順)"""
        items = [
            {'topicId': 'a', 'updatedAt': '2026-04-29T00:01:00Z'},
            {'topicId': 'b', 'updatedAt': '2026-04-29T00:03:00Z'},
            {'topicId': 'c', 'updatedAt': '2026-04-29T00:02:00Z'},
        ]
        out = sort_recency(items)
        self.assertEqual([t['topicId'] for t in out], ['b', 'c', 'a'])

    def test_topicid_fallback_when_no_updatedat(self):
        """updatedAt がない場合は topicId 降順でフォールバック"""
        items = [
            {'topicId': 'aaa'},
            {'topicId': 'ccc'},
            {'topicId': 'bbb'},
        ]
        out = sort_recency(items)
        self.assertEqual([t['topicId'] for t in out], ['ccc', 'bbb', 'aaa'])

    def test_updatedat_present_beats_missing(self):
        """updatedAt あり > updatedAt なし"""
        items = [
            {'topicId': 'no_ua_z'},                                    # tid='z' でも negative
            {'topicId': 'has_ua_a', 'updatedAt': '2026-04-29T00:01Z'},  # tid='a' でも updatedAt あり優先
        ]
        out = sort_recency(items)
        self.assertEqual([t['topicId'] for t in out], ['has_ua_a', 'no_ua_z'])

    def test_empty_string_updatedat_treated_as_missing(self):
        """updatedAt='' は欠損扱い → topicId フォールバック"""
        items = [
            {'topicId': 'a', 'updatedAt': ''},
            {'topicId': 'b', 'updatedAt': '2026-04-29T00:01Z'},
        ]
        out = sort_recency(items)
        self.assertEqual([t['topicId'] for t in out], ['b', 'a'])

    def test_none_updatedat_treated_as_missing(self):
        """updatedAt=None は欠損扱い"""
        items = [
            {'topicId': 'a', 'updatedAt': None},
            {'topicId': 'b', 'updatedAt': '2026-04-29T00:01Z'},
        ]
        out = sort_recency(items)
        self.assertEqual([t['topicId'] for t in out], ['b', 'a'])

    def test_same_updatedat_breaks_with_topicid(self):
        """updatedAt が完全一致 → tid 降順でタイブレーク"""
        ua = '2026-04-29T00:01:00Z'
        items = [
            {'topicId': 'a', 'updatedAt': ua},
            {'topicId': 'c', 'updatedAt': ua},
            {'topicId': 'b', 'updatedAt': ua},
        ]
        out = sort_recency(items)
        self.assertEqual([t['topicId'] for t in out], ['c', 'b', 'a'])

    def test_missing_topicid_does_not_crash(self):
        """topicId 欠損でも例外を出さない"""
        items = [
            {'updatedAt': '2026-04-29T00:01Z'},
            {'topicId': 'a', 'updatedAt': '2026-04-29T00:02Z'},
        ]
        out = sort_recency(items)
        # 欠損 tid は '' として扱われる
        self.assertEqual(out[0].get('topicId'), 'a')


if __name__ == '__main__':
    unittest.main()
