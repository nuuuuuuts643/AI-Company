#!/usr/bin/env python3
"""tests/test_quality_heal_mode_upgrade.py — T2026-0502-MU-FOLLOWUP-ARCHIVED

scripts/quality_heal.py の find_unhealthy() における
lifecycleStatus='archived' 救済ロジックの境界値テスト。

閾値: ac >= 6 AND score >= 100 の archived のみ救済 (high-value archived rescue)

実行:
  python3 -m pytest tests/test_quality_heal_mode_upgrade.py -v
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.quality_heal import find_unhealthy

PROCESSOR_SCHEMA_VERSION = 3


def _meta(topicId, ac, score, lifecycle='active', sv=None, keyPoint='x' * 150):
    """テスト用 META アイテムを生成。sv は指定なければ最新スキーマ。"""
    if sv is None:
        sv = PROCESSOR_SCHEMA_VERSION
    item = {
        'topicId': topicId,
        'articleCount': ac,
        'score': score,
        'lifecycleStatus': lifecycle,
        'schemaVersion': sv,
        'keyPoint': keyPoint,
        'statusLabel': 'test',
        'watchPoints': 'test',
        'storyTimeline': 'test',
        'storyPhase': 'test',
    }
    return item


class TestArchivedLifecycleRescue:
    """archived + high-value トピックの救済境界値テスト。"""

    def test_archived_ac6_score100_mode_mismatch_detected(self):
        """archived + ac=6 + score=100 + schema mismatch → 検出される (境界 inclusive)"""
        meta = _meta('tid-a', ac=6, score=100, lifecycle='archived', sv=0)
        result, _ = find_unhealthy([meta])
        assert any(r['topicId'] == 'tid-a' for r in result), \
            "archived+ac=6+score=100 は救済対象として検出されるべき"

    def test_archived_ac5_score200_not_detected(self):
        """archived + ac=5 + score=200 → ac 不足で検出されない"""
        meta = _meta('tid-b', ac=5, score=200, lifecycle='archived', sv=0)
        result, _ = find_unhealthy([meta])
        assert not any(r['topicId'] == 'tid-b' for r in result), \
            "archived+ac<6 は救済対象外"

    def test_archived_ac10_score99_not_detected(self):
        """archived + ac=10 + score=99 → score 不足で検出されない"""
        meta = _meta('tid-c', ac=10, score=99, lifecycle='archived', sv=0)
        result, _ = find_unhealthy([meta])
        assert not any(r['topicId'] == 'tid-c' for r in result), \
            "archived+score<100 は救済対象外"

    def test_legacy_ac10_score200_not_detected(self):
        """legacy + ac=10 + score=200 → legacy は touch しない"""
        meta = _meta('tid-d', ac=10, score=200, lifecycle='legacy', sv=0)
        result, _ = find_unhealthy([meta])
        assert not any(r['topicId'] == 'tid-d' for r in result), \
            "legacy は閾値に関わらず救済対象外"

    def test_deleted_ac10_score200_not_detected(self):
        """deleted + ac=10 + score=200 → deleted は touch しない"""
        meta = _meta('tid-e', ac=10, score=200, lifecycle='deleted', sv=0)
        result, _ = find_unhealthy([meta])
        assert not any(r['topicId'] == 'tid-e' for r in result), \
            "deleted は閾値に関わらず救済対象外"


class TestActiveLifecycleUnaffected:
    """active トピックの既存挙動が変わっていないことを確認。"""

    def test_active_schema_mismatch_detected(self):
        """active + schema mismatch → 検出される (既存テスト互換)"""
        meta = _meta('tid-f', ac=6, score=100, lifecycle='active', sv=0)
        result, _ = find_unhealthy([meta])
        assert any(r['topicId'] == 'tid-f' for r in result)

    def test_active_healthy_not_detected(self):
        """active + healthy (最新スキーマ + 十分な keyPoint) → 検出されない"""
        meta = _meta('tid-g', ac=6, score=100, lifecycle='active')
        result, _ = find_unhealthy([meta])
        assert not any(r['topicId'] == 'tid-g' for r in result)

    def test_empty_lifecycle_treated_as_active(self):
        """lifecycleStatus 未設定 (空文字) → active 扱いで通常チェックが走る"""
        meta = _meta('tid-h', ac=6, score=100, lifecycle='', sv=0)
        result, _ = find_unhealthy([meta])
        assert any(r['topicId'] == 'tid-h' for r in result)

    def test_cooling_lifecycle_schema_mismatch_detected(self):
        """cooling (= active 系) + schema mismatch → 検出される"""
        meta = _meta('tid-i', ac=6, score=100, lifecycle='cooling', sv=0)
        result, _ = find_unhealthy([meta])
        assert any(r['topicId'] == 'tid-i' for r in result)


class TestArchiveBoundaryInclusive:
    """archived 救済の境界が inclusive (>=6, >=100) であることの追加確認。"""

    def test_archived_ac7_score150_detected(self):
        """archived + ac=7 + score=150 → 閾値超過、検出される"""
        meta = _meta('tid-j', ac=7, score=150, lifecycle='archived', sv=0)
        result, _ = find_unhealthy([meta])
        assert any(r['topicId'] == 'tid-j' for r in result)

    def test_archived_ac6_score99_not_detected(self):
        """archived + ac=6 + score=99 → score 境界値 1 未満"""
        meta = _meta('tid-k', ac=6, score=99, lifecycle='archived', sv=0)
        result, _ = find_unhealthy([meta])
        assert not any(r['topicId'] == 'tid-k' for r in result)

    def test_archived_ac5_score100_not_detected(self):
        """archived + ac=5 + score=100 → ac 境界値 1 未満"""
        meta = _meta('tid-l', ac=5, score=100, lifecycle='archived', sv=0)
        result, _ = find_unhealthy([meta])
        assert not any(r['topicId'] == 'tid-l' for r in result)
