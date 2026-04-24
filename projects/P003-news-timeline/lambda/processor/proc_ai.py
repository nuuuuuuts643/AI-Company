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
    """Claude Haiku でトピックのストーリー（要約・タイムライン・フェーズ）を生成。

    Returns:
        dict: {"aiSummary": str, "timeline": list[{"date": str, "event": str}], "phase": str}
        または None（API未設定・エラー時）
    """
    if not ANTHROPIC_API_KEY:
        return None

    article_count = len(articles)
    # 日付付き見出しリストを生成（最大15件）
    article_lines = []
    for a in articles[:15]:
        title = clean_headline(a.get('title', ''))
        date_str = _format_pub_date(a.get('pubDate', '') or a.get('publishedAt', '') or '')
        article_lines.append(f'{date_str} {title}'.strip() if date_str else title)
    headlines = '\n'.join(article_lines)

    length_guide = '4〜6文（長期・複雑なトピックは情報量を優先）' if article_count >= 10 else '3〜4文'

    prompt = (
        '以下は同じニューストピックに関する記事の一覧です（日付付きの場合あり）。\n'
        'このトピックを「ストーリー」として分析し、JSONのみを出力してください。\n\n'
        '【言葉選びの厳格なルール】\n'
        '▼ 絶対に使わない表現:\n'
        '- 評価・判断を含む語: 「問題だ」「悪い」「正しい」「当然」「残念」「残酷」\n'
        '- 感情的な語: 「炎上」「批判が殺到」「大混乱」「衝撃」\n'
        '  → 代わりに「批判的な反応があった」「混乱が生じた」を使う\n'
        '- 因果の断定: 「〜が原因で」\n'
        '  → 代わりに「〜の後、」「〜を機に」を使う\n'
        '- 根拠のない断定: 「明らかに」「間違いなく」「確実に」\n'
        '- 主語が曖昧な表現: 「世論が」「国民が」「多くの人が」\n'
        '  → 具体的な主体（○○省が、○○党が）を使う\n\n'
        '▼ 推奨する言葉選び:\n'
        '- 事実ベースの動詞: 「発表した」「述べた」「提出した」「否定した」「要請した」\n'
        '- 不確かな情報: 「〜と報じられている」「〜とされている」「〜の見方がある」\n'
        '- 数字は記事に書いてある通りに（盛らない、縮小しない）\n'
        '- 時系列は「〜した後、」「〜の翌日、」など時間軸で繋ぐ\n'
        '- 文末は「〜した。」「〜となっている。」（断定的すぎず、でも自然な文章）\n\n'
        '▼ デリケートな領域での追加ルール:\n'
        '- 特定個人（政治家・芸能人・スポーツ選手）: 発言・行動は「〜と述べた」等の引用形式\n'
        '- 事件・事故: 被疑者・容疑者の段階では「〜の疑いで逮捕」「容疑を否認している」等、司法手続きの状態を正確に記述\n'
        '- 企業の不祥事: 確定情報のみ使用。不確かな情報は「報道によれば」で留める\n\n'
        '【出力フォーマット（JSON以外の説明文は不要）】\n'
        '{\n'
        '  "aiSummary": "発端から現在地まで、出来事の流れを自然な文章で説明",\n'
        '  "timeline": [\n'
        '    {"date": "M/D形式または空文字", "event": "何が起きたか（20文字以内）"},\n'
        '    ...\n'
        '  ],\n'
        '  "phase": "発端 または 拡散 または ピーク または 現在地"\n'
        '}\n\n'
        '【aiSummaryのルール】\n'
        f'- 長さ目安: {length_guide}\n'
        '- 誰が・何をして・何が起き・なぜ注目されたかを説明\n'
        '- 箇条書き（-・*）・番号・見出し（#）・改行禁止。1段落として続けて書く\n'
        '- メディア名は含めない。難しい言葉は避ける\n\n'
        '【timelineのルール】\n'
        '- 3〜6ステップ（重要な転換点のみ抜粋）\n'
        '- dateは記事の日付から推定（不明なら空文字""）\n'
        '- eventは体言止め推奨（例: "○○が声明発表"）\n\n'
        '【phaseのルール（このトピックが現在どのフェーズか1つ選択）】\n'
        '- 発端: まだ始まったばかり、情報が少ない\n'
        '- 拡散: メディア・SNSで広がっている段階\n'
        '- ピーク: 最も注目・議論が活発な状態\n'
        '- 現在地: 落ち着いてきた、またはその後の状況\n\n'
        f'記事一覧({article_count}件):\n{headlines}'
    )

    try:
        body = json.dumps({
            'model': 'claude-haiku-4-5-20251001',
            'max_tokens': 900,
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
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
        text = data['content'][0]['text'].strip()

        # ```json ... ``` ブロックまたは裸の {...} を抽出
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if json_match:
            text = json_match.group(1)
        else:
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                text = json_match.group(0)

        result = json.loads(text)

        # バリデーション・正規化
        if not isinstance(result.get('aiSummary'), str) or not result['aiSummary'].strip():
            return None
        if not isinstance(result.get('timeline'), list):
            result['timeline'] = []
        # timeline要素のサニタイズ
        result['timeline'] = [
            {'date': str(e.get('date', '')), 'event': str(e.get('event', ''))[:30]}
            for e in result['timeline']
            if isinstance(e, dict) and e.get('event')
        ][:6]
        valid_phases = ('発端', '拡散', 'ピーク', '現在地')
        if result.get('phase') not in valid_phases:
            result['phase'] = '現在地'

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
