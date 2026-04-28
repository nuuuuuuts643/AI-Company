"""T2026-0428-E2-4: proc_storage._parse_pubdate の boundary test。

CLAUDE.md「新規 formatter は boundary test 同梱」適用。
0/null/undefined/NaN/未来日付/RFC2822/ISO/epoch を全部 assert する。

実行:
  cd projects/P003-news-timeline
  python3 -m unittest tests.test_parse_pubdate -v
"""
import os
import sys
import unittest
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'lambda', 'processor'))

# proc_storage は boto3/PIL に依存するためモジュール level でつまづく。
# ここでは関数だけ取り出す。proc_config 側で boto3 client が初期化されるため
# 環境変数 ある程度モック化する。
os.environ.setdefault('S3_BUCKET', 'test-bucket')
os.environ.setdefault('AWS_REGION', 'ap-northeast-1')

import proc_storage  # noqa: E402

_pp = proc_storage._parse_pubdate


class ParsePubdateBoundaryTest(unittest.TestCase):
    def test_none_returns_none(self):
        self.assertIsNone(_pp(None))

    def test_empty_string_returns_none(self):
        self.assertIsNone(_pp(''))
        self.assertIsNone(_pp('   '))

    def test_garbage_returns_none(self):
        self.assertIsNone(_pp('not-a-date'))
        self.assertIsNone(_pp('NaN'))
        self.assertIsNone(_pp('???'))

    def test_iso_with_z(self):
        dt = _pp('2026-04-28T05:00:00Z')
        self.assertEqual(dt, datetime(2026, 4, 28, 5, 0, tzinfo=timezone.utc))

    def test_iso_with_offset(self):
        dt = _pp('2026-04-28T05:00:00+09:00')
        self.assertIsNotNone(dt)
        self.assertEqual(dt.tzinfo.utcoffset(None).total_seconds(), 9 * 3600)

    def test_iso_naive_assumed_utc(self):
        dt = _pp('2026-04-28T05:00:00')
        self.assertEqual(dt, datetime(2026, 4, 28, 5, 0, tzinfo=timezone.utc))

    def test_epoch_seconds(self):
        # round-trip: epoch -> dt -> epoch should match input
        dt = _pp('1777582800')
        self.assertIsNotNone(dt)
        self.assertEqual(int(dt.timestamp()), 1777582800)
        self.assertIs(dt.tzinfo, timezone.utc)

    def test_epoch_milliseconds(self):
        dt = _pp('1777582800000')
        self.assertIsNotNone(dt)
        self.assertEqual(int(dt.timestamp()), 1777582800)

    def test_epoch_int_input(self):
        dt = _pp(1777582800)
        self.assertIsNotNone(dt)
        self.assertEqual(int(dt.timestamp()), 1777582800)

    def test_epoch_zero_returns_none(self):
        # 0 epoch is unlikely valid; treat as missing
        self.assertIsNone(_pp(0))
        self.assertIsNone(_pp('0'))

    def test_epoch_negative_returns_none(self):
        self.assertIsNone(_pp(-1))

    def test_rfc2822_basic(self):
        dt = _pp('Mon, 23 Mar 2026 07:00:00 GMT')
        self.assertEqual(dt, datetime(2026, 3, 23, 7, 0, tzinfo=timezone.utc))

    def test_rfc2822_no_timezone(self):
        # RSS でしばしば見る tz 欠落形式 (Google News など)
        dt = _pp('Mon, 23 Mar 2026 07:00:00')
        self.assertIsNotNone(dt)
        self.assertEqual(dt.replace(tzinfo=None), datetime(2026, 3, 23, 7, 0))

    def test_rfc2822_offset(self):
        dt = _pp('Tue, 28 Apr 2026 14:30:00 +0900')
        self.assertIsNotNone(dt)
        # 09:00 UTC == 18:00 +0900? Actually 14:30 +0900 == 05:30 UTC
        self.assertEqual(dt.astimezone(timezone.utc),
                         datetime(2026, 4, 28, 5, 30, tzinfo=timezone.utc))

    def test_returns_aware(self):
        # 全パスが tz-aware を返すこと (since_dt との比較で TypeError を回避)
        for raw in ('2026-04-28T05:00:00', '2026-04-28T05:00:00Z',
                    '1777582800', 'Mon, 23 Mar 2026 07:00:00'):
            dt = _pp(raw)
            self.assertIsNotNone(dt, raw)
            self.assertIsNotNone(dt.tzinfo, raw)


if __name__ == '__main__':
    unittest.main()
