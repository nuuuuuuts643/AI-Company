#!/usr/bin/env python3
"""
bluesky_agent.py — Flotopic BlueSky 自動投稿エージェント
─────────────────────────────────────────────────────────────────────────────
投稿パターン3種:
  - 日次  (手動起動 or 将来のスケジュール): 今日の急上昇トップ3をスレッドで投稿
  - 週次  (月曜 JST 9:00 = UTC 0:00): 今週の5大ストーリーを1投稿
  - 月次  (1日 JST 9:00 = UTC 0:00): 今月の総括

実行方法:
  python3 bluesky_agent.py --mode daily    # 日次投稿
  python3 bluesky_agent.py --mode weekly   # 週次投稿
  python3 bluesky_agent.py --mode monthly  # 月次投稿

必要な環境変数（GitHub Secrets）:
  BLUESKY_HANDLE       : BlueSkyアカウントのハンドル (例: flotopic.bsky.social)
  BLUESKY_APP_PASSWORD : bsky.social > 設定 > アプリパスワード で生成したパスワード
  SLACK_WEBHOOK        : エラー通知用 Slack Incoming Webhook URL
  AWS_ACCESS_KEY_ID    : DynamoDB アクセス用 AWS アクセスキー
  AWS_SECRET_ACCESS_KEY: DynamoDB アクセス用 AWS シークレットキー
  AWS_DEFAULT_REGION   : DynamoDB リージョン（デフォルト: ap-northeast-1）

NOTE: BlueSkyアカウントが未作成の場合は https://bsky.app/ でアカウントを作成し、
      設定 > アプリパスワード でアプリ専用パスワードを生成してください。
      通常のログインパスワードではなく、必ずアプリパスワードを使用すること。

ガバナンス:
  実行前に _governance_check.py で自己停止チェックを実施。
  停止フラグが立っている場合は即座に終了する。

BlueSky 仕様:
  - 投稿文字数上限: 300文字（Xの280文字より若干多いが実質同等）
  - リンクカードプレビュー: External embed で flotopic.com へのリンクをカード表示
  - スレッド: reply_to で親投稿を参照して連鎖
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
    from atproto import Client, models
except ImportError:
    print('[bluesky_agent] atproto が未インストールです。pip install atproto を実行してください。')
    sys.exit(1)

try:
    import boto3
except ImportError:
    print('[bluesky_agent] boto3 が未インストールです。pip install boto3 を実行してください。')
    sys.exit(1)

# ── ガバナンスチェック ───────────────────────────────────────────────────────
_script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _script_dir)
try:
    from _governance_check import check_agent_status
    check_agent_status("bluesky_agent")
except ImportError:
    print('[bluesky_agent] _governance_check.py が見つかりません。ガバナンスチェックをスキップして続行。')

# ── 設定 ────────────────────────────────────────────────────────────────────
BLUESKY_HANDLE       = os.environ.get('BLUESKY_HANDLE', '')
BLUESKY_APP_PASSWORD = os.environ.get('BLUESKY_APP_PASSWORD', '')
SLACK_WEBHOOK        = os.environ.get('SLACK_WEBHOOK', '')
REGION               = os.environ.get('AWS_DEFAULT_REGION', 'ap-northeast-1')

# DynamoDB テーブル
TOPICS_TABLE         = 'p003-topics'
BLUESKY_POSTS_TABLE  = 'ai-company-bluesky-posts'  # 投稿済みトピックIDを記録（重複投稿防止・TTL 30日）

SITE_URL = 'https://flotopic.com'

# BlueSky 文字数制限
BSKY_MAX_CHARS = 300

# ── DynamoDB ─────────────────────────────────────────────────────────────────
dynamodb = boto3.resource('dynamodb', region_name=REGION)


def get_topics_from_dynamodb(limit=50, sort_by='velocity'):
    """
    DynamoDB p003-topics から最新の META アイテムを取得。
    sort_by='velocity' → velocityScore 降順（日次用）
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
        table  = dynamodb.Table(BLUESKY_POSTS_TABLE)
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
        print(f'[bluesky_agent] 投稿済みID取得エラー（テーブル未作成の可能性）: {e}')
        return set()


def mark_as_posted(topic_id: str, mode: str):
    """投稿済みとして DynamoDB に記録（TTL 30日）"""
    try:
        table = dynamodb.Table(BLUESKY_POSTS_TABLE)
        table.put_item(Item={
            'topicId':  topic_id,
            'mode':     mode,
            'postedAt': datetime.now(timezone.utc).isoformat(),
            'ttl':      int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp()),
        })
    except Exception as e:
        print(f'[bluesky_agent] 投稿記録エラー: {e}')


# ── Slack エラー通知 ─────────────────────────────────────────────────────────

def notify_slack_error(msg: str):
    """エラー時のみ Slack に通知"""
    if not SLACK_WEBHOOK:
        return
    try:
        body = json.dumps({'text': f'🚨 *BlueSky Agent エラー*\n{msg}'}).encode('utf-8')
        req  = urllib.request.Request(
            SLACK_WEBHOOK, data=body,
            headers={'Content-Type': 'application/json'}, method='POST',
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
    except Exception as e:
        print(f'[bluesky_agent] Slack通知失敗: {e}')


# ── BlueSky クライアント ──────────────────────────────────────────────────────

def get_bluesky_client() -> Client:
    """atproto Client を初期化してログイン"""
    if not BLUESKY_HANDLE or not BLUESKY_APP_PASSWORD:
        raise ValueError(
            '環境変数 BLUESKY_HANDLE と BLUESKY_APP_PASSWORD が未設定です。\n'
            'bsky.app > 設定 > アプリパスワード でアプリパスワードを生成し、\n'
            'GitHub Secrets に BLUESKY_HANDLE と BLUESKY_APP_PASSWORD を登録してください。'
        )
    client = Client()
    client.login(BLUESKY_HANDLE, BLUESKY_APP_PASSWORD)
    return client


def send_post(client: Client, text: str, reply_to=None, embed=None):
    """
    BlueSky に投稿し、レスポンスオブジェクトを返す。
    reply_to: AppBskyFeedPost.ReplyRef オブジェクト（スレッド用）
    embed   : AppBskyEmbedExternal.Main オブジェクト（リンクカード用）
    """
    kwargs = {'text': text}
    if reply_to:
        kwargs['reply_to'] = reply_to
    if embed:
        kwargs['embed'] = embed
    return client.send_post(**kwargs)


def make_reply_ref(post_response) -> 'models.AppBskyFeedPost.ReplyRef':
    """send_post のレスポンスから ReplyRef を生成（スレッド継続用）"""
    strong_ref = models.create_strong_ref(post_response)
    return models.AppBskyFeedPost.ReplyRef(root=strong_ref, parent=strong_ref)


def make_link_embed(uri: str, title: str, description: str) -> 'models.AppBskyEmbedExternal.Main':
    """flotopic.com へのリンクカード embed を生成"""
    return models.AppBskyEmbedExternal.Main(
        external=models.AppBskyEmbedExternal.External(
            uri=uri,
            title=title[:100],        # タイトルは 100 文字以内
            description=description[:200],  # 説明は 200 文字以内
        )
    )


def truncate(text: str, max_len: int) -> str:
    """テキストを max_len 文字に収める（超過時は末尾に「…」）"""
    if not text:
        return ''
    return text[:max_len] + '…' if len(text) > max_len else text


# ── ハッシュタグ生成 ─────────────────────────────────────────────────────────

GENRE_HASHTAGS = {
    '総合':         '#ニュース',
    '政治':         '#政治',
    'ビジネス':     '#ビジネス',
    'テクノロジー': '#テクノロジー',
    'スポーツ':     '#スポーツ',
    'エンタメ':     '#エンタメ',
    '科学':         '#科学',
    '健康':         '#健康',
    '国際':         '#国際',
    '株・金融':     '#株価 #金融',
}


def genre_tag(topic) -> str:
    genre = topic.get('genre', '総合')
    return GENRE_HASHTAGS.get(genre, '#ニュース')


# ── 日次投稿: 今日の急上昇トップ3 ───────────────────────────────────────────

def post_daily(client, dry_run=False):
    """
    velocityScore 降順で上位 3 件をスレッド形式で投稿。
    1投稿目: 「今日の急上昇トップ3 🔥」見出し（リンクカードなし）
    2〜4投稿目: 各トピックの詳細（タイトル・概要） + flotopic.com リンクカード

    BlueSky の 300 文字制限に合わせて各パート設計:
    - 見出し: タイトルプレビュー3件 + ハッシュタグ
    - 各詳細: 番号・タイトル・概要3行程度 + リンク
    """
    print('[bluesky_agent] 日次投稿 開始')
    topics     = get_topics_from_dynamodb(limit=50, sort_by='velocity')
    posted_ids = get_posted_ids()

    # active トピックかつ未投稿のものに絞る
    top3 = [
        t for t in topics
        if t.get('lifecycleStatus', 'active') == 'active'
        and t.get('topicId') not in posted_ids
    ][:3]

    if not top3:
        print('[bluesky_agent] 投稿対象トピックなし（全件投稿済みまたはトピック不足）')
        return

    jst_now  = datetime.now(timezone.utc) + timedelta(hours=9)
    date_str = jst_now.strftime('%Y年%m月%d日')

    # ── 1投稿目（見出し）────────────────────────────────────────────────────
    titles_preview = ' / '.join(
        truncate(t.get('generatedTitle') or t.get('title', ''), 20) for t in top3
    )
    header_text = (
        f'📈 {date_str} 急上昇トップ3\n\n'
        f'{titles_preview}\n\n'
        f'#Flotopic #ニュースまとめ'
    )
    # 300文字に収める（念のためトリム）
    header_text = header_text[:BSKY_MAX_CHARS]

    if dry_run:
        print(f'[DRY-RUN] 1投稿目 ({len(header_text)}文字):\n{header_text}\n')
        thread_ref = None
    else:
        resp       = send_post(client, header_text)
        thread_ref = make_reply_ref(resp)
        print(f'[bluesky_agent] 見出し投稿完了: {resp.uri}')

    # ── 2〜4投稿目（各トピック詳細）────────────────────────────────────────
    for i, topic in enumerate(top3, 1):
        title   = topic.get('generatedTitle') or topic.get('title', '')
        summary = topic.get('generatedSummary') or topic.get('extractiveSummary', '')
        tid     = topic.get('topicId', '')
        cnt     = int(topic.get('articleCount', 0) or 0)
        tag     = genre_tag(topic)
        url     = f'{SITE_URL}/topic.html?id={tid}'

        # 本文: タイトル30文字 + 概要90文字 + 記事数 + タグ → 概ね 200 文字以内
        post_text = (
            f'【{i}/3】{truncate(title, 30)}\n\n'
            f'{truncate(summary, 90)}\n\n'
            f'📄 {cnt}件の記事\n'
            f'{tag} #Flotopic'
        )
        post_text = post_text[:BSKY_MAX_CHARS]

        # リンクカード embed（トピックページ）
        embed = make_link_embed(
            uri=url,
            title=truncate(title, 80),
            description=truncate(summary, 150),
        )

        if dry_run:
            print(f'[DRY-RUN] 投稿 {i}/3 ({len(post_text)}文字):\n{post_text}\n  → リンクカード: {url}\n')
        else:
            resp       = send_post(client, post_text, reply_to=thread_ref, embed=embed)
            # 次の返信先を更新（スレッドチェーン）
            root_ref   = models.create_strong_ref(resp)
            thread_ref = models.AppBskyFeedPost.ReplyRef(
                root=thread_ref.root if thread_ref else root_ref,
                parent=root_ref,
            )
            mark_as_posted(tid, 'daily')
            print(f'[bluesky_agent] トピック {i}/3 投稿完了: {resp.uri}')

    print('[bluesky_agent] 日次投稿 完了')


# ── 週次投稿: 今週の5大ストーリー ───────────────────────────────────────────

def post_weekly(client, dry_run=False):
    """
    1週間のトップ5トピック（score降順）を1投稿＋リンクカードで投稿。
    文字数計算: 見出し30 + 5行×30文字 + フッター60 ≒ 240文字（300文字以内）
    """
    print('[bluesky_agent] 週次投稿 開始')
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
        print('[bluesky_agent] 週次投稿対象なし（過去7日にトピックなし）')
        return

    jst_now  = datetime.now(timezone.utc) + timedelta(hours=9)
    week_str = jst_now.strftime('%Y年%m月第%W週')

    lines = []
    for i, t in enumerate(top5, 1):
        title = t.get('generatedTitle') or t.get('title', '')
        cnt   = int(t.get('articleCount', 0) or 0)
        lines.append(f'{i}. {truncate(title, 22)}（{cnt}件）')

    post_text = (
        f'📰 {week_str} 5大ストーリー\n\n'
        + '\n'.join(lines)
        + f'\n\n#Flotopic #今週のニュース'
    )
    post_text = post_text[:BSKY_MAX_CHARS]

    # リンクカード: Flotopic トップページ
    embed = make_link_embed(
        uri=SITE_URL,
        title='Flotopic — 今週の5大ストーリー',
        description='\n'.join(lines),
    )

    if dry_run:
        print(f'[DRY-RUN] 週次投稿 ({len(post_text)}文字):\n{post_text}\n  → リンクカード: {SITE_URL}\n')
    else:
        resp = send_post(client, post_text, embed=embed)
        for t in top5:
            mark_as_posted(t.get('topicId', ''), 'weekly')
        print(f'[bluesky_agent] 週次投稿完了: {resp.uri}')

    print('[bluesky_agent] 週次投稿 完了')


# ── 月次投稿: 今月の総括 ─────────────────────────────────────────────────────

def post_monthly(client, dry_run=False):
    """
    過去30日で最も注目されたトピック Top3 + 月間ジャンル傾向コメントを1投稿。
    文字数計算: 見出し20 + 3行×35文字 + ジャンルコメント50 + フッター50 ≒ 225文字
    """
    print('[bluesky_agent] 月次投稿 開始')
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
        print('[bluesky_agent] 月次投稿対象なし（過去30日にトピックなし）')
        return

    jst_now   = datetime.now(timezone.utc) + timedelta(hours=9)
    month_str = jst_now.strftime('%Y年%m月')

    lines = []
    for i, t in enumerate(top3, 1):
        title = t.get('generatedTitle') or t.get('title', '')
        cnt   = int(t.get('articleCount', 0) or 0)
        lines.append(f'{i}. {truncate(title, 25)}（{cnt}件）')

    # ジャンル傾向を集計
    genre_counter: dict[str, int] = {}
    for t in recent:
        g = t.get('genre', '総合')
        genre_counter[g] = genre_counter.get(g, 0) + 1
    top_genre = max(genre_counter, key=lambda k: genre_counter[k]) if genre_counter else '総合'

    post_text = (
        f'📅 {month_str} ニュース総括\n\n'
        f'【注目トピック TOP3】\n'
        + '\n'.join(lines)
        + f'\n\n今月は「{top_genre}」の話題が活発でした。\n'
        + f'#Flotopic #{month_str}ニュース'
    )
    post_text = post_text[:BSKY_MAX_CHARS]

    # リンクカード: Flotopic トップページ
    embed = make_link_embed(
        uri=SITE_URL,
        title=f'Flotopic — {month_str} ニュース総括',
        description='\n'.join(lines) + f'\n\n今月は「{top_genre}」の話題が活発でした。',
    )

    if dry_run:
        print(f'[DRY-RUN] 月次投稿 ({len(post_text)}文字):\n{post_text}\n  → リンクカード: {SITE_URL}\n')
    else:
        resp = send_post(client, post_text, embed=embed)
        for t in top3:
            mark_as_posted(t.get('topicId', ''), 'monthly')
        print(f'[bluesky_agent] 月次投稿完了: {resp.uri}')

    print('[bluesky_agent] 月次投稿 完了')


# ── メイン ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Flotopic BlueSky 自動投稿エージェント')
    parser.add_argument(
        '--mode', required=True,
        choices=['daily', 'weekly', 'monthly'],
        help='投稿モード: daily=日次, weekly=週次, monthly=月次',
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='実際には投稿せず投稿内容をターミナルに出力する',
    )
    args = parser.parse_args()

    print(
        f'[bluesky_agent] モード={args.mode} / dry_run={args.dry_run} / '
        f'開始: {datetime.now(timezone.utc).isoformat()}'
    )

    try:
        client = get_bluesky_client() if not args.dry_run else None
    except ValueError as e:
        err = str(e)
        print(f'[bluesky_agent] 認証エラー: {err}')
        notify_slack_error(f'BlueSky認証エラー: {err}')
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
        print(f'[bluesky_agent] 予期しないエラー:\n{err_detail}')
        notify_slack_error(f'モード={args.mode} で予期しないエラー\n```{err_detail[:500]}```')
        sys.exit(1)

    print(f'[bluesky_agent] 完了: {datetime.now(timezone.utc).isoformat()}')


if __name__ == '__main__':
    main()
