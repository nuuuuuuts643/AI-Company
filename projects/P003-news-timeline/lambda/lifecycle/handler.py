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
    scan_kwargs = {'FilterExpression': Attr('SK').eq('META')}
    items = []
    while True:
        resp = table.scan(**scan_kwargs)
        items.extend(resp.get('Items', []))
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

        # すでに legacy → lifecycle Lambda では触らない（fetcher も上書きしない設計）
        if lifecycle == 'legacy':
            legacy_count += 1
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
