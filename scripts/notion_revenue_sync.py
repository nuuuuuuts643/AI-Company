#!/usr/bin/env python3
"""Notion 収益・コストダッシュボード同期スクリプト

月次の収益・コストデータを Notion データベースに同期する。
初回実行時に "収益・コスト管理" データベースを自動作成する。
"""
import json
import os
import re
import sys
from datetime import date, timedelta, timezone
from pathlib import Path
import urllib.request
import urllib.error

NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_DB_KNOWLEDGE = "53a98e27-1f97-443e-a491-42e5e2a867f9"
NOTION_PARENT_PAGE_ID = "3488fff7-e9cf-8136-9f3c-d09eac556ce9"  # AI-Company ダッシュボード
DB_TITLE = "収益・コスト管理"

REPO_ROOT = Path(__file__).parent.parent
REVENUE_LOG = REPO_ROOT / "dashboard" / "revenue-log.md"
TODAY = date.today()
JPY_RATE = 150


# ---------------------------------------------------------------------------
# Notion API
# ---------------------------------------------------------------------------

def notion_request(method: str, endpoint: str, payload: dict = None) -> dict:
    if not NOTION_API_KEY:
        print("[notion] NOTION_API_KEY 未設定 - スキップ")
        return {}
    url = f"https://api.notion.com/v1/{endpoint}"
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {NOTION_API_KEY}")
    req.add_header("Notion-Version", "2022-06-28")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"[notion] {method} {endpoint} HTTP {e.code}: {body[:300]}")
        return {}
    except Exception as e:
        print(f"[notion] {method} {endpoint} 失敗: {e}")
        return {}


def find_revenue_db() -> str:
    """ワークスペース内から収益DBを名前検索"""
    resp = notion_request("POST", "search", {
        "query": DB_TITLE,
        "filter": {"value": "database", "property": "object"},
    })
    for item in resp.get("results", []):
        title_parts = item.get("title", [])
        name = title_parts[0].get("plain_text", "") if title_parts else ""
        if name == DB_TITLE:
            print(f"[notion] 既存の収益DB発見: {item['id']}")
            return item["id"]
    return ""


def create_revenue_database() -> str:
    """収益管理データベースを AI-Company ダッシュボードページ内に作成"""
    parent = {"type": "page_id", "page_id": NOTION_PARENT_PAGE_ID}

    payload = {
        "parent": parent,
        "icon": {"type": "emoji", "emoji": "📊"},
        "title": [{"type": "text", "text": {"content": DB_TITLE}}],
        "properties": {
            "月": {"title": {}},
            "収益 (¥)": {"number": {"format": "yen"}},
            "AWSコスト (¥)": {"number": {"format": "yen"}},
            "Anthropic APIコスト (¥)": {"number": {"format": "yen"}},
            "合計コスト (¥)": {"number": {"format": "yen"}},
            "損益 (¥)": {"number": {"format": "yen"}},
            "ステータス": {
                "select": {
                    "options": [
                        {"name": "🔴 赤字", "color": "red"},
                        {"name": "🟡 ±0", "color": "yellow"},
                        {"name": "🟢 黒字", "color": "green"},
                    ]
                }
            },
            "Claude分析": {"rich_text": {}},
        },
    }
    resp = notion_request("POST", "databases", payload)
    db_id = resp.get("id", "")
    if db_id:
        print(f"[notion] 収益DB作成完了: {db_id}")
        # GitHub Actions: 次回以降のために output に書き出す
        gh_output = os.environ.get("GITHUB_OUTPUT", "")
        if gh_output:
            with open(gh_output, "a") as f:
                f.write(f"notion_db_revenue={db_id}\n")
    else:
        print("[notion] DB作成失敗")
    return db_id


def get_or_create_revenue_db() -> str:
    db_id = os.environ.get("NOTION_DB_REVENUE", "") or find_revenue_db()
    if db_id:
        return db_id
    print("[notion] 収益DBが存在しないため新規作成します")
    return create_revenue_database()


# ---------------------------------------------------------------------------
# データ取得
# ---------------------------------------------------------------------------

def get_aws_costs() -> dict:
    try:
        import boto3
        ce = boto3.client("ce", region_name="us-east-1")
        start = TODAY.replace(day=1).isoformat()
        end = TODAY.isoformat()
        if start == end:
            import calendar
            pm = TODAY.month - 1 if TODAY.month > 1 else 12
            py = TODAY.year if TODAY.month > 1 else TODAY.year - 1
            end = date(py, pm, calendar.monthrange(py, pm)[1]).isoformat()
            start = date(py, pm, 1).isoformat()

        resp = ce.get_cost_and_usage(
            TimePeriod={"Start": start, "End": end},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )
        services = []
        total_usd = 0.0
        for result in resp.get("ResultsByTime", []):
            for group in result.get("Groups", []):
                amt = float(group["Metrics"]["UnblendedCost"]["Amount"])
                total_usd += amt
                if amt > 0.001:
                    services.append({"name": group["Keys"][0], "usd": amt})
        services.sort(key=lambda x: x["usd"], reverse=True)
        return {
            "total_jpy": int(total_usd * JPY_RATE),
            "total_usd": total_usd,
            "services": services,
            "period": f"{start} → {end}",
        }
    except Exception as e:
        print(f"[aws] Cost Explorer 取得失敗: {e}")
        return {}


def parse_revenue_log() -> dict:
    try:
        content = REVENUE_LOG.read_text(encoding="utf-8")
    except Exception as e:
        print(f"[log] 読み込み失敗: {e}")
        return {}

    sections = re.split(r"(?=^## \d{4}年\d+月)", content, flags=re.MULTILINE)
    latest = sections[-1] if sections else content

    def yen(pattern, text):
        m = re.search(pattern, text)
        if not m:
            return 0
        try:
            return int(m.group(1).replace(",", "").replace("，", ""))
        except ValueError:
            return 0

    revenue = yen(r"収益[:：]\s*[¥￥]?([\d,]+)", latest)
    aws = yen(r"AWS.*?コスト[:：]\s*[¥￥]?([\d,]+)", latest)
    anthropic = yen(r"Anthropic.*?コスト[:：]\s*[¥￥]?([\d,]+)", latest)

    analysis_m = re.search(r"#### Claude分析\n(.*?)(?=\n---|$)", latest, re.DOTALL)
    analysis = analysis_m.group(1).strip() if analysis_m else ""

    return {
        "revenue": revenue,
        "aws_cost": aws,
        "anthropic_cost": anthropic,
        "analysis": analysis,
    }


# ---------------------------------------------------------------------------
# Notion ページ同期
# ---------------------------------------------------------------------------

def _bar(value: float, max_val: float, width: int = 16) -> str:
    if max_val <= 0:
        return "░" * width
    filled = round((value / max_val) * width)
    return "█" * filled + "░" * (width - filled)


def _rich(text: str) -> list:
    return [{"type": "text", "text": {"content": text}}]


def _heading(level: int, text: str) -> dict:
    key = f"heading_{level}"
    return {"object": "block", "type": key, key: {"rich_text": _rich(text)}}


def _bullet(text: str) -> dict:
    return {"object": "block", "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": _rich(text)}}


def _code(text: str) -> dict:
    return {"object": "block", "type": "code",
            "code": {"rich_text": _rich(text), "language": "plain text"}}


def _callout(text: str, emoji: str, color: str) -> dict:
    return {"object": "block", "type": "callout",
            "callout": {"rich_text": _rich(text), "icon": {"type": "emoji", "emoji": emoji}, "color": color}}


def _divider() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


def build_page_blocks(data: dict, aws_costs: dict) -> list:
    revenue = data["revenue"]
    aws_cost = data["aws_cost"]
    anthropic_cost = data["anthropic_cost"]
    total_cost = aws_cost + anthropic_cost
    profit = revenue - total_cost

    # テキストバーチャート
    max_val = max(revenue, total_cost, 1)
    chart_lines = [
        f"収益      {_bar(revenue, max_val)}  ¥{revenue:,}",
        f"AWSコスト {_bar(aws_cost, max_val)}  ¥{aws_cost:,}",
        f"API費用   {_bar(anthropic_cost, max_val)}  ¥{anthropic_cost:,}",
        f"{'─'*40}",
        f"損益      {'▲ -' if profit < 0 else '▶ +'}¥{abs(profit):,}",
    ]

    callout_color = "red_background" if profit < 0 else "green_background"
    callout_emoji = "🔴" if profit < 0 else "🟢"
    callout_text = f"収益: ¥{revenue:,}  /  コスト: ¥{total_cost:,}  /  損益: {'▲' if profit < 0 else '▶'} ¥{abs(profit):,}"

    blocks = [
        _callout(callout_text, callout_emoji, callout_color),
        _divider(),
        _heading(2, "📊 収支バーチャート"),
        _code("\n".join(chart_lines)),
        _divider(),
    ]

    # AWS サービス別内訳
    if aws_costs and aws_costs.get("services"):
        blocks.append(_heading(2, "☁️ AWSコスト内訳"))
        max_usd = aws_costs["services"][0]["usd"]
        for s in aws_costs["services"][:10]:
            jpy = int(s["usd"] * JPY_RATE)
            bar = _bar(s["usd"], max_usd, 12)
            blocks.append(_bullet(f"{bar}  {s['name']}: ${s['usd']:.4f}  (¥{jpy:,})"))
        blocks.append(_divider())

    # Claude 分析
    if data.get("analysis"):
        blocks.append(_heading(2, "🤖 Claude分析"))
        # 2000文字ずつに分割（Notion制限）
        analysis = data["analysis"]
        for i in range(0, min(len(analysis), 4000), 2000):
            blocks.append({
                "object": "block", "type": "paragraph",
                "paragraph": {"rich_text": _rich(analysis[i:i+2000])},
            })

    return blocks


def find_monthly_page(db_id: str, month_label: str) -> str:
    resp = notion_request("POST", f"databases/{db_id}/query", {
        "filter": {"property": "月", "title": {"equals": month_label}}
    })
    results = resp.get("results", [])
    return results[0]["id"] if results else ""


def upsert_monthly_page(db_id: str, data: dict, aws_costs: dict) -> None:
    month_label = TODAY.strftime("%Y年%-m月")
    aws_jpy = aws_costs["total_jpy"] if aws_costs else data["aws_cost"]
    anthropic_jpy = data["anthropic_cost"]
    total_cost = aws_jpy + anthropic_jpy
    profit = data["revenue"] - total_cost

    if profit > 0:
        status = "🟢 黒字"
    elif profit == 0:
        status = "🟡 ±0"
    else:
        status = "🔴 赤字"

    # AWS実コストで上書き
    data = {**data, "aws_cost": aws_jpy}

    props = {
        "月": {"title": [{"text": {"content": month_label}}]},
        "収益 (¥)": {"number": data["revenue"]},
        "AWSコスト (¥)": {"number": aws_jpy},
        "Anthropic APIコスト (¥)": {"number": anthropic_jpy},
        "合計コスト (¥)": {"number": total_cost},
        "損益 (¥)": {"number": profit},
        "ステータス": {"select": {"name": status}},
        "Claude分析": {"rich_text": [{"text": {"content": data.get("analysis", "")[:2000]}}]},
    }

    blocks = build_page_blocks(data, aws_costs)
    existing_id = find_monthly_page(db_id, month_label)

    if existing_id:
        notion_request("PATCH", f"pages/{existing_id}", {"properties": props, "icon": {"type": "emoji", "emoji": "📅"}})
        print(f"[notion] {month_label} 更新完了 ({existing_id})")
        # ページ本文を差し替え（既存ブロックを全削除して再作成）
        _replace_page_content(existing_id, blocks)
    else:
        payload = {
            "parent": {"database_id": db_id},
            "icon": {"type": "emoji", "emoji": "📅"},
            "properties": props,
            "children": blocks,
        }
        resp = notion_request("POST", "pages", payload)
        pid = resp.get("id", "N/A")
        print(f"[notion] {month_label} 新規作成完了 ({pid})")


def _replace_page_content(page_id: str, new_blocks: list) -> None:
    """ページ内の既存ブロックを全削除してから新しいブロックを追加"""
    resp = notion_request("GET", f"blocks/{page_id}/children")
    for block in resp.get("results", []):
        notion_request("DELETE", f"blocks/{block['id']}")
    # 100ブロック以内に収める（Notion API制限）
    notion_request("PATCH", f"blocks/{page_id}/children", {"children": new_blocks[:100]})


# ---------------------------------------------------------------------------
# メイン
# ---------------------------------------------------------------------------

def main():
    if not NOTION_API_KEY:
        print("[notion_revenue_sync] NOTION_API_KEY 未設定 - 終了")
        sys.exit(0)

    print(f"[notion_revenue_sync] 開始: {TODAY.isoformat()}")

    print("[1] AWSコスト取得...")
    aws_costs = get_aws_costs()
    if aws_costs:
        print(f"    合計: ${aws_costs['total_usd']:.4f} (¥{aws_costs['total_jpy']:,})")
    else:
        print("    取得失敗（スキップ）")

    print("[2] 収益ログ解析...")
    data = parse_revenue_log()
    if not data:
        data = {"revenue": 0, "aws_cost": 0, "anthropic_cost": 0, "analysis": ""}
    print(f"    収益: ¥{data['revenue']:,} / AWS: ¥{data['aws_cost']:,} / API: ¥{data['anthropic_cost']:,}")

    print("[3] Notion DB 取得/作成...")
    db_id = get_or_create_revenue_db()
    if not db_id:
        print("    DB取得・作成失敗 - 終了")
        sys.exit(1)
    print(f"    DB ID: {db_id}")

    print("[4] 月次ページ同期...")
    upsert_monthly_page(db_id, data, aws_costs)

    print("[notion_revenue_sync] 完了")


if __name__ == "__main__":
    main()
