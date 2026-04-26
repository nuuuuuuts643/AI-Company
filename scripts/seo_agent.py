#!/usr/bin/env python3
"""
SEOモニタリングエージェント (SEO Agent)
- flotopic.com の sitemap.xml / robots.txt を確認
- ページタイトル・メタディスクリプションを確認
- S3 の api/topics.json から generatedSummary 未設定トピックを特定
- 不足上位5件に対して Claude Haiku でメタディスクリプション生成
- 結果を Slack 通知 + dashboard/seo-log.md に保存
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ─────────────────────────────────────────────
# 設定
# ─────────────────────────────────────────────
FLOTOPIC_BASE_URL = "https://flotopic.com"
SITEMAP_URL = f"{FLOTOPIC_BASE_URL}/sitemap.xml"
ROBOTS_URL = f"{FLOTOPIC_BASE_URL}/robots.txt"
TOP_PAGE_URL = FLOTOPIC_BASE_URL

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"

S3_BUCKET_DEFAULT = "flotopic-frontend"
TOPICS_JSON_KEY = "api/topics.json"

EXPECTED_TITLE_KEYWORDS = ["flotopic", "フロトピック", "ニュース", "news"]
EXPECTED_DESC_MIN_LEN = 50

JST = timezone(timedelta(hours=9))

SEO_LOG_PATH = Path(__file__).parent.parent / "dashboard" / "seo-log.md"


def _env(key: str) -> str:
    val = os.environ.get(key, "")
    if not val:
        print(f"[WARN] 環境変数 {key} が未設定")
    return val


# ─────────────────────────────────────────────
# HTTP ユーティリティ
# ─────────────────────────────────────────────
def http_get(url: str, headers: dict | None = None, timeout: int = 15) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception as e:
        print(f"[ERROR] GET {url}: {e}")
        return 0, b""


def http_post(url: str, payload: dict, headers: dict) -> tuple[int, bytes]:
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


# ─────────────────────────────────────────────
# サイトマップチェック
# ─────────────────────────────────────────────
def check_sitemap() -> dict:
    result = {"ok": False, "status_code": 0, "url_count": 0, "issues": []}

    status, body = http_get(SITEMAP_URL)
    result["status_code"] = status

    if status != 200:
        result["issues"].append(f"sitemap.xml が取得できない: HTTP {status}")
        return result

    content = body.decode("utf-8", errors="replace")
    if "<urlset" not in content and "<sitemapindex" not in content:
        result["issues"].append("sitemap.xml に <urlset> または <sitemapindex> タグがない")
        return result

    url_count = content.count("<loc>")
    result["url_count"] = url_count

    if url_count == 0:
        result["issues"].append("sitemap.xml に <loc> エントリが0件")

    result["ok"] = len(result["issues"]) == 0
    return result


# ─────────────────────────────────────────────
# robots.txt チェック
# ─────────────────────────────────────────────
def check_robots() -> dict:
    result = {"ok": False, "status_code": 0, "has_sitemap_ref": False, "issues": []}

    status, body = http_get(ROBOTS_URL)
    result["status_code"] = status

    if status != 200:
        result["issues"].append(f"robots.txt が取得できない: HTTP {status}")
        return result

    content = body.decode("utf-8", errors="replace")
    result["has_sitemap_ref"] = "Sitemap:" in content

    if not result["has_sitemap_ref"]:
        result["issues"].append("robots.txt に Sitemap: 参照がない")

    if "User-agent:" not in content:
        result["issues"].append("robots.txt に User-agent: 行がない")

    result["ok"] = len(result["issues"]) == 0
    return result


# ─────────────────────────────────────────────
# トップページ メタ情報チェック
# ─────────────────────────────────────────────
def check_meta_tags() -> dict:
    result = {
        "ok": False,
        "status_code": 0,
        "title": None,
        "description": None,
        "issues": [],
    }

    status, body = http_get(TOP_PAGE_URL)
    result["status_code"] = status

    if status != 200:
        result["issues"].append(f"トップページが取得できない: HTTP {status}")
        return result

    content = body.decode("utf-8", errors="replace")

    # タイトル抽出
    title_match = re.search(r"<title[^>]*>(.*?)</title>", content, re.IGNORECASE | re.DOTALL)
    if title_match:
        result["title"] = title_match.group(1).strip()
        title_lower = result["title"].lower()
        if not any(kw.lower() in title_lower for kw in EXPECTED_TITLE_KEYWORDS):
            result["issues"].append(
                f"タイトルにキーワードがない: '{result['title']}'"
            )
    else:
        result["issues"].append("<title> タグが見つからない")

    # メタディスクリプション抽出
    desc_match = re.search(
        r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']',
        content,
        re.IGNORECASE | re.DOTALL,
    )
    if not desc_match:
        desc_match = re.search(
            r'<meta\s+content=["\'](.*?)["\']\s+name=["\']description["\']',
            content,
            re.IGNORECASE | re.DOTALL,
        )

    if desc_match:
        result["description"] = desc_match.group(1).strip()
        if len(result["description"]) < EXPECTED_DESC_MIN_LEN:
            result["issues"].append(
                f"メタディスクリプションが短すぎる: {len(result['description'])}文字"
            )
    else:
        result["issues"].append("meta description タグが見つからない")

    result["ok"] = len(result["issues"]) == 0
    return result


# ─────────────────────────────────────────────
# S3 topics.json 分析
# ─────────────────────────────────────────────
def analyze_topics(bucket: str) -> dict:
    result = {
        "ok": False,
        "total_topics": 0,
        "missing_summary_count": 0,
        "top_missing": [],
        "issues": [],
    }

    if not bucket:
        result["issues"].append("S3_BUCKET 未設定")
        return result

    s3_url = f"https://{bucket}.s3.ap-northeast-1.amazonaws.com/{TOPICS_JSON_KEY}"
    status, body = http_get(s3_url)

    if status != 200:
        # フォールバック: S3ウェブサイトエンドポイント
        s3_url = f"http://{bucket}.s3-website-ap-northeast-1.amazonaws.com/{TOPICS_JSON_KEY}"
        status, body = http_get(s3_url)

    if status != 200:
        result["issues"].append(f"topics.json が取得できない: HTTP {status} ({s3_url})")
        return result

    try:
        data = json.loads(body)
    except Exception as e:
        result["issues"].append(f"topics.json のJSONパース失敗: {e}")
        return result

    # topics フィールドの取得（複数パターン対応）
    topics = data if isinstance(data, list) else (
        data.get("topics") or data.get("articles") or []
    )

    result["total_topics"] = len(topics)

    missing = []
    for topic in topics:
        summary = topic.get("generatedSummary") or topic.get("summary") or ""
        if not summary or len(summary.strip()) < 20:
            missing.append(topic)

    result["missing_summary_count"] = len(missing)

    # スコア上位5件を選出
    missing_sorted = sorted(
        missing,
        key=lambda t: t.get("score", 0) or t.get("article_count", 0),
        reverse=True,
    )
    result["top_missing"] = missing_sorted[:5]

    if result["missing_summary_count"] > 0:
        result["issues"].append(
            f"generatedSummary 未設定トピック: {result['missing_summary_count']}件"
        )

    result["ok"] = True
    return result


# ─────────────────────────────────────────────
# Claude による メタディスクリプション生成
# ─────────────────────────────────────────────
def generate_meta_description(topic: dict, api_key: str) -> str:
    if not api_key:
        return ""

    title = topic.get("title") or topic.get("id") or "（タイトル不明）"
    articles = topic.get("articles") or []
    article_titles = [a.get("title", "") for a in articles[:5] if a.get("title")]
    articles_text = "\n".join(f"- {t}" for t in article_titles) if article_titles else "（記事情報なし）"

    prompt = f"""あなたはSEO専門家です。以下のニューストピックに対して、検索エンジン向けのメタディスクリプションを生成してください。

## トピックタイトル
{title}

## 関連記事（一部）
{articles_text}

## 要件
- 日本語で120〜160文字
- 検索ユーザーの興味を引く具体的な内容
- キーワードを自然に含む
- 「。」で終わる完結した文章
- メタディスクリプション本文のみ出力（説明文・引用符不要）
"""

    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 300,
        "messages": [{"role": "user", "content": prompt}],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    status, body = http_post(ANTHROPIC_API_URL, payload, headers)
    if status != 200:
        print(f"[ERROR] Claude API エラー: {status}")
        return ""

    try:
        resp = json.loads(body)
        return resp["content"][0]["text"].strip()
    except Exception:
        return ""


# ─────────────────────────────────────────────
# Slack 通知
# ─────────────────────────────────────────────
def send_slack(webhook_url: str, text: str) -> bool:
    if not webhook_url:
        print("[WARN] SLACK_WEBHOOK 未設定 — Slack通知スキップ")
        return False

    payload = {"text": text}
    headers = {"Content-Type": "application/json"}
    status, _ = http_post(webhook_url, payload, headers)
    if status not in (200, 204):
        print(f"[ERROR] Slack通知失敗: HTTP {status}")
        return False
    return True


# ─────────────────────────────────────────────
# ログ保存
# ─────────────────────────────────────────────
def append_log(content: str) -> None:
    SEO_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SEO_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(content + "\n")
    print(f"[INFO] ログ追記: {SEO_LOG_PATH}")


# ─────────────────────────────────────────────
# エントリポイント
# ─────────────────────────────────────────────
def main():
    anthropic_key = _env("ANTHROPIC_API_KEY")
    slack_webhook = _env("SLACK_WEBHOOK")
    s3_bucket = os.environ.get("S3_BUCKET", S3_BUCKET_DEFAULT)

    now_jst = datetime.now(JST)
    now_str = now_jst.strftime("%Y-%m-%d %H:%M JST")
    print(f"[INFO] SEOエージェント開始: {now_str}")

    # ── 各チェック実行 ────────────────────────
    print("[INFO] sitemap.xml チェック...")
    sitemap = check_sitemap()

    print("[INFO] robots.txt チェック...")
    robots = check_robots()

    print("[INFO] メタタグチェック...")
    meta = check_meta_tags()

    print("[INFO] topics.json 分析...")
    topics_result = analyze_topics(s3_bucket)

    # ── Claude でメタディスクリプション生成 ──────
    generated_descriptions = []
    if topics_result["top_missing"] and anthropic_key:
        print(f"[INFO] メタディスクリプション生成: {len(topics_result['top_missing'])}件")
        for topic in topics_result["top_missing"]:
            title = topic.get("title") or topic.get("id") or "不明"
            desc = generate_meta_description(topic, anthropic_key)
            generated_descriptions.append({"title": title, "description": desc})
            print(f"  - {title[:40]}: {desc[:60]}...")

    # ── 全体の問題集約 ────────────────────────
    all_issues = (
        [f"[sitemap] {i}" for i in sitemap["issues"]]
        + [f"[robots] {i}" for i in robots["issues"]]
        + [f"[meta] {i}" for i in meta["issues"]]
        + [f"[topics] {i}" for i in topics_result["issues"]]
    )
    has_issues = bool(all_issues)

    # ── Slack メッセージ組み立て ───────────────
    if has_issues:
        header = "🔍 *Flotopic SEO監視レポート — 要対応あり*"
    else:
        header = "🔍 *Flotopic SEO監視レポート — 週次チェック*"

    lines = [
        header,
        f"🕐 {now_str}",
        "",
        "*サイトマップ (sitemap.xml)*",
        f"  ステータス: HTTP {sitemap['status_code']}",
        f"  URL数: {sitemap['url_count']}件",
    ]
    if sitemap["issues"]:
        for iss in sitemap["issues"]:
            lines.append(f"  ⚠️ {iss}")
    else:
        lines.append("  ✅ 正常")

    lines += ["", "*クローラー設定 (robots.txt)*",
              f"  ステータス: HTTP {robots['status_code']}",
              f"  Sitemap参照: {'あり' if robots['has_sitemap_ref'] else 'なし'}"]
    if robots["issues"]:
        for iss in robots["issues"]:
            lines.append(f"  ⚠️ {iss}")
    else:
        lines.append("  ✅ 正常")

    lines += ["", "*トップページ メタ情報*",
              f"  ステータス: HTTP {meta['status_code']}",
              f"  タイトル: {meta['title'] or 'N/A'}",
              f"  ディスクリプション: {(meta['description'] or 'N/A')[:80]}"]
    if meta["issues"]:
        for iss in meta["issues"]:
            lines.append(f"  ⚠️ {iss}")
    else:
        lines.append("  ✅ 正常")

    lines += ["", "*トピック SEO品質*",
              f"  総トピック数: {topics_result['total_topics']}件",
              f"  summary未設定: {topics_result['missing_summary_count']}件"]
    if topics_result["issues"]:
        for iss in topics_result["issues"]:
            lines.append(f"  ⚠️ {iss}")
    else:
        lines.append("  ✅ 正常")

    if generated_descriptions:
        lines += ["", "*Claude生成 メタディスクリプション（上位5件）*"]
        for item in generated_descriptions:
            lines.append(f"  📝 *{item['title'][:40]}*")
            lines.append(f"     {item['description'][:120]}")

    message = "\n".join(lines)
    # 問題がある場合のみ通知（正常時はログ記録のみ）
    if has_issues:
        send_slack(slack_webhook, message)
        print("[INFO] Slack通知送信完了（問題あり）")
    else:
        print("[INFO] 問題なし → Slack通知スキップ（ログのみ記録）")

    # ── ログ保存 ──────────────────────────────
    log_lines = [
        f"\n## {now_str} SEOレポート",
        "",
        f"- sitemap.xml: HTTP {sitemap['status_code']}, {sitemap['url_count']} URLs",
        f"- robots.txt: HTTP {robots['status_code']}, Sitemap参照={'あり' if robots['has_sitemap_ref'] else 'なし'}",
        f"- トップページ: HTTP {meta['status_code']}, タイトル={meta['title'] or 'N/A'}",
        f"- topics: 総数={topics_result['total_topics']}, summary未設定={topics_result['missing_summary_count']}",
        "",
    ]

    if all_issues:
        log_lines.append("### 検出された問題")
        for iss in all_issues:
            log_lines.append(f"- {iss}")
        log_lines.append("")

    if generated_descriptions:
        log_lines.append("### 生成されたメタディスクリプション")
        for item in generated_descriptions:
            log_lines.append(f"**{item['title']}**")
            log_lines.append(f"> {item['description']}")
            log_lines.append("")

    if not all_issues:
        log_lines.append("問題なし — 全チェック正常")

    append_log("\n".join(log_lines))

    print("[INFO] SEOエージェント完了")
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[FATAL] 予期しないエラー: {e}")
        webhook = os.environ.get("SLACK_WEBHOOK", "")
        if webhook:
            send_slack(webhook, f"🚨 *SEOエージェント クラッシュ*\n```{e}```")
        sys.exit(0)
