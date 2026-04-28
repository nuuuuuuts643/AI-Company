"""Claude Haiku を使ったタイトル・ストーリー生成とフォールバック (抽出的生成)。"""
import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime

from proc_config import ANTHROPIC_API_KEY
try:
    from article_fetcher import fetch_full_articles
except Exception as _imp_err:
    # article_fetcher は本機能専用 (T2026-0428-AL)。import 失敗時は機能を無効化し
    # 既存ルート (snippet ベース) で動かし続ける (落ちないことを優先)。
    print(f'[proc_ai] article_fetcher import 失敗 — 全文取得を無効化: {_imp_err}')
    fetch_full_articles = None

_CLAUDE_API_URL = 'https://api.anthropic.com/v1/messages'


_RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}


def _call_claude(payload: dict, timeout: int = 25) -> dict:
    """Claude API を呼び出す。429 / 5xx 系を最大3回リトライ（指数バックオフ）。

    T235 (2026-04-28): 旧実装は 429 のみリトライで、500/502/503/504 は 1回失敗で
    return None → 当該トピックの AI フィールドが空のまま topics.json に publish され、
    keyPoint=8.5% / backgroundContext=0% / perspectives=20% 等の低充填の主因の一つだった。
    Tool Use 化で 1 call の所要時間が伸び、Anthropic 側 generation timeout / internal error
    に当たる確率が上がっているため、5xx もリトライ対象に統合する。
    観測用に [METRIC] claude_retry を出して governance worker で集計可能にする。
    """
    body = json.dumps(payload).encode('utf-8')
    headers = {
        'x-api-key': ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json',
    }
    delay = 5
    last_err = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(_CLAUDE_API_URL, data=body, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in _RETRYABLE_HTTP_CODES and attempt < 3:
                retry_after = e.headers.get('retry-after') if hasattr(e, 'headers') and e.headers else None
                wait = int(retry_after) if retry_after else delay
                kind = 'rate_limit' if e.code == 429 else '5xx'
                print(f'[Claude] HTTP {e.code} ({kind}), {wait}s 待機 (attempt {attempt+1}/3)')
                # METRIC: governance worker で集計するため固定フォーマットで出力
                print(f'[METRIC] claude_retry attempt={attempt+1} code={e.code} kind={kind} wait_s={wait}')
                time.sleep(wait)
                delay *= 2
            else:
                # リトライ対象外 (4xx 等) または上限到達 → 上位に伝搬
                if e.code in _RETRYABLE_HTTP_CODES:
                    print(f'[METRIC] claude_retry_exhausted code={e.code} attempts={attempt+1}')
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            # ネットワーク層 (DNS/TCP/タイムアウト) も transient として扱う
            last_err = e
            if attempt < 3:
                print(f'[Claude] network error: {type(e).__name__}: {e}, {delay}s 待機 (attempt {attempt+1}/3)')
                print(f'[METRIC] claude_retry attempt={attempt+1} code=network kind={type(e).__name__} wait_s={delay}')
                time.sleep(delay)
                delay *= 2
            else:
                print(f'[METRIC] claude_retry_exhausted code=network attempts={attempt+1}')
                raise
    # ループを抜けた場合は最後のエラーを raise（理論上到達しないが防御的に）
    if last_err:
        raise last_err
    raise RuntimeError('Claude API retries exhausted')


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
# T2026-0428-J/E: 「トピックの状況」をユーザー視点で明確に区分する 4 値ラベル。
# 既存 phase (発端/拡散/ピーク/現在地/収束) は AI 内部判定の細粒度ラベル、
# statusLabel は detail page で読者に直接見せる粗粒度ラベル。
_VALID_STATUS_LABELS = ['発端', '進行中', '沈静化', '決着']


def _build_story_schema(mode: str) -> dict:
    """Tool Use 用 JSON Schema を mode 別に構築。
    mode: 'minimal' | 'standard' | 'full'
    """
    # T2026-0428-J/E (2026-04-28): フィールド再設計（最終確定版）。
    # 「なぜ今か」はグラフ(記事数スパイク)が示すべきであり AI に語らせない。
    # AI 要約は「状況解説 / 各社の見解 / 注目ポイント / AI予想」の 4 軸に集中。
    # 削除: spreadReason, backgroundContext, background, whatChanged
    # 追加: statusLabel (粗粒度フェーズ), watchPoints (今後の観察軸)
    base_props = {
        'aiSummary': {'type': 'string', 'description': '150字以内・2文構成。「何が起きたか」+「何を意味するか」。事実羅列禁止、読んだ人が結論を理解できる内容にする。'},
        'keyPoint': {'type': 'string', 'description': 'トピックの状況解説 (200〜300字の連続した文章)。★想定読者: このトピックを1週間後に初めて読む人。背景・経緯・現在の状況を一気に理解できる時系列ストーリーとして書く。「もともと〇〇という状況があり、△△をきっかけに□□が起き、現在〇〇の段階にある」のように物語的に語る。箇条書き・事実の羅列・「〇〇が△△した」の繰り返しは禁止。言葉を選び、簡潔でキレのある日本語で書く。情報を並べるのではなくニュースを語る。専門用語は初出時に括弧で平易化 (例: FOMC（米国の金融政策を決める会議）)。グラフの鮮度に依存しない、構造の明快さが命のフィールド。'},
        'outlook': {'type': 'string', 'description': 'AI予想として「この先どうなるか」を1文で。〜が予想される/〜の可能性があるで締める。文末に [確信度:高] [確信度:中] [確信度:低] のいずれかを必ず付与 (例: 「合意成立の可能性がある [確信度:中]」)。記事内に明示根拠あり=高、複数の状況証拠=中、推測ベース=低。後で新記事と照合して当否判定するため、検証可能な仮説として書くこと。'},
        'topicTitle': {'type': 'string', 'description': '15文字以内のテーマ名(体言止め)。具体的な固有名詞を含む。例: 岸田政権の解散戦略。'},
        'latestUpdateHeadline': {'type': 'string', 'description': '最新の動きを40文字以内の1文(〜が〜した形式)。'},
        'isCoherent': {'type': 'boolean', 'description': 'true=全記事が同一主語・同一流れ。false=異主語/異論点混在。'},
        'topicLevel': {'type': 'string', 'enum': _VALID_LEVELS, 'description': 'major=国家間・産業横断/sub=majorの一側面/detail=個別発表'},
        'parentTopicTitle': {'type': ['string', 'null'], 'description': '上位テーマ名。独立トピックは null。'},
        'relatedTopicTitles': {'type': 'array', 'items': {'type': 'string'}, 'maxItems': 3, 'description': '因果・波及関係にある別テーマ。'},
        'genres': {'type': 'array', 'items': {'type': 'string', 'enum': list(_VALID_GENRE_SET)}, 'minItems': 1, 'maxItems': 2},
    }
    required = ['aiSummary', 'keyPoint', 'outlook', 'topicTitle', 'latestUpdateHeadline', 'isCoherent', 'topicLevel', 'genres']

    if mode == 'minimal':
        # minimal は perspectives/timeline/watchPoints/statusLabel は無し (記事1〜2件では差分が出ない)
        pass
    else:
        base_props['statusLabel'] = {
            'type': 'string',
            'enum': _VALID_STATUS_LABELS,
            'description': 'トピックの現在状況を読者向け 4 値で示す。発端=注目され始めた直後/進行中=報道が続き熱量がある/沈静化=報道頻度が落ちている/決着=結論や合意が出て話題が閉じた。phase の細粒度ラベルとは別に、ユーザー向け粗粒度として独立に判定する。',
        }
        base_props['watchPoints'] = {
            'type': 'string',
            'description': 'これからの注目ポイントを複数軸で簡潔に案内する(150字以内)。断言や予測は避け「ここを見ておくといい」という観察視点を提示する。形式: ①〇〇の進捗 ②△△の対応 ③□□の動向 のように 2〜3 項目を ① ② ③ 番号付きで列挙。outlook (AI予想) とは役割が異なり、こちらは「どこを見るべきか」のガイドに徹する。',
        }
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
        required += ['statusLabel', 'watchPoints', 'perspectives', 'phase', 'timeline']
        if mode == 'full':
            base_props['forecast'] = {'type': 'string', 'description': '今後どうなるか。記事内容を根拠にした仮説(2文)。〜が見込まれる/〜の可能性があるで締める。文末に [確信度:高] [確信度:中] [確信度:低] のいずれかを必ず付与 (例: 「..今後数ヶ月で進展が見込まれる [確信度:中]」)。記事内に明示根拠あり=高、複数の状況証拠=中、推測ベース=低。'}
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
        # T219 修正 (2026-04-28): minimal モード (記事1-2件) は phase 概念が薄い
        # → 「発端」固定はユーザーに「フェーズ機能が機能していない」誤印象を与える
        # phase=None で返し、frontend 側の存在チェックで非表示にさせる
        return {
            'aiSummary':              str(result.get('aiSummary') or '').strip(),
            'keyPoint':               str(result.get('keyPoint') or '').strip()[:400],
            'statusLabel':            None,
            'watchPoints':            '',
            'perspectives':           None,
            'outlook':                str(result.get('outlook') or '').strip(),
            'forecast':               '',
            'timeline':               [],
            'phase':                  None,
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
    # T219 (2026-04-28): AI が phase='発端' を返した場合、standard/full mode (記事3件以上) では矯正
    # prompt で禁止しているが contract violation 防御として normalize 層でも矯正する
    raw_phase = result.get('phase')
    if raw_phase == '発端' and mode in ('standard', 'full'):
        raw_phase = '拡散'
    raw_status = result.get('statusLabel')
    out = {
        'aiSummary':              str(result.get('aiSummary') or '').strip(),
        # T2026-0428-J/E: keyPoint は 200〜300 字の物語形式に拡張。truncate は 400 字で安全側に。
        'keyPoint':               str(result.get('keyPoint') or '').strip()[:400],
        'statusLabel':            raw_status if raw_status in _VALID_STATUS_LABELS else None,
        'watchPoints':            str(result.get('watchPoints') or '').strip()[:200],
        'perspectives':           result.get('perspectives') if isinstance(result.get('perspectives'), str) else None,
        'outlook':                str(result.get('outlook') or '').strip(),
        'forecast':               str(result.get('forecast') or '').strip() if mode == 'full' else '',
        'timeline':               _sanitize_timeline(result.get('timeline'), max_items=6 if mode == 'full' else 3),
        'phase':                  raw_phase if raw_phase in _VALID_PHASES else '現在地',
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
        '【aiSummary】150字以内の1段落。「何が起きたか（1文）」+「なぜ重要か・何を意味するか（1文）」の2文構成。読んだ人が「つまりこういうことか」と理解できる結論を必ず含める。\n'
        '【keyPoint】★最重要フィールド。状況解説を 200〜300 字の連続した文章で書く。背景→時系列→現状の流れで物語的に語る。箇条書き・事実羅列禁止。言葉を選びキレのある日本語で。\n'
        '【outlook】AI予想として「この先どうなるか」を1文で。〜が予想される/〜の可能性があるで締める。文末に「[確信度:高/中/低]」を必ず付与。検証可能な仮説として書く (曖昧な「動向次第」禁止)。\n'
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
    '【aiSummary】150字以内の1段落。「何が起きたか（1文）」+「なぜ重要か・何を意味するか（1文）」の2文構成を基本とする。事実羅列禁止。読んだ人が「つまりこういうことか」と理解できる結論を必ず含める。\n'
    '【keyPoint】★最重要フィールド。トピックの状況解説を 200〜300 字の連続した文章で書く。読者がこのトピックを初めて知っても理解できる物語形式で構成する。\n'
    '  ◎ 構成: ① 背景（この問題がなぜ存在するか）から始める → ② 時系列（何がいつ起きたか）を自然な流れで織り込む → ③ 現在の状況で締める。\n'
    '  ◎ トーン: 言葉を選び、簡潔でキレのある日本語で書く。情報を並べるのではなくニュースを語る。\n'
    '  × 箇条書き禁止。事実の羅列禁止。「〇〇が△△した」の繰り返し禁止。\n'
    '  ◎ 「もともと〇〇という状況があり、△△をきっかけに□□が起き、現在〇〇の段階にある」のように物語的に語る。\n'
    '  ◎ 専門用語は初出時に括弧で平易化 (例: FOMC（米国の金融政策を決める会議）)。\n'
    '【statusLabel】読者向け 4 値ラベル: 発端 / 進行中 / 沈静化 / 決着。\n'
    '  発端=注目され始めた直後。進行中=報道が続き熱量がある。沈静化=報道頻度が落ちている。決着=結論や合意が出て話題が閉じた。\n'
    '【watchPoints】これからの注目ポイントを複数軸で簡潔に案内 (150字以内)。断言や予測ではなく「ここを見ておくといい」という観察視点。\n'
    '  形式: ①〇〇の進捗 ②△△の対応 ③□□の動向 のように 2〜3 項目を ① ② ③ 番号付きで列挙。outlook (AI予想) とは役割が異なる。\n'
    '【perspectives】2〜3社の見解を「[メディア名] は〜」の構文で並列列挙。各社の本文 (ある場合) を根拠にし、推測ではなく実際の論調差を抽出する。\n'
    '  - 公平性: 特定メディアの論調に引きずられず、各社を等しく扱う。1社だけ詳しく書くのは禁止。\n'
    '  - 各社の論調差が薄い場合は無理に違いを作らず「概ね同様の論調 (◯社の本文より)」と書く。\n'
    '  - 例 (◎): 朝日は経済への打撃を懸念、産経は安全保障上の利益を指摘、毎日は外交プロセスの不透明性に着目。\n'
    '  - 例 (×): 朝日が「重大な懸念」と強く批判 (1社だけ詳述は偏りに見える)。\n'
    '【outlook】★ AI予想として記述。1文。〜が予想される/〜の可能性があるで締める。文末に「[確信度:高/中/低]」を必ず付与する (例: 「合意成立の可能性がある [確信度:中]」)。記事内に明示根拠あり=高、複数の状況証拠=中、推測ベース=低。後で新記事と照合し当否判定するため、検証可能な仮説として書くこと (曖昧な「動向次第」「状況による」は禁止)。\n'
    '【phase判定】このトピックは記事3件以上のため「発端」は選択禁止。選択肢は「拡散/ピーク/現在地/収束」のみ。'
    'デフォルトは「拡散」。タイムライン上で同じ話題が繰り返し報じられ熱量が高ければ「ピーク」、'
    '報道が落ち着き同じ局面で続いていれば「現在地」、明確に下火・解決しているなら「収束」。\n'
    '【isCoherent判定】true=全記事が同一主語・同一流れ。false=異主語/異論点混在。\n'
    '【topicTitle】15字以内、体言止め、具体的固有名詞を含む。\n'
    '【topicLevel】major=国家間・産業横断/sub=majorの一側面/detail=個別発表。\n'
    '【parentTopicTitle】明確に上位テーマの一部の場合のみ。独立は null。\n'
)


def _generate_story_standard(articles: list, cnt: int) -> dict | None:
    """3〜5件: Tool Use で structured output 強制 (旧 JSON 構文エラー撲滅)。
    T2026-0428-AL: 上位3記事の全文を取得し perspectives の比較根拠とする。"""
    headlines, _ = _build_headlines(articles, limit=5)
    media_block = _build_media_comparison_block(articles, max_count=3)
    prompt = (
        _STORY_PROMPT_RULES
        + _GENRES_PROMPT
        + f'\n記事情報（{cnt}件）:\n{headlines}'
        + (f'\n{media_block}' if media_block else '')
    )
    try:
        result = _call_claude_tool(prompt, 'emit_topic_story', _build_story_schema('standard'), max_tokens=1300)
        if not result or not str(result.get('aiSummary') or '').strip():
            return None
        return _normalize_story_result(result, 'standard')
    except Exception as e:
        print(f'generate_story (standard) error: {e}')
        return None


def _build_media_comparison_block(articles: list, max_count: int = 3) -> str:
    """T2026-0428-AL: 上位3記事の全文を取得し『メディア各社の本文』ブロックを返す。
    fetch_full_articles が無い (import 失敗) / 失敗時は空文字を返し、prompt は従来通り snippet ベースで動く。"""
    if fetch_full_articles is None or not articles:
        return ''
    try:
        fetched = fetch_full_articles(articles, max_count=max_count,
                                      per_url_timeout=5.0, max_text_chars=2500)
    except Exception as e:
        print(f'[proc_ai] fetch_full_articles 失敗 (snippet にフォールバック): {e}')
        return ''
    if not fetched:
        return ''
    succeeded = [f for f in fetched if f.get('isFull')]
    if not succeeded:
        return ''
    lines = ['', '【メディア各社の本文 (perspectives 比較用・公平に扱うこと)】']
    for f in fetched:
        marker = '全文' if f.get('isFull') else '概要'
        src = f.get('source') or '不明媒体'
        text = (f.get('fullText') or '').strip()
        if not text:
            continue
        lines.append(f'[{src} {marker}] {text}')
    return '\n'.join(lines)


def _generate_story_full(articles: list, cnt: int) -> dict | None:
    """6件以上: フル7セクション + 因果タイムライン（最大6件）。Tool Use で structured output 強制。
    記事数が多い大型トピック向け。Sonnet 4.6 を使い keyPoint/backgroundContext/perspectives 等の
    記述品質を底上げする (minimal/standard は Haiku 据え置き)。
    T2026-0428-AL: 上位3記事の全文を取得し perspectives の比較根拠とする。"""
    headlines, _ = _build_headlines(articles, limit=10)
    media_block = _build_media_comparison_block(articles, max_count=3)
    prompt = (
        _WORD_RULES
        + _STORY_PROMPT_RULES
        + '【forecast】記事内容を根拠にした仮説 (2文)。〜が見込まれる/〜の可能性があるで締める。文末に「[確信度:高/中/低]」を必ず付与する (記事内に明示根拠あり=高、複数の状況証拠=中、推測ベース=低)。\n'
        + '【timeline】3〜6件の重要な転換点。event は体言止め40字以内、transition は因果接続 (これを受けて/その翌日/反発を受け/声明を機に/審議を経て) 25字以内。\n'
        + _GENRES_PROMPT
        + f'\n記事情報（{cnt}件・見出しと概要）:\n{headlines}'
        + (f'\n{media_block}' if media_block else '')
    )
    try:
        # T2026-0428-AL: 全文ブロック注入で prompt が ~6000 字伸びるため timeout を 60s に拡張
        # (旧 25s では Sonnet 4.6 + 1700 max_tokens の生成が間に合わず full mode が
        # まるごと失敗 → fallback で None になり aiGenerated=False のまま放置されていた)
        result = _call_claude_tool(
            prompt, 'emit_topic_story', _build_story_schema('full'),
            max_tokens=1700, timeout=60, model='claude-sonnet-4-6',
        )
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


# ─────────────────────────────────────────────────────────────────────────────
# T2026-0428-PRED: outlook (AI予想) 自動当否判定
# ─────────────────────────────────────────────────────────────────────────────
_VALID_PREDICTION_RESULTS = ('matched', 'partial', 'missed', 'pending')

_PREDICTION_JUDGE_SCHEMA = {
    'type': 'object',
    'properties': {
        'result': {
            'type': 'string',
            'enum': list(_VALID_PREDICTION_RESULTS),
            'description': (
                'matched=新記事群が予想内容を明確に裏付けている / '
                'partial=部分的に方向性は合っているが完全には一致しない / '
                'missed=予想と異なる方向に展開した・反対の事実が報じられた / '
                'pending=判定可能な根拠が新記事群に十分含まれない (継続観測)'
            ),
        },
        'evidence': {
            'type': 'string',
            'description': '判定の根拠を 80 字以内で。どの記事の何を根拠にしたかを簡潔に。',
        },
    },
    'required': ['result', 'evidence'],
}


def judge_prediction(outlook: str, new_titles: list, min_titles: int = 5) -> dict | None:
    """outlook (AI 予想) と、predictionMadeAt 以降に追加された新記事タイトル群を比較し
    matched / partial / missed / pending を返す。

    Args:
        outlook:    AI が立てた予想文 (1〜2 文)。文末に [確信度:高/中/低] が付与されている。
        new_titles: predictionMadeAt 以降に追加された記事タイトルのリスト。
        min_titles: 判定に必要な最小タイトル数 (5 件未満は 1 件で判断するとノイズになるため None を返す)。

    Returns:
        {'result': 'matched'|'partial'|'missed'|'pending', 'evidence': '...'}
        または None (API 未設定 / 入力不足 / API 失敗時)。
    """
    if not ANTHROPIC_API_KEY:
        return None
    outlook = (outlook or '').strip()
    if not outlook:
        return None
    titles = [str(t).strip() for t in (new_titles or []) if str(t).strip()]
    if len(titles) < min_titles:
        # 1〜数件で判定するとノイズなので明示的に「pending = 継続観測」を返す。
        # API は呼ばずローカルで返す (コスト抑制)。
        return {'result': 'pending', 'evidence': f'新記事 {len(titles)} 件 < {min_titles} 件のため継続観測。'}

    headlines = '\n'.join(f'- {clean_headline(t)[:80]}' for t in titles[:20])
    prompt = (
        '以下は過去にAIが立てた「予想」と、その予想を立てた時刻以降に追加された新しい記事タイトル群です。\n'
        '新記事群の内容から、予想の当否を 4 値で判定してください。\n\n'
        '【判定ルール】\n'
        '- matched: 新記事群が予想の内容を明確に裏付けている (固有名詞・事象の方向性が一致)。\n'
        '- partial: 方向性は合っているが完全には一致しない / 部分的に進展。\n'
        '- missed:  予想と異なる方向に展開した、または反対の事実が報じられた。\n'
        '- pending: 新記事群に判定可能な根拠が十分含まれない (継続観測すべき)。\n\n'
        '【evidence】判定の根拠を 80 字以内で簡潔に。「どの記事の何を根拠にしたか」を書く。\n'
        '推測ではなく、新記事群に書かれた事実を引用すること。\n\n'
        f'【予想文】\n{outlook}\n\n'
        f'【新記事タイトル ({len(titles)} 件)】\n{headlines}'
    )
    try:
        result = _call_claude_tool(
            prompt, 'judge_prediction', _PREDICTION_JUDGE_SCHEMA,
            max_tokens=300, timeout=20,
        )
        if not result:
            return None
        verdict = result.get('result')
        if verdict not in _VALID_PREDICTION_RESULTS:
            return None
        evidence = str(result.get('evidence') or '').strip()[:200]
        return {'result': verdict, 'evidence': evidence}
    except Exception as e:
        print(f'judge_prediction error: {e}')
        return None
