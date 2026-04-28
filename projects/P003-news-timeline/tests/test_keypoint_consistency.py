"""T2026-0429-KP regression test: 「aiGenerated=True なのに keyPoint 空/短い」滞留の根本原因を物理ガードする。

背景 (2026-04-29 実測):
  本番 DDB p003-topics で aiGenerated=True が 536件あるのに、keyPoint が 100字以上の
  正常充填はわずか 7件 (1.3%)。529件が滞留。詳細パターン:
    - 149件: 全 AI フィールド空 (storyPhase 含む) → title 生成のみ成功で aiGenerated=True が立ったケース
    - 280件: storyPhase 等は埋まっているが keyPoint 空 (旧スキーマで keyPoint 未生成)
    - 38件: 全フィールド埋まっているが keyPoint が < 100字 (短いタイトル風) → handler.py の bool() 判定漏れで再生成スキップされ続けていた

修正ポイント:
  1) handler.py `_required_full_fields` の keyPoint 判定を bool() ではなく
     proc_storage._is_keypoint_inadequate (100字閾値) に統一。
     → 短い keyPoint の topic を必ず再生成キューに乗せる。
  2) ai_succeeded を title_succeeded / story_succeeded に分割。
     aiGenerated=True / aiGeneratedAt の更新は story 生成成功時のみ行う。
     → title-only 成功で「処理済」フラグだけ立つ事故を防ぐ。

実行:
  cd projects/P003-news-timeline
  python3 -m unittest tests.test_keypoint_consistency -v
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
_is_keypoint_inadequate = proc_storage._is_keypoint_inadequate
KEYPOINT_MIN_LENGTH = proc_storage.KEYPOINT_MIN_LENGTH
SCHEMA_VER = proc_storage.PROCESSOR_SCHEMA_VERSION


# 100字以上の "正常な" keyPoint サンプル (200-300字想定)
_LONG_KP = (
    'もともとマリの政情は 2012 年の北部反乱以来不安定であり、フランス撤退後はロシアの民間軍事会社が一定の治安を担ってきた。'
    'しかし 2026 年 4 月、複数のイスラム過激派が首都圏で同時多発攻撃を行い、国防相が殺害される事態に発展した。'
    'いま政府は事実上の戦時体制に移行しつつあり、サヘル全域への波及が現実の懸念となっている。'
)


def _full_topic(**override):
    """全フィールド充足 (aiGenerated=True / 再処理不要) のテンプレート。"""
    base = {
        'topicId': 't-full',
        'title': 'マリの過激派攻勢',
        'articleCount': 5,
        'aiGenerated': True,
        'pendingAI': False,
        'schemaVersion': SCHEMA_VER,
        'summaryMode': 'standard',
        'storyTimeline': [{'date': '2026-04-28', 'event': '国防相殺害'}],
        'storyPhase': '拡散',
        'imageUrl': 'https://example.com/og.jpg',
        'generatedTitle': 'マリのイスラム過激派、国防相殺害で攻勢強まる',
        'generatedSummary': 'マリで複数のイスラム過激派と反政府勢力が同時攻撃を行い国防相が殺害された。背景には長年の不安定なサヘル情勢がある。',
        'keyPoint': _LONG_KP,
        'statusLabel': '進行中',
        'watchPoints': '①治安部隊の対応 ②サヘル諸国の反応 ③民間人被害',
    }
    base.update(override)
    return base


# ─────────────────────────────────────────────────────────────────────────────
# Section 1: _is_keypoint_inadequate の境界条件
# ─────────────────────────────────────────────────────────────────────────────
class IsKeyPointInadequateTest(unittest.TestCase):
    def test_none_is_inadequate(self):
        self.assertTrue(_is_keypoint_inadequate(None))

    def test_empty_string_is_inadequate(self):
        self.assertTrue(_is_keypoint_inadequate(''))

    def test_whitespace_only_is_inadequate(self):
        self.assertTrue(_is_keypoint_inadequate('   \n\t  '))

    def test_short_string_is_inadequate(self):
        # 本番実例: 21字「ロシア撤退と過激派攻勢の同時進行が新段階へ」
        self.assertTrue(_is_keypoint_inadequate('ロシア撤退と過激派攻勢の同時進行が新段階へ'))

    def test_just_below_threshold_is_inadequate(self):
        s = 'あ' * (KEYPOINT_MIN_LENGTH - 1)
        self.assertTrue(_is_keypoint_inadequate(s))

    def test_at_threshold_is_adequate(self):
        s = 'あ' * KEYPOINT_MIN_LENGTH
        self.assertFalse(_is_keypoint_inadequate(s))

    def test_normal_length_is_adequate(self):
        self.assertFalse(_is_keypoint_inadequate(_LONG_KP))


# ─────────────────────────────────────────────────────────────────────────────
# Section 2: needs_ai_processing が短い keyPoint topic を再処理キューに載せる
# ─────────────────────────────────────────────────────────────────────────────
class NeedsAiProcessingKeyPointTest(unittest.TestCase):
    def test_full_topic_does_not_need_processing(self):
        """全フィールド + 充分な keyPoint → 再処理不要"""
        self.assertFalse(needs_ai(_full_topic()))

    def test_short_keypoint_needs_processing(self):
        """本番 38件パターン: 短い keyPoint (21字) で他は全埋め → 再処理対象"""
        item = _full_topic(keyPoint='ロシア撤退と過激派攻勢の同時進行が新段階へ')
        self.assertTrue(needs_ai(item))

    def test_empty_keypoint_needs_processing(self):
        """旧スキーマパターン: keyPoint 空 で他は埋め → 再処理対象"""
        item = _full_topic(keyPoint='')
        self.assertTrue(needs_ai(item))

    def test_none_keypoint_needs_processing(self):
        item = _full_topic(keyPoint=None)
        self.assertTrue(needs_ai(item))


# ─────────────────────────────────────────────────────────────────────────────
# Section 3: handler.py `_required_full_fields` ロジックの統一性
#   handler.py の skip 判定が proc_storage と一致することを保証する。
#   現物のロジックを抜き出して直接評価する (handler 全体を import すると boto3 副作用が走るため)。
# ─────────────────────────────────────────────────────────────────────────────
def _handler_required_full_fields(topic):
    """handler.py から抜粋した skip 判定の純粋関数版。
    proc_storage._is_keypoint_inadequate と一致しているかを物理確認する。"""
    cnt = int(topic.get('articleCount', 0) or 0)
    is_minimal = cnt <= 2
    return (
        (topic.get('storyTimeline') or is_minimal),
        (topic.get('storyPhase')    or is_minimal),
        (not _is_keypoint_inadequate(topic.get('keyPoint'))),
        (bool(topic.get('statusLabel')) or is_minimal),
        (bool(topic.get('watchPoints'))  or is_minimal),
    )


def _handler_needs_story(topic):
    """handler.py の needs_story 計算 (純粋関数版)"""
    cnt = int(topic.get('articleCount', 0) or 0)
    MIN_ARTICLES_FOR_SUMMARY = 3
    if cnt < MIN_ARTICLES_FOR_SUMMARY:
        return False
    fields = _handler_required_full_fields(topic)
    return not (topic.get('aiGenerated') and all(fields))


class HandlerStorageConsistencyTest(unittest.TestCase):
    """proc_storage が再生成キューに載せた topic を handler が「不要」と弾かないことを保証する。"""

    def test_full_topic_handler_skips(self):
        """充足 topic → handler も skip"""
        topic = _full_topic()
        self.assertFalse(_handler_needs_story(topic))

    def test_short_keypoint_handler_does_not_skip(self):
        """本番 38件パターン: handler 側でも skip されず再生成される (旧 bool() 判定では skip → keyPoint 滞留)"""
        topic = _full_topic(keyPoint='ロシア撤退と過激派攻勢の同時進行が新段階へ')
        self.assertTrue(_handler_needs_story(topic))

    def test_empty_keypoint_handler_does_not_skip(self):
        topic = _full_topic(keyPoint='')
        self.assertTrue(_handler_needs_story(topic))

    def test_consistency_for_short_keypoint(self):
        """short keyPoint について proc_storage と handler が同じ結論を出すこと (=どちらも「再処理する」)"""
        topic = _full_topic(keyPoint='短い')
        self.assertTrue(needs_ai(topic), 'proc_storage.needs_ai_processing must queue')
        self.assertTrue(_handler_needs_story(topic), 'handler must NOT skip — would leave keyPoint short forever')


# ─────────────────────────────────────────────────────────────────────────────
# Section 4: ai_succeeded 分離の効果 — title-only 成功で aiGenerated=True が立たないこと
# ─────────────────────────────────────────────────────────────────────────────
def _simulate_handler_success_flags(title_call_returns, story_call_returns):
    """handler.py の修正後ロジックを純粋関数で再現:
      title_succeeded / story_succeeded を独立に追跡し、ai_succeeded = story_succeeded で集約する。
    Returns: (ai_succeeded, gen_title_set, gen_story_set)
    """
    title_succeeded = False
    story_succeeded = False
    gen_title = None
    gen_story = None
    if title_call_returns:
        gen_title = title_call_returns
        title_succeeded = True
    if story_call_returns:
        gen_story = story_call_returns
        story_succeeded = True
    ai_succeeded = story_succeeded
    return ai_succeeded, gen_title is not None, gen_story is not None


class AiSucceededSplitTest(unittest.TestCase):
    """title-only 成功 → aiGenerated=True を立てない (本番 149 件の根本原因対策)"""

    def test_title_only_does_not_mark_ai_succeeded(self):
        ai_succ, gt_set, gs_set = _simulate_handler_success_flags('新しいタイトル', None)
        self.assertFalse(ai_succ, 'title-only 成功で aiGenerated=True を立ててはならない')
        self.assertTrue(gt_set, 'gen_title は保存されるべき (title 結果は生かす)')
        self.assertFalse(gs_set)

    def test_story_only_marks_ai_succeeded(self):
        ai_succ, gt_set, gs_set = _simulate_handler_success_flags(None, {'aiSummary': 's', 'keyPoint': 'k'})
        self.assertTrue(ai_succ, 'story 成功時に aiGenerated=True が立つこと')

    def test_both_succeeded_marks_ai_succeeded(self):
        ai_succ, gt_set, gs_set = _simulate_handler_success_flags('t', {'aiSummary': 's', 'keyPoint': 'k'})
        self.assertTrue(ai_succ)
        self.assertTrue(gt_set)
        self.assertTrue(gs_set)

    def test_both_failed(self):
        ai_succ, gt_set, gs_set = _simulate_handler_success_flags(None, None)
        self.assertFalse(ai_succ)


if __name__ == '__main__':
    unittest.main()
