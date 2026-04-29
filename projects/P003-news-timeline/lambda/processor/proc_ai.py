"""Claude Haiku を使ったタイトル・ストーリー生成とフォールバック (抽出的生成)。"""
from __future__ import annotations  # PEP 563 — Python 3.9 でも `str | None` annotation を許容

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
        'anthropic-beta': 'prompt-caching-2024-07-31',
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
                       model: str = 'claude-haiku-4-5-20251001',
                       system: str | None = None) -> dict | None:
    """Claude Tool Use API で structured output を取得。
    JSON Schema で出力形式を強制するため malformed JSON は物理的に発生しない。

    T2026-0428-AJ: prompt caching 対応。`system` を渡すと cache_control: ephemeral 付きで
    送信し、固定の共通プロンプトをキャッシュ再利用する (Haiku 2048 / Sonnet 1024 tokens 必要)。
    Returns: tool_use.input (dict) / 失敗時 None。

    measured: T2026-0429-P (2026-04-29) cache savings 試算。
      _SYSTEM_PROMPT 文字数 = 5362 chars (日本語混在)。
      日本語混在の Anthropic tokenizer 実測値 ≈ 1 token / 1.7-2.0 chars
        → 推定 2700-3150 tokens (Haiku 最低 2048 tokens を上回る・キャッシュ適用可能)。
      バッチ 1回 (MAX_API_CALLS=20) のうち、初回が cache write、2-20 件目が cache read。
      cache read tokens は 90% 割引 (Anthropic 公式)。
      節約: ~2900 tokens × 19 件 × 90% = ~49,590 tokens / バッチ。
      Haiku 4.5 input $0.80/MTok → 約 $0.04 / バッチ × 2 batch/day = $0.08/day 節約。
    観測: 実装後の実測は CloudWatch Insights で
      `fields @timestamp, @message | filter @message like /claude_cache/`
      で `read=` の出現を確認すること。read=0 が連続するならキャッシュミス。
    """
    payload = {
        'model': model,
        'max_tokens': max_tokens,
        'tools': [{
            'name': tool_name,
            'description': f'構造化された分析結果を出力する',
            'input_schema': input_schema,
        }],
        'tool_choice': {'type': 'tool', 'name': tool_name},
        'messages': [{'role': 'user', 'content': prompt}],
    }
    if system:
        payload['system'] = [{
            'type': 'text',
            'text': system,
            'cache_control': {'type': 'ephemeral'},
        }]
    response = _call_claude(payload, timeout=timeout)
    # cache hit/miss の観測 (governance worker で集計可能に)
    usage = response.get('usage') or {}
    cache_read  = usage.get('cache_read_input_tokens', 0)
    cache_write = usage.get('cache_creation_input_tokens', 0)
    if cache_read or cache_write:
        print(f'[METRIC] claude_cache read={cache_read} write={cache_write} model={model}')
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
# T2026-0428-AU (2026-04-28): フロント GENRES (frontend/app.js:93) と完全一致させる。
# 旧候補にあった「経済・教育・文化・環境」は AI が選んでもフロントに表示できない隠れバグの主因
# だった (107トピック中 経済=7/文化=1 が完全に隠れていた)。経済→ビジネス、文化/教育/環境→くらし
# に統合し、不一致を物理的に潰す。フロント側で旧 genre から新 genre に alias する。
_VALID_GENRE_SET = (
    '総合', '政治', 'ビジネス', '株・金融', 'テクノロジー', 'スポーツ', 'エンタメ',
    '科学', '健康', '国際', 'くらし', '社会', 'グルメ', 'ファッション',
)

_GENRES_PROMPT = (
    '【ジャンル選択肢】\n'
    f"次のリストからのみ選ぶ: {' / '.join(_VALID_GENRE_SET)}\n"
    '- 必ず1〜2個。最も主軸になるものを先頭に。\n'
    '- 該当が薄い場合は『総合』のみ。捨て台詞でジャンルを増やさない。\n'
    '\n'
    '【主語ベースで分類する】\n'
    '記事の「主題＝主語」で判断する。「内容のキーワード」に引きずられて誤分類しないこと。\n'
    '- 例1: 「選手がケガから回復しシーズン復帰」→ 主語=選手/競技 → 『スポーツ』(『健康』ではない)\n'
    '- 例2: 「健康的な食事の研究結果が公表」→ 主語=研究/食生活 → 『健康』\n'
    '- 例3: 「俳優が新作映画で病気の役を演じる」→ 主語=俳優/作品 → 『エンタメ』(『健康』ではない)\n'
    '- 例4: 「企業がAIを使った介護ロボを発売」→ 主語=企業/製品 → 『ビジネス』『テクノロジー』(『健康』ではない)\n'
    '\n'
    '【ジャンル境界の明確化】\n'
    '- ファッション = アパレル・コスメ・美容・ブランド・コレクション・デザイナーが主語のとき\n'
    '- グルメ = 飲食店・料理・食材・レシピが主語のとき (万博・経済イベントは含まない)\n'
    '- ビジネス = 企業活動・売上・買収・業績・経済全般・物価・GDP が主語のとき\n'
    '- くらし = 生活・育児・介護・教育・文化イベント・ペット・趣味・環境問題 が主語のとき\n'
    '- 株・金融 = 株価・為替・金利・日銀・投資商品 が主語のとき (ビジネスの下位ではなく独立)\n'
    '- 健康 = 医療・薬・病気・治療・栄養学 が主語のとき (ケガをした人が選手ならスポーツ)\n'
    '- 主題と関係ないジャンルは混ぜない (例: 米中外交トピックに『スポーツ』を付けない)。\n\n'
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
# T2026-0429-KP3 (2026-04-29): keyPoint ハード最小文字数。これを下回ったら 1 回だけ再生成を要求する。
# 旧スキーマ「200〜300 字」が prompt 上の推奨値でしかなく、実測 1.9% しか満たしていなかったため
# サーバ側で物理ガードを追加。proc_storage.KEYPOINT_MIN_LENGTH = 100 と完全一致させる。
_KEYPOINT_MIN_CHARS = 100
# パターン2 横断適用 (2026-04-29): perspectives / watchPoints / outlook にも最低文字数を schema 強制。
# 旧スキーマは keyPoint のみ minLength を持ち、他フィールドは「150字以内」等の上限のみで
# 実測 watchPoints 平均 38 字 / outlook 41 字 / perspectives 47 字程度の薄さに留まっていた。
# 最低文字数を schema に書くと Tool Use validation が schema 違反で再要求するため物理ガードになる。
_PERSPECTIVES_MIN_CHARS = 60
_WATCHPOINTS_MIN_CHARS = 80   # ① 〇〇 ② △△ の 2 項目分 (各 40 字目安) の合計
_OUTLOOK_MIN_CHARS = 60


def _keypoint_too_short(s) -> bool:
    """keyPoint が 100 字未満かどうかを判定。空・None も True (=不十分) として扱う。"""
    if not isinstance(s, str):
        return True
    return len(s.strip()) < _KEYPOINT_MIN_CHARS


def _emit_keypoint_metric(mode: str, keypoint, *, retried: bool) -> None:
    """T2026-0429-J: keyPoint 文字数を CloudWatch から拾える形で 1 行 print する。

    フォーマット: `[METRIC] keypoint_len mode=<mode> len=<n> ge100=<0|1> ge200=<0|1> retried=<0|1>`
    用途: 改善効果 (≥100 字 70% 達成) を本番ログから集計可能にする。
    """
    n = len((keypoint or '').strip()) if isinstance(keypoint, str) else 0
    print(
        f'[METRIC] keypoint_len mode={mode} len={n} '
        f'ge100={1 if n >= 100 else 0} '
        f'ge200={1 if n >= 200 else 0} '
        f'retried={1 if retried else 0}'
    )
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
    # AI 要約は「状況解説 / 各メディアの見解 / 注目ポイント / AI予想」の 4 軸に集中。
    # 削除: spreadReason, backgroundContext, background, whatChanged
    # 追加: statusLabel (粗粒度フェーズ), watchPoints (今後の観察軸)
    base_props = {
        'aiSummary': {'type': 'string', 'description': '150字以内・2文構成。「何が起きたか」+「何を意味するか」。事実羅列禁止、読んだ人が結論を理解できる内容にする。'},
        'keyPoint': {'type': 'string', 'minLength': _KEYPOINT_MIN_CHARS, 'description': 'トピックの状況解説。**必ず 100 字以上 必須** (推奨 200〜300 字)。100 字未満は schema 違反として扱われ再生成される。短い箇条書き・タイトル風の一行は禁止。★想定読者: このトピックを1週間後に初めて読む人。背景・経緯・現在の状況を一気に理解できる時系列ストーリーとして書く。「もともと〇〇という状況があり、△△をきっかけに□□が起き、現在〇〇の段階にある」のように物語的に語る。箇条書き・事実の羅列・「〇〇が△△した」の繰り返しは禁止。言葉を選び、簡潔でキレのある日本語で書く。情報を並べるのではなくニュースを語る。専門用語は初出時に括弧で平易化 (例: FOMC（米国の金融政策を決める会議）)。グラフの鮮度に依存しない、構造の明快さが命のフィールド。'},
        'outlook': {'type': 'string', 'minLength': _OUTLOOK_MIN_CHARS, 'description': 'AI予想として「この先どうなるか」を1文で。**60 字以上 必須**。〜が予想される/〜の可能性があるで締める。文末に [確信度:高] [確信度:中] [確信度:低] のいずれかを必ず付与 (例: 「合意成立の可能性がある [確信度:中]」)。記事内に明示根拠あり=高、複数の状況証拠=中、推測ベース=低。後で新記事と照合して当否判定するため、検証可能な仮説として書くこと。'},
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
            'minLength': _WATCHPOINTS_MIN_CHARS,
            'description': 'これからの注目ポイントを複数軸で簡潔に案内する(80〜150字)。**80 字以上 必須**。断言や予測は避け「ここを見ておくといい」という観察視点を提示する。形式: ①〇〇の進捗 ②△△の対応 ③□□の動向 のように 2〜3 項目を ① ② ③ 番号付きで列挙し、各項目を 40 字程度の説明で書く。outlook (AI予想) とは役割が異なり、こちらは「どこを見るべきか」のガイドに徹する。',
        }
        base_props['perspectives'] = {'type': 'string', 'minLength': _PERSPECTIVES_MIN_CHARS, 'description': '各社の懸念・可能性・着目点を並列列挙(2〜3社・60字以上)。**60 字以上 必須**。例: 朝日は経済への打撃を懸念、産経は安全保障上の利益を指摘、毎日は外交プロセスの不透明性に着目。'}
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


# T2026-0429-J (2026-04-29): 旧 _retry_short_keypoint は撤去 (ナオヤ指示・コスト抑制)。
# 「100 字未満なら 1 回再生成」は AI コール 2x 増 → コスト 2x 増のため許容しない。
# 代替策: プロンプト強化 (worked example + 200 字目標明示) のみで品質改善を狙う。
# 計測: _emit_keypoint_metric が CloudWatch ログに残し、verify_keypoint_length.py で外部観測する。


def _generate_story_minimal(articles: list) -> dict | None:
    """1〜2件: シンプルな1段落要約のみ生成（APIコスト最小）。Tool Use で structured output 強制。
    T2026-0428-AJ: 共通プロンプトは _SYSTEM_PROMPT に集約 (cache_control 対象)。
    """
    headlines, cnt = _build_headlines(articles, limit=2)
    prompt = (
        f'【今回のモード: minimal (記事 {cnt} 件)】\n'
        'phase / timeline / perspectives / statusLabel / watchPoints は schema 上存在しないため出力しない。\n'
        'aiSummary・keyPoint・outlook・topicTitle・latestUpdateHeadline・isCoherent・topicLevel・genres のみを schema に従って出力する。\n\n'
        f'記事情報（{cnt}件）:\n{headlines}'
    )
    try:
        schema = _build_story_schema('minimal')
        result = _call_claude_tool(
            prompt, 'emit_topic_story', schema,
            max_tokens=600, system=_SYSTEM_PROMPT,
        )
        if not result or not str(result.get('aiSummary') or '').strip():
            return None
        # T2026-0429-J: 再生成ロジックは廃止 (コスト抑制)。短い場合はメトリクスログで警告のみ。
        if _keypoint_too_short(result.get('keyPoint')):
            print(
                f'[WARN] keypoint_short mode=minimal len='
                f'{len((result.get("keyPoint") or "").strip())}'
            )
        _emit_keypoint_metric('minimal', result.get('keyPoint'), retried=False)
        return _normalize_story_result(result, 'minimal')
    except Exception as e:
        print(f'generate_story (minimal) error: {e}')
        return None


_STORY_PROMPT_RULES = (
    '【トピック分析】事実は「〜した/〜と述べた」で記述。断定・感情語・メディア名禁止。主語を具体的に。\n'
    '固有名詞は初出時に括弧で1語説明 (例: スターリンク（SpaceXの衛星インターネット）)。\n'
    '【aiSummary】150字以内の1段落。「何が起きたか（1文）」+「なぜ重要か・何を意味するか（1文）」の2文構成を基本とする。事実羅列禁止。読んだ人が「つまりこういうことか」と理解できる結論を必ず含める。\n'
    # T2026-0429-J (2026-04-29): keyPoint の充填率は 100% だが ≥100 字は 2.17% しか出ていない実測。
    # 平均 35.6 字で大半が「タイトル風一行」(例: 19〜36 字)。LLM が aiSummary や latestUpdateHeadline と
    # 役割を混同している。フィールド名 "keyPoint" の英語が「要点メモ」を連想させているのが第一原因。
    # → ① 200〜300 字目標を最重要要件として強調 ② ＜悪い例 vs 良い例＞ の worked example を埋め込む。
    '【keyPoint】★最重要フィールド。aiSummary / latestUpdateHeadline とは役割が完全に異なる。\n'
    '  ★★★ 文字数のハード要件: **必ず 200 字以上 300 字以内 (目標)**。\n'
    '       ハード下限: **100 字未満は schema 違反**として扱われ再生成される。\n'
    '       ★ aiSummary (150 字以内 結論) や latestUpdateHeadline (40 字以内 見出し) と"絶対に同じ長さ"にしない。\n'
    '       ★ keyPoint だけが「物語形式の状況解説」役。タイトル風 1 行は禁止。\n'
    '  ★★★ 想定読者: このトピックを 1 週間後に初めて読む人。背景・経緯・現在の状況を一気に理解できる時系列ストーリーとして書く。\n'
    '  ◎ 構成: ① 背景（この問題がなぜ存在するか）から始める → ② 時系列（何がいつ起きたか）を自然な流れで織り込む → ③ 現在の状況で締める。\n'
    '  ◎ トーン: 言葉を選び、簡潔でキレのある日本語で書く。情報を並べるのではなくニュースを語る。\n'
    '  × 箇条書き禁止。事実の羅列禁止。「〇〇が△△した」の繰り返し禁止。\n'
    '  ◎ 「もともと〇〇という状況があり、△△をきっかけに□□が起き、現在〇〇の段階にある」のように物語的に語る。\n'
    '  ◎ 専門用語は初出時に括弧で平易化 (例: FOMC（米国の金融政策を決める会議）)。\n'
    '  ◎ 出力前に self-check: keyPoint の文字数を数え、200 字未満なら**背景・経緯を補強して書き直してから出力する**。\n'
    '  ─── ★ 良い例 (251 字) ───\n'
    '  「これまでのAI競争は、大量テキストから統計的パターンを学ぶ言語モデルの性能向上が中心だった。しかし実世界での応用を考えると、単なる会話能力では限界がある。'
    'OpenAI や DeepMind といった主要企業は、物理現象や因果関係を直接理解する「世界モデル」（現実世界の仕組みを数学的に再現する手法）の開発にリソースを集中させ始めている。'
    'この転換により、ロボット制御や複雑なシミュレーション、科学研究での応用が現実味を帯びてきた段階にある。」\n'
    '  ─── × 悪い例 (21 字) ───「ロシア撤退と過激派攻勢の同時進行が新段階へ」← これは latestUpdateHeadline の役割。keyPoint としては不合格。\n'
    '  ─── × 悪い例 (36 字) ───「円安抑制を目的とした段階的利上げ継続、2026 年までの政策見通しが明確化」← これは aiSummary 級の長さ。keyPoint は 6 倍以上の物語が必要。\n'
    '【statusLabel】読者向け 4 値ラベル: 発端 / 進行中 / 沈静化 / 決着。\n'
    '  発端=注目され始めた直後。進行中=報道が続き熱量がある。沈静化=報道頻度が落ちている。決着=結論や合意が出て話題が閉じた。\n'
    '【watchPoints】これからの注目ポイントを複数軸で簡潔に案内 (80〜150字 / **80 字以上 必須**)。断言や予測ではなく「ここを見ておくといい」という観察視点。\n'
    '  形式: ①〇〇の進捗 ②△△の対応 ③□□の動向 のように 2〜3 項目を ① ② ③ 番号付きで列挙し、各項目に 40 字程度の説明を加える。outlook (AI予想) とは役割が異なる。\n'
    '  ★ 観点 1 件は **次回のブランチ判定材料となる注目点**を必ず含める (例: ①新たな主役エンティティが登場するか / 別事案への波及があるか等)。後続記事が来た際の merge/branch 判断を AI が再判定する際の手がかりになる。\n'
    '【perspectives】2〜3社の見解を「[メディア名] は〜」の構文で並列列挙 (**60 字以上 必須**)。各社の本文 (ある場合) を根拠にし、推測ではなく実際の論調差を抽出する。\n'
    '  - 公平性: 特定メディアの論調に引きずられず、各社を等しく扱う。1社だけ詳しく書くのは禁止。\n'
    '  - 各社の論調差が薄い場合は無理に違いを作らず「概ね同様の論調 (◯社の本文より)」と書く。\n'
    '  - 例 (◎): 朝日は経済への打撃を懸念、産経は安全保障上の利益を指摘、毎日は外交プロセスの不透明性に着目。\n'
    '  - 例 (×): 朝日が「重大な懸念」と強く批判 (1社だけ詳述は偏りに見える)。\n'
    '【outlook】★ AI予想として記述 (**60 字以上 必須**)。1文。〜が予想される/〜の可能性があるで締める。文末に「[確信度:高/中/低]」を必ず付与する (例: 「合意成立の可能性がある [確信度:中]」)。記事内に明示根拠あり=高、複数の状況証拠=中、推測ベース=低。後で新記事と照合し当否判定するため、検証可能な仮説として書くこと (曖昧な「動向次第」「状況による」は禁止)。\n'
    '【phase判定】このトピックは記事3件以上のため「発端」は選択禁止。選択肢は「拡散/ピーク/現在地/収束」のみ。'
    'デフォルトは「拡散」。タイムライン上で同じ話題が繰り返し報じられ熱量が高ければ「ピーク」、'
    '報道が落ち着き同じ局面で続いていれば「現在地」、明確に下火・解決しているなら「収束」。\n'
    '【isCoherent判定】true=全記事が同一主語・同一流れ。false=異主語/異論点混在。\n'
    '【topicTitle】15字以内、体言止め、具体的固有名詞を含む。\n'
    '【topicLevel】major=国家間・産業横断/sub=majorの一側面/detail=個別発表。\n'
    '【parentTopicTitle】明確に上位テーマの一部の場合のみ。独立は null。\n'
    '【ストーリー分岐の指針 (T2026-0429-B)】\n'
    '  ★ 同一事件の新展開 (逮捕→起訴→判決 / 申請→受理→可決 / 発表→発売→不具合報告 等) は**ブランチではなく同トピック継続**として扱う (timeline に追加)。\n'
    '  ★ 主役 (主要 PERSON / ORG) が変わる、もしくは因果的に独立した別事案が始まった場合のみブランチ (新トピック起点) を起こす。\n'
    '  ★ 数字 (velocityScore / 記事数) は分岐の動機にしない。内容軸 (主役・因果・登場人物重複) のみで判断する。\n'
)


# T2026-0428-AJ: prompt caching 用の共通システムプロンプト。
# 全モード (minimal/standard/full) で **完全に同一バイト** を渡すことで cache prefix がヒットする。
# Haiku 最低 2048 tokens / Sonnet 最低 1024 tokens 必要 → _WORD_RULES + _STORY_PROMPT_RULES +
# _GENRES_PROMPT + 役割定義 + forecast/timeline/出力品質チェックをまとめて 7000 字超 (≒4000 tokens 以上)
# を確保する。中身を変えるとキャッシュが破棄されるため、修正時は意図的に行うこと。
_SYSTEM_PROMPT = (
    'あなたはニュース記事を構造化分析して JSON Schema で出力する専門アシスタントです。\n'
    '出力は必ず指定されたツールスキーマに従い、事実ベース・断定回避・感情語回避を徹底してください。\n'
    'メディア名 (毎日新聞/NHK 等) は記述に出さない。固有名詞は初出時に括弧で1語説明を加える。\n'
    'モード (minimal/standard/full) は user メッセージで通知される。schema に存在しないフィールドは出力しないこと。\n\n'
    + _WORD_RULES
    + _STORY_PROMPT_RULES
    + _GENRES_PROMPT
    + '【forecast (full mode のみ)】記事内容を根拠にした仮説 (2文)。〜が見込まれる/〜の可能性があるで締める。'
      '文末に「[確信度:高/中/低]」を必ず付与する (記事内に明示根拠あり=高、複数の状況証拠=中、推測ベース=低)。\n'
    '【timeline (standard/full)】重要な転換点。event は体言止め40字以内、'
    'transition は因果接続 (これを受けて/その翌日/反発を受け/声明を機に/審議を経て) 25字以内。'
    'standard は最大3件、full は最大6件。最後の項目に transition は付けない。\n'
    '【出力品質チェック (送信前に内部で確認すること)】\n'
    '- aiSummary は 150 字以内・2文構成。1文目=何が起きたか、2文目=なぜ重要か/何を意味するか。\n'
    # T2026-0429-J: keyPoint 平均 35.6 字 / ≥100 字 2.17% の実測を受け、目標を「200 字以上 300 字以内」に格上げし、
    # aiSummary との混同を防ぐため "200 字以上必須" を最重要要件として最優先で記述する。
    '- keyPoint は **200 字以上 300 字以内 (目標)・100 字未満は schema 違反として再生成される**。\n'
    '  → 出力直前に必ず文字数を数え、200 字未満なら**背景・経緯を 1 段落補強してから**出力する。100 字未満は不合格。\n'
    '  → aiSummary (150 字以内) や latestUpdateHeadline (40 字以内) と同じ長さで終わらせない。keyPoint だけが物語形式の長文。\n'
    '  → 短い箇条書き・タイトル風の一行は禁止。「〇〇が△△した」の繰り返し・事実羅列は禁止。\n'
    '  → もともと〇〇 → △△を機に □□ → 現在〇〇 の物語形式で構成する。\n'
    '- perspectives は 2〜3 社を等しい分量で扱う。1 社だけ詳述しない。論調差が薄ければ「概ね同様」と書く。\n'
    '- outlook / forecast の文末に必ず [確信度:高] / [確信度:中] / [確信度:低] のいずれかを付与する。\n'
    '- topicTitle は 15 字以内・体言止め・固有名詞を含む。「〜の最新動向」「〜まとめ」のような曖昧表現は禁止。\n'
    '- latestUpdateHeadline は 40 字以内・「〜が〜した」形式。\n'
    '【記事データの渡し方】\n'
    '- user メッセージには「記事情報（N件）」のブロックがあり、必要に応じて「メディア各社の本文 (perspectives 比較用)」が続く。\n'
    '- 記事タイトルや概要をそのままコピーせず、抽象化・統合した分析を出力する。\n'
    '- 「メディア各社の本文」が提供された場合、perspectives はそのテキストを根拠に各社の論調差を抽出する。\n'
    '【失敗回避】\n'
    '- schema の required フィールドを欠落させない。型が enum なら enum 内から選ぶ。\n'
    '- 出力前に self-check: required を全部埋めたか / 確信度タグを付け忘れていないか。\n'
)


def _generate_story_standard(articles: list, cnt: int) -> dict | None:
    """3〜5件: Tool Use で structured output 強制 (旧 JSON 構文エラー撲滅)。
    T2026-0428-AL: 上位3記事の全文を取得し perspectives の比較根拠とする。
    T2026-0428-AJ: 共通プロンプトは _SYSTEM_PROMPT に集約 (cache_control 対象)。"""
    headlines, _ = _build_headlines(articles, limit=5)
    media_block = _build_media_comparison_block(articles, max_count=3)
    prompt = (
        f'【今回のモード: standard (記事 {cnt} 件)】\n'
        'phase は「拡散 / ピーク / 現在地 / 収束」のみ (発端は禁止)。timeline は最大3件。\n'
        'forecast は schema に存在しないため出力しない (full モードのみ)。\n\n'
        f'記事情報（{cnt}件）:\n{headlines}'
        + (f'\n{media_block}' if media_block else '')
    )
    try:
        schema = _build_story_schema('standard')
        result = _call_claude_tool(
            prompt, 'emit_topic_story', schema,
            max_tokens=1300, system=_SYSTEM_PROMPT,
        )
        if not result or not str(result.get('aiSummary') or '').strip():
            return None
        # T2026-0429-J: 再生成ロジックは廃止 (コスト抑制)。短い場合はメトリクスログで警告のみ。
        if _keypoint_too_short(result.get('keyPoint')):
            print(
                f'[WARN] keypoint_short mode=standard len='
                f'{len((result.get("keyPoint") or "").strip())}'
            )
        _emit_keypoint_metric('standard', result.get('keyPoint'), retried=False)
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
    T2026-0428-AL: 上位3記事の全文を取得し perspectives の比較根拠とする。
    T2026-0428-AJ: 共通プロンプトは _SYSTEM_PROMPT に集約 (cache_control 対象)。"""
    headlines, _ = _build_headlines(articles, limit=10)
    media_block = _build_media_comparison_block(articles, max_count=3)
    prompt = (
        f'【今回のモード: full (記事 {cnt} 件)】\n'
        'phase は「拡散 / ピーク / 現在地 / 収束」のみ (発端は禁止)。timeline は 3〜6 件出力。\n'
        'forecast は必ず出力する (確信度タグ必須)。\n\n'
        f'記事情報（{cnt}件・見出しと概要）:\n{headlines}'
        + (f'\n{media_block}' if media_block else '')
    )
    try:
        # T2026-0428-AL: 全文ブロック注入で prompt が ~6000 字伸びるため timeout を 60s に拡張
        # (旧 25s では Sonnet 4.6 + 1700 max_tokens の生成が間に合わず full mode が
        # まるごと失敗 → fallback で None になり aiGenerated=False のまま放置されていた)
        # measured: T2026-0429-P (2026-04-29) Sonnet 4.6 → Haiku 4.5 切替。
        # full mode コスト約 5 分の 1 ($3/MTok in → $0.80/MTok in、$15/MTok out → $4/MTok out)。
        # 品質劣化は次サイクルの実測 (keyPoint 長分布 / aiSummary 長分布) で確認。
        # timeout=60s は据え置き (Haiku は速いので余裕あり、外れ値だけ拾う)。
        schema = _build_story_schema('full')
        result = _call_claude_tool(
            prompt, 'emit_topic_story', schema,
            max_tokens=1700, timeout=60, model='claude-haiku-4-5-20251001',
            system=_SYSTEM_PROMPT,
        )
        if not result or not str(result.get('aiSummary') or '').strip():
            return None
        # T2026-0429-J: 再生成ロジックは廃止 (コスト抑制)。短い場合はメトリクスログで警告のみ。
        if _keypoint_too_short(result.get('keyPoint')):
            print(
                f'[WARN] keypoint_short mode=full len='
                f'{len((result.get("keyPoint") or "").strip())}'
            )
        _emit_keypoint_metric('full', result.get('keyPoint'), retried=False)
        return _normalize_story_result(result, 'full')
    except Exception as e:
        print(f'generate_story (full) error: {e}')
        return None


# 旧 text-mode の長大なプロンプト & JSON 手動 parse コードは削除。
# Tool Use API + JSON Schema (`_build_story_schema`) で structured output を物理的に強制。
# malformed JSON の発生確率は 0 になり、`generate_story (full) error: Expecting ',' delimiter`
# 系の警告が消える (T39 の続き、JSON parse error なぜなぜ分析の対策実装)。


# ─────────────────────────────────────────────────────────────────────────────
# T2026-0429-B: ストーリー分岐判定 (semantic should_branch)
# 仕様: docs/rules/story-branching-policy.md §3.3 判定マトリクス
#   - 主役エンティティ (PERSON / ORG 上位2件) 重複あり × 因果連続あり → 継続 (False)
#   - 主役エンティティ重複なし → 分岐 (True)
#   - 主役重複あり × 因果連続なし × Jaccard < 0.25 → 分岐 (True)
#   - それ以外 → 現行ロジック (Jaccard 0.35 以上で継続)
# 数字 (velocityScore / 記事数) は判定に使わない。内容軸のみで判断。
# ─────────────────────────────────────────────────────────────────────────────

# 因果連続キーワード (順序ペア)。両方が両 story の title/keyPoint に含まれていれば
# 因果シーケンスありとみなす (例: 逮捕 → 起訴, 起訴 → 判決)。
_CAUSAL_SEQUENCES = (
    ('逮捕', '起訴'),
    ('起訴', '判決'),
    ('逮捕', '判決'),
    ('容疑', '起訴'),
    ('容疑', '逮捕'),
    ('申請', '受理'),
    ('受理', '可決'),
    ('提案', '可決'),
    ('発表', '発売'),
    ('発売', '不具合'),
    ('発売', 'リコール'),
    ('発表', '提供開始'),
    ('発表', '上場'),
    ('合意', '締結'),
    ('交渉', '合意'),
    ('交渉', '決裂'),
    ('提携', '統合'),
    ('発足', '解散'),
    ('辞任', '後任'),
    ('就任', '辞任'),
    ('提訴', '判決'),
    ('提訴', '和解'),
    ('告訴', '不起訴'),
    ('指名', '承認'),
    ('開始', '完了'),
    ('開始', '中止'),
    ('発令', '解除'),
)


def _extract_primary_entities(entities: list) -> set:
    """entities フィールド (proc_ai 側で保持しないため呼出側で渡す) から
    type=PERSON|ORG の上位2件を主役エンティティとして返す。

    Args:
        entities: [{'name': '〜', 'type': 'PERSON'|'ORG'|'EVENT'|'PRODUCT'|...}, ...]
                  または ['〜', '〜'] (旧形式・全部主役扱い・上位2件)

    Returns:
        主役名の set (大文字小文字・全半角は区別する。呼出側で正規化)。
    """
    if not entities:
        return set()
    primary: list = []
    for e in entities:
        if isinstance(e, dict):
            name = str(e.get('name') or '').strip()
            etype = str(e.get('type') or '').upper()
            if name and etype in ('PERSON', 'ORG', 'ORGANIZATION'):
                primary.append(name)
        elif isinstance(e, str):
            name = e.strip()
            if name:
                primary.append(name)
        if len(primary) >= 2:
            break
    return set(primary)


def _has_causal_sequence(text_a: str, text_b: str) -> bool:
    """2 つのテキスト (title + keyPoint 連結を想定) の間に因果シーケンスがあるか。
    どちらに前段キーワード, どちらに後段キーワードがあるかは問わない (順序対称で判定)。
    どちらかに両方の単語が含まれていてもよい (時系列ストーリー内の連続展開)。"""
    if not text_a and not text_b:
        return False
    a = str(text_a or '')
    b = str(text_b or '')
    for first, second in _CAUSAL_SEQUENCES:
        in_a = (first in a, second in a)
        in_b = (first in b, second in b)
        # どちらか片側に両単語 (例: 「容疑で逮捕→今後の起訴可否が焦点」が a 側に)
        if all(in_a) or all(in_b):
            return True
        # 片側に first, もう片側に second (典型的な「逮捕→起訴」連続)
        if in_a[0] and in_b[1]:
            return True
        if in_b[0] and in_a[1]:
            return True
    return False


def _jaccard_set(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    union = len(a | b)
    if union == 0:
        return 0.0
    return len(a & b) / union


def should_branch(parent: dict, candidate: dict) -> bool:
    """セマンティック分岐判定。

    Args:
        parent:     既存トピック側 dict。{'title': str, 'keyPoint': str,
                    'entities': [...], 'tokens': set or list (任意)}
        candidate:  新候補トピック側 dict。同上。

    Returns:
        True  = 別ストーリーとして分岐 (新トピック起点)
        False = 同ストーリー継続 (既存トピックにマージ / timeline 追加)

    判定マトリクス (story-branching-policy.md §3.3):
      ① 主役重複あり × 因果連続あり          → False (継続: 逮捕→起訴 等の同事件展開)
      ② 主役重複なし                          → True  (分岐: 別主役 = 別ストーリー)
      ③ 主役重複あり × 因果連続なし × Jacc<.25 → True  (分岐: 同人物の別事案)
      ④ その他                                → 現行ロジック (Jaccard >= 0.35 で継続)
    """
    if not parent or not candidate:
        return True  # 比較不能 → 安全側で別扱い

    p_primary = _extract_primary_entities(parent.get('entities') or [])
    c_primary = _extract_primary_entities(candidate.get('entities') or [])

    p_text = f"{parent.get('title', '')}\n{parent.get('keyPoint', '')}"
    c_text = f"{candidate.get('title', '')}\n{candidate.get('keyPoint', '')}"

    primary_overlap = bool(p_primary & c_primary) if (p_primary and c_primary) else False
    has_causal = _has_causal_sequence(p_text, c_text)

    # tokens がなければ呼出側用に簡易トークン化 (空白・記号で split)。
    p_tokens = set(parent.get('tokens') or [])
    c_tokens = set(candidate.get('tokens') or [])
    if not p_tokens:
        p_tokens = set(re.findall(r'[A-Za-z0-9]+|[぀-ゟ゠-ヿ一-鿿]+', p_text))
    if not c_tokens:
        c_tokens = set(re.findall(r'[A-Za-z0-9]+|[぀-ゟ゠-ヿ一-鿿]+', c_text))
    jacc = _jaccard_set(p_tokens, c_tokens)

    # ① 主役重複 + 因果連続 → 継続 (同事件の新展開)
    if primary_overlap and has_causal:
        return False
    # ② 主役重複なし → 分岐 (別主役 = 別ストーリー)
    if (p_primary or c_primary) and not primary_overlap:
        return True
    # ③ 主役重複あり / 因果連続なし / Jaccard 低 → 分岐 (同人物の別事案)
    if primary_overlap and (not has_causal) and jacc < 0.25:
        return True
    # ④ その他 → 現行ロジック (Jaccard 0.35 以上で継続)
    return jacc < 0.35


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
