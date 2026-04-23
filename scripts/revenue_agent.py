#!/usr/bin/env python3
"""AI-Company 収益管理エージェント - GitHub Actions から実行される"""
import json
import os
import re
import sys
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "ap-northeast-1")
REPO_ROOT = Path(__file__).parent.parent
REVENUE_LOG = REPO_ROOT / "dashboard" / "revenue-log.md"
TODAY = date.today()


# ---------------------------------------------------------------------------
# ユーティリティ
# ---------------------------------------------------------------------------

def read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        return f"[読み込みエラー: {e}]"


def call_claude(prompt: str, max_tokens: int = 1500) -> str:
    """Anthropic Messages API を urllib で呼び出す"""
    payload = json.dumps({
        "model": "claude-opus-4-6",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.loads(resp.read())
    return body["content"][0]["text"].strip()


def slack_notify(text: str) -> None:
    if not SLACK_WEBHOOK_URL:
        print("[slack] SLACK_WEBHOOK_URL が未設定のためスキップ")
        return
    payload = json.dumps({"text": text}).encode()
    req = urllib.request.Request(
        SLACK_WEBHOOK_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=15)
        print("[slack] 通知送信完了")
    except Exception as e:
        print(f"[slack] 送信失敗: {e}")


# ---------------------------------------------------------------------------
# AWS Cost Explorer
# ---------------------------------------------------------------------------

def get_aws_costs() -> dict:
    """
    当月のAWSコストをサービス別に取得する。
    IAM権限不足など例外が発生した場合は空dictを返してスキップ。
    返り値: {"total_jpy": float, "services": [{"name": str, "usd": float}, ...]}
    """
    try:
        import boto3
        ce = boto3.client("ce", region_name="us-east-1")  # Cost Explorer は us-east-1 固定
        start = TODAY.replace(day=1).isoformat()
        end = TODAY.isoformat()
        if start == end:
            # 月初1日の場合は前月データも含める
            import calendar
            prev_month = TODAY.month - 1 if TODAY.month > 1 else 12
            prev_year = TODAY.year if TODAY.month > 1 else TODAY.year - 1
            last_day = calendar.monthrange(prev_year, prev_month)[1]
            start = date(prev_year, prev_month, 1).isoformat()
            end = date(prev_year, prev_month, last_day).isoformat()

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
                service_name = group["Keys"][0]
                amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
                if amount > 0.001:
                    services.append({"name": service_name, "usd": amount})
                total_usd += amount
        # USD → JPY 簡易換算（固定レート 150円/USD）
        JPY_RATE = 150
        services.sort(key=lambda x: x["usd"], reverse=True)
        return {
            "total_usd": total_usd,
            "total_jpy": total_usd * JPY_RATE,
            "services": services,
            "period": f"{start} → {end}",
        }
    except Exception as e:
        print(f"[aws] Cost Explorer 取得失敗（スキップ）: {e}")
        return {}


# ---------------------------------------------------------------------------
# 収益ログ解析
# ---------------------------------------------------------------------------

def parse_revenue_log(content: str) -> dict:
    """
    revenue-log.md から最新月の数値を正規表現で抽出する。
    返り値: {"revenue_jpy": int, "aws_jpy": int, "anthropic_jpy": int, "profit_jpy": int}
    """
    result = {"revenue_jpy": 0, "aws_jpy": 0, "anthropic_jpy": 0, "profit_jpy": 0}

    def extract_yen(pattern: str, text: str) -> int:
        m = re.search(pattern, text)
        if m:
            val = m.group(1).replace(",", "").replace("，", "")
            try:
                return int(val)
            except ValueError:
                return 0
        return 0

    # 最新月のセクションだけ対象にする（最後の ## 2026年X月 ブロック）
    sections = re.split(r"(?=^## \d{4}年\d+月)", content, flags=re.MULTILINE)
    latest = sections[-1] if sections else content

    result["revenue_jpy"] = extract_yen(r"収益[:：]\s*[¥￥]?([\d,]+)", latest)
    result["aws_jpy"] = extract_yen(r"AWS.*?コスト[:：]\s*[¥￥]?([\d,]+)", latest)
    result["anthropic_jpy"] = extract_yen(r"Anthropic.*?コスト[:：]\s*[¥￥]?([\d,]+)", latest)
    result["profit_jpy"] = extract_yen(r"損益[:：]\s*[-−]?[¥￥]?([\d,]+)", latest)
    # 損益は負の可能性あり
    if "損益" in latest:
        m = re.search(r"損益[:：]\s*([-−]?[¥￥]?[\d,]+)", latest)
        if m:
            raw = m.group(1).replace("¥", "").replace("￥", "").replace(",", "").replace("，", "")
            try:
                result["profit_jpy"] = int(raw.replace("−", "-"))
            except ValueError:
                pass

    return result


# ---------------------------------------------------------------------------
# Claude による分析
# ---------------------------------------------------------------------------

def analyze_with_claude(
    revenue_log: str,
    aws_costs: dict,
    parsed: dict,
) -> str:
    aws_section = ""
    if aws_costs:
        lines = [f"- {s['name']}: ${s['usd']:.4f} (¥{int(s['usd']*150):,})" for s in aws_costs["services"][:10]]
        aws_section = f"""
## AWS実コスト（Cost Explorer取得）
- 期間: {aws_costs['period']}
- 合計: ${aws_costs['total_usd']:.4f} (¥{int(aws_costs['total_jpy']):,})
サービス別:
{chr(10).join(lines)}
"""
    else:
        aws_section = "## AWS実コスト\n- 取得失敗（IAM権限不足の可能性）\n"

    prompt = f"""あなたはAI-Companyの財務アナリストです。以下のデータを元に収益分析を行い、日本語で報告書を作成してください。

{aws_section}

## 収益ログ（直近）
{revenue_log[-2000:]}

## 解析値（最新月）
- 収益: ¥{parsed['revenue_jpy']:,}
- AWS推定コスト: ¥{parsed['aws_jpy']:,}
- Anthropic API推定コスト: ¥{parsed['anthropic_jpy']:,}
- 損益: ¥{parsed['profit_jpy']:,}

## 分析してほしい内容
1. **今月の損益サマリー**（収益 - コスト合計）
2. **コスト削減の具体的提案**（AWSサービス別に無駄があれば指摘）
3. **収益改善の具体的提案**（広告収益・新規収益源）
4. **総合評価**（試作 / ベータ / 完成候補 のいずれか＋理由）

箇条書きで簡潔にまとめてください。全体で500字以内。"""

    print("[claude] 分析リクエスト送信中...")
    return call_claude(prompt, max_tokens=1000)


# ---------------------------------------------------------------------------
# ログ追記
# ---------------------------------------------------------------------------

def append_to_log(analysis: str, aws_costs: dict, parsed: dict) -> None:
    from datetime import timedelta
    JST = timezone(timedelta(hours=9))
    jst_now = datetime.now(JST)
    timestamp = jst_now.strftime("%Y-%m-%d %H:%M JST")

    aws_summary = ""
    if aws_costs:
        aws_summary = f"- AWS実コスト（自動取得）: ¥{int(aws_costs['total_jpy']):,}（${aws_costs['total_usd']:.4f}）\n"
    else:
        aws_summary = "- AWS実コスト: 取得失敗\n"

    entry = f"""
---

### 自動レポート {timestamp}

{aws_summary}- 収益（ログ読み取り）: ¥{parsed['revenue_jpy']:,}
- Anthropic APIコスト（ログ読み取り）: ¥{parsed['anthropic_jpy']:,}

#### Claude分析
{analysis}
"""
    current = REVENUE_LOG.read_text(encoding="utf-8")
    REVENUE_LOG.write_text(current + entry, encoding="utf-8")
    print(f"[log] revenue-log.md に追記しました")


# ---------------------------------------------------------------------------
# Slack 月次レポート
# ---------------------------------------------------------------------------

def build_slack_monthly_report(analysis: str, aws_costs: dict, parsed: dict) -> str:
    month = TODAY.strftime("%Y年%-m月")
    aws_line = f"¥{int(aws_costs['total_jpy']):,}" if aws_costs else "取得失敗"
    profit = parsed["revenue_jpy"] - parsed["aws_jpy"] - parsed["anthropic_jpy"]
    sign = "+" if profit >= 0 else ""
    report = f"""📊 *AI-Company 月次収益レポート（{month}）*

💰 収益: ¥{parsed['revenue_jpy']:,}
☁️ AWSコスト（実績）: {aws_line}
🤖 Anthropic APIコスト: ¥{parsed['anthropic_jpy']:,}
📉 損益: {sign}¥{profit:,}

{analysis[:600]}

詳細 → dashboard/revenue-log.md"""
    return report


# ---------------------------------------------------------------------------
# メイン
# ---------------------------------------------------------------------------

def main():
    print(f"[revenue_agent] 実行開始: {TODAY.isoformat()}")
    is_first_of_month = (TODAY.day == 1)

    # 1. AWSコスト取得
    print("[step 1] AWS Cost Explorer 取得...")
    aws_costs = get_aws_costs()
    if aws_costs:
        print(f"  → 合計: ${aws_costs['total_usd']:.4f} (¥{int(aws_costs['total_jpy']):,})")
    else:
        print("  → スキップ（権限不足など）")

    # 2. 収益ログ読み取り
    print("[step 2] 収益ログ読み取り...")
    revenue_log_content = read_file(REVENUE_LOG)
    parsed = parse_revenue_log(revenue_log_content)
    print(f"  → 収益: ¥{parsed['revenue_jpy']:,} / 損益: ¥{parsed['profit_jpy']:,}")

    # 3. Claude分析
    print("[step 3] Claude で分析...")
    analysis = analyze_with_claude(revenue_log_content, aws_costs, parsed)
    print(f"  → 分析完了 ({len(analysis)}文字)")

    # 4. ログ追記
    print("[step 4] ログ追記...")
    append_to_log(analysis, aws_costs, parsed)

    # 5. 月初のみSlack月次レポート
    if is_first_of_month:
        print("[step 5] 月初 → Slack月次レポート送信...")
        report = build_slack_monthly_report(analysis, aws_costs, parsed)
        slack_notify(report)
    else:
        print("[step 5] 月初以外 → Slack通知スキップ")

    print("[revenue_agent] 完了")


if __name__ == "__main__":
    main()
