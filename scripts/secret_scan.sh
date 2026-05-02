#!/usr/bin/env bash
# T2026-0502-SEC-AUDIT (2026-05-02): Secret pattern scanner
# 用途:
#   bash scripts/secret_scan.sh staged   ... pre-commit hook 用 (`git diff --cached` のみ)
#   bash scripts/secret_scan.sh head     ... CI push 時 (current HEAD のみ)
#   bash scripts/secret_scan.sh full     ... CI 週次 + 監査 (git history 全件)
#
# 検出パターン:
#   - GitHub PAT (ghp_*, gho_*, ghs_*, ghr_*) — classic + fine-grained
#   - Slack Bot/User/App tokens (xoxb-, xoxp-, xapp-, xoxe-)
#   - Slack Incoming Webhook (hooks.slack.com/services/...)
#   - Anthropic API key (sk-ant-api03-*)
#   - OpenAI legacy key (sk-proj-*, sk-* with 40+ chars)
#   - Notion integration token (ntn_*, secret_* with 40+ chars)
#   - AWS access key id (AKIA*) / secret access key heuristic
#   - Generic high-entropy bearer token in URL (https://user:token@host)
#
# Allowlist: scripts/secret_scan_allowlist.txt
#   (false positive が起きたら、コミットハッシュ + パターン1行 1パターンで追加する)

set -euo pipefail

MODE="${1:-head}"

# 検出パターン (extended regex)。ヒットしたら fail させたい全パターンを 1 ずつ列挙。
PATTERNS=(
    'ghp_[A-Za-z0-9]{36}'                                # GitHub Personal Access Token (classic)
    'gho_[A-Za-z0-9]{36}'                                # GitHub OAuth Token
    'ghs_[A-Za-z0-9]{36}'                                # GitHub App user-to-server
    'ghr_[A-Za-z0-9]{36}'                                # GitHub App refresh token
    'github_pat_[A-Za-z0-9_]{82,}'                       # Fine-grained PAT (82-94 chars)
    'xox[baprso]-[0-9]+-[0-9]+-[A-Za-z0-9-]+'            # Slack Bot/User/Refresh tokens
    'xoxe\.[A-Za-z0-9_-]+'                               # Slack rotated token
    'hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]+'  # Slack Incoming Webhook
    'sk-ant-api03-[A-Za-z0-9_-]{20,}'                    # Anthropic API key
    'sk-proj-[A-Za-z0-9_-]{20,}'                         # OpenAI project key
    'ntn_[A-Za-z0-9]{40,}'                               # Notion integration token
    'secret_[A-Za-z0-9]{40,}'                            # Notion (legacy)
    'AKIA[0-9A-Z]{16}'                                   # AWS Access Key ID
    'https://[A-Za-z0-9._-]+:[A-Za-z0-9._%-]{20,}@'      # creds embedded in URL
)

ALLOWLIST_FILE="$(dirname "$0")/secret_scan_allowlist.txt"

# 検出: 1 行 = "<pattern>:<file>:<line>:<context>"
hits=""
add_hit() {
    local p="$1" line="$2"
    if [[ -f "$ALLOWLIST_FILE" ]]; then
        # allowlist の各 entry を hit line の中で substring 検索する
        # (allowlist の方が短い substring。hit line の方が長い context 込み)
        while IFS= read -r entry; do
            # 空行 / コメント (#) はスキップ
            [[ -z "$entry" ]] && continue
            [[ "$entry" =~ ^[[:space:]]*# ]] && continue
            # 固定文字列で hit line 内検索
            if printf '%s' "$line" | grep -F -q -- "$entry" 2>/dev/null; then
                return 0
            fi
        done < "$ALLOWLIST_FILE"
    fi
    hits="${hits}${p}::${line}"$'\n'
}

scan_text() {
    local text="$1"
    for p in "${PATTERNS[@]}"; do
        # rg のかわりに egrep (CI ubuntu に標準)。ヒット行を集める。
        local found
        found=$(printf '%s' "$text" | grep -nE "$p" || true)
        if [[ -n "$found" ]]; then
            while IFS= read -r line; do
                add_hit "$p" "$line"
            done <<<"$found"
        fi
    done
}

case "$MODE" in
    staged)
        # pre-commit: index にあるファイルの diff のみ
        diff_text=$(git diff --cached --no-color -U0 || true)
        scan_text "$diff_text"
        ;;
    head)
        # CI push: tracked files only (current HEAD)
        # node_modules / .git / dist / build を除外。fast scan。
        # T2026-0502-AC-SCANNER-FALSE-POSITIVE: ドキュメント (TASKS.md / HISTORY.md /
        # docs/lessons-learned.md / docs/rules/**) は事象記述・例文置き場として scanner 対象外。
        # 個別 secret は CLAUDE.md / project rules で「ドキュメントに本物 token を書かない」と
        # 規定済 (思想ルール) — scanner はあくまで実コード経路の物理ガード。
        files_text=""
        while IFS= read -r f; do
            case "$f" in
                TASKS.md|HISTORY.md|docs/lessons-learned.md|docs/rules/*) continue ;;
            esac
            if [[ -f "$f" ]] && [[ "$(file -b --mime "$f" 2>/dev/null)" != *"binary"* ]]; then
                files_text+="$(printf '\n=== %s ===\n' "$f"; head -c 1000000 "$f" 2>/dev/null || true)"
            fi
        done < <(git ls-files | grep -vE '^(node_modules|\.git|dist|build|\.claude/worktrees)/')
        scan_text "$files_text"
        ;;
    full)
        # 週次 / 監査: git history 全件 (object database 全 walk)
        # 注意: 大規模リポでは重い。公開鍵 / lock file 等の noise が出やすい。
        history_text=$(git log --all -p --no-color 2>/dev/null || true)
        scan_text "$history_text"
        # current HEAD も追加で見る (history に未 push の場合の保険)
        bash "$0" head
        ;;
    *)
        echo "Usage: $0 {staged|head|full}" >&2
        exit 2
        ;;
esac

if [[ -n "$hits" ]]; then
    echo "❌ Secret pattern detected:" >&2
    echo "$hits" | head -50 >&2
    echo "" >&2
    echo "対処:" >&2
    echo "  1. 検出された secret を即 Revoke (GitHub Settings / Slack / Anthropic / Notion 等)" >&2
    echo "  2. ファイルから値を削除し env 変数経由に変更" >&2
    echo "  3. (必要なら) git filter-repo で history から消す" >&2
    echo "  4. False positive の場合は scripts/secret_scan_allowlist.txt に substring を追加" >&2
    exit 1
fi

echo "✅ secret_scan ($MODE): no secrets detected"
