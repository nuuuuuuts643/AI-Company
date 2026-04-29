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

# measured: T2026-0429-P (2026-04-29 PM) 30→20 に再削減。
# 同 PR で processor schedule を 4回/日 → 2回/日 (5:30/17:30 JST) に変更。
# 2回/日 × 20 = 40 calls/day = ~$0.092/day = ~$2.8/month（Haiku 4.5 基準・full mode 含む）。
# 旧 4 × 30 = 120 calls/day から約 67% 削減。fetcher 即時トリガーは速報例外時のみ
# (maxApiCalls=2) のため通常は加算なし。実測コストが目標 $0.50/日 を超えたら再調整。
MAX_API_CALLS          = 20
DAILY_API_BUDGET       = 40  # MAX_API_CALLS(20) × 2 回/日 = 40 が 1 日あたりの API 呼び出し上限（速報例外除く）
MIN_ARTICLES_FOR_TITLE   = 2
MIN_ARTICLES_FOR_SUMMARY = 2
TOPICS_S3_CAP          = 500

# T2026-0428-AO: 自己修復基盤。processor の出力スキーマバージョン。
# このバージョンを上げる = 全トピックを次サイクルで再処理する宣言。
# 増やすタイミング: 新フィールド追加 / 既存フィールド意味変更 / プロンプト大改修。
# - v1: keyPoint 追加
# - v2: statusLabel / watchPoints / perspectives 追加
# - v3: predictionMadeAt / predictionResult / topicTitle / latestUpdateHeadline 追加 (現行)
PROCESSOR_SCHEMA_VERSION = 3

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

def normalize(text):
    text = re.sub(r'[【】「」『』（）()\[\]！？!?\s　・]+', ' ', text.lower())
    words = set()
    for w in text.split():
        if len(w) > 1:
            words.add(SYNONYMS.get(w, w))
    return words


