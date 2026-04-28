"""T2026-0429-B: should_branch() のセマンティック分岐判定テスト。

判定マトリクス (docs/rules/story-branching-policy.md §3.3):
  ① 主役重複あり × 因果連続あり          → 継続 (False)  ※ 同一事件の新展開
  ② 主役重複なし                          → 分岐 (True)   ※ 別主役 = 別ストーリー
  ③ 主役重複あり × 因果連続なし × Jacc<.25 → 分岐 (True)   ※ 同人物の別事案
  ④ その他                                → 現行ロジック (Jaccard 0.35 以上で継続)

数字 (velocityScore / 記事数) は判定に使わない。内容軸のみ。
"""
import os
import sys

# Lambda processor を import するための path 設定
HERE = os.path.dirname(os.path.abspath(__file__))
PROC_DIR = os.path.normpath(os.path.join(HERE, '..', 'lambda', 'processor'))
if PROC_DIR not in sys.path:
    sys.path.insert(0, PROC_DIR)

# ANTHROPIC_API_KEY が無くても import できるよう dummy を入れる (本テストは API 呼ばない)
os.environ.setdefault('ANTHROPIC_API_KEY', 'sk-test-not-real')

import pytest  # noqa: E402

import proc_ai  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# ヘルパ
# ─────────────────────────────────────────────────────────────────────────────
def _topic(title: str, keypoint: str, entities: list) -> dict:
    return {'title': title, 'keyPoint': keypoint, 'entities': entities}


# ─────────────────────────────────────────────────────────────────────────────
# Case 1: 同一事件の新展開 (逮捕 → 起訴) は継続扱い (False)
# 主役重複あり × 因果連続あり → 継続
# ─────────────────────────────────────────────────────────────────────────────
def test_same_event_progression_arrest_to_indictment_should_not_branch():
    parent = _topic(
        title='元議員A氏 詐欺容疑で逮捕',
        keypoint='元国会議員のA氏が詐欺の容疑で警視庁に逮捕された。',
        entities=[{'name': 'A氏', 'type': 'PERSON'}, {'name': '警視庁', 'type': 'ORG'}],
    )
    candidate = _topic(
        title='A氏 詐欺罪で起訴',
        keypoint='東京地検特捜部はA氏を詐欺罪で起訴した。',
        entities=[{'name': 'A氏', 'type': 'PERSON'}, {'name': '東京地検', 'type': 'ORG'}],
    )
    assert proc_ai.should_branch(parent, candidate) is False, \
        '逮捕 → 起訴 (主役同一・因果連続) は継続扱いのはず'


def test_same_event_progression_release_to_recall_should_not_branch():
    parent = _topic(
        title='X社 新型スマホ発売',
        keypoint='X社は次世代スマートフォンを発売した。',
        entities=[{'name': 'X社', 'type': 'ORG'}],
    )
    candidate = _topic(
        title='X社 スマホ不具合でリコール',
        keypoint='X社の新型スマホで不具合が見つかりリコールが発表された。',
        entities=[{'name': 'X社', 'type': 'ORG'}],
    )
    assert proc_ai.should_branch(parent, candidate) is False, \
        '発売 → 不具合/リコール (主役同一・因果連続) は継続扱いのはず'


# ─────────────────────────────────────────────────────────────────────────────
# Case 2: 主役が変わる → 分岐 (True)
# ─────────────────────────────────────────────────────────────────────────────
def test_different_actor_should_branch():
    parent = _topic(
        title='A社 新製品発表',
        keypoint='A社が次世代AI製品を発表した。',
        entities=[{'name': 'A社', 'type': 'ORG'}],
    )
    candidate = _topic(
        title='B社 工場新設',
        keypoint='B社は新工場を建設すると発表した。',
        entities=[{'name': 'B社', 'type': 'ORG'}],
    )
    assert proc_ai.should_branch(parent, candidate) is True, \
        '主役 (A社 vs B社) が異なる場合は分岐すべき'


def test_different_person_should_branch():
    parent = _topic(
        title='岸田首相 訪米',
        keypoint='岸田首相がワシントンを訪問し首脳会談を行った。',
        entities=[{'name': '岸田首相', 'type': 'PERSON'}],
    )
    candidate = _topic(
        title='高市氏 党首選出馬表明',
        keypoint='高市早苗氏が党首選への出馬を正式表明した。',
        entities=[{'name': '高市氏', 'type': 'PERSON'}],
    )
    assert proc_ai.should_branch(parent, candidate) is True, \
        '別人物 (岸田 vs 高市) の話題は分岐すべき'


# ─────────────────────────────────────────────────────────────────────────────
# Case 3: 主役重複あり × 因果連続なし × Jaccard 低 → 分岐 (True)
# 同人物の別事案
# ─────────────────────────────────────────────────────────────────────────────
def test_same_actor_unrelated_event_low_jaccard_should_branch():
    parent = _topic(
        title='イーロン・マスク 火星計画講演',
        keypoint='イーロン・マスク氏は将来の火星移住について講演した。',
        entities=[{'name': 'イーロン・マスク', 'type': 'PERSON'}],
    )
    candidate = _topic(
        title='イーロン・マスク Twitter買収後の組織再編',
        keypoint='イーロン・マスク氏はソーシャルメディアの組織再編に着手した。',
        entities=[{'name': 'イーロン・マスク', 'type': 'PERSON'}],
    )
    # 主役 (マスク) は重複、因果連続なし (火星と Twitter で文脈無関係)、
    # Jaccard も低い (火星/移住/講演 vs Twitter/買収/組織再編)
    assert proc_ai.should_branch(parent, candidate) is True, \
        '主役同一でも別事案・Jaccard 低なら分岐すべき'


# ─────────────────────────────────────────────────────────────────────────────
# Case 4: 共通主役・高い Jaccard・因果なし → 継続 (False) ※ 現行ロジック ④
# ─────────────────────────────────────────────────────────────────────────────
def test_same_actor_high_jaccard_should_not_branch():
    parent = _topic(
        title='トヨタ EV 戦略 加速',
        keypoint='トヨタはEV戦略を加速し新型車種を投入する。',
        entities=[{'name': 'トヨタ', 'type': 'ORG'}],
    )
    candidate = _topic(
        title='トヨタ EV 戦略 強化 新型投入',
        keypoint='トヨタはEV戦略を強化し新型車種を投入する方針。',
        entities=[{'name': 'トヨタ', 'type': 'ORG'}],
    )
    # ほぼ同内容 = Jaccard 高 → ④ で継続
    assert proc_ai.should_branch(parent, candidate) is False, \
        '主役同一・内容類似 (高 Jaccard) は継続すべき'


# ─────────────────────────────────────────────────────────────────────────────
# Case 5: 主役なし (entities 空) でも内容類似なら継続 (現行ロジック ④)
# ─────────────────────────────────────────────────────────────────────────────
def test_no_entities_high_jaccard_fallback_should_not_branch():
    # スペース区切りで同じトークンを多く共有 → Jaccard >= 0.35 で継続
    parent = _topic(
        title='物価 高騰 家計 圧迫 続く 状況',
        keypoint='物価 高騰 家計 圧迫 続く 状況 続報',
        entities=[],
    )
    candidate = _topic(
        title='物価 高騰 家計 圧迫 続く 状況 詳報',
        keypoint='物価 高騰 家計 圧迫 続く 状況 詳細',
        entities=[],
    )
    # 主役不明 → ④ にフォールスルー → Jaccard 高で継続
    assert proc_ai.should_branch(parent, candidate) is False, \
        '主役不明でも Jaccard 高なら継続 (現行ロジック)'


def test_no_entities_low_jaccard_fallback_should_branch():
    parent = _topic(
        title='米雇用統計 予想上回る',
        keypoint='米国の雇用統計が市場予想を上回った。',
        entities=[],
    )
    candidate = _topic(
        title='欧州金利 据え置き決定',
        keypoint='ECBは政策金利を据え置きと発表した。',
        entities=[],
    )
    # 主役不明 → ④ → Jaccard 低 (0.35 未満) で分岐
    assert proc_ai.should_branch(parent, candidate) is True, \
        '主役不明・Jaccard 低は ④ で分岐'


# ─────────────────────────────────────────────────────────────────────────────
# 補助: ヘルパ関数の単体テスト
# ─────────────────────────────────────────────────────────────────────────────
def test_extract_primary_entities_only_person_org():
    ents = [
        {'name': 'A氏', 'type': 'PERSON'},
        {'name': '東京', 'type': 'LOC'},      # LOC は除外
        {'name': 'B社', 'type': 'ORG'},
        {'name': '製品X', 'type': 'PRODUCT'},  # PRODUCT は除外
    ]
    primary = proc_ai._extract_primary_entities(ents)
    assert 'A氏' in primary
    assert 'B社' in primary
    assert '東京' not in primary
    assert '製品X' not in primary
    assert len(primary) <= 2


def test_extract_primary_entities_legacy_string_list():
    """旧形式 (str リスト) もサポート"""
    primary = proc_ai._extract_primary_entities(['田中氏', '山田氏', '鈴木氏'])
    assert len(primary) == 2  # 上位2件のみ
    assert '田中氏' in primary
    assert '山田氏' in primary


def test_has_causal_sequence_arrest_indictment():
    a = '元議員が詐欺容疑で逮捕された'
    b = '東京地検が起訴を発表した'
    assert proc_ai._has_causal_sequence(a, b) is True


def test_has_causal_sequence_unrelated_words():
    a = '物価高騰が続いている'
    b = '雇用統計が予想を上回った'
    assert proc_ai._has_causal_sequence(a, b) is False


# ─────────────────────────────────────────────────────────────────────────────
# 数字 (velocityScore / 記事数) は判定に使われていないことを確認
# ─────────────────────────────────────────────────────────────────────────────
def test_velocity_score_does_not_affect_branching():
    """velocityScore や articleCount を渡しても判定結果は変わらない (内容軸のみ)。"""
    parent = _topic('A社 新製品', 'A社は新製品を発表した。', [{'name': 'A社', 'type': 'ORG'}])
    candidate = _topic('A社 株価上昇', 'A社の株価が上昇した。', [{'name': 'A社', 'type': 'ORG'}])

    # velocityScore を埋め込んでも結果が変わらないこと
    parent_with_velocity = dict(parent, velocityScore=99.9, articleCount=100)
    candidate_with_velocity = dict(candidate, velocityScore=0.1, articleCount=1)

    r1 = proc_ai.should_branch(parent, candidate)
    r2 = proc_ai.should_branch(parent_with_velocity, candidate_with_velocity)
    assert r1 == r2, '数字フィールドは判定に影響してはならない'


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-v']))
