# Active Projects

最終更新: 2026-04-24

---

## [P001] AI会社 基盤構築

- **開始日**: 2026-04-20
- **担当**: CEO・秘書（Claude）
- **ステータス**: 稼働中 ✅
- **完成度**: ベータ
- **最終更新**: 2026-04-24
- **概要**: CEOエージェント・秘書エージェントが毎朝自動実行。DynamoDBメモリDB（P005）と連携し判断履歴を蓄積中。専門AI 5体がgit push待ちで停止中（7日間）。
- **次のアクション**:
  - ナオヤ: **最優先** git push → 残り5エージェントが即座に有効化される（提案#003）
  - CEO: push後に全エージェント正常稼働を確認・Slack報告

---

## [P002] Unityゲーム開発（要塞都市育成ゲーム）

- **開始日**: 2026-04-20
- **担当**: CEO
- **ステータス**: 開発中（低優先度）
- **完成度**: 試作
- **最終更新**: 2026-04-21
- **概要**: Unity向けスクリプト一式とアセット生成済み。Unity Editorでの組み立てはナオヤ作業待ち。
- **次のアクション**:
  - ナオヤ: Unity Editor で `FortressCity > Setup Everything` 実行 → Play テスト
  - CEO: P003安定・Phase 1達成後にフェーズ2（ゲームAIエージェント群）を検討

---

## [P003] Flotopic（フロトピック）

- **開始日**: 2026-04-20
- **担当**: CEO
- **ステータス**: 本番稼働中 ✅ 6日目 / HTTPS・ドメイン設定待ち
- **完成度**: 完成候補
- **最終更新**: 2026-04-24
- **URL（現行）**: http://p003-news-946554699567.s3-website-ap-northeast-1.amazonaws.com
- **URL（正式）**: https://flotopic.com（HTTPS設定完了後に切り替え）
- **ヘルスチェック（2026-04-24）**: ✅ 応答あり・トピック数4,700+
- **フェーズ**: Phase 0（インフラ整備中）→ HTTPS完了でPhase 1開始
- **実装済み**:
  - AI要約・AIタイトル生成・差分更新・重複排除（Union-Find）
  - Cloudflare Analytics・忍者AdMax広告・プライバシーポリシー
  - コメント掲示板（DynamoDB）・Google ログイン（OAuth 2.0）・お気に入り機能
  - OGPメタタグ・X自動投稿エージェント・catchup.html・processor Lambda
- **未完了（home PC 作業必要）**:
  - git push → S3デプロイ（最優先・7日経過）
  - CloudFront HTTPS 設定（setup-domain.sh）
  - Squarespace NS → Route 53 変更
  - GOOGLE_CLIENT_ID取得・設定
  - AdSense 申請（HTTPS完了後）
- **監視状況**:
  - flotopic-analytics: ⚠️ データ未蓄積（提案#004で確認依頼中）
  - Cloudflare Analytics: 設置済み・データ取得API未接続
- **収益化ロードマップ**:
  1. HTTPS完了 → AdSense申請 + Search Console登録（提案#006）
  2. SEO強化（git push後SEO AIが自動稼働）→ 月間1,000PV目標（Phase 1）
  3. 月1,000PV達成 → CEOがPhase 2移行提案（Googleログイン・お気に入り解禁）
  4. 月5,000PV達成 → Phase 3（コメント機能解禁・セキュリティ有効化）
  5. 広告収益でAPI代を賄う

---

## [P004] Slack Bot

- **開始日**: 2026-04-21
- **担当**: CEO
- **ステータス**: 実装完了・Lambda デプロイ待ち
- **完成度**: ベータ
- **最終更新**: 2026-04-24
- **概要**: `/ai` コマンドで Claude に指示できる Slack Bot。handler.py 実装済み。Slack App・Bot Token 取得済み。
- **未完了**: home PC で `bash projects/P004-slack-bot/deploy.sh` 実行のみ（5分で完了・7日経過）
- **次のアクション**:
  - ナオヤ: home PCに戻り次第 deploy.sh を実行（git pushと同時に実施推奨）

---

## [P005] メモリDB

- **開始日**: 2026-04-21
- **担当**: CEO
- **ステータス**: 稼働中 ✅
- **完成度**: ベータ
- **最終更新**: 2026-04-24
- **概要**: DynamoDB `ai-company-memory`（ap-northeast-1）。CEO・秘書スクリプトからload_memory / save_memoryで読み書き。CEOの判断履歴・提案結果を蓄積中。
- **備考**: 本日のCEO実行でメモリ読み込みに失敗（DynamoDB接続エラーの可能性）。git push後に正常稼働を確認する。
- **次のアクション**: git push後に接続確認。データ蓄積が進んだら判断品質レビューを実施。
