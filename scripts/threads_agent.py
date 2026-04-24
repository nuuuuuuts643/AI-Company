#!/usr/bin/env python3
"""
threads_agent.py — Flotopic Threads 自動投稿エージェント

投稿パターン3種:
  daily  : 今日の急上昇トップ3（スレッド形式）
  weekly : 今週の5大ストーリー（1投稿）
  monthly: 今月の総括（1投稿）

必要な環境変数（GitHub Secrets）:
  THREADS_USER_ID    : ThreadsのユーザーID（数値）
  THREADS_ACCESS_TOKEN: 長期アクセストークン
  SLACK_WEBHOOK      : エラー通知用（任意）
  AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_DEFAULT_REGION

Threads API 仕様:
  - 文字数上限: 500文字
  - テキスト内URLで自動リンクプレビュー生成
  - スレッド: reply_to_id で連鎖
  - レート制限: 250投稿/日
"""

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

try:
    import boto3
except ImportError:
    print('[threads_agent] boto3 が未インストールです。')
    sys.exit(1)

# ── 設定 ────────────────────────────────────────────────────────────────────
THREADS_USER_ID     = os.environ.get('THREADS_USER_ID', '')
THREADS_ACCESS_TOKEN = os.environ.get('THREADS_ACCESS_TOKEN', '')
SLACK_WEBHOOK       = os.environ.get('SLACK_WEBHOOK', '')
REGION              = os.environ.get('AWS_DEFAULT_REGION', 'ap-northeast-1')

TOPICS_TABLE        = 'p003-topics'
THREADS_POSTS_TABLE = 'ai-company-threads-posts'
SITE_URL            = 'https://flotopic.com'
THREADS_API         = 'https://graph.threads.net/v1.0'
MAX_CHARS           = 500

dynamodb = boto3.resource('dynamodb', region_name=REGION)


# ── DynamoDB ─────────────────────────────────────────────────────────────────

def get_topics(limit=50, sort_by='velocity'):
    table  = dynamodb.Table(TOPICS_TABLE)
    items  = []
    kwargs = {'FilterExpression': 'SK = :m', 'ExpressionAttributeValues': {':m': 'META'}}
    while True:
        resp = table.scan(**kwargs)
        items.extend(resp.get('Items', []))
        if not resp.get('LastEvaluatedKey'):
            break
        kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']
    key = 'velocityScore' if sort_by == 'velocity' else 'score'
    items.sort(key=lambda x: int(x.get(key, 0) or 0), reverse=True)
    return items[:limit]


def get_posted_ids():
    try:
        table  = dynamodb.Table(THREADS_POSTS_TABLE)
        items  = []
        kwargs = {}
        while True:
            resp = table.scan(**kwargs)
            items.extend(resp.get('Items', []))
            if not resp.get('LastEvaluatedKey'):
                break
            kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']
        return {item['topicId'] for item in items}
    except Exception as e:
        print(f'[threads_agent] 投稿済みID取得エラー: {e}')
        return set()


def mark_posted(topic_id: str, mode: str):
    try:
        dynamodb.Table(THREADS_POSTS_TABLE).put_item(Item={
            'topicId':  topic_id,
            'mode':     mode,
            'postedAt': datetime.now(timezone.utc).isoformat(),
            'ttl':      int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp()),
        })
    except Exception as e:
        print(f'[threads_agent] 投稿記録エラー: {e}')


# ── Threads API ───────────────────────────────────────────────────────────────

def api_post(endpoint: str, params: dict) -> dict:
    params['access_token'] = THREADS_ACCESS_TOKEN
    url  = f'{THREADS_API}/{endpoint}'
    data = urllib.parse.urlencode(params).encode()
    req  = urllib.request.Request(url, data=data, method='POST')
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def create_container(text: str, reply_to_id: str = None) -> str:
    """テキストコンテナ作成 → container ID を返す"""
    params = {
        'media_type': 'TEXT',
        'text':       text[:MAX_CHARS],
    }
    if reply_to_id:
        params['reply_to_id'] = reply_to_id
    result = api_post(f'{THREADS_USER_ID}/threads', params)
    return result['id']


def publish_container(container_id: str) -> str:
    """コンテナを公開 → post ID を返す"""
    time.sleep(3)  # Threads APIの処理待ち
    result = api_post(f'{THREADS_USER_ID}/threads/publish', {'creation_id': container_id})
    return result['id']


def send_post(text: str, reply_to_id: str = None, dry_run: bool = False) -> str:
    """投稿して post_id を返す（dry_run時はNone）"""
    if dry_run:
        label = f'reply_to={reply_to_id}' if reply_to_id else 'root'
        print(f'[DRY-RUN] ({len(text)}文字 / {label}):\n{text}\n')
        return None
    container_id = create_container(text, reply_to_id)
    post_id      = publish_container(container_id)
    print(f'[threads_agent] 投稿完了: {post_id}')
    return post_id


# ── ユーティリティ ────────────────────────────────────────────────────────────

def truncate(text: str, n: int) -> str:
    if not text:
        return ''
    return text[:n] + '…' if len(text) > n else text


GENRE_TAGS = {
    '政治': '#政治', 'ビジネス': '#ビジネス', 'テクノロジー': '#テクノロジー',
    'スポーツ': '#スポーツ', 'エンタメ': '#エンタメ', '科学': '#科学',
    '健康': '#健康', '国際': '#国際', '株・金融': '#株価',
}


def genre_tag(topic) -> str:
    return GENRE_TAGS.get(topic.get('genre', ''), '#ニュース')


def notify_slack_error(msg: str):
    if not SLACK_WEBHOOK:
        return
    try:
        body = json.dumps({'text': f'🚨 *Threads Agent エラー*\n{msg}'}).encode()
        req  = urllib.request.Request(SLACK_WEBHOOK, data=body,
                                      headers={'Content-Type': 'application/json'}, method='POST')
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


# ── 日次投稿 ─────────────────────────────────────────────────────────────────

def post_daily(dry_run=False):
    print('[threads_agent] 日次投稿 開始')
    topics     = get_topics(50, 'velocity')
    posted_ids = get_posted_ids()
    top3 = [
        t for t in topics
        if t.get('lifecycleStatus', 'active') == 'active'
        and t.get('topicId') not in posted_ids
    ][:3]

    if not top3:
        print('[threads_agent] 投稿対象なし')
        return

    jst_now  = datetime.now(timezone.utc) + timedelta(hours=9)
    date_str = jst_now.strftime('%Y年%m月%d日')

    # 1投稿目（見出し）
    preview  = ' / '.join(truncate(t.get('generatedTitle') or t.get('title', ''), 20) for t in top3)
    header   = f'📈 {date_str} 急上昇トップ3\n\n{preview}\n\n{SITE_URL}\n\n#Flotopic #ニュースまとめ'
    root_id  = send_post(header, dry_run=dry_run)

    # 2〜4投稿目（各トピック）
    for i, topic in enumerate(top3, 1):
        title   = topic.get('generatedTitle') or topic.get('title', '')
        summary = topic.get('generatedSummary') or topic.get('extractiveSummary', '')
        tid     = topic.get('topicId', '')
        cnt     = int(topic.get('articleCount', 0) or 0)
        url     = f'{SITE_URL}/topic.html?id={tid}'
        tag     = genre_tag(topic)

        body = (
            f'【{i}/3】{truncate(title, 40)}\n\n'
            f'{truncate(summary, 120)}\n\n'
            f'📄 {cnt}件の記事\n{url}\n\n'
            f'{tag} #Flotopic'
        )
        post_id = send_post(body, reply_to_id=root_id, dry_run=dry_run)
        if post_id:
            mark_posted(tid, 'daily')

    print('[threads_agent] 日次投稿 完了')


# ── 週次投稿 ─────────────────────────────────────────────────────────────────

def post_weekly(dry_run=False):
    print('[threads_agent] 週次投稿 開始')
    topics = get_topics(100, 'score')
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    recent = []
    for t in topics:
        try:
            dt = datetime.fromisoformat((t.get('updatedAt') or t.get('createdAt', '')).replace('Z', '+00:00'))
            if dt >= cutoff:
                recent.append(t)
        except Exception:
            pass

    top5 = recent[:5]
    if not top5:
        print('[threads_agent] 週次投稿対象なし')
        return

    jst_now  = datetime.now(timezone.utc) + timedelta(hours=9)
    week_str = jst_now.strftime('%Y年%m月第%W週')
    lines    = [f'{i}. {truncate(t.get("generatedTitle") or t.get("title",""), 25)}（{int(t.get("articleCount",0) or 0)}件）'
                for i, t in enumerate(top5, 1)]

    text = f'📰 {week_str} 5大ストーリー\n\n' + '\n'.join(lines) + f'\n\n{SITE_URL}\n\n#Flotopic #今週のニュース'
    post_id = send_post(text, dry_run=dry_run)
    if post_id:
        for t in top5:
            mark_posted(t.get('topicId', ''), 'weekly')
    print('[threads_agent] 週次投稿 完了')


# ── 月次投稿 ─────────────────────────────────────────────────────────────────

def post_monthly(dry_run=False):
    print('[threads_agent] 月次投稿 開始')
    topics = get_topics(200, 'score')
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    recent = []
    for t in topics:
        try:
            dt = datetime.fromisoformat((t.get('updatedAt') or t.get('createdAt', '')).replace('Z', '+00:00'))
            if dt >= cutoff:
                recent.append(t)
        except Exception:
            pass

    top3 = recent[:3]
    if not top3:
        print('[threads_agent] 月次投稿対象なし')
        return

    jst_now   = datetime.now(timezone.utc) + timedelta(hours=9)
    month_str = jst_now.strftime('%Y年%m月')
    lines     = [f'{i}. {truncate(t.get("generatedTitle") or t.get("title",""), 25)}（{int(t.get("articleCount",0) or 0)}件）'
                 for i, t in enumerate(top3, 1)]

    genre_counter: dict[str, int] = {}
    for t in recent:
        g = t.get('genre', '総合')
        genre_counter[g] = genre_counter.get(g, 0) + 1
    top_genre = max(genre_counter, key=lambda k: genre_counter[k]) if genre_counter else '総合'

    text = (
        f'📅 {month_str} ニュース総括\n\n'
        f'【注目トピック TOP3】\n' + '\n'.join(lines)
        + f'\n\n今月は「{top_genre}」の話題が活発でした。\n{SITE_URL}\n\n#Flotopic'
    )
    post_id = send_post(text, dry_run=dry_run)
    if post_id:
        for t in top3:
            mark_posted(t.get('topicId', ''), 'monthly')
    print('[threads_agent] 月次投稿 完了')


# ── メイン ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', required=True, choices=['daily', 'weekly', 'monthly'])
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    print(f'[threads_agent] mode={args.mode} dry_run={args.dry_run} 開始: {datetime.now(timezone.utc).isoformat()}')

    if not args.dry_run and (not THREADS_USER_ID or not THREADS_ACCESS_TOKEN):
        print('[threads_agent] THREADS_USER_ID または THREADS_ACCESS_TOKEN が未設定')
        sys.exit(1)

    try:
        if args.mode == 'daily':
            post_daily(args.dry_run)
        elif args.mode == 'weekly':
            post_weekly(args.dry_run)
        elif args.mode == 'monthly':
            post_monthly(args.dry_run)
    except Exception as e:
        import traceback
        err = traceback.format_exc()
        print(f'[threads_agent] エラー:\n{err}')
        notify_slack_error(f'mode={args.mode}\n```{err[:500]}```')
        sys.exit(1)

    print(f'[threads_agent] 完了: {datetime.now(timezone.utc).isoformat()}')


if __name__ == '__main__':
    main()
