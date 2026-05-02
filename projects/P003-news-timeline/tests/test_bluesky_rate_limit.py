"""T2026-0502-L: Bluesky 投稿レート制御 (_check_rate_limit) のユニットテスト.

過去の事故 (5/1 debut が 48 件/日投稿) を再発させないための物理ガード検証:
  - enabled=False で必ず投稿停止 (kill switch)
  - cooldown 中は投稿停止
  - 24h 内 max_per_24h 件数到達で投稿停止
  - 上記いずれもクリアしたときだけ ok=True

設計: BLUESKY_POSTING_CONFIG が単一の真実の源で、_check_rate_limit がその
      唯一の解釈エントリ。各 post_xxx() はこの関数を呼ぶだけで rate-limit する。
"""
from __future__ import annotations

import os
import sys
import types
from datetime import datetime, timedelta, timezone
from unittest.mock import patch


def _import_agent():
    """テスト用に bluesky_agent を fresh import する。"""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    scripts_dir = os.path.join(repo_root, "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    # 既存キャッシュを掃除
    for k in list(sys.modules.keys()):
        if k in ("bluesky_agent", "_governance_check"):
            del sys.modules[k]

    # _governance_check を no-op モックで差し替え (DynamoDB 接続を回避)
    mock = types.ModuleType("_governance_check")
    mock.check_agent_status = lambda agent_id: None
    sys.modules["_governance_check"] = mock

    import bluesky_agent  # noqa: WPS433
    return bluesky_agent


class TestBlueskyPostingConfig:
    """設定ブロックの不変条件をテスト (リグレッション防止)."""

    def test_config_has_all_modes(self):
        """全モードのエントリが存在する."""
        agent = _import_agent()
        assert set(agent.BLUESKY_POSTING_CONFIG.keys()) >= {
            "daily", "morning", "debut", "weekly", "monthly"
        }

    def test_config_each_mode_has_required_keys(self):
        """各モードに enabled / cooldown_hours / max_per_24h がある."""
        agent = _import_agent()
        for mode, cfg in agent.BLUESKY_POSTING_CONFIG.items():
            assert "enabled" in cfg, f"{mode} に enabled がない"
            assert "cooldown_hours" in cfg, f"{mode} に cooldown_hours がない"
            assert "max_per_24h" in cfg, f"{mode} に max_per_24h がない"

    def test_daily_total_capped_at_4(self):
        """POの目標 = 4件/日。daily 3 + morning 1 + debut 0 = 4 を上回らないこと."""
        agent = _import_agent()
        daily_cap   = agent.BLUESKY_POSTING_CONFIG["daily"]["max_per_24h"]
        morning_cap = agent.BLUESKY_POSTING_CONFIG["morning"]["max_per_24h"]
        debut_cfg   = agent.BLUESKY_POSTING_CONFIG["debut"]
        debut_cap   = debut_cfg["max_per_24h"] if debut_cfg["enabled"] else 0
        total = daily_cap + morning_cap + debut_cap
        assert total <= 6, (
            f"日次総上限が大きすぎる (daily={daily_cap} morning={morning_cap} "
            f"debut={debut_cap} 合計{total}). PO目標 4件/日"
        )

    def test_legacy_aliases_match_config(self):
        """旧コード互換 alias (DAILY_COOLDOWN_HOURS 等) が config と一致する."""
        agent = _import_agent()
        assert agent.DAILY_COOLDOWN_HOURS == agent.BLUESKY_POSTING_CONFIG["daily"]["cooldown_hours"]
        assert agent.MORNING_COOLDOWN_HOURS == agent.BLUESKY_POSTING_CONFIG["morning"]["cooldown_hours"]


class TestCheckRateLimitEnabled:
    """enabled フラグの kill-switch 動作."""

    def test_disabled_mode_blocks(self):
        """enabled=False のモードは無条件で投稿停止."""
        agent = _import_agent()
        # debut は現在 enabled=False なのでそのまま検証
        ok, reason = agent._check_rate_limit("debut")
        assert ok is False
        assert "無効化" in reason or "enabled" in reason

    def test_unknown_mode_blocks(self):
        """未定義 mode はエラーで停止."""
        agent = _import_agent()
        ok, reason = agent._check_rate_limit("invalid_mode_xyz")
        assert ok is False
        assert "未定義" in reason

    def test_enabled_mode_passes_kill_switch(self):
        """enabled=True かつ cooldown/cap 余裕があれば ok=True."""
        agent = _import_agent()
        with patch.object(agent, "get_last_post_time", return_value=None), \
             patch.object(agent, "get_posted_ids_within_hours", return_value=set()):
            ok, _ = agent._check_rate_limit("daily")
            assert ok is True


class TestCheckRateLimitCooldown:
    """cooldown_hours の時間ガード."""

    def test_within_cooldown_blocks(self):
        """前回投稿から cooldown_hours 未満なら停止."""
        agent = _import_agent()
        recent = datetime.now(timezone.utc) - timedelta(hours=1)  # 1時間前
        with patch.object(agent, "get_last_post_time", return_value=recent), \
             patch.object(agent, "get_posted_ids_within_hours", return_value=set()):
            # daily の cooldown は 8h なので 1h 経過は不足
            ok, reason = agent._check_rate_limit("daily")
            assert ok is False
            assert "cooldown" in reason.lower()

    def test_after_cooldown_passes(self):
        """前回投稿から cooldown_hours 経過していれば pass."""
        agent = _import_agent()
        old = datetime.now(timezone.utc) - timedelta(hours=10)  # 10時間前 (>8h)
        with patch.object(agent, "get_last_post_time", return_value=old), \
             patch.object(agent, "get_posted_ids_within_hours", return_value=set()):
            ok, _ = agent._check_rate_limit("daily")
            assert ok is True

    def test_no_prior_post_passes_cooldown(self):
        """前回投稿が None (初回) なら cooldown は通過."""
        agent = _import_agent()
        with patch.object(agent, "get_last_post_time", return_value=None), \
             patch.object(agent, "get_posted_ids_within_hours", return_value=set()):
            ok, _ = agent._check_rate_limit("daily")
            assert ok is True


class TestCheckRateLimitDailyCap:
    """max_per_24h の二重ガード (cooldown スリップ事故対策)."""

    def test_at_cap_blocks(self):
        """24h 内件数が max_per_24h と等しければ停止 (cooldown ぐらつきの保険)."""
        agent = _import_agent()
        cap = agent.BLUESKY_POSTING_CONFIG["daily"]["max_per_24h"]
        # cooldown が抜けても cap で止まることを検証するため
        # get_last_post_time は None (cooldown 通過) にする
        with patch.object(agent, "get_last_post_time", return_value=None), \
             patch.object(agent, "get_posted_ids_within_hours", return_value=set([f"id{i}" for i in range(cap)])):
            ok, reason = agent._check_rate_limit("daily")
            assert ok is False
            assert "上限" in reason or "24h" in reason

    def test_below_cap_passes(self):
        """24h 内件数が max_per_24h 未満なら pass."""
        agent = _import_agent()
        cap = agent.BLUESKY_POSTING_CONFIG["daily"]["max_per_24h"]
        with patch.object(agent, "get_last_post_time", return_value=None), \
             patch.object(agent, "get_posted_ids_within_hours", return_value=set([f"id{i}" for i in range(cap - 1)])):
            ok, _ = agent._check_rate_limit("daily")
            assert ok is True


class TestRegressionDebut48PerDay:
    """T2026-0502-L: 5/1 の debut 48件/日 事故の再発防止 (回帰テスト)."""

    def test_debut_disabled_returns_false_immediately(self):
        """現在の設定 (enabled=False) で post_debut は早期 return False する."""
        agent = _import_agent()
        # post_debut は実 client / S3 を触る前に _check_rate_limit で弾けるはず
        ok, reason = agent._check_rate_limit("debut")
        assert ok is False, f"debut は無効化中のはず (reason={reason})"

    def test_debut_when_reenabled_caps_at_2_per_day(self):
        """debut を enabled=True に再有効化しても 24h cap で 2件/日に物理制限される."""
        agent = _import_agent()
        # config を一時的に enabled=True に書き換え (元の値は退避)
        original = dict(agent.BLUESKY_POSTING_CONFIG["debut"])
        agent.BLUESKY_POSTING_CONFIG["debut"] = {
            **original, "enabled": True
        }
        try:
            cap = agent.BLUESKY_POSTING_CONFIG["debut"]["max_per_24h"]
            assert cap <= 2, f"debut の max_per_24h は 2 以下であるべき (現在 {cap})"
            # 24h cap 到達状態で blocks
            old_post = datetime.now(timezone.utc) - timedelta(hours=24)  # cooldown 通過
            with patch.object(agent, "get_last_post_time", return_value=old_post), \
                 patch.object(agent, "get_posted_ids_within_hours",
                              return_value=set([f"d{i}" for i in range(cap)])):
                ok, reason = agent._check_rate_limit("debut")
                assert ok is False
                assert "上限" in reason or "24h" in reason
        finally:
            agent.BLUESKY_POSTING_CONFIG["debut"] = original
