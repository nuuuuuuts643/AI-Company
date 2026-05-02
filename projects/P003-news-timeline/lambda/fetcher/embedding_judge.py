"""embedding_judge.py — borderline トピックペアを embedding cosine sim で判定するモジュール。

T2026-0502-U Phase 2 (2026-05-02 PO 指示「embedding 移行進めたい」):
  ai_merge_judge.py (Haiku 月 ~$120) を embedding ベース (月 $0) に置換。
  multilingual-e5-small ONNX qint8 (118MB Lambda layer) でローカル推論。

入力契約 (AIMergeJudge と完全互換 → drop-in 置換可能):
  judge_pairs(pairs) -> dict[(title_a, title_b), bool]
  pairs[i]: {
    'title_a': str, 'title_b': str,
    'entities_a': list[str], 'entities_b': list[str],
    'shared_entities': list[str],
  }

判定アルゴリズム (Phase 2):
  1. shared_entities が空 → False (entity gate・現状の AIMergeJudge と同一)
  2. cosine(emb_a, emb_b) >= COSINE_HIGH (0.85) → True (高信頼で同一事件)
  3. cosine < COSINE_LOW (0.65) → False (高信頼で別事件)
  4. 0.65 <= cosine < 0.85 → AIMergeJudge fallback (env で OFF 可)

env 設定:
  EMBEDDING_MERGE_ENABLED=true   # この judge を使うか
  EMBEDDING_MODEL_PATH=/opt/embedding/model.onnx  # Lambda layer マウントパス
  EMBEDDING_TOKENIZER_PATH=/opt/embedding/tokenizer
  COSINE_HIGH=0.85
  COSINE_LOW=0.65

PoC 状態 (2026-05-02 14:50 JST 時点):
  - インターフェイス完成・mock backend で unit test pass 想定
  - 実 ONNX runtime + multilingual-e5-small は Code セッションで Lambda layer ビルドして bench 必要
  - 閾値 (0.85 / 0.65) は HuggingFace MTEB-Japanese ベンチで参考値・実測で再調整
"""
from __future__ import annotations

import os
from typing import Optional

# 閾値 (env でオーバーライド可)
COSINE_HIGH = float(os.environ.get('COSINE_HIGH', '0.85'))
COSINE_LOW = float(os.environ.get('COSINE_LOW', '0.65'))

# Lambda layer マウントパス (env でオーバーライド可)
_DEFAULT_MODEL_PATH = '/opt/embedding/model.onnx'
_DEFAULT_TOKENIZER_PATH = '/opt/embedding/tokenizer'


class EmbeddingBackend:
    """埋め込み計算の抽象化。本番は ONNX runtime・テストは mock。"""

    def encode(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    def cosine(self, a: list[float], b: list[float]) -> float:
        """簡易コサイン類似度 (numpy 不要・stdlib のみで動かす)。"""
        if not a or not b:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(y * y for y in b) ** 0.5
        return dot / (na * nb) if na and nb else 0.0


class OnnxEmbeddingBackend(EmbeddingBackend):
    """multilingual-e5-small ONNX qint8 実装。

    Lambda layer に model.onnx + tokenizer を同梱。layer 同梱前は ImportError で
    fail-fast (呼び出し側で fallback 判定)。
    """

    def __init__(self, model_path: str = _DEFAULT_MODEL_PATH,
                 tokenizer_path: str = _DEFAULT_TOKENIZER_PATH):
        try:
            import onnxruntime as ort
            from transformers import AutoTokenizer
        except ImportError as e:
            raise ImportError(
                f'ONNX/transformers 未配置: {e}. Lambda layer がビルドされてないか、'
                f'Code セッションで scripts/build_embedding_layer.sh を実行してください。'
            )
        # CPU only でロード (Lambda は CPU)
        self.session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_path)

    def encode(self, texts: list[str]) -> list[list[float]]:
        # E5 は "query: ..." prefix が推奨
        prefixed = [f'query: {t}' for t in texts]
        enc = self.tokenizer(prefixed, padding=True, truncation=True,
                             max_length=128, return_tensors='np')
        outputs = self.session.run(None, {
            'input_ids': enc['input_ids'],
            'attention_mask': enc['attention_mask'],
        })
        # mean pooling
        last_hidden = outputs[0]
        mask = enc['attention_mask'][..., None]
        summed = (last_hidden * mask).sum(axis=1)
        counts = mask.sum(axis=1).clip(min=1)
        pooled = summed / counts
        # L2 normalize
        norms = (pooled ** 2).sum(axis=1, keepdims=True) ** 0.5
        normed = pooled / norms.clip(min=1e-8)
        return normed.tolist()


class MockEmbeddingBackend(EmbeddingBackend):
    """テスト用・タイトル文字列の bigram set 大文字小文字一致でコサインを近似。

    Lambda layer 未配置でも動く（unit test と CI が通せる）。
    """

    def _bigrams(self, t: str) -> set:
        s = t.lower()
        return {s[i:i+2] for i in range(len(s) - 1)}

    def encode(self, texts: list[str]) -> list[list[float]]:
        # bigram の有無を 0/1 ベクトルに (テストのみ)
        all_bigrams = sorted({bg for t in texts for bg in self._bigrams(t)})
        idx = {bg: i for i, bg in enumerate(all_bigrams)}
        return [
            [1.0 if bg in self._bigrams(t) else 0.0 for bg in all_bigrams]
            for t in texts
        ]


class EmbeddingMergeJudge:
    """AIMergeJudge と互換インターフェイスの embedding ベース判定器。"""

    def __init__(self, backend: Optional[EmbeddingBackend] = None,
                 cosine_high: float = COSINE_HIGH,
                 cosine_low: float = COSINE_LOW,
                 fallback_judge=None):
        self.backend = backend or OnnxEmbeddingBackend()
        self.cosine_high = cosine_high
        self.cosine_low = cosine_low
        self.fallback_judge = fallback_judge  # AIMergeJudge instance (option)
        self._cache: dict[tuple[str, str], bool] = {}
        # 観測カウンタ (governance worker で集計・[FETCHER_HEALTH] に出す)
        self.pairs_asked = 0
        self.pairs_yes = 0
        self.pairs_no = 0
        self.high_confidence_decisions = 0  # >= COSINE_HIGH or < COSINE_LOW
        self.borderline_fallback_calls = 0  # AIMergeJudge fallback 数

    @staticmethod
    def _key(a: str, b: str) -> tuple[str, str]:
        return (a, b) if a <= b else (b, a)

    def judge_pairs(self, pairs: list[dict]) -> dict[tuple[str, str], bool]:
        if not pairs:
            return {}

        result: dict[tuple[str, str], bool] = {}
        to_compute: list[dict] = []  # backend に投げる必要があるペア

        # 1st pass: cache hit / entity gate / 重複除去
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

            # cache hit
            if k in self._cache:
                result[k] = self._cache[k]
                continue

            # entity gate: shared_entities 空なら別事件 (Haiku 同様)
            if not p.get('shared_entities'):
                self._cache[k] = False
                result[k] = False
                self.pairs_no += 1
                self.high_confidence_decisions += 1
                continue

            to_compute.append({**p, '_key': k})

        if not to_compute:
            self.pairs_asked += len(seen_keys)
            return result

        # 2nd pass: embedding cosine
        # ペアごとに 2 文を encode するのは重複多いので unique title 集めて 1 batch で encode
        unique_titles: list[str] = []
        title_idx: dict[str, int] = {}
        for p in to_compute:
            for t in (p['title_a'], p['title_b']):
                if t not in title_idx:
                    title_idx[t] = len(unique_titles)
                    unique_titles.append(t)

        embeddings = self.backend.encode(unique_titles)

        # 3rd pass: 各ペアの cosine 計算 + 閾値判定
        for p in to_compute:
            k = p['_key']
            ea = embeddings[title_idx[p['title_a']]]
            eb = embeddings[title_idx[p['title_b']]]
            sim = self.backend.cosine(ea, eb)

            if sim >= self.cosine_high:
                decision = True
                self.high_confidence_decisions += 1
            elif sim < self.cosine_low:
                decision = False
                self.high_confidence_decisions += 1
            else:
                # borderline: fallback (AIMergeJudge) があれば呼ぶ・なければ False (混入>分裂で保守的)
                if self.fallback_judge is not None:
                    self.borderline_fallback_calls += 1
                    fb_result = self.fallback_judge.judge_pairs([p])
                    decision = bool(fb_result.get(k, False))
                else:
                    decision = False

            self._cache[k] = decision
            result[k] = decision
            if decision:
                self.pairs_yes += 1
            else:
                self.pairs_no += 1

        self.pairs_asked = len(seen_keys)
        return result


def make_default_judge(api_key: Optional[str] = None) -> Optional[EmbeddingMergeJudge]:
    """env を見て embedding judge を作成。EMBEDDING_MERGE_ENABLED!=true なら None。

    fallback_judge は EMBEDDING_FALLBACK_TO_HAIKU=true かつ api_key 設定時のみ有効化。
    """
    if os.environ.get('EMBEDDING_MERGE_ENABLED', 'false').lower() != 'true':
        return None

    fallback = None
    if (api_key and
            os.environ.get('EMBEDDING_FALLBACK_TO_HAIKU', 'false').lower() == 'true' and
            os.environ.get('AI_MERGE_ENABLED', 'false').lower() == 'true'):
        try:
            from ai_merge_judge import AIMergeJudge
            fallback = AIMergeJudge(api_key=api_key)
        except Exception as e:
            print(f'[embedding_judge] AIMergeJudge fallback 初期化失敗 (continue without fallback): {e}')
            fallback = None

    try:
        return EmbeddingMergeJudge(fallback_judge=fallback)
    except ImportError as e:
        print(f'[embedding_judge] ONNX backend ロード失敗 → 無効化: {e}')
        return None
