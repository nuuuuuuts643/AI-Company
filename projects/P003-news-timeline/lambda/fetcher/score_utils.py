"""
score_utils.py — スコア計算・時間減衰・ライフサイクル判定の純関数群
"""
import json
import math
import time
import urllib.request
import urllib.parse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_tz, mktime_tz
from urllib.parse import urlparse

from config import URGENT_WORDS

# ──────────────────────────────────────────────────────────
# メディアカテゴリ分類（ドメインベース）
# カテゴリA: 公共放送（最高信頼度）
# カテゴリB: 全国紙・通信社
# カテゴリC: テックメディア（技術ニュースに偏重）
# ──────────────────────────────────────────────────────────
_MEDIA_CAT_A = frozenset([
    'nhk.or.jp',
])

_MEDIA_CAT_B = frozenset([
    'asahi.com',
    'yomiuri.co.jp',
    'mainichi.jp',
    'nikkei.com',
    'sankei.com',
    'reuters.com',
    'kyodo.jp',
    'nordot.app',   # 共同通信配信
    'jiji.com',
])

_MEDIA_CAT_C = frozenset([
    'itmedia.co.jp',
    'techcrunch.jp',
    'techcrunch.com',
    'gizmodo.jp',
    'gigazine.net',
    'ascii.jp',
    'cnet.com',
    'impress.co.jp',
])

# ──────────────────────────────────────────────────────────
# 一次情報ソースドメイン（eTLD+1 ホワイトリスト）
# T2026-0428-AN: 信頼スコアで一次情報を優遇するための物理判定。
# - URL のドメインで照合（source 名文字列での偽装を防ぐ）
# - サブドメイン許容（例: www3.nhk.or.jp）
# - 偽装ドメイン（例: nhk.or.jp.evil.com）は弾く（_domain_in_cat suffix チェック）
# 著作権法32条「引用」として利用、出典明示必須（フロント側で必ず source 名を表示）。
# ──────────────────────────────────────────────────────────
PRIMARY_SOURCE_DOMAINS = frozenset([
    # 公共放送・通信社（最高信頼）
    'nhk.or.jp',
    'kyodo.jp',
    'nordot.app',       # 共同通信配信
    'jiji.com',
    # 全国紙
    'asahi.com',
    'yomiuri.co.jp',
    'mainichi.jp',
    'nikkei.com',
    'sankei.com',
    # 海外主要通信社・報道
    'reuters.com',
    'apnews.com',
    'bbc.com',
    'bbc.co.uk',
    'bloomberg.com',
    'bloomberg.co.jp',
    'afp.com',
    'wsj.com',
    'ft.com',
])

# 政府・公式機関ドメインの suffix（go.jp = 日本政府専用 TLD、.gov = 米国政府）
_PRIMARY_GOV_SUFFIXES = ('.go.jp', '.gov')


def _get_domain(url: str) -> str:
    if not url:
        return ''
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ''


def _domain_in_cat(netloc: str, cat: frozenset) -> bool:
    return any(netloc == d or netloc.endswith('.' + d) for d in cat)


def is_primary_source(url) -> bool:
    """
    記事 URL のドメインが一次情報ソースかどうかを判定する。

    判定方針:
      - eTLD+1 ホワイトリスト（PRIMARY_SOURCE_DOMAINS）に完全一致 or サブドメイン
      - 政府ドメイン（.go.jp / .gov）の suffix
      - URL が None / 空 / パース失敗 → False（安全側）
      - source 名文字列（"NHK" 等）は使わない（偽装防止）

    Args:
      url: 記事 URL（http(s)://...）

    Returns:
      True なら一次情報源、False なら一次情報源ではない or 判定不能。
    """
    if not url or not isinstance(url, str):
        return False
    try:
        netloc = urlparse(url).netloc.lower()
    except Exception:
        return False
    if not netloc:
        return False
    # ポート除去
    if ':' in netloc:
        netloc = netloc.split(':', 1)[0]
    if _domain_in_cat(netloc, PRIMARY_SOURCE_DOMAINS):
        return True
    for suf in _PRIMARY_GOV_SUFFIXES:
        if netloc.endswith(suf):
            return True
    return False


def hatena_count(url):
    try:
        api = 'https://b.hatena.ne.jp/entry/jsonlite/?url=' + urllib.parse.quote(url, safe='')
        req = urllib.request.Request(api, headers={'User-Agent': 'Flotopic/1.0'})
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read())
        return int(data.get('count') or 0)
    except Exception:
        return 0


def _parse_pubdate_ts(pubdate: str) -> int:
    if not pubdate:
        return 0
    try:
        tpl = parsedate_tz(pubdate)
        if tpl:
            return mktime_tz(tpl)
    except Exception:
        pass
    try:
        return int(datetime.fromisoformat(pubdate.replace('Z', '+00:00')).timestamp())
    except Exception:
        return 0


def apply_time_decay(score: int, last_article_ts: int) -> int:
    if last_article_ts == 0:
        return score
    now = int(time.time())
    hours_old = (now - last_article_ts) / 3600

    if hours_old < 2:
        decay = 1.0
    elif hours_old < 6:
        decay = 0.85
    elif hours_old < 24:
        decay = 0.65
    elif hours_old < 48:
        decay = 0.30
    elif hours_old < 72:
        decay = 0.12
    else:
        decay = 0.04

    return max(1, int(score * decay))


def apply_velocity_decay(velocity_score: float, last_updated_iso: str) -> float:
    """
    lastUpdated からの経過時間に応じて velocityScore を指数減衰させる。
    半減期 12時間: t=12h→×0.50, t=24h→×0.25, t=48h→×0.063

    設計上の注意:
      - DynamoDB には書き戻さない（表示用スコアの調整のみ）
      - 今回の fetcher run で更新されたトピックには適用しないこと
        （handler.py 側で current_run_tids を除外して呼ぶ）
    """
    vs = float(velocity_score or 0)
    if vs == 0 or not last_updated_iso:
        return vs
    try:
        lu = datetime.fromisoformat(last_updated_iso)
        if lu.tzinfo is None:
            lu = lu.replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - lu).total_seconds() / 3600
        if age_hours <= 0:
            return vs
        decay = math.exp(-age_hours * math.log(2) / 12.0)
        return round(vs * decay, 4)
    except Exception:
        return vs


def calc_velocity_score(articles: list) -> int:
    now = int(time.time())
    recent = sum(1 for a in articles if now - a.get('published_ts', 0) < 7200)
    prev   = sum(1 for a in articles if 7200 <= now - a.get('published_ts', 0) < 14400)

    if prev == 0 and recent > 0:
        return min(100, recent * 20)
    elif prev == 0:
        return 0

    velocity = int(((recent - prev) / prev) * 100)
    return max(-100, min(100, velocity))


def source_count(articles):
    return len({a['source'] for a in articles})


def source_diversity_score(articles: list) -> float:
    """
    メディアカテゴリに基づく多様性乗数を返す。

    採点ロジック:
      カテゴリA(公共放送)1つ以上   → +2.0
      カテゴリB(全国紙・通信社)2社以上 → +1.5
      A+B合計3媒体以上          → +1.0 追加ボーナス
      カテゴリCのみ(テック専門)   → 0.3（テック偏重を抑制）
    """
    if not articles:
        return 1.0

    domains = {_get_domain(a.get('url', '')) for a in articles if a.get('url')}
    domains.discard('')

    cat_a = any(_domain_in_cat(d, _MEDIA_CAT_A) for d in domains)
    cat_b_domains = {d for d in domains if _domain_in_cat(d, _MEDIA_CAT_B)}
    cat_c_domains = {d for d in domains if _domain_in_cat(d, _MEDIA_CAT_C)}
    other_domains = domains - cat_c_domains

    # テックメディアのみの場合は抑制（ソース集中ペナルティより優先）
    if not cat_a and not cat_b_domains and cat_c_domains and not other_domains:
        return 0.3

    multiplier = 1.0
    if cat_a:
        multiplier += 2.0
    if len(cat_b_domains) >= 2:
        multiplier += 1.5
    ab_count = (1 if cat_a else 0) + len(cat_b_domains)
    if ab_count >= 3:
        multiplier += 1.0

    return round(multiplier, 2)


def calc_score(articles):
    media = source_count(articles)
    jp_articles = [a for a in articles if '.jp' in a.get('url', '') or 'nhk' in a.get('url', '')]
    urls = [a['url'] for a in jp_articles[:3]]
    hb = 0
    if urls:
        with ThreadPoolExecutor(max_workers=len(urls)) as ex:
            for count in as_completed([ex.submit(hatena_count, u) for u in urls], timeout=6):
                try:
                    hb += count.result()
                except Exception:
                    pass

    # はてなブックマークは上限30点・対数スケールで加算（テック偏重を防止）
    hb_score = min(int(math.log1p(hb) * 6), 30) if hb > 0 else 0
    base = media * 10 + hb_score

    now_ts = datetime.now(timezone.utc).timestamp()
    recency_bonus = False
    for a in articles:
        ts = a.get('published_ts', 0)
        if ts and (now_ts - ts) <= 21600:
            recency_bonus = True
            break

    diversity_bonus = media >= 3
    all_titles = ' '.join(a['title'] for a in articles)
    urgent_bonus = any(w in all_titles for w in URGENT_WORDS)

    multiplier = 1.0
    if recency_bonus:
        multiplier *= 1.20
    if diversity_bonus:
        multiplier *= 1.10
    if urgent_bonus:
        multiplier *= 1.15

    score = int(base * multiplier)
    return score, media, hb


def sort_by_pubdate(articles):
    def get_ts(a):
        return a.get('published_ts') or a.get('publishedAt') or 0
    return sorted(articles, key=get_ts, reverse=True)


def compute_lifecycle_status(score: int, last_article_ts: int, velocity_score: int, total_articles: int) -> str:
    now = int(time.time())
    hours_since = (now - last_article_ts) / 3600
    days_since  = hours_since / 24

    if hours_since < 48:
        return 'active'
    elif days_since < 7:
        return 'cooling'
    elif velocity_score <= 0:
        return 'archived'
    else:
        return 'cooling'
