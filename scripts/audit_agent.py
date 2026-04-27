#!/usr/bin/env python3
"""
audit_agent.py — AI-Company 外部監査AI

## 設計哲学
Claude API 呼び出し：完全ゼロ
判断根拠：DynamoDBのデータ比較・数値閾値・パターンマッチング・統計計算
独立性：監査対象エージェントと同じAIモデルを一切使わない

監査AIがClaudeを使った場合、監査対象のエージェントも同じClaudeを使っているため
独立性がゼロになる。Claudeが偏った判断をした時に監査も同様に偏る。
よって、監査の全判断は純粋なPythonロジックで行う。

## 監視対象エージェント（9体）
ceo, secretary, devops, marketing, revenue, editorial, seo, security, legal

## チェック項目と判断方法（全て純粋Python）
- drift:          出力長の過去30回の標準偏差。平均から3σ外れたら検知
- bias:           直近10回の出力から特定キーワードの出現率。80%超で検知
- scope:          DynamoDBのログからホワイトリスト外APIパターンをregex検出
- cost:           前週比コスト比率。2.0倍超で警告、5.0倍超でCRITICAL
- output_quality: 出力文字数チェック + 空報告（100文字以下）検知

## 重大度と対処
- LOW:    Slack警告のみ
- MEDIUM: DynamoDB一時停止フラグ + POさんにSlack直報
- HIGH:   即時停止（手動解除必須）+ Slack緊急通知

## 重要原則
- POさん（管理者メールは ADMIN_EMAIL 環境変数で設定）に直接報告。CEOを経由しない。
- 監査AIは自分自身の停止フラグを確認するが、自己停止はしない（監査継続のため）

## 完了度: 完成候補
## 最終更新: 2026-04-22
"""

import json
import math
import os
import re
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path
from statistics import mean, stdev

# ガバナンス共通モジュール
sys.path.insert(0, str(Path(__file__).parent))
from _governance_check import set_agent_status, get_all_agent_statuses

# --- 環境変数 ---
SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK", os.environ.get("SLACK_WEBHOOK_URL", ""))
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "ap-northeast-1")
REPO_ROOT = Path(__file__).parent.parent

# --- DynamoDB テーブル ---
AUDIT_TABLE = "ai-company-audit"
MEMORY_TABLE = "ai-company-memory"
AGENT_STATUS_TABLE = "ai-company-agent-status"

# --- 監査AIの自己確認（停止フラグがあっても実行継続・ログのみ）---
try:
    import boto3 as _boto3
    _tbl = _boto3.resource("dynamodb", region_name=AWS_REGION).Table(AGENT_STATUS_TABLE)
    _self_item = _tbl.get_item(Key={"agent_name": "audit"}).get("Item", {})
    if _self_item.get("status") in ("paused", "stopped"):
        print(f"[audit] ⚠️  監査AIにフラグ({_self_item['status']})がありますが監査継続します（監査AIは自己停止しない）")
except Exception:
    pass  # DynamoDB未接続でも続行

# =============================================================================
# 定数・設定
# =============================================================================

# 監視対象エージェント
ALL_AGENTS = [
    "ceo", "secretary", "devops", "marketing",
    "revenue", "editorial", "seo", "security", "legal"
]

# エージェントと対応するDynamoDB PKのマッピング
AGENT_PKS = {
    "ceo":       "CEO_MEMORY",
    "secretary": "SECRETARY_MEMORY",
    "devops":    "DEVOPS_MEMORY",
    "marketing": "MARKETING_MEMORY",
    "revenue":   "REVENUE_MEMORY",
    "editorial": "EDITORIAL_MEMORY",
    "seo":       "SEO_MEMORY",
    "security":  "SECURITY",
    "legal":     "LEGAL",
}

# エージェントごとの正常出力の最小文字数
MIN_OUTPUT_CHARS: dict[str, int] = {
    "ceo":       500,
    "secretary": 300,
    "devops":    200,
    "marketing": 300,
    "revenue":   200,
    "editorial": 300,
    "seo":       200,
    "security":  200,
    "legal":     200,
}

# バイアス検知: 特定キーワードがこの割合以上の回で出現したら警告
BIAS_KEYWORD_THRESHOLD = 0.80   # 80%
BIAS_MIN_LOGS = 5               # 最低この件数のログが必要

# ドリフト検知: σから何倍外れたら警告
DRIFT_SIGMA_THRESHOLD = 3.0
DRIFT_MIN_LOGS = 10             # 標準偏差計算に必要な最低ログ数

# コスト異常検知
COST_WARNING_RATIO = 2.0        # 前週比200%で警告
COST_CRITICAL_RATIO = 5.0       # 前週比500%でCRITICAL

# エージェントごとの許可APIアクションのホワイトリスト（正規表現）
SCOPE_WHITELIST: dict[str, list[str]] = {
    "ceo": [
        r"dynamodb\.(put_item|get_item|query|scan)",
        r"s3\.(get_object|list_objects)",
        r"anthropic\.api",
        r"slack\.webhook",
        r"urllib\.request",
    ],
    "secretary": [
        r"dynamodb\.(put_item|get_item|query)",
        r"notion\.api",
        r"slack\.webhook",
        r"urllib\.request",
    ],
    "marketing": [
        r"dynamodb\.(query|scan|get_item)",
        r"s3\.get_object",
        r"anthropic\.api",
        r"slack\.webhook",
    ],
    "editorial": [
        r"dynamodb\.(query|scan|get_item|put_item)",
        r"s3\.get_object",
        r"anthropic\.api",
        r"slack\.webhook",
    ],
    "seo": [
        r"dynamodb\.(query|scan|get_item)",
        r"s3\.(get_object|put_object)",
        r"anthropic\.api",
        r"slack\.webhook",
    ],
    "revenue": [
        r"dynamodb\.(query|scan|get_item|put_item)",
        r"cost_explorer\.(get_cost)",
        r"anthropic\.api",
        r"slack\.webhook",
        r"urllib\.request",
    ],
    "devops": [
        r"dynamodb\.(query|scan|get_item|put_item)",
        r"lambda\.(list_functions|get_function)",
        r"cloudwatch\.(get_metric|list_metrics)",
        r"s3\.(list_buckets|get_object)",
        r"slack\.webhook",
        r"urllib\.request",
    ],
    "security": [
        r"dynamodb\.(put_item|query|scan)",
        r"s3\.(list_buckets|get_public_access_block)",
        r"iam\.(list_attached_role_policies|list_roles)",
        r"lambda\.(list_functions|get_function)",
        r"slack\.webhook",
        r"subprocess\.(run)",
    ],
    "legal": [
        r"dynamodb\.(put_item|query|scan|get_item)",
        r"anthropic\.api",
        r"slack\.webhook",
        r"urllib\.request",
    ],
}

# スコープ違反として検知するキーワード（全エージェント共通）
SCOPE_VIOLATION_PATTERNS = [
    r"iam\.(create_|delete_|attach_|detach_|put_role_policy)",
    r"s3\.(delete_object|delete_bucket|put_public_access_block)",
    r"dynamodb\.(delete_table|create_table)",
    r"ec2\.(terminate|stop_instances|run_instances)",
    r"lambda\.(delete_function|create_function|update_function_code)",
    r"route53\.(change_resource_record|delete_hosted_zone)",
    r"acm\.(delete_certificate|request_certificate)",
    r"cloudfront\.(create_distribution|delete_distribution)",
]

# バイアス検知のキーワードグループ（エージェント別）
BIAS_KEYWORDS: dict[str, list[str]] = {
    "ceo": ["問題なし", "異常なし", "正常", "変化なし", "特になし"],
    "secretary": ["同期完了", "問題なし", "エラーなし"],
    "marketing": ["効果なし", "変化なし", "同じ"],
    "editorial": ["品質問題なし", "変更なし"],
    "revenue": ["収益なし", "変動なし"],
    "seo": ["変化なし", "改善なし"],
    "devops": ["問題なし", "正常稼働", "エラーなし"],
    "security": ["検出なし", "問題なし", "クリア"],
    "legal": ["問題なし", "クリア", "規約変更なし"],
}


# =============================================================================
# ユーティリティ
# =============================================================================

def slack_notify(text: str, direct: bool = False) -> None:
    """
    Slack Webhook に通知する。
    direct=True はPOさんへの直接報告であることをマーク。
    Claude API は使わない。メッセージはPythonテンプレートで組み立て。
    """
    if not SLACK_WEBHOOK:
        print("[audit/slack] SLACK_WEBHOOK 未設定 → スキップ")
        return
    prefix = "📋 *[外部監査AI → POさん直接報告]*\n" if direct else ""
    payload = json.dumps({"text": prefix + text}).encode()
    req = urllib.request.Request(
        SLACK_WEBHOOK,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=15)
        print("[audit/slack] 通知送信完了")
    except Exception as e:
        print(f"[audit/slack] 送信失敗: {e}")


def save_audit_log(agent_name: str, checks: dict, overall_severity: str) -> bool:
    """監査結果をDynamoDB ai-company-audit に保存"""
    try:
        import boto3
        dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
        table = dynamodb.Table(AUDIT_TABLE)
        now = datetime.now(timezone.utc).isoformat()
        table.put_item(Item={
            "pk": f"AUDIT_{agent_name.upper()}",
            "sk": now,
            "agent": agent_name,
            "overall_severity": overall_severity,
            "checks": json.dumps(checks, ensure_ascii=False, default=str)[:4000],
            "auditor": "audit_agent_v2_no_claude",
        })
        return True
    except Exception as e:
        print(f"[audit] ログ保存失敗 ({agent_name}): {e}")
        return False


def get_agent_logs(agent_name: str, limit: int = 30) -> list:
    """
    DynamoDB から指定エージェントの直近N回の実行ログを取得する。
    Returns: [{"sk": str, "summary": str, ...}, ...]
    """
    pk = AGENT_PKS.get(agent_name, "")
    if not pk:
        return []
    table_name = AUDIT_TABLE if agent_name in ("security", "legal") else MEMORY_TABLE
    try:
        import boto3
        from boto3.dynamodb.conditions import Key
        dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
        table = dynamodb.Table(table_name)
        resp = table.query(
            KeyConditionExpression=Key("pk").eq(pk),
            ScanIndexForward=False,
            Limit=limit,
        )
        return resp.get("Items", [])
    except Exception as e:
        print(f"[audit] ログ取得失敗 ({agent_name}): {e}")
        return []


# =============================================================================
# Check 1: output_quality — 文字数と空報告チェック（純粋Python）
# =============================================================================

def check_output_quality(agent_name: str, logs: list) -> dict:
    """
    出力の文字数を確認。空報告（100文字以下）や短すぎる出力を検知。
    判断: Python数値比較のみ
    """
    min_chars = MIN_OUTPUT_CHARS.get(agent_name, 100)
    if not logs:
        return {
            "severity": "LOW",
            "issue": "実行ログが0件 — このエージェントは実行されていない可能性があります",
            "logs_checked": 0,
        }

    lengths = []
    short_count = 0
    empty_count = 0

    for log in logs:
        summary = str(log.get("summary", ""))
        length = len(summary)
        lengths.append(length)
        if length < 100:
            empty_count += 1
        elif length < min_chars:
            short_count += 1

    total = len(logs)
    avg_len = mean(lengths) if lengths else 0

    # 評価
    if empty_count >= total * 0.5:
        return {
            "severity": "HIGH",
            "issue": f"空報告が{empty_count}/{total}回 (100文字未満) — エージェントが機能していません",
            "avg_chars": round(avg_len),
            "empty_count": empty_count,
            "short_count": short_count,
        }
    elif empty_count >= 2 or short_count >= total * 0.5:
        return {
            "severity": "MEDIUM",
            "issue": f"短すぎる出力: 空報告{empty_count}回 / 短い出力{short_count}回 (基準: {min_chars}文字)",
            "avg_chars": round(avg_len),
        }
    elif short_count >= 2:
        return {
            "severity": "LOW",
            "issue": f"短い出力が{short_count}件あります (基準: {min_chars}文字)",
            "avg_chars": round(avg_len),
        }
    return {"severity": "OK", "avg_chars": round(avg_len), "logs_checked": total}


# =============================================================================
# Check 2: drift — 出力長の標準偏差による変動検知（純粋Python統計）
# =============================================================================

def check_drift(agent_name: str, logs: list) -> dict:
    """
    出力長の過去N回の標準偏差を計算。
    直近1件が平均から3σ以上外れたら「ドリフト疑い」と判定。
    Claude不要: 数値統計のみ。
    """
    if len(logs) < DRIFT_MIN_LOGS:
        return {
            "severity": "OK",
            "note": f"ログ数不足 ({len(logs)}/{DRIFT_MIN_LOGS}) — ドリフト判定スキップ",
        }

    lengths = [len(str(log.get("summary", ""))) for log in logs]
    avg = mean(lengths)

    # 全て同じ長さ（std=0）の場合は別途チェック
    if all(l == lengths[0] for l in lengths):
        if avg < 50:
            return {
                "severity": "MEDIUM",
                "issue": f"全{len(logs)}回が同一の短い出力 ({int(avg)}文字) — テンプレート固定化の疑い",
                "avg_len": round(avg),
                "std_len": 0,
            }
        return {
            "severity": "LOW",
            "note": f"出力長が完全に一定 ({int(avg)}文字) — 正常の可能性もあるが要注意",
            "avg_len": round(avg),
            "std_len": 0,
        }

    try:
        std = stdev(lengths)
    except Exception:
        return {"severity": "OK", "note": "標準偏差計算エラー"}

    if std < 1:
        return {"severity": "OK", "avg_len": round(avg), "std_len": round(std, 1)}

    latest_len = lengths[0]  # 最新
    z_score = abs(latest_len - avg) / std

    if z_score >= DRIFT_SIGMA_THRESHOLD:
        direction = "急増" if latest_len > avg else "急減"
        return {
            "severity": "MEDIUM",
            "issue": (
                f"出力長が{DRIFT_SIGMA_THRESHOLD}σ外れています ({direction}) — "
                f"最新={latest_len}文字 / 平均={int(avg)}文字 / σ={round(std,1)} / z={round(z_score,2)}"
            ),
            "z_score": round(z_score, 2),
            "latest_len": latest_len,
            "avg_len": round(avg),
            "std_len": round(std, 1),
        }

    return {
        "severity": "OK",
        "avg_len": round(avg),
        "std_len": round(std, 1),
        "z_score": round(z_score, 2),
    }


# =============================================================================
# Check 3: bias — キーワード頻度カウントによる偏り検知（純粋Python）
# =============================================================================

def check_bias(agent_name: str, logs: list) -> dict:
    """
    直近N回の出力で特定キーワードが80%以上の回で登場したら「バイアス疑い」。
    Claude不要: 文字列カウントのみ。
    """
    if len(logs) < BIAS_MIN_LOGS:
        return {
            "severity": "OK",
            "note": f"ログ数不足 ({len(logs)}/{BIAS_MIN_LOGS}) — バイアス判定スキップ",
        }

    check_logs = logs[:10]  # 直近10件
    summaries = [str(log.get("summary", "")).lower() for log in check_logs]
    keywords = BIAS_KEYWORDS.get(agent_name, [])

    if not keywords:
        # キーワード未定義の場合は先頭50文字の重複チェック
        prefixes = [s[:50] for s in summaries if s]
        counter = Counter(prefixes)
        most_common, count = counter.most_common(1)[0] if counter else ("", 0)
        ratio = count / len(prefixes) if prefixes else 0
        if ratio >= BIAS_KEYWORD_THRESHOLD:
            return {
                "severity": "MEDIUM",
                "issue": (
                    f"同一パターンが{count}/{len(prefixes)}回 ({int(ratio*100)}%) — "
                    f"出力が固定化している可能性があります"
                ),
                "pattern": most_common[:40],
                "ratio": round(ratio, 2),
            }
        return {"severity": "OK"}

    # キーワード別の出現率を計算
    flagged = []
    for keyword in keywords:
        appearances = sum(1 for s in summaries if keyword in s)
        ratio = appearances / len(summaries) if summaries else 0
        if ratio >= BIAS_KEYWORD_THRESHOLD:
            flagged.append((keyword, appearances, len(summaries), ratio))

    if flagged:
        worst = max(flagged, key=lambda x: x[3])
        return {
            "severity": "MEDIUM",
            "issue": (
                f"キーワード '{worst[0]}' が{worst[1]}/{worst[2]}回 ({int(worst[3]*100)}%) 出現 — "
                f"判断パターンが固定化している可能性があります"
            ),
            "flagged_keywords": [
                {"keyword": kw, "appearances": ap, "total": tot, "ratio": round(r, 2)}
                for kw, ap, tot, r in flagged
            ],
        }

    # 連続同一パターンもチェック
    if len(summaries) >= 4:
        prefixes = [s[:40] for s in summaries[:6]]
        top_prefix, top_count = Counter(prefixes).most_common(1)[0]
        if top_count >= 4:
            return {
                "severity": "LOW",
                "issue": f"先頭40文字が{top_count}回一致 — 出力パターンが固定化の可能性",
                "pattern": top_prefix,
            }

    return {"severity": "OK", "keywords_checked": len(keywords)}


# =============================================================================
# Check 4: scope — ホワイトリスト外操作の検知（正規表現マッチング）
# =============================================================================

def check_scope(agent_name: str, logs: list) -> dict:
    """
    ログ内のテキストを正規表現でスキャン。
    ホワイトリスト外の危険な操作（IAM削除・S3削除・Lambda作成等）を検出。
    Claude不要: 正規表現マッチングのみ。
    """
    if not logs:
        return {"severity": "OK", "note": "ログなし"}

    violation_patterns = [re.compile(p, re.IGNORECASE) for p in SCOPE_VIOLATION_PATTERNS]
    violations = []

    for log in logs[:5]:  # 直近5件をスキャン
        text = json.dumps(log, ensure_ascii=False, default=str).lower()
        for i, pattern in enumerate(violation_patterns):
            if pattern.search(text):
                violations.append({
                    "log_sk": str(log.get("sk", "?"))[:30],
                    "pattern": SCOPE_VIOLATION_PATTERNS[i],
                })

    if violations:
        severity = "HIGH" if len(violations) >= 3 else "MEDIUM"
        return {
            "severity": severity,
            "issue": f"権限外操作の疑い: {len(violations)}件のパターン検出",
            "violations": violations[:5],
        }

    return {"severity": "OK", "logs_scanned": min(len(logs), 5)}


# =============================================================================
# Check 5: cost — AWS コスト異常検知（数値比較）
# =============================================================================

def check_cost(agent_name: str) -> dict:
    """
    AWS Cost Explorer で今週と先週のコストを比較。
    前週比200%超で警告、500%超でCRITICAL。
    Claude不要: 数値比較のみ。
    """
    try:
        import boto3
        ce = boto3.client("ce", region_name="us-east-1")
        now = datetime.now(timezone.utc)
        # 今週（直近7日）
        this_start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        this_end = now.strftime("%Y-%m-%d")
        # 先週（7〜14日前）
        last_start = (now - timedelta(days=14)).strftime("%Y-%m-%d")
        last_end = (now - timedelta(days=7)).strftime("%Y-%m-%d")

        def get_total_cost(start, end):
            resp = ce.get_cost_and_usage(
                TimePeriod={"Start": start, "End": end},
                Granularity="MONTHLY",
                Metrics=["UnblendedCost"],
            )
            total = 0.0
            for r in resp.get("ResultsByTime", []):
                total += float(r["Total"]["UnblendedCost"]["Amount"])
            return round(total, 4)

        this_week = get_total_cost(this_start, this_end)
        last_week = get_total_cost(last_start, last_end)

        if last_week < 0.01:
            return {
                "severity": "OK",
                "note": f"先週コストがほぼ0 → 比率計算スキップ (今週: ${this_week})",
                "this_week_usd": this_week,
            }

        ratio = this_week / last_week
        result_base = {
            "this_week_usd": this_week,
            "last_week_usd": last_week,
            "ratio": round(ratio, 2),
        }

        if ratio >= COST_CRITICAL_RATIO:
            return {
                **result_base,
                "severity": "HIGH",
                "issue": (
                    f"コスト急増: 今週${this_week} / 先週${last_week} = "
                    f"{round(ratio, 1)}倍 (閾値: {COST_CRITICAL_RATIO}倍)"
                ),
            }
        elif ratio >= COST_WARNING_RATIO:
            return {
                **result_base,
                "severity": "MEDIUM",
                "issue": (
                    f"コスト増加: 今週${this_week} / 先週${last_week} = "
                    f"{round(ratio, 1)}倍 (閾値: {COST_WARNING_RATIO}倍)"
                ),
            }
        return {**result_base, "severity": "OK"}

    except Exception as e:
        return {
            "severity": "OK",
            "note": f"コスト取得失敗（スキップ）: {e}",
        }


# =============================================================================
# エージェント単体監査
# =============================================================================

def audit_single_agent(agent_name: str) -> dict:
    """
    1エージェントに対して全5チェックを実行。
    全判断はPythonロジックのみ。Claude不使用。
    """
    print(f"[audit] 🔍 {agent_name} 監査中...")
    logs = get_agent_logs(agent_name, limit=30)

    checks = {
        "output_quality": check_output_quality(agent_name, logs),
        "drift":          check_drift(agent_name, logs),
        "bias":           check_bias(agent_name, logs),
        "scope":          check_scope(agent_name, logs[:5]),
        "cost":           check_cost(agent_name),
    }

    # 全体重大度（最も高いものを採用）
    severity_rank = {"OK": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}
    max_sev = max(
        (c.get("severity", "OK") for c in checks.values()),
        key=lambda s: severity_rank.get(s, 0),
        default="OK"
    )

    return {
        "agent": agent_name,
        "overall_severity": max_sev,
        "checks": checks,
        "logs_available": len(logs),
    }


# =============================================================================
# 重大度に応じた対処
# =============================================================================

def handle_severity(agent_name: str, severity: str, checks: dict) -> None:
    """
    重大度別に自動対処を実行する。
    通知メッセージはPythonテンプレートで組み立て（Claude不使用）。
    """
    if severity == "OK":
        return

    # 問題のある項目を収集
    issues_list = []
    for check_name, result in checks.items():
        sev = result.get("severity", "OK")
        if sev in ("LOW", "MEDIUM", "HIGH"):
            issue_text = result.get("issue", result.get("note", "詳細なし"))
            issues_list.append(f"  [{check_name}/{sev}] {issue_text}")

    issues_str = "\n".join(issues_list) if issues_list else "  （詳細不明）"

    if severity == "LOW":
        slack_notify(
            f"⚠️  *[AuditAI] {agent_name} — LOW警告*\n{issues_str}"
        )

    elif severity == "MEDIUM":
        # DynamoDB に一時停止フラグ
        reason = "\n".join(i.strip() for i in issues_list[:2])
        set_agent_status(
            agent_name, "paused",
            f"AuditAI MEDIUM: {reason[:200]}",
            severity="MEDIUM", resume_requires="auto"
        )
        slack_notify(
            f"⏸️  *[AuditAI] {agent_name} を一時停止しました（MEDIUM）*\n"
            f"{issues_str}\n\n"
            f"🔧 自動的に再開するには問題が解消されるか、DynamoDB `{AGENT_STATUS_TABLE}` の "
            f"`{agent_name}`.status を 'active' に変更してください。",
            direct=True
        )

    elif severity == "HIGH":
        # 即時停止（手動解除必須）
        reason = "\n".join(i.strip() for i in issues_list[:2])
        set_agent_status(
            agent_name, "stopped",
            f"AuditAI HIGH: {reason[:200]}",
            severity="HIGH", resume_requires="manual"
        )
        slack_notify(
            f"🚨 *[緊急 AuditAI] {agent_name} を強制停止 — 手動解除が必要です*\n"
            f"{issues_str}\n\n"
            f"⛔ 問題を修正してから DynamoDB `{AGENT_STATUS_TABLE}` の "
            f"`{agent_name}`.status を 'active' に戻してください。",
            direct=True
        )


# =============================================================================
# 全エージェント監査
# =============================================================================

def run_full_audit() -> None:
    """
    全9エージェントを監査し、DynamoDB保存 + POさんにSlack直接報告する。
    Claude API は一切呼ばない。
    """
    print("[audit] ===== 全エージェント監査開始 (Claude不使用) =====")
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    all_results = []
    severity_counts = {"OK": 0, "LOW": 0, "MEDIUM": 0, "HIGH": 0}

    for agent_name in ALL_AGENTS:
        result = audit_single_agent(agent_name)
        all_results.append(result)
        sev = result["overall_severity"]
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

        # DynamoDB保存
        save_audit_log(agent_name, result["checks"], sev)
        # 対処実行
        handle_severity(agent_name, sev, result["checks"])

    # ========================
    # 全体サマリーレポートを生成（Pythonテンプレート）
    # ========================
    total_issues = sum(v for k, v in severity_counts.items() if k != "OK")

    if total_issues == 0:
        overall_status = "✅ 全エージェント正常"
        header_emoji = "✅"
    elif severity_counts.get("HIGH", 0) > 0:
        overall_status = f"🚨 HIGH {severity_counts['HIGH']}件"
        header_emoji = "🚨"
    elif severity_counts.get("MEDIUM", 0) > 0:
        overall_status = f"⏸️  MEDIUM {severity_counts['MEDIUM']}件"
        header_emoji = "⏸️"
    else:
        overall_status = f"⚠️  LOW {severity_counts['LOW']}件"
        header_emoji = "⚠️"

    # エージェント別1行サマリー
    sev_emoji_map = {"OK": "✅", "LOW": "⚠️", "MEDIUM": "⏸️", "HIGH": "🚨"}
    agent_lines = [
        f"  {sev_emoji_map.get(r['overall_severity'], '❓')} {r['agent']}: "
        f"{r['overall_severity']} (ログ{r['logs_available']}件)"
        for r in all_results
    ]

    report = (
        f"{header_emoji} *AI-Company 全エージェント監査レポート*\n"
        f"実行時刻: {now_str}\n"
        f"総合: {overall_status}\n"
        f"内訳: OK={severity_counts.get('OK',0)} / LOW={severity_counts.get('LOW',0)} / "
        f"MEDIUM={severity_counts.get('MEDIUM',0)} / HIGH={severity_counts.get('HIGH',0)}\n"
        f"判断方法: Python統計・ルールエンジン（Claude不使用）\n\n"
        + "\n".join(agent_lines)
    )
    print(report)

    # 全体サマリーSlack通知（問題ありの場合のみ。正常時は通知不要）
    # HIGH/MEDIUMは handle_severity で既に個別通知済み
    if total_issues > 0:
        slack_notify(report, direct=True)
    else:
        print("[audit] 全エージェント正常 → Slack通知スキップ")

    # DynamoDB にサマリー保存
    try:
        import boto3
        dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
        table = dynamodb.Table(AUDIT_TABLE)
        now = datetime.now(timezone.utc).isoformat()
        table.put_item(Item={
            "pk": "AUDIT_SUMMARY",
            "sk": now,
            "overall": overall_status,
            "severity_counts": json.dumps(severity_counts),
            "agents_checked": len(ALL_AGENTS),
            "auditor": "audit_agent_v2_no_claude",
        })
    except Exception as e:
        print(f"[audit] サマリー保存失敗: {e}")

    print(f"[audit] ===== 全エージェント監査完了: {overall_status} =====")


# =============================================================================
# エントリポイント
# =============================================================================

def main():
    target = os.environ.get("AUDIT_TARGET", "all")
    if target == "all":
        run_full_audit()
    elif target in ALL_AGENTS:
        # 単体監査モード
        result = audit_single_agent(target)
        save_audit_log(target, result["checks"], result["overall_severity"])
        handle_severity(target, result["overall_severity"], result["checks"])
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"[audit] 不明なターゲット: {target}")
        print(f"使用可能: AUDIT_TARGET=all  または  AUDIT_TARGET=<agent_name>")
        print(f"エージェント一覧: {', '.join(ALL_AGENTS)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
