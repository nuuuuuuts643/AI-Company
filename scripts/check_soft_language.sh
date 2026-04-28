#!/usr/bin/env bash
# T2026-0428-BD: 形骸化検出 grep CI
#
# 目的:
#   「仕組み的対策」セクションに「気を付ける/注意する/意識する/確認する」
#   などのソフト言語が混入していないか物理検査する。
#   引用 (「気を付ける」禁止 のような禁止表現) と説明用 (例:〜) は除外する。
#
# 対象ファイル:
#   - CLAUDE.md
#   - docs/rules/global-baseline.md
#   - docs/lessons-learned.md
#
# 検出パターン:
#   行が「仕組み的対策」セクション内（「仕組み的対策」ヘッダー以降〜次のヘッダー手前）
#   かつ、ソフト言語を含み、かつ「禁止」「は答えではない」「ではない」「書かない」
#   のような否定/メタ言及がない場合に ERROR。
#
# 終了コード:
#   0: 混入なし
#   1: 混入あり (CI block)
#   2: スクリプト不正 (引数等)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FILES=(
  "$ROOT/CLAUDE.md"
  "$ROOT/docs/rules/global-baseline.md"
  "$ROOT/docs/lessons-learned.md"
)

TOKENS=("気を付ける" "気をつける" "注意する" "意識する" "確認する")

# 除外する meta/否定パターン (これを含む行は引用/メタ言及とみなす):
#   - 「気を付ける」など括弧付き引用
#   - 禁止 / 書かない / は答えではない / ではない / NG / 形骸化 / 〜が混入
EXCLUDE_PATTERNS=(
  "「気を付ける」"
  "「気をつける」"
  "「注意する」"
  "「意識する」"
  "「確認する」"
  "禁止"
  "書かない"
  "答えではない"
  "ではない"
  "NG"
  "混入"
  "形骸化"
)

violations=0

check_file() {
  local file="$1"
  if [ ! -f "$file" ]; then
    echo "  SKIP: $file (not found)"
    return 0
  fi

  python3 - "$file" "${TOKENS[@]}" <<'PY'
import sys, re

path = sys.argv[1]
tokens = sys.argv[2:]

EXCLUDES = [
    "「気を付ける」", "「気をつける」", "「注意する」", "「意識する」", "「確認する」",
    "禁止", "書かない", "答えではない", "ではない", "NG", "混入", "形骸化",
    "は答えではない", "ふんわり", "〜は答えではない",
]

with open(path, encoding="utf-8") as f:
    lines = f.readlines()

# 「仕組み的対策」が出現する行から、次の見出し (## or **見出し**: or 表区切り) 手前までを section とする
in_section = False
section_start = None
violations = []
header_re = re.compile(r"^(#{1,6}\s|---\s*$|\| Why|\| 観点|\| 規則|\| ID|\| ルール)")
section_open_re = re.compile(r"^\*\*仕組み的対策")

for i, line in enumerate(lines):
    stripped = line.rstrip("\n")
    if section_open_re.match(stripped.lstrip("- ").lstrip()):
        in_section = True
        section_start = i + 1
        continue
    if in_section:
        # セクション終了判定: 空行が 2 連続 / 別の **見出し:** / なぜなぜ表 / 次の事象見出し
        if header_re.match(stripped):
            in_section = False
            continue
        if re.match(r"^\*\*[^*]+\*\*:?\s*$", stripped) and "仕組み的対策" not in stripped:
            in_section = False
            continue
        # ソフト言語混入検査
        for tok in tokens:
            if tok in stripped:
                # 除外条件
                if any(ex in stripped for ex in EXCLUDES):
                    continue
                violations.append((i + 1, tok, stripped))
                break

if violations:
    print(f"  ❌ {path}")
    for ln, tok, text in violations:
        print(f"     L{ln} [{tok}] {text}")
    sys.exit(1)
else:
    print(f"  ✅ {path}")
    sys.exit(0)
PY
}

echo "=== 形骸化検出 grep (T2026-0428-BD) ==="
echo ""
echo "対象: 「仕組み的対策」セクション内のソフト言語混入検査"
echo "検出語: ${TOKENS[*]}"
echo ""

for f in "${FILES[@]}"; do
  rel="${f#$ROOT/}"
  if ! check_file "$f"; then
    violations=$((violations + 1))
  fi
done

echo ""
if [ "$violations" -gt 0 ]; then
  echo "❌ ERROR: $violations ファイルにソフト言語混入"
  echo ""
  echo "→ 「仕組み的対策」は CI / hook / metric / SLI / scripts のいずれかで物理化する。"
  echo "   テキストの「気を付ける/注意する/意識する/確認する」では何も担保されない。"
  exit 1
fi

echo "✅ ソフト言語混入なし"
exit 0
