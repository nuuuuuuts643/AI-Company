"""T235: _call_claude の 5xx / network リトライ動作 boundary test。

CLAUDE.md「新規 formatter は boundary test 同梱」を変更関数にも適用。
mock で urllib.request.urlopen を差し替えて 429/500/502/503/504/network を検証。

実行:
  cd projects/P003-news-timeline
  ANTHROPIC_API_KEY=dummy python3 -m unittest tests.test_proc_ai_retry -v
"""
import io
import json
import os
import sys
import types
import unittest
import urllib.error
from unittest import mock

# ANTHROPIC_API_KEY が無いと proc_config が SystemExit するため事前注入
os.environ.setdefault('ANTHROPIC_API_KEY', 'sk-ant-dummy-for-test')

# import path: <repo>/projects/P003-news-timeline/lambda/processor/proc_ai.py
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'lambda', 'processor'))

# proc_config は boto3 import を含み Lambda 外環境では未インストール。
# テスト目的では ANTHROPIC_API_KEY だけあれば十分なので fake module を挿入する。
if 'proc_config' not in sys.modules:
    fake = types.ModuleType('proc_config')
    fake.ANTHROPIC_API_KEY = os.environ['ANTHROPIC_API_KEY']
    sys.modules['proc_config'] = fake

import proc_ai  # noqa: E402


class _FakeResponse:
    def __init__(self, body):
        self._body = body if isinstance(body, bytes) else json.dumps(body).encode('utf-8')

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body


def _make_http_error(code, retry_after=None):
    headers = {}
    if retry_after is not None:
        headers['retry-after'] = str(retry_after)
    return urllib.error.HTTPError(
        url='https://api.anthropic.com/v1/messages',
        code=code,
        msg=f'HTTP {code}',
        hdrs=headers,
        fp=io.BytesIO(b'{"error":"forced"}'),
    )


class CallClaudeRetryTest(unittest.TestCase):

    def setUp(self):
        # time.sleep を stub して高速化
        self._sleep_patch = mock.patch('proc_ai.time.sleep', return_value=None)
        self._sleep_patch.start()

    def tearDown(self):
        self._sleep_patch.stop()

    def test_429_then_success(self):
        """429 で 1 回 retry → 成功 を返す。"""
        side = [
            _make_http_error(429, retry_after=1),
            _FakeResponse({'ok': True, 'attempt': 2}),
        ]
        with mock.patch('proc_ai.urllib.request.urlopen', side_effect=side):
            result = proc_ai._call_claude({'msg': 'x'})
        self.assertEqual(result['ok'], True)

    def test_500_then_success(self):
        """500 もリトライ対象に追加 (T235)。"""
        side = [
            _make_http_error(500),
            _FakeResponse({'ok': True}),
        ]
        with mock.patch('proc_ai.urllib.request.urlopen', side_effect=side):
            result = proc_ai._call_claude({'msg': 'x'})
        self.assertEqual(result['ok'], True)

    def test_503_three_times_then_success(self):
        """503 が 3 回続いても 4 回目で成功すれば返す。"""
        side = [
            _make_http_error(503),
            _make_http_error(503),
            _make_http_error(503),
            _FakeResponse({'ok': True, 'attempt': 4}),
        ]
        with mock.patch('proc_ai.urllib.request.urlopen', side_effect=side):
            result = proc_ai._call_claude({'msg': 'x'})
        self.assertEqual(result['attempt'], 4)

    def test_504_exhausted_raises(self):
        """504 が 4 回連続で起きたら最終的に raise。上位は失敗を観測する。"""
        side = [_make_http_error(504)] * 4
        with mock.patch('proc_ai.urllib.request.urlopen', side_effect=side):
            with self.assertRaises(urllib.error.HTTPError):
                proc_ai._call_claude({'msg': 'x'})

    def test_400_no_retry(self):
        """400 系 (4xx, 429 以外) はリトライせず即時 raise。回数増やさない。"""
        side = [_make_http_error(400)]
        with mock.patch('proc_ai.urllib.request.urlopen', side_effect=side) as urlopen:
            with self.assertRaises(urllib.error.HTTPError):
                proc_ai._call_claude({'msg': 'x'})
            self.assertEqual(urlopen.call_count, 1)

    def test_network_error_then_success(self):
        """URLError (ネットワーク層) もリトライ対象。"""
        side = [
            urllib.error.URLError('connection refused'),
            _FakeResponse({'ok': True}),
        ]
        with mock.patch('proc_ai.urllib.request.urlopen', side_effect=side):
            result = proc_ai._call_claude({'msg': 'x'})
        self.assertEqual(result['ok'], True)

    def test_timeout_error_then_success(self):
        """TimeoutError もリトライ対象。"""
        side = [
            TimeoutError('read timeout'),
            _FakeResponse({'ok': True}),
        ]
        with mock.patch('proc_ai.urllib.request.urlopen', side_effect=side):
            result = proc_ai._call_claude({'msg': 'x'})
        self.assertEqual(result['ok'], True)

    def test_first_call_success_no_retry(self):
        """初回成功なら sleep されない (リトライ動作で副作用が出ないこと)。"""
        side = [_FakeResponse({'ok': True})]
        with mock.patch('proc_ai.urllib.request.urlopen', side_effect=side) as urlopen:
            result = proc_ai._call_claude({'msg': 'x'})
            self.assertEqual(urlopen.call_count, 1)
        self.assertEqual(result['ok'], True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
