"""T2026-0502-AY: Anthropic Batch API helpers のテスト

背景:
  schedule cron 起動分の processor 呼び出しを Batch API に振り替えてコスト 50% off。
  fetcher_trigger 等の即時性が必要な経路は対象外 (realtime 維持)。

スコープ (本 PR):
  - proc_ai.py に Batch API helper 関数 4 件追加 (submit / status / results / build_request)
  - 既存 realtime path (_call_claude_tool) は無変更で互換性維持
  - 単体テストはモック (urlopen) で API 呼び出しせず検証 = Anthropic 課金ゼロ

統合 (別 PR):
  - handler.py で USE_BATCH_API=true 時の 2 段階フロー (submit → state 保存 → retrieve)
  - S3 state 管理 (api/batch/pending_*.json)
  - kill switch + fallback to realtime

実行:
  cd projects/P003-news-timeline
  python3 -m unittest tests.test_batch_api_helpers -v
"""
import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from io import BytesIO

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'lambda', 'processor'))

os.environ.setdefault('S3_BUCKET', 'test-bucket')
os.environ.setdefault('AWS_REGION', 'ap-northeast-1')
os.environ.setdefault('ANTHROPIC_API_KEY', 'dummy-test-not-a-real-key')

import proc_ai  # noqa: E402

# proc_config はモジュール load 時に Secrets Manager 経由 or env から読む。
# テスト用に直接 ANTHROPIC_API_KEY をセット (proc_ai は import 時の値を使う)。
proc_ai.ANTHROPIC_API_KEY = 'dummy-test-not-a-real-key-key'


def _mock_response(body_bytes: bytes):
    """urlopen の mock 返り値を作る (context manager)"""
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=BytesIO(body_bytes))
    cm.__exit__ = MagicMock(return_value=False)
    return cm


class BuildBatchRequestTest(unittest.TestCase):
    """`build_batch_request` の payload 構造確認"""

    def test_basic_payload_structure(self):
        req = proc_ai.build_batch_request(
            custom_id='topic_abc123',
            prompt='テストプロンプト',
            tool_name='generate_summary',
            input_schema={'type': 'object', 'properties': {'summary': {'type': 'string'}}},
        )
        self.assertEqual(req['custom_id'], 'topic_abc123')
        self.assertIn('params', req)
        params = req['params']
        self.assertEqual(params['model'], 'claude-haiku-4-5-20251001')
        self.assertEqual(params['tool_choice'], {'type': 'tool', 'name': 'generate_summary'})
        self.assertEqual(params['messages'], [{'role': 'user', 'content': 'テストプロンプト'}])
        self.assertEqual(len(params['tools']), 1)
        self.assertEqual(params['tools'][0]['name'], 'generate_summary')

    def test_with_system_prompt_adds_cache_control(self):
        req = proc_ai.build_batch_request(
            custom_id='topic_xyz',
            prompt='ユーザープロンプト',
            tool_name='analyze',
            input_schema={'type': 'object'},
            system='共通システムプロンプト',
        )
        self.assertIn('system', req['params'])
        sys_blocks = req['params']['system']
        self.assertEqual(len(sys_blocks), 1)
        self.assertEqual(sys_blocks[0]['type'], 'text')
        self.assertEqual(sys_blocks[0]['text'], '共通システムプロンプト')
        self.assertEqual(sys_blocks[0]['cache_control'], {'type': 'ephemeral'})

    def test_custom_model_and_max_tokens(self):
        req = proc_ai.build_batch_request(
            custom_id='c1', prompt='p', tool_name='t', input_schema={},
            max_tokens=2048, model='claude-sonnet-4-5-20250101',
        )
        self.assertEqual(req['params']['model'], 'claude-sonnet-4-5-20250101')
        self.assertEqual(req['params']['max_tokens'], 2048)


class CallClaudeBatchSubmitTest(unittest.TestCase):
    """`_call_claude_batch_submit` のモック検証"""

    def test_no_api_key_returns_none(self):
        original = proc_ai.ANTHROPIC_API_KEY
        proc_ai.ANTHROPIC_API_KEY = ''
        try:
            result = proc_ai._call_claude_batch_submit([{'custom_id': 'x', 'params': {}}])
            self.assertIsNone(result)
        finally:
            proc_ai.ANTHROPIC_API_KEY = original

    def test_empty_requests_returns_none(self):
        result = proc_ai._call_claude_batch_submit([])
        self.assertIsNone(result)

    @patch('proc_ai.urllib.request.urlopen')
    def test_successful_submit_returns_batch_info(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(json.dumps({
            'id': 'msgbatch_01ABC',
            'processing_status': 'in_progress',
            'request_counts': {'processing': 2, 'succeeded': 0, 'errored': 0},
        }).encode())
        requests = [
            {'custom_id': 'topic_1', 'params': {'model': 'claude-haiku-4-5-20251001', 'messages': []}},
            {'custom_id': 'topic_2', 'params': {'model': 'claude-haiku-4-5-20251001', 'messages': []}},
        ]
        result = proc_ai._call_claude_batch_submit(requests)
        self.assertIsNotNone(result)
        self.assertEqual(result['id'], 'msgbatch_01ABC')
        self.assertEqual(result['processing_status'], 'in_progress')

    @patch('proc_ai.urllib.request.urlopen')
    def test_http_error_returns_none(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url='http://test', code=500, msg='Server Error',
            hdrs=None, fp=BytesIO(b'{"error":"internal"}')
        )
        result = proc_ai._call_claude_batch_submit([{'custom_id': 'x', 'params': {}}])
        self.assertIsNone(result)


class CallClaudeBatchStatusTest(unittest.TestCase):
    """`_call_claude_batch_status` のモック検証"""

    def test_no_batch_id_returns_none(self):
        self.assertIsNone(proc_ai._call_claude_batch_status(''))
        self.assertIsNone(proc_ai._call_claude_batch_status(None))

    @patch('proc_ai.urllib.request.urlopen')
    def test_in_progress_status(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(json.dumps({
            'id': 'msgbatch_01ABC',
            'processing_status': 'in_progress',
            'request_counts': {'processing': 5, 'succeeded': 0, 'errored': 0},
        }).encode())
        result = proc_ai._call_claude_batch_status('msgbatch_01ABC')
        self.assertEqual(result['processing_status'], 'in_progress')

    @patch('proc_ai.urllib.request.urlopen')
    def test_ended_status_with_results_url(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(json.dumps({
            'id': 'msgbatch_01ABC',
            'processing_status': 'ended',
            'results_url': 'https://api.anthropic.com/v1/messages/batches/msgbatch_01ABC/results',
            'request_counts': {'processing': 0, 'succeeded': 5, 'errored': 0},
        }).encode())
        result = proc_ai._call_claude_batch_status('msgbatch_01ABC')
        self.assertEqual(result['processing_status'], 'ended')
        self.assertIn('results_url', result)


class CallClaudeBatchResultsTest(unittest.TestCase):
    """`_call_claude_batch_results` のモック検証 (JSONL parse)"""

    def test_no_batch_id_returns_none(self):
        self.assertIsNone(proc_ai._call_claude_batch_results(''))

    @patch('proc_ai.urllib.request.urlopen')
    def test_jsonl_parse_multiple_results(self, mock_urlopen):
        # 2 件の結果 (JSONL = 1行1 json)
        jsonl = (
            '{"custom_id":"topic_1","result":{"type":"succeeded","message":{"content":[{"type":"tool_use","input":{"summary":"s1"}}]}}}\n'
            '{"custom_id":"topic_2","result":{"type":"errored","error":{"type":"invalid_request_error"}}}\n'
        )
        mock_urlopen.return_value = _mock_response(jsonl.encode())
        results = proc_ai._call_claude_batch_results('msgbatch_01ABC')
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['custom_id'], 'topic_1')
        self.assertEqual(results[0]['result']['type'], 'succeeded')
        self.assertEqual(results[1]['custom_id'], 'topic_2')
        self.assertEqual(results[1]['result']['type'], 'errored')

    @patch('proc_ai.urllib.request.urlopen')
    def test_malformed_lines_skipped(self, mock_urlopen):
        jsonl = (
            '{"custom_id":"topic_1","result":{"type":"succeeded"}}\n'
            'not valid json\n'
            '{"custom_id":"topic_2","result":{"type":"succeeded"}}\n'
            '\n'  # 空行も skip
        )
        mock_urlopen.return_value = _mock_response(jsonl.encode())
        results = proc_ai._call_claude_batch_results('msgbatch_01ABC')
        self.assertEqual(len(results), 2)


class RealtimePathRegressionTest(unittest.TestCase):
    """既存 realtime path (_call_claude_tool) が batch helpers 追加後も無変更で動くか確認"""

    def test_call_claude_tool_still_exists(self):
        self.assertTrue(callable(proc_ai._call_claude_tool))

    def test_call_claude_still_exists(self):
        self.assertTrue(callable(proc_ai._call_claude))

    def test_judge_prediction_still_exists(self):
        self.assertTrue(callable(proc_ai.judge_prediction))

    def test_is_eligible_for_judgment_still_exists(self):
        """T2026-0502-BC で追加した関数も無変更"""
        self.assertTrue(callable(proc_ai.is_eligible_for_judgment))


if __name__ == '__main__':
    unittest.main()
