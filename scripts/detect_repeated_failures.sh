#!/bin/bash
# T2026-0429-D: GitHub Actions 同一ワークフローの連続失敗検出
#
# 目的: 「ナオヤがたまたま git 見たら同じエラーが繰り返されてた」を物理検出する。
# 仕様:
#   - 最近 50 件の workflow run を取得
#   - workflow 名でグルーピングし、最新側から連続 failure を数える
#   - N >= 3 で ⚠️ REPEATED FAILURE: [名前] が [N]回連続失敗 を出力
#   - gh 未インストール / 未認証 / オフライン時はサイレントスキップ (exit 0)
#   - session_bootstrap.sh から呼ぶため 5 秒以内に終わるよう gh は --json + 短い limit
#
# 使い方:
#   bash scripts/detect_repeated_failures.sh
#   THRESHOLD=2 bash scripts/detect_repeated_failures.sh   # 閾値変更
#   LIMIT=100 bash scripts/detect_repeated_failures.sh     # 取得件数変更

set -u

THRESHOLD="${THRESHOLD:-3}"
LIMIT="${LIMIT:-50}"
TIMEOUT_SEC="${TIMEOUT_SEC:-4}"

# gh CLI がない / 認証されていない / git repo の外なら何もしない (起動チェックを止めない)
command -v gh >/dev/null 2>&1 || exit 0
gh auth status >/dev/null 2>&1 || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

# gh run list を timeout 付きで実行 (ネットワーク死で起動チェックを止めない)
# macOS には gtimeout が無い場合があるので perl で代替
RUNS_JSON=$(perl -e '
  use strict; use warnings;
  my $pid = fork();
  if ($pid == 0) { exec @ARGV; exit 127; }
  my $deadline = time() + '"$TIMEOUT_SEC"';
  while (time() < $deadline) {
    my $kid = waitpid($pid, 1);  # WNOHANG = 1
    last if $kid > 0;
    select(undef, undef, undef, 0.1);
  }
  if (waitpid($pid, 1) == 0) { kill 9, $pid; exit 124; }
  exit($? >> 8);
' gh run list --limit "$LIMIT" --json name,conclusion,status,createdAt 2>/dev/null) || exit 0

[ -z "$RUNS_JSON" ] && exit 0

# python3 で workflow 名ごとに「最新側からの連続 failure」を数える
# (in_progress / queued は無視・skip しない方針: 失敗の流れの間に挟まる成功は連続を切る)
python3 - "$RUNS_JSON" "$THRESHOLD" <<'PY' || exit 0
import json, sys
from collections import defaultdict

runs_json, threshold = sys.argv[1], int(sys.argv[2])
try:
    runs = json.loads(runs_json)
except Exception:
    sys.exit(0)

# workflow 名ごとに createdAt 降順で並べる (新しい順)
by_name = defaultdict(list)
for r in runs:
    name = r.get("name") or "(unknown)"
    by_name[name].append(r)

for name, lst in by_name.items():
    lst.sort(key=lambda r: r.get("createdAt", ""), reverse=True)

flagged = []
for name, lst in by_name.items():
    consec = 0
    for r in lst:
        # 進行中はスキップ (連続を切らない・数えない)
        if r.get("status") != "completed":
            continue
        if r.get("conclusion") == "failure":
            consec += 1
        else:
            break  # success/cancelled 等が挟まったら連続終了
    if consec >= threshold:
        flagged.append((name, consec))

if not flagged:
    sys.exit(0)

# 連続回数が多い順
flagged.sort(key=lambda x: -x[1])
for name, consec in flagged:
    print(f"⚠️ REPEATED FAILURE: [{name}] が {consec}回連続失敗")
PY
