"""Claude Haiku を使ったタイトル・ストーリー生成とフォールバック (抽出的生成)。"""
import json
import re
import urllib.request
from collections import Counter
from datetime import datetime

from proc_config import ANTHROPIC_API_KEY, STOP_WORDS, SYNONYMS, normalize, extract_entities


def clean_headline(title):
    """記事タイトルからメディア名サフィックスを除去 例: '記事 - 毎日新聞' → '記事'"""
    return re.sub(r'\s*[-－–|｜]\s*[^\s].{1,20}$', '', title).strip()


def generate_title(articles):
    """Claude Haiku でトピックタイトルを生成。"""
    if not ANTHROPIC_API_KEY:
        return None
    headlines = '\n'.join(clean_headline(a.get('title', '')) for a in articles[:8])
    prompt = (
        '以下はニュース記事の見出しです。\n'
        'これらが共通して報じているトピックを表す、概念的で簡潔な日本語タイトルを作ってください。\n\n'
        '【出力ルール】\n'
        '- 15〜25文字程度の短いタイトル\n'
        '- 「〇〇事件」「△△問題」「△△の動向」「◇◇をめぐる動き」などの形式が望ましい\n'
        '- 記事タイトルをそのままコピーしないこと\n'
        '- メディア名（例: 毎日新聞、NHK等）は絶対に含めないこと\n'
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
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read())
        return data['content'][0]['text'].strip()
    except Exception as e:
        print(f'generate_title error: {e}')
        return None


def _format_pub_date(raw_date: str) -> str:
    """pubDate文字列を 'M/D' 形式に変換。パース失敗時は空文字を返す。"""
    if not raw_date:
        return ''
    for fmt in ('%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%d', '%a, %d %b %Y %H:%M:%S %z', '%a, %d %b %Y %H:%M:%S GMT'):
        try:
            dt = datetime.strptime(raw_date[:len(fmt)], fmt)
            return f'{dt.month}/{dt.day}'
        except ValueError:
            continue
    return ''


def generate_story(articles):
    """Claude Sonnet で4セクション形式のストーリー分析を生成。

    Returns:
        dict: {
          "aiSummary": str,      # ① 何が起きたか
          "spreadReason": str,   # ② なぜ広がったか
          "forecast": str,       # ④ 今後どうなるか（仮説）
          "timeline": list,      # 時系列ステップ
          "phase": str           # ③ 現在のフェーズ
        }
        または None（API未設定・エラー時）
    """
    if not ANTHROPIC_API_KEY:
        return None

    article_count = len(articles)
    article_lines = []
    for a in articles[:15]:
        title = clean_headline(a.get('title', ''))
        date_str = _format_pub_date(a.get('pubDate', '') or a.get('publishedAt', '') or '')
        article_lines.append(f'{date_str} {title}'.strip() if date_str else title)
    headlines = '\n'.join(article_lines)

    prompt = (
        '以下は同じニューストピックに関する記事の一覧です（日付付きの場合あり）。\n'
        'このトピックを4つの視点で分析し、JSONのみを出力してください。\n\n'
        '【言葉選びのルール】\n'
        '- 事実は「〜した」「〜と述べた」「〜と報じられている」で記述\n'
        '- 断定禁止: 「明らかに」「間違いなく」「〜が原因で」→「〜の後、」「〜を機に」\n'
        '- 感情語禁止: 「炎上」「衝撃」→「批判的な反応があった」「注目が集まった」\n'
        '- 主語を具体的に: 「世論が」→「○○党が」「○○社が」\n'
        '- 個人の発言・行動: 「〜と述べた」等の引用形式\n'
        '- 事件容疑者: 「〜の疑いで逮捕」「容疑を否認」等、司法手続きの状態を正確に\n\n'
        '【出力フォーマット（JSON以外出力禁止）】\n'
        '{\n'
        '  "aiSummary": "①何が起きたか。誰が・何をして・何が起き・なぜ注目されたかを事実ベースで1段落",\n'
        '  "spreadReason": "②なぜ広がったか。記事数・メディア種別・社会的背景・議論の焦点を2〜3文で分析",\n'
        '  "forecast": "③今後どうなるか。記事内容を根拠にした仮説を2文。断定せず「〜が見込まれる」「〜の可能性がある」で締める",\n'
        '  "timeline": [\n'
        '    {"date": "M/D形式または空文字", "event": "何が起きたか（20文字以内の体言止め）"},\n'
        '    ...\n'
        '  ],\n'
        '  "phase": "発端 または 拡散 または ピーク または 現在地"\n'
        '}\n\n'
        '【各フィールドのルール】\n'
        'aiSummary: 改行・箇条書き・見出し禁止。1段落。メディア名不要。\n'
        'spreadReason: なぜ今・なぜこのトピックが広がったかの構造分析。推測の場合は「〜と見られる」で。\n'
        'forecast: 「今後〜が予想される」「〜の可能性がある」で終える。根拠のない予測禁止。\n'
        'timeline: 3〜6件。重要な転換点のみ。\n'
        'phase: 発端（始まったばかり）/ 拡散（広がっている）/ ピーク（最も活発）/ 現在地（落ち着いてきた）\n\n'
        f'記事一覧({article_count}件):\n{headlines}'
    )

    try:
        body = json.dumps({
            'model': 'claude-haiku-4-5-20251001',
            'max_tokens': 1400,
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
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read())
        text = data['content'][0]['text'].strip()

        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if json_match:
            text = json_match.group(1)
        else:
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                text = json_match.group(0)

        result = json.loads(text)

        if not isinstance(result.get('aiSummary'), str) or not result['aiSummary'].strip():
            return None
        if not isinstance(result.get('timeline'), list):
            result['timeline'] = []
        result['timeline'] = [
            {'date': str(e.get('date', '')), 'event': str(e.get('event', ''))[:30]}
            for e in result['timeline']
            if isinstance(e, dict) and e.get('event')
        ][:6]
        valid_phases = ('発端', '拡散', 'ピーク', '現在地')
        if result.get('phase') not in valid_phases:
            result['phase'] = '現在地'
        # spreadReason / forecast は文字列に正規化（なければ空文字）
        result['spreadReason'] = str(result.get('spreadReason') or '').strip()
        result['forecast']     = str(result.get('forecast')     or '').strip()

        return result

    except Exception as e:
        print(f'generate_story error: {e}')
        return None


def extractive_title(articles):
    """AIを使わないフォールバックタイトル生成。"""
    word_counter = Counter()
    for a in articles:
        words = normalize(a.get('title', '')) - STOP_WORDS
        word_counter.update(w for w in words if len(w) >= 2)
    top_words = [w for w, _ in word_counter.most_common(5) if word_counter[w] >= 2]
    all_text  = ' '.join(a.get('title', '') for a in articles)
    entities  = list(extract_entities(all_text))
    if entities and top_words:
        return f'{entities[0]}と{top_words[0]}をめぐる動き'
    elif entities:
        return f'{entities[0]}に関する動向'
    elif top_words:
        return f'{top_words[0]}をめぐる動き'
    else:
        first = articles[0].get('title', '') if articles else ''
        return first[:25] + ('…' if len(first) > 25 else '')
