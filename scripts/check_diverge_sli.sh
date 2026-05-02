#!/bin/bash
# T2026-0502-DIVERGE-SLI: ローカル diverge 観測 SLI
#
# 根本原因: T2026-0502-M で origin/main との diverge が 11h 放置され、
#   pre-push hook / bootstrap exit 1 で発生は塞いだが bypass 時の検出網が欠如していた。
#   本スクリプトはその「外部観測」レイヤー。
#
# 使い方:
#   bash scripts/check_diverge_sli.sh            # カレントリポジトリの HEAD を計測
#   DIVERGE_BRANCH=feature/foo bash scripts/check_diverge_sli.sh  # ブランチ指定
#
# 出力:
#   stdout: diverge_count=<N>
#   stderr: WARN (2以上) / ERROR (5以上)
#
# 終了コード:
#   0: 正常 (0 or 1)
#   1: WARN (2〜4)
#   2: ERROR (5以上)
#   3: git コマンド失敗

set -uo pipefail

BRANCH="${DIVERGE_BRANCH:-HEAD}"
BASE="${DIVERGE_BASE:-origin/main}"

# git が使えるか確認
if ! git rev-parse --git-dir > /dev/null 2>&1; then
  echo "ERROR: git repository not found" >&2
  exit 3
fi

# origin/main が取得できない場合 (CI ではシャロークローンで参照できないことがある)
if ! git rev-parse "$BASE" > /dev/null 2>&1; then
  echo "::warning::check_diverge_sli: $BASE が見つからない — fetch が必要かもしれません" >&2
  echo "diverge_count=unknown"
  exit 0
fi

COUNT=$(git rev-list --count "${BASE}..${BRANCH}" 2>/dev/null) || {
  echo "ERROR: git rev-list failed" >&2
  exit 3
}

echo "diverge_count=${COUNT}"

if [ "$COUNT" -ge 5 ]; then
  echo "ERROR: local diverge ${COUNT} commits ahead of ${BASE} (threshold: 5)" >&2
  exit 2
elif [ "$COUNT" -ge 2 ]; then
  echo "WARN: local diverge ${COUNT} commits ahead of ${BASE} (threshold: 2)" >&2
  exit 1
fi

exit 0
