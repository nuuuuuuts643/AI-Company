"""
cluster_utils.py — 記事クラスタリング（Union-Find）と類似度計算
"""
import re
import hashlib
from collections import Counter

from config import STOP_WORDS, SYNONYMS, JACCARD_THRESHOLD, MAX_CLUSTER_SIZE


_LIVE_PREFIX = re.compile(r'^【(中継|速報|更新|独自|詳報|続報|緊急|号外)[^】]*】')
_KATAKANA_ENTITY = re.compile(r'^[゠-ヿ]{3,}$')  # 3文字以上のカタカナ固有名詞（トランプ/プーチン等）
_ENTITY_MERGE_THRESHOLD = 0.20  # 固有名詞1語共有の場合の緩和閾値（union_sz<=5 のみ）
_ENTITY_MERGE_MAX_WORDS  = 5    # 対象は短い記事のみ

# chunk-based similarity（スペースなし日本語タイトル向けフォールバック）
_KATAKANA_RUN = re.compile(r'[ァ-ヴーｦ-ﾟ]{3,}')
_KANJI_RUN    = re.compile(r'[一-鿿々〆〇]{2,}')
_CHUNK_THRESHOLD = 0.30  # 2語以上の固有語共有を要件にしているため誤クラスタはほぼ起きない
# 高頻度すぎて識別力のない一般語を除外
_CHUNK_COMMON = {'大統領', '首相', '大臣', '政府', '国会', '議員', '社長', '会長',
                 '委員会', '知事', '市長', '内閣', '官房', '大使', '長官',
                 '日本', '米国', '中国', '東京', '大阪', '会社', '企業', '事件', '事故',
                 '発表', '開始', '実施', '決定', '対応', '影響', '問題', '検討', '対策'}

def normalize(text):
    text = _LIVE_PREFIX.sub('', text).strip()  # 【中継】【速報】等のプレフィックスを除去してから比較
    text = re.sub(r'[【】「」『』（）()\[\]！？!?\s　・]+', ' ', text.lower())
    words = set()
    for w in text.split():
        if len(w) > 1:
            words.add(SYNONYMS.get(w, w))
    return words


def topic_fingerprint(articles):
    counter = Counter()
    for a in articles:
        words = normalize(a['title']) - STOP_WORDS
        counter.update(w for w in words if len(w) > 2)
    top = sorted(w for w, _ in counter.most_common(10) if counter[w] >= 1)[:5]
    if not top:
        top = [articles[0]['title'][:30]]
    return hashlib.md5(' '.join(top).encode()).hexdigest()[:16]


def _precompute_chunks(text):
    """チャンクデータを事前計算（O(n²)ループ内での重複regex呼び出しを排除）。"""
    text = _LIVE_PREFIX.sub('', text)
    text = re.sub(r'[0-9\s　・！？!?「」【】（）()]+', ' ', text)
    kana  = frozenset(SYNONYMS.get(t, t) for t in _KATAKANA_RUN.findall(text))
    kanji = frozenset(SYNONYMS.get(t, t) for t in _KANJI_RUN.findall(text))
    return kana, kanji


def cluster(articles):
    n = len(articles)
    parent = list(range(n))

    # O(n²)ループ内でのnormalize/regex重複呼び出しを排除するため事前計算
    normalized  = [normalize(a['title']) - STOP_WORDS for a in articles]
    pre_chunks  = [_precompute_chunks(a['title']) for a in articles]

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
        wi = normalized[i]
        for j in range(i + 1, n):
            ri, rj = find(i), find(j)
            if ri == rj:
                continue
            if cluster_size.get(ri, 1) + cluster_size.get(rj, 1) > MAX_CLUSTER_SIZE:
                continue
            wj = normalized[j]
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
                # word-level が失敗した場合（スペースなし日本語タイトル）事前計算チャンクでリトライ
                kana_a, kanji_a = pre_chunks[i]
                kana_b, kanji_b = pre_chunks[j]
                shared_kana  = kana_a & kana_b
                shared_kanji: set = set()
                for r in kanji_a:
                    for s in kanji_b:
                        if r == s or (len(r) >= 2 and r in s) or (len(s) >= 2 and s in r):
                            shared_kanji.add(r if len(r) <= len(s) else s)
                shared_c  = shared_kana | shared_kanji
                specific  = shared_c - _CHUNK_COMMON
                if len(specific) >= 2:
                    sa = kana_a | kanji_a
                    sb = kana_b | kanji_b
                    usz = len(sa | sb)
                    if usz and len(shared_c) / usz >= _CHUNK_THRESHOLD:
                        union(i, j)
                        new_size = cluster_size.get(ri, 1) + cluster_size.get(rj, 1)
                        cluster_size[find(i)] = new_size
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

    return _centroid_verify(list(groups_dict.values()))


def _centroid_verify(groups):
    """重心検証パス: 4件以上のクラスタで重心と共通語ゼロの記事をスタンドアロンに分離。"""
    result = []
    for group in groups:
        if len(group) < 4:
            result.append(group)
            continue
        word_lists = []
        freq = Counter()
        for a in group:
            ws = {w for w in (normalize(a['title']) - STOP_WORDS) if len(w) > 2}
            word_lists.append(ws)
            freq.update(ws)
        # 半数超（ceiling）の記事に出現する語を重心とする
        min_count = (len(group) + 1) // 2
        centroid = {w for w, c in freq.items() if c >= min_count}
        if not centroid:
            result.append(group)
            continue
        core, outliers = [], []
        for i, a in enumerate(group):
            if word_lists[i] & centroid:
                core.append(a)
            else:
                outliers.append(a)
        if not core:
            result.append(group)
            continue
        result.append(core)
        for o in outliers:
            result.append([o])
    return result
