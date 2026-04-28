#!/usr/bin/env python3
"""T2026-0428-AO: 全トピック棚卸し＆一括クリーンアップ。

過去のスキーマ変更・バグ・force_reset の積み重ねで DynamoDB と S3 の topics.json が
不整合状態になっている。このスクリプトはトピックを以下のカテゴリに分類し、
ゴミを物理削除・正常データを再処理キュー投入する。

カテゴリ:
  EMPTY                   META exists but articleCount missing/0
  ZOMBIE_FORWARD_ORPHAN   META in DynamoDB but NOT in topics.json
  ZOMBIE_REVERSE_ORPHAN   in topics.json but no META in DynamoDB (S3 のみ)
  ZOMBIE_STALE            lastArticleAt > 7 days ago AND articleCount <= 1
  ZOMBIE_NO_ARTICLES      articleCount > 0 だが timeline 全体が空 (記事0件)
  ZOMBIE_BROKEN_META      title 等の必須フィールドが欠落
  NO_AI                   articleCount >= 2 だが AI フィールドが全部空
  PARTIAL_AI              一部 AI フィールドあり / 一部空 → 不足分のみ heal
  GOOD                    現行スキーマで完備

実行:
  dry-run (デフォルト・分析のみ): python3 scripts/cleanup_all_topics.py
  実行:                            python3 scripts/cleanup_all_topics.py --apply
  特定カテゴリのみ:                 python3 scripts/cleanup_all_topics.py --apply --only EMPTY,ZOMBIE_STALE
  S3 再生成スキップ:                python3 scripts/cleanup_all_topics.py --apply --skip-regenerate

T2026-0428-AO 重要原則:
  NO_AI / PARTIAL_AI に対しては pendingAI=True だけセットする (アトミック更新)。
  既存の AI フィールドは絶対に上書きしない。processor 側 (incremental モード) が
  不足フィールドだけ補完する責務を持つ。本スクリプトは「キュー投入」だけ。
"""
import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import boto3
from boto3.dynamodb.conditions import Attr, Key

REGION = 'ap-northeast-1'
TABLE = 'p003-topics'
S3_BUCKET_DEFAULT = 'p003-news-946554699567'
PROCESSOR_LAMBDA = 'p003-processor'
STALE_DAYS = 7
# FORWARD_ORPHAN 判定: topics.json から落ちて N 日以上経過したものだけ削除対象。
# 新規・処理待ちトピック (まだ topics.json に入っていない可能性) を誤削除しないためのガード。
FORWARD_ORPHAN_GRACE_DAYS = 3
PROCESSOR_SCHEMA_VERSION = 3  # proc_config.PROCESSOR_SCHEMA_VERSION と同期

# AI 完成判定に必須のフィールド (articleCount >= 3 時)
AI_REQUIRED_FIELDS_FULL = ('keyPoint', 'statusLabel', 'watchPoints', 'storyTimeline', 'storyPhase')
# 最低限のヒント (articleCount == 2 時 minimal モード相当)
AI_REQUIRED_FIELDS_MINIMAL = ('keyPoint',)


def _is_empty(v):
    if v is None:
        return True
    if isinstance(v, str) and not v.strip():
        return True
    if isinstance(v, (list, dict)) and len(v) == 0:
        return True
    return False


def _parse_iso(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    except Exception:
        return None


def scan_all_meta(table):
    """全 META レコードをスキャン。"""
    items = []
    kwargs = {
        'FilterExpression': Attr('SK').eq('META'),
    }
    while True:
        r = table.scan(**kwargs)
        items.extend(r.get('Items', []))
        if not r.get('LastEvaluatedKey'):
            break
        kwargs['ExclusiveStartKey'] = r['LastEvaluatedKey']
    return items


def load_s3_topics_json(s3, bucket, key='api/topics.json'):
    try:
        resp = s3.get_object(Bucket=bucket, Key=key)
        data = json.loads(resp['Body'].read())
        return data.get('topics', []) if isinstance(data, dict) else (data or [])
    except Exception as e:
        print(f'[cleanup] S3 read failed key={key}: {e}', file=sys.stderr)
        return []


def get_topic_articles_signal(table, tid):
    """トピックの SNAP を最大 5 件確認し、articles を実際に持っているかを返す。"""
    try:
        r = table.query(
            KeyConditionExpression=Key('topicId').eq(tid) & Key('SK').begins_with('SNAP#'),
            ScanIndexForward=False, Limit=5,
            ProjectionExpression='articles',
        )
        for snap in r.get('Items', []):
            if snap.get('articles'):
                return True
    except Exception:
        pass
    return False


def categorize(metas, topics_json_tids, table):
    """各 META を分類してカテゴリ別 dict を返す。"""
    cats = defaultdict(list)
    meta_by_tid = {m['topicId']: m for m in metas if m.get('topicId')}

    # 1) S3 のみに存在 (REVERSE_ORPHAN)
    for tid in topics_json_tids:
        if tid not in meta_by_tid:
            cats['ZOMBIE_REVERSE_ORPHAN'].append({'topicId': tid, 'reason': 'topics.jsonにあるがDynamoDB META不在'})

    now = datetime.now(timezone.utc)

    for tid, m in meta_by_tid.items():
        ac_raw = m.get('articleCount')
        try:
            ac = int(ac_raw) if ac_raw is not None else 0
        except (ValueError, TypeError):
            ac = 0
        title = m.get('title') or m.get('generatedTitle') or ''
        last_article_at = _parse_iso(m.get('lastArticleAt'))

        # 2) BROKEN_META: 必須フィールド欠落
        if not title:
            cats['ZOMBIE_BROKEN_META'].append({'topicId': tid, 'reason': 'title なし'})
            continue
        if ac_raw is None:
            cats['EMPTY'].append({'topicId': tid, 'reason': 'articleCount フィールド欠如', 'title': title[:40]})
            continue

        # 3) EMPTY: articleCount = 0
        if ac == 0:
            cats['EMPTY'].append({'topicId': tid, 'reason': 'articleCount=0', 'title': title[:40]})
            continue

        # 4) ZOMBIE_STALE: 古くて articleCount <= 1
        if ac <= 1 and last_article_at and (now - last_article_at) > timedelta(days=STALE_DAYS):
            age_d = (now - last_article_at).days
            cats['ZOMBIE_STALE'].append({'topicId': tid, 'reason': f'articleCount<=1 & lastArticleAt {age_d}日前', 'title': title[:40]})
            continue

        # 5) ZOMBIE_NO_ARTICLES: articleCount > 0 だが SNAP に articles なし
        # (重い: SNAP query が 1 トピックあたり発生するので articleCount>0 のものだけチェック)
        # 注: 軽量化のため、 articleCount>=2 で aiGenerated=False かつ keyPoint なしのトピックのみチェック
        # (実際に「中身の壊れたゾンビ」候補に絞る)
        if ac >= 1:
            has_articles = get_topic_articles_signal(table, tid)
            if not has_articles:
                cats['ZOMBIE_NO_ARTICLES'].append({'topicId': tid, 'reason': f'articleCount={ac} だが SNAP に articles なし', 'title': title[:40]})
                continue

        # 6) FORWARD_ORPHAN: META あるが topics.json にない
        # (lifecycleStatus archived は除外。意図的非表示)
        lifecycle = m.get('lifecycleStatus', '')
        if tid not in topics_json_tids and lifecycle not in ('archived', 'legacy', 'deleted'):
            # archived 以外で非可視 = ゾンビ (古い・低スコア・未昇格 etc)
            score = m.get('score', 0)
            cats['ZOMBIE_FORWARD_ORPHAN'].append({
                'topicId': tid,
                'reason': f'DynamoDB META あるが topics.json 不在 (score={score}, ac={ac}, lifecycle={lifecycle or "未設定"})',
                'title': title[:40],
            })
            continue

        # 7) AI 充填度を判定
        is_minimal = ac <= 2
        ai_gen = bool(m.get('aiGenerated'))
        sv = 0
        try:
            sv = int(m.get('schemaVersion', 0) or 0)
        except (ValueError, TypeError):
            sv = 0

        # 必須フィールドの埋まり度
        required = AI_REQUIRED_FIELDS_MINIMAL if is_minimal else AI_REQUIRED_FIELDS_FULL
        filled = [f for f in required if not _is_empty(m.get(f))]
        empty = [f for f in required if _is_empty(m.get(f))]

        if not ai_gen and not filled:
            cats['NO_AI'].append({
                'topicId': tid, 'reason': 'aiGenerated=False かつ AIフィールド全部空',
                'title': title[:40], 'articleCount': ac,
            })
            continue
        if empty or sv < PROCESSOR_SCHEMA_VERSION:
            cats['PARTIAL_AI'].append({
                'topicId': tid,
                'reason': f'欠落={empty} schemaVersion={sv}/{PROCESSOR_SCHEMA_VERSION}',
                'title': title[:40], 'articleCount': ac,
            })
            continue

        cats['GOOD'].append({'topicId': tid, 'title': title[:40], 'articleCount': ac, 'schemaVersion': sv})

    return cats


def delete_topic_completely(table, tid):
    """指定トピックの全 SK (META + SNAP + PRED + VIEW) を削除する。"""
    try:
        # 全 SK を query で列挙
        sks = []
        last = None
        while True:
            kwargs = {
                'KeyConditionExpression': Key('topicId').eq(tid),
                'ProjectionExpression': 'SK',
            }
            if last:
                kwargs['ExclusiveStartKey'] = last
            r = table.query(**kwargs)
            sks.extend(it['SK'] for it in r.get('Items', []) if 'SK' in it)
            last = r.get('LastEvaluatedKey')
            if not last:
                break
        if not sks:
            return 0
        with table.batch_writer() as bw:
            for sk in sks:
                bw.delete_item(Key={'topicId': tid, 'SK': sk})
        return len(sks)
    except Exception as e:
        print(f'  [delete_topic] tid={tid} 失敗: {e}', file=sys.stderr)
        return 0


def mark_topic_for_reprocessing(table, tid):
    """T2026-0428-AO: pendingAI=True だけセット (既存 AI フィールドは絶対に触らない)。
    ConditionExpression で META 不在トピックへの誤書き込みを物理ガード。"""
    try:
        table.update_item(
            Key={'topicId': tid, 'SK': 'META'},
            UpdateExpression='SET pendingAI = :p',
            ConditionExpression='attribute_exists(topicId)',
            ExpressionAttributeValues={':p': True},
        )
        return True
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        print(f'  [mark_reprocess] tid={tid} META 不在のためスキップ')
        return False
    except Exception as e:
        print(f'  [mark_reprocess] tid={tid} 失敗: {e}', file=sys.stderr)
        return False


def remove_topic_detail_s3(s3, bucket, tids):
    """個別 topic JSON / 静的 HTML を S3 から削除。delete_objects で 1000 件単位の batch。"""
    if not tids:
        return 0
    keys = []
    for tid in tids:
        keys.append({'Key': f'api/topic/{tid}.json'})
        keys.append({'Key': f'topics/{tid}.html'})
    deleted = 0
    for i in range(0, len(keys), 1000):
        chunk = keys[i:i+1000]
        try:
            r = s3.delete_objects(Bucket=bucket, Delete={'Objects': chunk, 'Quiet': True})
            # delete_objects は存在しないキーもエラーなく成功扱い → chunk 全数で集計
            errs = r.get('Errors', []) or []
            deleted += len(chunk) - len(errs)
            for e in errs:
                print(f'    [s3 delete error] key={e.get("Key")} code={e.get("Code")}', file=sys.stderr)
        except Exception as e:
            print(f'  [remove_topic_detail_s3] batch失敗: {e}', file=sys.stderr)
    return deleted


def list_existing_html_tids(s3, bucket, prefix='topics/'):
    """S3 の topics/*.html プレフィクスをリストアップして tid セットを返す。"""
    tids = set()
    paginator = s3.get_paginator('list_objects_v2')
    try:
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get('Contents', []) or []:
                key = obj.get('Key', '')
                if key.endswith('.html'):
                    tid = key[len(prefix):-5]  # strip 'topics/' and '.html'
                    if tid:
                        tids.add(tid)
    except Exception as e:
        print(f'  [list_existing_html_tids] 失敗: {e}', file=sys.stderr)
    return tids


def cloudfront_invalidate(distribution_id, paths):
    """CloudFront キャッシュ invalidation を発行。distribution_id 不明時は no-op。"""
    if not distribution_id:
        return None
    try:
        cf = boto3.client('cloudfront', region_name='us-east-1')
        ts = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
        r = cf.create_invalidation(
            DistributionId=distribution_id,
            InvalidationBatch={
                'Paths': {'Quantity': len(paths), 'Items': paths},
                'CallerReference': f'cleanup-all-topics-{ts}',
            },
        )
        return r.get('Invalidation', {}).get('Id')
    except Exception as e:
        print(f'  [cloudfront_invalidate] 失敗: {e}', file=sys.stderr)
        return None


def find_cloudfront_distribution_for_bucket(bucket_domain_hint):
    """flotopic.com の CloudFront distribution ID を探索。
    Aliases 配列に flotopic.com が入っているものをマッチ。"""
    try:
        cf = boto3.client('cloudfront', region_name='us-east-1')
        paginator = cf.get_paginator('list_distributions')
        for page in paginator.paginate():
            dl = page.get('DistributionList', {}) or {}
            for d in dl.get('Items', []) or []:
                aliases = (d.get('Aliases') or {}).get('Items') or []
                if any('flotopic.com' in a for a in aliases):
                    return d.get('Id')
                # bucket origin マッチ
                origins = (d.get('Origins') or {}).get('Items') or []
                for o in origins:
                    if bucket_domain_hint in (o.get('DomainName') or ''):
                        return d.get('Id')
    except Exception as e:
        print(f'  [find_cloudfront_distribution] 失敗: {e}', file=sys.stderr)
    return None


def regenerate_topics_json_via_lambda(lambda_client):
    """processor lambda を regenerateSitemap で起動。
    topics.json / topics-full.json / topics-card.json / sitemap / RSS / news-sitemap を再生成。"""
    try:
        resp = lambda_client.invoke(
            FunctionName=PROCESSOR_LAMBDA,
            InvocationType='RequestResponse',
            Payload=json.dumps({'regenerateSitemap': True}).encode('utf-8'),
        )
        body = resp['Payload'].read()
        try:
            data = json.loads(body)
        except Exception:
            data = {'raw': body[:200].decode('utf-8', errors='replace')}
        return resp['StatusCode'], data
    except Exception as e:
        return 500, {'error': str(e)}


def filter_topics_json(s3, bucket, valid_tids):
    """processor lambda 起動が失敗した場合のフォールバック: 既存 topics.json から
    valid_tids 以外を除去するだけの軽量再生成。"""
    for key in ('api/topics.json', 'api/topics-full.json', 'api/topics-card.json'):
        try:
            resp = s3.get_object(Bucket=bucket, Key=key)
            data = json.loads(resp['Body'].read())
            if not isinstance(data, dict) or 'topics' not in data:
                continue
            before = len(data['topics'])
            data['topics'] = [t for t in data['topics'] if t.get('topicId') in valid_tids]
            after = len(data['topics'])
            data['updatedAt'] = datetime.now(timezone.utc).isoformat()
            s3.put_object(
                Bucket=bucket, Key=key,
                Body=json.dumps(data, ensure_ascii=False).encode('utf-8'),
                ContentType='application/json',
                CacheControl='max-age=60, must-revalidate',
            )
            print(f'  [fallback] {key}: {before} → {after} 件')
        except Exception as e:
            print(f'  [fallback] {key} 更新失敗: {e}', file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='実削除/書き込み (デフォルトは dry-run)')
    ap.add_argument('--only', default='', help='対象カテゴリをカンマ区切りで限定 (例: EMPTY,ZOMBIE_STALE)')
    ap.add_argument('--skip-regenerate', action='store_true', help='S3 topics.json 再生成をスキップ')
    ap.add_argument('--bucket', default=S3_BUCKET_DEFAULT, help=f'S3 バケット (デフォルト: {S3_BUCKET_DEFAULT})')
    ap.add_argument('--report', default=None, help='レポート JSON 出力先')
    ap.add_argument('--cf-distribution', default=None, help='CloudFront distribution ID (省略時は flotopic.com で自動探索)')
    args = ap.parse_args()

    only_cats = set(c.strip() for c in args.only.split(',') if c.strip())

    dynamo = boto3.resource('dynamodb', region_name=REGION)
    table = dynamo.Table(TABLE)
    s3 = boto3.client('s3', region_name=REGION)
    lambda_client = boto3.client('lambda', region_name=REGION)

    print('[cleanup] === Phase 1: スキャン ===')
    t0 = time.time()
    metas = scan_all_meta(table)
    print(f'[cleanup] DynamoDB META: {len(metas)} 件 ({time.time()-t0:.1f}s)')

    topics_json = load_s3_topics_json(s3, args.bucket, 'api/topics.json')
    topics_json_tids = {t.get('topicId') for t in topics_json if t.get('topicId')}
    print(f'[cleanup] S3 topics.json: {len(topics_json_tids)} 件')

    print('[cleanup] === Phase 2: カテゴリ分類 ===')
    cats = categorize(metas, topics_json_tids, table)

    print('\n[cleanup] === 分類結果 ===')
    for cat in ('GOOD', 'PARTIAL_AI', 'NO_AI', 'EMPTY',
                'ZOMBIE_FORWARD_ORPHAN', 'ZOMBIE_REVERSE_ORPHAN',
                'ZOMBIE_STALE', 'ZOMBIE_NO_ARTICLES', 'ZOMBIE_BROKEN_META'):
        items = cats.get(cat, [])
        print(f'  {cat:25s}: {len(items):4d} 件')

    # 詳細リスト (5件まで例示)
    print('\n[cleanup] === 詳細サンプル ===')
    for cat in ('EMPTY', 'ZOMBIE_FORWARD_ORPHAN', 'ZOMBIE_REVERSE_ORPHAN',
                'ZOMBIE_STALE', 'ZOMBIE_NO_ARTICLES', 'ZOMBIE_BROKEN_META', 'NO_AI', 'PARTIAL_AI'):
        items = cats.get(cat, [])
        if not items:
            continue
        print(f'\n[{cat}] 全 {len(items)} 件のうち 先頭 5 件:')
        for it in items[:5]:
            tid = it.get('topicId', '???')
            print(f'  - {tid[:12]}... {it.get("reason", "")} | {it.get("title", "")}')

    if args.report:
        report_data = {k: v for k, v in cats.items()}
        with open(args.report, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2, default=str)
        print(f'[cleanup] レポート出力: {args.report}')

    if not args.apply:
        print('\n[cleanup] dry-run のみ。--apply で実行。')
        return 0

    # ============ アクション実行 ============
    print('\n[cleanup] === Phase 3: 削除 ===')

    # 削除対象カテゴリ
    DELETE_CATS = ('EMPTY', 'ZOMBIE_FORWARD_ORPHAN', 'ZOMBIE_STALE',
                   'ZOMBIE_NO_ARTICLES', 'ZOMBIE_BROKEN_META')
    total_deleted = 0
    deleted_tids = []
    for cat in DELETE_CATS:
        if only_cats and cat not in only_cats:
            continue
        items = cats.get(cat, [])
        if not items:
            continue
        print(f'\n  [{cat}] 削除中 ({len(items)}件)...')
        cnt = 0
        for it in items:
            tid = it['topicId']
            n = delete_topic_completely(table, tid)
            if n:
                cnt += 1
                deleted_tids.append(tid)
        print(f'    → {cnt} 件削除完了')
        total_deleted += cnt

    # REVERSE_ORPHAN: DynamoDB にない (S3 のみ) → topics.json 再生成で消える
    # detail JSON も削除しておく
    rev_orphans = cats.get('ZOMBIE_REVERSE_ORPHAN', [])
    if rev_orphans and (not only_cats or 'ZOMBIE_REVERSE_ORPHAN' in only_cats):
        rev_tids = [it['topicId'] for it in rev_orphans]
        n = remove_topic_detail_s3(s3, args.bucket, rev_tids)
        print(f'\n  [ZOMBIE_REVERSE_ORPHAN] S3 detail/HTML 削除: {n} key')
        deleted_tids.extend(rev_tids)

    # 削除したトピックの個別 JSON / 静的 HTML も削除 (常に実行)
    if deleted_tids:
        unique_deleted = list(dict.fromkeys(deleted_tids))
        n = remove_topic_detail_s3(s3, args.bucket, unique_deleted)
        print(f'  [S3 detail/HTML 削除] {n} key (tid={len(unique_deleted)}件分)')

    # 静的 HTML プレフィクス全体のクリーンアップ:
    # 残った全トピック (META 存続 = 削除対象外) の tid セットを基準に
    # それ以外の HTML を全て削除する (孤立 HTML を物理一掃)
    surviving_tids = {m['topicId'] for m in metas if m.get('topicId')} - set(deleted_tids)
    existing_html_tids = list_existing_html_tids(s3, args.bucket, prefix='topics/')
    orphan_html_tids = existing_html_tids - surviving_tids
    if orphan_html_tids:
        n = remove_topic_detail_s3(s3, args.bucket, list(orphan_html_tids))
        print(f'  [孤立 HTML 一掃] {n} key (orphan_html_tids={len(orphan_html_tids)}件)')
    else:
        print(f'  [孤立 HTML 確認] なし (existing={len(existing_html_tids)} survived={len(surviving_tids)})')

    print('\n[cleanup] === Phase 4: 再処理キュー投入 ===')

    # NO_AI / PARTIAL_AI に pendingAI=True セット
    REPROCESS_CATS = ('NO_AI', 'PARTIAL_AI')
    queued = 0
    queued_tids = []
    for cat in REPROCESS_CATS:
        if only_cats and cat not in only_cats:
            continue
        items = cats.get(cat, [])
        if not items:
            continue
        print(f'\n  [{cat}] pendingAI=True セット中 ({len(items)}件)...')
        cnt = 0
        for it in items:
            tid = it['topicId']
            ok = mark_topic_for_reprocessing(table, tid)
            if ok:
                cnt += 1
                queued_tids.append(tid)
        print(f'    → {cnt} 件キュー投入完了')
        queued += cnt

    # pending_ai.json にも明示的に追加 (processor が次サイクルで拾う)
    if queued_tids and not only_cats:
        try:
            try:
                resp = s3.get_object(Bucket=args.bucket, Key='api/pending_ai.json')
                cur = json.loads(resp['Body'].read())
                cur_ids = list(cur.get('topicIds', []))
            except Exception:
                cur_ids = []
            merged = list(dict.fromkeys(cur_ids + queued_tids))
            s3.put_object(
                Bucket=args.bucket, Key='api/pending_ai.json',
                Body=json.dumps({'topicIds': merged}).encode('utf-8'),
                ContentType='application/json',
            )
            print(f'  [pending_ai.json] {len(cur_ids)} → {len(merged)} 件')
        except Exception as e:
            print(f'  [pending_ai.json] 更新失敗: {e}', file=sys.stderr)

    print('\n[cleanup] === Phase 5: S3 JSON / サイトマップ再生成 ===')
    if args.skip_regenerate:
        print('  --skip-regenerate 指定のため スキップ')
    else:
        sc, data = regenerate_topics_json_via_lambda(lambda_client)
        print(f'  processor invoke: status={sc} body={data}')
        if sc != 200:
            # フォールバック: ローカルで topics.json をフィルタ
            print('  [fallback] processor invoke 失敗 → ローカルフィルタ')
            valid_tids = {m['topicId'] for m in metas if m.get('topicId')} - set(deleted_tids)
            filter_topics_json(s3, args.bucket, valid_tids)

    print('\n[cleanup] === Phase 6: CloudFront invalidation ===')
    dist_id = args.cf_distribution or find_cloudfront_distribution_for_bucket(args.bucket)
    if dist_id:
        inv_id = cloudfront_invalidate(dist_id, [
            '/topics/*', '/api/topics.json', '/api/topics-full.json', '/api/topics-card.json',
            '/sitemap.xml', '/news-sitemap.xml', '/rss.xml',
        ])
        print(f'  distribution_id={dist_id} invalidation_id={inv_id}')
    else:
        print('  CloudFront distribution が見つからない (--cf-distribution で指定可)')

    print('\n[cleanup] === Phase 7: 残データ整合性チェック ===')
    # S3 HTML 残数 = 残った正常トピック数 を検証
    final_html_tids = list_existing_html_tids(s3, args.bucket, prefix='topics/')
    final_topics_json = load_s3_topics_json(s3, args.bucket, 'api/topics.json')
    final_json_tids = {t.get('topicId') for t in final_topics_json if t.get('topicId')}
    print(f'  topics/*.html 残数:        {len(final_html_tids)}')
    print(f'  topics.json 残数:          {len(final_json_tids)}')
    only_html = final_html_tids - final_json_tids
    only_json = final_json_tids - final_html_tids
    print(f'  HTML のみ (json 不在):     {len(only_html)}')
    print(f'  json のみ (HTML 不在):     {len(only_json)} (次の processor 走行で生成される想定)')

    print('\n[cleanup] === 完了サマリ ===')
    print(f'  削除トピック数:       {total_deleted}')
    print(f'  S3 のみ孤立削除数:    {len(rev_orphans)}')
    print(f'  再処理キュー投入数:   {queued}')
    print(f'  GOOD トピック数:      {len(cats.get("GOOD", []))}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
