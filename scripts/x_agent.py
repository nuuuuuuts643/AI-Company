#!/usr/bin/env python3
"""
x_agent.py — Flotopic X（Twitter）自動投稿エージェント
─────────────────────────────────────────────────────────────────────────────
投稿パターン3種:
  - 日次  (JST 8:00 = UTC 23:00): 今日の急上昇トップ3をスレッドで投稿
  - 週次  (月曜 JST 9:00 = UTC 0:00): 今週の5大ストーリーをまとめて投稿
  - 月次  (1日 JST 9:00 = UTC 0:00): 今月の総括

実行方法:
  python3 x_agent.py --mode daily    # 日次投稿
  python3 x_agent.py --mode weekly   # 週次投稿
  python3 x_agent.py --mode monthly  # 月次投稿

必要な環境変数:
  X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET
  SLACK_WEBHOOK (エラー通知用)
  AWS_DEFAULT_REGION (DynamoDB接続用、デフォルト: ap-northeast-1)

ガバナンス:
  実行前に _governance_check.py で自己停止チェックを実施。
  停止フラグが立っている場合は即座に終了する。
─────────────────────────────────────────────────────────────────────────────
"""

import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

# ── 依存チェック ─────────────────────────────────────────────────────────────
try:
    import tweepy
except ImportError:
    print('[x_agent] tweepy が未インストールです。pip install tweepy を実行してください。')
    sys.exit(1)

try:
    import boto3
    from boto3.dynamodb.conditions import Key
except ImportError:
    print('[x_agent] boto3 が未インストールです。pip install boto3 を実行してください。')
    sys.exit(1)

# ── ガバナンスチェック ───────────────────────────────────────────────────────
_script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _script_dir)
try:
    from _governance_check import check_agent_status
    check_agent_status("x_agent")
except ImportError:
    print('[x_agent] _governance_check.py が見つかりません。ガバナンスチェックをスキップして続行。')

# ── 設定 ────────────────────────────────────────────────────────────────────
X_API_KEY            = os.environ.get('X_API_KEY', '')
X_API_SECRET         = os.environ.get('X_API_SECRET', '')
X_ACCESS_TOKEN       = os.environ.get('X_ACCESS_TOKEN', '')
X_ACCESS_TOKEN_SECRET = os.environ.get('X_ACCESS_TOKEN_SECRET', '')
SLACK_WEBHOOK        = os.environ.get('SLACK_WEBHOOK', '')
REGION               = os.environ.get('AWS_DEFAULT_REGION', 'ap-northeast-1')

# DynamoDB テーブル
MEMORY_TABLE   = 'ai-company-memory'
TOPICS_TABLE   = 'p003-topics'
X_POSTS_TABLE  = 'ai-company-x-posts'   # 投稿済みトピックIDを記録（重複投稿防止）

SITE_URL = 'https://flotopic.com'

# ── DynamoDB ─────────────────────────────────────────────────────────────────
dynamodb = boto3.resource('dynamodb', region_name=REGION)


def get_topics_from_dynamodb(limit=50, sort_by='velocity'):
    """
    DynamoDB p003-topics から最新のMETAアイテムを取得。
    sort_by='velocity' → velocityScore 降順
    sort_by='score'    → score 降順（週次・月次用）
    """
    table  = dynamodb.Table(TOPICS_TABLE)
    items  = []
    kwargs = {
        'FilterExpression':          'SK = :m',
        'ExpressionAttributeValues': {':m': 'META'},
    }
    while True:
        resp = table.scan(**kwargs)
        items.extend(resp.get('Items', []))
        if not resp.get('LastEvaluatedKey'):
            break
        kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']

    # ソート
    if sort_by == 'velocity':
        items.sort(key=lambda x: int(x.get('velocityScore', 0) or 0), reverse=True)
    else:
        items.sort(key=lambda x: int(x.get('score', 0) or 0), reverse=True)

    return items[:limit]


def get_posted_ids():
    """投稿済みトピックIDのセットを取得（重複防止）"""
    try:
        table  = dynamodb.Table(X_POSTS_TABLE)
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
        print(f'[x_agent] 投稿済みID取得エラー（テーブル未作成の可能性）: {e}')
        return set()


def mark_as_posted(topic_id: str, mode: str):
    """投稿済みとしてDynamoDBに記録"""
    try:
        table = dynamodb.Table(X_POSTS_TABLE)
        table.put_item(Item={
            'topicId':   topic_id,
            'mode':      mode,
            'postedAt':  datetime.now(timezone.utc).isoformat(),
            'ttl':       int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp()),
        })
    except Exception as e:
        print(f'[x_agent] 投稿記録エラー: {e}')


# ── Slack エラー通知 ─────────────────────────────────────────────────────────

def notify_slack_error(msg: str):
    """エラー時のみSlackに通知"""
    if not SLACK_WEBHOOK:
        return
    try:
        body = json.dumps({'text': f'🚨 *X Agent エラー*\n{msg}'}).encode('utf-8')
        req  = urllib.request.Request(
            SLACK_WEBHOOK, data=body,
            headers={'Content-Type': 'application/json'}, method='POST',
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
    except Exception as e:
        print(f'[x_agent] Slack通知失敗: {e}')


# ── Twitter クライアント ──────────────────────────────────────────────────────

def get_twitter_client():
    """tweepy クライアントを初期化（Twitter API v2）"""
    if not all([X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET]):
        raise ValueError(
            '環境変数 X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET が未設定です。'
        )
    client = tweepy.Client(
        consumer_key=X_API_KEY,
        consumer_secret=X_API_SECRET,
        access_token=X_ACCESS_TOKEN,
        access_token_secret=X_ACCESS_TOKEN_SECRET,
        wait_on_rate_limit=True,
    )
    return client


def post_tweet(client, text: str, reply_to_id: str = None) -> str:
    """
    ツイートを投稿し、ツイートIDを返す。
    reply_to_id が指定された場合はそのツイートへのリプライ（スレッド）として投稿。
    """
    kwargs = {'text': text}
    if reply_to_id:
        kwargs['in_reply_to_tweet_id'] = reply_to_id
    resp = client.create_tweet(**kwargs)
    return str(resp.data['id'])


def truncate(text: str, max_len: int = 100) -> str:
    """日本語ツイートのテキストを最大文字数に収める"""
    return text[:max_len] + '…' if len(text) > max_len else text


# ── ハッシュタグ生成 ─────────────────────────────────────────────────────────

GENRE_HASHTAGS = {
    '総合':       '#ニュース',
    '政治':       '#政治',
    'ビジネス':   '#ビジネス',
    'テクノロジー': '#テクノロジー #Tech',
    'スポーツ':   '#スポーツ',
    'エンタメ':   '#エンタメ',
    '科学':       '#科学',
    '健康':       '#健康',
    '国際':       '#国際',
    '株・金融':   '#株価 #金融',
}


def genre_tag(topic) -> str:
    genre = topic.get('genre', '総合')
    return GENRE_HASHTAGS.get(genre, '#ニュース')


# ── 日次投稿: 今日の急上昇トップ3 ───────────────────────────────────────────

def post_daily(client, dry_run=False):
    """
    velocityScore 降順で上位3件をスレッド形式で投稿。
    1ツイート目: 「今日の急上昇トップ3 🔥」見出し
    2〜4ツイート目: 各トピックの詳細（タイトル・概要・リンク）
    """
    print('[x_agent] 日次投稿 開始')
    topics     = get_topics_from_dynamodb(limit=50, sort_by='velocity')
    posted_ids = get_posted_ids()

    # activeトピックのみ（cooling/archivedは除外）、かつ未投稿
    top3 = [
        t for t in topics
        if t.get('lifecycleStatus', 'active') == 'active'
        and t.get('topicId') not in posted_ids
    ][:3]

    if not top3:
        print('[x_agent] 投稿対象トピックなし（全件投稿済みまたはトピック不足）')
        return

    jst_now  = datetime.now(timezone.utc) + timedelta(hours=9)
    date_str = jst_now.strftime('%Y年%m月%d日')

    # 1ツイート目（見出し）
    titles_preview = '・'.join(
        truncate(t.get('generatedTitle') or t.get('title', ''), 18) for t in top3
    )
    header_text = (
        f'📈 {date_str} 急上昇トップ3\n\n'
        f'{titles_preview}\n\n'
        f'#Flotopic #ニュースまとめ'
    )

    if dry_run:
        print(f'[DRY-RUN] 1ツイート目:\n{header_text}\n')
        thread_id = 'dry-run-id'
    else:
        thread_id = post_tweet(client, header_text)
        print(f'[x_agent] 見出しツイート投稿: {thread_id}')

    # 2〜4ツイート目（各トピック詳細）
    for i, topic in enumerate(top3, 1):
        title   = topic.get('generatedTitle') or topic.get('title', '')
        summary = topic.get('generatedSummary') or topic.get('extractiveSummary', '')
        tid     = topic.get('topicId', '')
        cnt     = int(topic.get('articleCount', 0) or 0)
        tag     = genre_tag(topic)
        url     = f'{SITE_URL}/topic.html?id={tid}'

        tweet_text = (
            f'【{i}/3】{truncate(title, 30)}\n\n'
            f'{truncate(summary, 80)}\n\n'
            f'📄 {cnt}件の記事 | {url}\n'
            f'{tag}'
        )

        if dry_run:
            print(f'[DRY-RUN] ツイート {i}:\n{tweet_text}\n')
        else:
            tweet_id  = post_tweet(client, tweet_text, reply_to_id=thread_id)
            thread_id = tweet_id  # スレッドを繋げる
            mark_as_posted(tid, 'daily')
            print(f'[x_agent] トピック {i} 投稿完了: {tweet_id}')

    print('[x_agent] 日次投稿 完了')


# ── 週次投稿: 今週の5大ストーリー ───────────────────────────────────────────

def post_weekly(client, dry_run=False):
    """
    1週間のトップ5トピック（score降順）を1ツイートにまとめて投稿。
    """
    print('[x_agent] 週次投稿 開始')
    topics = get_topics_from_dynamodb(limit=100, sort_by='score')

    # 過去7日以内に更新されたトピックに絞る
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    recent = []
    for t in topics:
        updated_at = t.get('updatedAt') or t.get('createdAt', '')
        try:
            dt = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
            if dt >= cutoff:
                recent.append(t)
        except Exception:
            pass

    top5 = recent[:5]
    if not top5:
        print('[x_agent] 週次投稿対象なし（過去7日にトピックなし）')
        return

    jst_now   = datetime.now(timezone.utc) + timedelta(hours=9)
    week_str  = jst_now.strftime('%Y年%m月第%W週')
    lines     = []
    for i, t in enumerate(top5, 1):
        title = t.get('generatedTitle') or t.get('title', '')
        cnt   = int(t.get('articleCount', 0) or 0)
        lines.append(f'{i}. {truncate(title, 25)}（{cnt}件）')

    tweet_text = (
        f'📰 {week_str} 5大ストーリー\n\n'
        + '\n'.join(lines)
        + f'\n\n詳細は👉 {SITE_URL}\n#Flotopic #今週のニュース'
    )

    if dry_run:
        print(f'[DRY-RUN] 週次ツイート:\n{tweet_text}\n')
    else:
        tweet_id = post_tweet(client, tweet_text)
        for t in top5:
            mark_as_posted(t.get('topicId', ''), 'weekly')
        print(f'[x_agent] 週次投稿完了: {tweet_id}')

    print('[x_agent] 週次投稿 完了')


# ── 月次投稿: 今月の総括 ─────────────────────────────────────────────────────

def post_monthly(client, dry_run=False):
    """
    過去30日で最も注目されたトピックTop3 + 月間傾向コメントを投稿。
    """
    print('[x_agent] 月次投稿 開始')
    topics = get_topics_from_dynamodb(limit=200, sort_by='score')

    # 過去30日以内に更新されたトピックに絞る
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    recent = []
    for t in topics:
        updated_at = t.get('updatedAt') or t.get('createdAt', '')
        try:
            dt = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
            if dt >= cutoff:
                recent.append(t)
        except Exception:
            pass

    top3 = recent[:3]
    if not top3:
        print('[x_agent] 月次投稿対象なし（過去30日にトピックなし）')
        return

    jst_now  = datetime.now(timezone.utc) + timedelta(hours=9)
    month_str = jst_now.strftime('%Y年%m月')

    lines = []
    for i, t in enumerate(top3, 1):
        title = t.get('generatedTitle') or t.get('title', '')
        cnt   = int(t.get('articleCount', 0) or 0)
        lines.append(f'{i}. {truncate(title, 28)}（{cnt}件の記事）')

    # ジャンル傾向を集計
    genre_counter: dict[str, int] = {}
    for t in recent:
        g = t.get('genre', '総合')
        genre_counter[g] = genre_counter.get(g, 0) + 1
    top_genre = max(genre_counter, key=lambda k: genre_counter[k]) if genre_counter else '総合'

    tweet_text = (
        f'📅 {month_str} ニュース総括\n\n'
        f'【今月の注目トピック TOP3】\n'
        + '\n'.join(lines)
        + f'\n\n今月は「{top_genre}」分野の話題が特に活発でした。\n\n'
        + f'詳細は👉 {SITE_URL}\n#Flotopic #{month_str}ニュース'
    )

    if dry_run:
        print(f'[DRY-RUN] 月次ツイート:\n{tweet_text}\n')
    else:
        tweet_id = post_tweet(client, tweet_text)
        for t in top3:
            mark_as_posted(t.get('topicId', ''), 'monthly')
        print(f'[x_agent] 月次投稿完了: {tweet_id}')

    print('[x_agent] 月次投稿 完了')


# ── メイン ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Flotopic X自動投稿エージェント')
    parser.add_argument(
        '--mode', required=True,
        choices=['daily', 'weekly', 'monthly'],
        help='投稿モード: daily=日次, weekly=週次, monthly=月次',
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='実際には投稿せずツイート内容をターミナルに出力する',
    )
    args = parser.parse_args()

    print(f'[x_agent] モード={args.mode} / dry_run={args.dry_run} / 開始: {datetime.now(timezone.utc).isoformat()}')

    try:
        client = get_twitter_client() if not args.dry_run else None
    except ValueError as e:
        err = str(e)
        print(f'[x_agent] 認証エラー: {err}')
        notify_slack_error(f'Twitter認証エラー: {err}')
        sys.exit(1)

    try:
        if args.mode == 'daily':
            post_daily(client, dry_run=args.dry_run)
        elif args.mode == 'weekly':
            post_weekly(client, dry_run=args.dry_run)
        elif args.mode == 'monthly':
            post_monthly(client, dry_run=args.dry_run)
    except Exception as e:
        import traceback
        err_detail = traceback.format_exc()
        print(f'[x_agent] 予期しないエラー:\n{err_detail}')
        notify_slack_error(f'モード={args.mode} で予期しないエラー\n```{err_detail[:500]}```')
        sys.exit(1)

    print(f'[x_agent] 完了: {datetime.now(timezone.utc).isoformat()}')


if __name__ == '__main__':
    main()
