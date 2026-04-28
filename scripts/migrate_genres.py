#!/usr/bin/env python3
"""T2026-0428-AU: ジャンル統合マイグレーション。

旧ジャンル「経済・教育・文化・環境」を新ジャンルに書き換える:
  経済 → ビジネス
  教育 → くらし
  文化 → くらし
  環境 → くらし

対象:
  1. DynamoDB p003-topics の META レコード (genre, genres 両方)
  2. S3 api/topics.json
  3. S3 api/topics-card.json
  4. S3 api/topic/{topicId}.json (個別ファイル)

実行:
  dry-run (デフォルト): python3 scripts/migrate_genres.py
  実行:                  python3 scripts/migrate_genres.py --apply
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3
from boto3.dynamodb.conditions import Attr

REGION = 'ap-northeast-1'
TABLE = 'p003-topics'
S3_BUCKET = 'p003-news-946554699567'

# 旧 → 新 genre マッピング
GENRE_MIGRATION = {
    '経済': 'ビジネス',
    '教育': 'くらし',
    '文化': 'くらし',
    '環境': 'くらし',
}

dynamodb = boto3.resource('dynamodb', region_name=REGION)
table = dynamodb.Table(TABLE)
s3 = boto3.client('s3', region_name=REGION)


def _migrate_genre_value(g):
    """単一ジャンル文字列を新 genre に変換 (該当しなければそのまま)。"""
    return GENRE_MIGRATION.get(g, g) if isinstance(g, str) else g


def _migrate_genres_list(gs):
    """genres 配列の重複除去マージ。順序保持。"""
    if not isinstance(gs, list):
        return gs, False
    seen = []
    changed = False
    for raw in gs:
        new = _migrate_genre_value(raw)
        if new != raw:
            changed = True
        if new not in seen:
            seen.append(new)
    return seen, changed


def migrate_dynamodb(apply: bool):
    """META レコードの genre / genres を書き換える。"""
    print('[1/4] DynamoDB scan…')
    paginator_kwargs = {
        'FilterExpression': Attr('SK').eq('META'),
    }
    items = []
    last_key = None
    while True:
        kwargs = dict(paginator_kwargs)
        if last_key:
            kwargs['ExclusiveStartKey'] = last_key
        resp = table.scan(**kwargs)
        items.extend(resp.get('Items', []))
        last_key = resp.get('LastEvaluatedKey')
        if not last_key:
            break
    print(f'   META: {len(items)} 件')

    targets = []
    for it in items:
        g_old = it.get('genre')
        g_new = _migrate_genre_value(g_old)
        gs_old = it.get('genres')
        gs_new, gs_changed = _migrate_genres_list(gs_old) if isinstance(gs_old, list) else (gs_old, False)
        if g_new != g_old or gs_changed:
            targets.append((it['PK'], it['SK'], g_old, g_new, gs_old, gs_new))

    print(f'   migration 対象: {len(targets)} 件')
    if not targets:
        return 0

    sample = targets[:5]
    for pk, _sk, g_old, g_new, gs_old, gs_new in sample:
        print(f'     {pk}: genre {g_old}→{g_new} / genres {gs_old}→{gs_new}')
    if len(targets) > 5:
        print(f'     … 他 {len(targets)-5} 件')

    if not apply:
        print('   [dry-run] DynamoDB 更新スキップ')
        return len(targets)

    def _update_one(args):
        pk, sk, _g_old, g_new, _gs_old, gs_new = args
        try:
            update_expr_parts = []
            expr_attr_values = {}
            expr_attr_names = {}
            if g_new is not None:
                update_expr_parts.append('#g = :g')
                expr_attr_names['#g'] = 'genre'
                expr_attr_values[':g'] = g_new
            if gs_new is not None:
                update_expr_parts.append('#gs = :gs')
                expr_attr_names['#gs'] = 'genres'
                expr_attr_values[':gs'] = gs_new
            if not update_expr_parts:
                return True
            table.update_item(
                Key={'PK': pk, 'SK': sk},
                UpdateExpression='SET ' + ', '.join(update_expr_parts),
                ExpressionAttributeNames=expr_attr_names,
                ExpressionAttributeValues=expr_attr_values,
            )
            return True
        except Exception as e:
            print(f'     ERROR {pk}: {e}')
            return False

    ok = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        for fut in as_completed([ex.submit(_update_one, t) for t in targets]):
            if fut.result():
                ok += 1
    print(f'   DynamoDB 更新成功: {ok}/{len(targets)}')
    return ok


def _migrate_topic_dict(t):
    """topics.json 内の単一トピック dict を migration。書き換え発生で True を返す。"""
    changed = False
    g = t.get('genre')
    new_g = _migrate_genre_value(g)
    if new_g != g:
        t['genre'] = new_g
        changed = True
    gs = t.get('genres')
    if isinstance(gs, list):
        new_gs, gs_changed = _migrate_genres_list(gs)
        if gs_changed:
            t['genres'] = new_gs
            changed = True
    return changed


def migrate_s3_topics_json(apply: bool, key: str):
    print(f'[S3 {key}]…')
    try:
        resp = s3.get_object(Bucket=S3_BUCKET, Key=key)
        payload = json.loads(resp['Body'].read())
    except s3.exceptions.NoSuchKey:
        print(f'   {key} なし — スキップ')
        return 0
    except Exception as e:
        print(f'   {key} 読込失敗: {e}')
        return 0

    topics = payload.get('topics') if isinstance(payload, dict) else payload
    if not isinstance(topics, list):
        print(f'   {key} 形式不正 — スキップ')
        return 0

    changed_count = 0
    for t in topics:
        if isinstance(t, dict) and _migrate_topic_dict(t):
            changed_count += 1
    print(f'   migration 対象: {changed_count}/{len(topics)} 件')
    if not changed_count:
        return 0
    if not apply:
        print(f'   [dry-run] {key} 書き戻しスキップ')
        return changed_count
    body = json.dumps(payload, ensure_ascii=False)
    s3.put_object(
        Bucket=S3_BUCKET, Key=key,
        Body=body.encode('utf-8'),
        ContentType='application/json; charset=utf-8',
        CacheControl='public, max-age=60',
    )
    print(f'   {key} 書き戻し OK ({len(body)} bytes)')
    return changed_count


def migrate_s3_individual_topics(apply: bool):
    """api/topic/{tid}.json も走査する (詳細ページ用)。"""
    print('[S3 api/topic/*.json]…')
    paginator = s3.get_paginator('list_objects_v2')
    keys = []
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix='api/topic/'):
        for obj in page.get('Contents', []):
            k = obj['Key']
            if k.endswith('.json'):
                keys.append(k)
    print(f'   個別 topic ファイル: {len(keys)} 件')

    changed = 0

    def _process(k):
        try:
            resp = s3.get_object(Bucket=S3_BUCKET, Key=k)
            payload = json.loads(resp['Body'].read())
        except Exception as e:
            print(f'     {k} 読込失敗: {e}')
            return False
        if not isinstance(payload, dict):
            return False
        if not _migrate_topic_dict(payload):
            return False
        if not apply:
            return True
        try:
            s3.put_object(
                Bucket=S3_BUCKET, Key=k,
                Body=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                ContentType='application/json; charset=utf-8',
                CacheControl='public, max-age=60',
            )
            return True
        except Exception as e:
            print(f'     {k} 書込失敗: {e}')
            return False

    with ThreadPoolExecutor(max_workers=10) as ex:
        for fut in as_completed([ex.submit(_process, k) for k in keys]):
            if fut.result():
                changed += 1
    print(f'   個別ファイル migration: {changed} 件 ({"apply" if apply else "dry-run"})')
    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='実書き換え (省略時 dry-run)')
    ap.add_argument('--skip-individual', action='store_true', help='api/topic/*.json をスキップ (時短)')
    args = ap.parse_args()

    mode = 'APPLY' if args.apply else 'DRY-RUN'
    print(f'=== migrate_genres ({mode}) ===')
    print(f'マッピング: {GENRE_MIGRATION}')
    print()

    t0 = time.time()
    n_dynamo = migrate_dynamodb(args.apply)
    n_topics = migrate_s3_topics_json(args.apply, 'api/topics.json')
    n_card = migrate_s3_topics_json(args.apply, 'api/topics-card.json')
    n_full = migrate_s3_topics_json(args.apply, 'api/topics-full.json')
    n_indiv = 0
    if not args.skip_individual:
        n_indiv = migrate_s3_individual_topics(args.apply)

    print()
    print(f'=== 合計 ({mode}) ===')
    print(f'  DynamoDB META:        {n_dynamo}')
    print(f'  S3 topics.json:       {n_topics}')
    print(f'  S3 topics-card.json:  {n_card}')
    print(f'  S3 topics-full.json:  {n_full}')
    print(f'  S3 topic/*.json:      {n_indiv}')
    print(f'  所要: {time.time() - t0:.1f}s')


if __name__ == '__main__':
    main()
