"""T2026-0502-BA: pendingAI idempotent ガードのテスト

背景:
  processor は `pendingAI=True` フラグで管理しているが、quality_heal の rescue や
  fetcher_trigger 経由で「既に keyPoint>=100 + perspectives + outlook + storyPhase 等が
  揃っている」トピックも再生成キューに乗ってしまう経路がある。
  これは (a) Anthropic API 課金の無駄打ち (b) 上書き品質悪化リスク の二重害。

対策:
  - `_is_fully_filled(item)` を proc_storage に新設 — needs_ai_processing が True を
    返す全条件の **逆** に当たる「完全充填済」状態を判定。
  - `needs_ai_processing(item, force=False)` に force パラメータ追加。force=False かつ
    fully_filled なら True を返さない (idempotent skip)。
  - `forceRegenerateAll` パスでは force=True で bypass (全件強制再生成パス温存)。

副作用:
  - pendingAI=True に対する自動 re-summary は走らなくなる。
  - 朝刊・夕刊モデル (docs/product-direction.md) の「最大 12h 古い」UX 前提なので許容。

実行:
  cd projects/P003-news-timeline
  python3 -m unittest tests.test_idempotent_guard -v
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'lambda', 'processor'))

os.environ.setdefault('S3_BUCKET', 'test-bucket')
os.environ.setdefault('AWS_REGION', 'ap-northeast-1')

import proc_storage  # noqa: E402

needs_ai = proc_storage.needs_ai_processing
is_fully_filled = proc_storage._is_fully_filled
SCHEMA_VER = proc_storage.PROCESSOR_SCHEMA_VERSION


def _fully_filled_topic(**override):
    """全品質バー達成済の baseline item を作る。idempotent ガードのテスト用。"""
    base = {
        'topicId': 't-full',
        'title': 'OpenAIがGPT-5を発表',
        'articleCount': 5,
        'aiGenerated': True,
        'pendingAI': False,
        'schemaVersion': SCHEMA_VER,
        'summaryMode': 'standard',
        'storyTimeline': [{'date': '2026-04-28', 'event': '何かが起きた'}],
        'storyPhase': '拡散',
        'imageUrl': 'https://example.com/og.jpg',
        'generatedTitle': 'OpenAIがGPT-5を発表し業界全体が一斉に動いた',
        'generatedSummary': 'OpenAI が GPT-5 を発表し、Google・Meta が即日反応した。'
                            '同モデルは推論性能で従来の 2 倍を計測しており、'
                            '主要ベンダーの戦略再編を促している。',
        'keyPoint': 'GPT-5 はマルチモーダル推論で 2 倍の性能を示し、'
                    'OpenAI のロックイン戦略が新フェーズに入った。'
                    'Google・Meta は同日中に対抗発表を行い、業界の主導権争いが激化。'
                    'エンタープライズ採用は 30 日以内のベンチマーク結果次第になる。',
        'statusLabel': '主要ベンダーが対抗発表',
        'watchPoints': '推論ベンチマークの第三者検証 / 価格改定タイミング',
    }
    base.update(override)
    return base


class IsFullyFilledTest(unittest.TestCase):
    """`_is_fully_filled` の境界条件を網羅"""

    def test_baseline_fully_filled(self):
        """全フィールド充足 → True"""
        item = _fully_filled_topic()
        self.assertTrue(is_fully_filled(item))

    def test_aiGenerated_false_not_fully_filled(self):
        item = _fully_filled_topic(aiGenerated=False)
        self.assertFalse(is_fully_filled(item))

    def test_schemaVersion_low_not_fully_filled(self):
        """旧スキーマは再生成対象 = NOT fully filled"""
        item = _fully_filled_topic(schemaVersion=max(SCHEMA_VER - 1, 0))
        self.assertFalse(is_fully_filled(item))

    def test_keypoint_short_not_fully_filled(self):
        """keyPoint < 100 字は不十分扱い"""
        item = _fully_filled_topic(keyPoint='短すぎるキーポイント')
        self.assertFalse(is_fully_filled(item))

    def test_keypoint_empty_not_fully_filled(self):
        item = _fully_filled_topic(keyPoint='')
        self.assertFalse(is_fully_filled(item))

    def test_storyPhase_missing_not_fully_filled(self):
        """standard mode で storyPhase 欠落 → not fully filled"""
        item = _fully_filled_topic(storyPhase=None)
        self.assertFalse(is_fully_filled(item))

    def test_storyPhase_hatsutan_with_3_articles_not_fully_filled(self):
        """T2026-0428-AH ガード: 発端 & ac>=3 は再処理対象"""
        item = _fully_filled_topic(storyPhase='発端', articleCount=3)
        self.assertFalse(is_fully_filled(item))

    def test_storyPhase_hatsutan_with_2_articles_minimal_mode(self):
        """ac<=2 の minimal mode では storyPhase '発端' でもフルチェック対象外。
        ただし statusLabel/watchPoints は ac>=3 でしか必須化されないので、
        minimal の他要件 (keyPoint 等) を満たせば fully_filled になる。"""
        item = _fully_filled_topic(
            storyPhase='発端',
            articleCount=2,
            summaryMode='minimal',
            storyTimeline=[],  # minimal は timeline 不要
        )
        # 発端 & ac>=3 の AH ガードは ac=2 では発動しない
        # 他は全て満たすので True
        self.assertTrue(is_fully_filled(item))

    def test_imageUrl_missing_not_fully_filled(self):
        item = _fully_filled_topic(imageUrl=None)
        self.assertFalse(is_fully_filled(item))

    def test_low_quality_title_not_fully_filled(self):
        """曖昧タイトル (低品質) は再生成対象"""
        item = _fully_filled_topic(generatedTitle='OpenAIをめぐる最新の動き')
        self.assertFalse(is_fully_filled(item))

    def test_statusLabel_missing_with_3_articles_not_fully_filled(self):
        item = _fully_filled_topic(statusLabel='', articleCount=3)
        self.assertFalse(is_fully_filled(item))

    def test_watchPoints_missing_with_3_articles_not_fully_filled(self):
        item = _fully_filled_topic(watchPoints='', articleCount=3)
        self.assertFalse(is_fully_filled(item))

    def test_statusLabel_missing_with_2_articles_not_required(self):
        """ac<3 では statusLabel は必須でない (minimal mode)"""
        item = _fully_filled_topic(
            articleCount=2,
            summaryMode='minimal',
            statusLabel='',
            watchPoints='',
            storyTimeline=[],
        )
        self.assertTrue(is_fully_filled(item))

    def test_pendingAI_does_not_affect_fully_filled(self):
        """pendingAI=True でも fully filled の判定には影響しない (純粋な品質判定)"""
        item = _fully_filled_topic(pendingAI=True)
        self.assertTrue(is_fully_filled(item))


class NeedsAiProcessingForceTest(unittest.TestCase):
    """`needs_ai_processing` の force パラメータ動作確認"""

    def test_fully_filled_skipped_default(self):
        """force=False (default): fully filled トピックは skip"""
        item = _fully_filled_topic()
        self.assertFalse(needs_ai(item))
        self.assertFalse(needs_ai(item, force=False))

    def test_fully_filled_with_pendingAI_skipped(self):
        """force=False で pendingAI=True でも fully filled なら skip (idempotent ガードの本丸)"""
        item = _fully_filled_topic(pendingAI=True)
        self.assertFalse(needs_ai(item))

    def test_fully_filled_with_force_processed(self):
        """force=True: fully filled でも再生成対象 (forceRegenerateAll パス)"""
        item = _fully_filled_topic(pendingAI=True)
        self.assertTrue(needs_ai(item, force=True))

    def test_partial_topic_processed_regardless_of_force(self):
        """部分充填 (keyPoint 短い) は force に関わらず処理対象"""
        item = _fully_filled_topic(keyPoint='短い')
        self.assertTrue(needs_ai(item, force=False))
        self.assertTrue(needs_ai(item, force=True))

    def test_empty_topic_processed_regardless_of_force(self):
        """新規未生成トピックは force に関わらず処理対象"""
        item = _fully_filled_topic(
            aiGenerated=False,
            keyPoint=None,
            generatedTitle=None,
            generatedSummary=None,
            storyTimeline=[],
            storyPhase=None,
            imageUrl=None,
            statusLabel=None,
            watchPoints=None,
        )
        self.assertTrue(needs_ai(item, force=False))
        self.assertTrue(needs_ai(item, force=True))

    def test_low_article_count_skipped_regardless_of_force(self):
        """articleCount < 2 は force に関わらず skip (フロント非表示・既存挙動)"""
        item = _fully_filled_topic(articleCount=1)
        self.assertFalse(needs_ai(item, force=False))
        self.assertFalse(needs_ai(item, force=True))

    def test_existing_AH_guard_still_works(self):
        """既存の T2026-0428-AH ガード (storyPhase='発端' & ac>=3) は force に関わらず作動"""
        item = _fully_filled_topic(storyPhase='発端', articleCount=3)
        self.assertTrue(needs_ai(item, force=False))
        self.assertTrue(needs_ai(item, force=True))


class IdempotentGuardRegressionTest(unittest.TestCase):
    """既存テスト (test_needs_ai_processing.py) の挙動が壊れていないか確認"""

    def test_baseline_does_not_need_processing(self):
        """既存 _good_topic 互換: 全フィールド充足 → 再処理不要"""
        item = _fully_filled_topic()
        self.assertFalse(needs_ai(item))

    def test_phase_kakusan_not_reprocessed(self):
        """storyPhase='拡散' は AH ガード対象外で fully filled = skip"""
        item = _fully_filled_topic(storyPhase='拡散', articleCount=10)
        self.assertFalse(needs_ai(item))


if __name__ == '__main__':
    unittest.main()
