"""T2026-0501-H boundary test: トピックマージのエンティティゲート + Haiku 判定。

検証対象 (PO 指示「混入 > 分裂」):
  - Jaccard 高 + entity 重複なし → マージしない (例: 米国 vs 日本)
  - Jaccard 高 + entity 重複あり → マージする
  - Jaccard 中間 + entity 重複あり → Haiku に委譲
  - Jaccard 低                    → マージしない
  - Haiku 失敗 / API key 未設定    → failsafe で merge しない
  - extract_merge_entities が固有名詞 (人名/組織/カタカナ/英大文字) を抽出
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAMBDA = os.path.join(ROOT, 'lambda', 'fetcher')
if LAMBDA not in sys.path:
    sys.path.insert(0, LAMBDA)


class ExtractMergeEntitiesTest(unittest.TestCase):
    """extract_merge_entities が必要な entity を抽出することを検証。"""

    @classmethod
    def setUpClass(cls):
        from text_utils import extract_merge_entities  # type: ignore
        cls.fn = staticmethod(extract_merge_entities)

    def test_katakana_proper_noun_extracted(self):
        ents = self.fn('トランプ大統領が新方針を発表')
        self.assertIn('トランプ', ents)

    def test_kanji_proper_noun_extracted(self):
        # ENTITY_PATTERNS の `アメリカ|米国|アメリカ合衆国` canonical は 'アメリカ'
        ents = self.fn('米国が関税引き上げを発表')
        self.assertIn('アメリカ', ents)

    def test_english_caps_extracted(self):
        ents = self.fn('Apple decides new strategy')
        # "Apple" のような英大文字始まりは含まれる
        self.assertIn('Apple', ents)

    def test_generic_words_excluded(self):
        ents = self.fn('政府の対応について発表')
        # 「政府」「発表」「対応」は汎用語扱い → 除外
        self.assertNotIn('政府', ents)
        self.assertNotIn('発表', ents)
        self.assertNotIn('対応', ents)

    def test_synonym_normalized(self):
        ents = self.fn('アメリカが新政策を発表')
        # SYNONYMS で 'アメリカ' → '米国'
        self.assertIn('米国', ents)

    def test_empty_input(self):
        self.assertEqual(self.fn(''), set())
        self.assertEqual(self.fn(None), set())  # type: ignore[arg-type]

    def test_entity_overlap_detects_same_country(self):
        ents_a = self.fn('米国の関税引き上げ')
        ents_b = self.fn('米国がGDP速報を発表')
        self.assertTrue(ents_a & ents_b, 'same country (米国) should overlap')

    def test_entity_overlap_separates_different_countries(self):
        ents_a = self.fn('関税引き上げ 米国')
        ents_b = self.fn('関税引き上げ 日本')
        # PO 例: 米国 vs 日本 は別事件 → entity 重複なしを期待
        # 「関税引き上げ」は固有名詞ではないので除外。米国 / 日本 は互いに別 entity。
        self.assertFalse(ents_a & ents_b,
                         f'米国 vs 日本 should NOT overlap (got {ents_a & ents_b})')


class AIMergeJudgeFailsafeTest(unittest.TestCase):
    """API key 未設定 / 失敗時の failsafe (= 別トピック扱い) を検証。"""

    def test_no_api_key_returns_false_for_all(self):
        from ai_merge_judge import AIMergeJudge  # type: ignore
        judge = AIMergeJudge(api_key='')
        result = judge.judge_pairs([
            {'title_a': 'A', 'title_b': 'B', 'entities_a': ['x'],
             'entities_b': ['x'], 'shared_entities': ['x']},
        ])
        # すべて False (= マージしない)
        self.assertEqual(set(result.values()), {False})

    def test_empty_pairs_returns_empty(self):
        from ai_merge_judge import AIMergeJudge  # type: ignore
        judge = AIMergeJudge(api_key='dummy')
        self.assertEqual(judge.judge_pairs([]), {})

    def test_borderline_threshold_constants(self):
        from ai_merge_judge import AIMergeJudge, JACCARD_LOW, JACCARD_HIGH  # type: ignore
        self.assertEqual(JACCARD_LOW, 0.15)
        self.assertEqual(JACCARD_HIGH, 0.35)
        self.assertTrue(AIMergeJudge.is_borderline(0.20))
        self.assertTrue(AIMergeJudge.is_borderline(0.15))
        self.assertFalse(AIMergeJudge.is_borderline(0.14))
        self.assertFalse(AIMergeJudge.is_borderline(0.35))
        self.assertFalse(AIMergeJudge.is_borderline(0.50))

    def test_self_pair_skipped(self):
        from ai_merge_judge import AIMergeJudge  # type: ignore
        judge = AIMergeJudge(api_key='')
        result = judge.judge_pairs([
            {'title_a': 'same', 'title_b': 'same', 'entities_a': [],
             'entities_b': [], 'shared_entities': []},
        ])
        self.assertEqual(result, {})

    def test_cache_returns_consistent_result(self):
        from ai_merge_judge import AIMergeJudge  # type: ignore
        judge = AIMergeJudge(api_key='')
        # 1 回目: failsafe で False
        r1 = judge.judge_pairs([
            {'title_a': 'A', 'title_b': 'B', 'entities_a': ['x'],
             'entities_b': ['x'], 'shared_entities': ['x']},
        ])
        # 2 回目: cache hit (API key 無くても)
        r2 = judge.judge_pairs([
            {'title_a': 'B', 'title_b': 'A', 'entities_a': ['x'],
             'entities_b': ['x'], 'shared_entities': ['x']},
        ])
        self.assertEqual(r1, r2, 'cache key は順序非依存であるべき')


class MismergeDetectionTest(unittest.TestCase):
    """detect_mismerge_signals の境界値テスト。"""

    @classmethod
    def setUpClass(cls):
        from merge_audit import detect_mismerge_signals  # type: ignore
        from text_utils import extract_merge_entities  # type: ignore
        cls.detect = staticmethod(detect_mismerge_signals)
        cls.entities = staticmethod(extract_merge_entities)

    def test_no_articles_returns_clean(self):
        r = self.detect([])
        self.assertFalse(r['suspectedMismerge'])
        self.assertEqual(r['reasons'], [])

    def test_time_gap_over_7_days_flagged(self):
        # 8日離れた記事 2件 → time_gap
        articles = [
            {'title': 'A', 'publishedAt': 1700000000},  # 古い
            {'title': 'B', 'publishedAt': 1700000000 + 8 * 86400},  # 8日後
        ]
        r = self.detect(articles)
        self.assertTrue(r['suspectedMismerge'])
        self.assertIn('time_gap', r['reasons'])

    def test_time_gap_under_7_days_clean(self):
        articles = [
            {'title': 'A', 'publishedAt': 1700000000},
            {'title': 'B', 'publishedAt': 1700000000 + 6 * 86400},  # 6日後 = OK
        ]
        r = self.detect(articles)
        self.assertNotIn('time_gap', r['reasons'])

    def test_entity_split_two_clusters_flagged(self):
        # 米国 cluster 2件 + 日本 cluster 2件 → entity_split
        articles = [
            {'title': '米国の関税政策'},
            {'title': '米国大統領が新方針'},
            {'title': '日本政府の対応'},
            {'title': '日本円安が進む'},
        ]
        r = self.detect(articles, extract_entities_fn=self.entities)
        self.assertTrue(r['suspectedMismerge'])
        self.assertIn('entity_split', r['reasons'])

    def test_entity_no_split_clean(self):
        # 全て米国関連 → 単一クラスタ
        articles = [
            {'title': '米国の関税政策'},
            {'title': '米国大統領が新方針'},
            {'title': '米国議会が法案を可決'},
            {'title': '米国経済の見通し'},
        ]
        r = self.detect(articles, extract_entities_fn=self.entities)
        self.assertNotIn('entity_split', r['reasons'])

    def test_count_spike_over_2x_flagged(self):
        articles = [{'title': f'a{i}'} for i in range(15)]
        r = self.detect(articles, prev_article_count=5)  # 5 → 15 (3倍) → spike
        self.assertTrue(r['suspectedMismerge'])
        self.assertIn('count_spike', r['reasons'])

    def test_count_spike_within_2x_clean(self):
        articles = [{'title': f'a{i}'} for i in range(8)]
        r = self.detect(articles, prev_article_count=5)  # 5 → 8 (1.6倍) → OK
        self.assertNotIn('count_spike', r['reasons'])

    def test_all_signals_combine(self):
        articles = [
            {'title': '米国の関税政策', 'publishedAt': 1700000000},
            {'title': '米国大統領が新方針', 'publishedAt': 1700000000},
            {'title': '日本政府の対応', 'publishedAt': 1700000000 + 10 * 86400},
            {'title': '日本円安', 'publishedAt': 1700000000 + 10 * 86400},
        ]
        r = self.detect(articles, extract_entities_fn=self.entities, prev_article_count=1)
        self.assertTrue(r['suspectedMismerge'])
        # time_gap (10日) と entity_split (米国/日本) と count_spike (1→4) すべて立つ
        self.assertIn('time_gap', r['reasons'])
        self.assertIn('entity_split', r['reasons'])
        self.assertIn('count_spike', r['reasons'])

    # T2026-0502-N: 新動作テスト
    def test_count_spike_only_suppressed_for_sports(self):
        """T2026-0502-N: count_spike 単独 + スポーツジャンルは suspectedMismerge にならない"""
        articles = [{'title': f'試合{i}'} for i in range(15)]
        r = self.detect(articles, prev_article_count=5, genre='スポーツ')
        self.assertFalse(r['suspectedMismerge'])
        self.assertNotIn('count_spike', r['reasons'])

    def test_count_spike_only_suppressed_for_entertainment(self):
        """T2026-0502-N: count_spike 単独 + エンタメジャンルは suspectedMismerge にならない"""
        articles = [{'title': f'記事{i}'} for i in range(15)]
        r = self.detect(articles, prev_article_count=5, genre='エンタメ')
        self.assertFalse(r['suspectedMismerge'])

    def test_count_spike_plus_other_not_suppressed(self):
        """T2026-0502-N: count_spike + time_gap 複合はスポーツでも抑制しない"""
        articles = [
            {'title': '古い試合', 'publishedAt': 1700000000},
            {'title': '新しい試合', 'publishedAt': 1700000000 + 8 * 86400},  # 8日後
        ]
        # 1→2 はスパイクにならないが time_gap は立つ
        r = self.detect(articles, prev_article_count=0, genre='スポーツ')
        self.assertIn('time_gap', r['reasons'])

    def test_time_gap_30days_sets_split_candidate(self):
        """T2026-0502-N: 30日超の time_gap は split_candidate=True"""
        articles = [
            {'title': 'A', 'publishedAt': 1700000000},
            {'title': 'B', 'publishedAt': 1700000000 + 31 * 86400},  # 31日後
        ]
        r = self.detect(articles)
        self.assertTrue(r['suspectedMismerge'])
        self.assertIn('time_gap', r['reasons'])
        self.assertTrue(r.get('split_candidate'), 'split_candidate が True でない')
        self.assertTrue(r.get('detail', {}).get('requiresReview'), 'requiresReview が True でない')

    def test_time_gap_29days_not_split_candidate(self):
        """T2026-0502-N: 29日の time_gap は suspectedMismerge だが split_candidate にならない"""
        articles = [
            {'title': 'A', 'publishedAt': 1700000000},
            {'title': 'B', 'publishedAt': 1700000000 + 29 * 86400},  # 29日後
        ]
        r = self.detect(articles)
        self.assertTrue(r['suspectedMismerge'])
        self.assertFalse(r.get('split_candidate', False))

    def test_no_signals_split_candidate_false(self):
        """T2026-0502-N: シグナルなしは split_candidate=False"""
        articles = [{'title': 'A', 'publishedAt': 1700000000}]
        r = self.detect(articles)
        self.assertFalse(r.get('split_candidate', False))


class HandlerStaticGuardTest(unittest.TestCase):
    """fetcher/handler.py に entity gate / Haiku borderline ロジックが残存することを静的検査。"""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(LAMBDA, 'handler.py'), 'r', encoding='utf-8') as f:
            cls.source = f.read()

    def test_entity_gate_constants_present(self):
        self.assertIn('_JACCARD_BORDERLINE_LOW', self.source,
                      'borderline (Jaccard 0.15-0.35) 判定の定数が消えている。')
        self.assertIn('_TID_COLLISION_LOOKBACK_DAYS', self.source,
                      'lookback 日数定数が消えている。')

    def test_extract_merge_entities_imported(self):
        self.assertIn('extract_merge_entities', self.source,
                      'merge gate 用の extract_merge_entities が import されていない。')

    def test_aimergejudge_imported(self):
        self.assertIn('from ai_merge_judge import AIMergeJudge', self.source,
                      'AIMergeJudge の import が消えている。')

    def test_merge_auditor_imported(self):
        self.assertIn('from merge_audit import MergeAuditor', self.source,
                      'MergeAuditor の import が消えている。')

    def test_resolve_collisions_signature_extended(self):
        # 新シグネチャ: ai_judge / auditor の名前付き引数
        self.assertIn('def _resolve_tid_collisions_by_title(group_tids, existing_topics, ai_judge=None, auditor=None)',
                      self.source.replace('\n', ' '),
                      '_resolve_tid_collisions_by_title のシグネチャが ai_judge/auditor を受け取らない。')


if __name__ == '__main__':
    unittest.main()
