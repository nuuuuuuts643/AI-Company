#!/usr/bin/env bash
# scripts/check_lessons_landings.sh
# 横展開チェックリスト の landing 物理検証
#
# 目的: docs/lessons-learned.md 末尾の「横展開チェックリスト」表を読み、
#       状態 ✅ の行で「実装ファイル」列に書かれたパスが repo に存在するかを物理検査する。
#       「書いただけで動いていない」対策 (fossilize) を CI で検出する。
#
# 由来: 2026-04-28 PM T2026-0428-AX なぜなぜ — 過去対策の landing 検証ルーチン欠如。
#       仕様: docs/rules/global-baseline.md §1「仕組み的対策の landing 検証」
#
# 使い方:
#   bash scripts/check_lessons_landings.sh           # 通常検査 (✅ 行のみ)
#   bash scripts/check_lessons_landings.sh --strict  # ✗ 行も含めて全部検査 (TASKS.md と紐付くか)
#
# exit code:
#   0 — 全 ✅ 行の実装ファイルが存在
#   1 — ✅ 行で実装ファイル不在 (fossilize 検出)

set -u

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

LESSONS="docs/lessons-learned.md"
STRICT="${1:-}"

if [ ! -f "$LESSONS" ]; then
  echo "::error::$LESSONS が存在しません"
  exit 1
fi

# 横展開チェックリスト表を抽出
# 表は `### 横展開チェックリスト` セクション内の markdown table。
# 状態列: ✅ / ✗ / ⚠
# 実装ファイル列: パス (バッククォートで囲まれている場合あり)
TABLE_BLOCK=$(awk '
  /^### 横展開チェックリスト/ { in_section = 1; next }
  /^---$/ { if (in_section) in_section = 0 }
  in_section && /^\| / { print }
' "$LESSONS")

if [ -z "$TABLE_BLOCK" ]; then
  echo "::error::横展開チェックリスト 表が見つかりません ($LESSONS)"
  exit 1
fi

MISSING=0
CHECKED=0
FOSSIL=0

while IFS= read -r line; do
  # ヘッダー行 / 区切り行をスキップ
  if echo "$line" | grep -qE "^\|[[:space:]]*対策名|^\|[[:space:]]*-+"; then
    continue
  fi

  # 列を取得 (`|` 区切り、前後空白 trim)
  STATE=$(echo "$line" | awk -F'|' '{gsub(/^[[:space:]]+|[[:space:]]+$/, "", $5); print $5}')
  IMPL=$(echo "$line"  | awk -F'|' '{gsub(/^[[:space:]]+|[[:space:]]+$/, "", $4); print $4}')
  NAME=$(echo "$line"  | awk -F'|' '{gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2); print $2}')

  # 実装ファイル列のパスを抽出 (バッククォート内)
  PATHS=$(echo "$IMPL" | grep -oE '`[^`]+`' | tr -d '`' || true)

  # 状態ごとの処理
  case "$STATE" in
    "✅")
      # ✅ 行は必ず物理確認
      if [ -z "$PATHS" ]; then
        # path 抽出できなかった場合は path 全体を試行
        PATHS="$IMPL"
      fi
      for p in $PATHS; do
        # `(install_hooks.sh)` のような括弧を除去
        cleaned=$(echo "$p" | sed -E 's/^\(|\)$//g')
        # `.git/hooks/...` は git ignore されている可能性があるので install_hooks.sh の存在で代替
        if echo "$cleaned" | grep -q "^\.git/hooks/"; then
          if [ -f "scripts/install_hooks.sh" ]; then
            # OK
            :
          else
            echo "::error::[fossilize] $NAME → $cleaned (scripts/install_hooks.sh が無い)"
            MISSING=$((MISSING+1))
          fi
          CHECKED=$((CHECKED+1))
          continue
        fi
        # 行番号付きパス (例: `path:215-248`) はパス部分だけ取り出す
        cleaned_path=$(echo "$cleaned" | sed -E 's/:[0-9].*$//')
        if [ -e "$cleaned_path" ]; then
          CHECKED=$((CHECKED+1))
        else
          echo "::error::[fossilize] ✅ なのに実体なし: $NAME → $cleaned_path"
          MISSING=$((MISSING+1))
          FOSSIL=$((FOSSIL+1))
        fi
      done
      ;;
    "✗")
      # 未実装行は --strict のときだけ警告
      if [ "$STRICT" = "--strict" ]; then
        echo "::warning::[未実装] $NAME (期待: $IMPL)"
      fi
      ;;
    "⚠")
      echo "::warning::[部分実装] $NAME — $IMPL"
      ;;
  esac
done <<< "$TABLE_BLOCK"

echo ""
echo "===== 横展開チェックリスト landing 検証 ====="
echo "✅ 行で実体確認した entry: $CHECKED"
echo "✗ fossilize (✅ なのに実体なし): $FOSSIL"
echo ""

if [ $MISSING -gt 0 ]; then
  echo "::error::過去仕組み的対策が $MISSING 件 fossilize しています。lessons-learned.md の表を修正してください"
  exit 1
fi

echo "✅ 横展開チェックリスト 全 ✅ 行の実体確認 OK"
exit 0
