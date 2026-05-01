#!/usr/bin/env python3
"""scripts/verify_branching_quality.py

T2026-0429-C: should_branch() の効果を本番データで定量評価する。

判定マトリクス（T2026-0429-B 実装）が正しく動いているかを以下の SLI で見る:

  1. 分岐率 (branching_rate)
       parentTopicId が立つトピックの割合。
       実装前後の比較は履歴 snapshot がなければ「現在値のみ」を出す。
  2. 誤分岐疑い率 (suspect_false_branch)
       parent と child の title 類似度 (char-bigram Jaccard) > 0.6 なのに別トピック扱い
       → 同じ事件の延長を分岐させてしまった疑い。
  3. 誤マージ疑い率 (suspect_false_merge)
       parent と child の title 類似度 < 0.2 なのに同一ブランチ扱い
       → 全く別の話題を同じ親に紐付けてしまった疑い。

データソース:
  - 本番: https://flotopic.com/api/topics-full.json (default)
  - --source <path> でローカルファイル指定可
  - --source dynamodb で boto3 経由 (認証要)

使い方:
  python3 scripts/verify_branching_quality.py
  python3 scripts/verify_branching_quality.py --source /tmp/topics-full.json
  python3 scripts/verify_branching_quality.py --sample 30 --seed 42

出力:
  Verified-Effect: branching_quality
    branching_rate=<X>%(<branched>/<total>)
    error_branch=<N>(<rate>%)
    error_merge=<M>(<rate>%)
    sample=<S>
    PASS|FAIL @ <JST timestamp>

exit code:
  0 = PASS  (両疑い率 ≤ 閾値)
  1 = FAIL  (どちらか > 閾値)
  2 = ERROR (実行エラー / データ取得失敗 / サンプル不足)

閾値:
  --error-branch-threshold (default 20.0): suspect_false_branch_rate > 20% で FAIL
  --error-merge-threshold  (default 15.0): suspect_false_merge_rate  > 15% で FAIL
  --min-sample             (default 10):   サンプル数がこれ未満なら SKIP (exit 0)
                                            理由: 小サンプルだと 1 ペアの差で判定が大きく揺れる
                                            (sample=4 で 1 件 false_branch → 25% で FAIL 誤検知)
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta

DEFAULT_SOURCE = "https://flotopic.com/api/topics-full.json"
JST = timezone(timedelta(hours=9))


def fetch_topics(source: str) -> list[dict]:
    if source.startswith("http://") or source.startswith("https://"):
        req = urllib.request.Request(source, headers={"User-Agent": "verify_branching_quality"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    elif source == "dynamodb":
        try:
            import boto3
        except ImportError:
            raise RuntimeError("boto3 が必要 (pip install boto3)")
        client = boto3.resource("dynamodb", region_name="ap-northeast-1")
        table = client.Table("p003-topics")
        items: list[dict] = []
        last_key = None
        while True:
            kwargs = {"Limit": 500}
            if last_key:
                kwargs["ExclusiveStartKey"] = last_key
            resp = table.scan(**kwargs)
            items.extend(resp.get("Items", []))
            last_key = resp.get("LastEvaluatedKey")
            if not last_key:
                break
        return items
    else:
        with open(source, encoding="utf-8") as f:
            data = json.load(f)
    return data.get("topics", data) if isinstance(data, dict) else data


def char_bigrams(text: str) -> set[str]:
    """日本語混じり文字列から文字 bigram 集合を返す。空白・句読点除去後に bigram 化。"""
    if not text:
        return set()
    cleaned = "".join(ch for ch in text if not ch.isspace() and ch not in "、。「」『』・…ー-—()（）[]［］")
    if len(cleaned) < 2:
        return {cleaned} if cleaned else set()
    return {cleaned[i:i + 2] for i in range(len(cleaned) - 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def collect_branched_pairs(topics: list[dict]) -> tuple[list[dict], int, int]:
    """topics から評価対象の (parent, child) ペアを抽出する。

    Returns:
        (pairs, branched_total, orphans)
          - pairs: storyPhase != null かつ articleCount >= 2 の親子ペアリスト
          - branched_total: parentTopicId を持つトピックの総数 (フィルタ前)
          - orphans: parentTopicId はあるが parent が見つからないトピック数
    """
    by_id: dict[str, dict] = {}
    for t in topics:
        tid = t.get("topicId")
        if tid:
            by_id[tid] = t

    pairs: list[dict] = []
    orphans = 0
    for t in topics:
        pid = t.get("parentTopicId")
        if not pid:
            continue
        parent = by_id.get(pid)
        if parent is None:
            orphans += 1
            continue
        if not t.get("storyPhase"):
            continue
        if (t.get("articleCount") or 0) < 2:
            continue
        pairs.append({"parent": parent, "child": t})

    branched_total = sum(1 for t in topics if t.get("parentTopicId"))
    return pairs, branched_total, orphans


def extract_entities(text: str) -> set[str]:
    """テキストから単語（エンティティ）を抽出する簡易実装。

    空白および句読点を区切り文字として、2文字以上の連続文字列を単語として抽出。
    """
    import re
    # 空白・句読点を区切り文字として分割
    words = re.split(r'[\s、。「」『』・…ー\-()（）\[\]［］]+', text)
    # 2文字以上の単語のみを返す
    return {w for w in words if len(w) >= 2}


def evaluate_branching(
    topics: list[dict],
    *,
    sample_size: int = 30,
    seed: int = 20260429,
    min_sample: int = 10,
    fb_threshold: float = 20.0,
    fm_threshold: float = 15.0,
) -> dict:
    """topics 全体を評価して dict を返す純粋関数。

    全件スキャンを実行（サンプリング廃止）。

    verdict は以下のいずれか:
      - 'PASS'              : fb/fm 両方が閾値以下
      - 'FAIL'              : fb/fm のどちらかが閾値超過
      - 'SKIP_NO_BRANCH'    : 評価対象ペアがゼロ (まだ branching が起きていない)
      - 'SKIP_SMALL_SAMPLE' : ペア数が min_sample 未満 (メトリクスは計算するが判定しない)
    """
    pairs, branched_total, orphans = collect_branched_pairs(topics)
    total = len(topics)
    branching_rate = (branched_total / total * 100) if total else 0.0

    base = {
        "total": total,
        "branched_total": branched_total,
        "branching_rate": branching_rate,
        "orphans": orphans,
        "sample": 0,
        "false_branch": 0,
        "false_merge": 0,
        "ok": 0,
        "false_branch_rate": 0.0,
        "false_merge_rate": 0.0,
        "ok_rate": 0.0,
        "results": [],
        "fb_threshold": fb_threshold,
        "fm_threshold": fm_threshold,
        "min_sample": min_sample,
    }

    if not pairs:
        base["verdict"] = "SKIP_NO_BRANCH"
        return base

    # 全件スキャン（サンプリング廃止）
    results = [evaluate_pair(p["parent"], p["child"]) for p in pairs]
    n = len(results)
    fb = sum(1 for r in results if r["verdict"] == "suspect_false_branch")
    fm = sum(1 for r in results if r["verdict"] == "suspect_false_merge")
    ok = n - fb - fm
    fb_rate = fb / n * 100
    fm_rate = fm / n * 100
    ok_rate = ok / n * 100

    base.update({
        "sample": n,
        "false_branch": fb,
        "false_merge": fm,
        "ok": ok,
        "false_branch_rate": fb_rate,
        "false_merge_rate": fm_rate,
        "ok_rate": ok_rate,
        "results": results,
    })

    if n < min_sample:
        base["verdict"] = "SKIP_SMALL_SAMPLE"
        return base

    fb_pass = fb_rate <= fb_threshold
    fm_pass = fm_rate <= fm_threshold
    base["verdict"] = "PASS" if (fb_pass and fm_pass) else "FAIL"
    return base


def evaluate_pair(parent: dict, child: dict) -> dict:
    """1 ペアの分岐判定を評価。

    誤マージ判定を強化：
      - sim < 0.15 かつ entity 重複=0 → 誤マージ疑い
      - sim < 0.2 → 誤マージ疑い（従来判定）
    """
    p_title = parent.get("title") or parent.get("generatedTitle") or ""
    c_title = child.get("title") or child.get("generatedTitle") or ""
    p_bg = char_bigrams(p_title)
    c_bg = char_bigrams(c_title)
    sim = jaccard(p_bg, c_bg)
    # keyPoint も使って補強できるなら使う
    p_kp = parent.get("keyPoint") or ""
    c_kp = child.get("keyPoint") or ""
    if p_kp and c_kp:
        sim_kp = jaccard(char_bigrams(p_kp), char_bigrams(c_kp))
        # title と keyPoint の最大値を採用（片方でも内容が一致していれば類似と扱う）
        sim = max(sim, sim_kp)

    # entity 重複を集計（誤マージ判定補強用）
    p_entities = extract_entities(p_title)
    c_entities = extract_entities(c_title)
    entity_overlap = len(p_entities & c_entities)

    if sim >= 0.6:
        verdict = "suspect_false_branch"  # 似すぎなのに分岐 → 誤分岐疑い
    elif sim < 0.15 and entity_overlap == 0:
        verdict = "suspect_false_merge"   # 非常に違う＆エンティティ重複ゼロ → 誤マージ疑い
    elif sim < 0.2:
        verdict = "suspect_false_merge"   # 違いすぎなのに親子 → 誤マージ疑い
    else:
        verdict = "ok"

    return {
        "parent_id": parent.get("topicId"),
        "child_id": child.get("topicId"),
        "parent_title": p_title,
        "child_title": c_title,
        "similarity": round(sim, 3),
        "entity_overlap": entity_overlap,
        "verdict": verdict,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=DEFAULT_SOURCE,
                    help=f"topics データソース (URL / ファイルパス / 'dynamodb'). default={DEFAULT_SOURCE}")
    ap.add_argument("--sample", type=int, default=30, help="評価サンプル数 (default 30)")
    ap.add_argument("--seed", type=int, default=20260429, help="ランダムシード")
    ap.add_argument("--error-branch-threshold", type=float, default=20.0,
                    help="誤分岐疑い率 (%%) の上限。これを超えると FAIL")
    ap.add_argument("--error-merge-threshold", type=float, default=15.0,
                    help="誤マージ疑い率 (%%) の上限。これを超えると FAIL")
    ap.add_argument("--min-sample", type=int, default=10,
                    help="この件数未満のサンプルは SKIP 扱い (default 10)。"
                         "小サンプルだと 1 ペア差で揺れる誤 FAIL を防ぐ")
    ap.add_argument("--verbose", action="store_true", help="個別ペアを出力")
    args = ap.parse_args()

    try:
        topics = fetch_topics(args.source)
    except (urllib.error.URLError, OSError, json.JSONDecodeError, RuntimeError) as e:
        print(f"[verify_branching_quality] データ取得失敗: {e}", file=sys.stderr)
        return 2

    if not topics:
        print("[verify_branching_quality] topics が空", file=sys.stderr)
        return 2

    summary = evaluate_branching(
        topics,
        sample_size=args.sample,
        seed=args.seed,
        min_sample=args.min_sample,
        fb_threshold=args.error_branch_threshold,
        fm_threshold=args.error_merge_threshold,
    )

    if args.verbose and summary["results"]:
        print("=== 個別ペア ===")
        for r in summary["results"]:
            entity_overlap = r.get("entity_overlap", 0)
            print(
                f"[{r['verdict']:>22s}] sim={r['similarity']:.3f} ent_overlap={entity_overlap} "
                f"P={r['parent_title'][:40]} | C={r['child_title'][:40]}"
            )
        print()

    ts = datetime.now(JST).strftime("%Y-%m-%dT%H:%M%z")
    verdict = summary["verdict"]
    fb = summary["false_branch"]
    fm = summary["false_merge"]
    fb_rate = summary["false_branch_rate"]
    fm_rate = summary["false_merge_rate"]
    ok = summary["ok"]
    ok_rate = summary["ok_rate"]
    n = summary["sample"]
    branched_total = summary["branched_total"]
    total = summary["total"]
    branching_rate = summary["branching_rate"]
    orphans = summary["orphans"]

    if verdict == "SKIP_NO_BRANCH":
        print(
            f"Verified-Effect: branching_quality "
            f"branching_rate={branching_rate:.1f}%({branched_total}/{total}) "
            f"error_branch=N/A error_merge=N/A "
            f"sample=0 orphans={orphans} "
            f"SKIP @ {ts}"
        )
        return 0

    metrics = (
        f"branching_rate={branching_rate:.1f}%({branched_total}/{total}) "
        f"error_branch={fb}({fb_rate:.1f}%) "
        f"error_merge={fm}({fm_rate:.1f}%) "
        f"ok={ok}({ok_rate:.1f}%) "
        f"sample={n} orphans={orphans} "
        f"thresholds=fb<={args.error_branch_threshold:.0f}/fm<={args.error_merge_threshold:.0f}"
    )

    if verdict == "SKIP_SMALL_SAMPLE":
        print(
            f"Verified-Effect: branching_quality {metrics} "
            f"min_sample={args.min_sample} "
            f"SKIP_SMALL_SAMPLE @ {ts}"
        )
        return 0

    print(f"Verified-Effect: branching_quality {metrics} {verdict} @ {ts}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
