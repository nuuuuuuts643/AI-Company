"""
text_utils.py — テキスト処理・ソース名抽出・エンティティ・要約生成
"""
import re
import urllib.parse
from collections import Counter

from config import (
    MEDIA_NS, SOURCE_NAME_MAP, GENRE_KEYWORDS, ENTITY_PATTERNS,
)


def _domain_to_name(domain: str) -> str:
    domain = domain.lower()
    if domain in SOURCE_NAME_MAP and SOURCE_NAME_MAP[domain]:
        return SOURCE_NAME_MAP[domain]
    d = re.sub(r'^www\.', '', domain)
    d = re.sub(r'\.(co\.jp|or\.jp|ne\.jp|com|jp|net|org|io)$', '', d)
    d = re.sub(r'\.(co|or|ne)$', '', d)
    return d if d else ''


def extract_source_name(item, article_link: str, feed_url: str) -> str:
    # 1. <source> 要素のテキスト（Google以外ならそのまま使う）
    source_el = item.find('source')
    if source_el is not None:
        source_text = (source_el.text or '').strip()
        if source_text and 'google' not in source_text.lower():
            return source_text.split('|')[0].strip()

        source_url = source_el.get('url', '')
        if source_url:
            try:
                src_domain = urllib.parse.urlparse(source_url).netloc.lower()
                if src_domain and 'google' not in src_domain:
                    name = _domain_to_name(src_domain)
                    if name:
                        return name
            except Exception:
                pass

    # 2. article_link のドメインが Google 以外ならそこから取得
    try:
        domain = urllib.parse.urlparse(article_link).netloc.lower()
        if domain and 'google' not in domain:
            name = _domain_to_name(domain)
            if name:
                return name
    except Exception:
        pass

    # 3. Google News の場合: タイトル末尾の " - メディア名" を抽出
    try:
        domain = urllib.parse.urlparse(article_link).netloc.lower()
        if 'google' in domain or 'google' in feed_url:
            title = (item.findtext('title') or '').strip()
            for pat in [r'\s[-–―]\s([^-–―｜|]+)$', r'[｜|]([^｜|]+)$']:
                match = re.search(pat, title)
                if match:
                    candidate = match.group(1).strip()
                    if candidate and len(candidate) < 30:
                        return candidate
    except Exception:
        pass

    # 4. フィードドメインから推定
    try:
        feed_domain = urllib.parse.urlparse(feed_url).netloc.lower()
        if feed_domain and 'google' not in feed_domain:
            name = _domain_to_name(feed_domain)
            if name:
                return name
    except Exception:
        pass

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


_KW_STOPWORDS = {
    'の', 'に', 'は', 'を', 'が', 'で', 'と', 'も', 'する', 'した', 'して',
    'から', 'より', 'まで', 'など', 'ため', 'こと', 'もの', 'ある', 'いる',
    'なる', 'れる', 'られる', 'について', 'による', 'として', 'において',
    'という', 'および', 'また', 'さらに', 'ただし', 'による',
    'について', '向け', '対し', '日本', '今', '年', '月', '日', '円',
    '社', '氏', '同', '新', '元', '前', '後', '以上', '以下', '問題',
    '発表', '報道', '関連', '情報', '確認', '実施', '開始', '終了',
}
_KW_MAX_COUNT = 10


def extract_trending_keywords(topics: list) -> list:
    word_counter = Counter()
    for topic in topics:
        title = topic.get('generatedTitle') or topic.get('title', '')
        words = re.findall(r'[ァ-ヶー]{3,}|[一-龯々]{2,}|[A-Za-z]{4,}', title)
        for word in words:
            if word not in _KW_STOPWORDS and len(word) >= 2:
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
