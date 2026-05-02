#!/bin/bash
# T2026-0502-WORKFLOW-DEP-PHYSICAL: workflow YAML が参照する scripts/* / infra/* が repo に存在することを物理保証。
#
# 背景:
#   T2026-0502-IAM-CANON-RESCUE (PR #303) — c521a846 (PR #300) で apply.sh が
#   `scripts/iam_canon.py` を参照する形に書き換わったが、実体ファイルが commit されていなかった。
#   さらに 918621d3 (PR #302) で workflow `iam-policy-drift-check.yml` も同 helper 経由化したが
#   ファイル不在で IAM policy drift check が ~50 分 failure 続行。
#   本スクリプトは「workflow YAML から参照される scripts/foo.py や bash scripts/foo.sh が
#   実体として存在するか」を CI で物理 reject する。
#
# 検出パターン:
#   python3 scripts/foo.py
#   python  scripts/foo.py
#   bash    scripts/foo.sh
#   sh      scripts/foo.sh
#   ./scripts/foo.sh
#   ./infra/iam/apply.sh
#   bash infra/iam/apply.sh
#
# 検出しないパターン (意図的):
#   variable substitution (python3 "$MY_SCRIPT") — 動的解決のため check 不能
#   シェル組み込み (cat, ls, grep 等)
#   外部コマンド (aws, gh, curl 等)
#
# Exit:
#   0 = 全参照が repo に存在
#   1 = 1 件以上の参照先が不在 (CI で reject)

set -e

WORKFLOW_DIR=".github/workflows"
FOUND_MISSING=""

if [ ! -d "$WORKFLOW_DIR" ]; then
  echo "::warning::$WORKFLOW_DIR not found, skipping check"
  exit 0
fi

for wf in "$WORKFLOW_DIR"/*.yml; do
  [ -f "$wf" ] || continue
  # python3/python/bash/sh/./ で始まり scripts/ または infra/ 以下の .py/.sh/ファイルを参照する形を抽出
  refs=$(grep -oE '(python3?|bash|sh|\./)[[:space:]"'\'']*((scripts|infra)/[A-Za-z0-9_./-]+\.(py|sh))' "$wf" 2>/dev/null \
    | grep -oE '(scripts|infra)/[A-Za-z0-9_./-]+\.(py|sh)' \
    | sort -u || true)
  for ref in $refs; do
    if [ ! -f "$ref" ]; then
      line_no=$(grep -n -F "$ref" "$wf" | head -1 | cut -d: -f1)
      FOUND_MISSING="${FOUND_MISSING}
  $wf:${line_no} → $ref (NOT FOUND)"
    fi
  done
done

if [ -n "$FOUND_MISSING" ]; then
  echo "❌ Workflow YAML が repo に存在しないファイルを参照しています:"
  echo "$FOUND_MISSING"
  echo ""
  echo "対処:"
  echo "  1. 参照先ファイルを repo に commit する (推奨)"
  echo "  2. workflow から参照を削除する"
  echo ""
  echo "背景: T2026-0502-IAM-CANON-RESCUE (commit 漏れで drift CI 50min failure) の物理化。"
  echo "      参照先がなくても workflow merge できる構造を物理 reject する。"
  exit 1
fi

echo "✅ Workflow YAML が参照する scripts/* / infra/* は全て repo に存在 ($(ls "$WORKFLOW_DIR"/*.yml 2>/dev/null | wc -l) workflows checked)"
