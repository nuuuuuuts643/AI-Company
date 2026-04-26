# AI Company Overview

最終更新: 2026-04-24

## Active Projects

| ID | 名前 | ステータス | 完成度 | URL |
|----|------|----------|--------|-----|
| P001 | AI会社 基盤構築 | 秘書・CEO 稼働中 | ベータ | — |
| P002 | Unityゲーム（要塞都市育成） | スクリプト完了・Unity組み上げ待ち | 試作 | — |
| P003 | Flotopic（フロトピック） | **本番稼働中** 🟢 6日目 / HTTPS設定待ち | 完成候補 | http://p003-news-946554699567.s3-website-ap-northeast-1.amazonaws.com |
| P004 | Slack Bot | 実装完了・Lambdaデプロイ待ち | ベータ | — |
| P005 | メモリDB | **稼働中** 🟢 | ベータ | DynamoDB ap-northeast-1 |

## AI エージェント稼働状況

| エージェント | スケジュール | 状態 |
|---|---|---|
| CEO (ceo_run.py) | 毎朝8:30 JST | ✅ 稼働中 |
| 秘書 (secretary_run.py) | 毎朝9:00 JST | ✅ 稼働中 |
| 開発監視AI (devops_agent.py) | 毎時 | 🟡 git push 待ち（7日間停止中） |
| マーケティングAI (marketing_agent.py) | 毎朝10:00 JST | 🟡 git push 待ち（7日間停止中） |
| 収益管理AI (revenue_agent.py) | 毎週月曜9:30 JST | 🟡 git push 待ち（7日間停止中） |
| 編集AI (editorial_agent.py) | 毎週水曜9:00 JST | 🟡 git push 待ち（7日間停止中） |
| SEO AI (seo_agent.py) | 毎週月曜10:00 JST | 🟡 git push 待ち（7日間停止中） |
| X投稿AI (x_agent.py) | 日次8:00 / 週次月9:00 / 月次1日9:00 | 🟡 git push 待ち（7日間停止中） |

## P003 Flotopic 実装済み機能

| 機能 | 状態 |
|------|------|
| ニュース自動収集（30分ごと / EventBridge） | ✅ 稼働中 |
| AI要約・AIタイトル生成 | ✅ 実装済み |
| 差分更新（seen_articles.json） | ✅ 実装済み |
| 重複排除（Union-Find 閾値0.25） | ✅ 実装済み |
| Cloudflare Web Analytics | ✅ 設置済み（データ蓄積状況要確認） |
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

## Flotopic フェーズ判定（2026-04-24）

| フェーズ | 条件 | 状態 |
|---------|------|------|
| Phase 0（インフラ整備） | HTTPS確認 + AI要約正常動作 | 🟡 HTTPS未完了 |
| Phase 1（月1,000PV目標） | Phase 0完了 | ⏸ 待機中 |
| Phase 2（月5,000PV目標） | 月1,000PV達成 | ⏸ 待機中 |

## home PC に戻ったら実行するコマンド（優先順・最新）

```bash
cd ~/ai-company

# 【最優先】全変更をpush（→ 5体の専門AIが即座に稼働開始）
git push

# P003 S3再デプロイ（最優先）
bash projects/P003-news-timeline/deploy.sh

# P004 Slackボット デプロイ（5分で完了）
bash projects/P004-slack-bot/deploy.sh

# flotopic.com CloudFront + SSL + Route 53 セットアップ
bash scripts/setup-domain.sh

# Squarespace管理画面でNSをRoute 53のNSに変更

# Google Cloud ConsoleでCLIENT_IDを取得 → GitHub Secretsに追加
#    手順: docs/google-oauth-setup.md
```

## ブロッカー一覧（最新）

| 案件 | ブロッカー | 担当 | 経過日数 |
|------|-----------|------|--------|
| 全エージェント有効化 | git push | PO（home PC） | **7日** ⚠️ |
| P003 HTTPS / flotopic.com | setup-domain.sh 実行 + Squarespace NS 変更 | PO（home PC） | **7日** ⚠️ |
| P004 Lambda デプロイ | deploy.sh 実行 | PO（home PC） | **7日** ⚠️ |
| Google OAuth 有効化 | GOOGLE_CLIENT_ID取得・config.js設定 | PO（手順: docs/google-oauth-setup.md） | **7日** ⚠️ |
| AdSense 申請 | HTTPS 完了後 | CEO | — |
| flotopic-analytics蓄積 | 追跡コード動作確認（提案#004） | 要確認 | — |

## 未処理の提案

| 提案 | タイトル | 経過日数 |
|------|---------|--------|
| #002 | P003品質改善実装の体制確認 | **7日** ⚠️ エスカレーション済 |
| #003 | home PC作業ブロッカー解消（最優先） | 2日 |
| #004 | flotopic-analyticsデータ蓄積確認 | 2日 |
| #005 | 提案#002エスカレーション | 2日 |
| #006 | HTTPS完了後の即実行タスク事前準備 | 2日 |

## CEO実行状況

- last_run: 2026-04-23 08:30 JST
- 秘書稼働状態: ✅ 正常（毎日9:00 自動実行確認）
- 未処理Slack: 0件（全処理完了）
- セキュリティ確認: ✅ リスクなし（P003）
- コスト管理: ✅ 月500円以下で運用中
- P003稼働: ✅ 6日目 トピック数4,700+（ヘルスチェックOK）
- フェーズ判定: Phase 0（HTTPS未完了）
- 読者品質モニタリング: ⚠️ flotopic-analyticsデータ未蓄積（提案#004）

## 秘書実行状況

- last_run: 2026-04-24 09:00 JST
- 実行時間: 3分
- 処理内容: inbox 確認・各案件ブリーフィング更新・dashboard 更新・ブロッカー整理
- エラー: なし
- 次回実行: 2026-04-25 09:00 JST
