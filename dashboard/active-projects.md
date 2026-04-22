# Active Projects

最終更新: 2026-04-22

---

## [P001] AI会社 基盤構築

- **開始日**: 2026-04-20
- **担当**: CEO・秘書（Claude）
- **ステータス**: 稼働中 ✅
- **完成度**: ベータ
- **最終更新**: 2026-04-22
- **概要**: CEOエージェント・秘書エージェントが毎朝自動実行。DynamoDBメモリDB（P005）と連携し判断履歴を蓄積中。
- **次のアクション**:
  - PO: git push → 残り5エージェントが有効化される
  - CEO: push 後に全エージェント正常稼働を確認・Slack報告

---

## [P002] Unityゲーム開発（要塞都市育成ゲーム）

- **開始日**: 2026-04-20
- **担当**: CEO
- **ステータス**: 開発中（低優先度）
- **完成度**: 試作
- **最終更新**: 2026-04-21
- **概要**: Unity向けスクリプト一式と sword/shield/coin.svg アセット生成済み。Unity Editor での組み立てはPO作業待ち。
- **次のアクション**:
  - PO: Unity Editor で `FortressCity > Setup Everything` 実行 → Play テスト
  - CEO: P003 安定後にフェーズ2（ゲームAIエージェント群）を検討

---

## [P003] Flotopic（フロトピック）

- **開始日**: 2026-04-20
- **担当**: CEO
- **ステータス**: 本番稼働中 ✅ / HTTPS・ドメイン設定待ち
- **完成度**: 完成候補
- **最終更新**: 2026-04-22
- **URL（現行）**: http://p003-news-946554699567.s3-website-ap-northeast-1.amazonaws.com
- **URL（正式）**: https://flotopic.com（HTTPS設定完了後に切り替え）
- **実装済み**:
  - AI要約・AIタイトル生成・差分更新・重複排除（Union-Find）
  - Cloudflare Analytics・忍者AdMax広告・プライバシーポリシー
  - コメント掲示板（DynamoDB ai-company-comments）
  - Google ログイン（OAuth 2.0）・お気に入り機能
  - OGPメタタグ
  - X自動投稿エージェント・catchup.html・processor Lambda
- **未完了（home PC 作業必要）**:
  - git push → S3デプロイ
  - CloudFront HTTPS 設定（setup-domain.sh）
  - Squarespace ネームサーバー → Route 53 への変更
  - Google Cloud Console で GOOGLE_CLIENT_ID 取得（手順: docs/google-oauth-setup.md）
  - AdSense 申請（HTTPS完了後）
- **収益化ロードマップ**:
  1. HTTPS完了 → AdSense申請
  2. SEO強化 → 月間10,000PV目標
  3. 広告収益でAPI代を賄う

---

## [P004] Slack Bot

- **開始日**: 2026-04-21
- **担当**: CEO
- **ステータス**: 実装完了・Lambda デプロイ待ち
- **完成度**: ベータ
- **最終更新**: 2026-04-22
- **概要**: `/ai` コマンドで Claude に指示できる Slack Bot。handler.py 実装済み。Slack App・Bot Token 取得済み。
- **未完了**: home PC で `bash projects/P004-slack-bot/deploy.sh` 実行のみ
- **次のアクション**:
  - PO: home PC に戻り次第 deploy.sh を実行（5分で完了）

---

## [P005] メモリDB

- **開始日**: 2026-04-21
- **担当**: CEO
- **ステータス**: 稼働中 ✅
- **完成度**: ベータ
- **最終更新**: 2026-04-22
- **概要**: DynamoDB `ai-company-memory`（ap-northeast-1）。CEO・秘書スクリプトから load_memory / save_memory で読み書き。CEOの判断履歴・提案結果を蓄積中。
- **次のアクション**: 継続モニタリング。データ蓄積が進んだら判断品質レビューを実施。
