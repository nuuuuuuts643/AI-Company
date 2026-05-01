# Claude Code 引き継ぎプロンプト — T2026-0502-G fetcher Lambda 恒久対処

> **このファイルをコピーして `claude` の起動プロンプトに貼って下さい。**
> 起動コマンド: `cd ~/ai-company && claude` (または `claude --model sonnet` 明示)

---

## 役割

あなたは Eng Claude (Sonnet 推奨)。Cowork Dispatch から渡された **T2026-0502-G** 1 タスクのみを完走する。1セッション1タスク厳守。

## 背景（インシデント継続中・2026-05-02 01:50 JST 時点）

- `https://flotopic.com/api/topics.json` の `updatedAt = 2026-05-01T09:36:19.445443+00:00`
- 現時点 staleness = **427 分 / 7.1 時間**（閾値 90 分の 4.7 倍）
- `freshness-check.yml` 直近 3 連続 failure（2026-05-01 16:15 / 12:07 / 08:30 UTC）
- `fetcher-health-check.yml` 直近 3 連続 failure（2026-05-01 15:41 / 11:46 / 07:37 UTC）
- 最後の成功: freshness-check 2026-05-01 00:09 UTC / fetcher-health 2026-04-30 21:42 UTC
- `aiCallsUsed = 4`（topics.json 内）— processor は AI 呼んでるが書き込みが進んでいない

## 完了条件（すべて満たすまで完了報告禁止）

1. **topics.json `updatedAt` が 90 分以内に戻っている**（`curl -s https://flotopic.com/api/topics.json | python3 -c "import json,sys,datetime;d=json.load(sys.stdin);print(d['updatedAt'])"`）
2. **`fetcher-health-check.yml` の次の cron tick で success**（毎時 23 分 UTC）
3. **`freshness-check.yml` の次の cron tick で success**
4. **PR が main へ merge 済み**（`gh pr merge --squash --auto` 推奨）
5. **commit に `Verified:` 行 + `Verified-Effect:` 行両方含む**（commit-msg hook で物理 reject される）
6. **`bash done.sh T2026-0502-G <verify_target>` 実行済み**

## 着手前チェック（**スキップ厳禁**・既存 CI 失敗を踏まないため）

```bash
cd ~/ai-company
bash scripts/session_bootstrap.sh                        # 起動チェック
gh run list --branch main --limit 5                      # 既存 CI 失敗が main に無いことを確認
cat WORKING.md | grep "\[Code\]"                         # [Code] 行が 0 件であることを確認
cat docs/product-direction.md docs/north-star.md | head  # フェーズ2 の北極星確認
```

WORKING.md に `[Code] T2026-0502-G fetcher Lambda 恒久対処` 行を追記してから push する（needs-push: yes）。記載なしでコード変更禁止（物理ルール）。

## 調査順序

### Step 1: CloudWatch Logs で Lambda 実体エラーを特定

```bash
# fetcher Lambda 名を確認
aws lambda list-functions --region ap-northeast-1 --query "Functions[?contains(FunctionName, 'fetcher') || contains(FunctionName, 'p003')].[FunctionName,LastModified]" --output table

# 直近 24h のログ（fetcher）
aws logs tail /aws/lambda/p003-news-fetcher --since 24h --region ap-northeast-1 | tail -200

# processor も
aws logs tail /aws/lambda/p003-news-processor --since 24h --region ap-northeast-1 | tail -200

# ERROR / Exception / Timeout を抽出
aws logs filter-log-events --log-group-name /aws/lambda/p003-news-fetcher \
  --start-time $(date -u -d '24 hours ago' +%s)000 \
  --filter-pattern '?ERROR ?Exception ?Timeout ?TooManyRequests' \
  --region ap-northeast-1 --max-items 30
```

### Step 2: メトリクスで Invocation の有無を切り分け

```bash
# Invocations / Errors / Throttles / Duration の過去 24h
for METRIC in Invocations Errors Throttles Duration; do
  echo "=== $METRIC ==="
  aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name $METRIC \
    --dimensions Name=FunctionName,Value=p003-news-fetcher \
    --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
    --period 3600 --statistics Sum,Average \
    --region ap-northeast-1 --output table
done

# カスタムメトリクス
aws cloudwatch get-metric-statistics \
  --namespace P003/Fetcher --metric-name FetcherSavedArticles \
  --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 3600 --statistics Sum \
  --region ap-northeast-1 --output table
```

**Invocations が 0 = EventBridge Rule が発火していない / Lambda が無効化されている**
**Invocations > 0 かつ Errors > 0 = Lambda 内部エラー**
**Invocations > 0, Errors = 0, FetcherSavedArticles = 0 = 処理は走るが保存に進んでいない**

### Step 3: EventBridge Rule の状態確認（Step 2 で Invocations=0 のとき）

```bash
aws events list-rules --region ap-northeast-1 --query "Rules[?contains(Name,'fetcher') || contains(Name,'p003')].[Name,State,ScheduleExpression]" --output table
aws events list-targets-by-rule --rule <RULE_NAME> --region ap-northeast-1
```

### Step 4: S3 publish の状態確認

```bash
aws s3api head-object --bucket <BUCKET_NAME> --key topics.json --region ap-northeast-1
aws s3api list-objects-v2 --bucket <BUCKET_NAME> --prefix snap/ --query "Contents[?LastModified>'2026-05-01T00:00:00Z'].[Key,LastModified,Size]" --output table
```

バケット名は `projects/P003-news-timeline/lambda/fetcher/config.py` の `S3_BUCKET` を確認。

## 想定される根本原因と恒久対処

| 原因仮説 | 検出方法 | 恒久対処 |
|---|---|---|
| 外部 RSS フィードのいずれかがタイムアウトして Lambda 全体が時間切れ | Logs に `Task timed out after` または特定 URL での `urlopen timeout` | 個別フィードに timeout 上限 + `concurrent.futures` の `wait timeout`。1 フィード失敗で全体停止しないよう per-feed try/except + 部分 commit |
| AI API レート/エラーで processor が無限リトライ | Logs に `429` / `RetryError` の連発 | リトライ上限を絶対化（`max_retries=2` 等）、超えたら skip して save に進む |
| DynamoDB / S3 への書き込みが ProvisionedThroughputExceeded | Logs に `ThrottlingException` | exponential backoff + jitter、または on-demand 切替（PO 確認必要） |
| EventBridge Rule が Disable されている | `aws events list-rules` で State=DISABLED | `aws events enable-rule` + IaC（`scripts/deploy.sh` 関連 or terraform）に rule state を明文化 |
| Lambda タイムアウト設定が短すぎる（300s 等） | get-function-configuration で Timeout 確認 + Logs に `Task timed out` | Timeout を 600s 〜 900s に拡張 + 主ループ wallclock guard（CLAUDE.md 必須ルール）`context.get_remaining_time_in_millis()` で break |
| 新しい RSS フィードのフォーマットエラーで XML parse 全体失敗 | Logs に `ParseError` / `XMLSyntaxError` | `_parse_rss_items` 周辺を per-feed try/except で囲い、エラーフィードは記録して skip |

**band-aid 厳禁**（CLAUDE.md「対症療法ではなく根本原因」）。再発防止策を必ず仕組み化する：

- 失敗パターンを `docs/lessons-learned.md` に Why1〜Why5 + 仕組み的対策 3 つ以上で記録
- `docs/lessons-learned.md` の「横展開チェックリスト」表に 1 行追加（実装ファイルパス付き）
- 再発検知のための CI / SLI / アラートを追加または強化

## PR 要件

- ブランチ名: `fix/T2026-0502-G-fetcher-lambda-recovery`
- 1 PR = 1 task（複数タスク混ぜない）
- commit メッセージ:
  ```
  fix: T2026-0502-G fetcher Lambda <根本原因サマリ>

  <変更内容詳細>

  Verified: https://flotopic.com/api/topics.json:200:<JST timestamp>
  Verified-Effect: freshness:<旧staleness>min→<新staleness>min:<JST timestamp>
  ```
- `Verified:` / `Verified-Effect:` 行は commit-msg hook で物理 reject される。必ず付ける
- PR description に: 原因 / 対処 / 検証ログ / Lessons-learned エントリーへのリンク
- `gh pr merge --squash --auto` で auto-merge 設定

## 完了報告

main へ merge 後、以下を順に実行：

```bash
bash done.sh T2026-0502-G https://flotopic.com/api/topics.json
bash scripts/verify_effect.sh freshness                  # SLI 改善を数値で確認
```

`verify_effect.sh freshness` が SLI 改善を確認したら、TASKS.md の T2026-0502-G を取消線処理（`done.sh` 内で自動）。WORKING.md の `[Code]` 行も自動削除される。

最後に **`https://flotopic.com/` をブラウザで開いて目視確認**。トピックが新しく更新されていることを確認してから完了報告。

## 中断ルール

- 「実装の前提が根本的に変わった場合」のみ中断して PO 確認
- 新規 AWS リソース作成 / 課金変動 / 不可逆操作（DB drop 等）は事前確認
- それ以外は完走する。文言の好み・デザインの揺らぎで止まらない

## 関連ファイル

- `projects/P003-news-timeline/lambda/fetcher/handler.py` — fetcher 本体
- `projects/P003-news-timeline/lambda/fetcher/config.py` — RSS_FEEDS / S3_BUCKET
- `projects/P003-news-timeline/lambda/processor/handler.py` — AI 処理本体
- `.github/workflows/fetcher-health-check.yml` — 健全性監視
- `.github/workflows/freshness-check.yml` — 鮮度 SLI
- `scripts/setup_fetcher_alarm.sh` — CloudWatch Alarm 定義
- `docs/lessons-learned.md` — Why 構造化 + 横展開チェックリスト
- `docs/runbooks/rollback.md` — 緊急ロールバック手順

## 参考: 直近の関連 commit

- `affd1ba8` feat: T2026-0502-E session_bootstrap.sh §1c
- `a6ed463e` fix: docs/rules-rewrite-proposal の PII 違反解消
- `T2026-0430-H` で fetcher-health-check.yml を追加した（Decimal バグで 3 日間気付かなかった経験から）

---

**タスク ID**: T2026-0502-G
**優先度**: 🔴 最優先（フェーズ2 の前提・本番インシデント継続中）
**期限**: 即時（topics.json 鮮度 < 90 分に戻すまでセッション継続）
**モデル**: Sonnet
