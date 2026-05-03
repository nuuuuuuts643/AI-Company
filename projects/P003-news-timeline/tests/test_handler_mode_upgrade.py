"""T2026-0502-MU: summaryMode 昇格ロジック (_expected_mode / _is_mode_upgrade) の境界値テスト。

背景:
  proc_ai.py:723-728 で mode は cnt に応じて自動選択される:
    cnt<=2 → minimal / cnt<=5 → standard / cnt>=6 → full
  しかし旧 handler.py では needs_story 判定が
    「aiGenerated AND 全必須フィールド充足」のみを見て、
    現在の summaryMode が cnt にふさわしいかを確認していなかった。
  実害: ac=14 の topic が standard 止まりで forecast/timeline が一度も生成されない。

実行:
  cd projects/P003-news-timeline
  python3 -m unittest tests.test_handler_mode_upgrade -v
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'lambda', 'processor'))

from handler import _expected_mode, _is_mode_upgrade  # type: ignore


class ExpectedModeTest(unittest.TestCase):
    """_expected_mode の境界値テスト (proc_ai.py との一致確認)。"""

    def test_cnt_0_is_minimal(self):
        self.assertEqual(_expected_mode(0), 'minimal')

    def test_cnt_1_is_minimal(self):
        self.assertEqual(_expected_mode(1), 'minimal')

    def test_cnt_2_is_standard(self):
        # T2026-0503-UX-WATCHPOINTS/PERSPECTIVES-FILL: cnt=2 → standard に昇格
        self.assertEqual(_expected_mode(2), 'standard')

    def test_cnt_3_is_standard(self):
        self.assertEqual(_expected_mode(3), 'standard')

    def test_cnt_5_is_standard(self):
        self.assertEqual(_expected_mode(5), 'standard')

    def test_cnt_6_is_full(self):
        # 境界値: 6 から full
        self.assertEqual(_expected_mode(6), 'full')

    def test_cnt_14_is_full(self):
        # 実害事例 (ac=14 の EU自動車関税 topic)
        self.assertEqual(_expected_mode(14), 'full')

    def test_cnt_100_is_full(self):
        self.assertEqual(_expected_mode(100), 'full')


class IsModeUpgradeTest(unittest.TestCase):
    """_is_mode_upgrade の境界値テスト (昇格のみ True / ダウングレード抑制)。"""

    # ---- 昇格: True ----
    def test_minimal_to_standard_is_upgrade(self):
        self.assertTrue(_is_mode_upgrade('minimal', 'standard'))

    def test_minimal_to_full_is_upgrade(self):
        self.assertTrue(_is_mode_upgrade('minimal', 'full'))

    def test_standard_to_full_is_upgrade(self):
        self.assertTrue(_is_mode_upgrade('standard', 'full'))

    # ---- 同水準: False ----
    def test_same_minimal_not_upgrade(self):
        self.assertFalse(_is_mode_upgrade('minimal', 'minimal'))

    def test_same_standard_not_upgrade(self):
        self.assertFalse(_is_mode_upgrade('standard', 'standard'))

    def test_same_full_not_upgrade(self):
        self.assertFalse(_is_mode_upgrade('full', 'full'))

    # ---- ダウングレード: False (抑制) ----
    def test_full_to_standard_not_upgrade(self):
        # cnt が減った場合 (記事削除等) で full→standard は呼ばない
        self.assertFalse(_is_mode_upgrade('full', 'standard'))

    def test_full_to_minimal_not_upgrade(self):
        self.assertFalse(_is_mode_upgrade('full', 'minimal'))

    def test_standard_to_minimal_not_upgrade(self):
        self.assertFalse(_is_mode_upgrade('standard', 'minimal'))

    # ---- 不明な mode: False ----
    def test_unknown_current_not_upgrade(self):
        self.assertFalse(_is_mode_upgrade('', 'full'))

    def test_unknown_expected_not_upgrade(self):
        self.assertFalse(_is_mode_upgrade('standard', ''))


class ModeUpgradeIntegrationTest(unittest.TestCase):
    """_expected_mode + _is_mode_upgrade を組み合わせた needs_story 相当の判定テスト。"""

    def _needs_upgrade(self, current_mode: str, cnt: int) -> bool:
        return bool(current_mode) and _is_mode_upgrade(current_mode, _expected_mode(cnt))

    def test_standard_topic_cnt6_needs_upgrade(self):
        # 実害シナリオ: ac=6 になったが summaryMode=standard のまま → upgrade 必要
        self.assertTrue(self._needs_upgrade('standard', 6))

    def test_standard_topic_cnt14_needs_upgrade(self):
        # ac=14 (EU自動車関税 実害事例) → upgrade 必要
        self.assertTrue(self._needs_upgrade('standard', 14))

    def test_minimal_topic_cnt3_needs_upgrade(self):
        # cnt=3 になったが summaryMode=minimal のまま → standard へ upgrade 必要
        self.assertTrue(self._needs_upgrade('minimal', 3))

    def test_full_topic_cnt14_no_upgrade(self):
        # 既に full で cnt=14 → upgrade 不要
        self.assertFalse(self._needs_upgrade('full', 14))

    def test_standard_topic_cnt5_no_upgrade(self):
        # cnt=5 は standard が期待値 → upgrade 不要
        self.assertFalse(self._needs_upgrade('standard', 5))

    def test_standard_topic_cnt4_no_upgrade(self):
        # cnt=4 は standard → upgrade 不要
        self.assertFalse(self._needs_upgrade('standard', 4))

    def test_full_topic_cnt4_no_downgrade(self):
        # cnt=4 (standard 期待) だが既に full → ダウングレード抑制 → upgrade 不要
        self.assertFalse(self._needs_upgrade('full', 4))

    def test_empty_mode_no_upgrade(self):
        # summaryMode 未設定 → _current_mode='' → upgrade 判定しない (初回処理扱い)
        self.assertFalse(self._needs_upgrade('', 6))

    def test_boundary_cnt5_standard_no_upgrade(self):
        # 境界値: cnt=5 → standard が期待値、現在 standard → upgrade 不要
        self.assertFalse(self._needs_upgrade('standard', 5))

    def test_boundary_cnt6_standard_needs_upgrade(self):
        # 境界値: cnt=6 → full が期待値、現在 standard → upgrade 必要
        self.assertTrue(self._needs_upgrade('standard', 6))

    def test_boundary_cnt2_minimal_needs_upgrade(self):
        # T2026-0503-UX-WATCHPOINTS/PERSPECTIVES-FILL: cnt=2 → standard、現在 minimal → upgrade 必要
        self.assertTrue(self._needs_upgrade('minimal', 2))

    def test_boundary_cnt2_standard_no_upgrade(self):
        # cnt=2 → standard、現在 standard → upgrade 不要
        self.assertFalse(self._needs_upgrade('standard', 2))

    def test_boundary_cnt3_minimal_needs_upgrade(self):
        # 境界値: cnt=3 → standard、現在 minimal → upgrade 必要
        self.assertTrue(self._needs_upgrade('minimal', 3))


if __name__ == '__main__':
    unittest.main()
