import os
import boto3

TABLE_NAME        = os.environ.get('TABLE_NAME', 'p003-topics')
S3_BUCKET         = os.environ.get('S3_BUCKET', '')
REGION            = os.environ.get('REGION', 'ap-northeast-1')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
SLACK_WEBHOOK     = os.environ.get('SLACK_WEBHOOK', '')
SITE_URL          = os.environ.get('SITE_URL', 'https://flotopic.com')

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

JACCARD_THRESHOLD = 0.35
MAX_CLUSTER_SIZE  = 20

AI_GENERATION_LIMIT = 10
MAX_API_CALLS = 20

CLAUDE_CALL_CONDITIONS = {
    "min_articles_for_title":   3,
    "min_articles_for_summary": 5,
    "min_velocity_score":      20,
    "max_calls_per_run":       10,
    "cache_ttl_hours":          6,
}

STOP_WORDS = {
    'は','が','を','に','の','と','で','も','や','か','へ','より','から','まで',
    'という','として','による','において','について','した','する','して',
    'された','される','てい','ます','です','だっ','ある','いる','なっ','れる',
    'ニュース','news','yahoo','google','livedoor','narinari','gigazine','gizmodo',
    'itmatedia','itmedia','watch','ascii','pc','日経','読売','毎日','朝日','nhk',
    'reuters','bloomberg','報道','記事','速報','最新','情報','解説','まとめ',
    '続報','詳細','動画','写真','インタビュー','コメント','発表','掲載',
    'the','a','an','is','are','was','were','be','been','of','in','to','for',
    'on','at','by','with','as','from','that','this','it','its','and','or',
    'but','not','have','has','had','will','would','could','should','says',
    'said','new','more','after','over','after','about','up','out','two',
    'into','than','he','she','his','her','they','we','you','i',
}

SYNONYMS = {
    'アメリカ':'米国','米':'米国','usa':'米国','us':'米国',
    '総理':'首相','内閣総理大臣':'首相',
    '円相場':'為替','ドル円':'為替',
    '利上げ':'金利','利下げ':'金利',
    'オリンピック':'五輪','olympic':'五輪',
    'chatgpt':'ai','gpt':'ai','claude':'ai','gemini':'ai',
}

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

ENTITY_PATTERNS = [
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

MEDIA_NS = {
    'media':   'http://search.yahoo.com/mrss/',
    'content': 'http://purl.org/rss/1.0/modules/content/',
}

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
    'news.google.com': None,
    'president.jp': 'PRESIDENT Online',
    'bunshun.jp': '文春オンライン',
    'www.businessinsider.jp': 'Business Insider Japan',
    'forbesjapan.com': 'Forbes Japan',
    'gigazine.net': 'GIGAZINE',
    'ascii.jp': 'ASCII.jp',
    'news.livedoor.com': 'livedoorニュース',
}

URGENT_WORDS = {'緊急', '速報', '重大', '急騰', '急落', '大幅', '速報', '号外', '警報', '警告', '危機', '緊迫'}

CACHE_SK_PREFIX = 'CACHE#'

SEEN_KEY = 'api/seen_articles.json'
SEEN_MAX = 3000

# SNAPアイテムの保持期間（日）。DynamoDB TTLで自動削除される
SNAP_TTL_DAYS = 7
