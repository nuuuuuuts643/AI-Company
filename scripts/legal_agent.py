#!/usr/bin/env python3
"""
legal_agent.py — AI-Company リーガルチェックAI

## 概要
3層の法的リスクチェックを実施する専門エージェント。

- Layer 1: アセット追加時チェック
  - /projects/P002-flutter-game/assets/ の新規ファイル検知
  - ライセンス確認チェックリストをDynamoDBに記録
  - Suno（商用OK条件）/ Midjourney（Proプラン確認）の利用規約整合

- Layer 2: デプロイ前チェック
  - 著作権リスク項目: RSS利用規約・記事要約の範囲（見出し+2文）
  - privacy.htmlの存在確認、App Store向けプライバシーポリシー整合
  - AdSense申請要件（HTTPS・オリジナルコンテンツ）

- Layer 3: 月次監査
  - 利用サービスの規約変更チェック（Suno/Midjourney/AWS/AdSense）
  - Claudeへのプロンプトで最新規約の要確認フラグ立て
  - Slack通知 + DynamoDB記録

## 実行方法
  LAYER=1 python3 scripts/legal_agent.py   # アセットチェック
  LAYER=2 python3 scripts/legal_agent.py   # デプロイ前チェック
  LAYER=3 python3 scripts/legal_agent.py   # 月次監査（デフォルト）

## 完了度: 完成候補
## 最終更新: 2026-04-22
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ガバナンス共通モジュール
sys.path.insert(0, str(Path(__file__).parent))
from _governance_check import check_agent_status

# --- 環境変数 ---
SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK", os.environ.get("SLACK_WEBHOOK_URL", ""))
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "ap-northeast-1")
REPO_ROOT = Path(__file__).parent.parent
LAYER = int(os.environ.get("LAYER", "3"))

# --- DynamoDB テーブル ---
AUDIT_TABLE = "ai-company-audit"

# --- ガバナンスチェック ---
check_agent_status("legal")

# =============================================================================
# 共通ユーティリティ
# =============================================================================

def slack_notify(text: str) -> None:
    """Slack Webhook に通知する"""
    if not SLACK_WEBHOOK:
        print("[legal/slack] SLACK_WEBHOOK 未設定 → スキップ")
        return
    payload = json.dumps({"text": text}).encode()
    req = urllib.request.Request(
        SLACK_WEBHOOK,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=15)
        print("[legal/slack] 通知送信完了")
    except Exception as e:
        print(f"[legal/slack] 送信失敗: {e}")


def save_audit_log(layer: int, result: dict, severity: str) -> bool:
    """DynamoDB ai-company-audit にリーガルチェックログを保存"""
    try:
        import boto3
        dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
        table = dynamodb.Table(AUDIT_TABLE)
        now = datetime.now(timezone.utc).isoformat()
        table.put_item(Item={
            "pk": "LEGAL",
            "sk": now,
            "layer": layer,
            "severity": severity,
            "passed": result.get("passed", False),
            "summary": json.dumps(result, ensure_ascii=False, default=str)[:3000],
            "agent": "legal",
        })
        print(f"[legal] 監査ログ保存完了 (sk={now})")
        return True
    except Exception as e:
        print(f"[legal] 監査ログ保存失敗: {e}")
        return False


def call_claude(prompt: str, max_tokens: int = 800) -> str:
    """Anthropic Messages API を呼び出してリーガル判断を取得する"""
    if not ANTHROPIC_API_KEY:
        return "(ANTHROPIC_API_KEY 未設定 → Claude呼び出しスキップ)"
    payload = json.dumps({
        "model": "claude-sonnet-4-6",
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
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read())
        return body["content"][0]["text"].strip()
    except Exception as e:
        return f"(Claude呼び出し失敗: {e})"


# =============================================================================
# Layer 1: アセット追加時ライセンスチェック
# =============================================================================

# アセットディレクトリ
ASSET_DIRS = [
    "projects/P002-flutter-game/assets",
    "projects/P003-news-timeline/frontend",
]

# ライセンス確認済みとして扱う拡張子（コードファイル）
CODE_EXTENSIONS = {".py", ".js", ".ts", ".dart", ".html", ".css", ".json", ".yaml", ".yml"}

# 要ライセンス確認の拡張子（メディアファイル）
MEDIA_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".mp3", ".wav", ".ogg", ".mp4", ".ttf", ".otf"}

# ライセンス記録ファイル
LICENSE_REGISTRY = REPO_ROOT / "docs" / "asset-license-registry.json"


def load_license_registry() -> dict:
    """既存のライセンス台帳を読み込む"""
    if LICENSE_REGISTRY.exists():
        try:
            return json.loads(LICENSE_REGISTRY.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_license_registry(registry: dict) -> None:
    """ライセンス台帳を保存する"""
    LICENSE_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    LICENSE_REGISTRY.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def layer1_asset_check() -> dict:
    """
    Layer 1: アセットディレクトリの新規メディアファイルを検出し、
    ライセンス確認が必要なものをリストアップする。
    """
    print("[legal/L1] アセットライセンスチェック開始...")
    registry = load_license_registry()
    new_assets = []
    unregistered = []

    for asset_dir in ASSET_DIRS:
        dir_path = REPO_ROOT / asset_dir
        if not dir_path.exists():
            continue
        for filepath in dir_path.rglob("*"):
            if not filepath.is_file():
                continue
            if filepath.suffix.lower() not in MEDIA_EXTENSIONS:
                continue
            rel_path = str(filepath.relative_to(REPO_ROOT))
            if rel_path not in registry:
                new_assets.append(rel_path)
                unregistered.append({
                    "file": rel_path,
                    "extension": filepath.suffix.lower(),
                    "size_kb": round(filepath.stat().st_size / 1024, 1),
                    "checklist": _get_license_checklist(filepath.suffix.lower()),
                })

    # 新規アセットをDynamoDBに記録
    if unregistered:
        _record_unregistered_assets(unregistered)

    passed = len(unregistered) == 0
    print(f"[legal/L1] {'✅ 新規アセットなし' if passed else f'⚠️  {len(unregistered)}件 ライセンス未確認'}")
    return {
        "passed": passed,
        "unregistered_assets": unregistered,
        "total_registered": len(registry),
    }


def _get_license_checklist(extension: str) -> list:
    """ファイルタイプ別のライセンス確認チェックリストを返す"""
    if extension in {".mp3", ".wav", ".ogg"}:
        return [
            "Suno AIで生成した場合: Proプラン以上 + 商用利用条項を確認",
            "外部素材の場合: CC0またはRoyalty Free商用ライセンスを確認",
            "クレジット表記が必要か確認",
        ]
    elif extension in {".png", ".jpg", ".jpeg", ".gif", ".svg"}:
        return [
            "Midjourney生成の場合: Proプラン(商用OK)か確認",
            "外部素材の場合: CC0/RF/購入済みライセンスを確認",
            "App Store申請時にスクリーンショットとして使う場合の規約確認",
        ]
    elif extension in {".ttf", ".otf"}:
        return [
            "フォントライセンス(OFL/商用ライセンス)を確認",
            "埋め込み・再配布の可否を確認",
            "LICENSE.txtをassets/fonts/に配置",
        ]
    return ["ライセンス確認が必要"]


def _record_unregistered_assets(assets: list) -> None:
    """未登録アセットをDynamoDBに記録する"""
    try:
        import boto3
        dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
        table = dynamodb.Table(AUDIT_TABLE)
        now = datetime.now(timezone.utc).isoformat()
        for asset in assets:
            table.put_item(Item={
                "pk": "LEGAL_ASSET",
                "sk": f"{now}#{asset['file']}",
                "file": asset["file"],
                "extension": asset["extension"],
                "size_kb": str(asset["size_kb"]),
                "checklist": json.dumps(asset["checklist"], ensure_ascii=False),
                "status": "unregistered",
                "agent": "legal",
            })
    except Exception as e:
        print(f"[legal/L1] アセット記録失敗: {e}")


# =============================================================================
# Layer 2: デプロイ前チェック
# =============================================================================

# RSS利用規約確認済みソース（手動で承認したもの）
APPROVED_RSS_SOURCES = {
    "yomiuri.co.jp": "CC-BY相当・見出し+2文以内で要約OK",
    "mainichi.jp": "見出し転載可・本文要約2文以内",
    "asahi.com": "見出し転載可・本文不可・リンク必須",
    "nikkei.com": "見出し転載可・本文不可",
    "itmedia.co.jp": "見出し+リード2文以内OK",
    "gizmodo.jp": "見出し+リード2文以内OK",
    "diamond.jp": "見出し転載可・本文不可",
    "news.google.com": "Googleアグリゲーター経由・元ソース規約に従う",
}

# プライバシーポリシーページのパス
PRIVACY_PAGE_PATHS = [
    "projects/P003-news-timeline/frontend/privacy.html",
]

# AdSense要件確認項目
ADSENSE_REQUIREMENTS = [
    ("HTTPS対応", "setup-domain.sh実行済みか確認"),
    ("プライバシーポリシー", "privacy.htmlの存在確認"),
    ("オリジナルコンテンツ", "AI要約+リンクがコンテンツの主体か確認"),
    ("ナビゲーション", "トップページからのナビゲーション構造"),
    ("広告配置", "コンテンツと広告の比率（コンテンツ>広告）"),
]


def layer2_predeploy_check() -> dict:
    """
    Layer 2: デプロイ前の法的リスクチェック
    """
    print("[legal/L2] デプロイ前リーガルチェック開始...")
    issues = []
    warnings = []

    # --- 1. プライバシーポリシーページ存在確認 ---
    for privacy_path in PRIVACY_PAGE_PATHS:
        full_path = REPO_ROOT / privacy_path
        if not full_path.exists():
            issues.append(f"❌ プライバシーポリシーページ未作成: {privacy_path}")
        else:
            content = full_path.read_text(encoding="utf-8", errors="ignore")
            # 必須記載事項の確認
            required_terms = ["個人情報", "Cookie", "広告", "お問い合わせ"]
            missing = [t for t in required_terms if t not in content]
            if missing:
                warnings.append(f"⚠️  privacy.html に記載不足: {', '.join(missing)}")

    # --- 2. RSS利用規約整合チェック ---
    fetcher_path = REPO_ROOT / "projects/P003-news-timeline/lambda/fetcher/handler.py"
    if fetcher_path.exists():
        fetcher_code = fetcher_path.read_text(encoding="utf-8", errors="ignore")
        # URLパターンから利用ソースを抽出
        import re
        urls = re.findall(r'https?://(?:feeds\.|rss\.)?([a-zA-Z0-9\-\.]+\.[a-z]{2,})', fetcher_code)
        unique_domains = set(d.replace("feeds.", "").replace("rss.", "") for d in urls)
        unapproved = [d for d in unique_domains if d not in APPROVED_RSS_SOURCES and len(d) > 5]
        if unapproved:
            warnings.append(f"⚠️  未承認RSSソース（規約確認が必要）: {', '.join(list(unapproved)[:5])}")

    # --- 3. 記事要約の範囲チェック（プロンプト内の見出し制限） ---
    if fetcher_path.exists():
        fetcher_code = fetcher_path.read_text(encoding="utf-8", errors="ignore")
        # "full_text"や"全文"を使っているか確認
        if "full_text" in fetcher_code.lower() or "全文" in fetcher_code:
            issues.append("❌ 記事全文取得の可能性あり — 見出し+2文以内の要約に制限すること")
        # 要約文字数制限の確認
        import re
        max_chars = re.findall(r'max_chars\s*=\s*(\d+)', fetcher_code)
        for mc in max_chars:
            if int(mc) > 500:
                warnings.append(f"⚠️  要約文字数が多すぎる可能性: max_chars={mc} (推奨: 200以下)")

    # --- 4. AdSense申請要件チェック ---
    index_path = REPO_ROOT / "projects/P003-news-timeline/frontend/index.html"
    if index_path.exists():
        index_content = index_path.read_text(encoding="utf-8", errors="ignore")
        if "adsbygoogle" not in index_content and "ninja" not in index_content:
            warnings.append("⚠️  AdSenseまたは忍者AdMaxコードが未設置")
        # HTTPS確認（CSP/canonical）
        if "https://flotopic.com" not in index_content:
            warnings.append("⚠️  canonical URLがHTTPSになっていない可能性")

    # --- 5. App Store向けプライバシーポリシー ---
    flutter_info = REPO_ROOT / "projects/P002-flutter-game/ios/Runner/Info.plist"
    if flutter_info.exists():
        info_content = flutter_info.read_text(encoding="utf-8", errors="ignore")
        if "NSPrivacyUsageDescription" not in info_content and "NSUserTrackingUsageDescription" not in info_content:
            warnings.append("⚠️  iOS Info.plist にプライバシー許可説明文が未記載")

    passed = len(issues) == 0
    print(f"[legal/L2] {'✅ クリア' if passed else f'❌ {len(issues)}件 問題'} / ⚠️  {len(warnings)}件 警告")
    return {
        "passed": passed,
        "issues": issues,
        "warnings": warnings,
    }


# =============================================================================
# Layer 3: 月次規約変更チェック
# =============================================================================

# 監視対象サービスとその規約URL
MONITORED_SERVICES = [
    {
        "name": "Suno AI",
        "tos_url": "https://suno.com/terms",
        "key_terms": ["commercial", "subscription", "revenue", "monetize"],
        "risk_note": "商用利用: Proプラン($8/月)以上で商用OK。収益シェア条項に注意。",
    },
    {
        "name": "Midjourney",
        "tos_url": "https://docs.midjourney.com/docs/terms-of-service",
        "key_terms": ["commercial", "enterprise", "ownership", "copyright"],
        "risk_note": "商用利用: Proプラン($60/月)以上。企業年収25万ドル超はEnterpriseが必要。",
    },
    {
        "name": "AWS",
        "tos_url": "https://aws.amazon.com/service-terms/",
        "key_terms": ["acceptable use", "prohibited", "AI", "generative"],
        "risk_note": "AWS Bedrock/AI利用規約の変更に注意。",
    },
    {
        "name": "Google AdSense",
        "tos_url": "https://support.google.com/adsense/answer/48182",
        "key_terms": ["AI-generated", "content policy", "invalid click"],
        "risk_note": "AI生成コンテンツへの広告掲載ポリシーは変更頻度高い。",
    },
    {
        "name": "Anthropic",
        "tos_url": "https://www.anthropic.com/legal/usage-policy",
        "key_terms": ["commercial", "automated", "content", "prohibited"],
        "risk_note": "Claude APIの利用規約。自動化・大量処理の制限に注意。",
    },
]


def layer3_monthly_audit() -> None:
    """
    Layer 3: 月次規約変更チェック + Claudeによる要約・フラグ立て
    """
    print("[legal/L3] 月次規約監査開始...")
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    flags = []

    # --- 各サービスの規約チェック（Claude呼び出しで要確認フラグを立てる）---
    for service in MONITORED_SERVICES:
        print(f"[legal/L3] {service['name']} 規約チェック中...")

        # Claudeに規約の変更リスクを判断させる
        prompt = f"""あなたはAI企業の法務担当AIです。以下のサービスの利用規約について、
直近で問題になりそうな条項変更がないか確認してください。

サービス名: {service['name']}
規約URL: {service['tos_url']}
主な注意点: {service['risk_note']}
監視キーワード: {', '.join(service['key_terms'])}

以下の形式で簡潔に回答してください（日本語）:
1. 現在の商用利用条件: （1-2文）
2. AI生成コンテンツへの制限: （1-2文）
3. 要確認フラグ: 🟢なし / 🟡要注意 / 🔴要対応（理由を1文）

注: 最新情報がわからない場合は「最新規約の手動確認を推奨」と記載してください。"""

        assessment = call_claude(prompt, max_tokens=400)
        flag_level = "🟢"
        if "🔴" in assessment:
            flag_level = "🔴"
        elif "🟡" in assessment:
            flag_level = "🟡"

        flags.append({
            "service": service["name"],
            "flag": flag_level,
            "assessment": assessment,
            "tos_url": service["tos_url"],
        })

    # レポート生成
    report_lines = [
        f"⚖️  *AI-Company リーガル月次監査* ({now_str})",
        "",
    ]
    critical_flags = []
    for item in flags:
        report_lines.append(f"{item['flag']} *{item['service']}*")
        # assessmentの最初の3行のみ
        short_assess = "\n".join(item["assessment"].split("\n")[:4])
        report_lines.append(f"  {short_assess}")
        if item["flag"] == "🔴":
            critical_flags.append(item["service"])

    report = "\n".join(report_lines)
    print(report)

    # 重大度判定
    if critical_flags:
        severity = "CRITICAL"
        slack_notify(
            f"🔴 *[LegalAI] 月次規約監査 — 要対応*\n{report}\n\n"
            f"@POさん: {', '.join(critical_flags)} の規約変更を確認してください。"
        )
    elif any(f["flag"] == "🟡" for f in flags):
        severity = "WARNING"
        slack_notify(f"🟡 *[LegalAI] 月次規約監査 — 要注意*\n{report}")
    else:
        # CLEAR: 正常完了のためSlack通知不要（DynamoDBへのログ記録は完了済み）
        severity = "CLEAR"
        print("[legal/L3] クリア → Slack通知スキップ")

    # DynamoDB保存
    save_audit_log(3, {"flags": flags, "severity": severity}, severity)
    print(f"[legal/L3] 月次規約監査完了: {severity}")


# =============================================================================
# エントリポイント
# =============================================================================

def main():
    if LAYER == 1:
        result = layer1_asset_check()
        if not result["passed"]:
            slack_notify(
                f"⚠️  *[LegalAI] 未確認アセット検出* — {len(result['unregistered_assets'])}件\n"
                + "\n".join(f"  - {a['file']}" for a in result["unregistered_assets"][:10])
                + "\ndocs/asset-license-registry.json にライセンス情報を追加してください。"
            )
        save_audit_log(1, result, "WARNING" if not result["passed"] else "CLEAR")
    elif LAYER == 2:
        result = layer2_predeploy_check()
        save_audit_log(2, result, "CRITICAL" if not result["passed"] else (
            "WARNING" if result.get("warnings") else "CLEAR"
        ))
        if not result["passed"]:
            issues_text = "\n".join(result["issues"])
            slack_notify(f"❌ *[LegalAI] デプロイ前チェック NG*\n{issues_text}")
            sys.exit(1)
        if result.get("warnings"):
            warnings_text = "\n".join(result["warnings"])
            slack_notify(f"⚠️  *[LegalAI] デプロイ前警告*\n{warnings_text}")
    else:
        layer3_monthly_audit()


if __name__ == "__main__":
    main()
