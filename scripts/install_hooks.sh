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

exit 0
MSGHOOK

cat > "$HOOK_DIR/pre-push" <<'PUSHOOK'
#!/bin/bash
# AUTO-INSTALLED by scripts/install_hooks.sh
# PR #160: pre-push hook setup block
# Placeholder for pre-push validations; currently allows all pushes.
exit 0
PUSHOOK

chmod +x "$HOOK_DIR/pre-commit" "$HOOK_DIR/commit-msg" "$HOOK_DIR/pre-push"

echo "✅ installed: $HOOK_DIR/pre-commit"
echo "✅ installed: $HOOK_DIR/commit-msg"
echo "✅ installed: $HOOK_DIR/pre-push"
echo ""
echo "From now on, commits in this clone will fail if:"
echo "  - 旧4セクション / 旧フェーズ表記が混入したとき"
echo "  - index.html の AdSense pub-id が ads.txt に無いとき"
echo "  - feat:/fix:/perf: prefix の commit に 'Verified: <url>:<status>:<JST>' 行が無いとき"
echo "  - schedule-task を含む commit に '[Schedule-KPI] implemented=...' 行が無いとき"
echo ""
echo "Bypass (real emergency only):  git commit --no-verify"
