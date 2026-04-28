#!/usr/bin/env python3
"""T2026-0428-E2-4: predictionResult=pending を旧 META へ backfill する一回限りスクリプト。

背景:
    `predictionResult` フラグは T2026-0428-J/E (2026-04-28) で追加された。
    既に outlook を持つが flag を持たない過去 META (66 件) は judge_prediction の
    フィルタを永遠に通過しないため、当否判定の対象から漏れている。

このスクリプトは:
    1. p003-topics の SK=META を全 scan
    2. outlook を持ち、かつ predictionResult が未設定 (= AI が pending を立てる前の旧 record) を抽出
    3. 各 item に predictionResult='pending' / predictionMadeAt=<firstArticleAt - 1s> を書き込む

predictionMadeAt の選定理由 (firstArticleAt - 1s):
    - judge_prediction は predictionMadeAt 以降の新記事タイトル群と outlook を比較する
    - lastUpdated を使うと、既存記事は全て predictionMadeAt より古いので新記事 0 件 → 永遠に pending
    - firstArticleAt - 1s なら、その topic の全記事が「予測以降に積まれた証拠」として扱える
    - backfill 対象は「正確な予測時刻が分からない過去 record」なので、このアプローチは
      『予測は topic genesis 時点で成された』という近似である (記事を見て後から立てた予測の
       場合は若干 over-claim だが、ここでは pipeline validation 優先)
    - 新規 record (T2026-0428-J/E 以降) は AI が正しい predictionMadeAt を書き込む

使い方:
    python3 scripts/backfill_prediction_pending.py [--dry-run]

DynamoDB writes only — Lambda invoke / Anthropic API は呼ばない。
"""
from __future__ import annotations
import argparse
import sys
from datetime import datetime, timedelta, timezone
import boto3

TABLE = 'p003-topics'
REGION = 'ap-northeast-1'


def _epoch_to_iso_minus_1s(epoch_val) -> str | None:
    """epoch (int / Decimal / str) を ISO8601 UTC - 1s 文字列にする。"""
    try:
        ts = int(epoch_val)
    except Exception:
        return None
    if ts <= 0:
        return None
    if ts >= 1e11:
        ts = ts // 1000  # ms
    return (datetime.fromtimestamp(ts, tz=timezone.utc) - timedelta(seconds=1)).isoformat()


def find_orphans(client) -> list:
    """backfill 対象を返す:
    - outlook あり
    - predictionResult が未設定 (= AI が pending を立てる前の旧 record)、
      または predictionResult=pending かつ predictionMadeAt が 1 日以上前
      (= 過去の backfill 実行で predictionMadeAt=lastUpdated を入れたままの record)。
    後者を含めるのは、初回 backfill で lastUpdated を使った結果 new_titles=0 → 判定不能
    だった record を firstArticleAt 起点に上書きするため。
    """
    items = []
    kwargs = {
        'TableName': TABLE,
        'FilterExpression': '#sk = :meta',
        'ExpressionAttributeNames': {'#sk': 'SK'},
        'ExpressionAttributeValues': {':meta': {'S': 'META'}},
    }
    while True:
        resp = client.scan(**kwargs)
        items.extend(resp.get('Items', []))
        if 'LastEvaluatedKey' not in resp:
            break
        kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']

    now = datetime.now(timezone.utc)
    one_day_ago = now - timedelta(days=1)
    orphans = []
    for m in items:
        has_outlook = bool(m.get('outlook', {}).get('S', '').strip()) if 'outlook' in m else False
        pred_res = m.get('predictionResult', {}).get('S', '')
        topic_id = m.get('topicId', {}).get('S', '')
        first_article = m.get('firstArticleAt', {}).get('N') or m.get('firstArticleAt', {}).get('S', '')
        if not (has_outlook and topic_id and first_article):
            continue
        # 旧 record (flag 未設定) または 旧 backfill (pending かつ predictionMadeAt が古い)
        if pred_res == '':
            include = True
        elif pred_res == 'pending':
            pma = m.get('predictionMadeAt', {}).get('S', '')
            try:
                pma_dt = datetime.fromisoformat(pma.replace('Z', '+00:00')) if pma else None
            except Exception:
                pma_dt = None
            include = bool(pma_dt and pma_dt < one_day_ago)
        else:
            include = False
        if not include:
            continue
        prediction_made_at = _epoch_to_iso_minus_1s(first_article)
        if not prediction_made_at:
            continue
        orphans.append({'topicId': topic_id, 'predictionMadeAt': prediction_made_at})
    return orphans


def backfill(client, orphans: list, dry_run: bool) -> int:
    updated = 0
    for o in orphans:
        if dry_run:
            print(f"  [DRY] {o['topicId'][:12]} -> predictionMadeAt={o['predictionMadeAt'][:19]}")
            updated += 1
            continue
        try:
            client.update_item(
                TableName=TABLE,
                Key={'topicId': {'S': o['topicId']}, 'SK': {'S': 'META'}},
                UpdateExpression='SET predictionResult = :r, predictionMadeAt = :m',
                ExpressionAttributeValues={
                    ':r': {'S': 'pending'},
                    ':m': {'S': o['predictionMadeAt']},
                },
            )
            updated += 1
        except Exception as e:
            print(f"  ERR {o['topicId'][:12]}: {e}", file=sys.stderr)
    return updated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    client = boto3.client('dynamodb', region_name=REGION)
    orphans = find_orphans(client)
    print(f"Backfill candidates: {len(orphans)}")
    if not orphans:
        print("Nothing to backfill.")
        return 0
    updated = backfill(client, orphans, args.dry_run)
    print(f"{'[DRY] ' if args.dry_run else ''}Updated: {updated}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
