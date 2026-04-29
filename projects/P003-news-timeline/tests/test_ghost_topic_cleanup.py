"""T2026-0429-H: ゴースト topic 駆除の再発防止 boundary test。

検証対象:
- processor.proc_storage._drop_ghost_topics: S3 topics.json から「DDB に META が
  存在しない (= articleCount/lastUpdated 欠如) topic」を除去すること
- ConsistentRead=True で just-written 検証の正確性を保証
- batch_get_item 例外時は除去せずフォールバック (publish blocking 防止)

背景: fetcher 側の batch_writer 並列書き込みで silently drop された topicId が
saved_ids に残り、validate_topics_exist が skip_tids でスキップしていたため幽霊
エントリが topics.json に永続滞留。processor 側の get_topics_by_ids で
「ゴーストID検知 7件全件」となり keyPoint 生成が永久に発火しない事象 (本番)。

実行:
  cd projects/P003-news-timeline
  ANTHROPIC_API_KEY=dummy python3 -m unittest tests.test_ghost_topic_cleanup -v
"""
import os
import sys
import unittest
from unittest import mock

os.environ.setdefault('ANTHROPIC_API_KEY', 'sk-ant-dummy-for-test')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'lambda', 'processor'))


def _import_proc_storage():
    import importlib
    if 'proc_storage' in sys.modules:
        del sys.modules['proc_storage']
    import proc_storage as _p  # type: ignore
    return _p


class DropGhostTopicsTest(unittest.TestCase):
    def setUp(self):
        # proc_storage は Python 3.10+ syntax を含むため、3.9 環境では import 失敗。
        # その場合はソース静的検査でガード。
        try:
            self.proc_storage = _import_proc_storage()
            self.runtime_ok = True
        except SyntaxError:
            self.runtime_ok = False

    def _run_with_fake_batch_get(self, items, batch_responses):
        ps = self.proc_storage
        fake_db = mock.MagicMock()
        fake_db.batch_get_item.side_effect = batch_responses
        with mock.patch.object(ps, 'dynamodb', fake_db):
            return ps._drop_ghost_topics(items), fake_db

    def test_ghost_dropped(self):
        if not self.runtime_ok:
            self.skipTest('proc_storage import 失敗 (Python 3.10+ syntax)')
        ps = self.proc_storage
        items = [
            {'topicId': 'a' * 16, 'articleCount': 5},
            {'topicId': 'b' * 16, 'articleCount': 3},  # ghost (DDB 不在)
        ]
        responses = [{
            'Responses': {
                ps.table.name: [
                    {'topicId': 'a' * 16, 'articleCount': 5, 'lastUpdated': '2026-04-29T00:00:00Z'},
                    # b は応答なし = ghost
                ]
            }
        }]
        result, _fake = self._run_with_fake_batch_get(items, responses)
        ids = {t['topicId'] for t in result}
        self.assertIn('a' * 16, ids)
        self.assertNotIn('b' * 16, ids, 'DDB 不在の幽霊 topic は除去される')

    def test_stub_meta_dropped(self):
        if not self.runtime_ok:
            self.skipTest('proc_storage import 失敗')
        ps = self.proc_storage
        items = [{'topicId': 'c' * 16, 'articleCount': 2}]
        responses = [{
            'Responses': {
                ps.table.name: [{'topicId': 'c' * 16}],  # articleCount/lastUpdated 欠如
            }
        }]
        result, _ = self._run_with_fake_batch_get(items, responses)
        self.assertEqual(result, [], 'stub META (articleCount/lastUpdated 欠如) も除去')

    def test_consistent_read_used(self):
        if not self.runtime_ok:
            self.skipTest('proc_storage import 失敗')
        ps = self.proc_storage
        items = [{'topicId': 'd' * 16, 'articleCount': 4}]
        responses = [{
            'Responses': {ps.table.name: [
                {'topicId': 'd' * 16, 'articleCount': 4, 'lastUpdated': '2026-04-29T00:00:00Z'}
            ]}
        }]
        _result, fake = self._run_with_fake_batch_get(items, responses)
        call = fake.batch_get_item.call_args
        request = call.kwargs.get('RequestItems') or call.args[0].get('RequestItems')
        self.assertEqual(
            request[ps.table.name].get('ConsistentRead'), True,
            'ConsistentRead=True が必要: just-written 検証の整合性を確保'
        )

    def test_batch_error_keeps_records(self):
        """batch_get_item が例外を投げた場合は除去しない (publish blocking 防止)。"""
        if not self.runtime_ok:
            self.skipTest('proc_storage import 失敗')
        ps = self.proc_storage
        items = [{'topicId': 'e' * 16, 'articleCount': 1}]
        fake_db = mock.MagicMock()
        fake_db.batch_get_item.side_effect = Exception('boom')
        with mock.patch.object(ps, 'dynamodb', fake_db):
            result = ps._drop_ghost_topics(items)
        self.assertEqual(len(result), 1, 'エラー時は除去しない (本物 topic を失う方が悪い)')

    def test_empty_items(self):
        if not self.runtime_ok:
            self.skipTest('proc_storage import 失敗')
        ps = self.proc_storage
        self.assertEqual(ps._drop_ghost_topics([]), [])
        self.assertEqual(ps._drop_ghost_topics(None), None)


class DropGhostTopicsSourceCheck(unittest.TestCase):
    """proc_storage が Python 3.9 環境で import 失敗するケース用の静的検査。
    本番 Lambda は Python 3.11+ で動くので runtime テスト + 静的テストの二重保証。
    """

    @classmethod
    def setUpClass(cls):
        path = os.path.join(ROOT, 'lambda', 'processor', 'proc_storage.py')
        with open(path, encoding='utf-8') as f:
            cls.source = f.read()

    def test_drop_ghost_function_exists(self):
        self.assertIn('def _drop_ghost_topics', self.source,
                      '_drop_ghost_topics 関数の存在を物理ガード')

    def test_get_all_topics_for_s3_calls_drop_ghost(self):
        """get_all_topics_for_s3 が _drop_ghost_topics を必ず呼ぶこと。"""
        # 関数本体だけ抽出
        m_start = self.source.find('def get_all_topics_for_s3')
        self.assertNotEqual(m_start, -1)
        m_next = self.source.find('\ndef ', m_start + 1)
        body = self.source[m_start:m_next]
        self.assertIn(
            '_drop_ghost_topics', body,
            'get_all_topics_for_s3 内で _drop_ghost_topics を呼ばないと '
            'fetcher の旧ゴースト entry が永続化する (T2026-0429-H 再発防止)'
        )

    def test_consistent_read_specified(self):
        """_drop_ghost_topics が ConsistentRead=True を渡していること (静的検査)。"""
        m_start = self.source.find('def _drop_ghost_topics')
        m_next = self.source.find('\ndef ', m_start + 1)
        body = self.source[m_start:m_next]
        self.assertIn(
            "'ConsistentRead': True", body,
            '_drop_ghost_topics は ConsistentRead=True で読まないと '
            'eventual consistency で本物 topic を ghost と誤判定する'
        )


if __name__ == '__main__':
    unittest.main()
