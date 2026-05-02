#!/usr/bin/env python3
"""embedding_bench.py — multilingual-e5-small の P003 用 cosine 閾値検証ベンチ。

T2026-0502-U Phase 1 (2026-05-02 PO 指示「embedding 移行進めたい」):
  実 ONNX runtime + multilingual-e5-small で日本語ニュースタイトル ペアの
  cosine sim を計測し、閾値 (COSINE_HIGH=0.85, COSINE_LOW=0.65) の妥当性を
  fixture ベースで判定。

使い方 (Mac の Code セッションで):
  bash scripts/build_embedding_layer.sh   # まず layer をビルド (model + tokenizer 準備)
  pip install onnxruntime transformers tokenizers sentencepiece numpy --user
  WORK_DIR=/tmp/build_embedding_layer python3 scripts/embedding_bench.py

期待される出力:
  ✓ 同一事件ペア (T2026-0501-M フィクスチャ) は cosine > 0.85
  ✓ 別事件ペア (米国 GDP vs 日本 GDP) は cosine < 0.65
  ✓ borderline ペア (... ) は 0.65-0.85 の中間
  → bench 結果を docs/p003-embedding-migration-research.md に追記
"""
import json
import os
import sys

WORK_DIR = os.environ.get('WORK_DIR', '/tmp/build_embedding_layer')
MODEL_PATH = os.path.join(WORK_DIR, 'embedding', 'model.onnx')
TOKENIZER_PATH = os.path.join(WORK_DIR, 'embedding', 'tokenizer')

# Bench fixtures: (label, title_a, title_b, expected_decision)
FIXTURES = [
    # 同一事件 (cosine 高い想定)
    ('same_event_geo_subset',
     'トランプ大統領 欧州駐留米軍 削減 発表',
     'トランプ氏 ドイツ駐留米軍 縮小',
     True),
    ('same_event_paraphrase',
     '米GDP速報値 年率2.0%増',
     '米国GDP 第3四半期 年率2.0%増',
     True),
    ('same_event_continuing',
     '日経平均 終値 史上最高値 更新',
     'NY株式市場 ナスダック S&P500指数 再び最高値更新',
     False),  # 「日経」と「NY」は別市場・別事件
    # 別事件 (主体違い・cosine 低くなるべき)
    ('different_subject_same_topic',
     '米国 GDP 速報値 2.0%増',
     '日本 GDP 速報値 2.0%増',
     False),
    ('different_event_same_org',
     'トランプ大統領 関税引き上げ発表',
     'トランプ大統領 ロシア制裁 緩和示唆',
     False),
    # borderline (難しいケース)
    ('borderline_score_match',
     'NY株式市場 ナスダック 最高値更新',
     'S&P500指数 終値 最高値',
     True),  # 同一日同一相場の続報想定
]


def main():
    if not os.path.exists(MODEL_PATH):
        print(f'[ERROR] model not found: {MODEL_PATH}')
        print('       bash scripts/build_embedding_layer.sh を先に実行してください')
        sys.exit(1)

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..',
                                     'projects', 'P003-news-timeline', 'lambda', 'fetcher'))
    from embedding_judge import OnnxEmbeddingBackend, EmbeddingMergeJudge

    print(f'[1/3] ONNX backend ロード: {MODEL_PATH}')
    backend = OnnxEmbeddingBackend(model_path=MODEL_PATH, tokenizer_path=TOKENIZER_PATH)

    print(f'[2/3] {len(FIXTURES)} ペアを encode して cosine 計算')
    results = []
    for label, a, b, expected in FIXTURES:
        embeddings = backend.encode([a, b])
        sim = backend.cosine(embeddings[0], embeddings[1])
        results.append((label, a, b, expected, sim))

    print(f'[3/3] 結果 (COSINE_HIGH=0.85 / COSINE_LOW=0.65):')
    print()
    print(f'{"label":<35} {"sim":>6} {"expected":>9} {"decision":>9} {"match":>6}')
    print('-' * 80)
    misses = 0
    for label, a, b, expected, sim in results:
        if sim >= 0.85:
            decision = True
        elif sim < 0.65:
            decision = False
        else:
            decision = None  # borderline = fallback
        match = '✓' if decision == expected else ('?' if decision is None else '✗')
        if decision != expected and decision is not None:
            misses += 1
        print(f'{label:<35} {sim:6.3f} {str(expected):>9} {str(decision):>9} {match:>6}')
    print()
    print(f'misses (high-confidence mistake): {misses} / {len(FIXTURES)}')
    print(f'borderline (need fallback)      : {sum(1 for *_ , s in results if 0.65 <= s < 0.85)} / {len(FIXTURES)}')

    # 推奨閾値再計算
    print()
    print('=== 閾値チューニング candidates ===')
    same_sims = [s for _, _, _, exp, s in results if exp]
    diff_sims = [s for _, _, _, exp, s in results if not exp]
    if same_sims and diff_sims:
        print(f'  same min     : {min(same_sims):.3f} (これより小だと False positive リスク)')
        print(f'  diff max     : {max(diff_sims):.3f} (これより大だと False negative リスク)')
        if min(same_sims) > max(diff_sims):
            optimal = (min(same_sims) + max(diff_sims)) / 2
            print(f'  推奨単一閾値 : {optimal:.3f}')
        else:
            print('  ⚠ same と diff が overlapping → fixture 増やすか閾値帯化必須')

    # JSON 出力 (CI で取り込み・doc 自動更新用)
    out_path = os.path.join(os.path.dirname(__file__), '..', 'tmp_logs', 'embedding_bench_result.json')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump({
            'results': [{
                'label': l, 'title_a': a, 'title_b': b,
                'expected': exp, 'cosine_sim': s
            } for l, a, b, exp, s in results],
            'misses': misses,
            'cosine_high': 0.85,
            'cosine_low': 0.65,
        }, f, ensure_ascii=False, indent=2)
    print(f'\n結果を {out_path} に保存')

    if misses > 0:
        print(f'\n⚠ misses {misses} 件 → 閾値再調整 or 別モデル検討')
        sys.exit(2)
    print('\n✅ Phase 1 PoC 通過。次は Phase 2 (fetcher 統合) へ。')


if __name__ == '__main__':
    main()
