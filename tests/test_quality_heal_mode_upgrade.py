#!/usr/bin/env python3
"""tests/test_quality_heal_mode_upgrade.py — T2026-0502-MU-FOLLOWUP

scripts/quality_heal.py の find_mode_mismatch_topics 境界値テスト。
handler.py:_expected_mode / _is_mode_upgrade と論理が一致していることも検証する。
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.quality_heal import (  # noqa: E402
    _expected_mode,
    _is_mode_upgrade,
    find_mode_mismatch_topics,
)


def _make_meta(
    tid: str,
    ac: int,
    summary_mode: str | None,
    ai_generated: bool = True,
    pending_ai=None,
    lifecycle: str = '',
) -> dict:
    m: dict = {
        'topicId': tid,
        'SK': 'META',
        'articleCount': ac,
        'aiGenerated': ai_generated,
        'title': f'test-{tid}',
        'score': 50,
    }
    if summary_mode is not None:
        m['summaryMode'] = summary_mode
    if pending_ai is not None:
        m['pendingAI'] = pending_ai
    if lifecycle:
        m['lifecycleStatus'] = lifecycle
    return m


class TestExpectedMode:
    def test_cnt_0(self):
        assert _expected_mode(0) == 'minimal'

    def test_cnt_2_boundary(self):
        assert _expected_mode(2) == 'minimal'

    def test_cnt_3(self):
        assert _expected_mode(3) == 'standard'

    def test_cnt_5_boundary(self):
        assert _expected_mode(5) == 'standard'

    def test_cnt_6(self):
        assert _expected_mode(6) == 'full'

    def test_cnt_14(self):
        assert _expected_mode(14) == 'full'


class TestIsModeUpgrade:
    def test_minimal_to_standard(self):
        assert _is_mode_upgrade('minimal', 'standard') is True

    def test_minimal_to_full(self):
        assert _is_mode_upgrade('minimal', 'full') is True

    def test_standard_to_full(self):
        assert _is_mode_upgrade('standard', 'full') is True

    def test_full_to_standard_downgrade(self):
        assert _is_mode_upgrade('full', 'standard') is False

    def test_same_mode(self):
        assert _is_mode_upgrade('full', 'full') is False

    def test_unknown_current(self):
        assert _is_mode_upgrade('unknown', 'full') is False


class TestFindModeMismatchTopics:
    def test_cnt6_standard_detected(self):
        """cnt=6 (→full 期待) で summaryMode=standard → 検出される。"""
        metas = [_make_meta('topic-A', ac=6, summary_mode='standard')]
        result = find_mode_mismatch_topics(metas)
        assert len(result) == 1
        assert result[0]['topicId'] == 'topic-A'
        assert 'mode-upgrade:standard→full' in result[0]['reasons'][0]

    def test_cnt4_standard_not_detected(self):
        """cnt=4 (→standard 期待) で summaryMode=standard → 検出されない (mode 正しい)。"""
        metas = [_make_meta('topic-B', ac=4, summary_mode='standard')]
        result = find_mode_mismatch_topics(metas)
        assert result == []

    def test_cnt14_full_not_detected(self):
        """cnt=14 (→full 期待) で summaryMode=full → 検出されない (mode 正しい)。"""
        metas = [_make_meta('topic-C', ac=14, summary_mode='full')]
        result = find_mode_mismatch_topics(metas)
        assert result == []

    def test_cnt10_minimal_detected(self):
        """cnt=10 (→full 期待) で summaryMode=minimal → 検出される。"""
        metas = [_make_meta('topic-D', ac=10, summary_mode='minimal')]
        result = find_mode_mismatch_topics(metas)
        assert len(result) == 1
        assert result[0]['topicId'] == 'topic-D'
        assert 'mode-upgrade:minimal→full' in result[0]['reasons'][0]

    def test_ai_generated_false_not_detected(self):
        """aiGenerated=False → 検出されない (Tier-0 で別途処理)。"""
        metas = [_make_meta('topic-E', ac=6, summary_mode='standard', ai_generated=False)]
        result = find_mode_mismatch_topics(metas)
        assert result == []

    def test_pending_ai_true_not_detected(self):
        """pendingAI=True 既存 → 検出されない (二重キューイング防止)。"""
        metas = [_make_meta('topic-F', ac=6, summary_mode='standard', pending_ai=True)]
        result = find_mode_mismatch_topics(metas)
        assert result == []

    def test_cnt2_minimal_not_detected_boundary(self):
        """articleCount=2 で summaryMode=minimal → 検出されない (minimal 期待、境界)。"""
        metas = [_make_meta('topic-G', ac=2, summary_mode='minimal')]
        result = find_mode_mismatch_topics(metas)
        assert result == []

    def test_no_summary_mode_skipped(self):
        """summaryMode 未設定 → スキップ (別の heal ルートで対処)。"""
        metas = [_make_meta('topic-H', ac=6, summary_mode=None)]
        result = find_mode_mismatch_topics(metas)
        assert result == []

    def test_downgrade_direction_not_detected(self):
        """cnt=3 (→standard 期待) で summaryMode=full → upgrade でないので検出されない。"""
        metas = [_make_meta('topic-I', ac=3, summary_mode='full')]
        result = find_mode_mismatch_topics(metas)
        assert result == []

    def test_archived_lifecycle_skipped(self):
        """lifecycleStatus=archived → スキップ。"""
        metas = [_make_meta('topic-J', ac=6, summary_mode='standard', lifecycle='archived')]
        result = find_mode_mismatch_topics(metas)
        assert result == []

    def test_sorted_by_ac_desc(self):
        """複数件 → articleCount 降順でソートされる。"""
        metas = [
            _make_meta('topic-low', ac=6, summary_mode='standard'),
            _make_meta('topic-high', ac=10, summary_mode='minimal'),
        ]
        result = find_mode_mismatch_topics(metas)
        assert len(result) == 2
        assert result[0]['topicId'] == 'topic-high'
        assert result[1]['topicId'] == 'topic-low'

    def test_pending_ai_false_is_eligible(self):
        """pendingAI=False (明示的 False) → キューイング対象。"""
        metas = [_make_meta('topic-K', ac=6, summary_mode='standard', pending_ai=False)]
        result = find_mode_mismatch_topics(metas)
        assert len(result) == 1
