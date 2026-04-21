# 帰宅後やること 2026-04-21

## 必須（この順番で）

### 1. Lambda稼働確認（5分）
```bash
aws lambda get-function-configuration --function-name p003-fetcher --region ap-northeast-1
aws events describe-rule --name p003-fetcher-schedule --region ap-northeast-1
```
→ State: Active が返ってきたら本物。返ってこなければ報告する。

### 2. git push（5分）
```bash
cd ~/ai-company
git add -A
git commit -m "CEO system + P003 UI fixes + security"
git push
```
→ これでCEO・P003 UI・全修正がGitHubに上がる。

### 3. P003デプロイ（GitHubから実行）
- Actions → 「P003 デプロイ」→「Run workflow」
→ S3に最新UIが反映される。

## 翌朝確認
- 9時にSlackに秘書報告が届くか
- P003サイトのUIが正しいか（サムネイル横表示）

## 次のセッションでやること（優先順）
1. メモリDB設計・実装（DynamoDB `ai-company-memory`）
2. P004 Slackボット（承認ループ完成）
3. Notionコスト連携
