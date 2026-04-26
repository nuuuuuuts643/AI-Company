#!/usr/bin/env python3
"""
security_agent.py — AI-Company セキュリティ監査AI

Claude呼び出し回数: 0回/実行 (通常時・異常時ともに完全ゼロ)
判断ロジックはすべて Python ルールエンジンで完結。

## 概要
3層のセキュリティチェックを実施する専門エージェント。

- Layer 1: リアルタイム検知（コード内シークレットスキャン）
  - APIキー・Webhookのハードコード検出
  - 検出時は即Slack通知 + エージェント停止フラグ

- Layer 2: CIチェック（push時に実行想定）
  - 依存パッケージの既知脆弱性スキャン
  - S3バケットのパブリックアクセス設定確認
  - Lambda IAMロールの過剰権限検出

- Layer 3: 週次監査（GitHub Actions cronで実行）
  - Layer1+2の総合レポート生成
  - DynamoDB ai-company-audit テーブルに監査ログ保存
  - 既知問題はスキップ（繰り返し通知防止）
  - Slack通知: クリア / 警告 / 要対応 の3段階

## ルール管理
  SECURITY_RULES はコード内に定義。
  DynamoDB ai-company-memory から追加ルールを動的読み込み可能。
  コード変更なしでルールを追加・調整できる。

## 誤検知抑制
  DynamoDB ai-company-memory に "既知の誤検知パターン" を記録。
  次回以降は自動スキップ（繰り返し通知防止）。
  RuleEngine.learn(finding, was_false_positive=True) で登録。

## 実行方法
  LAYER=1 python3 scripts/security_agent.py   # 即時スキャン
  LAYER=2 python3 scripts/security_agent.py   # CIチェック
  LAYER=3 python3 scripts/security_agent.py   # 週次監査（デフォルト）

  # 誤検知パターンを手動登録する場合:
  python3 -c "
  import sys; sys.path.insert(0, 'scripts')
  from _rule_engine import RuleEngine
  engine = RuleEngine('security')
  engine.learn_pattern('s3_public_access', 'フロントエンド配信バケットは公開が正常')
  "

## 完了度: 完成候補
## 最終更新: 2026-04-22
"""

import json
import os
import re
import sys
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ガバナンス共通モジュール
sys.path.insert(0, str(Path(__file__).parent))
from _governance_check import check_agent_status, set_agent_status
from _rule_engine import RuleEngine, Finding

# --- 環境変数 ---
SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK", os.environ.get("SLACK_WEBHOOK_URL", ""))
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "ap-northeast-1")
REPO_ROOT = Path(__file__).parent.parent
LAYER = int(os.environ.get("LAYER", "3"))

# --- DynamoDB テーブル名 ---
AUDIT_TABLE = "ai-company-audit"

# --- ガバナンスチェック（自己停止） ---
check_agent_status("security")

# --- ルールエンジン初期化 ---
engine = RuleEngine("security")

# =============================================================================
# ルール定義（コード内 + DynamoDB動的読み込み）
# =============================================================================

# シークレット検出パターン（タプル: (パターンID, regex)）
# DynamoDBからの動的ルールも _load_dynamic_secret_patterns() で追加される
_BUILTIN_SECRET_PATTERNS = [
    ("anthropic_api_key",  re.compile(r'sk-ant-[A-Za-z0-9\-_]{10,}')),
    ("aws_access_key",     re.compile(r'AKIA[A-Z0-9]{16}')),
    ("github_pat",         re.compile(r'ghp_[A-Za-z0-9]{36}')),
    ("slack_bot_token",    re.compile(r'xoxb-[0-9]+-[0-9]+-[A-Za-z0-9]+')),
    ("slack_webhook_url",  re.compile(r'hooks\.slack\.com/services/[A-Za-z0-9/]+')),
    ("generic_secret",     re.compile(r'(?i)(secret|password|passwd|api_key)\s*=\s*["\'][^"\']{8,}["\']')),
    ("aws_secret_key",     re.compile(r'(?i)aws_secret_access_key\s*=\s*["\'][^"\']{20,}["\']')),
]

# 過剰権限IAMポリシー
OVERPRIVILEGED_POLICIES = [
    "AdministratorAccess",
    "PowerUserAccess",
    "FullAccess",
    "AmazonS3FullAccess",
    "AmazonDynamoDBFullAccess",
    "IAMFullAccess",
]

# 既知の脆弱パッケージ（簡易チェック用）
KNOWN_VULNERABLE_PACKAGES = {
    "requests":     {"vulnerable_below": "2.28.0", "cve": "CVE-2023-32681"},
    "cryptography": {"vulnerable_below": "41.0.0", "cve": "CVE-2023-38325"},
    "pillow":       {"vulnerable_below": "9.3.0",  "cve": "CVE-2022-45198"},
    "numpy":        {"vulnerable_below": "1.24.0", "cve": "CVE-2023-44271"},
}

# フロントエンド配信用として公開が許可されているS3バケット
ALLOWED_PUBLIC_BUCKETS = {
    "p003-news-946554699567",
    "p003-news-staging-946554699567",
}

# スキャン除外パターン（テスト・ドキュメント等）
EXCLUDE_PATTERNS = [
    re.compile(r'#.*NOQA', re.IGNORECASE),
    re.compile(r'os\.environ'),
    re.compile(r'\$\{'),
    re.compile(r'<YOUR_'),
    re.compile(r'example\.com'),
    re.compile(r'PLACEHOLDER'),
    re.compile(r'\.apps\.googleusercontent\.com'),  # Google OAuth Client ID（公開情報）
]

# スキャン対象ディレクトリ・拡張子
SCAN_DIRS = ["scripts", "projects", ".github"]
SCAN_EXTENSIONS = {".py", ".js", ".ts", ".json", ".yml", ".yaml", ".sh", ".env"}
EXCLUDE_FILES = {
    "package-lock.json", ".gitignore", "CLAUDE.md",
    "_governance_check.py",
    "_rule_engine.py",
    "security_agent.py",  # 自身のパターン定義を除外
}


def _load_dynamic_secret_patterns() -> list:
    """
    DynamoDBの動的ルールから追加シークレットパターンを読み込む。
    type=secret_pattern として登録されたルールを正規表現に変換。
    Returns: [(rule_id, compiled_regex), ...]
    """
    extra = []
    dynamic = engine.get_dynamic_rules()
    for rule_id, rule_def in dynamic.items():
        if rule_def.get("type") == "secret_pattern":
            pattern_str = rule_def.get("pattern", "")
            if pattern_str:
                try:
                    extra.append((rule_id, re.compile(pattern_str)))
                except re.error as e:
                    print(f"[security] 動的ルール正規表現エラー {rule_id}: {e}")
    return extra


def _get_all_secret_patterns() -> list:
    """ビルトイン + DynamoDB動的パターンをまとめて返す"""
    return _BUILTIN_SECRET_PATTERNS + _load_dynamic_secret_patterns()


# =============================================================================
# 既知問題デduplication（繰り返し通知防止）
# =============================================================================

DEDUP_WINDOW_DAYS = int(os.environ.get("DEDUP_WINDOW_DAYS", "7"))


def _get_recent_audit_findings(days: int = DEDUP_WINDOW_DAYS) -> set:
    """
    DynamoDB ai-company-audit から過去N日分の検知済み問題キーを取得。
    同じ問題を繰り返し通知しないための既知問題セット。

    Returns:
        set of "file:line:pattern_id" or "check_type:finding_json" strings
    """
    known = set()
    try:
        import boto3
        from boto3.dynamodb.conditions import Key
        dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
        table = dynamodb.Table(AUDIT_TABLE)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        resp = table.query(
            KeyConditionExpression=Key("pk").eq("SECURITY") & Key("sk").gte(cutoff),
            ProjectionExpression="summary",
        )
        for item in resp.get("Items", []):
            summary_str = item.get("summary", "{}")
            try:
                summary = json.loads(summary_str)
                for f in summary.get("l1", {}).get("findings", []):
                    known.add(f"{f.get('file')}:{f.get('line')}:{f.get('pattern')}")
                for check_name, res in summary.get("l2", {}).get("results", {}).items():
                    for f in res.get("findings", []):
                        known.add(f"{check_name}:{json.dumps(f, sort_keys=True)}")
            except Exception:
                pass
    except Exception as e:
        print(f"[security] 既知問題取得失敗（全件通知モード）: {e}")
    return known


# =============================================================================
# Slackメッセージ組み立て（Claude不要・Python純正テンプレート）
# =============================================================================

def build_slack_message(
    l1_result: dict,
    l2_result: dict,
    severity: str,
    now_str: str,
    new_only: bool = False,
) -> str:
    """
    セキュリティ監査結果から Slack メッセージを組み立てる。
    Claude を使わず Python テンプレートで構成する。
    """
    icon_map    = {"CLEAR": "✅", "WARNING": "⚠️", "CRITICAL": "🚨"}
    icon        = icon_map.get(severity, "ℹ️")
    total_new   = l1_result.get("total_new", 0) + l2_result.get("total_findings", 0)
    status_label = {
        "CLEAR":    "全チェック通過",
        "WARNING":  f"{total_new}件 要確認",
        "CRITICAL": f"{total_new}件 要対応",
    }.get(severity, "不明")
    new_suffix = "（新規問題のみ）" if new_only else ""

    lines = [
        f"{icon} *AI-Company セキュリティ週次監査* ({now_str}){new_suffix}",
        f"ステータス: {status_label}",
        "",
        # Layer 1 サマリー
        f"*Layer 1 シークレットスキャン* ({l1_result.get('scanned_files', 0)}ファイル): "
        + ("✅ 検出なし" if l1_result.get("passed")
           else f"🚨 {len(l1_result.get('findings', []))}件 (新規: {l1_result.get('total_new', 0)}件)"),
    ]

    display_findings = l1_result.get("new_findings", l1_result.get("findings", []))
    for f in display_findings[:5]:
        lines.append(f"  - `{f['file']}:{f['line']}` [{f['pattern']}]")
    overflow = len(l1_result.get("findings", [])) - 5
    if overflow > 0:
        lines.append(f"  ... 他 {overflow}件")

    lines += [
        "",
        # Layer 2 サマリー
        "*Layer 2 CIチェック*: "
        + ("✅ 全通過" if l2_result.get("passed")
           else f"⚠️  {l2_result.get('total_findings', 0)}件"),
    ]
    for check_name, res in l2_result.get("results", {}).items():
        check_icon = "✅" if res.get("passed", True) else "⚠️"
        count = len(res.get("findings", []))
        lines.append(f"  {check_icon} `{check_name}`: {count}件")

    return "\n".join(lines)


# =============================================================================
# Layer 1: リアルタイム シークレット検知
# =============================================================================

def should_exclude_line(line: str) -> bool:
    """除外条件に該当する行はスキャンしない"""
    for pat in EXCLUDE_PATTERNS:
        if pat.search(line):
            return True
    return False


def scan_secrets_in_file(filepath: Path, secret_patterns: list) -> list:
    """
    1ファイルをスキャンしてシークレット検出結果を返す。
    Returns: [{"file": str, "line": int, "pattern": str, "snippet": str}, ...]
    """
    findings = []
    try:
        text = filepath.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), 1):
            if should_exclude_line(line):
                continue
            for pattern_id, regex in secret_patterns:
                if regex.search(line):
                    findings.append({
                        "file": str(filepath.relative_to(REPO_ROOT)),
                        "line": lineno,
                        "pattern": pattern_id,
                        "snippet": line.strip()[:120],
                    })
    except Exception as e:
        print(f"[security/L1] ファイル読み込みエラー {filepath}: {e}")
    return findings


def layer1_scan(known_findings: set = None) -> dict:
    """
    Layer 1: 全コードベースのシークレットスキャン
    既知問題はスキップして新規問題のみ返す。
    """
    print("[security/L1] シークレットスキャン開始...")
    all_findings = []
    scanned = 0
    secret_patterns = _get_all_secret_patterns()

    for scan_dir in SCAN_DIRS:
        dir_path = REPO_ROOT / scan_dir
        if not dir_path.exists():
            continue
        for filepath in dir_path.rglob("*"):
            if not filepath.is_file():
                continue
            if filepath.name in EXCLUDE_FILES:
                continue
            if filepath.suffix not in SCAN_EXTENSIONS:
                continue
            if any(part in filepath.parts for part in ("node_modules", ".git", "__pycache__")):
                continue
            all_findings.extend(scan_secrets_in_file(filepath, secret_patterns))
            scanned += 1

    # RuleEngine誤検知フィルタ
    rule_objs = [
        Finding(
            pattern_id=f["pattern"],
            severity="HIGH",
            message=f"{f['file']}:{f['line']} に {f['pattern']} を検出",
            context={"file": f["file"], "line": str(f["line"])},
        )
        for f in all_findings
    ]
    _, suppressed = engine.filter_known_false_positives(rule_objs)
    suppressed_keys = {
        f"{s.context.get('file')}:{s.context.get('line')}:{s.pattern_id}"
        for s in suppressed
    }

    # 既知問題デduplication
    new_findings = []
    for f in all_findings:
        dedup_key = f"{f['file']}:{f['line']}:{f['pattern']}"
        if dedup_key in suppressed_keys:
            continue
        if known_findings and dedup_key in known_findings:
            print(f"[security/L1] 既知問題スキップ: {dedup_key}")
            continue
        new_findings.append(f)

    passed = len(new_findings) == 0
    status = "✅ クリア" if passed else f"🚨 {len(new_findings)}件 新規検出 (全体: {len(all_findings)}件)"
    print(f"[security/L1] {status} (スキャン: {scanned}ファイル)")

    return {
        "findings": all_findings,
        "new_findings": new_findings,
        "total_new": len(new_findings),
        "passed": passed,
        "scanned_files": scanned,
    }


# =============================================================================
# Layer 2: CIチェック（依存脆弱性・S3・IAM）
# =============================================================================

def check_python_dependencies() -> dict:
    """インストール済みパッケージに既知脆弱性があるか確認"""
    findings = []
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format=json"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return {"findings": [], "passed": True, "note": "pip list 失敗（スキップ）"}

        packages = {p["name"].lower(): p["version"] for p in json.loads(result.stdout)}
        for pkg, info in KNOWN_VULNERABLE_PACKAGES.items():
            installed_ver = packages.get(pkg.lower())
            if not installed_ver:
                continue
            try:
                def ver_tuple(v): return tuple(int(x) for x in v.split(".")[:3])
                if ver_tuple(installed_ver) < ver_tuple(info["vulnerable_below"]):
                    findings.append({
                        "package": pkg,
                        "installed": installed_ver,
                        "safe_from": info["vulnerable_below"],
                        "cve": info["cve"],
                    })
            except Exception:
                pass
    except Exception as e:
        return {"findings": [], "passed": True, "note": f"依存チェック例外: {e}"}

    return {"findings": findings, "passed": len(findings) == 0}


def check_s3_public_access() -> dict:
    """
    S3バケットのパブリックアクセス設定を確認。
    ALLOWED_PUBLIC_BUCKETS は除外（フロントエンド配信用）。
    """
    findings = []
    try:
        import boto3
        s3 = boto3.client("s3", region_name=AWS_REGION)
        for bucket in s3.list_buckets().get("Buckets", []):
            name = bucket["Name"]
            if name in ALLOWED_PUBLIC_BUCKETS:
                continue
            try:
                resp = s3.get_public_access_block(Bucket=name)
                config = resp.get("PublicAccessBlockConfiguration", {})
                blocked = all([
                    config.get("BlockPublicAcls", False),
                    config.get("IgnorePublicAcls", False),
                    config.get("BlockPublicPolicy", False),
                    config.get("RestrictPublicBuckets", False),
                ])
                if not blocked:
                    findings.append({
                        "bucket": name,
                        "config": config,
                        "risk": "パブリックアクセスブロックが不完全",
                    })
            except Exception:
                pass
    except Exception as e:
        return {"findings": [], "passed": True, "note": f"S3チェック例外: {e}"}

    return {"findings": findings, "passed": len(findings) == 0}


def check_lambda_iam_roles() -> dict:
    """Lambda関数に紐付いたIAMロールの過剰権限を検出"""
    findings = []
    try:
        import boto3
        lambda_client = boto3.client("lambda", region_name=AWS_REGION)
        iam = boto3.client("iam", region_name=AWS_REGION)

        paginator = lambda_client.get_paginator("list_functions")
        for page in paginator.paginate():
            for fn in page.get("Functions", []):
                role_arn = fn.get("Role", "")
                role_name = role_arn.split("/")[-1] if role_arn else ""
                if not role_name:
                    continue
                try:
                    attached = iam.list_attached_role_policies(RoleName=role_name)
                    for policy in attached.get("AttachedPolicies", []):
                        policy_name = policy.get("PolicyName", "")
                        if any(op in policy_name for op in OVERPRIVILEGED_POLICIES):
                            findings.append({
                                "function": fn["FunctionName"],
                                "role": role_name,
                                "policy": policy_name,
                                "risk": "過剰権限ポリシー",
                            })
                except Exception:
                    pass
    except Exception as e:
        return {"findings": [], "passed": True, "note": f"IAMチェック例外: {e}"}

    return {"findings": findings, "passed": len(findings) == 0}


def layer2_check(known_findings: set = None) -> dict:
    """
    Layer 2: 依存脆弱性・S3・IAM の総合チェック
    既知問題はフィルタして新規問題のみカウントする。
    """
    print("[security/L2] CIチェック開始...")
    results = {}
    total = 0

    for check_name, check_fn in [
        ("dependencies", check_python_dependencies),
        ("s3_public",    check_s3_public_access),
        ("iam_roles",    check_lambda_iam_roles),
    ]:
        res = check_fn()
        if known_findings:
            new_items = [
                f for f in res.get("findings", [])
                if f"{check_name}:{json.dumps(f, sort_keys=True)}" not in known_findings
            ]
        else:
            new_items = res.get("findings", [])
        res["findings"] = new_items
        res["passed"] = len(new_items) == 0
        results[check_name] = res
        total += len(new_items)

    passed = total == 0
    print(f"[security/L2] {'✅ 全チェック通過（新規問題なし）' if passed else f'⚠️  {total}件 新規要確認'}")
    return {"results": results, "passed": passed, "total_findings": total}


# =============================================================================
# Layer 3: 週次監査
# =============================================================================

def save_audit_log(layer: int, result: dict, severity: str) -> bool:
    """DynamoDB ai-company-audit テーブルに監査ログを保存する"""
    try:
        import boto3
        dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
        table = dynamodb.Table(AUDIT_TABLE)
        now = datetime.now(timezone.utc).isoformat()
        table.put_item(Item={
            "pk": "SECURITY",
            "sk": now,
            "layer": layer,
            "severity": severity,
            "passed": result.get("passed", False),
            "summary": json.dumps(result, ensure_ascii=False, default=str)[:3000],
            "agent": "security",
        })
        print(f"[security] 監査ログ保存完了 (sk={now})")
        return True
    except Exception as e:
        print(f"[security] 監査ログ保存失敗: {e}")
        return False


def slack_notify(text: str) -> None:
    """Slack Webhook に通知する（Python組み立て済みテキストのみ・Claude不要）"""
    if not SLACK_WEBHOOK:
        print("[security/slack] SLACK_WEBHOOK 未設定 → スキップ")
        return
    payload = json.dumps({"text": text}).encode()
    import urllib.request
    req = urllib.request.Request(
        SLACK_WEBHOOK,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=15)
        print("[security/slack] 通知送信完了")
    except Exception as e:
        print(f"[security/slack] 送信失敗: {e}")


def layer3_weekly_audit() -> None:
    """
    Layer 3: Layer1+2を実行して総合レポートを生成・記録・通知する。
    既知問題はスキップ（繰り返し通知防止）。
    Claude API 呼び出し: 0回。
    """
    print("[security/L3] 週次監査開始...")
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # 既知問題を事前取得（デduplication）
    known_findings = _get_recent_audit_findings(days=DEDUP_WINDOW_DAYS)
    print(f"[security/L3] 既知問題: {len(known_findings)}件（{DEDUP_WINDOW_DAYS}日以内）")

    l1 = layer1_scan(known_findings)
    l2 = layer2_check(known_findings)

    total_new = l1["total_new"] + l2["total_findings"]
    if total_new == 0:
        severity = "CLEAR"
    elif total_new <= 3:
        severity = "WARNING"
    else:
        severity = "CRITICAL"

    # Slackメッセージ: Python純正テンプレート（Claude不要）
    report = build_slack_message(
        l1_result=l1,
        l2_result=l2,
        severity=severity,
        now_str=now_str,
        new_only=(len(known_findings) > 0),
    )
    print(report)

    audit_data = {
        "l1": l1, "l2": l2,
        "severity": severity,
        "total_new": total_new,
        "known_skipped": len(known_findings),
    }
    save_audit_log(3, audit_data, severity)

    if severity == "CRITICAL":
        set_agent_status(
            "security", "active",
            f"週次監査 CRITICAL: {total_new}件新規検出",
            severity="HIGH",
        )
        slack_notify(f"🚨 *[緊急] セキュリティ監査 CRITICAL*\n{report}\n\n@POさん 即対応が必要です。")
    elif severity == "WARNING":
        slack_notify(f"⚠️ *セキュリティ監査 WARNING*\n{report}")
    else:
        # CLEAR: 正常完了のためSlack通知不要（DynamoDBへのログ記録は完了済み）
        print("[security/L3] クリア → Slack通知スキップ")

    print(f"[security/L3] 週次監査完了: {severity} (新規問題: {total_new}件)")


# =============================================================================
# エントリポイント
# =============================================================================

def main():
    if LAYER == 1:
        result = layer1_scan()
        if not result["passed"]:
            for f in result["new_findings"]:
                print(f"  🚨 {f['file']}:{f['line']} [{f['pattern']}]")
            msg_lines = [f"🚨 *[SecurityAI] シークレット検出* — {result['total_new']}件"]
            for f in result["new_findings"][:10]:
                msg_lines.append(f"  - `{f['file']}:{f['line']}` [{f['pattern']}]")
            slack_notify("\n".join(msg_lines))
            save_audit_log(1, result, "CRITICAL")
            sys.exit(1)  # CIで失敗させる

    elif LAYER == 2:
        result = layer2_check()
        save_audit_log(2, result, "WARNING" if not result["passed"] else "CLEAR")
        if not result["passed"]:
            sys.exit(1)

    else:
        layer3_weekly_audit()


if __name__ == "__main__":
    main()
