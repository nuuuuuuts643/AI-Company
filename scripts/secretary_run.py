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
NOTION_API_KEY = os.environ.get('NOTION_API_KEY', '')
REPO_ROOT = Path(__file__).parent.parent
TODAY = date.today().isoformat()

# Notion データベース ID
NOTION_DB_PROJECTS  = '88860b1e-9bf7-4d71-afa5-a1bd96c318ef'  # 案件管理
NOTION_DB_IDEAS     = 'fca493fb-2b25-4b9d-8a61-b31d3349864c'  # アイデアバンク
NOTION_DB_KNOWLEDGE = '53a98e27-1f97-443e-a491-42e5e2a867f9'  # ナレッジベース

# DynamoDB設定（CEOの記憶を参照するため）
MEMORY_TABLE = "ai-company-memory"
MEMORY_PK = "CEO_MEMORY"
AWS_REGION = os.environ.get('AWS_DEFAULT_REGION', 'ap-northeast-1')


def load_ceo_memory(limit=5):
    """DynamoDBからCEOの最近の判断履歴を読み込む（参照のみ・失敗しても継続）"""
    try:
        import boto3
        from boto3.dynamodb.conditions import Key
        dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
        table = dynamodb.Table(MEMORY_TABLE)
        resp = table.query(
            KeyConditionExpression=Key('pk').eq(MEMORY_PK),
            ScanIndexForward=False,
            Limit=limit
        )
        items = resp.get('Items', [])
        if not items:
            return "(CEOの過去記録なし)"
        lines = []
        for item in items:
            sk = item.get('sk', '')
            summary = item.get('summary', '（サマリーなし）')
            lines.append(f"- [{sk}] {summary}")
        return "\n".join(lines)
    except Exception as e:
        print(f"[memory] load_ceo_memory失敗（メイン処理は継続）: {e}")
        return "(メモリ読み込み失敗)"


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


# ---------------------------------------------------------------------------
# Notion API
# ---------------------------------------------------------------------------

def notion_request(method, endpoint, payload=None):
    """Notion API への汎用リクエスト（エラーは呼び出し元でキャッチ）"""
    if not NOTION_API_KEY:
        print("NOTION_API_KEY未設定 - Notion操作スキップ")
        return None
    url = f"https://api.notion.com/v1/{endpoint}"
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {NOTION_API_KEY}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        },
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"Notion API Error {e.code}: {body}")
        return None


def update_notion_project(page_id, status, next_action, last_run):
    """案件管理 DB のページを更新する。エラーがあってもメイン処理は止めない。"""
    try:
        payload = {
            "properties": {
                "ステータス": {
                    "select": {"name": status}
                },
                "次のアクション": {
                    "rich_text": [{"text": {"content": next_action[:2000]}}]
                },
                "最終更新日": {
                    "date": {"start": last_run}
                },
            }
        }
        result = notion_request("PATCH", f"pages/{page_id}", payload)
        if result:
            print(f"Notion案件更新完了: {page_id}")
        return result
    except Exception as e:
        print(f"Notion案件更新エラー ({page_id}): {e}")
        return None


def add_knowledge_entry(title, content, category):
    """ナレッジベース DB に記録を追加する。エラーがあってもメイン処理は止めない。"""
    try:
        payload = {
            "parent": {"database_id": NOTION_DB_KNOWLEDGE},
            "properties": {
                "名前": {
                    "title": [{"text": {"content": title[:2000]}}]
                },
                "カテゴリ": {
                    "select": {"name": category}
                },
                "日付": {
                    "date": {"start": TODAY}
                },
            },
            "children": [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {"type": "text", "text": {"content": content[:2000]}}
                        ]
                    },
                }
            ],
        }
        result = notion_request("POST", "pages", payload)
        if result:
            print(f"Notionナレッジ追加完了: {title}")
        return result
    except Exception as e:
        print(f"Notionナレッジ追加エラー ({title}): {e}")
        return None


def parse_notion_project_blocks(response):
    """
    <NOTION_PROJECT page_id="..." status="..." next_action="..." last_run="..."/>
    形式のタグを抽出する
    """
    pattern = (
        r'<NOTION_PROJECT\s+'
        r'page_id="([^"]+)"\s+'
        r'status="([^"]+)"\s+'
        r'next_action="([^"]+)"\s+'
        r'last_run="([^"]+)"\s*/>'
    )
    matches = re.findall(pattern, response)
    return [
        {"page_id": m[0], "status": m[1], "next_action": m[2], "last_run": m[3]}
        for m in matches
    ]


def parse_notion_knowledge_blocks(response):
    """
    <NOTION_KNOWLEDGE title="..." category="...">内容</NOTION_KNOWLEDGE>
    形式のタグを抽出する
    """
    pattern = (
        r'<NOTION_KNOWLEDGE\s+'
        r'title="([^"]+)"\s+'
        r'category="([^"]+)">'
        r'(.*?)</NOTION_KNOWLEDGE>'
    )
    matches = re.findall(pattern, response, re.DOTALL)
    return [
        {"title": m[0], "category": m[1], "content": m[2].strip()}
        for m in matches
    ]


def main():
    files_to_read = [
        "company/secretary-protocol.md",
        "company/decision-rules.md",
        "company/constitution.md",
        "dashboard/overview.md",
        "dashboard/active-projects.md",
        "dashboard/marketing-log.md",
        "dashboard/revenue-log.md",
        "dashboard/editorial-log.md",
        "company/departments/marketing.md",
        "company/departments/devops.md",
        "company/departments/revenue.md",
        "company/departments/editorial.md",
        "inbox/slack-messages.md",
        "inbox/raw-ideas.md",
        "projects/P001-ai-company-base/briefing.md",
        "projects/P003-news-timeline/briefing.md",
        "projects/P004-slack-bot/README.md",
        "docs/flotopic-launch-strategy.md",
        "docs/knowledge-and-ideas.md",
        "docs/google-oauth-setup.md",
        "dashboard/seo-log.md",
        "dashboard/weekly-digest-log.md",
    ]

    context_parts = []
    for f in files_to_read:
        content = read_file(f)
        context_parts.append(f"=== {f} ===\n{content}")
    context = "\n\n".join(context_parts)

    # CEOの過去判断履歴を参照
    print("[memory] CEOの過去判断履歴を読み込み中...")
    ceo_memory = load_ceo_memory(limit=5)
    print("[memory] 読み込み完了")

    prompt = f"""あなたはAI-Companyの秘書Claudeです。今日は{TODAY}です。
以下の会社ファイルを読んで、secretary-protocol.mdに記載されたStep1〜7の秘書業務を実行してください。
フェーズ移行条件の確認（flotopic-launch-strategy.md）も毎週Notionに同期すること。

{context}

=== CEOの最近の判断履歴（DynamoDB / 直近5件・参考情報） ===
{ceo_memory}

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

Notion 案件管理 DB の更新は以下のタグで出力すること（1案件につき1タグ）:
<NOTION_PROJECT page_id="Notionページ固有ID" status="稼働中 / 開発中 / 完了 など" next_action="次にやること" last_run="{TODAY}"/>

【Notion案件管理DBの更新対象】
- P003 ニュースタイムライン（通常案件）
- P004 Slackボット（通常案件）
- P005 メモリDB（通常案件）
- 専門AI: marketing-agent（マーケティングAI稼働状況を1案件として記録）
- 専門AI: revenue-agent（収益管理AI稼働状況を1案件として記録）
- 専門AI: editorial-agent（編集AIの稼働状況を1案件として記録）
- 専門AI: devops-agent（DevOpsアラート対応状況を1案件として記録）
  ※専門AIのpage_idは存在しない場合は空文字にし、Notion側で無視される

必ず以下の内容をNotionナレッジベースDBに記録すること（毎回必須）:

1. 専門AIステータスサマリー（各AIの最新状態・今日の実行結果）
<NOTION_KNOWLEDGE title="{TODAY} 専門AIステータス" category="運用">
各専門AIの今日の稼働状態・ログ要約・ブロッカーをここに書く（marketing/devops/revenue/editorial）
</NOTION_KNOWLEDGE>

2. 今週の主要KPI（P003稼働状況・収益・コスト）
<NOTION_KNOWLEDGE title="{TODAY} KPIサマリー" category="運用">
P003稼働状況・今週の収益見込み・コスト概算・その他KPIをここに書く
</NOTION_KNOWLEDGE>

3. ブロッカーと未解決問題（あれば）
<NOTION_KNOWLEDGE title="{TODAY} ブロッカー・未解決問題" category="運用">
現在のブロッカーと未解決問題の一覧をここに書く（なければ「なし」）
</NOTION_KNOWLEDGE>

4. 作業中に得た知見があれば追加で出力すること:
<NOTION_KNOWLEDGE title="知見のタイトル" category="技術 / 運用 / 設計 など">
知見の詳細内容をここに書く
</NOTION_KNOWLEDGE>

【絶対ルール】
- 出力できる <FILE> タグは上記5ファイルのみ。それ以外は一切出力禁止。
- frontend/ lambda/ scripts/ .github/ のコードファイルは絶対に変更しないこと。
- コードを改善・提案したい場合はSlackメッセージのみで報告すること。
- NOTION_KNOWLEDGEタグは必ず3件以上出力すること（専門AIステータス・KPI・ブロッカーは必須）。
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

    # Notion 同期（現フェーズでは無効化 — 将来再有効化する場合は以下のコメントを外す）
    # CLAUDE.mdとbriefing.mdが「完成図書」として機能するため現在は不要
    # try:
    #     notion_projects = parse_notion_project_blocks(response)
    #     notion_knowledge = parse_notion_knowledge_blocks(response)
    #     if NOTION_API_KEY:
    #         print(f"Notion同期開始: 案件={len(notion_projects)}件, ナレッジ={len(notion_knowledge)}件")
    #         for np in notion_projects:
    #             update_notion_project(
    #                 np["page_id"], np["status"], np["next_action"], np["last_run"]
    #             )
    #         for nk in notion_knowledge:
    #             add_knowledge_entry(nk["title"], nk["content"], nk["category"])
    #         print("Notion同期完了")
    #     else:
    #         print("NOTION_API_KEY未設定 - Notion同期スキップ")
    # except Exception as e:
    #     print(f"Notion同期中に予期せぬエラー（メイン処理は継続）: {e}")
    print("Notion同期スキップ（現フェーズでは無効化中）")

    # Slack通知は異常・要対応時のみ（正常完了は通知不要）
    # ファイル更新とDynamoDB記録で完了とする
    print(f"完了（{len(file_updates)}ファイル更新 / Slack通知スキップ）")


if __name__ == "__main__":
    main()
