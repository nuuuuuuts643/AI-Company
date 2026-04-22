#!/usr/bin/env python3
"""tasks/queue.md から次のタスクを取得し Claude Code 用プロンプトを生成する。"""
import re, sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
QUEUE_FILE = REPO_ROOT / "tasks" / "queue.md"
PROMPT_FILE = Path("/tmp/developer_prompt.txt")
TASK_FILE = Path("/tmp/current_task.txt")


def get_next_task():
    if not QUEUE_FILE.exists():
        return None
    m = re.search(r'- \[ \] (.+)', QUEUE_FILE.read_text())
    return m.group(1).strip() if m else None


def prepare(manual_task=""):
    task = manual_task.strip() if manual_task.strip() else get_next_task()
    if not task:
        print("[developer_agent] タスクなし 終了")
        sys.exit(0)

    TASK_FILE.write_text(task)

    claude_md = REPO_ROOT / "CLAUDE.md"
    context = "".join(claude_md.read_text().splitlines(keepends=True)[:120]) if claude_md.exists() else ""

    prompt = f"""あなたはAI-Companyの開発エージェントです。
作業ディレクトリのファイルを直接編集して実装を完了させてください。

## プロジェクト状態（CLAUDE.mdより）
{context}

## 今日の実装タスク
{task}

## 厳守ルール
- scripts/ .github/ は変更しない
- frontend/ lambda/ projects/ の変更のみ行う
- 実装完了後に「✅ 実装完了: [変更ファイル一覧]」を出力する
- 不明点は最善判断で進める（質問不要）
"""
    PROMPT_FILE.write_text(prompt)
    print(f"[developer_agent] タスク準備完了: {task}")


def mark_done():
    if not TASK_FILE.exists() or not QUEUE_FILE.exists():
        return
    task = TASK_FILE.read_text().strip()
    content = QUEUE_FILE.read_text()
    QUEUE_FILE.write_text(content.replace(f"- [ ] {task}", f"- [x] {task}", 1))
    print(f"[developer_agent] 完了マーク: {task}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    arg = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
    if cmd == "prepare":
        prepare(arg)
    elif cmd == "mark-done":
        mark_done()
    else:
        print(f"usage: developer_agent.py prepare [task] | mark-done")
        sys.exit(1)
