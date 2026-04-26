#!/usr/bin/env python3
"""
devops_agent.py — AI-Company 開発監視AI

Claude呼び出し回数: 0回/実行 (通常時)
条件: HIGH severity かつ DynamoDB未学習パターン の場合のみ呼び出し（月数回想定）

## 監視対象
- P003 ニュースタイムライン: 死活・データ鮮度・トピック数
- GitHub Actions: 直近5件の成功/失敗・連続失敗検知

## ルールベース判断（Claude不要）
通常時はすべて MONITORING_RULES で判断する。
- 3回連続失敗 → HIGH alert
- データが2時間以上古い → MEDIUM alert
- トピック数0件 → HIGH alert
- HTTP 200以外 → HIGH alert

## 誤検知学習（DynamoDB ai-company-memory）
- 毎週月曜のLambdaコールドスタート等の既知パターンを学習
- 学習済みパターンは自動スキップ（Claude呼び出し不要）
- learn_false_positive() で手動登録可能

## Claude呼び出し条件
- RuleEngine.should_call_claude(findings) == True のときのみ
- = HIGH severity かつ DynamoDB未学習パターン
- 通常運用では月数回以下を想定

## 誤検知手動登録
  python3 -c "
  import sys; sys.path.insert(0, 'scripts')
  from _rule_engine import RuleEngine
  engine = RuleEngine('devops')
  engine.learn_pattern('github_consecutive_failure',
    '毎週月曜のLambdaコールドスタートは正常')
  "

## 最終更新: 2026-04-22
"""

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ガバナンス・ルールエンジン共通モジュール
sys.path.insert(0, str(Path(__file__).parent))
from _rule_engine import RuleEngine, Finding

# =============================================================================
# 設定
# =============================================================================

P003_DATA_URL = (
    "http://p003-news-946554699567.s3-website-ap-northeast-1.amazonaws.com/data.json"
)
GITHUB_OWNER      = "nao-amj"
GITHUB_REPO       = "ai-company"
GITHUB_API_BASE   = "https://api.github.com"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL   = "claude-haiku-4-5-20251001"

JST                      = timezone(timedelta(hours=9))
STALENESS_THRESHOLD_HOURS = 2
CONSECUTIVE_FAIL_THRESHOLD = 3   # 連続失敗アラート閾値

# ルールエンジン初期化
engine = RuleEngine("devops")

# =============================================================================
# 監視ルール定義（コード内 + DynamoDB動的読み込み）
# =============================================================================

MONITORING_RULES = {
    "p003_http_error": {
        "description": "P003 HTTP ステータス異常",
        "severity": "HIGH",
        "check": "status_code != 200",
    },
    "p003_stale_data": {
        "description": f"P003 データが{STALENESS_THRESHOLD_HOURS}時間以上古い",
        "severity": "MEDIUM",
        "check": f"age_hours > {STALENESS_THRESHOLD_HOURS}",
    },
    "p003_no_topics": {
        "description": "P003 トピック数が0件",
        "severity": "HIGH",
        "check": "topic_count == 0",
    },
    "p003_no_last_updated": {
        "description": "P003 last_updated フィールドなし",
        "severity": "MEDIUM",
        "check": "last_updated is None",
    },
    "github_consecutive_failure": {
        "description": f"GitHub Actions {CONSECUTIVE_FAIL_THRESHOLD}回以上連続失敗",
        "severity": "HIGH",
        "check": f"consecutive_failures >= {CONSECUTIVE_FAIL_THRESHOLD}",
    },
    "github_single_failure": {
        "description": "GitHub Actions ワークフロー失敗",
        "severity": "MEDIUM",
        "check": "any_failure == True",
    },
    "github_token_missing": {
        "description": "GITHUB_TOKEN 未設定",
        "severity": "LOW",
        "check": "token == ''",
    },
}


# =============================================================================
# HTTP ユーティリティ
# =============================================================================

def http_get(url: str, headers: dict = None, timeout: int = 15) -> tuple:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception as e:
        print(f"[ERROR] GET {url}: {e}")
        return 0, b""


def http_post(url: str, payload: dict, headers: dict) -> tuple:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        print(f"[ERROR] POST {url}: {e}")
        return 0, b""


# =============================================================================
# P003 チェック → Finding生成
# =============================================================================

def check_p003() -> tuple:
    """
    P003サイトの死活・データ鮮度・トピック数を確認する。

    Returns:
        (raw_result: dict, findings: list[Finding])
    """
    result = {
        "ok": False,
        "status_code": 0,
        "last_updated": None,
        "topic_count": 0,
        "stale": True,
        "age_hours": None,
        "issues": [],
    }
    findings = []

    status, body = http_get(P003_DATA_URL)
    result["status_code"] = status

    if status != 200:
        result["issues"].append(f"HTTPステータス異常: {status}")
        findings.append(Finding(
            pattern_id="p003_http_error",
            severity=MONITORING_RULES["p003_http_error"]["severity"],
            message=f"P003 HTTP {status} エラー",
            context={"url": P003_DATA_URL, "status_code": str(status)},
        ))
        return result, findings

    try:
        data = json.loads(body)
    except Exception:
        result["issues"].append("data.json のJSONパース失敗")
        findings.append(Finding(
            pattern_id="p003_http_error",
            severity="HIGH",
            message="P003 data.json JSONパース失敗",
            context={"url": P003_DATA_URL},
        ))
        return result, findings

    # --- last_updated チェック ---
    last_updated_str = data.get("last_updated") or data.get("generated_at")
    if last_updated_str:
        result["last_updated"] = last_updated_str
        try:
            lu = datetime.fromisoformat(last_updated_str.replace("Z", "+00:00"))
            age_hours = (datetime.now(timezone.utc) - lu).total_seconds() / 3600
            result["age_hours"] = round(age_hours, 1)
            result["stale"] = age_hours > STALENESS_THRESHOLD_HOURS
            if result["stale"]:
                result["issues"].append(f"データが古い: {age_hours:.1f}時間経過")
                findings.append(Finding(
                    pattern_id="p003_stale_data",
                    severity=MONITORING_RULES["p003_stale_data"]["severity"],
                    message=f"P003 データが {age_hours:.1f}時間 更新されていない",
                    context={"age_hours": str(round(age_hours, 1)),
                             "last_updated": last_updated_str},
                ))
        except Exception as e:
            result["issues"].append(f"last_updated パース失敗: {e}")
    else:
        result["issues"].append("last_updated フィールドなし")
        findings.append(Finding(
            pattern_id="p003_no_last_updated",
            severity=MONITORING_RULES["p003_no_last_updated"]["severity"],
            message="P003 data.json に last_updated フィールドなし",
            context={"url": P003_DATA_URL},
        ))

    # --- トピック数チェック ---
    topics = data.get("topics") or data.get("articles") or []
    result["topic_count"] = len(topics)
    if len(topics) == 0:
        result["issues"].append("トピック数が0件")
        findings.append(Finding(
            pattern_id="p003_no_topics",
            severity=MONITORING_RULES["p003_no_topics"]["severity"],
            message="P003 トピック数が0件",
            context={"url": P003_DATA_URL},
        ))

    result["ok"] = len(result["issues"]) == 0
    return result, findings


# =============================================================================
# GitHub Actions チェック → Finding生成
# =============================================================================

def check_github_actions(token: str) -> tuple:
    """
    GitHub Actions の直近5件の結果を確認する。

    Returns:
        (raw_result: dict, findings: list[Finding])
    """
    result = {"ok": False, "runs": [], "issues": []}
    findings = []

    if not token:
        result["issues"].append("GITHUB_TOKEN 未設定")
        findings.append(Finding(
            pattern_id="github_token_missing",
            severity=MONITORING_RULES["github_token_missing"]["severity"],
            message="GITHUB_TOKEN が未設定のため GitHub Actions チェック不可",
            context={},
        ))
        return result, findings

    url = (f"{GITHUB_API_BASE}/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
           f"/actions/runs?per_page=10")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    status, body = http_get(url, headers=headers)

    if status != 200:
        result["issues"].append(f"GitHub API エラー: {status}")
        findings.append(Finding(
            pattern_id="p003_http_error",  # 汎用HTTPエラーとして扱う
            severity="MEDIUM",
            message=f"GitHub API HTTP {status} エラー",
            context={"status_code": str(status)},
        ))
        return result, findings

    try:
        data = json.loads(body)
    except Exception:
        result["issues"].append("GitHub API レスポンスのJSONパース失敗")
        return result, findings

    runs = data.get("workflow_runs", [])

    # ワークフロー名ごとに直近実行結果をチェック
    workflow_latest: dict = {}
    for run in runs:
        wf_name = run.get("name", "unknown")
        if wf_name not in workflow_latest:
            workflow_latest[wf_name] = []
        workflow_latest[wf_name].append(run.get("conclusion"))

    # 連続失敗チェック（ワークフロー名単位）
    any_failure = False
    for wf_name, conclusions in workflow_latest.items():
        recent_failures = 0
        for c in conclusions:
            if c == "failure":
                recent_failures += 1
            else:
                break  # 直近から連続でない場合は止める

        if recent_failures >= CONSECUTIVE_FAIL_THRESHOLD:
            findings.append(Finding(
                pattern_id="github_consecutive_failure",
                severity=MONITORING_RULES["github_consecutive_failure"]["severity"],
                message=f"GitHub Actions '{wf_name}' が {recent_failures}回連続失敗",
                context={"workflow": wf_name,
                         "consecutive_failures": str(recent_failures)},
            ))
            result["issues"].append(
                f"ワークフロー '{wf_name}' が {recent_failures}回連続失敗"
            )
            any_failure = True
        elif recent_failures > 0:
            findings.append(Finding(
                pattern_id="github_single_failure",
                severity=MONITORING_RULES["github_single_failure"]["severity"],
                message=f"GitHub Actions '{wf_name}' で失敗あり",
                context={"workflow": wf_name,
                         "recent_failures": str(recent_failures)},
            ))
            result["issues"].append(f"ワークフロー '{wf_name}' で失敗あり")
            any_failure = True

    for run in runs[:5]:
        result["runs"].append({
            "name":       run.get("name", ""),
            "conclusion": run.get("conclusion"),
            "status":     run.get("status"),
            "created_at": run.get("created_at"),
            "html_url":   run.get("html_url", ""),
        })

    result["ok"] = not any_failure
    return result, findings


# =============================================================================
# ルールベース Slackメッセージ組み立て（Claude不要）
# =============================================================================

def build_slack_message_rule_based(
    p003: dict,
    github: dict,
    findings: list,
    has_issues: bool,
    is_morning_run: bool,
    now_str: str,
) -> str:
    """
    監視結果から Slack メッセージを組み立てる。
    Claude を使わず Python テンプレートで構成。

    Args:
        p003: check_p003() の raw_result
        github: check_github_actions() の raw_result
        findings: 全Findingリスト（フィルタ済み）
        has_issues: True=異常あり
        is_morning_run: True=朝のサマリー
        now_str: 日時文字列

    Returns:
        Slack 通知テキスト
    """
    if has_issues:
        header = "🚨 *AI-Company 開発監視アラート*"
    else:
        header = "📊 *AI-Company 開発監視サマリー（毎朝レポート）*"

    lines = [
        header,
        f"🕐 {now_str}",
        "",
        "*P003 ニュースタイムライン*",
        f"  ステータス: HTTP {p003['status_code']}",
        f"  最終更新: {p003['last_updated'] or 'N/A'}",
        f"  データ経過: {p003.get('age_hours', 'N/A')}時間",
        f"  トピック数: {p003['topic_count']}件",
    ]

    if p003["issues"]:
        for iss in p003["issues"]:
            lines.append(f"  ⚠️ {iss}")
    else:
        lines.append("  ✅ 正常")

    lines.append("")
    lines.append("*GitHub Actions（直近5件）*")
    if github["runs"]:
        for r in github["runs"]:
            icon = (
                "✅" if r["conclusion"] == "success"
                else "🚨" if r["conclusion"] == "failure"
                else "⏳"
            )
            lines.append(f"  {icon} {r['name']} — {r['conclusion'] or r['status']}")
    else:
        lines.append("  （取得できませんでした）")

    if github["issues"]:
        for iss in github["issues"]:
            lines.append(f"  ⚠️ {iss}")

    # Finding サマリー（ルールエンジンの出力）
    if findings:
        lines.append("")
        lines.append("*検出された問題（ルールベース判定）*")
        for f in findings:
            sev_icon = {"HIGH": "🚨", "MEDIUM": "⚠️", "LOW": "ℹ️"}.get(f.severity, "ℹ️")
            lines.append(f"  {sev_icon} [{f.severity}] {f.message}")

    # 正常時の評価コメント
    if not has_issues:
        lines.append("")
        lines.append("_ルールベース判定: 全チェック通過。Claude呼び出しなし。_")

    return "\n".join(lines)


# =============================================================================
# Claude による詳細分析（HIGH severity + 未学習パターン のみ呼び出す）
# =============================================================================

def ask_claude_for_anomaly(
    monitoring_data: dict,
    high_findings: list,
    api_key: str,
) -> str:
    """
    ルールベースでは判断できない異常時のみ Claude に問い合わせる。
    通常時はこの関数は呼ばれない。

    Args:
        monitoring_data: 監視生データ
        high_findings: HIGH severity の未学習 Finding リスト
        api_key: Anthropic API Key

    Returns:
        Claude の分析テキスト（異常時のみ）
    """
    if not api_key:
        return "（ANTHROPIC_API_KEY 未設定のため詳細分析スキップ）"

    # 問い合わせ対象の問題を整理
    issues_text = "\n".join([
        f"- [{f.severity}] {f.message} (context: {f.context})"
        for f in high_findings
    ])

    prompt = f"""あなたはAI会社の開発監視AIです。
ルールベース監視で以下のHIGH severity問題が検出されました。
詳細な原因分析と具体的な対処手順を日本語で簡潔に答えてください。

## 検出された問題
{issues_text}

## 監視データ（抜粋）
{json.dumps(monitoring_data, ensure_ascii=False, indent=2)[:1500]}

## 指示
- 原因として考えられること（1〜2点）
- 推奨する対処手順（番号付きで3ステップ以内）
- 返答は300字以内
"""

    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 512,
        "messages": [{"role": "user", "content": prompt}],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    status, body = http_post(ANTHROPIC_API_URL, payload, headers)
    if status != 200:
        return f"（Claude API エラー: {status}）"

    try:
        resp = json.loads(body)
        return resp["content"][0]["text"].strip()
    except Exception:
        return "（Claude レスポンスのパース失敗）"


# =============================================================================
# Slack 通知
# =============================================================================

def send_slack(webhook_url: str, text: str) -> bool:
    """Slack Webhook に通知する"""
    if not webhook_url:
        print("[WARN] SLACK_WEBHOOK 未設定 — Slack通知スキップ")
        return False

    status, _ = http_post(webhook_url, {"text": text},
                           {"Content-Type": "application/json"})
    if status not in (200, 204):
        print(f"[ERROR] Slack通知失敗: HTTP {status}")
        return False
    return True


# =============================================================================
# エントリポイント
# =============================================================================

def main():
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    slack_webhook = os.environ.get("SLACK_WEBHOOK", os.environ.get("SLACK_WEBHOOK_URL", ""))
    github_token  = os.environ.get("GITHUB_TOKEN", "")

    if not slack_webhook:
        print("[WARN] 環境変数 SLACK_WEBHOOK が未設定")
    if not github_token:
        print("[WARN] 環境変数 GITHUB_TOKEN が未設定")

    now_jst       = datetime.now(JST)
    is_morning_run = now_jst.hour == 8   # 毎朝8:00 JST
    now_str        = now_jst.strftime("%Y-%m-%d %H:%M JST")

    print(f"[INFO] 監視開始: {now_str}")
    print(f"[INFO] 朝の定期サマリー: {is_morning_run}")

    # ── チェック実行 → Finding 生成 ─────────────────────────────
    p003,   p003_findings   = check_p003()
    github, github_findings = check_github_actions(github_token)

    all_findings_raw = p003_findings + github_findings

    # ── 誤検知フィルタ（DynamoDB学習済みパターンを除外）─────────
    real_findings, suppressed = engine.filter_known_false_positives(all_findings_raw)

    if suppressed:
        print(f"[INFO] 既知誤検知パターンをスキップ: {len(suppressed)}件")
        for s in suppressed:
            print(f"  - {s.pattern_id}: {s.message}")

    # ── 異常判定（フィルタ後のFindingで判断）────────────────────
    has_issues = bool(real_findings)

    # ── 通知判断（異常検知時のみ通知）───────────────────────────
    if not has_issues:
        print("[INFO] 異常なし → 通知スキップ")
        sys.exit(0)

    # ── Claude呼び出し判断（HIGH + 未学習パターンのみ）───────────
    claude_analysis = ""
    if engine.should_call_claude(real_findings):
        high_unknowns = [
            f for f in real_findings
            if f.severity == "HIGH" and not engine.is_known_false_positive(f)
        ]
        print(f"[INFO] HIGH severity 未知パターン {len(high_unknowns)}件 → Claude呼び出し")
        monitoring_data = {
            "timestamp_jst": now_str,
            "p003": {k: v for k, v in p003.items() if k != "issues"},
            "github": {"runs": github["runs"][:3]},
        }
        claude_analysis = ask_claude_for_anomaly(
            monitoring_data, high_unknowns, anthropic_key
        )
        print(f"[INFO] Claude分析:\n{claude_analysis}")
    else:
        print("[INFO] ルールベース判定のみで十分 → Claude呼び出しスキップ")

    # ── Slackメッセージ組み立て（Python純正テンプレート）───────
    message = build_slack_message_rule_based(
        p003=p003,
        github=github,
        findings=real_findings,
        has_issues=has_issues,
        is_morning_run=is_morning_run,
        now_str=now_str,
    )

    # Claude分析がある場合は追記
    if claude_analysis:
        message += f"\n\n*Claude 詳細分析（HIGH異常時のみ）*\n{claude_analysis}"

    # ── Slack 送信 ─────────────────────────────────────────────
    send_slack(slack_webhook, message)
    print("[INFO] Slack通知送信完了")
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[FATAL] 予期しないエラー: {e}")
        webhook = os.environ.get("SLACK_WEBHOOK", os.environ.get("SLACK_WEBHOOK_URL", ""))
        if webhook:
            send_slack(webhook, f"🚨 *開発監視AI クラッシュ*\n```{e}```")
        sys.exit(0)
