#!/usr/bin/env python3
"""AI-Company 編集AIエージェント - GitHub Actions から実行される

機能:
1. AI要約品質チェック  — P003 data.json を取得し品質を評価
2. コメントモデレーション — DynamoDB ai-company-comments のスパム判定
3. 週次レポート生成    — dashboard/editorial-log.md に追記
4. Slack報告           — 週次サマリーを通知
"""
import json
import os
import re
import sys
import urllib.request
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "ap-northeast-1")

REPO_ROOT = Path(__file__).parent.parent
EDITORIAL_LOG = REPO_ROOT / "dashboard" / "editorial-log.md"
TODAY = date.today().isoformat()

P003_DATA_URL = (
    "http://p003-news-946554699567.s3-website-ap-northeast-1.amazonaws.com/data.json"
)
COMMENTS_TABLE = "ai-company-comments"
ANALYTICS_TABLE = "flotopic-analytics"


# ---------------------------------------------------------------------------
# ユーティリティ
# ---------------------------------------------------------------------------

def call_claude(prompt: str, max_tokens: int = 2000) -> str:
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
    with urllib.request.urlopen(req, timeout=90) as resp:
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


def fetch_json(url: str) -> dict | list | None:
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "AI-Company-EditorialAgent/1.0"}
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"[fetch] {url} 取得失敗: {e}")
        return None


# ---------------------------------------------------------------------------
# 1. AI要約品質チェック
# ---------------------------------------------------------------------------

def check_summary_quality() -> dict:
    """
    P003 data.json から全トピックを取得し、Claude に品質評価させる。

    返り値:
        {
            "topics_total": int,
            "problem_topics": [{"id": str, "title": str, "score": int, "issues": [str]}, ...],
            "top5_low_quality": [...],   # スコア昇順上位5件
        }
    """
    print("[quality] P003 data.json を取得中...")
    data = fetch_json(P003_DATA_URL)
    if data is None:
        print("[quality] data.json 取得失敗 — スキップ")
        return {"topics_total": 0, "problem_topics": [], "top5_low_quality": []}

    # data.json の構造に応じてトピックリストを取り出す
    topics: list = []
    if isinstance(data, list):
        topics = data
    elif isinstance(data, dict):
        # {"topics": [...]} / {"data": [...]} など
        for key in ("topics", "data", "items", "articles"):
            if key in data and isinstance(data[key], list):
                topics = data[key]
                break
        if not topics:
            # フラットな dict の場合はリストに変換
            topics = list(data.values()) if data else []

    if not topics:
        print("[quality] トピックが0件 — スキップ")
        return {"topics_total": 0, "problem_topics": [], "top5_low_quality": []}

    print(f"[quality] {len(topics)} 件のトピックを評価します")

    # Claude に評価させるため、トピック情報を整形
    topic_summaries = []
    for i, t in enumerate(topics[:50]):  # 上限50件でコスト抑制
        if not isinstance(t, dict):
            continue
        title = t.get("title") or t.get("topic_title") or t.get("headline") or ""
        summary = (
            t.get("summary") or t.get("description") or t.get("body") or ""
        )
        topic_id = t.get("id") or t.get("topic_id") or str(i)
        topic_summaries.append(
            f"[ID={topic_id}]\nタイトル: {title}\n要約: {summary}"
        )

    if not topic_summaries:
        print("[quality] 評価可能なトピックなし — スキップ")
        return {"topics_total": len(topics), "problem_topics": [], "top5_low_quality": []}

    batch_text = "\n\n---\n\n".join(topic_summaries)

    prompt = f"""あなたはニュースメディアの編集品質チェックAIです。
以下のトピック一覧を評価し、問題のあるトピックを特定してください。

【評価基準】
1. 要約の文字数: 100〜200文字が理想。短すぎ（<80文字）または長すぎ（>250文字）は減点
2. センセーショナル・誇張表現: 「衝撃」「驚愕」「絶対」「必見」などの煽り文言は減点
3. タイトル形式: 「○○事件」「△△の動向」「××をめぐる議論」など概念的まとめ形式が望ましい。
   記事見出しをそのままコピーしたようなタイトル（具体的な固有名詞や数字が多い）は減点

各トピックに対して以下のJSON形式で評価してください（配列で全件出力）:
```json
[
  {{
    "id": "トピックID",
    "title": "タイトル（先頭20文字）",
    "score": 0〜100の品質スコア,
    "issues": ["問題点1", "問題点2"]  // 問題なければ空配列
  }}
]
```

トピック一覧:
{batch_text}

JSONのみを返してください（前後に説明文不要）。"""

    print("[quality] Claude に品質評価をリクエスト中...")
    try:
        raw = call_claude(prompt, max_tokens=3000)
        # JSON部分を抽出
        json_match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not json_match:
            raise ValueError("JSON配列が見つかりません")
        evaluated: list = json.loads(json_match.group())
    except Exception as e:
        print(f"[quality] Claude 評価パース失敗: {e}")
        return {"topics_total": len(topics), "problem_topics": [], "top5_low_quality": []}

    # 問題ありトピック (score < 70 または issues > 0)
    problem_topics = [
        t for t in evaluated if t.get("score", 100) < 70 or t.get("issues")
    ]
    # 品質スコア昇順で上位5件
    sorted_topics = sorted(evaluated, key=lambda x: x.get("score", 100))
    top5 = sorted_topics[:5]

    print(f"[quality] 評価完了: 問題あり {len(problem_topics)} 件 / 全 {len(evaluated)} 件")
    return {
        "topics_total": len(topics),
        "evaluated_count": len(evaluated),
        "problem_topics": problem_topics,
        "top5_low_quality": top5,
    }


# ---------------------------------------------------------------------------
# 2. アナリティクス：先週のトップトピック取得
# ---------------------------------------------------------------------------

def get_analytics_top_topics() -> list:
    """
    DynamoDB 'flotopic-analytics' テーブルから過去7日間のビュー数上位トピックを取得する。

    返り値:
        [{"topic_id": str, "title": str, "view_count": int}, ...]  最大10件
        DynamoDB アクセス失敗時は空リストを返す
    """
    print("[analytics] DynamoDB flotopic-analytics からビューデータ取得中...")
    try:
        import boto3
        from boto3.dynamodb.conditions import Attr
        from datetime import timedelta

        dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
        table = dynamodb.Table(ANALYTICS_TABLE)

        # 過去7日間のタイムスタンプ（秒）
        cutoff_ts = int(
            (datetime.now(timezone.utc) - timedelta(days=7)).timestamp()
        )

        # イベントタイプが "view" のレコードをスキャン
        resp = table.scan(
            FilterExpression=(
                Attr("event_type").eq("view") & Attr("timestamp").gte(cutoff_ts)
            ),
            ProjectionExpression="topic_id, title, view_count",
        )
        items = resp.get("Items", [])
        while "LastEvaluatedKey" in resp:
            resp = table.scan(
                FilterExpression=(
                    Attr("event_type").eq("view") & Attr("timestamp").gte(cutoff_ts)
                ),
                ProjectionExpression="topic_id, title, view_count",
                ExclusiveStartKey=resp["LastEvaluatedKey"],
            )
            items.extend(resp.get("Items", []))

        # topic_id ごとにビュー数を集計
        aggregated: dict[str, dict] = {}
        for item in items:
            tid = str(item.get("topic_id") or "")
            if not tid:
                continue
            if tid not in aggregated:
                aggregated[tid] = {
                    "topic_id": tid,
                    "title": str(item.get("title") or tid),
                    "view_count": 0,
                }
            # view_count フィールドがある場合はそれを加算、なければ1件=1PV
            vc = item.get("view_count", 1)
            aggregated[tid]["view_count"] += int(vc)

        # ビュー数降順で上位10件
        top10 = sorted(aggregated.values(), key=lambda x: x["view_count"], reverse=True)[:10]
        print(f"[analytics] トップトピック取得完了: {len(top10)} 件")
        return top10

    except Exception as e:
        print(f"[analytics] DynamoDB アクセス失敗（スキップ）: {e}")
        return []


# ---------------------------------------------------------------------------
# 3. コメントモデレーション
# ---------------------------------------------------------------------------

def moderate_comments() -> dict:
    """
    DynamoDB ai-company-comments からコメントを取得し、
    スパム・不適切投稿を flagged=True にする。

    DynamoDB が存在しない場合は try/except でスキップ。

    返り値:
        {"checked": int, "flagged": int, "skipped": bool}
    """
    print("[moderation] DynamoDB コメント取得中...")
    try:
        import boto3
        from boto3.dynamodb.conditions import Attr

        dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
        table = dynamodb.Table(COMMENTS_TABLE)

        # TTL未切れ（ttl が現在時刻より大きい、またはttlなし）& 未フラグのコメント
        now_ts = int(datetime.now(timezone.utc).timestamp())
        resp = table.scan(
            FilterExpression=(
                Attr("flagged").ne(True)
                & (Attr("ttl").not_exists() | Attr("ttl").gt(now_ts))
            )
        )
        items = resp.get("Items", [])
        # ページネーション対応
        while "LastEvaluatedKey" in resp:
            resp = table.scan(
                FilterExpression=(
                    Attr("flagged").ne(True)
                    & (Attr("ttl").not_exists() | Attr("ttl").gt(now_ts))
                ),
                ExclusiveStartKey=resp["LastEvaluatedKey"],
            )
            items.extend(resp.get("Items", []))

        print(f"[moderation] {len(items)} 件のコメントをチェック")
        if not items:
            return {"checked": 0, "flagged": 0, "skipped": False}

        # Claude にスパム判定させる（最大100件）
        batch = items[:100]
        comment_texts = []
        for c in batch:
            cid = c.get("comment_id") or c.get("id") or c.get("sk") or "?"
            body = c.get("body") or c.get("text") or c.get("content") or ""
            comment_texts.append(f'[ID={cid}] {body[:200]}')

        batch_text = "\n".join(comment_texts)

        prompt = f"""以下はウェブサイトに投稿されたコメント一覧です。
スパムまたは不適切なコメントを特定してください。

【フラグを立てる基準】
- スパム文言（SEO誘導、商品宣伝、「クリックして」など）
- URLの羅列（3個以上のURLが含まれる）
- 意味のない文字列（ランダム文字、同じ文字の繰り返し）
- 誹謗中傷・差別的表現

フラグを立てるべきコメントのIDリストをJSON配列で返してください:
```json
["ID1", "ID2"]
```
問題なければ空配列 `[]` を返してください。JSONのみ返してください。

コメント一覧:
{batch_text}"""

        print("[moderation] Claude にスパム判定をリクエスト中...")
        raw = call_claude(prompt, max_tokens=500)
        json_match = re.search(r"\[.*?\]", raw, re.DOTALL)
        flagged_ids: list[str] = []
        if json_match:
            try:
                flagged_ids = json.loads(json_match.group())
            except Exception:
                flagged_ids = []

        print(f"[moderation] フラグ対象: {len(flagged_ids)} 件")

        # DynamoDB を更新 (flagged=True を追記)
        updated = 0
        for c in batch:
            cid = str(c.get("comment_id") or c.get("id") or c.get("sk") or "")
            if cid in flagged_ids:
                pk_key = next(
                    (k for k in c if k in ("pk", "comment_id", "id")), None
                )
                sk_key = next(
                    (k for k in c if k in ("sk", "sort_key", "timestamp")), None
                )
                if not pk_key:
                    continue
                key = {pk_key: c[pk_key]}
                if sk_key and sk_key != pk_key:
                    key[sk_key] = c[sk_key]
                try:
                    table.update_item(
                        Key=key,
                        UpdateExpression="SET flagged = :f",
                        ExpressionAttributeValues={":f": True},
                    )
                    updated += 1
                except Exception as e:
                    print(f"[moderation] 更新失敗 (id={cid}): {e}")

        print(f"[moderation] {updated} 件を flagged=True に更新")
        return {"checked": len(batch), "flagged": updated, "skipped": False}

    except Exception as e:
        print(f"[moderation] DynamoDB アクセス失敗（スキップ）: {e}")
        return {"checked": 0, "flagged": 0, "skipped": True}


# ---------------------------------------------------------------------------
# 4. 週次レポート生成
# ---------------------------------------------------------------------------

def generate_report(quality_result: dict, moderation_result: dict, analytics_top_topics: list) -> str:
    """品質チェック結果・モデレーション結果から週次レポートを生成し、
    dashboard/editorial-log.md に追記する。返り値は追記したMarkdown文字列。"""

    top5 = quality_result.get("top5_low_quality", [])
    problem_count = len(quality_result.get("problem_topics", []))
    topics_total = quality_result.get("topics_total", 0)
    evaluated_count = quality_result.get("evaluated_count", 0)
    flagged_count = moderation_result.get("flagged", 0)
    comment_checked = moderation_result.get("checked", 0)
    moderation_skipped = moderation_result.get("skipped", False)

    # アナリティクス：トップトピックのテキスト整形
    analytics_text = ""
    if analytics_top_topics:
        analytics_text = "\n".join(
            f"{i+1}. {t['title']} （{t['view_count']:,} PV）"
            for i, t in enumerate(analytics_top_topics)
        )

    # 改善提案を Claude に生成させる（アナリティクスを文脈として含む）
    if top5:
        top5_text = "\n".join(
            f"- [{t.get('score', '?')}点] {t.get('title', '?')}: {', '.join(t.get('issues', []))}"
            for t in top5
        )
        analytics_context = (
            f"\n\n先週最も閲覧されたトピック:\n{analytics_text}"
            if analytics_text
            else ""
        )
        improvement_prompt = f"""以下は品質スコアが低かったニューストピックです。
編集チーム向けに、具体的な改善提案を3点簡潔に箇条書きで提案してください（日本語）。
```
{top5_text}
```{analytics_context}"""
        try:
            improvement_suggestions = call_claude(improvement_prompt, max_tokens=400)
        except Exception as e:
            improvement_suggestions = f"（提案生成失敗: {e}）"
    else:
        improvement_suggestions = "- 品質問題は検出されませんでした。現状維持でOKです。"

    # Markdown レポート作成
    report_lines = [
        f"## {TODAY} 週次編集レポート",
        "",
        "### AI要約品質チェック",
        f"- 総トピック数: {topics_total} 件（評価対象: {evaluated_count} 件）",
        f"- 品質問題あり: {problem_count} 件",
        "",
        "**品質スコア下位5件:**",
    ]
    if top5:
        for t in top5:
            issues_str = "、".join(t.get("issues", [])) or "なし"
            report_lines.append(
                f"- [{t.get('score', '?')}点] {t.get('title', '不明')} — {issues_str}"
            )
    else:
        report_lines.append("- 問題トピックなし")

    report_lines += [
        "",
        "### コメントモデレーション",
    ]
    if moderation_skipped:
        report_lines.append("- DynamoDB アクセス不可のためスキップ")
    else:
        report_lines.append(f"- チェック件数: {comment_checked} 件")
        report_lines.append(f"- フラグ付き（スパム等）: {flagged_count} 件")

    # アナリティクスセクション
    report_lines += ["", "### 先週のトップトピック（PV順）"]
    if analytics_top_topics:
        for i, t in enumerate(analytics_top_topics):
            report_lines.append(
                f"{i+1}. **{t['title']}** — {t['view_count']:,} PV"
            )
    else:
        report_lines.append("- アナリティクスデータなし（DynamoDB未設定またはアクセス不可）")

    report_lines += [
        "",
        "### 改善提案",
        improvement_suggestions,
        "",
        "---",
        "",
    ]

    report_text = "\n".join(report_lines)

    # dashboard/editorial-log.md に追記
    EDITORIAL_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(EDITORIAL_LOG, "a", encoding="utf-8") as f:
        f.write(report_text)

    print(f"[report] {EDITORIAL_LOG} に追記完了")
    return report_text


# ---------------------------------------------------------------------------
# 5. Slack 報告
# ---------------------------------------------------------------------------

def build_slack_message(
    quality_result: dict,
    moderation_result: dict,
    report_text: str,
    analytics_top_topics: list,
) -> str:
    problem_count = len(quality_result.get("problem_topics", []))
    topics_total = quality_result.get("topics_total", 0)
    flagged_count = moderation_result.get("flagged", 0)
    moderation_skipped = moderation_result.get("skipped", False)

    has_issues = problem_count > 0 or flagged_count > 0
    icon = "🚨" if has_issues else "✅"

    lines = [
        f"{icon} *AI-Company 編集AIエージェント 週次レポート* ({TODAY})",
        "",
        f"📰 *AI要約品質チェック*: {topics_total} トピック中 {problem_count} 件に問題あり",
    ]

    if not moderation_skipped:
        lines.append(
            f"💬 *コメントモデレーション*: {moderation_result.get('checked', 0)} 件中 {flagged_count} 件をフラグ"
        )
    else:
        lines.append("💬 *コメントモデレーション*: DynamoDB アクセス不可のためスキップ")

    if analytics_top_topics:
        lines.append("")
        lines.append("📊 *先週のトップトピック（PV順）*:")
        for t in analytics_top_topics[:5]:
            lines.append(f"  • {t['title']} — {t['view_count']:,} PV")

    if quality_result.get("top5_low_quality"):
        lines.append("")
        lines.append("📉 *品質スコア下位トップ5*:")
        for t in quality_result["top5_low_quality"][:5]:
            lines.append(
                f"  • [{t.get('score', '?')}点] {t.get('title', '不明')}"
            )

    lines += [
        "",
        "詳細は `dashboard/editorial-log.md` を参照してください。",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# メイン
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"=== AI-Company 編集AIエージェント 開始 ({TODAY}) ===")

    # 1. AI要約品質チェック
    print("\n[STEP 1] AI要約品質チェック")
    quality_result = check_summary_quality()

    # 2. アナリティクス：先週のトップトピック取得
    print("\n[STEP 2] アナリティクス取得（flotopic-analytics）")
    analytics_top_topics = get_analytics_top_topics()

    # 3. コメントモデレーション
    print("\n[STEP 3] コメントモデレーション")
    moderation_result = moderate_comments()

    # 4. 週次レポート生成
    print("\n[STEP 4] 週次レポート生成")
    report_text = generate_report(quality_result, moderation_result, analytics_top_topics)

    # 5. Slack 報告（問題がある場合のみ通知）
    print("\n[STEP 5] Slack 報告")
    slack_message = build_slack_message(
        quality_result, moderation_result, report_text, analytics_top_topics
    )
    print(slack_message)
    problem_count = len(quality_result.get("problem_topics", []))
    flagged_count = moderation_result.get("flagged", 0)
    has_issues = problem_count > 0 or flagged_count > 0
    if has_issues:
        slack_notify(slack_message)
    else:
        print("[Slack] 品質問題・スパムなし → Slack通知スキップ")

    print("\n=== 編集AIエージェント 完了 ===")


if __name__ == "__main__":
    main()
