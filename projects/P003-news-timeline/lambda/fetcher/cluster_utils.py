"""
cluster_utils.py — 記事クラスタリング（Union-Find）と類似度計算
"""
import re
import hashlib
from collections import Counter

from config import STOP_WORDS, SYNONYMS, JACCARD_THRESHOLD, MAX_CLUSTER_SIZE


_LIVE_PREFIX = re.compile(r'^【(中継|速報|更新|独自|詳報|続報|緊急|号外)[^】]*】')
_KATAKANA_ENTITY = re.compile(r'^[゠-ヿ]{3,}$')  # 3文字以上のカタカナ固有名詞（トランプ/プーチン等）
_ENTITY_MERGE_THRESHOLD = 0.12  # 固有名詞1語共有の場合の緩和閾値
_ENTITY_MERGE_MAX_WORDS  = 5    # 対象は短い記事のみ

def normalize(text):
    text = _LIVE_PREFIX.sub('', text).strip()  # 【中継】【速報】等のプレフィックスを除去してから比較
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
            wi = normalize(articles[i]['title']) - STOP_WORDS
            wj = normalize(articles[j]['title']) - STOP_WORDS
            shared = wi & wj
            union_sz = len(wi | wj)
            # カタカナ固有名詞（3文字以上）を1語共有し、かつ両記事が短い場合は緩和閾値で結合
            katakana_entities = {w for w in shared if _KATAKANA_ENTITY.match(w)}
            if (len(shared) == 1 and katakana_entities
                    and len(wi) <= _ENTITY_MERGE_MAX_WORDS
                    and len(wj) <= _ENTITY_MERGE_MAX_WORDS
                    and union_sz > 0
                    and 1.0 / union_sz >= _ENTITY_MERGE_THRESHOLD):
                pass  # → merge below
            elif len(shared) < 2:
                continue
            if union_sz == 0:
                continue
            jac = len(shared) / union_sz
            threshold = _ENTITY_MERGE_THRESHOLD if (len(shared) == 1 and katakana_entities) else JACCARD_THRESHOLD
            if jac >= threshold:
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
