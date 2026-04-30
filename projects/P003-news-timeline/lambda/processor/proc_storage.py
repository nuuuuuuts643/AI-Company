"""DynamoDB / S3 アクセス層と Slack 通知。"""
from __future__ import annotations
import hashlib
import io
import json
import os
import re
import time
import urllib.request
from collections import Counter
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor, as_completed
from email.utils import formatdate, parsedate_to_datetime

from boto3.dynamodb.conditions import Key, Attr

from proc_config import S3_BUCKET, SLACK_WEBHOOK, TOPICS_S3_CAP, dynamodb, table, s3, PROCESSOR_SCHEMA_VERSION

# OGP画像生成設定
_OGP_W, _OGP_H = 1200, 630
_OGP_BG     = (15, 23, 42)        # #0f172a (Flotopicダークブルー)
_OGP_ACCENT = (99, 102, 241)      # #6366f1 (インジゴ)
_OGP_TEXT   = (248, 250, 252)     # #f8fafc (ほぼ白)
_OGP_SUB    = (148, 163, 184)     # #94a3b8 (スレート)
_OGP_CARD   = (30, 41, 59)        # #1e293b (カード背景)
_FONT_PATH  = '/var/task/NotoSansJP-Regular.ttf'  # Lambda zip内に同梱

_TICKER_RE  = re.compile(r'【\d{3,5}[A-Z]?】|：株価|株式情報\b|株価情報\b')
_KW_STOP    = {
    'ニュース', '速報', '最新', '話題', '注目', '動画', '写真', '記事', '中継',
    # 汎用的すぎる漢字語（ニュース文中に頻出するが固有名詞・話題でない）
    '動向', '影響', '情勢', '問題', '対応', '状況', '関係', '活動', '実施', '開催',
    '発表', '報告', '内容', '結果', '方針', '対策', '検討', '確認', '実現', '推進',
    '強化', '改善', '整備', '支援', '提供', '拡大', '展開', '継続', '協力', '連携',
    '取り組み', '見通し', '増加', '減少', '上昇', '下落', '変化', '今後', '今回',
    'について', 'とは', 'のため', 'による', 'として',
    # 追加: 汎用名詞
    '課題', '企業', '議論', '対立', '会議', '調査', '研究', '報道', '声明', '決定',
    '方向', '制度', '政策', '経済', '社会', '市場', '投資', '技術', '事業', '計画',
}
_KW_MAX     = 10


def _parse_pubdate(raw) -> datetime | None:
    """記事 pubDate を datetime に変換する。RFC 2822 / ISO 8601 / epoch (秒・ミリ秒) すべて対応。

    戻り値は tz-aware (UTC). 失敗時 None。

    T2026-0428-E2-4: 旧実装は ISO/epoch のみ対応で、RSS 由来の RFC 2822 形式
    ('Mon, 23 Mar 2026 07:00:00') が silently drop される bug があり、
    judge_prediction が永遠に new_titles=0 で skip していた。
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    # 1. ISO 8601
    try:
        dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
    # 2. epoch (秒 / ミリ秒)
    try:
        ts = int(s)
        if ts > 0:
            return datetime.fromtimestamp(ts if ts < 1e11 else ts / 1000, tz=timezone.utc)
    except Exception:
        pass
    # 3. RFC 2822 (RSS pubDate)
    try:
        dt = parsedate_to_datetime(s)
        if dt is not None:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
    except Exception:
        pass
    return None


def _extract_trending_keywords(topics: list) -> list:
    counter = Counter()
    for t in topics:
        title = t.get('generatedTitle') or t.get('title', '')
        for w in re.findall(r'[ァ-ヶー]{3,}|[一-龯々]{2,}|[A-Za-z]{4,}', title):
            if w not in _KW_STOP:
                counter[w] += 1
    return [{'keyword': w, 'count': c} for w, c in counter.most_common(_KW_MAX * 3) if c >= 3][:_KW_MAX]


# タイトル一発理解性が低いと判定するNGパターン (2026-04-27)
# このパターンを含むタイトルは「何の話か」が抜けてるので強制再生成する
_NG_TITLE_PATTERNS = (
    'をめぐる最新の動き',
    '最新の動きまとめ',
    'をめぐる動き',
    'わかりやすく解説',
    'をわかりやすく',
    'について解説',
    'とは何か',  # 単独「とは何か」(タイトル末尾) のみ NG。「〜とは何か・なぜ〜」のような複合句はOK
    '動向と争点',
    '最新情報',
    '詳細まとめ',
    '背景まとめ',
    'と背景',
    '経緯まとめ',
)


def _is_low_quality_title(title: str) -> bool:
    """初見ユーザーが一発で『何の話か』分からない曖昧タイトルを検出。"""
    if not title:
        return False
    # 末尾が NG パターンで終わる場合のみ判定 (途中にあるのはOK)
    for pat in _NG_TITLE_PATTERNS:
        if title.endswith(pat) or title.endswith(pat + 'まとめ'):
            return True
    return False


_TITLE_MARKDOWN_LEAD_RE = re.compile(r'^\s*[#*]+\s*')
_TITLE_MARKDOWN_TRAIL_RE = re.compile(r'\s*[#*]+\s*$')


def _strip_title_markdown(title):
    """T2026-0428-AF: generatedTitle に残った markdown 装飾文字 (#, *, **) を除去。
    レガシー AI 生成では `# 米中対立` `**強調タイトル**` 等が title に混入していた。
    update_topic_with_ai / update_topic_s3_file 経由で再保存されるたびにここでクリーンアップする。
    既存データの一括書き換えは行わない（書き戻し時に自然に正規化される）。
    """
    if not isinstance(title, str):
        return title
    t = _TITLE_MARKDOWN_LEAD_RE.sub('', title)
    t = _TITLE_MARKDOWN_TRAIL_RE.sub('', t)
    return t.strip()


def save_prediction_log(tid: str, gen_story: dict | None) -> bool:
    """proc_ai が出した forecast/outlook を時系列で永続保存する。
    SK='PRED#YYYYMMDDTHHMMSS' で p003-topics テーブルに記録。
    将来「1ヶ月前の予測 vs 実際」を遡及検証するための土台 (Phase 3 の起点)。
    今しか作れない時系列データなので proc_ai 実行ごとに必ず保存する。
    Returns: 保存したか。"""
    if not gen_story:
        return False
    forecast = (gen_story.get('forecast') or '').strip()
    outlook = (gen_story.get('outlook') or '').strip()
    if not forecast and not outlook:
        return False  # 予測本体がない場合は保存しない
    try:
        ts_iso = datetime.now(timezone.utc).isoformat()
        ts_key = ts_iso.replace(':', '').replace('-', '').split('.')[0]  # YYYYMMDDTHHMMSS
        item = {
            'topicId':    tid,
            'SK':         f'PRED#{ts_key}',
            'timestamp':  ts_iso,
            'forecast':   forecast,
            'outlook':    outlook,
            'aiSummary':  (gen_story.get('aiSummary') or '')[:300],  # コンテキストとしての現状サマリー (検証時に必要)
            'phase':      gen_story.get('phase'),
            'topicTitle': gen_story.get('topicTitle'),
            'ttl':        int(time.time()) + 365 * 86400,  # 1年保持 (1年前の予測を遡及検証できるよう)
        }
        table.put_item(Item=item)
        return True
    except Exception as e:
        print(f'[save_prediction_log] {tid[:8]}... 失敗: {e}')
        return False


_ARCHIVED_META_TTL_DAYS = 90  # archived 化された META は 90日で自動削除 (コスト削減)


def auto_archive_incoherent(tid: str, gen_story: dict | None) -> bool:
    """AI が isCoherent=false と判定したトピックを lifecycleStatus='archived' に自動退避。
    重要トピック (大規模・人気・親子関係持ち・長期継続) は TTL を付けず永続保持。
    雑なゴミだけ TTL 90日で自動削除されコスト削減。
    Returns: archive したかどうか。"""
    if not gen_story:
        return False
    is_coherent = gen_story.get('isCoherent')
    if is_coherent is False:
        try:
            # 重要度を判定: 重要なら TTL 付けない
            existing = table.get_item(
                Key={'topicId': tid, 'SK': 'META'},
                ProjectionExpression='articleCount,hatenaCount,parentTopicId,childTopics,firstArticleAt',
            ).get('Item', {})
            if _is_protected_from_ttl(existing):
                table.update_item(
                    Key={'topicId': tid, 'SK': 'META'},
                    UpdateExpression='SET lifecycleStatus = :ls, topicCoherent = :tc',
                    ExpressionAttributeValues={':ls': 'archived', ':tc': False},
                )
                print(f'[auto_archive] {tid[:8]}... isCoherent=false → archived (重要トピックのため TTL なし保持)')
            else:
                ttl_ts = int(time.time()) + _ARCHIVED_META_TTL_DAYS * 86400
                # ttl は DynamoDB 予約語のため #ttl で別名置換 (UpdateExpression ValidationException 回避)
                table.update_item(
                    Key={'topicId': tid, 'SK': 'META'},
                    UpdateExpression='SET lifecycleStatus = :ls, topicCoherent = :tc, #ttl = :ttl',
                    ExpressionAttributeNames={'#ttl': 'ttl'},
                    ExpressionAttributeValues={':ls': 'archived', ':tc': False, ':ttl': ttl_ts},
                )
                print(f'[auto_archive] {tid[:8]}... isCoherent=false → archived + TTL{_ARCHIVED_META_TTL_DAYS}日')
            return True
        except Exception as e:
            print(f'[auto_archive] {tid[:8]}... 失敗: {e}')
    return False


def _is_protected_from_ttl(item: dict) -> bool:
    """TTL を付けるべきでない重要トピックの判定。
    保護対象: 大規模 (articles>=10) / 人気 (はてブ>=10 or 閲覧>=20) / 親子関係持ち / 長期継続 (>=180日) / 子トピック保有
    これらは archived でもストレージ保持。「戦争1年継続」「人気記事」を保護。"""
    if int(item.get('articleCount', 0) or 0) >= 10:
        return True
    if int(item.get('hatenaCount', 0) or 0) >= 10:
        return True
    if item.get('parentTopicId') or item.get('childTopics'):
        return True
    # 長期継続 (firstArticleAt が180日以上前)
    fst = item.get('firstArticleAt')
    if fst:
        try:
            fst_ts = int(fst)
            if (int(time.time()) - fst_ts) > 180 * 86400:
                return True
        except Exception:
            pass
    return False


def add_ttl_to_existing_archived() -> dict:
    """既存 archived/legacy メタに条件付き TTL 90日を後付けする (1回限り運用)。
    雑なゴミは消すが、人気・大規模・親子関係・長期継続トピックは保護。
    Returns: {ttl_added, protected, total}"""
    if not S3_BUCKET:
        return {'ttl_added': 0, 'protected': 0, 'total': 0}
    ttl_added = 0
    protected = 0
    total = 0
    ttl_ts = int(time.time()) + _ARCHIVED_META_TTL_DAYS * 86400
    scan_kwargs = {
        'FilterExpression': (
            Attr('SK').eq('META')
            & Attr('lifecycleStatus').is_in(['archived', 'legacy'])
            & ~Attr('ttl').exists()
        ),
        'ProjectionExpression': 'topicId,articleCount,hatenaCount,parentTopicId,childTopics,firstArticleAt',
    }
    while True:
        r = table.scan(**scan_kwargs)
        for item in r.get('Items', []):
            total += 1
            if _is_protected_from_ttl(item):
                protected += 1
                continue
            try:
                # ttl は DynamoDB 予約語のため #ttl で別名置換
                table.update_item(
                    Key={'topicId': item['topicId'], 'SK': 'META'},
                    UpdateExpression='SET #ttl = :ttl',
                    ExpressionAttributeNames={'#ttl': 'ttl'},
                    ExpressionAttributeValues={':ttl': ttl_ts},
                )
                ttl_added += 1
            except Exception:
                pass
        if not r.get('LastEvaluatedKey'):
            break
        scan_kwargs['ExclusiveStartKey'] = r['LastEvaluatedKey']
    return {'ttl_added': ttl_added, 'protected': protected, 'total': total}


def force_reset_pending_all() -> int:
    """topics.json に**実際に公開中**のトピックのみ pendingAI=True にリセット。
    DynamoDB scan ではなく S3 の topics.json を直接読んで対象を絞る (2026-04-27 コスト最適化)。
    結果: ~110件 ($0.25) で済む。

    T2026-0428-AE: ConditionExpression='attribute_exists(topicId)' を必須化。
    DynamoDB の update_item は対象キーが無いと新規作成するため、lifecycle/TTL で
    既に消えたトピックに対して呼ぶと「topicId+pendingAI+aiGenerated だけのスタブ META」
    を量産していた (空トピック再発の根本原因)。条件付き update に変えることで物理ガード。
    Returns: リセットしたトピック数。"""
    if not S3_BUCKET:
        return 0
    visible_tids = _load_visible_topic_ids()
    count = 0
    skipped = 0
    for tid in visible_tids:
        try:
            table.update_item(
                Key={'topicId': tid, 'SK': 'META'},
                UpdateExpression='SET pendingAI = :p, aiGenerated = :a',
                ConditionExpression='attribute_exists(topicId)',
                ExpressionAttributeValues={':p': True, ':a': False},
            )
            count += 1
        except table.meta.client.exceptions.ConditionalCheckFailedException:
            skipped += 1
        except Exception as e:
            print(f'[force_reset_pending_all] {tid} 失敗: {e}')
    if skipped:
        print(f'[force_reset_pending_all] {skipped}件 META 不在のためスキップ (stub生成防止)')
    # pending_ai.json をクリアして全トピックがフルスキャンで拾われるように
    try:
        s3.put_object(
            Bucket=S3_BUCKET, Key='api/pending_ai.json',
            Body=json.dumps({'topicIds': []}),
            ContentType='application/json',
        )
    except Exception:
        pass
    return count


def _is_extractive_summary(text: str) -> bool:
    """generatedSummary が fetcher 側 extractive_summary() フォールバックである可能性を判定。
    text_utils.is_extractive_summary と同じロジック (processor lambda は fetcher の
    text_utils をインポートしていないため複製)。
    AI 未実行のまま見出し連結が generatedSummary に居座っているケースを救済する。"""
    if not text:
        return False
    t = str(text)
    if '複数の報道' in t and '関連して' in t:
        return True
    if 'また、「' in t and '」など' in t:
        return True
    if '最新では「' in t and '」と報じられている' in t:
        return True
    import re as _re
    if _re.search(r'（[^（）]*ほか\s*\d+件）\s*$', t):
        return True
    if _re.search(r'（\s*\d+件）\s*$', t):
        return True
    return False


def needs_ai_processing(item):
    """このトピックがAI処理を必要とするかを判定。

    以下のいずれかに該当する場合は処理が必要:
    - aiGenerated=False または未設定
    - storyTimeline が空または未設定（4セクション形式未生成）
    - pendingAI=True（fetcher が新記事を検知してフラグを立てた）
    - imageUrl が未設定（OGP画像未生成）
    - generatedTitle が「〇〇をめぐる最新の動き」等の曖昧パターンで終わる(2026-04-27)
    - generatedSummary が extractive_summary フォールバックの形 (見出し連結) (2026-04-27 c1bbe0fe事件)
    - schemaVersion < PROCESSOR_SCHEMA_VERSION (T2026-0428-AO: 古いスキーマで処理されたトピックは自動再処理)

    Note: articleCount<2 のトピックはフロントエンドで非表示（processor もスキップ）のため
    False を返して pending_ai.json から自動クリーンアップされるようにする。
    2件目の記事が来た際は fetcher が pendingAI=True をセットし直す。
    """
    if int(item.get('articleCount', 0) or 0) < 2:
        return False
    if item.get('pendingAI'):
        return True
    if not item.get('aiGenerated'):
        return True
    # T2026-0428-AO: schemaVersion チェック。processor スキーマが上がったら全再処理。
    try:
        sv = int(item.get('schemaVersion', 0) or 0)
    except (ValueError, TypeError):
        sv = 0
    if sv < PROCESSOR_SCHEMA_VERSION:
        return True
    # T38: aiGenerated=True でも generatedSummary が extractive ならば未処理扱いで再処理させる
    if _is_extractive_summary(item.get('generatedSummary', '')):
        return True
    timeline = item.get('storyTimeline')
    is_minimal = (item.get('summaryMode') == 'minimal'
                  or int(item.get('articleCount', 0) or 0) <= 2)
    if not is_minimal and (not timeline or (isinstance(timeline, list) and len(timeline) == 0)):
        return True
    if not is_minimal and not item.get('storyPhase'):
        return True
    if not item.get('imageUrl'):
        return True
    # 曖昧タイトルは強制再生成
    if _is_low_quality_title(item.get('generatedTitle', '')):
        return True
    # T256 (2026-04-28): keyPoint は minimal/standard/full 全モードで生成される。
    # aiGenerated=True でも keyPoint が未設定/空文字なら再処理対象。
    # handler.py _required_full_fields の _is_minimal 免除削除（T256 fix）と対で機能する。
    # T2026-0428-BH: schema は 200〜300 字を要求するため 100 字未満は不十分扱いで再処理。
    # 過去 (2026-04-26〜27) に滞留した平均 43.8 字の短い keyPoint をキューに取り込む。
    if _is_keypoint_inadequate(item.get('keyPoint')):
        return True
    # T2026-0428-J/E: standard/full mode (記事3件以上) では statusLabel / watchPoints も必須。
    # 新フィールドが空の旧 aiGenerated=True topic を再処理対象に取り込み、滞留を解消する。
    _ac = int(item.get('articleCount', 0) or 0)
    if _ac >= 3:
        if not str(item.get('statusLabel') or '').strip():
            return True
        if not str(item.get('watchPoints') or '').strip():
            return True
    # T2026-0428-AH: storyPhase=='発端' かつ articleCount>=3 は再生成対象に含める。
    # T219 で「記事3件以上で発端禁止」をプロンプト強化済だが、aiGenerated=True 旧 topic は
    # ここで skip されるため誤判定の発端が永続化していた（本番 54/93 = 58% で確認）。
    if item.get('storyPhase') == '発端' and int(item.get('articleCount', 0) or 0) >= 3:
        return True
    return False


def _sort_by_recency(items: list) -> list:
    """新しい順 (updatedAt 降順) にソートする。updatedAt がない場合は topicId 降順でフォールバック。

    目的 (2026-04-29): MAX_API_CALLS=30/run の予算を「最新の topic」から消費する。
    背景: 旧実装は元の順序を保つだけだったため、古い backlog が先に処理され、
    新規トピックが後回しになっていた。

    優先順位:
      1. updatedAt あり > updatedAt なし
      2. updatedAt 降順 (新しい順)
      3. topicId 降順 (タイブレーク・updatedAt 同値や欠損時のフォールバック)
    """
    def _key(it):
        ua = it.get('updatedAt') or ''
        tid = it.get('topicId') or ''
        return (1 if ua else 0, ua, tid)
    return sorted(items, key=_key, reverse=True)


def _apply_tier0_budget(items: list, budget: int = 100) -> list:
    """T2026-0428-O: 大規模クラスタ (articles>=10) で aiGenerated=False の topic を
    必ず先頭に固定 budget 件まで配置する。Tier-0 以外は updatedAt 降順 (新しい順) にソート。

    背景: T213 の 4段階優先度ソート後でも、可視 × 未生成の 0 番手の中で
    articleCount の重みが弱く、小規模クラスタが先に処理されて大規模が放置される
    事象が観測された (本番 2026-04-28 05:13 JST)。

    2026-04-28 改訂: count 上限を 3→100 (=実質 max_topics) に拡大し、Tier-0 を
    全件最前列に配置する。1 サイクルでの取りこぼしは handler.py 側の
    「残り wallclock の 50% を Tier-0 専用に予約」する物理ゲートで防ぐ。

    2026-04-29 追加: Tier-0 以外の rest を _sort_by_recency で新しい順に並べ替える。
    MAX_API_CALLS=30 の予算を「最新トピック」から優先消費する。
    """
    if not items:
        return items
    tier0 = []
    rest = []
    for it in items:
        try:
            ac = int(it.get('articleCount', 0) or 0)
        except (ValueError, TypeError):
            ac = 0
        if ac >= 10 and not it.get('aiGenerated') and len(tier0) < budget:
            tier0.append(it)
        else:
            rest.append(it)
    if tier0:
        print(f'[get_pending_topics] Tier-0 (articles>=10 × aiGenerated=False) を先頭に固定: {len(tier0)}件')
    rest = _sort_by_recency(rest)
    return tier0 + rest


def _load_visible_topic_ids() -> set:
    """topics.jsonからユーザーに見えているtopicIdセットを返す。取得失敗時は空set。"""
    if not S3_BUCKET:
        return set()
    try:
        resp = s3.get_object(Bucket=S3_BUCKET, Key='api/topics.json')
        data = json.loads(resp['Body'].read())
        topics = data.get('topics', data) if isinstance(data, dict) else data
        return {t['topicId'] for t in topics if t.get('topicId')}
    except Exception:
        return set()


def get_pending_topics(max_topics=100):
    """S3のpending_ai.jsonからトピックIDを取得し、DynamoDBで個別に取得。"""
    pending_ids = []
    if S3_BUCKET:
        try:
            resp = s3.get_object(Bucket=S3_BUCKET, Key='api/pending_ai.json')
            data = json.loads(resp['Body'].read())
            pending_ids = data.get('topicIds', [])
        except Exception:
            pass

    # topics.jsonに含まれる（ユーザーに見えている）トピックIDを取得（T213優先度tier-0用）
    visible_tids = _load_visible_topic_ids()
    if visible_tids:
        print(f'[get_pending_topics] topics.json 可視トピック数: {len(visible_tids)}件')

    # E2-2 (2026-04-29): pending_ai.json が閾値未満なら DDB pendingAI=True で自動 union。
    # 過去 (2026-04-28) に pending_ai.json=24 件 vs DDB pendingAI=True=855 件 という極端な
    # 乖離が発生し、processor が 24 件しか処理対象に取れず 855 件の遡及が滞留した。
    # 原因: quality_heal cron は 1日1回だが、proc_ai は 5回/日 走るため pending_ai.json が
    # 早期に枯渇しやすい。閾値未満で自動 sync すれば quality_heal 待ちなしで回復する。
    # コストは scan 1回 (~1MB / META 1068 件) のみ。閾値超過時は scan しない。
    PENDING_REPLENISH_THRESHOLD = max_topics  # max_topics(100)未満なら次サイクルで処理が痩せるため補充
    if S3_BUCKET and len(pending_ids) < PENDING_REPLENISH_THRESHOLD:
        try:
            ddb_pending_ids: list = []
            scan_kwargs = {
                'FilterExpression': Attr('SK').eq('META') & Attr('pendingAI').eq(True),
                'ProjectionExpression': 'topicId',
            }
            while True:
                r = table.scan(**scan_kwargs)
                ddb_pending_ids.extend(
                    x['topicId'] for x in r.get('Items', []) if x.get('topicId')
                )
                if not r.get('LastEvaluatedKey'):
                    break
                scan_kwargs['ExclusiveStartKey'] = r['LastEvaluatedKey']
            if ddb_pending_ids:
                merged = list(dict.fromkeys(pending_ids + ddb_pending_ids))
                added = len(merged) - len(pending_ids)
                if added > 0:
                    print(
                        f'[get_pending_topics] auto-replenish: pending_ai.json={len(pending_ids)}件 '
                        f'< 閾値{PENDING_REPLENISH_THRESHOLD} → DDB pendingAI=True {len(ddb_pending_ids)}件 '
                        f'と union → +{added}件 (合計{len(merged)}件)'
                    )
                    pending_ids = merged
                    # pending_ai.json を再永続化して次回以降の起動を健全化
                    try:
                        s3.put_object(
                            Bucket=S3_BUCKET, Key='api/pending_ai.json',
                            Body=json.dumps({'topicIds': merged}).encode('utf-8'),
                            ContentType='application/json',
                        )
                    except Exception as e:
                        print(f'[get_pending_topics] auto-replenish 後の pending_ai.json 永続化失敗: {e}')
        except Exception as e:
            # scan 失敗は致命的でない (既存 pending_ids で続行)
            print(f'[get_pending_topics] auto-replenish scan 失敗 (継続): {e}')

    if pending_ids:
        items = []
        still_pending = []
        # 全IDを走査。削除済み・処理済みIDを取り除く（上限なし）。
        # キャップなしで全件収集してから優先度ソートすることで、
        # pending_ai.json 先頭の古いIDが新トピックをブロックする問題（T213）を解消。
        for tid in pending_ids:
            try:
                r = table.get_item(
                    Key={'topicId': tid, 'SK': 'META'},
                    ProjectionExpression='topicId,title,articleCount,score,velocityScore,lastUpdated,generatedTitle,generatedSummary,storyTimeline,storyPhase,aiGenerated,aiGeneratedAt,pendingAI,imageUrl,genre,genres,keyPoint,summaryMode,statusLabel,watchPoints',
                )
                item = r.get('Item')
                if item and needs_ai_processing(item):
                    still_pending.append(tid)
                    items.append(item)
                # 存在しないIDまたは処理済みIDはstill_pendingに追加しない（自動クリーンアップ）
            except Exception:
                still_pending.append(tid)

        # pending_ai.jsonを処理済みIDを除去した状態に更新
        if S3_BUCKET and len(still_pending) < len(pending_ids):
            try:
                s3.put_object(
                    Bucket=S3_BUCKET, Key='api/pending_ai.json',
                    Body=json.dumps({'topicIds': still_pending}),
                    ContentType='application/json',
                )
                print(f'[get_pending_topics] pending_ai.json 更新: {len(pending_ids)} → {len(still_pending)} 件')
            except Exception as e:
                print(f'[get_pending_topics] pending_ai.json 更新失敗: {e}')

        # 4段階優先度ソート（T213修正 + topics.json可視優先）:
        # 0. topics.json可視 かつ aiGenerated=False: ユーザーが見ているのに未生成 → 最優先
        # 1. pendingAI=True: fetcherが新記事を検知してフラグを立てた
        # 2. aiGenerated=False: 一度もAI処理されていない（非可視）
        # 3. imageUrl/storyTimeline等の欠損補完 → 最後
        # 各グループ内は score DESC → lastUpdated DESC
        def _ts(s):
            try:
                return datetime.fromisoformat((s or '').replace('Z', '+00:00')).timestamp()
            except Exception:
                return 0.0

        # T218 根本修正(2026-04-27): pending_ai.json に入ってない可視未AIトピックを強制 union
        # 古い高articleCountトピックが pending queue から永久に外れるバグを解消
        if visible_tids:
            already_in_queue = {it.get('topicId') for it in items}
            missing_visible = [tid for tid in visible_tids if tid not in already_in_queue]
            if missing_visible:
                print(f'[get_pending_topics] 可視untrackedトピック {len(missing_visible)}件をDynamoDBから補充')
                for tid in missing_visible[:50]:  # 1回 50件まで補充(暴走防止)
                    try:
                        r = table.get_item(
                            Key={'topicId': tid, 'SK': 'META'},
                            ProjectionExpression='topicId,title,articleCount,score,velocityScore,lastUpdated,generatedTitle,generatedSummary,storyTimeline,storyPhase,aiGenerated,aiGeneratedAt,pendingAI,imageUrl,genre,genres,keyPoint,summaryMode,statusLabel,watchPoints',
                        )
                        item = r.get('Item')
                        if item and needs_ai_processing(item):
                            still_pending.append(tid)
                            items.append(item)
                    except Exception:
                        pass

        def _sort_key(x):
            tid = x.get('topicId', '')
            is_visible = tid in visible_tids
            # T2026-0428-AW: 可視 × keyPoint 欠落 を priority 0 に昇格。
            # 旧来は aiGenerated=True で keyPoint 欠落の topic は priority 1 に沈み、
            # 新規未生成 topic に押されて永続的に補完されない事象が確認された
            # (本番 keyPoint 充填率 10.02%・961/1068 件未充填)。ユーザーが見ている
            # トピックで keyPoint が空なのは新規未生成と同等のユーザー影響なので priority 0。
            # T2026-0428-BH: 「欠落」判定を「100 字未満の不十分も含む」に拡張。
            # 過去 (2026-04-26〜27) の短い keyPoint (平均 43.8 字) を priority 0 に救済する。
            kp_missing = _is_keypoint_inadequate(x.get('keyPoint'))
            if is_visible and (not x.get('aiGenerated') or kp_missing):
                priority = 0
            elif x.get('pendingAI'):
                priority = 1
            elif not x.get('aiGenerated'):
                priority = 2
            else:
                priority = 3
            return (priority, -int(x.get('score', 0) or 0), -_ts(x.get('lastUpdated', '')))
        items.sort(key=_sort_key)
        # T2026-0428-O: 大規模クラスタ (articles>=10 × aiGenerated=False) を全件先頭固定。
        # 1 サイクルでの取りこぼしは handler.py の wallclock 50% Tier-0 予約で防ぐ。
        items = _apply_tier0_budget(items)
        visible_pending = sum(1 for x in items if x.get('topicId', '') in visible_tids and not x.get('aiGenerated'))
        print(f'[get_pending_topics] ソート完了: 可視未生成={visible_pending}件が先頭')

        # 補充があった場合は pending_ai.json も更新して次回スケジュール実行で再走査させる
        if S3_BUCKET and visible_tids:
            try:
                merged_ids = [it.get('topicId') for it in items if it.get('topicId')]
                if merged_ids and len(merged_ids) != len(pending_ids):
                    s3.put_object(
                        Bucket=S3_BUCKET, Key='api/pending_ai.json',
                        Body=json.dumps({'topicIds': merged_ids}),
                        ContentType='application/json',
                    )
                    print(f'[get_pending_topics] pending_ai.json 更新: {len(pending_ids)} → {len(merged_ids)}件')
            except Exception as e:
                print(f'[get_pending_topics] pending_ai.json 更新失敗: {e}')

        return items[:max_topics]

    # フォールバック: DynamoDBスキャン
    # pending_ai.json が空 or 未作成のとき、処理必要なトピックを全スキャンして pending_ai.json を再生成
    print('get_pending_topics: pending_ai.json空のためDynamoDBフルスキャン（storyTimeline欠如含む）')
    proj = 'topicId,title,articleCount,score,velocityScore,lastUpdated,generatedTitle,generatedSummary,storyTimeline,storyPhase,aiGenerated,aiGeneratedAt,pendingAI,imageUrl,genre,genres,keyPoint,statusLabel,watchPoints,schemaVersion'
    filt = (
        Attr('SK').eq('META') & (
            Attr('pendingAI').eq(True) |
            Attr('aiGenerated').ne(True) |
            ~Attr('storyTimeline').exists() |
            ~Attr('storyPhase').exists() |
            ~Attr('imageUrl').exists() |
            ~Attr('schemaVersion').exists() |
            Attr('schemaVersion').lt(PROCESSOR_SCHEMA_VERSION)
        )
    )
    items, kwargs = [], {
        'FilterExpression': filt,
        'ProjectionExpression': proj,
    }
    while True:
        r = table.scan(**kwargs)
        items.extend(r.get('Items', []))
        if not r.get('LastEvaluatedKey'): break
        kwargs['ExclusiveStartKey'] = r['LastEvaluatedKey']

    items = [it for it in items if needs_ai_processing(it)]

    def _ts(s):
        try:
            return datetime.fromisoformat((s or '').replace('Z', '+00:00')).timestamp()
        except Exception:
            return 0.0

    def _scan_sort_key(x):
        tid = x.get('topicId', '')
        is_visible = tid in visible_tids
        if is_visible and not x.get('aiGenerated'):
            priority = 0
        elif x.get('pendingAI'):
            priority = 1
        elif not x.get('aiGenerated'):
            priority = 2
        else:
            priority = 3
        return (priority, -int(x.get('score', 0) or 0), -_ts(x.get('lastUpdated', '')))

    items.sort(key=_scan_sort_key)
    # T2026-0428-O: フルスキャン経路でも Tier-0 (articles>=10 × aiGenerated=False) を全件先頭固定
    items = _apply_tier0_budget(items)

    # 発見したIDをpending_ai.jsonに保存して次回スキャンを省略
    if S3_BUCKET and items:
        try:
            new_ids = [it['topicId'] for it in items]
            s3.put_object(
                Bucket=S3_BUCKET, Key='api/pending_ai.json',
                Body=json.dumps({'topicIds': new_ids}),
                ContentType='application/json',
            )
            print(f'[get_pending_topics] DynamoDBフルスキャン完了: {len(items)}件 → pending_ai.json 再生成')
        except Exception as e:
            print(f'[get_pending_topics] pending_ai.json 再生成失敗: {e}')

    return items[:max_topics]


def get_topics_by_ids(topic_ids):
    """指定IDのトピックをDynamoDBから直接取得し、AI処理が必要なものを返す。fetcher_trigger専用。

    2026-04-29: keyPoint/schemaVersion/statusLabel/watchPoints を Projection に追加。
    needs_ai_processing が参照する全フィールドを取得しないと、Projection 欠落で None 扱いに
    なり判定がブレる。get_pending_topics 経路と挙動を揃える。

    2026-04-29: ゴーストID（DDB に存在しない topic_id）の件数をログに出す。
    fetcher_trigger 経路で「N件指定 → 0件処理対象」となる主因がゴーストID であることを
    実測で特定するため（pending_ai.json 経路は line 538 で自動クリーンアップ済みだが、
    fetcher_trigger 経路は fetcher が直接 IDs を渡すため別途観測が必要）。
    """
    proj = ('topicId,title,articleCount,score,velocityScore,lastUpdated,generatedTitle,'
            'generatedSummary,storyTimeline,storyPhase,aiGenerated,aiGeneratedAt,pendingAI,'
            'imageUrl,genre,genres,keyPoint,schemaVersion,statusLabel,watchPoints,summaryMode')
    items = []
    ghost_ids = []
    skipped_ids = []  # 存在するが needs_ai_processing が False
    for tid in topic_ids:
        try:
            r = table.get_item(
                Key={'topicId': tid, 'SK': 'META'},
                ProjectionExpression=proj,
            )
            item = r.get('Item')
            if not item:
                ghost_ids.append(tid)
                continue
            if needs_ai_processing(item):
                items.append(item)
            else:
                skipped_ids.append(tid)
        except Exception as e:
            print(f'get_topics_by_ids error [{tid}]: {e}')
    if ghost_ids:
        print(f'[get_topics_by_ids] ゴーストID検知: {len(ghost_ids)}件 / 全{len(topic_ids)}件 '
              f'(DDB に存在しない). サンプル: {ghost_ids[:5]}')
    if skipped_ids:
        print(f'[get_topics_by_ids] needs_ai_processing=False で skip: {len(skipped_ids)}件 '
              f'(処理済 or articleCount<2). サンプル: {skipped_ids[:5]}')
    items.sort(key=lambda x: (
        0 if x.get('pendingAI') else (1 if not x.get('aiGenerated') else 2),
        -float(x.get('velocityScore', 0) or 0),
        -int(x.get('score', 0) or 0),
    ))
    return items


def update_prediction_result(tid: str, result: str, evidence: str = '') -> bool:
    """T2026-0428-PRED: AI 予想 (outlook) の自動当否判定結果を DynamoDB META に書き戻す。

    Args:
        tid:      トピック ID
        result:   'matched' | 'partial' | 'missed' | 'pending'
        evidence: 判定根拠 (200 字以内)

    書き込みフィールド:
        - predictionResult:    判定結果 (matched/partial/missed/pending)
        - predictionVerifiedAt: 判定実行時刻 (ISO8601 UTC)
        - predictionEvidence:  判定根拠 (短文)

    判定後も outlook / predictionMadeAt は維持する (どの予想がいつ立ったかは履歴として保持)。
    新しい outlook が立つと proc_storage.update_topic_with_ai 側で predictionResult が
    'pending' に再リセットされる (既存実装)。
    """
    if result not in ('matched', 'partial', 'missed', 'pending'):
        print(f'[update_prediction_result] invalid result={result} for {tid[:8]}...')
        return False
    try:
        ts_iso = datetime.now(timezone.utc).isoformat()
        update_expr = 'SET predictionResult = :r, predictionVerifiedAt = :v'
        expr_values = {':r': result, ':v': ts_iso}
        if evidence:
            update_expr += ', predictionEvidence = :e'
            expr_values[':e'] = str(evidence)[:200]
        table.update_item(
            Key={'topicId': tid, 'SK': 'META'},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
        )
        return True
    except Exception as e:
        print(f'[update_prediction_result] {tid[:8]}... 失敗: {e}')
        return False


def get_topics_for_prediction_judging(min_age_days: int = 1, min_articles: int = 3,
                                      max_topics: int = 20) -> list:
    """T2026-0428-PRED: 当否判定対象のトピックを抽出する。

    T2026-0428-E2-4 (2026-04-28): default を 7d/5art → 1d/3art に緩和。
    根本原因 (実測): システム内 outlook の最大経過 2.12 日のため 7 日では永遠に 0 件。
    データが熟したら段階的に 3d/5art へ戻すこと。

    条件:
        - SK == 'META'
        - outlook が非空
        - predictionMadeAt が min_age_days 日以上前
        - articleCount >= min_articles
        - predictionResult == 'pending' (まだ判定済みでない)

    判定済み (matched/partial/missed) は再判定しない。新 outlook が立つと
    update_topic_with_ai 側で predictionResult が 'pending' に再リセットされ、
    再度この query で拾われる (履歴的には predictionVerifiedAt も上書きされるため
    同一 outlook の判定揺らぎは観測できないが、当否ログを別 SK に積む拡張は将来検討)。

    Returns: [{'topicId', 'outlook', 'predictionMadeAt', 'articleCount', ...}, ...]
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=min_age_days)
    cutoff_iso = cutoff.isoformat()
    candidates = []
    try:
        scan_kwargs = {
            'FilterExpression': (
                Attr('SK').eq('META')
                & Attr('outlook').exists()
                & Attr('predictionMadeAt').lt(cutoff_iso)
                & Attr('articleCount').gte(min_articles)
                & Attr('predictionResult').eq('pending')
            ),
            'ProjectionExpression': 'topicId, outlook, predictionMadeAt, articleCount, generatedTitle',
        }
        while True:
            r = table.scan(**scan_kwargs)
            for item in r.get('Items', []):
                candidates.append({
                    'topicId':          item.get('topicId'),
                    'outlook':          str(item.get('outlook') or ''),
                    'predictionMadeAt': str(item.get('predictionMadeAt') or ''),
                    'articleCount':     int(item.get('articleCount', 0) or 0),
                    'generatedTitle':   str(item.get('generatedTitle') or ''),
                })
                if len(candidates) >= max_topics:
                    return candidates
            if not r.get('LastEvaluatedKey'):
                break
            scan_kwargs['ExclusiveStartKey'] = r['LastEvaluatedKey']
    except Exception as e:
        print(f'[get_topics_for_prediction_judging] scan 失敗: {e}')
    return candidates


def get_articles_added_after(tid: str, since_iso: str, max_articles: int = 30) -> list:
    """T2026-0428-PRED: 指定時刻以降にトピックに追加された記事 (タイトルのみ) を返す。

    SNAP に含まれる pubDate を since_iso と比較する。pubDate パースに失敗した記事は除外。
    新しい順に最大 max_articles 件返す。
    """
    try:
        since_dt = datetime.fromisoformat(since_iso.replace('Z', '+00:00'))
    except Exception:
        # parse 失敗時は全 SNAP 対象 (= since=過去) として扱う
        since_dt = datetime.fromtimestamp(0, tz=timezone.utc)
    try:
        r = table.query(
            KeyConditionExpression=Key('topicId').eq(tid) & Key('SK').begins_with('SNAP#'),
            ScanIndexForward=False,
            Limit=10,
        )
        seen_urls = set()
        out = []
        for item in r.get('Items', []):
            for a in item.get('articles', []):
                url = a.get('url', '')
                if url in seen_urls:
                    continue
                # pubDate 比較 (T2026-0428-E2-4: RFC 2822 / ISO 8601 / epoch すべて対応。
                # 旧実装は ISO/epoch のみ対応で、RSS 由来の RFC 2822 ('Mon, 23 Mar 2026 07:00:00')
                # は silently drop され、judge_prediction が永遠に new_titles=0 で skip していた)
                raw = a.get('pubDate', '') or a.get('publishedAt', '')
                a_dt = _parse_pubdate(raw) if raw else None
                if a_dt is None:
                    continue
                if a_dt < since_dt:
                    continue
                seen_urls.add(url)
                out.append({'title': a.get('title', ''), 'pubDate': raw, 'url': url})
                if len(out) >= max_articles:
                    return out
        return out
    except Exception as e:
        print(f'[get_articles_added_after] {tid[:8]}... 失敗: {e}')
        return []


def get_latest_articles_for_topic(tid):
    """最新SNAPを優先しつつ過去スナップも合わせて最大20件の記事を返す（重複排除済み）。"""
    try:
        r = table.query(
            KeyConditionExpression=Key('topicId').eq(tid) & Key('SK').begins_with('SNAP#'),
            ScanIndexForward=False,
            Limit=5,
        )
        seen_urls = set()
        articles = []
        for item in r.get('Items', []):
            for a in item.get('articles', []):
                url = a.get('url', '')
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    articles.append(a)
                    if len(articles) >= 20:
                        return articles
        return articles
    except Exception as e:
        print(f'get_latest_articles_for_topic error [{tid}]: {e}')
    return []


def _is_field_empty(v):
    """T2026-0428-AO: 既存フィールドが「空」かどうかを判定する。
    None / 空文字 / whitespace のみ / 空 list / 空 dict を空として扱う。
    incremental ヒール時に「既に値があるフィールドは上書きしない」判定で使う。"""
    if v is None:
        return True
    if isinstance(v, str) and not v.strip():
        return True
    if isinstance(v, (list, dict)) and len(v) == 0:
        return True
    return False


# T2026-0428-BH: keyPoint は schema 上 200〜300 字の物語形式を要求するが、
# 過去 (2026-04-26〜27) に Tool Use API が短いタイトル風 (20〜50 字) を返した、
# あるいは fallback が記事見出しを書き込んだ結果、aiGenerated=True かつ keyPoint が
# 著しく短いレコードが本番に滞留していた (96/107 = 89.7% 平均 43.8 字)。
# 100 字未満は schema 要件を明確に満たさないため「不十分 = 空扱い」と判定し、
# incremental ヒールでの上書き許可および needs_ai_processing 再処理対象化に使う。
# 100 字閾値の根拠: 100-200 字は実測 1 件のみ、50-100 字は 4 件、< 50 字は 91 件
# (2026-04-28 22:30 JST 実測)。100 字で 89.7% を救済しつつ正常生成を巻き込まない。
KEYPOINT_MIN_LENGTH = 100


def _is_keypoint_inadequate(v) -> bool:
    """keyPoint が空 or 著しく短い (100 字未満) を不十分と判定。
    incremental ヒールの上書き許可および再処理キュー投入の判定で使う。"""
    if _is_field_empty(v):
        return True
    if isinstance(v, str) and len(v.strip()) < KEYPOINT_MIN_LENGTH:
        return True
    return False


def update_topic_with_ai(tid, gen_title, gen_story, ai_succeeded=False, image_url=None, existing_meta=None):
    """Claude 生成タイトル・ストーリーで DynamoDB META を更新。

    Args:
        tid:          トピックID
        gen_title:    str | None — 生成タイトル
        gen_story:    dict | None — {aiSummary, spreadReason, forecast, timeline, phase}
        ai_succeeded: bool — Claude が実際に成功したか（False なら aiGenerated は立てない）
        image_url:    str | None — 生成したOGP画像URL（既にimageUrlがあれば上書きしない）
        existing_meta: dict | None — DynamoDB から読んだ既存 META (incremental モード判定用)。
                       T2026-0428-AO: 既に値が入っているフィールドは上書きしない (heal/再処理時保護)。
                       None のときは「初回処理」扱いで全フィールドを書き込む。

    T2026-0428-AO 重要原則:
        ヒール・schema_version 上昇による再処理では、既存 AI フィールドを絶対に上書きしない。
        incremental モード = existing_meta が渡され、既存フィールドが空でない場合は SKIP する。
        → 過去に蓄積した良い要約が消える事故を防ぐ物理ゲート。
    """
    incremental = existing_meta is not None
    def _can_write(field):
        """incremental モードでは既存値が空のときだけ書ける。full モードでは常に書ける。
        T2026-0428-BH: keyPoint は 100 字未満を「不十分」と扱い、上書きを許可する
        (schema 200〜300 字要件を満たさない過去データを再生成で上書きできるようにする)。"""
        if not incremental:
            return True
        if field == 'keyPoint':
            return _is_keypoint_inadequate(existing_meta.get(field))
        return _is_field_empty(existing_meta.get(field))

    try:
        # aiGenerated は Claude が実際に成功した時だけ True にする
        # 失敗時に True にしてしまうと次回実行でスキップされてしまう（再発防止）
        update_expr = 'SET pendingAI = :f'
        expr_values = {':f': False}
        if ai_succeeded:
            update_expr += ', aiGenerated = :t'
            expr_values[':t'] = True
            # T2026-0428-AO: AI成功時のみ schemaVersion を最新版で記録。
            # 失敗時に書くと再処理対象から外れるため、ai_succeeded ガードと同じ条件にする。
            # schemaVersion は制御フィールドなので incremental モードでも常に更新する。
            update_expr += ', schemaVersion = :sv'
            expr_values[':sv'] = PROCESSOR_SCHEMA_VERSION
            # 2026-04-29 案C: AI 生成時刻を記録。「48h 以内 + 新記事 0 件」スキップ判定用。
            # 制御フィールドのため incremental でも常に最新で更新する。
            update_expr += ', aiGeneratedAt = :agat'
            expr_values[':agat'] = datetime.now(timezone.utc).isoformat()
        if gen_title and _can_write('generatedTitle'):
            update_expr += ', generatedTitle = :title'
            expr_values[':title'] = _strip_title_markdown(gen_title)
        if gen_story:
            if gen_story.get('aiSummary') and _can_write('generatedSummary'):
                update_expr += ', generatedSummary = :summary'
                expr_values[':summary'] = gen_story['aiSummary']
            if gen_story.get('keyPoint') and _can_write('keyPoint'):
                update_expr += ', keyPoint = :kp'
                expr_values[':kp'] = gen_story['keyPoint']
                # T2026-0430-A: 品質メトリクスを永続化。後で集計・分析に使う。
                # keyPoint と同時に書く (keyPoint が更新されないなら品質メタも古いままで OK)。
                update_expr += ', keyPointLength = :kpLen, keyPointRetried = :kpRet, keyPointFallback = :kpFb'
                expr_values[':kpLen'] = int(gen_story.get('keyPointLength') or len(gen_story['keyPoint']))
                expr_values[':kpRet'] = bool(gen_story.get('keyPointRetried', False))
                expr_values[':kpFb']  = bool(gen_story.get('keyPointFallback', False))
            # T2026-0428-J/E: 新フィールド statusLabel / watchPoints を永続化
            if gen_story.get('statusLabel') and _can_write('statusLabel'):
                update_expr += ', statusLabel = :sl'
                expr_values[':sl'] = gen_story['statusLabel']
            if gen_story.get('watchPoints') and _can_write('watchPoints'):
                update_expr += ', watchPoints = :wp'
                expr_values[':wp'] = gen_story['watchPoints']
            if gen_story.get('forecast') and _can_write('forecast'):
                update_expr += ', forecast = :fc'
                expr_values[':fc'] = gen_story['forecast']
            if gen_story.get('timeline') is not None and _can_write('storyTimeline'):
                update_expr += ', storyTimeline = :timeline'
                expr_values[':timeline'] = gen_story['timeline']
            if gen_story.get('phase') and _can_write('storyPhase'):
                update_expr += ', storyPhase = :phase'
                expr_values[':phase'] = gen_story['phase']
            if gen_story.get('summaryMode') and _can_write('summaryMode'):
                update_expr += ', summaryMode = :smode'
                expr_values[':smode'] = gen_story['summaryMode']
            if gen_story.get('backgroundContext') and _can_write('backgroundContext'):
                update_expr += ', backgroundContext = :bgctx'
                expr_values[':bgctx'] = gen_story['backgroundContext']
            if gen_story.get('background'):
                if _can_write('background'):
                    update_expr += ', background = :bg'
                    expr_values[':bg'] = gen_story['background']
            else:
                # 空フィールド検出を CloudWatch で観測可能にする (T35 prompt 改善の効果計測)
                print(f"[AI_FIELD_GAP] background empty topic={tid}")
            if gen_story.get('perspectives') is not None and str(gen_story.get('perspectives', '')).strip():
                if _can_write('perspectives'):
                    update_expr += ', perspectives = :persp'
                    expr_values[':persp'] = gen_story['perspectives']
            else:
                print(f"[AI_FIELD_GAP] perspectives null/empty topic={tid}")
            if gen_story.get('outlook'):
                # outlook の書き込み可否で predictionMadeAt/predictionResult もまとめて判定。
                # outlook が新規に書かれる場合のみ予測タイムスタンプを更新する。
                if _can_write('outlook'):
                    update_expr += ', outlook = :otlk'
                    expr_values[':otlk'] = gen_story['outlook']
                    # T2026-0428-J/E: outlook を AI 予想として記録した時刻 (後で当否判定する基準)。
                    update_expr += ', predictionMadeAt = :pma'
                    expr_values[':pma'] = datetime.now(timezone.utc).isoformat()
                    # 新しい予想が立つ度に判定状態をリセット (前回の判定結果は predictionHistory として別 SK に積む想定)。
                    update_expr += ', predictionResult = :prs'
                    expr_values[':prs'] = 'pending'
            else:
                print(f"[AI_FIELD_GAP] outlook empty topic={tid}")
            if gen_story.get('topicTitle') and _can_write('topicTitle'):
                update_expr += ', topicTitle = :ttitle'
                expr_values[':ttitle'] = gen_story['topicTitle']
            if gen_story.get('latestUpdateHeadline') and _can_write('latestUpdateHeadline'):
                update_expr += ', latestUpdateHeadline = :luh'
                expr_values[':luh'] = gen_story['latestUpdateHeadline']
            if 'isCoherent' in gen_story and _can_write('topicCoherent'):
                update_expr += ', topicCoherent = :coherent'
                expr_values[':coherent'] = bool(gen_story['isCoherent'])
            if gen_story.get('topicLevel') and _can_write('topicLevel'):
                update_expr += ', topicLevel = :tlevel'
                expr_values[':tlevel'] = gen_story['topicLevel']
            if gen_story.get('parentTopicTitle') and _can_write('parentTopicTitle'):
                update_expr += ', parentTopicTitle = :ptt'
                expr_values[':ptt'] = gen_story['parentTopicTitle']
            if 'relatedTopicTitles' in gen_story and _can_write('relatedTopicTitles'):
                update_expr += ', relatedTopicTitles = :rtt'
                expr_values[':rtt'] = gen_story.get('relatedTopicTitles') or []
        if gen_story and gen_story.get('genres'):
            # genre/genres は incremental モードで保護 (誤分類しても既存を尊重)
            if _can_write('genres') and _can_write('genre'):
                ai_genres = gen_story['genres']
                update_expr += ', genres = :genres, genre = :genre'
                expr_values[':genres'] = ai_genres
                expr_values[':genre']  = ai_genres[0]
        if image_url:
            # if_not_exists: 既にRSS由来画像があれば上書きしない
            update_expr += ', imageUrl = if_not_exists(imageUrl, :img)'
            expr_values[':img'] = image_url
        if incremental:
            print(f'[update_topic_with_ai] tid={tid[:8]}... incremental mode (既存フィールド保持)')
        table.update_item(
            Key={'topicId': tid, 'SK': 'META'},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
        )
    except Exception as e:
        print(f'update_topic_with_ai error [{tid}]: {e}')


def _is_ticker_topic(t):
    title = t.get('generatedTitle') or t.get('title') or ''
    return bool(_TICKER_RE.search(title))


def _dedup_topics(items):
    """generatedTitle（またはtitle）の正規化比較で重複トピックを除去し、スコア上位を残す。"""
    def _norm(t):
        s = (t.get('generatedTitle') or t.get('title', '')).lower()
        s = re.sub(r'[「」【】・、。,!?！？\[\]()（）\s　]+', '', s)
        return s[:18]
    seen = {}
    for t in items:
        key = _norm(t)
        if key not in seen or int(t.get('score', 0) or 0) > int(seen[key].get('score', 0) or 0):
            seen[key] = t
    return list(seen.values())


def _cap_topics(items):
    filtered = [t for t in items if not _is_ticker_topic(t)]
    filtered = _dedup_topics(filtered)
    filtered.sort(key=lambda x: int(x.get('score', 0) or 0), reverse=True)
    return filtered[:TOPICS_S3_CAP]


_BACKFILL_AI_FIELDS = (
    'keyPoint', 'statusLabel', 'watchPoints', 'outlook', 'topicTitle',
    'latestUpdateHeadline', 'topicLevel', 'parentTopicTitle', 'relatedTopicTitles',
    'topicCoherent', 'perspectives', 'storyPhase', 'summaryMode',
)


def _backfill_ai_fields_from_ddb(items):
    """T2026-0428-J/M: 既存 topics.json に欠落している AI フィールドを DynamoDB から補填する。

    背景: get_all_topics_for_s3 は S3 の topics.json を source of truth にしていた。
          後から DDB へ書かれた keyPoint/statusLabel/watchPoints 等は永久に
          published JSON へ反映されず、新規処理サイクルでも上書きされなかった
          (本番 keyPoint 充填率 26% の根本原因)。

    対策: S3 から読んだ items を返す前に、AI フィールドのうち空のものを
          DDB BatchGetItem で取得して overlay する。AI 再生成は不要。
          DDB が source of truth なので、過去に蓄積した値が即座に publish される。

    観測: BatchGetItem 100件/req、トピック ~100 件で 1 リクエスト ($0.0001) 程度。
          コストは無視できる (T2026-0428-AO の S3 コスト最適化を損なわない)。
    """
    if not items:
        return items
    needs_backfill = []
    for t in items:
        if any(_is_field_empty(t.get(f)) for f in _BACKFILL_AI_FIELDS):
            tid = t.get('topicId')
            if tid:
                needs_backfill.append(tid)
    if not needs_backfill:
        return items
    fetched = {}
    for i in range(0, len(needs_backfill), 100):
        chunk = needs_backfill[i:i + 100]
        keys = [{'topicId': tid, 'SK': 'META'} for tid in chunk]
        try:
            resp = dynamodb.batch_get_item(
                RequestItems={
                    table.name: {
                        'Keys': keys,
                        'ProjectionExpression': 'topicId,' + ','.join(_BACKFILL_AI_FIELDS),
                    }
                }
            )
            for it in resp.get('Responses', {}).get(table.name, []):
                tid = it.get('topicId')
                if tid:
                    fetched[tid] = it
        except Exception as e:
            print(f'[backfill_ai] batch_get_item 失敗: {e}')
    backfilled = 0
    for t in items:
        ddb_item = fetched.get(t.get('topicId'))
        if not ddb_item:
            continue
        for f in _BACKFILL_AI_FIELDS:
            if _is_field_empty(t.get(f)) and not _is_field_empty(ddb_item.get(f)):
                t[f] = ddb_item[f]
                if f == 'keyPoint':
                    backfilled += 1
    if backfilled:
        print(f'[backfill_ai] DDB→topics.json keyPoint 補填: {backfilled}件')
    return items


def _drop_ghost_topics(items):
    """T2026-0429-H: DDB に META が存在しない (= articleCount/lastUpdated が無い) topic を除去。
    fetcher 側の旧 batch_writer 並列書き込みで silently drop された topicId が
    topics.json に永続滞留し、processor が「ゴーストID検知 N件全件」で keyPoint 生成を
    永久に skip していた事象 (本番 7件/run) を解消する。
    """
    if not items:
        return items
    valid_ids = set()
    for i in range(0, len(items), 100):
        chunk = items[i:i + 100]
        keys = [{'topicId': t['topicId'], 'SK': 'META'} for t in chunk if t.get('topicId')]
        if not keys:
            continue
        try:
            resp = dynamodb.batch_get_item(
                RequestItems={
                    table.name: {
                        'Keys': keys,
                        'ProjectionExpression': 'topicId, articleCount, lastUpdated',
                        'ConsistentRead': True,
                    }
                }
            )
            for it in resp.get('Responses', {}).get(table.name, []):
                if 'articleCount' in it and 'lastUpdated' in it:
                    valid_ids.add(it.get('topicId'))
        except Exception as e:
            print(f'[drop_ghost] batch_get_item 失敗 (chunk {i}): {e}')
            # エラー時は chunk 全件 valid にフォールバック (publish blocking を避ける)
            for t in chunk:
                if t.get('topicId'):
                    valid_ids.add(t['topicId'])
    pre = len(items)
    cleaned = [t for t in items if t.get('topicId') in valid_ids]
    dropped = pre - len(cleaned)
    if dropped:
        print(f'[drop_ghost] DDB 不在の幽霊 topic を除去: {dropped}件 / pre={pre} → post={len(cleaned)}')
    return cleaned


def get_all_topics_for_s3():
    """S3のtopics.jsonから読み、欠落 AI フィールドを DynamoDB から backfill する。
    TOPICS_S3_CAP件にキャップ。trendingKeywordsはトピックタイトルから毎回新規生成する。"""
    if S3_BUCKET:
        try:
            resp = s3.get_object(Bucket=S3_BUCKET, Key='api/topics.json')
            data = json.loads(resp['Body'].read())
            items = data.get('topics', [])
            if items:
                items = _drop_ghost_topics(items)
                items = _backfill_ai_fields_from_ddb(items)
                capped = _cap_topics(items)
                return capped, _extract_trending_keywords(capped)
        except Exception as e:
            print(f'get_all_topics_for_s3 S3 error: {e}')
    items, kwargs = [], {
        'FilterExpression': 'SK = :m',
        'ExpressionAttributeValues': {':m': 'META'},
    }
    while True:
        r = table.scan(**kwargs)
        items.extend(r.get('Items', []))
        if not r.get('LastEvaluatedKey'): break
        kwargs['ExclusiveStartKey'] = r['LastEvaluatedKey']
    capped = _cap_topics(items)
    return capped, _extract_trending_keywords(capped)


def dec_convert(obj):
    if isinstance(obj, Decimal):
        return int(obj) if obj == obj.to_integral_value() else float(obj)
    raise TypeError


def write_s3(key, data):
    if not S3_BUCKET:
        return
    # 個別トピック JSON は更新頻度が高いため CloudFront に長く保持されないよう短い max-age を設定。
    # Cache-Control は CloudFront 既定 TTL より優先される (Origin Cache-Control 尊重設定の場合)。
    if key.startswith('api/topic/') and key.endswith('.json'):
        cache_control = 'max-age=30, must-revalidate'
    elif key in ('api/topics.json', 'api/topics-full.json', 'api/topics-card.json'):
        # T2026-0428-F: topics-full.json は topics.json の互換 alias、
        # topics-card.json は一覧用 minimal payload。Cache-Control は同じ。
        cache_control = 'max-age=60, must-revalidate'
    else:
        cache_control = 'max-age=60'
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=json.dumps(data, default=dec_convert, ensure_ascii=False).encode('utf-8'),
        ContentType='application/json',
        CacheControl=cache_control,
    )


# T265: 一覧ページ用に topics.json から最小フィールドだけ抽出した payload を返す。
# topics.json は AI 生成 long-text (perspectives / watchPoints / outlook 等) を含み 200KB+ に
# 肥大化していた → モバイル初回表示の帯域コストが高い。card 表示で実際に参照する短いフィールド
# だけ残すことで payload を半分以下に圧縮する (Step2: frontend は topics-card.json を一覧用に使う)。
#
# 含めるフィールドの基準:
#   - topic card で表示・分岐に使う ID, タイトル, ジャンル, スコア, 日時, 状態, badge 系
#   - keyPoint / latestUpdateHeadline は短く card 上で読まれるので含む
# 除外するフィールド (api/topic/{tid}.json 側で参照する):
#   - generatedSummary, perspectives, watchPoints, outlook,
#     predictionMadeAt, predictionResult, parentTopicTitle, relatedTopicTitles, trendsData
_CARD_INCLUDE_KEYS = (
    # 基本識別
    'topicId', 'topicTitle', 'generatedTitle', 'title',
    # 分類・サムネ
    'genres', 'genre', 'imageUrl',
    # スコア・カウント (card meta 行)
    'score', 'articleCount', 'articleCountDelta', 'hatenaCount', 'velocityScore',
    # 日時 (NEW badge / cooling-age / 並び替え)
    'lastArticleAt', 'lastUpdated', 'firstSeenAt', 'updatedAt',
    # ステータス (badge / フィルター)
    'status', 'lifecycleStatus', 'storyPhase', 'statusLabel', 'summaryMode',
    # card 上で読まれる短い AI テキスト
    'keyPoint', 'latestUpdateHeadline',
    # 制御フラグ
    'aiGenerated', 'topicCoherent', 'topicLevel', 'reliability',
    # 親子トピック (分岐 bar)
    'parentTopicId', 'childTopics',
)


def normalize_minimal_phase(item: dict) -> dict:
    """T2026-0429-G: minimal regime (articleCount<=2 or summaryMode=='minimal') の topic は
    storyPhase 概念が薄いため、レガシー値が残っていれば None に正規化して返す。

    背景:
      T219 (2026-04-28) で minimal mode の AI 出力を phase=None に変更したが、
      それ以前に「発端」固定で書き込まれた DDB 既存レコードが永続化していた。
      AI 再生成は articleCount>=3 になるまで走らないため、ac=2 のままの 49 件が
      「発端」のまま放置される構造（本番計測 2026-04-30: 全 126 件中 53/126=42.1%
      が「発端」、うち 49 件が ac=2 + summaryMode=minimal）。

    本関数は読み出しパス (S3 出力) で legacy 値を物理的に剥がす:
      - articleCount <= 2 OR summaryMode == 'minimal' なら storyPhase=None
      - それ以外 (articleCount>=3 の standard/full) は AI が正しい phase を保持

    DDB 直接書き換えは避け、表示用 JSON 上だけで吸収する (idempotent・コスト 0)。
    新記事到来で articleCount>=3 になれば既存の AI 再生成パスが正しい phase を上書きする。

    Args:
        item: topic dict (in-place 変更しない、コピーを返す)
    Returns:
        正規化済み dict (storyPhase が legacy minimal なら None に置換)
    """
    if not isinstance(item, dict):
        return item
    summary_mode = item.get('summaryMode')
    try:
        ac = int(item.get('articleCount', 0) or 0)
    except (TypeError, ValueError):
        ac = 0
    is_minimal_regime = (summary_mode == 'minimal') or (ac <= 2)
    if is_minimal_regime and item.get('storyPhase'):
        out = dict(item)
        out['storyPhase'] = None
        return out
    return item


def generate_topics_card_json(topics_pub: list, updated_at: str) -> dict:
    """topics_pub (= _trim 済みの公開用 topics) から card 表示に必要な最小フィールドのみを
    抽出した payload dict を返す (api/topics-card.json の中身)。

    T2026-0429-G: card 化する前に normalize_minimal_phase でレガシー minimal storyPhase
    を剥がす。card payload の方が SLI 計測対象なので、ここで吸収するのが最も効率的。

    Args:
        topics_pub: handler.py で _PROC_INTERNAL を除外した公開用 topics の list
        updated_at: ISO8601 タイムスタンプ
    Returns:
        {'topics': [...], 'updatedAt': str, 'count': int}
    """
    normalized = [normalize_minimal_phase(t) for t in topics_pub]
    cards = [{k: t[k] for k in _CARD_INCLUDE_KEYS if k in t} for t in normalized]
    return {
        'topics':    cards,
        'updatedAt': updated_at,
        'count':     len(cards),
    }


def generate_health_json(topics: list, updated_at: str) -> dict:
    """本番監視用ヘルスJSON生成。

    aiGenerated 件数に対する keyPoint 充填率と空トピック件数を算出し、
    閾値を下回れば status='degraded' を返す。check_health.sh が curl で取得して可視化する。
    """
    total = len(topics)
    ai_gen = sum(1 for t in topics if t.get('aiGenerated'))
    key_point = sum(1 for t in topics if t.get('keyPoint'))
    zero_articles = sum(1 for t in topics if t.get('articleCount', 0) == 0)

    return {
        'generatedAt':       updated_at,
        'topicCount':        total,
        'aiGeneratedCount':  ai_gen,
        'keyPointCount':     key_point,
        'keyPointRate':      round(key_point / ai_gen * 100, 1) if ai_gen > 0 else 0,
        'zeroArticleCount':  zero_articles,
        'status':            'ok' if zero_articles == 0 and (key_point / ai_gen > 0.5 if ai_gen > 0 else True) else 'degraded',
    }


def update_topic_s3_file(tid, upd, articles=None, incremental=False):
    """個別トピックS3ファイルのmetaにAIフィールドをマージ（pendingAI解除含む）。
    articles が渡された場合は静的SEO用HTMLも生成する。
    ETag(MD5)比較で内容変更がない場合はPUTをスキップしてコスト削減。

    Args:
        incremental: True のとき、既存 meta にすでに値がある AI フィールドは上書きしない
                     (T2026-0428-AO: ヒール/再処理で蓄積した良いデータを保護)。
                     False (初回処理) のときは従来どおり全フィールドを上書きする。
    """
    if not S3_BUCKET:
        return
    key = f'api/topic/{tid}.json'
    try:
        resp = s3.get_object(Bucket=S3_BUCKET, Key=key)
        old_etag = resp.get('ETag', '')
        raw = resp['Body'].read()
        data = json.loads(raw)

        # Fix A1 (T256, 2026-04-28): 2026-04-27以前に作成された SNAP は articles=[] だった。
        # 既存 timeline に SNAP は存在するが全エントリで articles が空の場合、
        # DynamoDB から最新 SNAP を再取得して timeline を再構築する。
        # update_topic_s3_file は meta のみ更新していたため topic JSON の timeline が
        # 永久に古いまま放置される構造バグを根本修正する。
        _current_tl = data.get('timeline', [])
        if _current_tl and all(not _s.get('articles') for _s in _current_tl):
            try:
                _snaps_resp = table.query(
                    KeyConditionExpression=Key('topicId').eq(tid) & Key('SK').begins_with('SNAP#'),
                    ScanIndexForward=False, Limit=30,
                )
                _fresh = sorted(_snaps_resp.get('Items', []), key=lambda x: x['SK'])
                if any(_s.get('articles') for _s in _fresh):
                    data['timeline'] = [
                        {'timestamp': _s['timestamp'], 'articleCount': _s['articleCount'],
                         'score': _s.get('score', 0), 'hatenaCount': _s.get('hatenaCount', 0),
                         'articles': _s.get('articles', [])}
                        for _s in _fresh
                    ]
                    print(f'[TIMELINE_REFRESH] tid={tid} snaps={len(data["timeline"])}件 articles再取得完了')
            except Exception as _te:
                print(f'[TIMELINE_REFRESH] tid={tid} SNAP再取得失敗: {_te}')

        meta = data.get('meta', {})
        meta.pop('pendingAI', None)
        # T2026-0428-AO: incremental モードでは既存値があるフィールドを上書きしない (heal保護)
        # T2026-0428-BH: keyPoint は 100 字未満を「不十分」扱い (上書き許可)
        def _can_set(field):
            if not incremental:
                return True
            if field == 'keyPoint':
                return _is_keypoint_inadequate(meta.get(field))
            return _is_field_empty(meta.get(field))

        if upd.get('generatedTitle') and _can_set('generatedTitle'):
            meta['generatedTitle'] = _strip_title_markdown(upd['generatedTitle'])
        if upd.get('generatedSummary') and _can_set('generatedSummary'):
            meta['generatedSummary'] = upd['generatedSummary']
        if upd.get('keyPoint') and _can_set('keyPoint'):
            meta['keyPoint'] = upd['keyPoint']
        # T2026-0428-J/E: 新フィールド statusLabel / watchPoints / predictionMadeAt / predictionResult を merge
        if upd.get('statusLabel') and _can_set('statusLabel'):
            meta['statusLabel'] = upd['statusLabel']
        if upd.get('watchPoints') and _can_set('watchPoints'):
            meta['watchPoints'] = upd['watchPoints']
        # predictionMadeAt/predictionResult は outlook の書き込みに紐付ける
        # (incremental で outlook 既存なら timing も更新しない)
        if upd.get('outlook') and _can_set('outlook'):
            meta['outlook'] = upd['outlook']
            if upd.get('predictionMadeAt'):
                meta['predictionMadeAt'] = upd['predictionMadeAt']
            if upd.get('predictionResult'):
                meta['predictionResult'] = upd['predictionResult']
        if upd.get('storyTimeline') is not None and _can_set('storyTimeline'):
            meta['storyTimeline'] = upd['storyTimeline']
        if upd.get('storyPhase') and _can_set('storyPhase'):
            meta['storyPhase'] = upd['storyPhase']
        if upd.get('forecast') and _can_set('forecast'):
            meta['forecast'] = upd['forecast']
        if upd.get('summaryMode') and _can_set('summaryMode'):
            meta['summaryMode'] = upd['summaryMode']
        if upd.get('perspectives') is not None and _can_set('perspectives'):
            meta['perspectives'] = upd['perspectives']
        # T220+1811e4b 統合(2026-04-27): topicTitle 系メタを S3 にも反映
        if upd.get('topicTitle') and _can_set('topicTitle'):
            meta['topicTitle'] = upd['topicTitle']
        if upd.get('latestUpdateHeadline') and _can_set('latestUpdateHeadline'):
            meta['latestUpdateHeadline'] = upd['latestUpdateHeadline']
        if upd.get('topicCoherent') is not None and _can_set('topicCoherent'):
            meta['topicCoherent'] = upd['topicCoherent']
        if upd.get('topicLevel') and _can_set('topicLevel'):
            meta['topicLevel'] = upd['topicLevel']
        if upd.get('parentTopicTitle') and _can_set('parentTopicTitle'):
            meta['parentTopicTitle'] = upd['parentTopicTitle']
        if upd.get('relatedTopicTitles') is not None and _can_set('relatedTopicTitles'):
            meta['relatedTopicTitles'] = upd['relatedTopicTitles']
        if upd.get('aiGenerated'):
            meta['aiGenerated'] = True
            # schemaVersion も AI 成功フラグと一緒に最新版へ (制御フィールドなので常に上書き)
            meta['schemaVersion'] = PROCESSOR_SCHEMA_VERSION
        # T41: Tool Use 後に genres が AI で更新される (例: スポーツ→国際) → S3 にも反映
        if upd.get('genres') and _can_set('genres'):
            meta['genres'] = upd['genres']
            meta['genre'] = upd['genres'][0] if upd['genres'] else meta.get('genre')
        if upd.get('imageUrl') and not meta.get('imageUrl'):
            meta['imageUrl'] = upd['imageUrl']
        data['meta'] = meta
        new_body = json.dumps(data, default=dec_convert, ensure_ascii=False).encode('utf-8')
        new_etag = '"' + hashlib.md5(new_body).hexdigest() + '"'
        json_changed = new_etag != old_etag
        if json_changed:
            s3.put_object(
                Bucket=S3_BUCKET, Key=key, Body=new_body,
                ContentType='application/json', CacheControl='max-age=60',
            )
        # 静的SEO用HTML生成: JSON変更時のみ再生成（変更なしはスキップしてS3 PUT削減）
        if json_changed and (meta.get('aiGenerated') or meta.get('generatedSummary')):
            # articles_cacheが空の場合はtimeline[].articlesから収集（トップレベルにarticlesキーは存在しない）
            if not articles:
                _tl_arts, _seen = [], set()
                for _snap in reversed(data.get('timeline', [])):
                    for _a in _snap.get('articles', []):
                        if _a.get('url') and _a['url'] not in _seen:
                            _seen.add(_a['url']); _tl_arts.append(_a)
                articles = _tl_arts
            generate_static_topic_html(tid, meta, articles)
    except Exception as e:
        # T249 (2026-04-28): 静的HTML生成失敗をサイレントに握り潰すと、古い genre/title のままの
        # SEO HTML が放置される (本番で「外交トピックがスポーツニュースとタグ付け」を確認)。
        # CLAUDE.md「対症療法ではなく根本原因」と「Lambda 主ループは可観測でなければ
        # 規則で守れない (band-aid 排除原則)」に従い、必ずログに残す。
        # governance worker で `[TOPIC_STATIC_FAIL]` の集計が将来できるようにする。
        print(f'[TOPIC_STATIC_FAIL] tid={tid} error={type(e).__name__}: {e}')


def update_topic_s3_files_parallel(ai_updates, max_workers=5, articles_cache=None, incremental_map=None):
    """ai_updatesの全トピックの個別S3ファイルをAIデータで並列更新。
    articles_cache が渡された場合は静的SEO用HTMLも同時生成。

    Args:
        incremental_map: dict[tid -> bool] | None — 各トピックを incremental モードで書くか。
                         T2026-0428-AO: heal/再処理ループで既存 AI フィールドを保護する。
                         None のときは全トピック full モード (初回処理扱い)。
    """
    if not ai_updates or not S3_BUCKET:
        return
    _arts = articles_cache or {}
    _inc  = incremental_map or {}
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {
            ex.submit(update_topic_s3_file, tid, upd, _arts.get(tid), _inc.get(tid, False)): tid
            for tid, upd in ai_updates.items()
        }
        for _ in as_completed(futures):
            pass
    print(f'[Processor] 個別S3ファイル+静的HTML更新完了 ({len(ai_updates)}件)')


def generate_and_upload_rss(topics):
    """上位トピックからRSS 2.0 フィードを生成してS3にアップロード。"""
    if not S3_BUCKET:
        return
    active = [t for t in topics if t.get('lifecycleStatus') in ('active', 'cooling', '')]
    active.sort(key=lambda x: float(x.get('velocityScore', 0) or 0), reverse=True)

    # 同一イベント重複抑制: キーワード3つ以上共通するトピックは最大2件のみ
    _STOP = {'ニュース', '速報', '情報', '中継', '会見', '更新'}
    def _kw(t):
        title = re.sub(r'[【】「」（）！？\[\]\s　・]+', ' ', t.get('generatedTitle', '') + ' ' + t.get('title', ''))
        return {w for w in title.split() if len(w) >= 3 and w not in _STOP}
    deduped, event_counts = [], {}
    for t in active:
        kw = _kw(t)
        matched = None
        for ev, ev_kw in event_counts.items():
            if len(kw & ev_kw) >= 3:
                matched = ev
                break
        if matched is None:
            ev_id = t.get('topicId', '')
            event_counts[ev_id] = kw
            deduped.append((ev_id, t))
        else:
            if sum(1 for eid, _ in deduped if eid == matched) < 2:
                deduped.append((matched, t))
    top = [t for _, t in deduped][:40]

    def to_rfc822(ts):
        try:
            if not ts:
                return formatdate()
            if isinstance(ts, (int, float)):
                return formatdate(time.mktime(datetime.utcfromtimestamp(ts).timetuple()))
            return formatdate(time.mktime(datetime.fromisoformat(str(ts).replace('Z', '+00:00')).timetuple()))
        except Exception:
            return formatdate()

    def xml_escape(s):
        return str(s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

    items = []
    for t in top:
        tid = t.get('topicId', '')
        title = xml_escape(t.get('generatedTitle') or t.get('title') or 'Flotopic')
        desc  = xml_escape((t.get('generatedSummary') or '')[:200])
        link  = f'https://flotopic.com/topics/{tid}.html'
        pub   = to_rfc822(t.get('lastArticleAt') or t.get('lastUpdated'))
        genre = xml_escape((t.get('genres') or [t.get('genre', '総合')])[0])
        items.append(
            f'  <item>\n'
            f'    <title>{title}</title>\n'
            f'    <link>{link}</link>\n'
            f'    <description>{desc}</description>\n'
            f'    <pubDate>{pub}</pubDate>\n'
            f'    <guid isPermaLink="true">{link}</guid>\n'
            f'    <category>{genre}</category>\n'
            f'  </item>'
        )

    rss = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
        '<channel>\n'
        '  <title>Flotopic — 話題の盛り上がりをAIで追う</title>\n'
        '  <link>https://flotopic.com/</link>\n'
        '  <description>AIがまとめた注目トピックの最新フィード</description>\n'
        '  <language>ja</language>\n'
        '  <ttl>30</ttl>\n'
        f'  <atom:link href="https://flotopic.com/rss.xml" rel="self" type="application/rss+xml"/>\n'
        + '\n'.join(items) + '\n'
        '</channel>\n'
        '</rss>\n'
    )

    try:
        s3.put_object(
            Bucket=S3_BUCKET,
            Key='rss.xml',
            Body=rss.encode('utf-8'),
            ContentType='application/rss+xml',
            CacheControl='max-age=1800',
        )
        print(f'[Processor] rss.xml 更新完了 ({len(top)}件)')
    except Exception as e:
        print(f'[Processor] rss.xml 更新エラー: {e}')


def generate_and_upload_news_sitemap(topics):
    """Google News Sitemap (news sitemap) を生成してS3にアップロード。
    直近2日以内に更新されたactive/coolingトピックのみ対象。
    """
    if not S3_BUCKET:
        return
    cutoff = datetime.now(timezone.utc) - timedelta(days=2)
    news_topics = []
    for t in topics:
        if t.get('lifecycleStatus') not in ('active', 'cooling'):
            continue
        if not t.get('generatedTitle') and not t.get('title'):
            continue
        raw_ts = t.get('lastArticleAt') or t.get('lastUpdated')
        if not raw_ts:
            continue
        try:
            if isinstance(raw_ts, (int, float)):
                ts = datetime.fromtimestamp(float(raw_ts), tz=timezone.utc)
            else:
                ts = datetime.fromisoformat(str(raw_ts).replace('Z', '+00:00'))
            if ts < cutoff:
                continue
            news_topics.append((t, ts))
        except Exception:
            continue

    news_topics.sort(key=lambda x: x[1], reverse=True)
    news_topics = news_topics[:50]

    def xml_escape(s):
        return str(s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    # T2026-0428-AB: 静的 HTML が S3 に存在する tid のみ sitemap に含める。
    # 背景: lifecycle が DDB と topics.json の sync に失敗するケース、または
    # AI 未生成のため `topics/{tid}.html` が未作成のケースで、sitemap が
    # 404 URL を Google News に送る事故を防ぐ防衛ライン。
    def _has_static_html(tid: str) -> bool:
        if not tid:
            return False
        try:
            s3.head_object(Bucket=S3_BUCKET, Key=f'topics/{tid}.html')
            return True
        except Exception:
            return False
    news_topics = [(t, ts) for t, ts in news_topics if _has_static_html(t.get('topicId', ''))]

    items = []
    for t, ts in news_topics:
        tid = t.get('topicId', '')
        title = xml_escape(t.get('generatedTitle') or t.get('title', ''))
        pub_iso = ts.strftime('%Y-%m-%dT%H:%M:%S+00:00')
        genres = t.get('genres') or ([t['genre']] if t.get('genre') else ['総合'])
        kw = xml_escape(', '.join(genres[:3]))
        items.append(
            f'  <url>\n'
            f'    <loc>https://flotopic.com/topics/{tid}.html</loc>\n'
            f'    <news:news>\n'
            f'      <news:publication>\n'
            f'        <news:name>Flotopic</news:name>\n'
            f'        <news:language>ja</news:language>\n'
            f'      </news:publication>\n'
            f'      <news:publication_date>{pub_iso}</news:publication_date>\n'
            f'      <news:title>{title}</news:title>\n'
            f'      <news:keywords>{kw}</news:keywords>\n'
            f'    </news:news>\n'
            f'  </url>'
        )

    ns = 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:news="http://www.google.com/schemas/sitemap-news/0.9"'
    sitemap = f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset {ns}>\n'
    sitemap += '\n'.join(items)
    sitemap += '\n</urlset>\n'

    try:
        s3.put_object(
            Bucket=S3_BUCKET,
            Key='news-sitemap.xml',
            Body=sitemap.encode('utf-8'),
            ContentType='application/xml',
            CacheControl='no-cache, must-revalidate',
        )
        print(f'[Processor] news-sitemap.xml 更新完了 ({len(items)}件)')
    except Exception as e:
        print(f'[Processor] news-sitemap.xml 更新エラー: {e}')


def generate_and_upload_sitemap(topics):
    """topics リストから sitemap.xml を生成して S3 にアップロード。"""
    if not S3_BUCKET:
        return
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    active = [t for t in topics if t.get('lifecycleStatus') in ('active', 'cooling', '')]
    active.sort(key=lambda x: float(x.get('velocityScore', 0) or 0), reverse=True)
    top = active[:200]

    urls = [
        f'  <url>\n    <loc>https://flotopic.com/</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>hourly</changefreq>\n    <priority>1.0</priority>\n  </url>',
        f'  <url>\n    <loc>https://flotopic.com/catchup.html</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>daily</changefreq>\n    <priority>0.8</priority>\n  </url>',
        f'  <url>\n    <loc>https://flotopic.com/about.html</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>monthly</changefreq>\n    <priority>0.5</priority>\n  </url>',
        f'  <url>\n    <loc>https://flotopic.com/terms.html</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>monthly</changefreq>\n    <priority>0.3</priority>\n  </url>',
        f'  <url>\n    <loc>https://flotopic.com/privacy.html</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>monthly</changefreq>\n    <priority>0.3</priority>\n  </url>',
        f'  <url>\n    <loc>https://flotopic.com/contact.html</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>monthly</changefreq>\n    <priority>0.4</priority>\n  </url>',
    ]
    # T2026-0428-AB: 静的 HTML が S3 に存在する tid のみ sitemap に含める防衛ライン。
    # head_object はバッチ処理だと 200 件で ~6 秒。許容範囲。
    def _has_static_html(tid: str) -> bool:
        if not tid:
            return False
        try:
            s3.head_object(Bucket=S3_BUCKET, Key=f'topics/{tid}.html')
            return True
        except Exception:
            return False
    for t in top:
        tid = t.get('topicId', '')
        if not tid:
            continue
        if not _has_static_html(tid):
            continue
        last = (t.get('lastUpdated') or today)[:10]
        # 静的HTMLが存在する場合はそちらをSEO canonical URLとして使用
        urls.append(f'  <url>\n    <loc>https://flotopic.com/topics/{tid}.html</loc>\n    <lastmod>{last}</lastmod>\n    <changefreq>hourly</changefreq>\n    <priority>0.8</priority>\n  </url>')

    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sitemap += '\n'.join(urls)
    sitemap += '\n</urlset>\n'

    try:
        s3.put_object(
            Bucket=S3_BUCKET,
            Key='sitemap.xml',
            Body=sitemap.encode('utf-8'),
            ContentType='application/xml',
            CacheControl='no-cache, must-revalidate',
        )
        print(f'[Processor] sitemap.xml 更新完了 ({len(top)+6}件)')
    except Exception as e:
        print(f'[Processor] sitemap.xml 更新エラー: {e}')


def _wrap_text_pil(draw, text, font, max_width: int) -> list:
    """Pillowのfontでテキストをmax_widthに折り返す（文字単位）。"""
    lines, current = [], ''
    for ch in text:
        test = current + ch
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] > max_width and current:
            lines.append(current)
            current = ch
        else:
            current = test
    if current:
        lines.append(current)
    return lines


def generate_ogp_image(tid: str, title: str, genre: str = '') -> 'str | None':
    """トピック用OGP画像(1200x630)を生成してS3にアップロード。CloudFront URLを返す。
    Pillowが未インストールの場合はNoneを返す（graceful degradation）。
    """
    if not S3_BUCKET or not title:
        return None
    title = _strip_title_markdown(title) or title
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None

    img  = Image.new('RGB', (_OGP_W, _OGP_H), _OGP_BG)
    draw = ImageDraw.Draw(img)

    # 右上のアクセント円
    draw.ellipse([900, -100, 1350, 350], fill=(20, 30, 60))
    draw.ellipse([950, -60, 1300, 290], fill=(25, 35, 70))

    # フォントロード（失敗時はデフォルトフォント）
    font_path = _FONT_PATH if os.path.exists(_FONT_PATH) else None
    def _font(size):
        if font_path:
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                pass
        return ImageFont.load_default()

    # Flotopicロゴ
    draw.text((60, 52), 'Flotopic', font=_font(38), fill=_OGP_ACCENT)

    # 区切り線
    draw.rectangle([60, 112, 1140, 114], fill=(40, 55, 80))

    # ジャンルタグ
    tag_y = 140
    if genre:
        tag_font = _font(26)
        tag_text = f'  #{genre}  '
        bbox = draw.textbbox((0, 0), tag_text, font=tag_font)
        tag_w = bbox[2] - bbox[0] + 20
        draw.rounded_rectangle([58, tag_y, 58 + tag_w, tag_y + 40], radius=8, fill=(40, 52, 80))
        draw.text((68, tag_y + 4), f'#{genre}', font=tag_font, fill=_OGP_ACCENT)
        tag_y += 52

    # トピックタイトル（折り返しあり・最大3行）
    title_font = _font(58)
    title_y = tag_y + 10
    lines = _wrap_text_pil(draw, title, title_font, _OGP_W - 120)
    for i, line in enumerate(lines[:3]):
        if i == 2 and len(lines) > 3:
            # 3行目は省略記号付き
            while line and draw.textbbox((0, 0), line + '…', font=title_font)[2] > _OGP_W - 120:
                line = line[:-1]
            line += '…'
        draw.text((60, title_y), line, font=title_font, fill=_OGP_TEXT)
        title_y += 72

    # フッター
    draw.rectangle([60, _OGP_H - 70, 1140, _OGP_H - 68], fill=(40, 55, 80))
    draw.text((60, _OGP_H - 56), 'flotopic.com  —  話題の盛り上がりをAIで追う', font=_font(24), fill=_OGP_SUB)

    # PNG → S3
    buf = io.BytesIO()
    img.save(buf, format='PNG', optimize=True)
    buf.seek(0)
    key = f'api/ogp/{tid}.png'
    try:
        s3.put_object(
            Bucket=S3_BUCKET, Key=key, Body=buf.getvalue(),
            ContentType='image/png', CacheControl='max-age=86400',
        )
        return f'https://flotopic.com/{key}'
    except Exception as e:
        print(f'[OGP] S3アップロード失敗 [{tid}]: {e}')
        return None


def _html_esc(s: str) -> str:
    return (s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


import re as _re
def _strip_md(s: str) -> str:
    """AI生成テキストのマークダウン記法を除去して1行プレーンテキストにする。"""
    s = _re.sub(r'^#{1,3}\s+.+?$', '', s, flags=_re.MULTILINE)
    s = _re.sub(r'^[-*]\s+', '', s, flags=_re.MULTILINE)
    s = _re.sub(r'^\d+\.\s+', '', s, flags=_re.MULTILINE)
    s = _re.sub(r'\n{2,}', ' ', s)
    return s.replace('\n', ' ').strip()


def generate_static_topic_html(tid: str, meta: dict, articles: list) -> None:
    """トピックの静的SEO用HTMLをS3の topics/{tid}.html に書き出す。
    Googlebotが読める完全なHTMLを生成する（JavaScriptなし）。
    """
    if not S3_BUCKET:
        return
    title      = _html_esc(meta.get('generatedTitle') or meta.get('title', ''))
    summary    = _html_esc(_strip_md(meta.get('generatedSummary') or ''))
    bg_context = _html_esc(_strip_md(meta.get('backgroundContext') or ''))
    spread     = _html_esc(_strip_md(meta.get('spreadReason') or ''))
    forecast   = _html_esc(_strip_md(meta.get('forecast') or ''))
    genres_raw = meta.get('genres') or ([meta.get('genre', '総合')] if meta.get('genre') else ['総合'])
    genre      = _html_esc(genres_raw[0])
    image_url  = _html_esc(meta.get('imageUrl') or 'https://flotopic.com/icons/icon-512.png')
    canonical  = f'https://flotopic.com/topics/{tid}.html'
    interactive = f'https://flotopic.com/topic.html?id={tid}'

    # アフィリエイトリンク（ジャンル別キーワード → もしもアフィリエイト経由）
    _GENRE_KW = {
        'テクノロジー': 'ガジェット 最新', 'グルメ': 'お取り寄せ グルメ',
        'ファッション': 'ファッション アイテム', 'スポーツ': 'スポーツ 用品',
        'エンタメ': 'エンタメ グッズ', '健康': '健康 サプリ',
        'ビジネス': 'ビジネス 書籍', '科学': '科学 本',
        'くらし': 'くらし 雑貨', '社会': 'くらし 便利グッズ',
        '国際': '旅行 グッズ', '株・金融': '投資 書籍', '政治': 'ビジネス 書籍',
    }
    _aff_kw  = _GENRE_KW.get(genres_raw[0], 'おすすめ 人気')
    import urllib.parse as _up
    _q       = _up.quote(_aff_kw, safe='')
    _aid     = '1188659'
    _amz_url = _up.quote(f'https://www.amazon.co.jp/s?k={_q}', safe='')
    _rkt_url = _up.quote(f'https://search.rakuten.co.jp/search/mall/{_q}/', safe='')
    _yhs_url = _up.quote(f'https://shopping.yahoo.co.jp/search?p={_q}', safe='')
    _affiliate_html = f'''<section class="aff-section">
<p class="aff-label">広告 — この話題に関連する商品</p>
<div class="aff-links">
<a href="https://af.moshimo.com/af/c/click?a_id={_aid}&amp;p_id=170&amp;pc_id=185&amp;pl_id=4062&amp;url={_amz_url}" target="_blank" rel="noopener sponsored" class="aff-btn aff-amz">🛒 Amazonで探す</a>
<a href="https://af.moshimo.com/af/c/click?a_id={_aid}&amp;p_id=54&amp;pc_id=53&amp;pl_id=616&amp;url={_rkt_url}" target="_blank" rel="noopener sponsored" class="aff-btn aff-rkt">楽天市場で探す</a>
<a href="https://af.moshimo.com/af/c/click?a_id={_aid}&amp;p_id=1225&amp;pc_id=2254&amp;pl_id=7610&amp;url={_yhs_url}" target="_blank" rel="noopener sponsored" class="aff-btn aff-yhs">Y! ショッピングで探す</a>
</div>
<p class="aff-note">※ アフィリエイトリンクを含みます。購入者様の費用は変わりません。キーワード: {_html_esc(_aff_kw)}</p>
</section>'''
    timeline   = meta.get('storyTimeline') or []
    story_phase = meta.get('storyPhase', '')
    article_count = int(meta.get('articleCount', 0) or 0)
    _PHASE_LABEL = {'発端': '🌱 始まり', '拡散': '📡 広まってる', 'ピーク': '🔥 急上昇', '現在地': '📍 進行中', '収束': '✅ ひと段落'}
    _PHASE_CSS   = {'発端': 'rising', '拡散': 'rising', 'ピーク': 'peak', '現在地': 'declining', '収束': 'declining'}
    phase_css    = _PHASE_CSS.get(story_phase, '')
    phase_badge  = (f'<span class="phase-badge phase-{phase_css}">{_PHASE_LABEL[story_phase]}</span>'
                    if story_phase in _PHASE_LABEL else '')
    last_upd   = (meta.get('lastUpdated') or '')[:10] or ''
    _lat = int(meta.get('lastArticleAt') or 0)
    date_published = (datetime.utcfromtimestamp(_lat).strftime('%Y-%m-%dT%H:%M:%SZ') if _lat else last_upd)

    # ロングテールSEO用 <title>: ジャンル別サフィックスを付与
    _GENRE_SUFFIX = {
        '政治': '政治ニュース 経緯・最新情報まとめ',
        'ビジネス': 'ビジネスニュース 経緯・最新情報まとめ',
        '株・金融': '株式・金融 経緯・最新情報まとめ',
        'テクノロジー': 'テクノロジーニュース 経緯まとめ',
        'スポーツ': 'スポーツニュース 経緯・最新情報まとめ',
        'エンタメ': 'エンタメニュース 経緯まとめ',
        '科学': '科学ニュース 最新情報まとめ',
        '健康': '健康・医療ニュース まとめ',
        '国際': '国際ニュース 経緯・最新情報まとめ',
        'グルメ': 'グルメ情報まとめ',
        'ファッション': 'ファッション・美容 最新情報まとめ',
    }
    seo_suffix = _GENRE_SUFFIX.get(genres_raw[0], '最新情報・経緯まとめ')
    seo_title  = _html_esc(f'{meta.get("generatedTitle") or meta.get("title", "")} — {seo_suffix}')

    # ストーリータイムラインHTML
    timeline_html = ''
    if timeline:
        items_html = []
        for ev in timeline:
            ev_event    = _html_esc(ev.get('event', ''))
            ev_date     = _html_esc(str(ev.get('date', '')))
            ev_trans    = _html_esc(ev.get('transition', ''))
            trans_part  = f'<p class="tr">{ev_trans}</p>' if ev_trans else ''
            items_html.append(
                f'<div class="ev">'
                f'<span class="ev-date">{ev_date}</span>'
                f'<strong>{ev_event}</strong>'
                f'{trans_part}'
                f'</div>'
            )
        timeline_html = '<section><h2>ストーリーの流れ</h2>' + ''.join(items_html) + '</section>'

    # 記事リストHTML（上位10件）
    # T2026-0428-AN: a.get('isPrimary') が True なら一次情報バッジを付与。
    # フラグは fetcher 側で URL ドメイン照合（is_primary_source）により付与済み。
    # 古い SNAP（フラグ未付与）はバッジ無しで表示する（後方互換）。
    # 著作権法32条「引用」として利用、出典明示必須（必ず source 名を表示する）。
    articles_html = ''
    if articles:
        art_items = []
        for a in articles[:10]:
            a_title  = _html_esc(a.get('title', ''))
            a_url    = _html_esc(a.get('url', ''))
            a_src    = _html_esc(a.get('source', ''))
            a_date   = _html_esc(str(a.get('pubDate', ''))[:10])
            primary_badge = (
                '<span class="primary-badge" title="この記事は一次情報源からの報道です">🔵 一次情報</span>'
                if a.get('isPrimary') else ''
            )
            if a_url and a_title:
                art_items.append(
                    f'<li>{primary_badge}<a href="{a_url}" rel="noopener">{a_title}</a>'
                    f'<span class="src"> — {a_src} {a_date}</span></li>'
                )
        if art_items:
            articles_html = '<section><h2>関連記事</h2><ul>' + ''.join(art_items) + '</ul></section>'

    # AI要約セクション
    ai_html = ''
    if summary:
        parts = [f'<section><h2>AIによるまとめ</h2><p>{summary}</p>']
        if bg_context:
            parts.append(f'<h3>なぜ起きたか（背景・構造的原因）</h3><p>{bg_context}</p>')
        if spread:
            parts.append(f'<h3>なぜ広がっているか</h3><p>{spread}</p>')
        if forecast:
            parts.append(f'<h3>今後の展望</h3><p>{forecast}</p>')
        parts.append('</section>')
        ai_html = ''.join(parts)

    # JSON-LD
    jsonld = json.dumps({
        '@context': 'https://schema.org',
        '@type': 'Article',
        'headline': meta.get('generatedTitle') or meta.get('title', ''),
        'description': _strip_md(meta.get('generatedSummary', ''))[:200],
        'image': meta.get('imageUrl') or 'https://flotopic.com/icons/icon-512.png',
        'datePublished': date_published,
        'dateModified': last_upd,
        'author': {'@type': 'Organization', 'name': 'Flotopic', 'url': 'https://flotopic.com'},
        'publisher': {'@type': 'Organization', 'name': 'Flotopic', 'url': 'https://flotopic.com'},
        'url': canonical,
        'keywords': ', '.join(genres_raw) if genres_raw else genre,
    }, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{seo_title} | Flotopic</title>
<meta name="description" content="{summary[:155] if summary else title}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="article">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{((_PHASE_LABEL.get(story_phase,'') + ' ') if story_phase else '') + (summary[:140] if summary else title)}">
<meta property="og:image" content="{image_url}">
<meta property="og:url" content="{canonical}">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">{jsonld}</script>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:800px;margin:0 auto;padding:16px;color:#1e293b;line-height:1.7}}
h1{{font-size:1.6rem;margin-bottom:.5rem}}
h2{{font-size:1.1rem;border-left:4px solid #6366f1;padding-left:.6rem;margin-top:2rem}}
h3{{font-size:1rem;color:#475569;margin-top:1.2rem}}
.genre{{display:inline-block;background:#e0e7ff;color:#4338ca;border-radius:4px;padding:2px 8px;font-size:.8rem;margin-bottom:.5rem}}
.phase-badge{{display:inline-block;font-size:.78rem;font-weight:700;border-radius:4px;padding:2px 8px;margin-left:6px;margin-bottom:.5rem}}
.phase-rising{{background:#fef2f2;color:#dc2626}}
.phase-peak{{background:#fffbeb;color:#b45309}}
.phase-declining{{background:#f1f5f9;color:#64748b}}
.ev{{border-left:2px solid #c7d2fe;margin:.8rem 0;padding:.4rem .8rem}}
.ev-date{{font-size:.8rem;color:#64748b;display:block}}
.tr{{font-style:italic;color:#6366f1;margin:.3rem 0 0}}
.cta{{background:#f1f5f9;border-radius:8px;padding:20px;margin:2rem 0;text-align:center}}
.cta-context{{font-size:.82rem;color:#64748b;margin:0 0 12px}}
.cta-btn{{display:inline-block;background:#6366f1;color:#fff;border-radius:8px;padding:12px 24px;font-weight:bold;font-size:.95rem;text-decoration:none;margin:0 0 10px}}
.cta-sub{{font-size:.75rem;color:#94a3b8;margin:6px 0 0}}
ul{{padding-left:1.2rem}}
li{{margin:.4rem 0}}
.src{{font-size:.8rem;color:#94a3b8}}
a{{color:#3b82f6}}
header{{display:flex;align-items:center;gap:12px;margin-bottom:1rem;border-bottom:1px solid #e2e8f0;padding-bottom:.8rem}}
header a{{color:#6366f1;font-weight:bold;font-size:1.1rem;text-decoration:none}}
.aff-section{{background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:14px 16px;margin:2rem 0}}
.aff-label{{font-size:.72rem;color:#92400e;font-weight:700;margin:0 0 10px}}
.aff-links{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:8px}}
.aff-btn{{display:inline-block;padding:8px 14px;border-radius:6px;font-size:.84rem;font-weight:600;text-decoration:none}}
.aff-amz{{background:#ff9900;color:#fff}}.aff-rkt{{background:#bf0000;color:#fff}}.aff-yhs{{background:#ff0033;color:#fff}}
.aff-note{{font-size:.7rem;color:#92400e;margin:0}}
.primary-badge{{display:inline-block;background:rgba(59,130,246,.12);color:#1d4ed8;border:1px solid rgba(59,130,246,.4);border-radius:4px;padding:1px 6px;font-size:.72rem;font-weight:700;margin-right:6px;vertical-align:middle}}
</style>
</head>
<body>
<header><a href="https://flotopic.com">Flotopic</a><span style="color:#94a3b8;font-size:.85rem">— 話題の盛り上がりをAIで追う</span></header>
<span class="genre">#{genre}</span>{phase_badge}
<h1>{title}</h1>
<p style="font-size:.8rem;color:#94a3b8;margin:.3rem 0 1.5rem;">{article_count}件の記事</p>
{ai_html}
{timeline_html}
{articles_html}
{_affiliate_html}
<div class="cta">
  <p class="cta-context">{article_count}件の記事からAIが経緯をまとめました</p>
  <a class="cta-btn" href="{interactive}">📖 ストーリーの全体像を見る →</a>
  <p class="cta-sub">お気に入り登録でこのトピックの新展開を見逃さない</p>
</div>
<footer style="margin-top:2rem;padding-top:1rem;border-top:1px solid #e2e8f0;font-size:.8rem;color:#94a3b8">
  <a href="https://flotopic.com">Flotopic</a> &nbsp;|&nbsp;
  <a href="https://flotopic.com/about.html">About</a> &nbsp;|&nbsp;
  <a href="https://flotopic.com/privacy.html">プライバシーポリシー</a>
</footer>
</body>
</html>"""

    try:
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=f'topics/{tid}.html',
            Body=html.encode('utf-8'),
            ContentType='text/html; charset=utf-8',
            CacheControl='max-age=600',
        )
    except Exception as e:
        print(f'[StaticHTML] S3書き込みエラー [{tid}]: {e}')


def batch_generate_static_html(max_topics: int = 500) -> int:
    """現在の api/topics.json に含まれるトピックの静的HTMLを一括生成する。
    api/topic/{tid}.json が存在するトピックのみ対象。
    """
    if not S3_BUCKET:
        return 0

    # 現在のアクティブトピック一覧を topics.json から取得
    try:
        resp = s3.get_object(Bucket=S3_BUCKET, Key='api/topics.json')
        topics_data = json.loads(resp['Body'].read())
        active_topics = topics_data if isinstance(topics_data, list) else topics_data.get('topics', [])
    except Exception as e:
        print(f'[StaticHTML] topics.json 読み込み失敗: {e}')
        return 0

    # アクティブトピックのIDから api/topic/{tid}.json キーリストを作成
    keys = [f'api/topic/{t["topicId"]}.json' for t in active_topics[:max_topics] if t.get('topicId')]
    print(f'[StaticHTML] バッチ生成対象: {len(keys)}件（topics.json ベース）')

    generated = 0

    def _gen(key):
        tid = key.split('/')[-1].replace('.json', '')
        try:
            resp = s3.get_object(Bucket=S3_BUCKET, Key=key)
            data = json.loads(resp['Body'].read())
            meta = data.get('meta', {})
            # トップレベルの 'articles' キーは存在しない。timeline[].articles から収集する
            _tl_arts, _seen = [], set()
            for _snap in reversed(data.get('timeline', [])):
                for _a in _snap.get('articles', []):
                    if _a.get('url') and _a['url'] not in _seen:
                        _seen.add(_a['url']); _tl_arts.append(_a)
            articles = _tl_arts
            generate_static_topic_html(tid, meta, articles)
            return 'ok'
        except Exception as e:
            if hasattr(e, 'response') and e.response.get('Error', {}).get('Code') == 'NoSuchKey':
                return 'skip'
            print(f'[StaticHTML] 生成失敗 [{tid}]: {e}')
            return 'fail'

    with ThreadPoolExecutor(max_workers=10) as ex:
        results = list(ex.map(_gen, keys))
    generated = sum(1 for r in results if r == 'ok')
    skipped   = sum(1 for r in results if r == 'skip')
    failed    = sum(1 for r in results if r == 'fail')
    if failed:
        print(f'[StaticHTML] バッチ生成完了: {generated}件生成 / {skipped}件スキップ / {failed}件失敗')
    else:
        print(f'[StaticHTML] バッチ生成完了: {generated}件生成 / {skipped}件スキップ（detail未作成）')
    return generated


def backfill_missing_detail_json() -> int:
    """topics.json に含まれるが api/topic/{tid}.json が S3 に存在しないトピックを DynamoDB から補完する。"""
    if not S3_BUCKET:
        return 0
    try:
        resp = s3.get_object(Bucket=S3_BUCKET, Key='api/topics.json')
        topics_data = json.loads(resp['Body'].read())
        active_topics = topics_data if isinstance(topics_data, list) else topics_data.get('topics', [])
    except Exception as e:
        print(f'[Backfill] topics.json 読み込み失敗: {e}')
        return 0

    _INTERNAL = {'SK', 'pendingAI', 'ttl'}
    filled = 0
    for t in active_topics:
        tid = t.get('topicId')
        if not tid:
            continue
        key = f'api/topic/{tid}.json'
        try:
            s3.head_object(Bucket=S3_BUCKET, Key=key)
            continue
        except Exception as e:
            if hasattr(e, 'response') and e.response.get('Error', {}).get('Code') not in ('404', 'NoSuchKey'):
                continue

        try:
            meta_resp = table.get_item(Key={'topicId': tid, 'SK': 'META'})
            meta = meta_resp.get('Item')
            if not meta:
                continue
            meta_public = {k: v for k, v in meta.items() if k not in _INTERNAL}

            snaps_resp = table.query(
                KeyConditionExpression=Key('topicId').eq(tid) & Key('SK').begins_with('SNAP#'),
                ScanIndexForward=False, Limit=30,
            )
            snaps = sorted(snaps_resp.get('Items', []), key=lambda x: x['SK'])

            write_s3(key, {
                'meta': meta_public,
                'timeline': [
                    {'timestamp': s['timestamp'], 'articleCount': s['articleCount'],
                     'score': s.get('score', 0), 'hatenaCount': s.get('hatenaCount', 0),
                     'articles': s.get('articles', [])}
                    for s in snaps
                ],
                'views': [],
            })
            filled += 1
            print(f'[Backfill] {tid}: detail JSON 補完完了')
        except Exception as e:
            print(f'[Backfill] {tid}: 補完失敗 {e}')

    print(f'[Backfill] 完了: {filled}件補完')
    return filled


def notify_slack_error(error_msg: str):
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
