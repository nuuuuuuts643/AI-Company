"""T2026-0502-BC: judge_prediction 期限到来絞込のテスト

背景:
  PRED# 823件中 predictionResult=pending 45件・matched/partial/missed が 0 件。
  毎回 judge_prediction で Anthropic API 叩いているのに signal が出ていない＝壊れている状態。

対策:
  - `_extract_deadline_offset_days(outlook)` で outlook 文中の期限フレーズを解析し
    予想立て時刻からの日数 (offset) を返す。
  - `is_eligible_for_judgment(outlook, made_at_iso)` で期限到来済か判定。
    期限未到来なら handler.py 側で API 呼び出しを skip。
  - 期限フレーズが outlook にない場合は fallback_days=7 で保守的判定。

期待効果:
  - judge_prediction Anthropic API 呼び出し -70〜90% (期限未到来分の skip)
  - matched/partial/missed の発生数 0→1+ 件 (期限到来後にしか judge しないため signal 出やすい)

実行:
  cd projects/P003-news-timeline
  python3 -m unittest tests.test_judge_prediction_eligibility -v
"""
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'lambda', 'processor'))

os.environ.setdefault('S3_BUCKET', 'test-bucket')
os.environ.setdefault('AWS_REGION', 'ap-northeast-1')

import proc_ai  # noqa: E402

extract_deadline = proc_ai._extract_deadline_offset_days
is_eligible = proc_ai.is_eligible_for_judgment


class ExtractDeadlineOffsetDaysTest(unittest.TestCase):
    """`_extract_deadline_offset_days` の各パターン網羅"""

    def test_konshu_returns_7(self):
        self.assertEqual(extract_deadline('今週中に方向性が定まる [確信度:中]'), 7)

    def test_raishu_returns_14(self):
        self.assertEqual(extract_deadline('来週末までに発表される可能性 [確信度:中]'), 14)

    def test_kongetsu_returns_30(self):
        self.assertEqual(extract_deadline('今月中の合意は厳しい [確信度:低]'), 30)

    def test_raigetsu_returns_60(self):
        self.assertEqual(extract_deadline('来月の利下げ判断が焦点 [確信度:中]'), 60)

    def test_3kagetsu_returns_90(self):
        self.assertEqual(extract_deadline('3ヶ月以内に新製品発表 [確信度:中]'), 90)

    def test_hantoshi_returns_180(self):
        self.assertEqual(extract_deadline('半年で結論が出る [確信度:中]'), 180)

    def test_nennai_returns_365(self):
        self.assertEqual(extract_deadline('年内には決着 [確信度:中]'), 365)

    def test_specific_days(self):
        self.assertEqual(extract_deadline('30日以内に判決 [確信度:高]'), 30)
        self.assertEqual(extract_deadline('60日後に発表 [確信度:中]'), 60)

    def test_specific_weeks(self):
        self.assertEqual(extract_deadline('2週間以内に再開 [確信度:中]'), 14)
        self.assertEqual(extract_deadline('3週間後に判定 [確信度:中]'), 21)

    def test_specific_months(self):
        self.assertEqual(extract_deadline('2ヶ月以内に解決 [確信度:中]'), 60)
        self.assertEqual(extract_deadline('6ヶ月後に再評価 [確信度:中]'), 180)

    def test_no_deadline_returns_none(self):
        self.assertIsNone(extract_deadline('市場の動向に注目したい [確信度:低]'))

    def test_empty_returns_none(self):
        self.assertIsNone(extract_deadline(''))
        self.assertIsNone(extract_deadline(None))


class IsEligibleForJudgmentTest(unittest.TestCase):
    """`is_eligible_for_judgment` の境界条件"""

    def _now(self):
        return datetime(2026, 5, 2, 12, 0, 0, tzinfo=timezone.utc)

    def _made_at_days_ago(self, days):
        return (self._now() - timedelta(days=days)).isoformat()

    def test_konshu_eligible_after_7_days(self):
        """今週中 → 7d 以内なら未到来・8d 以降で到来"""
        outlook = '今週中に決着 [確信度:中]'
        self.assertFalse(is_eligible(outlook, self._made_at_days_ago(3), now_utc=self._now()))
        self.assertFalse(is_eligible(outlook, self._made_at_days_ago(6), now_utc=self._now()))
        self.assertTrue(is_eligible(outlook, self._made_at_days_ago(7), now_utc=self._now()))
        self.assertTrue(is_eligible(outlook, self._made_at_days_ago(10), now_utc=self._now()))

    def test_raishu_eligible_after_14_days(self):
        """来週 → 14d 以降で到来"""
        outlook = '来週末に発表予定 [確信度:中]'
        self.assertFalse(is_eligible(outlook, self._made_at_days_ago(7), now_utc=self._now()))
        self.assertTrue(is_eligible(outlook, self._made_at_days_ago(14), now_utc=self._now()))

    def test_3kagetsu_eligible_after_90_days(self):
        outlook = '3ヶ月以内に判決 [確信度:高]'
        self.assertFalse(is_eligible(outlook, self._made_at_days_ago(60), now_utc=self._now()))
        self.assertTrue(is_eligible(outlook, self._made_at_days_ago(90), now_utc=self._now()))

    def test_no_deadline_uses_fallback_7d(self):
        """期限フレーズなし → fallback_days=7 で保守的判定"""
        outlook = '市場の反応に注目したい [確信度:低]'
        self.assertFalse(is_eligible(outlook, self._made_at_days_ago(3), now_utc=self._now()))
        self.assertFalse(is_eligible(outlook, self._made_at_days_ago(6), now_utc=self._now()))
        self.assertTrue(is_eligible(outlook, self._made_at_days_ago(7), now_utc=self._now()))

    def test_no_deadline_with_custom_fallback(self):
        """fallback_days=14 を渡した場合"""
        outlook = '見守りたい [確信度:低]'
        self.assertFalse(is_eligible(outlook, self._made_at_days_ago(10),
                                      now_utc=self._now(), fallback_days=14))
        self.assertTrue(is_eligible(outlook, self._made_at_days_ago(14),
                                     now_utc=self._now(), fallback_days=14))

    def test_invalid_made_at_returns_true_safely(self):
        """不正な made_at は判定不能なので保守的に True (既存挙動温存)"""
        outlook = '今週中に決着 [確信度:中]'
        self.assertTrue(is_eligible(outlook, '', now_utc=self._now()))
        self.assertTrue(is_eligible(outlook, 'not-a-date', now_utc=self._now()))
        self.assertTrue(is_eligible(outlook, None, now_utc=self._now()))

    def test_specific_pattern_overrides_keyword(self):
        """数値パターン (30日以内) が他キーワードより優先"""
        outlook = '30日以内に判決 [確信度:高]'
        self.assertEqual(extract_deadline(outlook), 30)
        # 30 days = at deadline
        self.assertTrue(is_eligible(outlook, self._made_at_days_ago(30), now_utc=self._now()))
        self.assertFalse(is_eligible(outlook, self._made_at_days_ago(20), now_utc=self._now()))

    def test_eligibility_uses_now_param(self):
        """now_utc パラメータで時刻を注入できる"""
        outlook = '今週中 [確信度:中]'
        made_at = '2026-04-01T00:00:00+00:00'
        # 2026-04-08 = exactly 7d after made_at
        now_after = datetime(2026, 4, 8, 0, 0, 0, tzinfo=timezone.utc)
        now_before = datetime(2026, 4, 7, 0, 0, 0, tzinfo=timezone.utc)
        self.assertTrue(is_eligible(outlook, made_at, now_utc=now_after))
        self.assertFalse(is_eligible(outlook, made_at, now_utc=now_before))


class CostReductionScenarioTest(unittest.TestCase):
    """実際のシナリオでコスト削減効果が出るか確認"""

    def test_typical_pending_predictions_with_short_deadline(self):
        """1日前に「今週中」予想 → 期限未到来 = API skip"""
        now = datetime(2026, 5, 2, 12, 0, 0, tzinfo=timezone.utc)
        made_at = (now - timedelta(days=1)).isoformat()
        outlook = '今週中に方向性が定まる [確信度:中]'
        # 1d 経過・期限 7d → 未到来
        self.assertFalse(is_eligible(outlook, made_at, now_utc=now))

    def test_long_deadline_predictions_skipped_for_long_time(self):
        """半年予想 → 6ヶ月経つまで skip"""
        now = datetime(2026, 5, 2, 12, 0, 0, tzinfo=timezone.utc)
        outlook = '半年以内に新製品発表 [確信度:中]'
        # 90d 経過 (3ヶ月) → 未到来
        made_at_90d = (now - timedelta(days=90)).isoformat()
        self.assertFalse(is_eligible(outlook, made_at_90d, now_utc=now))
        # 180d 経過 (6ヶ月) → 到来
        made_at_180d = (now - timedelta(days=180)).isoformat()
        self.assertTrue(is_eligible(outlook, made_at_180d, now_utc=now))

    def test_no_deadline_falls_to_7d_default(self):
        """期限フレーズなし & 1d 経過 → fallback (7d) 未到来 = skip"""
        now = datetime(2026, 5, 2, 12, 0, 0, tzinfo=timezone.utc)
        made_at = (now - timedelta(days=1)).isoformat()
        outlook = '市場の動向を見守りたい [確信度:低]'
        self.assertFalse(is_eligible(outlook, made_at, now_utc=now))


if __name__ == '__main__':
    unittest.main()
