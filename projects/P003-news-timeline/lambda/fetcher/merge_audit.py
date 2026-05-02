"""merge_audit.py — トピックマージの監査ログと誤マージ自動検知。

T2026-0501-H 設計方針 (2026-05-01 PO 指示):
  「混入 > 分裂」原則でマージは保守的にしているが、誤マージは必ずゼロにできない。
  そのため:
    1. マージするたびに監査ログを残す (S3 JSONL / 日次ファイル)
    2. マージ結果トピックを観測して誤マージシグナルを自動検知 → suspectedMismerge:true フラグ
    3. SLI で `mismerge_suspected_rate` (suspectedMismerge:true の割合) を集計可能化

検出シグナル (シンプル・誤検知より見落とし低減を優先):
  - **time_gap**: 記事の publishedAt 昇順で隣接記事間ギャップが 7 日超 → 別事件混入の可能性
  - **entity_split**: 記事タイトル群を見渡したとき、固有エンティティが 2 系統以上に分かれ
                      各系統が 2+ 記事を保持 → 別事件混入の可能性
  - **count_spike**: マージ後に articleCount が直前 SNAP の 2 倍超 (本ファイル外で計算)

監査ログのフォーマット:
  {
    'mergedAt': ISO 8601,
    'targetTopicId': str,        # 残ったトピック (新規 article をここに集約)
    'sourceTopicId': str,        # 解消されたトピック (新 fingerprint 等)
    'jaccardScore': float,       # 0.0〜1.0
    'entityOverlap': list[str],  # 共有エンティティ
    'haikuUsed': bool,           # Haiku に問うた場合 True
    'haikuVerdict': str,         # 'yes' / 'no' / 'skipped' / 'unknown'
    'confidence': str,           # 'high' (jac>=0.35) / 'medium' (haiku=yes) / 'low' (exact title)
    'titleA': str, 'titleB': str
  }
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone


def _today_iso() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%d')


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


class MergeAuditor:
    """1 run 内のマージイベントを蓄積し、最後にまとめて S3 へ flush する。

    高頻度 PUT を避けるためバッチ書き込み方式 (1 run = 1 PUT)。
    日次ファイル `api/admin/merge-audit/<YYYY-MM-DD>.jsonl` に append する
    (S3 は append できないため: 既存を読み → 末尾に追記 → 上書き)。
    """

    def __init__(self, s3_client=None, bucket: str = ''):
        self.s3 = s3_client
        self.bucket = bucket or ''
        self.events: list[dict] = []

    def log(self, *, target_tid: str, source_tid: str, jaccard: float,
            entity_overlap: list, haiku_used: bool, haiku_verdict: str,
            confidence: str, title_a: str = '', title_b: str = '') -> None:
        if not target_tid or not source_tid or target_tid == source_tid:
            return
        self.events.append({
            'mergedAt': _now_iso(),
            'targetTopicId': str(target_tid),
            'sourceTopicId': str(source_tid),
            'jaccardScore': round(float(jaccard or 0.0), 4),
            'entityOverlap': list(entity_overlap or []),
            'haikuUsed': bool(haiku_used),
            'haikuVerdict': str(haiku_verdict or 'unknown'),
            'confidence': str(confidence or 'unknown'),
            'titleA': str(title_a or '')[:200],
            'titleB': str(title_b or '')[:200],
        })

    def flush_to_s3(self) -> bool:
        """1 run 終わりにまとめて S3 へ append する (既存 + 新規)。"""
        if not self.events or not self.s3 or not self.bucket:
            return False
        key = f'api/admin/merge-audit/{_today_iso()}.jsonl'
        existing_lines: list[str] = []
        try:
            resp = self.s3.get_object(Bucket=self.bucket, Key=key)
            body = resp['Body'].read().decode('utf-8')
            existing_lines = [ln for ln in body.split('\n') if ln.strip()]
        except Exception as e:
            # NoSuchKey は初回のみ発生で正常 (ログには出さない)
            if 'NoSuchKey' not in str(type(e).__name__) and 'NoSuchKey' not in str(e):
                print(f'[merge_audit] 既存ログ取得失敗 ({type(e).__name__}: {e}) → 新規作成扱い')
        new_lines = [json.dumps(ev, ensure_ascii=False) for ev in self.events]
        body_out = '\n'.join(existing_lines + new_lines) + '\n'
        try:
            self.s3.put_object(
                Bucket=self.bucket, Key=key,
                Body=body_out.encode('utf-8'),
                ContentType='application/x-ndjson',
                CacheControl='no-store',
            )
            print(f'[merge_audit] {len(self.events)} 件のマージを {key} に記録 (累計 {len(existing_lines) + len(self.events)} 件)')
            return True
        except Exception as e:
            print(f'[merge_audit] S3 書き込み失敗 ({type(e).__name__}: {e}) → 監査ログ消失')
            return False


# ---- 誤マージシグナル検知 ---------------------------------------------------

# 7 日 (秒)。隣接記事の publishedAt がこれ以上離れていたら別事件混入を疑う。
_MISMERGE_TIME_GAP_SECONDS = 7 * 86400
# 30 日超の time_gap は「精査中」フラグ + split 候補キュー登録に昇格。
_MISMERGE_REVIEW_GAP_SECONDS = 30 * 86400
# entity_split 判定: 各エンティティクラスタに必要な最小記事数
_MISMERGE_MIN_CLUSTER_SIZE = 2
# count_spike 単独フラグが誤検知しやすいジャンル (スポーツ/エンタメ は急増が正常)。
_COUNT_SPIKE_SUPPRESS_GENRES = {'スポーツ', 'エンタメ'}


def _parse_pubms(a: dict) -> int:
    """記事 dict から publishedAt / pubDate / published_ts を ms に変換。失敗時 0。"""
    for key in ('publishedAt', 'pubDate', 'published_ts'):
        v = a.get(key)
        if v is None:
            continue
        try:
            f = float(v)
            if f > 0:
                return int(f * 1000) if f < 1e12 else int(f)
        except (TypeError, ValueError):
            pass
        if isinstance(v, str) and v:
            # try ISO 8601
            try:
                from datetime import datetime as _dt
                s = v.replace('Z', '+00:00')
                d = _dt.fromisoformat(s)
                return int(d.timestamp() * 1000)
            except Exception:
                pass
    return 0


def detect_mismerge_signals(
    articles: list,
    extract_entities_fn=None,
    *,
    prev_article_count: int = 0,
    genre: str = '',
) -> dict:
    """記事リストから誤マージシグナルを検出して reasons を返す。

    Args:
      articles: トピック内の記事 list (dict with title/publishedAt/pubDate)
      extract_entities_fn: 各記事タイトルから固有エンティティ集合を返す関数。
        None なら entity_split 判定はスキップ。
      prev_article_count: 直前 run / SNAP の articleCount。0 ならスパイク判定スキップ。
      genre: トピックのジャンル文字列。count_spike 誤検知抑制に使用。

    Returns:
      {'suspectedMismerge': bool, 'reasons': [str], 'detail': {...},
       'split_candidate': bool}
      split_candidate=True は time_gap>=30日 の場合に立つ。
      呼び出し側で AI 生成スキップ + statusLabel='精査中' + S3 split 候補キュー登録を行うこと。
    """
    reasons: list = []
    detail: dict = {}
    split_candidate = False
    if not articles:
        return {'suspectedMismerge': False, 'reasons': [], 'detail': {}, 'split_candidate': False}

    # ---- 1) time_gap ----
    pubs = sorted(filter(lambda x: x > 0, (_parse_pubms(a) for a in articles)))
    if len(pubs) >= 2:
        max_gap = max(pubs[i + 1] - pubs[i] for i in range(len(pubs) - 1))
        if max_gap > _MISMERGE_TIME_GAP_SECONDS * 1000:
            reasons.append('time_gap')
            gap_days = int(max_gap // (86400 * 1000))
            detail['maxGapDays'] = gap_days
            # T2026-0502-N: 30日超は「精査中」に昇格して AI 生成をスキップし split 候補に。
            if max_gap > _MISMERGE_REVIEW_GAP_SECONDS * 1000:
                split_candidate = True
                detail['requiresReview'] = True

    # ---- 2) entity_split ----
    if extract_entities_fn is not None and len(articles) >= 4:
        ents_per_article = [extract_entities_fn(a.get('title', '')) for a in articles]
        # union-find on entity overlap
        n = len(articles)
        parent = list(range(n))
        def _find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        for i in range(n):
            for j in range(i + 1, n):
                if _find(i) == _find(j):
                    continue
                if ents_per_article[i] & ents_per_article[j]:
                    parent[_find(i)] = _find(j)
        clusters: dict = {}
        for i in range(n):
            clusters.setdefault(_find(i), []).append(i)
        # 「各 cluster が 2+ 記事を持ち、cluster が 2 つ以上ある」場合のみ split 判定
        sized_clusters = [c for c in clusters.values() if len(c) >= _MISMERGE_MIN_CLUSTER_SIZE]
        if len(sized_clusters) >= 2:
            reasons.append('entity_split')
            detail['entityClusters'] = len(sized_clusters)
            detail['clusterSizes'] = sorted((len(c) for c in sized_clusters), reverse=True)

    # ---- 3) count_spike ----
    if prev_article_count > 0 and len(articles) > prev_article_count * 2:
        reasons.append('count_spike')
        detail['articleCountBefore'] = prev_article_count
        detail['articleCountAfter'] = len(articles)

    # T2026-0502-N: count_spike 単独かつスポーツ/エンタメは誤検知率が高いため除外。
    # スポーツ/エンタメは試合・公演など突発的な大量記事が正常で count_spike が誤判定しやすい。
    if reasons == ['count_spike'] and genre in _COUNT_SPIKE_SUPPRESS_GENRES:
        reasons = []
        detail.pop('articleCountBefore', None)
        detail.pop('articleCountAfter', None)

    return {
        'suspectedMismerge': bool(reasons),
        'reasons': reasons,
        'detail': detail,
        'split_candidate': split_candidate,
    }
