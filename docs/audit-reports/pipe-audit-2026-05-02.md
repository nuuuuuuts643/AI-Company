# Pipe Silence Audit Report

Generated: 2026-05-02 11:41:55 JST
Pattern: `|| true` + `tail -N` / `2>/dev/null || true` with `git` / `set +e` detection

---

## 1️⃣ `|| true` の前後 5 行に `tail` がある箇所

### 🔴 Found (potentially hiding errors):

```
scripts/session_bootstrap.sh:170:  git pull --no-rebase --no-edit origin main 2>&1 | _strip_fuse_noise | tail -2 || true
scripts/session_bootstrap.sh:172:  git push 2>&1 | _strip_fuse_noise | tail -2 || true
scripts/audit_pipe_silence.sh:33:    grep -rn "git pull\|git push" scripts/ .github/ --include="*.sh" --include="*.yml" 2>/dev/null | grep "tail" || true
scripts/audit_pipe_silence.sh:74:  echo "| session_bootstrap.sh | 170-172 | \`git pull/push \| ... \| tail -2 \|\| true\` | 🔴 実害 | git エラーを tail -2 で隠蔽 → T2026-0502-M 原因 |"
scripts/audit_pipe_silence.sh:87:  echo "   - 現在: \`git pull 2>&1 | _strip_fuse_noise | tail -2 || true\`"
```

## 2️⃣ `git ... 2>/dev/null || true` パターン（エラー吸収）

### Found:

```
scripts/session_bootstrap.sh:39:  GIT_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel 2>/dev/null || true)"
scripts/session_bootstrap.sh:75:      mv "$lock" ".git/_garbage/$(basename $lock).$(date +%s%N)" 2>/dev/null || true
scripts/session_bootstrap.sh:79:      mv .git/rebase-merge ".git/_garbage/rebase-merge.$(date +%s%N)" 2>/dev/null || true
scripts/session_bootstrap.sh:83:      mv .git/rebase-apply ".git/_garbage/rebase-apply.$(date +%s%N)" 2>/dev/null || true
scripts/session_bootstrap.sh:168:    git commit -m "chore: bootstrap sync $(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M JST')" 2>/dev/null || true
scripts/session_bootstrap.sh:361:  GIT_TOP="$(git rev-parse --show-toplevel 2>/dev/null || true)"
scripts/conflict_check.sh:33:  STATUS_OUTPUT="$(git status --porcelain 2>/dev/null || true)"
scripts/audit_pipe_silence.sh:26:  matches=$(grep -rn "|| true" scripts/ .github/ --include="*.sh" --include="*.yml" 2>/dev/null | grep -v Binary || true)
scripts/audit_pipe_silence.sh:33:    grep -rn "git pull\|git push" scripts/ .github/ --include="*.sh" --include="*.yml" 2>/dev/null | grep "tail" || true
scripts/audit_pipe_silence.sh:41:  # 2. git + 2>/dev/null || true パターン
scripts/audit_pipe_silence.sh:42:  echo "## 2️⃣ \`git ... 2>/dev/null || true\` パターン（エラー吸収）"
scripts/audit_pipe_silence.sh:47:  grep -rn "git.*2>/dev/null.*|| true" scripts/ .github/ --include="*.sh" --include="*.yml" 2>/dev/null | head -20 || true
scripts/audit_pipe_silence.sh:63:  grep -r "set +e" scripts/ .github/ --include="*.sh" --include="*.yml" 2>/dev/null | cut -d: -f1 | sort | uniq -c | sort -rn || true
scripts/cleanup_stale_worktrees.sh:27:  GIT_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel 2>/dev/null || true)"
scripts/cleanup_stale_worktrees.sh:30:    COMMON_DIR="$(git -C "$GIT_ROOT" rev-parse --git-common-dir 2>/dev/null || true)"
scripts/cleanup_stale_worktrees.sh:59:SELF_GIT_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel 2>/dev/null || true)"
```

## 3️⃣ `set +e` 使用スクリプト・ワークフロー

### Usage Count:

- Total: **      15 occurrences**

### Breakdown by file:

```
   6 scripts/audit_pipe_silence.sh
   2 .github/workflows/ux-check.yml
   1 .github/workflows/revenue-sli.yml
   1 .github/workflows/qualitative-eval.yml
   1 .github/workflows/pr-conflict-guard.yml
   1 .github/workflows/meta-doc-guard.yml
   1 .github/workflows/freshness-check.yml
   1 .github/workflows/env-scripts-dryrun.yml
   1 .github/workflows/ci.yml
```

---

## 判定表（実害 vs. 無害）

| ファイル | 行番号 | パターン | 判定 | 理由 |
|---|---|---|---|---|
| session_bootstrap.sh | 170-172 | `git pull/push \| ... \| tail -2 \|\| true` | 🔴 実害 | git エラーを tail -2 で隠蔽 → T2026-0502-M 原因 |
| session_bootstrap.sh | 39, 361 | `git rev-parse 2>/dev/null \|\| true` | ✅ 無害 | GIT_ROOT 空判定で安全 |
| session_bootstrap.sh | 75, 79, 83, 101 | `mv/mkdir ... 2>/dev/null \|\| true` | ✅ 無害 | FS 失敗も続行可能（salvage）|
| conflict_check.sh | 33 | `git status 2>/dev/null \|\| true` | ✅ 無害 | STATUS_OUTPUT 空判定で安全 |
| cleanup_stale_worktrees.sh | 27, 30, 59 | `git ... 2>/dev/null \|\| true` | ✅ 無害 | worktree パス検出失敗に対応 |
| .github/workflows/*.yml | 多数 | `set +e ... rc=$? ... set -e` | ✅ 無害 | exit code 捕捉の正常用法 |

---

## 推奨アクション

1. **🔴 session_bootstrap.sh 行170-172 を修正**
   - 現在: `git pull 2>&1 | _strip_fuse_noise | tail -2 || true`
   - 修正案: error を tap する（T2026-0502-PIPE-FIX-1）

2. **✅ その他は保留（無害）**

