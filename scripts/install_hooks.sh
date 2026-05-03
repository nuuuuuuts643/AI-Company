#!/bin/bash
# Install local git hooks so that "守らないと次に進めない仕組み" applies even before push.
# Run once per clone:  bash scripts/install_hooks.sh
#
# What it installs:
#   .git/hooks/pre-commit   →  runs scripts/check_section_sync.sh
#                              blocks the commit if old 4-section / old phase wording survives.
#
# Idempotent: running twice is fine.

set -e
cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"
HOOK_DIR="$REPO_ROOT/.git/hooks"

mkdir -p "$HOOK_DIR"

cat > "$HOOK_DIR/pre-commit" <<'HOOK'
#!/bin/bash
# AUTO-INSTALLED by scripts/install_hooks.sh
# Blocks commits that re-introduce drift in P003 thought-framework wording,
# missing AdSense ads.txt pub-id, or missing Verified: line on feat/fix/perf.

REPO_ROOT="$(git rev-parse --show-toplevel)"
SCRIPT="$REPO_ROOT/scripts/check_section_sync.sh"

if [ -x "$SCRIPT" ]; then
  echo "[pre-commit] running check_section_sync.sh ..."
  if ! bash "$SCRIPT" >/tmp/section_sync.$$.log 2>&1; then
    echo "❌ pre-commit blocked: section-sync drift detected"
    cat /tmp/section_sync.$$.log
    rm -f /tmp/section_sync.$$.log
    echo ""
    echo "Fix the wording above then retry. (To bypass in real emergency only:  git commit --no-verify)"
    exit 1
  fi
  rm -f /tmp/section_sync.$$.log
fi

# Also block obvious AdSense ads.txt regression: pub-id appears in index.html
# but NOT in ads.txt. (Mirrors the なぜなぜ from CLAUDE.md ads.txt 事件)
INDEX="$REPO_ROOT/projects/P003-news-timeline/frontend/index.html"
ADS="$REPO_ROOT/projects/P003-news-timeline/frontend/ads.txt"
if [ -f "$INDEX" ] && [ -f "$ADS" ]; then
  PUB=$(grep -oE 'ca-pub-[0-9]+' "$INDEX" | head -1 | sed 's/ca-//')
  if [ -n "$PUB" ]; then
    if ! grep -q "$PUB" "$ADS"; then
      echo "❌ pre-commit blocked: AdSense $PUB is referenced in index.html but missing from ads.txt"
      echo "   Add this line to ads.txt:"
      echo "   google.com, $PUB, DIRECT, f08c47fec0942fa0"
      exit 1
    fi
  fi
fi

# T2026-0502-PII-PRECOMMIT: PII (PO username/email) 直書き検知 (pre-commit 物理ガード)
# 背景: T2026-0502-PII-leak (PR #194) で docs/lessons-learned.md L1074/L1093 に PO のメールアドレスが
#       直書きされ、main マージ後に CI の PII 検査 step が連続 failure。pre-commit で止めれば
#       commit 段階で阻止できた。CLAUDE.md「PII / secrets コード直書き禁止」物理ルールの完全物理化。
# パターン: ci.yml の PII 検査 step (`grep -lE "m[u]rakaminaoya|mr[k]m\.naoya|n[a]oya643"`) と同一。
# 例外: scripts/security_audit.sh / done.sh / .github/workflows/ci.yml / .git/hooks/pre-commit (本ファイル)
PII_HITS=$(git diff --cached --name-only --diff-filter=ACMR \
  | xargs -I{} sh -c 'grep -lE "m[u]rakaminaoya|mr[k]m\.naoya|n[a]oya643" "{}" 2>/dev/null' 2>/dev/null \
  | grep -v "^scripts/security_audit\.sh$" \
  | grep -v "^done\.sh$" \
  | grep -v "^\.github/workflows/ci\.yml$" \
  | grep -v "^\.git/hooks/pre-commit$" \
  | grep -v "^scripts/install_hooks\.sh$" \
  || true)
if [ -n "$PII_HITS" ]; then
  echo "❌ pre-commit blocked: PII (owner username/email) を含むファイルが staged されています"
  echo "$PII_HITS" | sed 's/^/   /'
  echo ""
  echo "   ci.yml の PII 検査 step と同じルールを pre-commit で先取りブロックしています。"
  echo "   対処: 該当箇所を <owner-email> / <owner-handle> プレースホルダーに置換してから commit"
  echo "   詳細: docs/lessons-learned.md「T2026-0502-PII-leak」セクション (PR #194)"
  echo ""
  echo "   緊急時 bypass: git commit --no-verify (使用時は WORKING.md に理由記録必須)"
  exit 1
fi

# T2026-0502-SEC-AUDIT (2026-05-02): Secret pattern scanner (pre-commit)
# 物理ガード: ghp_/gho_/xoxb-/sk-ant-/ntn_/Slack Webhook 等の live secret が
# staged された時点で commit を block する。CI secret-scan.yml と同パターン。
SCAN_SCRIPT="$REPO_ROOT/scripts/secret_scan.sh"
if [ -x "$SCAN_SCRIPT" ]; then
  if ! bash "$SCAN_SCRIPT" staged >/tmp/secret_scan.$$.log 2>&1; then
    echo "❌ pre-commit blocked: secret pattern detected in staged changes"
    cat /tmp/secret_scan.$$.log
    rm -f /tmp/secret_scan.$$.log
    echo ""
    echo "緊急時 bypass: git commit --no-verify"
    echo "   ただし bypass 時は WORKING.md に理由記録必須 (CLAUDE.md 物理ルール)"
    exit 1
  fi
  rm -f /tmp/secret_scan.$$.log
fi

# T2026-0502-COST-DISCIPLINE-PHYSICAL (2026-05-02): コスト規律の物理化
# 物理ガード: コードに以下のアンチパターンが入っている場合 commit を block する。
# 1. workflow_dispatch を curl で直接叩く (scripts/gh_workflow_dispatch.sh wrapper を使うこと)
# 2. sleep N && curl / aws polling パターン (1 回確認 + schedule タスク委ね原則)
# 3. for i in {1..N}; do curl/aws ... done パターン
COST_HITS=$(git diff --cached --no-color -U0 \
    | grep -E '^\+' \
    | grep -vE '^\+\+\+' \
    | grep -vE 'gh_workflow_dispatch\.sh|cost.*-discipline|COST-DISCIPLINE|install_hooks\.sh|test.*pattern|test.*aspect' \
    | grep -E '(curl[^|&;]*-X[ ]*POST[^|&;]*actions/workflows/[^/]+/dispatches|sleep[ ]+[0-9]+[ ]*&&[ ]*curl|sleep[ ]+[0-9]+[ ]*;[ ]*curl|sleep[ ]+[0-9]+[ ]*&&[ ]*aws[ ]+lambda|for[ ]+[a-zA-Z_]+[ ]+in[ ]+[\\{`].*do[ ]+(curl|aws[ ]))' \
    || true)
if [ -n "$COST_HITS" ]; then
    echo "❌ pre-commit blocked: cost-discipline anti-pattern が staged されています (T2026-0502-COST-DISCIPLINE-PHYSICAL)"
    echo "$COST_HITS" | head -10 | sed 's/^/   /'
    echo ""
    echo "   検出パターン (CLAUDE.md コスト規律ルール参照):"
    echo "   ① curl で workflow_dispatch を直接叩く → bash scripts/gh_workflow_dispatch.sh <wf> を使うこと"
    echo "   ② sleep N && curl / aws polling → 1 回確認 + schedule (p003-haiku) 委ね"
    echo "   ③ for ループで curl/aws 連投 → 同上"
    echo ""
    echo "   緊急 bypass (テスト等): git commit --no-verify"
    echo "   (使用時は WORKING.md に理由記録必須)"
    exit 1
fi

# T2026-0502-IAM-DRIFT-FIX2 (初版 c521a846・file-path 修正 T2026-0502-IAM-FILTER-FIX 2026-05-02):
# IAM apply は infra/iam/apply.sh 経由必須。直接 `aws iam put-role-policy` /
# `put-user-policy` / `put-group-policy` を呼ぶスクリプトや workflow YAML を
# staged に追加することを物理 reject。
#
# 例外 (file-path ベース・誤検知防止):
#   - infra/iam/apply.sh 自体 (唯一の正しい IAM apply 経路)
#   - scripts/install_hooks.sh 自体 (本 hook の source)
#   - *.md 全般 (ドキュメント内のルール説明引用)
#   - tests/ 配下 (回帰テスト fixture)
#   - .git/hooks/ (インストール先 hook 自体に regex 文字列が入る)
#
# 旧実装 (c521a846) は git diff の "+ 行内容" に対して exemption regex を
# 当てていたため、*.md / lessons-learned.md 内のドキュメント文字列まで
# 誤検知して bypass を強いる構造だった。本実装は --name-only でファイル単位に
# exempt 判定する。回帰テスト: tests/test_pre_commit_iam_filter.sh
IAM_EXEMPT_PATH_RE='^infra/iam/apply\.sh$|^scripts/install_hooks\.sh$|\.md$|^tests?/|/tests?/|(^|/)test_[^/]+\.(py|sh|js|ts|yml|yaml)$|(^|/)test\.(py|sh|js|ts)$|^\.git/hooks/'
IAM_HITS=""
while IFS= read -r _iam_f; do
    [ -z "$_iam_f" ] && continue
    [ -f "$_iam_f" ] || continue
    if echo "$_iam_f" | grep -qE "$IAM_EXEMPT_PATH_RE"; then
        continue
    fi
    _iam_file_hits=$(git diff --cached --no-color -U0 -- "$_iam_f" \
        | grep -E '^\+[^+]' \
        | grep -E '(aws[ ]+iam[ ]+put-role-policy|aws[ ]+iam[ ]+put-user-policy|aws[ ]+iam[ ]+put-group-policy)' \
        || true)
    if [ -n "$_iam_file_hits" ]; then
        IAM_HITS="${IAM_HITS}--- ${_iam_f} ---"$'\n'"${_iam_file_hits}"$'\n'
    fi
done < <(git diff --cached --name-only --diff-filter=AM)
if [ -n "$IAM_HITS" ]; then
    echo "❌ pre-commit blocked: 直接 \`aws iam put-*-policy\` 呼び出しは禁止 (T2026-0502-IAM-DRIFT-FIX2)"
    printf '%s' "$IAM_HITS" | head -20 | sed 's/^/   /'
    echo ""
    echo "   IAM 変更は infra/iam/apply.sh 経由必須:"
    echo "   1. infra/iam/policies/<name>.json を編集 (git tracked source of truth)"
    echo "   2. PR で diff review"
    echo "   3. merge 後 bash infra/iam/apply.sh で同期 (post-apply 自己検証込み)"
    echo "   詳細: docs/runbooks/iam-policy-management.md"
    echo ""
    echo "   緊急 bypass: git commit --no-verify (要 WORKING.md 理由記録)"
    exit 1
fi

# T2026-0503-D (2026-05-03): CLAUDE.md 250行以内ガード (pre-commit 物理化)
# 背景: PR #339 で CLAUDE.md が 252 行になり CI の「メタドキュメント物理ガード」が failure。
#       CLAUDE.md「250 行以内」ルールを commit 時点で先取り block して CI failure を防ぐ。
if git diff --cached --name-only | grep -q "^CLAUDE\.md$"; then
    CLAUDE_LINES=$(git show :CLAUDE.md 2>/dev/null | wc -l | tr -d ' ')
    if [ -n "$CLAUDE_LINES" ] && [ "$CLAUDE_LINES" -gt 250 ]; then
        echo "❌ pre-commit blocked: CLAUDE.md が ${CLAUDE_LINES} 行あります (上限 250 行)"
        echo ""
        echo "   超過分を docs/rules/ 配下に外出しして 250 行以内に収めてください。"
        echo "   CLAUDE.md「250 行以内」ルール: CI meta-doc-guard と同じ条件 (T2026-0503-D)"
        echo ""
        echo "   緊急 bypass: git commit --no-verify (要 WORKING.md 記録)"
        exit 1
    fi
fi

exit 0
HOOK

# ---- commit-msg hook: Verified: 行を必須化 (feat/fix/perf プレフィックスのみ) ----
cat > "$HOOK_DIR/commit-msg" <<'MSGHOOK'
#!/bin/bash
# AUTO-INSTALLED by scripts/install_hooks.sh
# Requires `Verified: <url>:<status>:<JST_timestamp>` line in commit message
# when the commit is a feat:/fix:/perf: change.
# Skips: wip:, docs:, chore:, test:, refactor:, style:, build:, ci:, revert:

MSG_FILE="$1"
[ -z "$MSG_FILE" ] && exit 0
[ ! -f "$MSG_FILE" ] && exit 0

FIRST_LINE=$(grep -v '^#' "$MSG_FILE" | head -n 1)

# ---- (A) schedule-task commit: [Schedule-KPI] 行を必須化（プレフィックスに依らず先に判定）----
# commit message 全文に "schedule-task" (case-insensitive) が含まれる場合、
# `[Schedule-KPI] implemented=N created=M closed=K queue_delta=±X` を含めること。
# bootstrap の sync commit (`chore: bootstrap sync ...`) には schedule-task 文言が無いため誤発火しない。
# 「発見偏重 anti-pattern」を物理ガード化（lessons-learned 2026-04-28 由来）。
if grep -qiE 'schedule-task' "$MSG_FILE"; then
  if ! grep -qE '^\[Schedule-KPI\] implemented=[0-9]+ created=[0-9]+ closed=[0-9]+ queue_delta=[+-]?[0-9]+' "$MSG_FILE"; then
    echo "❌ commit-msg blocked: schedule-task commit には [Schedule-KPI] 行が必須です。"
    echo "   format: [Schedule-KPI] implemented=N created=M closed=K queue_delta=±X"
    echo "   例   : [Schedule-KPI] implemented=2 created=1 closed=3 queue_delta=-1"
    echo "   理由  : docs/lessons-learned.md 2026-04-28「scheduled-task が発見偏重」対策"
    echo "   bypass (緊急のみ): git commit --no-verify"
    exit 1
  fi
fi

# ---- (B) Verified 行（feat:/fix:/perf: のみ強制） ----
# skip non-verify-required prefixes (case-insensitive)
SKIP_RE='^[[:space:]]*(wip|docs|chore|test|refactor|style|build|ci|revert):'
if echo "$FIRST_LINE" | grep -qiE "$SKIP_RE"; then
  exit 0
fi

# require Verified for feat/fix/perf
REQUIRE_RE='^[[:space:]]*(feat|fix|perf):'
if ! echo "$FIRST_LINE" | grep -qiE "$REQUIRE_RE"; then
  # その他のプレフィックスは現状チェックしない（過去 commit 互換のため）
  exit 0
fi

if ! grep -qE '^Verified: ' "$MSG_FILE"; then
  echo "❌ commit-msg blocked: '$FIRST_LINE' requires a 'Verified:' line."
  echo "   format: Verified: <url>:<http_status>:<JST_timestamp>"
  echo "   helper: bash scripts/verified_line.sh <url>"
  echo "   skip prefixes: wip docs chore test refactor style build ci revert"
  echo "   bypass (emergency only): git commit --no-verify"
  exit 1
fi

# 2xx でなければ警告のみ（commit は通す）
if ! grep -qE '^Verified: .*:2[0-9]{2}:' "$MSG_FILE"; then
  echo "⚠️  Verified line found but HTTP status is not 2xx. Continuing — please double-check."
fi

# ---- (C) Verified-Effect 行（feat:/fix:/perf: で必須・T2026-0502-AA で物理化）----
# 「完了 = 動作確認済み + 効果検証済み」(CLAUDE.md) を物理ガード化。
# Verified: は「動作確認 (URL HTTP 200)」を保証するが、効果 (SLI 改善) は別軸。
# Cowork が「PR 出した時点で完了」と誤認するパターンが 2026-05-02 一日で 4 回発生 (T2026-0502-COST/U/W/Y)。
#
# 必須:
#   `Verified-Effect: <SLI 説明> <before>→<after> (<source>:<JST_timestamp>)` か
#   `Verified-Effect-Skip: <理由>` (例: \"build artifact only\" \"test fixture\" \"lint fix\") のどちらか。
# Verified-Effect-Skip は理由を明示することで「あえて効果検証しない」判断を可視化する。
# 効果検証が時間遅延 (deploy 後 N 時間後) の場合は `Verified-Effect-Pending: <Eval-Due日付>` も可。
if ! grep -qE '^Verified-Effect(-Skip|-Pending)?: ' "$MSG_FILE"; then
  echo "❌ commit-msg blocked: '$FIRST_LINE' requires one of:"
  echo "   - Verified-Effect: <SLI metric> <before>→<after> (<source>:<JST>)"
  echo "       (例: Verified-Effect: fetcher Haiku call 1100/run→0/run (CloudWatch:2026-05-02 14:08))"
  echo "   - Verified-Effect-Skip: <reason>"
  echo "       (例: Verified-Effect-Skip: build artifact only / test fixture / lint fix)"
  echo "   - Verified-Effect-Pending: <Eval-Due日付>"
  echo "       (例: Verified-Effect-Pending: 2026-05-09 effect_check_after_deploy)"
  echo ""
  echo "   理由: CLAUDE.md「完了=動作確認済+効果検証済」物理化 (T2026-0502-AA)"
  echo "         2026-05-02 に Cowork が「PR 出した=完了」誤認を 4 回繰り返した対策"
  echo "   bypass (emergency only): git commit --no-verify"
  exit 1
fi

exit 0
MSGHOOK

cat > "$HOOK_DIR/pre-push" <<'PUSHOOK'
#!/bin/bash
# AUTO-INSTALLED by scripts/install_hooks.sh
# T2026-0502-PHYSICAL-GUARD-AUDIT: main 直 push を物理 reject
# (PR #160 で「pre-push hook で物理ブロック ✅」と記録されていたが、
#  実装は exit 0 placeholder のままだった。今回ようやく実装。)
#
# 例外: ALLOW_MAIN_PUSH=1 環境変数が立っており、push される全 commit が
#       `chore: bootstrap sync` で始まる場合のみ allow
#       (session_bootstrap.sh の sync push 用 escape)
# bypass (緊急のみ): git push --no-verify

# stdin: <local_ref> <local_sha> <remote_ref> <remote_sha> per push ref
ZERO="0000000000000000000000000000000000000000"
while read local_ref local_sha remote_ref remote_sha; do
  # main 以外への push は素通し
  [ "$remote_ref" = "refs/heads/main" ] || continue
  # branch 削除 (local_sha が all zeros) は素通し
  [ "$local_sha" = "$ZERO" ] && continue

  if [ "${ALLOW_MAIN_PUSH:-0}" = "1" ]; then
    # ALLOW_MAIN_PUSH escape は「全 commit が chore: bootstrap sync」の AND 条件
    if [ "$remote_sha" = "$ZERO" ]; then
      RANGE="${local_sha}~1..${local_sha}"
    else
      RANGE="${remote_sha}..${local_sha}"
    fi
    NON_BOOTSTRAP=$(git log --format='%s' "$RANGE" 2>/dev/null \
      | grep -vE '^chore:[[:space:]]*bootstrap sync' | head -3 || true)
    if [ -z "$NON_BOOTSTRAP" ]; then
      continue
    fi
    echo "❌ pre-push blocked: ALLOW_MAIN_PUSH=1 でも 'chore: bootstrap sync' 以外の commit が含まれます" >&2
    echo "$NON_BOOTSTRAP" | sed 's/^/   /' >&2
    echo "   実コード変更は必ず branch + PR 経由 (cowork_commit.py / gh pr create)" >&2
    echo "   緊急 bypass: git push --no-verify (要 WORKING.md 記録 + Verified-Effect:)" >&2
    exit 1
  fi

  echo "❌ pre-push blocked: main への直接 push は禁止です (T2026-0502-M / -PHYSICAL-GUARD-AUDIT)" >&2
  echo "   実コード変更は branch + PR 経由で行ってください:" >&2
  echo "     - python3 scripts/cowork_commit.py --branch <name> --pr-title <title> ..." >&2
  echo "     - もしくは git checkout -b <branch> && git push origin <branch> + gh pr create" >&2
  echo "   bootstrap sync の場合: ALLOW_MAIN_PUSH=1 git push (session_bootstrap.sh が自動で付与)" >&2
  echo "   緊急時 bypass: git push --no-verify" >&2
  echo "     (使用時は WORKING.md に理由 + Verified-Effect: 行を必ず記録)" >&2
  exit 1
done

exit 0
PUSHOOK

chmod +x "$HOOK_DIR/pre-commit" "$HOOK_DIR/commit-msg" "$HOOK_DIR/pre-push"

echo "✅ installed: $HOOK_DIR/pre-commit"
echo "✅ installed: $HOOK_DIR/commit-msg"
echo "✅ installed: $HOOK_DIR/pre-push"
echo ""
echo "From now on, commits/pushes in this clone will fail if:"
echo "  - 旧4セクション / 旧フェーズ表記が混入したとき"
echo "  - index.html の AdSense pub-id が ads.txt に無いとき"
echo "  - feat:/fix:/perf: prefix の commit に 'Verified: <url>:<status>:<JST>' 行が無いとき"
echo "  - feat:/fix:/perf: prefix の commit に 'Verified-Effect:' 系の行が無いとき (T2026-0502-AA)"
echo "  - schedule-task を含む commit に '[Schedule-KPI] implemented=...' 行が無いとき"
echo "  - PII / live secret / cost-discipline anti-pattern が staged されたとき"
echo "  - main へ直接 push しようとしたとき (T2026-0502-PHYSICAL-GUARD-AUDIT で実装。bootstrap sync は ALLOW_MAIN_PUSH=1 で escape)"
echo ""
echo "Bypass (real emergency only):  git commit --no-verify  /  git push --no-verify"
