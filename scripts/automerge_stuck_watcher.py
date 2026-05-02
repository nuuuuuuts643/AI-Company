#!/usr/bin/env python3
"""scripts/automerge_stuck_watcher.py — T2026-0502-D + T2026-0502-AB

【T2026-0502-D】auto_merge が enabled で mergeable_state=blocked のまま N 分以上
停滞している PR を検出し、CI が全 success かつ failure/pending check が 0 件なら
GitHub API `PUT /pulls/{N}/merge` で squash merge を強制発動する。

【T2026-0502-AB】(2026-05-02 PO 観測「何回も見てるぞこのコンフリクトのエラー」)
auto_merge が enabled で mergeable_state=dirty (= main と git conflict) の PR を
検出し、git rebase origin/main を試みる:
  - rebase 成功 → git push --force-with-lease → 既存の auto-merge が拾う
  - rebase 失敗 (conflict) → GitHub Issue を自動起票して人間に handoff
これにより「PR 出した後に main が動いて dirty になり詰まる」という頻発パターンを
物理消滅させる (本日 PR #162 / #186 / #234 で計3回手動介入が必要だった)。

背景: 2026-05-02 に PR #125 / #130 / #132 が auto-merge bot の internal
recompute ラグで詰まり、Cowork が手動 API merge で救済した事象（lessons-learned
「コンフリクト解決時に upstream 採用で破壊」セクション参照）の物理化対策。

環境変数:
    GITHUB_TOKEN: 必須。pull-requests:write / contents:write 権限が必要。
    GITHUB_REPOSITORY: 必須 (owner/repo 形式)。
    STUCK_THRESHOLD_MINUTES: stuck 判定の閾値分（デフォルト 5）。
    DIRTY_THRESHOLD_MINUTES: dirty 判定の閾値分（デフォルト 10、main から最後に rebase される
        までの猶予を確保）。
    REBASE_DISABLED: '1' なら dirty rebase をスキップ (検出のみ・既存 stuck 動作は維持)。
    GITHUB_STEP_SUMMARY: GitHub Actions 用サマリ出力先（任意）。

Exit code:
    0: stuck PR 検出 0 件、または検出した stuck PR を全件 merge 成功
       (dirty PR の rebase 失敗は exit code に影響しない — Issue 起票で十分)
    1: stuck PR の API merge が 1 件以上失敗
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
from typing import Any
from urllib import request as urlrequest
from urllib.error import HTTPError

API_ROOT = "https://api.github.com"
DEFAULT_STUCK_THRESHOLD_MINUTES = 5
DEFAULT_DIRTY_THRESHOLD_MINUTES = 10
USER_AGENT = "automerge-stuck-watcher/1.0"
GIT_REBASE_TIMEOUT = 90  # seconds — git rebase 単体のタイムアウト
GIT_PUSH_TIMEOUT = 60


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


# ============================================================================
# T2026-0502-AB: dirty PR 自動 rebase (PO「何回も見てるエラー」物理消滅対策)
# ============================================================================

def is_dirty_for_rebase(
    pr: dict[str, Any],
    threshold_minutes: int,
    now: dt.datetime,
) -> tuple[bool, str]:
    """auto_merge enabled かつ mergeable_state=dirty かつ N 分以上経過した PR を rebase 候補と判定。

    返り値: (rebase候補か, 理由)
    """
    if pr.get("state") != "open":
        return False, "not open"
    if pr.get("merged"):
        return False, "already merged"
    if not pr.get("auto_merge"):
        return False, "auto_merge not enabled"
    if pr.get("mergeable_state") != "dirty":
        return False, f"mergeable_state={pr.get('mergeable_state')}"
    if pr.get("draft"):
        return False, "draft PR"
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
    return True, f"dirty for {age_minutes:.1f}min, attempt rebase"


def try_rebase_pr(branch_ref: str) -> tuple[bool, str]:
    """git fetch + checkout + rebase + force-push を順に試行して結果を返す。

    GitHub Actions 環境想定:
      - 既に actions/checkout で repo が clone されている
      - origin remote が設定済 (GITHUB_TOKEN 認証)
      - git config user.email / user.name が事前にセットされている (workflow yml で実施)

    返り値: (成功か, 詳細メッセージ)
    """
    def _run(cmd: list[str], timeout: int) -> tuple[int, str]:
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )
            output = (result.stdout + result.stderr).strip()
            return result.returncode, output[:500]
        except subprocess.TimeoutExpired:
            return 124, f"timeout after {timeout}s"
        except FileNotFoundError as exc:
            return 127, f"command not found: {exc}"

    # Step 1: fetch both branch and main
    rc, out = _run(["git", "fetch", "origin", branch_ref, "main"], 60)
    if rc != 0:
        return False, f"fetch failed: {out}"

    # Step 2: checkout the PR branch
    rc, out = _run(["git", "checkout", "-B", branch_ref, f"origin/{branch_ref}"], 30)
    if rc != 0:
        return False, f"checkout failed: {out}"

    # Step 3: try rebase (no -i, no edit)
    rc, out = _run(["git", "rebase", "origin/main"], GIT_REBASE_TIMEOUT)
    if rc != 0:
        # Conflict — abort and report
        _run(["git", "rebase", "--abort"], 30)
        return False, f"rebase conflict (aborted): {out[:300]}"

    # Step 4: push with --force-with-lease for safety
    rc, out = _run(
        ["git", "push", "origin", branch_ref, "--force-with-lease"],
        GIT_PUSH_TIMEOUT,
    )
    if rc != 0:
        return False, f"push failed: {out[:300]}"

    return True, "rebased onto main and force-pushed"


def create_rebase_failed_issue(
    repo: str,
    pr_number: int,
    pr_title: str,
    branch_ref: str,
    detail: str,
    token: str,
) -> tuple[bool, str]:
    """rebase が conflict で失敗した PR について GitHub Issue を起票して人間に handoff。

    既に同じ PR に対して未 close の Issue があれば二重起票しない。
    """
    # 既存 Issue 検索 (title prefix で重複検知)
    issue_title = f"[auto-rebase failed] PR #{pr_number} dirty - manual rebase required"
    search_url = (
        f"{API_ROOT}/search/issues?q="
        f"repo:{repo}+is:issue+is:open+in:title+%22auto-rebase+failed%22+%22PR+%23{pr_number}%22"
    )
    try:
        _, search_payload = http_request("GET", search_url, token)
        if isinstance(search_payload, dict) and search_payload.get("total_count", 0) > 0:
            return True, "issue already exists (skipped)"
    except HTTPError:
        pass  # search 失敗は致命的でない、起票へ進む

    body_lines = [
        f"PR #{pr_number} ({pr_title}) は **mergeable_state=dirty** で自動 rebase に失敗しました。",
        "",
        f"**failure detail**: `{detail}`",
        "",
        "## 手動対処",
        "```bash",
        f"gh pr checkout {pr_number}",
        "git fetch origin main",
        "git rebase origin/main",
        "# resolve conflicts manually (lessons-learned: upstream を採用して当方変更を捨てるな)",
        "git rebase --continue",
        "git push --force-with-lease",
        "```",
        "",
        "## 関連",
        "- 自動化ロジック: `scripts/automerge_stuck_watcher.py:try_rebase_pr` (T2026-0502-AB)",
        "- 元タスク: T2026-0502-AB (PO「何回も見てるコンフリクトエラー」物理化対策)",
    ]
    issue_body = "\n".join(body_lines)
    create_url = f"{API_ROOT}/repos/{repo}/issues"
    try:
        _, payload = http_request(
            "POST", create_url, token,
            body={
                "title": issue_title,
                "body": issue_body,
                "labels": ["auto-rebase-failed", "auto-created"],
            },
        )
        if isinstance(payload, dict) and payload.get("number"):
            return True, f"issue #{payload['number']} created"
    except HTTPError as exc:
        return False, f"issue create HTTP {exc.code}"
    return False, "unexpected create response"


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
    try:
        dirty_threshold = int(os.environ.get(
            "DIRTY_THRESHOLD_MINUTES", DEFAULT_DIRTY_THRESHOLD_MINUTES))
    except ValueError:
        dirty_threshold = DEFAULT_DIRTY_THRESHOLD_MINUTES
    rebase_disabled = os.environ.get("REBASE_DISABLED", "").strip() == "1"

    now = _now_utc()
    print(f"[info] scanning open PRs in {repo} "
          f"(stuck_threshold={threshold}min, dirty_threshold={dirty_threshold}min, "
          f"rebase_disabled={rebase_disabled})")
    pulls = list_open_pulls(repo, token)
    print(f"[info] {len(pulls)} open PR(s)")

    summary_lines = [
        f"## auto-merge stuck watcher — {now.strftime('%Y-%m-%d %H:%M UTC')}",
        f"- Open PRs: {len(pulls)}",
        f"- Stuck threshold: {threshold} min / Dirty threshold: {dirty_threshold} min",
    ]

    stuck_results: list[tuple[int, str, bool, str]] = []
    dirty_results: list[tuple[int, str, bool, str]] = []
    failure_seen = False

    for pr in pulls:
        number = pr.get("number")
        title = pr.get("title", "")
        head_sha = (pr.get("head") or {}).get("sha", "")
        if not number or not head_sha:
            continue

        # T2026-0502-AB: dirty PR の自動 rebase を最初に試行 (stuck より先に救済)
        if not rebase_disabled:
            is_dirty, dirty_reason = is_dirty_for_rebase(pr, dirty_threshold, now)
            if is_dirty:
                branch_ref = (pr.get("head") or {}).get("ref", "")
                if not branch_ref:
                    print(f"[skip-dirty] PR #{number}: no head.ref")
                else:
                    print(f"[dirty] PR #{number}: {dirty_reason}")
                    rb_ok, rb_detail = try_rebase_pr(branch_ref)
                    dirty_results.append((number, title, rb_ok, rb_detail))
                    if rb_ok:
                        print(f"[rebased] PR #{number}: {rb_detail}")
                        # rebase 成功なら次回 watcher run で stuck 判定が走る
                        # (今 run では check 結果が古いので merge は試みない)
                        continue
                    print(f"[rebase-fail] PR #{number}: {rb_detail}")
                    issue_ok, issue_detail = create_rebase_failed_issue(
                        repo, number, title, branch_ref, rb_detail, token,
                    )
                    print(f"[issue] PR #{number}: {issue_detail}")
                    # rebase 失敗は failure_seen に積まない (Issue 起票で人間 handoff 完了)
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

    if dirty_results:
        summary_lines.append("")
        summary_lines.append("### Dirty PRs (T2026-0502-AB auto-rebase)")
        summary_lines.append("| PR | Title | Result | Detail |")
        summary_lines.append("|---|---|---|---|")
        for number, title, ok, detail in dirty_results:
            status_label = "✅ rebased" if ok else "❌ conflict (issue created)"
            safe_title = title.replace("|", "\\|")[:60]
            safe_detail = detail.replace("|", "\\|")[:120]
            summary_lines.append(
                f"| #{number} | {safe_title} | {status_label} | {safe_detail} |"
            )

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
    elif not dirty_results:
        summary_lines.append("")
        summary_lines.append("No stuck or dirty PRs detected.")

    write_summary(summary_lines)
    return 1 if failure_seen else 0


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
