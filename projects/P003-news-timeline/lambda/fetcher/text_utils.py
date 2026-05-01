"""
text_utils.py — テキスト処理・ソース名抽出・エンティティ・要約生成
"""
import re
import urllib.parse
from collections import Counter

from config import (
    MEDIA_NS, SOURCE_NAME_MAP, GENRE_KEYWORDS, GENRE_STRONG_KEYWORDS,
    GENRE_PRIORITY, ENTITY_PATTERNS, SYNONYMS,
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

    # 3. Google News の場合: タイトル末尾の " - メディア名" や「（メディア名）」を抽出
    is_google = False
    try:
        domain = urllib.parse.urlparse(article_link).netloc.lower()
        is_google = 'google' in domain or 'google' in feed_url
        if is_google:
            title = (item.findtext('title') or '').strip()
            for pat in [
                r'\s[-–―]\s([^-–―｜|]+)$',
                r'[｜|]([^｜|]+)$',
                r'（([^）]{1,20})）$',
                r'\(([^)]{1,20})\)$',
            ]:
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

    # Google フィード由来でソース名が特定できなかった場合
    if is_google:
        return 'Google News'
    return 'Unknown'


_IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.webp', '.gif')


def _looks_like_image(url: str) -> bool:
    return bool(url) and any(ext in url.lower() for ext in _IMAGE_EXTS)


def extract_rss_image(item):
    # 1. media:thumbnail — 配信者が明示したサムネイル（最優先）
    mt = item.find('media:thumbnail', MEDIA_NS)
    if mt is not None and mt.get('url'):
        return mt.get('url')

    # 2. media:content — medium="image" 優先、次に medium 属性なし（旧動作互換）
    mcs = item.findall('media:content', MEDIA_NS)
    for mc in mcs:
        url = mc.get('url', '')
        if url and mc.get('medium') == 'image':
            return url
    for mc in mcs:
        url = mc.get('url', '')
        if url and mc.get('medium', '') == '':
            return url

    # 3. enclosure (type="image/...")
    enc = item.find('enclosure')
    if enc is not None and enc.get('type', '').startswith('image') and enc.get('url'):
        return enc.get('url')

    # 4. <image><url>...</url></image>
    img_el = item.find('image')
    if img_el is not None:
        url = (img_el.findtext('url') or '').strip()
        if url.startswith('http'):
            return url

    # 5. description / content:encoded の <img> タグ
    for field in ('description', f'{{{MEDIA_NS["content"]}}}encoded'):
        raw = item.findtext(field) or ''
        if raw:
            m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', raw, re.I)
            if m:
                src = m.group(1)
                if src.startswith('http') and _looks_like_image(src):
                    return src

    return None


# 特定性の高いジャンル: キーワード1件でも分類。広義ジャンル(グルメ・くらし・ビジネス)は2件維持。
_SINGLE_HIT_GENRES = frozenset({'テクノロジー', 'スポーツ', '政治', '社会', '健康', '国際', '株・金融', '科学', 'エンタメ'})


def dominant_genres(articles, max_genres=2):
    # 記事単位スコアリング: 各記事ごとにキーワードヒット数を集計して合算する。
    # 旧実装（全記事結合テキストでユニークキーワード数）は、少数の汚染記事が多数の記事を
    # 上回るスコアを出せてしまう欠陥があった（例: 国際ニュース群に野球記事1件が混入→スポーツ誤分類）。
    scores = {}
    for a in articles:
        title = a['title']
        for genre, keywords in GENRE_KEYWORDS.items():
            hit = sum(1 for kw in keywords if kw in title)
            if hit > 0:
                scores[genre] = scores.get(genre, 0) + hit

    # 強固キーワード: 結合タイトルで検索し×3ボーナス（従来通り）
    all_titles = ' '.join(a['title'] for a in articles)
    for genre, keywords in GENRE_STRONG_KEYWORDS.items():
        hit = sum(1 for kw in keywords if kw in all_titles)
        if hit >= 1:
            scores[genre] = scores.get(genre, 0) + hit * 3

    # 閾値フィルター: 広義ジャンル(グルメ・くらし等)は最低2件の記事でマッチが必要
    # 特定ジャンルは1件でも可（従来ルール維持）
    filtered = {}
    for genre, score in scores.items():
        min_articles = 1 if genre in _SINGLE_HIT_GENRES else 2
        matching_cnt = sum(1 for a in articles if any(kw in a['title'] for kw in GENRE_KEYWORDS.get(genre, [])))
        if matching_cnt >= min_articles:
            filtered[genre] = score
    scores = filtered

    if scores:
        priority_rank = {g: i for i, g in enumerate(GENRE_PRIORITY)}
        top = sorted(
            scores,
            key=lambda g: (-scores[g], priority_rank.get(g, 99)),
        )[:max_genres]
        return top

    return ['総合']


_OVERRIDE_GENRE_RULES = [
    ('株・金融', ['株価', '日経平均', '日経平均株価', 'TOPIX', '為替レート', '日銀', '円安', '円高', 'ドル円']),
    # T2026-0501-F: 政治 override は「日本国内政治」を強く示す語に限定する。
    # 「政府」「大臣」だけだと「ミャンマー政府」「インド大臣」のような海外ニュースを誤って政治へ寄せるため、
    # 国会・衆院/参院・組閣など日本固有の語のみ残す。
    ('政治',    ['首相', '総理大臣', '国会審議', '内閣府', '解散', '組閣', '参院選', '衆院選']),
    # T2026-0501-F: 海外 override を強化。海外政情・要人ニュースはクラスタタイトルに 1 件あれば
    # 国際で確定させる（情報の地図として日本国内政治と海外政治を分ける）。
    ('国際',    ['ミサイル発射', '核実験', '制裁措置', 'NATO首脳', 'ウクライナ侵攻',
                 'クーデター', '軍事政権', '親軍政権', 'ASEAN加盟', 'ASEAN首脳',
                 'ミャンマー', 'スーチー', 'アウンサンスーチー', 'ガザ',
                 'プーチン', 'ゼレンスキー', 'ネタニヤフ', '金正恩', '習近平大統領', 'モディ首相']),
    ('スポーツ', ['オリンピック', '五輪', 'ワールドカップ', 'W杯']),
]


def override_genre_by_title(articles: list):
    """クラスター記事タイトルに強固キーワードが2件以上（1件クラスタは1件）あればジャンルを強制上書き。

    combined_titles で ANY 一致するだけでは、別ジャンルのクラスタに混入した1記事が
    クラスタ全体のジャンルを汚染する問題が起きる（例: 国際クラスタ内のW杯記事1件→スポーツ誤分類）。
    """
    min_hits = max(1, min(2, len(articles)))
    for genre, keywords in _OVERRIDE_GENRE_RULES:
        for kw in keywords:
            hits = sum(1 for a in articles if kw in a.get('title', ''))
            if hits >= min_hits:
                return genre
    return None


def dominant_lang(articles):
    return Counter(a.get('lang', 'ja') for a in articles).most_common(1)[0][0]


_TITLE_MARKDOWN_LEAD_RE = re.compile(r'^\s*[#*]+\s*')
_TITLE_MARKDOWN_TRAIL_RE = re.compile(r'\s*[#*]+\s*$')


def strip_title_markdown(title):
    """generatedTitle に残った markdown 装飾文字 (#, *, **) を除去。
    processor 側 _strip_title_markdown と同じ振る舞いを fetcher でも提供する
    (パターン1 横断適用: title 書き込みパスは全て strip するルール)。"""
    if not isinstance(title, str):
        return title
    t = _TITLE_MARKDOWN_LEAD_RE.sub('', title)
    t = _TITLE_MARKDOWN_TRAIL_RE.sub('', t)
    return t.strip()


def clean_title(title):
    t = re.sub(r'\s*[-－–|｜]\s*[^\s].{1,25}$', '', title).strip()
    t = re.sub(r'^\[.{1,20}\]\s*', '', t).strip()
    return t or title


def extractive_title(articles):
    if not articles:
        return ''
    first = clean_title(articles[0]['title'])
    return first[:40] + ('…' if len(first) > 40 else '')


def is_extractive_summary(text: str) -> bool:
    """既存 generatedSummary が AI 出力ではなく fetcher 側 extractive_summary()
    フォールバックである可能性を判定する。AI 未実行のまま見出し連結が generatedSummary
    に入っているケースを後続パスで除外するためのヘルパ。

    判定パターン (どれかにマッチで extractive とみなす):
      - 旧フォールバック: 「複数の報道」「関連して」が両方含まれる
      - 現行 extractive_summary(): 「また、「」 + 「」など」 (中ライン連結句)
      - 現行 extractive_summary(): 「最新では「」と報じられている」 (closing句)
      - 現行 extractive_summary(): 末尾の「（… ほかN件）」/「（N件）」
    """
    if not text:
        return False
    t = str(text)
    if '複数の報道' in t and '関連して' in t:
        return True
    if 'また、「' in t and '」など' in t:
        return True
    if '最新では「' in t and '」と報じられている' in t:
        return True
    # 末尾の「（… ほか12件）」「（5件）」パターン (extractive_summary src_note)
    if re.search(r'（[^（）]*ほか\s*\d+件）\s*$', t):
        return True
    if re.search(r'（\s*\d+件）\s*$', t):
        return True
    return False


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
    'という', 'および', 'また', 'さらに', 'ただし',
    '向け', '対し', '日本', '今', '年', '月', '日', '円',
    '社', '氏', '同', '新', '元', '前', '後', '以上', '以下',
    # 汎用的すぎるニュース頻出語（proc_storageと共通化）
    'ニュース', '速報', '最新', '話題', '注目', '動画', '写真', '記事', '中継',
    '動向', '影響', '情勢', '問題', '対応', '状況', '関係', '活動', '実施', '開催',
    '発表', '報告', '内容', '結果', '方針', '対策', '検討', '確認', '実現', '推進',
    '強化', '改善', '整備', '支援', '提供', '拡大', '展開', '継続', '協力', '連携',
    '取り組み', '見通し', '増加', '減少', '上昇', '下落', '変化', '今後', '今回',
    '課題', '企業', '議論', '対立', '会議', '調査', '研究', '報道', '声明', '決定',
    '方向', '制度', '政策', '経済', '社会', '市場', '投資', '技術', '事業', '計画',
    '関連', '情報', '開始', '終了',
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


# T2026-0501-H: トピックマージ判定用のエンティティ抽出 (固有名詞のみ・PO 指示でシンプル化)。
# 「混入 > 分裂」原則で merge gate に使う。エンティティ重複が無ければ
# Jaccard 値に関わらずマージしない (例:「関税引き上げ 米国」vs「関税引き上げ 日本」は
# 関税 が共有されても国が異なるので別事件)。
#
# 抽出ソース (シンプルに固有名詞のみ):
#  - ENTITY_PATTERNS canonical (米国/中国/トランプ/プーチン 等の正規化済みキー)
#  - カタカナ 3 文字以上 (汎用語除く) - 人名/組織名/サービス名
#  - 英大文字始まり 2 文字以上 (Apple/OpenAI/NASA 等)
#  - 国名漢字 (日本/韓国/北朝鮮/台湾 等のうち ENTITY_PATTERNS に無いもの) を補完
#
# **漢字一般語の抽出はしない** (関税 / 政策 / 制度 等の policy ワードが entity 重複に紛れ込み、
# 「関税引き上げ 米国」と「関税引き上げ 日本」を誤判定するため)。
_MERGE_ENTITY_KATAKANA = re.compile(r'[ァ-ヴー]{3,}')
_MERGE_ENTITY_LATIN    = re.compile(r'[A-Z][A-Za-z0-9]{1,}')
# ENTITY_PATTERNS に未登録の漢字固有名詞 (国名/著名人名/政党) を補完。
# canonical キーで返す (例: '日本' は 日本/邦/和 を吸収)。
_MERGE_ENTITY_KANJI_SUPPLEMENT = [
    ('日本', re.compile(r'日本')),
    ('英国', re.compile(r'英国|イギリス')),
    ('独国', re.compile(r'ドイツ|独国')),
    ('仏国', re.compile(r'フランス|仏国')),
    ('沖縄', re.compile(r'沖縄')),
    ('北海道', re.compile(r'北海道')),
    ('東京', re.compile(r'東京')),
    ('大阪', re.compile(r'大阪')),
    ('自民党', re.compile(r'自民党|自由民主党')),
    ('立憲民主党', re.compile(r'立憲民主党')),
    ('公明党', re.compile(r'公明党')),
    ('共産党', re.compile(r'共産党')),
    ('維新の会', re.compile(r'維新の会|日本維新')),
    ('国民民主党', re.compile(r'国民民主党')),
]
# 主体性が薄く merge gate のシグナルにならない汎用語
_MERGE_ENTITY_STOP = {
    'ニュース', '速報', '最新', '話題', '注目', '動画', '写真', '記事', '中継',
    '動向', '影響', '情勢', '問題', '対応', '状況', '関係', '活動', '実施', '開催',
    '発表', '報告', '内容', '結果', '方針', '対策', '検討', '確認', '実現', '推進',
    '強化', '改善', '整備', '支援', '提供', '拡大', '展開', '継続', '協力', '連携',
    '取り組み', '見通し', '増加', '減少', '上昇', '下落', '変化', '今後', '今回',
    '課題', '議論', '対立', '会議', '調査', '研究', '報道', '声明', '決定',
    '方向', '制度', '政策', '関連', '情報', '開始', '終了',
    '社会', '世界', '政府', '当局', '地域', '国内', '海外',
    # 短すぎて識別力ない英語汎用語
    'AI', 'IT', 'EC', 'PC', 'PR', 'GDP', 'CEO', 'CTO', 'COO', 'CFO',
    'The', 'This', 'That', 'News', 'Update',
}


def extract_merge_entities(text: str) -> set:
    """トピックマージ判定用のエンティティ抽出 (固有名詞のみ・シンプル)。

    重複していれば「同じ事件の可能性」、なければ「別事件」と判断するためのシグナル。
    PO 指示「混入 > 分裂」を守るため、policy ワード (関税/政策/制度 等) は意図的に拾わない。
    返す集合は SYNONYMS 正規化済み。
    """
    if not text:
        return set()
    cleaned = re.sub(r'\s*[|｜].*$', '', str(text))
    cleaned = re.sub(r'^【[^】]*】', '', cleaned)
    entities = set()
    # ENTITY_PATTERNS canonical (米国/中国/トランプ/プーチン 等)
    for pattern in ENTITY_PATTERNS:
        if re.search(pattern, cleaned):
            entities.add(pattern.split('|')[0])
    # 補完: ENTITY_PATTERNS に無い国名/政党などの漢字固有名詞
    for canonical, regex in _MERGE_ENTITY_KANJI_SUPPLEMENT:
        if regex.search(cleaned):
            entities.add(canonical)
    # カタカナ
    for m in _MERGE_ENTITY_KATAKANA.findall(cleaned):
        norm = SYNONYMS.get(m, m)
        if norm not in _MERGE_ENTITY_STOP:
            entities.add(norm)
    # 英大文字始まり (Apple/OpenAI/NASA 等)
    for m in _MERGE_ENTITY_LATIN.findall(cleaned):
        if m not in _MERGE_ENTITY_STOP and len(m) >= 2:
            entities.add(m)
    return entities


_KW_STOP_RELATED = {
    'ニュース', '速報', '最新', '話題', '注目', '動画', '写真', '記事', '中継',
    '動向', '影響', '情勢', '問題', '対応', '状況', '関係', '活動', '実施', '開催',
    '発表', '報告', '内容', '結果', '方針', '対策', '検討', '実現', '推進',
    '強化', '改善', '支援', '提供', '拡大', '継続', '協力', '連携', '取り組み',
    '増加', '減少', '上昇', '下落', '変化', '今後', '今回',
    'ついて', '社会', '日本', '世界', '政府', '当局', '地域', '国内', '海外',
}


def _extract_kw_tokens(title: str) -> set:
    """カタカナ3文字以上・漢字2文字以上のトークンを抽出（汎用語除く）。"""
    tokens = re.findall(r'[ァ-ヶー]{3,}|[一-龯々]{2,}', title)
    return {t for t in tokens if t not in _KW_STOP_RELATED and len(t) >= 3}


def _title_bigrams(title: str) -> set:
    """タイトルを正規化してバイグラムセットを返す（Jaccard類似度用）。"""
    s = re.sub(r'[^\w\u3040-\u30FF\u4E00-\u9FFF]', '', title.lower())
    return {s[i:i+2] for i in range(len(s) - 1)} if len(s) >= 2 else set()


# T2026-0429-E: detect_topic_hierarchy の親子化 false_merge ガード用。
# scripts/verify_branching_quality.py が使う char-bigram と一致させることで、
# 「ガードを通過した親子ペアは validator で suspect_false_merge にならない」
# という不変条件を成立させる。
_HIERARCHY_BIGRAM_DROP_CHARS = frozenset('、。「」『』・…ー-—()（）[]［］')


def _hierarchy_bigrams(text: str) -> set:
    """validator (verify_branching_quality.py::char_bigrams) と同じ計算で char bigram を返す。"""
    if not text:
        return set()
    cleaned = ''.join(
        ch for ch in text
        if not ch.isspace() and ch not in _HIERARCHY_BIGRAM_DROP_CHARS
    )
    if len(cleaned) < 2:
        return {cleaned} if cleaned else set()
    return {cleaned[i:i + 2] for i in range(len(cleaned) - 1)}


# 親子化最低類似度。
# 実測 (2026-04-29 production topics-full.json, n=12 branched pairs):
#   suspect_false_merge: 11 件すべて max(title,keyPoint) sim <= 0.18 (validator metric)
#   ok:                   1 件 sim = 0.32 (チョルノービリ事故40年 系)
# 0.20 = validator (verify_branching_quality.py) の suspect_false_merge 境界
# (sim < 0.2)。本ガードを通過したペアは validator で false_merge とカウントされない。
_HIERARCHY_CONTENT_SIM_THRESHOLD = 0.20


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def find_related_topics(topics: list, max_related: int = 5) -> dict:
    topic_entities: dict = {}
    topic_kw: dict = {}
    topic_bigrams: dict = {}

    # 転置インデックス: トークン → topicId集合
    entity_idx: dict = {}
    kw_idx: dict = {}
    bigram_idx: dict = {}

    topic_by_id = {t['topicId']: t for t in topics}

    for t in topics:
        title = t.get('generatedTitle') or t.get('title', '')
        tid = t['topicId']
        ents = extract_entities(title)
        kws = _extract_kw_tokens(title)
        bgs = _title_bigrams(title)
        topic_entities[tid] = ents
        topic_kw[tid] = kws
        topic_bigrams[tid] = bgs
        for e in ents:
            entity_idx.setdefault(e, set()).add(tid)
        for kw in kws:
            kw_idx.setdefault(kw, set()).add(tid)
        for bg in bgs:
            bigram_idx.setdefault(bg, set()).add(tid)

    GENERIC = {'ai', 'it', 'ec', 'pc', 'sns', 'dx'}
    related = {}
    for t in topics:
        tid = t['topicId']
        my_entities = topic_entities.get(tid, set())
        my_kw       = topic_kw.get(tid, set())
        my_bigrams  = topic_bigrams.get(tid, set())
        my_genre    = t.get('genre', '')

        # 転置インデックスで候補を絞る（O(n)→O(k)、k=共有トークンを持つトピック数）
        cand_ids: set = set()
        for e in my_entities:
            cand_ids |= entity_idx.get(e, set())
        for kw in my_kw:
            cand_ids |= kw_idx.get(kw, set())
        for bg in my_bigrams:
            cand_ids |= bigram_idx.get(bg, set())
        cand_ids.discard(tid)

        candidates = []
        for oid in cand_ids:
            other = topic_by_id.get(oid)
            if not other:
                continue
            other_entities = topic_entities.get(oid, set())
            other_kw       = topic_kw.get(oid, set())
            other_bigrams  = topic_bigrams.get(oid, set())

            shared_ent = my_entities & other_entities
            meaningful_ent = {e for e in shared_ent if len(e) > 1 and e.lower() not in GENERIC}
            shared_kw = my_kw & other_kw
            jac = _jaccard(my_bigrams, other_bigrams)
            same_genre = my_genre and my_genre == other.get('genre', '')

            score = len(meaningful_ent) * 3 + len(shared_ent) + len(shared_kw)
            entity_match = len(meaningful_ent) >= 2 or (len(meaningful_ent) == 1 and len(shared_ent) >= 2)
            kw_match     = len(shared_kw) >= 2 and len(shared_kw & my_kw) / max(len(my_kw), 1) >= 0.3
            jaccard_match = (jac >= 0.35) or (jac >= 0.25 and same_genre)

            if not entity_match and not kw_match and not jaccard_match:
                continue
            if jaccard_match and not entity_match and not kw_match:
                score = int(jac * 10)

            shared_labels = list(meaningful_ent or shared_kw)[:3]
            candidates.append({
                'topicId': oid,
                'title': other.get('generatedTitle') or other.get('title', ''),
                'sharedEntities': shared_labels,
                'overlapScore': score,
            })

        candidates.sort(key=lambda x: x['overlapScore'], reverse=True)
        related[tid] = candidates[:max_related]

    return related


_HIERARCHY_TIME_WINDOW = 72 * 3600  # 72時間以上離れたトピックは別イベント


def detect_topic_hierarchy(topics: list, topic_entities: dict) -> dict:
    """
    親子トピックを検出する。
    修正ポイント:
    - entity数ではなく記事数(articleCount)で親を判定（同一entity数でも機能する）
    - 72時間の時間ウィンドウ（異なる日のイベントを誤接続しない）
    - entityインデックスに加えてキーワードインデックスでも候補を探す
    - 最も記事数の多い候補を親として選択
    """
    parent_map = {}
    topic_meta = {t['topicId']: t for t in topics}

    # キーワードトークンを事前計算
    topic_kw: dict = {
        t['topicId']: _extract_kw_tokens(t.get('generatedTitle') or t.get('title', ''))
        for t in topics
    }

    # T2026-0429-E: 親子化 false_merge ガード用に title / keyPoint の char bigram を事前計算。
    topic_title_bigrams: dict = {}
    topic_keypoint_bigrams: dict = {}
    for t in topics:
        tid = t['topicId']
        title = t.get('generatedTitle') or t.get('title') or ''
        keypoint = t.get('keyPoint') or ''
        topic_title_bigrams[tid] = _hierarchy_bigrams(title)
        topic_keypoint_bigrams[tid] = _hierarchy_bigrams(keypoint) if keypoint else set()

    # 転置インデックス: entity → topicId集合
    entity_to_tids: dict = {}
    for tid, ents in topic_entities.items():
        for e in ents:
            entity_to_tids.setdefault(e, set()).add(tid)

    # 転置インデックス: キーワード → topicId集合
    kw_to_tids: dict = {}
    for tid, kws in topic_kw.items():
        for kw in kws:
            kw_to_tids.setdefault(kw, set()).add(tid)

    for topic_b in topics:
        tid_b = topic_b['topicId']
        if tid_b in parent_map:
            continue

        cnt_b   = int(topic_b.get('articleCount', 0))
        # T36: 子側の score 閾値を撤廃 (2記事 low-velocity トピックも親子化候補に)。
        # 「77% が 2-3 記事孤立」を解消する post-cluster merge パスの一環。
        # entity 共有要件は残すので無関係トピックの誤親子化リスクは低い。
        if cnt_b < 2:
            continue

        entities_b = topic_entities.get(tid_b, set())
        kw_b       = topic_kw.get(tid_b, set())
        first_b    = int(topic_b.get('firstArticleAt', topic_b.get('lastUpdated', 0)) or 0)

        # 候補: entity または キーワードを共有するトピック（和集合）
        candidate_tids: set = set()
        for e in entities_b:
            candidate_tids |= entity_to_tids.get(e, set())
        for kw in kw_b:
            candidate_tids |= kw_to_tids.get(kw, set())
        candidate_tids.discard(tid_b)

        if not candidate_tids:
            continue

        best_parent: str | None = None
        best_priority             = -1

        for tid_a in candidate_tids:
            t_a = topic_meta.get(tid_a)
            if not t_a:
                continue

            score_a = int(t_a.get('score', 0))
            cnt_a   = int(t_a.get('articleCount', 0))
            first_a = int(t_a.get('firstArticleAt', t_a.get('lastUpdated', 0)) or 0)

            # 親は最低 2 記事必要 (1 記事は parent として弱すぎる)
            if cnt_a < 2:
                continue

            # T36: 親は子より記事数 ≥ + 親の方が時間的に早い、というルールに緩和。
            # 旧: cnt_a <= cnt_b は continue (strict >)
            # 新: cnt_a < cnt_b は continue。同数なら first_a < first_b (親が先) で許容。
            # これで 2 記事先発トピック → 2 記事派生トピック の親子化が可能に。
            if cnt_a < cnt_b:
                continue
            if cnt_a == cnt_b:
                # 同数なら親側が時間的に先に立っていることを必須条件とする
                if not (first_a > 0 and first_b > 0 and first_a < first_b):
                    continue

            # 時間ウィンドウ: 72時間以内
            if first_a > 0 and first_b > 0:
                if abs(first_b - first_a) > _HIERARCHY_TIME_WINDOW:
                    continue

            entities_a = topic_entities.get(tid_a, set())
            kw_a       = topic_kw.get(tid_a, set())

            # ジャンル互換性チェック: 両方に具体的なジャンルがある場合、共通ジャンルがなければスキップ
            # 「総合」は汎用なので除外して判定
            genres_a = {g for g in (t_a.get('genres') or ([t_a['genre']] if t_a.get('genre') else [])) if g != '総合'}
            genres_b = {g for g in (topic_b.get('genres') or ([topic_b.get('genre', '')] if topic_b.get('genre') else [])) if g != '総合'}
            if genres_a and genres_b and not (genres_a & genres_b):
                continue

            # T36 強度上げ: false-positive (例: c1bbe0fe(米イラン核合意) と 08189ac4(米露ウク停戦)
            # が共通 entity「トランプ」だけで親子化されていた) を防ぐ。
            # 旧: shared_ents>=1 OR shared_kws>=2 → これだと有名人物名 1 件で誤マッチ
            # 新: (shared_ents>=2) OR (shared_ents>=1 AND shared_kws>=2)
            #     1 entity だけだと弱いので追加の kw シグナルを要求する
            shared_ents = entities_a & entities_b
            shared_kws  = kw_a & kw_b
            if len(shared_ents) >= 2:
                pass  # 強い entity overlap → OK
            elif len(shared_ents) >= 1 and len(shared_kws) >= 2:
                pass  # 1 entity + 補強 kw → OK
            else:
                continue

            # T2026-0429-E: コンテンツ類似度ガード。
            # entity / kw 共有だけでは「高市首相」「マリ」等の主役名 1 語＋汎用 kw で
            # 別事件・別主役のトピックが誤マージされる (error_merge=83% in T2026-0429-C)。
            # validator (verify_branching_quality.py) と同じ char-bigram + max(title,keyPoint)
            # で sim を算出し、suspect_false_merge 境界 (sim < 0.20) を切る。
            tba = topic_title_bigrams.get(tid_a, set())
            tbb = topic_title_bigrams.get(tid_b, set())
            kpa = topic_keypoint_bigrams.get(tid_a, set())
            kpb = topic_keypoint_bigrams.get(tid_b, set())
            content_sim = _jaccard(tba, tbb)
            if kpa and kpb:
                content_sim = max(content_sim, _jaccard(kpa, kpb))
            if content_sim < _HIERARCHY_CONTENT_SIM_THRESHOLD:
                continue

            # 優先度: 記事数 × 100 + スコア + 早出現ボーナス
            time_bonus = max(0, (first_b - first_a) // 3600) if first_a > 0 and first_b > 0 else 0
            priority   = cnt_a * 100 + score_a + time_bonus

            if priority > best_priority:
                best_priority = priority
                best_parent   = tid_a

        if best_parent:
            parent_map[tid_b] = best_parent

    return parent_map
