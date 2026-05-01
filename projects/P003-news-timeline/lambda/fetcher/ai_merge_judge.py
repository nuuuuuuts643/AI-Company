"""ai_merge_judge.py — borderline トピックペアを Haiku に「同一事件か」と問う判定モジュール。

T2026-0501-H 設計方針 (2026-05-01 PO 指示):
  「混入 > 分裂」の害。マージ判定は保守的に。
  - エンティティ重複なし → 必ず別トピック (Jaccard 値に関わらず)
  - エンティティ重複あり + Jaccard >= 0.35 → マージ
  - エンティティ重複あり + 0.15 <= Jaccard < 0.35 → Haiku に同一事件か問う
  - 上記以外                                       → 別トピック
  - Haiku が「いいえ」or 判断不能                    → 別トピック (失敗時 failsafe)

  例:「関税引き上げ 米国」vs「関税引き上げ 日本」 = エンティティ重複なし → 別事件 (Jaccard 高くてもマージしない)

入力契約:
  judge_pairs(pairs)
    pairs: list of dict {
      'title_a': str, 'title_b': str,
      'entities_a': list[str], 'entities_b': list[str],
      'shared_entities': list[str],   # 呼び出し側で計算した重複エンティティ
    }
  戻り値: dict (title_a, title_b) -> bool   # ペアキーは sorted tuple

実装方針:
  - 1 run 内の borderline ペア候補を全部集めて 1 リクエストに batch 投入
  - in-memory cache (sorted titles) で同 run 内の重複質問を避ける
  - API key 未設定 / 失敗 / タイムアウト時は failsafe = "別トピック (False)"
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request


_CLAUDE_API_URL = 'https://api.anthropic.com/v1/messages'
_DEFAULT_MODEL = 'claude-haiku-4-5-20251001'
_RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}

# borderline 判定閾値 (Jaccard 0.15 < x < 0.35 を Haiku に投げる)
JACCARD_LOW = 0.15
JACCARD_HIGH = 0.35

# 1 リクエストに含める最大ペア数 (Haiku context は十分広いがレイテンシ抑制で 50)
_MAX_PAIRS_PER_REQUEST = 50


class AIMergeJudge:
    """Haiku に borderline ペアを batch で問う判定器。

    Lambda 1 run 内で再利用するインスタンス。`_cache` は in-memory dict で
    同一ペアの再質問を避ける (sorted tuple をキーにすることで対称性を保つ)。
    """

    def __init__(self, api_key: str, model: str = _DEFAULT_MODEL, timeout: int = 20):
        self.api_key = api_key or ''
        self.model = model
        self.timeout = timeout
        self._cache: dict[tuple[str, str], bool] = {}
        # 観測用カウンタ (governance worker で集計)
        self.calls = 0
        self.pairs_asked = 0
        self.pairs_yes = 0
        self.pairs_no = 0
        self.failures = 0

    @staticmethod
    def _key(a: str, b: str) -> tuple[str, str]:
        return (a, b) if a <= b else (b, a)

    @staticmethod
    def is_borderline(jaccard: float) -> bool:
        """Jaccard 値が borderline (Haiku に投げる範囲) かを返す。"""
        return JACCARD_LOW <= jaccard < JACCARD_HIGH

    def judge_pairs(self, pairs: list[dict]) -> dict[tuple[str, str], bool]:
        """ペアの list を受け取り、各ペアが「同一事件か (True/False)」の dict を返す。

        ペア dict は 'title_a' / 'title_b' / 'entities_a' / 'entities_b' / 'shared_entities' を含むこと。
        - cache hit はスキップ
        - API key 未設定 or 全失敗時は failsafe で False を返す
        """
        if not pairs:
            return {}
        # 重複・対称キーを除去
        normalized: list[dict] = []
        seen_keys: set = set()
        for p in pairs:
            a = (p.get('title_a') or '').strip()
            b = (p.get('title_b') or '').strip()
            if not a or not b or a == b:
                continue
            k = self._key(a, b)
            if k in seen_keys:
                continue
            seen_keys.add(k)
            normalized.append({
                'title_a': a, 'title_b': b,
                'entities_a': list(p.get('entities_a') or []),
                'entities_b': list(p.get('entities_b') or []),
                'shared_entities': list(p.get('shared_entities') or []),
                '_key': k,
            })

        result: dict[tuple[str, str], bool] = {}
        to_ask: list[dict] = []
        for p in normalized:
            k = p['_key']
            if k in self._cache:
                result[k] = self._cache[k]
            else:
                to_ask.append(p)

        if not to_ask:
            return result
        if not self.api_key:
            print(f'[ai_merge_judge] ANTHROPIC_API_KEY 未設定 → {len(to_ask)} ペアを skip (failsafe=False)')
            for p in to_ask:
                self._cache[p['_key']] = False
                result[p['_key']] = False
            return result

        for i in range(0, len(to_ask), _MAX_PAIRS_PER_REQUEST):
            chunk = to_ask[i:i + _MAX_PAIRS_PER_REQUEST]
            try:
                judgments = self._call_haiku(chunk)
            except Exception as e:
                print(f'[ai_merge_judge] batch 失敗 ({type(e).__name__}: {e}) → {len(chunk)} ペアを failsafe=False')
                self.failures += 1
                for p in chunk:
                    self._cache[p['_key']] = False
                    result[p['_key']] = False
                continue
            for p, same in zip(chunk, judgments):
                k = p['_key']
                self._cache[k] = bool(same)
                result[k] = bool(same)
                if same:
                    self.pairs_yes += 1
                else:
                    self.pairs_no += 1
            self.pairs_asked += len(chunk)

        return result

    def _call_haiku(self, pairs: list[dict]) -> list[bool]:
        """Tool Use API で構造化された yes/no 配列を得る。"""
        if not pairs:
            return []
        self.calls += 1

        def fmt_entities(es: list[str]) -> str:
            return '、'.join(es) if es else '(なし)'

        numbered = '\n'.join(
            (
                f'{i+1}. \n'
                f'   A: {p["title_a"]}\n'
                f'      [Aの主要エンティティ] {fmt_entities(p["entities_a"])}\n'
                f'   B: {p["title_b"]}\n'
                f'      [Bの主要エンティティ] {fmt_entities(p["entities_b"])}\n'
                f'   [共有エンティティ] {fmt_entities(p["shared_entities"])}'
            )
            for i, p in enumerate(pairs)
        )
        system = (
            'あなたはニュース編集者です。2 つの記事タイトル A と B が「同一の事件・出来事」を'
            '報じているかを判定してください。\n'
            '\n'
            '判定原則 (重要):\n'
            '- **混入 > 分裂**。誤って別事件をマージすると品質を大きく下げます。\n'
            '- 迷ったら sameEvent=false を返してください。\n'
            '\n'
            '判定基準:\n'
            '- 同じ事件・事故・発表・声明・試合結果・人事・政策決定 (A と B が指す出来事が一致) → true\n'
            '- 同じテーマ (例: 関税引き上げ) でも対象エンティティが異なる (米国 vs 日本) → false\n'
            '- 同じ人物が登場しても出来事が異なる (別の発言・別の会談) → false\n'
            '- 続報・速報・詳報・更新は元の事象と同一とみなす → true\n'
            '- 数値や日時が一致するのに表現が違うだけ (「米GDP速報値2.0%増」と「米GDP年率2.0%増」) → true\n'
            '- 共有エンティティが空 or 弱い (汎用語のみ) → false (主要登場人物/組織/場所が一致しない)\n'
        )
        user = (
            f'以下 {len(pairs)} 個のペアそれぞれについて、A と B が同一の事件を報じているかを判定してください。\n\n'
            f'{numbered}\n\n'
            f'各ペアについて index (1〜{len(pairs)}) と sameEvent (true/false) を返してください。'
            f'迷ったら false で結構です。'
        )
        tool_schema = {
            'type': 'object',
            'properties': {
                'judgments': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'index': {'type': 'integer', 'minimum': 1, 'maximum': len(pairs)},
                            'sameEvent': {'type': 'boolean'},
                        },
                        'required': ['index', 'sameEvent'],
                    },
                    'minItems': len(pairs),
                    'maxItems': len(pairs),
                },
            },
            'required': ['judgments'],
        }
        payload = {
            'model': self.model,
            'max_tokens': 1024,
            'tools': [{
                'name': 'report_judgments',
                'description': '各ペアの判定結果を返す',
                'input_schema': tool_schema,
            }],
            'tool_choice': {'type': 'tool', 'name': 'report_judgments'},
            'system': [{'type': 'text', 'text': system, 'cache_control': {'type': 'ephemeral'}}],
            'messages': [{'role': 'user', 'content': user}],
        }
        body = json.dumps(payload).encode('utf-8')
        headers = {
            'x-api-key': self.api_key,
            'anthropic-version': '2023-06-01',
            'anthropic-beta': 'prompt-caching-2024-07-31',
            'content-type': 'application/json',
        }
        delay = 5
        last_err: Exception | None = None
        response = None
        for attempt in range(3):
            try:
                req = urllib.request.Request(_CLAUDE_API_URL, data=body, headers=headers, method='POST')
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    response = json.loads(resp.read())
                break
            except urllib.error.HTTPError as e:
                last_err = e
                if e.code in _RETRYABLE_HTTP_CODES and attempt < 2:
                    print(f'[ai_merge_judge] HTTP {e.code} retry attempt={attempt+1} wait_s={delay}')
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                last_err = e
                if attempt < 2:
                    print(f'[ai_merge_judge] network error retry attempt={attempt+1} wait_s={delay}: {type(e).__name__}')
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise
        if response is None:
            if last_err:
                raise last_err
            raise RuntimeError('Claude API retries exhausted')

        usage = response.get('usage') or {}
        cache_read = usage.get('cache_read_input_tokens', 0)
        cache_write = usage.get('cache_creation_input_tokens', 0)
        if cache_read or cache_write:
            print(f'[METRIC] ai_merge_judge_cache read={cache_read} write={cache_write}')

        judgments_by_idx: dict[int, bool] = {}
        for block in response.get('content', []):
            if block.get('type') == 'tool_use' and block.get('name') == 'report_judgments':
                input_data = block.get('input') or {}
                for j in input_data.get('judgments', []):
                    try:
                        idx = int(j.get('index'))
                        judgments_by_idx[idx] = bool(j.get('sameEvent'))
                    except (TypeError, ValueError):
                        continue
                break

        # 抜けたインデックスは failsafe=False
        return [judgments_by_idx.get(i + 1, False) for i in range(len(pairs))]
