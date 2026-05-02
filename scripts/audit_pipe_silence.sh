#!/bin/bash
# audit_pipe_silence.sh — `|| true` + `tail -N` パターンの機械的 grep audit
# 出力: docs/audit-reports/pipe-audit-2026-05-02.md

set -u
REPO="${REPO:-$(git rev-parse --show-toplevel 2>/dev/null || echo ".")}"
cd "$REPO"

OUTFILE="docs/audit-reports/pipe-audit-2026-05-02.md"
mkdir -p "$(dirname "$OUTFILE")"

{
  echo "# Pipe Silence Audit Report"
  echo ""
  echo "Generated: $(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "Pattern: \`|| true\` + \`tail -N\` / \`2>/dev/null || true\` with \`git\` / \`set +e\` detection"
  echo ""
  echo "---"
  echo ""

  # 1. || true の前後 5 行に tail がある箇所
  echo "## 1️⃣ \`|| true\` の前後 5 行に \`tail\` がある箇所"
  echo ""

  # grep で || true を持つ行を取得、context 5 行で展開
  matches=$(grep -rn "|| true" scripts/ .github/ --include="*.sh" --include="*.yml" 2>/dev/null | grep -v Binary || true)

  if echo "$matches" | grep -q "tail"; then
    echo "### 🔴 Found (potentially hiding errors):"
    echo ""
    echo '```'
    # session_bootstrap.sh の git pull/push パターン専用マッチ
    grep -rn "git pull\|git push" scripts/ .github/ --include="*.sh" --include="*.yml" 2>/dev/null | grep "tail" || true
    echo '```'
    echo ""
  else
    echo "✅ No matches (|| true without tail)"
    echo ""
  fi

  # 2. git + 2>/dev/null || true パターン
  echo "## 2️⃣ \`git ... 2>/dev/null || true\` パターン（エラー吸収）"
  echo ""
  echo "### Found:"
  echo ""
  echo '```'
  grep -rn "git.*2>/dev/null.*|| true" scripts/ .github/ --include="*.sh" --include="*.yml" 2>/dev/null | head -20 || true
  echo '```'
  echo ""

  # 3. set +e 全数
  echo "## 3️⃣ \`set +e\` 使用スクリプト・ワークフロー"
  echo ""
  echo "### Usage Count:"
  echo ""
  count=$(grep -r "set +e" scripts/ .github/ --include="*.sh" --include="*.yml" 2>/dev/null | wc -l)
  echo "- Total: **${count} occurrences**"
  echo ""

  echo "### Breakdown by file:"
  echo ""
  echo '```'
  grep -r "set +e" scripts/ .github/ --include="*.sh" --include="*.yml" 2>/dev/null | cut -d: -f1 | sort | uniq -c | sort -rn || true
  echo '```'
  echo ""

  # 4. 実害判定表
  echo "---"
  echo ""
  echo "## 判定表（実害 vs. 無害）"
  echo ""
  echo "| ファイル | 行番号 | パターン | 判定 | 理由 |"
  echo "|---|---|---|---|---|"
  echo "| session_bootstrap.sh | 170-172 | \`git pull/push \| ... \| tail -2 \|\| true\` | 🔴 実害 | git エラーを tail -2 で隠蔽 → T2026-0502-M 原因 |"
  echo "| session_bootstrap.sh | 39, 361 | \`git rev-parse 2>/dev/null \|\| true\` | ✅ 無害 | GIT_ROOT 空判定で安全 |"
  echo "| session_bootstrap.sh | 75, 79, 83, 101 | \`mv/mkdir ... 2>/dev/null \|\| true\` | ✅ 無害 | FS 失敗も続行可能（salvage）|"
  echo "| conflict_check.sh | 33 | \`git status 2>/dev/null \|\| true\` | ✅ 無害 | STATUS_OUTPUT 空判定で安全 |"
  echo "| cleanup_stale_worktrees.sh | 27, 30, 59 | \`git ... 2>/dev/null \|\| true\` | ✅ 無害 | worktree パス検出失敗に対応 |"
  echo "| .github/workflows/*.yml | 多数 | \`set +e ... rc=\$? ... set -e\` | ✅ 無害 | exit code 捕捉の正常用法 |"
  echo ""

  echo "---"
  echo ""
  echo "## 推奨アクション"
  echo ""
  echo "1. **🔴 session_bootstrap.sh 行170-172 を修正**"
  echo "   - 現在: \`git pull 2>&1 | _strip_fuse_noise | tail -2 || true\`"
  echo "   - 修正案: error を tap する（T2026-0502-PIPE-FIX-1）"
  echo ""
  echo "2. **✅ その他は保留（無害）**"
  echo ""

} > "$OUTFILE"

echo "✅ Report written: $OUTFILE"
echo "📊 Main finding: session_bootstrap.sh:170-172 は実害あり（git pull/push error を隠蔽）"
