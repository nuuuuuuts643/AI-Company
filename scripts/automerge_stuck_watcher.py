#!/usr/bin/env python3
"""scripts/automerge_stuck_watcher.py — T2026-0502-D

auto_merge が enabled で mergeable_state=blocked のまま N 分以上停滞している
PR を検出し、CI が全 success かつ failure/pending check が 0 件なら
GitHub API `PUT /pulls/{N}/merge` で squash merge を強制発動する。

背景: 2026-05-02 に PR #125 / #130 / #132 が auto-merge bot の internal
recompute ラグで詰まり、Cowork が手動 API merge で救済した事象（lessons-learned
「コンフリクト解決時に upstream 採用で破壊」セクション参照）の物理化対策。

環境変数:
    GITHUB_TOKEN: 必須。pull-requests:write / contents:write 権限が必要。
    GITHUB_REPOSITORY: 必須 (owner/repo 形式)。
    STUCK_THRESHOLD_MINUTES: stuck 判定の閾値分（デフォルト 5）。
    GITHUB_STEP_SUMMARY: GitHub Actions 用サマリ出力先（任意）。

Exit code:
    0: stuck PR 検出 0 件、または検出した stuck PR を全件 merge 成功
    1: stuck PR の API merge が 1 件以上失敗
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from typing import Any
from urllib import request as urlrequest
from urllib.error import HTTPError

API_ROOT = "https://api.github.com"
DEFAULT_STUCK_THRESHOLD_MINUTES = 5
USER_AGENT = "automerge-stuck-watcher/1.0"


def _now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _parse_iso8601(value: str) -> dt.datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return dt.datetime.fromisoformat(value)


def http_request(
    method: str,
    url: str,
    token: str,
    body: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any] | list[Any]]:
    """GitHub REST API を叩いて (status, parsed_json) を返す。

    HTTPError は呼び出し側で捕捉する。404/422 等の API エラーは raise されるので
    呼び出し側がリカバリ判断する。
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": USER_AGENT,
    }
    data: bytes | None = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urlrequest.Request(url, data=data, headers=headers, method=method)
    with urlrequest.urlopen(req) as resp:
        raw = resp.read().decode("utf-8")
        parsed: dict[str, Any] | list[Any] = json.loads(raw) if raw else {}
        return resp.status, parsed


def list_open_pulls(repo: str, token: str) -> list[dict[str, Any]]:
    url = f"{API_ROOT}/repos/{repo}/pulls?state=open&per_page=50"
    _, payload = http_request("GET", url, token)
    if not isinstance(payload, list):
        return []
    return payload


def list_check_runs(repo: str, sha: str, token: str) -> list[dict[str, Any]]:
    url = f"{API_ROOT}/repos/{repo}/commits/{sha}/check-runs?per_page=100"
    _, payload = http_request("GET", url, token)
    if isinstance(payload, dict):
        runs = payload.get("check_runs", [])
        return runs if isinstance(runs, list) else []
    return []


def is_stuck(
    pr: dict[str, Any],
    check_runs: list[dict[str, Any]],
    threshold_minutes: int,
    now: dt.datetime,
) -> tuple[bool, str]:
    """Stuck 判定。(stuck か, 判定理由) を返す。"""
    if pr.get("state") != "open":
        return False, "not open"
    if pr.get("merged"):
        return False, "already merged"
    if not pr.get("auto_merge"):
        return False, "auto_merge not enabled"
    if pr.get("mergeable_state") != "blocked":
        return False, f"mergeable_state={pr.get('mergeable_state')}"
    updated_at_str = pr.get("updated_at")
    if not updated_at_str:
        return False, "no updated_at"
    try:
        updated_at = _parse_iso8601(updated_at_str)
    except ValueError:
        return False, "invalid updated_at"
    age_minutes = (now - updated_at).total_seconds() / 60.0
    if age_minutes < threshold_minutes:
        return False, f"age={age_minutes:.1f}min < {threshold_minutes}min"
    failure_count = sum(
        1 for run in check_runs if run.get("conclusion") == "failure"
    )
    if failure_count > 0:
        return False, f"{failure_count} failed check(s)"
    pending_count = sum(
        1 for run in check_runs if run.get("status") != "completed"
    )
    if pending_count > 0:
        return False, f"{pending_count} pending check(s)"
    return True, f"stuck for {age_minutes:.1f}min"


def merge_pr(repo: str, number: int, token: str) -> tuple[bool, str]:
    url = f"{API_ROOT}/repos/{repo}/pulls/{number}/merge"
    try:
        status, payload = http_request(
            "PUT", url, token, body={"merge_method": "squash"}
        )
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
        return False, f"HTTP {exc.code}: {body[:200]}"
    if isinstance(payload, dict) and payload.get("merged"):
        sha = payload.get("sha", "")
        return True, f"merged sha={sha[:7]}"
    return False, f"status={status} payload={str(payload)[:200]}"


def write_summary(lines: list[str]) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    try:
        with open(summary_path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    except OSError as exc:
        print(f"[warn] failed to write GITHUB_STEP_SUMMARY: {exc}", file=sys.stderr)


def run(argv: list[str] | None = None) -> int:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not token:
        print("ERROR: GITHUB_TOKEN is required", file=sys.stderr)
        return 1
    if not repo:
        print("ERROR: GITHUB_REPOSITORY is required (owner/repo)", file=sys.stderr)
        return 1
    try:
        threshold = int(os.environ.get("STUCK_THRESHOLD_MINUTES", DEFAULT_STUCK_THRESHOLD_MINUTES))
    except ValueError:
        threshold = DEFAULT_STUCK_THRESHOLD_MINUTES

    now = _now_utc()
    print(f"[info] scanning open PRs in {repo} (threshold={threshold}min)")
    pulls = list_open_pulls(repo, token)
    print(f"[info] {len(pulls)} open PR(s)")

    summary_lines = [
        f"## auto-merge stuck watcher — {now.strftime('%Y-%m-%d %H:%M UTC')}",
        f"- Open PRs: {len(pulls)}",
        f"- Stuck threshold: {threshold} min",
    ]

    stuck_results: list[tuple[int, str, bool, str]] = []
    failure_seen = False

    for pr in pulls:
        number = pr.get("number")
        title = pr.get("title", "")
        head_sha = (pr.get("head") or {}).get("sha", "")
        if not number or not head_sha:
            continue
        try:
            check_runs = list_check_runs(repo, head_sha, token)
        except HTTPError as exc:
            print(f"[warn] PR #{number}: failed to fetch check-runs: HTTP {exc.code}")
            continue
        stuck, reason = is_stuck(pr, check_runs, threshold, now)
        if not stuck:
            print(f"[skip] PR #{number}: {reason}")
            continue
        print(f"[stuck] PR #{number}: {reason} → attempting squash merge")
        ok, detail = merge_pr(repo, number, token)
        stuck_results.append((number, title, ok, detail))
        if ok:
            print(f"[ok] PR #{number}: {detail}")
        else:
            print(f"[fail] PR #{number}: {detail}")
            failure_seen = True

    if stuck_results:
        summary_lines.append("")
        summary_lines.append("### Stuck PRs handled")
        summary_lines.append("| PR | Title | Result | Detail |")
        summary_lines.append("|---|---|---|---|")
        for number, title, ok, detail in stuck_results:
            status_label = "✅ merged" if ok else "❌ failed"
            safe_title = title.replace("|", "\\|")[:60]
            safe_detail = detail.replace("|", "\\|")[:120]
            summary_lines.append(
                f"| #{number} | {safe_title} | {status_label} | {safe_detail} |"
            )
    else:
        summary_lines.append("")
        summary_lines.append("No stuck PRs detected.")

    write_summary(summary_lines)
    return 1 if failure_seen else 0


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
