#!/usr/bin/env bash
# T2026-0428-AO: トピック一括 heal コマンド。
# 対象トピックを DynamoDB で検索して needs_ai_processing=True (pendingAI=True) にセット。
# 既存の AI フィールドは絶対に上書きしない (processor 側 incremental モードで補完)。
#
# 使い方:
#   bash scripts/bulk_heal.sh all            # 全可視トピック
#   bash scripts/bulk_heal.sh no-keypoint    # keyPoint 空のトピック
#   bash scripts/bulk_heal.sh empty          # articleCount=0 (削除候補・heal対象外なので注意)
#   bash scripts/bulk_heal.sh old-schema     # schemaVersion < PROCESSOR_SCHEMA_VERSION
#
# 環境変数:
#   APPLY=1   # 実際に書き込む (デフォルト dry-run)
#
# 動作:
#   bash scripts/bulk_heal.sh no-keypoint           # dry-run
#   APPLY=1 bash scripts/bulk_heal.sh no-keypoint   # 実行

set -euo pipefail

MODE="${1:-}"
APPLY_FLAG=""
if [[ "${APPLY:-0}" == "1" ]]; then
  APPLY_FLAG="--apply"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

case "${MODE}" in
  all)
    echo "[bulk_heal] mode=all: 全可視トピックを heal キューに投入"
    exec python3 "${SCRIPT_DIR}/bulk_heal_python.py" all ${APPLY_FLAG}
    ;;
  no-keypoint)
    echo "[bulk_heal] mode=no-keypoint: keyPoint 空のトピックを heal キューに投入"
    exec python3 "${SCRIPT_DIR}/bulk_heal_python.py" no-keypoint ${APPLY_FLAG}
    ;;
  empty)
    echo "[bulk_heal] mode=empty: articleCount=0 のトピックを cleanup スクリプトで処理"
    exec python3 "${SCRIPT_DIR}/cleanup_all_topics.py" --only EMPTY ${APPLY_FLAG}
    ;;
  old-schema)
    echo "[bulk_heal] mode=old-schema: schemaVersion 古いトピックを heal キューに投入"
    exec python3 "${SCRIPT_DIR}/bulk_heal_python.py" old-schema ${APPLY_FLAG}
    ;;
  "")
    echo "Usage: $0 {all|no-keypoint|empty|old-schema}"
    echo "  APPLY=1 を立てると実書き込み (デフォルト dry-run)"
    exit 1
    ;;
  *)
    echo "Unknown mode: ${MODE}"
    echo "Usage: $0 {all|no-keypoint|empty|old-schema}"
    exit 1
    ;;
esac
