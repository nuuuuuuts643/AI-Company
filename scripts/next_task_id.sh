#!/usr/bin/env bash
# scripts/next_task_id.sh
# 日付ベースの未使用タスクIDを返す。
#
# 出力例: T2026-0428-A
#
# 使い方:
#   NEW_ID=$(bash scripts/next_task_id.sh)
#   echo "$NEW_ID"
#
# 仕様:
#   - 日付プレフィックス: T<YYYY>-<MMDD>-
#   - サフィックス: A〜Z (使い切ったら AA〜ZZ)
#   - 既存 ID は TASKS.md / HISTORY.md / WORKING.md / docs/*.md / git log から走査
#   - 候補の一意性を確認してから出力

set -u

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

DATE=$(TZ=Asia/Tokyo date '+%Y-%m%d')
PREFIX="T${DATE}-"

# 走査対象
SOURCES=(
  "TASKS.md"
  "HISTORY.md"
  "WORKING.md"
)
# docs/ 配下の md も対象に追加（ドキュメントから ID 引用される場合に検出）
while IFS= read -r f; do
  SOURCES+=("$f")
done < <(find docs -name "*.md" -maxdepth 3 2>/dev/null || true)

# 本日分の既存 suffix を抽出（ファイルから）
SUFFIXES=$(grep -hoE "T${DATE}-[A-Z]+" "${SOURCES[@]}" 2>/dev/null \
  | sed "s/T${DATE}-//" | sort -u)

# git log からも同日の ID を抽出
GIT_SUFFIXES=$(git log --all --grep="T${DATE}-" --oneline 2>/dev/null | grep -oE "T${DATE}-[A-Z]+" | sed "s/T${DATE}-//" | sort -u)

# 重複を除去（git と ファイルの組み合わせ）
ALL_SUFFIXES=$(printf "%s\n%s\n" "$SUFFIXES" "$GIT_SUFFIXES" | grep -v '^$' | sort -u)

# A〜Z で未使用の最初を返す
for L in {A..Z}; do
  if ! echo "$ALL_SUFFIXES" | grep -qx "$L"; then
    echo "${PREFIX}${L}"
    exit 0
  fi
done

# AA〜ZZ
for L1 in {A..Z}; do
  for L2 in {A..Z}; do
    if ! echo "$ALL_SUFFIXES" | grep -qx "${L1}${L2}"; then
      echo "${PREFIX}${L1}${L2}"
      exit 0
    fi
  done
done

echo "ERROR: ran out of suffixes for $DATE" >&2
exit 1
