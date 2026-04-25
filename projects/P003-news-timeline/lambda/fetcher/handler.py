import json
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from decimal import Decimal

from config import (
    SLACK_WEBHOOK, S3_BUCKET,
    RSS_FEEDS, SNAP_TTL_DAYS, table, INACTIVE_LIFECYCLE_STATUSES, s3,
    SOURCE_TIER_MAP,
)
from filters import (
    _DIGEST_SKIP_PATS, load_filter_weights,
    _apply_secondary_penalty,
)
from scoring import (
    detect_uncertainty, calc_topic_reliability, detect_numeric_conflict,
    apply_tier_and_diversity_scoring, apply_tech_audience_filter,
    record_filter_feedback,
)
from cluster_utils import topic_fingerprint, cluster
from score_utils import (
    calc_score, calc_velocity_score, apply_time_decay, apply_velocity_decay,
    source_diversity_score, compute_lifecycle_status,
    sort_by_pubdate, _parse_pubdate_ts,
)
from text_utils import (
    dominant_genres, dominant_lang,
    extract_source_name, extract_rss_image,
    extract_trending_keywords,
    extract_entities, find_related_topics, detect_topic_hierarchy,
    extractive_title, extractive_summary,
)
from storage import (
    write_s3, get_all_topics, get_topic_detail,
    recent_counts, calc_velocity, validate_topics_exist,
    load_seen_articles, save_seen_articles,
    generate_rss, generate_sitemap,
)


_RSS10_NS = 'http://purl.org/rss/1.0/'
_DC_NS    = 'http://purl.org/dc/elements/1.1/'


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
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Flotopic/1.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read()
        root = ET.fromstring(content)
        items, is_rdf = _parse_rss_items(root)
        for item in items:
            if is_rdf:
                title   = (item.findtext(f'{{{_RSS10_NS}}}title') or '').strip()
                link    = (item.findtext(f'{{{_RSS10_NS}}}link')  or '').strip()
                pubdate = (item.findtext(f'{{{_DC_NS}}}date')     or '').strip()
            else:
                title   = (item.findtext('title')   or '').strip()
                link    = (item.findtext('link')     or '').strip()
                pubdate = (item.findtext('pubDate')  or '').strip()
            img = extract_rss_image(item)
            if title and link:
                if any(p.search(title) for p in _DIGEST_SKIP_PATS):
                    continue
                source_name   = extract_source_name(item, link, url)
                resolved_tier = SOURCE_TIER_MAP.get(source_name, feed_tier)
                articles.append({
                    'title':        title, 'url': link,
                    'pubDate':      pubdate, 'genre': genre,
                    'lang':         lang,
                    'source':       source_name,
                    'imageUrl':     img,
                    'published_ts': _parse_pubdate_ts(pubdate),
                    'tier':         resolved_tier,
                })
    except Exception as e:
        print(f'RSS error [{url}]: {e}')
    return articles


def fetch_ogp_image(url):
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


def _fetch_ogp_group(tid, urls):
    """複数 URL を順番に試して最初に取得できた OGP 画像を返す。"""
    for u in urls:
        img = fetch_ogp_image(u)
        if img:
            return tid, img
    return tid, None


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

    # Step 3: 差分チェック
    current_urls = {a['url'] for a in all_articles}
    new_urls     = current_urls - seen_urls

    if seen_urls and not new_urls:
        print('新規記事なし。DynamoDB 呼び出しをスキップします。')
        save_seen_articles(current_urls)
        return {'statusCode': 200,
                'body': json.dumps({'articles': len(all_articles), 'new': 0, 'skipped': True})}

    print(f'新規記事: {len(new_urls)}件 / 既知: {len(seen_urls)}件')
    save_seen_articles(current_urls)

    groups = cluster(all_articles)
    print(f'トピック数: {len(groups)}')

    groups_sorted = sorted(groups, key=lambda g: len({a['source'] for a in g}) * 10, reverse=True)
    group_tids    = [(g, topic_fingerprint(g)) for g in groups_sorted]

    # Step 4: DynamoDB（hist + META）を全グループ並列プリフェッチ
    prefetched = {}
    with ThreadPoolExecutor(max_workers=20) as ex:
        fs = {ex.submit(_prefetch_group, tid): tid for _, tid in group_tids}
        for f in as_completed(fs):
            tid = fs[f]
            try:
                prefetched[tid] = f.result()
            except Exception:
                prefetched[tid] = ([], {})

    # Step 5: OGP 画像が必要なグループを特定して並列取得（最大 20 件）
    ogp_candidates = []
    for g, tid in group_tids:
        _, existing = prefetched.get(tid, ([], {}))
        if existing.get('imageUrl') or any(a.get('imageUrl') for a in g):
            continue
        if len(g) < 2:
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

    # Step 6: メインループ（外部 I/O なし・DynamoDB 書き込みのみ）
    for g, tid in group_tids:
        cnt    = len(g)
        genres = dominant_genres(g)
        genre  = genres[0]
        lang   = dominant_lang(g)
        hist, existing = prefetched.get(tid, ([], {}))

        groups_meta_list.append((g, tid, cnt, hist))
        st             = calc_status(hist, cnt)
        score, media, hb = calc_score(g)

        last_article_ts  = max((a.get('published_ts', 0) for a in g), default=0)
        first_article_ts = int(existing.get('firstArticleAt') or
                               min((a.get('published_ts', 0) for a in g if a.get('published_ts')), default=0))
        score = apply_time_decay(score, last_article_ts)
        score = max(1, int(score * source_diversity_score(g)))
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
        _is_old_extractive = existing_summary and '複数の報道' in existing_summary and '関連して' in existing_summary
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
        # 急上昇中(velocity>40)かつ新記事が増えている場合は再処理（ストーリーを最新状態に保つ）
        _force_reprocess = velocity_score > 40 and existing.get('aiGenerated') and cnt > _existing_cnt
        pending_ai = _force_reprocess or not bool(
            existing.get('aiGenerated') and existing.get('generatedSummary') and not _is_old_extractive and _has_timeline
        )

        image_url = (
            existing.get('imageUrl') or
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
            'generatedTitle':  gen_title or g[0]['title'],
            'status':          st,
            'genre':           genre,
            'genres':          genres,
            'lang':            lang,
            'articleCount':    cnt,
            'mediaCount':      media,
            'hatenaCount':     hb,
            'score':           score,
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
            'commentCount':    comment_count,
            'favoriteCount':   fav_count,
        }
        if gen_summary:                 item['generatedSummary'] = gen_summary
        if image_url:                   item['imageUrl']         = image_url
        if existing.get('aiGenerated'): item['aiGenerated']      = True
        table.put_item(Item=item)
        current_run_metas[tid] = item
        table.put_item(Item={
            'topicId':      tid,
            'SK':           f'SNAP#{ts_key}',
            'articleCount': cnt,
            'score':        score,
            'hatenaCount':  hb,
            'mediaCount':   media,
            'timestamp':    ts_iso,
            'ttl':          int(time.time()) + SNAP_TTL_DAYS * 86400,
            'articles': sort_by_pubdate(list({
                a['source']: {
                    'title':       a['title'], 'url': a['url'],
                    'source':      a['source'], 'pubDate': a['pubDate'],
                    'publishedAt': a.get('published_ts', 0),
                } for a in g
            }.values()))[:20],
        })
        saved_ids.append(tid)

    if S3_BUCKET:
        topics = get_all_topics()

        # 今回のrun で書いたトピック（DynamoDB確定）をtopics.jsonにマージ
        # 既存エントリはフレッシュデータで上書き（旧実装は新規追加のみで更新を取りこぼしていた）
        topics_by_tid = {t['topicId']: t for t in topics}
        for item in current_run_metas.values():
            if item['topicId'] in topics_by_tid:
                topics_by_tid[item['topicId']].update(item)  # フレッシュデータで上書き
            else:
                topics_by_tid[item['topicId']] = item
        topics = list(topics_by_tid.values())

        # 幽霊エントリ除去: 今回runで書いたtopicはDynamoDB確定なのでスキップ
        saved_tids = set(saved_ids)
        pre_count  = len(topics)
        topics     = validate_topics_exist(topics, skip_tids=saved_tids)
        if len(topics) < pre_count:
            print(f'幽霊エントリ除去: {pre_count - len(topics)}件削除')

        topics_active = [t for t in topics if t.get('lifecycleStatus', 'active') not in INACTIVE_LIFECYCLE_STATUSES]
        topics_active = sorted(topics_active, key=lambda x: int(x.get('score', 0) or 0), reverse=True)[:1000]
        print(f'O(n²)処理対象: {len(topics_active)}件 / 全{len(topics)}件')

        related_map = find_related_topics(topics_active)
        for t in topics:
            t['relatedTopics'] = related_map.get(t.get('topicId', ''), [])

        topic_entities_map = {
            t['topicId']: extract_entities(t.get('generatedTitle') or t.get('title', ''))
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
                parent_to_children[tid_a].append({
                    'topicId': tid_b,
                    'title':   child_t.get('generatedTitle') or child_t.get('title', ''),
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
        # velocityScore降順でソートし上位500件に絞り込む
        # （topics.jsonを1.4MB→300KB台に削減。velocityScore>0は245件なので有効トピックは全カバー）
        topics_deduped = sorted(
            [t for t in topics_deduped_all
             if t.get('lifecycleStatus', 'active') not in INACTIVE_LIFECYCLE_STATUSES
             and (int(t.get('articleCount', 0) or 0) >= 2 or float(t.get('velocityScore', 0) or 0) > 0)
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

        # DynamoDB内部フィールドをpublicなtopics.jsonから除外
        _INTERNAL = {'SK', 'pendingAI'}
        topics_public = [{k: v for k, v in t.items() if k not in _INTERNAL} for t in topics_deduped]

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
                          and t.get('storyTimeline'))),  # timeline欠如も再処理対象
                key=lambda t: float(t.get('velocityScore', 0) or 0),
                reverse=True,
            )
            if orphan_candidates:
                add_count = min(20, _ORPHAN_CAP - len(pending_ids), len(orphan_candidates))
                pending_ids = pending_ids + [t['topicId'] for t in orphan_candidates[:add_count]]
                print(f'[pending] summary欠如orphan追加: {add_count}件 (残{len(orphan_candidates)-add_count}件, total={len(pending_ids)})')

        write_s3('api/pending_ai.json', {'topicIds': pending_ids, 'updatedAt': ts_iso})
        generate_rss(topics, ts_iso)
        generate_sitemap(topics_deduped)  # 公開対象のみsitemapに含める

        _TOPIC_INTERNAL = {'SK', 'pendingAI', 'ttl'}
        s3_written = 0
        for tid in (tid for tid in saved_ids if tid in deduped_tids):
            meta, snaps, views = get_topic_detail(tid)
            if meta:
                s3_written += 1
                meta['relatedTopics'] = related_map.get(tid, [])
                if tid in child_to_parent:   meta['parentTopicId'] = child_to_parent[tid]
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
        print(f'S3書き出し完了: {s3_written}件')

    # フィルター判定ログをS3に保存（lifecycle Lambda が週次で集計して重みを調整）
    if all_filter_feedback:
        record_filter_feedback(all_filter_feedback, ts_key)

    spikes = find_trending_spikes(groups_meta_list)
    if spikes:
        post_slack_spike(spikes)

    save_seen_articles(current_urls)

    return {'statusCode': 200,
            'body': json.dumps({'articles': len(all_articles), 'new': len(new_urls),
                                'topics': len(groups_sorted), 'ts': ts_key})}
