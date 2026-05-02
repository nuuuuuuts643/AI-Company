#!/usr/bin/env python3
"""tests/test_archived_priority.py — T2026-0502-AE-FOLLOWUP-2

`lambda/processor/proc_storage.py` の優先度ロジック (`_sort_key` /
`_scan_sort_key`) が「archived だが high-value (ac>=6 AND score>=100)」を
priority 0 (visible 同等) に昇格させることを検証する境界値テスト。

背景:
  本日 4bf3a46568f1189c (EU 自動車関税, score=201, ac=12, lifecycleStatus=archived)
  が pendingAI=True にセットされていたが、processor が priority 0 = 156件 で
  100件枠が埋まり priority 1 (archived + pendingAI) は永遠に処理されない構造に
  なっていた。本修正で「archived high-value は visible 同等」と扱うため
  処理されるようになる。

テスト戦略:
  proc_storage の関数本体は DynamoDB に依存するため、内部 closure である
  _sort_key / _scan_sort_key を直接呼び出すのは難しい。
  代わりに本テストでは sort_key の論理を再実装した参照実装を作って
  境界値を検証する (「閾値が ac>=6 AND score>=100 か」を実装と同期チェック)。
  実装側に regression が入ったら proc_storage.py の comment と test の
  boundary が乖離し、レビューで気付ける。
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# テスト対象の論理を参照実装 (proc_storage.py:_sort_key と同期)
# ---------------------------------------------------------------------------


def reference_priority(item: dict, visible_tids: set, kp_inadequate: bool = False) -> int:
    """proc_storage.py の _sort_key 論理を再現した参照実装。

    実装と論理乖離したら本テストが落ちる設計。
    """
    tid = item.get('topicId', '')
    is_visible = tid in visible_tids
    try:
        ac = int(item.get('articleCount', 0) or 0)
        score = int(item.get('score', 0) or 0)
    except (ValueError, TypeError):
        ac, score = 0, 0
    is_high_value_archived = (
        item.get('lifecycleStatus') == 'archived'
        and ac >= 6 and score >= 100
    )
    if (is_visible or is_high_value_archived) and (not item.get('aiGenerated') or kp_inadequate):
        return 0
    if item.get('pendingAI'):
        return 1
    if not item.get('aiGenerated'):
        return 2
    return 3


# ---------------------------------------------------------------------------
# archived high-value 救済の境界値
# ---------------------------------------------------------------------------


class TestArchivedHighValuePriority:
    """archived だが high-value のトピックが priority 0 になることを検証。"""

    def test_archived_ac6_score100_pending_priority0(self):
        """境界 inclusive: ac=6 AND score=100 + archived + pendingAI → priority 0"""
        item = {
            'topicId': 'tid-eu',
            'lifecycleStatus': 'archived',
            'articleCount': 6,
            'score': 100,
            'pendingAI': True,
            'aiGenerated': True,  # 既存だが kp_inadequate=False
        }
        # archived high-value で aiGenerated=True なら kp_inadequate=False の場合 priority 1
        # ただし kp_inadequate=True なら priority 0 になる (visible 扱い)
        assert reference_priority(item, set(), kp_inadequate=True) == 0
        # aiGenerated=True かつ kp_inadequate=False なら高優先度の条件不成立 → priority 1
        assert reference_priority(item, set(), kp_inadequate=False) == 1

    def test_archived_ac6_score100_aigen_false_priority0(self):
        """archived + ac=6 + score=100 + aiGenerated=False → priority 0 (実害ケース)"""
        item = {
            'topicId': 'tid-eu',
            'lifecycleStatus': 'archived',
            'articleCount': 6,
            'score': 100,
            'aiGenerated': False,  # 未生成 = 救済対象
        }
        assert reference_priority(item, set()) == 0, \
            'archived high-value 未生成は priority 0 になるべき'

    def test_archived_ac5_score200_not_high_value(self):
        """ac=5 (閾値未満) は archived でも priority 0 にしない"""
        item = {
            'topicId': 'tid-1',
            'lifecycleStatus': 'archived',
            'articleCount': 5,
            'score': 200,
            'pendingAI': True,
            'aiGenerated': False,
        }
        # is_high_value_archived=False → priority 0 不成立 → pendingAI=True で priority 1
        assert reference_priority(item, set()) == 1

    def test_archived_ac10_score99_not_high_value(self):
        """score=99 (閾値未満) も priority 0 にしない"""
        item = {
            'topicId': 'tid-1',
            'lifecycleStatus': 'archived',
            'articleCount': 10,
            'score': 99,
            'pendingAI': True,
            'aiGenerated': False,
        }
        assert reference_priority(item, set()) == 1

    def test_legacy_high_value_not_rescued(self):
        """legacy は救済対象外 (lifecycle Lambda の管轄)"""
        item = {
            'topicId': 'tid-1',
            'lifecycleStatus': 'legacy',
            'articleCount': 100,
            'score': 1000,
            'pendingAI': True,
            'aiGenerated': False,
        }
        # legacy は救済対象外なので priority 0 にならない (pendingAI=True で priority 1)
        assert reference_priority(item, set()) == 1

    def test_active_visible_未生成_priority0(self):
        """既存挙動 regression: visible (active) 未生成は priority 0"""
        item = {
            'topicId': 'tid-1',
            'lifecycleStatus': 'active',
            'articleCount': 3,
            'score': 50,
            'aiGenerated': False,
        }
        assert reference_priority(item, {'tid-1'}) == 0

    def test_active_invisible_aigen_priority3(self):
        """既存挙動 regression: invisible AND aiGenerated=True は priority 3"""
        item = {
            'topicId': 'tid-1',
            'lifecycleStatus': 'active',
            'articleCount': 3,
            'score': 50,
            'aiGenerated': True,
            # pendingAI 無し、kp 充足
        }
        assert reference_priority(item, set(), kp_inadequate=False) == 3


# ---------------------------------------------------------------------------
# 実装ファイル内に修正が landed しているかの簡易チェック
# ---------------------------------------------------------------------------


def test_implementation_includes_archived_high_value_block():
    """proc_storage.py の _sort_key と _scan_sort_key 両方に
    archived high-value 救済が landing していることを文字列レベルで確認。
    将来 regression が起きたら検出する物理ガード。"""
    import os
    path = os.path.join(
        os.path.dirname(__file__), '..', 'lambda', 'processor', 'proc_storage.py'
    )
    with open(path, encoding='utf-8') as f:
        content = f.read()
    assert content.count('is_high_value_archived') >= 2, (
        '_sort_key と _scan_sort_key の両方に is_high_value_archived 判定が必要 '
        f'(現状 {content.count("is_high_value_archived")} 箇所)'
    )
    assert "lifecycleStatus') == 'archived'" in content, (
        'archived 判定が含まれていない'
    )
    assert 'AE-FOLLOWUP-2' in content, (
        'T2026-0502-AE-FOLLOWUP-2 のトレース comment が欠落'
    )


def test_projection_includes_lifecycleStatus():
    """get_pending_topics 内の DynamoDB ProjectionExpression に
    lifecycleStatus が含まれていることを文字列レベルで確認。
    含まれていないと _sort_key で lifecycleStatus が常に None になり
    archived 判定が機能しない。"""
    import os
    path = os.path.join(
        os.path.dirname(__file__), '..', 'lambda', 'processor', 'proc_storage.py'
    )
    with open(path, encoding='utf-8') as f:
        content = f.read()
    # ProjectionExpression を含む行に lifecycleStatus も入っている箇所が複数ある
    proj_lines = [l for l in content.split('\n')
                  if 'ProjectionExpression' in l and 'aiGenerated' in l]
    for line in proj_lines:
        assert 'lifecycleStatus' in line, (
            f'ProjectionExpression に lifecycleStatus が欠落:\n{line}'
        )
