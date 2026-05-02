#!/bin/bash
# conflict_check.sh — shared docs が UU (両側変更) 状態だったら ERROR で停止
#
# 出自: docs/lessons-learned.md 「コンフリクト解決時に upstream 採用で CLAUDE.md を破壊（2026-05-02）」
# 物理化対象: shared docs (CLAUDE.md / WORKING.md / TASKS.md / HISTORY.md / docs/lessons-learned.md)
#
# 仕様:
#   - `git status --porcelain` で UU を抽出する
#   - shared docs (上記 5 ファイル) が含まれていれば ERROR (exit 1) + 標準エラー出力で警告
#   - shared docs が含まれず、コードファイルだけ UU なら exit 0 (本 script の責務外)
#   - 引数なし。cwd を git repo として扱う
#   - test での mock: 環境変数 CONFLICT_CHECK_GIT_STATUS_OUTPUT に
#     `git status --porcelain` の出力を入れると実 git に問い合わせず env 値で判定する
#
# 詳細は docs/rules/conflict-resolution.md を参照
set -u

SHARED_DOCS=(
  "CLAUDE.md"
  "WORKING.md"
  "TASKS.md"
  "HISTORY.md"
  "docs/lessons-learned.md"
)

# git status 取得 (mock 対応)
# git の porcelain v1 形式: "XY <path>" — 両側変更は "UU"。
# rename/copy の "AU"/"UA"/"DU"/"UD" もマージコンフリクトの一種だが、
# shared docs では rename/copy は通常起きないので UU だけを対象にする。
if [ -n "${CONFLICT_CHECK_GIT_STATUS_OUTPUT+x}" ]; then
  STATUS_OUTPUT="$CONFLICT_CHECK_GIT_STATUS_OUTPUT"
else
  STATUS_OUTPUT="$(git status --porcelain 2>/dev/null || true)"
fi

# UU 行のパスを抽出 (porcelain v1: "UU <path>")
# パスにスペースが入る可能性は低いが、awk で先頭 2 文字 "UU" を検出して
# それ以降を path として読む (空白 1 個区切り想定)。
UU_PATHS=$(echo "$STATUS_OUTPUT" | awk '/^UU / { sub(/^UU /, ""); print }')

# shared docs と突合
HIT=""
while IFS= read -r p; do
  [ -z "$p" ] && continue
  for shared in "${SHARED_DOCS[@]}"; do
    if [ "$p" = "$shared" ]; then
      HIT="${HIT}${p}"$'\n'
      break
    fi
  done
done <<< "$UU_PATHS"

if [ -n "$HIT" ]; then
  {
    echo "ERROR: shared docs are in conflict (UU) state."
    while IFS= read -r p; do
      [ -z "$p" ] && continue
      echo "  - $p"
    done <<< "$HIT"
    echo "shared docs は両側マージ必須・upstream 採用禁止。"
    echo "詳しくは docs/rules/conflict-resolution.md を参照。"
  } >&2
  exit 1
fi

exit 0
