#!/bin/bash
# T2026-0429-D: HISTORY.md からタスクカテゴリを集計し、繰り返し発生パターンを検出
#
# 目的: 「同じ root cause のバグ修正・コンフリクト解消が繰り返されてる」を物理検出する。
#       人間が「たまたま気づく」のを待たず、起動時に自動で警告する。
#
# 仕様:
#   - HISTORY.md の `^- ✅` 行を完了タスクとして読む (新しい順に並んでいる前提)
#   - 直近 LIMIT (=30) 件を対象にカテゴリ推定: fix / merge-conflict / ci / perf / docs / feat / ops
#   - カテゴリ別件数が THRESHOLD (=3) 以上なら ⚠️ PATTERN: [カテゴリ] が繰り返し発生 を出す
#   - 「fix」「merge-conflict」「ci」のような **問題系** カテゴリのみ警告対象 (feat/docs は除外)
#   - HISTORY.md が無い / 空なら何もしない (起動チェックを止めない)
#
# 使い方:
#   bash scripts/analyze_task_patterns.sh
#   LIMIT=50 THRESHOLD=2 bash scripts/analyze_task_patterns.sh

set -u

REPO="${REPO:-.}"
LIMIT="${LIMIT:-30}"
THRESHOLD="${THRESHOLD:-3}"
HISTORY="${REPO}/HISTORY.md"

[ -f "$HISTORY" ] || exit 0

python3 - "$HISTORY" "$LIMIT" "$THRESHOLD" <<'PY' || exit 0
import sys, re
from collections import Counter

path, limit, threshold = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
try:
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
except Exception:
    sys.exit(0)

# `^- ✅` で始まる完了タスクの 1 行目を抽出 (新しい順に並んでいる)
tasks = [l.strip() for l in lines if l.startswith("- ✅")]
if not tasks:
    sys.exit(0)
tasks = tasks[:limit]

# キーワードでカテゴリ推定 (順序が優先順位 — マッチした最初のカテゴリを採用)
RULES = [
    # 問題系 (警告対象)
    ("merge-conflict", [r"マージコンフリクト", r"コンフリクト解消", r"merge conflict", r"\bconflict\b"]),
    ("ci",             [r"\bCI\b", r"GitHub Actions.*失敗", r"workflow.*失敗", r"hook.*失敗", r"pre-commit.*失敗"]),
    ("regression",     [r"リグレッション", r"\bregression\b", r"再発", r"後退"]),
    ("rollback",       [r"ロールバック", r"\brollback\b", r"revert"]),
    ("fix",            [r"\bfix\b", r"修正", r"バグ", r"不具合", r"原因.*特定", r"根本原因", r"の解消", r"を解消"]),
    ("perf",           [r"\bperf\b", r"パフォーマンス", r"高速化", r"コスト削減", r"レスポンス改善"]),
    ("ops",            [r"運用", r"監視", r"アラート", r"SLI", r"runbook", r"ロールアウト"]),
    # 中立系 (集計はするが警告対象外)
    ("feat",           [r"新設", r"追加", r"新機能", r"\bfeat\b", r"実装", r"バッジ追加"]),
    ("docs",           [r"\bdocs?\b", r"ドキュメント", r"README", r"整理", r"文書"]),
]
PROBLEM_CATEGORIES = {"merge-conflict", "ci", "regression", "rollback", "fix"}

def categorize(title: str) -> str:
    for cat, patterns in RULES:
        for p in patterns:
            if re.search(p, title, re.IGNORECASE):
                return cat
    return "other"

counts = Counter(categorize(t) for t in tasks)

# 問題系カテゴリで threshold 以上のものを警告
flagged = [(cat, n) for cat, n in counts.items()
           if cat in PROBLEM_CATEGORIES and n >= threshold]
flagged.sort(key=lambda x: -x[1])

for cat, n in flagged:
    print(f"⚠️ PATTERN: [{cat}] が繰り返し発生 ({n}件 / 直近{len(tasks)}件中)")
PY
