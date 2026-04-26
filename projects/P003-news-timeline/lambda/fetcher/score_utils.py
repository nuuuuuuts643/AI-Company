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

from config import URGENT_WORDS


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
        return mktime_tz(tpl) if tpl else 0
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
    if not articles:
        return 1.0
    sources = [a.get('source', '') for a in articles]
    counts = Counter(sources)
    top_source, top_count = counts.most_common(1)[0]
    top_source_ratio = top_count / len(sources)
    # NHKは権威性は高いが単独支配は減点（多様な視点がないトピックを下げる）
    if top_source_ratio > 0.7:
        return 0.65
    elif top_source_ratio > 0.5:
        return 0.80
    return 1.0


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
        try:
            tpl = parsedate_tz(a.get('pubDate', ''))
            if tpl and (now_ts - mktime_tz(tpl)) <= 21600:
                recency_bonus = True
                break
        except Exception:
            pass

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
        try:
            tpl = parsedate_tz(a.get('pubDate', ''))
            return mktime_tz(tpl) if tpl else 0
        except Exception:
            return 0
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
