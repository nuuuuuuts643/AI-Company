#!/usr/bin/env bash
# scripts/health_check.sh
# システムが自分で問題に気づいて TASKS.md に未着手タスクを追記する自己診断スクリプト。
#
# 「人間が気づいて指摘する」前にシステム自身が問題を検出するための物理ゲート。
# 検出した問題は TASKS.md の「🤖 自動検出キュー」セクションに追記される。
#
# 使い方:
#   bash scripts/health_check.sh              # 全カテゴリ実行
#   bash scripts/health_check.sh --code-only  # コード品質のみ (AWS 不要)
#   bash scripts/health_check.sh --dry-run    # TASKS.md は書き換えず stdout に出力のみ
#
# 環境変数:
#   FLOTOPIC_TOPICS_URL     (default: https://flotopic.com/api/topics.json)
#   AWS_REGION              (default: ap-northeast-1)
#   LAMBDA_ERROR_THRESHOLD  (default: 1.0  — %)
#   AI_MISSING_THRESHOLD    (default: 20   — %)
#   ANALYTICS_ITEM_LIMIT    (default: 100000)
#   FILE_LINE_LIMIT         (default: 500)
#
# exit code:
#   0  : 検出なし or タスク追記成功
#   2  : 実行エラー (依存不足など)
#
# 仕様:
#   - 同じ「タグ」を持つタスクが既に TASKS.md に存在すれば skip (重複防止)
#   - タグ形式: AUTO-<CATEGORY>-<DETAIL> 例: AUTO-LINES-HANDLER
#   - 1 回の実行で複数タスクを追記可能

set -u

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

DRY_RUN=0
CODE_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --code-only) CODE_ONLY=1 ;;
    -h|--help)
      sed -n '2,30p' "$0"
      exit 0
      ;;
  esac
done

DATE_TAG=$(TZ=Asia/Tokyo date '+%Y-%m%d')        # T<DATE_TAG>- 形式の ID プレフィックス
DATE_DISPLAY=$(TZ=Asia/Tokyo date '+%Y-%m-%d')   # 追加日カラム表記
JST_TS=$(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M JST')
TASKS_FILE="${REPO_ROOT}/TASKS.md"
SECTION_HEADER="## 🤖 自動検出キュー (health_check.sh)"
DETECTED_COUNT=0
APPENDED_COUNT=0

# ──────────────────────────────────────────────────────────────────
# ヘルパ: 同じタグのタスクが既に TASKS.md にあるか確認 → 無ければ追記
# 引数: <tag> <priority(高/中/低)> <axis> <content> <files>
# 例: append_task "AUTO-LINES-HANDLER" "中" "技術負債" "handler.py 500行超" "lambda/processor/handler.py"
append_task() {
  local tag="$1" priority="$2" axis="$3" content="$4" files="$5"
  DETECTED_COUNT=$((DETECTED_COUNT + 1))
  # 重複検出: 既に同じタグの行がある (どの日付でも) なら skip
  if grep -qE "T[0-9]{4}-[0-9]{4}-${tag}\b" "$TASKS_FILE" 2>/dev/null; then
    echo "[skip] 既存タスクあり: ${tag}"
    return 0
  fi
  local task_id="T${DATE_TAG}-${tag}"
  local row="| ${task_id} | ${priority} | ${axis} | [自動検出] ${content} | ${files} | ${DATE_DISPLAY} |"
  echo "[detect] ${task_id}: ${content}"
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "  → (dry-run) ${row}"
    return 0
  fi
  ensure_section
  # セクション直後の表ヘッダ行の次に row を追記
  python3 - "$TASKS_FILE" "$row" <<'PY'
import sys, pathlib, re
path = pathlib.Path(sys.argv[1])
row = sys.argv[2]
text = path.read_text(encoding='utf-8')
marker = '## 🤖 自動検出キュー (health_check.sh)'
if marker not in text:
    sys.exit(1)
lines = text.split('\n')
out = []
i = 0
inserted = False
while i < len(lines):
    out.append(lines[i])
    if not inserted and lines[i].startswith(marker):
        # ヘッダ行直後の表ヘッダ・区切りを探して、その下に追記
        j = i + 1
        while j < len(lines) and not lines[j].startswith('|---'):
            out.append(lines[j])
            j += 1
        if j < len(lines):
            out.append(lines[j])  # |---|---|... 区切り行
            out.append(row)
            inserted = True
            i = j
    i += 1
if not inserted:
    sys.exit(2)
path.write_text('\n'.join(out), encoding='utf-8')
PY
  if [ $? -eq 0 ]; then
    APPENDED_COUNT=$((APPENDED_COUNT + 1))
    echo "  → 追記: ${task_id}"
  else
    echo "  → 追記失敗 (セクション挿入エラー)" >&2
  fi
}

# 「🤖 自動検出キュー」セクションが TASKS.md に無ければ末尾に追加
ensure_section() {
  if grep -qF "$SECTION_HEADER" "$TASKS_FILE"; then
    return 0
  fi
  cat >> "$TASKS_FILE" <<'EOF'

---

## 🤖 自動検出キュー (health_check.sh)

> `scripts/health_check.sh` が自動で追記する。GitHub Actions `health-check.yml` が毎日 09:00 JST に実行する。
> 同じタグのタスクは重複追記されない。完了したら HISTORY.md に移動して行を削除する。

| ID | 優先 | 軸 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|---|
EOF
}

# ──────────────────────────────────────────────────────────────────
# カテゴリ 1: コード品質
# ──────────────────────────────────────────────────────────────────
check_code_quality() {
  echo "=== [1/3] コード品質チェック ==="
  local limit="${FILE_LINE_LIMIT:-500}"

  # 1-a. app.js / handler.py の行数
  local targets=(
    "projects/P003-news-timeline/frontend/app.js:LINES-APPJS:frontend/app.js"
    "projects/P003-news-timeline/lambda/processor/handler.py:LINES-PROCESSOR:lambda/processor/handler.py"
    "projects/P003-news-timeline/lambda/fetcher/handler.py:LINES-FETCHER:lambda/fetcher/handler.py"
  )
  for target in "${targets[@]}"; do
    local path="${target%%:*}"
    local rest="${target#*:}"
    local tag="${rest%%:*}"
    local label="${rest#*:}"
    if [ ! -f "$path" ]; then continue; fi
    local lines
    lines=$(wc -l < "$path" | tr -d ' ')
    if [ "$lines" -gt "$limit" ]; then
      append_task "AUTO-${tag}" "中" "技術負債" \
        "**${label} が ${lines} 行 (閾値 ${limit} 行)** — ファイル分割で保守性を改善する。責務ごとに別ファイルへ切り出し、import/require で接続。" \
        "\`${path}\`"
    fi
  done

  # 1-b. デバッグ用 console.log / print( がコードに残留 (テスト・スクリプト除く)
  # 対象: projects/P003-news-timeline/frontend/*.js (node_modules / vendor 除外)
  if command -v grep >/dev/null 2>&1; then
    local console_count
    console_count=$(grep -rE '^\s*console\.log\(' projects/P003-news-timeline/frontend/ \
      --include='*.js' \
      --exclude-dir=node_modules \
      --exclude-dir=vendor \
      --exclude-dir=js/lib 2>/dev/null \
      | wc -l | tr -d ' ')
    if [ "$console_count" -gt 20 ]; then
      append_task "AUTO-CONSOLE-LOG" "低" "技術負債" \
        "**frontend/ 配下に console.log が ${console_count} 箇所残留** — 本番デバッグログとして発見性を下げる。意図的な err.log / warn.log 以外は削除し、必要なら logger.debug 経由にする。" \
        "\`projects/P003-news-timeline/frontend/\`"
    fi
    local print_count
    print_count=$(grep -rE "^\s*print\(" projects/P003-news-timeline/lambda/ \
      --include='*.py' \
      --exclude-dir=__pycache__ \
      --exclude-dir=tests 2>/dev/null \
      | wc -l | tr -d ' ')
    if [ "$print_count" -gt 5 ]; then
      append_task "AUTO-PRINT-RESIDUE" "低" "技術負債" \
        "**lambda/ 配下に print( が ${print_count} 箇所残留** — CloudWatch には出るが構造化ログにならない。logger.info/warning/error に置換する。" \
        "\`projects/P003-news-timeline/lambda/\`"
    fi
  fi

  # 1-c. 内部スクリプトに defer/async が混入していないか (chart.js / config.js / app.js / detail.js)
  local defer_hit
  defer_hit=$(grep -lEr '<script[^>]*(defer|async)[^>]*(chart\.js|config\.js|app\.js|detail\.js)|<script[^>]*(chart\.js|config\.js|app\.js|detail\.js)[^>]*(defer|async)' \
    projects/P003-news-timeline/frontend/ --include='*.html' 2>/dev/null \
    | head -5)
  if [ -n "$defer_hit" ]; then
    append_task "AUTO-DEFER-INTERNAL" "高" "安定性" \
      "**内部 JS (chart.js / config.js / app.js / detail.js) に defer/async が混入** — 実行順序が壊れて初期化失敗する。CLAUDE.md 絶対ルール違反。即座に削除して同期実行に戻す。検出ファイル: $(echo "$defer_hit" | tr '\n' ' ')" \
      "$(echo "$defer_hit" | tr '\n' ' ')"
  fi
}

# ──────────────────────────────────────────────────────────────────
# カテゴリ 2: インフラ (AWS CLI 必須)
# ──────────────────────────────────────────────────────────────────
check_infra() {
  echo "=== [2/3] インフラチェック (AWS) ==="
  if [ "$CODE_ONLY" -eq 1 ]; then
    echo "  → --code-only 指定のため skip"
    return 0
  fi
  if ! command -v aws >/dev/null 2>&1; then
    echo "  → aws CLI が無いため skip"
    return 0
  fi
  if ! aws sts get-caller-identity >/dev/null 2>&1; then
    echo "  → AWS 認証情報なしのため skip"
    return 0
  fi
  local region="${AWS_REGION:-ap-northeast-1}"

  # 2-a. DynamoDB テーブルで TTL 未設定のもの
  local tables
  tables=$(aws dynamodb list-tables --region "$region" --output text --query 'TableNames[]' 2>/dev/null || true)
  if [ -n "$tables" ]; then
    local missing_ttl=()
    for t in $tables; do
      # P003 関連テーブルのみに絞る (誤検出防止)
      case "$t" in
        flotopic-*|p003-*) ;;
        *) continue ;;
      esac
      local ttl_status
      ttl_status=$(aws dynamodb describe-time-to-live --table-name "$t" --region "$region" \
        --query 'TimeToLiveDescription.TimeToLiveStatus' --output text 2>/dev/null || echo "ERROR")
      if [ "$ttl_status" = "DISABLED" ] || [ -z "$ttl_status" ] || [ "$ttl_status" = "None" ]; then
        missing_ttl+=("$t")
      fi
    done
    if [ ${#missing_ttl[@]} -gt 0 ]; then
      local table_list
      table_list=$(IFS=,; echo "${missing_ttl[*]}")
      append_task "AUTO-DDB-TTL" "中" "コスト・運用" \
        "**DynamoDB テーブルで TTL 未設定: ${table_list}** — 古いレコードが永続蓄積しコスト増 & スキャン速度低下。enable-time-to-live で expiresAt 属性を有効化する。" \
        "AWS DynamoDB console / IaC"
    fi
  fi

  # 2-b. Lambda エラー率 > 閾値 (過去 24h)
  local lambda_threshold="${LAMBDA_ERROR_THRESHOLD:-1.0}"
  local funcs
  funcs=$(aws lambda list-functions --region "$region" --output text \
    --query 'Functions[?starts_with(FunctionName, `p003-`)].FunctionName' 2>/dev/null || true)
  if [ -n "$funcs" ]; then
    local end_ts start_ts
    end_ts=$(date -u +%s)
    start_ts=$((end_ts - 86400))
    local end_iso start_iso
    if date -u -d "@$end_ts" +"%Y-%m-%dT%H:%M:%SZ" >/dev/null 2>&1; then
      end_iso=$(date -u -d "@$end_ts" +"%Y-%m-%dT%H:%M:%SZ")
      start_iso=$(date -u -d "@$start_ts" +"%Y-%m-%dT%H:%M:%SZ")
    else
      end_iso=$(date -u -j -f "%s" "$end_ts" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null)
      start_iso=$(date -u -j -f "%s" "$start_ts" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null)
    fi
    for f in $funcs; do
      local invocations errors
      invocations=$(aws cloudwatch get-metric-statistics --region "$region" \
        --namespace AWS/Lambda --metric-name Invocations \
        --dimensions Name=FunctionName,Value="$f" \
        --start-time "$start_iso" --end-time "$end_iso" \
        --period 86400 --statistics Sum \
        --query 'Datapoints[0].Sum' --output text 2>/dev/null || echo "0")
      errors=$(aws cloudwatch get-metric-statistics --region "$region" \
        --namespace AWS/Lambda --metric-name Errors \
        --dimensions Name=FunctionName,Value="$f" \
        --start-time "$start_iso" --end-time "$end_iso" \
        --period 86400 --statistics Sum \
        --query 'Datapoints[0].Sum' --output text 2>/dev/null || echo "0")
      [ "$invocations" = "None" ] && invocations=0
      [ "$errors" = "None" ] && errors=0
      local rate
      rate=$(awk -v e="$errors" -v i="$invocations" 'BEGIN{ if(i+0>0) printf "%.2f", e/i*100; else print "0" }')
      local exceed
      exceed=$(awk -v r="$rate" -v t="$lambda_threshold" 'BEGIN{ if(r+0 > t+0) print "1"; else print "0" }')
      if [ "$exceed" = "1" ] && awk -v i="$invocations" 'BEGIN{ exit !(i+0 >= 10) }'; then
        # function 名から短縮タグを作る (大文字 + ハイフン正規化)
        local short
        short=$(echo "$f" | tr 'a-z-' 'A-Z_' | sed 's/^P003_//')
        append_task "AUTO-LAMBDA-ERR-${short}" "高" "安定性" \
          "**Lambda \`${f}\` のエラー率が ${rate}% (閾値 ${lambda_threshold}%, invocations=${invocations}, errors=${errors}, 過去24h)** — CloudWatch Logs で root cause 調査し、リトライ・タイムアウト・依存サービス側の障害を切り分ける。" \
          "CloudWatch Logs / \`projects/P003-news-timeline/lambda/${f#p003-}/\`"
      fi
    done
  fi

  # 2-c. flotopic-analytics の item 数 > 閾値 (TTL 未設定なら 2-a で既出だが、サイズ警告は別軸)
  local analytics_limit="${ANALYTICS_ITEM_LIMIT:-100000}"
  local item_count
  item_count=$(aws dynamodb describe-table --table-name flotopic-analytics --region "$region" \
    --query 'Table.ItemCount' --output text 2>/dev/null || echo "")
  if [ -n "$item_count" ] && [ "$item_count" != "None" ] && [ "$item_count" -gt "$analytics_limit" ] 2>/dev/null; then
    append_task "AUTO-ANALYTICS-SIZE" "中" "コスト" \
      "**flotopic-analytics の item 数が ${item_count} (閾値 ${analytics_limit}) を超えた** — TTL 設定 (例: 90日) かサンプリングでサイズを抑える。スキャンコストが線形に増える。" \
      "DynamoDB \`flotopic-analytics\`"
  fi
}

# ──────────────────────────────────────────────────────────────────
# カテゴリ 3: データ品質
# ──────────────────────────────────────────────────────────────────
check_data_quality() {
  echo "=== [3/3] データ品質チェック ==="
  if [ "$CODE_ONLY" -eq 1 ]; then
    echo "  → --code-only 指定のため skip"
    return 0
  fi
  if ! command -v curl >/dev/null 2>&1 || ! command -v python3 >/dev/null 2>&1; then
    echo "  → curl / python3 が無いため skip"
    return 0
  fi
  local url="${FLOTOPIC_TOPICS_URL:-https://flotopic.com/api/topics.json}"
  local missing_threshold="${AI_MISSING_THRESHOLD:-20}"
  local tmp
  tmp=$(mktemp)
  trap 'rm -f "$tmp"' RETURN
  if ! curl -fsSL -m 30 "$url" -o "$tmp"; then
    echo "  → topics.json 取得失敗 ($url): skip"
    return 0
  fi
  # AI 要約なしトピック比率を計算
  local result
  result=$(python3 - "$tmp" "$missing_threshold" <<'PY'
import json, sys
path, threshold = sys.argv[1], float(sys.argv[2])
try:
    data = json.load(open(path, encoding='utf-8'))
except Exception as e:
    print(f"PARSE_ERROR {e}")
    sys.exit(0)
topics = data.get('topics', data) if isinstance(data, dict) else data
if not isinstance(topics, list):
    print("NOT_LIST")
    sys.exit(0)
# articleCount>=3 のフル要約対象のみを母数にする
target = [t for t in topics if isinstance(t, dict) and t.get('articleCount', 0) >= 3
          and t.get('lifecycleStatus') != 'archived']
total = len(target)
if total == 0:
    print(f"OK 0 0 0.0")
    sys.exit(0)
missing = sum(1 for t in target if not t.get('aiGenerated'))
pct = missing * 100 / total
status = 'WARN' if pct > threshold else 'OK'
print(f"{status} {missing} {total} {pct:.1f}")
PY
)
  echo "  → AI 要約 missing: $result"
  case "$result" in
    WARN*)
      local missing total pct
      missing=$(echo "$result" | awk '{print $2}')
      total=$(echo "$result" | awk '{print $3}')
      pct=$(echo "$result" | awk '{print $4}')
      append_task "AUTO-AI-MISSING" "高" "AI品質" \
        "**AI 要約なしトピック比率が ${pct}% (${missing}/${total}, 閾値 ${missing_threshold}%, articleCount>=3 母数)** — processor の AI 生成キューが詰まっているか proc_ai.py がエラーで skip している。CloudWatch Logs で processor の error/warning を直近 24h 確認し、ANTHROPIC_API_KEY / 429 / wallclock guard 起因か特定する。" \
        "\`projects/P003-news-timeline/lambda/processor/proc_ai.py\`, CloudWatch Logs"
      ;;
    PARSE_ERROR*|NOT_LIST)
      append_task "AUTO-TOPICS-MALFORMED" "高" "AI品質" \
        "**topics.json が JSON として壊れているか topics 配列が不在** — 詳細: ${result}. processor 出力の生成プロセスを確認 (proc_storage.py の publish 経路)。" \
        "\`projects/P003-news-timeline/lambda/processor/proc_storage.py\`"
      ;;
  esac
}

# ──────────────────────────────────────────────────────────────────
# main
# ──────────────────────────────────────────────────────────────────
echo "🩺 health_check.sh 開始: ${JST_TS} (dry_run=${DRY_RUN}, code_only=${CODE_ONLY})"
check_code_quality
check_infra
check_data_quality
echo ""
echo "──────────────────────────────────────────"
echo "検出 ${DETECTED_COUNT} 件 / 追記 ${APPENDED_COUNT} 件 (重複除く) @ ${JST_TS}"
echo "──────────────────────────────────────────"
exit 0
