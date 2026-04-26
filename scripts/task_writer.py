#!/usr/bin/env python3
"""CEO日次実行後に呼ばれ、今日の実装タスクを1件 tasks/queue.md に書く。"""
import json, os, re
from datetime import date
from pathlib import Path

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
REPO_ROOT = Path(__file__).parent.parent
TODAY = date.today().isoformat()
QUEUE_FILE = REPO_ROOT / "tasks" / "queue.md"


def call_claude(prompt):
    import urllib.request
    data = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 256,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=data,
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
    )
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read())["content"][0]["text"].strip()


def pending_count():
    if not QUEUE_FILE.exists():
        return 0
    return len(re.findall(r'- \[ \]', QUEUE_FILE.read_text()))


def read_context():
    parts = []
    for f in ["dashboard/ceo-daily.md", "inbox/ceo-proposals.md"]:
        p = REPO_ROOT / f
        if p.exists():
            parts.append(p.read_text()[:1500])
    return "\n\n".join(parts)


def append_task(task):
    QUEUE_FILE.parent.mkdir(exist_ok=True)
    if not QUEUE_FILE.exists():
        QUEUE_FILE.write_text("# 実装タスクキュー\n\n## 待機中\n\n## 完了済み\n")
    content = QUEUE_FILE.read_text()
    entry = f"- [ ] [{TODAY}] {task}\n"
    content = content.replace("## 待機中\n", f"## 待機中\n{entry}")
    QUEUE_FILE.write_text(content)
    print(f"[task_writer] 追加: {task}")


def main():
    if not ANTHROPIC_API_KEY:
        print("[task_writer] ANTHROPIC_API_KEY未設定 スキップ")
        return
    if pending_count() >= 2:
        print(f"[task_writer] 未処理タスク{pending_count()}件あり スキップ")
        return

    context = read_context()
    task = call_claude(f"""AI-Companyの開発タスク管理AIです。
以下のCEOレポートを読み、Developer Agentが今日実装すべきタスクを1行で出力してください。

## レポート
{context}

## 条件
- projects/P003-news-timeline/ のフロントエンドかLambdaの改善
- 1〜2時間で実装できる規模
- ユーザーへの価値が明確なもの

タスク説明を1行だけ出力してください（余分なテキスト不要）。""")

    if task:
        append_task(task)


if __name__ == "__main__":
    main()
