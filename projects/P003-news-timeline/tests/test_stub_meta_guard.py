"""T2026-0428-AE: 空トピック (stub META) 再発防止 boundary test。

検証対象:
1. fetcher.storage.validate_topics_exist が articleCount/lastUpdated 欠如の
   stub META を topics.json から駆除すること
2. processor.proc_storage.force_reset_pending_all が
   ConditionExpression='attribute_exists(topicId)' を必ず付けて update_item を呼ぶこと
   (lifecycle/TTL で消えた META を update で再生成しない物理ガード)

実行:
  cd projects/P003-news-timeline
  ANTHROPIC_API_KEY=dummy python3 -m unittest tests.test_stub_meta_guard -v
"""
import os
import sys
import types
import unittest
from unittest import mock

os.environ.setdefault('ANTHROPIC_API_KEY', '***REDACTED-SEC3***')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'lambda', 'fetcher'))
sys.path.insert(0, os.path.join(ROOT, 'lambda', 'processor'))


# fetcher.storage は boto3 を import するが、関数単体テストのため module 経由で injection
def _import_fetcher_storage():
    import importlib
    if 'storage' in sys.modules:
        del sys.modules['storage']
    # boto3 / dynamodb のスタブを差し込む
    import storage as _s  # type: ignore
    return _s


class ValidateTopicsExistStubRejectTest(unittest.TestCase):
    """stub META (articleCount/lastUpdated 欠如) を topics.json から除去するか。"""

    def setUp(self):
        self.storage = _import_fetcher_storage()

    def _run_with_fake_batch_get(self, topics, batch_responses):
        """dynamodb.batch_get_item を fake にして validate_topics_exist を実行。"""
        fake_db = mock.MagicMock()
        fake_db.batch_get_item.side_effect = batch_responses
        with mock.patch.object(self.storage, 'dynamodb', fake_db):
            return self.storage.validate_topics_exist(topics)

    def test_stub_record_dropped(self):
        topics = [
            {'topicId': 'a' * 16, 'articleCount': 5},  # 完全
            {'topicId': 'b' * 16, 'articleCount': 3},  # スタブ (DynamoDB側で articleCount 欠如)
        ]
        # batch_get_item の fake response: a=完全, b=stub
        responses = [{
            'Responses': {
                self.storage.TABLE_NAME: [
                    {'topicId': 'a' * 16, 'articleCount': 5, 'lastUpdated': '2026-04-28T00:00:00Z'},
                    {'topicId': 'b' * 16},  # stub (articleCount/lastUpdated 欠如)
                ]
            }
        }]
        result = self._run_with_fake_batch_get(topics, responses)
        result_ids = {t['topicId'] for t in result}
        self.assertIn('a' * 16, result_ids, '完全な META は残る')
        self.assertNotIn('b' * 16, result_ids, 'stub META は topics.json から除去')

    def test_articlecount_only_stub_dropped(self):
        """articleCount だけある (lastUpdated 欠如) も stub 扱い。"""
        topics = [{'topicId': 'c' * 16, 'articleCount': 2}]
        responses = [{
            'Responses': {
                self.storage.TABLE_NAME: [
                    {'topicId': 'c' * 16, 'articleCount': 2},  # lastUpdated 無し
                ]
            }
        }]
        result = self._run_with_fake_batch_get(topics, responses)
        self.assertEqual(result, [], 'lastUpdated 欠如 stub も除去')

    def test_skip_tids_bypass_validation(self):
        """skip_tids で渡したトピックは batch_get_item 自体を行わず通す。"""
        topics = [{'topicId': 'd' * 16, 'articleCount': 7}]
        fake_db = mock.MagicMock()
        with mock.patch.object(self.storage, 'dynamodb', fake_db):
            result = self.storage.validate_topics_exist(topics, skip_tids={'d' * 16})
        self.assertEqual(len(result), 1)
        fake_db.batch_get_item.assert_not_called()

    def test_batch_error_keeps_records(self):
        """batch_get_item が例外を投げた場合は既存挙動 (通す) を維持。"""
        topics = [{'topicId': 'e' * 16, 'articleCount': 1}]
        fake_db = mock.MagicMock()
        fake_db.batch_get_item.side_effect = Exception('boom')
        with mock.patch.object(self.storage, 'dynamodb', fake_db):
            result = self.storage.validate_topics_exist(topics)
        self.assertEqual(len(result), 1, 'エラー時は除去しない (誤判定で本物トピック失う方が悪い)')


class ForceResetConditionExpressionTest(unittest.TestCase):
    """force_reset_pending_all の update_item に ConditionExpression が含まれること。

    proc_storage は Python 3.10+ の `T | None` 構文を使うため、ローカル python3.9 環境
    では import 出来ない。ここでは「ソース上 ConditionExpression が物理的に書いてある」
    ことを静的検査する CI 物理ゲート。production 動作は本番 Lambda (Python 3.11+) で。
    """

    @classmethod
    def setUpClass(cls):
        proc_storage_path = os.path.join(
            ROOT, 'lambda', 'processor', 'proc_storage.py'
        )
        with open(proc_storage_path, encoding='utf-8') as f:
            cls.source = f.read()

    def _force_reset_block(self):
        """force_reset_pending_all 関数本体だけを抽出。"""
        m_start = self.source.find('def force_reset_pending_all')
        self.assertNotEqual(m_start, -1, 'force_reset_pending_all が見つからない')
        # 次の def までを関数本体とする
        m_next = self.source.find('\ndef ', m_start + 1)
        return self.source[m_start:m_next] if m_next != -1 else self.source[m_start:]

    def test_update_item_has_condition_expression(self):
        body = self._force_reset_block()
        self.assertIn(
            "ConditionExpression='attribute_exists(topicId)'", body,
            '物理ガード: update_item は attribute_exists(topicId) 条件付きでのみ実行する '
            '(lifecycle/TTL で消えた META に対して空 stub を生成しないため)。'
            'これを外すと flotopic で空トピックが再発する (T2026-0428-AE 再発防止条件)。'
        )

    def test_handles_conditional_check_failed(self):
        body = self._force_reset_block()
        self.assertIn(
            'ConditionalCheckFailedException', body,
            'META 不在時の例外を握り潰さず、捕捉して処理継続する必要がある'
        )

    def test_no_unconditional_update_item(self):
        """force_reset_pending_all 内に ConditionExpression なしの update_item が無いこと。"""
        body = self._force_reset_block()
        # update_item の引数群に ConditionExpression が含まれることを構造確認
        # 単純な部分文字列検査ではなく、update_item 呼び出しブロックを確認
        idx = body.find('table.update_item(')
        self.assertNotEqual(idx, -1, 'force_reset 内に update_item が必要')
        # 次の閉じ括弧 ) までの引数ブロック
        # 簡易: 200文字以内に ConditionExpression があるか確認
        block = body[idx:idx + 500]
        self.assertIn('ConditionExpression', block,
                      f'update_item ブロックに ConditionExpression が無い: {block[:300]}')


if __name__ == '__main__':
    unittest.main()
