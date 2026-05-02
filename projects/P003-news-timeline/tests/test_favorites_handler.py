"""
PayloadFormatVersion 2.0 準拠 + _make_response ヘルパーの境界値テスト

テスト対象: lambda/favorites/handler.py
- _make_response(status, payload, headers=None) が常に正しい形式を返すこと
- lambda_handler の GET /favorites/{userId} ルートが有効なレスポンスを返すこと
- 境界値: 空リスト / 大量データ / None 値 / Decimal 型 / 未来日付
"""

import json
import sys
import os
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

# Lambda ディレクトリをパスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'favorites'))


def _is_valid_payload_format_v2(resp: dict) -> None:
    """PayloadFormatVersion 2.0 の構造を assert する共通ヘルパー"""
    assert isinstance(resp, dict), "response must be dict"
    assert isinstance(resp.get('statusCode'), int), f"statusCode must be int, got {type(resp.get('statusCode'))}"
    assert isinstance(resp.get('body'), str), f"body must be str, got {type(resp.get('body'))}"
    assert isinstance(resp.get('headers'), dict), "headers must be dict"
    # body が valid JSON であること
    parsed = json.loads(resp['body'])
    assert parsed is not None


# ── _make_response 単体テスト ─────────────────────────────────────

class TestMakeResponse:
    def setup_method(self):
        import handler
        self.handler = handler

    def test_normal_200(self):
        r = self.handler._make_response(200, {'key': 'value'})
        _is_valid_payload_format_v2(r)
        assert r['statusCode'] == 200
        assert json.loads(r['body']) == {'key': 'value'}

    def test_statuscode_is_always_int(self):
        r = self.handler._make_response(200, {})
        assert isinstance(r['statusCode'], int)
        assert r['statusCode'] == 200

    def test_body_is_always_str(self):
        r = self.handler._make_response(200, {'list': [1, 2, 3]})
        assert isinstance(r['body'], str)

    def test_empty_payload(self):
        r = self.handler._make_response(200, {})
        _is_valid_payload_format_v2(r)
        assert json.loads(r['body']) == {}

    def test_empty_list_in_payload(self):
        r = self.handler._make_response(200, {'favorites': []})
        _is_valid_payload_format_v2(r)
        assert json.loads(r['body'])['favorites'] == []

    def test_large_list(self):
        items = [{'topicId': f'{i:016x}', 'createdAt': '2026-01-01T00:00:00+00:00'} for i in range(1000)]
        r = self.handler._make_response(200, {'favorites': items})
        _is_valid_payload_format_v2(r)
        parsed = json.loads(r['body'])
        assert len(parsed['favorites']) == 1000

    def test_decimal_values_serialized_as_string(self):
        # DynamoDB が Decimal を返す場合
        r = self.handler._make_response(200, {'count': Decimal('42'), 'score': Decimal('3.14')})
        _is_valid_payload_format_v2(r)
        parsed = json.loads(r['body'])
        assert parsed['count'] == '42'
        assert parsed['score'] == '3.14'

    def test_none_values(self):
        r = self.handler._make_response(200, {'field': None})
        _is_valid_payload_format_v2(r)
        assert json.loads(r['body'])['field'] is None

    def test_future_date_string(self):
        future = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
        r = self.handler._make_response(200, {'createdAt': future})
        _is_valid_payload_format_v2(r)
        parsed = json.loads(r['body'])
        assert parsed['createdAt'] == future

    def test_japanese_unicode(self):
        r = self.handler._make_response(200, {'message': '日本語テスト🎉'})
        _is_valid_payload_format_v2(r)
        parsed = json.loads(r['body'])
        assert parsed['message'] == '日本語テスト🎉'

    def test_500_error_format(self):
        r = self.handler._make_response(500, {'error': '失敗', 'detail': 'RuntimeError: something'})
        _is_valid_payload_format_v2(r)
        assert r['statusCode'] == 500
        assert json.loads(r['body'])['error'] == '失敗'

    def test_custom_headers(self):
        headers = {'X-Custom': 'value', 'Content-Type': 'application/json'}
        r = self.handler._make_response(200, {}, headers=headers)
        _is_valid_payload_format_v2(r)
        assert r['headers']['X-Custom'] == 'value'

    def test_default_headers_include_cors(self):
        r = self.handler._make_response(200, {})
        assert 'Access-Control-Allow-Origin' in r['headers']
        assert r['headers']['Access-Control-Allow-Origin'] == '*'

    def test_nested_dict_payload(self):
        payload = {'a': {'b': {'c': [1, 2, {'d': Decimal('99')}]}}}
        r = self.handler._make_response(200, payload)
        _is_valid_payload_format_v2(r)


# ── lambda_handler GET /favorites/{userId} テスト ─────────────────

class TestLambdaHandlerGetFavorites:
    def setup_method(self):
        import handler
        self.handler = handler

    def _make_event(self, user_id: str, method: str = 'GET') -> dict:
        return {
            'requestContext': {'http': {'method': method}},
            'rawPath': f'/favorites/{user_id}',
        }

    @patch('handler.get_favorites')
    def test_empty_favorites_list(self, mock_get):
        mock_get.return_value = []
        r = self.handler.lambda_handler(self._make_event('user001'), None)
        _is_valid_payload_format_v2(r)
        assert r['statusCode'] == 200
        assert json.loads(r['body'])['favorites'] == []

    @patch('handler.get_favorites')
    def test_normal_favorites_list(self, mock_get):
        mock_get.return_value = [
            {'topicId': 'abcdef1234567890', 'createdAt': '2026-01-01T00:00:00+00:00'},
            {'topicId': '1234567890abcdef', 'createdAt': '2026-02-01T00:00:00+00:00'},
        ]
        r = self.handler.lambda_handler(self._make_event('user001'), None)
        _is_valid_payload_format_v2(r)
        assert r['statusCode'] == 200
        parsed = json.loads(r['body'])
        assert len(parsed['favorites']) == 2

    @patch('handler.get_favorites')
    def test_favorites_with_decimal_createdAt(self, mock_get):
        # 旧データ形式: createdAt が Decimal (Unix timestamp)
        mock_get.return_value = [{'topicId': 'abcdef1234567890', 'createdAt': Decimal('1746153700')}]
        r = self.handler.lambda_handler(self._make_event('user001'), None)
        _is_valid_payload_format_v2(r)
        assert r['statusCode'] == 200

    @patch('handler.get_favorites')
    def test_large_favorites_list(self, mock_get):
        mock_get.return_value = [
            {'topicId': f'{i:016x}', 'createdAt': '2026-01-01T00:00:00+00:00'} for i in range(500)
        ]
        r = self.handler.lambda_handler(self._make_event('user001'), None)
        _is_valid_payload_format_v2(r)
        assert r['statusCode'] == 200
        assert len(json.loads(r['body'])['favorites']) == 500

    @patch('handler.get_favorites')
    def test_dynamo_exception_returns_500_with_log(self, mock_get, capsys):
        mock_get.side_effect = Exception('DynamoDB connection timeout')
        r = self.handler.lambda_handler(self._make_event('user001'), None)
        _is_valid_payload_format_v2(r)
        assert r['statusCode'] == 500
        # ログが出力されること
        captured = capsys.readouterr()
        assert '[ERROR]' in captured.out
        assert 'DynamoDB connection timeout' in captured.out

    def test_missing_user_id_returns_400(self):
        event = {'requestContext': {'http': {'method': 'GET'}}, 'rawPath': '/favorites'}
        r = self.handler.lambda_handler(event, None)
        _is_valid_payload_format_v2(r)
        assert r['statusCode'] == 400

    def test_options_preflight(self):
        event = {'requestContext': {'http': {'method': 'OPTIONS'}}, 'rawPath': '/favorites/user001'}
        r = self.handler.lambda_handler(event, None)
        _is_valid_payload_format_v2(r)
        assert r['statusCode'] == 200

    def test_unsupported_method_405(self):
        event = {'requestContext': {'http': {'method': 'PATCH'}}, 'rawPath': '/favorites/user001'}
        r = self.handler.lambda_handler(event, None)
        _is_valid_payload_format_v2(r)
        assert r['statusCode'] == 405
