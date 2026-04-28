"""
T2026-0428-AK 即時対処: 空トピックを DynamoDB + S3 から一括清掃する。

対象:
  1. DynamoDB p003-topics の META で articleCount < 2 → そのトピックの全 SK を削除
  2. S3 api/topic/{tid}.json で対応 META が無いもの → S3 削除
  3. S3 api/topics.json / topics-full.json / topics-card.json から下記 tid を除外:
     - 上記で削除した tid
     - detail JSON が S3 に存在しない tid

実行:
  python3 scripts/oneoff/cleanup_empty_topics.py [--dry-run]

注意:
  AWS_PROFILE / AWS_REGION 環境変数を呼び出し側で設定しておくこと。
  既定リージョンは ap-northeast-1。
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3
from boto3.dynamodb.conditions import Attr, Key as DKey

REGION    = os.environ.get('AWS_REGION', 'ap-northeast-1')
TABLE     = 'p003-topics'
S3_BUCKET = 'p003-news-946554699567'

dynamodb = boto3.resource('dynamodb', region_name=REGION)
table    = dynamodb.Table(TABLE)
s3       = boto3.client('s3', region_name=REGION)


def scan_low_article_count_metas():
    """articleCount<2 の META を全件スキャン。"""
    items = []
    kwargs = {
        'FilterExpression': Attr('SK').eq('META') & Attr('articleCount').lt(2),
        'ProjectionExpression': 'topicId, articleCount, lifecycleStatus',
    }
    while True:
        r = table.scan(**kwargs)
        items.extend(r.get('Items', []))
        if not r.get('LastEvaluatedKey'):
            break
        kwargs['ExclusiveStartKey'] = r['LastEvaluatedKey']
    return items


def delete_all_sks_for_topic(topic_id: str) -> int:
    """指定 topicId の全 SK (META + SNAP#... + VIEW#...) を削除。"""
    keys = []
    kwargs = {
        'KeyConditionExpression': DKey('topicId').eq(topic_id),
        'ProjectionExpression': 'topicId, SK',
    }
    while True:
        r = table.query(**kwargs)
        keys.extend({'topicId': it['topicId'], 'SK': it['SK']} for it in r.get('Items', []))
        if not r.get('LastEvaluatedKey'):
            break
        kwargs['ExclusiveStartKey'] = r['LastEvaluatedKey']
    if not keys:
        return 0
    with table.batch_writer() as bw:
        for k in keys:
            bw.delete_item(Key=k)
    return len(keys)


def detail_exists(tid: str) -> bool:
    try:
        s3.head_object(Bucket=S3_BUCKET, Key=f'api/topic/{tid}.json')
        return True
    except Exception:
        return False


def meta_exists_set(tids):
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
            for t in chunk:
                existing.add(t)  # 安全側
    return existing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    print(f'[cleanup] region={REGION} table={TABLE} bucket={S3_BUCKET} dry_run={args.dry_run}')

    # ---- Step 1: DynamoDB articleCount<2 の META 一括削除 ----
    t0 = time.time()
    low_items = scan_low_article_count_metas()
    print(f'[cleanup] articleCount<2 META: {len(low_items)} 件 (scan {time.time()-t0:.1f}s)')

    deleted_dynamo_tids = set()
    if not args.dry_run and low_items:
        with ThreadPoolExecutor(max_workers=10) as ex:
            fs = {ex.submit(delete_all_sks_for_topic, it['topicId']): it['topicId'] for it in low_items}
            done = 0
            for f in as_completed(fs):
                tid = fs[f]
                try:
                    n = f.result()
                    deleted_dynamo_tids.add(tid)
                    done += 1
                    if done % 500 == 0:
                        print(f'  ...{done}/{len(low_items)} 削除済み')
                except Exception as e:
                    print(f'  [err] {tid}: {e}')
        print(f'[cleanup] DynamoDB 削除完了: {len(deleted_dynamo_tids)} tid')

    # ---- Step 2: topics.json から空トピック除外 + 削除 tid 除外 ----
    deleted_total_tids = set(deleted_dynamo_tids)
    s3_topics_cleaned = {}

    for key in ('api/topics.json', 'api/topics-full.json', 'api/topics-card.json'):
        try:
            resp = s3.get_object(Bucket=S3_BUCKET, Key=key)
            data = json.loads(resp['Body'].read())
            topics = data.get('topics', []) if isinstance(data, dict) else data
            before = len(topics)

            removal = set(deleted_total_tids)
            all_tids = [t.get('topicId') for t in topics if t.get('topicId')]
            existing_metas = meta_exists_set(all_tids)
            for tid in all_tids:
                if tid not in existing_metas:
                    removal.add(tid)

            if key == 'api/topics.json':
                # detail JSON 欠損も検出 (topics-full / topics-card は同じ tid なので 1 回だけ)
                with ThreadPoolExecutor(max_workers=20) as ex:
                    fs = {ex.submit(detail_exists, tid): tid for tid in all_tids if tid not in removal}
                    for f in as_completed(fs):
                        tid = fs[f]
                        try:
                            if not f.result():
                                removal.add(tid)
                                deleted_total_tids.add(tid)
                        except Exception:
                            pass

            new_topics = [t for t in topics if t.get('topicId') not in removal]
            after = len(new_topics)
            removed = before - after
            s3_topics_cleaned[key] = removed
            if removed and not args.dry_run:
                if isinstance(data, dict):
                    data['topics'] = new_topics
                    if 'count' in data:
                        data['count'] = after
                    body = json.dumps(data, ensure_ascii=False).encode('utf-8')
                else:
                    body = json.dumps(new_topics, ensure_ascii=False).encode('utf-8')
                s3.put_object(
                    Bucket=S3_BUCKET, Key=key, Body=body,
                    ContentType='application/json',
                    CacheControl='max-age=60, must-revalidate',
                )
            print(f'[cleanup] {key}: {before} -> {after} (-{removed})')
        except Exception as e:
            print(f'[cleanup] {key} error: {e}')

    # ---- Step 3: 削除 tid に対応する S3 detail/HTML を削除 ----
    if not args.dry_run and deleted_total_tids:
        s3_deleted = 0
        for tid in deleted_total_tids:
            for k in (f'api/topic/{tid}.json', f'topics/{tid}.html'):
                try:
                    s3.delete_object(Bucket=S3_BUCKET, Key=k)
                    s3_deleted += 1
                except Exception:
                    pass
        print(f'[cleanup] S3 detail/HTML 削除: {s3_deleted} オブジェクト')

    print(f'[cleanup] 合計 {len(deleted_total_tids)} tid を清掃 (DynamoDB={len(deleted_dynamo_tids)} + S3 only={len(deleted_total_tids)-len(deleted_dynamo_tids)})')
    print(f'[cleanup] topics.json cleaned: {s3_topics_cleaned}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
