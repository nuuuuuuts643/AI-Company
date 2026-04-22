#!/usr/bin/env python3
"""
_governance_check.py — AI-Company 統合ガバナンス 共通自己停止モジュール

## 概要
全エージェント（CEO, Secretary, DevOps, Marketing, Revenue, Editorial, SEO,
Security, Legal）がスクリプト先頭でimportして使う共通モジュール。

DynamoDB `agent_status` テーブルを確認し、停止フラグが立っていれば
エラーメッセージを出力してsys.exit(0)で自己停止する。

## 使い方（各エージェントスクリプト先頭に追加）
    from _governance_check import check_agent_status
    check_agent_status("ceo")  # "paused" または "stopped" なら即終了

## DynamoDB テーブル仕様
- Table: ai-company-agent-status
- PK: agent_name (str) — 例: "ceo", "secretary", "security"
- status: "active" | "paused" | "stopped"
- reason: 停止理由テキスト
- paused_at / stopped_at: ISO8601 タイムスタンプ
- resume_requires: "manual" | "auto" — "manual"なら手動解除が必要
"""

import os
import sys
from datetime import datetime, timezone

AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "ap-northeast-1")
AGENT_STATUS_TABLE = "ai-company-agent-status"


def check_agent_status(agent_name: str) -> bool:
    """
    DynamoDBのagent_statusを確認。停止フラグがあれば自己停止。

    Args:
        agent_name: エージェント識別名 (例: "ceo", "secretary", "security")

    Returns:
        True — activeなので続行OK
        ※ paused / stopped の場合はsys.exit(0)で終了するため返らない
    """
    try:
        import boto3
        dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
        table = dynamodb.Table(AGENT_STATUS_TABLE)
        resp = table.get_item(Key={"agent_name": agent_name})
        item = resp.get("Item")

        if item is None:
            # テーブルにエントリなし → アクティブとみなして続行
            print(f"[governance] {agent_name}: ステータス未登録 → active扱いで続行")
            return True

        status = item.get("status", "active")
        reason = item.get("reason", "（理由なし）")
        resume_requires = item.get("resume_requires", "manual")

        if status == "stopped":
            print(
                f"[governance] ⛔ {agent_name} は STOPPED 状態です。\n"
                f"  理由: {reason}\n"
                f"  再起動条件: {resume_requires}\n"
                f"  AuditAIの判断を確認し、手動で status を 'active' に変更してください。"
            )
            sys.exit(0)

        if status == "paused":
            print(
                f"[governance] ⏸️  {agent_name} は PAUSED 状態です。\n"
                f"  理由: {reason}\n"
                f"  自動再開条件: {resume_requires}\n"
                f"  MEDIUM問題が解消されたら AuditAI が自動的にactiveに戻します。"
            )
            sys.exit(0)

        # active
        return True

    except ImportError:
        print("[governance] boto3未インストール → ガバナンスチェックをスキップして続行")
        return True
    except Exception as e:
        # DynamoDB接続失敗はブロッカーにしない（可用性優先）
        print(f"[governance] ガバナンスチェック失敗（続行）: {e}")
        return True


def set_agent_status(
    agent_name: str,
    status: str,
    reason: str,
    severity: str = "LOW",
    resume_requires: str = "auto",
) -> bool:
    """
    AuditAI / SecurityAI が呼び出す: エージェントの状態を更新する。

    Args:
        agent_name: 対象エージェント名
        status: "active" | "paused" | "stopped"
        reason: 変更理由（Slackにも通知される）
        severity: "LOW" | "MEDIUM" | "HIGH"
        resume_requires: "auto" | "manual"

    Returns:
        True on success, False on failure
    """
    try:
        import boto3
        dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
        table = dynamodb.Table(AGENT_STATUS_TABLE)
        now = datetime.now(timezone.utc).isoformat()

        item = {
            "agent_name": agent_name,
            "status": status,
            "reason": reason,
            "severity": severity,
            "resume_requires": resume_requires,
            "updated_at": now,
        }
        if status == "paused":
            item["paused_at"] = now
        elif status == "stopped":
            item["stopped_at"] = now
        elif status == "active":
            item["resumed_at"] = now

        table.put_item(Item=item)
        print(f"[governance] {agent_name} ステータスを '{status}' に更新 (severity={severity})")
        return True

    except Exception as e:
        print(f"[governance] set_agent_status失敗: {e}")
        return False


def get_all_agent_statuses() -> list:
    """
    全エージェントの現在ステータスを取得する（AuditAI用）。

    Returns:
        [{"agent_name": str, "status": str, "reason": str, ...}, ...]
    """
    try:
        import boto3
        dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
        table = dynamodb.Table(AGENT_STATUS_TABLE)
        resp = table.scan()
        return resp.get("Items", [])
    except Exception as e:
        print(f"[governance] get_all_agent_statuses失敗: {e}")
        return []


def ensure_agent_status_table_exists() -> bool:
    """
    agent_statusテーブルが存在しなければ作成する（初回セットアップ用）。
    冪等: 既存テーブルがある場合は何もしない。
    """
    try:
        import boto3
        from botocore.exceptions import ClientError
        client = boto3.client("dynamodb", region_name=AWS_REGION)
        try:
            client.describe_table(TableName=AGENT_STATUS_TABLE)
            print(f"[governance] テーブル {AGENT_STATUS_TABLE} は既存")
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                raise
        # テーブル作成
        client.create_table(
            TableName=AGENT_STATUS_TABLE,
            KeySchema=[{"AttributeName": "agent_name", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "agent_name", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        waiter = client.get_waiter("table_exists")
        waiter.wait(TableName=AGENT_STATUS_TABLE)
        print(f"[governance] テーブル {AGENT_STATUS_TABLE} を作成しました")
        return True
    except Exception as e:
        print(f"[governance] テーブル作成失敗: {e}")
        return False


# --- スタンドアロン実行: テーブル初期化 + 全エージェントをactiveで登録 ---
if __name__ == "__main__":
    AGENTS = [
        "ceo", "secretary", "devops", "marketing",
        "revenue", "editorial", "seo", "security", "legal", "audit"
    ]
    print("=== AI-Company ガバナンス テーブル初期化 ===")
    if ensure_agent_status_table_exists():
        try:
            import boto3
            dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
            table = dynamodb.Table(AGENT_STATUS_TABLE)
            now = datetime.now(timezone.utc).isoformat()
            for agent in AGENTS:
                # 既存エントリを上書きしない（初回のみ）
                resp = table.get_item(Key={"agent_name": agent})
                if "Item" not in resp:
                    table.put_item(Item={
                        "agent_name": agent,
                        "status": "active",
                        "reason": "初期登録",
                        "severity": "LOW",
                        "resume_requires": "auto",
                        "updated_at": now,
                    })
                    print(f"  ✅ {agent}: active で登録")
                else:
                    print(f"  - {agent}: 既存エントリあり（スキップ）")
        except Exception as e:
            print(f"初期化エラー: {e}")
    print("=== 完了 ===")
