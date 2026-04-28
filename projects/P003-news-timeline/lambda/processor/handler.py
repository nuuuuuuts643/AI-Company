"""
lambda/processor/handler.py
─────────────────────────────────────────────────────────────────────────────
Stage 2: バッチAI処理 Lambda
  スケジュール: 1日2回 JST 08:00/17:00 (2026-04-29 コスト削減のため日中2回に変更)
  EventBridge: cron(0 23,8 * * ? *)  ← UTC 23:00/08:00
  即時処理:    fetcher が新規トピック作成時に invoke (maxApiCalls=10 で少量処理)

依存モジュール:
  proc_config.py  — 定数・boto3クライアント・テキストユーティリティ
  proc_ai.py      — Claude Haiku 呼び出し・抽出的フォールバック
  proc_storage.py — DynamoDB/S3アクセス・Slack通知
─────────────────────────────────────────────────────────────────────────────
"""
import json
import time
from datetime import datetime, timezone

from proc_config import MAX_API_CALLS, MIN_ARTICLES_FOR_TITLE, MIN_ARTICLES_FOR_SUMMARY, PROCESSOR_SCHEMA_VERSION
from proc_ai import generate_title, generate_story, judge_prediction
from proc_storage import (
    get_pending_topics, get_topics_by_ids, get_latest_articles_for_topic,
    update_topic_with_ai, get_all_topics_for_s3,
    update_topic_s3_files_parallel, generate_ogp_image,
    write_s3, notify_slack_error, generate_and_upload_sitemap,
    generate_and_upload_rss, generate_and_upload_news_sitemap,
    batch_generate_static_html, backfill_missing_detail_json,
    auto_archive_incoherent, save_prediction_log,
    update_prediction_result, get_topics_for_prediction_judging,
    get_articles_added_after, generate_topics_card_json,
    generate_health_json,
    _is_keypoint_inadequate,
)

_PROC_INTERNAL = {'SK', 'pendingAI', 'ttl', 'spreadReason', 'forecast', 'storyTimeline', 'backgroundContext', 'background'}

# PRED# レコードを topics.json から除外するためのプレフィックスチェックは不要
# (get_all_topics_for_s3 が SK='META' のみ取得するため自動除外)


def lambda_handler(event, context):
    start_time = time.time()
    print(f'[Processor] 開始: {datetime.now(timezone.utc).isoformat()}')

    # Wallclock budget guard (T218 根本対策・2026-04-28)
    # Why: Tool Use 化で 1 API call が 5-15 秒に膨張、MAX_API_CALLS=200 だと
    #      200 * 10s = 2000s で Lambda Timeout (900s) を確実に越える。
    #      Timeout で in-flight 中断 → S3書き戻しフェーズ未実行 →
    #      processed 件の aiGenerated=True が topics.json に反映されない。
    # 仕組み: 残り Lambda 実行時間が WALLCLOCK_GUARD_MS を切ったら主ループを break。
    #         break 後の S3 書き戻し (update_topic_s3_files_parallel + topics.json 生成 +
    #         sitemap/RSS 生成) には ~100s 程度必要なので 120s 残す。
    # 観測: forceRegenerateAll は次回スケジュール (4x/day) で続きを処理するため、
    #       単発 invoke 上限 ≠ 全件処理の制約にならない。
    WALLCLOCK_GUARD_MS = 120_000  # 120秒残し: S3書き戻し + topics.json生成 + sitemap
    def _wallclock_remaining_ms():
        try:
            return context.get_remaining_time_in_millis()
        except Exception:
            return 9_000_000  # local test or context 不在時は無制限扱い
    def _wallclock_ok():
        return _wallclock_remaining_ms() > WALLCLOCK_GUARD_MS

    # 特殊モード: 既存トピックの静的HTML一括生成
    if event.get('regenerateStaticHtml'):
        count = batch_generate_static_html(max_topics=event.get('maxTopics', 500))
        return {'statusCode': 200, 'body': json.dumps({'generated': count})}

    # 特殊モード: detail JSON欠損トピックをDynamoDBから補完
    if event.get('backfillDetailJson'):
        filled = backfill_missing_detail_json()
        return {'statusCode': 200, 'body': json.dumps({'filled': filled})}

    # 特殊モード: 既存 archived/legacy メタに TTL 90日を後付け (コスト削減・1回限り)
    # 使い方: aws lambda invoke --function-name p003-processor --payload '{"backfillArchivedTtl":true}' /tmp/r.json
    if event.get('backfillArchivedTtl'):
        from proc_storage import add_ttl_to_existing_archived
        result = add_ttl_to_existing_archived()
        print(f'[Processor] backfillArchivedTtl: {result["ttl_added"]} 件 TTL 追加 / {result["protected"]} 件保護 (大規模・人気・親子関係・長期継続) / 合計 {result["total"]} 件処理')
        return {'statusCode': 200, 'body': json.dumps(result)}

    # 特殊モード: 全トピック完全削除 (核オプション・2026-04-27)
    # 使い方:
    #   件数確認(dry_run): aws lambda invoke --function-name p003-processor --payload '{"purgeAll":true,"dryRun":true}' /tmp/r.json
    #   実行(取り返し不可): aws lambda invoke --function-name p003-processor --payload '{"purgeAll":true,"confirm":"CONFIRM_PURGE_ALL_2026"}' /tmp/r.json
    # 削除対象: DynamoDB の p003-topics 全 META+SNAP / S3 api/topics.json / api/topic/*.json / topics/*.html
    # 保護対象: ユーザー データ (flotopic-favorites / flotopic-analytics / ai-company-comments) は別テーブルなので影響なし
    # 副作用: Google インデックス済みURL が 404 になる→SEO一時悪化。次回 fetcher 実行で全新規生成。
    if event.get('purgeAll'):
        from proc_config import table, s3
        from boto3.dynamodb.conditions import Attr
        if event.get('dryRun'):
            meta_count = 0; snap_count = 0
            scan_kwargs = {'Select': 'COUNT'}
            while True:
                r = table.scan(**scan_kwargs)
                meta_count += r.get('Count', 0)
                if not r.get('LastEvaluatedKey'): break
                scan_kwargs['ExclusiveStartKey'] = r['LastEvaluatedKey']
            print(f'[Processor] purgeAll dryRun: 全アイテム {meta_count} 件削除予定')
            return {'statusCode': 200, 'body': json.dumps({'dryRun': True, 'totalItems': meta_count, 'warning': 'これを実行すると取り戻せません。confirm=CONFIRM_PURGE_ALL_2026 を渡してください'})}
        if event.get('confirm') != 'CONFIRM_PURGE_ALL_2026':
            return {'statusCode': 400, 'body': json.dumps({'error': '安全のため、confirm=CONFIRM_PURGE_ALL_2026 を payload に含めてください'})}
        # 実削除
        from proc_storage import S3_BUCKET as _S3
        deleted_meta = 0; deleted_snap = 0
        scan_kwargs = {'ProjectionExpression': 'topicId,SK'}
        with table.batch_writer() as bw:
            while True:
                r = table.scan(**scan_kwargs)
                for item in r.get('Items', []):
                    bw.delete_item(Key={'topicId': item['topicId'], 'SK': item['SK']})
                    if item['SK'] == 'META': deleted_meta += 1
                    else: deleted_snap += 1
                if not r.get('LastEvaluatedKey'): break
                scan_kwargs['ExclusiveStartKey'] = r['LastEvaluatedKey']
        # S3 cleanup
        deleted_s3 = 0
        for prefix in ('api/topic/', 'topics/'):
            paginator = s3.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=_S3, Prefix=prefix):
                objs = [{'Key': o['Key']} for o in page.get('Contents', [])]
                if objs:
                    s3.delete_objects(Bucket=_S3, Delete={'Objects': objs})
                    deleted_s3 += len(objs)
        # topics.json と pending_ai.json を空に
        for k in ('api/topics.json', 'api/pending_ai.json'):
            try:
                s3.put_object(Bucket=_S3, Key=k, Body=json.dumps({'topics': [], 'topicIds': [], 'trendingKeywords': [], 'updatedAt': datetime.now(timezone.utc).isoformat()}), ContentType='application/json')
            except Exception:
                pass
        print(f'[Processor] purgeAll 完了: META={deleted_meta}件, SNAP={deleted_snap}件, S3 objects={deleted_s3}件')
        return {'statusCode': 200, 'body': json.dumps({'purged': True, 'metaDeleted': deleted_meta, 'snapDeleted': deleted_snap, 's3Deleted': deleted_s3})}

    # 特殊モード: 全トピックの AI を強制再生成 (新プロンプト適用のため・2026-04-27)
    # 使い方:
    #   コスト確認(dry_run): aws lambda invoke --function-name p003-processor --payload '{"forceRegenerateAll":true,"dryRun":true}' /tmp/r.json
    #   実行:                aws lambda invoke --function-name p003-processor --payload '{"forceRegenerateAll":true}' /tmp/r.json
    # コスト試算: Haiku 4.5 で 1 call ≈ $0.0023。110 トピック → ~$0.25。1回のinvokeで MAX_API_CALLS=200 件まで処理。
    # 注意: 一度しか実行しないこと。繰り返すとコストが積み上がる。
    if event.get('forceRegenerateAll'):
        from proc_storage import force_reset_pending_all
        if event.get('dryRun'):
            # topics.json から可視トピック数のみ取得 (DynamoDB全件scanの無駄を排除)
            from proc_storage import _load_visible_topic_ids
            visible_tids = _load_visible_topic_ids()
            count = len(visible_tids)
            est_cost_usd = round(count * 0.0023, 3)
            print(f'[Processor] forceRegenerateAll dryRun: topics.json可視 {count} 件対象 → 推定コスト ${est_cost_usd} (Haiku 4.5)')
            return {'statusCode': 200, 'body': json.dumps({'dryRun': True, 'targetCount': count, 'estimatedCostUsd': est_cost_usd})}
        reset_count = force_reset_pending_all()
        est_cost_usd = round(reset_count * 0.0023, 3)
        print(f'[Processor] forceRegenerateAll: {reset_count} 件を pendingAI=True にリセット → 推定コスト ${est_cost_usd}。通常処理ルートに合流して MAX_API_CALLS={int(MAX_API_CALLS)} 件まで処理')
        # リセット後は通常のスケジュール処理ルートに合流して MAX_API_CALLS まで処理
        # 続きは次回手動 invoke or 次回スケジュール (4x/day)で

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

    topic_id_filter = event.get('topic_ids')
    source = event.get('source', 'scheduled')
    if topic_id_filter:
        pending = get_topics_by_ids(topic_id_filter)
        print(f'[Processor] フェッチャートリガー (source={source}): {len(topic_id_filter)}件指定 → {len(pending)}件処理対象')
    else:
        pending = get_pending_topics(max_topics=100)
        print(f'[Processor] pendingAI=True トピック数: {len(pending)}')

    # event.maxApiCalls で上限をオーバーライド可能 (fetcher_trigger は 10 件など少量で即時処理)。
    # 不正値 (0/負/非数値) は MAX_API_CALLS にフォールバック。
    _override = event.get('maxApiCalls')
    try:
        _override_int = int(_override) if _override is not None else None
    except (TypeError, ValueError):
        _override_int = None
    effective_max_api_calls = _override_int if (_override_int and _override_int > 0) else MAX_API_CALLS
    if effective_max_api_calls != MAX_API_CALLS:
        print(f'[Processor] MAX_API_CALLS オーバーライド: {MAX_API_CALLS} → {effective_max_api_calls} (source={source})')

    api_calls      = 0
    processed      = 0
    skipped        = 0
    deferred_tier0 = 0  # T2026-0428-O: Tier-0 予約により後回しにした非 Tier-0 件数
    ai_updates     = {}
    articles_cache = {}
    # T2026-0428-AO: トピックごとに incremental か full かを記録 → S3 書き込み時に渡す
    incremental_map = {}

    # T2026-0428-O: 残り wallclock の 50% を Tier-0 (articles>=10 × aiGenerated=False)
    # 専用に予約する。Phase A (前半 50%) は Tier-0 が pending に残る限り非 Tier-0 を
    # 後回し → 次回スケジュールで処理。proc_storage._apply_tier0_budget でソート済の
    # ため通常は Tier-0 が先に消化されるが、本ガードは「Tier-0 を取り切る前に時間切れ」
    # を構造的に防ぐ物理ゲート (count budget=3 の補完)。
    def _is_tier0(t):
        try:
            ac = int(t.get('articleCount', 0) or 0)
        except (ValueError, TypeError):
            ac = 0
        return ac >= 10 and not t.get('aiGenerated')
    tier0_total = sum(1 for t in pending if _is_tier0(t))
    _initial_runtime_ms = max(0, _wallclock_remaining_ms() - WALLCLOCK_GUARD_MS)
    # phase A 終了時点での「残り時間」(ここを下回ったら Phase B = 全 topic 解放)
    TIER0_PHASE_END_REMAINING_MS = _wallclock_remaining_ms() - (_initial_runtime_ms // 2)
    tier0_processed = 0
    if tier0_total > 0:
        print(f'[Processor] Tier-0 (articles>=10 × aiGenerated=False) {tier0_total}件 / Phase A wallclock={(_initial_runtime_ms//2)/1000:.0f}s 予約')

    for topic in pending:
        if api_calls >= effective_max_api_calls:
            print(f'[Processor] API呼び出し上限 ({effective_max_api_calls}) 到達。残り {len(pending) - processed - skipped - deferred_tier0} 件は次回。')
            break
        if not _wallclock_ok():
            remaining_s = _wallclock_remaining_ms() / 1000
            print(f'[Processor] Wallclock guard 到達 (残り {remaining_s:.1f}s < {WALLCLOCK_GUARD_MS/1000:.0f}s)。残り {len(pending) - processed - skipped - deferred_tier0} 件は次回スケジュールで継続')
            break

        # T2026-0428-O: Tier-0 予約 — Phase A 中 (残り > TIER0_PHASE_END_REMAINING_MS)
        # かつ Tier-0 が未消化の間は、非 Tier-0 を skip して次回 invoke へ回す。
        _is_t0 = _is_tier0(topic)
        in_phase_a = _wallclock_remaining_ms() > TIER0_PHASE_END_REMAINING_MS
        if (not _is_t0) and in_phase_a and (tier0_total - tier0_processed) > 0:
            deferred_tier0 += 1
            continue

        tid = topic['topicId']
        cnt = int(topic.get('articleCount', 0) or 0)

        # 1件記事トピックはユーザーに表示されないためスキップ（API節約）
        if cnt < MIN_ARTICLES_FOR_TITLE:
            skipped += 1
            continue

        articles = get_latest_articles_for_topic(tid)
        if not articles:
            raw_title = topic.get('title', '')
            articles  = [{'title': raw_title}] if raw_title else []

        gen_title       = topic.get('generatedTitle')
        title_succeeded = False
        story_succeeded = False

        # 既にAI処理済み(aiGenerated=True)かつタイトルがあればタイトル再生成をスキップ
        # → APIコスト半減・スループット2倍
        needs_title = (cnt >= MIN_ARTICLES_FOR_TITLE
                       and not (topic.get('aiGenerated') and gen_title))
        if needs_title:
            new_title = generate_title(articles)
            api_calls += 1
            time.sleep(1.5)
            if new_title:
                gen_title       = new_title
                title_succeeded = True
                print(f'  [Claude タイトル] {tid[:8]}... → {new_title[:30]}')

        gen_story = None
        _is_minimal = cnt <= 2
        # T255 (2026-04-28 Cowork): keyPoint も skip 必須フィールドへ追加。
        # 旧 aiGenerated topic は keyPoint プロンプト追加 (commit 963ff61) 以前の処理結果のため
        # keyPoint=None のまま永久に skip されていた (本番 0/115 で確認済)。
        # 仕組み的対策: 必須フィールドリストを 1 箇所で管理し、新フィールド追加時の漏れを構造的に防ぐ。
        # T2026-0428-J/E: statusLabel / watchPoints も standard/full mode で必須化。
        # T2026-0429-KP (2026-04-29): keyPoint は bool() ではなく長さベース判定に変更。
        # 旧 bool() 判定は短い keyPoint (例: 21 字「ロシア撤退と過激派攻勢の…」) を「充足」と誤判定し、
        # proc_storage.needs_ai_processing が再生成キューに乗せても handler 側で skip されて
        # 永久に短いまま滞留していた (本番 38件)。proc_storage._is_keypoint_inadequate と
        # 100 字閾値を共有して定義の不整合を排除する。
        _required_full_fields = (
            (topic.get('storyTimeline') or _is_minimal),  # minimal は timeline 生成しない
            (topic.get('storyPhase')    or _is_minimal),  # minimal は phase 生成しない
            (not _is_keypoint_inadequate(topic.get('keyPoint'))),  # T2026-0429-KP: 100字閾値 / proc_storage と一致
            (bool(topic.get('statusLabel')) or _is_minimal),   # T2026-0428-J/E: standard/full のみ必須
            (bool(topic.get('watchPoints'))  or _is_minimal),
        )
        needs_story = (cnt >= MIN_ARTICLES_FOR_SUMMARY
                       and not (topic.get('aiGenerated') and all(_required_full_fields)))
        # T2026-0428-AH: storyPhase=='発端' かつ articleCount>=3 は再生成対象に含める。
        # proc_storage.py get_pending_topics 側の例外と対で機能させ、handler.py 側の skip
        # ロジックでも同じ topic を弾かないようにする (T219 プロンプト強化済の効果反映用)。
        if (not needs_story
                and topic.get('storyPhase') == '発端'
                and cnt >= 3):
            needs_story = True
        # 2026-04-29 案C: 「aiGenerated=True かつ AI 生成から 48h 以内 かつ 新記事 0 件」は skip。
        # 新記事の有無は lastUpdated > aiGeneratedAt で判定 (fetcher が記事追加時に lastUpdated を更新)。
        # 目的: pendingAI=True で再キューイングされたが実は変化のない topic で API call を浪費しない。
        if needs_story and topic.get('aiGenerated') and topic.get('aiGeneratedAt'):
            try:
                _ai_at = datetime.fromisoformat(str(topic['aiGeneratedAt']).replace('Z', '+00:00'))
                _last_upd_raw = topic.get('lastUpdated')
                _last_upd = datetime.fromisoformat(str(_last_upd_raw).replace('Z', '+00:00')) if _last_upd_raw else None
                _hours_since_ai = (datetime.now(timezone.utc) - _ai_at).total_seconds() / 3600
                _no_new_articles = (_last_upd is None) or (_last_upd <= _ai_at)
                if _hours_since_ai < 48 and _no_new_articles:
                    needs_story = False
                    skipped += 1
                    print(f'  [skip] {tid[:8]}... aiGen後{_hours_since_ai:.1f}h・新記事なし → 再生成 skip')
                    continue
            except Exception as _e:
                pass  # パース失敗時は通常処理
        if needs_story and api_calls < effective_max_api_calls:
            new_story = generate_story(articles, article_count=cnt)
            api_calls += 1
            time.sleep(1.5)
            if new_story:
                gen_story       = new_story
                story_succeeded = True
                mode = new_story.get('summaryMode', 'full')
                print(f'  [Claude ストーリー] {tid[:8]}... mode={mode} phase={new_story.get("phase")} timeline={len(new_story.get("timeline", []))}件')

        # T2026-0429-AISG (2026-04-29): aiGenerated=True / aiGeneratedAt 更新は **story 生成成功** にのみ紐付ける。
        # 旧実装は title 生成のみ成功した場合でも ai_succeeded=True としていたため、
        # gen_story=None のまま update_topic_with_ai が aiGenerated=True を書き、
        # keyPoint/storyPhase/statusLabel/perspectives 全部空のまま「処理済」扱いされる事故が発生 (本番 149件)。
        # 修正: title-only 成功は generatedTitle だけ更新する (update_topic_with_ai の generatedTitle 書込は ai_succeeded ガード外なので保たれる)。
        ai_succeeded = story_succeeded

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

        # T2026-0428-AO: 既に aiGenerated=True の topic は incremental モードで更新する。
        # = 既存フィールドを上書きせず、不足フィールドだけ補完する (heal/schema_version保護)。
        # 初回処理 (aiGenerated=False) は existing_meta=None で従来どおり全フィールド書き込み。
        _is_incremental = bool(topic.get('aiGenerated'))
        _existing_meta = topic if _is_incremental else None
        update_topic_with_ai(tid, gen_title, gen_story, ai_succeeded=ai_succeeded, image_url=ogp_url, existing_meta=_existing_meta)
        # 予測ログを時系列保存 (Phase 3 の土台・1日早く始めるほど早く遡及検証できる)
        save_prediction_log(tid, gen_story)
        # AI が「記事の中身が乖離」と判定した場合は自動で archive (思想: 雑なクラスタを視界から消す)
        archived = auto_archive_incoherent(tid, gen_story)
        if archived:
            skipped += 1
            continue
        processed += 1
        if _is_t0:
            tier0_processed += 1

        # T2026-0428-AS: 初回 AI 要約完了 → Bluesky 即時投稿マーカーを S3 に書き込む。
        # bluesky_agent.py が次回 cron tick (≤30分後) で消費して投稿する。
        # 条件: 既存 AI が無い (incremental ではない) × AI が実際に成功 × story 要約あり。
        # 注目度ベースの定期投稿 (post_daily) とは完全に独立した別トリガー。
        if (not _is_incremental) and ai_succeeded and gen_story and gen_story.get('aiSummary'):
            try:
                write_s3(f'bluesky/pending/{tid}.json', {
                    'topicId':   tid,
                    'title':     (gen_title or '')[:140],
                    'createdAt': datetime.now(timezone.utc).isoformat(),
                })
                print(f'  [Bluesky pending] {tid[:8]}... 初回要約完了マーカー作成')
            except Exception as _bp_err:
                print(f'  [Bluesky pending] {tid[:8]}... マーカー作成失敗: {_bp_err}')
        articles_cache[tid] = articles
        incremental_map[tid] = _is_incremental
        ai_updates[tid] = {
            'generatedTitle':       gen_title,
            'generatedSummary':     gen_story['aiSummary']           if gen_story else None,
            'keyPoint':             gen_story.get('keyPoint')         if gen_story else None,
            # T2026-0428-J/E: 新フィールド (statusLabel / watchPoints / predictionMadeAt / predictionResult)
            'statusLabel':          gen_story.get('statusLabel')      if gen_story else None,
            'watchPoints':          gen_story.get('watchPoints')      if gen_story else None,
            'predictionMadeAt':     (datetime.now(timezone.utc).isoformat() if gen_story and gen_story.get('outlook') else None),
            'predictionResult':     ('pending' if gen_story and gen_story.get('outlook') else None),
            'forecast':             gen_story['forecast']             if gen_story else None,
            'storyTimeline':        gen_story['timeline']             if gen_story else None,
            'storyPhase':           gen_story['phase']                if gen_story else None,
            'summaryMode':          gen_story['summaryMode']          if gen_story else None,
            'perspectives':         gen_story.get('perspectives')      if gen_story else None,
            'outlook':              gen_story.get('outlook')           if gen_story else None,
            'topicTitle':           gen_story.get('topicTitle')              if gen_story else None,
            'latestUpdateHeadline': gen_story.get('latestUpdateHeadline')    if gen_story else None,
            'topicCoherent':        gen_story.get('isCoherent', True)        if gen_story else None,
            'topicLevel':           gen_story.get('topicLevel')              if gen_story else None,
            'parentTopicTitle':     gen_story.get('parentTopicTitle')        if gen_story else None,
            'relatedTopicTitles':   gen_story.get('relatedTopicTitles', []) if gen_story else None,
            'genres':               gen_story.get('genres')          if gen_story else None,
            'genre':                gen_story['genres'][0]            if gen_story and gen_story.get('genres') else None,
            'aiGenerated':          ai_succeeded,
            'imageUrl':             ogp_url,
        }

    elapsed = time.time() - start_time
    print(f'[Processor] 完了: 処理={processed}件 (Tier-0 消化={tier0_processed}/{tier0_total}) / API呼び出し={api_calls}回 / スキップ={skipped}件 / Tier-0予約deferred={deferred_tier0}件 / {elapsed:.1f}s')

    if processed > 0:
        # 個別トピックS3ファイルをAIデータで並列更新（静的HTML生成含む）
        # T2026-0428-AO: incremental_map で既存 AI フィールドを heal 時に保護する
        update_topic_s3_files_parallel(ai_updates, articles_cache=articles_cache, incremental_map=incremental_map)

        try:
            topics, trending_keywords = get_all_topics_for_s3()
            # T2026-0428-AO: incremental モードのトピックは既存値があるフィールドを上書きしない
            def _empty(v):
                if v is None: return True
                if isinstance(v, str) and not v.strip(): return True
                if isinstance(v, (list, dict)) and len(v) == 0: return True
                return False
            for t in topics:
                tid_t = t.get('topicId', '')
                upd = ai_updates.get(tid_t)
                if upd:
                    is_inc = incremental_map.get(tid_t, False)
                    def _set(field, value, t=t, is_inc=is_inc):
                        if value is None or (isinstance(value, str) and not value):
                            return
                        if is_inc and not _empty(t.get(field)):
                            return
                        t[field] = value

                    if upd.get('generatedTitle'):                        _set('generatedTitle', upd['generatedTitle'])
                    if upd.get('generatedSummary'):                      _set('generatedSummary', upd['generatedSummary'])
                    if upd.get('keyPoint'):                              _set('keyPoint', upd['keyPoint'])
                    if upd.get('statusLabel'):                           _set('statusLabel', upd['statusLabel'])
                    if upd.get('watchPoints'):                           _set('watchPoints', upd['watchPoints'])
                    # outlook 書き込み時のみ predictionMadeAt / predictionResult もペアで反映
                    if upd.get('outlook'):
                        if not is_inc or _empty(t.get('outlook')):
                            t['outlook'] = upd['outlook']
                            if upd.get('predictionMadeAt'):
                                t['predictionMadeAt'] = upd['predictionMadeAt']
                            if upd.get('predictionResult'):
                                t['predictionResult'] = upd['predictionResult']
                    if upd.get('forecast'):                              _set('forecast', upd['forecast'])
                    if upd.get('storyTimeline') is not None:             _set('storyTimeline', upd['storyTimeline'])
                    if upd.get('storyPhase'):                            _set('storyPhase', upd['storyPhase'])
                    if upd.get('summaryMode'):                           _set('summaryMode', upd['summaryMode'])
                    if upd.get('perspectives') is not None:              _set('perspectives', upd['perspectives'])
                    if upd.get('topicTitle'):                            _set('topicTitle', upd['topicTitle'])
                    if upd.get('latestUpdateHeadline'):                  _set('latestUpdateHeadline', upd['latestUpdateHeadline'])
                    if upd.get('topicCoherent') is not None:             _set('topicCoherent', upd['topicCoherent'])
                    if upd.get('topicLevel'):                            _set('topicLevel', upd['topicLevel'])
                    if upd.get('parentTopicTitle'):                      _set('parentTopicTitle', upd['parentTopicTitle'])
                    if upd.get('relatedTopicTitles') is not None:        _set('relatedTopicTitles', upd['relatedTopicTitles'])
                    if upd.get('genres'):
                        if not is_inc or _empty(t.get('genres')):
                            t['genres'] = upd['genres']
                            t['genre']  = upd['genres'][0]
                    if upd.get('aiGenerated'):
                        t['aiGenerated']    = True
                        # T2026-0428-AO: schemaVersion は制御フィールド (常に最新へ更新)
                        t['schemaVersion']  = PROCESSOR_SCHEMA_VERSION
                    if upd.get('imageUrl') and not t.get('imageUrl'):    t['imageUrl']                = upd['imageUrl']
            ts_iso = datetime.now(timezone.utc).isoformat()
            # T2026-0428-J/E: generatedSummary[:120] truncate を撤廃。
            # 旧実装は文中切断 ("...直接的な譲歩に") を発生させ、ユーザーから「要約がカオス」と
            # 評価される主因となっていた。AI 側で 150 字以内に既に制約しているので、
            # 後段の文字数 cap は不要 (size 抑制目的なら他フィールドの方が効果大)。
            def _trim(t):
                return {k: v for k, v in t.items() if k not in _PROC_INTERNAL}
            topics_pub = [_trim(t) for t in topics]
            full_payload = {
                'topics':           topics_pub,
                'trendingKeywords': trending_keywords,
                'updatedAt':        ts_iso,
                'processedByAI':    processed,
                'aiCallsUsed':      api_calls,
            }
            write_s3('api/topics.json', full_payload)
            # T2026-0428-F Step1: topics-full.json は topics.json の互換 alias、
            # topics-card.json は一覧用 minimal payload (tid/title/articleCount/
            # genres/keyPoint/storyPhase/imageUrl/aiGenerated/score)。
            # frontend は当面 topics.json を使い続ける (Step2 で切替)。
            write_s3('api/topics-full.json', full_payload)
            # T265: card 用 minimal payload 生成は proc_storage.generate_topics_card_json() に集約。
            card_payload = generate_topics_card_json(topics_pub, ts_iso)
            write_s3('api/topics-card.json', card_payload)
            # T2026-0428-AQ: 本番監視用 health.json (keyPoint 充填率・空トピック件数・status)
            health_payload = generate_health_json(topics_pub, ts_iso)
            write_s3('api/health.json', health_payload)
            print(f'[Processor] S3 topics.json + topics-full.json + topics-card.json + health.json 再生成完了 ({len(topics)}件 / card={len(card_payload["topics"])}件 / health={health_payload["status"]})')
            generate_and_upload_sitemap(topics)
            generate_and_upload_rss(topics)
            generate_and_upload_news_sitemap(topics)
        except Exception as e:
            err = f'S3再生成エラー: {e}'
            print(f'[Processor] {err}')
            notify_slack_error(err)

    # detail JSON 欠損補完（topics.json に存在するが S3 に未作成のトピックを DynamoDB から補完）
    try:
        backfill_missing_detail_json()
    except Exception as e:
        print(f'[Processor] backfill error: {e}')

    # T2026-0428-PRED: AI 予想 (outlook) の自動当否判定
    # 1 日経過 かつ articleCount>=3 かつ predictionResult=='pending' を対象に
    # judge_prediction() で matched / partial / missed / pending を再評価する。
    # T2026-0428-E2-4 (2026-04-28): 閾値を 7d/5art → 1d/3art に緩和。
    # 根本原因 (実測): pending tracking が当日追加で、システム内 outlook の最大経過 2.12 日。
    # 7d では永遠に verdict 0 件。1d/3art なら backfill 後 6 件が即時 eligible になる。
    # データが熟したら段階的に 3d/5art へ戻すこと。
    # 対象数を JUDGE_MAX で抑制し、wallclock guard も尊重する。
    #
    # 2026-04-29 案D: コスト削減のため、judge_prediction は 1 日 1 回 (UTC 13:00 = JST 22:00 前後) のみ実行。
    # fetcher_trigger 経由 (即時処理) でも skip。新スケジュール cron(0 23,8) には UTC 13 起動はないが、
    # fetcher は 30 分毎に走るため UTC 13 台に fetcher_trigger が来た場合のみ判定が走る。
    pred_judged = 0
    pred_skipped = 0
    JUDGE_MAX = 10
    _utc_hour = datetime.now(timezone.utc).hour
    _should_judge = (source != 'fetcher_trigger') and (_utc_hour == 13)
    if not _should_judge:
        print(f'[Processor] judge_prediction skip (source={source}, UTC_hour={_utc_hour}) — JST 22:00 前後の scheduled invoke のみ実行')
    try:
        if not _should_judge:
            candidates = []
        else:
            candidates = get_topics_for_prediction_judging(min_age_days=1, min_articles=3,
                                                           max_topics=JUDGE_MAX)
        if candidates:
            print(f'[Processor] 予想判定対象: {len(candidates)} 件')
        for cand in candidates:
            if not _wallclock_ok():
                print('[Processor] 予想判定: wallclock guard 到達。残りは次回。')
                break
            tid = cand['topicId']
            outlook = cand['outlook']
            since = cand['predictionMadeAt']
            if not outlook or not since:
                pred_skipped += 1
                continue
            new_articles = get_articles_added_after(tid, since, max_articles=20)
            new_titles = [a.get('title', '') for a in new_articles if a.get('title')]
            if len(new_titles) < 3:
                # 3 件未満は judge_prediction 内部で pending を返すが、書き戻しは行わない
                # (predictionMadeAt は更新せず継続観測)
                pred_skipped += 1
                continue
            verdict = judge_prediction(outlook, new_titles, min_titles=3)
            if not verdict:
                pred_skipped += 1
                continue
            ok = update_prediction_result(tid, verdict['result'], verdict.get('evidence', ''))
            if ok:
                pred_judged += 1
                print(f'  [予想判定] {tid[:8]}... → {verdict["result"]} (新記事 {len(new_titles)} 件)')
            time.sleep(1.0)
        if pred_judged or pred_skipped:
            print(f'[Processor] 予想判定: 判定 {pred_judged} 件 / スキップ {pred_skipped} 件')
    except Exception as e:
        print(f'[Processor] judge_prediction error: {e}')

    return {
        'statusCode': 200,
        'body': json.dumps({
            'pending':   len(pending),
            'processed': processed,
            'api_calls': api_calls,
            'skipped':   skipped,
            # T2026-0428-O: Tier-0 (articles>=10 × aiGenerated=False) 消化状況
            'tier0_total':     tier0_total,
            'tier0_processed': tier0_processed,
            'tier0_deferred':  deferred_tier0,
            # T2026-0428-PRED: 予想自動判定の実績
            'pred_judged':     pred_judged,
            'pred_skipped':    pred_skipped,
        }),
    }
