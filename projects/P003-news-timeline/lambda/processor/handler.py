"""
lambda/processor/handler.py
─────────────────────────────────────────────────────────────────────────────
Stage 2: バッチAI処理 Lambda
  スケジュール: 1日3回 JST 7:00 / 12:00 / 18:00
  EventBridge: cron(0 22,3,9 * * ? *)  ← UTC 22:00/03:00/09:00

依存モジュール:
  proc_config.py  — 定数・boto3クライアント・テキストユーティリティ
  proc_ai.py      — Claude Haiku 呼び出し・抽出的フォールバック
  proc_storage.py — DynamoDB/S3アクセス・Slack通知
─────────────────────────────────────────────────────────────────────────────
"""
import json
import time
from datetime import datetime, timezone

from proc_config import MAX_API_CALLS, MIN_ARTICLES_FOR_TITLE, MIN_ARTICLES_FOR_SUMMARY
from proc_ai import generate_title, generate_story
from proc_storage import (
    get_pending_topics, get_latest_articles_for_topic,
    update_topic_with_ai, get_all_topics_for_s3,
    update_topic_s3_files_parallel, generate_ogp_image,
    write_s3, notify_slack_error, generate_and_upload_sitemap,
    generate_and_upload_rss, generate_and_upload_news_sitemap,
    batch_generate_static_html,
)

_PROC_INTERNAL = {'SK', 'pendingAI', 'ttl', 'spreadReason', 'forecast', 'storyTimeline'}


def lambda_handler(event, context):
    start_time = time.time()
    print(f'[Processor] 開始: {datetime.now(timezone.utc).isoformat()}')

    # 特殊モード: 既存トピックの静的HTML一括生成
    if event.get('regenerateStaticHtml'):
        count = batch_generate_static_html(max_topics=event.get('maxTopics', 500))
        return {'statusCode': 200, 'body': json.dumps({'generated': count})}

    # 特殊モード: サイトマップ・RSS・静的JSON再生成のみ（AI呼び出しなし）
    if event.get('regenerateSitemap'):
        try:
            topics, trending_keywords = get_all_topics_for_s3()
            ts_iso = datetime.now(timezone.utc).isoformat()
            topics_pub = [{k: v for k, v in t.items() if k not in _PROC_INTERNAL} for t in topics]
            write_s3('api/topics.json', {
                'topics': topics_pub, 'trendingKeywords': trending_keywords,
                'updatedAt': ts_iso, 'processedByAI': 0, 'aiCallsUsed': 0,
            })
            generate_and_upload_sitemap(topics)
            generate_and_upload_rss(topics)
            generate_and_upload_news_sitemap(topics)
            return {'statusCode': 200, 'body': json.dumps({'topics': len(topics)})}
        except Exception as e:
            return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}

    pending = get_pending_topics(max_topics=100)
    print(f'[Processor] pendingAI=True トピック数: {len(pending)}')

    api_calls      = 0
    processed      = 0
    skipped        = 0
    ai_updates     = {}
    articles_cache = {}

    for topic in pending:
        if api_calls >= MAX_API_CALLS:
            print(f'[Processor] API呼び出し上限 ({MAX_API_CALLS}) 到達。残り {len(pending) - processed - skipped} 件は次回。')
            break

        tid = topic['topicId']
        cnt = int(topic.get('articleCount', 0) or 0)

        articles = get_latest_articles_for_topic(tid)
        if not articles:
            raw_title = topic.get('title', '')
            articles  = [{'title': raw_title}] if raw_title else []

        gen_title    = topic.get('generatedTitle')
        ai_succeeded = False

        # 既にAI処理済み(aiGenerated=True)かつタイトルがあればタイトル再生成をスキップ
        # → APIコスト半減・スループット2倍
        needs_title = (cnt >= MIN_ARTICLES_FOR_TITLE
                       and not (topic.get('aiGenerated') and gen_title))
        if needs_title:
            new_title = generate_title(articles)
            api_calls += 1
            time.sleep(1.5)
            if new_title:
                gen_title    = new_title
                ai_succeeded = True
                print(f'  [Claude タイトル] {tid[:8]}... → {new_title[:30]}')

        gen_story = None
        _is_minimal = (topic.get('summaryMode') == 'minimal' or cnt <= 2)
        needs_story = (cnt >= MIN_ARTICLES_FOR_SUMMARY
                       and not (topic.get('aiGenerated')
                                and (topic.get('storyTimeline') or _is_minimal)))
        if needs_story and api_calls < MAX_API_CALLS:
            new_story = generate_story(articles, article_count=cnt)
            api_calls += 1
            time.sleep(1.5)
            if new_story:
                gen_story    = new_story
                ai_succeeded = True
                mode = new_story.get('summaryMode', 'full')
                print(f'  [Claude ストーリー] {tid[:8]}... mode={mode} phase={new_story.get("phase")} timeline={len(new_story.get("timeline", []))}件')

        # OGP画像生成（imageUrl未設定の場合のみ。AI処理成否に関わらず実行）
        ogp_url = None
        if not topic.get('imageUrl'):
            try:
                title_for_ogp = gen_title or topic.get('generatedTitle') or topic.get('title', '')
                genres = topic.get('genres') or ([topic['genre']] if topic.get('genre') else [])
                ogp_url = generate_ogp_image(tid, title_for_ogp, genres[0] if genres else '')
                if ogp_url:
                    print(f'  [OGP] {tid[:8]}... 生成完了')
            except Exception as ogp_err:
                print(f'  [OGP] {tid[:8]}... 失敗（スキップ）: {ogp_err}')

        update_topic_with_ai(tid, gen_title, gen_story, ai_succeeded=ai_succeeded, image_url=ogp_url)
        processed += 1
        articles_cache[tid] = articles
        ai_updates[tid] = {
            'generatedTitle':   gen_title,
            'generatedSummary': gen_story['aiSummary']      if gen_story else None,
            'spreadReason':     gen_story['spreadReason']   if gen_story else None,
            'forecast':         gen_story['forecast']       if gen_story else None,
            'storyTimeline':    gen_story['timeline']       if gen_story else None,
            'storyPhase':       gen_story['phase']          if gen_story else None,
            'summaryMode':      gen_story['summaryMode']    if gen_story else None,
            'aiGenerated':      ai_succeeded,
            'imageUrl':         ogp_url,
        }

    elapsed = time.time() - start_time
    print(f'[Processor] 完了: 処理={processed}件 / API呼び出し={api_calls}回 / スキップ={skipped}件 / {elapsed:.1f}s')

    if processed > 0:
        # 個別トピックS3ファイルをAIデータで並列更新（静的HTML生成含む）
        update_topic_s3_files_parallel(ai_updates, articles_cache=articles_cache)

        try:
            topics, trending_keywords = get_all_topics_for_s3()
            for t in topics:
                upd = ai_updates.get(t.get('topicId', ''))
                if upd:
                    if upd.get('generatedTitle'):            t['generatedTitle']   = upd['generatedTitle']
                    if upd.get('generatedSummary'):          t['generatedSummary'] = upd['generatedSummary']
                    if upd.get('spreadReason'):              t['spreadReason']     = upd['spreadReason']
                    if upd.get('forecast'):                  t['forecast']         = upd['forecast']
                    if upd.get('storyTimeline') is not None: t['storyTimeline']    = upd['storyTimeline']
                    if upd.get('storyPhase'):                t['storyPhase']       = upd['storyPhase']
                    if upd.get('summaryMode'):               t['summaryMode']      = upd['summaryMode']
                    if upd.get('aiGenerated'):               t['aiGenerated']      = True
                    if upd.get('imageUrl') and not t.get('imageUrl'): t['imageUrl'] = upd['imageUrl']
            ts_iso = datetime.now(timezone.utc).isoformat()
            def _trim(t):
                d = {k: v for k, v in t.items() if k not in _PROC_INTERNAL}
                if d.get('generatedSummary'):
                    d['generatedSummary'] = d['generatedSummary'][:120]
                return d
            topics_pub = [_trim(t) for t in topics]
            write_s3('api/topics.json', {
                'topics':           topics_pub,
                'trendingKeywords': trending_keywords,
                'updatedAt':        ts_iso,
                'processedByAI':    processed,
                'aiCallsUsed':      api_calls,
            })
            print(f'[Processor] S3 topics.json 再生成完了 ({len(topics)}件)')
            generate_and_upload_sitemap(topics)
            generate_and_upload_rss(topics)
            generate_and_upload_news_sitemap(topics)
        except Exception as e:
            err = f'S3再生成エラー: {e}'
            print(f'[Processor] {err}')
            notify_slack_error(err)

    return {
        'statusCode': 200,
        'body': json.dumps({
            'pending':   len(pending),
            'processed': processed,
            'api_calls': api_calls,
            'skipped':   skipped,
        }),
    }
