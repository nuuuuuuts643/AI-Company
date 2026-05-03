import json
import os
import re
import time
import unicodedata
import urllib.request
import boto3
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from decimal import Decimal

# T2026-0502-SEC13/SEC14 (2026-05-02): SSRF + XXE 防御ヘルパ
from url_safety import is_safe_url, parse_xml_safely

from config import (
    SLACK_WEBHOOK, S3_BUCKET,
    RSS_FEEDS, SNAP_TTL_DAYS, table, INACTIVE_LIFECYCLE_STATUSES, s3,
    SOURCE_TIER_MAP,
)
from filters import (
    _DIGEST_SKIP_PATS, load_filter_weights,
    _apply_secondary_penalty, is_blocked_domain,
)
from scoring import (
    calc_topic_reliability, detect_numeric_conflict,
    apply_tier_and_diversity_scoring, apply_tech_audience_filter,
    record_filter_feedback,
)
from cluster_utils import topic_fingerprint, cluster
from ai_merge_judge import AIMergeJudge
from merge_audit import MergeAuditor, detect_mismerge_signals
from score_utils import (
    calc_score, calc_velocity_score, apply_time_decay, apply_velocity_decay,
    source_diversity_score, compute_lifecycle_status,
    sort_by_pubdate, _parse_pubdate_ts,
    is_primary_source,
)
from text_utils import (
    dominant_genres, dominant_lang, override_genre_by_title,
    extract_source_name, extract_rss_image,
    extract_trending_keywords,
    extract_entities, extract_merge_entities,
    find_related_topics, detect_topic_hierarchy,
    extractive_title, extractive_summary, is_extractive_summary,
    strip_title_markdown, hierarchy_aware_overlap,
)
from storage import (
    write_s3, get_all_topics, get_topic_detail,
    recent_counts, calc_velocity, validate_topics_exist,
    load_seen_articles, save_seen_articles,
    generate_rss, generate_sitemap, get_latest_snap_articles,
)


_RSS10_NS = 'http://purl.org/rss/1.0/'
_DC_NS    = 'http://purl.org/dc/elements/1.1/'


def _dynamo_safe(obj):
    """DynamoDB は float 非対応のため再帰的に float → Decimal 変換する。
    外部から持ち込まれる float（mismergeDetail.maxGapDays / S3読み込み後の数値等）を
    一括ガードする。add-hoc な個別修正より層防御として DynamoDB 書き込みパスに置く。
    """
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _dynamo_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_dynamo_safe(v) for v in obj]
    return obj


def _parse_rss_items(root):
    """RSS 2.0 と RSS 1.0(RDF) の両方に対応してアイテムリストを返す。"""
    # RSS 2.0: 名前空間なし
    items = root.findall('.//item')
    if items:
        return items, False  # (items, is_rdf)
    # RSS 1.0 (RDF): {http://purl.org/rss/1.0/}item
    items = root.findall(f'.//{{{_RSS10_NS}}}item')
    return items, True


def fetch_rss(feed):
    articles = []
    url, genre, lang = feed['url'], feed['genre'], feed.get('lang', 'ja')
    feed_tier = feed.get('tier', 3)
    # T2026-0502-SEC13: SSRF 防御 — RSS_FEEDS は curated だが defense in depth
    safe, reason = is_safe_url(url)
    if not safe:
        print(f'[SEC13] fetch_rss blocked: {url} ({reason})')
        return articles
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Flotopic/1.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read()
        # T2026-0502-SEC14: XXE / billion laughs 防御
        root = parse_xml_safely(content)
        items, is_rdf = _parse_rss_items(root)
        for item in items:
            if is_rdf:
                title   = (item.findtext(f'{{{_RSS10_NS}}}title') or '').strip()
                link    = (item.findtext(f'{{{_RSS10_NS}}}link')  or '').strip()
                pubdate = (item.findtext(f'{{{_DC_NS}}}date')     or '').strip()
                raw_desc = (item.findtext(f'{{{_RSS10_NS}}}description') or
                            item.findtext('description') or '').strip()
            else:
                title    = (item.findtext('title')   or '').strip()
                link     = (item.findtext('link')     or '').strip()
                pubdate  = (item.findtext('pubDate')  or '').strip()
                raw_desc = (item.findtext('description') or '').strip()
            # HTMLタグ除去・ノイズ除去・200字に切り詰め
            desc = re.sub(r'<[^>]+>', '', raw_desc).strip()
            desc = re.sub(r'\s+', ' ', desc)
            # タイトルと同一 or 「続きを読む」系の無意味な説明は捨てる
            if desc and (desc == title or len(desc) < 30 or
                         re.search(r'続きを読|全文表示|もっと見る|記事全文|詳しくは', desc)):
                desc = ''
            desc = desc[:200]
            img = extract_rss_image(item)
            if title and link:
                if is_blocked_domain(link):
                    continue
                if any(p.search(title) for p in _DIGEST_SKIP_PATS):
                    continue
                source_name   = extract_source_name(item, link, url)
                resolved_tier = SOURCE_TIER_MAP.get(source_name, feed_tier)
                # T2026-0428-AN: 一次情報源は URL ドメインで物理判定（source 名偽装対策）
                is_primary = is_primary_source(link)
                a = {
                    'title':        title, 'url': link,
                    'pubDate':      pubdate, 'genre': genre,
                    'lang':         lang,
                    'source':       source_name,
                    'imageUrl':     img,
                    'published_ts': _parse_pubdate_ts(pubdate),
                    'tier':         resolved_tier,
                    'isPrimary':    is_primary,
                }
                if desc:
                    a['description'] = desc
                articles.append(a)
    except Exception as e:
        print(f'RSS error [{url}]: {e}')
    return articles


def fetch_ogp_image(url):
    # T2026-0502-SEC13: SSRF 防御
    safe, reason = is_safe_url(url)
    if not safe:
        print(f'[SEC13] fetch_ogp_image blocked: {url} ({reason})')
        return None
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Flotopic/1.0'})
        with urllib.request.urlopen(req, timeout=2) as resp:
            html = resp.read(16384).decode('utf-8', errors='ignore')
        m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
        if m: return m.group(1)
        m = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html, re.I)
        if m: return m.group(1)
    except Exception:
        pass
    return None


def find_trending_spikes(groups_meta_list):
    spikes = []
    for articles, tid, cnt, hist_with_ts in groups_meta_list:
        if cnt < 5 or not hist_with_ts:
            continue
        prev_counts = [c for c, _ in hist_with_ts]
        avg_prev = sum(prev_counts) / len(prev_counts)
        if avg_prev > 0 and cnt > 3 * avg_prev:
            spikes.append({'title': articles[0]['title'], 'count': cnt, 'avg_prev': avg_prev})
    return spikes


def post_slack_spike(spikes):
    if not SLACK_WEBHOOK or not spikes:
        return
    message = '\n'.join(
        '\U0001f525 急上昇トピック検出: ' + s['title'] + ' (' + str(s['count']) + '件)'
        for s in spikes
    )
    try:
        body = json.dumps({'text': message}).encode('utf-8')
        req = urllib.request.Request(
            SLACK_WEBHOOK, data=body,
            headers={'Content-Type': 'application/json'}, method='POST',
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
        print(f'Slack spike alert sent: {len(spikes)}件')
    except Exception as e:
        print(f'Slack spike alert error: {e}')


def calc_status(history_with_ts, current):
    counts = list(reversed([c for c, _ in history_with_ts])) + [current]
    if len(counts) < 2:
        return 'rising'
    diff = counts[-1] - counts[0]
    count_diff_recent = current - history_with_ts[0][0] if history_with_ts else diff
    if diff > 0 or count_diff_recent > 0:
        return 'rising'
    if diff < -1:
        return 'declining'
    return 'peak'


def _prefetch_group(tid):
    """DynamoDB から hist と既存 META を同時取得。"""
    hist     = recent_counts(tid)
    existing = table.get_item(Key={'topicId': tid, 'SK': 'META'}).get('Item', {})
    return hist, existing


# T2026-0428-E2-3: title 重複による tid 分裂を解消するための正規化キー。
# proc_storage.py の `_dedup_topics`/`_core_key` と整合させた最小集合。
_TITLE_DEDUP_PUNCT_RE = re.compile(r'[「」【】・、。,!?！？\[\]()（）『』""\'\'#＃\s　]+')
_TITLE_DEDUP_LIVE_PREFIX_RE = re.compile(r'^(中継|速報|更新|独自|詳報|続報|緊急|号外)\s*')


def _title_dedup_key(title: str) -> str:
    """generatedTitle / title の正規化キーを返す。空文字は ''。

    T2026-0430-L: NFKC 正規化を追加。
    `米ＧＤＰ` (全角) と `米GDP` (半角) を同一キーに揃え、半角/全角差で
    別 tid が生まれるのを防ぐ。
    """
    if not title:
        return ''
    s = unicodedata.normalize('NFKC', str(title))
    s = s.lower()
    s = _TITLE_DEDUP_PUNCT_RE.sub('', s)
    s = _TITLE_DEDUP_LIVE_PREFIX_RE.sub('', s)
    return s[:18]


# T2026-0430-L: title 完全一致 dedup を超える Jaccard 類似度マージ。
# 「米GDP速報値2.0%増 1〜3月期」 vs 「米GDP年率2.0%増 4四半期連続のプラス成長」
# のような同イベントの異なる切り口を既存 AI topic に紐付ける。
#
# T2026-0501-H: マージ判定に「エンティティ重複必須」ゲート + borderline Haiku 判定を追加。
#   - 共有エンティティ無し                            → Jaccard に関わらず別事件 (例: 米国 vs 日本)
#   - 共有エンティティあり + Jaccard >= 0.35           → マージ
#   - 共有エンティティあり + 0.15 <= Jaccard < 0.35    → Haiku に「同一事件か」問う
#   - その他                                          → 別トピック
#   失敗時 / API key 未設定は failsafe = "別トピック" (現状挙動と同等)
_JACCARD_TITLE_THRESHOLD = 0.35  # cluster_utils と同じ閾値
_JACCARD_BORDERLINE_LOW = 0.15  # T2026-0501-H: borderline 下限 (T2026-0502-COST: 0.10→0.15 戻し・Haiku 呼び出しが pairs ~1100/run に膨らみ月$380追加→品質効果未検証のため戻す。within-run dedup と entity guard は維持)
_JACCARD_RECENT_TOPICS_MAX = 500  # T2026-0501-H: 14d→30d lookback 拡張に合わせて 200→500
_TID_COLLISION_LOOKBACK_DAYS = 30  # T2026-0501-H: 14→30 で継続イベントの再分裂を抑える


def _title_bigrams(title: str) -> frozenset:
    """タイトルから bigram set を返す。NFKC 正規化 + 句読点除去後に作る。"""
    if not title:
        return frozenset()
    s = unicodedata.normalize('NFKC', str(title)).lower()
    s = _TITLE_DEDUP_PUNCT_RE.sub('', s)
    s = _TITLE_DEDUP_LIVE_PREFIX_RE.sub('', s)
    if len(s) < 2:
        return frozenset()
    return frozenset(s[i:i+2] for i in range(len(s) - 1))


def _jaccard_title_sim(a: str, b: str) -> float:
    """2 つのタイトルの bigram Jaccard 類似度。0.0〜1.0。"""
    bg_a = _title_bigrams(a)
    bg_b = _title_bigrams(b)
    if not bg_a or not bg_b:
        return 0.0
    inter = bg_a & bg_b
    union = bg_a | bg_b
    if not union:
        return 0.0
    return len(inter) / len(union)


def _resolve_tid_collisions_by_title(group_tids, existing_topics, ai_judge=None, auditor=None):
    """title 完全一致で既存 tid に再バインドし、同 run 内 tid 衝突 group をマージする。

    背景:
      `topic_fingerprint(g)` はクラスタ内 top-5 単語に依存するため、RSS 記事構成が
      変わると同一イベントでも別 tid を生成する (本番計測 2026-04-29 PO調査:
      828 トピック中 343 件 = 41.43% が完全同一 title で別 tid に分裂)。

    解決:
      毎 run 頭で取得した `existing_topics` (S3 topics.json 由来 = active/cooling のみ)
      を直近 30 日のものだけ filter し、title / generatedTitle の正規化キー →
      tid マップを構築する。新規 group の `extractive_title(g)` がキー一致したら、
      `topic_fingerprint` で生まれた新 tid を破棄して既存 tid を採用する。

    T2026-0501-H マージゲート (PO 指示「混入 > 分裂」):
      1. **エンティティ重複必須**: 候補 group と既存 AI topic のタイトル両方から
         `extract_merge_entities` で固有名詞 (人名/組織/地名/カタカナ語/英大文字 etc) を
         抽出し、重複が無ければマージ対象から除外する。
         例: 「関税引き上げ 米国」vs「関税引き上げ 日本」は別事件 → エンティティ重複なし。
      2. 共有エンティティあり + Jaccard >= 0.35  → マージ (rebound_jaccard)
      3. 共有エンティティあり + 0.15 <= Jac < 0.35 → Haiku に同一事件か判定 (rebound_haiku)
      4. それ以外                                  → 別トピック維持
      `ai_judge` が None または API key 未設定なら 3 はスキップして 2 のみ動作 (failsafe)。
    """
    if not existing_topics or not group_tids:
        return group_tids

    now_ts = int(time.time())
    cutoff_ts = now_ts - _TID_COLLISION_LOOKBACK_DAYS * 86400
    title_to_tid = {}
    # T2026-0430-L: AI 生成済 active topic を Jaccard fallback の候補として保持。
    # (tid, title, ts) の tuple list。直近の AI topic を優先するため
    # lastArticleAt 降順で _JACCARD_RECENT_TOPICS_MAX 件に絞る。
    ai_topic_candidates: list = []
    for t in existing_topics:
        tid_e = t.get('topicId', '')
        if not tid_e:
            continue
        if t.get('lifecycleStatus') in INACTIVE_LIFECYCLE_STATUSES:
            continue
        last = int(t.get('lastArticleAt', 0) or 0)
        if not last or last < cutoff_ts:
            continue
        for src_title in (t.get('title'), t.get('generatedTitle')):
            norm = _title_dedup_key(src_title)
            if norm and norm not in title_to_tid:
                title_to_tid[norm] = tid_e
        if t.get('aiGenerated'):
            # T2026-0501-M: generatedTitle と raw title 両方を候補に追加。
            # extractive_title(new cluster) は生の記事見出しなので raw title との
            # bigram Jaccard の方が generatedTitle より高くなる場合がある。
            for cand_title in dict.fromkeys(filter(None, [t.get('generatedTitle'), t.get('title')])):
                ai_topic_candidates.append((tid_e, cand_title, last))

    if not title_to_tid and not ai_topic_candidates:
        return group_tids

    ai_topic_candidates.sort(key=lambda x: x[2], reverse=True)
    ai_topic_candidates = ai_topic_candidates[:_JACCARD_RECENT_TOPICS_MAX]
    # T2026-0501-H: bigram と entity を事前計算 (タイトル別 1 回のみ)
    ai_topic_meta = [
        (tid_e, ttl, _title_bigrams(ttl), extract_merge_entities(ttl))
        for tid_e, ttl, _ in ai_topic_candidates
    ]

    rebound = 0
    rebound_jaccard = 0
    rebound_haiku = 0
    skipped_no_entity = 0
    # 第 1 パス: 完全一致 / Jaccard>=0.35 を確定し、borderline 候補を集める。
    resolved: list = []
    borderline_queue: list = []  # [(group_idx, candidate_title, cand_entities, [(tid_e, sim, ttl, ents)])]
    for idx, (g, tid) in enumerate(group_tids):
        candidate = extractive_title(g) or (g[0].get('title', '') if g else '')
        norm = _title_dedup_key(candidate)
        target = title_to_tid.get(norm)
        if target and target != tid:
            resolved.append((g, target, idx))
            rebound += 1
            if auditor is not None:
                auditor.log(
                    target_tid=target, source_tid=tid,
                    jaccard=1.0,
                    entity_overlap=sorted(extract_merge_entities(candidate)),
                    haiku_used=False, haiku_verdict='skipped',
                    confidence='low', title_a=candidate, title_b=candidate,
                )
            continue
        if not ai_topic_meta or not candidate:
            resolved.append((g, tid, idx))
            continue
        cand_bg = _title_bigrams(candidate)
        if not cand_bg:
            resolved.append((g, tid, idx))
            continue
        cand_entities = extract_merge_entities(candidate)
        # 全候補を走査。 entity 重複あり + jac >= 0.35 を最優先。
        # entity 重複あり + 0.15 <= jac < 0.35 を borderline 候補として収集。
        best_hard_tid = None
        best_hard_sim = 0.0
        borderline_cands: list = []
        for tid_e, ttl, ttl_bg, ttl_ents in ai_topic_meta:
            if not ttl_bg:
                continue
            inter = cand_bg & ttl_bg
            if not inter:
                continue
            union = cand_bg | ttl_bg
            if not union:
                continue
            sim = len(inter) / len(union)
            if sim < _JACCARD_BORDERLINE_LOW:
                continue
            shared_ents = hierarchy_aware_overlap(cand_entities, ttl_ents)
            if not shared_ents:
                # entity 重複なし → マージ対象外
                if sim >= _JACCARD_TITLE_THRESHOLD:
                    skipped_no_entity += 1
                continue
            if sim >= _JACCARD_TITLE_THRESHOLD:
                if sim > best_hard_sim:
                    best_hard_sim = sim
                    best_hard_tid = tid_e
            else:
                borderline_cands.append((tid_e, ttl, ttl_ents, shared_ents, sim))
        if best_hard_tid and best_hard_tid != tid:
            resolved.append((g, best_hard_tid, idx))
            rebound_jaccard += 1
            # T2026-0501-H 監査ログ: 高 Jaccard + entity overlap の確定マージ
            if auditor is not None:
                # best_hard_* の元データを再取得 (entity overlap)
                _hard_ents = next(
                    (cand_entities & ttl_ents
                     for tid_e, _ttl, _bg, ttl_ents in ai_topic_meta if tid_e == best_hard_tid),
                    set()
                )
                _hard_title = next(
                    (ttl for tid_e, ttl, _bg, _ents in ai_topic_meta if tid_e == best_hard_tid),
                    ''
                )
                auditor.log(
                    target_tid=best_hard_tid, source_tid=tid,
                    jaccard=best_hard_sim,
                    entity_overlap=sorted(_hard_ents),
                    haiku_used=False, haiku_verdict='skipped',
                    confidence='high',
                    title_a=candidate, title_b=_hard_title,
                )
            continue
        if borderline_cands:
            # 最も類似度の高い候補のみ Haiku に問う (1 group につき 1 ペア)
            borderline_cands.sort(key=lambda x: x[4], reverse=True)
            tid_e, ttl, ttl_ents, shared_ents, sim = borderline_cands[0]
            borderline_queue.append({
                'group_idx': idx,
                'group': g,
                'orig_tid': tid,
                'cand_tid': tid_e,
                'jaccard': sim,
                'pair': {
                    'title_a': candidate,
                    'title_b': ttl,
                    'entities_a': sorted(cand_entities),
                    'entities_b': sorted(ttl_ents),
                    'shared_entities': sorted(shared_ents),
                },
            })
            resolved.append((g, tid, idx))  # 仮置き。後で書き換える。
        else:
            resolved.append((g, tid, idx))

    # 第 2 パス: borderline_queue を batch で Haiku に問う。
    if borderline_queue and ai_judge is not None:
        pairs = [b['pair'] for b in borderline_queue]
        judgments = ai_judge.judge_pairs(pairs)
        for b, p in zip(borderline_queue, pairs):
            k = (p['title_a'], p['title_b']) if p['title_a'] <= p['title_b'] else (p['title_b'], p['title_a'])
            same = bool(judgments.get(k))
            if same:
                # 同一事件と判定 → cand_tid に書き換える
                resolved[b['group_idx']] = (b['group'], b['cand_tid'], b['group_idx'])
                rebound_haiku += 1
            if auditor is not None:
                auditor.log(
                    target_tid=b['cand_tid'], source_tid=b['orig_tid'],
                    jaccard=b['jaccard'],
                    entity_overlap=p['shared_entities'],
                    haiku_used=True,
                    haiku_verdict='yes' if same else 'no',
                    confidence='medium' if same else 'low',
                    title_a=p['title_a'], title_b=p['title_b'],
                )

    if rebound:
        print(f'[title-dedup] {rebound}/{len(group_tids)} groups rebound to existing tids')
    if rebound_jaccard:
        print(f'[title-dedup-jaccard] {rebound_jaccard}/{len(group_tids)} groups merged into AI topics by Jaccard>={_JACCARD_TITLE_THRESHOLD} + entity overlap')
    if rebound_haiku:
        print(f'[title-dedup-haiku] {rebound_haiku}/{len(group_tids)} borderline groups merged after Haiku same-event judgment')
    if skipped_no_entity:
        print(f'[title-dedup-skip] {skipped_no_entity} high-Jaccard groups skipped due to entity mismatch (e.g. 米国 vs 日本)')

    by_tid: dict = {}
    order: list = []
    for g, tid, _idx in resolved:
        if tid in by_tid:
            existing_g = by_tid[tid]
            seen_urls = {a.get('url') for a in existing_g if a.get('url')}
            for a in g:
                u = a.get('url')
                if u and u not in seen_urls:
                    existing_g.append(a)
                    seen_urls.add(u)
        else:
            by_tid[tid] = list(g)
            order.append(tid)
    merged = len(resolved) - len(by_tid)
    if merged:
        print(f'[title-dedup] {merged} same-run groups merged into existing tids')
    return [(by_tid[tid], tid) for tid in order]


def _merge_within_run_duplicates(group_tids, existing_tids, ai_judge=None, auditor=None):
    """同一 run 内の新クラスタ同士を重複チェックしてマージする。

    T2026-0501-M: _resolve_tid_collisions_by_title は「新 vs 既存」を処理するが、
    同一 run で生まれた別クラスタ（例: 欧州米軍削減 vs ドイツ米軍削減）は比較されない。
    この関数で「新 vs 新」の重複を検出して統合する。

    existing_tids: set of tids already in topics.json (these are already deduped, skip them)
    """
    if len(group_tids) < 2:
        return group_tids

    new_indices = [i for i, (_g, tid) in enumerate(group_tids) if tid not in existing_tids]
    if len(new_indices) < 2:
        return group_tids

    cands = []
    for i in new_indices:
        g, tid = group_tids[i]
        title = extractive_title(g) or (g[0].get('title', '') if g else '')
        bg = _title_bigrams(title)
        ents = extract_merge_entities(title)
        cands.append((i, g, tid, title, bg, ents))

    parent = {i: i for i, *_ in cands}
    cand_by_idx = {i: (g, tid, title, bg, ents) for i, g, tid, title, bg, ents in cands}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px == py:
            return
        # 記事数が多い方を root にする
        if len(cand_by_idx[px][0]) >= len(cand_by_idx[py][0]):
            parent[py] = px
        else:
            parent[px] = py

    borderline: list = []
    hard_merged = 0

    for a_pos, (i, _gi, _ti, title_i, bg_i, ents_i) in enumerate(cands):
        for b_pos in range(a_pos + 1, len(cands)):
            j, _gj, _tj, title_j, bg_j, ents_j = cands[b_pos]
            if find(i) == find(j):
                continue
            if not bg_i or not bg_j:
                continue
            inter = bg_i & bg_j
            if not inter:
                continue
            sim = len(inter) / len(bg_i | bg_j)
            if sim < _JACCARD_BORDERLINE_LOW:
                continue
            shared_ents = hierarchy_aware_overlap(ents_i, ents_j)
            if not shared_ents:
                continue
            if sim >= _JACCARD_TITLE_THRESHOLD:
                union(i, j)
                hard_merged += 1
                if auditor:
                    auditor.log(
                        target_tid=group_tids[find(i)][1], source_tid=group_tids[j][1],
                        jaccard=sim, entity_overlap=sorted(shared_ents),
                        haiku_used=False, haiku_verdict='skipped', confidence='high',
                        title_a=title_i, title_b=title_j,
                    )
            else:
                borderline.append({'i': i, 'j': j, 'sim': sim,
                                   'title_a': title_i, 'title_b': title_j,
                                   'entities_a': sorted(ents_i), 'entities_b': sorted(ents_j),
                                   'shared_entities': sorted(shared_ents)})

    haiku_merged = 0
    if borderline and ai_judge:
        pairs = [{'title_a': p['title_a'], 'title_b': p['title_b'],
                  'entities_a': p['entities_a'], 'entities_b': p['entities_b'],
                  'shared_entities': p['shared_entities']}
                 for p in borderline]
        judgments = ai_judge.judge_pairs(pairs)
        for p in borderline:
            key = ai_judge._key(p['title_a'], p['title_b'])
            if judgments.get(key):
                union(p['i'], p['j'])
                haiku_merged += 1

    total_merged = hard_merged + haiku_merged
    if total_merged == 0:
        return group_tids

    # Union-Find の結果を group_tids に反映: 非 root の記事を root にマージして削除
    result = list(group_tids)
    remove = set()
    for i, _g, _tid, *_ in cands:
        root = find(i)
        if root == i:
            continue
        root_articles = result[root][0]
        seen_urls = {a.get('url') for a in root_articles if a.get('url')}
        for a in result[i][0]:
            u = a.get('url')
            if u and u not in seen_urls:
                root_articles.append(a)
                seen_urls.add(u)
        remove.add(i)

    out = [(g, tid) for idx, (g, tid) in enumerate(result) if idx not in remove]
    print(f'[within-run-dedup] merged {total_merged} pairs '
          f'(hard={hard_merged} haiku={haiku_merged}): {len(group_tids)}→{len(out)} groups')
    return out


def _fetch_ogp_group(tid, urls):
    """複数 URL を順番に試して最初に取得できた OGP 画像を返す。"""
    for u in urls:
        img = fetch_ogp_image(u)
        if img:
            return tid, img
    return tid, None


def _topic_cluster_dedup(topics, auditor=None):
    """同一イベントが複数topicIdに分裂した場合に統合する二次dedup。
    タイトルに cluster() と同じ Jaccard 閾値(0.35)を適用し、
    類似クラスタ内は velocityScore 最大のトピックを残す。

    T2026-0501-H: cluster() でまとめられたグループ内で **entity 重複が無い**
    トピックは別事件として分離する (例: 「関税引き上げ 米国」と「関税引き上げ 日本」が
    Jaccard でクラスタ化されても entity 重複なしなら別トピックを維持)。
    auditor が渡されればマージのたびに監査ログを残す。
    """
    if len(topics) < 2:
        return topics
    fake = [
        {'title': (t.get('generatedTitle') or t.get('title', '')), '_idx': i}
        for i, t in enumerate(topics)
    ]
    groups = cluster(fake)
    result = []
    split_by_entity = 0
    for group in groups:
        if len(group) == 1:
            result.append(topics[group[0]['_idx']])
            continue
        group_topics = [topics[a['_idx']] for a in group]
        # T2026-0501-H entity gate: cluster 内で entity 重複が連結している部分のみマージ。
        # union-find で「entity 共有つながり」を求め、subgroup ごとに best を選ぶ。
        n = len(group_topics)
        parent = list(range(n))
        def _find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        ents_list = [
            extract_merge_entities(t.get('generatedTitle') or t.get('title', ''))
            for t in group_topics
        ]
        for i in range(n):
            for j in range(i + 1, n):
                if _find(i) == _find(j):
                    continue
                if ents_list[i] & ents_list[j]:
                    pi, pj = _find(i), _find(j)
                    parent[pi] = pj
        sub_groups: dict = {}
        for i in range(n):
            sub_groups.setdefault(_find(i), []).append(group_topics[i])
        if len(sub_groups) > 1:
            split_by_entity += len(sub_groups) - 1
        for sub in sub_groups.values():
            best = max(sub, key=lambda t: float(t.get('velocityScore', 0) or 0))
            merged_count = len(sub)
            if merged_count > 1:
                print(f'[dedup] 類似topicマージ {merged_count}件: {best.get("generatedTitle") or best.get("title", "")[:40]}')
                if auditor is not None:
                    target_tid = best.get('topicId', '')
                    target_ttl = best.get('generatedTitle') or best.get('title', '')
                    target_ents = extract_merge_entities(target_ttl)
                    for other in sub:
                        if other is best:
                            continue
                        other_tid = other.get('topicId', '')
                        other_ttl = other.get('generatedTitle') or other.get('title', '')
                        if not other_tid or other_tid == target_tid:
                            continue
                        auditor.log(
                            target_tid=target_tid, source_tid=other_tid,
                            jaccard=0.0,  # cluster() 経由なので個別 Jaccard 値を持たない
                            entity_overlap=sorted(target_ents & extract_merge_entities(other_ttl)),
                            haiku_used=False, haiku_verdict='skipped',
                            confidence='medium',
                            title_a=target_ttl, title_b=other_ttl,
                        )
            result.append(best)
    if split_by_entity:
        print(f'[dedup-entity-split] {split_by_entity} 件のクラスタを entity 重複なしで分離 (例: 米国 vs 日本)')
    return result


def lambda_handler(event, context):
    # Step 0: フィルター重みをS3から読み込む（コールド起動時のみ実行）
    load_filter_weights()

    # Step 1: 前回既知 URL を読み込む（差分更新用）
    seen_urls = load_seen_articles()

    # Step 2: 全 RSS フィードを並列取得
    all_articles = []
    with ThreadPoolExecutor(max_workers=15) as ex:
        fs = {ex.submit(fetch_rss, feed): feed for feed in RSS_FEEDS}
        for f in as_completed(fs):
            feed = fs[f]
            try:
                fetched = f.result()
                all_articles.extend(fetched)
                print(f'[{feed["genre"]}] {feed["url"].split("/")[2]}: {len(fetched)}件')
            except Exception as e:
                print(f'RSS error [{feed["url"]}]: {e}')

    print(f'合計: {len(all_articles)}記事')

    # Step 2.5: URL 重複除去（同一 URL が複数フィードから来るケース）
    # 例: Yahoo!ニュース が他媒体記事を再配信し、元媒体の RSS にも同 URL が載る。
    # この dedup を入れないと cluster 後の `cnt = len(g)` が水増しされ、
    # SNAP.articles は URL-dedup 済みなため、フロントの「全 X 件の記事」表示や
    # detail.js の記事数グラフ最終点と meta.articleCount が乖離する根本原因になる。
    # （T2026-0428-AI: 2026-04-28 PO報告「記事数グラフがトピック内記事数と合ってない」）
    _before = len(all_articles)
    _seen_url_local: set = set()
    deduped_articles = []
    for _a in all_articles:
        _u = _a.get('url')
        if not _u or _u in _seen_url_local:
            continue
        _seen_url_local.add(_u)
        deduped_articles.append(_a)
    if _before != len(deduped_articles):
        print(f'[URL-DEDUP] {_before} → {len(deduped_articles)} (フィード横断重複除去)')
    all_articles = deduped_articles

    # Step 3: 差分チェック
    current_urls = {a['url'] for a in all_articles}
    new_urls     = current_urls - seen_urls

    if seen_urls and not new_urls:
        print('新規記事なし。DynamoDB 呼び出しをスキップします。')
        save_seen_articles(current_urls)
        print('[FETCHER_HEALTH] ' + json.dumps({
            'event': 'fetcher_health',
            'status': 'run_complete',
            'saved_articles': 0,
            'new_topics': 0,
            'fetched': len(all_articles),
            'new_urls': 0,
            'skipped': True,
        }))
        return {'statusCode': 200,
                'body': json.dumps({'articles': len(all_articles), 'new': 0, 'skipped': True})}

    print(f'新規記事: {len(new_urls)}件 / 既知: {len(seen_urls)}件')

    _t_cluster = time.time()
    groups = cluster(all_articles)
    print(f'[TIMING] cluster: {time.time()-_t_cluster:.1f}s')
    print(f'トピック数: {len(groups)}')

    groups_sorted = sorted(groups, key=lambda g: len({a['source'] for a in g}) * 10, reverse=True)
    group_tids    = [(g, topic_fingerprint(g)) for g in groups_sorted]

    # T2026-0428-E2-3 / T2026-0501-H: title 重複による tid 分裂を解消する。
    # `topic_fingerprint` はクラスタ top-5 単語に依存するため、RSS 記事構成が
    # 変わると同一イベントでも別 tid を生成し、META 分裂が起きていた
    # (本番計測 2026-04-29: 343/828 = 41.43% が完全同一 title で別 tid)。
    # 既存 topics.json (active/cooling・直近 30 日 / lookback) を読み、title 完全一致 +
    # entity 重複 + Jaccard / Haiku 判定で既存 tid に再バインドする。
    # get_all_topics() は S3 topics.json を読むだけで DynamoDB scan しないため、
    # 後段の topics.json 構築との重複読みは S3 GET 1 回分の追加コストのみ。
    _existing_topics_for_dedup = get_all_topics() if S3_BUCKET else []
    # T2026-0501-H: borderline (Jaccard 0.15-0.35) ペアを Haiku に「同一事件か」問う。
    # API key 未設定 / 失敗時は failsafe で merge せず (= 現状挙動)。
    # T2026-0502-COST2 (2026-05-02 PO 指示「最小コスト構成へ」): env `AI_MERGE_ENABLED` で gate。
    # default=false → Haiku 呼び出しゼロ (月 ~$120 削減)。borderline ペアは failsafe=False で別事象判定に倒す。
    # PR #84/#118 で入れた false-split 統合 (例「欧州駐留米軍」vs「ドイツ駐留米軍」) の効果は
    # SLI 検証されないまま投入されたため、コスト正当化が出来るまで disable。
    from config import ANTHROPIC_API_KEY as _ANTHROPIC_API_KEY  # noqa: E402  (ローカル import で依存最小化)
    _AI_MERGE_ENABLED = os.environ.get('AI_MERGE_ENABLED', 'false').lower() == 'true'
    _ai_judge = AIMergeJudge(api_key=_ANTHROPIC_API_KEY) if (_ANTHROPIC_API_KEY and _AI_MERGE_ENABLED) else None
    if _ANTHROPIC_API_KEY and not _AI_MERGE_ENABLED:
        print('[ai_merge_judge] disabled by env AI_MERGE_ENABLED!=true (T2026-0502-COST2 最小コスト構成)')
    # T2026-0501-H: マージ監査ログ (S3 JSONL)。1 run 終わりに flush_to_s3() でまとめて書き込む。
    _merge_auditor = MergeAuditor(s3_client=s3 if S3_BUCKET else None, bucket=S3_BUCKET)
    group_tids = _resolve_tid_collisions_by_title(
        group_tids, _existing_topics_for_dedup,
        ai_judge=_ai_judge, auditor=_merge_auditor,
    )
    # T2026-0501-M: 新 vs 新クラスタの重複を検出してマージ（同一 run 内分裂対策）
    _existing_tids = {t.get('topicId') for t in _existing_topics_for_dedup if t.get('topicId')}
    group_tids = _merge_within_run_duplicates(
        group_tids, _existing_tids,
        ai_judge=_ai_judge, auditor=_merge_auditor,
    )

    # Step 4: DynamoDB（hist + META）を全グループ並列プリフェッチ
    _t_pre = time.time()
    prefetched = {}
    with ThreadPoolExecutor(max_workers=20) as ex:
        fs = {ex.submit(_prefetch_group, tid): tid for _, tid in group_tids}
        for f in as_completed(fs):
            tid = fs[f]
            try:
                prefetched[tid] = f.result()
            except Exception:
                prefetched[tid] = ([], {})
    print(f'[TIMING] prefetch {len(group_tids)}groups: {time.time()-_t_pre:.1f}s')

    # Step 5: OGP 画像が必要なグループを特定して並列取得（最大 20 件）
    ogp_candidates = []
    for g, tid in group_tids:
        _, existing = prefetched.get(tid, ([], {}))
        if existing.get('imageUrl') or any(a.get('imageUrl') for a in g):
            continue
        jp_urls    = [a['url'] for a in g if '.jp' in a.get('url', '')]
        check_urls = jp_urls[:2] + [a['url'] for a in g[:3] if a['url'] not in jp_urls]
        if check_urls:
            ogp_candidates.append((tid, check_urls[:3]))

    ogp_results = {}
    with ThreadPoolExecutor(max_workers=10) as ex:
        fs = [ex.submit(_fetch_ogp_group, tid, urls) for tid, urls in ogp_candidates[:20]]
        for f in as_completed(fs):
            try:
                tid, img = f.result()
                if img:
                    ogp_results[tid] = img
            except Exception:
                pass

    now    = datetime.now(timezone.utc)
    ts_key = now.strftime('%Y%m%dT%H%M%SZ')
    ts_iso = now.isoformat()

    saved_ids         = []
    current_run_metas = {}  # {tid: item} 今回のrunで書いたMETAアイテム
    groups_meta_list  = []
    all_filter_feedback: list = []  # フィルター判定ログ（実行終了後にS3へ書く）
    _dynamo_puts: list = []  # META+SNAPをバッファに溜めて後でバッチ並列書き込み

    # Step 6: メインループ（外部 I/O なし・DynamoDB はバッファに蓄積）
    _t_loop = time.time()
    for g, tid in group_tids:
        # new_urls との交差がないグループ（古い記事のみ）はスキップ
        # Union-Find 推移性による無関係記事の永続混入を防ぐ
        if not any(a['url'] in new_urls for a in g):
            continue
        cnt    = len(g)
        # T2026-0428-AK: 空トピック量産を物理的に防止する。
        # cluster_utils.cluster() は最小サイズ閾値なしで singleton(=1記事) クラスタも返す。
        # 旧実装は articleCount<2 トピックも DynamoDB に書き、UI 層 (L693-694) でフィルタしていた
        # → DynamoDB に articleCount<2 のゾンビメタが累積 (本番で 9680件 / 11882件)。
        # さらに lifecycle が detail JSON 欠損ゾンビを掃除しないため、UI で 11% の空トピックが発生。
        # 物理ゲート: ユニーク URL 2 件未満のクラスタは META/SNAP を書かない。
        # 既存ゾンビは lifecycle 側の articleCount<2 削除ロジックで除去する。
        unique_url_count = len({a['url'] for a in g if a.get('url')})
        if unique_url_count < 2:
            continue
        genres = dominant_genres(g)
        genre  = genres[0]
        forced_genre = override_genre_by_title(g)
        if forced_genre and forced_genre != genre:
            print(f'ジャンル上書き: {genre}→{forced_genre} ({g[0]["title"][:30]})')
            genre  = forced_genre
            genres = [forced_genre] + [x for x in genres if x != forced_genre][:1]
        lang   = dominant_lang(g)
        hist, existing = prefetched.get(tid, ([], {}))

        groups_meta_list.append((g, tid, cnt, hist))
        st             = calc_status(hist, cnt)
        score, media, hb = calc_score(g)

        last_article_ts  = max((a.get('published_ts', 0) for a in g), default=0)
        first_article_ts = int(existing.get('firstArticleAt') or
                               min((a.get('published_ts', 0) for a in g if a.get('published_ts')), default=0))
        score = apply_time_decay(score, last_article_ts)
        _div_mult = source_diversity_score(g)
        score = max(1, int(score * _div_mult))
        velocity_score  = calc_velocity_score(g)

        secondary_penalty, feedback_entries = _apply_secondary_penalty(g)
        if secondary_penalty < 1.0:
            score          = max(1, int(score * secondary_penalty))
            velocity_score = round(velocity_score * secondary_penalty, 4)
            print(f'二次情報フィルター適用: {g[0]["title"][:40]} (係数={round(secondary_penalty, 3)})')
            all_filter_feedback.extend(feedback_entries)

        # ソース品質評価: tier重み・ソース多様性・集中ペナルティを適用
        velocity_score = apply_tier_and_diversity_scoring(g, velocity_score)

        # 信頼性シグナル算出（断定せず「材料の可視化」のみ）
        reliability       = calc_topic_reliability(g)
        has_conflict      = detect_numeric_conflict(g)
        unique_src_count  = len({a.get('source', '') for a in g if a.get('source')})

        if existing.get('aiGenerated') and existing.get('generatedTitle'):
            gen_title = existing['generatedTitle']
        else:
            gen_title = existing.get('generatedTitle') or extractive_title(g)

        existing_summary  = existing.get('generatedSummary', '')
        # is_extractive_summary() で旧/現行両方の extractive パターンを検出する。
        # 旧 _is_old_extractive は「複数の報道」「関連して」のみ判定したので、現行
        # 「また、『…』など」「最新では…と報じられている」「（…ほかN件）」を素通りさせていた。
        # この素通りで「aiGenerated=None なのに extractive 出力が generatedSummary に入る」
        # 状態 (例: c1bbe0fe 12記事topic) が永続化されていた。
        _is_old_extractive = is_extractive_summary(existing_summary)
        if existing.get('aiGenerated') and existing_summary and not _is_old_extractive:
            gen_summary = existing_summary
        else:
            gen_summary = extractive_summary(g) if cnt >= 3 else None

        # テック記事の一般向けフィルター（ニッチ専門記事のスコアを下げる）
        velocity_score = apply_tech_audience_filter(
            gen_title or g[0]['title'],
            gen_summary or '',
            genre,
            velocity_score,
        )

        # 24h記事数差分計算（「昨日から+N件」カード表示用）
        _day_base_cnt = int(existing.get('articleCountDayBase', 0) or 0)
        _day_base_ts  = existing.get('articleCountDayBaseTs') or ''
        if not _day_base_ts:
            _count_delta   = 0
            _day_base_cnt  = cnt
            _day_base_ts   = ts_iso
        else:
            try:
                _base_age = (datetime.now(timezone.utc) - datetime.fromisoformat(_day_base_ts)).total_seconds()
            except Exception:
                _base_age = 0
            _count_delta = max(0, cnt - _day_base_cnt)
            if _base_age >= 86400:
                _day_base_cnt = cnt
                _day_base_ts  = ts_iso

        # ソーシャルシグナル加点: コメント数・お気に入り数（ユーザー注目度を反映）
        comment_count  = int(existing.get('commentCount')  or 0)
        fav_count      = int(existing.get('favoriteCount') or 0)
        if comment_count > 0 or fav_count > 0:
            # コメント1件=+2%、お気に入り1件=+1%（最大+100%）
            social_bonus = 1.0 + min(comment_count * 0.02 + fav_count * 0.01, 1.0)
            velocity_score = round(velocity_score * social_bonus, 4)

        # 4セクション形式（storyTimeline）が揃っている場合のみ処理済みとみなす
        # aiGenerated=True でも storyTimeline がなければ再処理させる（再発防止）
        _has_timeline = bool(existing.get('storyTimeline') and isinstance(existing.get('storyTimeline'), list) and len(existing.get('storyTimeline', [])) > 0)
        _existing_cnt = int(existing.get('articleCount', 0) or 0)
        # proc_ai.py と同じ閾値: cnt<=2 は minimal モード（storyTimeline不生成）なので不要
        _needs_timeline = cnt > 2
        # 急上昇中(velocity>40)かつ新記事が増えている場合は再処理（ストーリーを最新状態に保つ）
        _force_reprocess = velocity_score > 40 and existing.get('aiGenerated') and cnt > _existing_cnt
        pending_ai = _force_reprocess or not bool(
            existing.get('aiGenerated') and existing.get('generatedSummary') and not _is_old_extractive
            and (not _needs_timeline or _has_timeline)
        )

        _tier1_img = next(
            (a.get('imageUrl') for a in g
             if a.get('imageUrl') and a.get('tier', 99) == 1),
            None,
        )
        image_url = (
            existing.get('imageUrl') or
            _tier1_img or
            next((a.get('imageUrl') for a in g if a.get('imageUrl')), None) or
            ogp_results.get(tid)
        )

        velocity = calc_velocity(hist, cnt, ts_iso)

        prev_lifecycle = existing.get('lifecycleStatus', 'active')
        if prev_lifecycle == 'legacy':
            lifecycle_status = 'legacy'
        elif prev_lifecycle == 'archived' and velocity_score <= 0:
            # velocity=0の間はarchivedを維持（fetcher上書き防止）
            lifecycle_status = 'archived'
        else:
            lifecycle_status = compute_lifecycle_status(score, last_article_ts, velocity_score, cnt)

        item = {
            'topicId':         tid,
            'SK':              'META',
            'title':           g[0]['title'],
            'generatedTitle':  strip_title_markdown(gen_title or g[0]['title']),
            'status':          st,
            'genre':           genre,
            'genres':          genres,
            'lang':            lang,
            'articleCount':    cnt,
            'mediaCount':      media,
            'hatenaCount':     hb,
            'score':           score,
            'diversityScore':  Decimal(str(_div_mult)),
            'velocity':        Decimal(str(velocity)),
            'velocityScore':   Decimal(str(velocity_score)),
            'lastUpdated':     ts_iso,
            'lastArticleAt':   last_article_ts,
            'firstArticleAt':  first_article_ts,
            'lifecycleStatus': lifecycle_status,
            'sources':         list({a['source'] for a in g}),
            'pendingAI':       pending_ai,
            # 信頼性シグナル（断定ではなく「情報の材料を可視化」）
            'reliability':     reliability,
            'hasConflict':     has_conflict,
            'uniqueSourceCount': unique_src_count,
            # ソーシャルシグナル（フロントエンド表示用）
            'commentCount':      comment_count,
            'favoriteCount':     fav_count,
            # 24h差分（「昨日から+N件」カード表示用）
            'articleCountDelta':     _count_delta,
            'articleCountDayBase':   _day_base_cnt,
            'articleCountDayBaseTs': _day_base_ts,
        }
        if gen_summary:                 item['generatedSummary'] = gen_summary
        if image_url:                   item['imageUrl']         = image_url
        if existing.get('aiGenerated'): item['aiGenerated']      = True
        # put_item はフィールドを完全上書きするため、既存AI生成フィールドをコピーして保持
        for _fld in ('storyTimeline', 'storyPhase', 'spreadReason', 'forecast', 'summaryMode'):
            if existing.get(_fld):
                item[_fld] = existing[_fld]
        # trendsData: DynamoDB は Number を Decimal で返すので int に正規化して保持
        if existing.get('trendsData'):
            item['trendsData'] = {k: int(v) for k, v in existing['trendsData'].items()}
        if existing.get('trendsUpdatedAt'):
            item['trendsUpdatedAt'] = existing['trendsUpdatedAt']
        # T2026-0501-H: SNAP の articles を 1 度だけ計算 (mismerge 検知でも再利用)。
        # publishedAt 昇順で並べる (古い→新しい)。PO 指示「同じ事象なら時系列で並べる」。
        _merged_dict = {
            **{prev['url']: prev for prev in get_latest_snap_articles(tid, max_articles=50) if prev.get('url')},
            **{a['url']: {
                'title':       a['title'], 'url': a['url'],
                'source':      a['source'], 'pubDate': a['pubDate'],
                'publishedAt': a.get('published_ts', 0),
            } for a in g},
        }
        _merged_articles = sorted(
            _merged_dict.values(),
            key=lambda x: x.get('publishedAt') or x.get('published_ts') or 0,
        )[-50:]  # 古い順なので上限超過時は新しい 50 件を残す
        # T2026-0501-H: 誤マージ自動検知 (time gap / entity split / count spike)。
        # `_merged_articles` は累積 50 件まで。シグナルが立てば item に suspectedMismerge=True を付与。
        try:
            _prev_ac = int(existing.get('articleCount', 0) or 0)
        except (TypeError, ValueError):
            _prev_ac = 0
        _signals = detect_mismerge_signals(
            _merged_articles, extract_entities_fn=extract_merge_entities,
            prev_article_count=_prev_ac, genre=genre,
        )
        if _signals.get('suspectedMismerge'):
            item['suspectedMismerge'] = True
            item['mismergeReasons'] = _signals.get('reasons', [])
            if _signals.get('detail'):
                item['mismergeDetail'] = _signals['detail']
            print(f'[mismerge] tid={tid} reasons={_signals["reasons"]} title="{(gen_title or g[0]["title"])[:50]}"')
        # T2026-0502-N: time_gap>=30日は「精査中」フラグを立ててAI生成をスキップ対象化し
        # S3 split 候補キューに登録する (フロント storymap で split 操作の導線を提供)。
        if _signals.get('split_candidate'):
            item['statusLabel'] = '精査中'
            item['pendingAI'] = False  # AI 生成を抑制
            _split_key = f'api/admin/split-candidates/{datetime.now(timezone.utc).strftime("%Y-%m-%d")}.jsonl'
            _split_entry = json.dumps({
                'topicId': tid, 'detectedAt': ts_iso,
                'maxGapDays': _signals.get('detail', {}).get('maxGapDays', 0),
                'title': (gen_title or g[0]['title'])[:100],
            }, ensure_ascii=False)
            try:
                _existing_split = ''
                try:
                    _existing_split = s3.get_object(
                        Bucket=S3_BUCKET, Key=_split_key,
                    )['Body'].read().decode('utf-8')
                except Exception:
                    pass
                s3.put_object(
                    Bucket=S3_BUCKET, Key=_split_key,
                    Body=(_existing_split + _split_entry + '\n').encode('utf-8'),
                    ContentType='application/x-ndjson', CacheControl='no-store',
                )
                print(f'[mismerge] split_candidate 登録: tid={tid} gap={_signals.get("detail", {}).get("maxGapDays")}日')
            except Exception as _se:
                print(f'[mismerge] split_candidate S3書き込み失敗 ({_se}) → 継続')
        current_run_metas[tid] = item
        _dynamo_puts.append(item)
        _dynamo_puts.append({
            'topicId':      tid,
            'SK':           f'SNAP#{ts_key}',
            'articleCount': cnt,
            'score':        score,
            'hatenaCount':  hb,
            'mediaCount':   media,
            'timestamp':    ts_iso,
            'ttl':          int(time.time()) + SNAP_TTL_DAYS * 86400,
            # 累積マージ: 前回 SNAP の articles + 今回の articles を URL-dedup して保存
            # これで古い記事が RSS から消えても topic detail の履歴に残る (2026-04-27 履歴15件問題の根本修正)
            # T2026-0501-H: 時系列で並べて保存 (古い順) — フロント detail.js が「古い順 / 新しい順」
            # 切り替えできるが内部表現は publishedAt 昇順で安定。
            'articles': _merged_articles,
        })
        saved_ids.append(tid)

    print(f'[TIMING] main-loop {len(group_tids)}iter: {time.time()-_t_loop:.1f}s')

    # Step 6.5: Google Trends（上位20件のみ・ベストエフォート・24hキャッシュ）
    try:
        from trends_utils import fetch_trends
        _t_trends = time.time()
        _trend_failures = 0
        _trend_candidates = sorted(
            current_run_metas.items(),
            key=lambda kv: float(kv[1].get('diversityScore', 0) or 0),
            reverse=True,
        )[:20]
        for _tid, _m in _trend_candidates:
            if _trend_failures >= 3:
                print('[trends] 連続失敗3回 → 残りスキップ')
                break
            _td_ts = _m.get('trendsUpdatedAt', '')
            if _td_ts:
                try:
                    _td_age = (datetime.now(timezone.utc) - datetime.fromisoformat(_td_ts)).total_seconds() / 3600
                    if _td_age < 24:
                        continue
                except Exception:
                    pass
            _kw = (_m.get('generatedTitle') or _m.get('title', ''))[:40]
            _result = fetch_trends(_kw)
            if _result:
                _m['trendsData'] = _result
                _m['trendsUpdatedAt'] = ts_iso
                _trend_failures = 0
            else:
                _trend_failures += 1
            time.sleep(2.5)
        print(f'[TIMING] trends: {time.time()-_t_trends:.1f}s')
    except Exception as _te:
        print(f'[trends] 全体エラー（スキップ）: {_te}')

    # Step 6b: DynamoDB バッチ並列書き込み（逐次put_item→batch_writer並列化）
    # T2026-0429-H: ThreadPool で f.result() を呼び出して例外を顕在化させる。
    # 旧実装は as_completed の future を捨てており、batch_writer 内で投げられた
    # 例外 (throttling / ValidationException 等) が silently 消えて topicId が
    # 「saved_ids には入っているが DDB には書かれていない」ゴーストになっていた。
    _t_db = time.time()
    _CHUNK = 25
    _db_chunks = [_dynamo_puts[i:i+_CHUNK] for i in range(0, len(_dynamo_puts), _CHUNK)]

    def _write_dynamo_chunk(chunk):
        with table.batch_writer() as bw:
            for it in chunk:
                bw.put_item(Item=_dynamo_safe(it))

    _write_failures = 0
    with ThreadPoolExecutor(max_workers=20) as ex:
        for f in as_completed([ex.submit(_write_dynamo_chunk, c) for c in _db_chunks]):
            try:
                f.result()
            except Exception as _we:
                _write_failures += 1
                print(f'[dynamo-batch] chunk write 失敗: {_we}')
    if _write_failures:
        print(f'[dynamo-batch] WARN: {_write_failures}/{len(_db_chunks)} chunks 失敗 — '
              f'validate_topics_exist で saved_ids 全件検証して幽霊を除去する')
    print(f'[TIMING] dynamo-batch {len(_dynamo_puts)}items/{len(_db_chunks)}chunks: {time.time()-_t_db:.1f}s')

    # T2026-0428-AK: 新規保存トピックの detail JSON を即座に S3 に書く。
    # 物理ゲート: META が DynamoDB に書かれた = api/topic/{tid}.json も S3 に存在する。
    # 旧実装は META put のみで detail JSON は processor.proc_storage.update_topic_s3_file が
    # 後刻補完していたが、processor 起動前にユーザーが topics.json を見ると「detail 404」状態に。
    # 本番計測で 12/109 件 (11%) がこのパスで生成されていた → ユーザーが離れる主因。
    # ここで雛形 (META + 今回 SNAP のみ) を書いておけば AI 結果は次サイクルで上書きマージされる。
    if S3_BUCKET and saved_ids:
        _t_detail = time.time()
        # tid -> 今回書いた SNAP (articles 含む)
        _tid_to_snap = {}
        for p in _dynamo_puts:
            sk = p.get('SK')
            if isinstance(sk, str) and sk.startswith('SNAP#'):
                _tid_to_snap[p.get('topicId')] = p

        _detail_internal = {'SK', 'pendingAI'}

        def _ensure_detail(tid):
            key = f'api/topic/{tid}.json'
            try:
                s3.head_object(Bucket=S3_BUCKET, Key=key)
                return False  # 既存
            except Exception:
                pass
            meta = current_run_metas.get(tid)
            snap = _tid_to_snap.get(tid)
            if not meta or not snap:
                return False
            detail = {
                'meta': {k: v for k, v in meta.items() if k not in _detail_internal},
                'timeline': [{
                    'timestamp':    snap.get('timestamp'),
                    'articleCount': snap.get('articleCount'),
                    'score':        snap.get('score', 0),
                    'hatenaCount':  snap.get('hatenaCount', 0),
                    'articles':     snap.get('articles', []),
                }],
                'views': [],
            }
            try:
                write_s3(key, detail)
                return True
            except Exception as e:
                print(f'[detail-init] {tid} write failed: {e}')
                return False

        _detail_created = 0
        with ThreadPoolExecutor(max_workers=20) as ex:
            for f in as_completed([ex.submit(_ensure_detail, tid) for tid in saved_ids]):
                try:
                    if f.result():
                        _detail_created += 1
                except Exception:
                    pass
        print(f'[TIMING] detail-init {_detail_created}/{len(saved_ids)} new files: {time.time()-_t_detail:.1f}s')

    if S3_BUCKET:
        topics = get_all_topics()
        # T2026-0503-N: api/topics.json に含まれる ID = 前サイクル validate 済み。
        # validate_topics_exist に渡すことで、これらの DDB batch_get_item を省略する。
        # current_run_metas（今回新規）は api/topics.json 未収録なので DDB 検証が引き続き走る。
        _s3_known_ids = {t['topicId'] for t in topics}

        # 今回のrun で書いたトピック（DynamoDB確定）をtopics.jsonにマージ
        # 既存エントリはフレッシュデータで上書き（旧実装は新規追加のみで更新を取りこぼしていた）
        topics_by_tid = {t['topicId']: t for t in topics}
        for item in current_run_metas.values():
            if item['topicId'] in topics_by_tid:
                topics_by_tid[item['topicId']].update(item)  # フレッシュデータで上書き
            else:
                topics_by_tid[item['topicId']] = item
        topics = list(topics_by_tid.values())
        # T2026-0502-G: current_run_tids を lifecycle ループより先に定義する。
        # 旧実装では行1224 で定義していたため、この行より先に参照するとUnboundLocalError。
        current_run_tids = set(current_run_metas.keys())

        # T2026-0501-F2: 今回 run で更新されなかったトピックの lifecycle を
        # decayed velocity で再計算して topics dict を修正する (DDB 書き戻しなし・memory only)。
        # 旧実装は compute_lifecycle_status が新記事のある run 時にしか呼ばれないため、
        # cooling トピックが velocity=0 になっても最大7日間 topics.json に残留していた。
        _inactive_archived = 0
        for _t in topics:
            if _t['topicId'] in current_run_tids:
                continue
            _stored_ls = _t.get('lifecycleStatus', 'active')
            if _stored_ls in INACTIVE_LIFECYCLE_STATUSES:
                continue
            _last_art = int(_t.get('lastArticleAt') or _t.get('firstArticleAt') or 0)
            if not _last_art:
                continue
            _decayed_vs = int(apply_velocity_decay(
                float(_t.get('velocityScore', 0) or 0),
                _t.get('lastUpdated', '')
            ))
            _new_ls = compute_lifecycle_status(
                int(_t.get('score', 0) or 0),
                _last_art,
                _decayed_vs,
                int(_t.get('articleCount', 0) or 0),
            )
            if _new_ls != _stored_ls:
                _t['lifecycleStatus'] = _new_ls
                if _new_ls in INACTIVE_LIFECYCLE_STATUSES:
                    _inactive_archived += 1
        if _inactive_archived:
            print(f'[T2026-0501-F2] lifecycle 再計算: {_inactive_archived}件を archived に移行 (memory only)')

        # 幽霊エントリ除去: T2026-0503-N known_good_ids 最適化。
        # _s3_known_ids（api/topics.json = 前サイクル validate 済み）はDDB照合をスキップ。
        # current_run_metas 由来の新規 topicId は _s3_known_ids に含まれないため
        # ConsistentRead=True で DDB 検証され、ThreadPool silent drop によるゴーストを検出する。
        pre_count  = len(topics)
        topics     = validate_topics_exist(topics, known_good_ids=_s3_known_ids)
        if len(topics) < pre_count:
            print(f'幽霊エントリ除去: {pre_count - len(topics)}件削除')
        # 幽霊が消えた tid は saved_ids / current_run_metas からも除去 (pending 計算の整合性確保)
        _verified_tids = {t['topicId'] for t in topics}
        _ghost_saved = [tid for tid in saved_ids if tid not in _verified_tids]
        if _ghost_saved:
            print(f'[ghost] saved_ids から DDB 不在の {len(_ghost_saved)}件を除去 (sample={_ghost_saved[:5]})')
            saved_ids = [tid for tid in saved_ids if tid in _verified_tids]
            for tid in _ghost_saved:
                current_run_metas.pop(tid, None)

        topics_active = [t for t in topics if t.get('lifecycleStatus', 'active') not in INACTIVE_LIFECYCLE_STATUSES]
        topics_active = sorted(topics_active, key=lambda x: int(x.get('score', 0) or 0), reverse=True)[:500]
        print(f'O(n·k)処理対象: {len(topics_active)}件 / 全{len(topics)}件')

        related_map = find_related_topics(topics_active)
        for t in topics:
            t['relatedTopics'] = related_map.get(t.get('topicId', ''), [])

        # T2026-0501-E: extract_entities は ENTITY_PATTERNS (~30件) のみ。大半の日本語
        # トピックでエンティティ空 → shared_ents=0 → 親子化不可 が low child_density の根本原因。
        # extract_merge_entities はカタカナ3文字以上・英大文字語・漢字固有名詞も抽出するため、
        # ほぼすべてのトピックでエンティティを検出でき、親子化候補が大幅に増える。
        topic_entities_map = {
            t['topicId']: extract_merge_entities(t.get('generatedTitle') or t.get('title', ''))
            for t in topics_active
        }
        parent_map = detect_topic_hierarchy(topics_active, topic_entities_map)

        child_to_parent  = {}
        parent_to_children = {}
        for tid_b, tid_a in parent_map.items():
            child_to_parent[tid_b] = tid_a
            parent_to_children.setdefault(tid_a, [])
            child_t = next((t for t in topics if t['topicId'] == tid_b), None)
            if child_t:
                # T41: childTopics ref に articleCount/lastArticleAt/lifecycleStatus も含める
                # 親側 detail page で「分岐」カードを描く際、tMap (topics.jsonベース) が
                # この子を持たない (archived など) 場合でも footer メタを正しく描けるように
                # する (旧バグ: footer に "0件 · 1/1" が出ていた)
                parent_to_children[tid_a].append({
                    'topicId':         tid_b,
                    'title':           child_t.get('generatedTitle') or child_t.get('title', ''),
                    'articleCount':    int(child_t.get('articleCount', 0) or 0),
                    'lastArticleAt':   child_t.get('lastArticleAt') or child_t.get('lastUpdated') or '',
                    'lifecycleStatus': child_t.get('lifecycleStatus') or 'active',
                })

        for t in topics:
            tid = t['topicId']
            if tid in child_to_parent:   t['parentTopicId'] = child_to_parent[tid]
            if tid in parent_to_children: t['childTopics']   = parent_to_children[tid]

        def _norm_title(t):
            s = (t.get('generatedTitle') or t.get('title', '')).strip()
            s = s.replace('｢', '「').replace('｣', '」').replace('　', ' ')
            s = re.sub(r'\s+', ' ', s)
            s = re.sub(r'\s*[-－–|｜]\s*[^\s].{1,25}$', '', s)
            return s.lower()[:50]

        _LIVE_PREFIX_WORDS = re.compile(r'^(中継|速報|更新|独自|詳報|続報|緊急|号外)\s*')

        def _core_key(t):
            s = (t.get('generatedTitle') or t.get('title', '')).lower()
            s = re.sub(r'[「」【】・、。,!?！？\[\]()（）『』""\'\'#＃]', '', s)
            s = _LIVE_PREFIX_WORDS.sub('', s)  # 【中継】→中継→除去
            s = re.sub(r'\s+', '', s)
            return s[:18]

        dedup_long = {}
        dedup_core = {}
        for t in topics:
            kl = _norm_title(t)
            kc = _core_key(t)
            sc = int(t.get('score', 0) or 0)
            if kl in dedup_long:
                if sc > int(dedup_long[kl].get('score', 0) or 0):
                    dedup_long[kl] = t
                    dedup_core[kc] = t
            elif kc in dedup_core:
                if sc > int(dedup_core[kc].get('score', 0) or 0):
                    old_kl = _norm_title(dedup_core[kc])
                    dedup_long.pop(old_kl, None)
                    dedup_long[kl] = t
                    dedup_core[kc] = t
            else:
                dedup_long[kl] = t
                dedup_core[kc] = t

        topics_deduped_all = sorted(dedup_long.values(), key=lambda x: int(x.get('score', 0) or 0), reverse=True)
        # 二次dedup: タイトル類似度クラスタリングで同一イベントの重複topicIdを統合
        # T2026-0501-H: auditor 経由でマージイベントを記録
        topics_deduped_all = _topic_cluster_dedup(topics_deduped_all, auditor=_merge_auditor)
        # 2件以上の記事を持つトピックのみtopics.jsonに含める（1件=コアバリュー違反）
        # velocityScore降順でソートし上位500件に絞り込む
        # T211: 同一ドメインで複数記事が出るUGC・PR記事の混入を防ぐため、
        #   uniqueSourceCount >= 2 も要求する。レガシートピック（uniqueSourceCount未設定）は
        #   articleCount にフォールバックして既存挙動を維持し、再フェッチ後に新フィルタが適用される。
        def _unique_src_or_articles(t):
            v = t.get('uniqueSourceCount')
            if v is None:
                return int(t.get('articleCount', 0) or 0)
            try:
                return int(v or 0)
            except (TypeError, ValueError):
                return int(t.get('articleCount', 0) or 0)

        topics_deduped = sorted(
            [t for t in topics_deduped_all
             if t.get('lifecycleStatus', 'active') not in INACTIVE_LIFECYCLE_STATUSES
             and int(t.get('articleCount', 0) or 0) >= 2
             and _unique_src_or_articles(t) >= 2
             and not any(p.search(t.get('title', '') + t.get('generatedTitle', '')) for p in _DIGEST_SKIP_PATS)
            ],
            key=lambda t: (float(t.get('velocityScore', 0) or 0), t.get('lastUpdated', '') or ''),
            reverse=True,
        )[:500]

        # 今回runで更新されなかったトピックのvelocityScoreを時間減衰させる
        # DynamoDBには書き戻さない（topics.json の表示スコアのみ調整）
        current_run_tids = set(current_run_metas.keys())
        for t in topics_deduped:
            if t['topicId'] not in current_run_tids:
                raw_vs = float(t.get('velocityScore', 0) or 0)
                t['velocityScore'] = apply_velocity_decay(raw_vs, t.get('lastUpdated', ''))

        # カード表示・検索用フィールドのみ公開。詳細ページ専用フィールドは除外してサイズ削減
        # spreadReason/forecast/storyTimeline/backgroundContext は api/topic/{id}.json から取得するので不要
        _INTERNAL = {'SK', 'pendingAI', 'spreadReason', 'forecast', 'storyTimeline', 'backgroundContext',
                     'trendsData', 'trendsUpdatedAt'}
        def _pub(t):
            d = {k: v for k, v in t.items() if k not in _INTERNAL}
            if d.get('generatedSummary'):
                d['generatedSummary'] = d['generatedSummary'][:120]
            # T2026-0429-G: minimal regime (ac<=2 / summaryMode='minimal') の legacy storyPhase を None に正規化。
            # 詳細は proc_storage.normalize_minimal_phase の docstring 参照 (fetcher は別 Lambda
            # で proc_storage を import できないため、同等ロジックを inline で重複実装する)。
            try:
                _ac = int(d.get('articleCount', 0) or 0)
            except (TypeError, ValueError):
                _ac = 0
            if (d.get('summaryMode') == 'minimal' or _ac <= 2) and d.get('storyPhase'):
                d['storyPhase'] = None
            return d
        topics_public = [_pub(t) for t in topics_deduped]

        # T2026-0428-AK: detail JSON が無いトピックは topics.json に含めない。
        # 上の detail-init ブロックで saved_ids 分は雛形生成済だが、過去 run で META だけ
        # 残っているレガシーゾンビ (DynamoDB に META・S3 に detail なし) を二重防御で除外する。
        # 物理ゲート: 「topics.json のエントリ = api/topic/{tid}.json が必ず S3 に存在する」を保証。
        def _detail_exists_check(tid):
            try:
                s3.head_object(Bucket=S3_BUCKET, Key=f'api/topic/{tid}.json')
                return tid, True
            except Exception:
                return tid, False

        _check_tids = [t['topicId'] for t in topics_public if t.get('topicId')]
        _has_detail = {}
        with ThreadPoolExecutor(max_workers=30) as ex:
            for f in as_completed([ex.submit(_detail_exists_check, tid) for tid in _check_tids]):
                try:
                    tid, ok = f.result()
                    _has_detail[tid] = ok
                except Exception:
                    pass
        _before = len(topics_public)
        topics_public = [t for t in topics_public if _has_detail.get(t.get('topicId'), False)]
        if len(topics_public) < _before:
            print(f'[topics-public] detail JSON 欠損で除外: {_before - len(topics_public)}件 (残り {len(topics_public)}件)')

        write_s3('api/topics.json', {
            'topics':          topics_public,
            'trendingKeywords': extract_trending_keywords(topics_deduped),
            'updatedAt':       ts_iso,
        })

        # topics_deduped に含まれるIDのみ pending 対象にする
        # （サイト非公開の低品質トピックをAI処理キューに入れない）
        deduped_tids = {t['topicId'] for t in topics_deduped}
        topic_map = {t['topicId']: t for t in topics if t['topicId'] in deduped_tids}

        # 今回の未処理ID: 公開対象(topics_deduped)かつ pendingAI=True のみ
        new_pending = set(tid for tid in saved_ids
                          if tid in deduped_tids
                          and current_run_metas.get(tid, {}).get('pendingAI'))

        # 以前のpending IDを読み込み、まだ未処理のものを引き継ぐ
        old_pending = []
        try:
            resp = s3.get_object(Bucket=S3_BUCKET, Key='api/pending_ai.json')
            old_data = json.loads(resp['Body'].read())
            old_pending = old_data.get('topicIds', [])
        except Exception:
            pass
        # 以前のIDのうち公開対象かつAI未完了のものを引き継ぐ。それ以外（削除済み・非公開）は除外。
        old_still_pending = [tid for tid in old_pending
                             if tid not in new_pending
                             and tid in topic_map
                             and (topic_map[tid].get('pendingAI') or
                                  not (topic_map[tid].get('aiGenerated') and
                                       topic_map[tid].get('generatedSummary')))]

        pending_ids = list(new_pending) + old_still_pending
        print(f'[pending] new={len(new_pending)} old={len(old_still_pending)} total={len(pending_ids)}')

        # summary欠如の既存トピックをペンディングに追加（カバレッジ改善）
        # pending が _ORPHAN_CAP 件以下の場合のみ追加し、キューの無限肥大を防ぐ
        _ORPHAN_CAP = 80
        if len(pending_ids) < _ORPHAN_CAP:
            already_pending = set(pending_ids)
            orphan_candidates = sorted(
                (t for t in topics_deduped  # 公開対象のみ対象
                 if t['topicId'] not in already_pending
                 and not (t.get('aiGenerated')
                          and t.get('generatedSummary')
                          and (t.get('storyTimeline')                       # full/standard: timeline必須
                               or t.get('summaryMode') == 'minimal'         # minimal: timeline不要
                               or int(t.get('articleCount', 0) or 0) <= 2)  # 2件以下: timeline不要
                          and t.get('imageUrl')                              # imageUrl未生成なら再処理
                          and (t.get('storyPhase')                           # storyPhase未生成なら再処理
                               or t.get('summaryMode') == 'minimal'
                               or int(t.get('articleCount', 0) or 0) <= 2)
                          )),
                key=lambda t: float(t.get('velocityScore', 0) or 0),
                reverse=True,
            )
            if orphan_candidates:
                add_count = min(20, _ORPHAN_CAP - len(pending_ids), len(orphan_candidates))
                pending_ids = pending_ids + [t['topicId'] for t in orphan_candidates[:add_count]]
                print(f'[pending] summary欠如orphan追加: {add_count}件 (残{len(orphan_candidates)-add_count}件, total={len(pending_ids)})')

        # storyPhase欠如トピックをorphan_capに関わらず優先追加（T139: 大きなキューでもカバレッジ確保）
        _PHASE_CAP = 5
        already_pending_set = set(pending_ids)
        phase_missing = sorted(
            (t for t in topics_deduped
             if t['topicId'] not in already_pending_set
             and t.get('aiGenerated')
             and t.get('generatedSummary')
             and not t.get('storyPhase')
             and int(t.get('articleCount', 0) or 0) >= 3),
            key=lambda t: float(t.get('velocityScore', 0) or 0),
            reverse=True,
        )
        if phase_missing:
            add_count = min(_PHASE_CAP, len(phase_missing))
            pending_ids = pending_ids + [t['topicId'] for t in phase_missing[:add_count]]
            print(f'[pending] storyPhase欠如追加: {add_count}件 (残{len(phase_missing)-add_count}件)')

        write_s3('api/pending_ai.json', {'topicIds': pending_ids, 'updatedAt': ts_iso})

        # 新規ペンディングトピックがあれば processor を即時非同期トリガー
        # maxApiCalls=10: 即時処理は少量に絞る (定期 cron が MAX_API_CALLS=30 で残りを処理)。
        # 目的: 新規トピック作成→AI要約付与までのレイテンシを最大6時間→最大30分に短縮。
        if new_pending:
            try:
                _lambda = boto3.client('lambda', region_name='ap-northeast-1')
                _lambda.invoke(
                    FunctionName='p003-processor',
                    InvocationType='Event',
                    Payload=json.dumps({
                        'topic_ids': list(new_pending),
                        'source': 'fetcher_trigger',
                        'maxApiCalls': 10,
                    }).encode(),
                )
                print(f'[fetcher] processor即時トリガー: {len(new_pending)}件 (maxApiCalls=10)')
            except Exception as _e:
                print(f'[fetcher] processorトリガー失敗（スキップ）: {_e}')

        generate_rss(topics, ts_iso)
        generate_sitemap(topics_deduped)  # 公開対象のみsitemapに含める

        _TOPIC_INTERNAL = {'SK', 'pendingAI', 'ttl', 'trendsUpdatedAt'}
        _tids_to_write  = [tid for tid in saved_ids if tid in deduped_tids]

        def _write_topic_s3(tid):
            meta, snaps, views = get_topic_detail(tid)
            if not meta:
                return False
            meta['relatedTopics'] = related_map.get(tid, [])
            if tid in child_to_parent:    meta['parentTopicId'] = child_to_parent[tid]
            if tid in parent_to_children: meta['childTopics']   = parent_to_children[tid]
            meta_public = {k: v for k, v in meta.items() if k not in _TOPIC_INTERNAL}
            write_s3(f'api/topic/{tid}.json', {
                'meta': meta_public,
                'timeline': [
                    {'timestamp':    s['timestamp'],
                     'articleCount': s['articleCount'],
                     'score':        s.get('score', 0),
                     'hatenaCount':  s.get('hatenaCount', 0),
                     'articles':     s.get('articles', [])}
                    for s in snaps
                ],
                'views': [
                    {'date': v['date'], 'count': int(v.get('count', 0))}
                    for v in views
                ],
            })
            return True

        _t_s3 = time.time()
        s3_written = 0
        with ThreadPoolExecutor(max_workers=20) as ex:
            futures = [ex.submit(_write_topic_s3, tid) for tid in _tids_to_write]
            for f in as_completed(futures):
                try:
                    if f.result():
                        s3_written += 1
                except Exception as e:
                    print(f'write_topic error: {e}')
        print(f'[TIMING] S3 topic write {s3_written}件: {time.time()-_t_s3:.1f}s')
        print(f'S3書き出し完了: {s3_written}件')

    # フィルター判定ログをS3に保存（lifecycle Lambda が週次で集計して重みを調整）
    if all_filter_feedback:
        record_filter_feedback(all_filter_feedback, ts_key)

    spikes = find_trending_spikes(groups_meta_list)
    if spikes:
        post_slack_spike(spikes)

    save_seen_articles(current_urls)

    # T2026-0501-H: マージ監査ログを S3 へ flush。1 run = 1 PUT (バッチ書き込み)。
    try:
        _merge_auditor.flush_to_s3()
    except Exception as _ae:
        print(f'[merge_audit] flush 失敗 ({type(_ae).__name__}: {_ae})')

    # T2026-0501-H: suspectedMismerge カウントを FETCHER_HEALTH に出す (SLI 用)
    _mismerge_count = sum(1 for it in current_run_metas.values() if it.get('suspectedMismerge'))

    print('[FETCHER_HEALTH] ' + json.dumps({
        'event': 'fetcher_health',
        'status': 'run_complete',
        'saved_articles': len(saved_ids),
        'new_topics': len(new_pending),
        'fetched': len(all_articles),
        'new_urls': len(new_urls),
        'merge_audit_events': len(_merge_auditor.events),
        'haiku_pairs_asked': getattr(_ai_judge, 'pairs_asked', 0) if _ai_judge else 0,
        'haiku_pairs_yes': getattr(_ai_judge, 'pairs_yes', 0) if _ai_judge else 0,
        'suspected_mismerge_count': _mismerge_count,
    }))
    return {'statusCode': 200,
            'body': json.dumps({'articles': len(all_articles), 'new': len(new_urls),
                                'topics': len(groups_sorted), 'ts': ts_key})}
