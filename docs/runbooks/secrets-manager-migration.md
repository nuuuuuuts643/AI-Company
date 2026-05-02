# Secrets Manager 移行 runbook (T2026-0502-SEC9)

> **対象**: Lambda env に平文保管していた `ANTHROPIC_API_KEY` / `SLACK_WEBHOOK` を AWS Secrets Manager に移管。
> **コード側準備**: PR #225 で `proc_config.py` / `fetcher/config.py` に Secrets Manager fetch (env fallback 付き) 実装済 → 既存環境では何も変わらず動く。
> **PO アクション**: 下記手順で AWS リソース作成 + Lambda env 設定 → 動作確認 → 古い env 値を削除。

---

## アーキテクチャ

```
旧 (平文 env):
  Lambda env: ANTHROPIC_API_KEY=sk-ant-api03-xxx  ← Lambda 設定読み取り権限を持つ任意 IAM principal が値取得可能

新 (Secrets Manager):
  Lambda env: ANTHROPIC_SECRET_ID=flotopic/anthropic-api-key
  Lambda IAM: secretsmanager:GetSecretValue on flotopic/anthropic-api-key
  Secrets Manager: flotopic/anthropic-api-key = sk-ant-api03-xxx (KMS 暗号化・誰がいつ読んだか CloudTrail で追跡可能)
```

`_load_secret_or_env(secret_id_env, fallback_env)` が両方読みするため、移行期間中は env と secret 両方が共存可能。

---

## 手順

### 1️⃣ Secrets Manager に secret 作成 (PO・AWS Console / CLI)

```bash
# Anthropic API key
aws secretsmanager create-secret \
  --name flotopic/anthropic-api-key \
  --description "Anthropic API key for p003-fetcher / p003-processor" \
  --secret-string "***REDACTED-SEC3***" \
  --region ap-northeast-1

# Slack Webhook (任意・本タスクでは Anthropic 優先)
aws secretsmanager create-secret \
  --name flotopic/slack-webhook \
  --description "Slack incoming webhook for p003-fetcher alerts" \
  --secret-string "https://hooks.slack.com/services/T.../B.../..." \
  --region ap-northeast-1
```

⚠️ 同名 secret が既に存在する場合は `update-secret` で値だけ更新:
```bash
aws secretsmanager update-secret \
  --secret-id flotopic/anthropic-api-key \
  --secret-string "***REDACTED-SEC3***" \
  --region ap-northeast-1
```

### 2️⃣ Lambda IAM Role に secretsmanager:GetSecretValue 権限追加

`deploy.sh` の `flotopic-least-privilege` policy に追加 (本 PR で実装):

```json
{
  "Sid": "SecretsManagerRead",
  "Effect": "Allow",
  "Action": ["secretsmanager:GetSecretValue"],
  "Resource": [
    "arn:aws:secretsmanager:ap-northeast-1:946554699567:secret:flotopic/anthropic-api-key-*",
    "arn:aws:secretsmanager:ap-northeast-1:946554699567:secret:flotopic/slack-webhook-*"
  ]
}
```

deploy-lambdas.yml で次回 deploy 時に IAM が更新される (`bash deploy.sh` のような手動デプロイは不要)。

### 3️⃣ Lambda env に SECRET_ID を設定

`p003-fetcher` / `p003-processor` の env 変数に追加:

```bash
# fetcher
aws lambda update-function-configuration \
  --function-name p003-fetcher \
  --environment "Variables={...既存...,ANTHROPIC_SECRET_ID=flotopic/anthropic-api-key,SLACK_WEBHOOK_SECRET_ID=flotopic/slack-webhook}" \
  --region ap-northeast-1

# processor
aws lambda update-function-configuration \
  --function-name p003-processor \
  --environment "Variables={...既存...,ANTHROPIC_SECRET_ID=flotopic/anthropic-api-key}" \
  --region ap-northeast-1
```

このタイミングで `_load_secret_or_env` は Secrets Manager から取得し始める。
失敗時は env fallback (既存の `ANTHROPIC_API_KEY` 平文) が使われるので動作は止まらない。

### 4️⃣ 動作確認

次の fetcher 起動 (30 分毎) を待ち、CloudWatch Logs で:

```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/p003-fetcher \
  --filter-pattern "[SEC9]" \
  --start-time $(($(date +%s)*1000 - 3600000)) \
  --region ap-northeast-1
```

- ログに `[SEC9]` が **出ない** = Secrets Manager 取得成功 (正常)
- ログに `[SEC9] Secrets Manager fetch failed ...` = IAM 権限不足 → 手順 2 を再実行

processor も同様 (`/aws/lambda/p003-processor`)。

### 5️⃣ 旧 env 値を削除 (Secrets Manager から取れていることを確認後)

最低 24 時間 fetcher / processor が正常動作したら、Lambda env から平文値を削除:

```bash
aws lambda update-function-configuration \
  --function-name p003-fetcher \
  --environment "Variables={...既存から ANTHROPIC_API_KEY と SLACK_WEBHOOK だけ削除...,ANTHROPIC_SECRET_ID=flotopic/anthropic-api-key,SLACK_WEBHOOK_SECRET_ID=flotopic/slack-webhook}" \
  --region ap-northeast-1
```

⚠️ env 全置換になる (既存の他 env も忘れず含める)。`ci_lambda_merge_env.py` を改修して `ANTHROPIC_API_KEY` を出力しない仕様に変えるのが恒久対処。

### 6️⃣ deploy.sh / deploy-lambdas.yml も追従

- `deploy.sh` の Lambda 起動時 env から `ANTHROPIC_API_KEY` を削除 (`SECRET_ID` のみ参照に)
- `.github/workflows/deploy-lambdas.yml` の fetcher/processor step の `ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}` 削除
- `scripts/ci_lambda_merge_env.py` の `env["ANTHROPIC_API_KEY"] = ...` 削除

---

## 完了確認

- [ ] `aws lambda get-function-configuration --function-name p003-fetcher --query 'Environment.Variables' | grep ANTHROPIC_API_KEY` が空
- [ ] 同 `--query Environment.Variables.ANTHROPIC_SECRET_ID` が `flotopic/anthropic-api-key`
- [ ] CloudWatch Logs に `[SEC9]` エラーなし (24h 観察)
- [ ] `gh secret list` で GitHub Secrets `ANTHROPIC_API_KEY` を **残す** (deploy.yml が新キー rotate 時に Secrets Manager 更新するため・別途 rotation script 化検討)

---

## ロールバック

問題発生時は env に旧値を戻すだけで済む (`_load_secret_or_env` は SECRET_ID 未指定なら env を読む):

```bash
aws lambda update-function-configuration \
  --function-name p003-fetcher \
  --environment "Variables={...,ANTHROPIC_API_KEY=sk-ant-api03-xxx}" \
  --region ap-northeast-1
# ANTHROPIC_SECRET_ID も削除すれば完全に旧経路に戻る
```

---

## 参考

- AWS Secrets Manager pricing: $0.40/secret/月 + $0.05/10,000 API calls (2 secret + 月数千 call → $1/月程度)
- IAM least-privilege ベストプラクティス: https://docs.aws.amazon.com/secretsmanager/latest/userguide/auth-and-access_examples.html
