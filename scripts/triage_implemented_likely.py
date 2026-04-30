#!/usr/bin/env python3
"""TASKS.md `(HISTORY 確認要)` 行を HISTORY.md と突合して自動取消線化する。

T2026-0428-H: 「実装済の可能性あり」と書かれたまま放置されるタスクを物理的に
解消する。AI が手動で HISTORY を grep する手間を省き、scheduled-task の
発見偏重バイアスを下げる構造的対策の一部。

仕組み:
  1. TASKS.md を読む
  2. `(HISTORY 確認要)` を含む行から TaskID を抽出 (T123 / T2026-0428-X 形式)
  3. HISTORY.md を全文 grep して同 TaskID の `done` / `✅` / `完了` を含む行があれば一致
  4. 一致したら TASKS.md の該当行を `~~TaskID~~` で取消線化
     (triage_tasks.py が次回起動で HISTORY.md に集約移動する)

副作用:
  TASKS.md を直接書き換える。書き換え件数は STDOUT に出す。
  cron / session_bootstrap.sh から呼ばれる前提。

呼び出し:
  python3 scripts/triage_implemented_likely.py
  python3 scripts/triage_implemented_likely.py --dry-run
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import subprocess
import sys
from pathlib import Path

# === REPO 検出 (triage_tasks.py と同方針: glob で session ID 不定対策) ===

def _candidates() -> list[Path]:
    cand: list[Path] = []
    env_repo = os.environ.get("REPO")
    if env_repo:
        cand.append(Path(env_repo))
    # スクリプト位置から git toplevel を解決（worktree 含めどこから呼ばれても効く）
    try:
        script_dir = Path(__file__).resolve().parent
        out = subprocess.check_output(
            ["git", "-C", str(script_dir), "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        if out:
            cand.append(Path(out))
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    home_repo = Path.home() / "ai-company"
    cand.append(home_repo)
    for p in glob.glob("/sessions/*/mnt/ai-company"):
        cand.append(Path(p))
    cand.append(Path(os.getcwd()))
    return cand


def find_repo() -> Path:
    for p in _candidates():
        try:
            if (p / "CLAUDE.md").exists():
                return p
        except (PermissionError, OSError):
            continue
    raise SystemExit("repo root not found (CLAUDE.md is the marker)")


# === 抽出: HISTORY 確認要 を含む行 ===

# 「(HISTORY 確認要)」「※実装済 (...)。HISTORY 確認要。」等のバリエーションを許容
CHECK_PATTERN = re.compile(r"HISTORY\s*確認要")
# TASKS.md の行は `| T123 |` か `| ~~T123~~ |` で始まる。後者はすでに取消線化済なので skip。
ROW_RE = re.compile(r"^\|\s*(T[0-9A-Za-z\-]+)\s*\|")


def find_done_in_history(history_text: str, tid: str) -> bool:
    """HISTORY.md の本文に対して `tid` が完了マーカーと共に出現するかを判定する。

    マーカー: `done` (case-insensitive) / `✅` / `完了`
    判定単位は行。同一行に tid とマーカーが両方あれば True。
    """
    # case-insensitive で TID を探し、その行の前後にマーカーがあるか
    # 完全一致を要求する: 単語境界 (空白、`|`, `:` 等) で囲まれていること
    tid_re = re.compile(rf"(?<![A-Za-z0-9\-]){re.escape(tid)}(?![A-Za-z0-9\-])")
    marker_re = re.compile(r"(done|完了|✅)", re.IGNORECASE)
    for line in history_text.split("\n"):
        if tid_re.search(line) and marker_re.search(line):
            return True
    return False


def strikethrough_row(line: str, tid: str) -> str:
    """| T123 | ... | → | ~~T123~~ | ✅ 完了 (auto-triage) | ... | のように取消線を入れる。

    安全のため:
    - 既に `~~` を含む行はそのまま (二重取消線化しない)
    - TaskID 部分のみ `~~T...~~` に置換し、行末に「✅ 自動triage 注記」を追加しない
      (誤判定時のロールバック容易性を保つ・元の行は参照可能)
    """
    if "~~" in line.split("|", 2)[1] if "|" in line else "~~" in line:
        return line
    return re.sub(rf"\|\s*{re.escape(tid)}\s*\|", f"| ~~{tid}~~ |", line, count=1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="書き換えずに対象行を STDOUT に出力するのみ")
    args = ap.parse_args()

    repo = find_repo()
    tasks_path = repo / "TASKS.md"
    history_path = repo / "HISTORY.md"
    if not tasks_path.exists() or not history_path.exists():
        print("[triage-implemented] TASKS.md or HISTORY.md not found, skip.")
        return 0

    tasks_text = tasks_path.read_text(encoding="utf-8")
    history_text = history_path.read_text(encoding="utf-8")

    new_lines: list[str] = []
    matched = 0
    for line in tasks_text.split("\n"):
        if CHECK_PATTERN.search(line):
            m = ROW_RE.match(line)
            if m:
                tid = m.group(1)
                if find_done_in_history(history_text, tid):
                    matched += 1
                    new_line = strikethrough_row(line, tid)
                    print(f"[triage-implemented] matched {tid}: {line[:80]}...")
                    if args.dry_run:
                        new_lines.append(line)
                    else:
                        new_lines.append(new_line)
                    continue
        new_lines.append(line)

    if matched and not args.dry_run:
        tasks_path.write_text("\n".join(new_lines), encoding="utf-8")
        print(f"[triage-implemented] struck through {matched} rows in TASKS.md")
    elif matched and args.dry_run:
        print(f"[triage-implemented] DRY-RUN: would strike {matched} rows")
    else:
        print("[triage-implemented] no matched rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
