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

# chunk-based similarity（スペースなし日本語タイトル向けフォールバック）
_KATAKANA_RUN = re.compile(r'[ァ-ヴーｦ-ﾟ]{3,}')
_KANJI_RUN    = re.compile(r'[一-鿿々〆〇]{2,}')
_CHUNK_THRESHOLD = 0.40  # word-level より高めに設定して誤クラスタを防ぐ
# 高頻度すぎて識別力のない一般語を除外
_CHUNK_COMMON = {'大統領', '首相', '大臣', '政府', '国会', '議員', '社長', '会長',
                 '委員会', '知事', '市長', '内閣', '官房', '大使', '長官',
                 '日本', '米国', '中国', '東京', '大阪', '会社', '企業', '事件', '事故',
                 '発表', '開始', '実施', '決定', '対応', '影響', '問題', '検討', '対策'}

def _chunk_sim(a: str, b: str) -> float:
    """カタカナ連続(3字以上)・漢字連続(2字以上)をチャンクとして抽出しJaccard類似度を計算。
    スペースなし日本語タイトル同士の比較に使用する（word-level が 0 の場合のみ呼ばれる）。
    共通語が全て _CHUNK_COMMON の汎用語なら 0 を返す（誤クラスタ防止）。"""
    def _chunks(text):
        text = _LIVE_PREFIX.sub('', text)
        text = re.sub(r'[0-9\s　・！？!?「」【】（）()]+', ' ', text)
        kana  = {SYNONYMS.get(t, t) for t in _KATAKANA_RUN.findall(text)}
        kanji = {SYNONYMS.get(t, t) for t in _KANJI_RUN.findall(text)}
        return kana | kanji
    sa, sb = _chunks(a), _chunks(b)
    if not sa or not sb:
        return 0.0
    shared = sa & sb
    specific = shared - _CHUNK_COMMON
    if len(specific) < 2:
        return 0.0  # 固有語を2語以上共有していなければ誤クラスタリスク大
    return len(shared) / len(sa | sb)


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
                # word-level が失敗した場合（スペースなし日本語タイトル）chunk-level でリトライ
                cs = _chunk_sim(articles[i]['title'], articles[j]['title'])
                if cs >= _CHUNK_THRESHOLD:
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

    return list(groups_dict.values())
