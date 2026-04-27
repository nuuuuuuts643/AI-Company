# AI Company Overview

最終更新: 2026-04-28

## Active Projects

| ID | 名前 | ステータス | 完成度 | URL |
|----|------|----------|--------|-----|
| P001 | AI会社 基盤構築 | （CEO/秘書 思想呼び出し廃止 2026-04-28） | ベータ | — |
| P002 | Unityゲーム（要塞都市育成） | スクリプト完了・Unity組み上げ待ち | 試作 | — |
| P003 | Flotopic（フロトピック） | **本番稼働中** 🟢 6日目 / HTTPS設定待ち | 完成候補 | http://p003-news-946554699567.s3-website-ap-northeast-1.amazonaws.com |
| P004 | Slack Bot | 実装完了・Lambdaデプロイ待ち | ベータ | — |
| P005 | メモリDB | **稼働中** 🟢 | ベータ | DynamoDB ap-northeast-1 |

## AI エージェント稼働状況

> CEO (ceo_run.py) / 秘書 (secretary_run.py) は 2026-04-28 に廃止（会社思想呼び出しパターン整理 T2026-0428-AA）。

| エージェント | スケジュール | 状態 |
|---|---|---|
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
| 全エージェント有効化 | git push | ナオヤ（home PC） | **7日** ⚠️ |
| P003 HTTPS / flotopic.com | setup-domain.sh 実行 + Squarespace NS 変更 | ナオヤ（home PC） | **7日** ⚠️ |
| P004 Lambda デプロイ | deploy.sh 実行 | ナオヤ（home PC） | **7日** ⚠️ |
| Google OAuth 有効化 | GOOGLE_CLIENT_ID取得・config.js設定 | ナオヤ（手順: docs/google-oauth-setup.md） | **7日** ⚠️ |
| AdSense 申請 | HTTPS 完了後 | CEO | — |
| flotopic-analytics蓄積 | 追跡コード動作確認（提案#004） | 要確認 | — |

<!-- 「未処理の提案」「CEO実行状況」「秘書実行状況」セクションは
     2026-04-28 T2026-0428-AA で会社思想呼び出しパターンと一緒に廃止 -->

