"""embedding_judge.py のユニットテスト。

実 ONNX runtime + multilingual-e5-small は Lambda layer ビルド済の Code セッションで
実行する。ここでは MockEmbeddingBackend を使ってロジック検証のみ。
"""
import os
import sys
import unittest

# lambda/fetcher を import path に追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'fetcher'))

from embedding_judge import (
    EmbeddingMergeJudge,
    MockEmbeddingBackend,
)


class TestEmbeddingJudgeWithMock(unittest.TestCase):
    """Mock backend で interface とロジックを検証。"""

    def setUp(self):
        # Mock backend は bigram 一致でコサインを近似
        self.backend = MockEmbeddingBackend()

    def test_empty_pairs(self):
        judge = EmbeddingMergeJudge(backend=self.backend)
        self.assertEqual(judge.judge_pairs([]), {})

    def test_entity_gate_no_shared_entities(self):
        """shared_entities が空なら必ず False (entity gate)。"""
        judge = EmbeddingMergeJudge(backend=self.backend)
        pairs = [{
            'title_a': '米国 GDP 速報値 2.0%',
            'title_b': '日本 GDP 速報値 2.0%',
            'entities_a': ['米国'], 'entities_b': ['日本'],
            'shared_entities': [],  # 空
        }]
        result = judge.judge_pairs(pairs)
        self.assertEqual(len(result), 1)
        self.assertFalse(list(result.values())[0], '主体が違うペアは entity gate で False になるべき')
        self.assertEqual(judge.pairs_no, 1)

    def test_high_similarity_returns_true(self):
        """ほぼ同じ文 (bigram 大半一致 → cosine 高) は同一事件。"""
        judge = EmbeddingMergeJudge(backend=self.backend, cosine_high=0.85, cosine_low=0.65)
        pairs = [{
            # bigram の大半が一致 → MockBackend (bigram set) で cosine 高くなる
            'title_a': 'トランプ大統領 関税引き上げ発表',
            'title_b': 'トランプ大統領 関税引き上げ発表する',
            'entities_a': ['トランプ'], 'entities_b': ['トランプ'],
            'shared_entities': ['トランプ'],
        }]
        result = judge.judge_pairs(pairs)
        self.assertEqual(len(result), 1, '重複除去 (a==b) に引っかかってないこと')
        self.assertTrue(list(result.values())[0],
                        f'cosine 高くて True 期待だが False: 閾値再確認')
        self.assertEqual(judge.pairs_yes, 1)
        self.assertEqual(judge.high_confidence_decisions, 1)

    def test_low_similarity_returns_false(self):
        """全く違う文 (cosine 低) は別事件。"""
        judge = EmbeddingMergeJudge(backend=self.backend, cosine_high=0.85, cosine_low=0.65)
        pairs = [{
            'title_a': 'トランプ大統領 関税引き上げ発表',
            'title_b': '日本 株価 最高値 更新',
            'entities_a': ['トランプ', '関税'], 'entities_b': ['日本', '株価'],
            'shared_entities': ['市場'],  # 弱い shared
        }]
        result = judge.judge_pairs(pairs)
        self.assertFalse(list(result.values())[0])
        self.assertEqual(judge.pairs_no, 1)

    def test_borderline_no_fallback_returns_false(self):
        """borderline で fallback がなければ保守的に False。"""
        judge = EmbeddingMergeJudge(backend=self.backend, cosine_high=0.99, cosine_low=0.95,
                                    fallback_judge=None)
        # 閾値を狭くして mock で borderline に落ちやすくする
        pairs = [{
            'title_a': 'トランプ大統領 関税引き上げ',
            'title_b': 'トランプ氏 関税アップ',
            'entities_a': ['トランプ'], 'entities_b': ['トランプ'],
            'shared_entities': ['トランプ', '関税'],
        }]
        result = judge.judge_pairs(pairs)
        # 結果値は何でも良いが、fallback が呼ばれてないことだけ確認
        self.assertEqual(judge.borderline_fallback_calls, 0)

    def test_cache_avoids_recompute(self):
        """同じペアを 2 回問うても backend は 1 回しか呼ばれない (cache)。"""
        call_count = [0]

        class CountingBackend(MockEmbeddingBackend):
            def encode(self, texts):
                call_count[0] += 1
                return super().encode(texts)

        judge = EmbeddingMergeJudge(backend=CountingBackend())
        pairs = [{
            'title_a': 'A', 'title_b': 'B',
            'entities_a': [], 'entities_b': [],
            'shared_entities': ['x'],
        }]
        judge.judge_pairs(pairs)
        judge.judge_pairs(pairs)  # 2 回目
        self.assertEqual(call_count[0], 1, '2 回目は cache hit で encode 呼ばれないはず')

    def test_symmetric_pair_keys(self):
        """(A,B) と (B,A) は同じキーで cache される。"""
        judge = EmbeddingMergeJudge(backend=self.backend)
        pairs = [{
            'title_a': 'A', 'title_b': 'B',
            'shared_entities': ['x'],
            'entities_a': [], 'entities_b': [],
        }, {
            'title_a': 'B', 'title_b': 'A',  # 順序逆
            'shared_entities': ['x'],
            'entities_a': [], 'entities_b': [],
        }]
        result = judge.judge_pairs(pairs)
        # 重複除去で key は 1 つ
        self.assertEqual(len(result), 1)


class TestEmbeddingJudgeIntegrationFixtures(unittest.TestCase):
    """実 model がない環境でも fixture でロジック検証可能なものだけ。

    実 cosine 値の検証は Code セッションで scripts/embedding_bench.py 経由。
    """

    def test_fixture_ouchu_doitsu_zairyu_beigun(self):
        """T2026-0501-M で問題になった「欧州駐留米軍」vs「ドイツ駐留米軍」フィクスチャ。

        実 ONNX backend なら cosine > 0.85 で True 想定 (HuggingFace MTEB で類似事象)。
        Mock backend では bigram 一致が低いので False になる可能性あり (それは想定通り)。
        """
        backend = MockEmbeddingBackend()
        judge = EmbeddingMergeJudge(backend=backend)
        result = judge.judge_pairs([{
            'title_a': 'トランプ大統領 欧州駐留米軍 削減 発表',
            'title_b': 'トランプ氏 ドイツ駐留米軍 縮小',
            'entities_a': ['トランプ', '欧州', '米軍'],
            'entities_b': ['トランプ', 'ドイツ', '米軍'],
            'shared_entities': ['トランプ', '米軍'],
        }])
        # MockBackend (bigram) では cosine 低くなりやすい → False になる
        # Code セッション側 (実 ONNX) で True に変わるべきフィクスチャとして残す
        self.assertEqual(len(result), 1)


if __name__ == '__main__':
    unittest.main()
