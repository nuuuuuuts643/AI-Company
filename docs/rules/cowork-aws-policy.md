# Cowork × AWS MCP × git ─ 役割分離と多重防御

> 起点: 2026-05-02 PO 観察「Cowork から Claude Code 起動できないんだねぇ」「git 使わなくても良いの？」
> 結論: AWS MCP は **運用観測専用**・コード変更は **必ず git 経由**。物理ガードは git 側 (CI / branch protection) と AWS 側 (IAM) の **多重防御** が正解。
> 本ファイルは CLAUDE.md「セッション役割分担」セクションの詳細版（CLAUDE.md 250 行制約を守るための外出し）。

---

## 1. AWS MCP は git の代替ではない (役割の明確な分離)

**AWS MCP** = `mcp__awslabs_aws-mcp-server__call_aws` で AWS CLI を直接実行できる仕組み。**運用観測・調査専用**として使う。

| 用途 | 例 | OK? |
|---|---|---|
| read 系 | `lambda get-function-configuration` / `cloudwatch get-metric-statistics` / `logs filter-log-events` / `events list-rules` / `s3 list-objects` | ✅ |
| 軽 write 系 | `lambda invoke` (冪等性確認後) / `dynamodb update-item` (運用データ修正) | ✅ |
| **コード書換** | `lambda update-function-code` | ❌ **絶対禁止** |
| **破壊操作** | `dynamodb delete-table` / `s3 rb` / `ec2 terminate-instances` | ❌ 絶対禁止 |
| **新規課金リソース** | `rds create-db-instance` / `ec2 run-instances` 等 | ❌ PO 承認必須 |

**git** = ソースコードのバージョン管理。これは変わらない。
- すべてのコード変更は **PR → CI → GitHub Actions deploy workflow → Lambda 更新** の経路
- AWS MCP で「ぽちっ」とコード書き換えたら git に履歴残らず・ロールバック不能・誰が何変えたか不明
- 「AWS 直に行く」は調査だけ・**修正は必ず git 経由**

---

## 2. API 経由 commit と多重防御 (cowork_commit.py を使う場合)

**前提**: `scripts/cowork_commit.py` は GitHub API (`git/blobs` `git/trees` `git/commits` `git/refs`) で直接 commit を作る。git CLI と同じ commit が main に積まれる（区別不可）。

| チェック | API 経由の挙動 |
|---|---|
| GitHub Actions CI (`.github/workflows/*.yml`) | ✅ 走る (push トリガー発火) |
| branch protection / required status checks | ✅ 適用 |
| auto-merge.yml | ✅ 動く |
| **ローカル `pre-commit` / `commit-msg` hook** | ❌ **スキップされる** (API は hook を呼ばない) |

**多重防御原則**: 必須チェック (PII / 250行 / Verified 行 / Phase-Impact 等) は **必ず GitHub Actions CI に landing する**。ローカル hook だけに頼ると Cowork API 経由で抜ける。

- 新規物理ガード追加 PR は **CI ジョブと ローカル hook の両方** に実装（シングルポイント・オブ・フェイラー回避）
- 提案書 (`docs/rules-rewrite-proposal-2026-05-01.md`) Section 4 A-1 / F-1 / G-2 等の物理化は CI 側必須

---

## 3. 物理ガード × 配置場所マトリクス

| 違反タイプ | git 側 (CI / branch protection) | AWS 側 (IAM / Resource Policy) | 最適配置 |
|---|---|---|---|
| コード変更前チェック (PII / Phase-Impact / 250行) | ✅ CI で強い | ❌ 無関係 | **GitHub Actions CI** + ローカル hook |
| main 直 push 禁止 | ✅ branch protection 100% | ❌ 無関係 | **branch protection** |
| Lambda コード書換 禁止 | ⚠️ 思想のみ | ✅ **IAM Deny で物理** | **AWS IAM (推奨)** |
| DB 破壊禁止 | ⚠️ 思想 | ✅ IAM Deny | **AWS IAM** |
| 新規課金リソース禁止 | ⚠️ 思想 | ✅ SCP / IAM | **AWS SCP / IAM** |
| Lambda runtime エラー | ✅ CI test | ✅ CloudWatch Alarm | **両方 (多重防御)** |

→ **結論: 思想ルールを思想のまま放置せず、CI / IAM / SCP で物理化できないか必ず検討する**。

---

## 4. AWS IAM Deny の物理化候補 (PO 承認待ち)

Cowork ユーザー `arn:aws:iam::946554699567:user/Claude` のポリシーに以下の Deny を追加すれば、CLAUDE.md「思想ルール」を **物理化** できる:

```json
{
  "Effect": "Deny",
  "Action": [
    "lambda:UpdateFunctionCode",
    "lambda:DeleteFunction",
    "dynamodb:DeleteTable",
    "dynamodb:DeleteBackup",
    "s3:DeleteBucket",
    "ec2:TerminateInstances",
    "rds:DeleteDBInstance",
    "iam:DeletePolicy",
    "iam:CreateAccessKey"
  ],
  "Resource": "*"
}
```

**完了条件**: Cowork が `aws lambda update-function-code` を試して `AccessDenied` で reject されることを確認 → 提案書 K-1 思想ルールの物理化第一弾。

---

## 関連ドキュメント

- `CLAUDE.md` セッション役割分担 (本ファイルの要約版)
- `docs/rules-rewrite-proposal-2026-05-01.md` Section 4 (物理ガード追加案)
- `docs/rules-rewrite-proposal-2026-05-01.md` Section 14 (組織として動く Claude)
- `scripts/cowork_commit.py` (FUSE 環境での GitHub API 経由 PR スクリプト)
