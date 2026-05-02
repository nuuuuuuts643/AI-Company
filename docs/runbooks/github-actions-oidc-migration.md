# GitHub Actions OIDC 移行 runbook (T2026-0502-SEC10)

> **対象**: 10 workflow が `secrets.AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` で長寿命キー使用 → AWS OIDC + IAM Role assumption に移行。
> **移行戦略**: 段階的。まず PO が AWS OIDC IdP + IAM Role を作成 → 新方式テスト workflow を 1 つ動作確認 → 全 workflow 一括書換 → 最後に長寿命 access key 削除。
>
> **メリット**: ①長寿命キー漏洩リスク消失 ②IAM Role 単位で workflow ごとの権限制御可能 ③CloudTrail で「どの workflow run」が誰の権限で何したか完全追跡

---

## 影響を受ける workflow (10 ファイル)

| ファイル | 用途 | 必要な権限 |
|---|---|---|
| `freshness-check.yml` | SLI 計測 + Slack 通知 | `cloudwatch:GetMetricStatistics` + DynamoDB scan + S3 read |
| `bluesky-agent.yml` | Bluesky 投稿 | DynamoDB read/write (ai-company-bluesky-posts) |
| `weekly-digest.yml` | 週次サマリ | S3 + DynamoDB read |
| `quality-heal.yml` | 品質自動修復 | S3 read/write + DynamoDB |
| `security-audit.yml` | 週次セキュリティ監査 | IAM read + S3 read |
| `sli-keypoint-fill-rate.yml` | SLI 計測 | DynamoDB scan + S3 read |
| `editorial-agent.yml` | 編集 AI | DynamoDB + S3 |
| `deploy-trigger-watchdog.yml` | deploy 失敗監視 | CloudWatch + Lambda invoke |
| `deploy-lambdas.yml` | Lambda デプロイ | Lambda update-function-code (※特権) |
| `deploy-p003.yml` | Frontend S3 デプロイ | S3 sync + CloudFront invalidation |

`deploy-lambdas.yml` は特権 (Lambda コード書き換え) なので別 IAM Role に分けるのが望ましい。

---

## 手順

### 1️⃣ AWS IAM OIDC Identity Provider を作成 (PO・1 回のみ)

```bash
# Provider 作成 (GitHub Actions 公式)
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 \
  --region us-east-1
```

⚠️ thumbprint は GitHub の TLS 証明書から計算される値で、稀に変わる。最新は GitHub docs を参照: https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services

### 2️⃣ IAM Role を 2 つ作成 (PO)

#### Role A: 一般 workflow 用 (read-only + 限定 write)

`GitHubActionsRole-Flotopic-Standard`:

```bash
TRUST_POLICY=$(cat <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::946554699567:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:nuuuuuuts643/AI-Company:*"
        }
      }
    }
  ]
}
EOF
)

aws iam create-role \
  --role-name GitHubActionsRole-Flotopic-Standard \
  --assume-role-policy-document "$TRUST_POLICY"

# 権限: 既存 lambda role と同様の最小権限を attach (内容は deploy.sh の flotopic-least-privilege と同等)
aws iam put-role-policy \
  --role-name GitHubActionsRole-Flotopic-Standard \
  --policy-name flotopic-actions-standard \
  --policy-document file://flotopic-actions-standard.json
```

#### Role B: deploy 用 (Lambda update-function-code 特権)

`GitHubActionsRole-Flotopic-Deploy`:

```bash
# Trust policy は branch を main 限定にして特権を絞る (本番ブランチからのみ deploy 可)
TRUST_POLICY_DEPLOY=$(cat <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::946554699567:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:sub": "repo:nuuuuuuts643/AI-Company:ref:refs/heads/main"
        }
      }
    }
  ]
}
EOF
)
```

### 3️⃣ 1 workflow をパイロット書換 (Code セッション・本 PR のサンプル参照)

例: `freshness-check.yml` を OIDC 方式に書換 (env fallback あり):

```yaml
permissions:
  id-token: write   # ← OIDC で必須
  contents: read

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: AWS 認証 (OIDC を優先・無ければ legacy access key fallback)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          # 移行期間: secrets.AWS_ROLE_ARN が設定されていれば OIDC、無ければ legacy key を使う
          role-to-assume: ${{ secrets.AWS_ROLE_ARN_STANDARD }}
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ap-northeast-1
```

`aws-actions/configure-aws-credentials@v4` は `role-to-assume` が指定されていれば OIDC を優先するため、両方書いておけば安全に移行できる。

### 4️⃣ 動作確認 → 残り 9 workflow も同パターンで書換

`AWS_ROLE_ARN_STANDARD` / `AWS_ROLE_ARN_DEPLOY` を GitHub Secrets に設定したら、aws-actions/configure-aws-credentials@v4 が自動で OIDC を使う。

### 5️⃣ 旧 access key を Deactivate

24-48h 全 workflow が green で動いていることを確認後:

```bash
# IAM ユーザーから access key を取得
aws iam list-access-keys --user-name <github-actions-user>

# 該当 access key を deactivate (削除はしない・問題発生時の rollback 用)
aws iam update-access-key \
  --user-name <github-actions-user> \
  --access-key-id AKIAxxx \
  --status Inactive
```

### 6️⃣ 1 週間問題なければ access key を完全削除 + GitHub Secrets からも削除

```bash
aws iam delete-access-key \
  --user-name <github-actions-user> \
  --access-key-id AKIAxxx

# GitHub UI: Settings → Secrets → AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY を削除
```

最後に workflow から `aws-access-key-id` / `aws-secret-access-key` の行を削除:

```yaml
- uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: ${{ secrets.AWS_ROLE_ARN_STANDARD }}
    aws-region: ap-northeast-1
```

---

## 完了確認

- [ ] `secrets.AWS_ACCESS_KEY_ID` の grep が `.github/workflows/` で 0 件
- [ ] 旧 access key で `aws sts get-caller-identity` が 401
- [ ] 全 10 workflow が直近 1 週間 green
- [ ] CloudTrail で role assumption が記録されている (workflow run id 追跡可能)

---

## ロールバック

旧 access key が active なら、workflow を 1 commit で revert すれば動く。
旧 key を delete してしまった場合は IAM ユーザーで新 access key を発行 → GitHub Secrets 更新。

---

## 参考

- GitHub Actions OIDC: https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect
- aws-actions/configure-aws-credentials: https://github.com/aws-actions/configure-aws-credentials
