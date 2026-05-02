#!/usr/bin/env bash
# T2026-0502-COST-DISCIPLINE-PHYSICAL (2026-05-02): workflow_dispatch の物理予算ガード。
#
# Cowork から GitHub Actions workflow を dispatch する唯一の入口。
# 直接 `curl -X POST .../actions/workflows/<wf>/dispatches` するのは pre-commit hook で物理 reject される。
#
# 物理ガード:
#   1. 同一セッション内で同一 workflow を 3 回目以上 dispatch しようとすると exit 1
#   2. 同一 workflow の直近 main 上の N 回が連続失敗していたら exit 1 (再 trigger 無駄打ち防止)
#
# 状態保存先: /tmp/cowork_dispatches.<pid_chain>.tsv (1 行 = ts<TAB>workflow<TAB>result_status)
#   - PID chain で「同一 Cowork セッション」を識別 (Cowork プロセス→bash→このスクリプト)
#   - tmp なので OS 再起動でリセット (セッション境界として十分)
#
# 使い方:
#   bash scripts/gh_workflow_dispatch.sh deploy-lambdas.yml
#   bash scripts/gh_workflow_dispatch.sh deploy-lambdas.yml --ref main      # default は main
#   bash scripts/gh_workflow_dispatch.sh --force deploy-lambdas.yml         # 物理ガードを bypass (緊急のみ・WORKING.md に理由記録必須)
#
# 環境変数:
#   GITHUB_TOKEN      : 必須 (.git/config の url から自動取得 fallback)
#   GITHUB_REPO       : default = nuuuuuuts643/AI-Company
#   COWORK_BUDGET_DIR : default = /tmp (テスト時に上書き可能)

set -euo pipefail

MAX_PER_SESSION=2          # 同一 workflow をこのセッションで何回まで dispatch して良いか
MAX_RECENT_FAILURES=2      # 直近 main 上の連続失敗が何件あったら新規 dispatch を block するか

FORCE=""
WORKFLOW=""
REF="main"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --force)  FORCE=1; shift ;;
        --ref)    REF="$2"; shift 2 ;;
        --help|-h)
            sed -n '2,30p' "$0" >&2
            exit 0
            ;;
        *)        WORKFLOW="$1"; shift ;;
    esac
done

if [[ -z "$WORKFLOW" ]]; then
    echo "usage: $0 [--force] [--ref REF] <workflow_file>" >&2
    exit 2
fi

# token / repo
TOKEN="${GITHUB_TOKEN:-}"
if [[ -z "$TOKEN" ]]; then
    REMOTE_URL="$(git config --get remote.origin.url 2>/dev/null || true)"
    TOKEN="$(printf '%s' "$REMOTE_URL" | grep -oE '(gho_|ghp_|gh[su]_)[A-Za-z0-9_]+' | head -1 || true)"
fi
REPO="${GITHUB_REPO:-nuuuuuuts643/AI-Company}"
if [[ -z "$TOKEN" ]]; then
    echo "ERROR: GITHUB_TOKEN not found (env or .git/config)" >&2
    exit 2
fi

# session id = root of process tree (login shell の PID で代用)
SESSION_ID="$(ps -o ppid= -p $PPID 2>/dev/null | tr -d ' ' || echo $PPID)"
BUDGET_DIR="${COWORK_BUDGET_DIR:-/tmp}"
BUDGET_FILE="$BUDGET_DIR/cowork_dispatches.${SESSION_ID}.tsv"
mkdir -p "$BUDGET_DIR"
touch "$BUDGET_FILE"

# 1) 同一セッションでの dispatch 回数チェック
SESSION_COUNT=$(grep -c -F "	${WORKFLOW}	" "$BUDGET_FILE" 2>/dev/null || echo 0)
SESSION_COUNT="${SESSION_COUNT//[^0-9]/}"
SESSION_COUNT="${SESSION_COUNT:-0}"

if [[ -z "$FORCE" ]] && (( SESSION_COUNT >= MAX_PER_SESSION )); then
    echo "❌ 物理ガード発動: 同一セッションで '${WORKFLOW}' を既に ${SESSION_COUNT} 回 dispatch しています" >&2
    echo "   (T2026-0502-COST-DISCIPLINE-PHYSICAL ルール: max ${MAX_PER_SESSION} 回/セッション)" >&2
    echo "" >&2
    echo "   過去の dispatch 履歴:" >&2
    grep -F "	${WORKFLOW}	" "$BUDGET_FILE" | sed 's/^/     /' >&2
    echo "" >&2
    echo "   対処:" >&2
    echo "   1. logs を gh CLI で取得して原因究明 (Code セッションを起動)" >&2
    echo "   2. TASKS.md に「<workflow> N 回連続 failure・原因不明」エントリーを書く" >&2
    echo "   3. p003-haiku (毎朝 7:08 JST) に観察を委ねて即セッションクローズ" >&2
    echo "" >&2
    echo "   緊急 bypass: bash $0 --force ${WORKFLOW}" >&2
    echo "   (使用時は WORKING.md に理由記録必須)" >&2
    exit 1
fi

# 2) 直近 main 上の連続失敗チェック
RECENT_RUNS=$(curl -fsS -H "Authorization: token $TOKEN" \
    "https://api.github.com/repos/$REPO/actions/workflows/${WORKFLOW}/runs?branch=main&per_page=${MAX_RECENT_FAILURES}" \
    2>/dev/null \
    | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    runs = d.get('workflow_runs', [])
    print(' '.join(str(r.get('conclusion') or 'pending') for r in runs))
except Exception:
    print('')
" || echo "")

# 直近 N 件すべて 'failure' なら block
if [[ -z "$FORCE" ]] && [[ -n "$RECENT_RUNS" ]]; then
    ALL_FAIL=true
    for c in $RECENT_RUNS; do
        if [[ "$c" != "failure" ]]; then
            ALL_FAIL=false
            break
        fi
    done
    if $ALL_FAIL; then
        echo "❌ 物理ガード発動: '${WORKFLOW}' の直近 ${MAX_RECENT_FAILURES} 回が連続失敗" >&2
        echo "   (results: $RECENT_RUNS)" >&2
        echo "   再 dispatch しても同じ理由で失敗する可能性が高い → 原因究明が先" >&2
        echo "" >&2
        echo "   対処: gh run view <RUN_ID> --log-failed で logs を取得 (Code セッション)" >&2
        echo "   緊急 bypass: bash $0 --force ${WORKFLOW}" >&2
        exit 1
    fi
fi

# 3) 実際に dispatch
echo "→ dispatch ${WORKFLOW} ref=${REF} (session count: $((SESSION_COUNT + 1))/${MAX_PER_SESSION})"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    -H "Authorization: token $TOKEN" \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/$REPO/actions/workflows/${WORKFLOW}/dispatches" \
    -d "{\"ref\":\"${REF}\"}")

if [[ "$HTTP_CODE" != "204" ]]; then
    echo "❌ dispatch failed: HTTP $HTTP_CODE" >&2
    exit 1
fi

# 履歴記録
TS=$(date +%s)
printf '%s\t%s\t%s\n' "$TS" "$WORKFLOW" "dispatched" >> "$BUDGET_FILE"
echo "✓ dispatched. budget file: $BUDGET_FILE"
echo "  ⚠️ 結果は次セッション or schedule task (p003-haiku 朝7:08) で確認すること。"
echo "     polling (sleep && curl) は物理 reject されます (T2026-0502-COST-DISCIPLINE-PHYSICAL)。"
