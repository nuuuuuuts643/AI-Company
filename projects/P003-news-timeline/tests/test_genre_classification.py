"""T2026-0501-F: 海外ニュースが「政治」に誤分類されない boundary test。

きっかけ: トピック 1017d101df11d48b (ミャンマー政府、スーチー氏に恩赦) が
genre='政治' に分類されていた。fetcher の GENRE_KEYWORDS で
- 政治: '政府' が 1 ヒット
- 国際: ミャンマー / スーチー / ASEAN がいずれも未登録 → 0 ヒット
となり 政治 が勝つ構造的バグだった。情報の地図としては
「日本国内政治」と「海外政治・国際関係」は別ジャンルでないと
ユーザーが地図を読めない (前提知識を要求してしまう)。

実行:
  cd projects/P003-news-timeline
  python3 -m unittest tests.test_genre_classification -v
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'lambda', 'fetcher'))

from text_utils import dominant_genres, override_genre_by_title  # noqa: E402


def _articles(*titles):
    return [{'title': t} for t in titles]


class TestForeignNewsClassification(unittest.TestCase):
    def test_myanmar_suchi_amnesty(self):
        """T2026-0501-F の根本原因ケース。海外政府ニュースは 国際 になるべき。"""
        arts = _articles(
            'ミャンマー政府、スーチー氏に恩赦 「住居で軟禁」',
            'スーチー氏 軟禁状態に 国営メディアが近影公開',
            'ASEAN加盟国の解放要求受け 親軍政権が融和姿勢',
            'クーデター後の国際関係修復 ミンアウンフライン氏',
            'アウンサンスーチー氏の刑期 33年から約18年に短縮',
        )
        genres = dominant_genres(arts)
        self.assertEqual(genres[0], '国際',
                         f'海外政府/要人ニュースが「政治」に誤分類された: {genres}')

        # override 単体でも 国際 を強制できること
        forced = override_genre_by_title(arts)
        self.assertEqual(forced, '国際')

    def test_thailand_government(self):
        # 「タイ」は 2 字で部分一致リスクがあるため (タイトル等にも反応してしまう)、
        # ASEAN や東南アジア等の文脈マーカーを優先して国際を確定させる狙い。
        arts = _articles(
            'タイ・東南アジア首脳が安保協議',
            'ASEAN加盟のタイ 与党再編',
            'タイ大統領 訪米へ',
        )
        self.assertEqual(dominant_genres(arts)[0], '国際')

    def test_india_modi(self):
        arts = _articles(
            'モディ首相 訪日へ',
            'インド政府 半導体投資を発表',
            'インド大統領 来日',
        )
        self.assertEqual(dominant_genres(arts)[0], '国際')

    def test_gaza_palestine(self):
        arts = _articles(
            'ガザ地区で停戦交渉',
            'パレスチナ自治政府 声明',
            'イスラエル政府 軍事作戦継続',
        )
        self.assertEqual(dominant_genres(arts)[0], '国際')

    def test_african_news(self):
        arts = _articles(
            'スーダンで武力衝突',
            'エチオピア政府 和平合意',
            'ナイジェリア大統領 会談',
        )
        self.assertEqual(dominant_genres(arts)[0], '国際')

    def test_japan_domestic_politics_still_seishi(self):
        """日本国内政治は依然 政治 へ。境界が壊れていないこと。"""
        arts = _articles(
            '首相 国会で答弁',
            '内閣改造 与党内で調整',
            '衆院選 自民党が公示',
        )
        self.assertEqual(dominant_genres(arts)[0], '政治')


class TestOverrideForeignAsymmetry(unittest.TestCase):
    """override_genre_by_title が 政治 (日本固有) と 国際 (海外) を区別すること。"""

    def test_japanese_pm_keyword_does_not_trigger_foreign(self):
        arts = _articles('日本の首相 国会演説')
        forced = override_genre_by_title(arts)
        # 国際にはならない (政治 か None)
        self.assertNotEqual(forced, '国際')

    def test_myanmar_government_does_not_trigger_seishi(self):
        """『ミャンマー政府』のような海外政府ニュースが override 政治 に倒れない。"""
        arts = _articles('ミャンマー政府 恩赦発表', 'ミャンマー軍事政権の動向')
        forced = override_genre_by_title(arts)
        self.assertEqual(forced, '国際',
                         '海外政府ニュースが override で 国際 に強制されなかった')


if __name__ == '__main__':
    unittest.main()
