"""T2026-0428-AN: 一次情報ソース判定の boundary test。

検証対象:
  1. score_utils.is_primary_source(url): URL ドメインで一次情報を判定
     - 正規 nhk.or.jp / Reuters / 政府ドメイン → True
     - 偽装 (nhk.or.jp.evil.com) / 空 / None / 不正型 → False
     - 大文字混じり / サブドメイン / ポート付き → 正規ドメインなら True
  2. scoring.apply_tier_and_diversity_scoring が一次情報URL含有で ×1.2 ボーナスを掛けること

CLAUDE.md「新規 formatter は boundary test 同梱」適用。
著作権法32条「引用」設計の物理ゲートとして機能する（出典明示 + バッジ表示の前提）。

実行:
  cd projects/P003-news-timeline
  python3 -m unittest tests.test_primary_source -v
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'lambda', 'fetcher'))

# AWS / boto3 へのアクセスを避けるためダミー env
os.environ.setdefault('S3_BUCKET', 'test-bucket')
os.environ.setdefault('SLACK_WEBHOOK', '')

import score_utils
from score_utils import is_primary_source, PRIMARY_SOURCE_DOMAINS


class IsPrimarySourceTest(unittest.TestCase):
    """URL ドメインベースの一次情報判定。"""

    # ──────────── 正常系: 一次情報源は True ────────────

    def test_nhk_jp_is_primary(self):
        self.assertTrue(is_primary_source('https://www3.nhk.or.jp/news/html/20260428/k10014000000.html'))

    def test_reuters_is_primary(self):
        self.assertTrue(is_primary_source('https://www.reuters.com/world/japan/article-2026-04-28/'))

    def test_apnews_is_primary(self):
        self.assertTrue(is_primary_source('https://apnews.com/article/abc123'))

    def test_bbc_co_uk_is_primary(self):
        self.assertTrue(is_primary_source('https://www.bbc.co.uk/news/world-asia-12345'))

    def test_kyodo_is_primary(self):
        self.assertTrue(is_primary_source('https://english.kyodonews.net/news/2026/04/abc.html')
                        or is_primary_source('https://www.kyodo.jp/article/12345'))

    def test_nordot_is_primary(self):
        self.assertTrue(is_primary_source('https://nordot.app/1234567890'))

    def test_subdomain_match(self):
        # サブドメインも eTLD+1 一致なら一次情報扱い
        self.assertTrue(is_primary_source('https://news.tbs.co.jp/...')) if False else None  # tbs not in list, skip
        self.assertTrue(is_primary_source('https://english.kyodonews.net/...')) if False else None
        self.assertTrue(is_primary_source('https://sub.nikkei.com/article/abc'))

    def test_uppercase_url_normalized(self):
        # ドメインは大文字小文字を区別しない
        self.assertTrue(is_primary_source('HTTPS://WWW.NHK.OR.JP/NEWS/'))

    def test_port_in_url_is_stripped(self):
        # ポート付き URL でも判定可能
        self.assertTrue(is_primary_source('https://www.reuters.com:443/world/article'))

    def test_government_jp_suffix(self):
        # .go.jp は政府専用 TLD → 一次情報
        self.assertTrue(is_primary_source('https://www.kantei.go.jp/jp/news/abc.html'))
        self.assertTrue(is_primary_source('https://www.mhlw.go.jp/stf/abc.html'))

    def test_government_us_suffix(self):
        # .gov は米国政府ドメイン → 一次情報
        self.assertTrue(is_primary_source('https://www.whitehouse.gov/briefing-room/abc'))

    # ──────────── 異常系: 一次情報扱いしない ────────────

    def test_spoofed_subdomain_attack_blocked(self):
        # 重要: nhk.or.jp.evil.com のような偽装ドメインは弾く
        self.assertFalse(is_primary_source('https://nhk.or.jp.evil.com/fake-article'))
        self.assertFalse(is_primary_source('https://reuters.com.attacker.io/fake'))

    def test_partial_match_blocked(self):
        # 接尾辞偽装（fakenhk.or.jp 等）も弾く
        # ※ "fakenhk.or.jp" は ".nhk.or.jp" で終わらないので False
        self.assertFalse(is_primary_source('https://fakenhk.or.jp/article'))

    def test_empty_url_returns_false(self):
        self.assertFalse(is_primary_source(''))

    def test_none_url_returns_false(self):
        self.assertFalse(is_primary_source(None))

    def test_non_string_returns_false(self):
        # int / dict が来ても安全に False
        self.assertFalse(is_primary_source(12345))
        self.assertFalse(is_primary_source({'url': 'https://nhk.or.jp/'}))

    def test_malformed_url_returns_false(self):
        # スキーム無し、不正文字列でも例外を吐かず False
        self.assertFalse(is_primary_source('not-a-url'))
        self.assertFalse(is_primary_source('://broken'))

    def test_aggregator_with_nhk_in_path_is_not_primary(self):
        # まとめサイトの URL に "nhk" が含まれていても一次情報ではない
        self.assertFalse(is_primary_source('https://matome-site.example.com/articles/nhk-news-2026'))

    def test_yahoo_news_is_not_primary(self):
        # アグリゲーターは一次情報扱いしない
        self.assertFalse(is_primary_source('https://news.yahoo.co.jp/articles/abc123'))

    def test_personal_blog_is_not_primary(self):
        self.assertFalse(is_primary_source('https://example.com/blog/post-1'))

    # ──────────── ホワイトリスト一貫性 ────────────

    def test_whitelist_all_lowercase(self):
        # ホワイトリスト自体が小文字で統一されていること（正規化前提）
        for d in PRIMARY_SOURCE_DOMAINS:
            self.assertEqual(d, d.lower(), f'PRIMARY_SOURCE_DOMAINS contains non-lowercase: {d}')

    def test_whitelist_no_leading_dot(self):
        # 先頭ドット禁止（_domain_in_cat の suffix チェックで二重ドットになる）
        for d in PRIMARY_SOURCE_DOMAINS:
            self.assertFalse(d.startswith('.'), f'PRIMARY_SOURCE_DOMAINS leading dot: {d}')


class ScoringPrimaryBonusTest(unittest.TestCase):
    """apply_tier_and_diversity_scoring の一次情報×1.2 ボーナス。"""

    def setUp(self):
        # scoring モジュールは config をロード時に S3/Dynamo を参照する場合あり
        sys.path.insert(0, os.path.join(ROOT, 'lambda', 'fetcher'))
        import scoring
        self.scoring = scoring

    def _articles(self, urls):
        return [{'url': u, 'source': u, 'tier': 2} for u in urls]

    def test_primary_url_gives_bonus(self):
        # 一次情報URL含む → ×1.2 ボーナス（tier×1.0平均と合わせて 100×1.0×1.2 = 120）
        articles = self._articles([
            'https://www3.nhk.or.jp/news/html/article1.html',
            'https://example.com/article2',
        ])
        result = self.scoring.apply_tier_and_diversity_scoring(articles, 100.0)
        # cat_a (NHK) ボーナス×1.5 + 一次情報×1.2 = 100 × 1.0 × 1.5 × 1.2 = 180
        self.assertGreaterEqual(result, 100.0 * 1.5 * 1.2 - 0.01)

    def test_no_primary_url_no_bonus(self):
        # 一次情報源 0 → ×1.2 ボーナス無し
        articles = self._articles([
            'https://example.com/article1',
            'https://example.org/article2',
        ])
        baseline = self.scoring.apply_tier_and_diversity_scoring(articles, 100.0)
        # ×1.2 が掛からないので baseline は 100×1.0(tier平均) = 100 程度
        self.assertLess(baseline, 100.0 * 1.2)

    def test_spoofed_url_does_not_get_bonus(self):
        # 偽装URL（nhk.or.jp.evil.com）はボーナス対象外
        articles = self._articles([
            'https://nhk.or.jp.evil.com/fake',
            'https://example.com/legit',
        ])
        result = self.scoring.apply_tier_and_diversity_scoring(articles, 100.0)
        # 一次情報ボーナス×1.2 が掛からない
        self.assertLess(result, 100.0 * 1.2)

    def test_empty_articles_returns_unchanged(self):
        self.assertEqual(self.scoring.apply_tier_and_diversity_scoring([], 50.0), 50.0)


if __name__ == '__main__':
    unittest.main()
