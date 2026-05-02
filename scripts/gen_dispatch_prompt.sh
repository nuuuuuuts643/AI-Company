#!/bin/bash
# gen_dispatch_prompt.sh — Dispatch セッション起動プロンプトを自動生成する
# 使い方: bash scripts/gen_dispatch_prompt.sh | pbcopy  (Mac でクリップボードにコピー)
# または:  bash scripts/gen_dispatch_prompt.sh          (標準出力に表示)
#
# 「仕組み」: WORKING.md の Dispatch継続性・TASKS.md の未着手高優先タスクを
#  自動で埋め込み、毎回コピペで使えるプロンプトを生成する。
#  ルールが変わったり完了条件が変わっても、このスクリプトを更新すれば全セッションに反映される。

set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"

# --- Dispatch継続性セクションを抽出 ---
dispatch_section=""
if [ -f "$REPO/WORKING.md" ]; then
  dispatch_section=$(awk '/## 🟢 Dispatch 継続性/,/^---/' "$REPO/WORKING.md" \
    | grep -v "^---" | grep -v "^## 🟢" | grep -v "^>" | sed '/^$/d' | head -10)
fi

# --- TASKS.md から未着手の高・中優先タスクを抽出（🔴/🟡 のみ、先頭3件）---
priority_tasks=""
if [ -f "$REPO/TASKS.md" ]; then
  priority_tasks=$(grep -E "^\| T[0-9]|^\| ~~T" "$REPO/TASKS.md" \
    | grep -v "~~T" \
    | grep -E "🔴|🟡" \
    | head -3 \
    | sed 's/|/│/g' \
    | awk -F'│' '{printf "  - %s: %s\n", $2, $4}' \
    | sed 's/  */ /g')
fi

# --- JST 現在時刻 ---
jst=$(TZ='Asia/Tokyo' date '+%Y-%m-%d %H:%M JST')

# --- プロンプト生成 ---
# heredoc は `<< 'PROMPT'` (シングルクォート) で囲み、bash の variable expansion / glob 展開を物理停止。
# 中身の `*` `update-function-code` `lambda/handler.py` などを bash が解釈する事故を防ぐ (2026-05-02 PR #X 修正)。
cat << 'PROMPT'
P003 自走セッション (Cowork Dispatch / scheduled / 手動コピペ問わず共通)。

⚠️ あなたは「タスクを実装するだけのプログラマー」ではない。
   仕組みを足すこと自体は成果ではない。**ユーザー被害が解消することが成果**。
   「PR が merge された」=「効果が出た」と勘違いしない (違反 #17 = 実装→評価→次が口だけ)。
   提案書 docs/rules-rewrite-proposal-2026-05-01.md Section 14「組織として動く Claude」の精神で動く。

## STEP 1: 現状把握 (実装着手前必須・思考停止しない)
1.1 bash scripts/session_bootstrap.sh
1.2 docs/north-star.md と docs/current-phase.md を全文読む
1.3 WORKING.md Dispatch継続性 を読む (本プロンプト末尾の「現在の状態」と整合性確認)
1.4 SLI 実測 (curl/gh / 数値で記録):
    - topics.json 鮮度 (閾値 90 分)
    - keyPoint >= 100字 充填率 (target 70%)
    - 鮮度モニタ + fetcher-health-check 直近 run 状態
    - current-phase.md 完了条件との進捗
1.5 並走チェック: WORKING.md「現在着手中」テーブルに [Code] or 別 [Cowork] あれば即終了 (K-1 物理回避)

## STEP 2: 問題特定と効果仮説 (実装着手前必須・WORKING.md に書き出す)
- 何が悪化 / 改善停滞しているか
- ユーザー被害が発生中なら何か (鮮度 stale / keyPoint 空 等)
- 提案書 Section 1 の違反パターン #1〜#28 のいずれが発火しているか
- これは「仕組み側の課題」か「プロダクト側 (Lambda/CloudWatch) の課題」か
- 仮説: このタスクを実装したら何が改善するか (想定 Verified-Effect)

## STEP 3: タスク選択 (考えてから選ぶ)
- 第一候補: WORKING.md「次セッションでやること」最優先 1 件
- ただし STEP 2 の仮説と矛盾する (=ユーザー被害解消に直結しない) なら、別タスクを選ぶ理由を書く
- **自分の権限で対処可能か AWS MCP で確認**:
  - 障害調査 / 効果検証 / 運用設定確認 → **Cowork が AWS MCP で完結** (Eng 起動不要)
  - Lambda コード修正 (`lambda/handler.py` 等のソース改変) → Eng Claude 起動が必要 → 「Pending-Eng エスカレーション」で TASKS.md 起票して止める
  - 不可逆操作 (`update-function-code` / `delete-*` / 新規 AWS 課金リソース) → PO 確認必須・着手前に止める

## STEP 4: 実装 (1 セッション 1 タスク厳守)
- PR 経由必須・main 直 push 禁止 (cowork_commit.py が物理 reject)
- commit-msg 必須行: Phase-Impact / Approach + Why / Fix-Type / Verified / Eval-Due
- auto-merge.yml が CI green で自動 squash merge

## STEP 5: 効果検証 (合格しないと「完了」と言わない・違反 #17 防止)
- 該当 SLI を Before/After で実測
- 改善ゼロ or 悪化 → ロールバック PR 起票 + lessons-learned 追記
- 改善あり → Verified-Effect 行で確定 + 次施策候補を TASKS.md に Phase-Impact 付きで起票
- ユーザー被害継続中なら「完了」と書かない (仕組みだけ足して PR closes するな)

## STEP 6: 完了報告 (Before/After SLI を必ず数値で)
- Before SLI: <測定値>
- After SLI:  <測定値>
- 改善: ±X (ユーザー被害解消 / 部分改善 / ゼロ / 悪化)
- 次にやること + 残タスク + Pending-Eng エスカレーションリスト

## 物理的禁止事項
❌ STEP 1-2 を飛ばして実装に入る
❌ Verified-Effect / Eval-Due を空で「完了」報告
❌ ユーザー被害継続中なのに「仕組みを足したから完了」判断
❌ main 直 push (cowork_commit.py が物理 reject)
❌ 並走違反 ([Code]/[Cowork] 並走中の着手)
❌ コアタイム (JST 23-翌7時 = 米国昼間) に緊急性低い軽量タスクを動かす

## 自走 Lv 上昇の鍵
仕組みを足すこと自体は成果ではない。ユーザー被害が解消することが成果。
- 仕組みだけ動いて SLI 改善ゼロなら自走 Lv は上がっていない
- Eng Claude (Lambda 権限) が必要なタスクは Pending-Eng で止める
- PO 介入が減る = 自走 Lv 上昇の代理指標
PROMPT

# --- 動的部分: jst を展開してから出力 ---
echo ""
echo "--- 現在の状態 ($jst) ---"

if [ -n "$dispatch_section" ]; then
  echo "【Dispatch継続性】"
  echo "$dispatch_section" | head -6
  echo ""
fi

if [ -n "$priority_tasks" ]; then
  echo "【未着手優先タスク（TASKS.md より）】"
  echo "$priority_tasks"
  echo ""
fi

cat << 'FOOTER'
---
※ この状態スナップショットは gen_dispatch_prompt.sh が自動生成。
   ルール変更時は docs/dispatch-session-start.md と本スクリプトを更新する。
FOOTER
