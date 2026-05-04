"""Step 6 S1: chapters / background / relatedTopicIds / lastChapterDate を
DynamoDB から S3 api/topic/{tid}.json に素通しする処理の boundary test。

検証対象:
  proc_storage.update_topic_s3_file
  - 新フィールドが upd に存在する → meta に含まれる
  - 新フィールドが upd に存在しない (None/空) → meta に含まれない（既存トピック不変）
  - background は一度書いたら上書きしない
  - chapters は空リストを書かない

実行:
  cd projects/P003-news-timeline
  S3_BUCKET=test python3 -m unittest tests.test_chapter_passthrough -v
"""
import io
import json
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'lambda', 'processor'))

os.environ.setdefault('S3_BUCKET', 'test-bucket')
os.environ.setdefault('AWS_REGION', 'ap-northeast-1')
os.environ.setdefault('ANTHROPIC_API_KEY', '***REDACTED-SEC3***')

import proc_storage  # noqa: E402

_SAMPLE_CHAPTERS = [
    {
        'date': '2026-05-01',
        'summary': '事実サマリー',
        'commentary': '解説テキスト',
        'prediction': '予測テキスト',
        'articleIds': ['art_01', 'art_02'],
    }
]


def _make_s3_response(meta, timeline=None):
    body_dict = {'meta': meta, 'timeline': timeline or [], 'views': []}
    body_bytes = json.dumps(body_dict, ensure_ascii=False).encode('utf-8')
    return {
        'ETag': '"oldetag000000000000000000000000"',
        'Body': io.BytesIO(body_bytes),
    }


def _get_written_meta(fake_s3):
    """put_object に渡された Body の meta を返す。"""
    call = fake_s3.put_object.call_args
    body = call.kwargs.get('Body') or call.args[0]
    data = json.loads(body)
    return data['meta']


class ChapterPassthroughTest(unittest.TestCase):
    """update_topic_s3_file で新フィールドが正しく pass-through されるか。"""

    def setUp(self):
        self.fake_s3 = mock.MagicMock()
        self.fake_table = mock.MagicMock()
        self.s3_patch = mock.patch.object(proc_storage, 's3', self.fake_s3)
        self.table_patch = mock.patch.object(proc_storage, 'table', self.fake_table)
        self.s3_patch.start()
        self.table_patch.start()
        self.html_patch = mock.patch.object(
            proc_storage, 'generate_static_topic_html', return_value=None
        )
        self.html_patch.start()

    def tearDown(self):
        self.s3_patch.stop()
        self.table_patch.stop()
        self.html_patch.stop()

    # ---- 新フィールドあり ----------------------------------------

    def test_chapters_written_when_present(self):
        """upd に chapters があれば meta['chapters'] に書かれる。"""
        self.fake_s3.get_object.return_value = _make_s3_response(
            {'topicId': 'aaa1', 'aiGenerated': True}
        )
        upd = {
            'aiGenerated': True,
            'generatedTitle': 'タイトル',
            'chapters': _SAMPLE_CHAPTERS,
        }
        proc_storage.update_topic_s3_file('aaa1', upd=upd)
        self.fake_s3.put_object.assert_called_once()
        meta = _get_written_meta(self.fake_s3)
        self.assertIn('chapters', meta)
        self.assertEqual(meta['chapters'], _SAMPLE_CHAPTERS)

    def test_background_written_when_present(self):
        """upd に background があれば meta['background'] に書かれる。"""
        self.fake_s3.get_object.return_value = _make_s3_response(
            {'topicId': 'aaa2', 'aiGenerated': True}
        )
        upd = {
            'aiGenerated': True,
            'generatedTitle': 'タイトル',
            'background': 'トピックの背景説明テキスト',
        }
        proc_storage.update_topic_s3_file('aaa2', upd=upd)
        meta = _get_written_meta(self.fake_s3)
        self.assertIn('background', meta)
        self.assertEqual(meta['background'], 'トピックの背景説明テキスト')

    def test_related_topic_ids_written_when_present(self):
        """upd に relatedTopicIds があれば meta['relatedTopicIds'] に書かれる。"""
        self.fake_s3.get_object.return_value = _make_s3_response(
            {'topicId': 'aaa3', 'aiGenerated': True}
        )
        upd = {
            'aiGenerated': True,
            'generatedTitle': 'タイトル',
            'relatedTopicIds': ['id_x', 'id_y'],
        }
        proc_storage.update_topic_s3_file('aaa3', upd=upd)
        meta = _get_written_meta(self.fake_s3)
        self.assertIn('relatedTopicIds', meta)
        self.assertEqual(meta['relatedTopicIds'], ['id_x', 'id_y'])

    def test_last_chapter_date_written_when_present(self):
        """upd に lastChapterDate があれば meta['lastChapterDate'] に書かれる。"""
        self.fake_s3.get_object.return_value = _make_s3_response(
            {'topicId': 'aaa4', 'aiGenerated': True}
        )
        upd = {
            'aiGenerated': True,
            'generatedTitle': 'タイトル',
            'lastChapterDate': '2026-05-03',
        }
        proc_storage.update_topic_s3_file('aaa4', upd=upd)
        meta = _get_written_meta(self.fake_s3)
        self.assertIn('lastChapterDate', meta)
        self.assertEqual(meta['lastChapterDate'], '2026-05-03')

    # ---- 新フィールドなし → 既存トピックを壊さない ---------------

    def test_chapters_absent_when_upd_has_none(self):
        """upd の chapters が None → 既存 meta に chapters が無ければキー自体が出力されない。"""
        self.fake_s3.get_object.return_value = _make_s3_response(
            {'topicId': 'bbb1', 'aiGenerated': True, 'generatedTitle': '既存タイトル'}
        )
        upd = {
            'aiGenerated': True,
            'generatedTitle': '更新タイトル',
            'chapters': None,
        }
        proc_storage.update_topic_s3_file('bbb1', upd=upd)
        self.fake_s3.put_object.assert_called_once()
        meta = _get_written_meta(self.fake_s3)
        self.assertNotIn('chapters', meta)

    def test_chapters_absent_when_upd_has_empty_list(self):
        """upd の chapters が [] → meta に chapters キーを追加しない。"""
        self.fake_s3.get_object.return_value = _make_s3_response(
            {'topicId': 'bbb2', 'aiGenerated': True, 'generatedTitle': '既存タイトル'}
        )
        upd = {
            'aiGenerated': True,
            'generatedTitle': '更新タイトル',
            'chapters': [],
        }
        proc_storage.update_topic_s3_file('bbb2', upd=upd)
        meta = _get_written_meta(self.fake_s3)
        self.assertNotIn('chapters', meta)

    def test_background_absent_when_upd_has_none(self):
        """upd の background が None → meta に background キーを追加しない。"""
        self.fake_s3.get_object.return_value = _make_s3_response(
            {'topicId': 'bbb3', 'aiGenerated': True, 'generatedTitle': '既存タイトル'}
        )
        upd = {'aiGenerated': True, 'generatedTitle': '更新タイトル', 'background': None}
        proc_storage.update_topic_s3_file('bbb3', upd=upd)
        meta = _get_written_meta(self.fake_s3)
        self.assertNotIn('background', meta)

    def test_no_new_fields_when_all_absent(self):
        """chapters/background/relatedTopicIds/lastChapterDate 全て upd に無い
        → 既存 aiGenerated=True トピックの meta が新フィールドで汚染されない。"""
        self.fake_s3.get_object.return_value = _make_s3_response(
            {'topicId': 'bbb4', 'aiGenerated': True, 'keyPoint': '既存keyPoint'}
        )
        upd = {'aiGenerated': True, 'generatedTitle': 'タイトル'}
        proc_storage.update_topic_s3_file('bbb4', upd=upd)
        meta = _get_written_meta(self.fake_s3)
        for field in ('chapters', 'background', 'relatedTopicIds', 'lastChapterDate'):
            self.assertNotIn(field, meta, f'{field} が不要なのに meta に含まれている')

    # ---- background 上書き禁止 -----------------------------------

    def test_background_not_overwritten_when_already_set(self):
        """既存 meta に background がある場合、upd の値で上書きしない。"""
        existing_bg = '最初の背景説明'
        self.fake_s3.get_object.return_value = _make_s3_response(
            {'topicId': 'ccc1', 'aiGenerated': True, 'background': existing_bg}
        )
        upd = {
            'aiGenerated': True,
            'generatedTitle': 'タイトル',
            'background': '新しい背景説明（上書きすべきでない）',
        }
        proc_storage.update_topic_s3_file('ccc1', upd=upd)
        meta = _get_written_meta(self.fake_s3)
        self.assertEqual(meta['background'], existing_bg)

    # ---- 全フィールド同時 ----------------------------------------

    def test_all_new_fields_written_together(self):
        """4 フィールドを同時に upd に入れたとき全て meta に書かれる。"""
        self.fake_s3.get_object.return_value = _make_s3_response(
            {'topicId': 'ddd1', 'aiGenerated': True}
        )
        upd = {
            'aiGenerated': True,
            'generatedTitle': 'タイトル',
            'chapters': _SAMPLE_CHAPTERS,
            'background': '背景テキスト',
            'relatedTopicIds': ['rel1', 'rel2'],
            'lastChapterDate': '2026-05-03',
        }
        proc_storage.update_topic_s3_file('ddd1', upd=upd)
        meta = _get_written_meta(self.fake_s3)
        self.assertEqual(meta['chapters'], _SAMPLE_CHAPTERS)
        self.assertEqual(meta['background'], '背景テキスト')
        self.assertEqual(meta['relatedTopicIds'], ['rel1', 'rel2'])
        self.assertEqual(meta['lastChapterDate'], '2026-05-03')


if __name__ == '__main__':
    unittest.main()
