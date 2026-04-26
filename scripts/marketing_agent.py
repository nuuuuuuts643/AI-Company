#!/usr/bin/env python3
"""AI-Company マーケティングAIエージェント - GitHub Actions から実行される

機能:
  1. P003のS3データから上位トピック5件取得
  2. Claudeで SNS投稿文・誘導文・SEO改善提案を生成
  3. dashboard/marketing-log.md に追記
  4. Slackに上位3件トピックを投稿
  5. P003 OGPメタタグの監査レポート
  6. X（Twitter）に上位3件SNS投稿文を自動投稿（OAuth 1.0a）
"""
import base64
import hashlib
import hmac
import json
import os
import re
import sys
import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
REPO_ROOT = Path(__file__).parent.parent
TODAY = date.today().isoformat()

# X (Twitter) API 認証情報（未設定時はスキップ）
X_API_KEY            = os.environ.get("X_API_KEY", "")
X_API_SECRET         = os.environ.get("X_API_SECRET", "")
X_ACCESS_TOKEN       = os.environ.get("X_ACCESS_TOKEN", "")
X_ACCESS_TOKEN_SECRET = os.environ.get("X_ACCESS_TOKEN_SECRET", "")

# P003 データURL（api/topics.json が正）
P003_DATA_URL = (
    "http://p003-news-946554699567.s3-website-ap-northeast-1.amazonaws.com"
    "/api/topics.json"
)

# P003 サイトURL
P003_SITE_URL = "https://flotopic.com"

# OGP監査対象ファイル
OGP_FILES = {
    "index.html": REPO_ROOT / "projects/P003-news-timeline/frontend/index.html",
    "topic.html": REPO_ROOT / "projects/P003-news-timeline/frontend/topic.html",
}

# 必須OGPタグ
REQUIRED_OGP = ["og:title", "og:description", "og:image"]

# マーケティングログ出力先
MARKETING_LOG = REPO_ROOT / "dashboard/marketing-log.md"

# Twitter API v2 ツイート投稿エンドポイント
TWITTER_TWEET_URL = "https://api.twitter.com/2/tweets"

# ツイートの最大文字数
TWEET_MAX_CHARS = 280


# ───────────────────────────────────────────────
# ユーティリティ
# ───────────────────────────────────────────────

def fetch_p003_topics(top_n=5):
    """P003のS3からトピックデータを取得し、article_count順上位N件を返す"""
    req = urllib.request.Request(
        P003_DATA_URL,
        headers={"User-Agent": "AI-Company-Marketing-Agent/1.0"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=20)
        data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"[P003] HTTPError {e.code}: {e.reason}")
        raise
    except Exception as e:
        print(f"[P003] データ取得失敗: {e}")
        raise

    topics = data.get("topics", [])
    print(f"[P003] トピック総数: {len(topics)}")

    # article_count（articleCount）降順でソート
    sorted_topics = sorted(
        topics,
        key=lambda t: int(t.get("articleCount", t.get("article_count", 0))),
        reverse=True,
    )
    top = sorted_topics[:top_n]
    for i, t in enumerate(top, 1):
        title = t.get("generatedTitle") or t.get("title", "（タイトル不明）")
        cnt = t.get("articleCount", t.get("article_count", 0))
        print(f"  [{i}] {title}（記事数: {cnt}）")
    return top


def call_claude(prompt, max_tokens=2048, model="claude-sonnet-4-6"):
    """Claude APIを呼び出してテキストを返す"""
    data = json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=data,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
    )
    try:
        resp = urllib.request.urlopen(req, timeout=120)
        return json.loads(resp.read())["content"][0]["text"]
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"[Claude] API Error {e.code}: {body}")
        raise


def send_slack(message):
    """Slack Webhookにメッセージを送信する"""
    if not SLACK_WEBHOOK_URL:
        print("[Slack] SLACK_WEBHOOK_URL未設定 - スキップ")
        return
    data = json.dumps({"text": message}).encode()
    req = urllib.request.Request(
        SLACK_WEBHOOK_URL,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        print("[Slack] 送信完了")
    except Exception as e:
        print(f"[Slack] 送信失敗: {e}")


# ───────────────────────────────────────────────
# OGP監査
# ───────────────────────────────────────────────

def audit_ogp():
    """index.html / topic.html の OGPタグを監査してレポート文字列を返す"""
    results = {}
    for filename, filepath in OGP_FILES.items():
        try:
            html = filepath.read_text(encoding="utf-8")
        except FileNotFoundError:
            results[filename] = {"error": "ファイルが見つかりません"}
            continue

        found = []
        missing = []
        for tag in REQUIRED_OGP:
            pattern = rf'property=["\']?{re.escape(tag)}["\']?'
            if re.search(pattern, html, re.IGNORECASE):
                found.append(tag)
            else:
                missing.append(tag)
        results[filename] = {"found": found, "missing": missing}

    # レポート文字列生成
    lines = ["#### OGPメタタグ監査結果"]
    all_ok = True
    for filename, result in results.items():
        if "error" in result:
            lines.append(f"- `{filename}`: ⚠️ {result['error']}")
            all_ok = False
            continue
        missing = result["missing"]
        found = result["found"]
        if missing:
            all_ok = False
            lines.append(f"- `{filename}`: 🔴 不足タグ: {', '.join(f'`{t}`' for t in missing)}")
            if found:
                lines.append(f"  - 設定済み: {', '.join(f'`{t}`' for t in found)}")
            else:
                lines.append(f"  - 設定済み: なし")
        else:
            lines.append(f"- `{filename}`: ✅ 全OGPタグ設定済み")

    if not all_ok:
        lines.append("")
        lines.append("> **改善推奨**: OGPタグ未設定のためSNSシェア時にサムネイル・説明文が表示されません。")
        lines.append("> index.html: `og:title`, `og:description`, `og:image` を `<head>` 内に追加してください。")
        lines.append("> topic.html: JavaScript動的生成またはデフォルト値での静的設定を推奨します。")

    return "\n".join(lines), results


# ───────────────────────────────────────────────
# Claude によるコンテンツ生成
# ───────────────────────────────────────────────

def generate_marketing_content(topics):
    """Claudeに各種マーケティングコンテンツを生成させる"""
    topic_list = []
    for i, t in enumerate(topics, 1):
        title = t.get("generatedTitle") or t.get("title", "不明")
        summary = t.get("generatedSummary", "")
        genre = t.get("genre", "")
        cnt = t.get("articleCount", t.get("article_count", 0))
        status = t.get("status", "")
        keywords_hint = ", ".join(t.get("genres", [genre]) or [genre])
        # ステータスに応じたラベルを付与
        status_label = {"rising": "🔺 急上昇", "peak": "🔷 注目", "declining": "📉 落ち着き中"}.get(status, "📰 話題")
        topic_list.append(
            f"{i}. 【{title}】\n"
            f"   ステータス: {status_label}\n"
            f"   ジャンル: {genre}（関連: {keywords_hint}）\n"
            f"   記事数: {cnt}件\n"
            f"   概要: {summary or '（概要なし）'}"
        )

    topics_text = "\n\n".join(topic_list)
    site_url = P003_SITE_URL

    prompt = f"""あなたはAI-Companyのマーケティング担当AIです。今日は{TODAY}です。

Flotopic（フロトピック）サイトの今日のトップトピックを基に、以下を生成してください。
サイトURL: {site_url}

===== 今日のトップトピック =====
{topics_text}
================================

以下の3種類のコンテンツを指定形式で出力してください。

【1. 各トピックのX（Twitter）投稿文】
各トピックについて、エンゲージメントを引き出すX投稿文を日本語140文字以内で生成してください。

ルール:
- URLは含めないこと（後で自動追記する）
- ステータスが「🔺 急上昇」のトピックは投稿文の先頭に「🔺 急上昇」を付ける
- ステータスが「🔷 注目」のトピックは投稿文の先頭に「🔷 注目」を付ける
- ハッシュタグはジャンルに合ったもの最大3個を末尾に付ける（例: #政治 #国際情勢 #速報）
- 投稿フォーマットを以下の3種類からバランスよく使い分ける（トピック5件で均等に分散）:
  A. 問いかけ型: 読者に意見を求める（「〇〇についてどう思いますか？」「皆さんは〇〇を経験したことありますか？」）
  B. 驚き・事実型: 意外な事実や数字で興味を引く（「実は〇〇だった」「〇〇件もの報道が...」）
  C. 速報・緊急型: 今起きていることを伝える臨場感（「今、〇〇が急展開」「見逃せない〇〇の最新動向」）
- 絵文字は1〜2個使い、文体は親しみやすく、拡散・返信されやすい内容にする
- 必ず140文字以内に収める（ハッシュタグ含む）

<SNS_POSTS>
[トピック1のタイトル]
[140文字以内の投稿文（ステータスラベル+本文+ハッシュタグ）]

[トピック2のタイトル]
[140文字以内の投稿文（ステータスラベル+本文+ハッシュタグ）]

[トピック3のタイトル]
[140文字以内の投稿文（ステータスラベル+本文+ハッシュタグ）]

[トピック4のタイトル]
[140文字以内の投稿文（ステータスラベル+本文+ハッシュタグ）]

[トピック5のタイトル]
[140文字以内の投稿文（ステータスラベル+本文+ハッシュタグ）]
</SNS_POSTS>

【2. サイトへの誘導文】
Flotopic（フロトピック）サイトへ読者を誘導する文章を2〜3文で書いてください。
今日の注目トピックに触れながら、タイムライン形式の特長（話題の盛り上がりが一目でわかる）をアピールして。

<SITE_CTA>
[誘導文をここに]
</SITE_CTA>

【3. 週次SEO改善提案】
上記トピックのキーワード分析から、Flotopicサイトのみせ方・SEO改善提案を3〜5項目挙げてください。
具体的なキーワード・メタデータ・コンテンツ戦略の観点で提案してください。

<SEO_PROPOSALS>
[SEO改善提案をここに]
</SEO_PROPOSALS>
"""

    print("[Claude] マーケティングコンテンツ生成中...")
    response = call_claude(prompt, max_tokens=2048)
    print("[Claude] 生成完了")
    return response


def parse_tagged_block(text, tag):
    """<TAG>...</TAG> ブロックを抽出する"""
    pattern = rf"<{tag}>(.*?)</{tag}>"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else ""


# ───────────────────────────────────────────────
# X (Twitter) OAuth 1.0a 投稿機能
# ───────────────────────────────────────────────

def _percent_encode(s):
    """RFC 3986 パーセントエンコード（OAuth署名用）"""
    return urllib.parse.quote(str(s), safe="")


def _build_oauth_header(method, url, consumer_key, consumer_secret, token, token_secret):
    """
    OAuth 1.0a の Authorization ヘッダーを標準ライブラリのみで生成する。

    Twitter API v2 は JSON ボディを使うため、ボディパラメータは
    OAuth 署名の対象に含めない（query/form パラメータのみ対象）。
    """
    oauth_params = {
        "oauth_consumer_key":     consumer_key,
        "oauth_nonce":            uuid.uuid4().hex,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp":        str(int(time.time())),
        "oauth_token":            token,
        "oauth_version":          "1.0",
    }

    # 署名対象パラメータ（OAuth パラメータのみ。JSON ボディは含めない）
    sorted_params = sorted(oauth_params.items())
    param_string = "&".join(
        f"{_percent_encode(k)}={_percent_encode(v)}" for k, v in sorted_params
    )

    # 署名ベース文字列: METHOD & encoded_url & encoded_params
    signature_base = "&".join([
        method.upper(),
        _percent_encode(url),
        _percent_encode(param_string),
    ])

    # 署名キー: consumer_secret & token_secret
    signing_key = f"{_percent_encode(consumer_secret)}&{_percent_encode(token_secret)}"

    # HMAC-SHA1 署名
    digest = hmac.new(
        signing_key.encode("utf-8"),
        signature_base.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    signature = base64.b64encode(digest).decode("utf-8")

    oauth_params["oauth_signature"] = signature

    # Authorization ヘッダー文字列（キー名アルファベット順）
    auth_parts = ", ".join(
        f'{_percent_encode(k)}="{_percent_encode(v)}"'
        for k, v in sorted(oauth_params.items())
    )
    return f"OAuth {auth_parts}"


def post_tweet(text):
    """
    Twitter API v2 POST /2/tweets でツイートを1件投稿する。
    成功したらツイートIDを返す。失敗時は例外を送出。
    """
    body = json.dumps({"text": text}).encode("utf-8")
    auth_header = _build_oauth_header(
        method="POST",
        url=TWITTER_TWEET_URL,
        consumer_key=X_API_KEY,
        consumer_secret=X_API_SECRET,
        token=X_ACCESS_TOKEN,
        token_secret=X_ACCESS_TOKEN_SECRET,
    )
    req = urllib.request.Request(
        TWITTER_TWEET_URL,
        data=body,
        headers={
            "Authorization": auth_header,
            "Content-Type":  "application/json",
            "User-Agent":    "AI-Company-Marketing-Agent/1.0",
        },
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read())
        tweet_id = result.get("data", {}).get("id", "unknown")
        print(f"[X] 投稿成功: id={tweet_id} / text={text[:40]}...")
        return tweet_id
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"[X] HTTPError {e.code}: {err_body}")
        raise


def parse_sns_posts(sns_posts_block, top_n=3):
    """
    SNS_POSTS ブロックから投稿本文を最大 top_n 件抽出する。

    想定フォーマット（空行区切り、1ブロック = タイトル行 + 投稿文行）:
        [トピック1のタイトル]
        [投稿文]

        [トピック2のタイトル]
        [投稿文]
        ...

    タイトル行は [〜] 形式と判定するか、単純に2行目を本文とみなす。
    空行が少ない場合は奇数行=タイトル・偶数行=本文として補完する。
    """
    posts = []
    # 空行で段落分割
    groups = re.split(r"\n\s*\n", sns_posts_block.strip())
    for group in groups:
        lines = [ln.strip() for ln in group.splitlines() if ln.strip()]
        if not lines:
            continue
        if len(lines) >= 2:
            # 2行目が投稿本文
            posts.append(lines[1])
        else:
            # 1行だけのグループ: そのまま投稿本文として扱う
            # （タイトル行だけのケースを除外するため、[ で始まる場合はスキップ）
            if not lines[0].startswith("[") and not lines[0].endswith("]"):
                posts.append(lines[0])
        if len(posts) >= top_n:
            break

    return posts[:top_n]


def post_to_x(sns_posts_block):
    """
    SNS_POSTS ブロックから上位 3 件を X（Twitter）に投稿する。

    - 環境変数 X_API_KEY / X_API_SECRET / X_ACCESS_TOKEN / X_ACCESS_TOKEN_SECRET
      のいずれかが未設定の場合はスキップ（エラーにしない）。
    - 各投稿間は 3 秒のインターバルを置く。
    - 投稿テキストの末尾にサイト URL を付与し、280 文字を超える場合は本文を短縮する。

    戻り値: 実際に投稿成功した件数 (int)
    """
    if not all([X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET]):
        print("[X] 認証情報の環境変数が未設定のためX投稿をスキップします")
        return 0

    if not sns_posts_block:
        print("[X] SNS投稿文が空のためX投稿をスキップします")
        return 0

    posts = parse_sns_posts(sns_posts_block, top_n=3)
    if not posts:
        print("[X] SNS投稿文のパースに失敗したためX投稿をスキップします")
        return 0

    print(f"[X] 投稿予定件数: {len(posts)}")
    posted_count = 0

    for i, post_text in enumerate(posts, 1):
        # URL を末尾に付与
        suffix = f"\n{P003_SITE_URL}"
        # 本文 + URL が 280 文字を超える場合、本文を短縮して「…」を付ける
        max_body_len = TWEET_MAX_CHARS - len(suffix)
        if len(post_text) > max_body_len:
            post_text = post_text[: max_body_len - 1] + "…"
        tweet_text = post_text + suffix

        print(f"[X] 投稿 {i}/{len(posts)} ({len(tweet_text)}文字): {tweet_text[:60]}...")
        try:
            post_tweet(tweet_text)
            posted_count += 1
        except Exception as e:
            print(f"[X] 投稿 {i} 失敗（スキップして続行）: {e}")

        # 最後の投稿後はスリープ不要
        if i < len(posts):
            time.sleep(3)

    print(f"[X] 投稿完了: {posted_count}/{len(posts)} 件成功")
    return posted_count


# ───────────────────────────────────────────────
# ログ追記
# ───────────────────────────────────────────────

def append_marketing_log(topics, sns_posts, site_cta, seo_proposals, ogp_report):
    """dashboard/marketing-log.md に本日のマーケティング活動を追記する"""
    MARKETING_LOG.parent.mkdir(parents=True, exist_ok=True)

    # 既存ファイルの読み込み（初回は空）
    try:
        existing = MARKETING_LOG.read_text(encoding="utf-8")
    except FileNotFoundError:
        existing = "# マーケティングログ\n\nAI-Company P003 マーケティングAIの日次レポートです。\n\n"

    # 上位5トピック一覧
    topic_lines = []
    for i, t in enumerate(topics, 1):
        title = t.get("generatedTitle") or t.get("title", "不明")
        cnt = t.get("articleCount", t.get("article_count", 0))
        genre = t.get("genre", "")
        topic_lines.append(f"{i}. **{title}**（{genre} / 記事数: {cnt}）")

    now_jst = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M JST")

    new_entry = f"""
---

## {TODAY} の日次マーケティングレポート

> 生成時刻: {now_jst}

### 今日の上位トピック（article_count順）

{chr(10).join(topic_lines)}

### SNS投稿文（各140文字以内）

{sns_posts}

### サイト誘導文

{site_cta}

### 週次SEO改善提案

{seo_proposals}

### OGPメタタグ監査

{ogp_report}

"""

    updated = existing + new_entry
    MARKETING_LOG.write_text(updated, encoding="utf-8")
    print(f"[Log] {MARKETING_LOG} に追記完了")


# ───────────────────────────────────────────────
# Slack通知
# ───────────────────────────────────────────────

def build_slack_message(topics, site_cta, x_posted_count=0):
    """Slackに送るメッセージを構築する（上位3件）"""
    lines = [f"📣 *今日のP003注目トピック* ({TODAY})\n"]

    for i, t in enumerate(topics[:3], 1):
        title = t.get("generatedTitle") or t.get("title", "不明")
        cnt = t.get("articleCount", t.get("article_count", 0))
        genre = t.get("genre", "")
        summary = t.get("generatedSummary", "")
        status = t.get("status", "")
        status_emoji = {"rising": "📈", "peak": "🔥", "declining": "📉"}.get(status, "📰")
        lines.append(f"{status_emoji} *{i}. {title}*（{genre} / {cnt}件）")
        if summary:
            # 要約は80文字以内に短縮
            short_summary = summary[:80] + "…" if len(summary) > 80 else summary
            lines.append(f"   _{short_summary}_")
        lines.append("")

    lines.append(f"🔗 {P003_SITE_URL}")
    lines.append("")
    lines.append(f"_{site_cta[:100]}{'…' if len(site_cta) > 100 else ''}_")

    # X投稿結果を追記
    if x_posted_count > 0:
        lines.append("")
        lines.append(f"🐦 X投稿済み ✅（{x_posted_count}件投稿）")

    return "\n".join(lines)


# ───────────────────────────────────────────────
# メイン
# ───────────────────────────────────────────────

def main():
    print(f"=== マーケティングAI実行開始: {TODAY} ===")

    # Step 1: P003データ取得
    print("\n[Step 1] P003トピックデータ取得中...")
    try:
        topics = fetch_p003_topics(top_n=5)
    except Exception as e:
        error_msg = f"【マーケティングAI ERROR】{TODAY}\nP003データ取得失敗: {e}"
        send_slack(error_msg)
        sys.exit(1)

    if not topics:
        print("トピックが0件のためスキップ")
        send_slack(f"【マーケティングAI】{TODAY}\nP003トピックが0件のため本日はスキップします。")
        sys.exit(0)

    # Step 2: Claudeでコンテンツ生成
    print("\n[Step 2] Claudeでマーケティングコンテンツ生成中...")
    try:
        marketing_response = generate_marketing_content(topics)
    except Exception as e:
        error_msg = f"【マーケティングAI ERROR】{TODAY}\nClaude API失敗: {e}"
        send_slack(error_msg)
        sys.exit(1)

    sns_posts = parse_tagged_block(marketing_response, "SNS_POSTS")
    site_cta = parse_tagged_block(marketing_response, "SITE_CTA")
    seo_proposals = parse_tagged_block(marketing_response, "SEO_PROPOSALS")

    if not sns_posts:
        print("[警告] SNS_POSTSブロックの抽出に失敗。レスポンス冒頭:")
        print(marketing_response[:300])

    # Step 3: OGP監査
    print("\n[Step 3] OGPメタタグ監査中...")
    ogp_report, ogp_results = audit_ogp()
    print(ogp_report)

    # Step 4: ログ追記
    print("\n[Step 4] marketing-log.md に追記中...")
    append_marketing_log(topics, sns_posts, site_cta, seo_proposals, ogp_report)

    # Step 5: X（Twitter）自動投稿
    print("\n[Step 5] X（Twitter）自動投稿中...")
    x_posted_count = post_to_x(sns_posts)

    # Step 6: Slack通知は異常時のみ（正常完了通知は無効化）
    # 正常完了時はmarketing-log.mdへの記録とX投稿で完了とする
    print("\n[Step 6] Slack通知スキップ（正常完了 → ログ記録のみ）")
    # エラーや0件時は上のステップで既にsend_slackを呼んでいるため通知済み

    print("\n=== マーケティングAI実行完了 ===")


if __name__ == "__main__":
    main()
