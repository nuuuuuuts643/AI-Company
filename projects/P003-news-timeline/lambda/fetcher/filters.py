"""
filters.py — 二次情報フィルター・パターン定義・フィルター重みキャッシュ

パターンの更新方法:
  lifecycle Lambda が週次で filter-feedback を集計し
  api/filter-weights.json を S3 に書き込む（TODO: lifecycle側実装予定）。
  Lambda コールド起動時に load_filter_weights() で読み込む。
"""
import json
import re

from config import S3_BUCKET, s3


# ── 完全スキップ: 日次まとめ・ヘッドライン集記事 ──────────────────────────
_DIGEST_SKIP_PATS = [
    re.compile(r'\d{4}年\d{1,2}月\d{1,2}日の.{0,10}ヘッドライン'),
    re.compile(r'\d{1,2}月\d{1,2}日.{0,10}ヘッドライン'),
    re.compile(r'今日のニュースまとめ'),
    re.compile(r'今週のニュースまとめ'),
    re.compile(r'^【\d{1,2}月\d{1,2}日】.{0,30}まとめ'),
    re.compile(r'ニュースまとめ[：:\s（(]'),
    re.compile(r'^週刊.{0,20}まとめ$'),
    re.compile(r'本日のヘッドライン'),
    re.compile(r'ヘッドラインニュース$'),
    re.compile(r'株価・株式情報\s*[-–]\s*Yahoo!ファイナンス'),
    re.compile(r'【\d{3,5}】[：:].{0,20}株価'),
    re.compile(r'掲示板\s*[-–]\s*Yahoo!ファイナンス'),
]

# ── 意見・コラム記事パターン (正規表現, ベース係数, weight_key) ──────────
_OPINION_PATS = [
    (r'について考える', 0.5, 'opinion:について考える'),
    (r'を考える',       0.5, 'opinion:を考える'),
    (r'の問題点',       0.5, 'opinion:の問題点'),
    (r'を分析',         0.5, 'opinion:を分析'),
    (r'の真相',         0.5, 'opinion:の真相'),
    (r'とは何か',       0.5, 'opinion:とは何か'),
    (r'はなぜ',         0.5, 'opinion:はなぜ'),
    (r'すべきか',       0.5, 'opinion:すべきか'),
    (r'の危機',         0.5, 'opinion:の危機'),
    (r'か？$',          0.5, 'opinion:か？'),
    (r'のか$',          0.5, 'opinion:のか'),
    (r'だろうか',       0.5, 'opinion:だろうか'),
    (r'コラム',         0.5, 'opinion:コラム'),
    (r'オピニオン',     0.5, 'opinion:オピニオン'),
    (r'解説[：:]',      0.5, 'opinion:解説'),
    (r'考察[：:]',      0.5, 'opinion:考察'),
]

# ── 二次情報パターン ──────────────────────────────────────────────────────
_SECONDARY_PATS = [
    (r'と報じた',       0.6, 'secondary:と報じた'),
    (r'が報じた',       0.6, 'secondary:が報じた'),
    (r'が伝えた',       0.6, 'secondary:が伝えた'),
    (r'が明らかにした', 0.6, 'secondary:が明らかにした'),
    (r'によると',       0.6, 'secondary:によると'),
    (r'によれば',       0.6, 'secondary:によれば'),
    (r'と伝えた',       0.6, 'secondary:と伝えた'),
    (r'と明かした',     0.6, 'secondary:と明かした'),
    (r'報道によ',       0.6, 'secondary:報道によ'),
    (r'各紙が',         0.6, 'secondary:各紙が'),
    (r'各社が',         0.6, 'secondary:各社が'),
]

_DEFAULT_WEIGHTS: dict = {
    **{key: 1.0 for _, _, key in _OPINION_PATS},
    **{key: 1.0 for _, _, key in _SECONDARY_PATS},
    'secondary:title_reporting': 1.0,
}

# Lambda コールド起動時に S3 から読み込むキャッシュ（ウォーム呼び出しで使い回す）
_FILTER_WEIGHTS: dict = {}
_FILTER_WEIGHTS_LOADED: bool = False


def load_filter_weights() -> None:
    """S3 から filter-weights.json を読み込み _FILTER_WEIGHTS に格納する（コールド起動時のみ）。"""
    global _FILTER_WEIGHTS, _FILTER_WEIGHTS_LOADED
    if _FILTER_WEIGHTS_LOADED:
        return
    _FILTER_WEIGHTS_LOADED = True
    _FILTER_WEIGHTS.update(_DEFAULT_WEIGHTS)
    if not S3_BUCKET:
        return
    try:
        resp = s3.get_object(Bucket=S3_BUCKET, Key='api/filter-weights.json')
        loaded = json.loads(resp['Body'].read()).get('weights', {})
        _FILTER_WEIGHTS.update(loaded)
        print(f'filter-weights.json ロード完了: {len(_FILTER_WEIGHTS)}パターン')
    except s3.exceptions.NoSuchKey:
        print('filter-weights.json 未作成 → デフォルト値使用')
    except Exception as e:
        print(f'filter-weights.json 読み込みエラー → デフォルト値使用: {e}')


def _effective_mult(base: float, weight_key: str) -> float:
    """
    パターン重みを適用した実効係数を計算する。
    実効係数 = 1.0 - (1.0 - base) × weight
    """
    weight = _FILTER_WEIGHTS.get(weight_key, 1.0)
    return max(0.2, min(1.0, 1.0 - (1.0 - base) * weight))


def is_secondary_article(title: str, description: str = '') -> tuple:
    """
    記事タイトル・本文冒頭を解析し、二次情報・意見記事を検出する。
    戻り値: (multiplier: float, pattern_key: str | None)
    """
    text = (title or '') + ' ' + (description or '')
    t = title or ''

    for pat, base, key in _OPINION_PATS:
        if re.search(pat, t):
            return _effective_mult(base, key), key

    for pat, base, key in _SECONDARY_PATS:
        if re.search(pat, text):
            return _effective_mult(base, key), key

    if re.search(r'.{2,15}(報道|報じ|伝え)', t):
        key = 'secondary:title_reporting'
        return _effective_mult(0.6, key), key

    return 1.0, None


def _apply_secondary_penalty(g: list) -> tuple:
    """
    グループ内記事の二次情報割合に応じた係数とフィードバックを返す。
    過半数が減点対象の場合のみグループ全体に適用する。
    戻り値: (penalty: float, feedback_entries: list)
    """
    if not g:
        return 1.0, []

    results = [(is_secondary_article(a.get('title', '')), a) for a in g]
    penalized = [((mult, key), a) for (mult, key), a in results if mult < 1.0]

    if len(penalized) > len(g) / 2:
        all_mults = [mult for (mult, _), _ in results]
        avg_penalty = sum(all_mults) / len(all_mults)
        feedback = [{
            'url':        a.get('url', ''),
            'title':      a.get('title', '')[:80],
            'pattern':    key,
            'multiplier': round(mult, 4),
        } for (mult, key), a in penalized]
        return avg_penalty, feedback

    return 1.0, []
