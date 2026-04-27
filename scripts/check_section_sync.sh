#!/bin/bash
# AI セクション説明の不一致を検出するスクリプト
# 使い方: bash scripts/check_section_sync.sh
# 旧表現が残っていたら警告。CI に組み込み or 手動 invoke 想定。

set -e
cd "$(dirname "$0")/.."

ROOT=projects/P003-news-timeline
ERRORS=0

echo "==[check_section_sync] 旧4セクション表現の残存検出==="

# 旧表現パターン (実装が7セクションに移行後も残ってたら警告)
OLD_PATTERNS=(
  "①何が起きたか.*②なぜ広がったか"
  "4セクション構成"
  "4セクション分析"
  "4視点で分析"
  "4つの視点で分析"
)

for pat in "${OLD_PATTERNS[@]}"; do
  HITS=$(grep -rEn "$pat" "$ROOT/frontend" "$ROOT/lambda" 2>/dev/null | grep -v "_garbage\|.pyc\|node_modules" || true)
  if [ -n "$HITS" ]; then
    echo "❌ 旧表現発見: $pat"
    echo "$HITS" | sed 's/^/   /'
    ERRORS=$((ERRORS+1))
  fi
done

echo ""
echo "==旧フェーズ表現の検出 (発端/拡散/ピーク/現在地/収束 → 始まり/広まってる/急上昇/進行中/ひと段落 移行漏れ)==="
# T187 で UIフェーズ名を新表記化したが、ドキュメント残存があれば警告
DOC_OLD_PHASE=$(grep -rEn "発端→拡散→ピーク→現在地→収束" "$ROOT/frontend" 2>/dev/null | grep -v "_garbage\|.pyc" | grep -v "phase 判定\|valid_phases\|phase.*=" || true)
if [ -n "$DOC_OLD_PHASE" ]; then
  echo "⚠️ ドキュメント側に旧フェーズ表記が残ってる可能性:"
  echo "$DOC_OLD_PHASE" | sed 's/^/   /'
fi

echo ""
if [ "$ERRORS" -eq 0 ]; then
  echo "✅ AI セクション説明の同期 OK"
  exit 0
else
  echo "❌ $ERRORS 種類の旧表現が残存。about.html / FAQ / 関連箇所を更新してください。"
  exit 1
fi
