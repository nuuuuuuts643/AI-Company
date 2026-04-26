import os
import re
import boto3

TABLE_NAME        = os.environ.get('TABLE_NAME', 'p003-topics')
S3_BUCKET         = os.environ.get('S3_BUCKET', '')
REGION            = os.environ.get('REGION', 'ap-northeast-1')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
SLACK_WEBHOOK     = os.environ.get('SLACK_WEBHOOK', '')

dynamodb = boto3.resource('dynamodb', region_name=REGION)
table    = dynamodb.Table(TABLE_NAME)
s3       = boto3.client('s3', region_name=REGION)

MAX_API_CALLS          = 25
MIN_ARTICLES_FOR_TITLE   = 1
MIN_ARTICLES_FOR_SUMMARY = 1
TOPICS_S3_CAP          = 500

STOP_WORDS = {
    'は', 'が', 'を', 'に', 'の', 'と', 'で', 'も', 'や', 'か', 'へ', 'より',
    'から', 'まで', 'という', 'として', 'による', 'において', 'について',
    'した', 'する', 'して', 'された', 'される', 'てい', 'ます', 'です',
    'だっ', 'ある', 'いる', 'なっ', 'れる',
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'of', 'in',
    'to', 'for', 'on', 'at', 'by', 'with', 'as', 'from', 'that', 'this',
    'it', 'its', 'and', 'or', 'but', 'not', 'have', 'has', 'had', 'will',
    'would', 'could', 'should', 'says', 'said', 'new', 'more', 'after',
    'over', 'about', 'up', 'out', 'two', 'into', 'than',
    'he', 'she', 'his', 'her', 'they', 'we', 'you', 'i',
}

SYNONYMS = {
    'アメリカ': '米国', '米': '米国', 'usa': '米国', 'us': '米国',
    '総理': '首相', '内閣総理大臣': '首相',
    '円相場': '為替', 'ドル円': '為替',
    '利上げ': '金利', '利下げ': '金利',
    'オリンピック': '五輪', 'olympic': '五輪',
    'chatgpt': 'ai', 'gpt': 'ai', 'claude': 'ai', 'gemini': 'ai',
}

ENTITY_PATTERNS = [
    r'アメリカ|米国', r'中国|中華人民共和国', r'ロシア|ロシア連邦',
    r'イラン', r'イスラエル', r'韓国|大韓民国', r'北朝鮮',
    r'ウクライナ', r'台湾', r'インド',
    r'石油|原油|エネルギー', r'株価|日経|TOPIX',
    r'円安|円高|為替', r'AI|人工知能', r'半導体',
    r'金利|利上げ|利下げ', r'GDP|景気|インフレ',
    r'選挙|大統領|首相|首脳', r'軍事|戦争|攻撃|爆撃|ミサイル',
    r'地震|台風|災害', r'大谷|翔平', r'トランプ', r'プーチン', r'習近平',
]


def normalize(text):
    text = re.sub(r'[【】「」『』（）()\[\]！？!?\s　・]+', ' ', text.lower())
    words = set()
    for w in text.split():
        if len(w) > 1:
            words.add(SYNONYMS.get(w, w))
    return words


def extract_entities(text):
    entities = set()
    for pattern in ENTITY_PATTERNS:
        if re.search(pattern, text):
            entities.add(pattern.split('|')[0])
    return entities
