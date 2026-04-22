#\!/usr/bin/env python3
"""
Flotopic 週次セキュリティ分析エージェント

実行内容:
  1. flotopic-rate-limits テーブルからブロックされた IP を集計
  2. flotopic-analytics から異常パターン（1時間に100件超）を検出
  3. flotopic-users から高活動の新規アカウントを抽出
  4. Claude Haiku でセキュリティポスチャを要約
  5. Slack に投稿

環境変数:
  SLACK_WEBHOOK   … Slack Incoming Webhook URL
  REGION          … AWS リージョン（デフォルト: ap-northeast-1）
  ANTHROPIC_API_KEY … Claude API キー
"""

import json
import os
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Attr

REGION          = os.environ.get('REGION', 'ap-northeast-1')
SLACK_WEBHOOK   = os.environ.get('SLACK_WEBHOOK', '')
ANTHROPIC_KEY   = os.environ.get('ANTHROPIC_API_KEY', '')

RATE_TABLE      = 'flotopic-rate-limits'
ANALYTICS_TABLE = 'flotopic-analytics'
USERS_TABLE     = 'flotopic-users'

dynamodb = boto3.resource('dynamodb', region_name=REGION)


# ── DynamoDB スキャンヘルパー ─────────────────────────────────────

def full_scan(table_name: str, filter_expr=None) -> list:
    table = dynamodb.Table(table_name)
    kwargs = {}
    if filter_expr is not None:
        kwargs['FilterExpression'] = filter_expr
    items = []
    last_key = None
    while True:
        if last_key:
            kwargs['ExclusiveStartKey'] = last_key
        result = table.scan(**kwargs)
        items.extend(result.get('Items', []))
        last_key = result.get('LastEvaluatedKey')
        if not last_key:
            break
    return items


# ── 1. ブロックされた IP の集計 ───────────────────────────────────

def analyze_rate_limits() -> dict:
    """
    flotopic-rate-limits から count が多いエントリを抽出。
    pk 形式: identifier#action#window
    """
    print('Analyzing rate limits...')
    items = full_scan(RATE_TABLE)

    # identifier ごとに合計カウントを集計
    identifier_counts = defaultdict(int)
    action_counts     = defaultdict(int)
    for item in items:
        pk = item.get('pk', '')
        parts = pk.split('#')
        if len(parts) >= 3:
            identifier = parts[0]
            action     = parts[1]
            count      = int(item.get('count', 0))
            identifier_counts[identifier] += count
            action_counts[action]         += count

    # 上位10件
    top_identifiers = sorted(
        identifier_counts.items(), key=lambda x: x[1], reverse=True
    )[:10]

    return {
        'total_entries':    len(items),
        'top_identifiers':  [{'id': k, 'count': v} for k, v in top_identifiers],
        'action_breakdown': dict(action_counts),
    }


# ── 2. 異常パターン検出 ───────────────────────────────────────────

def analyze_anomalies() -> dict:
    """
    flotopic-analytics から直近1時間で100件超の活動をしたユーザーを検出。
    """
    print('Analyzing anomalies...')
    since = int(time.time()) - 3600  # 1時間前

    items = full_scan(ANALYTICS_TABLE, filter_expr=Attr('timestamp').gte(since))

    # ユーザーごとのイベント数
    user_counts = defaultdict(int)
    for item in items:
        user_id = item.get('userId', 'unknown')
        user_counts[user_id] += 1

    anomalies = [
        {'userId': uid, 'eventCount': cnt}
        for uid, cnt in user_counts.items()
        if cnt > 100
    ]
    anomalies.sort(key=lambda x: x['eventCount'], reverse=True)

    return {
        'period_hours':    1,
        'total_events':    len(items),
        'unique_users':    len(user_counts),
        'anomalous_users': anomalies,
    }


# ── 3. 高活動の新規アカウント ──────────────────────────────────────

def analyze_new_users() -> dict:
    """
    flotopic-users から過去7日以内に作成され、banned=False のユーザーを抽出。
    アナリティクスと突合して活動量を確認する。
    """
    print('Analyzing new users...')
    seven_days_ago_iso = datetime.fromtimestamp(
        time.time() - 7 * 86400, tz=timezone.utc
    ).isoformat()

    users = full_scan(
        USERS_TABLE,
        filter_expr=Attr('createdAt').gte(seven_days_ago_iso),
    )

    # アナリティクスからユーザーごとのイベント数を取得（直近7日）
    since = int(time.time()) - 7 * 86400
    analytics_items = full_scan(
        ANALYTICS_TABLE,
        filter_expr=Attr('timestamp').gte(since),
    )
    user_event_counts = defaultdict(int)
    for item in analytics_items:
        user_event_counts[item.get('userId', '')] += 1

    # 新規ユーザーと活動量を結合
    new_user_activity = []
    for user in users:
        uid = user.get('userId', '')
        new_user_activity.append({
            'userId':    uid,
            'createdAt': user.get('createdAt', ''),
            'banned':    user.get('banned', False),
            'eventCount': user_event_counts.get(uid, 0),
        })

    # 活動量でソート
    new_user_activity.sort(key=lambda x: x['eventCount'], reverse=True)

    # 高活動新規ユーザー（50件超）
    high_activity = [u for u in new_user_activity if u['eventCount'] > 50]

    return {
        'new_users_7d':      len(users),
        'high_activity':     high_activity[:10],
        'top_new_users':     new_user_activity[:5],
    }


# ── 4. Claude Haiku でサマリー生成 ───────────────────────────────

def generate_summary(rate_data: dict, anomaly_data: dict, user_data: dict) -> str:
    if not ANTHROPIC_KEY:
        return '（ANTHROPIC_API_KEY 未設定のため AI サマリースキップ）'

    prompt_data = {
        'rate_limits': rate_data,
        'anomalies':   anomaly_data,
        'new_users':   user_data,
        'generated_at': datetime.now(timezone.utc).isoformat(),
    }

    prompt = f"""以下は Flotopic のセキュリティデータです。日本語で簡潔にセキュリティポスチャを評価してください。
特に以下の点を報告してください:
1. 高頻度アクセス源（不審な IP や UserID）
2. 異常なユーザー行動
3. 新規アカウントの不審な活動
4. 推奨アクション（もしあれば）

データ:
{json.dumps(prompt_data, ensure_ascii=False, indent=2)}

200字以内で要点を箇条書きにしてください。"""

    payload = {
        'model': 'claude-haiku-4-5',
        'max_tokens': 512,
        'messages': [{'role': 'user', 'content': prompt}],
    }
    req = urllib.request.Request(
        'https://api.anthropic.com/v1/messages',
        data=json.dumps(payload).encode(),
        headers={
            'x-api-key':         ANTHROPIC_KEY,
            'anthropic-version': '2023-06-01',
            'content-type':      'application/json',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            data = json.loads(res.read())
        return data['content'][0]['text']
    except Exception as e:
        return f'AI サマリー生成エラー: {e}'


# ── 5. Slack 投稿 ──────────────────────────────────────────────────

def post_to_slack(message: str):
    if not SLACK_WEBHOOK:
        print('SLACK_WEBHOOK 未設定。Slack 投稿をスキップ。')
        print(message)
        return

    payload = {'text': message}
    req = urllib.request.Request(
        SLACK_WEBHOOK,
        data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            print(f'Slack 投稿完了: {res.status}')
    except Exception as e:
        print(f'Slack 投稿エラー: {e}')


# ── メイン ────────────────────────────────────────────────────────

def main():
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    print(f'=== Flotopic セキュリティレポート {now_str} ===')

    rate_data    = analyze_rate_limits()
    anomaly_data = analyze_anomalies()
    user_data    = analyze_new_users()

    # AI サマリー
    ai_summary = generate_summary(rate_data, anomaly_data, user_data)

    # Slack メッセージ組み立て
    anomaly_count = len(anomaly_data.get('anomalous_users', []))
    high_activity = len(user_data.get('high_activity', []))

    message = f"""*Flotopic 週次セキュリティレポート* ({now_str})

*レートリミット状況*
• 記録エントリ数: {rate_data['total_entries']}
• アクション別: {json.dumps(rate_data['action_breakdown'], ensure_ascii=False)}
• 最多アクセス元 TOP3: {', '.join([f"{x['id']}({x['count']})" for x in rate_data['top_identifiers'][:3]])}

*異常パターン (直近1h)*
• 総イベント数: {anomaly_data['total_events']}
• ユニークユーザー: {anomaly_data['unique_users']}
• 異常ユーザー (>100件/h): {anomaly_count} 件

*新規アカウント (直近7日)*
• 新規ユーザー数: {user_data['new_users_7d']}
• 高活動新規ユーザー (>50件/7d): {high_activity} 件

*AI セキュリティ評価*
{ai_summary}
"""

    post_to_slack(message)

    # ローカルにも保存
    report_path = os.path.join(
        os.path.dirname(__file__),
        '../dashboard/security-report.json',
    )
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump({
            'generatedAt': now_str,
            'rateLimits':  rate_data,
            'anomalies':   anomaly_data,
            'newUsers':    user_data,
            'aiSummary':   ai_summary,
        }, f, ensure_ascii=False, indent=2)
    print(f'レポート保存: {report_path}')


if __name__ == '__main__':
    main()
