import json
import os
import re
import boto3

TABLE_NAME        = os.environ.get('TABLE_NAME', 'p003-topics')
S3_BUCKET         = os.environ.get('S3_BUCKET', '')
REGION            = os.environ.get('REGION', 'ap-northeast-1')


def _load_secret_or_env(secret_id_env: str, fallback_env: str) -> str:
    """T2026-0502-SEC9 (2026-05-02): AWS Secrets Manager 優先 + env fallback。

    優先順位:
        1. SECRET ID が <secret_id_env> で指定されていれば Secrets Manager から取得
        2. 取得失敗 or SECRET ID 未指定なら <fallback_env> 環境変数を読む
        3. それも無ければ '' を返す (caller 側で空判定)

    Lambda env から live key を消す移行期間中は、両方が共存する形でデプロイ可能。
    SECRET ID 未指定環境では従来通り env からのみ読む = 後方互換。

    SecretString は plain text もしくは JSON {"<fallback_env>": "value"} を許容する。
    """
    secret_id = os.environ.get(secret_id_env, '').strip()
    if secret_id:
        try:
            sm = boto3.client('secretsmanager', region_name=REGION)
            resp = sm.get_secret_value(SecretId=secret_id)
            raw = resp.get('SecretString') or ''
            if raw.startswith('{'):
                try:
                    j = json.loads(raw)
                    return str(j.get(fallback_env) or j.get('value') or raw)
                except json.JSONDecodeError:
                    return raw
            return raw.strip()
        except Exception as e:
            # Secrets Manager 取得失敗時は env fallback (落ちないことを優先)
            print(f'[SEC9] Secrets Manager fetch failed ({secret_id}): {type(e).__name__}: {e}. Using env fallback.')
    return os.environ.get(fallback_env, '')


# T2026-0502-SEC9: ANTHROPIC_API_KEY と SLACK_WEBHOOK を Secrets Manager から取得 (env fallback 付き)
# 移行手順:
#   1. AWS Secrets Manager に flotopic/anthropic-api-key と flotopic/slack-webhook を作成 (PO 操作)
#   2. Lambda 環境変数に ANTHROPIC_SECRET_ID=flotopic/anthropic-api-key を追加
#   3. 動作確認後 Lambda env から ANTHROPIC_API_KEY / SLACK_WEBHOOK を削除
# 詳細: docs/runbooks/secrets-manager-migration.md
ANTHROPIC_API_KEY = _load_secret_or_env('ANTHROPIC_SECRET_ID', 'ANTHROPIC_API_KEY')
SLACK_WEBHOOK     = _load_secret_or_env('SLACK_WEBHOOK_SECRET_ID', 'SLACK_WEBHOOK')

dynamodb = boto3.resource('dynamodb', region_name=REGION)
table    = dynamodb.Table(TABLE_NAME)
s3       = boto3.client('s3', region_name=REGION)

# 200→30 に削減（2026-04-29 コスト削減）。
# 4回/日 × 30 = 120 calls/day = ~$0.28/day = ~$8.4/month（Haiku 4.5 基準）。
# 現状の 200 × 4 = 800 calls/day から約 85% 削減。
# 上げる必要が出たら DAILY_API_BUDGET と一緒に再調整する。
MAX_API_CALLS          = 30
DAILY_API_BUDGET       = 120  # MAX_API_CALLS(30) × 4 回/日 = 120 が 1 日あたりの API 呼び出し上限
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


