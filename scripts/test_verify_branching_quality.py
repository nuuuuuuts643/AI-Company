"""T2026-0501-E: verify_branching_quality.py の純粋関数をテスト。

ネットワーク I/O は行わず、collect_branched_pairs / evaluate_pair / evaluate_branching の
3 つを fixture topic データで検証する。

実行: python3 -m unittest scripts.test_verify_branching_quality -v
"""
from __future__ import annotations

import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location(
    'verify_branching_quality', os.path.join(ROOT, 'verify_branching_quality.py')
)
mod = importlib.util.module_from_spec(SPEC)
sys.modules['verify_branching_quality'] = mod
SPEC.loader.exec_module(mod)


def _topic(tid, title, *, parent=None, story_phase=None, ac=1, kp=None):
    return {
        'topicId': tid,
        'title': title,
        'parentTopicId': parent,
        'storyPhase': story_phase,
        'articleCount': ac,
        'keyPoint': kp,
    }


class CollectBranchedPairsTest(unittest.TestCase):
    def test_no_topics(self):
        pairs, branched_total, orphans = mod.collect_branched_pairs([])
        self.assertEqual(pairs, [])
        self.assertEqual(branched_total, 0)
        self.assertEqual(orphans, 0)

    def test_orphan_parent_id(self):
        # parentTopicId を持つが parent が見つからない → orphan
        topics = [
            _topic('child1', '子', parent='missing', story_phase='development', ac=3),
        ]
        pairs, branched_total, orphans = mod.collect_branched_pairs(topics)
        self.assertEqual(pairs, [])
        self.assertEqual(branched_total, 1)
        self.assertEqual(orphans, 1)

    def test_filters_no_storyphase(self):
        topics = [
            _topic('p1', 'parent'),
            _topic('c1', 'child', parent='p1', story_phase=None, ac=3),
        ]
        pairs, branched_total, orphans = mod.collect_branched_pairs(topics)
        self.assertEqual(pairs, [])  # storyPhase が無いと除外
        self.assertEqual(branched_total, 1)
        self.assertEqual(orphans, 0)

    def test_filters_low_article_count(self):
        topics = [
            _topic('p1', 'parent'),
            _topic('c1', 'child', parent='p1', story_phase='development', ac=1),
        ]
        pairs, _, _ = mod.collect_branched_pairs(topics)
        self.assertEqual(pairs, [])  # ac < 2 で除外

    def test_collects_valid_pair(self):
        topics = [
            _topic('p1', 'parent'),
            _topic('c1', 'child', parent='p1', story_phase='development', ac=3),
        ]
        pairs, branched_total, orphans = mod.collect_branched_pairs(topics)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]['parent']['topicId'], 'p1')
        self.assertEqual(pairs[0]['child']['topicId'], 'c1')
        self.assertEqual(branched_total, 1)
        self.assertEqual(orphans, 0)


class EvaluatePairTest(unittest.TestCase):
    def test_high_similarity_is_false_branch(self):
        parent = {'title': 'AI規制法案、議会通過'}
        child = {'title': 'AI規制法案、議会通過の続報'}
        r = mod.evaluate_pair(parent, child)
        self.assertEqual(r['verdict'], 'suspect_false_branch')
        self.assertGreaterEqual(r['similarity'], 0.6)

    def test_low_similarity_is_false_merge(self):
        parent = {'title': '株価急騰、日経平均最高値'}
        child = {'title': 'プログラミング言語Rust採用拡大'}
        r = mod.evaluate_pair(parent, child)
        self.assertEqual(r['verdict'], 'suspect_false_merge')
        self.assertLess(r['similarity'], 0.2)

    def test_medium_similarity_is_ok(self):
        parent = {'title': 'AI企業、新製品発表'}
        child = {'title': 'AI企業、追加投資を実施'}
        r = mod.evaluate_pair(parent, child)
        # bigram Jaccard が 0.2 〜 0.6 の中間ゾーン
        self.assertEqual(r['verdict'], 'ok')


class EvaluateBranchingTest(unittest.TestCase):
    """sample 数による verdict 切替を中心にテスト。"""

    def test_no_branching_returns_skip_no_branch(self):
        topics = [_topic('a', 'foo'), _topic('b', 'bar')]
        out = mod.evaluate_branching(topics, sample_size=30, min_sample=10)
        self.assertEqual(out['verdict'], 'SKIP_NO_BRANCH')
        self.assertEqual(out['sample'], 0)

    def test_small_sample_returns_skip_small_sample(self):
        # 4 ペアのみ (T2026-0501-E が解決する誤 FAIL ケース)
        topics = [_topic('p1', 'parent1'), _topic('p2', 'parent2'),
                  _topic('p3', 'parent3'), _topic('p4', 'parent4')]
        topics += [
            # parent と child の title 類似度を意図的に高くして false_branch にする
            _topic('c1', 'parent1の続報', parent='p1', story_phase='development', ac=3),
            _topic('c2', 'parent2の続報', parent='p2', story_phase='development', ac=3),
            _topic('c3', 'parent3の続報', parent='p3', story_phase='development', ac=3),
            _topic('c4', 'parent4の続報', parent='p4', story_phase='development', ac=3),
        ]
        out = mod.evaluate_branching(topics, sample_size=30, min_sample=10)
        # min_sample=10 未満のサンプル数 (4) なので SKIP
        self.assertEqual(out['verdict'], 'SKIP_SMALL_SAMPLE')
        self.assertEqual(out['sample'], 4)
        # メトリクス自体は計算されている (観測用)
        self.assertGreater(out['false_branch_rate'], 0)

    def test_small_sample_passes_when_min_lowered(self):
        # min_sample=2 に下げれば判定が走る
        topics = [_topic('p1', '株価上昇'), _topic('p2', '為替動向')]
        topics += [
            _topic('c1', 'プログラミング言語', parent='p1', story_phase='development', ac=3),
            _topic('c2', '料理レシピ', parent='p2', story_phase='development', ac=3),
        ]
        out = mod.evaluate_branching(topics, sample_size=30, min_sample=2)
        # sample=2 >= min_sample=2 なので判定が走る (両方類似度低 → false_merge=100%)
        self.assertIn(out['verdict'], ('FAIL', 'PASS'))
        self.assertEqual(out['sample'], 2)

    def test_pass_when_all_pairs_ok(self):
        # 中間ゾーン (0.2 < sim < 0.6) のペアを 12 件作って PASS させる
        topics = []
        for i in range(12):
            topics.append(_topic(f'p{i}', f'AI企業{i}号、新製品発表'))
            topics.append(_topic(
                f'c{i}', f'AI企業{i}号、追加投資を実施',
                parent=f'p{i}', story_phase='development', ac=3,
            ))
        out = mod.evaluate_branching(topics, sample_size=30, min_sample=10)
        self.assertEqual(out['verdict'], 'PASS')
        self.assertEqual(out['sample'], 12)
        self.assertLessEqual(out['false_branch_rate'], 20.0)
        self.assertLessEqual(out['false_merge_rate'], 15.0)

    def test_fail_when_threshold_exceeded(self):
        # 類似度が高すぎるペアを 15 件作って FAIL させる
        topics = []
        for i in range(15):
            topics.append(_topic(f'p{i}', f'政府が経済対策を検討案件{i}'))
            topics.append(_topic(
                f'c{i}', f'政府が経済対策を検討案件{i}の続報',
                parent=f'p{i}', story_phase='development', ac=3,
            ))
        out = mod.evaluate_branching(topics, sample_size=30, min_sample=10)
        self.assertEqual(out['verdict'], 'FAIL')
        self.assertGreater(out['false_branch_rate'], 20.0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
