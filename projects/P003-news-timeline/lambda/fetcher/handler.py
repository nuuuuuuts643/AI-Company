import json
import os
import re
import time
import hashlib
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from email.utils import parsedate_tz, mktime_tz

import boto3
from boto3.dynamodb.conditions import Key

TABLE_NAME        = os.environ.get('TABLE_NAME', 'p003-topics')
S3_BUCKET         = os.environ.get('S3_BUCKET', '')
REGION            = os.environ.get('REGION', 'ap-northeast-1')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
SLACK_WEBHOOK     = os.environ.get('SLACK_WEBHOOK', '')

dynamodb = boto3.resource('dynamodb', region_name=REGION)
table    = dynamodb.Table(TABLE_NAME)
s3       = boto3.client('s3', region_name=REGION)

RSS_FEEDS = [
    # Google News（日本語・カテゴリ別）
    {'url': 'https://news.google.com/rss/headlines/section/topic/NATION?hl=ja&gl=JP&ceid=JP:ja',         'genre': '総合'},
    {'url': 'https://news.google.com/rss/headlines/section/topic/POLITICS?hl=ja&gl=JP&ceid=JP:ja',       'genre': '政治'},
    {'url': 'https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=ja&gl=JP&ceid=JP:ja',       'genre': 'ビジネス'},
    {'url': 'https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=ja&gl=JP&ceid=JP:ja',     'genre': 'テクノロジー'},
    {'url': 'https://news.google.com/rss/headlines/section/topic/SPORTS?hl=ja&gl=JP&ceid=JP:ja',         'genre': 'スポーツ'},
    {'url': 'https://news.google.com/rss/headlines/section/topic/ENTERTAINMENT?hl=ja&gl=JP&ceid=JP:ja',  'genre': 'エンタメ'},
    {'url': 'https://news.google.com/rss/headlines/section/topic/SCIENCE?hl=ja&gl=JP&ceid=JP:ja',        'genre': '科学'},
    {'url': 'https://news.google.com/rss/headlines/section/topic/HEALTH?hl=ja&gl=JP&ceid=JP:ja',         'genre': '健康'},
    {'url': 'https://news.google.com/rss/headlines/section/topic/WORLD?hl=ja&gl=JP&ceid=JP:ja',          'genre': '国際'},
    # ライブドアニュース（補完）
    {'url': 'https://news.livedoor.com/topics/rss/dom.xml', 'genre': '総合'},
    {'url': 'https://news.livedoor.com/topics/rss/ent.xml', 'genre': 'エンタメ'},
    {'url': 'https://news.livedoor.com/topics/rss/spo.xml', 'genre': 'スポーツ'},
    {'url': 'https://news.livedoor.com/topics/rss/int.xml', 'genre': '国際'},
    # テクノロジー系
    {'url': 'https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml', 'genre': 'テクノロジー'},
    {'url': 'https://rss.itmedia.co.jp/rss/2.0/itmedia_all.xml', 'genre': 'テクノロジー'},
    {'url': 'https://gigazine.net/news/rss_2.0/',                 'genre': 'テクノロジー'},
    {'url': 'https://ascii.jp/rss.xml',                           'genre': 'テクノロジー'},
    {'url': 'https://www.gizmodo.jp/index.xml',                   'genre': 'テクノロジー'},
    # 総合・一般紙
    {'url': 'https://www3.nhk.or.jp/rss/news/cat0.xml',           'genre': '総合'},
    {'url': 'https://www.yomiuri.co.jp/feed/',                     'genre': '総合'},
    {'url': 'https://mainichi.jp/rss/etc/mainichi-flash.rss',     'genre': '総合'},
    {'url': 'https://www.asahi.com/rss/asahi/newsheadlines.rdf',  'genre': '総合'},
    {'url': 'https://www3.nhk.or.jp/rss/news/cat4.xml',           'genre': 'エンタメ'},
    {'url': 'https://www3.nhk.or.jp/rss/news/cat7.xml',           'genre': 'スポーツ'},
    # ビジネス・経済
    {'url': 'https://toyokeizai.net/list/feed/rss',  'genre': 'ビジネス'},
    {'url': 'https://diamond.jp/list/feed/rss',       'genre': 'ビジネス'},
    {'url': 'https://www.nikkei.com/rss/index.xml',   'genre': '株・金融'},
    # 株・金融（Google News検索RSS）
    {'url': 'https://news.google.com/rss/search?q=%E6%A0%AA%E4%BE%A1+%E6%97%A5%E6%9C%AC&hl=ja&gl=JP&ceid=JP:ja',    'genre': '株・金融'},
    {'url': 'https://news.google.com/rss/search?q=%E6%97%A5%E9%8A%80+%E9%87%91%E5%88%A9+%E7%82%BA%E6%9B%BF&hl=ja&gl=JP&ceid=JP:ja', 'genre': '株・金融'},
    {'url': 'https://news.google.com/rss/search?q=%E6%B1%BA%E7%AE%97+%E4%B8%8A%E5%A0%B4+%E6%A0%AA%E5%BC%8F&hl=ja&gl=JP&ceid=JP:ja', 'genre': '株・金融'},
]

JACCARD_THRESHOLD = 0.35  # 0.25→0.35に戻す（過剰クラスタリング防止）
MAX_CLUSTER_SIZE  = 20    # 1トピックの最大記事数（超えたら新クラスタに分割）

AI_GENERATION_LIMIT = 10   # スコア上位10件のみAI生成対象（コスト削減）
MAX_API_CALLS = 20          # 1Lambda実行あたりのClaude API呼び出し上限（タイトル10＋要約10）

# Claude API呼び出し条件（戦略3: 条件を厳しく設定）
CLAUDE_CALL_CONDITIONS = {
    "min_articles_for_title":   3,   # タイトル生成: 3件未満 → extractive_title（Claude不要）
    "min_articles_for_summary": 5,   # 要約生成:    5件未満 → extractive_summary（Claude不要）
    "min_velocity_score":      20,   # velocity低い → extractive（Claude不要）
    "max_calls_per_run":       10,   # 1実行あたりの上限（Claude必要ルートの絶対上限）
    "cache_ttl_hours":          6,   # 6時間以内に生成した要約は再利用（Claude不要）
}

STOP_WORDS = {
    # 日本語助詞・助動詞
    'は','が','を','に','の','と','で','も','や','か','へ','より','から','まで',
    'という','として','による','において','について','した','する','して',
    'された','される','てい','ます','です','だっ','ある','いる','なっ','れる',
    # ニュースサイト・メディア名ノイズ
    'ニュース','news','yahoo','google','livedoor','narinari','gigazine','gizmodo',
    'itmatedia','itmedia','watch','ascii','pc','日経','読売','毎日','朝日','nhk',
    'reuters','bloomberg','報道','記事','速報','最新','情報','解説','まとめ',
    '続報','詳細','動画','写真','インタビュー','コメント','発表','掲載',
    # 英語
    'the','a','an','is','are','was','were','be','been','of','in','to','for',
    'on','at','by','with','as','from','that','this','it','its','and','or',
    'but','not','have','has','had','will','would','could','should','says',
    'said','new','more','after','over','after','about','up','out','two',
    'into','than','he','she','his','her','they','we','you','i',
}


def normalize(text):
    text = re.sub(r'[【】「」『』（）()\[\]！？!?\s\u3000・]+', ' ', text.lower())
    return {w for w in text.split() if len(w) > 1}


def jaccard(a, b):
    sa, sb = normalize(a), normalize(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def topic_fingerprint(articles):
    """記事群から安定したキーワード指紋を生成 → トピックIDに使う"""
    counter = Counter()
    for a in articles:
        words = normalize(a['title']) - STOP_WORDS
        counter.update(w for w in words if len(w) > 2)
    top = sorted(w for w, _ in counter.most_common(10) if counter[w] >= 1)[:5]
    if not top:
        # フォールバック：最初の記事タイトルをそのまま使用
        top = [articles[0]['title'][:30]]
    return hashlib.md5(' '.join(top).encode()).hexdigest()[:16]


MEDIA_NS = {
    'media':   'http://search.yahoo.com/mrss/',
    'content': 'http://purl.org/rss/1.0/modules/content/',
}

# Well-known source domain → display name mapping
SOURCE_NAME_MAP = {
    'www3.nhk.or.jp': 'NHK',
    'nhk.or.jp': 'NHK',
    'www.yomiuri.co.jp': '読売新聞',
    'mainichi.jp': '毎日新聞',
    'www.asahi.com': '朝日新聞',
    'www.nikkei.com': '日本経済新聞',
    'rss.itmedia.co.jp': 'ITmedia',
    'www.itmedia.co.jp': 'ITmedia',
    'www.gizmodo.jp': 'Gizmodo Japan',
    'toyokeizai.net': '東洋経済',
    'diamond.jp': 'ダイヤモンド',
    'www.sankei.com': '産経新聞',
    'news.yahoo.co.jp': 'Yahoo!ニュース',
    'news.google.com': None,  # Google News — use <source> child element instead
    'president.jp': 'PRESIDENT Online',
    'bunshun.jp': '文春オンライン',
    'www.businessinsider.jp': 'Business Insider Japan',
    'forbesjapan.com': 'Forbes Japan',
    'gigazine.net': 'GIGAZINE',
    'ascii.jp': 'ASCII.jp',
    'news.livedoor.com': 'livedoorニュース',
}


def extract_source_name(item, article_link: str, feed_url: str) -> str:
    """
    Extract the real publisher name from an RSS XML item element.
    Handles Google News aggregator feeds by looking at the <source> child element
    (Google News emits <source url="...">Publisher Name</source> per item).
    Falls back to domain mapping, title parsing, then a cleaned domain string.
    """
    # 1. Try <source> child element (works for Google News RSS)
    source_el = item.find('source')
    if source_el is not None:
        source_text = (source_el.text or '').strip()
        if source_text and 'google' not in source_text.lower():
            return source_text

    # 2. Try article URL domain mapping
    try:
        domain = urllib.parse.urlparse(article_link).netloc.lower()
        if domain in SOURCE_NAME_MAP and SOURCE_NAME_MAP[domain]:
            return SOURCE_NAME_MAP[domain]
        # Google News article links: titles often end with " - Publisher Name"
        if 'google' in domain:
            title = (item.findtext('title') or '').strip()
            match = re.search(r'\s[-\u2013]\s([^\-\u2013]+)$', title)
            if match:
                return match.group(1).strip()
    except Exception:
        pass

    # 3. Try feed URL domain mapping (for direct publisher feeds)
    try:
        feed_domain = urllib.parse.urlparse(feed_url).netloc.lower()
        if feed_domain in SOURCE_NAME_MAP and SOURCE_NAME_MAP[feed_domain]:
            return SOURCE_NAME_MAP[feed_domain]
    except Exception:
        pass

    # 4. Fallback: clean domain name from article URL
    try:
        domain = urllib.parse.urlparse(article_link).netloc
        domain = re.sub(r'^www\.', '', domain)
        domain = re.sub(r'\.(co\.jp|com|jp|net|org)$', '', domain)
        return domain if domain else 'Unknown'
    except Exception:
        return 'Unknown'

def extract_rss_image(item):
    """RSSアイテムからメディア画像URLを抽出"""
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


def fetch_rss(feed):
    articles = []
    url, genre, lang = feed['url'], feed['genre'], feed.get('lang', 'ja')
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Flotopic/1.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read()
        root = ET.fromstring(content)
        for item in root.findall('.//item'):
            title   = (item.findtext('title')   or '').strip()
            link    = (item.findtext('link')     or '').strip()
            pubdate = (item.findtext('pubDate')  or '').strip()
            img     = extract_rss_image(item)
            if title and link:
                articles.append({
                    'title':       title, 'url': link,
                    'pubDate':     pubdate, 'genre': genre,
                    'lang':        lang,
                    'source':      extract_source_name(item, link, url),
                    'imageUrl':    img,
                    'published_ts': _parse_pubdate_ts(pubdate),
                })
    except Exception as e:
        print(f'RSS error [{url}]: {e}')
    return articles


def cluster(articles):
    """
    Union-Find によるクラスタリング。
    MAX_CLUSTER_SIZE を超えたクラスタは分割して過剰クラスタを防ぐ。
    """
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

    # クラスタサイズを追跡してMAX_CLUSTER_SIZEを超えないようにする
    cluster_size = {i: 1 for i in range(n)}

    for i in range(n):
        for j in range(i + 1, n):
            ri, rj = find(i), find(j)
            if ri == rj:
                continue
            # 統合後のサイズがMAX_CLUSTER_SIZEを超える場合はスキップ
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


GENRE_KEYWORDS = {
    '株・金融': ['株価','日経平均','円安','円高','為替','金利','日銀','決算','上場','株式','NISA','投資','FRB','ダウ','ナスダック','債券','利上げ','利下げ','景気','物価','インフレ','GDP','貿易','輸出','輸入'],
    '政治':    ['国会','首相','総理','大臣','選挙','与党','野党','自民','政府','閣議','議員','内閣','知事','官房','外交','条約','法案','政策'],
    'スポーツ':  ['野球','サッカー','テニス','ゴルフ','バスケ','陸上','水泳','五輪','オリンピック','ワールドカップ','Ｊリーグ','プロ野球','NFL','NBA','相撲','ラグビー','大谷','錦織','W杯','Jリーグ'],
    '健康':    ['病院','医療','がん','薬','治療','ワクチン','感染','医師','手術','診断','症状','厚生労働'],
    '科学':    ['宇宙','NASA','JAXA','研究','発見','論文','気候','地震','火山','iPS','ゲノム'],
    'エンタメ':  ['映画','俳優','女優','歌手','アイドル','芸能','ドラマ','アニメ','マンガ','コンサート','紅白','グラミー','アーティスト','ライブ','音楽'],
    'テクノロジー':['AI','人工知能','ChatGPT','iPhone','Android','スマホ','クラウド','サイバー','半導体','アプリ','ソフトウェア','データセンター','量子','セキュリティ','スタートアップ','DX'],
    'ビジネス':  ['売上','利益','赤字','黒字','買収','合併','リストラ','上半期','通期','業績','IPO','スタートアップ','企業'],
    '国際':    ['米国','アメリカ','中国','ロシア','ウクライナ','EU','NATO','国連','外相','首脳','制裁','イラン','イスラエル','中東','北朝鮮','台湾','韓国','欧州','大統領','外務省'],
}

# 同義語正規化（クラスタリング精度向上）
SYNONYMS = {
    'アメリカ':'米国','米':'米国','usa':'米国','us':'米国',
    '総理':'首相','内閣総理大臣':'首相',
    '円相場':'為替','ドル円':'為替',
    '利上げ':'金利','利下げ':'金利',
    'オリンピック':'五輪','olympic':'五輪',
    'chatgpt':'ai','gpt':'ai','claude':'ai','gemini':'ai',
}

def normalize(text):
    text = re.sub(r'[【】「」『』（）()\[\]！？!?\s\u3000・]+', ' ', text.lower())
    words = set()
    for w in text.split():
        if len(w) > 1:
            words.add(SYNONYMS.get(w, w))
    return words


def dominant_genres(articles, max_genres=2):
    """最大2ジャンルを返す。スコア上位のジャンルを採用"""
    all_titles = ' '.join(a['title'] for a in articles)
    scores = {}
    for genre, keywords in GENRE_KEYWORDS.items():
        hit = sum(1 for kw in keywords if kw in all_titles)
        if hit >= 2:
            scores[genre] = hit
    if scores:
        top = sorted(scores, key=scores.get, reverse=True)[:max_genres]
        return top
    # キーワード不足時はRSSフィードのジャンル集計で決定
    return [Counter(a['genre'] for a in articles).most_common(1)[0][0]]


def dominant_lang(articles):
    return Counter(a.get('lang', 'ja') for a in articles).most_common(1)[0][0]


def source_count(articles):
    """何メディアが報道したか（真の重複排除）"""
    return len({a['source'] for a in articles})


def hatena_count(url):
    """はてなブックマーク数を取得（日本語記事用・失敗時は0）"""
    try:
        api = 'https://b.hatena.ne.jp/entry/jsonlite/?url=' + urllib.parse.quote(url, safe='')
        req = urllib.request.Request(api, headers={'User-Agent': 'Flotopic/1.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        return int(data.get('count') or 0)
    except Exception:
        return 0


URGENT_WORDS = {'緊急', '速報', '重大', '急騰', '急落', '大幅', '速報', '号外', '警報', '警告', '危機', '緊迫'}


def _parse_pubdate_ts(pubdate: str) -> int:
    """RSS pubDate 文字列を unix timestamp（int）に変換する。失敗時は 0 を返す。"""
    if not pubdate:
        return 0
    try:
        tpl = parsedate_tz(pubdate)
        return mktime_tz(tpl) if tpl else 0
    except Exception:
        return 0


def apply_time_decay(score: int, last_article_ts: int) -> int:
    """
    最終記事の公開時刻に基づいてスコアを減衰させる。
    - < 2h:  減衰なし (×1.0)
    - 2-6h:  軽度減衰  (×0.85)
    - 6-24h: 中度減衰  (×0.65)
    - 24-72h: 強度減衰 (×0.40)
    - > 72h: 重度減衰  (×0.20)
    """
    if last_article_ts == 0:
        return score  # タイムスタンプ不明時は減衰しない
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
    """
    直近2時間に公開された記事数 vs その前の2〜4時間の記事数を比較してベロシティを算出。
    新規トピックスパイクや急上昇を検出する。
    返り値: -100〜+100 の整数（フロントエンドで velocityScore > 50 → 🔥 急上昇バッジ）
    """
    now = int(time.time())
    recent = sum(1 for a in articles if now - a.get('published_ts', 0) < 7200)
    prev   = sum(1 for a in articles if 7200 <= now - a.get('published_ts', 0) < 14400)

    if prev == 0 and recent > 0:
        return min(100, recent * 20)  # 新規トピックのスパイク
    elif prev == 0:
        return 0

    velocity = int(((recent - prev) / prev) * 100)
    return max(-100, min(100, velocity))


def source_diversity_score(articles: list) -> float:
    """
    単一ソースが全記事の 60% 超を占める場合に 0.8 の係数を返す（多様性ペナルティ）。
    通常は 1.0。
    """
    if not articles:
        return 1.0
    sources = [a.get('source', '') for a in articles]
    counts = Counter(sources)
    top_source_ratio = counts.most_common(1)[0][1] / len(sources)
    return 0.8 if top_source_ratio > 0.6 else 1.0


def compute_lifecycle_status(score: int, last_article_ts: int, velocity_score: int, total_articles: int) -> str:
    """
    記事の流入速度に基づいてライフサイクル状態を判定する。
    時間経過だけで判定しない → 戦争・政治危機など継続型トピックを守る。

    active   → 直近48h以内に記事あり（velocity問わず）
    cooling  → 直近7日以内に記事あり（スコアが一定以上）
    archived → 14日以上記事なし かつ velocity_score <= 0
    legacy   → lifecycle Lambda が別途設定。ここでは設定しない。
    """
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
        return 'cooling'  # 7〜14日 or まだ記事が来る可能性あり → cooling維持


def calc_score(articles):
    """
    バズスコア = (メディア数×10 + はてブ数) × 各種ボーナス係数（整数で保存）
    - 鮮度ボーナス: 6時間以内の記事が1件以上あれば +20%
    - ソース多様性ボーナス: 3メディア以上なら +10%
    - 緊急ワードボーナス: タイトルに速報ワード含む場合 +15%
    """
    media = source_count(articles)
    hb    = 0
    jp_articles = [a for a in articles if '.jp' in a.get('url', '') or 'nhk' in a.get('url', '')]
    for a in jp_articles[:3]:  # 上位3記事だけ取得（速度優先）
        hb += hatena_count(a['url'])

    base = media * 10 + hb

    # 鮮度ボーナス: 過去6時間以内に公開された記事が存在するか
    now_ts = datetime.now(timezone.utc).timestamp()
    recency_bonus = False
    for a in articles:
        try:
            tpl = parsedate_tz(a.get('pubDate', ''))
            if tpl and (now_ts - mktime_tz(tpl)) <= 21600:  # 6h = 21600s
                recency_bonus = True
                break
        except Exception:
            pass

    # ソース多様性ボーナス: 3メディア以上
    diversity_bonus = media >= 3

    # 緊急ワードボーナス: いずれかの記事タイトルに速報ワード
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


# ── 急上昇キーワード抽出 ──────────────────────────────────────────────────────
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
    """全トピックタイトルから急上昇キーワードを抽出して返す。"""
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
# ─────────────────────────────────────────────────────────────────────────────


# ── 関連トピック検出: エンティティ抽出 & トピック間リンク ──────────────────────
ENTITY_PATTERNS = [
    # Countries
    r'アメリカ|米国|アメリカ合衆国',
    r'中国|中華人民共和国',
    r'ロシア|ロシア連邦',
    r'イラン',
    r'イスラエル',
    r'韓国|大韓民国',
    r'北朝鮮|朝鮮民主主義人民共和国',
    r'ウクライナ',
    r'台湾',
    r'インド',
    # Topics/domains
    r'石油|原油|エネルギー',
    r'株価|日経|TOPIX',
    r'円安|円高|為替',
    r'AI|人工知能',
    r'半導体',
    r'金利|利上げ|利下げ',
    r'GDP|景気|インフレ|デフレ',
    r'選挙|大統領|首相|首脳',
    r'軍事|戦争|攻撃|爆撃|ミサイル',
    r'地震|台風|災害',
    r'大谷|翔平',
    r'トランプ',
    r'プーチン',
    r'習近平',
]


def extract_entities(text: str) -> set:
    """Extract known entities from text using pattern matching."""
    entities = set()
    for pattern in ENTITY_PATTERNS:
        if re.search(pattern, text):
            # Use the first alternative as canonical name
            canonical = pattern.split('|')[0]
            entities.add(canonical)
    return entities


def find_related_topics(topics: list, max_related: int = 5) -> dict:
    """
    For each topic, find related topics based on entity overlap.
    Returns: {topicId: [{"topicId": ..., "title": ..., "sharedEntities": [...], "overlapScore": N}, ...]}

    Two topics are related if they share >= 1 entity.
    Sorted by overlap score (more shared entities = higher relevance).
    """
    # Build entity sets for each topic
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
            # 汎用エンティティ（1文字・AI等）だけの一致は除外
            GENERIC = {'ai', 'it', 'ec', 'pc', 'sns', 'dx'}
            meaningful = {e for e in shared if len(e) > 1 and e.lower() not in GENERIC}
            if len(meaningful) >= 2 or (len(meaningful) == 1 and len(shared) >= 2):
                candidates.append({
                    'topicId': oid,
                    'title': other.get('generatedTitle') or other.get('title', ''),
                    'sharedEntities': list(meaningful or shared),
                    'overlapScore': len(meaningful) + len(shared),
                })

        # Sort by overlap score desc, take top N
        candidates.sort(key=lambda x: x['overlapScore'], reverse=True)
        related[tid] = candidates[:max_related]

    return related
# ─────────────────────────────────────────────────────────────────────────────


def detect_topic_hierarchy(topics: list, topic_entities: dict) -> dict:
    """
    Detect parent-child relationships between topics.

    A topic B is considered a "child" of topic A if:
    1. Topic A's entity set is a superset of B's entities (A contains all of B's subjects)
    2. Topic A's score is higher than B's (parent is usually bigger)
    3. Topic A has at least 2 entities (enough context to be a parent)

    Returns: {childTopicId: parentTopicId}
    """
    parent_map = {}

    # Sort by score descending — higher score = more likely to be parent
    sorted_topics = sorted(topics, key=lambda t: int(t.get('score', 0)), reverse=True)

    for i, topic_a in enumerate(sorted_topics):
        tid_a = topic_a['topicId']
        entities_a = topic_entities.get(tid_a, set())
        score_a = int(topic_a.get('score', 0))

        if len(entities_a) < 2:  # need at least 2 entities to be a parent
            continue

        for topic_b in sorted_topics[i + 1:]:
            tid_b = topic_b['topicId']
            if tid_b in parent_map:  # already has a parent
                continue

            entities_b = topic_entities.get(tid_b, set())
            if not entities_b:
                continue

            score_b = int(topic_b.get('score', 0))

            # B is child of A if: A's entities contain all of B's AND A scores higher
            if entities_b.issubset(entities_a) and score_a > score_b and len(entities_a) > len(entities_b):
                parent_map[tid_b] = tid_a

    return parent_map
# ─────────────────────────────────────────────────────────────────────────────


def fetch_ogp_image(url):
    """記事URLからOGP画像URLを取得（2秒タイムアウト、失敗時はNone）"""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Flotopic/1.0'})
        with urllib.request.urlopen(req, timeout=2) as resp:
            html = resp.read(16384).decode('utf-8', errors='ignore')
        # property="og:image" content="..."
        m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
        if m: return m.group(1)
        # content="..." property="og:image"
        m = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html, re.I)
        if m: return m.group(1)
    except Exception:
        pass
    return None


def generate_title(articles):
    """
    Claude APIで記事群の文脈を読んで概念的なトピックタイトルを生成（初回のみ呼ばれる）。
    単記事でも呼ばれるため、1件でも意味のあるタイトルを返すよう設計。
    「〇〇事件」「△△の動向」「▲▲問題」のような要約タイトルを目指す。
    """
    if not ANTHROPIC_API_KEY:
        return None
    headlines = '\n'.join(a['title'] for a in articles[:6])
    prompt = (
        '以下はニュース記事の見出しです。\n'
        'これらが共通して報じているトピックを表す、概念的で簡潔な日本語タイトルを作ってください。\n\n'
        '【出力ルール】\n'
        '- 12〜20文字程度の短いタイトル\n'
        '- 「〇〇事件」「△△問題」「▲▲の動向」「◇◇をめぐる動き」などの形式が望ましい\n'
        '- 記事タイトルをそのままコピーしないこと\n'
        '- 固有名詞や核心キーワードは必ず含める\n'
        '- 説明文・句読点・かぎかっこ不要。タイトルのみ1行で出力\n\n'
        f'見出し:\n{headlines}'
    )
    try:
        body = json.dumps({
            'model': 'claude-haiku-4-5-20251001',
            'max_tokens': 30,
            'messages': [{'role': 'user', 'content': prompt}],
        }).encode('utf-8')
        req = urllib.request.Request(
            'https://api.anthropic.com/v1/messages',
            data=body,
            headers={
                'x-api-key': ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        return data['content'][0]['text'].strip()
    except Exception as e:
        print(f'Title generation error: {e}')
        return None


def generate_summary(articles):
    """Claude APIでトピックの要約を3〜4文で生成（初回のみ呼ばれる）"""
    if not ANTHROPIC_API_KEY:
        return None
    headlines = '\n'.join(a['title'] for a in articles[:8])
    prompt = (
        '以下は同じニューストピックを報じた見出し一覧です。\n'
        'このトピックの概要を分かりやすく2〜3文で要約してください。\n'
        '日本語で150字以内にまとめてください。箇条書き不要。自然な文章のみ出力。\n\n'
        f'見出し:\n{headlines}'
    )
    try:
        body = json.dumps({
            'model': 'claude-haiku-4-5-20251001',
            'max_tokens': 150,
            'messages': [{'role': 'user', 'content': prompt}],
        }).encode('utf-8')
        req = urllib.request.Request(
            'https://api.anthropic.com/v1/messages',
            data=body,
            headers={
                'x-api-key': ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read())
        return data['content'][0]['text'].strip()
    except Exception as e:
        print(f'Summary generation error: {e}')
        return None


# ══════════════════════════════════════════════════════════════════════════════
# コスト削減戦略: Claude API呼び出し削減モジュール
# ══════════════════════════════════════════════════════════════════════════════

# 戦略1: articles_hashベースのキャッシュ（Claude不要ルート）
CACHE_SK_PREFIX = 'CACHE#'

def compute_articles_hash(articles):
    """記事URLのソートされたリストからハッシュを生成。キャッシュキーに使用。"""
    urls = sorted(a['url'] for a in articles)
    return hashlib.md5('|'.join(urls).encode('utf-8')).hexdigest()[:16]


def get_cached_summary(topic_id, articles_hash):
    """
    DynamoDBからキャッシュされたタイトル・要約を取得。
    【Claude不要ルート】: キャッシュヒット時はClaude API呼び出しゼロ。
    Returns: (title, summary) or (None, None)
    """
    try:
        resp = table.get_item(Key={
            'topicId': topic_id,
            'SK': f'{CACHE_SK_PREFIX}{articles_hash}'
        })
        item = resp.get('Item')
        if not item:
            return None, None
        # TTL確認（DynamoDB TTLがある場合は自動削除されるが念のため手動確認）
        cached_at = float(item.get('cachedAtTs', 0))
        if time.time() - cached_at > CLAUDE_CALL_CONDITIONS['cache_ttl_hours'] * 3600:
            return None, None  # 期限切れ
        return item.get('generatedTitle'), item.get('generatedSummary')
    except Exception as e:
        print(f'get_cached_summary error: {e}')
        return None, None


def save_summary_cache(topic_id, articles_hash, title, summary):
    """
    生成した要約をDynamoDBにキャッシュ保存。
    次回同じ記事セットが来たときにClaude呼び出しを回避するため。
    """
    try:
        now_ts = int(time.time())
        ttl_ts = now_ts + int(CLAUDE_CALL_CONDITIONS['cache_ttl_hours'] * 3600)
        item = {
            'topicId': topic_id,
            'SK': f'{CACHE_SK_PREFIX}{articles_hash}',
            'cachedAtTs': Decimal(str(now_ts)),
            'ttl': Decimal(str(ttl_ts)),  # DynamoDB TTL属性（自動削除）
        }
        if title:   item['generatedTitle']   = title
        if summary: item['generatedSummary'] = summary
        table.put_item(Item=item)
    except Exception as e:
        print(f'save_summary_cache error: {e}')


# 戦略2: 抽出的タイトル・要約（Claude不要・コストゼロ）

def clean_title(title):
    """記事タイトルからメディア名サフィックスを除去 例: '記事 - 毎日新聞' → '記事'"""
    import re as _re
    t = _re.sub(r'\s*[-－–|｜]\s*[^\s].{1,25}$', '', title).strip()
    t = _re.sub(r'^\[.{1,20}\]\s*', '', t).strip()  # '[ITmedia News] タイトル' → 'タイトル'
    return t or title


def extractive_title(articles):
    """
    AIを使わない抽出的タイトル生成。最初の記事タイトルをそのまま使う（Claude不要）。
    テンプレートは使わない（「ニュースをめぐる動き」等の無意味タイトル防止）。
    """
    if not articles:
        return ''
    # 最もスコアが高い記事（最初の記事）のタイトルをクリーニングして使う
    first = clean_title(articles[0]['title'])
    return first[:40] + ('…' if len(first) > 40 else '')


def extractive_summary(articles):
    """
    AIを使わない抽出的要約（Claude不要）。
    複数記事見出しからストーリーの流れが読み取れる段落形式。
    Claude版が生成されるまでの仮表示。
    """
    if not articles:
        return None
    # 時系列順（古い順）にソートして経緯を表現
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


# 戦略5: 差分更新（新記事のみClaudeに渡す・トークン削減）

def incremental_summary(existing_summary, new_articles):
    """
    既存要約 + 新着記事だけをClaudeに渡す差分更新。【Claude必要ルート・トークン削減版】
    全記事を渡す代わりに差分だけ渡すことでトークン数を大幅削減。
    Returns updated summary string or None on failure.
    """
    if not ANTHROPIC_API_KEY or not new_articles or not existing_summary:
        return None
    new_headlines = '\n'.join(a['title'] for a in new_articles[:5])
    prompt = (
        f'既存の要約:\n{existing_summary}\n\n'
        f'新着ニュース見出し:\n{new_headlines}\n\n'
        '上記の新着情報を踏まえて、既存の要約を150字以内で更新してください。'
        '日本語、自然な文章のみ出力。'
    )
    try:
        body = json.dumps({
            'model': 'claude-haiku-4-5-20251001',
            'max_tokens': 150,
            'messages': [{'role': 'user', 'content': prompt}],
        }).encode('utf-8')
        req = urllib.request.Request(
            'https://api.anthropic.com/v1/messages',
            data=body,
            headers={
                'x-api-key': ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read())
        return data['content'][0]['text'].strip()
    except Exception as e:
        print(f'incremental_summary error: {e}')
        return None


# ナレッジ蓄積: 要約パターンログ

def log_summary_pattern(topic_id, entity, article_count, method):
    """
    要約生成パターンをDynamoDBメモリDBに記録（非同期・失敗しても続行）。
    method: 'claude' | 'extractive' | 'cached' | 'existing'
    将来的にパターンが溜まればClaude不要の判断精度を向上させるため。
    """
    try:
        memory_table = dynamodb.Table('ai-company-memory')
        now = datetime.now(timezone.utc).isoformat()
        memory_table.put_item(Item={
            'pk': f'SUMMARY_PATTERN#{datetime.now(timezone.utc).strftime("%Y%m")}',
            'sk': f'{topic_id}#{now}',
            'topicId': topic_id,
            'entity': entity,
            'articleCount': Decimal(str(article_count)),
            'method': method,
            'timestamp': now,
        })
    except Exception:
        pass  # 非クリティカル・失敗しても本処理に影響しない

# ══════════════════════════════════════════════════════════════════════════════


def recent_counts(tid, n=5):
    """Return list of (articleCount, timestamp) tuples, newest-first."""
    try:
        r = table.query(
            KeyConditionExpression=Key('topicId').eq(tid) & Key('SK').begins_with('SNAP#'),
            ScanIndexForward=False, Limit=n,
            ProjectionExpression='articleCount, #ts',
            ExpressionAttributeNames={'#ts': 'timestamp'},
        )
        items = r.get('Items', [])
        return [(int(item['articleCount']), item.get('timestamp', '')) for item in items]
    except Exception:
        return []


def calc_velocity(history_with_ts, current_count, now_iso):
    """velocity = (current - prev) / elapsed_hours.
    Returns integer value * 100 to avoid DynamoDB float issues.
    e.g. +3.75 articles/h stored as 375.
    """
    if not history_with_ts:
        return 0
    prev_count, prev_ts = history_with_ts[0]  # most recent previous snapshot
    if not prev_ts:
        return 0
    try:
        t_now  = datetime.fromisoformat(now_iso.replace('Z', '+00:00'))
        t_prev = datetime.fromisoformat(prev_ts.replace('Z', '+00:00'))
        elapsed_hours = (t_now - t_prev).total_seconds() / 3600.0
        if elapsed_hours < 0.01:
            return 0
        velocity = (current_count - prev_count) / elapsed_hours
        return int(round(velocity * 100))
    except Exception:
        return 0


def find_trending_spikes(groups_meta_list):
    """Identify topics where current count > 3x avg of previous snapshots AND count >= 5.
    groups_meta_list: list of (articles, tid, cnt, hist_with_ts)
    Returns list of dicts with title, count, avg_prev.
    """
    spikes = []
    for articles, tid, cnt, hist_with_ts in groups_meta_list:
        if cnt < 5:
            continue
        if not hist_with_ts:
            continue
        prev_counts = [c for c, _ in hist_with_ts]
        avg_prev = sum(prev_counts) / len(prev_counts)
        if avg_prev > 0 and cnt > 3 * avg_prev:
            spikes.append({'title': articles[0]['title'], 'count': cnt, 'avg_prev': avg_prev})
    return spikes


def post_slack_spike(spikes):
    """Post spike alert to Slack webhook."""
    if not SLACK_WEBHOOK or not spikes:
        return
    lines = []
    for s in spikes:
        lines.append("\U0001f525 " + "急上昇トピック検出: " + s['title'] + " (" + str(s['count']) + "件)")
    message = '\n'.join(lines)
    try:
        body = json.dumps({'text': message}).encode('utf-8')
        req = urllib.request.Request(
            SLACK_WEBHOOK,
            data=body,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
        print(f'Slack spike alert sent: {len(spikes)}件')
    except Exception as e:
        print(f'Slack spike alert error: {e}')


def calc_status(history_with_ts, current):
    """history_with_ts: list of (count, ts) newest-first (from recent_counts).
    Uses both total diff AND velocity for accurate status label.
    """
    counts = list(reversed([c for c, _ in history_with_ts])) + [current]
    if len(counts) < 2:
        return 'rising'
    diff = counts[-1] - counts[0]
    # also check the most recent delta
    count_diff_recent = current - history_with_ts[0][0] if history_with_ts else diff
    if diff > 0 or count_diff_recent > 0:
        return 'rising'
    if diff < -1:
        return 'declining'
    return 'peak'


def dec_convert(obj):
    if isinstance(obj, Decimal): return int(obj)
    raise TypeError


def get_all_topics():
    items, kwargs = [], {
        'FilterExpression': 'SK = :m',
        'ExpressionAttributeValues': {':m': 'META'},
        'ProjectionExpression': 'topicId,title,generatedTitle,generatedSummary,imageUrl,#s,articleCount,lastUpdated,genre,genres,#l,score,mediaCount,hatenaCount,lastArticleAt,velocityScore,lifecycleStatus,pendingAI,aiGenerated,relatedTopics,sources',
        'ExpressionAttributeNames': {'#s': 'status', '#l': 'lang'},
    }
    while True:
        r = table.scan(**kwargs)
        items.extend(r.get('Items', []))
        if not r.get('LastEvaluatedKey'): break
        kwargs['ExclusiveStartKey'] = r['LastEvaluatedKey']
    # 時間減衰を topics.json 書き出し時に再適用（DynamoDB保存スコアは古い場合がある）
    for item in items:
        raw_score = int(item.get('score', 0) or 0)
        last_ts   = int(item.get('lastArticleAt', 0) or 0)
        # lastArticleAt 未設定の旧データは lastUpdated をフォールバックに使う
        if last_ts == 0:
            lu = item.get('lastUpdated', '')
            if lu:
                try:
                    # ISO形式 "2026-04-20T16:29:09.737353+00:00" を unix ts に変換
                    lu_norm = lu[:19].replace('T', ' ')
                    from datetime import datetime as _dt, timezone as _tz
                    last_ts = int(_dt.strptime(lu_norm, '%Y-%m-%d %H:%M:%S').replace(tzinfo=_tz.utc).timestamp())
                except Exception:
                    pass
        decayed = apply_time_decay(raw_score, last_ts)
        # 過剰クラスターペナルティ: 記事数/メディア数 > 8 は品質低下フラグ
        cnt   = int(item.get('articleCount', 1) or 1)
        media = int(item.get('mediaCount',   1) or 1)
        ratio = cnt / max(media, 1)
        if ratio > 15:
            decayed = max(1, int(decayed * 0.15))   # 激しい過剰クラスター
        elif ratio > 8:
            decayed = max(1, int(decayed * 0.35))   # 過剰クラスター
        # 大量クラスターのハードキャップ: 30件超のトピックは新鮮な単一ニュースに勝てない
        if cnt > 50:
            decayed = min(decayed, 25)
        elif cnt > 30:
            decayed = min(decayed, 30)
        item['score'] = decayed
        # lifecycleStatus 未設定の旧トピックに自動補完（フロントエンドのフィルタが機能するように）
        if not item.get('lifecycleStatus'):
            hours = (time.time() - last_ts) / 3600 if last_ts else 999
            if hours < 48:
                item['lifecycleStatus'] = 'active'
            elif hours < 168:
                item['lifecycleStatus'] = 'cooling'
            else:
                item['lifecycleStatus'] = 'archived'
    items.sort(key=lambda x: int(x.get('score', 0) or 0), reverse=True)
    return items


def get_topic_detail(tid):
    r     = table.query(KeyConditionExpression=Key('topicId').eq(tid))
    items = r.get('Items', [])
    meta  = next((i for i in items if i['SK'] == 'META'), None)
    snaps = sorted([i for i in items if i['SK'].startswith('SNAP#')], key=lambda x: x['SK'])
    views = sorted([i for i in items if i['SK'].startswith('VIEW#')], key=lambda x: x['SK'])
    return meta, snaps, views


def cleanup_stale(now):
    """72h以上更新なく低スコアのトピックを削除。人気だったもの(score>=30)は保持。"""
    cutoff = (now - timedelta(hours=72)).isoformat()
    kwargs = {
        'FilterExpression': 'SK = :m AND lastUpdated < :cut',
        'ExpressionAttributeValues': {':m': 'META', ':cut': cutoff},
        'ProjectionExpression': 'topicId, score',
    }
    stale = []
    while True:
        r = table.scan(**kwargs)
        stale.extend(r.get('Items', []))
        if not r.get('LastEvaluatedKey'): break
        kwargs['ExclusiveStartKey'] = r['LastEvaluatedKey']

    deleted = 0
    for item in stale:
        if int(item.get('score', 0) or 0) >= 30:
            continue  # 流行したトピックは保持
        tid = item['topicId']
        all_items = table.query(KeyConditionExpression=Key('topicId').eq(tid)).get('Items', [])
        with table.batch_writer() as batch:
            for i in all_items:
                batch.delete_item(Key={'topicId': i['topicId'], 'SK': i['SK']})
        deleted += 1
    if deleted:
        print(f'Cleanup: {deleted}件削除')


def write_s3(key, data):
    if not S3_BUCKET: return
    s3.put_object(
        Bucket=S3_BUCKET, Key=key,
        Body=json.dumps(data, default=dec_convert, ensure_ascii=False).encode('utf-8'),
        ContentType='application/json', CacheControl='max-age=60',
    )


def generate_rss(topics, updated_at):
    """article_count降順で上位20トピックのRSS 2.0 XMLを生成しS3に保存"""
    if not S3_BUCKET:
        return

    site_url = os.environ.get('SITE_URL', 'https://flotopic.com')

    # article_count降順・上位20件
    sorted_topics = sorted(
        topics,
        key=lambda x: int(x.get('articleCount', 0) or 0),
        reverse=True,
    )[:20]

    def esc(text):
        if not text:
            return ''
        return (
            str(text)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&apos;')
        )

    def to_rfc2822(iso_str):
        """ISO 8601 → RFC 2822"""
        try:
            dt = datetime.fromisoformat(str(iso_str).replace('Z', '+00:00'))
            return dt.strftime('%a, %d %b %Y %H:%M:%S +0000')
        except Exception:
            return datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000')

    items_xml = ''
    for t in sorted_topics:
        tid         = t.get('topicId', '')
        title       = esc(t.get('generatedTitle') or t.get('title', ''))
        description = esc(t.get('generatedSummary') or t.get('generatedTitle') or t.get('title', ''))
        link        = f'{site_url}/topic.html?id={tid}'
        pub_date    = to_rfc2822(t.get('lastUpdated', updated_at))
        genre       = esc(t.get('genre', ''))

        items_xml += (
            f'    <item>\n'
            f'      <title>{title}</title>\n'
            f'      <description>{description}</description>\n'
            f'      <link>{link}</link>\n'
            f'      <guid isPermaLink="true">{link}</guid>\n'
            f'      <pubDate>{pub_date}</pubDate>\n'
            f'      <category>{genre}</category>\n'
            f'    </item>\n'
        )

    now_rfc2822 = to_rfc2822(updated_at)
    rss_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
        '  <channel>\n'
        '    <title>Flotopic</title>\n'
        f'    <link>{site_url}/</link>\n'
        '    <description>話題の流れをAIで追う日本語ニュースまとめ</description>\n'
        '    <language>ja</language>\n'
        f'    <lastBuildDate>{now_rfc2822}</lastBuildDate>\n'
        '    <ttl>30</ttl>\n'
        f'    <atom:link href="{site_url}/rss.xml" rel="self" type="application/rss+xml"/>\n'
        f'{items_xml}'
        '  </channel>\n'
        '</rss>\n'
    )

    try:
        s3.put_object(
            Bucket=S3_BUCKET, Key='rss.xml',
            Body=rss_xml.encode('utf-8'),
            ContentType='application/rss+xml; charset=utf-8',
            CacheControl='max-age=1800',
        )
        print(f'RSS生成完了 ({len(sorted_topics)}件)')
    except Exception as e:
        print(f'RSS生成エラー: {e}')


def generate_sitemap(topics):
    """全トピックのサイトマップXMLを生成してS3に保存"""
    if not S3_BUCKET:
        return

    site_url = os.environ.get('SITE_URL', 'https://flotopic.com')

    def to_date(iso_str):
        try:
            dt = datetime.fromisoformat(str(iso_str).replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d')
        except Exception:
            return datetime.now(timezone.utc).strftime('%Y-%m-%d')

    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    urls_xml = (
        '  <url>\n'
        f'    <loc>{site_url}/</loc>\n'
        '    <changefreq>hourly</changefreq>\n'
        '    <priority>1.0</priority>\n'
        '  </url>\n'
    )

    for t in topics:
        tid      = t.get('topicId', '')
        if not tid:
            continue
        lastmod  = to_date(t.get('lastUpdated', today))
        urls_xml += (
            '  <url>\n'
            f'    <loc>{site_url}/topic.html?id={tid}</loc>\n'
            f'    <lastmod>{lastmod}</lastmod>\n'
            '    <changefreq>hourly</changefreq>\n'
            '    <priority>0.8</priority>\n'
            '  </url>\n'
        )

    sitemap_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'{urls_xml}'
        '</urlset>\n'
    )

    try:
        s3.put_object(
            Bucket=S3_BUCKET, Key='sitemap.xml',
            Body=sitemap_xml.encode('utf-8'),
            ContentType='application/xml',
            CacheControl='max-age=3600',
        )
        print(f'サイトマップ生成完了 ({len(topics)}件)')
    except Exception as e:
        print(f'サイトマップ生成エラー: {e}')


# ── 差分更新用: 既知記事URLの永続化 ──────────────────────────────
SEEN_KEY = 'api/seen_articles.json'
# 保持するURL数の上限（古いものから切り捨て）
SEEN_MAX = 3000

def load_seen_articles():
    """S3から前回取得済み記事URLセットを読み込む。初回または取得失敗時は空setを返す。"""
    if not S3_BUCKET:
        return set()
    try:
        resp = s3.get_object(Bucket=S3_BUCKET, Key=SEEN_KEY)
        data = json.loads(resp['Body'].read())
        return set(data.get('urls', []))
    except s3.exceptions.NoSuchKey:
        return set()  # 初回起動
    except Exception as e:
        print(f'load_seen_articles error: {e}')
        return set()


def save_seen_articles(current_urls: set):
    """現在取得した記事URLセットをS3に保存。上限を超えた場合は古いものを切り捨て。"""
    if not S3_BUCKET:
        return
    url_list = list(current_urls)[:SEEN_MAX]
    try:
        s3.put_object(
            Bucket=S3_BUCKET, Key=SEEN_KEY,
            Body=json.dumps(
                {'urls': url_list, 'savedAt': datetime.now(timezone.utc).isoformat()},
                ensure_ascii=False,
            ).encode('utf-8'),
            ContentType='application/json', CacheControl='no-cache',
        )
    except Exception as e:
        print(f'save_seen_articles error: {e}')
# ─────────────────────────────────────────────────────────────────


def lambda_handler(event, context):
    # ── Step 1: 前回既知URLを読み込む（差分更新用） ────────────────
    seen_urls = load_seen_articles()

    # ── Step 2: 全RSSフィードを取得 ────────────────────────────────
    all_articles = []
    for feed in RSS_FEEDS:
        fetched = fetch_rss(feed)
        all_articles.extend(fetched)
        print(f'[{feed["genre"]}] {feed["url"].split("/")[2]}: {len(fetched)}件')

    print(f'合計: {len(all_articles)}記事')

    # ── Step 3: 差分チェック ─────────────────────────────────────
    current_urls = {a['url'] for a in all_articles}
    new_urls = current_urls - seen_urls

    # seen_urls が空（初回起動）の場合は必ず全件処理する
    if seen_urls and not new_urls:
        print('新規記事なし。DynamoDB/Claude API 呼び出しをスキップします。')
        # URLセットを最新化して終了（次回以降のために更新は行う）
        save_seen_articles(current_urls)
        return {'statusCode': 200,
                'body': json.dumps({'articles': len(all_articles), 'new': 0, 'skipped': True})}

    print(f'新規記事: {len(new_urls)}件 / 既知: {len(seen_urls)}件')
    # ─────────────────────────────────────────────────────────────

    groups = cluster(all_articles)
    print(f'トピック数: {len(groups)}')

    # スコア上位AI_GENERATION_LIMIT件のみClaude API呼び出しを行うため、
    # 事前にメディア数×10で簡易スコアを計算してソートしておく
    groups_sorted = sorted(groups, key=lambda g: len({a['source'] for a in g}) * 10, reverse=True)

    now    = datetime.now(timezone.utc)
    ts_key = now.strftime('%Y%m%dT%H%M%SZ')
    ts_iso = now.isoformat()

    saved_ids = []
    groups_meta_list = []  # for spike detection: [(articles, tid, cnt, hist_with_ts)]
    ogp_fetched = 0  # OGP取得は上位20トピックまで
    api_calls_this_run = 0  # Claude API呼び出し回数カウンター
    for rank, g in enumerate(groups_sorted):
        tid    = topic_fingerprint(g)
        cnt    = len(g)
        genres = dominant_genres(g)
        genre  = genres[0]   # 後方互換用プライマリ
        lang   = dominant_lang(g)
        hist  = recent_counts(tid)  # list of (count, ts) newest-first
        groups_meta_list.append((g, tid, cnt, hist))
        st    = calc_status(hist, cnt)
        score, media, hb = calc_score(g)

        # ── 鮮度・多様性による後処理スコアリング ──────────────────────
        # 最終記事タイムスタンプ（時間減衰・lastArticleAt 保存用）
        last_article_ts = max((a.get('published_ts', 0) for a in g), default=0)
        # 時間減衰を適用（古いトピックを自然に降順）
        score = apply_time_decay(score, last_article_ts)
        # 単一ソース支配ペナルティ（×0.8）
        score = max(1, int(score * source_diversity_score(g)))
        # ベロシティスコア（急上昇バッジ用：> 50 で 🔥）
        velocity_score = calc_velocity_score(g)
        # ─────────────────────────────────────────────────────────────

        # ── Stage 1 (fetcher): 抽出的要約のみ・Claude呼び出しゼロ ─────────────
        # Claude処理は processor Lambda（1日3回 JST 7:00/12:00/18:00）が担当する。
        # このLambdaではClaude APIを一切呼び出さない。

        existing = table.get_item(Key={'topicId': tid, 'SK': 'META'}).get('Item', {})

        # タイトル: Claude生成済みを保持 / 未処理は抽出的生成（即時表示用）
        # 【Claude不要ルート・コストゼロ】
        if existing.get('aiGenerated') and existing.get('generatedTitle'):
            gen_title = existing['generatedTitle']   # processor済み → 保持
        else:
            # 抽出的タイトル（processor Lambdaが後でClaude版に上書きする）
            gen_title = existing.get('generatedTitle') or extractive_title(g)

        # 要約: Claude生成済みを保持 / 未処理は3件以上で抽出的生成
        # 【Claude不要ルート・コストゼロ】
        if existing.get('aiGenerated') and existing.get('generatedSummary'):
            gen_summary = existing['generatedSummary']  # processor済み → 保持
        else:
            gen_summary = existing.get('generatedSummary') or (
                extractive_summary(g) if cnt >= 3 else None
            )

        # processor Lambda向けフラグ: aiGenerated=Trueでないトピックをマーク
        # processor が処理後に aiGenerated=True, pendingAI=False に更新する
        pending_ai = not bool(existing.get('aiGenerated'))

        # パターンログ（ai-company-memoryに記録）
        _all_entities = extract_entities(' '.join(a['title'] for a in g))
        _main_entity  = list(_all_entities)[0] if _all_entities else ''
        log_summary_pattern(tid, _main_entity, cnt, 'extractive' if pending_ai else 'existing')
        # ─────────────────────────────────────────────────────────────────────

        # 画像URL: RSSメディアタグ → OGPフォールバック（上位スコアのトピックのみ）
        image_url = existing.get('imageUrl') or next(
            (a.get('imageUrl') for a in g if a.get('imageUrl')), None
        )
        if not image_url and cnt >= 2 and ogp_fetched < 20:
            jp_urls = [a['url'] for a in g if '.jp' in a.get('url', '')]
            check_urls = jp_urls[:2] + [a['url'] for a in g[:3] if a['url'] not in jp_urls]
            for u in check_urls[:3]:
                image_url = fetch_ogp_image(u)
                if image_url:
                    ogp_fetched += 1
                    break

        velocity = calc_velocity(hist, cnt, ts_iso)

        # ライフサイクル状態: 既存が 'legacy' なら上書きしない（lifecycle Lambda が管理）
        existing_lifecycle = existing.get('lifecycleStatus', '')
        if existing_lifecycle == 'legacy':
            lifecycle_status = 'legacy'
        else:
            lifecycle_status = compute_lifecycle_status(score, last_article_ts, velocity_score, cnt)

        item = {
            'topicId':          tid,
            'SK':               'META',
            'title':            g[0]['title'],
            'generatedTitle':   gen_title or g[0]['title'],
            'status':           st,
            'genre':            genre,
            'genres':           genres,
            'lang':             lang,
            'articleCount':     cnt,
            'mediaCount':       media,
            'hatenaCount':      hb,
            'score':            score,
            'velocity':         velocity,
            'velocityScore':    velocity_score,
            'lastUpdated':      ts_iso,
            'lastArticleAt':    last_article_ts,
            'lifecycleStatus':  lifecycle_status,
            'sources':          list({a['source'] for a in g}),
            'pendingAI':        pending_ai,   # True → processor Lambdaが未処理
        }
        if gen_summary: item['generatedSummary'] = gen_summary
        if image_url:   item['imageUrl'] = image_url
        table.put_item(Item=item)
        table.put_item(Item={
            'topicId':      tid,
            'SK':           f'SNAP#{ts_key}',
            'articleCount': cnt,
            'score':        score,
            'hatenaCount':  hb,
            'mediaCount':   media,
            'timestamp':    ts_iso,
            'articles': sort_by_pubdate(list({
                a['source']: {
                    'title': a['title'], 'url': a['url'],
                    'source': a['source'], 'pubDate': a['pubDate'],
                } for a in g  # ソースごとに最初の1記事のみ
            }.values()))[:20],
        })
        saved_ids.append(tid)

    if S3_BUCKET:
        topics = get_all_topics()
        # ── 関連トピック検出（S3書き出し前にメモリ上で付与）──────────────
        related_map = find_related_topics(topics)
        for t in topics:
            t['relatedTopics'] = related_map.get(t.get('topicId', ''), [])
        # ─────────────────────────────────────────────────────────────────

        # ── 親子トピック階層検出 ───────────────────────────────────────────
        topic_entities_map = {
            t['topicId']: extract_entities(
                (t.get('generatedTitle') or t.get('title', ''))
            )
            for t in topics
        }
        parent_map = detect_topic_hierarchy(topics, topic_entities_map)

        # Store parentTopicId / childTopics on each topic (in-memory only)
        child_to_parent = {}  # tid_b -> tid_a
        parent_to_children = {}  # tid_a -> [{topicId, title}]
        for tid_b, tid_a in parent_map.items():
            child_to_parent[tid_b] = tid_a
            parent_to_children.setdefault(tid_a, [])
            # Look up the child topic's title
            child_t = next((t for t in topics if t['topicId'] == tid_b), None)
            if child_t:
                parent_to_children[tid_a].append({
                    'topicId': tid_b,
                    'title': child_t.get('generatedTitle') or child_t.get('title', ''),
                })

        for t in topics:
            tid = t['topicId']
            if tid in child_to_parent:
                t['parentTopicId'] = child_to_parent[tid]
            if tid in parent_to_children:
                t['childTopics'] = parent_to_children[tid]
        # ─────────────────────────────────────────────────────────────────
        # 重複タイトルを排除（2段階）
        # 1. 長キー (normalized title[:50]) — 完全一致
        # 2. 短キー (記号除去後の先頭18文字) — "ChatGPT Images 2.0発表" と "ChatGPT Images 2.0リリース" を同一視
        def _norm_title(t):
            s = (t.get('generatedTitle') or t.get('title', '')).strip()
            s = s.replace('｢','「').replace('｣','」').replace('　',' ')
            s = re.sub(r'\s+', ' ', s)
            s = re.sub(r'\s*[-－–|｜]\s*[^\s].{1,25}$', '', s)
            return s.lower()[:50]
        def _core_key(t):
            s = (t.get('generatedTitle') or t.get('title', '')).lower()
            s = re.sub(r'[「」【】・、。,!?！？\[\]()（）『』""\'\'#＃]', '', s)
            s = re.sub(r'\s+', '', s)
            return s[:18]
        dedup_long = {}  # long key → topic
        dedup_core = {}  # core key → topic
        for t in topics:
            kl = _norm_title(t)
            kc = _core_key(t)
            sc = int(t.get('score', 0) or 0)
            if kl in dedup_long:
                if sc > int(dedup_long[kl].get('score', 0) or 0):
                    dedup_long[kl] = t
                    dedup_core[kc] = t
            elif kc in dedup_core:
                if sc > int(dedup_core[kc].get('score', 0) or 0):
                    old_kl = _norm_title(dedup_core[kc])
                    dedup_long.pop(old_kl, None)
                    dedup_long[kl] = t
                    dedup_core[kc] = t
            else:
                dedup_long[kl] = t
                dedup_core[kc] = t
        topics_deduped = sorted(dedup_long.values(), key=lambda x: int(x.get('score', 0) or 0), reverse=True)
        write_s3('api/topics.json', {'topics': topics_deduped, 'trendingKeywords': extract_trending_keywords(topics_deduped), 'updatedAt': ts_iso})
        generate_rss(topics, ts_iso)
        generate_sitemap(topics)
        for tid in saved_ids:
            meta, snaps, views = get_topic_detail(tid)
            if meta:
                meta['relatedTopics'] = related_map.get(tid, [])
                if tid in child_to_parent:
                    meta['parentTopicId'] = child_to_parent[tid]
                if tid in parent_to_children:
                    meta['childTopics'] = parent_to_children[tid]
                write_s3(f'api/topic/{tid}.json', {
                    'meta': meta,
                    'timeline': [
                        {'timestamp': s['timestamp'],
                         'articleCount': s['articleCount'],
                         'score': s.get('score', 0),
                         'hatenaCount': s.get('hatenaCount', 0),
                         'articles': s.get('articles', [])}
                        for s in snaps
                    ],
                    'views': [
                        {'date': v['date'], 'count': int(v.get('count', 0))}
                        for v in views
                    ],
                })
        print('S3書き出し完了')

    print(f'Claude API呼び出し回数: {api_calls_this_run} / {MAX_API_CALLS}')

    # ── Spike detection ──────────────────────────────────────────────────
    spikes = find_trending_spikes(groups_meta_list)
    if spikes:
        post_slack_spike(spikes)
    # ─────────────────────────────────────────────────────────────────────

    cleanup_stale(now)

    # ── Step 4: 今回取得URLを保存（次回差分チェック用） ─────────────
    save_seen_articles(current_urls)
    # ─────────────────────────────────────────────────────────────

    return {'statusCode': 200,
            'body': json.dumps({'articles': len(all_articles), 'new': len(new_urls), 'topics': len(groups_sorted), 'api_calls': api_calls_this_run, 'ts': ts_key})}
