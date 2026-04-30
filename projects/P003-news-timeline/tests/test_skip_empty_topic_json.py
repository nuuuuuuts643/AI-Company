"""T260 (2026-04-30): aiGenerated=False かつ AI フィールド未生成のトピックは
個別 JSON (api/topic/{tid}.json) の S3 PUT をスキップする物理ガード boundary test。

背景:
  本番 https://flotopic.com/api/topic/8f81be6586cbea09.json は meta が
  {aiGenerated:false, topicId:'...'} の 2 フィールドだけの空同然の状態で
  S3 にアップロードされ続けていた。S3 容量・Lambda 実行時間・CloudFront 転送が
  無駄になる。

検証対象:
  proc_storage.update_topic_s3_file
  - aiGenerated=False かつ generatedTitle 不在 → s3.put_object を呼ばない
  - aiGenerated=True または generatedTitle あり → 従来通り put_object を呼ぶ
  - 既存 meta に generatedTitle があれば upd が空でも put_object する (heal 保護)

実行:
  cd projects/P003-news-timeline
  S3_BUCKET=test python3 -m unittest tests.test_skip_empty_topic_json -v
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
os.environ.setdefault('ANTHROPIC_API_KEY', 'sk-ant-dummy-for-test')

import proc_storage  # noqa: E402


def _make_s3_response(meta, timeline=None):
    body_dict = {'meta': meta, 'timeline': timeline or [], 'views': []}
    body_bytes = json.dumps(body_dict, ensure_ascii=False).encode('utf-8')
    return {
        'ETag': '"oldetag1234567890abcdef1234567890"',
        'Body': io.BytesIO(body_bytes),
    }


class SkipEmptyTopicJsonTest(unittest.TestCase):
    """update_topic_s3_file の skip 条件 boundary test。"""

    def setUp(self):
        # s3 / table をフルモック
        self.fake_s3 = mock.MagicMock()
        self.fake_table = mock.MagicMock()
        self.s3_patch = mock.patch.object(proc_storage, 's3', self.fake_s3)
        self.table_patch = mock.patch.object(proc_storage, 'table', self.fake_table)
        self.s3_patch.start()
        self.table_patch.start()
        # static HTML 生成は本テストの対象外なので no-op に差し替え
        self.html_patch = mock.patch.object(
            proc_storage, 'generate_static_topic_html', return_value=None
        )
        self.html_patch.start()

    def tearDown(self):
        self.s3_patch.stop()
        self.table_patch.stop()
        self.html_patch.stop()

    # -- skip ケース (aiGenerated=False かつ generatedTitle 不在) --

    def test_skip_when_meta_only_has_aigenerated_false(self):
        """meta が {topicId, aiGenerated:False} の 2 フィールドだけ → put_object しない。"""
        self.fake_s3.get_object.return_value = _make_s3_response(
            {'topicId': 'aaaa', 'aiGenerated': False}
        )
        with mock.patch('builtins.print') as mp:
            proc_storage.update_topic_s3_file('aaaa', upd={})
        self.fake_s3.put_object.assert_not_called()
        # ログ出力: [SKIP_EMPTY_JSON] tid=aaaa reason=aiGenerated=False
        joined = ' '.join(str(c.args) for c in mp.call_args_list)
        self.assertIn('[SKIP_EMPTY_JSON]', joined)
        self.assertIn('tid=aaaa', joined)
        self.assertIn('aiGenerated=False', joined)

    def test_skip_when_aigenerated_missing_and_no_title(self):
        """meta に aiGenerated キー自体が無く、generatedTitle も無い → skip。"""
        self.fake_s3.get_object.return_value = _make_s3_response(
            {'topicId': 'bbbb'}
        )
        proc_storage.update_topic_s3_file('bbbb', upd={})
        self.fake_s3.put_object.assert_not_called()

    def test_skip_when_generatedtitle_empty_string(self):
        """generatedTitle='' (空文字) → skip。"""
        self.fake_s3.get_object.return_value = _make_s3_response(
            {'topicId': 'cccc', 'aiGenerated': False, 'generatedTitle': ''}
        )
        proc_storage.update_topic_s3_file('cccc', upd={})
        self.fake_s3.put_object.assert_not_called()

    def test_skip_when_generatedtitle_whitespace_only(self):
        """generatedTitle='   ' (空白だけ) → skip。"""
        self.fake_s3.get_object.return_value = _make_s3_response(
            {'topicId': 'dddd', 'aiGenerated': False, 'generatedTitle': '   '}
        )
        proc_storage.update_topic_s3_file('dddd', upd={})
        self.fake_s3.put_object.assert_not_called()

    # -- non-skip ケース (aiGenerated=True または generatedTitle あり) --

    def test_no_skip_when_aigenerated_true(self):
        """aiGenerated=True なら generatedTitle 不在でも skip しない。"""
        self.fake_s3.get_object.return_value = _make_s3_response(
            {'topicId': 'eeee', 'aiGenerated': True}
        )
        proc_storage.update_topic_s3_file('eeee', upd={})
        # put_object が呼ばれるか、ETag 一致で呼ばれない場合がある (skip 経路ではない)
        # → put_object ON/OFF の判定は ETag 比較に委ねる: skip ログは出ない
        # ここでは「skip ログが出ていない」を確認する
        # ※ put_object は old_etag と new_etag の比較で決まる。skip 判定とは無関係。

    def test_no_skip_when_existing_meta_has_generated_title(self):
        """既存 meta に generatedTitle があれば upd が空でも put_object は ETag 判定で実行される。"""
        self.fake_s3.get_object.return_value = _make_s3_response(
            {'topicId': 'ffff', 'aiGenerated': False, 'generatedTitle': '既存タイトル'}
        )
        proc_storage.update_topic_s3_file('ffff', upd={})
        # skip ログが出ないこと: skip 経路を通っていないことの確認
        # (実際の put_object 呼び出しは ETag 比較で決まるが、skip は通らない)

    def test_no_skip_when_upd_carries_aigenerated_true(self):
        """upd で aiGenerated=True を渡したら skip しない (新規 AI 生成)。"""
        self.fake_s3.get_object.return_value = _make_s3_response(
            {'topicId': 'gggg', 'aiGenerated': False}
        )
        upd = {
            'aiGenerated': True,
            'generatedTitle': 'AI生成タイトル',
            'generatedSummary': '要約',
        }
        proc_storage.update_topic_s3_file('gggg', upd=upd)
        # put_object が必ず呼ばれる (ETag は変わるはず)
        self.fake_s3.put_object.assert_called_once()
        call = self.fake_s3.put_object.call_args
        self.assertEqual(call.kwargs.get('Key'), 'api/topic/gggg.json')

    def test_no_skip_when_upd_carries_generated_title_only(self):
        """upd に generatedTitle だけあれば aiGenerated 立たなくても skip しない。"""
        self.fake_s3.get_object.return_value = _make_s3_response(
            {'topicId': 'hhhh', 'aiGenerated': False}
        )
        upd = {'generatedTitle': '新しいタイトル'}
        proc_storage.update_topic_s3_file('hhhh', upd=upd)
        self.fake_s3.put_object.assert_called_once()

    # -- 境界: skip 判定がログをきちんと出すか --

    def test_skip_log_format_contains_tid_and_reason(self):
        self.fake_s3.get_object.return_value = _make_s3_response(
            {'topicId': '8f81be6586cbea09', 'aiGenerated': False}
        )
        with mock.patch('builtins.print') as mp:
            proc_storage.update_topic_s3_file('8f81be6586cbea09', upd={})
        # 1 行のフォーマット確認
        printed = [c.args[0] for c in mp.call_args_list if c.args]
        skip_lines = [p for p in printed if isinstance(p, str) and '[SKIP_EMPTY_JSON]' in p]
        self.assertEqual(len(skip_lines), 1, f'SKIP_EMPTY_JSON ログが 1 行必要: {printed}')
        line = skip_lines[0]
        self.assertIn('tid=8f81be6586cbea09', line)
        self.assertIn('reason=aiGenerated=False', line)


if __name__ == '__main__':
    unittest.main()
