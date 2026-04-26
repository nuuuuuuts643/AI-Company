# P003 News Timeline

話題のニュースを時系列で追うWebアプリ。

## 機能
- RSSから自動取得（30分ごと）
- 類似タイトルをトピックにまとめる
- 上昇中 / ピーク / 減衰中 の3段階判定
- トピック一覧 + 時系列グラフの詳細画面
- ブラウザを開いたまま5分ごとに自動更新

## デプロイ方法

### 事前準備
AWSの「Claude」ユーザーに `AdministratorAccess` ポリシーを追加してください。
（IAM → ユーザー → Claude → 許可を追加）

### 実行
```bash
cd projects/P003-news-timeline
bash deploy.sh
```

表示されたサイトURLをブラウザで開けば完了です。

## AWS構成（すべて無料枠内）
| サービス | 用途 |
|---------|------|
| Lambda (Fetcher) | RSSを取得してトピック化 |
| Lambda (API) | フロントへデータを返す |
| DynamoDB | トピックと時系列データを保存 |
| S3 | HTMLファイルをホスティング |
| EventBridge | 30分ごとにFetcherを自動実行 |

## ファイル構成
```
lambda/fetcher/handler.py  ← RSS取得・トピック化
lambda/api/handler.py      ← APIエンドポイント
frontend/index.html        ← トピック一覧
frontend/topic.html        ← 詳細・時系列グラフ
frontend/app.js            ← 自動更新ロジック
frontend/style.css         ← デザイン
deploy.sh                  ← 一発デプロイ
```
