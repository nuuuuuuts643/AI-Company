"""T2026-0428-AH regression test: needs_ai_processing で
storyPhase='発端' かつ articleCount>=3 の旧トピックが再生成対象に含まれることを保証する。

背景:
  T219 で「記事3件以上で発端禁止」をプロンプト強化したが、aiGenerated=True 旧 topic は
  needs_ai_processing で skip されるため誤判定の発端が永続化していた
  (本番 2026-04-28 05:13 JST: 発端 54/93 = 58%)。
  6f39b55c で skip 条件に AH ガードを追加。本テストは恒久回帰防止用。

実行:
  cd projects/P003-news-timeline
  python3 -m unittest tests.test_needs_ai_processing -v
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
SCHEMA_VER = proc_storage.PROCESSOR_SCHEMA_VERSION


def _good_topic(**override):
    """先行 skip 条件 (extractive / low_quality_title / keyPoint不足 / statusLabel欠落 等)
    を全部クリアした「再処理不要」の baseline item を作る。
    AH ガード単体の効果を見るためのテンプレート。"""
    base = {
        'topicId': 't-good',
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
        'perspectives': 'OpenAI側: 技術的優位性と差別化を主張。Google側: 既存サービスとの統合・コスト優位性を強調。両社で戦略の方向性が明確に分岐。',
    }
    base.update(override)
    return base


class NeedsAiProcessingAHTest(unittest.TestCase):
    def test_ah_baseline_does_not_need_processing(self):
        """全フィールド充足 + storyPhase=拡散 → 再処理不要 (False)"""
        item = _good_topic()
        self.assertFalse(needs_ai(item))

    def test_ah_phase_hatsutan_with_3_articles_triggers_reprocess(self):
        """storyPhase=='発端' かつ articleCount>=3 → 再処理対象 (True)"""
        item = _good_topic(storyPhase='発端', articleCount=3)
        self.assertTrue(needs_ai(item))

    def test_ah_phase_hatsutan_with_5_articles_triggers_reprocess(self):
        item = _good_topic(storyPhase='発端', articleCount=5)
        self.assertTrue(needs_ai(item))

    def test_ah_phase_hatsutan_with_2_articles_skipped_by_articlecount_guard(self):
        """articleCount<2 は最初の早期 return で False (フロント非表示扱い)"""
        item = _good_topic(storyPhase='発端', articleCount=1)
        self.assertFalse(needs_ai(item))

    def test_ah_phase_hatsutan_with_2_articles_minimal_mode(self):
        """articleCount=2 = minimal mode: storyPhase='発端' でも AH ガード対象外 (3件未満)"""
        item = _good_topic(
            storyPhase='発端',
            articleCount=2,
            summaryMode='minimal',
            statusLabel='',
            watchPoints='',
        )
        # AH ガードは articleCount>=3 のみ。2件なら他の False 経路を辿る
        self.assertFalse(needs_ai(item))

    def test_ah_phase_kakusan_not_reprocessed(self):
        """storyPhase='拡散' は AH ガードに引っかからない"""
        item = _good_topic(storyPhase='拡散', articleCount=10)
        self.assertFalse(needs_ai(item))

    def test_ah_phase_peak_not_reprocessed(self):
        item = _good_topic(storyPhase='ピーク', articleCount=10)
        self.assertFalse(needs_ai(item))

    def test_ah_phase_genzaichi_not_reprocessed(self):
        item = _good_topic(storyPhase='現在地', articleCount=10)
        self.assertFalse(needs_ai(item))


class PerspectivesCheckTest(unittest.TestCase):
    """perspectives が ac>=2 で必須であることを物理確認。"""

    def test_perspectives_missing_ac2_triggers_reprocess(self):
        """ac>=2 で perspectives 欠落 → 再処理対象 (True)"""
        item = _good_topic(perspectives='', articleCount=2, summaryMode='minimal',
                           statusLabel='', watchPoints='', storyTimeline=[])
        self.assertTrue(needs_ai(item))

    def test_perspectives_none_ac5_triggers_reprocess(self):
        """perspectives=None (ac=5) → 再処理対象"""
        item = _good_topic(perspectives=None)
        self.assertTrue(needs_ai(item))

    def test_perspectives_missing_ac5_triggers_reprocess(self):
        """perspectives='' (ac=5) → 再処理対象"""
        item = _good_topic(perspectives='')
        self.assertTrue(needs_ai(item))

    def test_perspectives_present_ac2_no_reprocess(self):
        """ac=2 で perspectives あり + 他全充足 → 再処理不要 (False)"""
        item = _good_topic(
            articleCount=2,
            summaryMode='minimal',
            storyTimeline=[],
            statusLabel='',
            watchPoints='',
        )
        self.assertFalse(needs_ai(item))

    def test_perspectives_missing_ac1_not_required(self):
        """ac=1 はフロント非表示・最初の早期 return で False (perspectives 不問)"""
        item = _good_topic(perspectives='', articleCount=1)
        self.assertFalse(needs_ai(item))


if __name__ == '__main__':
    unittest.main()
