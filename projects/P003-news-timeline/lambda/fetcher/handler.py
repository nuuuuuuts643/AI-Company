import json
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from config import (
    SLACK_WEBHOOK, S3_BUCKET,
    RSS_FEEDS, SNAP_TTL_DAYS, table, INACTIVE_LIFECYCLE_STATUSES, s3,
    SOURCE_TIER_MAP, TIER_WEIGHTS, UNCERTAINTY_PATTERNS,
    TECH_NICHE_KEYWORDS, TECH_GENERAL_KEYWORDS,
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
    write_s3, get_all_topics, get_topic_detail,
    recent_counts, calc_velocity, validate_topics_exist,
    load_seen_articles, save_seen_articles,
    generate_rss, generate_sitemap,
)


def fetch_rss(feed):
    articles = []
    url, genre, lang = feed['url'], feed['genre'], feed.get('lang', 'ja')
    feed_tier = feed.get('tier', 3)  # フィード単位のtier（デフォルト3）
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
                if any(p.search(title) for p in _DIGEST_SKIP_PATS):
                    continue
                source_name = extract_source_name(item, link, url)
                # ソース名からtierを解決（Google News経由記事など）
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


# ── 完全スキップ: 日次まとめ・ヘッドライン集記事 ─────────────────────────────
# 「N月N日のヘッドライン」「今日のニュースまとめ」等、それ自体が独立したトピックではなく
# 他記事の見出しを羅列しただけのメタ記事。フロントでは1記事トピックとして表示されてしまう。
_DIGEST_SKIP_PATS = [
    re.compile(r'\d{4}年\d{1,2}月\d{1,2}日の.{0,10}ヘッドライン'),
    re.compile(r'\d{1,2}月\d{1,2}日.{0,10}ヘッドライン'),
    re.compile(r'今日のニュースまとめ'),
    re.compile(r'今週のニュースまとめ'),
    re.compile(r'^【\d{1,2}月\d{1,2}日】.{0,30}まとめ'),
    re.compile(r'ニュースまとめ[：:\s（(]'),
    re.compile(r'^週刊.{0,20}まとめ$'),
    re.compile(r'本日のヘッドライン'),
    re.compile(r'ヘッドラインニュース$'),
    # Yahoo!ファイナンス 株価ページ（ニュースではなくデータページ）
    re.compile(r'株価・株式情報\s*[-–]\s*Yahoo!ファイナンス'),
    re.compile(r'【\d{3,5}】[：:].{0,20}株価'),
    re.compile(r'掲示板\s*[-–]\s*Yahoo!ファイナンス'),
]

# ── 二次情報フィルター ────────────────────────────────────────────────────────
#
# パターン定義: (正規表現, ベース係数, weight_key)
# weight_key は filter-weights.json のキーと対応する。
# lifecycle Lambda が週次で重みを 0.1 ずつ調整し S3 に保存する（TODO: lifecycle側実装）。
#
_OPINION_PATS = [
    (r'について考える', 0.5, 'opinion:について考える'),
    (r'を考える',       0.5, 'opinion:を考える'),
    (r'の問題点',       0.5, 'opinion:の問題点'),
    (r'を分析',         0.5, 'opinion:を分析'),
    (r'の真相',         0.5, 'opinion:の真相'),
    (r'とは何か',       0.5, 'opinion:とは何か'),
    (r'はなぜ',         0.5, 'opinion:はなぜ'),
    (r'すべきか',       0.5, 'opinion:すべきか'),
    (r'の危機',         0.5, 'opinion:の危機'),
    (r'か？$',          0.5, 'opinion:か？'),
    (r'のか$',          0.5, 'opinion:のか'),
    (r'だろうか',       0.5, 'opinion:だろうか'),
    (r'コラム',         0.5, 'opinion:コラム'),
    (r'オピニオン',     0.5, 'opinion:オピニオン'),
    (r'解説[：:]',      0.5, 'opinion:解説'),
    (r'考察[：:]',      0.5, 'opinion:考察'),
]

_SECONDARY_PATS = [
    (r'と報じた',       0.6, 'secondary:と報じた'),
    (r'が報じた',       0.6, 'secondary:が報じた'),
    (r'が伝えた',       0.6, 'secondary:が伝えた'),
    (r'が明らかにした', 0.6, 'secondary:が明らかにした'),
    (r'によると',       0.6, 'secondary:によると'),
    (r'によれば',       0.6, 'secondary:によれば'),
    (r'と伝えた',       0.6, 'secondary:と伝えた'),
    (r'と明かした',     0.6, 'secondary:と明かした'),
    (r'報道によ',       0.6, 'secondary:報道によ'),
    (r'各紙が',         0.6, 'secondary:各紙が'),
    (r'各社が',         0.6, 'secondary:各社が'),
]

# デフォルト重み（初期値 1.0）。lifecycle Lambda が調整後 S3 に書き込む
_DEFAULT_WEIGHTS: dict = {
    **{key: 1.0 for _, _, key in _OPINION_PATS},
    **{key: 1.0 for _, _, key in _SECONDARY_PATS},
    'secondary:title_reporting': 1.0,
}

# Lambda コールド起動時にS3から読み込むキャッシュ（ウォーム呼び出しでは使い回す）
_FILTER_WEIGHTS: dict = {}
_FILTER_WEIGHTS_LOADED: bool = False


def load_filter_weights() -> None:
    """
    S3 から api/filter-weights.json を読み込み _FILTER_WEIGHTS に格納する。
    コールド起動時のみ実行（ウォーム呼び出しは既存キャッシュを使う）。
    """
    global _FILTER_WEIGHTS, _FILTER_WEIGHTS_LOADED
    if _FILTER_WEIGHTS_LOADED:
        return
    _FILTER_WEIGHTS_LOADED = True
    _FILTER_WEIGHTS.update(_DEFAULT_WEIGHTS)  # まずデフォルトで初期化
    if not S3_BUCKET:
        return
    try:
        resp = s3.get_object(Bucket=S3_BUCKET, Key='api/filter-weights.json')
        loaded = json.loads(resp['Body'].read()).get('weights', {})
        _FILTER_WEIGHTS.update(loaded)  # S3値で上書き
        print(f'filter-weights.json ロード完了: {len(_FILTER_WEIGHTS)}パターン')
    except s3.exceptions.NoSuchKey:
        print('filter-weights.json 未作成 → デフォルト値使用')
    except Exception as e:
        print(f'filter-weights.json 読み込みエラー → デフォルト値使用: {e}')


def _effective_mult(base: float, weight_key: str) -> float:
    """
    パターン重みを適用した実効係数を計算する。
    実効係数 = 1.0 - (1.0 - base) × weight
      weight=1.0 → base そのまま
      weight=0.5 → ペナルティ軽減（過剰検出時に lifecycle が下げる）
      weight=2.0 → ペナルティ強化（適切検出時に lifecycle が上げる）
    """
    weight = _FILTER_WEIGHTS.get(weight_key, 1.0)
    effective = 1.0 - (1.0 - base) * weight
    return max(0.2, min(1.0, effective))


def is_secondary_article(title: str, description: str = '') -> tuple:
    """
    記事タイトル・本文冒頭を解析し、二次情報や意見記事を検出する。
    戻り値: (multiplier: float, pattern_key: str | None)
      - 1.0, None       → 問題なし
      - <1.0, 'key'     → 減点対象（key はフィードバック記録用）
    """
    text = (title or '') + ' ' + (description or '')
    t = title or ''

    for pat, base, key in _OPINION_PATS:
        if re.search(pat, t):
            return _effective_mult(base, key), key

    for pat, base, key in _SECONDARY_PATS:
        if re.search(pat, text):
            return _effective_mult(base, key), key

    if re.search(r'.{2,15}(報道|報じ|伝え)', t):
        key = 'secondary:title_reporting'
        return _effective_mult(0.6, key), key

    return 1.0, None


def _apply_secondary_penalty(g: list) -> tuple:
    """
    グループ内記事を評価し、二次情報・意見記事の割合に応じた係数とフィードバックを返す。
    グループ内の過半数が減点対象の場合のみグループ全体に適用する。
    戻り値: (penalty: float, feedback_entries: list)
    """
    if not g:
        return 1.0, []

    results = [(is_secondary_article(a.get('title', '')), a) for a in g]
    penalized = [((mult, key), a) for (mult, key), a in results if mult < 1.0]

    if len(penalized) > len(g) / 2:
        all_mults = [mult for (mult, _), _ in results]
        avg_penalty = sum(all_mults) / len(all_mults)
        feedback = [{
            'url':        a.get('url', ''),
            'title':      a.get('title', '')[:80],
            'pattern':    key,
            'multiplier': round(mult, 4),
        } for (mult, key), a in penalized]
        return avg_penalty, feedback

    return 1.0, []


def detect_uncertainty(text: str) -> str:
    """
    記事タイトル・概要テキストから不確実表現を検出し、信頼性ラベルを返す。
    戻り値: 'unverified' | 'uncertain' | 'stated'

    設計方針: 「嘘を判定する」のではなく「情報の確実度の材料を可視化する」のみ。
    断定的な判断はせず、ユーザーへの参考情報として提供する。
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
    """
    トピック内の全記事のreliabilityを集計し、トピック全体の信頼性を返す。
    過半数がuncertain以上の場合に判定に反映する。
    """
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
    同一トピック内の記事群で、数値が大きく食い違う場合にTrueを返す。
    「情報に食い違いがある可能性」を示すだけで、真偽判定はしない。
    同一文脈のコンテキスト語（人/億/万/円/名など）に隣接する数値を比較する。
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
    max_val = max(all_nums)
    min_val = min(all_nums)
    # ゼロ除算回避 + 2倍以上の乖離を「食い違いの可能性あり」と判断
    if min_val > 0 and max_val / min_val >= 2.0:
        return True
    return False


def apply_tier_and_diversity_scoring(articles: list, velocity_score: float) -> float:
    """
    ソースのtier重み・集中ペナルティ・多様性ボーナスをvelocityScoreに適用する。

    - Tier重み: 各記事のtierに応じた重みの平均を掛ける
    - ソース集中ペナルティ: 1社が60%超 → 0.8倍（話題の広がりが小さい）
    - ソース多様性ボーナス: ユニークソース4社以上 → 1.1倍
    """
    if not articles:
        return velocity_score

    # Tier重みの平均を計算
    tier_mults = [TIER_WEIGHTS.get(a.get('tier', 3), 0.8) for a in articles]
    avg_tier_weight = sum(tier_mults) / len(tier_mults)
    velocity_score = round(velocity_score * avg_tier_weight, 4)

    # ソース集中ペナルティ
    sources = [a.get('source', '') for a in articles if a.get('source')]
    if sources:
        from collections import Counter
        source_counts = Counter(sources)
        top_source_ratio = source_counts.most_common(1)[0][1] / len(sources)
        if top_source_ratio > 0.6:
            velocity_score = round(velocity_score * 0.8, 4)

    # ソース多様性ボーナス
    unique_sources = len({a.get('source', '') for a in articles if a.get('source')})
    if unique_sources >= 4:
        velocity_score = round(velocity_score * 1.1, 4)

    return velocity_score


def apply_tech_audience_filter(topic_title: str, topic_summary: str, genre: str, velocity: float) -> float:
    """
    テック記事を一般向けかどうかでvelocityScoreを調整する。

    - 一般向けキーワードあり → スコアそのまま
    - ニッチキーワードあり   → velocityScore × 0.3（大幅ダウン）
    - どちらでもない         → velocityScore × 0.7（やや下げる）
    """
    if genre != 'テクノロジー':
        return velocity

    text = f"{topic_title} {topic_summary or ''}"

    # 一般向けキーワードがあればそのまま
    if any(kw in text for kw in TECH_GENERAL_KEYWORDS):
        return velocity

    # ニッチキーワードがあれば大幅ダウン
    if any(kw in text for kw in TECH_NICHE_KEYWORDS):
        print(f'テックニッチフィルター適用（×0.3）: {topic_title[:40]}')
        return round(velocity * 0.3, 4)

    # どちらでもない → やや下げる
    print(f'テック一般度不明フィルター適用（×0.7）: {topic_title[:40]}')
    return round(velocity * 0.7, 4)


def record_filter_feedback(decisions: list, ts_key: str) -> None:
    """
    フィルター判定ログを S3 に保存する（1実行 = 1ファイル）。
    保存先: api/filter-feedback/{ts_key}.json
    lifecycle Lambda はこのプレフィックス以下を週次で集計し、
    パターンの過剰/適切検出を判断して filter-weights.json を更新する
    （TODO: lifecycle/handler.py に実装予定）。
    """
    if not decisions or not S3_BUCKET:
        return
    try:
        key = f'api/filter-feedback/{ts_key}.json'
        body = json.dumps(
            {'runAt': ts_key, 'count': len(decisions), 'decisions': decisions},
            ensure_ascii=False,
        ).encode('utf-8')
        s3.put_object(
            Bucket=S3_BUCKET, Key=key,
            Body=body,
            ContentType='application/json',
            CacheControl='no-cache',
        )
        print(f'フィルターフィードバック記録: {len(decisions)}件 → {key}')
    except Exception as e:
        print(f'フィルターフィードバック記録エラー: {e}')


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

        last_article_ts = max((a.get('published_ts', 0) for a in g), default=0)
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

        pending_ai = not bool(
            existing.get('aiGenerated') and existing.get('generatedSummary') and not _is_old_extractive
        )

        image_url = (
            existing.get('imageUrl') or
            next((a.get('imageUrl') for a in g if a.get('imageUrl')), None) or
            ogp_results.get(tid)
        )

        velocity = calc_velocity(hist, cnt, ts_iso)

        if existing.get('lifecycleStatus') == 'legacy':
            lifecycle_status = 'legacy'
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
            'velocity':        velocity,
            'velocityScore':   velocity_score,
            'lastUpdated':     ts_iso,
            'lastArticleAt':   last_article_ts,
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
        existing_tids = {t['topicId'] for t in topics}
        for item in current_run_metas.values():
            if item['topicId'] not in existing_tids:
                topics.append(item)
                existing_tids.add(item['topicId'])

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
        # 記事1件かつvelocity=0の死亡トピックをtopics.jsonから除外（ストーリーにならないため）
        topics_deduped = [
            t for t in topics_deduped_all
            if t.get('lifecycleStatus', 'active') not in INACTIVE_LIFECYCLE_STATUSES
            and (int(t.get('articleCount', 0) or 0) >= 2 or float(t.get('velocityScore', 0) or 0) > 0)
        ][:2000]

        write_s3('api/topics.json', {
            'topics':          topics_deduped,
            'trendingKeywords': extract_trending_keywords(topics_deduped),
            'updatedAt':       ts_iso,
        })

        topic_map   = {t['topicId']: t for t in topics}
        pending_ids = [tid for tid in saved_ids
                       if not (topic_map.get(tid, {}).get('aiGenerated') and
                               topic_map.get(tid, {}).get('generatedSummary'))]
        write_s3('api/pending_ai.json', {'topicIds': pending_ids, 'updatedAt': ts_iso})
        generate_rss(topics, ts_iso)
        generate_sitemap(topics)

        s3_written = 0
        for tid in saved_ids:
            meta, snaps, views = get_topic_detail(tid)
            if meta:
                s3_written += 1
                meta['relatedTopics'] = related_map.get(tid, [])
                if tid in child_to_parent:   meta['parentTopicId'] = child_to_parent[tid]
                if tid in parent_to_children: meta['childTopics']   = parent_to_children[tid]
                write_s3(f'api/topic/{tid}.json', {
                    'meta': meta,
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
