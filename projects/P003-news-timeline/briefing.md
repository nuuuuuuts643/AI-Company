# P003 ブリーフィング

## 概要
話題のニュースを時系列で追うWebアプリ。RSSを自動取得してトピックに分類、上昇中/ピーク/減衰中を判定。

## 現状
- last_run: 2026-04-20
- status: **本番稼働中**
- done_this_run: AWSデプロイ完了・初回ニュース取得完了（46記事・46トピック）

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
- [ ] AWSデプロイ実施
- [ ] 動作確認（ニュースが取得・表示される）

## next_action
- Claude: コードの品質チェック・改善できる箇所があれば対応する
- 社長（ブロッカー）: AWSのIAMユーザー「Claude」に `AdministratorAccess` ポリシーを付与する
  → AWS Console → IAM → ユーザー → Claude → 許可を追加 → AdministratorAccess

## ブロッカー
**AWS認証情報の設定が必要**
IAMユーザー「Claude」にAdministratorAccessが付与されたら、`bash deploy.sh` で即デプロイ可能。

## 作業ログ
- 2026-04-20: コード一式確認。デプロイ待ち状態。AWS権限付与後に即デプロイ予定。
