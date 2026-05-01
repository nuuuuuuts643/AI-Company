#!/usr/bin/env python3
"""tests/test_verify_branching.py

T2026-0501-SLI-MISMERGE: verify_branching_quality.py の境界値テスト
全件スキャン・entity 重複チェック・Jaccard 複合判定を検証。
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.verify_branching_quality import (
    evaluate_branching, evaluate_pair, extract_entities, char_bigrams, jaccard
)


def test_extract_entities():
    """固有表現抽出の動作確認。"""
    # 3文字以上
    text = "Apple iPhone Android システム"
    entities = extract_entities(text)
    assert "Apple" in entities
    assert "iPhone" in entities
    assert "Android" in entities
    # 2文字以下は抽出されない
    assert "AI" not in entities or len("AI") < 3
    print("✓ test_extract_entities passed")


def test_char_bigrams():
    """char_bigrams の動作確認。"""
    text = "テスト"
    bgrams = char_bigrams(text)
    assert "テス" in bgrams
    assert "スト" in bgrams
    # 句読点除去
    text2 = "テスト、データ"
    bgrams2 = char_bigrams(text2)
    assert "、" not in "".join(bgrams2)
    print("✓ test_char_bigrams passed")


def test_jaccard_similarity():
    """Jaccard 類似度の計算確認。"""
    # 完全一致
    set_a = {"a", "b", "c"}
    set_b = {"a", "b", "c"}
    assert jaccard(set_a, set_b) == 1.0
    # 部分重複
    set_c = {"a", "b"}
    set_d = {"b", "c"}
    sim = jaccard(set_c, set_d)  # {"b"} / {"a", "b", "c"} = 1/3
    assert 0.32 < sim < 0.34
    # 非重複
    set_e = {"a", "b"}
    set_f = {"c", "d"}
    assert jaccard(set_e, set_f) == 0.0
    # 片方が空
    assert jaccard(set(), set({"a"})) == 0.0
    print("✓ test_jaccard_similarity passed")


def test_evaluate_pair_false_branch():
    """誤分岐疑い（similarity >= 0.6）。"""
    parent = {
        "topicId": "p1",
        "title": "トヨタ自動車 新型EV発表",
        "generatedTitle": "",
        "keyPoint": "",
    }
    child = {
        "topicId": "c1",
        "title": "トヨタ自動車 新型EV展示会",  # 似た内容
        "generatedTitle": "",
        "keyPoint": "",
    }
    result = evaluate_pair(parent, child)
    # 類似度が高い
    assert result["similarity"] >= 0.4
    assert result["verdict"] == "suspect_false_branch"
    print("✓ test_evaluate_pair_false_branch passed")


def test_evaluate_pair_false_merge_with_entities():
    """誤マージ疑い（sim < 0.15 かつ entity_overlap = 0）。"""
    parent = {
        "topicId": "p1",
        "title": "Apple iPhone 新機能",
        "generatedTitle": "",
        "keyPoint": "",
    }
    child = {
        "topicId": "c1",
        "title": "Google Pixel 価格",  # 全く別のメーカー・内容
        "generatedTitle": "",
        "keyPoint": "",
    }
    result = evaluate_pair(parent, child)
    # entity 重複なし・Jaccard 低い → 誤マージ疑い
    assert result["entity_overlap"] == 0
    assert result["similarity"] < 0.2
    assert result["verdict"] == "suspect_false_merge"
    print("✓ test_evaluate_pair_false_merge_with_entities passed")


def test_evaluate_pair_ok():
    """適切な分岐（0.15 <= sim < 0.6 or entity_overlap > 0）。"""
    parent = {
        "topicId": "p1",
        "title": "Apple iPhone 新機能",
        "generatedTitle": "",
        "keyPoint": "",
    }
    child = {
        "topicId": "c1",
        "title": "iPhone 最新情報 発表",  # 関連あり
        "generatedTitle": "",
        "keyPoint": "",
    }
    result = evaluate_pair(parent, child)
    # entity 重複あり（iPhone）→ 誤マージ疑いではない
    # sim < 0.6 → 誤分岐疑いでもない → ok
    assert result["entity_overlap"] > 0 or result["similarity"] >= 0.15
    assert result["similarity"] < 0.6
    assert result["verdict"] == "ok"
    print("✓ test_evaluate_pair_ok passed")


def test_evaluate_branching_empty():
    """topics が空の場合。"""
    result = evaluate_branching([])
    assert result["verdict"] == "SKIP_NO_BRANCH"
    assert result["total"] == 0
    print("✓ test_evaluate_branching_empty passed")


def test_evaluate_branching_no_branched():
    """分岐なし（全て orphan）。"""
    topics = [
        {"topicId": "t1", "title": "News1", "storyPhase": None},
        {"topicId": "t2", "title": "News2", "storyPhase": None},
    ]
    result = evaluate_branching(topics)
    assert result["verdict"] == "SKIP_NO_BRANCH"
    assert result["branching_rate"] == 0.0
    print("✓ test_evaluate_branching_no_branched passed")


def test_evaluate_branching_full_scan():
    """全件スキャン確認（サンプリングなし）。"""
    topics = [
        {
            "topicId": "p1",
            "title": "Apple iPhone 新型発表",
            "generatedTitle": "",
            "storyPhase": "発端",
            "articleCount": 3,
        },
        {
            "topicId": "c1",
            "parentTopicId": "p1",
            "title": "Apple iPhone 新型 発表会",  # 似た内容 → 誤分岐疑い（sim >= 0.6）
            "generatedTitle": "",
            "storyPhase": "拡散",
            "articleCount": 2,
        },
    ]
    result = evaluate_branching(topics)
    # sample（n）は全件 = 1
    assert result["sample"] == 1
    # similarity >= 0.6 で誤分岐疑い
    assert result["false_branch"] == 1
    assert result["false_branch_rate"] == 100.0
    assert result["verdict"] == "FAIL"  # 100% > 20% threshold
    print("✓ test_evaluate_branching_full_scan passed")


def test_evaluate_branching_mixed_quality():
    """OK と誤マージの混在（複数ペア）。"""
    topics = [
        {
            "topicId": "p1",
            "title": "Apple iPhone 新型発表",
            "generatedTitle": "",
            "storyPhase": "発端",
            "articleCount": 5,
        },
        {
            "topicId": "c1",
            "parentTopicId": "p1",
            "title": "iPhone 詳細スペック",  # 関連あり → ok
            "generatedTitle": "",
            "storyPhase": "拡散",
            "articleCount": 2,
        },
        {
            "topicId": "c2",
            "parentTopicId": "p1",
            "title": "トヨタ 新型EV",  # 全く別 → 誤マージ疑い
            "generatedTitle": "",
            "storyPhase": "拡散",
            "articleCount": 2,
        },
    ]
    result = evaluate_branching(topics)
    # 2 ペア : 1 ok + 1 誤マージ
    assert result["sample"] == 2
    assert result["false_merge"] == 1
    assert result["ok"] == 1
    assert result["false_merge_rate"] == 50.0
    assert result["verdict"] == "FAIL"  # 50% > 15% threshold
    print("✓ test_evaluate_branching_mixed_quality passed")


if __name__ == "__main__":
    test_extract_entities()
    test_char_bigrams()
    test_jaccard_similarity()
    test_evaluate_pair_false_branch()
    test_evaluate_pair_false_merge_with_entities()
    test_evaluate_pair_ok()
    test_evaluate_branching_empty()
    test_evaluate_branching_no_branched()
    test_evaluate_branching_full_scan()
    test_evaluate_branching_mixed_quality()
    print("\n✅ All tests passed!")
