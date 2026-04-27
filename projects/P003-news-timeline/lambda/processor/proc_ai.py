"""Claude Haiku を使ったタイトル・ストーリー生成とフォールバック (抽出的生成)。"""
import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime

from proc_config import ANTHROPIC_API_KEY

_CLAUDE_API_URL = 'https://api.anthropic.com/v1/messages'


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


def _call_claude_tool(prompt: str, tool_name: str, input_schema: dict,
                       max_tokens: int = 1500, timeout: int = 25,
                       model: str = 'claude-haiku-4-5-20251001') -> dict | None:
    """Claude Tool Use API で structured output を取得。
    JSON Schema で出力形式を強制するため malformed JSON は物理的に発生しない。
    Returns: tool_use.input (dict) / 失敗時 None。
    """
    response = _call_claude({
        'model': model,
        'max_tokens': max_tokens,
        'tools': [{
            'name': tool_name,
            'description': f'構造化された分析結果を出力する',
            'input_schema': input_schema,
        }],
        'tool_choice': {'type': 'tool', 'name': tool_name},
        'messages': [{'role': 'user', 'content': prompt}],
    }, timeout=timeout)
    for block in response.get('content', []):
        if block.get('type') == 'tool_use' and block.get('name') == tool_name:
            return block.get('input') or {}
    return None


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
        'これらが共通して報じているトピックを表す、**初見ユーザーが見出し1行で「何の話か」一発で分かる**日本語タイトルを作ってください。\n\n'
        '【最重要ルール: 一発理解性】\n'
        '- 必ず「主語(誰/何が)」+「目的語(何を/何の)」+「動詞 or 状態」を含める\n'
        '- 「〇〇をめぐる最新の動き」「〇〇問題まとめ」のような **何の話か特定できない曖昧な締め方は絶対禁止**\n'
        '- 商品名/組織名/事件名だけでは不十分。「何が起きたか」「何の問題か」を必ず添える\n'
        '- 例(❌→✅):\n'
        '  ❌「イラン・トランプ政権の対立をめぐる最新の動き」\n'
        '  ✅「核合意修復で対立する米イラン、パキスタン仲介の行方」\n'
        '  ❌「プラスチック危機をめぐる最新の動きまとめ」\n'
        '  ✅「プラスチック汚染削減条約、主要国の対立で交渉難航」\n'
        '  ❌「ソニーREON POCKET PRO Plus わかりやすく解説」\n'
        '  ✅「ソニーREON POCKET PRO Plus、首掛け冷暖房デバイス発表」\n'
        '  ❌「安保3文書の改定内容と論点をわかりやすく解説」\n'
        '  ✅「安保3文書改定、防衛費GDP比2%目標と反撃能力をめぐる論点」\n\n'
        '【その他ルール】\n'
        '- 18〜35文字程度のタイトル\n'
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
        # markdown 残骸の除去 (Claude が `# Title` 形式で返してくることがあるため)
        title = re.sub(r'^#+\s*', '', title)            # 先頭の # / ## など削除
        title = re.sub(r'^\*+\s*|\s*\*+$', '', title)   # 先頭/末尾の * 削除
        title = title.strip(' \t\n"\'「」')
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


# Flotopic で使うジャンル候補。AI に提示して選ばせる + 出力を検証する。
# fetcher/text_utils.py の _SINGLE_HIT_GENRES と auth/handler.py の VALID_GENRES の和集合を取り、
# Flotopic の 2026 ジャンルに合わせて整理。誤分類防止のため AI には必ずこの中から選ばせる。
_VALID_GENRE_SET = (
    '総合', '政治', '経済', 'ビジネス', 'テクノロジー', 'スポーツ', 'エンタメ',
    '科学', '国際', '社会', '健康', '株・金融', 'ファッション', 'グルメ',
    '教育', '文化', '環境',
)

_GENRES_PROMPT = (
    '【ジャンル選択肢】\n'
    f"次のリストからのみ選ぶ: {' / '.join(_VALID_GENRE_SET)}\n"
    '- 必ず1〜2個。最も主軸になるものを先頭に。\n'
    '- 該当が薄い場合は『総合』のみ。捨て台詞でジャンルを増やさない。\n'
    '- スポーツ/エンタメ/政治 など主題と関係ないジャンルは混ぜない (例: 米中外交トピックに『スポーツ』を付けない)。\n\n'
)


def _validate_genres(raw):
    """AI が返した genres を _VALID_GENRE_SET 内に絞り込む。
    - 文字列が来たら 1 要素配列扱い
    - リスト以外は ['総合']
    - 全要素が無効なら ['総合']
    - 重複除去 + 最大 2 個
    """
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return ['総合']
    seen = []
    for g in raw:
        if not isinstance(g, str):
            continue
        g = g.strip()
        if g in _VALID_GENRE_SET and g not in seen:
            seen.append(g)
        if len(seen) >= 2:
            break
    return seen if seen else ['総合']


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
    """APIレスポンステキストからJSONを抽出・パースする (legacy text-mode 用)。
    Tool Use 移行後はこの関数は使わない。tool_use.input が直接 dict で返る。"""
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


_VALID_PHASES = ['発端', '拡散', 'ピーク', '現在地', '収束']
_VALID_LEVELS = ['major', 'sub', 'detail']


def _build_story_schema(mode: str) -> dict:
    """Tool Use 用 JSON Schema を mode 別に構築。
    mode: 'minimal' | 'standard' | 'full'
    """
    base_props = {
        'aiSummary': {'type': 'string', 'description': '思考フレーム背景→課題→目的→手段→結果→今後で内部整理した1段落。主語+動詞+目的語+目的を明示。事実羅列禁止、何が普通と違うか/ポイントか/なぜ重要かの角度を込める。'},
        'keyPoint': {'type': 'string', 'description': 'この話のポイント1文(40字以内・体言止め)。普通と違う角度を抽出。例: 単なる外交儀礼ではなく米中対立の代理戦/赤字脱却よりブランド再建が本丸。'},
        'background': {'type': 'string', 'description': 'なぜ今このトピックが浮上しているか。直近1〜4週間の触媒(法案審議入り/決算/選挙日程/裁判期日/季節要因等)。'},
        'outlook': {'type': 'string', 'description': 'この先どうなるか。1文。〜が予想される/〜の可能性があるで締める。'},
        'topicTitle': {'type': 'string', 'description': '15文字以内のテーマ名(体言止め)。具体的な固有名詞を含む。例: 岸田政権の解散戦略。'},
        'latestUpdateHeadline': {'type': 'string', 'description': '最新の動きを40文字以内の1文(〜が〜した形式)。'},
        'isCoherent': {'type': 'boolean', 'description': 'true=全記事が同一主語・同一流れ。false=異主語/異論点混在。'},
        'topicLevel': {'type': 'string', 'enum': _VALID_LEVELS, 'description': 'major=国家間・産業横断/sub=majorの一側面/detail=個別発表'},
        'parentTopicTitle': {'type': ['string', 'null'], 'description': '上位テーマ名。独立トピックは null。'},
        'relatedTopicTitles': {'type': 'array', 'items': {'type': 'string'}, 'maxItems': 3, 'description': '因果・波及関係にある別テーマ。'},
        'genres': {'type': 'array', 'items': {'type': 'string', 'enum': list(_VALID_GENRE_SET)}, 'minItems': 1, 'maxItems': 2},
    }
    required = ['aiSummary', 'keyPoint', 'background', 'outlook', 'topicTitle', 'latestUpdateHeadline', 'isCoherent', 'topicLevel', 'genres']

    if mode == 'minimal':
        # minimal は backgroundContext/spreadReason/forecast/perspectives/timeline は無し
        pass
    else:
        base_props['backgroundContext'] = {'type': 'string', 'description': 'なぜ起きたか。背景にある構造的・社会的・経済的・政治的要因(2文)。'}
        base_props['spreadReason'] = {'type': 'string', 'description': 'なぜ広がったか。トリガー/時事文脈/注目層/関連ニュースの観点(2-3文)。'}
        base_props['perspectives'] = {'type': 'string', 'description': '各社の懸念・可能性・着目点を並列列挙(2〜3社)。例: 朝日は経済への打撃を懸念、産経は安全保障上の利益を指摘、毎日は外交プロセスの不透明性に着目。'}
        base_props['phase'] = {'type': 'string', 'enum': _VALID_PHASES}
        base_props['timeline'] = {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'date': {'type': 'string'},
                    'event': {'type': 'string'},
                    'transition': {'type': 'string'},
                },
                'required': ['event'],
            },
            'maxItems': 6 if mode == 'full' else 3,
        }
        required += ['backgroundContext', 'spreadReason', 'perspectives', 'phase', 'timeline']
        if mode == 'full':
            base_props['forecast'] = {'type': 'string', 'description': '今後どうなるか。記事内容を根拠にした仮説(2文)。〜が見込まれる/〜の可能性があるで締める。'}
            required += ['forecast']

    return {
        'type': 'object',
        'properties': base_props,
        'required': required,
    }


def _normalize_story_result(result: dict, mode: str) -> dict:
    """tool_use.input を内部 dict 形式に正規化。"""
    parent_title    = result.get('parentTopicTitle')
    related_titles  = result.get('relatedTopicTitles') or []
    if mode == 'minimal':
        return {
            'aiSummary':              str(result.get('aiSummary') or '').strip(),
            'keyPoint':               str(result.get('keyPoint') or '').strip()[:60],
            'background':             str(result.get('background') or '').strip(),
            'perspectives':           None,
            'outlook':                str(result.get('outlook') or '').strip(),
            'spreadReason':           '',
            'forecast':               '',
            'timeline':               [],
            'phase':                  '発端',
            'summaryMode':            'minimal',
            'topicTitle':             str(result.get('topicTitle') or '').strip()[:15],
            'latestUpdateHeadline':   str(result.get('latestUpdateHeadline') or '').strip()[:40],
            'isCoherent':             result.get('isCoherent') is not False,
            'topicLevel':             result.get('topicLevel') if result.get('topicLevel') in _VALID_LEVELS else 'detail',
            'parentTopicTitle':       str(parent_title).strip()[:30] if parent_title and parent_title != 'null' else None,
            'relatedTopicTitles':     [str(t).strip()[:30] for t in related_titles[:3]] if isinstance(related_titles, list) and related_titles else [],
            'genres':                 _validate_genres(result.get('genres')),
        }
    # standard / full 共通
    out = {
        'aiSummary':              str(result.get('aiSummary') or '').strip(),
        'keyPoint':               str(result.get('keyPoint') or '').strip()[:60],
        'backgroundContext':      str(result.get('backgroundContext') or '').strip(),
        'spreadReason':           str(result.get('spreadReason') or '').strip(),
        'background':             str(result.get('background') or '').strip(),
        'perspectives':           result.get('perspectives') if isinstance(result.get('perspectives'), str) else None,
        'outlook':                str(result.get('outlook') or '').strip(),
        'forecast':               str(result.get('forecast') or '').strip() if mode == 'full' else '',
        'timeline':               _sanitize_timeline(result.get('timeline'), max_items=6 if mode == 'full' else 3),
        'phase':                  result.get('phase') if result.get('phase') in _VALID_PHASES else '現在地',
        'summaryMode':            mode,
        'topicTitle':             str(result.get('topicTitle') or '').strip()[:15],
        'latestUpdateHeadline':   str(result.get('latestUpdateHeadline') or '').strip()[:40],
        'isCoherent':             result.get('isCoherent') is not False,
        'topicLevel':             result.get('topicLevel') if result.get('topicLevel') in _VALID_LEVELS else 'detail',
        'parentTopicTitle':       str(parent_title).strip()[:30] if parent_title and parent_title != 'null' else None,
        'relatedTopicTitles':     [str(t).strip()[:30] for t in related_titles[:3]] if isinstance(related_titles, list) and related_titles else [],
        'genres':                 _validate_genres(result.get('genres')),
    }
    return out


def _generate_story_minimal(articles: list) -> dict | None:
    """1〜2件: シンプルな1段落要約のみ生成（APIコスト最小）。Tool Use で structured output 強制。"""
    headlines, cnt = _build_headlines(articles, limit=2)
    prompt = (
        '以下はニューストピックに関する記事です。事実のみで簡潔にまとめてください。\n'
        '断定・感情語・メディア名禁止。固有名詞は初出時に括弧で1語説明 (例: スターリンク（SpaceXの衛星インターネット）)。\n\n'
        '【isCoherent判定】true=全記事が同一主語・同一流れ。false=異主語/異論点混在。\n'
        '【topicLevel判定】major=国家間・産業横断/sub=majorの一側面/detail=個別発表。\n'
        + _GENRES_PROMPT
        + f'\n記事情報（{cnt}件）:\n{headlines}'
    )
    try:
        result = _call_claude_tool(prompt, 'emit_topic_story', _build_story_schema('minimal'), max_tokens=600)
        if not result or not str(result.get('aiSummary') or '').strip():
            return None
        return _normalize_story_result(result, 'minimal')
    except Exception as e:
        print(f'generate_story (minimal) error: {e}')
        return None


_STORY_PROMPT_RULES = (
    '【トピック分析】事実は「〜した/〜と述べた」で記述。断定・感情語・メディア名禁止。主語を具体的に。\n'
    '固有名詞は初出時に括弧で1語説明 (例: スターリンク（SpaceXの衛星インターネット）)。\n'
    '【aiSummary】思考フレーム『背景→課題→目的→手段→結果→今後』で内部整理してから1段落で。事実羅列禁止、何が普通と違うか/ポイントか/なぜ重要かの角度を込める。物語的接続詞 (実は/ところが/にもかかわらず) で温度差を出す。\n'
    '【keyPoint】40字以内、体言止め。普通と違う角度を抽出。\n'
    '【backgroundContext】構造的・社会的・経済的・政治的要因 (2文)。\n'
    '【background】直近1〜4週間の触媒。backgroundContextと別の角度で。\n'
    '【spreadReason】トリガー/時事文脈/注目層/関連ニュース観点 (2-3文)。\n'
    '【perspectives】2〜3社の見解を並列。例: 朝日は経済への打撃を懸念、産経は安全保障上の利益を指摘。\n'
    '【outlook】1文。〜が予想される/〜の可能性があるで締める。\n'
    '【phase判定】発端は記事3件未満+24h以内のみ。それ以外で発端は選ばない。デフォルトは拡散。\n'
    '【isCoherent判定】true=全記事が同一主語・同一流れ。false=異主語/異論点混在。\n'
    '【topicTitle】15字以内、体言止め、具体的固有名詞を含む。\n'
    '【topicLevel】major=国家間・産業横断/sub=majorの一側面/detail=個別発表。\n'
    '【parentTopicTitle】明確に上位テーマの一部の場合のみ。独立は null。\n'
)


def _generate_story_standard(articles: list, cnt: int) -> dict | None:
    """3〜5件: Tool Use で structured output 強制 (旧 JSON 構文エラー撲滅)。"""
    headlines, _ = _build_headlines(articles, limit=5)
    prompt = _STORY_PROMPT_RULES + _GENRES_PROMPT + f'\n記事情報（{cnt}件）:\n{headlines}'
    try:
        result = _call_claude_tool(prompt, 'emit_topic_story', _build_story_schema('standard'), max_tokens=1300)
        if not result or not str(result.get('aiSummary') or '').strip():
            return None
        return _normalize_story_result(result, 'standard')
    except Exception as e:
        print(f'generate_story (standard) error: {e}')
        return None


def _generate_story_full(articles: list, cnt: int) -> dict | None:
    """6件以上: フル7セクション + 因果タイムライン（最大6件）。Tool Use で structured output 強制。"""
    headlines, _ = _build_headlines(articles, limit=10)
    prompt = (
        _WORD_RULES
        + _STORY_PROMPT_RULES
        + '【forecast】記事内容を根拠にした仮説 (2文)。〜が見込まれる/〜の可能性があるで締める。\n'
        + '【timeline】3〜6件の重要な転換点。event は体言止め40字以内、transition は因果接続 (これを受けて/その翌日/反発を受け/声明を機に/審議を経て) 25字以内。\n'
        + _GENRES_PROMPT
        + f'\n記事情報（{cnt}件・見出しと概要）:\n{headlines}'
    )
    try:
        result = _call_claude_tool(prompt, 'emit_topic_story', _build_story_schema('full'), max_tokens=1700)
        if not result or not str(result.get('aiSummary') or '').strip():
            return None
        return _normalize_story_result(result, 'full')
    except Exception as e:
        print(f'generate_story (full) error: {e}')
        return None


# 旧 text-mode の長大なプロンプト & JSON 手動 parse コードは削除。
# Tool Use API + JSON Schema (`_build_story_schema`) で structured output を物理的に強制。
# malformed JSON の発生確率は 0 になり、`generate_story (full) error: Expecting ',' delimiter`
# 系の警告が消える (T39 の続き、JSON parse error なぜなぜ分析の対策実装)。
