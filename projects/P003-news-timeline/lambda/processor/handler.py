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
    update_topic_s3_files_parallel,
    write_s3, notify_slack_error, generate_and_upload_sitemap,
    generate_and_upload_rss, generate_and_upload_news_sitemap,
)


def lambda_handler(event, context):
    start_time = time.time()
    print(f'[Processor] 開始: {datetime.now(timezone.utc).isoformat()}')

    pending = get_pending_topics(max_topics=100)
    print(f'[Processor] pendingAI=True トピック数: {len(pending)}')

    api_calls  = 0
    processed  = 0
    skipped    = 0
    ai_updates = {}

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

        if cnt >= MIN_ARTICLES_FOR_TITLE:
            new_title = generate_title(articles)
            if new_title:
                gen_title    = new_title
                api_calls   += 1
                ai_succeeded = True
                print(f'  [Claude タイトル] {tid[:8]}... → {new_title[:30]}')

        gen_story = None
        if cnt >= MIN_ARTICLES_FOR_SUMMARY and api_calls < MAX_API_CALLS:
            new_story = generate_story(articles)
            if new_story:
                gen_story    = new_story
                api_calls   += 1
                ai_succeeded = True
                print(f'  [Claude ストーリー] {tid[:8]}... phase={new_story.get("phase")} timeline={len(new_story.get("timeline", []))}件')

        update_topic_with_ai(tid, gen_title, gen_story, ai_succeeded=ai_succeeded)
        processed += 1
        ai_updates[tid] = {
            'generatedTitle':   gen_title,
            'generatedSummary': gen_story['aiSummary']      if gen_story else None,
            'spreadReason':     gen_story['spreadReason']   if gen_story else None,
            'forecast':         gen_story['forecast']       if gen_story else None,
            'storyTimeline':    gen_story['timeline']       if gen_story else None,
            'storyPhase':       gen_story['phase']          if gen_story else None,
            'aiGenerated':      ai_succeeded,
        }

    elapsed = time.time() - start_time
    print(f'[Processor] 完了: 処理={processed}件 / API呼び出し={api_calls}回 / スキップ={skipped}件 / {elapsed:.1f}s')

    if processed > 0:
        # 個別トピックS3ファイルをAIデータで並列更新（topic.htmlがAI要約を表示できるように）
        update_topic_s3_files_parallel(ai_updates)

        try:
            topics = get_all_topics_for_s3()
            for t in topics:
                # 処理済みトピックはpendingAIを解除（topics.jsonでも反映）
                if t.get('aiGenerated') or t.get('generatedSummary'):
                    t['pendingAI'] = False
                upd = ai_updates.get(t.get('topicId', ''))
                if upd:
                    t['pendingAI'] = False
                    if upd.get('generatedTitle'):            t['generatedTitle']   = upd['generatedTitle']
                    if upd.get('generatedSummary'):          t['generatedSummary'] = upd['generatedSummary']
                    if upd.get('spreadReason'):              t['spreadReason']     = upd['spreadReason']
                    if upd.get('forecast'):                  t['forecast']         = upd['forecast']
                    if upd.get('storyTimeline') is not None: t['storyTimeline']    = upd['storyTimeline']
                    if upd.get('storyPhase'):                t['storyPhase']       = upd['storyPhase']
                    if upd.get('aiGenerated'):               t['aiGenerated']      = True
            ts_iso = datetime.now(timezone.utc).isoformat()
            write_s3('api/topics.json', {
                'topics':        topics,
                'updatedAt':     ts_iso,
                'processedByAI': processed,
                'aiCallsUsed':   api_calls,
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
