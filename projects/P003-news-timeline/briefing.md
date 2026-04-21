# P003 ブリーフィング

## 概要
話題のニュースを時系列で追うWebアプリ。RSSを自動取得してトピックに分類、上昇中/ピーク/減衰中を判定。

## 現状
- last_run: 2026-04-21
- status: **本番稼働中** ✅
- done_this_run: UIリデザイン（サムネイル横配置）・EventBridgeスケジュール追加・apply-fixes修正

## 本番URL
http://p003-news-946554699567.s3-website-ap-northeast-1.amazonaws.com

## 構成
- `lambda/fetcher/handler.py` — RSS取得・トピック化・OGP画像取得・AI要約生成
- `frontend/` — index.html / topic.html / app.js / style.css
- `.github/workflows/deploy-p003.yml` — Lambda + S3 + EventBridgeスケジュール設定

## 実装済み機能
- [x] RSSマルチフィード（18ソース・9ジャンル）
- [x] Jaccard類似度によるトピッククラスタリング
- [x] 上昇中/ピーク/減衰中の自動ステータス判定
- [x] Claude Haiku によるAIタイトル生成・要約生成
- [x] OGP画像 / RSSメディア画像 自動取得
- [x] カードUI：横サムネイル（68px）+ タイトル + メタ情報
- [x] 詳細ページ：閲覧数グラフ（昨日比・累計）・ストーリー時系列
- [x] 天気ウィジェット・検索・ジャンルフィルター
- [x] EventBridge 30分自動スケジュール
- [x] DynamoDB 72時間スパムクリーンアップ

## next_action
- 社長: GitHubからP003デプロイワークフローを実行（UIを反映）
- Claude: 品質モニタリング・トピック分類精度向上（随時）

## ブロッカー
なし（P003デプロイワークフロー実行待ち）

## 作業ログ
- 2026-04-20: コード一式確認。AWSデプロイ完了。30分ごと自動実行稼働中。
- 2026-04-21: apply-fixes.yml修正（workflows:write削除・base64修正）。秘書スクリプト動作確認。
             P003 UI改善（横サムネイル・AI要約・faviconバッジ）。
             deploy-p003.ymlにEventBridgeスケジュール設定ステップ追加。
