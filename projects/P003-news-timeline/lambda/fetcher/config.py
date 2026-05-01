import os
import boto3

TABLE_NAME    = os.environ.get('TABLE_NAME', 'p003-topics')
S3_BUCKET     = os.environ.get('S3_BUCKET', '')
REGION        = os.environ.get('REGION', 'ap-northeast-1')
SLACK_WEBHOOK = os.environ.get('SLACK_WEBHOOK', '')
SITE_URL      = os.environ.get('SITE_URL', 'https://flotopic.com')
# T2026-0501-H: borderline トピック merge 判定 (Jaccard 0.15-0.35) を Haiku に委譲する。
# 未設定時は failsafe で merge しない (現状挙動と同等)。
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

from botocore.config import Config as BotocoreConfig
_boto_cfg = BotocoreConfig(max_pool_connections=50)
dynamodb = boto3.resource('dynamodb', region_name=REGION, config=_boto_cfg)
table    = dynamodb.Table(TABLE_NAME)
s3       = boto3.client('s3', region_name=REGION, config=_boto_cfg)

RSS_FEEDS = [
    # ===== Google News（日本語・カテゴリ別）=====
    # 判定: ⚠️ グレーゾーン（ToSは個人利用が前提だが明示的商業禁止なし）→ 残す
    # tier=3: アグリゲーター（実際の記事ソースに依存）
    {'url': 'https://news.google.com/rss/headlines/section/topic/NATION?hl=ja&gl=JP&ceid=JP:ja',         'genre': '総合',       'tier': 3},
    {'url': 'https://news.google.com/rss/headlines/section/topic/POLITICS?hl=ja&gl=JP&ceid=JP:ja',       'genre': '政治',       'tier': 3},
    {'url': 'https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=ja&gl=JP&ceid=JP:ja',       'genre': 'ビジネス',   'tier': 3},
    {'url': 'https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=ja&gl=JP&ceid=JP:ja',     'genre': 'テクノロジー', 'tier': 3},
    {'url': 'https://news.google.com/rss/headlines/section/topic/SPORTS?hl=ja&gl=JP&ceid=JP:ja',         'genre': 'スポーツ',   'tier': 3},
    {'url': 'https://news.google.com/rss/headlines/section/topic/ENTERTAINMENT?hl=ja&gl=JP&ceid=JP:ja',  'genre': 'エンタメ',   'tier': 3},
    {'url': 'https://news.google.com/rss/headlines/section/topic/SCIENCE?hl=ja&gl=JP&ceid=JP:ja',        'genre': '科学',       'tier': 3},
    {'url': 'https://news.google.com/rss/headlines/section/topic/HEALTH?hl=ja&gl=JP&ceid=JP:ja',         'genre': '健康',       'tier': 3},
    {'url': 'https://news.google.com/rss/headlines/section/topic/WORLD?hl=ja&gl=JP&ceid=JP:ja',          'genre': '国際',       'tier': 3},
    # ===== ライブドアニュース =====
    # 判定: ⚠️ グレーゾーン（明示的商業禁止なし）→ 残す
    # tier=3: アグリゲーター
    {'url': 'https://news.livedoor.com/topics/rss/dom.xml', 'genre': '総合',   'tier': 3},
    {'url': 'https://news.livedoor.com/topics/rss/ent.xml', 'genre': 'エンタメ', 'tier': 3},
    {'url': 'https://news.livedoor.com/topics/rss/spo.xml', 'genre': 'スポーツ', 'tier': 3},
    {'url': 'https://news.livedoor.com/topics/rss/int.xml', 'genre': '国際',   'tier': 3},
    # ===== テクノロジー系 =====
    # ITmedia: ⚠️ グレーゾーン（RSS配信に積極的・明示的商業禁止なし）→ 残す
    # tier=2: 主要テクノロジーメディア
    {'url': 'https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml', 'genre': 'テクノロジー', 'tier': 2},
    {'url': 'https://rss.itmedia.co.jp/rss/2.0/itmedia_all.xml', 'genre': 'テクノロジー', 'tier': 2},
    # Gigazine: ⚠️ グレーゾーン→ 残す
    {'url': 'https://gigazine.net/news/rss_2.0/',                 'genre': 'テクノロジー', 'tier': 2},
    # ASCII.jp: ⚠️ グレーゾーン→ 残す
    {'url': 'https://ascii.jp/rss.xml',                           'genre': 'テクノロジー', 'tier': 2},
    # Gizmodo Japan: ⚠️ グレーゾーン→ 残す
    {'url': 'https://www.gizmodo.jp/index.xml',                   'genre': 'テクノロジー', 'tier': 2},
    # CNET Japan: ✅ 2026-04-25確認 30件・RSS公開・商業利用制限なし
    {'url': 'https://feeds.japan.cnet.com/rss/cnet/all.rdf',      'genre': 'テクノロジー', 'tier': 2},
    # PC Watch / ケータイWatch (Impress): ✅ 2026-04-25確認・RSS明示公開
    {'url': 'https://pc.watch.impress.co.jp/data/rss/1.0/pcw/feed.rdf',    'genre': 'テクノロジー', 'tier': 2},
    {'url': 'https://k-tai.watch.impress.co.jp/data/rss/1.0/ktw/feed.rdf', 'genre': 'テクノロジー', 'tier': 2},
    # ===== 総合・一般紙 =====
    # NHK: ✅ 公共放送・見出し+リンクは広く許容→ 残す
    # tier=1: 一次情報・権威性高
    # cat0(総合)とcat5(生活文化)はcat1〜cat4と重複するため除外（NHK偏重防止 2026-04-26）
    {'url': 'https://www3.nhk.or.jp/rss/news/cat1.xml',           'genre': '社会',       'tier': 1},  # NHK 社会
    {'url': 'https://www3.nhk.or.jp/rss/news/cat2.xml',           'genre': 'エンタメ',   'tier': 1},  # NHK 文化・エンタメ
    {'url': 'https://www3.nhk.or.jp/rss/news/cat3.xml',           'genre': '政治',       'tier': 1},  # NHK 政治
    {'url': 'https://www3.nhk.or.jp/rss/news/cat4.xml',           'genre': 'くらし',     'tier': 1},  # NHK 暮らし・健康
    {'url': 'https://www3.nhk.or.jp/rss/news/cat6.xml',           'genre': '国際',       'tier': 1},  # NHK 国際
    {'url': 'https://www3.nhk.or.jp/rss/news/cat7.xml',           'genre': 'スポーツ',   'tier': 1},
    # 毎日新聞: ⚠️ グレーゾーン（明示的商業禁止なし・積極的な訴訟実績なし）→ 残す
    # tier=2: 主要一般紙
    {'url': 'https://mainichi.jp/rss/etc/mainichi-flash.rss',     'genre': '総合', 'tier': 2},
    # 朝日新聞: ⚠️ グレーゾーン（同上）→ 残す
    {'url': 'https://www.asahi.com/rss/asahi/newsheadlines.rdf',  'genre': '総合', 'tier': 2},
    # 読売新聞: ❌ 削除 — 2002年「読売オンライン vs デジタルアライアンス」判決でリンク集・見出し転載を問題視。
    #           RSS利用規約に「著作権者の許諾なく商業目的での利用を禁ずる」旨の記載あり。リスク高のため除外。
    # {'url': 'https://www.yomiuri.co.jp/feed/', 'genre': '総合'},  # ← 除外済み
    # ===== ビジネス・経済 =====
    # 東洋経済: ⚠️ グレーゾーン→ 残す
    # tier=2: 主要経済メディア
    {'url': 'https://toyokeizai.net/list/feed/rss',  'genre': 'ビジネス', 'tier': 2},
    # ダイヤモンド: ❌ 削除 — RSSフィードURLが非フィードページにリダイレクト（2026-04-25確認）
    # {'url': 'https://diamond.jp/list/feed/rss', 'genre': 'ビジネス', 'tier': 2},
    # 日経: ❌ 削除 — 日経は著作権保護に極めて積極的（「ネット上の無断転載に対し法的措置」と明言）。
    #       RSS利用規約で「個人利用目的のみ」と明記。商業利用は明確にNG。
    # {'url': 'https://www.nikkei.com/rss/index.xml', 'genre': '株・金融'},  # ← 除外済み
    # ===== 株・金融（Google News検索RSS）=====
    # 判定: ⚠️ Google News同様グレーゾーン→ 残す
    {'url': 'https://news.google.com/rss/search?q=%E6%A0%AA%E4%BE%A1+%E6%97%A5%E6%9C%AC&hl=ja&gl=JP&ceid=JP:ja',    'genre': '株・金融', 'tier': 3},
    {'url': 'https://news.google.com/rss/search?q=%E6%97%A5%E9%8A%80+%E9%87%91%E5%88%A9+%E7%82%BA%E6%9B%BF&hl=ja&gl=JP&ceid=JP:ja', 'genre': '株・金融', 'tier': 3},
    {'url': 'https://news.google.com/rss/search?q=%E6%B1%BA%E7%AE%97+%E4%B8%8A%E5%A0%B4+%E6%A0%AA%E5%BC%8F&hl=ja&gl=JP&ceid=JP:ja', 'genre': '株・金融', 'tier': 3},
    # ===== 官公庁・政府系 =====
    # 首相官邸: ❌ 削除 — RSSフィード廃止（404確認 2026-04-25）。政治ニュースはNHK cat3で代替カバー済み。
    # ===== ほっこり・くらし・話題系 =====
    # BuzzFeed Japan: ⚠️ グレーゾーン（明示的商業禁止なし）→ 残す
    # tier=3: バイラル・くらし・面白記事混在
    {'url': 'https://www.buzzfeed.com/jp.xml',              'genre': 'くらし', 'tier': 3},  # BuzzFeed Japan
    # ===== グルメ・ファッション・美容（Google News検索RSS）=====
    # 判定: ⚠️ Google News同様グレーゾーン→ 残す
    # T2026-0428-AU: グルメ/ファッション系は genre を「総合」ではなく明示する。
    # 旧設定だと AI 後段で再分類されるまで「総合」扱いで埋もれていた。
    {'url': 'https://news.google.com/rss/search?q=%E3%82%B0%E3%83%AB%E3%83%A1+%E3%83%AC%E3%82%B9%E3%83%88%E3%83%A9%E3%83%B3+%E6%97%A5%E6%9C%AC&hl=ja&gl=JP&ceid=JP:ja',   'genre': 'グルメ', 'tier': 3},
    {'url': 'https://news.google.com/rss/search?q=%E6%96%99%E7%90%86+%E3%83%AC%E3%82%B7%E3%83%94+%E9%A3%9F%E4%BA%8B&hl=ja&gl=JP&ceid=JP:ja',                              'genre': 'グルメ', 'tier': 3},
    {'url': 'https://news.google.com/rss/search?q=%E3%83%95%E3%82%A1%E3%83%83%E3%82%B7%E3%83%A7%E3%83%B3+%E3%83%88%E3%83%AC%E3%83%B3%E3%83%89+%E3%83%96%E3%83%A9%E3%83%B3%E3%83%89&hl=ja&gl=JP&ceid=JP:ja', 'genre': 'ファッション', 'tier': 3},
    {'url': 'https://news.google.com/rss/search?q=%E7%BE%8E%E5%AE%B9+%E3%82%B3%E3%82%B9%E3%83%A1+%E3%82%B9%E3%82%AD%E3%83%B3%E3%82%B1%E3%82%A2&hl=ja&gl=JP&ceid=JP:ja',  'genre': 'ファッション', 'tier': 3},
    # ===== ファッション専門メディア（T2026-0428-AU 追加）=====
    # ファッションカテゴリが 0件問題への対応。VOGUE Japan / WWD Japan は直接 RSS が取れないため
    # Google News site: 検索 RSS で代替。ELLE Japan は公式 RSS が稼働しているため直接購読。
    # 判定: ⚠️ Google News 経由はグレーゾーン継続/ELLE 公式は明示公開→ 採用
    {'url': 'https://news.google.com/rss/search?q=site%3Avogue.co.jp&hl=ja&gl=JP&ceid=JP:ja',     'genre': 'ファッション', 'tier': 2},
    {'url': 'https://news.google.com/rss/search?q=site%3Awwdjapan.com&hl=ja&gl=JP&ceid=JP:ja',    'genre': 'ファッション', 'tier': 2},
    {'url': 'https://www.elle.com/jp/rss/all.xml',                                                'genre': 'ファッション', 'tier': 2},
    # ===== 沖縄県紙（T2026-0428-AU 追加）=====
    # 辺野古・普天間・米軍関連は本土紙では扱いが薄く、ユーザーから「沖縄関連が少ない」指摘あり。
    # 直接 RSS は提供されていないため Google News site: 検索 RSS で代替。
    # 沖縄県内の社会・基地問題は『社会』ジャンルとして扱う (主語=自治体・住民・米軍)。
    {'url': 'https://news.google.com/rss/search?q=site%3Aryukyushimpo.jp&hl=ja&gl=JP&ceid=JP:ja',    'genre': '社会', 'tier': 2},
    {'url': 'https://news.google.com/rss/search?q=site%3Aokinawatimes.co.jp&hl=ja&gl=JP&ceid=JP:ja', 'genre': '社会', 'tier': 2},
]

# ソースドメイン → tier マッピング（Google News経由の記事など、フィードtierが使えない場合のフォールバック）
# 注意: このマップは source 名文字列ベースのため偽装に弱い。
# 一次情報の物理判定は score_utils.is_primary_source(url) を使うこと（T2026-0428-AN）。
SOURCE_TIER_MAP = {
    # Tier 1: 一次情報・権威性高（URL ドメインでも is_primary_source が True を返す媒体）
    'NHK':                 1,
    '首相官邸':            1,
    '共同通信':            1,
    'ロイター':            1,
    'Reuters':             1,
    'AP通信':              1,
    'AP':                  1,
    'BBCニュース':         1,
    'BBC':                 1,
    'Bloomberg':           1,
    'ブルームバーグ':      1,
    'AFP':                 1,
    'AFPBB News':          1,
    '時事通信':            1,
    'JIJI.COM':            1,
    '日本経済新聞':        1,
    '読売新聞':            1,
    '読売新聞オンライン':  1,
    # Tier 2: 主要メディア
    '毎日新聞':   2,
    '朝日新聞':   2,
    'ITmedia':    2,
    'Gizmodo Japan': 2,
    'GIGAZINE':   2,
    'ASCII.jp':   2,
    '東洋経済':   2,
    'ダイヤモンド': 2,
    '産経新聞':   2,
    'PRESIDENT Online': 2,
    '文春オンライン': 2,
    'Business Insider Japan': 2,
    'Forbes Japan': 2,
    # T2026-0428-AU: 沖縄県紙・ファッション系メディア
    '琉球新報':       2,
    '沖縄タイムス':   2,
    'VOGUE Japan':    2,
    'WWD Japan':      2,
    'ELLE Japan':     2,
    # Tier 3: アグリゲーター・その他
    'livedoorニュース': 3,
    'Yahoo!ニュース':   3,
}

# Tier別スコア重み（T2026-0428-AN: tier1 を 1.3 → 1.5 に引き上げ。一次情報優遇）
TIER_WEIGHTS = {1: 1.5, 2: 1.0, 3: 0.8}

# 不確実表現パターン（「信頼性の材料を可視化」するための検出のみ、真偽判定ではない）
UNCERTAINTY_PATTERNS = [
    r'とみられる', r'とされる', r'という', r'関係者によると',
    r'報道によれば', r'〜か', r'疑い', r'匿名', r'情報筋',
    r'複数のメディア', r'一部報道', r'噂', r'未確認',
]

# テック記事の「専門的すぎる」キーワード（これに引っかかったらvelocityスコアを下げる）
TECH_NICHE_KEYWORDS = [
    # セキュリティ専門用語
    '脆弱性', 'CVE-', 'ゼロデイ', 'パッチ適用', 'セキュリティアドバイザリ',
    'CVSS', 'エクスプロイト', 'PoC公開',
    # 開発者向け
    'プルリクエスト', 'コミット', 'リポジトリ', 'フレームワーク',
    'API仕様', 'SDK', 'npm', 'PyPI', 'GitHub Actions',
    # インフラ・サーバー
    'Docker', 'Kubernetes', 'Linux kernel', 'カーネル', 'コンテナ',
    'クラウドネイティブ', 'CI/CD', 'DevOps',
    # ニッチなOS・ハード
    'BIOS', 'ファームウェア', 'ドライバ', 'マザーボード',
]

# テック記事でも一般向けとして優先的に扱うキーワード
# 「一般日本人が日常生活で直接接するテック」に絞る
TECH_GENERAL_KEYWORDS = [
    # デバイス・OS（誰でも知っているもの）
    'iPhone', 'Android', 'スマートフォン', 'スマホ', 'iPad',
    # AI・生成AI（社会的関心が高い）
    'ChatGPT', 'AI', '人工知能', '生成AI', 'Gemini',
    # 主要プラットフォーム・サービス
    'Google', 'Apple', 'Meta', 'Amazon', 'Microsoft',
    'LINE', 'Instagram', 'YouTube', 'X（旧Twitter）', 'TikTok',
    # ECサービス（トラブル・変更が一般ニュースになる）
    'メルカリ', '楽天', 'Amazon',
    # 動画・配信サービス（契約変更・値上げ等）
    'Netflix', 'Amazon Prime', 'Disney+', 'NHKプラス', 'Hulu',
    # スマホアプリ（生活密着）
    'アプリ', 'ゲーム',
    # キャッシュレス・決済
    'キャッシュレス', 'PayPay', '電子マネー', 'QRコード決済',
    # 行政・社会インフラ系デジタル
    'マイナンバー', 'マイナカード', '給付金', '補助金',
    # 詐欺・被害（社会問題として一般向け）
    '詐欺', 'フィッシング', 'なりすまし', 'インターネット詐欺',
    # 個人情報・セキュリティ被害（企業事故→一般被害）
    '個人情報', '情報漏えい', '個人情報流出',
    # ランサムウェア（企業被害が社会問題化している）
    'ランサムウェア',
    # 通信障害（日常生活への影響が直接的）
    '通信障害', 'ドコモ', 'au', 'ソフトバンク',
    # EV・自動運転（生活に近い話題）
    'EV', '自動運転',
]

JACCARD_THRESHOLD = 0.35
MAX_CLUSTER_SIZE  = 15

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
    # 事件・事故系
    '発砲':'銃撃','射撃':'銃撃','乱射':'銃撃',
    '爆発物':'爆発','爆破':'爆発','爆発事故':'爆発',
    'テロ攻撃':'テロ','テロ事件':'テロ',
    'サイバー攻撃':'ハッキング','不正アクセス':'ハッキング',
    '墜落':'航空事故','衝突事故':'衝突',
    # 政治・外交
    '大統領府':'ホワイトハウス','米大統領府':'ホワイトハウス',
    '首脳会談':'サミット','G7サミット':'サミット','G20サミット':'サミット',
    '経済制裁':'制裁','追加制裁':'制裁',
    # 経済
    '値上げ':'物価','インフレ':'物価','物価上昇':'物価',
    '円安進行':'円安','円高進行':'円高',
    # 災害
    '震度':'地震','マグニチュード':'地震',
    '台風接近':'台風','上陸':'台風',
}

# T2026-0428-AU: フロント GENRES と AI _VALID_GENRE_SET (proc_ai.py) と完全一致させる14ジャンル。
# 旧「経済」キーは廃止しビジネスへ統合 (景気/物価/インフレ/GDP/貿易は経済ニュースだが「企業活動」より広いので
# あえて株・金融側にも重複してヒットさせる)。「文化/教育/環境」キーワードはくらしへ集約。
# ファッション系は VOGUE/WWD/ELLE 等メディア固有ワードと、業界用語 (ランウェイ/ファッションウィーク等) を強化。
GENRE_KEYWORDS = {
    '株・金融': ['株','株価','日経平均','円安','円高','為替','金利','日銀','決算','上場','株式','NISA','投資','FRB','ダウ','ナスダック','債券','利上げ','利下げ','景気','物価','インフレ','GDP','貿易','輸出','輸入'],
    '社会':    ['事件','事故','裁判','逮捕','警察','消防','火災','交通事故','人身','台風','地震','災害','被害','支援','救助','遺族','詐欺','不正','汚職','虐待','行方不明','捜索','地域','自治体','沖縄','辺野古','普天間','米軍基地'],
    # T2026-0428-AU: 旧「文化/教育/環境」をくらしに統合。文化・芸術・SDGs もここに寄せる。
    'くらし':  ['生活','暮らし','育児','子育て','学校','教育','保育','介護','福祉','年金','節約','家計','旅行','観光','ペット','趣味','話題','感動','ほっこり',
               '文化','文化財','美術','美術館','博物館','展覧会','アート','工芸','伝統芸能','歌舞伎','能楽','茶道','華道',
               '環境','気候変動','温暖化','SDGs','リサイクル','省エネ','脱炭素','再生可能エネルギー','プラスチックごみ',
               '入試','奨学金','大学受験','保育園','幼稚園','学童','PTA'],
    'グルメ':  ['グルメ','料理','レシピ','レストラン','ラーメン','居酒屋','スイーツ','カフェ','食べ歩き','ランチ','ディナー','食品','食事','弁当','食べログ','ミシュラン','飲食','食材','調理','蕎麦','寿司','焼肉','和食','洋食','中華','イタリアン','フレンチ'],
    'ファッション':['ファッション','ブランド','コーデ','コスメ','スキンケア','メイク','美容','おしゃれ','化粧','ヘア','ネイル','アパレル','コレクション','デザイナー','コーディネート','ビューティー',
                  'ランウェイ','ファッションウィーク','ハイブランド','ストリートファッション','メンズコレクション','ドレス','スーツ','靴','バッグ','アクセサリー','ジュエリー','時計',
                  'VOGUE','WWD','ELLE','GINZA','POPEYE','ヴァンサンカン','装苑'],
    '政治':    ['国会','首相','総理','大臣','選挙','与党','野党','自民','政府','閣議','議員','内閣','知事','官房','外交','条約','法案','政策'],
    'スポーツ':  ['野球','サッカー','テニス','ゴルフ','バスケ','陸上','水泳','五輪','オリンピック','ワールドカップ','Ｊリーグ','プロ野球','NFL','NBA','相撲','ラグビー','大谷','錦織','W杯','Jリーグ','ボクシング','格闘技','UFC','MMA','マラソン','駅伝','競馬','スキー','体操','競泳','卓球','バドミントン','柔道','レスリング','自転車','フィギュア','スケート','トライアスロン','選手権','優勝','準優勝','決勝','開幕','閉幕'],
    '健康':    ['病院','医療','がん','薬','治療','ワクチン','感染','医師','手術','診断','症状','厚生労働','ダイエット','健康法'],
    '科学':    ['宇宙','NASA','JAXA','研究','発見','論文','気候','地震','火山','iPS','ゲノム','原子炉','原発','核融合','物理'],
    'エンタメ':  ['映画','俳優','女優','歌手','アイドル','芸能','ドラマ','アニメ','マンガ','コンサート','紅白','グラミー','アーティスト','ライブ','音楽','タレント','芸人','お笑い','声優','バラエティ','ミュージシャン','バンド','舞台','演劇','漫才','落語','ヒット','興行'],
    'テクノロジー':['AI','人工知能','ChatGPT','iPhone','Android','スマホ','クラウド','サイバー','半導体','アプリ','ソフトウェア','データセンター','量子','セキュリティ','スタートアップ','DX'],
    # T2026-0428-AU: 旧「経済」を吸収。マクロ経済 (物価・インフレ・GDP) は株・金融側に既にあるため重複不可避だがOK。
    'ビジネス':  ['売上','利益','赤字','黒字','買収','合併','リストラ','上半期','通期','業績','IPO','スタートアップ','企業','経済','経営','社長','CEO','商品開発','新商品','値上げ','値下げ','撤退','参入'],
    # T2026-0501-F: 海外ニュース誤分類対策。米中露欧中東のみだったため
    # ASEAN 諸国・南西アジア・中東広域・アフリカ・中南米・欧州主要国・大洋州 を網羅。
    # 「ミャンマー政府、スーチー氏に恩赦」のような海外政府ニュースが「政府」キーワード
    # 1ヒットで『政治』に倒れる構造的バグを直す（情報の地図は「日本国内政治」と「海外」を区別する）。
    '国際':    ['米国','アメリカ','中国','ロシア','ウクライナ','EU','NATO','国連','外相','首脳','制裁',
                'イラン','イスラエル','中東','北朝鮮','台湾','韓国','欧州','大統領','外務省',
                'ミサイル','核','軍事','爆撃','戦争',
                # ASEAN/東南アジア
                'ASEAN','東南アジア','ミャンマー','タイ','ベトナム','インドネシア','フィリピン','マレーシア',
                'シンガポール','カンボジア','ラオス','ブルネイ','東ティモール',
                # 南西アジア
                'インド','パキスタン','アフガニスタン','バングラデシュ','スリランカ','ネパール','モルディブ',
                # 中東広域
                'シリア','パレスチナ','ガザ','トルコ','サウジアラビア','UAE','アラブ首長国連邦','エジプト',
                'ヨルダン','レバノン','イラク','イエメン','クウェート','カタール','バーレーン','オマーン',
                # アフリカ
                'アフリカ','南アフリカ','ナイジェリア','ケニア','エチオピア','スーダン','モロッコ','チュニジア','リビア','アルジェリア',
                # 中南米
                '中南米','南米','ラテンアメリカ','メキシコ','ブラジル','アルゼンチン','チリ','コロンビア','ペルー','ベネズエラ','キューバ',
                # 欧州主要国 (EU/欧州 既出だが個別国も)
                'ドイツ','フランス','イタリア','スペイン','イギリス','英国','オランダ','ベルギー','スイス','スウェーデン','ノルウェー','フィンランド','ポーランド','ハンガリー','チェコ','ギリシャ',
                # 大洋州・北米
                'オーストラリア','豪州','ニュージーランド','カナダ',
                # 体制・政情
                'クーデター','軍事政権','親軍政権','独裁','亡命','難民','国際社会','在外邦人','邦人保護','大使館',
                # 海外要人 (略称含む)
                'スーチー','アウンサンスーチー','ミンアウンフライン','モディ','マクロン','ショルツ','スナク','スターマー',
                'バイデン','プーチン','ゼレンスキー','ネタニヤフ','エルドアン','金正恩','尹錫悦'],
}

# 1件ヒットで自動分類できる強固なキーワード（曖昧性が低いもの）
GENRE_STRONG_KEYWORDS = {
    # T2026-0501-F: クーデター/軍事政権/ASEAN は海外限定の強い国際シグナル。
    # ミャンマー/スーチー等の固有名詞も曖昧性ゼロのため強キーワード化。
    '国際':    ['北朝鮮','ミサイル','核兵器','NATO','ウクライナ','イスラエル','制裁',
                'クーデター','軍事政権','親軍政権','ASEAN','東南アジア',
                'ミャンマー','スーチー','アウンサンスーチー','ゼレンスキー','プーチン','ネタニヤフ'],
    'スポーツ':  ['五輪','オリンピック','W杯','ワールドカップ','ボクシング','格闘技'],
    '政治':    ['衆議院','参議院','内閣改造','解散総選挙'],
}

# ジャンル優先度（スコア同点時に上位が勝つ）
# T2026-0428-AU: フロント GENRES と AI _VALID_GENRE_SET と完全一致 (14ジャンル)
GENRE_PRIORITY = ['国際','政治','スポーツ','健康','テクノロジー','株・金融','ビジネス','社会','科学','エンタメ','グルメ','くらし','ファッション','総合']

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
    r'地震|震度|余震',
    r'台風|暴風雨|強風警報',
    r'災害|洪水|豪雨|水害|土砂',
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
    'feeds.japan.cnet.com': 'CNET Japan',
    'japan.cnet.com': 'CNET Japan',
    'pc.watch.impress.co.jp': 'PC Watch',
    'k-tai.watch.impress.co.jp': 'ケータイWatch',
    'news.livedoor.com': 'livedoorニュース',
    'www.buzzfeed.com':  'BuzzFeed Japan',
    # T2026-0428-AU: 沖縄県紙・ファッション系メディアを追加
    'ryukyushimpo.jp':       '琉球新報',
    'www.ryukyushimpo.jp':   '琉球新報',
    'okinawatimes.co.jp':    '沖縄タイムス',
    'www.okinawatimes.co.jp':'沖縄タイムス',
    'www.vogue.co.jp':       'VOGUE Japan',
    'vogue.co.jp':           'VOGUE Japan',
    'www.wwdjapan.com':      'WWD Japan',
    'wwdjapan.com':          'WWD Japan',
    'www.elle.com':          'ELLE Japan',
    'elle.com':              'ELLE Japan',
}

URGENT_WORDS = {'緊急', '速報', '重大', '急騰', '急落', '大幅', '速報', '号外', '警報', '警告', '危機', '緊迫'}

SEEN_KEY = 'api/seen_articles.json'
SEEN_MAX = 3000

# SNAPアイテムの保持期間（日）。DynamoDB TTLで自動削除される
SNAP_TTL_DAYS = 14  # 7→14: 履歴保持を倍に拡大(2026-04-27 履歴記事数不足対応)

INACTIVE_LIFECYCLE_STATUSES = frozenset({'legacy', 'archived'})
