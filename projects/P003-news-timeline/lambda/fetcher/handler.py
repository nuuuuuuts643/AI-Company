import json
import re
import time
import hashlib
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from config import (
    ANTHROPIC_API_KEY, SLACK_WEBHOOK, S3_BUCKET,
    RSS_FEEDS, MAX_API_CALLS, SNAP_TTL_DAYS,
)
from text_utils import (
    topic_fingerprint, dominant_genres, dominant_lang,
    extract_source_name, extract_rss_image, cluster,
    calc_score, calc_velocity_score, apply_time_decay,
    source_diversity_score, compute_lifecycle_status,
    sort_by_pubdate, extract_trending_keywords,
    extract_entities, find_related_topics, detect_topic_hierarchy,
    extractive_title, extractive_summary,
    _parse_pubdate_ts,
)
from storage import (
    write_s3, get_all_topics, get_topic_detail, cleanup_stale,
    log_summary_pattern, recent_counts, calc_velocity,
    load_seen_articles, save_seen_articles,
    generate_rss, generate_sitemap,
)


def fetch_rss(feed):
    articles = []
    url, genre, lang = feed['url'], feed['genre'], feed.get('lang', 'ja')
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Flotopic/1.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read()
        root = ET.fromstring(content)
        for item in root.findall('.//item'):
            title   = (item.findtext('title')   or '').strip()
            link    = (item.findtext('link')     or '').strip()
            pubdate = (item.findtext('pubDate')  or '').strip()
            img     = extract_rss_image(item)
            if title and link:
                articles.append({
                    'title':       title, 'url': link,
                    'pubDate':     pubdate, 'genre': genre,
                    'lang':        lang,
                    'source':      extract_source_name(item, link, url),
                    'imageUrl':    img,
                    'published_ts': _parse_pubdate_ts(pubdate),
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


def generate_title(articles):
    if not ANTHROPIC_API_KEY:
        return None
    headlines = '\n'.join(a['title'] for a in articles[:6])
    prompt = (
        '以下はニュース記事の見出しです。\n'
        'これらが共通して報じているトピックを表す、概念的で簡潔な日本語タイトルを作ってください。\n\n'
        '【出力ルール】\n'
        '- 12〜20文字程度の短いタイトル\n'
        '- 「〇〇事件」「△△問題」「▲▲の動向」「◇◇をめぐる動き」などの形式が望ましい\n'
        '- 記事タイトルをそのままコピーしないこと\n'
        '- 固有名詞や核心キーワードは必ず含める\n'
        '- 説明文・句読点・かぎかっこ不要。タイトルのみ1行で出力\n\n'
        f'見出し:\n{headlines}'
    )
    try:
        body = json.dumps({
            'model': 'claude-haiku-4-5-20251001',
            'max_tokens': 30,
            'messages': [{'role': 'user', 'content': prompt}],
        }).encode('utf-8')
        req = urllib.request.Request(
            'https://api.anthropic.com/v1/messages',
            data=body,
            headers={
                'x-api-key': ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        return data['content'][0]['text'].strip()
    except Exception as e:
        print(f'Title generation error: {e}')
        return None


def generate_summary(articles):
    if not ANTHROPIC_API_KEY:
        return None
    headlines = '\n'.join(a['title'] for a in articles[:8])
    prompt = (
        '以下は同じニューストピックを報じた見出し一覧です。\n'
        'このトピックの概要を分かりやすく2〜3文で要約してください。\n'
        '日本語で150字以内にまとめてください。箇条書き不要。自然な文章のみ出力。\n\n'
        f'見出し:\n{headlines}'
    )
    try:
        body = json.dumps({
            'model': 'claude-haiku-4-5-20251001',
            'max_tokens': 150,
            'messages': [{'role': 'user', 'content': prompt}],
        }).encode('utf-8')
        req = urllib.request.Request(
            'https://api.anthropic.com/v1/messages',
            data=body,
            headers={
                'x-api-key': ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read())
        return data['content'][0]['text'].strip()
    except Exception as e:
        print(f'Summary generation error: {e}')
        return None


def incremental_summary(existing_summary, new_articles):
    if not ANTHROPIC_API_KEY or not new_articles or not existing_summary:
        return None
    new_headlines = '\n'.join(a['title'] for a in new_articles[:5])
    prompt = (
        f'既存の要約:\n{existing_summary}\n\n'
        f'新着ニュース見出し:\n{new_headlines}\n\n'
        '上記の新着情報を踏まえて、既存の要約を150字以内で更新してください。'
        '日本語、自然な文章のみ出力。'
    )
    try:
        body = json.dumps({
            'model': 'claude-haiku-4-5-20251001',
            'max_tokens': 150,
            'messages': [{'role': 'user', 'content': prompt}],
        }).encode('utf-8')
        req = urllib.request.Request(
            'https://api.anthropic.com/v1/messages',
            data=body,
            headers={
                'x-api-key': ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read())
        return data['content'][0]['text'].strip()
    except Exception as e:
        print(f'incremental_summary error: {e}')
        return None


def find_trending_spikes(groups_meta_list):
    spikes = []
    for articles, tid, cnt, hist_with_ts in groups_meta_list:
        if cnt < 5:
            continue
        if not hist_with_ts:
            continue
        prev_counts = [c for c, _ in hist_with_ts]
        avg_prev = sum(prev_counts) / len(prev_counts)
        if avg_prev > 0 and cnt > 3 * avg_prev:
            spikes.append({'title': articles[0]['title'], 'count': cnt, 'avg_prev': avg_prev})
    return spikes


def post_slack_spike(spikes):
    if not SLACK_WEBHOOK or not spikes:
        return
    lines = []
    for s in spikes:
        lines.append('\U0001f525 急上昇トピック検出: ' + s['title'] + ' (' + str(s['count']) + '件)')
    message = '\n'.join(lines)
    try:
        body = json.dumps({'text': message}).encode('utf-8')
        req = urllib.request.Request(
            SLACK_WEBHOOK,
            data=body,
            headers={'Content-Type': 'application/json'},
            method='POST',
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


def lambda_handler(event, context):
    # Step 1: 前回既知URLを読み込む（差分更新用）
    seen_urls = load_seen_articles()

    # Step 2: 全RSSフィードを取得
    all_articles = []
    for feed in RSS_FEEDS:
        fetched = fetch_rss(feed)
        all_articles.extend(fetched)
        print(f'[{feed["genre"]}] {feed["url"].split("/")[2]}: {len(fetched)}件')

    print(f'合計: {len(all_articles)}記事')

    # Step 3: 差分チェック
    current_urls = {a['url'] for a in all_articles}
    new_urls = current_urls - seen_urls

    if seen_urls and not new_urls:
        print('新規記事なし。DynamoDB/Claude API 呼び出しをスキップします。')
        save_seen_articles(current_urls)
        return {'statusCode': 200,
                'body': json.dumps({'articles': len(all_articles), 'new': 0, 'skipped': True})}

    print(f'新規記事: {len(new_urls)}件 / 既知: {len(seen_urls)}件')

    # Step 3.5: 今回取得URLを先に保存
    save_seen_articles(current_urls)

    groups = cluster(all_articles)
    print(f'トピック数: {len(groups)}')

    groups_sorted = sorted(groups, key=lambda g: len({a['source'] for a in g}) * 10, reverse=True)

    now    = datetime.now(timezone.utc)
    ts_key = now.strftime('%Y%m%dT%H%M%SZ')
    ts_iso = now.isoformat()

    saved_ids = []
    groups_meta_list = []
    ogp_fetched = 0
    api_calls_this_run = 0

    from config import table

    for rank, g in enumerate(groups_sorted):
        tid    = topic_fingerprint(g)
        cnt    = len(g)
        genres = dominant_genres(g)
        genre  = genres[0]
        lang   = dominant_lang(g)
        hist  = recent_counts(tid)
        groups_meta_list.append((g, tid, cnt, hist))
        st    = calc_status(hist, cnt)
        score, media, hb = calc_score(g)

        last_article_ts = max((a.get('published_ts', 0) for a in g), default=0)
        score = apply_time_decay(score, last_article_ts)
        score = max(1, int(score * source_diversity_score(g)))
        velocity_score = calc_velocity_score(g)

        existing = table.get_item(Key={'topicId': tid, 'SK': 'META'}).get('Item', {})

        if existing.get('aiGenerated') and existing.get('generatedTitle'):
            gen_title = existing['generatedTitle']
        else:
            gen_title = existing.get('generatedTitle') or extractive_title(g)

        existing_summary = existing.get('generatedSummary', '')
        _is_old_extractive = existing_summary and '複数の報道' in existing_summary and '関連して' in existing_summary
        if existing.get('aiGenerated') and existing_summary and not _is_old_extractive:
            gen_summary = existing_summary
        else:
            gen_summary = extractive_summary(g) if cnt >= 3 else None

        _has_valid_summary = bool(
            existing.get('aiGenerated') and
            existing.get('generatedSummary') and
            not _is_old_extractive
        )
        pending_ai = not _has_valid_summary

        _all_entities = extract_entities(' '.join(a['title'] for a in g))
        _main_entity  = list(_all_entities)[0] if _all_entities else ''
        log_summary_pattern(tid, _main_entity, cnt, 'extractive' if pending_ai else 'existing')

        image_url = existing.get('imageUrl') or next(
            (a.get('imageUrl') for a in g if a.get('imageUrl')), None
        )
        if not image_url and cnt >= 2 and ogp_fetched < 20:
            jp_urls = [a['url'] for a in g if '.jp' in a.get('url', '')]
            check_urls = jp_urls[:2] + [a['url'] for a in g[:3] if a['url'] not in jp_urls]
            for u in check_urls[:3]:
                image_url = fetch_ogp_image(u)
                if image_url:
                    ogp_fetched += 1
                    break

        velocity = calc_velocity(hist, cnt, ts_iso)

        existing_lifecycle = existing.get('lifecycleStatus', '')
        if existing_lifecycle == 'legacy':
            lifecycle_status = 'legacy'
        else:
            lifecycle_status = compute_lifecycle_status(score, last_article_ts, velocity_score, cnt)

        item = {
            'topicId':          tid,
            'SK':               'META',
            'title':            g[0]['title'],
            'generatedTitle':   gen_title or g[0]['title'],
            'status':           st,
            'genre':            genre,
            'genres':           genres,
            'lang':             lang,
            'articleCount':     cnt,
            'mediaCount':       media,
            'hatenaCount':      hb,
            'score':            score,
            'velocity':         velocity,
            'velocityScore':    velocity_score,
            'lastUpdated':      ts_iso,
            'lastArticleAt':    last_article_ts,
            'lifecycleStatus':  lifecycle_status,
            'sources':          list({a['source'] for a in g}),
            'pendingAI':        pending_ai,
        }
        if gen_summary:                    item['generatedSummary'] = gen_summary
        if image_url:                      item['imageUrl']         = image_url
        if existing.get('aiGenerated'):    item['aiGenerated']      = True
        table.put_item(Item=item)
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
                    'title': a['title'], 'url': a['url'],
                    'source': a['source'], 'pubDate': a['pubDate'],
                    'publishedAt': a.get('published_ts', 0),
                } for a in g
            }.values()))[:20],
        })
        saved_ids.append(tid)

    if S3_BUCKET:
        topics = get_all_topics()
        topics_active = [t for t in topics if t.get('lifecycleStatus', 'active') not in ('legacy', 'archived')]
        topics_active = sorted(topics_active, key=lambda x: int(x.get('score', 0) or 0), reverse=True)[:1000]
        print(f'O(n²)処理対象: {len(topics_active)}件 / 全{len(topics)}件')

        related_map = find_related_topics(topics_active)
        for t in topics:
            t['relatedTopics'] = related_map.get(t.get('topicId', ''), [])

        topic_entities_map = {
            t['topicId']: extract_entities(
                (t.get('generatedTitle') or t.get('title', ''))
            )
            for t in topics_active
        }
        parent_map = detect_topic_hierarchy(topics_active, topic_entities_map)

        child_to_parent = {}
        parent_to_children = {}
        for tid_b, tid_a in parent_map.items():
            child_to_parent[tid_b] = tid_a
            parent_to_children.setdefault(tid_a, [])
            child_t = next((t for t in topics if t['topicId'] == tid_b), None)
            if child_t:
                parent_to_children[tid_a].append({
                    'topicId': tid_b,
                    'title': child_t.get('generatedTitle') or child_t.get('title', ''),
                })

        for t in topics:
            tid = t['topicId']
            if tid in child_to_parent:
                t['parentTopicId'] = child_to_parent[tid]
            if tid in parent_to_children:
                t['childTopics'] = parent_to_children[tid]

        def _norm_title(t):
            s = (t.get('generatedTitle') or t.get('title', '')).strip()
            s = s.replace('｢','「').replace('｣','」').replace('　',' ')
            s = re.sub(r'\s+', ' ', s)
            s = re.sub(r'\s*[-－–|｜]\s*[^\s].{1,25}$', '', s)
            return s.lower()[:50]

        def _core_key(t):
            s = (t.get('generatedTitle') or t.get('title', '')).lower()
            s = re.sub(r'[「」【】・、。,!?！？\[\]()（）『』""\'\'#＃]', '', s)
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
        topics_deduped = [t for t in topics_deduped_all if t.get('lifecycleStatus', 'active') not in ('legacy', 'archived')][:2000]

        write_s3('api/topics.json', {
            'topics': topics_deduped,
            'trendingKeywords': extract_trending_keywords(topics_deduped),
            'updatedAt': ts_iso,
        })

        def _needs_ai(tid):
            t = next((x for x in topics if x.get('topicId') == tid), None)
            if not t: return True
            return not (t.get('aiGenerated') and t.get('generatedSummary'))

        pending_ids = [tid for tid in saved_ids if _needs_ai(tid)]
        write_s3('api/pending_ai.json', {'topicIds': pending_ids, 'updatedAt': ts_iso})
        generate_rss(topics, ts_iso)
        generate_sitemap(topics)

        s3_write_ids = {t['topicId'] for t in topics_deduped[:300]}
        s3_written = 0
        for tid in saved_ids:
            if tid not in s3_write_ids:
                continue
            meta, snaps, views = get_topic_detail(tid)
            if meta:
                s3_written += 1
                meta['relatedTopics'] = related_map.get(tid, [])
                if tid in child_to_parent:
                    meta['parentTopicId'] = child_to_parent[tid]
                if tid in parent_to_children:
                    meta['childTopics'] = parent_to_children[tid]
                write_s3(f'api/topic/{tid}.json', {
                    'meta': meta,
                    'timeline': [
                        {'timestamp': s['timestamp'],
                         'articleCount': s['articleCount'],
                         'score': s.get('score', 0),
                         'hatenaCount': s.get('hatenaCount', 0),
                         'articles': s.get('articles', [])}
                        for s in snaps
                    ],
                    'views': [
                        {'date': v['date'], 'count': int(v.get('count', 0))}
                        for v in views
                    ],
                })
        print(f'S3書き出し完了: {s3_written}件')

    print(f'Claude API呼び出し回数: {api_calls_this_run} / {MAX_API_CALLS}')

    spikes = find_trending_spikes(groups_meta_list)
    if spikes:
        post_slack_spike(spikes)

    cleanup_stale(now)

    save_seen_articles(current_urls)

    return {'statusCode': 200,
            'body': json.dumps({'articles': len(all_articles), 'new': len(new_urls), 'topics': len(groups_sorted), 'api_calls': api_calls_this_run, 'ts': ts_key})}
