import re
import hashlib
import time
import json
import urllib.request
import urllib.parse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from email.utils import parsedate_tz, mktime_tz
from datetime import datetime, timezone

from config import (
    STOP_WORDS, SYNONYMS, GENRE_KEYWORDS, ENTITY_PATTERNS,
    MEDIA_NS, SOURCE_NAME_MAP, URGENT_WORDS,
    JACCARD_THRESHOLD, MAX_CLUSTER_SIZE,
)


def normalize(text):
    text = re.sub(r'[【】「」『』（）()\[\]！？!?\s　・]+', ' ', text.lower())
    words = set()
    for w in text.split():
        if len(w) > 1:
            words.add(SYNONYMS.get(w, w))
    return words


def jaccard(a, b):
    sa, sb = normalize(a), normalize(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def topic_fingerprint(articles):
    counter = Counter()
    for a in articles:
        words = normalize(a['title']) - STOP_WORDS
        counter.update(w for w in words if len(w) > 2)
    top = sorted(w for w, _ in counter.most_common(10) if counter[w] >= 1)[:5]
    if not top:
        top = [articles[0]['title'][:30]]
    return hashlib.md5(' '.join(top).encode()).hexdigest()[:16]


def extract_source_name(item, article_link: str, feed_url: str) -> str:
    source_el = item.find('source')
    if source_el is not None:
        source_text = (source_el.text or '').strip()
        if source_text and 'google' not in source_text.lower():
            return source_text

    try:
        domain = urllib.parse.urlparse(article_link).netloc.lower()
        if domain in SOURCE_NAME_MAP and SOURCE_NAME_MAP[domain]:
            return SOURCE_NAME_MAP[domain]
        if 'google' in domain:
            title = (item.findtext('title') or '').strip()
            match = re.search(r'\s[-–]\s([^\-–]+)$', title)
            if match:
                return match.group(1).strip()
    except Exception:
        pass

    try:
        feed_domain = urllib.parse.urlparse(feed_url).netloc.lower()
        if feed_domain in SOURCE_NAME_MAP and SOURCE_NAME_MAP[feed_domain]:
            return SOURCE_NAME_MAP[feed_domain]
    except Exception:
        pass

    try:
        domain = urllib.parse.urlparse(article_link).netloc
        domain = re.sub(r'^www\.', '', domain)
        domain = re.sub(r'\.(co\.jp|com|jp|net|org)$', '', domain)
        return domain if domain else 'Unknown'
    except Exception:
        return 'Unknown'


def extract_rss_image(item):
    mc = item.find('media:content', MEDIA_NS)
    if mc is not None and mc.get('url') and mc.get('medium', '') in ('image', ''):
        return mc.get('url')
    mt = item.find('media:thumbnail', MEDIA_NS)
    if mt is not None and mt.get('url'):
        return mt.get('url')
    enc = item.find('enclosure')
    if enc is not None and enc.get('type', '').startswith('image'):
        return enc.get('url')
    return None


def cluster(articles):
    n = len(articles)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    cluster_size = {i: 1 for i in range(n)}

    for i in range(n):
        for j in range(i + 1, n):
            ri, rj = find(i), find(j)
            if ri == rj:
                continue
            if cluster_size.get(ri, 1) + cluster_size.get(rj, 1) > MAX_CLUSTER_SIZE:
                continue
            if jaccard(articles[i]['title'], articles[j]['title']) >= JACCARD_THRESHOLD:
                new_size = cluster_size.get(ri, 1) + cluster_size.get(rj, 1)
                union(i, j)
                cluster_size[find(i)] = new_size

    groups_dict = {}
    for i in range(n):
        root = find(i)
        if root not in groups_dict:
            groups_dict[root] = []
        groups_dict[root].append(articles[i])

    return list(groups_dict.values())


def dominant_genres(articles, max_genres=2):
    all_titles = ' '.join(a['title'] for a in articles)
    scores = {}
    for genre, keywords in GENRE_KEYWORDS.items():
        hit = sum(1 for kw in keywords if kw in all_titles)
        if hit >= 2:
            scores[genre] = hit
    if scores:
        top = sorted(scores, key=scores.get, reverse=True)[:max_genres]
        return top
    return [Counter(a['genre'] for a in articles).most_common(1)[0][0]]


def dominant_lang(articles):
    return Counter(a.get('lang', 'ja') for a in articles).most_common(1)[0][0]


def source_count(articles):
    return len({a['source'] for a in articles})


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


def source_diversity_score(articles: list) -> float:
    if not articles:
        return 1.0
    sources = [a.get('source', '') for a in articles]
    counts = Counter(sources)
    top_source_ratio = counts.most_common(1)[0][1] / len(sources)
    return 0.8 if top_source_ratio > 0.6 else 1.0


def compute_lifecycle_status(score: int, last_article_ts: int, velocity_score: int, total_articles: int) -> str:
    now = int(time.time())
    hours_since = (now - last_article_ts) / 3600
    days_since  = hours_since / 24

    if hours_since < 48:
        return 'active'
    elif days_since < 7:
        return 'cooling'
    elif days_since >= 14 and velocity_score <= 0:
        return 'archived'
    else:
        return 'cooling'


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

    base = media * 10 + hb

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


_KW_STOPWORDS = {
    'の', 'に', 'は', 'を', 'が', 'で', 'と', 'も', 'する', 'した', 'して',
    'から', 'より', 'まで', 'など', 'ため', 'こと', 'もの', 'ある', 'いる',
    'なる', 'れる', 'られる', 'について', 'による', 'として', 'において',
    'という', 'および', 'また', 'さらに', 'ただし', 'による',
    'について', '向け', '対し', '日本', '今', '年', '月', '日', '円',
    '社', '氏', '同', '新', '元', '前', '後', '以上', '以下', '問題',
    '発表', '報道', '関連', '情報', '確認', '実施', '開始', '終了',
}
_KW_MIN_LEN   = 2
_KW_MAX_COUNT = 10


def extract_trending_keywords(topics: list) -> list:
    word_counter = Counter()
    for topic in topics:
        title = topic.get('generatedTitle') or topic.get('title', '')
        words = re.findall(r'[ァ-ヶー]{3,}|[一-龯々]{2,}|[A-Za-z]{4,}', title)
        for word in words:
            if word not in _KW_STOPWORDS and len(word) >= _KW_MIN_LEN:
                word_counter[word] += 1
    keywords = [
        {'keyword': w, 'count': c}
        for w, c in word_counter.most_common(_KW_MAX_COUNT * 3)
        if c >= 2
    ][:_KW_MAX_COUNT]
    return keywords


def extract_entities(text: str) -> set:
    entities = set()
    for pattern in ENTITY_PATTERNS:
        if re.search(pattern, text):
            canonical = pattern.split('|')[0]
            entities.add(canonical)
    return entities


def find_related_topics(topics: list, max_related: int = 5) -> dict:
    topic_entities = {}
    for t in topics:
        title = t.get('generatedTitle') or t.get('title', '')
        topic_entities[t['topicId']] = extract_entities(title)

    related = {}
    for t in topics:
        tid = t['topicId']
        my_entities = topic_entities.get(tid, set())
        if not my_entities:
            related[tid] = []
            continue

        candidates = []
        for other in topics:
            oid = other['topicId']
            if oid == tid:
                continue
            other_entities = topic_entities.get(oid, set())
            shared = my_entities & other_entities
            GENERIC = {'ai', 'it', 'ec', 'pc', 'sns', 'dx'}
            meaningful = {e for e in shared if len(e) > 1 and e.lower() not in GENERIC}
            if len(meaningful) >= 2 or (len(meaningful) == 1 and len(shared) >= 2):
                candidates.append({
                    'topicId': oid,
                    'title': other.get('generatedTitle') or other.get('title', ''),
                    'sharedEntities': list(meaningful or shared),
                    'overlapScore': len(meaningful) + len(shared),
                })

        candidates.sort(key=lambda x: x['overlapScore'], reverse=True)
        related[tid] = candidates[:max_related]

    return related


def detect_topic_hierarchy(topics: list, topic_entities: dict) -> dict:
    parent_map = {}
    sorted_topics = sorted(topics, key=lambda t: int(t.get('score', 0)), reverse=True)

    for i, topic_a in enumerate(sorted_topics):
        tid_a = topic_a['topicId']
        entities_a = topic_entities.get(tid_a, set())
        score_a = int(topic_a.get('score', 0))

        if len(entities_a) < 2:
            continue

        for topic_b in sorted_topics[i + 1:]:
            tid_b = topic_b['topicId']
            if tid_b in parent_map:
                continue

            entities_b = topic_entities.get(tid_b, set())
            if not entities_b:
                continue

            score_b = int(topic_b.get('score', 0))

            if entities_b.issubset(entities_a) and score_a > score_b and len(entities_a) > len(entities_b):
                parent_map[tid_b] = tid_a

    return parent_map


def clean_title(title):
    t = re.sub(r'\s*[-－–|｜]\s*[^\s].{1,25}$', '', title).strip()
    t = re.sub(r'^\[.{1,20}\]\s*', '', t).strip()
    return t or title


def extractive_title(articles):
    if not articles:
        return ''
    first = clean_title(articles[0]['title'])
    return first[:40] + ('…' if len(first) > 40 else '')


def extractive_summary(articles):
    if not articles:
        return None
    sorted_arts = sorted(articles, key=lambda a: a.get('publishedAt', ''))
    seen = set()
    lines = []
    sources = set()
    for a in sorted_arts[:15]:
        t = clean_title(a.get('title', ''))
        src = a.get('source', '')
        if t and t not in seen:
            seen.add(t)
            lines.append(t)
            if src:
                sources.add(src)
        if len(lines) >= 6:
            break
    if not lines:
        return None
    if len(lines) == 1:
        return lines[0]
    lead = lines[0]
    mid = lines[1:-1]
    last = lines[-1]
    src_list = '、'.join(list(sources)[:3])
    mid_text = ('また、' + '、'.join(f'「{l[:30]}」' for l in mid) + 'など') if mid else ''
    closing = f'最新では「{last[:40]}」と報じられている。' if last != lead else ''
    src_note = f'（{src_list} ほか{len(articles)}件）' if src_list else f'（{len(articles)}件）'
    return f'{lead}。{mid_text}{closing}{src_note}'
