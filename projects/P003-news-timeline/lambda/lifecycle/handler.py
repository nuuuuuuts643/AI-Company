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

import json
import os
import time
import urllib.request

import boto3
from boto3.dynamodb.conditions import Attr, Key as DKey

REGION     = os.environ.get('REGION', 'ap-northeast-1')
TABLE      = os.environ.get('TABLE_NAME', 'p003-topics')
SLACK_URL  = os.environ.get('SLACK_WEBHOOK', '')

# スコア閾値
LEGACY_SCORE_THRESHOLD = 50   # このスコア以上なら legacy 保存
DEAD_SCORE_THRESHOLD   = 20   # このスコア未満なら削除

# 日数閾値（velocity <= 0 との AND 条件）
ARCHIVE_DAYS = 30   # 30日以上記事がなく、velocity <= 0 → 判定対象に入れる

dynamodb = boto3.resource('dynamodb', region_name=REGION)
table    = dynamodb.Table(TABLE)


def is_truly_inactive(item: dict, now: int) -> bool:
    """
    「本当に活動停止しているか」を判定する。
    time.time() ベースの経過日数に加え、velocity_score が 0 以下であることを必須とする。
    → velocity > 0 なら記事が来続けているので継続型トピックと判断して除外する。
    """
    last_article = int(item.get('lastArticleAt', 0))
    velocity     = int(item.get('velocityScore', 0))
    days_since   = (now - last_article) / 86400

    return days_since >= ARCHIVE_DAYS and velocity <= 0


def lambda_handler(event, context):
    now = int(time.time())

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

    for item in items:
        topic_id  = item.get('topicId', '')
        score     = int(item.get('score', 0))
        lifecycle = item.get('lifecycleStatus', 'active')

        # すでに legacy → lifecycle Lambda では触らない（fetcher も上書きしない設計）
        if lifecycle == 'legacy':
            legacy_count += 1
            continue

        # 活動停止していないトピックはスキップ
        if not is_truly_inactive(item, now):
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
            # 低スコアで完全停止 → 全アイテム削除
            topic_items = table.query(
                KeyConditionExpression=DKey('topicId').eq(topic_id)
            ).get('Items', [])
            for ti in topic_items:
                table.delete_item(Key={'topicId': ti['topicId'], 'SK': ti['SK']})
            deleted_count += 1
            print(f"[deleted]  topicId={topic_id} score={score} items={len(topic_items)}")

        else:
            # 中間スコア → archived に設定（レガシーページに表示）
            table.update_item(
                Key={'topicId': topic_id, 'SK': 'META'},
                UpdateExpression='SET lifecycleStatus = :s',
                ExpressionAttributeValues={':s': 'archived'}
            )
            archived_count += 1
            print(f"[archived] topicId={topic_id} score={score}")

    summary = (
        f"Lifecycle sweep: {legacy_count} legacy, "
        f"{archived_count} archived, {deleted_count} deleted, "
        f"{skipped_count} skipped (still active/cooling)"
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
