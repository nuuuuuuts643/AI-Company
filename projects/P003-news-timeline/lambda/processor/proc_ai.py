"""Claude Haiku を使ったタイトル・ストーリー生成とフォールバック (抽出的生成)。"""
from __future__ import annotations  # PEP 563 — Python 3.9 でも `str | None` annotation を許容

import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from proc_config import ANTHROPIC_API_KEY
try:
    from article_fetcher import fetch_full_articles
except Exception as _imp_err:
    # article_fetcher は本機能専用 (T2026-0428-AL)。import 失敗時は機能を無効化し
    # 既存ルート (snippet ベース) で動かし続ける (落ちないことを優先)。
    print(f'[proc_ai] article_fetcher import 失敗 — 全文取得を無効化: {_imp_err}')
    fetch_full_articles = None

# Re-exports from split modules (T2026-0504-A) — maintain proc_ai.X compatibility for all callers.
from proc_genre import (
    _VALID_GENRE_SET, _GENRES_PROMPT,
    _GENRE_PERSPECTIVE_ACTORS, _GENRE_READER_PERSONAS, _GENRE_IMPACT_TARGETS,
    _GENRE_KEYPOINT_HINTS, _GENRE_KEYPOINT_AXES, _GENRE_KEYPOINT_EXAMPLES,
    _GENRE_TITLE_HINTS, _GENRE_AISUMMARY_CAUSAL_FRAMES,
    _validate_genres,
    _build_keypoint_genre_hint, _build_perspective_actor_hint,
    _build_outlook_actor_hint, _build_causal_outlook_hint,
    _build_aisummary_causal_hint,
)
from proc_prompts import _WORD_RULES, _STORY_PROMPT_RULES, _SYSTEM_PROMPT
from proc_formatter import (
    clean_headline, _format_pub_date, _build_headlines,
    _parse_story_json, _sanitize_timeline,
    _VALID_PHASES, _VALID_LEVELS, _VALID_STATUS_LABELS,
    _KEYPOINT_MIN_CHARS, _PERSPECTIVES_MIN_CHARS,
    _WATCHPOINTS_MIN_CHARS, _OUTLOOK_MIN_CHARS, _KEYPOINT_RETRY_MIN_CHARS,
    _keypoint_too_short, _emit_keypoint_metric,
    _build_story_schema, _sanitize_causal_chain, _normalize_story_result,
)

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


# ============================================================================
# T2026-0502-AY: Anthropic Batch API helpers (50% off list price・schedule cron 専用)
# ----------------------------------------------------------------------------
# 用途: schedule cron 起動分の processor 呼び出しを Batch API に振り替えてコスト 50%off。
#       fetcher_trigger 等の即時性が必要な経路は対象外 (realtime 維持)。
# 統合: env `USE_BATCH_API=true` 時のみ起動 (default false で既存挙動温存)。
# 仕様: https://docs.anthropic.com/en/api/messages-batches
#       - 24h SLA (実測 1h 程度が大半)
#       - 1 batch あたり最大 10,000 requests
#       - submit → batch_id 取得 → poll → 全件完了で results 取得
# Lambda 制約 (15min max) を踏まえ、submit と retrieve を別 invoke に分割する 2 段階フロー想定。
# 本ファイルでは API helper のみ実装。state 管理 (S3) と handler.py 側統合は別 PR で段階的に landing。
# ============================================================================

_CLAUDE_BATCH_URL = 'https://api.anthropic.com/v1/messages/batches'


def _call_claude_batch_submit(requests: list, timeout: int = 30) -> dict | None:
    """Anthropic Batch API に複数 request を一括 submit する。

    Args:
        requests: 各 request は `{custom_id, params}` 形式。`params` は messages.create
                  payload と同じスキーマ (model, max_tokens, messages, tools, system 等)。
                  custom_id は自分側で管理する一意 ID (例: 'topic_<topicId>_<task>')、
                  retrieve 時に結果を topic に紐付けるキーとして使う。
        timeout: HTTP timeout 秒。

    Returns:
        {'id': '<batch_id>', 'processing_status': 'in_progress', ...}
        失敗時 None。

    cost: list price の 50% (Batch API 規定)。submit 自体は数秒で完了。

    NOTE: fetcher_trigger や即時 UX が必要な経路では使わない。schedule cron の
          24h SLA 許容パスのみで使用すること。
    """
    if not ANTHROPIC_API_KEY:
        return None
    if not requests:
        return None
    body = json.dumps({'requests': requests}).encode('utf-8')
    headers = {
        'x-api-key': ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01',
        'anthropic-beta': 'message-batches-2024-09-24',
        'content-type': 'application/json',
    }
    try:
        req = urllib.request.Request(_CLAUDE_BATCH_URL, data=body, headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f'[batch_submit] HTTP {e.code}: {e.read()[:200] if hasattr(e, "read") else e}')
        return None
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        print(f'[batch_submit] network error: {type(e).__name__}: {e}')
        return None


def _call_claude_batch_status(batch_id: str, timeout: int = 30) -> dict | None:
    """Batch の処理状況を確認する。

    Args:
        batch_id: submit 時に返された batch ID

    Returns:
        {'id', 'processing_status', 'request_counts', 'results_url' (完了時のみ), ...}
        失敗時 None。
    processing_status: 'in_progress' / 'canceling' / 'ended' のいずれか。
                       'ended' なら results_url が設定され retrieve 可能。
    """
    if not ANTHROPIC_API_KEY:
        return None
    if not batch_id:
        return None
    url = f'{_CLAUDE_BATCH_URL}/{batch_id}'
    headers = {
        'x-api-key': ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01',
        'anthropic-beta': 'message-batches-2024-09-24',
    }
    try:
        req = urllib.request.Request(url, headers=headers, method='GET')
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f'[batch_status] HTTP {e.code} for {batch_id[:16]}...')
        return None
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        print(f'[batch_status] network error: {type(e).__name__}: {e}')
        return None


def _call_claude_batch_results(batch_id: str, timeout: int = 60) -> list | None:
    """Batch の結果を JSONL として取得し、各 request の結果 dict のリストを返す。

    Args:
        batch_id: 完了した batch の ID (processing_status='ended' であること)

    Returns:
        [{'custom_id', 'result': {'type': 'succeeded'|'errored', 'message': {...}}}]
        失敗時 None。

    各 result entry の `result.type` は 'succeeded' / 'errored' / 'canceled' / 'expired'。
    succeeded 時のみ result.message.content[].input が tool_use の出力。
    """
    if not ANTHROPIC_API_KEY:
        return None
    if not batch_id:
        return None
    url = f'{_CLAUDE_BATCH_URL}/{batch_id}/results'
    headers = {
        'x-api-key': ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01',
        'anthropic-beta': 'message-batches-2024-09-24',
    }
    try:
        req = urllib.request.Request(url, headers=headers, method='GET')
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode('utf-8')
        # JSONL 形式: 1 行 1 JSON オブジェクト
        results = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f'[batch_results] malformed line: {e}')
                continue
        return results
    except urllib.error.HTTPError as e:
        print(f'[batch_results] HTTP {e.code} for {batch_id[:16]}...')
        return None
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        print(f'[batch_results] network error: {type(e).__name__}: {e}')
        return None


def build_batch_request(custom_id: str, prompt: str, tool_name: str, input_schema: dict,
                        max_tokens: int = 1500,
                        model: str = 'claude-haiku-4-5-20251001',
                        system: str | None = None) -> dict:
    """T2026-0502-AY: `_call_claude_tool` と同等の payload を batch request 形式で組み立てる。

    Returns: {'custom_id': ..., 'params': {model, max_tokens, tools, tool_choice, messages, system}}

    NOTE: handler.py 側で複数トピック分の request を build → batch submit する設計。
          batch retrieve 後は params 構造が同じなので _call_claude_tool 同等に
          `result.message.content[*].input` から tool 出力を取り出せる。
    """
    params = {
        'model': model,
        'max_tokens': max_tokens,
        'tools': [{
            'name': tool_name,
            'description': '構造化された分析結果を出力する',
            'input_schema': input_schema,
        }],
        'tool_choice': {'type': 'tool', 'name': tool_name},
        'messages': [{'role': 'user', 'content': prompt}],
    }
    if system:
        params['system'] = [{
            'type': 'text',
            'text': system,
            'cache_control': {'type': 'ephemeral'},
        }]
    return {'custom_id': custom_id, 'params': params}


# ============================================================================
# realtime path (T2026-0502-AY 以前から存在・既存挙動温存)
# ============================================================================
def _call_claude_tool(prompt: str | list, tool_name: str, input_schema: dict,
                       max_tokens: int = 1500, timeout: int = 25,
                       model: str = 'claude-haiku-4-5-20251001',
                       system: str | None = None) -> dict | None:
    """Claude Tool Use API で structured output を取得。
    JSON Schema で出力形式を強制するため malformed JSON は物理的に発生しない。

    T2026-0428-AJ: prompt caching 対応。`system` を渡すと cache_control: ephemeral 付きで
    送信し、固定の共通プロンプトをキャッシュ再利用する (Haiku 2048 / Sonnet 1024 tokens 必要)。
    Returns: tool_use.input (dict) / 失敗時 None。
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


def generate_title(articles, genre: str | None = None):
    """Claude Haiku でトピックタイトルを生成。

    Args:
        articles: 元記事リスト (title, description, pubDate を見る)。
        genre:    既知ジャンル ('政治' / 'ビジネス' 等)。プロンプト内に角度ヒントとして
                  注入する。None の場合は『総合』のヒントを使う。将来ジャンル別の
                  完全分岐に拡張するための引数 (T2026-0501-C, PO 指示)。
    """
    if not ANTHROPIC_API_KEY:
        return None
    headlines = '\n'.join(clean_headline(a.get('title', '')) for a in articles[:8])
    genre_hint = _GENRE_TITLE_HINTS.get(genre or '', _GENRE_TITLE_HINTS['総合'])
    prompt = (
        '以下はニュース記事の見出しです。\n'
        'これらが共通して報じているトピックを、読者が「**続きを読みたい**」と感じる魅力的な日本語タイトルにしてください。\n\n'
        '【最重要: 角度と緊張感を加える】\n'
        '事実を正確に伝えつつ、「何が引っかかるのか」「なぜ今動いたのか」を1フレーズで表現する。\n'
        '安全な要約ではなく、ニュースの「角度」(intrigue / tension / hook) を出す。\n'
        '- 数字があれば必ず入れる(GDP、株価、票差、件数、年限 等)\n'
        '- 対立軸・予想とのギャップ・連鎖反応・電撃性・矛盾 を見出しに織り込む\n'
        '- 「——」「、」で前段(事実)+後段(意味/含意)の二段構造にすると惹きが出る\n'
        f'- ジャンル別の切り口ヒント【{genre or "総合"}】: {genre_hint}\n\n'
        '【⚖ 正確性・リーガル制約 (絶対遵守)】\n'
        '- タイトルは記事に書かれた事実のみを根拠にする。記事に書かれていないことを推測で書かない\n'
        '- 名誉毀損になる断定は禁止: 「〜が不正」「〜は詐欺」「〜が虚偽」「〜が違法」\n'
        '  → 司法判断や当局発表が記事内に明示されている場合のみ「〜の疑いで送検」「〜と発表」等の引用形式で記述\n'
        '- 個人/企業の人格・能力を貶める表現は禁止: 「無能」「破綻寸前」「失墜」等の主観評価\n'
        '- 「煽り」と「角度」は別物: 角度=事実から自然に出る含意 / 煽り=事実を超えた断定\n\n'
        '【❌ 禁止: 平坦な要約】\n'
        '- 末尾が「〜について」「〜が発表」「〜を決定」「〜まとめ」「〜の動き」で終わるタイトル\n'
        '- 「〇〇が△△した」だけで終わる起承転結なしの中立タイトル\n'
        '- 商品名/組織名/事件名だけ並べた告知文(「○○、新製品発表」レベルは弱い)\n'
        '- 「速報」「続報」「最新」など時事マーカーで誤魔化す\n\n'
        '【✅ 改善例(平坦→惹きあり、いずれも事実ベース)】\n'
        '  ❌「米国GDPが発表される」\n'
        '  ✅「米GDP、予想割れ2.0%——市場の利下げ観測が一気に動く」\n'
        '  ❌「政府が方針を決定」\n'
        '  ✅「政府、○○を電撃決定——業界に反発の声」\n'
        '  ❌「イラン・トランプ政権の対立をめぐる最新の動き」\n'
        '  ✅「核合意修復で対立する米イラン、パキスタン仲介の行方」\n'
        '  ❌「プラスチック危機をめぐる最新の動きまとめ」\n'
        '  ✅「プラスチック汚染削減条約、主要国の対立で交渉難航」\n'
        '  ❌「ソニーREON POCKET PRO Plus わかりやすく解説」\n'
        '  ✅「ソニーの首掛け冷暖房新型——猛暑対策市場で先手」\n'
        '  ❌「安保3文書の改定内容と論点をわかりやすく解説」\n'
        '  ✅「安保3文書改定、GDP比2%目標と反撃能力で割れる与野党」\n\n'
        '【その他ルール】\n'
        '- 20〜35文字。短く力強く、20字台前半を目指す\n'
        '- 必ず「主語(誰/何が)」+「動詞 or 状態」を含める。曖昧な締めは禁止\n'
        '- 記事タイトルをそのままコピーしない(抽象化・統合する)\n'
        '- メディア名(毎日新聞、NHK等)は絶対に含めない\n'
        '- 固有名詞・核心キーワードを必ず含める\n'
        '- 説明文・かぎかっこ不要。タイトルのみ1行で出力\n\n'
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


def generate_story(articles, article_count: int | None = None, genre: str | None = None):
    """記事数に応じた段階的ストーリー分析を生成。

    - 1〜2件 / storyTimeline ≤ 2ステップ相当: シンプルな1段落要約のみ
    - 3〜5件: 概要 + なぜ広がったか + 短いタイムライン（2〜3件）
    - 6件以上: フル4セクション + 因果タイムライン（最大6件）

    Args:
        articles: 元記事リスト
        article_count: 件数 (省略時 len(articles))
        genre: 既知ジャンル (再処理時)。perspectives アクター指定に使われる。
               T2026-0501-C-2: PO 指示で追加。trial: ジャンル単位で視点ホルダー切替。

    Returns:
        dict: {"aiSummary", "spreadReason", "forecast", "timeline", "phase", "summaryMode"}
              summaryMode: "minimal" | "standard" | "full"
        または None（API未設定・エラー時）
    """
    if not ANTHROPIC_API_KEY:
        return None

    cnt = article_count if article_count is not None else len(articles)

    # T2026-0503-UX-WATCHPOINTS-FILL / T2026-0503-UX-PERSPECTIVES-FILL (2026-05-03):
    # 閾値を cnt<=2 → cnt<=1 に緩和。cnt=2 (aiGenerated の約49%) を standard mode に昇格。
    # standard mode では watchPoints/perspectives が schema required → 充填率を 0%/14% から引き上げ。
    if cnt <= 1:
        return _generate_story_minimal(articles, genre=genre)
    elif cnt <= 5:
        return _generate_story_standard(articles, cnt, genre=genre)
    else:
        return _generate_story_full(articles, cnt, genre=genre)


# T2026-0430-A (2026-04-30): _retry_short_keypoint を新アーキテクチャで再導入。
#
# 経緯: T2026-0429-J で「コスト抑制のため retry 撤去」したが、本番 SLI では keyPoint ≥100 字
# の充填率が 2.2% (2/92) のまま停滞 (2026-04-30 18:05 JST 観測)。プロンプト強化のみでは
# Tool Use API が「タイトル風 30〜40 字」「空文字」を返し続けるパターンを抑制できなかった。
#
# 新アーキ:
#   1) 初回 keyPoint が 100 字未満なら 1 回だけ再生成 (合計 2 回まで)。
#   2) 再生成プロンプトは「前回が短すぎたので最低 100 字以上、具体数字・固有名詞を含めて拡張」を明示。
#   3) keyPoint だけ生成する縮小スキーマ (max_tokens=400) でコストを最小化。
#   4) 再生成も短ければ "SHORT_FALLBACK" フラグを立てて original または retry の長い方を保存
#      (捨てない・空にしない)。
#   5) keyPointLength / keyPointRetried / keyPointFallback を DynamoDB に記録。
#   6) [KP_QUALITY] プレフィックスで CloudWatch Logs に出力し、後で集計・分析できるようにする。
#
# コスト試算: pendingAI=True なトピックは 1 サイクル ~30〜50 件、内 ~98% が短文
# → +50 retry call/サイクル × 2 サイクル/日 = ~100 retry/日。Haiku 4.5 の retry は
# system prompt cache hit + max_tokens=400 で 1 call ~$0.001 → +$0.10/日 ≒ +$3/月 で許容範囲。
def _retry_short_keypoint(articles: list, cnt: int, mode: str,
                          original_keypoint: str,
                          ai_summary: str | None = None) -> str | None:
    """T2026-0430-A: keyPoint が 100 字未満だった場合に 1 回だけ再生成する。

    元の keyPoint を渡し、「短すぎたので最低 100 字以上で具体的な数字・固有名詞を含めて拡張」
    と指示する。retry 専用の縮小スキーマ (keyPoint のみ) で max_tokens を抑え、
    system prompt は同一文字列を渡すことで cache hit を維持する (Haiku 2048 tokens 必要)。

    T2026-0503-UX-NO-KEYPOINT-23: ai_summary を追加コンテキストとして渡せるように拡張。
    original_keypoint が空文字の場合、aiSummary をヒントに keyPoint を生成させる。

    Returns:
        新しい keyPoint (str) — 失敗時は None。
    """
    headlines, _ = _build_headlines(articles, limit=5)
    original_len = len((original_keypoint or '').strip())
    summary_block = f'【aiSummary (参考・keyPoint 生成のヒントに使うこと)】\n{ai_summary}\n\n' if ai_summary else ''
    if original_len == 0:
        prompt = (
            '【keyPoint 初回生成リクエスト (T2026-0503-UX)】\n'
            'このトピックの keyPoint が未生成のため、100 字以上で生成してください。\n'
            '「何が起きたか」「なぜ重要か」「構造的背景」の3点を具体的な数字・固有名詞を用いて書く。\n'
            '一般論・抽象論・「〜が注目される」のような曖昧表現は禁止。\n'
            f'モード: {mode} (記事 {cnt} 件)。\n'
            f'{summary_block}'
            f'【記事情報 ({cnt} 件)】\n{headlines}\n'
        )
    else:
        prompt = (
            '【keyPoint 再生成リクエスト (T2026-0430-A)】\n'
            f'前回の keyPoint は {original_len} 字と短すぎました (基準: 100 字以上)。\n'
            '同じトピックに対し、最低 100 字以上で、**具体的な数字・固有名詞・変化**を含む内容に拡張してください。\n'
            '一般論・抽象論・「〜が注目される」「動向に注目」のような曖昧表現は禁止。\n'
            f'モード: {mode} (記事 {cnt} 件)。記事 1 件 = 初動フェーズ 3 要素 / 2 件以上 = 変化フェーズ 4 文構成。\n'
            f'【元の (短すぎた) keyPoint】\n{original_keypoint}\n\n'
            f'{summary_block}'
            f'【記事情報 ({cnt} 件)】\n{headlines}\n'
        )
    # T2026-0501-D (2026-05-01): retry schema を `minLength: 60` で物理ガード化。
    # 旧設計 (minLength: 0) では Tool Use API のスキーマ強制が効かず、retry でも
    # 10〜30 字の短文が返り続けて SHORT_FALLBACK で永続化される構造的バグがあった。
    # 本番 SLI で keyPoint>=50字 充填率 38.6% (228 件中 88 件) で停滞 (2026-05-01 朝)。
    # 60 字 = SLI 警告閾値 (50 字) + 10 字バッファ。outlook (_OUTLOOK_MIN_CHARS=60)、
    # perspectives (80)、watchPoints (80) と同じ物理ガード方式。
    # メイン schema の minLength=0 は PO 指示「書けない場合は生成しない」物理化のため維持
    # (test_keypoint_retry.SchemaMinLengthTest で landing 検証済)。retry は
    # 「すでに不十分と判断した topic に対する強化リクエスト」のため軟化文言は不要。
    schema = {
        'type': 'object',
        'properties': {
            'keyPoint': {
                'type': 'string',
                'minLength': _KEYPOINT_RETRY_MIN_CHARS,
                'description': f'トピックの注目ポイントを {_KEYPOINT_MIN_CHARS} 字以上で具体的に書く。'
                               f'最低 {_KEYPOINT_RETRY_MIN_CHARS} 字必須 (物理ガード)。'
                               '固有名詞・数字・変化を含めること。一般論・抽象論・'
                               '「〜が注目される」「動向に注目」のような曖昧表現は禁止。',
            },
        },
        'required': ['keyPoint'],
    }
    try:
        result = _call_claude_tool(
            prompt, 'emit_keypoint_retry', schema,
            max_tokens=400, system=_SYSTEM_PROMPT,
        )
        if not result:
            return None
        new_kp = str(result.get('keyPoint') or '').strip()
        return new_kp or None
    except Exception as e:
        print(f'[KP_QUALITY] retry_error mode={mode} err={e}')
        return None


def _process_keypoint_quality(result: dict, articles: list, cnt: int,
                              mode: str, topic_id: str | None = None) -> None:
    """T2026-0430-A: keyPoint 長さ検証 + 1 回 retry + SHORT_FALLBACK フラグ + KP_QUALITY ログ。

    result を in-place で更新する:
      - 必要なら result['keyPoint'] を retry 結果に差し替え
      - result['_kpRetried']  : bool — retry を呼んだか
      - result['_kpFallback'] : bool — retry 後も < 100 字 (フォールバック保存) か
      - result['_kpLength']   : int  — 最終的に保存される keyPoint の文字数

    CloudWatch には [KP_QUALITY] プレフィックスで 1 行出力 (後で集計分析できる固定フォーマット)。
    既存の [METRIC] keypoint_len も維持する (互換性)。
    """
    original_kp = str(result.get('keyPoint') or '').strip()
    original_len = len(original_kp)
    retried = False
    fallback = False

    if _keypoint_too_short(original_kp):
        retried = True
        ai_summary_ctx = str(result.get('aiSummary') or '').strip() or None
        new_kp = _retry_short_keypoint(articles, cnt, mode, original_kp, ai_summary=ai_summary_ctx)
        new_len = len((new_kp or '').strip())
        if new_kp and not _keypoint_too_short(new_kp):
            # retry 成功 (>= 100 字)
            result['keyPoint'] = new_kp
        else:
            # retry も短い → fallback。長い方を残す (空文字より短文の方が情報量がある)。
            if new_kp and new_len > original_len:
                result['keyPoint'] = new_kp
            fallback = True

    final_kp = str(result.get('keyPoint') or '').strip()

    # T2026-0503-UX-NO-KEYPOINT-23: 両方空のとき aiSummary を keyPoint 代用として保存。
    # Claude が「何が変わったのか不明確」で空を返し続ける topic が 23.1% 滞留していた。
    # aiSummary は aiGenerated フロー上必ず非空なので、空 keyPoint を "準備中" から救済する。
    if not final_kp:
        ai_summary = str(result.get('aiSummary') or '').strip()
        if ai_summary:
            result['keyPoint'] = ai_summary
            final_kp = ai_summary
            print(f'[KP_QUALITY] aiSummary fallback used topic={topic_id[:8] + "..." if topic_id else "n/a"} len={len(final_kp)}')

    final_len = len(final_kp)
    result['_kpRetried']  = retried
    result['_kpFallback'] = fallback
    result['_kpLength']   = final_len

    # KP_QUALITY ログ (CloudWatch 集計用・固定フォーマット)
    tid_short = (topic_id[:8] + '...') if topic_id else 'n/a'
    print(
        f'[KP_QUALITY] mode={mode} cnt={cnt} topic={tid_short} '
        f'orig_len={original_len} final_len={final_len} '
        f'retried={1 if retried else 0} fallback={1 if fallback else 0} '
        f'ge100={1 if final_len >= 100 else 0}'
    )
    # 互換: 既存の [METRIC] keypoint_len も残す
    _emit_keypoint_metric(mode, result.get('keyPoint'), retried=retried)


def _generate_story_minimal(articles: list, genre: str | None = None) -> dict | None:
    """1〜2件: シンプルな1段落要約のみ生成（APIコスト最小）。Tool Use で structured output 強制。
    T2026-0428-AJ: 共通プロンプトは _SYSTEM_PROMPT に集約 (cache_control 対象)。
    T2026-0430-G (2026-04-30): cnt>=2 のときは perspectives も生成 (2 媒体の論調差)。
    watchPoints/timeline/statusLabel は引き続き minimal mode では出さない。
    """
    headlines, cnt = _build_headlines(articles, limit=2)
    has_perspectives = cnt >= 2
    # T2026-0430-G: cnt>=2 のときのみ媒体本文を取得 (上位 2 件)。
    media_block = _build_media_comparison_block(articles, max_count=2) if has_perspectives else ''
    # T-keypoint-prompt (2026-04-30): keyPoint のフェーズ分岐を明示。
    # 記事 1 件 = 初動フェーズ (3 要素) / 2 件以上 = 変化フェーズ (4 文構成)。
    keypoint_phase_hint = (
        '【keyPoint のフェーズ判定】記事 1 件 = 初動フェーズ → ①何が起きたか ②なぜ重要か ③なぜこうなったか・構造的背景 の 3 要素で書く。\n'
        if cnt <= 1 else
        '【keyPoint のフェーズ判定】記事 2 件 = 変化フェーズ → 4 文構成（1文目=今回の変化 / 2文目=以前の状況 / 3文目=追加情報 / 4文目=意味・今後）。1 文目で「何が変わったか」を必ず明示する。\n'
    )
    schema_hint = (
        'phase / timeline / statusLabel / watchPoints は schema 上存在しないため出力しない。\n'
        'aiSummary・keyPoint・outlook・perspectives・topicTitle・latestUpdateHeadline・isCoherent・topicLevel・genres のみを schema に従って出力する。\n'
        '【perspectives】2 媒体の見解を「[メディア名] は〜」の構文で並列列挙 (**80 字以上 必須**)。各社が扱う論点・取り上げ方の重心を 1 文ずつ書く。論調差が薄くても短文 fallback (「概ね同様」だけで終わる) は禁止。差が薄ければ「両社とも〜の事実関係を中心に報じている / 各社の論調差は限定的」のように具体的な共通点と差の大きさまで書く。1 社だけ詳述は禁止。\n'
        if has_perspectives else
        'phase / timeline / perspectives / statusLabel / watchPoints は schema 上存在しないため出力しない。\n'
        'aiSummary・keyPoint・outlook・topicTitle・latestUpdateHeadline・isCoherent・topicLevel・genres のみを schema に従って出力する。\n'
    )
    perspective_actor_hint = _build_perspective_actor_hint(genre) if has_perspectives else ''
    # T2026-0501-G: outlook は minimal mode (cnt=1 でも) 必須フィールドのため
    # 全ケースで読者ペルソナ + 視点アクター hint を注入する。
    outlook_actor_hint = _build_outlook_actor_hint(genre)
    # T2026-0501-OL2: 波及先マッピング + 因果連鎖深度 + causalChain 必須化 hint。
    causal_outlook_hint = _build_causal_outlook_hint(genre)
    # T2026-0501-KPG: ジャンル別 keyPoint 角度ヒント (健康/テックの kp≥100% 低迷対策)。
    keypoint_genre_hint = _build_keypoint_genre_hint(genre)
    # T2026-0502-AZ: Split into cached static block (pure genre hints) + dynamic block.
    # keypoint_genre_hint / outlook_actor_hint / causal_outlook_hint depend only on genre → cacheable.
    # schema_hint / keypoint_phase_hint / perspective_actor_hint depend on cnt → dynamic block.
    _static_hints = keypoint_genre_hint + outlook_actor_hint + causal_outlook_hint
    _dynamic_part = (
        f'【今回のモード: minimal (記事 {cnt} 件)】\n'
        + schema_hint
        + keypoint_phase_hint
        + perspective_actor_hint
        + '\n'
        + f'記事情報（{cnt}件）:\n{headlines}'
        + (f'\n{media_block}' if media_block else '')
    )
    prompt = [
        {'type': 'text', 'text': _static_hints, 'cache_control': {'type': 'ephemeral'}},
        {'type': 'text', 'text': _dynamic_part},
    ]
    try:
        schema = _build_story_schema('minimal', cnt=cnt)
        # perspectives 生成時は出力 token を 600→900 に増量 (perspectives 60+ 字 + 余裕)
        max_tokens = 900 if has_perspectives else 600
        result = _call_claude_tool(
            prompt, 'emit_topic_story', schema,
            max_tokens=max_tokens, system=_SYSTEM_PROMPT,
        )
        if not result or not str(result.get('aiSummary') or '').strip():
            return None
        # T2026-0430-A: 100 字未満なら 1 回 retry + KP_QUALITY ログ + SHORT_FALLBACK フラグ。
        _process_keypoint_quality(result, articles, cnt, 'minimal')
        return _normalize_story_result(result, 'minimal')
    except Exception as e:
        print(f'generate_story (minimal) error: {e}')
        return None


def _generate_story_standard(articles: list, cnt: int, genre: str | None = None) -> dict | None:
    """2〜5件: Tool Use で structured output 強制 (旧 JSON 構文エラー撲滅)。
    T2026-0503-UX-WATCHPOINTS/PERSPECTIVES-FILL: cnt=2 も standard に昇格 (旧: 3〜5件)。
    T2026-0428-AL: 上位3記事の全文を取得し perspectives の比較根拠とする。
    T2026-0428-AJ: 共通プロンプトは _SYSTEM_PROMPT に集約 (cache_control 対象)。"""
    headlines, _ = _build_headlines(articles, limit=5)
    media_block = _build_media_comparison_block(articles, max_count=3)
    perspective_actor_hint = _build_perspective_actor_hint(genre)
    outlook_actor_hint = _build_outlook_actor_hint(genre)
    # T2026-0501-OL2: 波及先マッピング + 因果連鎖深度 + causalChain 必須化 hint。
    causal_outlook_hint = _build_causal_outlook_hint(genre)
    # T2026-0501-KPG: ジャンル別 keyPoint 角度ヒント。
    keypoint_genre_hint = _build_keypoint_genre_hint(genre)
    # T2026-0502-AE: aiSummary に「なぜ今/引き金/利害」(causal chain) 強制注入。
    aisummary_causal_hint = _build_aisummary_causal_hint(genre)
    # T2026-0502-AZ: Split into cached static block (genre hints) + dynamic block (article data).
    # Same-genre calls share the cached prefix → Haiku/Sonnet cache hit from 2nd topic onward.
    # cnt is removed from the static block so different article counts reuse the same cache entry.
    _static_hints = (
        '【今回のモード: standard】\n'
        'phase は「拡散 / ピーク / 現在地 / 収束」のみ (発端は禁止)。timeline は最大3件。\n'
        'forecast は schema に存在しないため出力しない (full モードのみ)。\n'
        # T-keypoint-prompt (2026-04-30): 記事 2 件以上は変化フェーズ。
        # T2026-0503-C: 「書けない場合は空文字」→「一般論より短い具体論のほうがよい」に転換。
        '【keyPoint のフェーズ判定】記事 2 件以上 = 変化フェーズ → 4 文構成（1文目=今回の変化 / 2文目=以前の状況 / 3文目=追加情報 / 4文目=意味・今後）。1 文目で「何が変わったか」を必ず明示する。一般論より短い具体論のほうがよい。事実が1つでもあれば書く。\n\n'
        + aisummary_causal_hint
        + keypoint_genre_hint
        + perspective_actor_hint
        + outlook_actor_hint
        + causal_outlook_hint
    )
    prompt = [
        {'type': 'text', 'text': _static_hints, 'cache_control': {'type': 'ephemeral'}},
        {'type': 'text', 'text': f'記事情報（{cnt}件）:\n{headlines}' + (f'\n{media_block}' if media_block else '')},
    ]
    try:
        schema = _build_story_schema('standard')
        result = _call_claude_tool(
            prompt, 'emit_topic_story', schema,
            max_tokens=1300, system=_SYSTEM_PROMPT,
        )
        if not result or not str(result.get('aiSummary') or '').strip():
            return None
        # T2026-0430-A: 100 字未満なら 1 回 retry + KP_QUALITY ログ + SHORT_FALLBACK フラグ。
        _process_keypoint_quality(result, articles, cnt, 'standard')
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


def _generate_story_full(articles: list, cnt: int, genre: str | None = None) -> dict | None:
    """6件以上: フル7セクション + 因果タイムライン（最大6件）。Tool Use で structured output 強制。
    記事数が多い大型トピック向け。
    T-haiku-full (2026-04-30): Sonnet 4.6 → Haiku 4.5 に統一しコスト 91% 削減。
    Haiku は Sonnet より指示追従が弱いため、user prompt 先頭に「最重要・必ず守る」ブロックを
    入れて keyPoint/perspectives/outlook の品質を担保する。
    T2026-0428-AL: 上位3記事の全文を取得し perspectives の比較根拠とする。
    T2026-0428-AJ: 共通プロンプトは _SYSTEM_PROMPT に集約 (cache_control 対象)。"""
    headlines, _ = _build_headlines(articles, limit=10)
    media_block = _build_media_comparison_block(articles, max_count=3)
    perspective_actor_hint = _build_perspective_actor_hint(genre)
    outlook_actor_hint = _build_outlook_actor_hint(genre)
    # T2026-0501-OL2: 波及先マッピング + 因果連鎖深度 + causalChain 必須化 hint。
    causal_outlook_hint = _build_causal_outlook_hint(genre)
    # T2026-0501-KPG: ジャンル別 keyPoint 角度ヒント。
    keypoint_genre_hint = _build_keypoint_genre_hint(genre)
    # T2026-0502-AE: aiSummary に「なぜ今/引き金/利害」(causal chain) 強制注入。
    aisummary_causal_hint = _build_aisummary_causal_hint(genre)
    # T2026-0502-AZ: Split into cached static block (genre hints) + dynamic block (article data).
    # Same-genre calls share the cached prefix → Haiku/Sonnet cache hit from 2nd topic onward.
    # cnt is removed from the static block so different article counts reuse the same cache entry.
    _static_hints = (
        '【最重要: 必ず守ること】\n'
        '1. keyPoint は必ずフェーズ判定に従って書く（記事1件=初動3要素 / 2件以上=変化4文構成）。\n'
        '2. 一般論・抽象論・「〜が注目される」「〜に影響を与える」「動向に注目」は禁止。\n'
        '3. 具体的な固有名詞・数字・変化を必ず含める。\n'
        '4. 一般論より短い具体論のほうがよい。事実が1つでもあれば書く。\n'
        '5. perspectives は 2〜3 アクターを等しく扱う (下記アクター指定参照)。1 アクターだけ詳述は禁止。論調差が薄ければ「概ね同様」と書く。\n'
        '6. outlook / forecast の文末に必ず [確信度:高] / [確信度:中] / [確信度:低] のいずれかを付ける。\n'
        '7. ★ outlook は読者ペルソナ視点で「もし〜なら N週/Nヶ月以内に □□となる」の条件付き仮説で書く (下記 outlook 生成方針参照)。当たり障りなく観測する書き方は禁止。\n'
        '8. ★ causalChain は outlook の根拠として 3〜6 ステップで必ず出力 (下記 OL2 ルール参照)。1 次効果で止まらず 2 次/3 次連鎖まで踏み込む。\n'
        '9. ★ aiSummary は 150 字 2 文構成 — 国際/政治/ビジネス等は 2 文目に「なぜ今/引き金/利害」を必ず具体名詞で含める (下記 AE ルール参照)。「対立深刻化」「影響を与える」等の抽象表現は禁止。\n\n'
        '【今回のモード: full】\n'
        'phase は「拡散 / ピーク / 現在地 / 収束」のみ (発端は禁止)。timeline は 3〜6 件出力。\n'
        'forecast は必ず出力する (確信度タグ必須)。\n'
        # T-keypoint-prompt (2026-04-30): 記事 2 件以上は変化フェーズ。
        # T2026-0503-C: 「書けない場合は空文字」→「一般論より短い具体論のほうがよい」に転換。
        '【keyPoint のフェーズ判定】記事 2 件以上 = 変化フェーズ → 4 文構成（1文目=今回の変化 / 2文目=以前の状況 / 3文目=追加情報 / 4文目=意味・今後）。1 文目で「何が変わったか」を必ず明示する。一般論より短い具体論のほうがよい。事実が1つでもあれば書く。\n\n'
        + aisummary_causal_hint
        + keypoint_genre_hint
        + perspective_actor_hint
        + outlook_actor_hint
        + causal_outlook_hint
    )
    prompt = [
        {'type': 'text', 'text': _static_hints, 'cache_control': {'type': 'ephemeral'}},
        {'type': 'text', 'text': f'記事情報（{cnt}件・見出しと概要）:\n{headlines}' + (f'\n{media_block}' if media_block else '')},
    ]
    try:
        # T2026-0428-AL: 全文ブロック注入で prompt が ~6000 字伸びるため timeout を 60s に拡張。
        # T-haiku-full (2026-04-30): Haiku 4.5 に切替後も media_block で prompt が長いため 60s 維持。
        schema = _build_story_schema('full')
        result = _call_claude_tool(
            prompt, 'emit_topic_story', schema,
            max_tokens=1700, timeout=60,
            system=_SYSTEM_PROMPT,
        )
        if not result or not str(result.get('aiSummary') or '').strip():
            return None
        # T2026-0430-A: 100 字未満なら 1 回 retry + KP_QUALITY ログ + SHORT_FALLBACK フラグ。
        _process_keypoint_quality(result, articles, cnt, 'full')
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


def _extract_deadline_offset_days(outlook: str) -> int | None:
    """T2026-0502-BC: outlook 文中の期限フレーズから「予想立て時刻からの日数」を推定する。

    対応パターン (proc_ai.py の outlook プロンプトで「期限を必ず名指し」と指示している語彙):
      - 今週中 / 今週 / 週末まで → 7 日
      - 来週中 / 来週 / 来週末 → 14 日
      - 今月中 / 今月 / 月末 → 30 日
      - 来月 / 来月中 → 60 日
      - 3 ヶ月 / 三ヶ月 / 3ヶ月以内 → 90 日
      - 半年 / 6 ヶ月 / 六ヶ月 → 180 日
      - 年内 → 365 日 (大雑把)
      - 数値マッチ: "N 日以内" / "N 週間以内" / "N ヶ月以内"

    Returns:
        int | None: 予想立て時刻からの日数 (offset)。期限フレーズなしなら None。

    None を返した場合、caller (`is_eligible_for_judgment`) は保守的フォールバック (7d) を使う。
    """
    if not outlook:
        return None
    s = str(outlook)

    # 数値パターン優先 (より具体的)
    import re
    m = re.search(r'(\d+)\s*日(?:以内|間|後)', s)
    if m:
        return int(m.group(1))
    m = re.search(r'(\d+)\s*週間?(?:以内|後)?', s)
    if m:
        return int(m.group(1)) * 7
    m = re.search(r'(\d+)\s*[ヶか]?月(?:以内|間|後)?', s)
    if m:
        return int(m.group(1)) * 30

    # キーワードマッチ
    # ★順序注意: 「来週」「来月」を「今週」「今月」より先に check (substring 衝突回避)
    if '来週' in s:
        return 14
    if '来月' in s:
        return 60
    if '今週' in s or '週末まで' in s:
        return 7
    if '今月' in s or '月末' in s:
        return 30
    if '三ヶ月' in s or '3ヶ月' in s or '半年' in s or '六ヶ月' in s or '6ヶ月' in s:
        if '半年' in s or '六ヶ月' in s or '6ヶ月' in s:
            return 180
        return 90
    if '年内' in s or '今年中' in s:
        return 365

    return None


def is_eligible_for_judgment(outlook: str, made_at_iso: str,
                             now_utc=None, fallback_days: int = 7) -> bool:
    """T2026-0502-BC: 予想 (outlook) の期限が到来しているか判定する。

    期限が到来していない場合は False を返し、handler.py 側で judge_prediction の
    Anthropic API 呼び出しを skip させる。これによりコスト無駄打ちを物理的に削減し、
    期限到来後の判定 signal を改善する (matched/partial/missed が 0 件問題の対処)。

    Args:
        outlook:    AI が立てた予想文 (期限フレーズを含む可能性)。
        made_at_iso: 予想立て時刻 (ISO8601・例: '2026-04-25T10:00:00+00:00')。
        now_utc:    判定基準時刻 (テスト用に注入可能・None なら現在時刻)。
        fallback_days: 期限フレーズが outlook にない場合の保守的閾値 (default 7d)。

    Returns:
        bool: 期限到来済 = True (judge 対象) / 期限未到来 = False (skip)。
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    try:
        made_at_dt = datetime.fromisoformat((made_at_iso or '').replace('Z', '+00:00'))
    except (ValueError, TypeError):
        # 不正な made_at は判定不能なので保守的に True (既存挙動温存)
        return True

    offset_days = _extract_deadline_offset_days(outlook)
    if offset_days is None:
        offset_days = fallback_days

    deadline = made_at_dt + timedelta(days=offset_days)
    return now_utc >= deadline


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


_CHAPTER_SYSTEM_PROMPT = """あなたはニュース分析の専門家です。
提供された新着記事を読み、トピックの最新チャプター（章）を生成してください。

【絶対ルール】
- summary: 事実のみ。意見・予想は一切入れない。箇条書き不可。1〜3文。
- commentary: なぜ重要か・何が変わるか・何に影響するかのAI解説。文中で関連トピックに言及する場合は [topicId:xxxx] 形式のプレースホルダーを使ってよい。
- prediction: 次に何が起きるか。「〜の可能性」「〜かもしれない」は禁止。断定形で書く。根拠を必ず示す。
- articleIds: 使用した記事URLのリスト（全て含める）。
- date: 新着記事の中で最も新しい記事の日付（YYYY-MM-DD形式）。
"""


def generate_chapter(topic_data: dict, new_articles: list) -> dict | None:
    """Step 6 S2: チャプター型ストーリーの新チャプターを生成する。

    topic_data: DynamoDB から取得したトピックメタ（background/keyPoint/chapters/topicTitle を使用）
    new_articles: lastChapterDate 以降の新着記事リスト（title/url/pubDate フィールドを持つ）
    Returns: 新チャプター dict または失敗時 None
    """
    if not new_articles:
        return None

    topic_title = topic_data.get('topicTitle') or topic_data.get('generatedTitle') or ''
    background = topic_data.get('background') or ''
    key_point = topic_data.get('keyPoint') or ''
    existing_chapters = topic_data.get('chapters') or []
    latest_chapter = existing_chapters[-1] if existing_chapters else None

    # 新着記事ブロック
    articles_block = '\n'.join(
        f'- [{a.get("pubDate", "")[:10]}] {a.get("title", "")} ({a.get("url", "")})'
        for a in new_articles
    )

    # 最新チャプターの文脈（あれば）
    prev_chapter_block = ''
    if latest_chapter:
        prev_chapter_block = f"""
【直前のチャプター（{latest_chapter.get('date', '')}）】
summary: {latest_chapter.get('summary', '')}
prediction: {latest_chapter.get('prediction', '')}
"""

    prompt = f"""トピック: {topic_title}

【背景・文脈】
{background}

【このトピックの最大の注目点】
{key_point}
{prev_chapter_block}
【新着記事】
{articles_block}

上記の新着記事を元に、このトピックの最新チャプターを生成してください。"""

    schema = {
        'type': 'object',
        'properties': {
            'date': {'type': 'string', 'description': '最新記事の日付 (YYYY-MM-DD)'},
            'summary': {'type': 'string', 'description': '事実のみ・1〜3文'},
            'commentary': {'type': 'string', 'description': 'AI解説・なぜ重要か'},
            'prediction': {'type': 'string', 'description': '断定形の予測・根拠付き'},
            'articleIds': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': '使用した記事のURL一覧',
            },
        },
        'required': ['date', 'summary', 'commentary', 'prediction', 'articleIds'],
    }

    result = _call_claude_tool(
        prompt=prompt,
        tool_name='generate_chapter',
        input_schema=schema,
        max_tokens=1200,
        system=_CHAPTER_SYSTEM_PROMPT,
    )
    if not result:
        print('[generate_chapter] Claude API 失敗: result=None')
        return None

    # 最低限のバリデーション
    for field in ('date', 'summary', 'commentary', 'prediction'):
        if not str(result.get(field) or '').strip():
            print(f'[generate_chapter] 必須フィールド欠落: {field}')
            return None

    return {
        'date': str(result.get('date', '')).strip()[:10],
        'summary': str(result.get('summary', '')).strip(),
        'commentary': str(result.get('commentary', '')).strip(),
        'prediction': str(result.get('prediction', '')).strip(),
        'articleIds': [str(u) for u in (result.get('articleIds') or []) if u],
    }


def log_skip_reason(tid: str, reason: str) -> None:
    """スキップ理由を統一フォーマットでログ出力する。

    handler.py の各スキップ箇所から呼ぶことで、CloudWatch Logs Insights で
    'filter @message like "[SKIP]"' として集計できるようになる。

    現時点では既存のスキップ条件の動作は変えない。可視化のみ。
    """
    print(f'[SKIP] {tid[:8]}... reason={reason}')
