"""
lambda/processor/handler.py
─────────────────────────────────────────────────────────────────────────────
Stage 2: バッチAI処理 Lambda
  スケジュール: 1日3回 JST 7:00 / 12:00 / 18:00
  EventBridge: cron(0 22,3,9 * * ? *)  ← UTC 22:00/03:00/09:00

役割:
  - DynamoDB の pendingAI=True トピックをスキャン
  - 条件を満たすトピックに Claude Haiku でタイトル・要約を生成
  - DynamoDB を更新（aiGenerated=True, pendingAI=False）
  - S3 api/topics.json を再生成

このLambdaだけがClaude APIを呼び出す。fetcher LambdaはClaude不要。
─────────────────────────────────────────────────────────────────────────────
"""
import json
import os
import re
import time
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

TABLE_NAME        = os.environ.get('TABLE_NAME', 'p003-topics')
S3_BUCKET         = os.environ.get('S3_BUCKET', '')
REGION            = os.environ.get('REGION', 'ap-northeast-1')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
SLACK_WEBHOOK     = os.environ.get('SLACK_WEBHOOK', '')

dynamodb = boto3.resource('dynamodb', region_name=REGION)
table    = dynamodb.Table(TABLE_NAME)
s3       = boto3.client('s3', region_name=REGION)

# 1回のバッチ処理でのClaude API呼び出し上限
# 1日3回 × 最大10 = 最大30呼び出し/日
MAX_API_CALLS = 10

# Claude呼び出し条件
MIN_ARTICLES_FOR_TITLE   = 3   # 3件以上あればタイトル生成 → 【Claude必要ルート】
MIN_ARTICLES_FOR_SUMMARY = 5   # 5件以上あれば要約生成  → 【Claude必要ルート】
# 上記未満は extractive_title/extractive_summary のまま → 【Claude不要ルート】

# ── テキスト正規化 ─────────────────────────────────────────────────────────
STOP_WORDS = {
    'は', 'が', 'を', 'に', 'の', 'と', 'で', 'も', 'や', 'か', 'へ', 'より',
    'から', 'まで', 'という', 'として', 'による', 'において', 'について',
    'した', 'する', 'して', 'された', 'される', 'てい', 'ます', 'です',
    'だっ', 'ある', 'いる', 'なっ', 'れる',
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'of', 'in',
    'to', 'for', 'on', 'at', 'by', 'with', 'as', 'from', 'that', 'this',
    'it', 'its', 'and', 'or', 'but', 'not', 'have', 'has', 'had', 'will',
    'would', 'could', 'should', 'says', 'said', 'new', 'more', 'after',
    'over', 'about', 'up', 'out', 'two', 'into', 'than',
    'he', 'she', 'his', 'her', 'they', 'we', 'you', 'i',
}

SYNONYMS = {
    'アメリカ': '米国', '米': '米国', 'usa': '米国', 'us': '米国',
    '総理': '首相', '内閣総理大臣': '首相',
    '円相場': '為替', 'ドル円': '為替',
    '利上げ': '金利', '利下げ': '金利',
    'オリンピック': '五輪', 'olympic': '五輪',
    'chatgpt': 'ai', 'gpt': 'ai', 'claude': 'ai', 'gemini': 'ai',
}

ENTITY_PATTERNS = [
    r'アメリカ|米国', r'中国|中華人民共和国', r'ロシア|ロシア連邦',
    r'イラン', r'イスラエル', r'韓国|大韓民国', r'北朝鮮',
    r'ウクライナ', r'台湾', r'インド',
    r'石油|原油|エネルギー', r'株価|日経|TOPIX',
    r'円安|円高|為替', r'AI|人工知能', r'半導体',
    r'金利|利上げ|利下げ', r'GDP|景気|インフレ',
    r'選挙|大統領|首相|首脳', r'軍事|戦争|攻撃|爆撃|ミサイル',
    r'地震|台風|災害', r'大谷|翔平', r'トランプ', r'プーチン', r'習近平',
]


def normalize(text):
    text = re.sub(r'[【】「」『』（）()\[\]！？!?\s\u3000・]+', ' ', text.lower())
    words = set()
    for w in text.split():
        if len(w) > 1:
            words.add(SYNONYMS.get(w, w))
    return words


def extract_entities(text):
    entities = set()
    for pattern in ENTITY_PATTERNS:
        if re.search(pattern, text):
            entities.add(pattern.split('|')[0])
    return entities


# ── フォールバック: 抽出的タイトル・要約（Claude不要ルート） ─────────────────

def extractive_title(articles):
    """
    AIを使わないフォールバックタイトル生成。【Claude不要ルート・コストゼロ】
    Claude条件未達のトピックに使う。
    """
    word_counter = Counter()
    for a in articles:
        words = normalize(a.get('title', '')) - STOP_WORDS
        word_counter.update(w for w in words if len(w) >= 2)
    top_words = [w for w, _ in word_counter.most_common(5) if word_counter[w] >= 2]
    all_text  = ' '.join(a.get('title', '') for a in articles)
    entities  = list(extract_entities(all_text))
    if entities and top_words:
        return f'{entities[0]}と{top_words[0]}をめぐる動き'
    elif entities:
        return f'{entities[0]}に関する動向'
    elif top_words:
        return f'{top_words[0]}をめぐる動き'
    else:
        first = articles[0].get('title', '') if articles else ''
        return first[:25] + ('…' if len(first) > 25 else '')


# ── Claude生成関数（このLambdaだけが呼び出す） ────────────────────────────

def generate_title(articles):
    """
    Claude Haiku でトピックタイトルを生成。
    【Claude必要ルート】: MIN_ARTICLES_FOR_TITLE 以上の記事がある場合のみ呼ばれる。
    """
    if not ANTHROPIC_API_KEY:
        return None
    headlines = '\n'.join(a.get('title', '') for a in articles[:6])
    prompt = (
        '以下はニュース記事の見出しです。\n'
        'これらが共通して報じているトピックを表す、概念的で簡潔な日本語タイトルを作ってください。\n\n'
        '【出力ルール】\n'
        '- 12〜20文字程度の短いタイトル\n'
        '- 「〇〇事件」「△△問題」「▲▲の動向」「◇◇をめぐる動き」などの形式が望ましい\n'
        '- 記事タイトルをそのままコピーしないこと\n'
        '- 固有名詞や核心キーワードは必ず含める\n'
        '- 説明文・句読点・かぎかっこ不要。タイトルのみ1行で出力\n\n'
        f'見出し:\n{headlines}'
    )
    try:
        body = json.dumps({
            'model': 'claude-haiku-4-5-20251001',
            'max_tokens': 30,
            'messages': [{'role': 'user', 'content': prompt}],
        }).encode('utf-8')
        req = urllib.request.Request(
            'https://api.anthropic.com/v1/messages',
            data=body,
            headers={
                'x-api-key': ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read())
        return data['content'][0]['text'].strip()
    except Exception as e:
        print(f'generate_title error: {e}')
        return None


def generate_summary(articles):
    """
    Claude Haiku でトピック要約を生成。
    【Claude必要ルート】: MIN_ARTICLES_FOR_SUMMARY 以上の記事がある場合のみ呼ばれる。
    """
    if not ANTHROPIC_API_KEY:
        return None
    headlines = '\n'.join(a.get('title', '') for a in articles[:8])
    prompt = (
        '以下は同じニューストピックを報じた見出し一覧です。\n'
        'このトピックの概要を分かりやすく2〜3文で要約してください。\n'
        '日本語で150字以内にまとめてください。箇条書き不要。自然な文章のみ出力。\n\n'
        f'見出し:\n{headlines}'
    )
    try:
        body = json.dumps({
            'model': 'claude-haiku-4-5-20251001',
            'max_tokens': 150,
            'messages': [{'role': 'user', 'content': prompt}],
        }).encode('utf-8')
        req = urllib.request.Request(
            'https://api.anthropic.com/v1/messages',
            data=body,
            headers={
                'x-api-key': ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        return data['content'][0]['text'].strip()
    except Exception as e:
        print(f'generate_summary error: {e}')
        return None


# ── DynamoDB アクセス ──────────────────────────────────────────────────────

def get_pending_topics(max_topics=100):
    """
    DynamoDB から pendingAI=True のトピックを取得。
    スコア降順で最大 max_topics 件を返す。
    """
    items   = []
    kwargs  = {
        'FilterExpression':        'SK = :m AND pendingAI = :t',
        'ExpressionAttributeValues': {':m': 'META', ':t': True},
        'ProjectionExpression':    'topicId,title,articleCount,score,velocityScore,generatedTitle,generatedSummary,aiGenerated',
    }
    while True:
        r = table.scan(**kwargs)
        items.extend(r.get('Items', []))
        if not r.get('LastEvaluatedKey'):
            break
        kwargs['ExclusiveStartKey'] = r['LastEvaluatedKey']
    items.sort(key=lambda x: int(x.get('score', 0) or 0), reverse=True)
    return items[:max_topics]


def get_latest_articles_for_topic(tid):
    """
    最新 SNAP# アイテムから記事リストを取得。
    fetcher が SNAP# に articles フィールドを保存している。
    """
    try:
        r = table.query(
            KeyConditionExpression=Key('topicId').eq(tid) & Key('SK').begins_with('SNAP#'),
            ScanIndexForward=False,
            Limit=1,
        )
        items = r.get('Items', [])
        if items:
            return items[0].get('articles', [])
    except Exception as e:
        print(f'get_latest_articles_for_topic error [{tid}]: {e}')
    return []


def update_topic_with_ai(tid, gen_title, gen_summary):
    """
    Claude 生成タイトル・要約で DynamoDB META を更新し、pendingAI をクリア。
    aiGenerated=True を設定して次回の fetcher が保持するようにする。
    """
    try:
        update_expr  = 'SET aiGenerated = :t, pendingAI = :f'
        expr_values  = {':t': True, ':f': False}
        if gen_title:
            update_expr += ', generatedTitle = :title'
            expr_values[':title'] = gen_title
        if gen_summary:
            update_expr += ', generatedSummary = :summary'
            expr_values[':summary'] = gen_summary
        table.update_item(
            Key={'topicId': tid, 'SK': 'META'},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
        )
    except Exception as e:
        print(f'update_topic_with_ai error [{tid}]: {e}')


def get_all_topics_for_s3():
    """S3 再生成用に全 META トピックを取得（スコア降順）"""
    items  = []
    kwargs = {
        'FilterExpression':        'SK = :m',
        'ExpressionAttributeValues': {':m': 'META'},
    }
    while True:
        r = table.scan(**kwargs)
        items.extend(r.get('Items', []))
        if not r.get('LastEvaluatedKey'):
            break
        kwargs['ExclusiveStartKey'] = r['LastEvaluatedKey']
    items.sort(key=lambda x: int(x.get('score', 0) or 0), reverse=True)
    return items


# ── S3 出力 ────────────────────────────────────────────────────────────────

def dec_convert(obj):
    if isinstance(obj, Decimal):
        return int(obj)
    raise TypeError


def write_s3(key, data):
    if not S3_BUCKET:
        return
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=json.dumps(data, default=dec_convert, ensure_ascii=False).encode('utf-8'),
        ContentType='application/json',
        CacheControl='max-age=60',
    )


# ── Slack 通知 ─────────────────────────────────────────────────────────────

def notify_slack_error(error_msg: str):
    """エラー発生時のみSlackに通知する（正常完了時は通知しない）"""
    if not SLACK_WEBHOOK:
        return
    try:
        msg = f'🚨 *Processor エラー*\n{error_msg}'
        body = json.dumps({'text': msg}).encode('utf-8')
        req  = urllib.request.Request(
            SLACK_WEBHOOK, data=body,
            headers={'Content-Type': 'application/json'}, method='POST',
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
    except Exception as e:
        print(f'Slack通知エラー: {e}')


# ── Lambda エントリーポイント ──────────────────────────────────────────────

def lambda_handler(event, context):
    """
    バッチAI処理 Lambda エントリーポイント。

    処理フロー:
    1. DynamoDB から pendingAI=True のトピックをスキャン（スコア降順）
    2. 記事数・スコアなどの条件でClaude呼び出しを判断
       - cnt >= MIN_ARTICLES_FOR_TITLE  → 【Claude必要ルート】タイトル生成
       - cnt >= MIN_ARTICLES_FOR_SUMMARY → 【Claude必要ルート】要約生成
       - 条件未達                        → 【Claude不要ルート】既存のextractiveを保持
    3. DynamoDB 更新（aiGenerated=True, pendingAI=False）
    4. S3 api/topics.json を再生成（処理あった場合のみ）
    """
    start_time = time.time()
    print(f'[Processor] 開始: {datetime.now(timezone.utc).isoformat()}')

    pending = get_pending_topics(max_topics=100)
    print(f'[Processor] pendingAI=True トピック数: {len(pending)}')

    api_calls = 0
    processed = 0
    skipped   = 0

    for topic in pending:
        if api_calls >= MAX_API_CALLS:
            print(f'[Processor] API呼び出し上限 ({MAX_API_CALLS}) 到達。残り {len(pending) - processed - skipped} 件は次回。')
            break

        tid      = topic['topicId']
        cnt      = int(topic.get('articleCount', 0) or 0)

        # すでに aiGenerated=True なら pendingAI クリアのみ（fetcherの残留フラグ）
        if topic.get('aiGenerated'):
            update_topic_with_ai(tid, None, None)
            continue

        # 最新 SNAP から記事リストを取得
        articles = get_latest_articles_for_topic(tid)
        if not articles:
            # SNAP なし（古いトピックや削除済み） → title のみのダミーリスト
            raw_title = topic.get('title', '')
            articles  = [{'title': raw_title}] if raw_title else []

        # ── タイトル判定 ────────────────────────────────────────────────────
        gen_title = topic.get('generatedTitle')  # 現在の extractive タイトルを初期値に

        if cnt >= MIN_ARTICLES_FOR_TITLE:
            # 【Claude必要ルート】記事数十分 → Claude Haiku でタイトル生成
            new_title = generate_title(articles)
            if new_title:
                gen_title = new_title
                api_calls += 1
                print(f'  [Claude タイトル] {tid[:8]}... → {new_title[:30]}')
        # else: 【Claude不要ルート】extractive タイトルをそのまま保持

        # ── 要約判定 ─────────────────────────────────────────────────────────
        gen_summary = topic.get('generatedSummary')  # 現在の extractive 要約を初期値に

        if cnt >= MIN_ARTICLES_FOR_SUMMARY and api_calls < MAX_API_CALLS:
            # 【Claude必要ルート】記事数十分 → Claude Haiku で要約生成
            new_summary = generate_summary(articles)
            if new_summary:
                gen_summary = new_summary
                api_calls  += 1
                print(f'  [Claude 要約] {tid[:8]}...')
        # else: 【Claude不要ルート】extractive 要約をそのまま保持

        # DynamoDB 更新
        update_topic_with_ai(tid, gen_title, gen_summary)
        processed += 1

    elapsed = time.time() - start_time
    print(f'[Processor] 完了: 処理={processed}件 / API呼び出し={api_calls}回 / スキップ={skipped}件 / {elapsed:.1f}s')

    # S3 topics.json 再生成（処理があった場合のみ）
    if processed > 0 and S3_BUCKET:
        try:
            topics = get_all_topics_for_s3()
            ts_iso = datetime.now(timezone.utc).isoformat()
            write_s3('api/topics.json', {
                'topics':         topics,
                'updatedAt':      ts_iso,
                'processedByAI':  processed,
                'aiCallsUsed':    api_calls,
            })
            print(f'[Processor] S3 topics.json 再生成完了 ({len(topics)}件)')
        except Exception as e:
            err = f'S3再生成エラー: {e}'
            print(f'[Processor] {err}')
            notify_slack_error(err)

    return {
        'statusCode': 200,
        'body': json.dumps({
            'pending':   len(pending),
            'processed': processed,
            'api_calls': api_calls,
            'skipped':   skipped,
        }),
    }
