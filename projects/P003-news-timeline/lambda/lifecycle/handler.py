"""
lambda/lifecycle/handler.py

週次 EventBridge で起動し、トピックのライフサイクルを管理する。

判定方針（設計原則）:
- 時間だけで archived/legacy にしない。
- 戦争・政治危機のような継続型トピックは記事が毎日来るため永遠に active/cooling を維持する。
- 「記事速度がゼロになった（velocity_score <= 0）かつ長期間記事がない」場合のみ archived/legacy へ移行。

ステータス遷移:
  fetcher が毎回書く: active / cooling / archived
  lifecycle が週次で書く: legacy (高スコア) / DELETE (低スコア)

legacy 昇格条件:
  - lastArticleAt が ARCHIVE_DAYS 日以上前
  - かつ velocity_score <= 0（直近7日で新記事ゼロ）
  - かつ 生涯スコア >= LEGACY_SCORE_THRESHOLD（注目されたトピックだった）

削除条件:
  - lastArticleAt が ARCHIVE_DAYS 日以上前
  - かつ velocity_score <= 0
  - かつ スコア < DEAD_SCORE_THRESHOLD（注目されなかった低品質トピック）
"""

import datetime
import json
import os
import time
import urllib.request

import boto3
from boto3.dynamodb.conditions import Attr, Key as DKey

REGION     = os.environ.get('REGION', 'ap-northeast-1')
TABLE      = os.environ.get('TABLE_NAME', 'p003-topics')
S3_BUCKET  = os.environ.get('S3_BUCKET', 'p003-news-946554699567')
SLACK_URL  = os.environ.get('SLACK_WEBHOOK', '')

# スコア閾値
LEGACY_SCORE_THRESHOLD = 50   # このスコア以上なら legacy 保存
DEAD_SCORE_THRESHOLD   = 20   # このスコア未満なら削除

# 日数閾値（velocity <= 0 との AND 条件）
# サービス稼働2週間時点では30日条件はゼロ件しか処理しない。7日で十分。
ARCHIVE_DAYS = 7    # 7日以上記事がなく、velocity <= 0 → 判定対象に入れる

# filter-feedback ファイルの保持日数
FEEDBACK_RETENTION_DAYS = 7   # 7日以上前のファイルは削除

dynamodb = boto3.resource('dynamodb', region_name=REGION)
table    = dynamodb.Table(TABLE)
s3       = boto3.client('s3', region_name=REGION)


FORCE_ARCHIVE_DAYS = 30  # 30日超は velocityScore の値に関係なく inactive 扱い

def is_truly_inactive(item: dict, now: int) -> bool:
    """
    「本当に活動停止しているか」を判定する。

    判定ルール:
    - lastArticleAt=0: 低スコア(<DEAD_SCORE_THRESHOLD)なら True（ゾンビ）
    - lastArticleAt設定済み:
      - days_since >= FORCE_ARCHIVE_DAYS(30日): 無条件 True
        （DynamoDBのvocityScoreが古い正値のまま残っている場合への対策）
      - days_since >= ARCHIVE_DAYS(7日) AND velocity <= 0: True
    """
    last_article = int(item.get('lastArticleAt', 0))
    if last_article == 0:
        score = int(item.get('score', 0))
        return score < DEAD_SCORE_THRESHOLD
    days_since = (now - last_article) / 86400
    if days_since >= FORCE_ARCHIVE_DAYS:
        return True  # 30日以上記事がない → 速度スコアに関係なく停止扱い
    velocity = int(item.get('velocityScore', 0))
    return days_since >= ARCHIVE_DAYS and velocity <= 0


def delete_snaps(topic_id: str) -> int:
    """指定トピックのSNAPアイテムをすべて削除する（batch_writer使用）"""
    keys_to_delete = []
    kwargs = {'KeyConditionExpression': DKey('topicId').eq(topic_id) & DKey('SK').begins_with('SNAP#'),
              'ProjectionExpression': 'topicId, SK'}
    while True:
        resp = table.query(**kwargs)
        keys_to_delete.extend({'topicId': i['topicId'], 'SK': i['SK']} for i in resp.get('Items', []))
        if not resp.get('LastEvaluatedKey'):
            break
        kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']
    with table.batch_writer() as bw:
        for key in keys_to_delete:
            bw.delete_item(Key=key)
    return len(keys_to_delete)


def delete_old_snaps(topic_id: str, cutoff_sk: str) -> int:
    """7日超のSNAP（TTLなし含む）を削除する。active/coolingトピックの肥大化防止。"""
    keys_to_delete = []
    kwargs = {
        'KeyConditionExpression': DKey('topicId').eq(topic_id) & DKey('SK').between('SNAP#', cutoff_sk),
        'ProjectionExpression': 'topicId, SK',
    }
    while True:
        resp = table.query(**kwargs)
        for item in resp.get('Items', []):
            sk = item.get('SK', '')
            if sk.startswith('SNAP#') and sk < cutoff_sk:
                keys_to_delete.append({'topicId': item['topicId'], 'SK': sk})
        if not resp.get('LastEvaluatedKey'):
            break
        kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']
    if keys_to_delete:
        with table.batch_writer() as bw:
            for key in keys_to_delete:
                bw.delete_item(Key=key)
    return len(keys_to_delete)


def cleanup_filter_feedback(now: int) -> int:
    """7日以上前の filter-feedback JSON ファイルを S3 から削除する"""
    prefix = 'api/filter-feedback/'
    cutoff = now - FEEDBACK_RETENTION_DAYS * 86400
    deleted = 0
    paginator = s3.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
        for obj in page.get('Contents', []):
            ts = obj['LastModified'].timestamp()
            if ts < cutoff:
                s3.delete_object(Bucket=S3_BUCKET, Key=obj['Key'])
                deleted += 1
    return deleted


# TODO(phase2): api/filter-feedback/*.json を週次集計して api/filter-weights.json を自動更新する
# 参照: fetcher/filters.py (_OPINION_PATS, _SECONDARY_PATS, _DEFAULT_WEIGHTS, _effective_mult)


DELETION_CAP = 300  # 1回のLambda実行で削除するトピック数の上限（タイムアウト防止）


def lambda_handler(event, context):
    now = int(time.time())

    cutoff_dt  = datetime.datetime.utcfromtimestamp(now - 7 * 86400)
    cutoff_sk  = f"SNAP#{cutoff_dt.strftime('%Y%m%dT%H%M%SZ')}"

    # ---- DynamoDB 全 META アイテムをスキャン ----
    # FilterExpression に SK(sort key) を指定すると DynamoDB が ValidationException を出す。
    # 全件 Scan して Python 側で SK=='META' を絞る（案A）。
    # TODO(T2026-0502-B-followup): 項目数が膨れたら SK の GSI 化を検討すること
    scan_kwargs = {}
    items = []
    while True:
        resp = table.scan(**scan_kwargs)
        items.extend(item for item in resp.get('Items', []) if item.get('SK') == 'META')
        last = resp.get('LastEvaluatedKey')
        if not last:
            break
        scan_kwargs['ExclusiveStartKey'] = last

    legacy_count   = 0
    archived_count = 0
    deleted_count  = 0
    skipped_count  = 0
    old_snap_deleted = 0
    # T2026-0428-AB: DynamoDB から削除した tid を追跡し、topics.json と同期する。
    # これを欠くと sitemap が orphan tid を含み続け、本番 URL が 404 を返す
    # (Google News に SEO 信頼度を毀損する状態が継続)。
    deleted_tids = set()

    # T2026-0428-AK: 空トピック (articleCount<2) を物理削除する集計用カウンタ。
    empty_deleted_count = 0

    for item in items:
        topic_id  = item.get('topicId', '')
        score     = int(item.get('score', 0))
        lifecycle = item.get('lifecycleStatus', 'active')

        # すでに legacy → lifecycle Lambda では触らない（fetcher も上書きしない設計）
        if lifecycle == 'legacy':
            legacy_count += 1
            continue

        # T2026-0428-AK: articleCount<2 のトピックを即削除する。
        # 背景:
        #   - cluster_utils.cluster() が singleton(=1記事) クラスタを返していたため、
        #     fetcher は articleCount=1 の META を DynamoDB に書いていた。
        #   - 既存 UI フィルタ (fetcher handler.py L693-694) では articleCount>=2 のみ
        #     topics.json に出すが、DynamoDB には残り続けるため累積ゾンビが発生
        #     (本番計測で 9680件 / 11882件 = 81% がゾンビ)。
        #   - lifecycle の従来ロジック (is_truly_inactive) は lastArticleAt>0 のうちは
        #     ARCHIVE_DAYS 経過まで掃除しないため、articleCount<2 ゾンビが永続化していた。
        # 物理ゲート: メタ・SNAP・S3 detail JSON を一括削除し、topics.json からも除去する。
        # 並行して fetcher 側で articleCount<2 を新規生成しないガードを入れている。
        article_count = int(item.get('articleCount', 0) or 0)
        if article_count < 2:
            if deleted_count + empty_deleted_count >= DELETION_CAP:
                skipped_count += 1
                continue
            del_keys = []
            del_kwargs = {'KeyConditionExpression': DKey('topicId').eq(topic_id),
                          'ProjectionExpression': 'topicId, SK'}
            while True:
                r = table.query(**del_kwargs)
                del_keys.extend({'topicId': ti['topicId'], 'SK': ti['SK']} for ti in r.get('Items', []))
                if not r.get('LastEvaluatedKey'):
                    break
                del_kwargs['ExclusiveStartKey'] = r['LastEvaluatedKey']
            with table.batch_writer() as bw:
                for k in del_keys:
                    bw.delete_item(Key=k)
            try:
                s3.delete_object(Bucket=S3_BUCKET, Key=f'api/topic/{topic_id}.json')
            except Exception:
                pass
            try:
                s3.delete_object(Bucket=S3_BUCKET, Key=f'topics/{topic_id}.html')
            except Exception:
                pass
            empty_deleted_count += 1
            deleted_tids.add(topic_id)
            print(f"[empty-deleted] topicId={topic_id} articleCount={article_count} items={len(del_keys)}")
            continue

        # 活動停止していないトピックは7日超SNAPだけ削除してスキップ
        if not is_truly_inactive(item, now):
            old_snap_deleted += delete_old_snaps(topic_id, cutoff_sk)
            skipped_count += 1
            continue

        # ── 活動停止 + velocity <= 0 の場合のみ以下を判定 ──

        if score >= LEGACY_SCORE_THRESHOLD:
            # 注目度が高かったトピック → legacy に昇格して保存
            table.update_item(
                Key={'topicId': topic_id, 'SK': 'META'},
                UpdateExpression='SET lifecycleStatus = :s',
                ExpressionAttributeValues={':s': 'legacy'}
            )
            legacy_count += 1
            print(f"[legacy]   topicId={topic_id} score={score}")

        elif score < DEAD_SCORE_THRESHOLD:
            if deleted_count >= DELETION_CAP:
                skipped_count += 1
                continue
            # 低スコアで完全停止 → 全アイテムをbatch削除 + S3個別ファイル削除
            del_keys = []
            del_kwargs = {'KeyConditionExpression': DKey('topicId').eq(topic_id), 'ProjectionExpression': 'topicId, SK'}
            while True:
                r = table.query(**del_kwargs)
                del_keys.extend({'topicId': ti['topicId'], 'SK': ti['SK']} for ti in r.get('Items', []))
                if not r.get('LastEvaluatedKey'):
                    break
                del_kwargs['ExclusiveStartKey'] = r['LastEvaluatedKey']
            with table.batch_writer() as bw:
                for k in del_keys:
                    bw.delete_item(Key=k)
            try:
                s3.delete_object(Bucket=S3_BUCKET, Key=f'api/topic/{topic_id}.json')
            except Exception:
                pass
            deleted_count += 1
            deleted_tids.add(topic_id)
            print(f"[deleted]  topicId={topic_id} score={score} items={len(del_keys)}")

        else:
            # 中間スコア → archived に設定 + SNAPを即削除（容量節約）
            table.update_item(
                Key={'topicId': topic_id, 'SK': 'META'},
                UpdateExpression='SET lifecycleStatus = :s',
                ExpressionAttributeValues={':s': 'archived'}
            )
            snaps_deleted = delete_snaps(topic_id)
            archived_count += 1
            print(f"[archived] topicId={topic_id} score={score} snaps_deleted={snaps_deleted}")

    # ---- 孤立S3トピックファイルのクリーンアップ ----
    # DynamoDB に対応するMETAがないapi/topic/*.jsonを削除する
    s3_topic_deleted = 0
    try:
        all_s3_tids = []
        paginator = s3.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=S3_BUCKET, Prefix='api/topic/'):
            for obj in page.get('Contents', []):
                key = obj['Key']
                # api/topic/{topicId}.json
                if not key.endswith('.json'):
                    continue
                tid = key[len('api/topic/'):-len('.json')]
                if tid:
                    all_s3_tids.append((tid, key))
        # DynamoDB batch_get_item で存在確認
        existing_tids = set()
        for i in range(0, len(all_s3_tids), 100):
            chunk = all_s3_tids[i:i+100]
            keys = [{'topicId': tid, 'SK': 'META'} for tid, _ in chunk]
            try:
                resp = dynamodb.batch_get_item(
                    RequestItems={TABLE: {'Keys': keys, 'ProjectionExpression': 'topicId'}}
                )
                for it in resp.get('Responses', {}).get(TABLE, []):
                    existing_tids.add(it['topicId'])
            except Exception:
                for tid, _ in chunk:
                    existing_tids.add(tid)  # エラー時は削除しない
        for tid, key in all_s3_tids:
            if tid not in existing_tids:
                try:
                    s3.delete_object(Bucket=S3_BUCKET, Key=key)
                    s3_topic_deleted += 1
                except Exception:
                    pass
        print(f"[s3-topic-cleanup] orphan files deleted: {s3_topic_deleted} / {len(all_s3_tids)}")
    except Exception as e:
        print(f"[s3-topic-cleanup] error: {e}")

    # ---- 孤立 topics/*.html のクリーンアップ ----
    s3_html_deleted = 0
    try:
        html_paginator = s3.get_paginator('list_objects_v2')
        all_html_tids = []
        for page in html_paginator.paginate(Bucket=S3_BUCKET, Prefix='topics/'):
            for obj in page.get('Contents', []):
                key = obj['Key']
                if key.endswith('.html'):
                    tid = key[len('topics/'):-len('.html')]
                    if tid:
                        all_html_tids.append((tid, key))
        existing_html_tids = set()
        for i in range(0, len(all_html_tids), 100):
            chunk = all_html_tids[i:i+100]
            keys = [{'topicId': tid, 'SK': 'META'} for tid, _ in chunk]
            try:
                resp = dynamodb.batch_get_item(
                    RequestItems={TABLE: {'Keys': keys, 'ProjectionExpression': 'topicId'}}
                )
                for it in resp.get('Responses', {}).get(TABLE, []):
                    existing_html_tids.add(it['topicId'])
            except Exception:
                for tid, _ in chunk:
                    existing_html_tids.add(tid)
        for tid, key in all_html_tids:
            if tid not in existing_html_tids:
                try:
                    s3.delete_object(Bucket=S3_BUCKET, Key=key)
                    s3_html_deleted += 1
                except Exception:
                    pass
        print(f"[s3-html-cleanup] orphan html deleted: {s3_html_deleted} / {len(all_html_tids)}")
    except Exception as e:
        print(f"[s3-html-cleanup] error: {e}")

    # ---- topics.json から削除 tid を除去 (T2026-0428-AB) ----
    # 背景: lifecycle が DDB から topic を削除しても topics.json (S3) に entry が残ると、
    # processor の sitemap 生成は topics.json を読むため orphan tid を sitemap に書き出す。
    # 結果: news-sitemap.xml の URL が本番で 404 → Google News の SEO 信頼度低下。
    # 物理ゲート: 削除 tid を topics.json/topics-full.json/topics-card.json から同時に削除する。
    #
    # T2026-0428-AK 拡張: detail JSON が S3 に存在しないトピックも除外する。
    # 背景: fetcher が topics.json を生成 → processor が AI 結果を上書き保存する流れだが、
    # processor が backfill_missing_detail_json で補完しても META が消えているトピックは
    # 補完できず topics.json に残り続ける。本番で 12/109 件 (11%) が detail 欠損で 404。
    # 物理ゲート: 毎サイクル detail JSON 存在チェック + DynamoDB META 存在チェックで両側除去。
    topics_json_cleaned = 0

    # detail JSON の存在を判定するヘルパ
    def _detail_json_exists(tid: str) -> bool:
        try:
            s3.head_object(Bucket=S3_BUCKET, Key=f'api/topic/{tid}.json')
            return True
        except Exception:
            return False

    # DynamoDB META の存在を一括判定（batch_get_item）
    def _meta_exists_set(tids: list) -> set:
        existing = set()
        for i in range(0, len(tids), 100):
            chunk = tids[i:i+100]
            keys = [{'topicId': t, 'SK': 'META'} for t in chunk]
            try:
                resp = dynamodb.batch_get_item(
                    RequestItems={TABLE: {'Keys': keys, 'ProjectionExpression': 'topicId'}}
                )
                for it in resp.get('Responses', {}).get(TABLE, []):
                    existing.add(it['topicId'])
            except Exception:
                # エラー時は安全側に倒して全件 existing 扱い（誤削除防止）
                for t in chunk:
                    existing.add(t)
        return existing

    for key in ('api/topics.json', 'api/topics-full.json', 'api/topics-card.json'):
        try:
            resp = s3.get_object(Bucket=S3_BUCKET, Key=key)
            data = json.loads(resp['Body'].read())
            topics = data.get('topics', []) if isinstance(data, dict) else data
            before = len(topics)

            # 削除済み tid を除去
            removal_ids = set(deleted_tids)

            # DynamoDB META が無いトピックを検出
            all_tids = [t.get('topicId') for t in topics if t.get('topicId')]
            existing_metas = _meta_exists_set(all_tids)
            for tid in all_tids:
                if tid not in existing_metas:
                    removal_ids.add(tid)

            # detail JSON が無いトピックを検出（topics.json と topics-full.json のみ。
            # topics-card.json は同じ tid 集合で判定するため重複呼び出しを避ける）
            if key == 'api/topics.json':
                for tid in all_tids:
                    if tid in removal_ids:
                        continue
                    if not _detail_json_exists(tid):
                        removal_ids.add(tid)
                        # detail 欠損 tid は他 JSON からも除外させるため deleted_tids に追記
                        deleted_tids.add(tid)

            topics = [t for t in topics if t.get('topicId') not in removal_ids]
            after = len(topics)
            if before != after:
                if isinstance(data, dict):
                    data['topics'] = topics
                    if 'count' in data:
                        data['count'] = after
                    body = json.dumps(data, ensure_ascii=False).encode('utf-8')
                else:
                    body = json.dumps(topics, ensure_ascii=False).encode('utf-8')
                s3.put_object(
                    Bucket=S3_BUCKET, Key=key, Body=body,
                    ContentType='application/json',
                    CacheControl='max-age=60, must-revalidate',
                )
                topics_json_cleaned += (before - after)
                print(f"[topics-json-sync] {key}: {before} -> {after} (-{before-after})")
        except Exception as e:
            print(f"[topics-json-sync] {key} error: {e}")

    # ---- filter-feedback S3 クリーンアップ ----
    try:
        fb_deleted = cleanup_filter_feedback(now)
        print(f"[feedback-cleanup] {fb_deleted} files deleted")
    except Exception as e:
        print(f"[feedback-cleanup] error: {e}")
        fb_deleted = -1

    summary = (
        f"Lifecycle sweep: {legacy_count} legacy, "
        f"{archived_count} archived, {deleted_count} deleted, "
        f"{empty_deleted_count} empty(articleCount<2) deleted, "
        f"{topics_json_cleaned} topics.json entries cleaned, "
        f"{skipped_count} skipped (active/cooling, {old_snap_deleted} old SNAPs cleaned) | "
        f"feedback-cleanup: {fb_deleted} files"
    )
    print(summary)

    # ---- Slack 通知 ----
    if SLACK_URL:
        msg = json.dumps({'text': f'♻️ Flotopic Lifecycle Sweep\n{summary}'})
        req = urllib.request.Request(
            SLACK_URL,
            data=msg.encode(),
            headers={'Content-Type': 'application/json'}
        )
        try:
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            print(f"Slack notify failed: {e}")

    return {'statusCode': 200, 'body': summary}
