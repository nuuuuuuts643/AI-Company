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

os.environ.setdefault('ANTHROPIC_API_KEY', 'sk-ant-dummy-for-test')

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
    """force_reset_pending_all の update_item に ConditionExpression が含まれること。"""

    def setUp(self):
        # proc_config の fake injection
        if 'proc_config' not in sys.modules:
            fake_cfg = types.ModuleType('proc_config')
            fake_cfg.ANTHROPIC_API_KEY = os.environ['ANTHROPIC_API_KEY']
            sys.modules['proc_config'] = fake_cfg
        # proc_storage を再 import
        if 'proc_storage' in sys.modules:
            del sys.modules['proc_storage']

    def test_update_item_includes_condition(self):
        """visible_tids 全件に対して ConditionExpression='attribute_exists(topicId)' を渡す。"""
        # boto3 / table mock を差し込んでから proc_storage import
        fake_table = mock.MagicMock()
        fake_table.meta.client.exceptions.ConditionalCheckFailedException = type(
            'CCFE', (Exception,), {}
        )
        fake_s3 = mock.MagicMock()

        fake_proc_config = types.ModuleType('proc_config')
        fake_proc_config.table = fake_table
        fake_proc_config.s3 = fake_s3
        fake_proc_config.S3_BUCKET = 'fake-bucket'
        fake_proc_config.SLACK_WEBHOOK = ''
        fake_proc_config.TOPICS_S3_CAP = 500
        fake_proc_config.ANTHROPIC_API_KEY = 'dummy'
        sys.modules['proc_config'] = fake_proc_config

        import proc_storage as ps

        # _load_visible_topic_ids が3件返す形に mock
        with mock.patch.object(ps, '_load_visible_topic_ids', return_value={'t1', 't2', 't3'}):
            ps.force_reset_pending_all()

        self.assertEqual(fake_table.update_item.call_count, 3)
        for call in fake_table.update_item.call_args_list:
            kwargs = call.kwargs or call[1]
            self.assertIn(
                'ConditionExpression', kwargs,
                f'update_item は ConditionExpression を必ず付ける必要がある: {kwargs}'
            )
            self.assertEqual(
                kwargs['ConditionExpression'],
                'attribute_exists(topicId)',
                'topicId 不在の META を新規作成しないための物理ガード'
            )

    def test_skips_nonexistent_topic_silently(self):
        """ConditionalCheckFailedException が来ても処理継続し、count に含めない。"""
        fake_table = mock.MagicMock()
        ccfe_cls = type('CCFE', (Exception,), {})
        fake_table.meta.client.exceptions.ConditionalCheckFailedException = ccfe_cls
        fake_s3 = mock.MagicMock()

        # 1件目のみ存在、2件目は ConditionalCheckFailed
        def update_side(**kwargs):
            if kwargs['Key']['topicId'] == 't_missing':
                raise ccfe_cls('not exist')
            return {}
        fake_table.update_item.side_effect = update_side

        fake_proc_config = types.ModuleType('proc_config')
        fake_proc_config.table = fake_table
        fake_proc_config.s3 = fake_s3
        fake_proc_config.S3_BUCKET = 'fake-bucket'
        fake_proc_config.SLACK_WEBHOOK = ''
        fake_proc_config.TOPICS_S3_CAP = 500
        fake_proc_config.ANTHROPIC_API_KEY = 'dummy'
        sys.modules['proc_config'] = fake_proc_config
        if 'proc_storage' in sys.modules:
            del sys.modules['proc_storage']
        import proc_storage as ps

        with mock.patch.object(ps, '_load_visible_topic_ids', return_value={'t_exists', 't_missing'}):
            count = ps.force_reset_pending_all()

        self.assertEqual(count, 1, '存在する 1 件のみカウントされる (stub 量産防止)')


if __name__ == '__main__':
    unittest.main()
