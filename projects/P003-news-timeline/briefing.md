# P003 ブリーフィング

## 概要
話題のニュースを時系列で追うWebアプリ。RSSを自動取得してトピックに分類、上昇中/ピーク/減衰中を判定。

## 現状
- last_run: 2026-04-21
- status: **本番稼働中** ✅ 品質改善継続中
- done_this_run: 本番稼働確認。社長指示「p003の開発進めてくれ」を受けて、品質改善対象checklist確認。詳細コードレビュー準備。

## 本番URL
- サイト: http://p003-news-946554699567.s3-website-ap-northeast-1.amazonaws.com
- API: https://hdiltmwjzm3euuod3xo2pd5kja0bfbrp.lambda-url.ap-northeast-1.on.aws/

## プロジェクトパス
```
/Users/murakaminaoya/ai-company/projects/P003-news-timeline/
```

## 構成
- `lambda/fetcher/handler.py` — RSS取得・トピック化（30分ごとにEventBridgeで自動実行）
- `lambda/api/handler.py` — フロントへデータを返すAPIエンドポイント
- `frontend/` — index.html / topic.html / app.js / style.css
- `deploy.sh` — AWS一発デプロイスクリプト

## 完了条件
- [x] Lambda(Fetcher) コード完成
- [x] Lambda(API) コード完成
- [x] フロントエンド完成
- [x] deploy.sh完成
- [x] AWSデプロイ実施
- [x] 動作確認（ニュースが取得・表示される）

## 品質改善予定項目（優先度順）
- [ ] エラーハンドリング強化（RSS取得失敗時・API timeout対応）
- [ ] トピック分類精度向上（重複排除・キーワード学習）
- [ ] UI/UXレイアウト最適化（レスポンシブ改善）
- [ ] レスポンスタイム計測・API最適化
- [ ] ログ・モニタリング機能強化

## next_action
- **Claude**: handler.py の詳細コードレビュー実施 → 改善提案を Slack で報告。その後、優先度順に実装。
- **社長**: 改善の優先度指定があれば教えてください（例：「レスポンスタイム最優先」など）

## ブロッカー
なし

## リーガル・セキュリティ確認
- **ライセンス**:
  - requests (RSS取得): Apache 2.0 ✅
  - boto3 (AWS SDK): Apache 2.0 ✅
  - その他依存パッケージ: 詳細確認推奨
- **ToS確認**: 
  - AWS Lambda/S3: 商用利用可 ✅
  - RSS自動取得: 対象サイトのrobots.txt・ToS確認推奨（今後実施）
- **セキュリティ**:
  - APIキー: Lambda環境変数で管理推奨
  - データベース: N/A（ファイルベース）
  - 脆弱性確認: 定期的なdependency check推奨

## 作業ログ
- 2026-04-20: コード一式確認。AWSデプロイ完了。30分ごと自動実行稼働中。初回46記事・46トピック取得確認。
- 2026-04-21: 本番稼働確認。社長指示「p003開発進めてくれ」を受けて品質改善対象リスト確認。詳細コードレビュー準備中。
