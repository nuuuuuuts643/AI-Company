#!/bin/bash
# ai-company-memory DynamoDB操作スクリプト
# 使い方:
#   ./memory.sh write <type> <id> <title> <body>
#   ./memory.sh read <type> <id>
#   ./memory.sh list <type>
#   ./memory.sh delete <type> <id>

TABLE="ai-company-memory"
REGION="ap-northeast-1"
NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

cmd=$1
shift

case "$cmd" in
  write)
    memory_type="$1"
    memory_id="$2"
    title="$3"
    body="$4"
    aws dynamodb put-item \
      --table-name "$TABLE" \
      --region "$REGION" \
      --item "{
        \"memory_type\": {\"S\": \"$memory_type\"},
        \"memory_id\":   {\"S\": \"$memory_id\"},
        \"title\":       {\"S\": \"$title\"},
        \"body\":        {\"S\": \"$body\"},
        \"updated_at\":  {\"S\": \"$NOW\"}
      }" \
      --output json
    echo "✅ written: [$memory_type] $memory_id"
    ;;

  read)
    memory_type="$1"
    memory_id="$2"
    aws dynamodb get-item \
      --table-name "$TABLE" \
      --region "$REGION" \
      --key "{\"memory_type\":{\"S\":\"$memory_type\"},\"memory_id\":{\"S\":\"$memory_id\"}}" \
      --output json
    ;;

  list)
    memory_type="$1"
    aws dynamodb query \
      --table-name "$TABLE" \
      --region "$REGION" \
      --key-condition-expression "memory_type = :t" \
      --expression-attribute-values "{\":t\":{\"S\":\"$memory_type\"}}" \
      --projection-expression "memory_id, title, updated_at" \
      --output table
    ;;

  delete)
    memory_type="$1"
    memory_id="$2"
    aws dynamodb delete-item \
      --table-name "$TABLE" \
      --region "$REGION" \
      --key "{\"memory_type\":{\"S\":\"$memory_type\"},\"memory_id\":{\"S\":\"$memory_id\"}}"
    echo "🗑 deleted: [$memory_type] $memory_id"
    ;;

  *)
    echo "Usage: $0 {write|read|list|delete} ..."
    exit 1
    ;;
esac
