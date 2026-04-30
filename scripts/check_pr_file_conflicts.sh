#!/bin/bash
# PR 同時編集ファイル衝突検出スクリプト
# 用途: GitHub Actions の pull_request トリガー、または手動実行
# 機能:
#   - gh pr list で現在オープンな PR のファイル一覧を取得
#   - 同一ファイルを 2 件以上の PR が編集している場合に WARN/ERROR を出力
#   - conflict 高リスクファイル（コード本体）が複数 PR で編集されていれば exit 1 (ERROR)
#   - ドキュメントのみ（*.md, *.json）の重複は WARN に留める (exit 0)
#
# 使用例:
#   bash scripts/check_pr_file_conflicts.sh
#   echo $?  # 0: OK / WARN のみ, 1: ERROR (コード重複編集あり)
#
# 関連:
#   - T2026-0429-PR-CONFLICT
#   - .github/workflows/pr-conflict-guard.yml
#   - CLAUDE.md「同名ファイル並行編集禁止」ルールの物理ガード

set -u

# conflict 高リスク（複数 PR で同時編集されたら ERROR）
# proc_ai.py / proc_storage.py / handler.py の他、CI workflow も含む
HIGH_RISK_PATTERNS=(
  'projects/P003-news-timeline/lambda/processor/proc_ai\.py'
  'projects/P003-news-timeline/lambda/processor/proc_storage\.py'
  'projects/P003-news-timeline/lambda/processor/handler\.py'
  'projects/P003-news-timeline/lambda/processor/proc_fetcher\.py'
  'projects/P003-news-timeline/lambda/processor/proc_quality\.py'
  '\.github/workflows/deploy-lambdas\.yml'
  '\.github/workflows/deploy-p003\.yml'
)

is_high_risk() {
  local path="$1"
  for pat in "${HIGH_RISK_PATTERNS[@]}"; do
    if [[ "$path" =~ ^${pat}$ ]]; then
      return 0
    fi
  done
  return 1
}

is_doc_only() {
  local path="$1"
  case "$path" in
    *.md|*.json|*.txt|*.yaml|*.yml)
      # workflows/*.yml は doc 扱いしない
      if [[ "$path" == .github/workflows/*.yml ]]; then
        return 1
      fi
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

# gh CLI 確認
if ! command -v gh >/dev/null 2>&1; then
  echo "❌ gh CLI not found"
  exit 2
fi

# PR 一覧取得（open のみ）
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT

if ! gh pr list --state open --limit 100 --json number,title,headRefName,files > "$TMP" 2>/dev/null; then
  echo "❌ gh pr list failed"
  exit 2
fi

# JSON が空配列なら早期 return
if ! command -v jq >/dev/null 2>&1; then
  echo "❌ jq not found"
  exit 2
fi

PR_COUNT=$(jq 'length' "$TMP")
if [ "$PR_COUNT" -eq 0 ]; then
  echo "✅ open PR なし"
  exit 0
fi

echo "── PR file conflict check (open PRs: $PR_COUNT) ──"

# ファイル → PR 番号一覧 のマップを作る
# tab-separated: file<TAB>pr_number
MAP=$(jq -r '
  .[] |
  . as $pr |
  .files[]? |
  "\(.path)\t\($pr.number)"
' "$TMP" | sort)

# uniq で 2 件以上を抽出
DUPLICATES=$(echo "$MAP" | awk -F'\t' '
  {
    if (file == $1) {
      prs = prs "," $2
      count++
    } else {
      if (count >= 2) print file "\t" prs
      file = $1
      prs = $2
      count = 1
    }
  }
  END { if (count >= 2) print file "\t" prs }
')

if [ -z "$DUPLICATES" ]; then
  echo "✅ 重複編集なし"
  exit 0
fi

ERROR_COUNT=0
WARN_COUNT=0

while IFS=$'\t' read -r FILE PRS; do
  [ -z "$FILE" ] && continue
  PR_LIST=$(echo "$PRS" | tr ',' ' ')
  PR_LINKS=$(echo "$PR_LIST" | tr ' ' '\n' | sed 's/^/#/' | tr '\n' ' ')

  if is_high_risk "$FILE"; then
    echo "❌ ERROR  $FILE  (PRs: $PR_LINKS)"
    echo "    → conflict 高リスク (コード本体)。1 PR にまとめるか順次 merge してください"
    ERROR_COUNT=$((ERROR_COUNT + 1))
  elif is_doc_only "$FILE"; then
    echo "⚠️  WARN  $FILE  (PRs: $PR_LINKS) [docs/config — 同時 merge 時は手動で conflict 解決]"
    WARN_COUNT=$((WARN_COUNT + 1))
  else
    echo "❌ ERROR  $FILE  (PRs: $PR_LINKS)"
    echo "    → コード/設定の多重編集。conflict のリスクあり"
    ERROR_COUNT=$((ERROR_COUNT + 1))
  fi
done <<< "$DUPLICATES"

echo "── 結果 ──"
echo "ERROR: $ERROR_COUNT 件 / WARN: $WARN_COUNT 件"

if [ "$ERROR_COUNT" -gt 0 ]; then
  exit 1
fi
exit 0
