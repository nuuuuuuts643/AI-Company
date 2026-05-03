#!/bin/bash
# AI-Company セッション起動チェック（Code/Cowork 共通）
# 用途: 各セッションが冒頭で 1 回だけ呼ぶ。冪等。
# 仕様: CLAUDE.md「セッション開始時に必ず最初に実行すること」を 1 コマンドに集約。
#
# やること:
#   1. git lock / rebase-merge を _garbage に退避（FUSE rm 不可環境向け）
#   2. ローカル変更を sync commit して remote と同期（push）
#   3. CLAUDE.md の最近の commit を表示（変更検知）
#   4. WORKING.md の stale (8h 超) 行を自動削除
#   5. TASKS.md の取消線済み (`~~T...~~`) 行を HISTORY.md に集約移動
#   6. needs-push:yes が WORKING.md に残っていれば最優先で警告
#   7. 1 行サマリ「✅ 起動チェック完了」を出力
#
# 失敗してもセッション続行できるよう、各ステップは ` || true ` で吸収する。

set -u

# ---- 0. --dry-run フラグ検知（T2026-0428-K）----
# CI で REPO 検出 / JST 表示 / WORKING.md 未来日付 stale 検出ロジックを
# git push / commit / file mutation なしで物理 test するためのモード。
# 副作用ある操作（lock 退避・git pull/push/commit・triage_tasks 実行）を全 skip し、
# 読み取り専用の検査だけ走らせて exit code を返す。
DRY_RUN=0
case " $* " in *" --dry-run "*) DRY_RUN=1 ;; esac

# REPO 検出（優先度順）:
#   1. 環境変数 REPO （明示指定があれば最優先）
#   2. Mac 標準 path （Code セッション）
#   3. Cowork VM mount path （session ID は毎回変わるため glob で検出）
# 過去の bug: ハードコードされた session ID (`/sessions/<old-id>/mnt/...`) が
# 新セッションでは存在せず「❌ repo not found」で起動チェック自体が失敗した。
# 修正: glob で `/sessions/*/mnt/ai-company` を探索し、最初に見つかったものを使う。
REPO="${REPO:-}"
# REPO が明示的に渡されていれば、その値を尊重する（負のテスト互換のため）。
# 未指定のときだけ自動検出に進む。
if [ -z "$REPO" ]; then
  # 1. 現在のスクリプト位置から git toplevel を解決（worktree 含めどこから呼ばれても効く）
  GIT_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel 2>/dev/null || true)"
  if [ -n "$GIT_ROOT" ] && [ -d "$GIT_ROOT" ]; then
    REPO="$GIT_ROOT"
  elif [ -d "$HOME/ai-company" ]; then
    REPO="$HOME/ai-company"
  else
    # Cowork VM 環境: session ID は不定なので glob で発見
    for cand in /sessions/*/mnt/ai-company; do
      if [ -d "$cand" ]; then
        REPO="$cand"
        break
      fi
    done
  fi
fi
[ -d "$REPO" ] || { echo "❌ repo not found (REPO=$REPO)"; exit 1; }
cd "$REPO"

if [ "$DRY_RUN" = "0" ]; then
  mkdir -p .git/_garbage 2>/dev/null
fi

# ---- 1. lock / rebase-merge 退避（堅牢化）----
# FUSE 環境では rm が permission denied なので mv で _garbage に逃がす。
# mv も失敗する場合があるため複数回トライ。
# DRY_RUN=1 では mutation せず、ロックの存在のみ報告する。
if [ "$DRY_RUN" = "1" ]; then
  for lock in .git/index.lock .git/HEAD.lock .git/objects/maintenance.lock .git/rebase-merge .git/rebase-apply; do
    [ -e "$lock" ] && echo "[DRY-RUN] would relocate: $lock"
  done
else
  for i in 1 2 3; do
    found_any=0
    for lock in .git/index.lock .git/HEAD.lock .git/objects/maintenance.lock; do
      [ -e "$lock" ] || continue
      found_any=1
      mv "$lock" ".git/_garbage/$(basename $lock).$(date +%s%N)" 2>/dev/null || true
    done
    if [ -d .git/rebase-merge ]; then
      found_any=1
      mv .git/rebase-merge ".git/_garbage/rebase-merge.$(date +%s%N)" 2>/dev/null || true
    fi
    if [ -d .git/rebase-apply ]; then
      found_any=1
      mv .git/rebase-apply ".git/_garbage/rebase-apply.$(date +%s%N)" 2>/dev/null || true
    fi
    [ "$found_any" -eq 0 ] && break
    sleep 1
  done

  # ---- 1c. tmp_obj_* 自動退避 (T2026-0502-E 恒久対処) ----
  # FUSE 環境では git の内部 tmp ファイル (.git/objects/<hash>/tmp_obj_*)
  # が unlink できず累積する。Cowork セッション 1 回の commit で数件、
  # 1500 件超えで内部処理が遅延し始める。
  # 既存 §1 lock 退避と同じ mv → _garbage パターンで自動解消 (J-6 パターン再利用)。
  # 「気づいて自動で消す」 = session_bootstrap 起動のたびに実行 = 恒久対処。
  TMP_OBJ_FILES=$(find .git/objects -name "tmp_obj_*" 2>/dev/null)
  if [ -n "$TMP_OBJ_FILES" ]; then
    TMP_OBJ_DEST=".git/_garbage/tmp_objs-$(date +%s%N)"
    mkdir -p "$TMP_OBJ_DEST" 2>/dev/null
    TMP_OBJ_COUNT=$(echo "$TMP_OBJ_FILES" | wc -l | tr -d ' ')
    echo "$TMP_OBJ_FILES" | while read f; do
      [ -n "$f" ] && mv "$f" "$TMP_OBJ_DEST/" 2>/dev/null || true
    done
    REMAINING=$(find .git/objects -name "tmp_obj_*" 2>/dev/null | wc -l | tr -d ' ')
    echo "🧹 tmp_obj_* 自動退避: ${TMP_OBJ_COUNT} 件 → _garbage/ (残: ${REMAINING})"
  fi
fi

# ---- 1b. broken worktree 自動クリーンアップ ----
# gitdir ポインタが存在しないエントリを検出して削除する。
# git worktree prune では検出できない「ポインタ先が消えた孤児」を対象とする。
_cleanup_broken_worktrees() {
  local wt_dir
  wt_dir="$(git rev-parse --git-dir 2>/dev/null)/worktrees"
  [ -d "$wt_dir" ] || return 0
  local count=0
  for entry in "$wt_dir"/*/; do
    local gitdir_file="$entry/gitdir"
    [ -f "$gitdir_file" ] || continue
    local target
    target=$(cat "$gitdir_file")
    # 相対パスの場合は entry ディレクトリからの相対として解決
    if [[ "$target" != /* ]]; then
      target="$entry/$target"
    fi
    if [ ! -e "$target" ]; then
      rm -rf "$entry"
      count=$((count + 1))
    fi
  done
  [ $count -gt 0 ] && echo "🧹 broken worktree ${count}件 自動削除"
}
if [ "$DRY_RUN" = "0" ]; then
  _cleanup_broken_worktrees || true
fi

# ---- 1c. ブランチ自動クリーンアップ (マージ済み/孤児削除) ----
# 各セッションが新しいブランチを作るが、完了後に削除されないため、
# session_bootstrap 起動のたびに old branches を削除する恒久対処。
# 背景: T2026-0503-BRANCH-CLEANUP（根本原因特定: 435個溜積・worktree は削除されるがブランチ残存）
_cleanup_merged_branches() {
  local count=0
  # リモート削除済みの追跡ブランチを削除
  git fetch --prune origin >/dev/null 2>&1 || true
  # main にマージ済みのローカルブランチを削除（main 自身は除外）
  while IFS= read -r branch; do
    [ -z "$branch" ] && continue
    git branch -d "$branch" 2>/dev/null && count=$((count + 1)) || true
  done < <(git branch --merged main | grep -v '^\* main' | grep -v '^  main')
  [ $count -gt 0 ] && echo "🧹 merged branches 削除: $count 件"
}
if [ "$DRY_RUN" = "0" ]; then
  _cleanup_merged_branches || true
fi

# ---- 2. sync commit & pull --no-rebase & push ----
# rebase 系の中断を作らないため pull は merge 戦略で固定。
#
# FUSE 環境では git fetch/pull/push が以下の "harmless noise" を吐く:
#   - "may have crashed in this repository earlier:" / "remove the file manually to continue."
#   - "warning: unable to unlink '...': Operation not permitted"
#   - "! refs/remotes/origin/main: unable to update local ref"
# これらは _garbage 退避ロジックで実害ゼロ。Claude のコンテキストを汚染するだけなので
# grep -v で物理的に弾く (LANG=C で英語固定。i18n 環境でも安定)。
# 実害ある warning/error は素通しする (フィルタは substring 一致のみ・正規表現使わない)。
_strip_fuse_noise() {
  # FUSE 環境 + 並行セッション起因の "実害ゼロ noise" のみ落とす。
  # 実害ある warning/error (push 失敗・auth・network など) は通すこと。
  # 追加する場合は「実害が無い・mv/_garbage で吸収済」と確認してから入れる。
  LANG=C grep -v -e 'may have crashed in this repository earlier' \
                 -e 'remove the file manually to continue' \
                 -e "warning: unable to unlink" \
                 -e ': unable to update local ref' \
                 -e "an editor opened by 'git commit'" \
                 -e 'are terminated then try again' \
                 -e 'Another git process seems to be running' \
                 -e "error: cannot lock ref 'refs/remotes/" \
                 -e "error: update_ref failed for ref 'refs/remotes/" \
                 -e "Unable to create '.*\.lock': File exists" \
    | sed -E '/^[[:space:]]*$/d; /^ \! .*unable to update local ref/d' \
    || true
}
if [ "$DRY_RUN" = "1" ]; then
  echo "[DRY-RUN] skip: git add/commit/pull/push"
else
  git add -A 2>/dev/null
  if ! git diff --cached --quiet 2>/dev/null; then
    git commit -m "chore: bootstrap sync $(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M JST')" 2>/dev/null || true
  fi
  timeout 60 git pull --no-rebase --no-edit origin main 2>&1 | _strip_fuse_noise | tail -2
  # T2026-0502-PHYSICAL-GUARD-AUDIT: PR #159 landing を実 exit 経路に直結。
  # `| tail -2 || true` だけだと失敗を握り潰すので PIPESTATUS[0] を BOOTSTRAP_EXIT に流す。
  # T2026-05-03-GIT-TIMEOUT: timeout 60 で git hang を 60 秒で強制終了。
  _git_pull_status="${PIPESTATUS[0]:-0}"
  if [ "$_git_pull_status" -ne 0 ]; then
    echo "⚠️  git pull failed (exit=$_git_pull_status). 続行するが末尾で exit 1 する。" >&2
    BOOTSTRAP_EXIT=1
  fi
  mv .git/index.lock .git/_garbage/ 2>/dev/null
  # main 直 push: pre-push hook が ALLOW_MAIN_PUSH=1 escape を要求する (T2026-0502-PHYSICAL-GUARD-AUDIT)
  # T2026-05-03-GIT-TIMEOUT: timeout 120 で git hang を 120 秒で強制終了。
  timeout 120 sh -c 'ALLOW_MAIN_PUSH=1 git push' 2>&1 | _strip_fuse_noise | tail -2
  _git_push_status="${PIPESTATUS[0]:-0}"
  if [ "$_git_push_status" -ne 0 ]; then
    echo "⚠️  git push failed (exit=$_git_push_status). 続行するが末尾で exit 1 する。" >&2
    BOOTSTRAP_EXIT=1
  fi
fi

# ---- 2b. shared docs conflict guard (T2026-0502-H) ----
# pull で shared docs (CLAUDE.md / WORKING.md / TASKS.md / HISTORY.md / docs/lessons-learned.md)
# が UU 状態に陥ったら以後の処理を全て止める。upstream 採用で重要セクションを潰す事故
# (2026-05-02 「コンフリクト解決時に upstream 採用で CLAUDE.md を破壊」) の物理化。
# 詳細: docs/rules/conflict-resolution.md
if [ -x scripts/conflict_check.sh ]; then
  if ! bash scripts/conflict_check.sh; then
    echo "❌ shared docs conflict が未解決のため bootstrap を中断します。" >&2
    echo "   両側マージで解決してから再実行してください (docs/rules/conflict-resolution.md)。" >&2
    exit 1
  fi
fi

# ---- 3. CLAUDE.md 変更検知 ----
LATEST_CLAUDE=$(git log --oneline -1 -- CLAUDE.md 2>/dev/null || echo "(none)")

# ---- 3b. product-direction.md 表示 ----
# セッション切れで方針が消える問題への恒久対策。毎回フルテキストを表示し、
# Claude が起動直後に現在のプロダクト方針を必ずコンテキストに入れる。
if [ -f "docs/product-direction.md" ]; then
  echo ""
  echo "=== 現在のプロダクト方針 (docs/product-direction.md) ==="
  cat docs/product-direction.md
  echo "======================================================="
fi

# ---- 3c. project-phases.md 表示 (現在フェーズ・完了条件の確認) ----
# タスク単位の管理に加え、案件・機能要件 (Epic) の階層を毎回確認する。
if [ -f "docs/project-phases.md" ]; then
  echo ""
  echo "=== プロジェクト・フェーズ階層 (docs/project-phases.md 先頭30行) ==="
  head -30 docs/project-phases.md
  echo "==================================================================="
fi

# ---- 3d. north-star.md 表示 (リライト案 Layer 1 不変層・T2026-0502-A 着地分) ----
# 出自: docs/rules-rewrite-proposal-2026-05-01.md Section 11 Step 3
# 目的: 「プロダクト完成にブレない」北極星を毎セッション必読化する物理ガード。
# 一タスク完遂の局所最適化を防ぐ (PO 観察「変な方向に進む」「組織として動いて欲しい」への対策)。
if [ -f "docs/north-star.md" ]; then
  echo ""
  echo "=== ⭐ 北極星 (docs/north-star.md・全文・毎セッション必読) ==="
  cat docs/north-star.md
  echo "==================================================================="
fi

# ---- 3e. current-phase.md 表示 (リライト案 Layer 2 現フェーズ層・T2026-0502-A 着地分) ----
# 出自: docs/rules-rewrite-proposal-2026-05-01.md Section 11 Step 3
# 目的: 現フェーズ完了条件と「やらないこと」を毎回視界に入れる。
# project-phases.md は階層全体を概観 (3c)、本ファイルは現フェーズだけにフォーカス。
if [ -f "docs/current-phase.md" ]; then
  echo ""
  echo "=== 🎯 現在のフェーズ (docs/current-phase.md・全文・毎セッション必読) ==="
  cat docs/current-phase.md
  echo "==================================================================="
fi

# ---- 3e2. .git/config URL に token 直書き検出 (T2026-0502-SEC2-RECURRENCE) ----
# 背景: 2026-05-02 SEC2 対応で `.git/config` の `remote.origin.url` から PAT を剥がしたが、
#       将来の clone や手動操作で再混入する可能性がある。CLAUDE.md「PII / secrets コード直書き禁止」
#       物理ルールを `.git/config` にも適用する物理ガード。
# 動作: bootstrap 起動時に URL を grep して `gho_` / `ghp_` / `ghs_` / `gho_` パターンが含まれていれば ERROR。
# 対処: `git remote set-url origin https://github.com/<owner>/<repo>.git` + `gh auth login` で Keychain 認証へ。
if [ "$DRY_RUN" = "0" ]; then
  GIT_URL=$(git config --get remote.origin.url 2>/dev/null || echo "")
  if echo "$GIT_URL" | LANG=C grep -qE '://[^/]+:(gh[opsu]_|ghp_)[A-Za-z0-9_-]+@github\.com'; then
    echo "❌ ERROR: .git/config の remote.origin.url に token が直書きされています (T2026-0502-SEC2-RECURRENCE)" >&2
    echo "   セキュリティリスク: PAT/OAuth token が平文で保存されています。" >&2
    echo "   対処:" >&2
    echo "     1. git remote set-url origin https://github.com/nuuuuuuts643/AI-Company.git" >&2
    echo "     2. git config --global credential.helper osxkeychain  # Mac" >&2
    echo "     3. gh auth login --web で Keychain 認証へ移行" >&2
    echo "     4. (Cowork から push する場合) gh auth token > .cowork-token && chmod 600 .cowork-token" >&2
    echo "   詳細: docs/lessons-learned.md「T2026-0502-SEC2-RECURRENCE」「T2026-0502-BJ」" >&2
    BOOTSTRAP_EXIT=1
  fi
fi

# ---- 3e3. Cowork sandbox 認証経路の死活検査 (T2026-0502-BJ-RECURRENCE) ----
# 背景: 2026-05-02 T2026-0502-BJ で「.git/config から PAT を剥がした結果、Cowork sandbox から
#       auth 経路が一切なくなり cowork_commit.py が壊れた」事故が発生。原因は SEC2 対応単独で
#       実施し、別経路 (.cowork-token) のセットアップを忘れたまま剥がしたため。
# 検査: bootstrap 起動時に「Cowork から GitHub にアクセスできる経路」が 1 つ以上あるか確認。
#       (a) .git/config URL に token 直書き (旧仕様・SEC2 違反だが動く)
#       (b) workspace/.cowork-token ファイル (推奨経路・T2026-0502-BJ で導入)
#       (c) env GITHUB_TOKEN / GH_TOKEN
#       上記すべて NG = Cowork から push 不可状態 → WARN で警告
# 対処: Mac で `gh auth token > ~/ai-company/.cowork-token && chmod 600 ~/ai-company/.cowork-token`
# 注: Mac CLI 単独で git push する分には Mac の Keychain で OK。本検査は Cowork sandbox からの
#     push 経路の死活が目的。Mac 単独セッションでも誤検知しないよう、検査結果は WARN 扱い (ERROR
#     にせず BOOTSTRAP_EXIT を変えない)。これは「壊れていることを見えるようにする」ガード。
if [ "$DRY_RUN" = "0" ]; then
  COWORK_AUTH_OK=0
  COWORK_AUTH_PATH=""

  # 経路 (a): .git/config URL に token (SEC2 違反だが auth は通る)
  if echo "$GIT_URL" | LANG=C grep -qE '://[^/]+:(gh[opsu]_|ghp_)[A-Za-z0-9_-]+@github\.com'; then
    COWORK_AUTH_OK=1
    COWORK_AUTH_PATH="(SEC2 違反: .git/config URL 直書き)"
  fi

  # 経路 (b): .cowork-token ファイル (推奨)
  if [ "$COWORK_AUTH_OK" = "0" ] && [ -s .cowork-token ]; then
    if head -c 4 .cowork-token | LANG=C grep -qE '^gh[opsu]_'; then
      COWORK_AUTH_OK=1
      COWORK_AUTH_PATH=".cowork-token (推奨経路)"
    fi
  fi

  # 経路 (c): env
  if [ "$COWORK_AUTH_OK" = "0" ] && { [ -n "${GITHUB_TOKEN:-}" ] || [ -n "${GH_TOKEN:-}" ]; }; then
    COWORK_AUTH_OK=1
    COWORK_AUTH_PATH="env GITHUB_TOKEN/GH_TOKEN"
  fi

  if [ "$COWORK_AUTH_OK" = "0" ]; then
    echo "⚠️  WARN: Cowork sandbox 用の GitHub auth 経路が見つかりません (T2026-0502-BJ-RECURRENCE)" >&2
    echo "   症状: cowork_commit.py / Cowork からの API 呼び出しが 401 になる" >&2
    echo "   恒久対処 (Mac で 1 回): gh auth token > ~/ai-company/.cowork-token && chmod 600 ~/ai-company/.cowork-token" >&2
    echo "   詳細: docs/lessons-learned.md「T2026-0502-BJ」セクション" >&2
    # WARN なので BOOTSTRAP_EXIT は変えない (Mac CLI 単独セッションを break しない)
  fi
fi

# ---- 3f. hook 再汚染検知 (T2026-0502-M-FOLLOW-UP) ----
# 背景: T2026-0502-SESSION-END-HOOK-AUDIT (PR #173) で `~/.claude/settings.json` の Stop hook が
#       全セッション終了時に `git add -A && git commit && git push` を main に直実行していたため、
#       476 件もの auto-sync コミットを生成して main を汚染していた事実が判明。Stop hook は撤去済だが、
#       将来別の hook (PreToolUse / PostToolUse / Notification 等) が同じパターンを再発させた場合、
#       lessons-learned.md に書いた思想ルールでは検出できない。
# 目的: bootstrap 起動時に `~/.claude/settings.json` を grep して、hook ブロック内に
#       `git add` / `git commit` / `git push` パターンがあれば ERROR で BOOTSTRAP_EXIT=1。
# 制約: ファイル不在 (Cowork VM 環境など) はスキップ (Mac セッションでだけ動く)。
HOME_CLAUDE_SETTINGS="${HOME:-/dev/null}/.claude/settings.json"
if [ "$DRY_RUN" = "0" ] && [ -f "$HOME_CLAUDE_SETTINGS" ]; then
  if LANG=C grep -nE 'git[[:space:]]+(-C[[:space:]]+\S+[[:space:]]+)?(add|commit|push)' "$HOME_CLAUDE_SETTINGS" >/tmp/.hook_audit.$$ 2>/dev/null; then
    if [ -s /tmp/.hook_audit.$$ ]; then
      echo "❌ ERROR: ~/.claude/settings.json に git add/commit/push を含む hook が再発しています (T2026-0502-SESSION-END-HOOK-AUDIT 再汚染)" >&2
      echo "   PR #173 で撤去した Stop hook と同じパターンの hook が復活している可能性があります。" >&2
      echo "   該当行:" >&2
      sed 's/^/     /' /tmp/.hook_audit.$$ >&2
      echo "   対処: ~/.claude/settings.json の hook ブロックから git push 系コマンドを除去" >&2
      echo "   詳細: docs/lessons-learned.md「T2026-0502-SESSION-END-HOOK-AUDIT」セクション" >&2
      BOOTSTRAP_EXIT=1
    fi
  fi
  rm -f /tmp/.hook_audit.$$
fi

# ---- 3g. 直近 main CI failure 検知 (T2026-0502-M-FOLLOW-UP) ----
# 背景: CLAUDE.md「Dispatch / Cowork 起動時 (毎回必須・行動前に実行)」で
#       「gh run list --branch main --limit 3 で直近 CI がすべて green であることを確認」と
#       指示しているが、これまでは思想ルール (テキスト止まり) だった。bootstrap で物理化する。
# 目的: gh CLI が使える環境で、直近 3 件の main run に failure があれば WARN を出力 (ERROR にしない)。
#       SLI 閾値違反 (perspectives 充填率など) と Lambda デプロイ失敗を区別できないため WARN 止まり。
# 制約: gh CLI / 認証が無い環境はサイレント skip。
if [ "$DRY_RUN" = "0" ] && command -v gh >/dev/null 2>&1; then
  if gh auth status >/dev/null 2>&1; then
    RECENT_FAIL=$(gh run list --branch main --limit 3 --json conclusion --jq '[.[] | select(.conclusion == "failure")] | length' 2>/dev/null || echo 0)
    if [ "${RECENT_FAIL:-0}" -gt 0 ]; then
      echo "" >&2
      echo "⚠️  WARN: 直近 main CI に failure が ${RECENT_FAIL} 件あります" >&2
      gh run list --branch main --limit 3 2>/dev/null | head -5 | sed 's/^/   /' >&2 || true
      echo "   CLAUDE.md「直近 CI が green」ルール: 失敗があれば修正セッションを先に起動してください" >&2
      echo "   SLI 閾値違反 (perspectives 充填率など) なら別系統タスクで対応可" >&2
    fi
  fi
fi

# ---- 4. WORKING.md 8h stale 自動削除 ----
# DRY_RUN=1 では triage 実行を skip（mutation 回避）。WORKING.md の存在のみ確認。
if [ "$DRY_RUN" = "1" ]; then
  if [ -f WORKING.md ]; then
    echo "[DRY-RUN] WORKING.md exists ($(wc -l < WORKING.md) lines) — would run triage_tasks.py --clean-working-md"
  fi
else
  if [ -f WORKING.md ] && [ -x scripts/triage_tasks.py ]; then
    python3 scripts/triage_tasks.py --clean-working-md 2>/dev/null || true
  fi
fi

# ---- 4b. .claude/worktrees/ stale worktree 検知 (T264) ----
# WORKING.md の 8h TTL とは別軸で、worktree ディレクトリ自体の stale 検出を行う。
# session_bootstrap.sh 経由では --dry-run で「削除候補の一覧表示のみ」。
# 実削除は手動 (`bash scripts/cleanup_stale_worktrees.sh`) で発火させる。
# 失敗は silent (exit 0 保証)。
if [ "$DRY_RUN" = "0" ] && [ -x scripts/cleanup_stale_worktrees.sh ]; then
  bash scripts/cleanup_stale_worktrees.sh --dry-run 2>/dev/null | grep -E '^\[CLEANUP_WORKTREE\]' || true
fi

# ---- 5. TASKS.md 取消線→HISTORY.md ----
if [ "$DRY_RUN" = "1" ]; then
  if [ -f TASKS.md ]; then
    echo "[DRY-RUN] TASKS.md exists ($(wc -l < TASKS.md) lines) — would run triage_tasks.py --triage-tasks"
  fi
else
  if [ -f TASKS.md ] && [ -x scripts/triage_tasks.py ]; then
    python3 scripts/triage_tasks.py --triage-tasks 2>/dev/null || true
  fi
fi

# ---- 5b. (HISTORY 確認要) 行を HISTORY.md と突合して自動取消線化 (T2026-0428-H) ----
# 「実装済の可能性あり (HISTORY 確認要)」のままタスク再起票 anti-pattern を物理化対策。
# scheduled-task の発見偏重バイアス対策の一環 (lessons-learned 2026-04-28 由来)。
if [ "$DRY_RUN" = "0" ]; then
  if [ -f TASKS.md ] && [ -f HISTORY.md ] && [ -x scripts/triage_implemented_likely.py ]; then
    python3 scripts/triage_implemented_likely.py 2>/dev/null || true
  fi
fi

# ---- 6. needs-push 警告 ----
# 「現在着手中」セクションのテーブル本体行のうち、最終セルが yes のものだけを拾う。
# 説明文・引用・記入フォーマット例 を誤検出しないよう awk で厳密化する。
# (旧: `grep -nE 'needs-push.*\<yes\>'` は規則の解説文を毎回拾い、警告がノイズで埋没していた)
NEEDS_PUSH=$(awk '
  /^## 現在着手中/        { in_sec=1; next }
  /^## /                  { in_sec=0 }
  in_sec && /^\|/ && /\| *yes( *\| *)?$/ { printf "%d:%s\n", NR, $0 }
' WORKING.md 2>/dev/null || true)

# ---- 6b. 並行タスク行カウント (T2026-0428-X / P0-STABLE-C / T2026-0428-BB) ----
# 「現在着手中」テーブル本体行だけを数える。ヘッダ行 (`| タスク名 |...`) と
# 区切り行 (`|---|---|`) を除外して、本物のタスク行のみカウント。
# 2026-04-28 PM (T2026-0428-BB): [Code] 並走 ≥2 を WARNING ではなく ERROR で出すように昇格。
# Dispatch 同時 1 件ルール (CLAUDE.md ⚡ Cowork↔Code 連携セクション「セッション並走ルール」) を物理担保。
CONCURRENT_TASKS=$(awk '
  /^## 現在着手中/        { in_sec=1; next }
  /^## /                  { in_sec=0 }
  in_sec && /^\|/ && !/^\| *タスク名/ && !/^\|[ \-]*\|[ \-]*\|/ { count++ }
  END { print count + 0 }
' WORKING.md 2>/dev/null || echo 0)

# [Code] プレフィックス行のみカウント — Dispatch 並走ルール用
CODE_CONCURRENT=$(awk '
  /^## 現在着手中/        { in_sec=1; next }
  /^## /                  { in_sec=0 }
  in_sec && /^\| *\[Code\]/ { count++ }
  END { print count + 0 }
' WORKING.md 2>/dev/null || echo 0)

# ---- 6c. コードセッション名規則 WARN (T2026-0428-BF) ----
# WORKING.md の [Code] 行のタスク名が空抽象タイトル（「作業」「調査」「タスク」「着手」単体等）
# だった場合、何を commit するかが不明確のまま走り出すため WARN する。
# project-phases.md §C 「コードセッション名規則の徹底」を物理担保。
ABSTRACT_TITLES=$(awk -F'|' '
  /^## 現在着手中/        { in_sec=1; next }
  /^## /                  { in_sec=0 }
  in_sec && /^\| *\[Code\]/ {
    name=$2
    gsub(/^[ \t]+|[ \t]+$/, "", name)
    # [Code] プレフィックスを除去して中身チェック
    sub(/^\[Code\][ 　]*/, "", name)
    # 抽象語のみ or 5 文字以下 or 「作業/調査/タスク/着手/wip/test/対応/確認/対応中」のみ
    if (length(name) <= 5) { print name; next }
    if (name ~ /^(作業|調査|タスク|着手|wip|WIP|test|TEST|対応|確認|対応中|チェック|修正)([ 　:：]|$)/) { print name; next }
    if (name ~ /^(作業|調査|タスク|着手|wip|WIP|test|TEST|対応|確認|対応中|チェック|修正)$/) { print name }
  }
' WORKING.md 2>/dev/null || true)

# ---- 6.5 schedule-task モード検知 ----
# `SCHEDULE_TASK=1` または引数 `--schedule` を渡された場合、
# scheduled-task-protocol.md と最優先 unblocked タスク 1 件を強調表示する。
# Claude が起動チェック直後にこの 1 件を見るため、発見前に実装着手を考えさせる狙い。
SCHED=0
case " $* " in *" --schedule "*) SCHED=1 ;; esac
[ "${SCHEDULE_TASK:-0}" = "1" ] && SCHED=1

# 最優先 unblocked task: TASKS.md「🔥 今週やること」テーブルの先頭から ~~ で取消線化
# されていない最初の行を抽出する（簡易ヒューリスティック）。
TOP_TASK=""
if [ -f TASKS.md ]; then
  TOP_TASK=$(awk '
    /^## 🔥/ { in_main=1; next }
    /^## / && in_main { exit }
    in_main && /^\| *T[0-9A-Za-z\-]+ *\|/ && $0 !~ /~~T/ { print; exit }
  ' TASKS.md 2>/dev/null || true)
fi

# 確定済み決定の期限チェック
bash "$(dirname "$0")/check_decisions.sh" || true

# ---- 6.6 繰り返し失敗パターン検出 (T2026-0429-D) ----
# 目的: 「POがたまたま git 見たら同じエラーが繰り返されてた」を物理検出。
# 仕様: gh CLI で workflow run 連続失敗、HISTORY.md でカテゴリ偏り。
# 制約: 各 script は内部で gh 不在 / HISTORY.md 不在を吸収し exit 0 で抜ける。
#       時間予算は両方合計 ~3 秒以内 (gh は TIMEOUT_SEC=4 で打ち切り)。
REPEAT_FAIL=$(bash "$(dirname "$0")/detect_repeated_failures.sh" 2>/dev/null || true)
TASK_PATTERN=$(bash "$(dirname "$0")/analyze_task_patterns.sh" 2>/dev/null || true)

# ---- 6.7 dry-run 検証 (T2026-0428-K) ----
# CI で REPO 解決・JST タイムゾーン・WORKING.md 存在・git status 動作・stale 検出ロジック
# が壊れていないことを物理 assert する。失敗すれば DRY_RUN_FAIL=1 を立てて非ゼロ exit。
if [ "$DRY_RUN" = "1" ]; then
  DRY_RUN_FAIL=0
  echo ""
  echo "=== [DRY-RUN] validation checks ==="

  # (a) REPO は git toplevel と一致するか
  GIT_TOP="$(git rev-parse --show-toplevel 2>/dev/null || true)"
  if [ -n "$GIT_TOP" ] && [ "$GIT_TOP" = "$REPO" ]; then
    echo "  [OK] REPO == git toplevel ($REPO)"
  else
    echo "  [FAIL] REPO ($REPO) != git toplevel ($GIT_TOP)"
    DRY_RUN_FAIL=1
  fi

  # (b) JST タイムゾーンが +0900 であること（過去の UTC/JST 誤ラベル bug 検出）
  JST_TZ="$(TZ=Asia/Tokyo date '+%z' 2>/dev/null || true)"
  if [ "$JST_TZ" = "+0900" ]; then
    echo "  [OK] JST timezone offset = +0900"
  else
    echo "  [FAIL] JST timezone offset mismatch: got '$JST_TZ', want '+0900'"
    DRY_RUN_FAIL=1
  fi

  # (c) WORKING.md が存在すること
  if [ -f WORKING.md ]; then
    echo "  [OK] WORKING.md exists ($(wc -l < WORKING.md | tr -d ' ') lines)"
  else
    echo "  [FAIL] WORKING.md not found"
    DRY_RUN_FAIL=1
  fi

  # (d) git status がワーキングツリー上で動作すること
  if git status --short >/dev/null 2>&1; then
    echo "  [OK] git status runs on working tree"
  else
    echo "  [FAIL] git status failed"
    DRY_RUN_FAIL=1
  fi

  # (e) stale エントリ検出ロジック (8h 超 = 480 分超) のカウント
  # 「現在着手中」テーブル本体の `| ... | YYYY-MM-DD HH:MM | ... |` を parse し、
  # 480 分以上経過した行を stale としてカウント。triage_tasks.py の判定と独立な
  # awk 実装で「count だけは取れる」ことを物理 assert（ロジック改変時の早期発見）。
  NOW_EPOCH=$(date '+%s' 2>/dev/null || echo 0)
  STALE_COUNT=$(awk -F'|' -v now="$NOW_EPOCH" '
    function jst_to_epoch(s,    cmd, e) {
      gsub(/^[ \t]+|[ \t]+$/, "", s)
      if (s !~ /^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}/) return -1
      cmd = "TZ=Asia/Tokyo date -j -f \"%Y-%m-%d %H:%M\" \"" s "\" +%s 2>/dev/null || TZ=Asia/Tokyo date -d \"" s " +0900\" +%s 2>/dev/null"
      cmd | getline e
      close(cmd)
      return e + 0
    }
    /^## 現在着手中/ { in_sec=1; next }
    /^## /          { in_sec=0 }
    in_sec && /^\|/ && !/^\| *タスク名/ && !/^\|[ \-]*\|[ \-]*\|/ {
      e = jst_to_epoch($5)
      if (e > 0 && (now - e) > 8*3600) count++
    }
    END { print count + 0 }
  ' WORKING.md 2>/dev/null || echo 0)
  echo "  [OK] stale entry detection: ${STALE_COUNT} entries older than 8h"

  echo "==================================="
  echo ""
fi

# ---- 6.5 並走 PR / Code セッション 一覧表示 (T2026-0502-AC) ----
# Cowork が「既に走っている作業」を見ずに重複提案する物理パスを潰すため、
# 起動時に必ず open PR と進行中 Code セッション (WORKING.md [Code] 行) を表示する。
# CLAUDE.md「Dispatch 起動時に gh pr list で並走確認」の物理化。
echo "─────────────────────────────────────────"
echo "📋 並走 PR / Code セッション (確認スキップ不可)"
if command -v gh >/dev/null 2>&1; then
  if [ "$DRY_RUN" = "1" ]; then
    echo "[DRY-RUN] gh pr list --state open --limit 10 を実行する想定"
  else
    _OPEN_PRS=$(gh pr list --state open --limit 10 \
      --json number,title,mergeStateStatus,author \
      --template '{{range .}}  #{{.number}} [{{.mergeStateStatus}}] {{.title}}{{"\n"}}{{end}}' 2>/dev/null \
      || echo "  (gh pr list 失敗: 未認証 or オフライン)")
    if [ -n "$_OPEN_PRS" ]; then
      echo "$_OPEN_PRS"
    else
      echo "  (open PR ゼロ)"
    fi
  fi
else
  echo "  (gh CLI 未インストール — open PR 一覧スキップ)"
fi
if [ -f WORKING.md ]; then
  _CODE_LINES=$(grep -E '^\| \[Code\]' WORKING.md 2>/dev/null || true)
  if [ -n "$_CODE_LINES" ]; then
    echo "  進行中 [Code] セッション:"
    echo "$_CODE_LINES" | sed 's/^/    /'
  else
    echo "  進行中 [Code] セッションなし"
  fi
fi
echo ""

# ---- 7. サマリ出力 ----
# T2026-0502-BOOTSTRAP-SUMMARY-FIX: BOOTSTRAP_EXIT に応じてシンボル/メッセージを分岐。
# 旧実装: 失敗時 (BOOTSTRAP_EXIT=1) でも stdout 末尾は「✅ 起動チェック完了」のまま →
#         lessons-learned.md L961「✅ 完了ログは実際に成功した条件下でのみ出す」のメタ教訓
#         そのものを bootstrap 自身が踏み続けていた。 git pull/push auth fail のとき
#         ⚠️ stderr メッセージは出るが見落とされやすく、 ✅ で成功と誤認するリスク。
echo "─────────────────────────────────────────"
if [ "$DRY_RUN" = "1" ]; then
  echo "✅ [DRY-RUN] 起動チェック完了 ($(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M JST'))"
  echo "  REPO=$REPO"
elif [ "${BOOTSTRAP_EXIT:-0}" -ne 0 ]; then
  echo "❌ 起動チェック異常終了 ($(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M JST')) — exit ${BOOTSTRAP_EXIT}"
  echo "  詳細は stderr の ⚠️ 行を参照 (例: git pull/push 失敗・lock 競合・並走違反 等)"
  echo "  bootstrap は exit ${BOOTSTRAP_EXIT} で終了します。後続セッションが状態確認できるよう WORKING.md に状況を記録してください。"
else
  echo "✅ 起動チェック完了 ($(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M JST'))"
fi
echo "  CLAUDE.md latest: $LATEST_CLAUDE"
if [ -n "$NEEDS_PUSH" ]; then
  echo "  ⚠️ needs-push 滞留:"
  echo "$NEEDS_PUSH" | sed 's/^/    /'
fi
if [ "${CONCURRENT_TASKS:-0}" -ge 3 ]; then
  echo "  ⚠️ WORKING.md 並行タスク行 ${CONCURRENT_TASKS} 件 (≥3) — lock 競合・重複作業の可能性。各行の開始JST/needs-push を確認すること"
fi
# コードセッション名規則 WARN (T2026-0428-BF)
if [ -n "$ABSTRACT_TITLES" ]; then
  echo "  ⚠️ WARN: [Code] セッション名が抽象的すぎる行を検出"
  echo "$ABSTRACT_TITLES" | sed 's/^/      → /'
  echo "     セッション名は「何を commit するか」が一目で分かる名前にする"
  echo "     ✅ 例: 「CI 構文チェック fix」「T2026-0428-BD 形骸化 grep CI」"
  echo "     ❌ 例: 「調査」「作業」「タスク」「対応」"
fi
# WORKING.md 自己宣言リマインダー (T2026-0430-REV): [Code]=0 の場合、
# このセッション自身がまだ宣言していない可能性があるため、毎回 REMIND を出す。
# 「宣言なしで着手できない」物理ブロックはないが、見落とし率を下げる目的。
if [ "${CODE_CONCURRENT:-0}" -eq 0 ]; then
  echo "  📋 REMIND: WORKING.md に [Code] 行を追記してから着手すること"
  echo "     | [Code] <タスクID> <タスク名> | Code | <変更予定ファイル> | <開始JST> | yes |"
fi
# Dispatch 並走ルール: [Code] が同時 2 件以上は ERROR (T2026-0428-BB)
if [ "${CODE_CONCURRENT:-0}" -ge 2 ]; then
  echo "  ❌ ERROR: WORKING.md [Code] セッションが ${CODE_CONCURRENT} 件並走中 (≥2)"
  echo "     Dispatch ルール: コードセッションは同時 1 件まで (CLAUDE.md ⚡ Cowork↔Code 連携セクション)"
  echo "     対応: 完了済みセッション行を削除 → push してから新規セッション開始"
  # 環境変数 ALLOW_CONCURRENT_CODE=1 で bypass 可能 (緊急のみ)
  if [ "${ALLOW_CONCURRENT_CODE:-0}" != "1" ]; then
    echo "     bypass (緊急のみ): ALLOW_CONCURRENT_CODE=1 bash scripts/session_bootstrap.sh"
    BOOTSTRAP_EXIT=1
  fi
fi
if [ "$SCHED" = "1" ]; then
  echo ""
  echo "  📋 schedule-task モード:"
  echo "    1. cat docs/rules/scheduled-task-protocol.md を必ず読んでから動く"
  echo "    2. 探索 → 実装 1 件以上 → 報告（フェーズ順序固定）"
  echo "    3. commit message に [Schedule-KPI] implemented=N created=M closed=K queue_delta=±X 行を含める（commit-msg hook で物理強制）"
  if [ -n "$TOP_TASK" ]; then
    echo ""
    echo "  🎯 最優先 unblocked タスク (このセッションで実装候補):"
    echo "$TOP_TASK" | sed 's/^/    /'
  fi
fi
# T2026-0429-D: 繰り返し失敗の自動可視化 (gh / HISTORY.md ベース)
if [ -n "${REPEAT_FAIL:-}" ]; then
  echo "$REPEAT_FAIL" | sed 's/^/  /'
fi
if [ -n "${TASK_PATTERN:-}" ]; then
  echo "$TASK_PATTERN" | sed 's/^/  /'
fi

# ---- [scope:large] タグ検出警告 (T2026-0501-SCOPE-CHECK, なぜなぜ Why3 対策) ----
# 広範囲変更が含まれるタスク定義を起動時に検出して、着手前に分割を促す。
# PR #86 で一度に 22 箇所変更が発生した根本原因: 「タスク定義に広範囲変更が含まれていて、
# 誰も気付かない」ことへの仕組み的対策。
LARGE_TASKS=$(grep -c '\[scope:large\]' TASKS.md 2>/dev/null | tr -d ' \n' || echo "0")
if [ "$LARGE_TASKS" != "0" ] && [ "$LARGE_TASKS" -gt 0 ]; then
  echo "  ⚠️  [SCOPE-LARGE] TASKS.md に [scope:large] タグが ${LARGE_TASKS} 件あります。着手前に分割を検討してください。"
  grep '\[scope:large\]' TASKS.md | head -5
fi

echo "  次の TASKS.md 着手: cat TASKS.md で未着手を確認"
echo "─────────────────────────────────────────"

# Dispatch 並走 ERROR が出ていれば exit 1 で物理ブロック (T2026-0428-BB)
if [ "${BOOTSTRAP_EXIT:-0}" -ne 0 ]; then
  exit "$BOOTSTRAP_EXIT"
fi

# DRY-RUN 終端マーカー (T2026-0428-K) — CI が grep で検査する
if [ "$DRY_RUN" = "1" ]; then
  if [ "${DRY_RUN_FAIL:-0}" = "0" ]; then
    echo "[DRY-RUN OK]"
    exit 0
  else
    echo "[DRY-RUN FAIL]"
    exit 1
  fi
fi
exit 0
