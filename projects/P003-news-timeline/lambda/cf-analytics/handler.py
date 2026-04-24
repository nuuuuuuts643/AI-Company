"""
cf-analytics Lambda
- Cloudflare Web Analytics GraphQL から過去7日のPVデータを取得
- DynamoDB 各テーブルからサイト統計（ユーザー・コメント・お気に入り）を取得
- S3 api/cf-analytics.json にキャッシュ（admin.html が読む）

EventBridge で毎日 7:00 JST (22:00 UTC) に自動実行

必要な環境変数:
  CF_API_TOKEN   Cloudflare API トークン (Analytics:Read 権限)
  CF_ACCOUNT_ID  Cloudflare アカウント ID
  CF_SITE_TAG    Cloudflare Web Analytics サイトタグ（デフォルト値あり）
  S3_BUCKET / USERS_TABLE / COMMENTS_TABLE / FAVORITES_TABLE / REGION
"""

import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone

import boto3

# ── 設定 ──────────────────────────────────────────────────────────────────
CF_API_TOKEN     = os.environ.get('CF_API_TOKEN', '')
CF_ACCOUNT_ID    = os.environ.get('CF_ACCOUNT_ID', '')
CF_SITE_TAG      = os.environ.get('CF_SITE_TAG', '35149d754c3a4903b9461c157568d392')
S3_BUCKET        = os.environ.get('S3_BUCKET',        'p003-news-946554699567')
USERS_TABLE      = os.environ.get('USERS_TABLE',      'flotopic-users')
COMMENTS_TABLE   = os.environ.get('COMMENTS_TABLE',   'ai-company-comments')
FAVORITES_TABLE  = os.environ.get('FAVORITES_TABLE',  'flotopic-favorites')
REGION           = os.environ.get('REGION',           'ap-northeast-1')
CF_GRAPHQL       = 'https://api.cloudflare.com/client/v4/graphql'
CACHE_KEY        = 'api/cf-analytics.json'

dynamodb = boto3.resource('dynamodb', region_name=REGION)
s3       = boto3.client('s3', region_name=REGION)


# ── Cloudflare Analytics ───────────────────────────────────────────────────

CF_QUERY = """
query Analytics($accountId: String!, $siteTag: String!, $start: Date!, $end: Date!) {
  viewer {
    accounts(filter: {accountTag: $accountId}) {
      daily: rumPageloadEventsAdaptiveGroups(
        filter: {AND: [{siteTag: $siteTag}, {date_geq: $start}, {date_leq: $end}]}
        limit: 30 orderBy: [date_ASC]
      ) { count dimensions { date } }

      topPages: rumPageloadEventsAdaptiveGroups(
        filter: {AND: [{siteTag: $siteTag}, {date_geq: $start}, {date_leq: $end}]}
        limit: 10 orderBy: [count_DESC]
      ) { count dimensions { requestPath } }

      byCountry: rumPageloadEventsAdaptiveGroups(
        filter: {AND: [{siteTag: $siteTag}, {date_geq: $start}, {date_leq: $end}]}
        limit: 10 orderBy: [count_DESC]
      ) { count dimensions { country } }

      byDevice: rumPageloadEventsAdaptiveGroups(
        filter: {AND: [{siteTag: $siteTag}, {date_geq: $start}, {date_leq: $end}]}
        limit: 5 orderBy: [count_DESC]
      ) { count dimensions { deviceType } }
    }
  }
}
"""


def fetch_cf_analytics(days: int = 7) -> dict:
    if not CF_API_TOKEN or not CF_ACCOUNT_ID:
        print('[cf-analytics] CF_API_TOKEN/CF_ACCOUNT_ID 未設定 → CF データなし')
        return {}

    today = datetime.now(timezone.utc).date()
    start = (today - timedelta(days=days)).isoformat()
    end   = today.isoformat()

    req = urllib.request.Request(
        CF_GRAPHQL,
        data=json.dumps({'query': CF_QUERY, 'variables': {
            'accountId': CF_ACCOUNT_ID, 'siteTag': CF_SITE_TAG,
            'start': start, 'end': end,
        }}).encode(),
        headers={'Authorization': f'Bearer {CF_API_TOKEN}', 'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            result = json.loads(r.read())
    except Exception as e:
        print(f'[cf-analytics] CF API エラー: {e}')
        return {}

    if 'errors' in result:
        print(f'[cf-analytics] GraphQL エラー: {result["errors"]}')
        return {}

    data = (result.get('data', {}).get('viewer', {}).get('accounts') or [{}])[0]
    daily = data.get('daily', [])

    return {
        'totalPv7d': sum(d.get('count', 0) for d in daily),
        'daily':    [{'date': d['dimensions']['date'], 'count': d['count']} for d in daily],
        'topPages': [{'path': p['dimensions']['requestPath'], 'count': p['count']}
                     for p in data.get('topPages', [])],
        'byCountry':[{'code': c['dimensions'].get('country','—'), 'count': c['count']}
                     for c in data.get('byCountry', [])],
        'byDevice': [{'type': dv['dimensions'].get('deviceType','—'), 'count': dv['count']}
                     for dv in data.get('byDevice', [])],
        'period':   {'start': start, 'end': end},
    }


# ── DynamoDB スキャン共通 ──────────────────────────────────────────────────

def scan_table(table_name: str, projection: str = None) -> list:
    table  = dynamodb.Table(table_name)
    items  = []
    kwargs = {}
    if projection:
        kwargs['ProjectionExpression'] = projection
    try:
        while True:
            resp = table.scan(**kwargs)
            items.extend(resp.get('Items', []))
            if not resp.get('LastEvaluatedKey'):
                break
            kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']
    except Exception as e:
        print(f'[cf-analytics] {table_name} スキャンエラー: {e}')
    return items


# ── ユーザー統計 ───────────────────────────────────────────────────────────

def fetch_user_stats() -> dict:
    items    = scan_table(USERS_TABLE, 'userId, createdAt')
    total    = len(items)
    cutoff7  = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    cutoff30 = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    new_7d   = sum(1 for i in items if (i.get('createdAt') or '') >= cutoff7)
    new_30d  = sum(1 for i in items if (i.get('createdAt') or '') >= cutoff30)
    print(f'[cf-analytics] users: total={total} new7d={new_7d}')
    return {'total': total, 'new7d': new_7d, 'new30d': new_30d}


# ── コメント統計 ───────────────────────────────────────────────────────────

def fetch_comment_stats() -> dict:
    # ai-company-comments: PK=topicId, SK=commentId
    items   = scan_table(COMMENTS_TABLE, 'topicId, createdAt, likedBy')
    total   = len(items)
    cutoff7 = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    new_7d  = sum(1 for i in items if (i.get('createdAt') or '') >= cutoff7)
    total_likes = sum(len(i.get('likedBy') or []) for i in items)

    # コメント数が多いトピック TOP5
    topic_cnt: dict = {}
    for i in items:
        tid = i.get('topicId', '')
        topic_cnt[tid] = topic_cnt.get(tid, 0) + 1
    top5 = sorted(topic_cnt.items(), key=lambda x: x[1], reverse=True)[:5]

    print(f'[cf-analytics] comments: total={total} new7d={new_7d} likes={total_likes}')
    return {
        'total':       total,
        'new7d':       new_7d,
        'totalLikes':  total_likes,
        'topTopics':   [{'topicId': tid, 'count': cnt} for tid, cnt in top5],
    }


# ── お気に入り統計 ─────────────────────────────────────────────────────────

def fetch_favorites_stats() -> dict:
    # flotopic-favorites: PK=userId, SK=topicId
    items    = scan_table(FAVORITES_TABLE, 'userId, topicId, createdAt')
    total    = len(items)
    cutoff7  = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    new_7d   = sum(1 for i in items if (i.get('createdAt') or '') >= cutoff7)

    # お気に入りが多いトピック TOP5
    topic_cnt: dict = {}
    for i in items:
        tid = i.get('topicId', '')
        topic_cnt[tid] = topic_cnt.get(tid, 0) + 1
    top5 = sorted(topic_cnt.items(), key=lambda x: x[1], reverse=True)[:5]

    print(f'[cf-analytics] favorites: total={total} new7d={new_7d}')
    return {
        'total':     total,
        'new7d':     new_7d,
        'topTopics': [{'topicId': tid, 'count': cnt} for tid, cnt in top5],
    }


# ── S3 書き込み ───────────────────────────────────────────────────────────

def save_to_s3(payload: dict):
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=CACHE_KEY,
        Body=json.dumps(payload, ensure_ascii=False, default=str),
        ContentType='application/json',
        CacheControl='max-age=3600',
    )
    print(f'[cf-analytics] → s3://{S3_BUCKET}/{CACHE_KEY}')


# ── エントリポイント ──────────────────────────────────────────────────────

def lambda_handler(event, context):
    print(f'[cf-analytics] 開始: {datetime.now(timezone.utc).isoformat()}')

    cf_data   = fetch_cf_analytics(days=7)
    users     = fetch_user_stats()
    comments  = fetch_comment_stats()
    favorites = fetch_favorites_stats()

    payload = {
        'cf':          cf_data,
        'users':       users,
        'comments':    comments,
        'favorites':   favorites,
        'generatedAt': datetime.now(timezone.utc).isoformat(),
    }

    save_to_s3(payload)

    print(f'[cf-analytics] 完了: PV7d={cf_data.get("totalPv7d","N/A")} '
          f'users={users["total"]} comments={comments["total"]} favs={favorites["total"]}')
    return {'statusCode': 200, 'body': json.dumps({'ok': True})}
