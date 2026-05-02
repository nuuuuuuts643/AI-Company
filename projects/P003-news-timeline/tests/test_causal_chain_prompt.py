#!/usr/bin/env python3
"""tests/test_causal_chain_prompt.py — T2026-0502-AE

`lambda/processor/proc_ai.py` の `_build_aisummary_causal_hint` の境界値テスト。

設計方針:
  - 国際/政治/ビジネス/株・金融/テクノロジー/科学/健康/社会 ジャンルでは
    causal chain hint が必ず出力されること
  - 上記以外 (エンタメ/グルメ/スポーツ/ファッション/くらし/総合) では空文字
  - None / 空文字 / 未知ジャンル も空文字
  - 出力に必ず「なぜ今 / 何が引き金 / 誰の利害」のキーワードが含まれること
  - 抽象表現禁止条項 (「対立深刻化」「影響を与える」) が出力に含まれること

このテストが守るべき不変条件:
  full / standard 両モードで genre 別 causal hint を inject する設計が壊れた瞬間に
  CI で検知できる。
"""
from __future__ import annotations

import os
import sys

import pytest

# proc_ai の import パスを通す
_LAMBDA_PROCESSOR = os.path.join(
    os.path.dirname(__file__), '..', 'lambda', 'processor'
)
sys.path.insert(0, _LAMBDA_PROCESSOR)

import proc_ai  # noqa: E402


# ---------------------------------------------------------------------------
# _build_aisummary_causal_hint: ジャンル別 hint 出力テスト
# ---------------------------------------------------------------------------


CAUSAL_GENRES = ['国際', '政治', 'ビジネス', '株・金融', 'テクノロジー',
                 '科学', '健康', '社会']
NON_CAUSAL_GENRES = ['エンタメ', 'グルメ', 'スポーツ', 'ファッション',
                     'くらし', '総合']


@pytest.mark.parametrize('genre', CAUSAL_GENRES)
def test_causal_genres_emit_hint(genre):
    """causal対象 ジャンルは必ず hint を返す (空文字でない)。"""
    hint = proc_ai._build_aisummary_causal_hint(genre)
    assert hint, f'genre={genre} should emit non-empty hint'
    assert 'aiSummary causal chain' in hint
    assert 'T2026-0502-AE' in hint


@pytest.mark.parametrize('genre', NON_CAUSAL_GENRES)
def test_non_causal_genres_emit_empty(genre):
    """エンタメ等は keyPoint で causal が十分なため空文字を返す。"""
    hint = proc_ai._build_aisummary_causal_hint(genre)
    assert hint == '', f'genre={genre} should NOT emit hint, got: {hint[:80]}'


def test_none_genre_returns_empty():
    assert proc_ai._build_aisummary_causal_hint(None) == ''


def test_empty_genre_returns_empty():
    assert proc_ai._build_aisummary_causal_hint('') == ''


def test_unknown_genre_returns_empty():
    """_GENRE_AISUMMARY_CAUSAL_FRAMES に無いジャンルは空文字。"""
    assert proc_ai._build_aisummary_causal_hint('架空ジャンル') == ''


# ---------------------------------------------------------------------------
# hint 内容: 必須キーワード / 禁止表現
# ---------------------------------------------------------------------------


@pytest.mark.parametrize('genre', CAUSAL_GENRES)
def test_hint_includes_three_dimensions(genre):
    """各 genre の hint は「なぜ今 / 引き金 / 利害」の 3 軸全部に言及すること。"""
    hint = proc_ai._build_aisummary_causal_hint(genre)
    assert 'なぜ今' in hint, f'genre={genre} hint missing "なぜ今"'
    assert '引き金' in hint, f'genre={genre} hint missing "引き金"'
    assert '利害' in hint, f'genre={genre} hint missing "利害"'


@pytest.mark.parametrize('genre', CAUSAL_GENRES)
def test_hint_forbids_abstract_phrases(genre):
    """各 genre の hint は禁止表現リストを必ず含めて AI に伝えること。"""
    hint = proc_ai._build_aisummary_causal_hint(genre)
    # 抽象表現禁止が hint 自体に明記されていること
    assert '抽象表現禁止' in hint
    # 具体的な禁止フレーズも出る
    assert '動向に注目' in hint or '影響を与える' in hint


@pytest.mark.parametrize('genre', CAUSAL_GENRES)
def test_hint_enforces_150char_constraint(genre):
    """150 字制約の言及があること (aiSummary の字数上限)。"""
    hint = proc_ai._build_aisummary_causal_hint(genre)
    assert '150' in hint, f'genre={genre} hint missing 150-char constraint'


def test_kokusai_frame_specific_example():
    """国際 frame は元苦情 (4bf3a46568f1189c EU 関税) の具体例を含むこと。
    将来 frame を改修して例文が消えたら検知する unit test (regression detection)。"""
    hint = proc_ai._build_aisummary_causal_hint('国際')
    # EU の例 or 関税の例 が含まれていることを確認
    assert 'EU' in hint or '関税' in hint, \
        '国際 frame should keep the EU/関税 worked example for regression detection'


# ---------------------------------------------------------------------------
# 統合: hint がプロンプト build に影響することの軽い smoke test
# ---------------------------------------------------------------------------


def test_hint_inject_does_not_raise_for_known_genres():
    """全 causal genre で _build_aisummary_causal_hint を呼んでも例外なし (smoke)。"""
    for g in CAUSAL_GENRES + NON_CAUSAL_GENRES + [None, '']:
        try:
            result = proc_ai._build_aisummary_causal_hint(g)
            assert isinstance(result, str)
        except Exception as exc:
            pytest.fail(f'_build_aisummary_causal_hint({g!r}) raised: {exc}')


def test_genre_aisummary_causal_frames_dict_keys_match_causal_genres():
    """設計不変条件: _GENRE_AISUMMARY_CAUSAL_FRAMES のキーは
    CAUSAL_GENRES と一致 (将来 dict に追加した時テストも更新を促す)。"""
    dict_keys = set(proc_ai._GENRE_AISUMMARY_CAUSAL_FRAMES.keys())
    assert dict_keys == set(CAUSAL_GENRES), (
        f'_GENRE_AISUMMARY_CAUSAL_FRAMES keys diverged from test CAUSAL_GENRES.\n'
        f'  in dict but not in test: {dict_keys - set(CAUSAL_GENRES)}\n'
        f'  in test but not in dict: {set(CAUSAL_GENRES) - dict_keys}\n'
        f'-> test と dict を同期更新してください'
    )
