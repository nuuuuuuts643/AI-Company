#!/bin/bash
# Slack通知スクリプト
# 使い方: export SLACK_WEBHOOK_URL=https://hooks.slack.com/... && bash company/notify.sh "メッセージ"

MESSAGE="$1"
# SLACK_WEBHOOK_URL は環境変数またはコマンド引数2で渡す
# 例: SLACK_WEBHOOK_URL=https://... bash company/notify.sh "msg"
# 例: bash company/notify.sh "msg" "https://..."
SLACK_WEBHOOK_URL="${2:-$SLACK_WEBHOOK_URL}"

python3 -c "
import urllib.request, json, sys
msg = sys.argv[1]
webhook = sys.argv[2]
data = json.dumps({'text': msg}).encode('utf-8')
req = urllib.request.Request(webhook, data=data, headers={'Content-Type': 'application/json'})
urllib.request.urlopen(req)
print('Slack通知送信完了')
" "$MESSAGE" "$SLACK_WEBHOOK_URL"
