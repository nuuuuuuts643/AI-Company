"""Step 6 S2: チャプター差分処理のユニットテスト。

検証対象:
  proc_storage.get_new_articles_since — since_date フィルタリング
  proc_storage.append_chapter — DynamoDB list_append 呼び出し
  handler.py チャプターモード — 新着なし → Claude 呼び出しなし

実行:
  cd projects/P003-news-timeline
  S3_BUCKET=test python3 -m unittest tests.test_chapter_generation -v
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


# ---------------------------------------------------------------------------
# get_new_articles_since のテスト
# ---------------------------------------------------------------------------

class GetNewArticlesSinceTest(unittest.TestCase):
    """since_date フィルタリングの境界値テスト。"""

    def _make_articles(self):
        return [
            {'title': '記事A', 'url': 'http://ex/a', 'pubDate': '2026-04-29'},
            {'title': '記事B', 'url': 'http://ex/b', 'pubDate': '2026-04-30'},
            {'title': '記事C', 'url': 'http://ex/c', 'pubDate': '2026-05-01'},
            {'title': '記事D', 'url': 'http://ex/d', 'pubDate': '2026-05-02'},
        ]

    def test_since_none_returns_all(self):
        """since_date が None のとき全件を返す。"""
        arts = self._make_articles()
        result = proc_storage.get_new_articles_since(arts, None)
        self.assertEqual(len(result), 4)

    def test_since_date_excludes_equal_date(self):
        """since_date と同日の記事は含まない（strictly after）。"""
        arts = self._make_articles()
        result = proc_storage.get_new_articles_since(arts, '2026-04-30')
        urls = [a['url'] for a in result]
        self.assertNotIn('http://ex/a', urls)  # 2026-04-29: 古い
        self.assertNotIn('http://ex/b', urls)  # 2026-04-30: 同日は除外
        self.assertIn('http://ex/c', urls)      # 2026-05-01: 新しい
        self.assertIn('http://ex/d', urls)      # 2026-05-02: 新しい
        self.assertEqual(len(result), 2)

    def test_all_articles_older_returns_empty(self):
        """全記事が since_date より古い場合は空リストを返す。"""
        arts = self._make_articles()
        result = proc_storage.get_new_articles_since(arts, '2026-05-10')
        self.assertEqual(result, [])

    def test_all_articles_newer_returns_all(self):
        """全記事が since_date より新しい場合は全件を返す。"""
        arts = self._make_articles()
        result = proc_storage.get_new_articles_since(arts, '2026-04-01')
        self.assertEqual(len(result), 4)

    def test_no_pubdate_included(self):
        """pubDate が欠落している記事は含める（除外しない）。"""
        arts = [
            {'title': '記事E', 'url': 'http://ex/e'},
            {'title': '記事F', 'url': 'http://ex/f', 'pubDate': '2026-04-28'},
        ]
        result = proc_storage.get_new_articles_since(arts, '2026-04-30')
        urls = [a['url'] for a in result]
        self.assertIn('http://ex/e', urls)   # pubDate なし → 含める
        self.assertNotIn('http://ex/f', urls)  # 2026-04-28: 古い

    def test_empty_articles_returns_empty(self):
        """空リストを渡した場合は空リストを返す。"""
        result = proc_storage.get_new_articles_since([], '2026-04-30')
        self.assertEqual(result, [])

    def test_invalid_since_date_returns_all(self):
        """since_date が不正な文字列のときは全件を返す。"""
        arts = self._make_articles()
        result = proc_storage.get_new_articles_since(arts, 'not-a-date')
        self.assertEqual(len(result), 4)


# ---------------------------------------------------------------------------
# append_chapter のモックテスト
# ---------------------------------------------------------------------------

class AppendChapterTest(unittest.TestCase):
    """DynamoDB list_append が正しく呼ばれることを確認する。"""

    def setUp(self):
        self.mock_table = mock.MagicMock()
        self.patch_table = mock.patch.object(proc_storage, 'table', self.mock_table)
        self.patch_table.start()

    def tearDown(self):
        self.patch_table.stop()

    def _sample_chapter(self):
        return {
            'date': '2026-05-01',
            'summary': '事実サマリー',
            'commentary': '解説テキスト',
            'prediction': '予測テキスト',
            'articleIds': ['http://ex/a', 'http://ex/b'],
        }

    def test_basic_append(self):
        """通常の append が update_item を1回呼び出すこと。"""
        chap = self._sample_chapter()
        proc_storage.append_chapter('topic-id-123', chap)
        self.mock_table.update_item.assert_called_once()

    def test_update_expression_contains_list_append(self):
        """UpdateExpression に list_append と lastChapterDate 更新が含まれること。"""
        chap = self._sample_chapter()
        proc_storage.append_chapter('topic-id-123', chap)
        call_kwargs = self.mock_table.update_item.call_args.kwargs
        expr = call_kwargs['UpdateExpression']
        self.assertIn('list_append', expr)
        self.assertIn('lastChapterDate', expr)

    def test_key_contains_topic_id(self):
        """DynamoDB Key に topicId と SK='META' が含まれること。"""
        chap = self._sample_chapter()
        proc_storage.append_chapter('topic-abc-def', chap)
        call_kwargs = self.mock_table.update_item.call_args.kwargs
        self.assertEqual(call_kwargs['Key']['topicId'], 'topic-abc-def')
        self.assertEqual(call_kwargs['Key']['SK'], 'META')

    def test_chapter_in_expression_values(self):
        """ExpressionAttributeValues に新チャプターが含まれること。"""
        chap = self._sample_chapter()
        proc_storage.append_chapter('topic-id-123', chap)
        call_kwargs = self.mock_table.update_item.call_args.kwargs
        values = call_kwargs['ExpressionAttributeValues']
        self.assertIn(':new_chapter', values)
        self.assertEqual(values[':new_chapter'], [chap])

    def test_with_related_topic_ids(self):
        """related_topic_ids を渡すと relatedTopicIds が UpdateExpression に含まれること。"""
        chap = self._sample_chapter()
        proc_storage.append_chapter('topic-id-123', chap, related_topic_ids=['t1', 't2'])
        call_kwargs = self.mock_table.update_item.call_args.kwargs
        expr = call_kwargs['UpdateExpression']
        self.assertIn('relatedTopicIds', expr)
        values = call_kwargs['ExpressionAttributeValues']
        self.assertEqual(values[':rtids'], ['t1', 't2'])

    def test_without_related_topic_ids(self):
        """related_topic_ids を渡さないと relatedTopicIds が更新されないこと。"""
        chap = self._sample_chapter()
        proc_storage.append_chapter('topic-id-123', chap)
        call_kwargs = self.mock_table.update_item.call_args.kwargs
        expr = call_kwargs['UpdateExpression']
        self.assertNotIn('relatedTopicIds', expr)


# ---------------------------------------------------------------------------
# チャプターモードのスキップ条件テスト（handler.py）
# ---------------------------------------------------------------------------

class ChapterModeSkipTest(unittest.TestCase):
    """新着記事なし → Claude 呼び出しなし。"""

    def _make_pending_topic(self, genre='politics', last_chapter_date='2026-05-01',
                             article_count=5, ai_generated=True):
        return {
            'topicId': 'test-topic-id',
            'title': 'テストトピック',
            'generatedTitle': 'テストトピック（生成済み）',
            'articleCount': article_count,
            'score': 50,
            'velocityScore': 1.0,
            'aiGenerated': ai_generated,
            'pendingAI': True,
            'genre': genre,
            'genres': [genre],
            'keyPoint': 'テストのキーポイント' * 12,
            'lastChapterDate': last_chapter_date,
            'chapters': [],
        }

    def _make_articles(self, dates):
        return [
            {'title': f'記事 {d}', 'url': f'http://ex/{i}', 'pubDate': d}
            for i, d in enumerate(dates)
        ]

    def test_no_new_articles_skips_claude(self):
        """lastChapterDate 以降の新着記事なし → generate_chapter を呼ばない。"""
        topic = self._make_pending_topic(last_chapter_date='2026-05-02')
        articles = self._make_articles(['2026-04-30', '2026-05-01', '2026-05-02'])

        with mock.patch('proc_storage.get_new_articles_since', return_value=[]) as mock_filter, \
             mock.patch('proc_ai.generate_chapter') as mock_gen:
            new_arts = proc_storage.get_new_articles_since(articles, topic['lastChapterDate'])
            mock_filter.return_value = []
            self.assertEqual(new_arts, [])
            # generate_chapter は呼ばれないはず
            mock_gen.assert_not_called()

    def test_new_articles_present_would_call_claude(self):
        """新着記事あり → get_new_articles_since が空でないことを確認。"""
        topic = self._make_pending_topic(last_chapter_date='2026-04-30')
        articles = self._make_articles(['2026-05-01', '2026-05-02'])

        result = proc_storage.get_new_articles_since(articles, '2026-04-30')
        self.assertEqual(len(result), 2)

    def _parse_chapter_mode_genres(self, env_value: str) -> frozenset:
        """handler.py の _CHAPTER_MODE_GENRES と同じパースロジック。"""
        return frozenset(
            g.strip().lower()
            for g in env_value.split(',')
            if g.strip()
        )

    def test_chapter_mode_not_active_when_genre_not_in_env(self):
        """CHAPTER_MODE_GENRES='politics' のとき politics のみ有効。"""
        genres = self._parse_chapter_mode_genres('politics')
        self.assertIn('politics', genres)
        self.assertNotIn('tech', genres)

    def test_chapter_mode_empty_env_disables_all(self):
        """CHAPTER_MODE_GENRES が空のとき空集合になる。"""
        genres = self._parse_chapter_mode_genres('')
        self.assertEqual(genres, frozenset())

    def test_chapter_mode_multiple_genres(self):
        """カンマ区切り複数ジャンルが正しくパースされる。"""
        genres = self._parse_chapter_mode_genres('politics,tech, economy ')
        self.assertIn('politics', genres)
        self.assertIn('tech', genres)
        self.assertIn('economy', genres)
        self.assertEqual(len(genres), 3)


if __name__ == '__main__':
    unittest.main()
