"""
scoring.py — トピック信頼性・スコア調整の純関数群

設計方針:
  副作用なし（S3/DynamoDB非依存）のため単体テスト可能。
  「嘘を判定する」のではなく「確実度の材料を可視化する」のみ。
"""
import json
import re
from collections import Counter

from config import (
    UNCERTAINTY_PATTERNS, TIER_WEIGHTS,
    TECH_NICHE_KEYWORDS, TECH_GENERAL_KEYWORDS,
    S3_BUCKET, s3,
)


def detect_uncertainty(text: str) -> str:
    """
    記事テキストから不確実表現を検出し信頼性ラベルを返す。
    戻り値: 'unverified' | 'uncertain' | 'stated'
    """
    if not text:
        return 'stated'
    matches = sum(1 for pat in UNCERTAINTY_PATTERNS if re.search(pat, text))
    if matches >= 3:
        return 'unverified'
    if matches >= 1:
        return 'uncertain'
    return 'stated'


def calc_topic_reliability(articles: list) -> str:
    """トピック内全記事のreliabilityを集計してトピック全体の信頼性を返す。"""
    if not articles:
        return 'stated'
    labels = []
    for a in articles:
        text = (a.get('title', '') or '') + ' ' + (a.get('description', '') or '')
        labels.append(detect_uncertainty(text))
    unverified_count = labels.count('unverified')
    uncertain_count  = labels.count('uncertain') + unverified_count
    total = len(labels)
    if unverified_count > total * 0.4:
        return 'unverified'
    if uncertain_count > total * 0.5:
        return 'uncertain'
    return 'stated'


def detect_numeric_conflict(articles: list) -> bool:
    """
    同一トピック内記事で数値が2倍以上乖離している場合にTrueを返す。
    「情報に食い違いの可能性がある」を示すのみ（真偽判定はしない）。
    """
    num_pattern = re.compile(r'(\d[\d,，.．]*)\s*(?:人|名|億|万|千|百|円|ドル|%|％|kg|km)')
    all_nums = []
    for a in articles:
        text = a.get('title', '') or ''
        for m in num_pattern.finditer(text):
            raw = m.group(1).replace(',', '').replace('，', '').replace('.', '').replace('．', '')
            try:
                all_nums.append(float(raw))
            except ValueError:
                pass
    if len(all_nums) < 2:
        return False
    max_val, min_val = max(all_nums), min(all_nums)
    return min_val > 0 and max_val / min_val >= 2.0


def apply_tier_and_diversity_scoring(articles: list, velocity_score: float) -> float:
    """
    ソースtier重み・集中ペナルティ・多様性ボーナスをvelocityScoreに適用する。
      - Tier重み平均を乗算
      - 1社60%超 → ×0.8（ソース集中ペナルティ）
      - ユニークソース4社以上 → ×1.1（多様性ボーナス）
    """
    if not articles:
        return velocity_score

    tier_mults = [TIER_WEIGHTS.get(a.get('tier', 3), 0.8) for a in articles]
    velocity_score = round(velocity_score * (sum(tier_mults) / len(tier_mults)), 4)

    sources = [a.get('source', '') for a in articles if a.get('source')]
    if sources:
        top_ratio = Counter(sources).most_common(1)[0][1] / len(sources)
        if top_ratio > 0.6:
            velocity_score = round(velocity_score * 0.8, 4)

    if len({a.get('source', '') for a in articles if a.get('source')}) >= 4:
        velocity_score = round(velocity_score * 1.1, 4)

    return velocity_score


def apply_tech_audience_filter(topic_title: str, topic_summary: str, genre: str, velocity: float) -> float:
    """
    テック記事の一般向け度でvelocityScoreを調整する。
      - 一般向けキーワードあり → そのまま
      - ニッチキーワードあり   → ×0.3
      - どちらでもない         → ×0.7
    """
    if genre != 'テクノロジー':
        return velocity

    text = f"{topic_title} {topic_summary or ''}"
    if any(kw in text for kw in TECH_GENERAL_KEYWORDS):
        return velocity
    if any(kw in text for kw in TECH_NICHE_KEYWORDS):
        print(f'テックニッチフィルター適用（×0.3）: {topic_title[:40]}')
        return round(velocity * 0.3, 4)
    print(f'テック一般度不明フィルター適用（×0.7）: {topic_title[:40]}')
    return round(velocity * 0.7, 4)


def record_filter_feedback(decisions: list, ts_key: str) -> None:
    """
    フィルター判定ログを S3 に保存する（1実行 = 1ファイル）。
    保存先: api/filter-feedback/{ts_key}.json
    lifecycle Lambda が週次で集計し filter-weights.json を更新する予定。
    """
    if not decisions or not S3_BUCKET:
        return
    try:
        key = f'api/filter-feedback/{ts_key}.json'
        body = json.dumps(
            {'runAt': ts_key, 'count': len(decisions), 'decisions': decisions},
            ensure_ascii=False,
        ).encode('utf-8')
        s3.put_object(Bucket=S3_BUCKET, Key=key, Body=body,
                      ContentType='application/json', CacheControl='no-cache')
        print(f'フィルターフィードバック記録: {len(decisions)}件 → {key}')
    except Exception as e:
        print(f'フィルターフィードバック記録エラー: {e}')
