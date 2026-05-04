"""
ソースフィルタリングモジュール (Step 6 S2.5)

目的: チャプター生成前に記事の品質・重複・偏りをフィルタして
     Claude API のコストを削減しながら情報の質を上げる。

設計意図: docs/decisions/001-source-filtering.md を参照。
"""
from __future__ import annotations

import json
import os
import re
from urllib.parse import urlparse


_DEFAULT_POLICY = {
    'tiers': {'A': [], 'B': []},
    'summarize_tiers': ['A', 'B'],
    'max_articles_per_source': 2,
    'min_content_length': 100,
    'dedup_syndicated': True,
    'syndicated_patterns': ['によると', '（共同）', '（ロイター）', '（AP）', '（時事）', 'が報じた'],
}

# source-policy.json のデフォルト探索パス（Lambda デプロイ時は /var/task/ 以下）
_POLICY_SEARCH_PATHS = [
    os.path.join(os.path.dirname(__file__), '..', '..', 'source-policy.json'),
    os.path.join(os.path.dirname(__file__), 'source-policy.json'),
    '/var/task/source-policy.json',
]


def load_source_policy(policy_path: str | None = None) -> dict:
    """source-policy.json を読み込む。ファイルがなければデフォルトを返す。"""
    candidates = [policy_path] if policy_path else _POLICY_SEARCH_PATHS
    for path in candidates:
        if path and os.path.isfile(path):
            try:
                with open(path, encoding='utf-8') as f:
                    data = json.load(f)
                merged = dict(_DEFAULT_POLICY)
                merged.update({k: v for k, v in data.items() if not k.startswith('_')})
                return merged
            except Exception as e:
                print(f'[proc_sources] source-policy.json 読み込み失敗 ({path}): {e}')
    return dict(_DEFAULT_POLICY)


def _domain_of(url: str) -> str:
    """URL からドメインを取得する。失敗時は空文字列。"""
    try:
        return urlparse(url).netloc.lower().lstrip('www.')
    except Exception:
        return ''


def _tier_of(article: dict, policy: dict) -> str | None:
    """記事の source/URL からティアを判定する。A/B/None を返す。"""
    domain = _domain_of(article.get('url', ''))
    source = (article.get('source') or '').lower()
    tiers = policy.get('tiers', {})
    for tier_name in ('A', 'B'):
        for entry in tiers.get(tier_name, []):
            if entry in domain or entry in source:
                return tier_name
    return None


def detect_syndicated(article: dict) -> bool:
    """転載記事を検出する。

    タイトル・本文冒頭・ソース名に「〇〇によると」「（共同）」「（ロイター）」等のパターンがあれば True。
    チェック対象: title, snippet, source フィールド（冒頭チェックはタイトルのみ）。
    """
    patterns = _DEFAULT_POLICY['syndicated_patterns']
    title = article.get('title') or ''
    source = article.get('source') or ''
    snippet = article.get('snippet') or article.get('content') or ''

    text_to_check = title + '　' + source + '　' + snippet[:200]
    for pat in patterns:
        if pat in text_to_check:
            return True
    return False


def deduplicate_articles(articles: list[dict]) -> list[dict]:
    """同内容の記事を重複除去する。

    同一タイトルの記事が複数ある場合、ソースティア（A > B > None）が高い記事を優先し、
    同ティアなら文字数（content/snippet）が多い記事を選ぶ。
    """
    if not articles:
        return []

    # タイトルの正規化（記号・空白除去）で同一性を判定
    def _normalize_title(t: str) -> str:
        return re.sub(r'[\s　「」『』【】〔〕（）()・\-—─―]+', '', t).lower()

    _TIER_RANK = {'A': 2, 'B': 1, None: 0}
    policy = load_source_policy()

    seen: dict[str, dict] = {}
    for a in articles:
        key = _normalize_title(a.get('title') or '')
        if not key:
            continue
        if key not in seen:
            seen[key] = a
        else:
            existing = seen[key]
            existing_tier = _TIER_RANK[_tier_of(existing, policy)]
            new_tier = _TIER_RANK[_tier_of(a, policy)]
            existing_len = len(existing.get('content') or existing.get('snippet') or existing.get('title') or '')
            new_len = len(a.get('content') or a.get('snippet') or a.get('title') or '')
            if new_tier > existing_tier or (new_tier == existing_tier and new_len > existing_len):
                seen[key] = a

    # 元の順序を保持しつつ重複除去（最初に出現した URL のポジションを維持）
    result = []
    kept_keys: set[str] = set()
    for a in articles:
        key = _normalize_title(a.get('title') or '')
        if not key:
            result.append(a)
            continue
        if key not in kept_keys and seen.get(key) is a:
            kept_keys.add(key)
            result.append(a)
    return result


def filter_articles(articles: list[dict], policy: dict) -> dict:
    """記事リストをフィルタして使用する記事を選択する。

    Returns:
        {
            "selected": [...],       チャプター生成に使う記事
            "rejected": [...],       弾いた記事（reason 付き）
            "single_source": bool,   1ソースのみの場合 True
            "summary": str           フィルタ結果のサマリーログ用文字列
        }
    """
    selected = []
    rejected = []

    max_per_source: int = policy.get('max_articles_per_source', 2)
    min_length: int = policy.get('min_content_length', 100)
    dedup_syndicated: bool = policy.get('dedup_syndicated', True)

    # Step1: 転載除去（フラグがある記事を弾く、ただし同一パターンで唯一の記事なら残す）
    if dedup_syndicated:
        syndicated = [a for a in articles if detect_syndicated(a)]
        non_syndicated = [a for a in articles if not detect_syndicated(a)]
        # 転載元が存在しない（全記事が転載）場合は除外せず1件残す
        if non_syndicated:
            for a in syndicated:
                rejected.append({**a, '_reject_reason': 'syndicated'})
            working = non_syndicated
        else:
            working = articles[:1]
            for a in articles[1:]:
                rejected.append({**a, '_reject_reason': 'syndicated_all_kept_first'})
    else:
        working = list(articles)

    # Step2: 最小文字数フィルタ（title のみの記事でも title 文字数でチェック）
    length_filtered = []
    for a in working:
        text_len = len(a.get('content') or a.get('snippet') or a.get('title') or '')
        if text_len < min_length:
            rejected.append({**a, '_reject_reason': f'too_short:{text_len}'})
        else:
            length_filtered.append(a)
    working = length_filtered

    # Step3: タイトル重複除去（ティア優先）
    working = deduplicate_articles(working)

    # Step4: 同一ソース上限
    source_counts: dict[str, int] = {}
    for a in working:
        domain = _domain_of(a.get('url', '')) or (a.get('source') or 'unknown')
        count = source_counts.get(domain, 0)
        if count < max_per_source:
            source_counts[domain] = count + 1
            selected.append(a)
        else:
            rejected.append({**a, '_reject_reason': f'max_per_source:{domain}'})

    # single_source 判定：選択された記事のユニークドメイン数が 1 以下
    unique_domains = {
        _domain_of(a.get('url', '')) or (a.get('source') or 'unknown')
        for a in selected
    }
    single_source = len(unique_domains) <= 1 and len(selected) > 0

    summary = (
        f'before={len(articles)} after={len(selected)} '
        f'rejected={len(rejected)} single_source={single_source}'
    )

    return {
        'selected': selected,
        'rejected': rejected,
        'single_source': single_source,
        'summary': summary,
    }
