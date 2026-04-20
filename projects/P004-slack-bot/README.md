# P004 Slack Bot

SlackからAI-Companyに指示を送れるようにするBot。

## 仕組み
1. 社長がSlackでメッセージ送信（または `/ai` スラッシュコマンド）
2. Lambda がメッセージを受け取り GitHub の `inbox/slack-messages.md` に追記
3. 4時間おきの秘書がそれを読んで実行
4. 完了したらSlackに報告

## ステータス
- [ ] Slack App作成・Bot Token取得
- [ ] Lambda関数デプロイ
- [ ] GitHub Personal Access Token設定
- [ ] 動作テスト
