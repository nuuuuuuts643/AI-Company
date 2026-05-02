#!/usr/bin/env python3
"""tests/test_automerge_stuck_watcher.py — T2026-0502-D

scripts/automerge_stuck_watcher.py の境界値テスト。
0件 / 1件 / 複数件 / 5分未満 / failed check 1件 / pending 1件 / merged 済み
の 7 ケースを検証する。
"""
from __future__ import annotations

import datetime as dt
import io
import json
import os
import sys
from typing import Any
from unittest import mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts import automerge_stuck_watcher as watcher


NOW = dt.datetime(2026, 5, 2, 12, 0, 0, tzinfo=dt.timezone.utc)


def _iso(delta_minutes: float) -> str:
    """NOW から delta_minutes 分前の ISO8601(Z) 文字列。"""
    t = NOW - dt.timedelta(minutes=delta_minutes)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _make_pr(
    number: int = 1,
    *,
    auto_merge: bool = True,
    mergeable_state: str = "blocked",
    age_minutes: float = 10.0,
    state: str = "open",
    merged: bool = False,
    head_sha: str = "abc1234deadbeef",
    title: str = "test PR",
) -> dict[str, Any]:
    return {
        "number": number,
        "title": title,
        "state": state,
        "merged": merged,
        "auto_merge": {"enabled_by": {"login": "octocat"}} if auto_merge else None,
        "mergeable_state": mergeable_state,
        "updated_at": _iso(age_minutes),
        "head": {"sha": head_sha},
    }


# ---- is_stuck 境界値 ---------------------------------------------------------


def test_is_stuck_happy_path():
    pr = _make_pr()
    stuck, reason = watcher.is_stuck(pr, [], threshold_minutes=5, now=NOW)
    assert stuck is True
    assert "stuck" in reason


def test_is_stuck_under_threshold():
    """更新から閾値未満なら stuck と判定しない（5分未満ケース）。"""
    pr = _make_pr(age_minutes=2.0)
    stuck, reason = watcher.is_stuck(pr, [], threshold_minutes=5, now=NOW)
    assert stuck is False
    assert "age=" in reason


def test_is_stuck_with_failed_check():
    """failure check が 1 件でもあれば stuck と判定しない。"""
    pr = _make_pr()
    runs = [
        {"name": "ci", "status": "completed", "conclusion": "success"},
        {"name": "lint", "status": "completed", "conclusion": "failure"},
    ]
    stuck, reason = watcher.is_stuck(pr, runs, threshold_minutes=5, now=NOW)
    assert stuck is False
    assert "failed check" in reason


def test_is_stuck_with_pending_check():
    """pending check が 1 件でもあれば stuck と判定しない。"""
    pr = _make_pr()
    runs = [
        {"name": "ci", "status": "completed", "conclusion": "success"},
        {"name": "slow", "status": "in_progress", "conclusion": None},
    ]
    stuck, reason = watcher.is_stuck(pr, runs, threshold_minutes=5, now=NOW)
    assert stuck is False
    assert "pending check" in reason


def test_is_stuck_already_merged():
    """既に merged 済みは stuck と判定しない。"""
    pr = _make_pr(state="closed", merged=True, mergeable_state="clean")
    stuck, reason = watcher.is_stuck(pr, [], threshold_minutes=5, now=NOW)
    assert stuck is False


def test_is_stuck_auto_merge_disabled():
    """auto_merge が有効化されていない PR は対象外。"""
    pr = _make_pr(auto_merge=False)
    stuck, reason = watcher.is_stuck(pr, [], threshold_minutes=5, now=NOW)
    assert stuck is False
    assert "auto_merge" in reason


def test_is_stuck_mergeable_state_clean():
    """blocked 以外（clean / behind / dirty）は stuck と判定しない。"""
    pr = _make_pr(mergeable_state="clean")
    stuck, reason = watcher.is_stuck(pr, [], threshold_minutes=5, now=NOW)
    assert stuck is False


# ---- run() 統合テスト（API モック）-----------------------------------------


class _FakeAPI:
    """http_request をフェイクして PR と check-runs と merge を返す。

    pulls: list of PR dicts
    check_runs_by_sha: dict[sha, list[run]]
    merge_responses: dict[pr_number, (status, payload)] or HTTPError
    """

    def __init__(
        self,
        pulls: list[dict[str, Any]],
        check_runs_by_sha: dict[str, list[dict[str, Any]]] | None = None,
        merge_responses: dict[int, tuple[int, dict[str, Any]]] | None = None,
    ):
        self.pulls = pulls
        self.check_runs_by_sha = check_runs_by_sha or {}
        self.merge_responses = merge_responses or {}
        self.merge_calls: list[int] = []

    def __call__(self, method: str, url: str, token: str, body: dict[str, Any] | None = None):
        if method == "GET" and "/pulls?state=open" in url:
            return 200, self.pulls
        if method == "GET" and "/check-runs" in url:
            sha = url.split("/commits/")[1].split("/")[0]
            return 200, {"check_runs": self.check_runs_by_sha.get(sha, [])}
        if method == "PUT" and "/pulls/" in url and url.endswith("/merge"):
            number = int(url.rstrip("/merge").rstrip("/").split("/")[-1])
            self.merge_calls.append(number)
            resp = self.merge_responses.get(number, (200, {"merged": True, "sha": "deadbeef" * 5}))
            return resp
        raise AssertionError(f"unexpected call: {method} {url}")


def _patched_run(monkeypatch, pulls, check_runs_by_sha=None, merge_responses=None,
                 threshold="5", now=NOW):
    fake = _FakeAPI(pulls, check_runs_by_sha, merge_responses)
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("STUCK_THRESHOLD_MINUTES", threshold)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setattr(watcher, "http_request", fake)
    monkeypatch.setattr(watcher, "_now_utc", lambda: now)
    code = watcher.run([])
    return code, fake


def test_run_zero_open_prs(monkeypatch):
    """case 1: open PR が 0 件。exit 0、merge 呼び出し 0。"""
    code, fake = _patched_run(monkeypatch, pulls=[])
    assert code == 0
    assert fake.merge_calls == []


def test_run_one_stuck_pr(monkeypatch):
    """case 2: stuck PR 1 件 → 1 件 squash merge 成功。exit 0。"""
    pr = _make_pr(number=42, head_sha="sha42abc")
    code, fake = _patched_run(
        monkeypatch,
        pulls=[pr],
        check_runs_by_sha={"sha42abc": [{"name": "ci", "status": "completed", "conclusion": "success"}]},
    )
    assert code == 0
    assert fake.merge_calls == [42]


def test_run_multiple_stuck_prs(monkeypatch):
    """case 3: stuck PR 複数件 → 全件 merge 試行。exit 0。"""
    prs = [
        _make_pr(number=10, head_sha="sha10"),
        _make_pr(number=11, head_sha="sha11"),
        _make_pr(number=12, head_sha="sha12"),
    ]
    code, fake = _patched_run(
        monkeypatch,
        pulls=prs,
        check_runs_by_sha={
            "sha10": [{"name": "ci", "status": "completed", "conclusion": "success"}],
            "sha11": [{"name": "ci", "status": "completed", "conclusion": "success"}],
            "sha12": [{"name": "ci", "status": "completed", "conclusion": "success"}],
        },
    )
    assert code == 0
    assert sorted(fake.merge_calls) == [10, 11, 12]


def test_run_pr_under_threshold_not_merged(monkeypatch):
    """case 4: 5 分未満の stuck PR は merge を試行しない。"""
    pr = _make_pr(number=99, age_minutes=2.0, head_sha="sha99")
    code, fake = _patched_run(
        monkeypatch,
        pulls=[pr],
        check_runs_by_sha={"sha99": []},
    )
    assert code == 0
    assert fake.merge_calls == []


def test_run_pr_with_failed_check_not_merged(monkeypatch):
    """case 5: failure check が 1 件あれば merge しない。"""
    pr = _make_pr(number=77, head_sha="sha77")
    code, fake = _patched_run(
        monkeypatch,
        pulls=[pr],
        check_runs_by_sha={"sha77": [
            {"name": "ci", "status": "completed", "conclusion": "success"},
            {"name": "lint", "status": "completed", "conclusion": "failure"},
        ]},
    )
    assert code == 0
    assert fake.merge_calls == []


def test_run_pr_with_pending_check_not_merged(monkeypatch):
    """case 6: pending check が 1 件あれば merge しない。"""
    pr = _make_pr(number=88, head_sha="sha88")
    code, fake = _patched_run(
        monkeypatch,
        pulls=[pr],
        check_runs_by_sha={"sha88": [
            {"name": "ci", "status": "in_progress", "conclusion": None},
        ]},
    )
    assert code == 0
    assert fake.merge_calls == []


def test_run_already_merged_pr_skipped(monkeypatch):
    """case 7: state=closed/merged=True の PR は対象外。"""
    pr = _make_pr(number=55, state="closed", merged=True, mergeable_state="clean", head_sha="sha55")
    code, fake = _patched_run(
        monkeypatch,
        pulls=[pr],
        check_runs_by_sha={"sha55": []},
    )
    assert code == 0
    assert fake.merge_calls == []


# ---- merge 失敗時の exit code ----------------------------------------------


def test_run_merge_api_failure_exit_1(monkeypatch):
    """merge API が merged=False を返したら exit 1。"""
    pr = _make_pr(number=33, head_sha="sha33")
    code, fake = _patched_run(
        monkeypatch,
        pulls=[pr],
        check_runs_by_sha={"sha33": [{"name": "ci", "status": "completed", "conclusion": "success"}]},
        merge_responses={33: (405, {"message": "Method Not Allowed", "merged": False})},
    )
    assert code == 1
    assert fake.merge_calls == [33]


# ---- threshold 環境変数 ----------------------------------------------------


def test_threshold_env_var_overrides_default(monkeypatch):
    """STUCK_THRESHOLD_MINUTES=30 なら 10 分前の PR は stuck と判定しない。"""
    pr = _make_pr(number=1, age_minutes=10.0, head_sha="x1")
    code, fake = _patched_run(
        monkeypatch,
        pulls=[pr],
        check_runs_by_sha={"x1": [{"name": "ci", "status": "completed", "conclusion": "success"}]},
        threshold="30",
    )
    assert code == 0
    assert fake.merge_calls == []


# ============================================================================
# T2026-0502-AB: dirty PR 自動 rebase テスト
# ============================================================================


class TestIsDirtyForRebase:
    """is_dirty_for_rebase 境界値テスト。"""

    def test_dirty_with_auto_merge_and_age_ok(self):
        pr = _make_pr(mergeable_state="dirty", auto_merge=True, age_minutes=15.0)
        ok, reason = watcher.is_dirty_for_rebase(pr, threshold_minutes=10, now=NOW)
        assert ok, f"reason={reason}"

    def test_dirty_but_too_young(self):
        pr = _make_pr(mergeable_state="dirty", auto_merge=True, age_minutes=3.0)
        ok, reason = watcher.is_dirty_for_rebase(pr, threshold_minutes=10, now=NOW)
        assert not ok
        assert "age=" in reason

    def test_dirty_but_no_auto_merge(self):
        pr = _make_pr(mergeable_state="dirty", auto_merge=False, age_minutes=15.0)
        ok, reason = watcher.is_dirty_for_rebase(pr, threshold_minutes=10, now=NOW)
        assert not ok
        assert "auto_merge" in reason

    def test_blocked_not_dirty_skipped(self):
        pr = _make_pr(mergeable_state="blocked", auto_merge=True, age_minutes=15.0)
        ok, reason = watcher.is_dirty_for_rebase(pr, threshold_minutes=10, now=NOW)
        assert not ok

    def test_clean_skipped(self):
        pr = _make_pr(mergeable_state="clean", auto_merge=True, age_minutes=15.0)
        ok, _ = watcher.is_dirty_for_rebase(pr, threshold_minutes=10, now=NOW)
        assert not ok

    def test_draft_skipped(self):
        pr = _make_pr(mergeable_state="dirty", auto_merge=True, age_minutes=15.0)
        pr["draft"] = True
        ok, reason = watcher.is_dirty_for_rebase(pr, threshold_minutes=10, now=NOW)
        assert not ok
        assert reason == "draft PR"

    def test_merged_skipped(self):
        pr = _make_pr(mergeable_state="dirty", auto_merge=True, merged=True, age_minutes=15.0)
        ok, _ = watcher.is_dirty_for_rebase(pr, threshold_minutes=10, now=NOW)
        assert not ok

    def test_closed_skipped(self):
        pr = _make_pr(mergeable_state="dirty", auto_merge=True, state="closed", age_minutes=15.0)
        ok, _ = watcher.is_dirty_for_rebase(pr, threshold_minutes=10, now=NOW)
        assert not ok


class TestTryRebasePr:
    """try_rebase_pr の subprocess 実行をモック化したテスト。"""

    def test_rebase_success(self, monkeypatch):
        calls = []

        def fake_run(cmd, capture_output, text, timeout):
            calls.append(cmd)
            class R:
                returncode = 0
                stdout = "ok"
                stderr = ""
            return R()

        monkeypatch.setattr(watcher.subprocess, "run", fake_run)
        ok, detail = watcher.try_rebase_pr("feature/test")
        assert ok, f"detail={detail}"
        assert "rebased" in detail.lower()
        assert len(calls) == 4
        assert calls[0][0:2] == ["git", "fetch"]
        assert calls[2][0:3] == ["git", "rebase", "origin/main"]
        assert calls[3][0:2] == ["git", "push"]
        assert "--force-with-lease" in calls[3]

    def test_rebase_conflict_aborts(self, monkeypatch):
        calls = []

        def fake_run(cmd, capture_output, text, timeout):
            calls.append(cmd)
            class R:
                pass
            r = R()
            if cmd[0:3] == ["git", "rebase", "origin/main"]:
                r.returncode = 1
                r.stdout = ""
                r.stderr = "CONFLICT (content): merge conflict in foo.py"
            else:
                r.returncode = 0
                r.stdout = ""
                r.stderr = ""
            return r

        monkeypatch.setattr(watcher.subprocess, "run", fake_run)
        ok, detail = watcher.try_rebase_pr("feature/test")
        assert not ok
        assert "conflict" in detail.lower()
        assert any(cmd[0:3] == ["git", "rebase", "--abort"] for cmd in calls)

    def test_fetch_failure_short_circuits(self, monkeypatch):
        calls = []

        def fake_run(cmd, capture_output, text, timeout):
            calls.append(cmd)
            class R:
                returncode = 128
                stdout = ""
                stderr = "fatal: could not read"
            return R()

        monkeypatch.setattr(watcher.subprocess, "run", fake_run)
        ok, detail = watcher.try_rebase_pr("feature/test")
        assert not ok
        assert "fetch failed" in detail
        assert len(calls) == 1

    def test_push_failure_after_successful_rebase(self, monkeypatch):
        def fake_run(cmd, capture_output, text, timeout):
            class R:
                pass
            r = R()
            if cmd[0:2] == ["git", "push"]:
                r.returncode = 1
                r.stdout = ""
                r.stderr = "remote rejected"
            else:
                r.returncode = 0
                r.stdout = ""
                r.stderr = ""
            return r

        monkeypatch.setattr(watcher.subprocess, "run", fake_run)
        ok, detail = watcher.try_rebase_pr("feature/test")
        assert not ok
        assert "push failed" in detail

    def test_timeout_handled(self, monkeypatch):
        import subprocess as sp_mod

        def fake_run(cmd, capture_output, text, timeout):
            raise sp_mod.TimeoutExpired(cmd=cmd, timeout=timeout)

        monkeypatch.setattr(watcher.subprocess, "run", fake_run)
        ok, detail = watcher.try_rebase_pr("feature/test")
        assert not ok
