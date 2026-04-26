# AWS MCP セットアップ手順

CoworkからAWSに直接アクセスできるようにする設定。
完了するとローカルPCなしでS3デプロイ・Lambda更新が可能になる。

## ステップ1: AWS認証情報の設定

ターミナルでどこでもOK：

```bash
aws configure
```

入力項目：
- AWS Access Key ID: （AWSコンソール → IAM → ユーザー → セキュリティ認証情報 → アクセスキー作成）
- AWS Secret Access Key: （上と同じ画面で取得）
- Default region name: `ap-northeast-1`
- Default output format: `json`

確認：
```bash
aws sts get-caller-identity
```
アカウントIDが返ってくればOK。

---

## ステップ2: Claude desktop の MCP設定

設定ファイルを開く：
```bash
open ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

以下を追加（既存の `mcpServers` に追記）：

```json
{
  "mcpServers": {
    "aws": {
      "command": "uvx",
      "args": ["awslabs.aws-mcp-server@latest"],
      "env": {
        "AWS_PROFILE": "default",
        "AWS_REGION": "ap-northeast-1"
      }
    }
  }
}
```

※ `mcpServers` が既にある場合は既存のキーに `aws` を追記するだけ。

---

## ステップ3: Claude desktop を再起動

設定ファイル保存後、Claude desktopを完全終了して再起動。

---

## 完了後にできること

- Coworkから直接 `aws s3 sync` でFlotopicをデプロイ
- LambdaのコードをCoworkから更新
- DynamoDBの中身を確認・操作
- ローカルPCに触らず自走デプロイが可能に

---

## 注意

- IAMユーザーに必要な権限: S3フルアクセス、Lambda実行・更新、DynamoDB読み書き
- アクセスキーはGitHubにコミットしない（.gitignoreで保護済み）
