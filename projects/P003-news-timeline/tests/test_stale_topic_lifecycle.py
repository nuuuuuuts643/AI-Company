"""T2026-0501-F2 regression test: compute_lifecycle_status の 72h archive 境界値テスト
+ handler.py の非更新トピック lifecycle 再計算ロジック

背景:
  旧実装は 48h〜7日を無条件 cooling にしていたため、velocity=0 のトピックが
  最大7日間 topics.json に残留し stale48h SLI が 39% (>30% 閾値) になっていた。
  修正: 72h 超 + velocity=0 → archived。48〜72h は grace period (cooling 維持)。

実行:
  cd projects/P003-news-timeline
  python3 -m unittest tests.test_stale_topic_lifecycle -v
"""
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'fetcher'))

from score_utils import compute_lifecycle_status


class TestComputeLifecycleStatus(unittest.TestCase):

    def _ts(self, hours_ago: float) -> int:
        return int(time.time()) - int(hours_ago * 3600)

    # --- active boundary ---

    def test_active_under_48h(self):
        self.assertEqual(compute_lifecycle_status(10, self._ts(47), 5, 5), 'active')

    def test_active_at_0h(self):
        self.assertEqual(compute_lifecycle_status(10, self._ts(0), 0, 3), 'active')

    def test_active_exactly_47h(self):
        self.assertEqual(compute_lifecycle_status(0, self._ts(47.9), 0, 3), 'active')

    # --- cooling grace period (48〜72h) ---

    def test_cooling_at_48h_zero_velocity(self):
        # 48h 超でも 72h 未満は grace period → cooling (velocity=0 でも)
        self.assertEqual(compute_lifecycle_status(0, self._ts(48.1), 0, 3), 'cooling')

    def test_cooling_at_71h_zero_velocity(self):
        self.assertEqual(compute_lifecycle_status(0, self._ts(71.9), 0, 3), 'cooling')

    def test_cooling_at_50h_nonzero_velocity(self):
        self.assertEqual(compute_lifecycle_status(5, self._ts(50), 3, 5), 'cooling')

    # --- archived: 72h+ with zero velocity ---

    def test_archived_at_72h_zero_velocity(self):
        self.assertEqual(compute_lifecycle_status(0, self._ts(72.1), 0, 3), 'archived')

    def test_archived_at_7days_zero_velocity(self):
        self.assertEqual(compute_lifecycle_status(0, self._ts(168), 0, 5), 'archived')

    def test_archived_with_null_velocity(self):
        # velocity_score=0 is falsy — must archive after 72h
        self.assertEqual(compute_lifecycle_status(100, self._ts(80), 0, 10), 'archived')

    # --- cooling: 72h+ but velocity > 0 (still active story) ---

    def test_cooling_at_72h_with_velocity(self):
        self.assertEqual(compute_lifecycle_status(5, self._ts(72.1), 2, 8), 'cooling')

    def test_cooling_long_running_high_velocity(self):
        self.assertEqual(compute_lifecycle_status(50, self._ts(200), 10, 30), 'cooling')

    # --- boundary: last_article_ts=0 ---

    def test_zero_ts_treated_as_very_old(self):
        # last_article_ts=0 means epoch → very old → archived if velocity=0
        result = compute_lifecycle_status(0, 0, 0, 3)
        self.assertEqual(result, 'archived')


if __name__ == '__main__':
    unittest.main()
