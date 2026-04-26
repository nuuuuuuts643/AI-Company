#!/usr/bin/env python3
"""AI-Company CEO スクリプト - GitHub Actions から実行される"""
import json
import os
import re
import sys
from pathlib import Path
import urllib.request
from datetime import date, datetime, timezone

ANTHROPIC_API_KEY = os.environ['ANTHROPIC_API_KEY']
SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL', '')
REPO_ROOT = Path(__file__).parent.parent
TODAY = date.today().isoformat()

# DynamoDB設定
MEMORY_TABLE = "ai-company-memory"
MEMORY_PK = "CEO_MEMORY"
AWS_REGION = os.environ.get('AWS_DEFAULT_REGION', 'ap-northeast-1')


def load_memory(limit=10):
    """DynamoDBから最近のCEO判断履歴を読み込む（失敗してもメイン処理は続行）"""
    try:
        import boto3
        from boto3.dynamodb.conditions import Key
        dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
        table = dynamodb.Table(MEMORY_TABLE)
        resp = table.query(
            KeyConditionExpression=Key('pk').eq(MEMORY_PK),
            ScanIndexForward=False,  # 降順（新しい順）
            Limit=limit
        )
        items = resp.get('Items', [])
        if not items:
            return "(過去の記憶なし)"
        lines = []
        for item in items:
            sk = item.get('sk', '')
            summary = item.get('summary', '（サマリーなし）')
            lines.append(f"- [{sk}] {summary}")
        return "\n".join(lines)
    except Exception as e:
        print(f"[memory] load_memory失敗（メイン処理は継続）: {e}")
        return "(メモリ読み込み失敗)"


def save_memory(summary, proposals_count=0, files_updated=0):
    """CEOの判断サマリーをDynamoDBに保存する（失敗してもメイン処理は続行）"""
    try:
        import boto3
        dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
        table = dynamodb.Table(MEMORY_TABLE)
        sk = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
        table.put_item(Item={
            'pk': MEMORY_PK,
            'sk': sk,
            'date': TODAY,
            'summary': summary,
            'proposals_count': proposals_count,
            'files_updated': files_updated,
        })
        print(f"[memory] 判断サマリーを保存しました (sk={sk})")
    except Exception as e:
        print(f"[memory] save_memory失敗（メイン処理は継続）: {e}")


def read_file(rel_path):
    try:
        return (REPO_ROOT / rel_path).read_text(encoding='utf-8')
    except Exception as e:
        return f"[読み込みエラー: {e}]"


def compute_audience_analysis():
    """
    DynamoDB flotopic-analytics テーブルから直近7日間の新規/リピーター比率を集計し、
    CEO向けの読者品質分析テキストを返す。失敗時は空文字を返す。
    """
    try:
        import boto3
        from boto3.dynamodb.conditions import Attr
        from collections import defaultdict
        import time

        dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
        table = dynamodb.Table('flotopic-analytics')
        since = int(time.time()) - 86400 * 7  # 7日前

        counts = defaultdict(lambda: {'views': 0, 'new_viewers': 0})
        paginator_kwargs = {
            'FilterExpression': Attr('timestamp').gte(since) & Attr('topicId').exists(),
        }
        last_key = None
        while True:
            if last_key:
                paginator_kwargs['ExclusiveStartKey'] = last_key
            result = table.scan(**paginator_kwargs)
            for item in result.get('Items', []):
                tid = item.get('topicId', '')
                event_type = item.get('eventType', '')
                if not tid:
                    continue
                if event_type in ('view', 'topic_click', 'page_view'):
                    counts[tid]['views'] += 1
                    if item.get('isNewViewer'):
                        counts[tid]['new_viewers'] += 1
            last_key = result.get('LastEvaluatedKey')
            if not last_key:
                break

        if not counts:
            return ""

        # new_viewer_ratio 付きリスト
        topics = []
        for tid, v in counts.items():
            total = v['views']
            new_v = v['new_viewers']
            ratio = round(new_v / total, 2) if total > 0 else 0
            topics.append({'topicId': tid, 'views': total, 'new_viewers': new_v, 'ratio': ratio})

        # Top5: バイラル（新規率高い順）
        viral = sorted([t for t in topics if t['views'] >= 5], key=lambda x: x['ratio'], reverse=True)[:5]
        viral_text = ', '.join([f"{t['topicId']}（新規率{int(t['ratio']*100)}%/計{t['views']}views）" for t in viral]) or 'なし'

        # Top5: 総ビュー数（人気順）
        popular = sorted(topics, key=lambda x: x['views'], reverse=True)[:5]
        popular_text = ', '.join([f"{t['topicId']}（{t['views']}views/新規率{int(t['ratio']*100)}%）" for t in popular]) or 'なし'

        # 固定読者トラップ（新規率 < 30% かつ総ビュー > 100）
        loyal_trap = [t for t in topics if t['ratio'] < 0.3 and t['views'] > 100]
        loyal_text = ', '.join([f"{t['topicId']}（{t['views']}views/新規率{int(t['ratio']*100)}%）" for t in loyal_trap]) or 'なし'

        return f"""
## 読者分析（先週 / flotopic-analytics）
新規読者率が高いトピック（本当にバイラルなもの）：{viral_text}
総ビュー数は高いがリピーターが多いトピック（固定読者）：{popular_text}
固定読者トラップ（新規率<30% かつ total>100views）：{loyal_text}

→ スコアリング調整提案：新規率>60%のトピックに急上昇ブーストを適用すべきか判断する
"""
    except Exception as e:
        print(f"[audience] 読者分析失敗（メイン処理は継続）: {e}")
        return ""


def check_p003_health():
    """P003のS3データが正常に更新されているかチェックする"""
    # flotopic.comが稼働していればそちらを優先チェック
    urls_to_try = [
        "https://flotopic.com/api/topics.json",
        "http://p003-news-946554699567.s3-website-ap-northeast-1.amazonaws.com/api/topics.json",
    ]
    url = urls_to_try[0]
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AI-Company-CEO-HealthCheck/1.0"})
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read())
        last_updated = data.get("last_updated", "")
        topic_count = len(data.get("topics", []))
        if last_updated:
            from datetime import datetime, timezone, timedelta
            try:
                updated_dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                age_hours = (now - updated_dt).total_seconds() / 3600
                if age_hours > 2:
                    return f"⚠️ P003データが{age_hours:.1f}時間前から更新停止（トピック数: {topic_count}）"
                return f"✅ P003正常稼働中（最終更新: {age_hours:.1f}時間前、トピック数: {topic_count}）"
            except Exception:
                pass
        return f"✅ P003応答あり（トピック数: {topic_count}）"
    except Exception as e:
        return f"🚨 P003アクセス不能: {e}"


def call_claude(prompt):
    data = json.dumps({
        "model": "claude-sonnet-4-6",
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


def parse_proposals(response):
    """
    <PROPOSAL id="XXX">内容</PROPOSAL> 形式で提案を抽出する
    提案リストをまとめて返す
    """
    pattern = r'<PROPOSAL id="([^"]+)">(.*?)</PROPOSAL>'
    matches = re.findall(pattern, response, re.DOTALL)
    return [{"id": m[0], "content": m[1].strip()} for m in matches]


def write_proposals_to_inbox(proposals):
    """提案を inbox/ceo-proposals.md に追記する"""
    if not proposals:
        return

    proposals_path = REPO_ROOT / "inbox" / "ceo-proposals.md"
    try:
        existing = proposals_path.read_text(encoding='utf-8')
    except Exception:
        existing = "# CEO提案ログ\n\n"

    new_entries = []
    for p in proposals:
        entry = f"\n---\n\n## 提案#{p['id']} （{TODAY}）\n\n{p['content']}\n\nステータス: 承認待ち\n"
        new_entries.append(entry)

    updated = existing + "\n".join(new_entries)
    proposals_path.write_text(updated, encoding='utf-8')
    print(f"提案 {len(proposals)} 件を inbox/ceo-proposals.md に記録しました")


def validate_file_path(path):
    """
    出力可能なファイルパスかチェックする。
    frontend/ lambda/ scripts/ .github/ は絶対禁止。
    dashboard系・inbox系・briefing.mdのみ許可。
    """
    forbidden_prefixes = [
        "frontend/",
        "lambda/",
        "scripts/",
        ".github/",
    ]
    allowed_prefixes = [
        "dashboard/",
        "inbox/",
        "projects/",
        "company/",
    ]
    # 絶対禁止チェック
    for prefix in forbidden_prefixes:
        if path.startswith(prefix):
            print(f"警告: 禁止パス '{path}' をスキップします")
            return False
    # 許可リストチェック（projects/ は briefing.md のみ）
    for prefix in allowed_prefixes:
        if path.startswith(prefix):
            if prefix == "projects/":
                return path.endswith("briefing.md")
            return True
    print(f"警告: 許可外パス '{path}' をスキップします")
    return False


def main():
    files_to_read = [
        "company/ceo-constitution.md",
        "company/constitution.md",
        "dashboard/overview.md",
        "dashboard/active-projects.md",
        "projects/P003-news-timeline/briefing.md",
        "inbox/slack-messages.md",
        "inbox/ceo-proposals.md",
        "docs/flotopic-launch-strategy.md",
        "docs/knowledge-and-ideas.md",
        "company/departments/marketing.md",
        "company/departments/devops.md",
        "company/departments/revenue.md",
        "company/departments/editorial.md",
        "dashboard/marketing-log.md",
        "dashboard/revenue-log.md",
        "dashboard/seo-log.md",
    ]

    context_parts = []
    for f in files_to_read:
        content = read_file(f)
        context_parts.append(f"=== {f} ===\n{content}")
    context = "\n\n".join(context_parts)

    # 既存の提案ログも読み込む（重複提案を避けるため）
    existing_proposals = read_file("inbox/ceo-proposals.md")

    # DynamoDBから過去の判断履歴を読み込む
    print("[memory] 過去の判断履歴を読み込み中...")
    memory_context = load_memory(limit=10)
    print(f"[memory] 読み込み完了")

    # P003ヘルスチェック
    print("[health] P003稼働確認中...")
    p003_health = check_p003_health()
    print(f"[health] {p003_health}")

    # 読者品質分析（DynamoDB flotopic-analytics）
    print("[audience] 読者分析中...")
    audience_analysis = compute_audience_analysis()
    print(f"[audience] 完了 ({'データあり' if audience_analysis else 'データなし/エラー'})")

    prompt = f"""あなたはAI-CompanyのCEO Claudeです。今日は{TODAY}です。
ナオヤさんは出資者・取締役として、あなたの提案を承認する立場です。
あなたは事業執行者として、自律的に会社を動かします。

【最重要姿勢】
ナオヤが思いつくような一般的な改善・次の一手は、すべてあなたが先に考えて提案済みにしておくこと。
「ユーザーが増えたらコメント解禁」「収益化は流入が安定してから」「セキュリティは後で」のような
フェーズ判断を自律的に行い、条件が揃ったら即座に提案を出す。
docs/flotopic-launch-strategy.md のKPI閾値を毎日チェックし、移行条件を満たしていれば提案を出す。
手を止めることはCEO失格。常に次の一手を考え、動き続けること。

以下の会社ファイルを読んで、ceo-constitution.mdに記載されたデイリールーティンを実行してください。

{context}

=== 過去の判断履歴（DynamoDB / 直近10件・新しい順） ===
{memory_context}

=== インフラヘルスチェック（リアルタイム） ===
{p003_health}

=== 読者品質分析（直近7日間・DynamoDB flotopic-analytics） ==={audience_analysis if audience_analysis else "（データ未蓄積またはアクセス不能）"}

=== 既存の提案ログ（重複登録を避けるために参照） ===
{existing_proposals}

---

【実行フロー】
1. 全ファイルを読んで現状を把握する
2. 問題・改善点・チャンスを分析する
3. アクションを2種類に分類する：
   - 即時実行（小修正・ドキュメント更新など承認不要のもの）→ <EXECUTE> タグで記録
   - 出資者への提案（コスト増加・コード変更・新規投資など）→ <PROPOSAL id="XXX"> タグで記録
4. ダッシュボードを更新する
5. Slackに報告する（実行したこと + 提案リスト）

---

全ての分析・判断を終えたら、以下の形式で出力してください。

即時実行したアクションは <EXECUTE> タグで記録:
<EXECUTE>
- ダッシュボードの overview.md を最新状態に更新した
- briefing.md の last_run を更新した
</EXECUTE>

出資者への提案は <PROPOSAL id="XXX"> タグで記録（番号は001から順番に）:
<PROPOSAL id="001">
タイトル: P003に広告スロットを追加したい
内容: P003のフロントエンドにGoogle AdSense広告を追加する
理由: 月間PVが増加しており収益化のタイミング
想定効果: 月3,000〜5,000円の収益
想定コスト: Google AdSense審査（無料）+ 実装工数
</PROPOSAL>

更新するファイルは <FILE path="相対パス"> タグで囲んでください:
<FILE path="dashboard/overview.md">
ファイルの全内容をここに書く
</FILE>

Slackへの報告は <SLACK> タグで囲んでください:
<SLACK>
【CEO日次レポート】{TODAY}

■ 本日実行したこと
  - ...

■ 出資者への提案（承認待ち）
  提案#001: [タイトル]（想定効果: ...）
  → 承認はCoworkのチャットで「承認 #001」と伝えてください
  ※提案がない場合は「なし」

■ KPI
  - アクティブプロジェクト数: X件
  - ブロッカー件数: X件
  - 未処理の提案数: X件
</SLACK>

必ず以下のファイルを <FILE> タグで出力すること:
- dashboard/overview.md
- dashboard/active-projects.md
- projects/P003-news-timeline/briefing.md（last_run を更新）
- inbox/slack-messages.md（処理済みに ✅ を追加）

【絶対ルール】
- 出力できる <FILE> タグは上記4ファイルのみ。それ以外は一切出力禁止。
- frontend/ lambda/ scripts/ .github/ のコードファイルは絶対に変更しないこと。
- コードを改善・提案したい場合は <PROPOSAL> タグと Slack メッセージのみで報告すること。
- inbox/ceo-proposals.md は <FILE> タグで出力せず、<PROPOSAL> タグのみを使うこと（スクリプトが自動追記する）。
"""

    print(f"CEO Claude API呼び出し中... ({TODAY})")
    response = call_claude(prompt)
    print("レスポンス受信完了")

    # 提案を抽出して inbox/ceo-proposals.md に追記
    proposals = parse_proposals(response)
    if proposals:
        write_proposals_to_inbox(proposals)
    else:
        print("本日の提案: なし")

    # ファイル更新を抽出（許可パスのみ）
    raw_file_updates = parse_file_blocks(response)
    file_updates = [u for u in raw_file_updates if validate_file_path(u["path"])]

    if not file_updates:
        print("警告: 有効なファイル更新が見つかりませんでした")
        print(f"レスポンス冒頭: {response[:200]}")
        send_slack(f"【AI-Company CEOエラー】{TODAY}\nファイル更新の抽出に失敗しました。手動確認が必要です。")
        sys.exit(1)

    # ファイル書き込み
    for update in file_updates:
        path = REPO_ROOT / update["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(update["content"], encoding="utf-8")
        print(f"更新: {update['path']}")

    # Slack通知（提案がある場合 or P003異常の場合のみ送信）
    slack_msg = parse_slack_block(response)
    has_action = bool(proposals) or ("⚠️" in p003_health or "🚨" in p003_health)
    if has_action:
        if not slack_msg:
            slack_msg = (
                f"【AI-Company CEO提案】{TODAY}\n"
                f"新規提案 {len(proposals)} 件 / インフラ状態: {p003_health}\n"
                f"Coworkチャットで「承認 #XXX」と返信してください。"
            )
        send_slack(slack_msg)
    else:
        print(f"提案なし・インフラ正常 → Slack通知スキップ（{len(file_updates)}ファイル更新完了）")

    # 今回の判断サマリーをDynamoDBに保存
    print("[memory] 判断サマリーをDynamoDBに保存中...")
    # EXECUTE タグからサマリーを抽出、なければ件数ベースの要約を使用
    execute_match = re.search(r'<EXECUTE>(.*?)</EXECUTE>', response, re.DOTALL)
    if execute_match:
        execute_summary = execute_match.group(1).strip()[:500]  # 500文字以内
    else:
        execute_summary = f"ファイル{len(file_updates)}件更新、提案{len(proposals)}件"
    save_memory(
        summary=execute_summary,
        proposals_count=len(proposals),
        files_updated=len(file_updates),
    )

    print("完了")


if __name__ == "__main__":
    main()
