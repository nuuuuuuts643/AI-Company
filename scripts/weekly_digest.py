#\!/usr/bin/env python3
"""
週次ダイジェストAI (Weekly Digest Agent)
- S3 の api/topics.json からトップ30トピックを読み込む
- スコア上位10件（ジャンル多様性を考慮）を選定
- Claude Haiku APIで各トピックの週次サマリーを生成
- HTMLページ「今週のFlotopic：注目トピックまとめ」を生成してS3に保存
- Slack通知・ダッシュボードログ追記
"""

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ─────────────────────────────────────────────
# 設定
# ─────────────────────────────────────────────
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
JST = timezone(timedelta(hours=9))
REPO_ROOT = Path(__file__).parent.parent
DIGEST_LOG = REPO_ROOT / "dashboard" / "weekly-digest-log.md"

TOP_N_FETCH = 30       # S3から取得する最大件数
TOP_N_SELECT = 10      # 選定する件数
MAX_PER_GENRE = 3      # 1ジャンルあたりの上限


def _env(key: str) -> str:
    val = os.environ.get(key, "")
    if not val:
        print(f"[WARN] 環境変数 {key} が未設定")
    return val


# ─────────────────────────────────────────────
# HTTP ユーティリティ
# ─────────────────────────────────────────────
def http_get(url: str, headers: dict | None = None, timeout: int = 20) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception as e:
        print(f"[ERROR] GET {url}: {e}")
        return 0, b""


def http_post(url: str, payload: dict, headers: dict, timeout: int = 60) -> tuple[int, bytes]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        print(f"[ERROR] POST {url}: {e}")
        return 0, b""


# ─────────────────────────────────────────────
# S3 操作
# ─────────────────────────────────────────────
def s3_get_json(bucket: str, key: str) -> dict | list | None:
    """boto3 でS3からJSONを取得する"""
    try:
        import boto3
        s3 = boto3.client("s3")
        resp = s3.get_object(Bucket=bucket, Key=key)
        return json.loads(resp["Body"].read().decode("utf-8"))
    except Exception as e:
        print(f"[ERROR] S3 GET s3://{bucket}/{key}: {e}")
        return None


def s3_put_html(bucket: str, key: str, html: str) -> bool:
    """boto3 でS3にHTMLをアップロードする"""
    try:
        import boto3
        s3 = boto3.client("s3")
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=html.encode("utf-8"),
            ContentType="text/html; charset=utf-8",
            CacheControl="max-age=3600",
        )
        print(f"[INFO] S3 PUT s3://{bucket}/{key} 完了")
        return True
    except Exception as e:
        print(f"[ERROR] S3 PUT s3://{bucket}/{key}: {e}")
        return False


# ─────────────────────────────────────────────
# トピック選定
# ─────────────────────────────────────────────
def select_top_topics(topics: list) -> list:
    """
    スコア降順でソートし、ジャンル多様性（1ジャンルMAX_PER_GENRE件）を
    考慮しながらTOP_N_SELECT件を選ぶ。
    """
    def get_score(t: dict) -> float:
        return float(t.get("score", t.get("article_count", 0)))

    sorted_topics = sorted(topics, key=get_score, reverse=True)

    selected = []
    genre_counts: dict[str, int] = {}
    for topic in sorted_topics[:TOP_N_FETCH]:
        genre = topic.get("genre") or topic.get("category") or "その他"
        count = genre_counts.get(genre, 0)
        if count < MAX_PER_GENRE:
            selected.append(topic)
            genre_counts[genre] = count + 1
        if len(selected) >= TOP_N_SELECT:
            break

    print(f"[INFO] トピック選定: {len(sorted_topics)}件中 {len(selected)}件選択")
    return selected


# ─────────────────────────────────────────────
# Claude による要約生成
# ─────────────────────────────────────────────
def summarize_topic(topic: dict, api_key: str) -> str:
    """1トピックについて2文の日本語要約を生成する"""
    if not api_key:
        return "（ANTHROPIC_API_KEY 未設定のため要約スキップ）"

    title = topic.get("title") or topic.get("label") or "（タイトル不明）"
    articles = topic.get("articles") or []
    article_titles = [a.get("title", "") for a in articles[:5] if a.get("title")]
    article_text = "\n".join(f"- {t}" for t in article_titles) if article_titles else "（記事情報なし）"
    genre = topic.get("genre") or topic.get("category") or "その他"

    prompt = f"""あなたはニュースキュレーターです。以下のトピックについて、読者向けの簡潔な週次サマリーを日本語で2文で書いてください。

トピック名: {title}
ジャンル: {genre}
関連記事タイトル:
{article_text}

要件:
- 2文で完結させる
- 何がなぜ注目されているかを伝える
- 読者が読みたくなる書き方にする
- 余計な説明（「以下はサマリーです」等）は書かない
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
        print(f"[WARN] Claude API エラー (topic={title}): HTTP {status}")
        return "（要約生成に失敗しました）"

    try:
        resp = json.loads(body)
        return resp["content"][0]["text"].strip()
    except Exception as e:
        print(f"[WARN] Claude レスポンスのパース失敗: {e}")
        return "（要約生成に失敗しました）"


# ─────────────────────────────────────────────
# HTML 生成
# ─────────────────────────────────────────────
GENRE_COLORS: dict[str, str] = {
    "テクノロジー": "#4f8ef7",
    "ビジネス":     "#f7a24f",
    "政治":         "#e05c5c",
    "社会":         "#5cb85c",
    "エンタメ":     "#9b59b6",
    "スポーツ":     "#1abc9c",
    "科学":         "#3498db",
    "国際":         "#e67e22",
    "経済":         "#c0392b",
    "その他":       "#7f8c8d",
}


def genre_color(genre: str) -> str:
    return GENRE_COLORS.get(genre, "#546e8a")


def build_html(selected: list[dict], summaries: list[str], published_jst: datetime) -> str:
    date_str = published_jst.strftime("%Y年%m月%d日")
    iso_date = published_jst.strftime("%Y-%m-%d")

    cards_html = ""
    for rank, (topic, summary) in enumerate(zip(selected, summaries), start=1):
        title = topic.get("title") or topic.get("label") or "（タイトル不明）"
        genre = topic.get("genre") or topic.get("category") or "その他"
        topic_id = topic.get("id") or topic.get("topic_id") or ""
        article_count = topic.get("article_count", len(topic.get("articles", [])))
        color = genre_color(genre)
        link = f"https://flotopic.com/topic.html?id={topic_id}" if topic_id else "https://flotopic.com"

        summary_snippet = summary[:100] + "…" if len(summary) > 100 else summary
        cards_html += f"""
        <div class="card">
          <div class="card-rank">#{rank}</div>
          <div class="card-body">
            <div class="card-header">
              <span class="genre-badge" style="background:{color}">{genre}</span>
              <span class="article-count">📰 {article_count}件</span>
            </div>
            <h2 class="card-title">
              <a href="{link}" target="_blank" rel="noopener">{title}</a>
            </h2>
            <p class="card-summary">{summary_snippet}</p>
            <a class="read-more" href="{link}" target="_blank" rel="noopener">
              詳しく見る →
            </a>
          </div>
        </div>"""

    html = f"""<\!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta property="og:title" content="今週のFlotopic：注目トピックまとめ ({date_str})">
  <meta property="og:description" content="AIが選んだ今週の注目トピックTOP10をお届けします。">
  <meta property="og:type" content="article">
  <title>今週のFlotopic：注目トピックまとめ ({date_str})</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      background: #0d1b2a;
      color: #e0e6ef;
      font-family: 'Hiragino Kaku Gothic ProN', 'Noto Sans JP', 'Meiryo', sans-serif;
      min-height: 100vh;
      line-height: 1.7;
    }}

    .site-header {{
      background: #1e293b;
      border-bottom: 2px solid #334155;
      padding: 2rem 1rem;
      text-align: center;
    }}
    .site-header .logo {{
      font-size: 1.1rem;
      color: #7dd3fc;
      text-decoration: none;
      letter-spacing: 0.05em;
      font-weight: 800;
    }}
    .page-title {{
      font-size: clamp(1.4rem, 5vw, 2.2rem);
      font-weight: 900;
      color: #ffffff;
      margin-top: 0.8rem;
      letter-spacing: -0.01em;
    }}
    .page-subtitle {{
      font-size: 0.95rem;
      color: #7fa8cc;
      margin-top: 0.5rem;
    }}
    .published-date {{
      display: inline-block;
      margin-top: 0.8rem;
      padding: 0.3rem 0.9rem;
      background: #1e3a5f;
      border-radius: 999px;
      font-size: 0.85rem;
      color: #4a9eff;
    }}

    .container {{
      max-width: 780px;
      margin: 0 auto;
      padding: 2rem 1rem 4rem;
    }}

    .card {{
      display: flex;
      gap: 1rem;
      background: #142233;
      border: 1px solid #1e3a5f;
      border-radius: 12px;
      padding: 1.4rem;
      margin-bottom: 1.2rem;
      transition: transform 0.15s ease, border-color 0.15s ease;
    }}
    .card:hover {{
      transform: translateY(-2px);
      border-color: #4a9eff;
    }}
    .card-rank {{
      font-size: 2rem;
      font-weight: 900;
      color: #1e3a5f;
      min-width: 3rem;
      text-align: center;
      line-height: 1;
      padding-top: 0.2rem;
    }}
    .card-body {{ flex: 1; }}
    .card-header {{
      display: flex;
      align-items: center;
      gap: 0.6rem;
      margin-bottom: 0.5rem;
      flex-wrap: wrap;
    }}
    .genre-badge {{
      font-size: 0.72rem;
      font-weight: 700;
      padding: 0.2rem 0.7rem;
      border-radius: 999px;
      color: #fff;
      letter-spacing: 0.04em;
    }}
    .article-count {{
      font-size: 0.8rem;
      color: #7fa8cc;
    }}
    .card-title {{
      font-size: 1.05rem;
      font-weight: 700;
      margin-bottom: 0.6rem;
      line-height: 1.4;
    }}
    .card-title a {{
      color: #e0e6ef;
      text-decoration: none;
    }}
    .card-title a:hover {{
      color: #4a9eff;
      text-decoration: underline;
    }}
    .card-summary {{
      font-size: 0.9rem;
      color: #a8bdd4;
      margin-bottom: 0.8rem;
    }}
    .read-more {{
      font-size: 0.82rem;
      color: #4a9eff;
      text-decoration: none;
      font-weight: 600;
    }}
    .read-more:hover {{ text-decoration: underline; }}

    .site-footer {{
      border-top: 1px solid #1e3a5f;
      text-align: center;
      padding: 2rem 1rem;
      color: #546e8a;
      font-size: 0.85rem;
    }}
    .site-footer a {{
      color: #4a9eff;
      text-decoration: none;
    }}
    .site-footer a:hover {{ text-decoration: underline; }}

    @media (max-width: 480px) {{
      .card {{ flex-direction: column; gap: 0.4rem; }}
      .card-rank {{ font-size: 1.5rem; text-align: left; min-width: auto; }}
    }}
  </style>
</head>
<body>

  <header class="site-header">
    <a class="logo" href="https://flotopic.com">📰 Flotopic</a>
    <h1 class="page-title">今週のFlotopic：注目トピックまとめ</h1>
    <p class="page-subtitle">AIが選んだ今週の注目トピック TOP10</p>
    <span class="published-date">📅 {date_str} 公開</span>
  </header>

  <main class="container">
    {cards_html}
  </main>

  <footer class="site-footer">
    <p>
      <a href="https://flotopic.com">← Flotopic トップページへ戻る</a>
    </p>
    <p style="margin-top:0.5rem">
      &copy; {published_jst.year} Flotopic — AIによる自動生成ダイジェスト
    </p>
    <p style="margin-top:0.8rem; font-size:0.78rem; color:#334155;">
      配信停止はこちら（準備中）
    </p>
  </footer>

</body>
</html>"""
    return html


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
    print("[INFO] Slack通知送信完了")
    return True


# ─────────────────────────────────────────────
# ダッシュボードログ追記
# ─────────────────────────────────────────────
def append_digest_log(selected: list[dict], published_jst: datetime) -> None:
    date_str = published_jst.strftime("%Y-%m-%d")
    topics_md = "\n".join(
        f"  {i+1}. {t.get('title') or t.get('label') or '（不明）'} "
        f"[{t.get('genre') or t.get('category') or 'その他'}]"
        for i, t in enumerate(selected)
    )
    iso_week_key = published_jst.strftime("%Y-%V")
    entry = f"""
## {date_str} 週次ダイジェスト

- 選定トピック数: {len(selected)}件
- 掲載URL: https://flotopic.com/digest/latest.html
- アーカイブ: https://flotopic.com/digest/{iso_week_key}.html

### 選定トピック
{topics_md}

---
"""
    try:
        DIGEST_LOG.parent.mkdir(parents=True, exist_ok=True)
        if not DIGEST_LOG.exists():
            DIGEST_LOG.write_text(
                "# 週次ダイジェストログ\n\n"
                "`weekly_digest.py` が毎週日曜21:00 UTC（月曜06:00 JST）に自動追記する。\n\n---\n",
                encoding="utf-8",
            )
        with DIGEST_LOG.open("a", encoding="utf-8") as f:
            f.write(entry)
        print(f"[INFO] ダイジェストログ追記: {DIGEST_LOG}")
    except Exception as e:
        print(f"[WARN] ログ追記失敗: {e}")


# ─────────────────────────────────────────────
# エントリポイント
# ─────────────────────────────────────────────
def main():
    anthropic_key = _env("ANTHROPIC_API_KEY")
    slack_webhook  = _env("SLACK_WEBHOOK")
    s3_bucket      = _env("S3_BUCKET")

    now_jst = datetime.now(JST)
    iso_date = now_jst.strftime("%Y-%m-%d")
    # ISO週番号キー例: "2026-16"（%V は ISO week number）
    iso_week_key = now_jst.strftime("%Y-%V")
    print(f"[INFO] 週次ダイジェスト開始: {now_jst.strftime('%Y-%m-%d %H:%M JST')} (week {iso_week_key})")

    # ── 1. S3からトピックデータ取得 ──────────
    if not s3_bucket:
        print("[FATAL] S3_BUCKET が未設定のため終了")
        sys.exit(1)

    print(f"[INFO] S3からトピックデータ取得: s3://{s3_bucket}/api/topics.json")
    raw = s3_get_json(s3_bucket, "api/topics.json")
    if raw is None:
        print("[FATAL] topics.json の取得に失敗")
        sys.exit(1)

    # topics.json の構造を吸収: リスト or {"topics": [...]}
    if isinstance(raw, list):
        all_topics = raw
    elif isinstance(raw, dict):
        all_topics = raw.get("topics") or raw.get("articles") or []
    else:
        all_topics = []

    print(f"[INFO] トピック総数: {len(all_topics)}件")
    if not all_topics:
        print("[WARN] トピックが0件 — 終了")
        sys.exit(0)

    # ── 2. 上位10件選定 ──────────────────────
    selected = select_top_topics(all_topics)

    # ── 3. Claude Haiku で要約生成 ────────────
    summaries: list[str] = []
    for i, topic in enumerate(selected):
        title = topic.get("title") or topic.get("label") or f"トピック{i+1}"
        print(f"[INFO] 要約生成 [{i+1}/{len(selected)}]: {title[:40]}")
        summary = summarize_topic(topic, anthropic_key)
        summaries.append(summary)

    # ── 4. HTML 生成 ──────────────────────────
    html = build_html(selected, summaries, now_jst)

    # ── 5. S3へアップロード ───────────────────
    # digest/YYYY-WW.html 形式（ISO週番号）＋ latest エイリアス
    ok_latest  = s3_put_html(s3_bucket, "digest/latest.html", html)
    ok_archive = s3_put_html(s3_bucket, f"digest/{iso_week_key}.html", html)

    if not (ok_latest and ok_archive):
        print("[WARN] S3アップロードの一部が失敗しました")

    # ── 6. Slack通知 ──────────────────────────
    top3_lines = "\n".join(
        f"  #{i+1} {t.get('title') or t.get('label') or '（不明）'}"
        for i, t in enumerate(selected[:3])
    )
    slack_msg = (
        f"📰 *今週のFlotopic 週次ダイジェスト* ({iso_date} / week {iso_week_key})\n\n"
        f"AIが選んだ今週の注目トピック TOP10 を公開しました。\n\n"
        f"*今週のTOP3*\n{top3_lines}\n\n"
        f"🔗 https://flotopic.com/digest/latest.html"
    )
    send_slack(slack_webhook, slack_msg)

    # ── 7. ダッシュボードログ追記 ─────────────
    append_digest_log(selected, now_jst)

    print("[INFO] 週次ダイジェスト完了")
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print(f"[FATAL] 予期しないエラー: {e}")
        traceback.print_exc()
        webhook = os.environ.get("SLACK_WEBHOOK", "")
        if webhook:
            payload = json.dumps({"text": f"🚨 *週次ダイジェストAI クラッシュ*\n```{e}```"}).encode()
            req = urllib.request.Request(
                webhook,
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            try:
                urllib.request.urlopen(req, timeout=10)
            except Exception:
                pass
        sys.exit(1)
