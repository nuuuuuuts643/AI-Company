"""Step 6 S2.5: ソースフィルタリングのユニットテスト。

実行:
  cd projects/P003-news-timeline
  S3_BUCKET=test python3 -m pytest tests/test_proc_sources.py -v
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'lambda', 'processor'))

os.environ.setdefault('S3_BUCKET', 'test-bucket')
os.environ.setdefault('AWS_REGION', 'ap-northeast-1')
os.environ.setdefault('ANTHROPIC_API_KEY', '***REDACTED-SEC3***')

from proc_sources import detect_syndicated, deduplicate_articles, filter_articles, load_source_policy  # noqa: E402


_POLICY = {
    'tiers': {
        'A': ['nhk.or.jp'],
        'B': ['asahi.com', 'nikkei.com'],
    },
    'summarize_tiers': ['A', 'B'],
    'max_articles_per_source': 2,
    'min_content_length': 0,  # テスト基本ポリシーでは長さフィルタを無効化
    'dedup_syndicated': True,
    'syndicated_patterns': ['によると', '（共同）', '（ロイター）', '（AP）', '（時事）', 'が報じた'],
}


# ---------------------------------------------------------------------------
# detect_syndicated
# ---------------------------------------------------------------------------
class DetectSyndicatedTest(unittest.TestCase):

    def test_syndicated_pattern_in_title(self):
        a = {'title': '首相によると今後の方針を検討', 'url': 'http://ex.com/1', 'source': ''}
        self.assertTrue(detect_syndicated(a))

    def test_kyodo_pattern_in_title(self):
        a = {'title': '防衛費増額へ（共同）', 'url': 'http://ex.com/2', 'source': ''}
        self.assertTrue(detect_syndicated(a))

    def test_reuters_pattern_in_title(self):
        a = {'title': '円安加速（ロイター）', 'url': 'http://ex.com/3', 'source': ''}
        self.assertTrue(detect_syndicated(a))

    def test_syndicated_pattern_in_source(self):
        a = {'title': '通常記事', 'url': 'http://ex.com/4', 'source': '共同通信'}
        # 「共同」は「（共同）」のパターンにマッチしない
        self.assertFalse(detect_syndicated(a))

    def test_syndicated_pattern_in_source_kyodo(self):
        a = {'title': '通常記事', 'url': 'http://ex.com/5', 'source': 'ABC（共同）'}
        self.assertTrue(detect_syndicated(a))

    def test_no_syndicated_pattern(self):
        a = {'title': '政府が新方針を発表した', 'url': 'http://nhk.or.jp/1', 'source': 'NHK'}
        self.assertFalse(detect_syndicated(a))

    def test_empty_article(self):
        self.assertFalse(detect_syndicated({}))

    def test_pattern_only_in_snippet(self):
        a = {'title': '通常記事', 'url': 'http://ex.com/6', 'source': '', 'snippet': '関係者によると詳細は不明'}
        self.assertTrue(detect_syndicated(a))

    def test_pattern_not_at_start_still_detected(self):
        """タイトル中間にパターンがあっても検出する（本文冒頭限定ではない）。"""
        a = {'title': '新法案について関係者によると審議入りへ', 'url': 'http://ex.com/7', 'source': ''}
        self.assertTrue(detect_syndicated(a))


# ---------------------------------------------------------------------------
# deduplicate_articles
# ---------------------------------------------------------------------------
class DeduplicateArticlesTest(unittest.TestCase):

    def test_no_duplicates(self):
        arts = [
            {'title': '記事A', 'url': 'http://nhk.or.jp/a'},
            {'title': '記事B', 'url': 'http://asahi.com/b'},
        ]
        result = deduplicate_articles(arts)
        self.assertEqual(len(result), 2)

    def test_duplicate_same_title(self):
        arts = [
            {'title': '同じ見出し', 'url': 'http://asahi.com/1'},
            {'title': '同じ見出し', 'url': 'http://nikkei.com/1'},
        ]
        result = deduplicate_articles(arts)
        self.assertEqual(len(result), 1)

    def test_tier_a_preferred_over_b(self):
        """Tier-A ソースが Tier-B より優先される。"""
        arts = [
            {'title': '同じ記事', 'url': 'http://asahi.com/1'},   # Tier-B
            {'title': '同じ記事', 'url': 'http://nhk.or.jp/1'},   # Tier-A
        ]
        result = deduplicate_articles(arts)
        self.assertEqual(len(result), 1)
        self.assertIn('nhk.or.jp', result[0]['url'])

    def test_same_tier_longer_content_preferred(self):
        """同ティアなら content が長い方を選ぶ。"""
        arts = [
            {'title': '同じ記事', 'url': 'http://asahi.com/1', 'content': 'short'},
            {'title': '同じ記事', 'url': 'http://asahi.com/2', 'content': 'much longer content here'},
        ]
        result = deduplicate_articles(arts)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['url'], 'http://asahi.com/2')

    def test_empty_list(self):
        self.assertEqual(deduplicate_articles([]), [])

    def test_symbol_normalization(self):
        """記号の有無で同一記事と判定される。"""
        arts = [
            {'title': '【速報】増税へ', 'url': 'http://nhk.or.jp/1'},
            {'title': '速報　増税へ', 'url': 'http://asahi.com/1'},
        ]
        result = deduplicate_articles(arts)
        self.assertEqual(len(result), 1)


# ---------------------------------------------------------------------------
# filter_articles
# ---------------------------------------------------------------------------
class FilterArticlesTest(unittest.TestCase):

    def _make_articles(self):
        return [
            {'title': '政府が新方針を発表した（NHK速報）', 'url': 'http://nhk.or.jp/1', 'source': 'NHK'},
            {'title': '防衛費増額へ（共同）', 'url': 'http://asahi.com/2', 'source': '朝日新聞'},
            {'title': '政府が新方針を発表した（NHK速報）', 'url': 'http://nikkei.com/3', 'source': '日経'},
            {'title': 'NHK追加記事', 'url': 'http://nhk.or.jp/4', 'source': 'NHK'},
            {'title': 'NHK3本目', 'url': 'http://nhk.or.jp/5', 'source': 'NHK'},
        ]

    def test_syndicated_rejected(self):
        """転載パターンがある記事は rejected に入る。"""
        arts = [
            {'title': '政府方針（共同）', 'url': 'http://asahi.com/1', 'source': ''},
            {'title': '政府が方針を発表', 'url': 'http://nhk.or.jp/1', 'source': 'NHK'},
        ]
        result = filter_articles(arts, _POLICY)
        rejected_reasons = [a['_reject_reason'] for a in result['rejected']]
        self.assertIn('syndicated', rejected_reasons)
        selected_urls = [a['url'] for a in result['selected']]
        self.assertIn('http://nhk.or.jp/1', selected_urls)

    def test_max_per_source_enforced(self):
        """同一ソース上限を超えた記事は rejected に入る。"""
        arts = [
            {'title': '記事1', 'url': 'http://nhk.or.jp/1', 'source': 'NHK'},
            {'title': '記事2', 'url': 'http://nhk.or.jp/2', 'source': 'NHK'},
            {'title': '記事3', 'url': 'http://nhk.or.jp/3', 'source': 'NHK'},
        ]
        policy = dict(_POLICY, max_articles_per_source=2)
        result = filter_articles(arts, policy)
        self.assertEqual(len(result['selected']), 2)
        self.assertEqual(len(result['rejected']), 1)
        self.assertIn('max_per_source', result['rejected'][0]['_reject_reason'])

    def test_single_source_true_when_one_domain(self):
        """1ドメインの記事のみ → single_source=True。"""
        arts = [
            {'title': '記事1', 'url': 'http://nhk.or.jp/1', 'source': 'NHK'},
            {'title': '記事2', 'url': 'http://nhk.or.jp/2', 'source': 'NHK'},
        ]
        result = filter_articles(arts, _POLICY)
        self.assertTrue(result['single_source'])

    def test_single_source_false_when_multiple_domains(self):
        """複数ドメイン → single_source=False。"""
        arts = [
            {'title': '記事1', 'url': 'http://nhk.or.jp/1', 'source': 'NHK'},
            {'title': '記事2', 'url': 'http://asahi.com/1', 'source': '朝日'},
        ]
        result = filter_articles(arts, _POLICY)
        self.assertFalse(result['single_source'])

    def test_empty_input(self):
        result = filter_articles([], _POLICY)
        self.assertEqual(result['selected'], [])
        self.assertEqual(result['rejected'], [])
        self.assertFalse(result['single_source'])

    def test_all_syndicated_keeps_one(self):
        """全記事が転載の場合、1件残す。"""
        arts = [
            {'title': '記事A（共同）', 'url': 'http://asahi.com/1', 'source': ''},
            {'title': '記事B（共同）', 'url': 'http://nikkei.com/1', 'source': ''},
        ]
        result = filter_articles(arts, _POLICY)
        self.assertEqual(len(result['selected']), 1)

    def test_summary_string_format(self):
        """summary 文字列に before=/after=/single_source= が含まれる。"""
        arts = [{'title': '記事', 'url': 'http://nhk.or.jp/1', 'source': 'NHK'}]
        result = filter_articles(arts, _POLICY)
        self.assertIn('before=', result['summary'])
        self.assertIn('after=', result['summary'])
        self.assertIn('single_source=', result['summary'])

    def test_too_short_rejected(self):
        """min_content_length 未満のタイトルのみの記事は rejected に入る。"""
        policy = dict(_POLICY, min_content_length=50)
        arts = [
            {'title': '短い', 'url': 'http://nhk.or.jp/1', 'source': 'NHK'},
            {'title': 'これは50文字以上になるように書かれた十分に長いニュースタイトルの記事です', 'url': 'http://nhk.or.jp/2', 'source': 'NHK'},
        ]
        result = filter_articles(arts, policy)
        rejected_reasons = [a['_reject_reason'] for a in result['rejected']]
        self.assertTrue(any('too_short' in r for r in rejected_reasons))


# ---------------------------------------------------------------------------
# load_source_policy
# ---------------------------------------------------------------------------
class LoadSourcePolicyTest(unittest.TestCase):

    def test_default_policy_returned_when_no_file(self):
        """存在しないパスを渡したらデフォルトが返る。"""
        policy = load_source_policy('/nonexistent/path.json')
        self.assertIn('tiers', policy)
        self.assertIn('syndicated_patterns', policy)

    def test_custom_policy_loaded(self):
        """実在の source-policy.json が読める。"""
        policy_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'source-policy.json',
        )
        if not os.path.isfile(policy_path):
            self.skipTest('source-policy.json not found')
        policy = load_source_policy(policy_path)
        self.assertIn('tiers', policy)
        self.assertIn('A', policy['tiers'])


if __name__ == '__main__':
    unittest.main()
