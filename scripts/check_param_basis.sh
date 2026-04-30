#!/bin/bash
# check_param_basis.sh — T2026-0429-N
# PR本文/直近 commit のいずれにも次の3要素のうち 1 つも含まれていない場合に WARNING を出す:
#   - "## このPRで答えられる問い"  (PRテンプレで埋まる)
#   - "# measured:"                (実測根拠)
#   - "# theoretical:"             (理論根拠)
# 強制ブロックはしない (exit 0)。緩い運用で、PRレビュアーの目視を促す目的。
#
# 環境変数:
#   PR_BODY_FILE       — PR 本文を書き出したファイルパス (gh pr view で取得した想定)
#   PR_BODY            — PR 本文文字列 (PR_BODY_FILE がない場合に使う)
#   COMMIT_RANGE       — 検査する commit range (default: origin/main..HEAD)
#
# CI から呼ぶ場合は PR_BODY_FILE を渡す想定。ローカル実行は引数なしで OK (commit range のみ確認)。

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMMIT_RANGE="${COMMIT_RANGE:-origin/main..HEAD}"

found=0
sources=""

# 1) PR 本文確認
pr_body=""
if [ -n "${PR_BODY_FILE:-}" ] && [ -f "${PR_BODY_FILE}" ]; then
  pr_body="$(cat "${PR_BODY_FILE}")"
elif [ -n "${PR_BODY:-}" ]; then
  pr_body="${PR_BODY}"
fi

if [ -n "$pr_body" ]; then
  # テンプレのプレースホルダ (HTMLコメント内) は除外して判定
  pr_body_stripped="$(printf '%s' "$pr_body" | python3 -c '
import re, sys
src = sys.stdin.read()
# Remove HTML comments
src = re.sub(r"<!--.*?-->", "", src, flags=re.DOTALL)
print(src)
')"
  # "## このPRで答えられる問い" のセクションに実際の記述があるか (空セクション/プレースホルダのみ検出)
  if printf '%s' "$pr_body_stripped" | python3 -c '
import re, sys
src = sys.stdin.read()
# Split on top-level ## headings
parts = re.split(r"^##\s+", src, flags=re.MULTILINE)
for p in parts:
    head, _, body = p.partition("\n")
    if "このPRで答えられる問い" in head and body.strip():
        sys.exit(0)
sys.exit(1)
' 2>/dev/null; then
    found=1
    sources="${sources} pr-template-question"
  fi
  if printf '%s' "$pr_body" | grep -qE '#\s*measured:'; then
    found=1
    sources="${sources} pr-measured"
  fi
  if printf '%s' "$pr_body" | grep -qE '#\s*theoretical:'; then
    found=1
    sources="${sources} pr-theoretical"
  fi
fi

# 2) commit message 確認
if commit_msgs="$(git -C "$REPO_ROOT" log --format=%B "$COMMIT_RANGE" 2>/dev/null)"; then
  if printf '%s' "$commit_msgs" | grep -qE '#\s*measured:'; then
    found=1
    sources="${sources} commit-measured"
  fi
  if printf '%s' "$commit_msgs" | grep -qE '#\s*theoretical:'; then
    found=1
    sources="${sources} commit-theoretical"
  fi
fi

# 3) diff 中のコメント確認 (新規コメントとして埋め込まれた根拠)
if diff_text="$(git -C "$REPO_ROOT" diff "$COMMIT_RANGE" 2>/dev/null)"; then
  # 追加行 (^+) 中の "# measured:" / "# theoretical:" / "// measured:" / "// theoretical:"
  if printf '%s' "$diff_text" | grep -E '^\+' | grep -qE '(#|//)\s*measured:'; then
    found=1
    sources="${sources} diff-measured"
  fi
  if printf '%s' "$diff_text" | grep -E '^\+' | grep -qE '(#|//)\s*theoretical:'; then
    found=1
    sources="${sources} diff-theoretical"
  fi
fi

if [ "$found" -eq 1 ]; then
  echo "✅ check_param_basis: 係数・パラメータの根拠が見つかりました (sources:${sources})"
  exit 0
fi

cat >&2 <<EOF
⚠️  check_param_basis: WARNING
   このPR/commit に係数・パラメータの根拠 (# measured: / # theoretical: / PRテンプレ「このPRで答えられる問い」) が見つかりません。
   将来「これは正しかったか」を判断するため、可能なら以下のいずれかを追加してください:
     - PR本文の「## このPRで答えられる問い」セクションに具体的な問いを書く
     - 係数を導入したコードに ${COLOR_NOTE:-}# measured: <実測値>${COLOR_NOTE:-} or # theoretical: <理論根拠> コメントを添える
     - commit message に同様の根拠行を含める
   (現在は WARNING のみ・強制ブロックなし — T2026-0429-N)
EOF

exit 0
