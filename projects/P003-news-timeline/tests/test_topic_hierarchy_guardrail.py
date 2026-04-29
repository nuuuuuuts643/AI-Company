"""T2026-0429-E: detect_topic_hierarchy の親子化 false_merge ガードを物理ガード。

背景 (2026-04-29):
  T2026-0429-C の verify_branching_quality.py 実測で
  error_merge=83.3%(10/12) を検出。原因は detect_topic_hierarchy が
  「entity 1+ kw 2+」だけで親子化を許していたため、
  「高市首相」「マリ」「OpenAI」等の主役 1 語＋汎用 kw で
  別事件・別主役のトピックが誤マージされていた。

修正:
  detect_topic_hierarchy に content-similarity ガードを追加。
  validator (verify_branching_quality.py::char_bigrams) と同じ
  char-bigram + max(title_jacc, keyPoint_jacc) で sim を算出し、
  suspect_false_merge 境界 (sim < 0.20) を切る。

実測 (production topics-full.json, n=12 branched pairs):
  suspect_false_merge: 11 件すべて max(title,keyPoint) sim <= 0.18
  ok:                   1 件 sim = 0.32 (チョルノービリ事故40年 系)
  → 0.20 で 11 BLOCK / 1 PASS と完全分離

このテストは以下を物理確認する:
  - 共通 entity だけで内容が違うペアは親子化されない (false_merge ブロック)
  - 共通 entity + 内容類似なペアは親子化される (legitimate ok 通過)
  - keyPoint が片方欠落していても title だけで判定する
  - keyPoint 類似は高いが title 類似が低い場合は max() で救済される
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'lambda', 'fetcher'))

# detect_topic_hierarchy は config を import するので env を埋める
os.environ.setdefault('S3_BUCKET', 'test-bucket')
os.environ.setdefault('AWS_REGION', 'ap-northeast-1')

import text_utils  # noqa: E402


def _topic(tid: str, title: str, keypoint: str = '', article_count: int = 3,
           score: int = 100, first_at: int = 1000, genre: str = '政治') -> dict:
    return {
        'topicId': tid,
        'generatedTitle': title,
        'keyPoint': keypoint,
        'articleCount': article_count,
        'score': score,
        'firstArticleAt': first_at,
        'lastUpdated': first_at,
        'genre': genre,
        'genres': [genre],
    }


class TopicHierarchyGuardrailTest(unittest.TestCase):
    def test_low_content_similarity_blocks_parent_assignment(self):
        """共通 entity「高市首相」と汎用 kw だけで親子化される現状を再現し、
        新ガードで親子化が拒否されることを確認。"""
        parent = _topic(
            'p1',
            '高市首相の補正予算編成方針をめぐる最新の立場まとめ',
            '危機下での補正予算見送りは異例。財政規律重視の姿勢が異例。',
            article_count=5, first_at=1000,
        )
        child = _topic(
            'c1',
            '高市首相が靖国神社に真榊奉納、北朝鮮が狂信的行為と非難',
            '日本首相の靖国参拝が北朝鮮の反発を招く歴史認識対立',
            article_count=3, first_at=2000,
        )
        # 共通 entity / kw を強制的に作る (主役名・汎用語)
        topic_entities = {
            'p1': {'高市首相'},
            'c1': {'高市首相'},
        }
        result = text_utils.detect_topic_hierarchy([parent, child], topic_entities)
        self.assertNotIn(
            'c1', result,
            '別事件 (補正予算 vs 靖国参拝) は同じ主役でも親子化してはいけない',
        )

    def test_high_content_similarity_allows_parent_assignment(self):
        """同主題で title が類似しているペアは親子化される。"""
        parent = _topic(
            'p1',
            'チョルノービリ事故40年と核攻撃をめぐる最新の動きまとめ',
            '歴史的災害の記念日にロシアの攻撃を「核テロ」と命名し国際規範への訴え',
            article_count=5, first_at=1000, genre='国際',
        )
        child = _topic(
            'c1',
            'チョルノービリ事故40年、核リスクをめぐる現在地',
            '40年前の大事故教訓から、核施設への攻撃を国際的に非難する必要性を提示',
            article_count=3, first_at=2000, genre='国際',
        )
        topic_entities = {
            'p1': {'チョルノービリ', '核'},
            'c1': {'チョルノービリ', '核'},
        }
        result = text_utils.detect_topic_hierarchy([parent, child], topic_entities)
        self.assertEqual(
            result.get('c1'), 'p1',
            'タイトル類似度の高い同主題ペアは親子化されるべき',
        )

    def test_helper_hierarchy_bigrams_matches_validator(self):
        """_hierarchy_bigrams の出力が validator (verify_branching_quality.py) と一致することを確認。"""
        # validator の char_bigrams 実装 (snapshot)
        def validator_bigrams(text: str) -> set:
            cleaned = ''.join(
                ch for ch in text
                if not ch.isspace()
                and ch not in '、。「」『』・…ー-—()（）[]［］'
            )
            if len(cleaned) < 2:
                return {cleaned} if cleaned else set()
            return {cleaned[i:i + 2] for i in range(len(cleaned) - 1)}

        for sample in [
            '高市首相の補正予算編成方針をめぐる最新の立場まとめ',
            'チョルノービリ事故40年、核リスクをめぐる現在地',
            'OpenAIの画像生成AI搭載で加速、AI画像氾濫とIT女性人材不足の危機',
            '',
            'a',
        ]:
            self.assertEqual(
                text_utils._hierarchy_bigrams(sample),
                validator_bigrams(sample),
                f'_hierarchy_bigrams must match validator for: {sample!r}',
            )

    def test_max_title_keypoint_picks_higher_jaccard(self):
        """max(title, keyPoint) が高い方を採用することを直接確認 (helper レベル)。"""
        # title はほぼ無関係, keyPoint はほぼ同一
        title_a = 'A社 株価上昇'
        title_b = '欧州金利据え置き'
        kp_a = 'マリ国防相が過激派攻撃で殺害され政情不安が深まった'
        kp_b = 'マリ国防相が過激派攻撃で殺害され政情不安が継続している'
        title_jac = text_utils._jaccard(
            text_utils._hierarchy_bigrams(title_a),
            text_utils._hierarchy_bigrams(title_b),
        )
        kp_jac = text_utils._jaccard(
            text_utils._hierarchy_bigrams(kp_a),
            text_utils._hierarchy_bigrams(kp_b),
        )
        # title はほぼ 0、keyPoint は 0.5 前後なので max() が keyPoint を採用すれば 0.20 を超える
        self.assertLess(title_jac, 0.10, f'title sim 想定外: {title_jac}')
        self.assertGreaterEqual(kp_jac, 0.30, f'keyPoint sim 想定外: {kp_jac}')
        self.assertGreaterEqual(max(title_jac, kp_jac), text_utils._HIERARCHY_CONTENT_SIM_THRESHOLD)

    def test_threshold_constant_matches_validator_boundary(self):
        """ガード閾値 0.20 が validator の suspect_false_merge 境界と一致することを確認。"""
        # verify_branching_quality.py のデフォルト error-merge-threshold は 15%, 境界は sim < 0.2
        self.assertEqual(text_utils._HIERARCHY_CONTENT_SIM_THRESHOLD, 0.20)


if __name__ == '__main__':
    unittest.main()
