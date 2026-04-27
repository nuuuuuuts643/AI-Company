#!/usr/bin/env python3
"""T2026-0428-AE: DynamoDB p003-topics の「stub META」を物理削除する。

stub META = SK='META' でありながら articleCount フィールドが欠如しているレコード。
過去に processor/proc_storage.py:force_reset_pending_all() が ConditionExpression なしで
update_item を呼んでいたため、lifecycle/TTL で消えたトピックに対して
{topicId, SK, pendingAI, aiGenerated} だけのスタブを量産していた。
これらは ART# (記事) を持たないため flotopic 上で「空トピック」として表示される。

修正: ConditionExpression='attribute_exists(topicId)' を追加 (commit 同時に push)。
本スクリプトは既存の 15 件を一括清掃する一回限りの運用。
削除後は topics.json から validate_topics_exist が自動的に該当トピックを除去する
(fetcher/storage.py の同一コミットで強化済)。

dry-run:
  python3 scripts/cleanup_stub_meta.py
実削除:
  python3 scripts/cleanup_stub_meta.py --apply

CLAUDE.md ルール: deploy.sh 直接実行禁止に該当しない (スクリプトはローカル AWS CLI 経由)。
"""
import argparse
import json
import sys
import boto3
from boto3.dynamodb.conditions import Attr

REGION = 'ap-northeast-1'
TABLE = 'p003-topics'


def find_stub_metas(table):
    """SK='META' かつ attribute_not_exists(articleCount) を全スキャン。"""
    items = []
    kwargs = {
        'FilterExpression': Attr('SK').eq('META') & Attr('articleCount').not_exists(),
        'ProjectionExpression': 'topicId, SK, pendingAI, aiGenerated',
    }
    while True:
        r = table.scan(**kwargs)
        items.extend(r.get('Items', []))
        if not r.get('LastEvaluatedKey'):
            break
        kwargs['ExclusiveStartKey'] = r['LastEvaluatedKey']
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true',
                    help='実削除 (デフォルトは dry-run)')
    args = ap.parse_args()

    dynamo = boto3.resource('dynamodb', region_name=REGION)
    table = dynamo.Table(TABLE)

    stubs = find_stub_metas(table)
    print(f'[cleanup_stub_meta] stub META 検出: {len(stubs)} 件')
    for it in stubs:
        print(f'  - topicId={it["topicId"]} pendingAI={it.get("pendingAI")} '
              f'aiGenerated={it.get("aiGenerated")}')

    if not stubs:
        print('[cleanup_stub_meta] クリーン。何もしない。')
        return 0

    if not args.apply:
        print('[cleanup_stub_meta] dry-run のみ。--apply で実削除。')
        return 0

    deleted = 0
    with table.batch_writer() as bw:
        for it in stubs:
            bw.delete_item(Key={'topicId': it['topicId'], 'SK': 'META'})
            deleted += 1
    print(f'[cleanup_stub_meta] 削除完了: {deleted} 件')
    return 0


if __name__ == '__main__':
    sys.exit(main())
