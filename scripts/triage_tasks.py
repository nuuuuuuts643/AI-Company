#!/usr/bin/env python3
"""TASKS.md / WORKING.md 自動 triage スクリプト。

目的:
1. TASKS.md の取消線済み行 (`| ~~T...~~ |` で始まる行) を HISTORY.md に集約移動
   → TASKS.md の肥大化を防ぎ、AIが「未着手のみ」を最短で読める状態を保つ
2. WORKING.md の 8 時間超 stale エントリを自動削除
   → CLAUDE.md「8h TTL」ルールの物理化
3. (将来) タスクID 重複の検知（CI 連携用）

呼び出し:
  python3 scripts/triage_tasks.py --clean-working-md
  python3 scripts/triage_tasks.py --triage-tasks
  python3 scripts/triage_tasks.py --check-duplicate-task-ids   # exit 1 if 重複あり

副作用:
  TASKS.md / WORKING.md / HISTORY.md を直接書き換える。
  session_bootstrap.sh が呼ぶ前提。手動でも実行可能。
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
from pathlib import Path

REPO_CANDIDATES = [
    Path("/Users/OWNER/ai-company"),
    Path("/sessions/keen-optimistic-keller/mnt/ai-company"),
    Path(os.getcwd()),
]


def find_repo() -> Path:
    for p in REPO_CANDIDATES:
        if (p / "CLAUDE.md").exists():
            return p
    raise SystemExit("repo root not found (CLAUDE.md is the marker)")


# ---------- 1. WORKING.md stale 削除 ----------

WORKING_ROW_RE = re.compile(
    r"^\|\s*\[(Code|Cowork)\][^|]*\|"
    r"[^|]*\|"
    r"[^|]*\|"
    r"\s*(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2})"
)


def clean_working_md(repo: Path, max_age_h: int = 8) -> int:
    path = repo / "WORKING.md"
    if not path.exists():
        return 0
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    cutoff = dt.datetime.utcnow() + dt.timedelta(hours=9) - dt.timedelta(hours=max_age_h)
    removed = 0
    new_lines: list[str] = []
    for line in lines:
        m = WORKING_ROW_RE.match(line)
        if m:
            ts_raw = m.group(2).replace("T", " ")
            try:
                ts = dt.datetime.strptime(ts_raw, "%Y-%m-%d %H:%M")
            except ValueError:
                new_lines.append(line)
                continue
            if ts < cutoff:
                removed += 1
                continue
        new_lines.append(line)
    if removed:
        path.write_text("\n".join(new_lines), encoding="utf-8")
        print(f"[triage] removed {removed} stale rows from WORKING.md")
    return removed


# ---------- 2. TASKS.md 取消線 → HISTORY.md ----------

# 取消線形式: `| ~~T123~~ |` または `| ~~T2026-0428-A~~ |`
STRIKE_RE = re.compile(r"^\|\s*~~T[0-9A-Za-z\-]+~~\s*\|")


def triage_tasks(repo: Path) -> int:
    tasks = repo / "TASKS.md"
    history = repo / "HISTORY.md"
    if not tasks.exists() or not history.exists():
        return 0
    src_lines = tasks.read_text(encoding="utf-8").split("\n")
    moved: list[str] = []
    keep: list[str] = []
    for line in src_lines:
        if STRIKE_RE.match(line):
            moved.append(line)
        else:
            keep.append(line)
    if not moved:
        return 0

    today = dt.datetime.utcnow() + dt.timedelta(hours=9)
    header = f"\n### 自動 triage: {today:%Y-%m-%d} に TASKS.md から移動した取消線済みタスク\n"
    body = "\n".join(["", header, "<details><summary>取消線で完了マークされた行（TASKS.md 由来）</summary>", ""] + moved + ["", "</details>", ""])

    hist_text = history.read_text(encoding="utf-8")
    history.write_text(hist_text + body, encoding="utf-8")
    tasks.write_text("\n".join(keep), encoding="utf-8")
    print(f"[triage] moved {len(moved)} struck-through rows TASKS.md → HISTORY.md")
    return len(moved)


# ---------- 3. タスクID 重複検出 ----------

ID_RE = re.compile(r"^\|\s*~?~?(T[0-9A-Za-z\-]+)~?~?\s*\|")


def check_duplicate_task_ids(repo: Path) -> int:
    tasks = repo / "TASKS.md"
    if not tasks.exists():
        return 0
    seen: dict[str, list[int]] = {}
    for i, line in enumerate(tasks.read_text(encoding="utf-8").split("\n"), start=1):
        m = ID_RE.match(line)
        if not m:
            continue
        seen.setdefault(m.group(1), []).append(i)
    duplicates = {tid: rows for tid, rows in seen.items() if len(rows) > 1}
    if duplicates:
        print("[triage] DUPLICATE TASK IDS DETECTED:", file=sys.stderr)
        for tid, rows in duplicates.items():
            print(f"  {tid}: lines {rows}", file=sys.stderr)
        return 1
    return 0


# ---------- main ----------


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean-working-md", action="store_true")
    ap.add_argument("--triage-tasks", action="store_true")
    ap.add_argument("--check-duplicate-task-ids", action="store_true")
    args = ap.parse_args()

    repo = find_repo()
    rc = 0
    if args.clean_working_md:
        clean_working_md(repo)
    if args.triage_tasks:
        triage_tasks(repo)
    if args.check_duplicate_task_ids:
        rc = max(rc, check_duplicate_task_ids(repo))
    if not (args.clean_working_md or args.triage_tasks or args.check_duplicate_task_ids):
        print(__doc__)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
