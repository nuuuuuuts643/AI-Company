#!/usr/bin/env python3
"""
_rule_engine.py — AI-Company 共通ルールエンジン

Claude呼び出し回数: 0回/実行 (通常時)
条件: HIGH severity かつ DynamoDB未学習パターン のみ外部AI判断を推奨

## 概要
全エージェントが import して使う共通ルール評価モジュール。
- ルール定義: コード内ハードコード + DynamoDB動的読み込み（コード変更なしでルール追加可能）
- 誤検知学習: フィードバックを DynamoDB ai-company-memory に記録
- Claude呼び出し判断: HIGH severity + 未学習パターンのみ True を返す

## DynamoDB テーブル
- ai-company-memory: 誤検知パターン・学習済みルールを保存
  PK: "RULE_ENGINE#{agent_name}"
  SK: "FP#{fingerprint}"     ← 誤検知パターン
      "RULE#{rule_id}"       ← 動的ルール定義

## 使い方
    from _rule_engine import RuleEngine, Finding

    engine = RuleEngine("devops")
    findings = engine.evaluate({"github_failures": 4, "consecutive": True})
    if engine.should_call_claude(findings):
        # HIGH severity + 未知パターンのみここに来る（月数回想定）
        analysis = ask_claude(...)
    else:
        # 通常時: Claudeを呼ばずにSlack通知を組み立てる
        msg = engine.build_slack_summary(findings, "開発監視レポート")

## 最終更新: 2026-04-22
"""

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "ap-northeast-1")
MEMORY_TABLE = "ai-company-memory"


# =============================================================================
# Finding: ルール評価結果の単位
# =============================================================================

@dataclass
class Finding:
    """ルール評価で検出された1件の問題"""
    pattern_id: str       # ルール識別子 (例: "github_consecutive_failure")
    severity: str         # "HIGH" | "MEDIUM" | "LOW"
    message: str          # 人間向けメッセージ
    context: dict = field(default_factory=dict)  # 詳細コンテキスト

    def fingerprint(self) -> str:
        """
        パターンIDとコンテキストから一意のハッシュを生成。
        誤検知キャッシュのキーとして使用。
        コンテキストが同じなら同じfingerprintになる。
        """
        key = f"{self.pattern_id}:{json.dumps(self.context, sort_keys=True, ensure_ascii=False)}"
        return hashlib.md5(key.encode("utf-8")).hexdigest()[:12]

    def fingerprint_loose(self) -> str:
        """
        パターンIDのみのハッシュ（緩やかなマッチング用）。
        コンテキストが変わっても同じパターンとして扱う。
        """
        return hashlib.md5(self.pattern_id.encode("utf-8")).hexdigest()[:12]

    def to_dict(self) -> dict:
        return {
            "pattern_id": self.pattern_id,
            "severity": self.severity,
            "message": self.message,
            "context": self.context,
            "fingerprint": self.fingerprint(),
        }


# =============================================================================
# RuleEngine: 共通ルール評価エンジン
# =============================================================================

class RuleEngine:
    """
    エージェント固有のルールを評価し、Finding を生成する共通エンジン。

    設計方針:
    - ルールはコード内 + DynamoDB から読み込む（動的拡張可能）
    - 誤検知パターンを DynamoDB に学習・蓄積する
    - should_call_claude() が True のときだけ外部AI呼び出しを許可する
    """

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self._false_positive_cache: dict[str, bool] = {}  # fingerprint → True/False
        self._dynamic_rules: dict = {}                     # DynamoDBから読んだ追加ルール
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """遅延ロード: 初回アクセス時にDynamoDBから読み込む"""
        if self._loaded:
            return
        self._loaded = True
        self._load_from_dynamodb()

    def _load_from_dynamodb(self) -> None:
        """DynamoDBから誤検知パターンと動的ルールを読み込む"""
        try:
            import boto3
            dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
            table = dynamodb.Table(MEMORY_TABLE)

            # PK = "RULE_ENGINE#{agent_name}" で始まる全エントリを取得
            pk = f"RULE_ENGINE#{self.agent_name}"
            resp = table.query(
                KeyConditionExpression="pk = :pk",
                ExpressionAttributeValues={":pk": pk},
            )
            items = resp.get("Items", [])

            for item in items:
                sk = item.get("sk", "")
                if sk.startswith("FP#"):
                    # 誤検知パターン
                    fp_key = sk[3:]  # "FP#" の後ろ
                    self._false_positive_cache[fp_key] = True
                elif sk.startswith("RULE#"):
                    # 動的ルール定義
                    rule_id = sk[5:]
                    try:
                        rule_def = json.loads(item.get("rule_json", "{}"))
                        self._dynamic_rules[rule_id] = rule_def
                    except Exception:
                        pass

            fp_count = len([k for k in [item.get("sk","") for item in items] if k.startswith("FP#")])
            rule_count = len(self._dynamic_rules)
            print(f"[rule_engine/{self.agent_name}] "
                  f"DynamoDB読み込み完了: 誤検知={fp_count}件, 動的ルール={rule_count}件")

        except ImportError:
            print(f"[rule_engine/{self.agent_name}] boto3未インストール → DynamoDB読み込みスキップ")
        except Exception as e:
            print(f"[rule_engine/{self.agent_name}] DynamoDB読み込み失敗（継続）: {e}")

    def get_dynamic_rules(self) -> dict:
        """DynamoDBから読み込んだ動的ルールを返す"""
        self._ensure_loaded()
        return self._dynamic_rules.copy()

    # -------------------------------------------------------------------------
    # 誤検知学習
    # -------------------------------------------------------------------------

    def is_known_false_positive(self, finding: Finding) -> bool:
        """
        DynamoDBの学習データでこのFindingが誤検知かどうか判断。
        - 厳密マッチ（fingerprint）または緩やかマッチ（pattern_idのみ）で判定
        """
        self._ensure_loaded()
        fp = finding.fingerprint()
        fp_loose = finding.fingerprint_loose()
        return (
            self._false_positive_cache.get(fp, False)
            or self._false_positive_cache.get(fp_loose, False)
        )

    def learn(self, finding: Finding, was_false_positive: bool) -> bool:
        """
        フィードバックをDynamoDBに記録してルールを改善する。

        Args:
            finding: 対象のFinding
            was_false_positive: True=誤検知として記録（以降スキップ）

        Returns:
            True on success
        """
        self._ensure_loaded()
        try:
            import boto3
            dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
            table = dynamodb.Table(MEMORY_TABLE)

            fp = finding.fingerprint()
            pk = f"RULE_ENGINE#{self.agent_name}"
            sk = f"FP#{fp}"

            if was_false_positive:
                table.put_item(Item={
                    "pk": pk,
                    "sk": sk,
                    "pattern_id": finding.pattern_id,
                    "message": finding.message,
                    "context_json": json.dumps(finding.context, ensure_ascii=False),
                    "learned_at": datetime.now(timezone.utc).isoformat(),
                    "agent": self.agent_name,
                    "type": "false_positive",
                })
                self._false_positive_cache[fp] = True
                print(f"[rule_engine/{self.agent_name}] 誤検知学習: "
                      f"{finding.pattern_id} ({fp})")
            else:
                # 真陽性: 誤検知記録を削除（もし存在すれば）
                table.delete_item(Key={"pk": pk, "sk": sk})
                self._false_positive_cache.pop(fp, None)
                print(f"[rule_engine/{self.agent_name}] 真陽性確認: "
                      f"{finding.pattern_id} ({fp})")
            return True

        except Exception as e:
            print(f"[rule_engine/{self.agent_name}] learn失敗: {e}")
            return False

    def learn_pattern(self, pattern_id: str, description: str) -> bool:
        """
        特定のパターンIDを誤検知として一括登録（コンテキスト不問）。
        例: 毎週月曜のLambdaコールドスタートエラーを正常として学習。
        """
        self._ensure_loaded()
        dummy_finding = Finding(
            pattern_id=pattern_id,
            severity="LOW",
            message=description,
            context={},
        )
        fp_loose = dummy_finding.fingerprint_loose()
        try:
            import boto3
            dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
            table = dynamodb.Table(MEMORY_TABLE)
            pk = f"RULE_ENGINE#{self.agent_name}"
            sk = f"FP#{fp_loose}"
            table.put_item(Item={
                "pk": pk,
                "sk": sk,
                "pattern_id": pattern_id,
                "message": description,
                "learned_at": datetime.now(timezone.utc).isoformat(),
                "agent": self.agent_name,
                "type": "pattern_suppress",
                "loose_match": True,
            })
            self._false_positive_cache[fp_loose] = True
            print(f"[rule_engine/{self.agent_name}] パターン抑制登録: {pattern_id}")
            return True
        except Exception as e:
            print(f"[rule_engine/{self.agent_name}] learn_pattern失敗: {e}")
            return False

    # -------------------------------------------------------------------------
    # Claude呼び出し判断
    # -------------------------------------------------------------------------

    def should_call_claude(self, findings: list) -> bool:
        """
        Claude呼び出しが本当に必要かどうかを判断する。

        条件: HIGH severity かつ 誤検知でないパターン が1件以上あるときのみ True。
        これにより通常時はClaude呼び出しゼロを実現する。

        Returns:
            True  → Claude呼び出しを推奨（月数回想定）
            False → ルールベース処理のみで十分（通常時）
        """
        self._ensure_loaded()
        for f in findings:
            if f.severity == "HIGH" and not self.is_known_false_positive(f):
                return True
        return False

    # -------------------------------------------------------------------------
    # Slackメッセージ組み立て（Claude不要）
    # -------------------------------------------------------------------------

    def build_slack_summary(
        self,
        findings: list,
        header: str,
        timestamp: Optional[str] = None,
    ) -> str:
        """
        Findingリストから Slackメッセージを組み立てる。
        Claudeを使わず、Pythonテンプレートエンジン的に構成する。

        Args:
            findings: Finding のリスト
            header: メッセージヘッダーテキスト
            timestamp: 日時文字列（省略時は現在時刻）

        Returns:
            Slack Block Kit 互換のテキスト
        """
        ts = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        if not findings:
            return f"✅ *{header}* ({ts})\n全チェック通過 — 問題なし"

        high   = [f for f in findings if f.severity == "HIGH"]
        medium = [f for f in findings if f.severity == "MEDIUM"]
        low    = [f for f in findings if f.severity == "LOW"]

        # 全体ステータス
        if high:
            top_icon = "🚨"
            top_status = f"要対応 {len(high)}件 (HIGH)"
        elif medium:
            top_icon = "⚠️"
            top_status = f"要確認 {len(medium)}件 (MEDIUM)"
        else:
            top_icon = "ℹ️"
            top_status = f"通知 {len(low)}件 (LOW)"

        lines = [
            f"{top_icon} *{header}* ({ts})",
            f"ステータス: {top_status}",
            "",
        ]

        severity_map = [
            ("🚨", "HIGH",   high),
            ("⚠️",  "MEDIUM", medium),
            ("ℹ️",  "LOW",    low),
        ]
        for icon, label, items in severity_map:
            for f in items:
                lines.append(f"{icon} `[{label}]` {f.message}")
                # コンテキスト詳細（最大2行）
                ctx_items = list(f.context.items())[:2]
                for k, v in ctx_items:
                    lines.append(f"   └ {k}: {v}")

        return "\n".join(lines)

    def build_slack_ok(self, header: str, summary: str, timestamp: Optional[str] = None) -> str:
        """正常時の簡潔なSlackメッセージ"""
        ts = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        return f"✅ *{header}* ({ts})\n{summary}"

    # -------------------------------------------------------------------------
    # 動的ルール管理（DynamoDBへの書き込み）
    # -------------------------------------------------------------------------

    def add_rule(self, rule_id: str, rule_def: dict) -> bool:
        """
        新しいルールをDynamoDBに追加する（コード変更なしでルール追加可能）。

        Args:
            rule_id: ルール識別子
            rule_def: ルール定義dict（patterns, severity, action等）

        Returns:
            True on success
        """
        try:
            import boto3
            dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
            table = dynamodb.Table(MEMORY_TABLE)
            pk = f"RULE_ENGINE#{self.agent_name}"
            sk = f"RULE#{rule_id}"
            table.put_item(Item={
                "pk": pk,
                "sk": sk,
                "rule_id": rule_id,
                "rule_json": json.dumps(rule_def, ensure_ascii=False),
                "added_at": datetime.now(timezone.utc).isoformat(),
                "agent": self.agent_name,
            })
            self._dynamic_rules[rule_id] = rule_def
            print(f"[rule_engine/{self.agent_name}] ルール追加: {rule_id}")
            return True
        except Exception as e:
            print(f"[rule_engine/{self.agent_name}] add_rule失敗: {e}")
            return False

    # -------------------------------------------------------------------------
    # ユーティリティ
    # -------------------------------------------------------------------------

    def dedup_findings(self, findings: list) -> list:
        """fingerprintが重複するFindingを除去する"""
        seen: set[str] = set()
        result = []
        for f in findings:
            fp = f.fingerprint()
            if fp not in seen:
                seen.add(fp)
                result.append(f)
        return result

    def filter_known_false_positives(self, findings: list) -> tuple[list, list]:
        """
        FindingリストをDynamoDB学習データでフィルタリングする。

        Returns:
            (real_findings, suppressed_findings)
        """
        self._ensure_loaded()
        real = []
        suppressed = []
        for f in findings:
            if self.is_known_false_positive(f):
                suppressed.append(f)
                print(f"[rule_engine/{self.agent_name}] 既知誤検知のためスキップ: "
                      f"{f.pattern_id}")
            else:
                real.append(f)
        return real, suppressed

    def stats(self) -> dict:
        """学習済みデータの統計"""
        self._ensure_loaded()
        return {
            "agent": self.agent_name,
            "false_positive_patterns": len(self._false_positive_cache),
            "dynamic_rules": len(self._dynamic_rules),
        }
