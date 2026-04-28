"""T2026-0428-AL: article_fetcher の boundary test。

CLAUDE.md「新規 formatter は boundary test 同梱」適用。0件/壊れた URL/同系列メディア/
HTML パーサのコーナーケース (空 / no-article / 巨大ノイズ) を全部 assert する。

実行:
  cd projects/P003-news-timeline
  python3 -m unittest tests.test_article_fetcher -v
"""
import io
import os
import sys
import unittest
import urllib.error
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'lambda', 'processor'))

import article_fetcher as af


class SelectArticlesTest(unittest.TestCase):
    """select_articles_for_comparison: 信頼性・多様性で上位 N 件を選ぶ。"""

    def test_empty_returns_empty(self):
        self.assertEqual(af.select_articles_for_comparison([]), [])

    def test_no_url_articles_excluded(self):
        articles = [{'title': 't', 'source': 's'}]
        self.assertEqual(af.select_articles_for_comparison(articles), [])

    def test_cat_a_first(self):
        articles = [
            {'url': 'https://www.itmedia.co.jp/x',  'source': 'ITmedia',  'tier': 3},
            {'url': 'https://www.nhk.or.jp/news/y', 'source': 'NHK',       'tier': 1},
            {'url': 'https://www.asahi.com/z',     'source': '朝日新聞',  'tier': 2},
        ]
        picked = af.select_articles_for_comparison(articles, max_count=3)
        self.assertEqual(picked[0]['source'], 'NHK')
        self.assertEqual(picked[0]['mediaCategory'], 'A')
        self.assertEqual(picked[1]['mediaCategory'], 'B')
        self.assertEqual(picked[2]['mediaCategory'], 'C')

    def test_same_domain_group_dedupe(self):
        # 産経 + sankeibiz は同グループ → 1件のみ採用
        articles = [
            {'url': 'https://www.sankei.com/a',     'source': '産経新聞',     'tier': 2},
            {'url': 'https://www.sankeibiz.jp/b',   'source': 'SankeiBiz',    'tier': 2},
            {'url': 'https://www.mainichi.jp/c',    'source': '毎日新聞',     'tier': 2},
            {'url': 'https://www.yomiuri.co.jp/d',  'source': '読売新聞',     'tier': 2},
        ]
        picked = af.select_articles_for_comparison(articles, max_count=3)
        domains = [af._domain_of(p['url']) for p in picked]
        # 同じ sankei グループは1つだけ
        sankei_count = sum(1 for d in domains if 'sankei' in d)
        self.assertEqual(sankei_count, 1, f'sankei グループから2件採用された: {domains}')
        self.assertEqual(len(picked), 3)

    def test_max_count_respected(self):
        articles = [
            {'url': f'https://example{i}.com/p', 'source': f's{i}', 'tier': 3}
            for i in range(10)
        ]
        self.assertEqual(len(af.select_articles_for_comparison(articles, max_count=3)), 3)
        self.assertEqual(len(af.select_articles_for_comparison(articles, max_count=1)), 1)

    def test_tier_orders_within_category(self):
        # 同カテゴリ B 内では tier 値が小さい方が先 (低 tier = 高信頼)
        articles = [
            {'url': 'https://www.asahi.com/a',  'source': '朝日',  'tier': 3},
            {'url': 'https://www.nikkei.com/b', 'source': '日経',  'tier': 1},
        ]
        picked = af.select_articles_for_comparison(articles, max_count=2)
        self.assertEqual(picked[0]['source'], '日経')

    def test_invalid_tier_falls_back_to_default(self):
        articles = [
            {'url': 'https://www.asahi.com/a', 'source': '朝日', 'tier': 'bogus'},
            {'url': 'https://www.asahi.com/b', 'source': '朝日', 'tier': None},
        ]
        # tier が壊れていても落ちずに 1件 (asahi グループは1件のみ)
        picked = af.select_articles_for_comparison(articles, max_count=3)
        self.assertEqual(len(picked), 1)


class DomainHelpersTest(unittest.TestCase):

    def test_domain_strip_www(self):
        self.assertEqual(af._domain_of('https://www.asahi.com/abc'), 'asahi.com')

    def test_domain_empty(self):
        self.assertEqual(af._domain_of(''), '')
        self.assertEqual(af._domain_of(None), '')

    def test_media_category(self):
        self.assertEqual(af._media_category('nhk.or.jp'), 'A')
        self.assertEqual(af._media_category('news.nhk.or.jp'), 'A')
        self.assertEqual(af._media_category('mainichi.jp'), 'B')
        self.assertEqual(af._media_category('itmedia.co.jp'), 'C')
        self.assertEqual(af._media_category('example.com'), 'X')


class TextExtractorTest(unittest.TestCase):
    """HTML パーサ: <article> 内の本文のみを抽出する。"""

    def test_article_tag(self):
        html_text = (
            '<html><body><nav>menu</nav>'
            '<article>' + ('本文テストです。' * 50) + '</article>'
            '<footer>foot</footer></body></html>'
        )
        p = af._TextExtractor()
        p.feed(html_text)
        body = p.best_text()
        self.assertIn('本文テストです', body)
        self.assertNotIn('menu', body)
        self.assertNotIn('foot', body)

    def test_class_hint(self):
        html_text = (
            '<html><body>'
            '<div class="article-body">' + ('クラス命中。' * 50) + '</div>'
            '</body></html>'
        )
        p = af._TextExtractor()
        p.feed(html_text)
        self.assertIn('クラス命中', p.best_text())

    def test_no_content_node_returns_empty(self):
        html_text = '<html><body><div>no article tag here</div></body></html>'
        p = af._TextExtractor()
        p.feed(html_text)
        self.assertEqual(p.best_text(), '')

    def test_empty_html(self):
        p = af._TextExtractor()
        p.feed('')
        self.assertEqual(p.best_text(), '')

    def test_short_article_below_min_excluded(self):
        # 200字未満は採用しない
        p = af._TextExtractor()
        p.feed('<html><body><article>短い</article></body></html>')
        self.assertEqual(p.best_text(), '')

    def test_picks_longest_when_multiple_candidates(self):
        html_text = (
            '<html><body>'
            '<article>' + ('短い候補。' * 50) + '</article>'
            '<article>' + ('長い候補本文です。' * 100) + '</article>'
            '</body></html>'
        )
        p = af._TextExtractor()
        p.feed(html_text)
        self.assertIn('長い候補本文', p.best_text())

    def test_script_inside_article_excluded(self):
        html_text = (
            '<html><body><article>'
            'これは本文。' * 50 +
            '<script>var evil = "noise text noise text"</script>'
            '残りの本文。' * 30 +
            '</article></body></html>'
        )
        p = af._TextExtractor()
        p.feed(html_text)
        body = p.best_text()
        self.assertIn('これは本文', body)
        self.assertNotIn('var evil', body)


class FetchFullTextTest(unittest.TestCase):
    """fetch_full_text: HTTP 失敗系で落ちないことを保証。"""

    def test_empty_url_returns_empty(self):
        self.assertEqual(af.fetch_full_text(''), '')
        self.assertEqual(af.fetch_full_text(None), '')

    def test_http_error_returns_empty(self):
        with mock.patch('urllib.request.urlopen',
                        side_effect=urllib.error.URLError('boom')):
            self.assertEqual(af.fetch_full_text('https://example.com/x'), '')

    def test_timeout_returns_empty(self):
        with mock.patch('urllib.request.urlopen', side_effect=TimeoutError('to')):
            self.assertEqual(af.fetch_full_text('https://example.com/y'), '')

    def test_non_html_returns_empty(self):
        fake = mock.MagicMock()
        fake.headers = {'Content-Type': 'application/pdf'}
        fake.read.return_value = b'%PDF-1.4'
        fake.__enter__ = mock.MagicMock(return_value=fake)
        fake.__exit__ = mock.MagicMock(return_value=False)
        with mock.patch('urllib.request.urlopen', return_value=fake):
            self.assertEqual(af.fetch_full_text('https://example.com/p.pdf'), '')

    def test_html_extracts_article_body(self):
        html_text = (
            '<!doctype html><html><head><meta charset="utf-8"></head><body>'
            '<nav>menu</nav>'
            '<article>' + ('テスト本文。' * 60) + '</article>'
            '</body></html>'
        ).encode('utf-8')
        fake = mock.MagicMock()
        fake.headers = {'Content-Type': 'text/html; charset=utf-8'}
        fake.read.return_value = html_text
        fake.__enter__ = mock.MagicMock(return_value=fake)
        fake.__exit__ = mock.MagicMock(return_value=False)
        with mock.patch('urllib.request.urlopen', return_value=fake):
            body = af.fetch_full_text('https://example.com/a')
        self.assertIn('テスト本文', body)


class FetchFullArticlesTest(unittest.TestCase):
    """fetch_full_articles: 本文が取れない場合 description にフォールバック。"""

    def test_fallback_to_description_when_fetch_fails(self):
        articles = [{
            'url':         'https://www.nhk.or.jp/news/x',
            'source':      'NHK',
            'title':       'タイトル',
            'description': 'スニペットの内容',
            'tier':        1,
        }]
        with mock.patch('article_fetcher.fetch_full_text', return_value=''):
            out = af.fetch_full_articles(articles)
        self.assertEqual(len(out), 1)
        self.assertFalse(out[0]['isFull'])
        self.assertEqual(out[0]['fullText'], 'スニペットの内容')
        self.assertEqual(out[0]['mediaCategory'], 'A')

    def test_full_text_truncated(self):
        articles = [{
            'url':         'https://www.asahi.com/a',
            'source':      '朝日',
            'tier':        2,
            'description': 'snippet',
        }]
        long_body = '本文。' * 5000  # 約 15000 字
        with mock.patch('article_fetcher.fetch_full_text', return_value=long_body):
            out = af.fetch_full_articles(articles, max_text_chars=3000)
        self.assertTrue(out[0]['isFull'])
        self.assertLessEqual(len(out[0]['fullText']), 3000)

    def test_empty_input(self):
        self.assertEqual(af.fetch_full_articles([]), [])


if __name__ == '__main__':
    unittest.main()
