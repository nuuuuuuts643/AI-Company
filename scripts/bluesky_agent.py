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
import time
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
S3_BUCKET            = os.environ.get('S3_BUCKET', 'flotopic-public')

SITE_URL = 'https://flotopic.com'

# BlueSky 文字数制限
BSKY_MAX_CHARS = 300

# ════════════════════════════════════════════════════════════════════════════
# ⭐ Bluesky 投稿頻度・モード設定（単一の真実の源 / Single Source of Truth）⭐
# ════════════════════════════════════════════════════════════════════════════
# T2026-0502-L: 投稿頻度を変えたいときは **このブロックだけ** 編集すれば済むよう
#   全モードのレート制御パラメータをここに集約。各 post_xxx() 関数は冒頭で
#   `_check_rate_limit(mode)` を呼ぶだけで、独自のクールタイムを持たない。
#
# 経緯（lessons-learned: 2026-05-02 T2026-0502-L）:
#   debut モードに per-day cap が無く、30分 cron × 48tick × 1件 = 最大48件/日の
#   過剰投稿が発生（5/1 実測 48件）。当初は DEBUT_MAX_PER_RUN=0 のキルスイッチで
#   応急処置していたが、設計欠陥として恒久対処（このブロック化）。
#
# 3 重ガード設計（AND で全部通過したときのみ投稿）:
#   1) enabled        — False で完全停止 (kill switch)
#   2) cooldown_hours — 前回同モード投稿から N 時間空ける（DynamoDB lookup）
#   3) max_per_24h    — 24h 内の同モード投稿件数キャップ（DynamoDB lookup）
#
# 1日あたりの投稿上限（POの目標 = 4件/日）:
#   daily   3件 (8h cooldown × 3回 = 24h)
#   morning 1件 (JST 08:00 cron 単発)
#   debut   0件 (現在 enabled=False。再有効化時は max_per_24h=2 で最大2件/日)
#   合計    最大 4件/日 (debut 有効化時 6件/日)
#
# weekly/monthly はここに含めない (cron が単発・実質キュー外。post_weekly/
# post_monthly は CONFIG を参照しないので追加しても dead config になるだけ)。
# ════════════════════════════════════════════════════════════════════════════
BLUESKY_POSTING_CONFIG = {
    'daily': {
        'enabled':        True,
        'cooldown_hours': 8,    # 8h × 3 = 24h → 1日3回まで
        'max_per_24h':    3,    # 二重ガード: 24h スキャンで 3 件以上なら投稿停止
    },
    'morning': {
        'enabled':        True,
        'cooldown_hours': 20,   # 1 日 1 回想定 (20h バッファで cron 揺らぎ吸収)
        'max_per_24h':    1,
    },
    'debut': {
        # ⚠️ 現在無効化中 (新トピック登場通知の即時投稿)
        # 再有効化したい場合: enabled=True にする。max_per_24h=2 で 1日最大2件保証。
        # cooldown_hours=12 で前回 debut から 12h 空ける ⇒ 物理上限 2件/日。
        'enabled':        False,
        'cooldown_hours': 12,
        'max_per_24h':    2,
    },
}

# ════════════════════════════════════════════════════════════════════════════
# ⭐ Bluesky 投稿内容テンプレート（単一の真実の源 / Single Source of Truth）⭐
# ════════════════════════════════════════════════════════════════════════════
# T2026-0502-L: 投稿文言を変えたいときは **このブロックだけ** 編集すれば済むよう
#   全モードのフック・絵文字・フッターをここに集約。実体は build_post_text()
#   ヘルパーが組み立てる。各 post_xxx() 関数は build_post_text(mode, topic) を
#   呼ぶだけで、独自の f-string を持たない。
#
# 将来 X (Twitter) など他プラットフォームに展開する際は、同じ shape の辞書を
# x_agent.py に X_POSTING_TEMPLATES として複製し、char_limit と truncation
# パラメータを差し替えるだけで使い回せる設計。
#
# プレースホルダ:
#   {title_short}    — タイトル (デフォルト 36 字で truncate)
#   {summary_block}  — 要約ブロック (空なら空文字・要約有なら truncate(95)\n\n)
#   {hook}           — モード別の冒頭文（hooks 辞書から storyPhase 別に選択）
#   {footer}         — 末尾の記事数 + ハッシュタグ
#   {cnt}            — articleCount
#   {tag}            — genre_tag(topic) (#エンタメ #芸能 等)
# ════════════════════════════════════════════════════════════════════════════
BLUESKY_POSTING_TEMPLATES = {
    'daily': {
        # storyPhase 別のフック (ロングテール SEO 狙いの問いかけ形式)
        'hooks': {
            '発端':   '📰 速報: {title_short}\n今何が起きているのか？',
            '拡散':   '📢 注目: {title_short}\nなぜこれほど広がっているのか、背景と経緯',
            'ピーク': '🔥 急上昇中: {title_short}\nなぜ今これほど話題になっているのか',
            '現在地': '📍 進行中: {title_short}\n今どの段階まで進んでいるのか、経緯を追う',
            '収束':   '📋 まとめ: {title_short}\n何が起きたのか、全容を振り返る',
            '_default': '🔥 急上昇: {title_short}\nとは何か・なぜ注目される？',
        },
        'footer': '📄 {cnt}件の記事 {tag} #Flotopic',
    },
    'morning': {
        'hooks': {
            '_default': '🌅 今朝の動き: {title_short}\n昨夜から今朝にかけての動きをまとめました',
        },
        'footer': '📄 {cnt}件の記事 {tag} #Flotopic #朝のニュース',
    },
    'debut': {
        'hooks': {
            '_default': '🆕 新トピック登場: {title_short}\n初回スナップショットができました',
        },
        'footer': '📄 {cnt}件の記事 {tag} #Flotopic',
    },
}

# 全モード共通の本文構造 (mode を跨ぐ全体レイアウトを変えたいときはここだけ編集)
BLUESKY_POSTING_BODY_TEMPLATE = '{hook}\n\n{summary_block}{footer}'

# 切り詰め長 (将来 X agent では char_limit=280 に合わせて短縮)
BLUESKY_TITLE_TRUNCATE     = 36
BLUESKY_SUMMARY_TRUNCATE   = 95

MORNING_RECENT_HOURS    = 24    # post_morning の topic フィルタ（投稿対象の鮮度上限）


def build_post_text(mode: str, topic: dict) -> str:
    """
    BLUESKY_POSTING_TEMPLATES に基づき投稿本文を組み立てる単一エントリ。

    全 post_xxx() 関数はこの関数を呼ぶだけで、独自の f-string を持たない。
    文言・絵文字・ハッシュタグの調整は BLUESKY_POSTING_TEMPLATES の編集で完結する。

    Args:
      mode:  'daily' | 'morning' | 'debut'
      topic: topics.json の 1 トピック (generatedTitle / generatedSummary /
             articleCount / storyPhase / genre などを含む dict)

    Returns:
      組み立て済み投稿本文 (BSKY_MAX_CHARS で truncate 済み)
    """
    cfg = BLUESKY_POSTING_TEMPLATES.get(mode, {})
    hooks = cfg.get('hooks', {})
    footer_tmpl = cfg.get('footer', '')

    title       = topic.get('generatedTitle') or topic.get('title', '')
    summary     = topic.get('generatedSummary') or topic.get('extractiveSummary', '')
    cnt         = int(topic.get('articleCount', 0) or 0)
    phase       = topic.get('storyPhase', '')
    tag         = genre_tag(topic)
    title_short = truncate(title, BLUESKY_TITLE_TRUNCATE)

    # storyPhase に該当 hook がなければ '_default' にフォールバック (空辞書なら空文字)
    hook_tmpl = hooks.get(phase) or hooks.get('_default') or ''
    hook = hook_tmpl.format(title_short=title_short)

    summary_block = f'{truncate(summary, BLUESKY_SUMMARY_TRUNCATE)}\n\n' if summary else ''
    footer = footer_tmpl.format(cnt=cnt, tag=tag)

    body = BLUESKY_POSTING_BODY_TEMPLATE.format(
        hook=hook,
        summary_block=summary_block,
        footer=footer,
    )
    return body[:BSKY_MAX_CHARS]

# T2026-0428-AS: 初回 AI 要約完了 → 即時投稿 (debut) 用の S3 pending マーカー。
# processor Lambda が初回 AI 要約成功時に bluesky/pending/{topicId}.json を書き込み、
# bluesky_agent が次の cron tick (≤30分後) で消費して投稿する。
BLUESKY_PENDING_PREFIX  = 'bluesky/pending/'
DEBUT_MARKER_TTL_HOURS  = 24    # これより古いマーカーは破棄 (リトライ無限ループ防止)
# DEBUT_MAX_PER_RUN は 1 tick あたりの上限。日次キャップは BLUESKY_POSTING_CONFIG['debut']
# ['max_per_24h'] が _check_rate_limit() 経由で物理担保する。
DEBUT_MAX_PER_RUN       = 1     # T2026-0502-L: 1 に戻し、日次制御は config に委譲

# T2026-0429-K: 同一 topicId を 24h 以内に再投稿しない (時間ベース重複ガード)。
DUP_GUARD_HOURS  = 24

# トピックの「鮮度」カットオフ。lastUpdated/lastArticleAt が
# 24h 超のトピックは「古いトピックの再掲」とみなし投稿候補から除外する。
DAILY_TOPIC_FRESHNESS_HOURS = 24

# ── AWS クライアント ───────────────────────────────────────────────────────────
dynamodb = boto3.resource('dynamodb', region_name=REGION)
s3       = boto3.client('s3', region_name=REGION)


def compute_freshness_score(topic) -> float:
    """
    articleCount × 鮮度（直近24h以内の記事数）の代替スコアを 0-100 で返す。

    シグナル:
      - articleCountDelta  = 当日中に追加された記事数（articleCount - articleCountDayBase）
      - lastArticleAt      = 最終記事の epoch 秒
      - articleCount       = 累計記事数（delta=0 のフォールバック）

    減衰カーブ:
      <6h    ×1.0  / <24h ×0.7  / <48h ×0.3  / <72h ×0.1  / それ以降 ×0.02
    1記事=10点換算 → 100点上限でクランプ。

    fetcher/Google Trends に依存しない物理計測のみで算出するため、
    Trends 取得失敗時の安全側フォールバックとして機能する。
    """
    cnt     = int(topic.get('articleCount', 0) or 0)
    delta   = int(topic.get('articleCountDelta', 0) or 0)
    last_at = int(topic.get('lastArticleAt', 0) or 0)

    # 当日追加分が立っていればそれを優先、立っていなければ累計記事数で代用
    base_count = delta if delta > 0 else cnt

    if last_at == 0 or base_count == 0:
        return 0.0

    hours_since = (time.time() - last_at) / 3600
    if hours_since < 6:
        decay = 1.0
    elif hours_since < 24:
        decay = 0.7
    elif hours_since < 48:
        decay = 0.3
    elif hours_since < 72:
        decay = 0.1
    else:
        decay = 0.02

    return round(min(100.0, base_count * decay * 10), 4)


def compute_attention_score(topic) -> float:
    """
    Bluesky 選定用のハイブリッド注目度スコア。

    設計方針（Google Trends 単独依存を排除）:
      - velocityScore は RSS 伸び率に tier/メディア多様性/一次情報を乗じた
        「急上昇度」。半減期12hで時間減衰するため 0 や欠損になりうる。
      - velocityScore > 0  → velocityScore 70% + 鮮度 30% のブレンド
      - velocityScore ≤ 0  → 鮮度 100%（フォールバック）

    NOTE: velocityScore 自体は Google Trends に依存しない（trendsData は別フィールドで
    可視化専用）。それでも単一シグナル依存を避けるためハイブリッドにしている。
    velocityScore は乗算ボーナスで 100 超えうるので 100 上限でクランプして合算する。
    """
    vs    = float(topic.get('velocityScore', 0) or 0)
    fresh = compute_freshness_score(topic)
    if vs > 0:
        vs_norm = min(100.0, vs)
        return round(vs_norm * 0.7 + fresh * 0.3, 4)
    return fresh


def get_topics_from_s3(limit=50, sort_by='velocity'):
    """
    S3 api/topics.json から最新のトピック一覧を取得。
    DynamoDB フルスキャンより大幅にコスト削減（月$2.5削減）。
    sort_by='velocity' → ハイブリッド注目度（compute_attention_score 降順）日次用
    sort_by='score'    → score 降順（週次・月次用）

    注目度シグナルの設計（fetcher/scoring.py + score_utils.py 参照）:
      - velocityScore = 直近2h vs 前2h の伸び率にtier重み/メディア多様性/一次情報/
        テック一般度フィルタを乗じ、半減期12hで時間減衰した「急上昇度」（RSS派生）。
      - score        = 基礎ニュース性（メディア数×10 + log(はてブ) + 鮮度/多様性/緊急ボーナス）。
      - 鮮度         = 直近 24h 以内の記事数 × 時間減衰（compute_freshness_score）。
      - 記事数 (articleCount) を単独でランキングに使わない（記事数偏重を避ける）。

    日次選定では velocityScore=0 で大半が同点になる現象を避けるため、
    velocityScore があるときは 70:30 ブレンド、ないときは鮮度のみ。
    同点時は score を二次キー、lastArticleAt を三次キーで時系列タイブレーク。
    """
    try:
        resp  = s3.get_object(Bucket=S3_BUCKET, Key='api/topics.json')
        data  = json.loads(resp['Body'].read())
        items = data.get('topics', [])
    except Exception as e:
        print(f'[bluesky_agent] S3読み取り失敗、フォールバックなし: {e}')
        return []

    if sort_by == 'velocity':
        items.sort(
            key=lambda x: (
                compute_attention_score(x),
                float(x.get('score', 0) or 0),
                int(x.get('lastArticleAt', 0) or 0),
            ),
            reverse=True,
        )
    else:
        items.sort(key=lambda x: float(x.get('score', 0) or 0), reverse=True)

    return items[:limit]


def get_recent_posted_ids(mode: str, limit: int = 4) -> set:
    """
    指定 mode の直近 limit 件の topicId を集合で返す（重複投稿防止用・近接窓ガード）。

    設計方針:
      - TTL=30日内すべてを除外すると候補が枯渇する（ロングテールが効かなくなる）。
      - 直近 N 件だけ重複させない近接窓ガードに切り替え、
        それより前に投稿したものは「再ピックアップ可」とする。
      - 注目度（velocityScore + score）が高ければ同じトピックを再投稿しても良い。
        ただしN投稿以内の連投は読み手に冗長なので避ける。

    Args:
      mode:  'daily' | 'weekly' | 'monthly'
      limit: 直近 N 件（デフォルト 4）

    Returns:
      直近 limit 件分の topicId セット。テーブル未作成・取得失敗時は空集合（安全側）。
    """
    try:
        table  = dynamodb.Table(BLUESKY_POSTS_TABLE)
        items  = []
        kwargs = {}
        while True:
            resp = table.scan(**kwargs)
            for item in resp.get('Items', []):
                if item.get('mode') != mode:
                    continue
                if not item.get('postedAt') or not item.get('topicId'):
                    continue
                items.append(item)
            if not resp.get('LastEvaluatedKey'):
                break
            kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']
        items.sort(key=lambda x: x.get('postedAt', ''), reverse=True)
        return {it['topicId'] for it in items[:limit]}
    except Exception as e:
        print(f'[bluesky_agent] 直近{limit}件取得エラー（重複防止スキップ）: {e}')
        return set()


def get_posted_ids_within_hours(mode: str, hours: int = DUP_GUARD_HOURS) -> set:
    """指定 mode で直近 ``hours`` 時間以内に投稿された topicId のセットを返す。

    時間ベースの厳密な重複ガード (T2026-0429-K)。
    get_recent_posted_ids の近接窓ガード (件数ベース) と併用する:
      - 近接窓 (件数) = 短い周期での連投回避が目的。候補枯渇時にすぐ解除される。
      - 時間窓 (時間) = フォロワー視点で「同じネタを 1 日に複数回流さない」保証。

    Returns:
      ``hours`` 以内に投稿された topicId のセット。テーブル未作成・取得失敗時は
      空集合 (安全側 = 既存挙動を壊さない)。
    """
    try:
        table  = dynamodb.Table(BLUESKY_POSTS_TABLE)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        ids    = set()
        kwargs = {}
        while True:
            resp = table.scan(**kwargs)
            for item in resp.get('Items', []):
                if item.get('mode') != mode:
                    continue
                pt = item.get('postedAt', '')
                tid = item.get('topicId', '')
                if not pt or not tid:
                    continue
                try:
                    dt = datetime.fromisoformat(pt.replace('Z', '+00:00'))
                except Exception:
                    continue
                if dt >= cutoff:
                    ids.add(tid)
            if not resp.get('LastEvaluatedKey'):
                break
            kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']
        return ids
    except Exception as e:
        print(f'[bluesky_agent] {hours}h以内投稿ID取得エラー（重複防止スキップ）: {e}')
        return set()


def topic_updated_within_hours(topic, hours: int) -> bool:
    """トピックが直近 ``hours`` 時間以内に更新されているか判定する。

    優先順位: lastUpdated → updatedAt → lastArticleAt(epoch)
    どれも欠落 or 不正なら False (古いトピック扱いで除外側に倒す)。
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    upd = topic.get('lastUpdated') or topic.get('updatedAt') or ''
    if isinstance(upd, str) and upd:
        try:
            dt = datetime.fromisoformat(upd.replace('Z', '+00:00'))
            return dt >= cutoff
        except Exception:
            pass
    last_at = topic.get('lastArticleAt')
    if isinstance(last_at, (int, float)) and last_at > 0:
        try:
            return datetime.fromtimestamp(int(last_at), tz=timezone.utc) >= cutoff
        except Exception:
            pass
    return False


def get_last_post_time(mode: str):
    """指定 mode の直近投稿時刻（datetime, UTC）を返す。なければ None。"""
    try:
        table  = dynamodb.Table(BLUESKY_POSTS_TABLE)
        latest = None
        kwargs = {}
        while True:
            resp = table.scan(**kwargs)
            for item in resp.get('Items', []):
                if item.get('mode') != mode:
                    continue
                pt = item.get('postedAt', '')
                if not pt:
                    continue
                try:
                    dt = datetime.fromisoformat(pt.replace('Z', '+00:00'))
                except Exception:
                    continue
                if latest is None or dt > latest:
                    latest = dt
            if not resp.get('LastEvaluatedKey'):
                break
            kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']
        return latest
    except Exception as e:
        print(f'[bluesky_agent] 最終投稿時刻取得エラー（投稿継続）: {e}')
        return None


# ── レート制御の単一エントリ (T2026-0502-L 恒久対処の中核) ────────────────
def _check_rate_limit(mode: str) -> tuple[bool, str]:
    """
    BLUESKY_POSTING_CONFIG[mode] に基づき投稿可否を判定する **唯一** のエントリ。

    全 post_xxx() 関数はこの関数を冒頭で呼ぶだけで、独自のクールタイム実装を
    持たない。設定変更は BLUESKY_POSTING_CONFIG だけで完結する。

    3 つのガードを AND で全部通過したら投稿可:
      1) enabled        — False なら即停止 (kill switch)
      2) cooldown_hours — 前回同 mode 投稿から N 時間空いているか
      3) max_per_24h    — 24h 内の同 mode 投稿件数が N 件未満か (二重ガード)

    Args:
      mode: 'daily' | 'morning' | 'debut' | 'weekly' | 'monthly'

    Returns:
      (ok, reason)
        ok=True  → 投稿OK
        ok=False → reason に skip 理由（ログ出力用）
    """
    cfg = BLUESKY_POSTING_CONFIG.get(mode)
    if not cfg:
        return False, f"未定義 mode={mode!r}"

    if not cfg.get('enabled', True):
        return False, f"{mode} は無効化中 (BLUESKY_POSTING_CONFIG[{mode!r}]['enabled']=False)"

    cooldown_h = float(cfg.get('cooldown_hours', 0) or 0)
    if cooldown_h > 0:
        last = get_last_post_time(mode)
        if last is not None:
            elapsed = datetime.now(timezone.utc) - last
            cooldown = timedelta(hours=cooldown_h)
            if elapsed < cooldown:
                remain = int((cooldown - elapsed).total_seconds() / 60)
                return False, f"{mode} cooldown 中 (残り{remain}分 / 設定{cooldown_h}h)"

    cap = int(cfg.get('max_per_24h', 0) or 0)
    if cap > 0:
        recent = get_posted_ids_within_hours(mode, hours=24)
        if len(recent) >= cap:
            return False, f"{mode} 24h 内 {len(recent)}件 (上限{cap}) 到達"

    return True, "OK"


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


def fetch_image_blob(client: Client, image_url: str):
    """画像URLからblobをアップロードして返す（失敗時はNone）"""
    try:
        req = urllib.request.Request(image_url, headers={'User-Agent': 'Flotopic/1.0'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = resp.read()
        mime = 'image/jpeg'
        if image_url.lower().endswith('.png'):
            mime = 'image/png'
        elif image_url.lower().endswith('.webp'):
            mime = 'image/webp'
        blob_resp = client.upload_blob(data)
        return blob_resp.blob
    except Exception as e:
        print(f'[bluesky_agent] 画像アップロード失敗（スキップ）: {e}')
        return None


def make_link_embed(client: Client, uri: str, title: str, description: str, image_url: str = None) -> 'models.AppBskyEmbedExternal.Main':
    """flotopic.com へのリンクカード embed を生成（サムネ画像付き）"""
    thumb = None
    if image_url and client is not None:
        thumb = fetch_image_blob(client, image_url)
    external_kwargs = {
        'uri': uri,
        'title': title[:100],
        'description': description[:200],
    }
    if thumb:
        external_kwargs['thumb'] = thumb
    return models.AppBskyEmbedExternal.Main(
        external=models.AppBskyEmbedExternal.External(**external_kwargs)
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
    'くらし':       '#くらし #生活',
    '社会':         '#社会',
    'グルメ':       '#グルメ #食',
    'ファッション': '#ファッション',
}


def genre_tag(topic) -> str:
    genre = topic.get('genre', '総合')
    return GENRE_HASHTAGS.get(genre, '#ニュース')


# ── 時間帯ラベル ─────────────────────────────────────────────────────────────

def time_label() -> str:
    """現在のJST時刻から「朝」「昼」「夕」を返す"""
    jst_hour = (datetime.now(timezone.utc) + timedelta(hours=9)).hour
    if 5 <= jst_hour < 11:
        return '朝'
    elif 11 <= jst_hour < 16:
        return '昼'
    else:
        return '夕'


# ── 日次投稿: 1回の実行で1トピックを単発投稿 ────────────────────────────────

def post_daily(client, dry_run=False):
    """
    1回の実行でvocityScore最上位の未投稿トピックを1件だけ単発投稿する。
    1日3回スケジュール（JST 8:00 / 12:00 / 18:00）から呼ばれることを想定。
    各回で異なるトピックが選ばれる（投稿済みIDをDynamoDBで管理）。

    投稿フォーマット（300文字以内）:
      🔥 [朝/昼/夕]の急上昇トピック

      [タイトル]

      [要約 ~110文字]

      📄 N件の記事
      [ジャンルハッシュタグ] #Flotopic
    """
    print('[bluesky_agent] 日次投稿 開始')

    # T2026-0502-L: レート制御は BLUESKY_POSTING_CONFIG['daily'] に集約済み。
    # _check_rate_limit() が enabled / cooldown / 24h cap の3重ガードを担う。
    ok, reason = _check_rate_limit('daily')
    if not ok:
        print(f'[bluesky_agent] daily skip: {reason}')
        return

    topics            = get_topics_from_s3(limit=50, sort_by='velocity')
    recent_posted_ids = get_recent_posted_ids('daily', limit=4)
    posted_within_24h = get_posted_ids_within_hours('daily', hours=DUP_GUARD_HOURS)

    # 注目度（velocityScore→score タイブレーク）降順で並んだ topics から以下の
    # フィルタ全てを満たす最上位を選ぶ:
    #   1. lifecycle が active / cooling / 空
    #   2. 直近4件の daily 投稿に含まれていない (近接窓ガード・連投回避)
    #   3. 直近 DUP_GUARD_HOURS=24h 以内に投稿していない (時間ベース重複ガード)
    #   4. lastUpdated/lastArticleAt が DAILY_TOPIC_FRESHNESS_HOURS=24h 以内 (古いトピック除外)
    #
    # NOTE: lifecycleStatus は 48h 以内→'active', 2-7日→'cooling'。
    # 'active' のみだと48h経過後に全件除外されて投稿ゼロになるため
    # codebase 全体の定義（proc_storage.py L396, fetcher/storage.py L186）に合わせて
    # 'active', 'cooling', '' を許容する。
    #
    # T2026-0429-K で 3 と 4 を追加。フォロワー視点で「同ネタの 1 日複数回投稿」
    # と「24h 超の古ネタの再投稿」がスパムとして見える事故を防ぐ。
    candidates = [
        t for t in topics
        if t.get('lifecycleStatus', 'active') in ('active', 'cooling', '')
        and t.get('topicId') not in recent_posted_ids
        and t.get('topicId') not in posted_within_24h
        and topic_updated_within_hours(t, DAILY_TOPIC_FRESHNESS_HOURS)
    ]

    if not candidates:
        print(
            f'[bluesky_agent] 投稿対象トピックなし'
            f'（鮮度{DAILY_TOPIC_FRESHNESS_HOURS}h以内・'
            f'過去{DUP_GUARD_HOURS}h未投稿の候補なし）'
        )
        return

    # 静的HTMLが存在するトピックのみ投稿（OGPリンクカードが正しく表示される）
    topic = None
    for c in candidates:
        _tid = c.get('topicId', '')
        try:
            s3.head_object(Bucket=S3_BUCKET, Key=f'topics/{_tid}.html')
            topic = c
            break
        except Exception:
            continue

    if not topic:
        print('[bluesky_agent] 静的HTMLが存在するトピックなし（静的ページ生成待ち）')
        return

    title     = topic.get('generatedTitle') or topic.get('title', '')
    summary   = topic.get('generatedSummary') or topic.get('extractiveSummary', '')
    tid       = topic.get('topicId', '')
    image_url = topic.get('imageUrl') or ''
    url       = f'{SITE_URL}/topic.html?id={tid}'

    # T2026-0502-L: 投稿文言は BLUESKY_POSTING_TEMPLATES['daily'] に集約済。
    post_text = build_post_text('daily', topic)

    embed = make_link_embed(
        client=client,
        uri=url,
        title=truncate(title, 80),
        description=truncate(summary, 150),
        image_url=image_url,
    )

    if dry_run:
        print(f'[DRY-RUN] ({len(post_text)}文字):\n{post_text}\n  → リンクカード: {url}\n')
    else:
        resp = send_post(client, post_text, embed=embed)
        mark_as_posted(tid, 'daily')
        print(f'[bluesky_agent] 投稿完了: {resp.uri}')

    print('[bluesky_agent] 日次投稿 完了')


# ── 週次投稿: 今週の5大ストーリー ───────────────────────────────────────────

def post_weekly(client, dry_run=False):
    """
    1週間のトップ5トピック（score降順）を1投稿＋リンクカードで投稿。
    文字数計算: 見出し30 + 5行×30文字 + フッター60 ≒ 240文字（300文字以内）
    """
    print('[bluesky_agent] 週次投稿 開始')
    topics = get_topics_from_s3(limit=100, sort_by='score')

    # 過去7日以内に更新されたトピックに絞る
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    recent = []
    for t in topics:
        updated_at = t.get('lastUpdated') or t.get('updatedAt') or t.get('createdAt', '')
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

    # リンクカード: Flotopic トップページ（週次はトップページ画像なし）
    embed = make_link_embed(
        client=client,
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
    topics = get_topics_from_s3(limit=200, sort_by='score')

    # 過去30日以内に更新されたトピックに絞る
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    recent = []
    for t in topics:
        updated_at = t.get('lastUpdated') or t.get('updatedAt') or t.get('createdAt', '')
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

    embed = make_link_embed(
        client=client,
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


# ── 初回投稿 (debut): 新規トピック AI 要約完了の即時通知 ──────────────────────

def list_debut_pending() -> list:
    """
    S3 bluesky/pending/*.json の pending マーカーを古い順に取得する。

    Returns:
      [{'key': S3 key, 'topicId': str, 'createdAt': iso str}, ...]  古い→新しい順
      取得失敗時は空配列。
    """
    items = []
    try:
        paginator = s3.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=BLUESKY_PENDING_PREFIX):
            for obj in page.get('Contents', []):
                key = obj['Key']
                try:
                    body = s3.get_object(Bucket=S3_BUCKET, Key=key)['Body'].read()
                    data = json.loads(body)
                    if data.get('topicId'):
                        items.append({
                            'key':       key,
                            'topicId':   data['topicId'],
                            'createdAt': data.get('createdAt', ''),
                        })
                except Exception as e:
                    print(f'[bluesky_agent] pending マーカー読込失敗 ({key}): {e}')
    except Exception as e:
        print(f'[bluesky_agent] pending マーカー一覧取得失敗: {e}')
        return []

    items.sort(key=lambda x: x['createdAt'])
    return items


def delete_debut_marker(key: str):
    """投稿済 or 期限切れマーカーを削除する。"""
    try:
        s3.delete_object(Bucket=S3_BUCKET, Key=key)
    except Exception as e:
        print(f'[bluesky_agent] マーカー削除失敗 ({key}): {e}')


def post_debut(client, dry_run: bool = False) -> bool:
    """
    新規トピックの初回 AI 要約完了マーカー (bluesky/pending/) を 1 件投稿する。

    レート制御 (T2026-0502-L):
      BLUESKY_POSTING_CONFIG['debut'] が単一の真実の源。
      _check_rate_limit('debut') で enabled / cooldown / 24h cap の3重ガード。
      enabled=False のときは pending マーカーに触らず即 return False。

    定期投稿 (post_daily) と完全に独立したトリガー:
      - 注目度フィルタなし (新トピック登場の通知が目的)
      - 1 cron tick につき DEBUT_MAX_PER_RUN 件まで
      - DEBUT_MARKER_TTL_HOURS を超えた古いマーカーは投稿せず破棄

    Returns:
      True  = 投稿（または dry-run 出力）した。同 tick の定期投稿はスキップ推奨。
      False = 対象なし or レート制限。呼び出し側は通常の mode 別投稿に進んでよい。
    """
    print('[bluesky_agent] 初回投稿 (debut) チェック 開始')

    # 期限切れマーカーの GC は enabled / cooldown に**先行**して実施する。
    # 理由: enabled=False のとき rate-limit で早期 return すると S3 マーカーが
    # 永遠に消費されず累積する事故 (T2026-0502-L follow-up で 85件発見)。
    # GC は投稿しない安全な操作なので rate-limit 判定とは独立に走らせる。
    pending = list_debut_pending()
    if pending:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=DEBUT_MARKER_TTL_HOURS)
        fresh = []
        for m in pending:
            try:
                ca = datetime.fromisoformat(m['createdAt'].replace('Z', '+00:00'))
            except Exception:
                print(f'[bluesky_agent] 不正な createdAt のため破棄: {m["topicId"][:8]}...')
                delete_debut_marker(m['key'])
                continue
            if ca < cutoff:
                print(f'[bluesky_agent] 期限切れマーカー破棄 ({DEBUT_MARKER_TTL_HOURS}h超): {m["topicId"][:8]}...')
                delete_debut_marker(m['key'])
                continue
            fresh.append(m)
        pending = fresh

    # T2026-0502-L: enabled/cooldown/24h-cap を BLUESKY_POSTING_CONFIG に委譲。
    # GC のあとにレート判定する: enabled=False でもマーカーは TTL で掃除される。
    ok, reason = _check_rate_limit('debut')
    if not ok:
        print(f'[bluesky_agent] debut skip: {reason}')
        return False

    if not pending:
        print('[bluesky_agent] 初回投稿対象なし (期限内マーカー 0 件)')
        return False
    fresh = pending  # 以降の処理は fresh 変数を使う既存コードに合わせる

    # 既に debut 投稿済みの topicId を除外 (重複投稿防止)
    posted_debut_ids = get_recent_posted_ids('debut', limit=50)

    # topics.json から最新メタを取得 (limit を大きめに: pending は順不同でランクが低くても拾う)
    topics_index = {t.get('topicId'): t for t in get_topics_from_s3(limit=500, sort_by='velocity')}

    posted_count = 0
    for m in fresh:
        if posted_count >= DEBUT_MAX_PER_RUN:
            break

        tid = m['topicId']

        # 投稿済みなら無条件にマーカー削除
        if tid in posted_debut_ids:
            print(f'[bluesky_agent] 既投稿につきマーカー削除: {tid[:8]}...')
            delete_debut_marker(m['key'])
            continue

        topic = topics_index.get(tid)
        if not topic:
            # topics.json に居ない (アーカイブ等) → マーカー削除
            print(f'[bluesky_agent] topics.json 不在につきマーカー削除: {tid[:8]}...')
            delete_debut_marker(m['key'])
            continue

        # 投稿可否のミニマム条件
        if int(topic.get('articleCount', 0) or 0) < 3:
            print(f'[bluesky_agent] 記事数不足 (<3) でリトライ保留: {tid[:8]}...')
            continue
        if not topic.get('generatedSummary'):
            print(f'[bluesky_agent] 要約欠落でリトライ保留: {tid[:8]}...')
            continue
        if topic.get('lifecycleStatus', 'active') not in ('active', 'cooling', ''):
            print(f'[bluesky_agent] lifecycle 対象外につきマーカー削除: {tid[:8]}...')
            delete_debut_marker(m['key'])
            continue

        # 静的 HTML が無いとリンクカードが死ぬ → 生成待ち (マーカー残してリトライ)
        try:
            s3.head_object(Bucket=S3_BUCKET, Key=f'topics/{tid}.html')
        except Exception:
            print(f'[bluesky_agent] 静的HTML未生成でリトライ保留: {tid[:8]}...')
            continue

        title     = topic.get('generatedTitle') or topic.get('title', '')
        summary   = topic.get('generatedSummary') or topic.get('extractiveSummary', '')
        image_url = topic.get('imageUrl') or ''
        url       = f'{SITE_URL}/topic.html?id={tid}'

        # T2026-0502-L: 投稿文言は BLUESKY_POSTING_TEMPLATES['debut'] に集約済。
        post_text = build_post_text('debut', topic)

        embed = make_link_embed(
            client=client,
            uri=url,
            title=truncate(title, 80),
            description=truncate(summary, 150),
            image_url=image_url,
        )

        if dry_run:
            print(f'[DRY-RUN debut] ({len(post_text)}文字):\n{post_text}\n  → リンクカード: {url}\n')
        else:
            resp = send_post(client, post_text, embed=embed)
            mark_as_posted(tid, 'debut')
            print(f'[bluesky_agent] 初回投稿完了: {resp.uri}')

        delete_debut_marker(m['key'])
        posted_count += 1

    print(f'[bluesky_agent] 初回投稿 (debut) 完了: {posted_count}件投稿')
    return posted_count > 0


# ── 朝の定期投稿 (T193): JST 08:00 EventBridge cron で起動 ─────────────────

def post_morning(client, dry_run=False):
    """
    JST 08:00 に EventBridge cron で 1 日 1 回起動される朝の定期投稿。
    過去 MORNING_RECENT_HOURS 以内に更新されたトピックのうち velocityScore 最大の
    1 件を「🌅 今朝の動き」プレフィックスで投稿する。

    daily / debut とは独立した別系統:
      - mode='morning' で BLUESKY_POSTS_TABLE に記録
      - レート制御は BLUESKY_POSTING_CONFIG['morning'] (cron 揺らぎ + 二重発火対策)
      - 静的HTMLが存在するトピックのみ投稿 (OGP リンクカード正しく表示)
    """
    print('[bluesky_agent] 朝投稿 開始')

    # T2026-0502-L: レート制御は BLUESKY_POSTING_CONFIG['morning'] に集約済み。
    ok, reason = _check_rate_limit('morning')
    if not ok:
        print(f'[bluesky_agent] morning skip: {reason}')
        return

    topics = get_topics_from_s3(limit=100, sort_by='velocity')
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MORNING_RECENT_HOURS)

    def _topic_updated_at(t):
        upd = t.get('lastUpdated') or t.get('updatedAt') or ''
        if isinstance(upd, str) and upd:
            try:
                return datetime.fromisoformat(upd.replace('Z', '+00:00'))
            except Exception:
                return None
        last_at = t.get('lastArticleAt')
        if isinstance(last_at, (int, float)) and last_at > 0:
            try:
                return datetime.fromtimestamp(int(last_at), tz=timezone.utc)
            except Exception:
                return None
        return None

    recent_posted_ids = get_recent_posted_ids('morning', limit=3)
    posted_within_24h = get_posted_ids_within_hours('morning', hours=DUP_GUARD_HOURS)

    fresh = []
    for t in topics:
        if t.get('lifecycleStatus', 'active') not in ('active', 'cooling', ''):
            continue
        tid = t.get('topicId')
        if tid in recent_posted_ids or tid in posted_within_24h:
            continue
        dt = _topic_updated_at(t)
        if dt is None or dt < cutoff:
            continue
        fresh.append(t)

    if not fresh:
        print(f'[bluesky_agent] 過去{MORNING_RECENT_HOURS}h 以内の動きトピックなし → skip')
        return

    topic = None
    for c in fresh:
        tid = c.get('topicId', '')
        if not tid:
            continue
        try:
            s3.head_object(Bucket=S3_BUCKET, Key=f'topics/{tid}.html')
            topic = c
            break
        except Exception:
            continue

    if not topic:
        print('[bluesky_agent] 静的HTMLが存在する朝トピックなし → skip')
        return

    title     = topic.get('generatedTitle') or topic.get('title', '')
    tid       = topic.get('topicId', '')
    image_url = topic.get('imageUrl') or ''
    url       = f'{SITE_URL}/topic.html?id={tid}'

    # T2026-0502-L: 投稿文言は BLUESKY_POSTING_TEMPLATES['morning'] に集約済。
    post_text = build_post_text('morning', topic)

    embed = make_link_embed(
        client=client,
        uri=url,
        title=truncate(title, 80),
        description=truncate(summary, 150),
        image_url=image_url,
    )

    if dry_run:
        print(f'[DRY-RUN morning] ({len(post_text)}文字):\n{post_text}\n  → リンクカード: {url}\n')
    else:
        resp = send_post(client, post_text, embed=embed)
        mark_as_posted(tid, 'morning')
        print(f'[bluesky_agent] 朝投稿完了: {resp.uri}')

    print('[bluesky_agent] 朝投稿 完了')


# ── メイン ───────────────────────────────────────────────────────────────────

def run(mode: str = 'daily', dry_run: bool = False) -> dict:
    """BlueSky 投稿のメインロジック。CLI / Lambda 両方から呼ばれる。

    Args:
        mode: 'daily' / 'weekly' / 'monthly' / 'morning'
        dry_run: True なら実投稿せずに本文を print

    Returns:
        実行サマリ dict (Lambda レスポンス用)。
    """
    if mode not in ('daily', 'weekly', 'monthly', 'morning'):
        raise ValueError(f"invalid mode: {mode!r}")

    started_at = datetime.now(timezone.utc).isoformat()
    print(f'[bluesky_agent] モード={mode} / dry_run={dry_run} / 開始: {started_at}')

    try:
        client = get_bluesky_client() if not dry_run else None
    except ValueError as e:
        err = str(e)
        print(f'[bluesky_agent] 認証エラー: {err}')
        notify_slack_error(f'BlueSky認証エラー: {err}')
        return {'ok': False, 'mode': mode, 'error': f'auth: {err}'}

    debut_posted = False
    try:
        # T2026-0428-AS: 初回投稿 (debut) チェックを mode 問わず先に実行する。
        # 同一 cron tick で 2 件投稿しないため、debut が走ったら定期投稿はスキップ。
        debut_posted = post_debut(client, dry_run=dry_run)
        if debut_posted:
            print(f'[bluesky_agent] debut 投稿実行のため mode={mode} の定期投稿は次回 tick へ繰り越し')
        elif mode == 'daily':
            post_daily(client, dry_run=dry_run)
        elif mode == 'weekly':
            post_weekly(client, dry_run=dry_run)
        elif mode == 'monthly':
            post_monthly(client, dry_run=dry_run)
        elif mode == 'morning':
            post_morning(client, dry_run=dry_run)
    except Exception:
        import traceback
        err_detail = traceback.format_exc()
        print(f'[bluesky_agent] 予期しないエラー:\n{err_detail}')
        notify_slack_error(f'モード={mode} で予期しないエラー\n```{err_detail[:500]}```')
        return {'ok': False, 'mode': mode, 'error': err_detail[:500]}

    finished_at = datetime.now(timezone.utc).isoformat()
    print(f'[bluesky_agent] 完了: {finished_at}')
    return {
        'ok': True,
        'mode': mode,
        'dry_run': dry_run,
        'debut_posted': debut_posted,
        'started_at': started_at,
        'finished_at': finished_at,
    }


def main():
    parser = argparse.ArgumentParser(description='Flotopic BlueSky 自動投稿エージェント')
    parser.add_argument(
        '--mode', required=True,
        choices=['daily', 'weekly', 'monthly', 'morning'],
        help='投稿モード: daily=日次, weekly=週次, monthly=月次, morning=朝のみ (T193)',
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='実際には投稿せず投稿内容をターミナルに出力する',
    )
    args = parser.parse_args()
    result = run(mode=args.mode, dry_run=args.dry_run)
    if not result.get('ok'):
        sys.exit(1)


if __name__ == '__main__':
    main()
