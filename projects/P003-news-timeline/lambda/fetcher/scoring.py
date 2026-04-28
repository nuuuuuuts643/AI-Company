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
from score_utils import (
    _get_domain, _domain_in_cat,
    _MEDIA_CAT_A, _MEDIA_CAT_B, _MEDIA_CAT_C,
    is_primary_source,
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
    ソースtier重み・集中ペナルティ・メディアカテゴリ多様性をvelocityScoreに適用する。
      - Tier重み平均を乗算
      - 1社60%超 → ×0.8（ソース集中ペナルティ）
      - ユニークソース4社以上 → ×1.1（多様性ボーナス）
      - カテゴリA(公共放送)あり → ×1.5
      - カテゴリB(全国紙)2社以上 → ×1.3
      - A+B 3媒体以上 → ×1.1 追加
      - テックメディアのみ → ×0.6
      - 一次情報URL(政府・主要通信社等)を含む → ×1.2（T2026-0428-AN）
        ※ source 名文字列ではなく URL ドメインで判定（偽装防止）
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

    # メディアカテゴリ多様性ボーナス
    domains = {_get_domain(a.get('url', '')) for a in articles if a.get('url')}
    domains.discard('')
    cat_a = any(_domain_in_cat(d, _MEDIA_CAT_A) for d in domains)
    cat_b_domains = {d for d in domains if _domain_in_cat(d, _MEDIA_CAT_B)}
    cat_c_domains = {d for d in domains if _domain_in_cat(d, _MEDIA_CAT_C)}
    other_domains = domains - cat_c_domains

    if not cat_a and not cat_b_domains and cat_c_domains and not other_domains:
        velocity_score = round(velocity_score * 0.6, 4)
    else:
        if cat_a:
            velocity_score = round(velocity_score * 1.5, 4)
        if len(cat_b_domains) >= 2:
            velocity_score = round(velocity_score * 1.3, 4)
        ab_count = (1 if cat_a else 0) + len(cat_b_domains)
        if ab_count >= 3:
            velocity_score = round(velocity_score * 1.1, 4)

    # T2026-0428-AN: 一次情報源(URL ドメイン判定)が1記事でも含まれていれば追加ボーナス
    # is_primary_source は URL 不正/None で False を返すため安全（偽装は弾く）
    if any(is_primary_source(a.get('url')) for a in articles):
        velocity_score = round(velocity_score * 1.2, 4)

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
