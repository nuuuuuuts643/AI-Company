#!/usr/bin/env bash
# scripts/setup_fetcher_alarm.sh
# Fetcher Lambda が連続 2 時間 0 件保存になったら検知するための CloudWatch リソース作成。
#
# 背景:
#   2026-04-30 まで、Decimal バグで 3 日間記事が 0 件保存になっても誰も気づかなかった。
#   freshness SLI は 12 時間に 1 回しか走らないため最大 72h の検知遅延が発生。
#   このスクリプトは検知を 72h → 2h に短縮する。
#
# 構成:
#   1. Metric Filter: /aws/lambda/p003-fetcher の [FETCHER_HEALTH] JSON ログから
#      saved_articles の値を抽出 → P003/Fetcher.FetcherSavedArticles に送信。
#   2. CloudWatch Alarm: 過去 2h (4 period × 30min) の Sum < 1 件 → ALARM。
#      → SNS p003-lambda-alerts (既存 email 購読あり)。
#      treat-missing-data=breaching で fetcher 起動すらしてないケースも検知。
#
# 冪等: 既存リソースは上書き。再実行 OK。
#
# 使い方:
#   bash scripts/setup_fetcher_alarm.sh
#   DRY_RUN=1 bash scripts/setup_fetcher_alarm.sh

set -euo pipefail

REGION="${AWS_REGION:-ap-northeast-1}"
ACCOUNT_ID="${AWS_ACCOUNT_ID:-946554699567}"
LOG_GROUP="/aws/lambda/p003-fetcher"
METRIC_FILTER_NAME="FetcherSavedArticles"
METRIC_NAMESPACE="P003/Fetcher"
METRIC_NAME="FetcherSavedArticles"
ALARM_NAME="P003-Fetcher-Zero-Articles-2h"
SNS_TOPIC_ARN="arn:aws:sns:${REGION}:${ACCOUNT_ID}:p003-lambda-alerts"

run() {
  if [[ "${DRY_RUN:-}" == "1" ]]; then
    printf '+ '; printf '%q ' "$@"; printf '\n'
  else
    printf '+ '; printf '%q ' "$@"; printf '\n'
    "$@"
  fi
}

echo "=== Step 1: Metric Filter (${METRIC_FILTER_NAME}) ==="
# fetcher は JSON ログを '[FETCHER_HEALTH] {"event":"fetcher_health","saved_articles":N,...}' で出す。
# CloudWatch Metric Filter の JSON pattern: '{ $.event = "fetcher_health" }'
# metricValue=$.saved_articles で N を抽出。defaultValue=0 で「ログ自体ない」期間も値 0 を埋める。
run aws logs put-metric-filter \
  --region "$REGION" \
  --log-group-name "$LOG_GROUP" \
  --filter-name "$METRIC_FILTER_NAME" \
  --filter-pattern '{ $.event = "fetcher_health" }' \
  --metric-transformations \
    "metricName=${METRIC_NAME},metricNamespace=${METRIC_NAMESPACE},metricValue=\$.saved_articles,defaultValue=0"

echo ""
echo "=== Step 2: CloudWatch Alarm (${ALARM_NAME}) ==="
# fetcher は EventBridge で 30 分おきに走る → 2h で 4 run。
# 4 datapoint 全てで Sum < 1 (= saved_articles=0) なら ALARM。
# treat-missing-data=breaching: メトリクス欠損も「異常」扱い（fetcher 起動失敗）。
run aws cloudwatch put-metric-alarm \
  --region "$REGION" \
  --alarm-name "$ALARM_NAME" \
  --alarm-description "Fetcher Lambda が 2 時間 0 件保存（または起動せず）→ Decimal バグ等の停止検知。72h 遅延だった freshness SLI を 2h に短縮。" \
  --namespace "$METRIC_NAMESPACE" \
  --metric-name "$METRIC_NAME" \
  --statistic Sum \
  --period 1800 \
  --evaluation-periods 4 \
  --datapoints-to-alarm 4 \
  --threshold 1 \
  --comparison-operator LessThanThreshold \
  --treat-missing-data breaching \
  --alarm-actions "$SNS_TOPIC_ARN"

echo ""
echo "=== Step 3: 確認 ==="
run aws logs describe-metric-filters \
  --region "$REGION" \
  --log-group-name "$LOG_GROUP" \
  --filter-name-prefix "$METRIC_FILTER_NAME" \
  --query 'metricFilters[*].[filterName,filterPattern]' \
  --output table

run aws cloudwatch describe-alarms \
  --region "$REGION" \
  --alarm-names "$ALARM_NAME" \
  --query 'MetricAlarms[*].[AlarmName,StateValue,ActionsEnabled]' \
  --output table

echo ""
echo "✅ 完了: ${ALARM_NAME} 登録済み。"
echo "   検知遅延: 72h → 2h"
echo "   通知先: ${SNS_TOPIC_ARN} (email)"
echo "   Slack 並走通知: .github/workflows/fetcher-health-check.yml"
