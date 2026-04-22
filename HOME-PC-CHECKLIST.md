# home PC 作業チェックリスト

最終更新: 2026-04-22

## ① git push（最優先）

```bash
cd ~/ai-company
git push
```

pushが通ったら以下が自動で有効になる：
- 開発監視AI（毎時）
- マーケティングAI（毎朝10:00）
- 収益管理AI（毎週月曜）
- 編集AI（毎週水曜）
- P003改善（AI要約・差分更新・OGP・広告・PP・コメント掲示板）

---

## ② P003 S3再デプロイ

```bash
bash projects/P003-news-timeline/deploy.sh
```

これでP003の全改善が本番反映される。コメント掲示板用のLambdaとDynamoDBも自動作成される。

---

## ③ P004 Slackボット デプロイ

```bash
GITHUB_TOKEN="***REDACTED-SEC3***" \
SLACK_BOT_TOKEN="***REDACTED-SEC3***23616-10995291739264-bNUcli9Op3eos6H9tHCDDMMF" \
SLACK_WEBHOOK="***REDACTED-SEC3***" \
bash projects/P004-slack-bot/deploy.sh
```

完了するとLambda URLが表示される。
→ そのURLを https://api.slack.com/apps → Event Subscriptions → Request URL に貼る。
→ Subscribe to bot events に `message.channels` を追加して保存。

---

## ④ GitHub MCP設定（Coworkからgit pushできるようになる）

`~/Library/Application Support/Claude/claude_desktop_config.json` を開く。

**既存のmcpServersがある場合** → 既存の`{}`の中に追記：
```json
"github": {
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-github"],
  "env": {
    "GITHUB_PERSONAL_ACCESS_TOKEN": "***REDACTED-SEC3***"
  }
}
```

**mcpServersが空の場合** → 丸ごと置き換え：
```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "***REDACTED-SEC3***"
      }
    }
  }
}
```

→ Claude desktopを再起動。

---

## ⚠️ 既知のリスク・注意点

| リスク | 内容 | 対処 |
|--------|------|------|
| GitHubトークン期限切れ | ghp_JPS5... が無効になっている可能性 | push失敗したら `gh auth login` か新トークン発行 |
| Cost Explorer権限なし | 収益管理AIがAWSコストを取得できない場合あり | エラーはスキップして動作継続する設計のためOK |
| config.jsonのJSON構文エラー | 既存MCPと上手くマージできていない場合 | Claude起動時にエラーが出る。JSONを確認 |
| P004 Lambda URLの手動設定 | Slack Event Subscriptions設定が必要 | デプロイ後にURLをSlack Appに貼るだけ |

---

## 確認コマンド

```bash
# git の状態確認
git log --oneline -5
git status

# AWS接続確認
aws sts get-caller-identity

# デプロイ済みLambda確認
aws lambda list-functions --region ap-northeast-1 --query 'Functions[].FunctionName'
```
