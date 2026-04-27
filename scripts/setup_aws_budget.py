#!/usr/bin/env python3
"""
AWSコストアラート設定スクリプト（一度だけ実行）

使い方:
    python3 scripts/setup_aws_budget.py

内容:
    - 月間コストが $30 を超えた場合にメールアラートを送信する Budget を作成
    - 既に同名の Budget が存在する場合はスキップ（冪等）
    - Budget名: flotopic-monthly-budget
"""

import boto3
import json
import os
from datetime import datetime
from botocore.exceptions import ClientError

BUDGET_NAME = "flotopic-monthly-budget"
ALERT_EMAIL = os.environ.get("ALERT_EMAIL", "")  # PII漏洩対策(2026-04-27): 環境変数経由に変更。ローカル実行時は環境変数を設定すること
MONTHLY_LIMIT_USD = "30.0"

if not ALERT_EMAIL:
    raise SystemExit("ALERT_EMAIL 環境変数が未設定です。export ALERT_EMAIL=... してから実行してください")


def get_account_id() -> str:
    sts = boto3.client("sts")
    return sts.get_caller_identity()["Account"]


def budget_exists(client, account_id: str) -> bool:
    """同名のBudgetが既に存在するか確認する"""
    try:
        paginator = client.get_paginator("describe_budgets")
        for page in paginator.paginate(AccountId=account_id):
            for budget in page.get("Budgets", []):
                if budget["BudgetName"] == BUDGET_NAME:
                    return True
    except ClientError as e:
        print(f"⚠️  Budget一覧の取得に失敗: {e}")
    return False


def create_budget(client, account_id: str) -> None:
    """月間コスト $30 超えのアラートBudgetを作成する"""
    budget = {
        "BudgetName": BUDGET_NAME,
        "BudgetLimit": {
            "Amount": MONTHLY_LIMIT_USD,
            "Unit": "USD",
        },
        "TimeUnit": "MONTHLY",
        "BudgetType": "COST",
        "CostTypes": {
            "IncludeTax": True,
            "IncludeSubscription": True,
            "UseBlended": False,
            "IncludeRefund": False,
            "IncludeCredit": False,
            "IncludeUpfront": True,
            "IncludeRecurring": True,
            "IncludeOtherSubscription": True,
            "IncludeSupport": True,
            "IncludeDiscount": True,
            "UseAmortized": False,
        },
    }

    notifications_with_subscribers = [
        # 実績コストが $30 (100%) を超えたらアラート
        {
            "Notification": {
                "NotificationType": "ACTUAL",
                "ComparisonOperator": "GREATER_THAN",
                "Threshold": 100.0,
                "ThresholdType": "PERCENTAGE",
                "NotificationState": "ALARM",
            },
            "Subscribers": [
                {"SubscriptionType": "EMAIL", "Address": ALERT_EMAIL}
            ],
        },
        # 予測コストが $30 (100%) を超えたらアラート（月末前に警告）
        {
            "Notification": {
                "NotificationType": "FORECASTED",
                "ComparisonOperator": "GREATER_THAN",
                "Threshold": 100.0,
                "ThresholdType": "PERCENTAGE",
                "NotificationState": "ALARM",
            },
            "Subscribers": [
                {"SubscriptionType": "EMAIL", "Address": ALERT_EMAIL}
            ],
        },
        # 実績コストが $21 (70%) を超えたら早期警告
        {
            "Notification": {
                "NotificationType": "ACTUAL",
                "ComparisonOperator": "GREATER_THAN",
                "Threshold": 70.0,
                "ThresholdType": "PERCENTAGE",
                "NotificationState": "ALARM",
            },
            "Subscribers": [
                {"SubscriptionType": "EMAIL", "Address": ALERT_EMAIL}
            ],
        },
    ]

    client.create_budget(
        AccountId=account_id,
        Budget=budget,
        NotificationsWithSubscribers=notifications_with_subscribers,
    )


def main():
    print("=" * 50)
    print("  AWS Budgets コストアラート設定")
    print("=" * 50)
    print(f"  Budget名    : {BUDGET_NAME}")
    print(f"  月間上限    : ${MONTHLY_LIMIT_USD}")
    print(f"  通知先      : {ALERT_EMAIL}")
    print()

    account_id = get_account_id()
    print(f"  AWSアカウント: {account_id}")

    # Budgets は us-east-1 固定
    client = boto3.client("budgets", region_name="us-east-1")

    if budget_exists(client, account_id):
        print(f"\n✅ Budget '{BUDGET_NAME}' は既に存在します（スキップ）")
        return

    try:
        create_budget(client, account_id)
        print(f"\n✅ Budget '{BUDGET_NAME}' を作成しました")
        print(f"   月間コストが ${MONTHLY_LIMIT_USD} (100%) を超えると {ALERT_EMAIL} へメールが届きます")
        print(f"   70% (${float(MONTHLY_LIMIT_USD) * 0.7:.1f}) 超えでも早期警告メールが届きます")
        print(f"   予測コストが上限を超えた場合も通知されます")
    except ClientError as e:
        print(f"\n❌ Budget作成に失敗しました: {e}")
        raise


if __name__ == "__main__":
    main()
