# AI Company Overview

最終更新: 2026-04-22

## Active Projects

| ID | 名前 | ステータス | 完成度 | URL |
|----|------|----------|--------|-----|
| P001 | AI会社 基盤構築 | 秘書・CEO 稼働中 | ベータ | — |
| P002 | Unityゲーム（要塞都市育成） | スクリプト完了・Unity組み上げ待ち | 試作 | — |
| P003 | Flotopic（フロトピック） | **本番稼働中** 🟢 HTTPS設定待ち | 完成候補 | flotopic.com |
| P004 | Slack Bot | 実装完了・Lambdaデプロイ待ち | ベータ | — |
| P005 | メモリDB | **稼働中** 🟢 | ベータ | DynamoDB ap-northeast-1 |

## AI エージェント稼働状況

| エージェント | スケジュール | 状態 |
|---|---|---|
| CEO (ceo_run.py) | 毎朝8:30 JST | ✅ 稼働中 |
| 秘書 (secretary_run.py) | 毎朝9:00 JST | ✅ 稼働中 |
| 開発監視AI (devops_agent.py) | 毎時 | 🟡 git push 待ち |
| マーケティングAI (marketing_agent.py) | 毎朝10:00 JST | 🟡 git push 待ち |
| 収益管理AI (revenue_agent.py) | 毎週月曜9:30 JST | 🟡 git push 待ち |
| 編集AI (editorial_agent.py) | 毎週水曜9:00 JST | 🟡 git push 待ち |
| SEO AI (seo_agent.py) | 毎週月曜10:00 JST | 🟡 git push 待ち |
| X投稿AI (x_agent.py) | 日次8:00 / 週次月9:00 / 月次1日9:00 | 🟡 git push 待ち |

## P003 Flotopic 実装済み機能

| 機能 | 状態 |
|------|------|
| ニュース自動収集（30分ごと / EventBridge） | ✅ 稼働中 |
| AI要約・AIタイトル生成 | ✅ 実装済み |
| 差分更新（seen_articles.json） | ✅ 実装済み |
| 重複排除（Union-Find 閾値0.25） | ✅ 実装済み |
| Cloudflare Web Analytics | ✅ 設置済み |
| 忍者AdMax 広告 | ✅ 設置済み |
| プライバシーポリシーページ | ✅ 作成済み |
| コメント掲示板（DynamoDB） | ✅ 実装済み・デプロイ待ち |
| Google ログイン（OAuth 2.0） | ✅ 実装済み・GOOGLE_CLIENT_ID設定待ち |
| お気に入り機能 | ✅ 実装済み |
| OGP メタタグ | ✅ 設定済み |
| X自動投稿エージェント | ✅ 実装済み・デプロイ待ち |
| catchup.html（N日ぶりモード） | ✅ 実装済み・デプロイ待ち |
| HTTPS / CloudFront | 🟡 home PC 作業待ち |
| flotopic.com DNS（Route 53） | 🟡 Squarespace NS 変更待ち |
| Google AdSense | 🟡 HTTPS 完了後に申請 |

## home PC に戻ったら実行するコマンド（優先順）

```bash
cd ~/ai-company

# 1. 全変更をpush
git push

# 2. P003 S3再デプロイ
bash projects/P003-news-timeline/deploy.sh

# 3. P004 Slackボット デプロイ
bash projects/P004-slack-bot/deploy.sh

# 4. flotopic.com CloudFront + SSL + Route 53 セットアップ
bash scripts/setup-domain.sh
```

## ブロッカー一覧

| 案件 | ブロッカー | 担当 |
|------|-----------|------|
| 全エージェント有効化 | git push | ナオヤ（home PC） |
| P003 HTTPS / flotopic.com | setup-domain.sh 実行 + Squarespace NS 変更 | ナオヤ（home PC） |
| P004 Lambda デプロイ | deploy.sh 実行 | ナオヤ（home PC） |
| Google OAuth 有効化 | Google Cloud Console で Client ID 取得 → config.js に設定 | ナオヤ（手順: docs/google-oauth-setup.md） |
| AdSense 申請 | HTTPS 完了後 | CEO |

## CEO実行状況

- last_run: 2026-04-22 09:00 JST
- 秘書稼働状態: ✅ 正常（GitHub Actions自動実行確認）
- 未処理Slack: 0件（全処理完了）
- セキュリティ確認: ✅ リスクなし（P003）
- コスト管理: ✅ 月500円以下で運用中
