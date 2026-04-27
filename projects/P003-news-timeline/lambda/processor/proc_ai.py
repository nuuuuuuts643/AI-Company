"""Claude Haiku を使ったタイトル・ストーリー生成とフォールバック (抽出的生成)。"""
import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime

from proc_config import ANTHROPIC_API_KEY

_CLAUDE_API_URL = 'https://api.anthropic.com/v1/messages'

VALID_GENRES = frozenset([
    '政治', '国際', '社会', '経済', 'ビジネス', '株・金融',
    'テクノロジー', '科学', '健康', 'スポーツ', 'エンタメ',
    'くらし', 'グルメ', 'ファッション', '総合',
])

_GENRES_PROMPT = (
    '利用可能なジャンル（このリスト外は使用禁止）: '
    '政治 / 国際 / 社会 / 経済 / ビジネス / 株・金融 / '
    'テクノロジー / 科学 / 健康 / スポーツ / エンタメ / '
    'くらし / グルメ / ファッション / 総合\n'
)


def _validate_genres(raw) -> list:
    """AI出力のgenresフィールドを検証・正規化する。"""
    if not isinstance(raw, list):
        return ['総合']
    result = [g for g in raw if isinstance(g, str) and g in VALID_GENRES]
    return result[:2] if result else ['総合']


def _call_claude(payload: dict, timeout: int = 25) -> dict:
    """Claude API を呼び出す。429 は最大3回リトライ（指数バックオフ）。"""
    body = json.dumps(payload).encode('utf-8')
    headers = {
        'x-api-key': ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json',
    }
    delay = 5
    for attempt in range(4):
        try:
            req = urllib.request.Request(_CLAUDE_API_URL, data=body, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 3:
                retry_after = e.headers.get('retry-after')
                wait = int(retry_after) if retry_after else delay
                print(f'[Claude] 429 rate limit, {wait}s 待機 (attempt {attempt+1})')
                time.sleep(wait)
                delay *= 2
            else:
                raise
    raise RuntimeError('Claude API 429 retries exhausted')


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
        'これらが共通して報じているトピックを表す、Googleで検索されやすい日本語タイトルを作ってください。\n\n'
        '【出力ルール】\n'
        '- 18〜30文字程度のタイトル\n'
        '- 検索意図に合わせた以下の形式を優先して選ぶ:\n'
        '  「〇〇とは何か・わかりやすく解説」「△△事件の経緯と背景まとめ」\n'
        '  「〇〇問題の原因と今後の影響」「◇◇をめぐる最新の動きまとめ」\n'
        '  「〇〇とは」「△△の真相と全容」「◇◇事件 なぜ・どうなる」\n'
        '  「〇〇問題」「△△の動向と争点」（短く核心を突く形も可）\n'
        '- 「〇〇が△△した」「〇〇、△△を××」のような報道見出し形式は避ける\n'
        '- 記事タイトルをそのままコピーしないこと\n'
        '- メディア名（例: 毎日新聞、NHK等）は絶対に含めないこと\n'
        '- 固有名詞・核心キーワードを必ず含める\n'
        '- 「速報」「続報」は使わない\n'
        '- 説明文・句読点・かぎかっこ不要。タイトルのみ1行で出力\n\n'
        f'見出し:\n{headlines}'
    )
    _REFUSAL = ('申し訳', 'できません', 'ありません', 'ください', '提供いただいた', '異なる',
                'この提供', 'というタイトル', 'という記事', 'ですね。', '**', '\n')
    try:
        data = _call_claude({
            'model': 'claude-haiku-4-5-20251001',
            'max_tokens': 100,
            'messages': [{'role': 'user', 'content': prompt}],
        }, timeout=12)
        title = data['content'][0]['text'].strip()
        unmatched_bracket = title.count('「') != title.count('」') or title.count('【') != title.count('】')
        if len(title) > 50 or unmatched_bracket or any(w in title for w in _REFUSAL):
            print(f'generate_title: 無効な応答を除外: {title[:40]}')
            return None
        return title if title else None
    except Exception as e:
        print(f'generate_title error: {e}')
        return None


def _format_pub_date(raw_date) -> str:
    """pubDate（文字列またはUnix秒整数）を 'M/D' 形式に変換。パース失敗時は空文字を返す。"""
    if not raw_date:
        return ''
    # Unix timestamp（整数または数値文字列）
    try:
        ts = int(raw_date)
        if ts > 1_000_000_000:
            dt = datetime.utcfromtimestamp(ts if ts < 1e11 else ts / 1000)
            return f'{dt.month}/{dt.day}'
    except (TypeError, ValueError):
        pass
    s = str(raw_date)
    for fmt in ('%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%d', '%a, %d %b %Y %H:%M:%S %z', '%a, %d %b %Y %H:%M:%S GMT'):
        try:
            dt = datetime.strptime(s, fmt)
            return f'{dt.month}/{dt.day}'
        except ValueError:
            continue
    return ''


_WORD_RULES = (
    '【言葉選びのルール】\n'
    '- 事実は「〜した」「〜と述べた」「〜と報じられている」で記述\n'
    '- 断定禁止: 「明らかに」「間違いなく」「〜が原因で」→「〜の後、」「〜を機に」\n'
    '- 感情語禁止: 「炎上」「衝撃」→「批判的な反応があった」「注目が集まった」\n'
    '- 主語を具体的に: 「世論が」→「○○党が」「○○社が」\n'
    '- 個人の発言・行動: 「〜と述べた」等の引用形式\n'
    '- 事件容疑者: 「〜の疑いで逮捕」「容疑を否認」等、司法手続きの状態を正確に\n'
    '- 固有名詞・企業名・サービス名は初出時に括弧で1語説明を加える（例: スターリンク（SpaceXの衛星インターネット）が〜）\n\n'
)


def _build_headlines(articles: list, limit: int = 15) -> tuple[str, int]:
    """記事リストからプロンプト用の見出し文字列と件数を返す。"""
    lines = []
    for a in articles[:limit]:
        title    = clean_headline(a.get('title', ''))
        desc     = (a.get('description') or '').strip()
        date_str = _format_pub_date(a.get('pubDate', '') or a.get('publishedAt', '') or '')
        line = f'{date_str} {title}'.strip() if date_str else title
        if desc:
            line += f'\n  概要: {desc[:150]}'
        lines.append(line)
    return '\n'.join(lines), len(articles)


def _parse_story_json(text: str) -> dict | None:
    """APIレスポンステキストからJSONを抽出・パースする。"""
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if json_match:
        text = json_match.group(1)
    else:
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            text = json_match.group(0)
    return json.loads(text)


def _sanitize_timeline(raw_timeline, max_items: int = 6) -> list:
    """timelineリストを検証・正規化する。transitionは最後以外のアイテムにのみ付与。"""
    if not isinstance(raw_timeline, list):
        return []
    sanitized = []
    items = [e for e in raw_timeline if isinstance(e, dict) and e.get('event')][:max_items]
    for i, e in enumerate(items):
        item = {
            'date':  str(e.get('date', '')),
            'event': str(e.get('event', ''))[:40],
        }
        raw_tr = str(e.get('transition') or '').strip()
        if raw_tr and i < len(items) - 1:
            item['transition'] = raw_tr[:25]
        sanitized.append(item)
    return sanitized


def generate_story(articles, article_count: int | None = None):
    """記事数に応じた段階的ストーリー分析を生成。

    - 1〜2件 / storyTimeline ≤ 2ステップ相当: シンプルな1段落要約のみ
    - 3〜5件: 概要 + なぜ広がったか + 短いタイムライン（2〜3件）
    - 6件以上: フル4セクション + 因果タイムライン（最大6件）

    Returns:
        dict: {"aiSummary", "spreadReason", "forecast", "timeline", "phase", "summaryMode"}
              summaryMode: "minimal" | "standard" | "full"
        または None（API未設定・エラー時）
    """
    if not ANTHROPIC_API_KEY:
        return None

    cnt = article_count if article_count is not None else len(articles)

    if cnt <= 2:
        return _generate_story_minimal(articles)
    elif cnt <= 5:
        return _generate_story_standard(articles, cnt)
    else:
        return _generate_story_full(articles, cnt)


def _generate_story_minimal(articles: list) -> dict | None:
    """1〜2件: シンプルな1段落要約のみ生成（APIコスト最小）。"""
    headlines, cnt = _build_headlines(articles, limit=2)
    prompt = (
        '以下はニューストピックに関する記事です。\n'
        '事実のみで1段落（100〜150文字）にまとめてください。断定・感情語・メディア名禁止。\n'
        '固有名詞・企業名・サービス名は初出時に括弧で1語説明を加える（例: スターリンク（SpaceXの衛星インターネット）が〜）。\n\n'
        + _GENRES_PROMPT
        + '【出力フォーマット（JSON以外出力禁止）】\n'
        '{"aiSummary": "何が起きたか。誰が・何をして・何が起き・なぜ注目されたかを事実ベースで1段落",\n'
        ' "genres": ["最も適切なジャンル1つ、または2つ（上のリストから選ぶ）"]}\n\n'
        f'記事情報（{cnt}件）:\n{headlines}'
    )
    try:
        data = _call_claude({
            'model': 'claude-haiku-4-5-20251001',
            'max_tokens': 250,
            'messages': [{'role': 'user', 'content': prompt}],
        })
        result = _parse_story_json(data['content'][0]['text'].strip())
        if not isinstance(result.get('aiSummary'), str) or not result['aiSummary'].strip():
            return None
        return {
            'aiSummary':   result['aiSummary'].strip(),
            'spreadReason': '',
            'forecast':     '',
            'timeline':     [],
            'phase':        '発端',
            'summaryMode':  'minimal',
            'genres':       _validate_genres(result.get('genres')),
        }
    except Exception as e:
        print(f'generate_story (minimal) error: {e}')
        return None


def _generate_story_standard(articles: list, cnt: int) -> dict | None:
    """3〜5件: 概要 + なぜ広がったか + 短いタイムライン（2〜3件）。"""
    headlines, _ = _build_headlines(articles, limit=5)
    prompt = (
        '以下は同じニューストピックに関する記事の一覧です。\n'
        'このトピックを2つの視点で分析し、JSONのみを出力してください。\n\n'
        '【ルール】事実は「〜した/〜と述べた」で記述。断定・感情語・メディア名禁止。主語を具体的に。\n'
        '固有名詞・企業名・サービス名は初出時に括弧で1語説明を加える（例: スターリンク（SpaceXの衛星インターネット）が〜）。\n\n'
        + _GENRES_PROMPT
        + '【出力フォーマット（JSON以外出力禁止）】\n'
        '{\n'
        '  "aiSummary": "何が起きたか。誰が・何をして・何が起き・なぜ注目されたかを事実ベースで1段落",\n'
        '  "backgroundContext": "なぜ起きたか。この問題の背景にある構造的・社会的・経済的・政治的要因を1文で分析。推測は「〜と見られる」で",\n'
        '  "spreadReason": "なぜ広がったか。①トリガーイベント（引き金となった出来事）②なぜ今か（時事・政治・経済文脈）③誰が注目しているか（注目層・立場）④他ニュースとの関連のうち該当する観点を2文で分析",\n'
        '  "timeline": [\n'
        '    {"date": "M/D形式または空文字", "event": "何が起きたか（40文字以内の体言止め）", "transition": "次への因果・接続（25文字以内）"},\n'
        '    ...\n'
        '    {"date": "M/D形式または空文字", "event": "最後のイベント（transitionは省略）"}\n'
        '  ],\n'
        '  "phase": "発端 または 拡散 または ピーク または 現在地 または 収束",\n'
        '  "genres": ["最も適切なジャンル1つ、または2つ（上のリストから選ぶ）"]\n'
        '}\n\n'
        '【ルール】\n'
        'aiSummary: 改行・箇条書き禁止。1段落。メディア名不要。\n'
        'backgroundContext: 1文。表面の出来事ではなく背景にある構造的要因を書く。「〜という構造的背景がある」「〜が長年の課題となっていた」等。\n'
        'spreadReason: 2文で分析。①〜④の観点から該当するものを選ぶ。推測は「〜と見られる」で。\n'
        'timeline: 2〜3件のみ。重要な転換点のみ。\n'
        'timeline[].event: 体言止め。具体的な出来事を40文字以内で。\n'
        'timeline[].transition: 因果・接続詞（例: これを受けて、その結果、翌日、）。事実のみ。最後のアイテムは省略。\n'
        'phase: 発端 / 拡散 / ピーク / 現在地 / 収束\n\n'
        f'記事情報（{cnt}件）:\n{headlines}'
    )
    try:
        data = _call_claude({
            'model': 'claude-haiku-4-5-20251001',
            'max_tokens': 950,
            'messages': [{'role': 'user', 'content': prompt}],
        })
        result = _parse_story_json(data['content'][0]['text'].strip())
        if not isinstance(result.get('aiSummary'), str) or not result['aiSummary'].strip():
            return None
        valid_phases = ('発端', '拡散', 'ピーク', '現在地', '収束')
        return {
            'aiSummary':         result['aiSummary'].strip(),
            'backgroundContext': str(result.get('backgroundContext') or '').strip(),
            'spreadReason':      str(result.get('spreadReason') or '').strip(),
            'forecast':          '',
            'timeline':          _sanitize_timeline(result.get('timeline'), max_items=3),
            'phase':             result.get('phase') if result.get('phase') in valid_phases else '現在地',
            'summaryMode':       'standard',
            'genres':            _validate_genres(result.get('genres')),
        }
    except Exception as e:
        print(f'generate_story (standard) error: {e}')
        return None


def _generate_story_full(articles: list, cnt: int) -> dict | None:
    """6件以上: フル4セクション + 因果タイムライン（最大6件）。"""
    headlines, _ = _build_headlines(articles, limit=10)
    prompt = (
        '以下は同じニューストピックに関する記事の一覧です（日付付きの場合あり）。\n'
        'このトピックを4つの視点で分析し、JSONのみを出力してください。\n\n'
        + _WORD_RULES
        + _GENRES_PROMPT
        + '【出力フォーマット（JSON以外出力禁止）】\n'
        '{\n'
        '  "aiSummary": "①何が起きたか。誰が・何をして・何が起き・なぜ注目されたかを事実ベースで1段落",\n'
        '  "backgroundContext": "②なぜ起きたか。この問題の背景にある構造的・社会的・経済的・政治的要因を2文で分析。表面の出来事ではなく根本にある構造や文脈を掘り下げる。推測は「〜と見られる」で",\n'
        '  "spreadReason": "③なぜ広がったか。①トリガーイベント（引き金となった出来事）②なぜ今か（時事・政治・経済文脈）③誰が注目しているか（注目層・立場）④他ニュースとの関連のうち該当する観点を3文で深く分析",\n'
        '  "forecast": "④今後どうなるか。記事内容を根拠にした仮説を2文。断定せず「〜が見込まれる」「〜の可能性がある」で締める",\n'
        '  "timeline": [\n'
        '    {"date": "M/D形式または空文字", "event": "何が起きたか（40文字以内の体言止め）", "transition": "次のステップへの因果・接続（25文字以内。例: これを受けて、/その結果、/翌日、）"},\n'
        '    ...\n'
        '    {"date": "M/D形式または空文字", "event": "最後のイベント（transitionは省略）"}\n'
        '  ],\n'
        '  "phase": "発端 または 拡散 または ピーク または 現在地 または 収束",\n'
        '  "genres": ["最も適切なジャンル1つ、または2つ（上のリストから選ぶ）"]\n'
        '}\n\n'
        '【各フィールドのルール】\n'
        'aiSummary: 改行・箇条書き・見出し禁止。1段落。メディア名不要。\n'
        'backgroundContext: 2文。表面の出来事ではなく背景の構造的要因を書く。「〜という構造的背景がある」「〜が長年の課題となっていた」「〜という政策的文脈がある」等。\n'
        'spreadReason: 3文で深く分析。①〜④の観点から該当するものを組み合わせる。推測の場合は「〜と見られる」で。\n'
        'forecast: 「今後〜が予想される」「〜の可能性がある」で終える。根拠のない予測禁止。\n'
        'timeline: 3〜6件。重要な転換点のみ。\n'
        'timeline[].event: 体言止め。具体的な出来事を40文字以内で。固有名詞を使って具体的に書く。\n'
        'timeline[].transition: 「前のイベント → 次のイベント」を繋ぐ因果・接続詞。25文字以内。事実のみ。感情語禁止。最後のアイテムは省略。\n'
        '  例: 「これを受けて、」「その翌日、」「反発を受け、」「声明を機に、」「審議を経て、」\n'
        'phase: 発端（始まったばかり）/ 拡散（広がっている）/ ピーク（最も活発）/ 現在地（落ち着いてきた）/ 収束（話題が終息した）\n\n'
        f'記事情報（{cnt}件・見出しと概要）:\n{headlines}'
    )
    try:
        data = _call_claude({
            'model': 'claude-haiku-4-5-20251001',
            'max_tokens': 1300,
            'messages': [{'role': 'user', 'content': prompt}],
        })
        result = _parse_story_json(data['content'][0]['text'].strip())
        if not isinstance(result.get('aiSummary'), str) or not result['aiSummary'].strip():
            return None
        valid_phases = ('発端', '拡散', 'ピーク', '現在地', '収束')
        return {
            'aiSummary':         result['aiSummary'].strip(),
            'backgroundContext': str(result.get('backgroundContext') or '').strip(),
            'spreadReason':      str(result.get('spreadReason') or '').strip(),
            'forecast':          str(result.get('forecast')     or '').strip(),
            'timeline':          _sanitize_timeline(result.get('timeline'), max_items=6),
            'phase':             result.get('phase') if result.get('phase') in valid_phases else '現在地',
            'summaryMode':       'full',
            'genres':            _validate_genres(result.get('genres')),
        }
    except Exception as e:
        print(f'generate_story (full) error: {e}')
        return None
