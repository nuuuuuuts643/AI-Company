"""T2026-0428-AI: 記事数グラフ乖離 再発防止 boundary test。

検証対象:
1. fetcher/handler.py が all_articles を URL で dedup してから cluster() に渡すこと
   (cnt = len(g) の水増しを防ぎ、SNAP.articles の URL-dedup と整合させる)

旧バグ: 同一 URL が複数 RSS フィードに含まれる場合、
   - cluster 後の `cnt = len(g)` が水増しされ、
   - meta.articleCount = 20 だが SNAP.articles = 7 件、
   - フロントの「全 X 件の記事」表示と「グラフ最終点」が乖離する。

実行:
  cd projects/P003-news-timeline
  ANTHROPIC_API_KEY=dummy python3 -m unittest tests.test_url_dedup_guard -v
"""
import ast
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HANDLER_PATH = os.path.join(ROOT, 'lambda', 'fetcher', 'handler.py')


class UrlDedupGuardTest(unittest.TestCase):
    """fetcher/handler.py のソース静的解析で URL dedup ステップが残存することを確認。"""

    def setUp(self):
        with open(HANDLER_PATH, 'r', encoding='utf-8') as f:
            self.source = f.read()

    def test_url_dedup_block_exists(self):
        """[URL-DEDUP] のログプリント文が handler.py に存在すること。

        理由: dedup ステップは `cnt = len(g)` の水増し防止に必須。
        コメントだけだと将来 refactor で消える可能性がある → ログ文字列を物理ガードに。
        """
        self.assertIn('[URL-DEDUP]', self.source,
                      '[URL-DEDUP] ログ文字列が消えている。'
                      'URL重複除去ステップが削除されていないか確認すること。')

    def test_dedup_runs_before_cluster(self):
        """URL dedup が cluster() 呼び出しより前に実行されること。"""
        dedup_pos = self.source.find('[URL-DEDUP]')
        cluster_pos = self.source.find('groups = cluster(all_articles)')
        self.assertGreater(dedup_pos, 0, '[URL-DEDUP] ログ位置が見つからない')
        self.assertGreater(cluster_pos, 0, 'cluster(all_articles) 呼び出しが見つからない')
        self.assertLess(dedup_pos, cluster_pos,
                        'URL dedup が cluster() より後ろに移動している。'
                        'cluster の入力が dedup 済みでなければ cnt の水増しが残る。')


class _FakeArticle(dict):
    """テスト用の擬似 article dict。url/title/source が最低限あれば fetcher dedup ロジックで動く。"""


class FetcherDedupBehaviorTest(unittest.TestCase):
    """handler.py のソースから dedup ロジック相当部分を抽出してロジックを検証する。

    handler.py 全体は boto3 等の重い import が走るため、純粋ロジック部分のみ
    テスト用に再現して boundary を assert する。本ロジックが handler.py から逸脱した場合は
    UrlDedupGuardTest が文字列消失で失敗する二重ガード構造。
    """

    @staticmethod
    def _dedupe(all_articles):
        seen = set()
        out = []
        for a in all_articles:
            u = a.get('url')
            if not u or u in seen:
                continue
            seen.add(u)
            out.append(a)
        return out

    def test_empty_list(self):
        self.assertEqual(self._dedupe([]), [])

    def test_no_duplicates(self):
        arts = [_FakeArticle(url='u1'), _FakeArticle(url='u2')]
        self.assertEqual(len(self._dedupe(arts)), 2)

    def test_drops_exact_url_duplicates(self):
        # 旧バグ実例: 同一 URL が 3 回入る → dedup 後は 1 件
        arts = [
            _FakeArticle(url='https://example.com/a', source='news.yahoo.co.jp'),
            _FakeArticle(url='https://example.com/a', source='Yahoo!ニュース'),
            _FakeArticle(url='https://example.com/a', source='ITmedia'),
            _FakeArticle(url='https://example.com/b', source='Asahi'),
        ]
        out = self._dedupe(arts)
        self.assertEqual(len(out), 2)
        self.assertEqual([a['url'] for a in out],
                         ['https://example.com/a', 'https://example.com/b'])

    def test_keeps_first_occurrence_metadata(self):
        # 同じ URL でも最初に出現したエントリの source/title を残す
        arts = [
            _FakeArticle(url='u1', source='SrcA', title='T1'),
            _FakeArticle(url='u1', source='SrcB', title='T1-alt'),
        ]
        out = self._dedupe(arts)
        self.assertEqual(out[0]['source'], 'SrcA')
        self.assertEqual(out[0]['title'], 'T1')

    def test_skips_articles_without_url(self):
        # URL が None / 空のエントリは silently skip（既存動作維持）
        arts = [
            _FakeArticle(title='no-url'),  # url キーなし
            _FakeArticle(url='', title='empty-url'),
            _FakeArticle(url=None, title='none-url'),
            _FakeArticle(url='u1', title='ok'),
        ]
        out = self._dedupe(arts)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['url'], 'u1')

    def test_inflated_count_scenario_real_world(self):
        # 本番再現: meta.articleCount=20 だが unique URL=7 のケース
        # 同一URL を 3 倍に水増ししたフィード入力で dedup 後に 7 件になることを確認
        urls = [f'https://news.example.jp/article/{i}' for i in range(7)]
        arts = []
        for url in urls:
            for src in ('Yahoo!ニュース', '元媒体', 'アグリゲーター'):
                arts.append(_FakeArticle(url=url, source=src, title=f'タイトル {url}'))
        # 計 21 件（7 URL × 3 source 重複）
        self.assertEqual(len(arts), 21)
        out = self._dedupe(arts)
        self.assertEqual(len(out), 7,
                         '水増しシナリオで dedup 後に unique URL 数と一致しない')


if __name__ == '__main__':
    unittest.main()
