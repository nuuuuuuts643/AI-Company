#!/usr/bin/env python3
"""AI-Company 秘書スクリプト - GitHub Actions から実行される"""
import json
import os
import re
import sys
from pathlib import Path
import urllib.request
from datetime import date

ANTHROPIC_API_KEY = os.environ['ANTHROPIC_API_KEY']
SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL', '')
REPO_ROOT = Path(__file__).parent.parent
TODAY = date.today().isoformat()


def read_file(rel_path):
    try:
        return (REPO_ROOT / rel_path).read_text(encoding='utf-8')
    except Exception as e:
        return f"W読み込みエラー: {e}]"


def call_claude(prompt):
    data = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 8192,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=data,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01"
        }
    )
    try:
        resp = urllib.request.urlopen(req, timeout=180)
        return json.loads(resp.read())["content"][0]["text"]
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"API Error {e.code}: {body}")
        raise


def send_slack(message):
    if not SLACK_WEBHOOK_URL:
        print("SLACK_WEBHOOK_URL未設定 - Slack通知スキップ")
        return
    data = json.dumps({"text": message}).encode()
    req = urllib.request.Request(
        SLACK_WEBHOOK_URL,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    urllib.request.urlopen(req, timeout=10)
    print("Slack通知送信完了")


def parse_file_blocks(response):
    """
    <FILE path="...">内容</FILE> 形式でファイル更新を抽出する
    JSONより改行に強いフォーマット
    """
    pattern = r'<FILE path="([^"]+)">(.*?)</FILE>'
    matches = re.findall(pattern, response, re.DOTALL)
    return [{"path": m[0], "content": m[1].lstrip('\n')} for m in matches]


def parse_slack_block(response):
    """<SLACK>内容</SLACK> 形式でSlackメッセージを抽出"""
    match = re.search(r'<SLACK>(.*?)</SLACK>', response, re.DOTALL)
    return match.group(1).strip() if match else None


def main():
    files_to_read = [
        "company/secretary-protocol.md",
        "company/decision-rules.md",
        "company/constitution.md",
        "dashboard/overview.md",
        "dashboard/active-projects.md",
        "inbox/slack-messages.md",
        "inbox/raw-ideas.md",
        "projects/P001-ai-company-base/briefing.md",
        "projects/P003-news-timeline/briefing.md",
        "projects/P004-slack-bot/README.md",
    ]

    context_parts = []
    for f in files_to_read:
        content = read_file(f)
        context_parts.append(f"=== {f} ===\n{content}")
    context = "\n\n".join(context_parts)

    prompt = f"""あなたはAI-Companyの秘書Claudeです。今日は{TODAY}です。
以下の会社ファイルを読んで、secretary-protocol.mdに記載されたStep1〜7の秘書業務を実行してください。

{context}

---

全ての分析・判断を終えたら、以下の形式で出力してください。

更新するファイルは <FILE path="相対パス"> タグで囲んでください:
<FILE path="dashboard/overview.md">
ファイルの全内容をここに書く
</FILE>

Slackへの報告は <SLACK> タグで囲んでください:
<SLACK>
【AI-Company 定期報告】{TODAY}

■ 今回やったこと
  - 内容

■ 社長のアクションが必要
  - 内容（なければ「なし」）

■ 次回予定
  - 内容
</SLACK>

必ず以下のファイルを <FILE> タグで出力すること:
- dashboard/overview.md
- dashboard/active-projects.md
- projects/P001-ai-company-base/briefing.md（last_run, done_this_run, next_action を更新）
- projects/P003-news-timeline/briefing.md（last_run を更新）
- inbox/slack-messages.md（処理済みに ✅ を追加）
"""

    print(f"Claude API呼び出し中... ({TODAY})")
    response = call_claude(prompt)
    print("レスポンス受信完了")

    # ファイル更新を抽出
    file_updates = parse_file_blocks(response)
    if not file_updates:
        print("警告: ファイル更新が見つかりませんでした")
        print(f"レスポンス冒頭: {response[:200]}")
        send_slack(f"【AI-Company 秘書エラー】{TODAY}\nファイル更新の抽出に失敗しました。手動確認が必要です。")
        sys.exit(1)

    # ファイル書き込み
    for update in file_updates:
        path = REPO_ROOT / update["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(update["content"], encoding="utf-8")
        print(f"更新: {update['path']}")

    # Slack通知
    slack_msg = parse_slack_block(response)
    if not slack_msg:
        slack_msg = f"【AI-Company 定期報告】{TODAY}\n秘書実行完了（{len(file_updates)}ファイル更新）"
    send_slack(slack_msg)
    print("完了")


if __name__ == "__main__":
    main()
