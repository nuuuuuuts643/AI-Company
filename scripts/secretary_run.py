#!/usr/bin/env python3
"""AI-Company 秘書スクリプト - GitHub Actions から実行される"""
import json
import os
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
        return (REPO_ROOT / rel_path).read_text()
    except Exception as e:
        return f"[読み込みエラー: {e}]"


def call_claude(prompt):
    data = json.dumps({
        "model": "claude-sonnet-4-6",
        "max_tokens": 8096,
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
    resp = urllib.request.urlopen(req, timeout=120)
    return json.loads(resp.read())["content"][0]["text"]


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
        "projects/P002-unity-game/briefing.md",
        "projects/P003-news-timeline/briefing.md",
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

全ての分析・判断を終えたら、以下のJSON形式だけで返答してください（他のテキスト不要）:
{{
  "file_updates": [
    {{"path": "ファイルのパス(リポジトリルートからの相対パス)", "content": "ファイルの全内容"}}
  ],
  "slack_message": "Slackに送る報告メッセージ（\\nで改行）",
  "summary": "今回やったことの要約（1〜3行）"
}}

必ずfile_updatesには以下を含めること:
- dashboard/overview.md (更新)
- dashboard/active-projects.md (更新)
- 各案件のbriefing.md (last_run, status, done_this_run, next_action を更新)
- inbox/slack-messages.md (処理済みアイテムに ✅ を追加)

slack_messageは以下フォーマット:
【AI-Company 定期報告】{TODAY}

■ 今回やったこと
  - 内容

■ 社長のアクションが必要
  - 内容（なければ「なし」）

■ 次回予定
  - 内容
"""

    print(f"Claude API呼び出し中... ({TODAY})")
    response = call_claude(prompt)

    # JSON抽出
    try:
        start = response.find('{')
        end = response.rfind('}') + 1
        if start == -1:
            raise ValueError("JSONが見つかりません")
        result = json.loads(response[start:end])
    except Exception as e:
        print(f"JSONパースエラー: {e}")
        print(f"レスポンス冒頭: {response[:300]}")
        # フォールバック: Slackにエラー通知
        send_slack(f"【AI-Company 秘書エラー】{TODAY}\nJSONパースに失敗しました。手動確認が必要です。")
        sys.exit(1)

    print(f"サマリー: {result.get('summary', '(なし)')}")

    # ファイル更新
    for update in result.get("file_updates", []):
        path = REPO_ROOT / update["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(update["content"], encoding="utf-8")
        print(f"更新: {update['path']}")

    # Slack通知
    slack_msg = result.get(
        "slack_message",
        f"【AI-Company 定期報告】{TODAY}\n\n{result.get('summary', '秘書実行完了')}"
    )
    send_slack(slack_msg)


if __name__ == "__main__":
    main()
