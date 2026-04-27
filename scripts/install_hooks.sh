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
# Blocks commits that re-introduce drift in P003 thought-framework wording.

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

chmod +x "$HOOK_DIR/pre-commit"

echo "✅ installed: $HOOK_DIR/pre-commit"
echo ""
echo "From now on, commits in this clone will fail if:"
echo "  - 旧4セクション / 旧フェーズ表記が混入したとき"
echo "  - index.html の AdSense pub-id が ads.txt に無いとき"
echo ""
echo "Bypass (real emergency only):  git commit --no-verify"
