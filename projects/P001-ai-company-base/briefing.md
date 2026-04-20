# P001 ブリーフィング

## 概要
AI-Company自体の基盤。秘書システム・ファイル管理・自走スケジュールの整備が目的。

## 現状
- last_run: 2026-04-21
- status: GitHub Actions秘書ワークフロー設置済み・Anthropic APIクレジット待ち
- done_this_run: CCR→GitHub Actions+Claude API直接呼び出しに切替。secretary.yml + secretary_run.py 作成・デプロイ済み。

## 完了条件
- [ ] スケジュール起動が実際に動く（定期実行確認）
- [x] secretary-protocol.md 完成
- [x] 全案件にbriefing.md 整備
- [x] GitHub Actions ワークフロー設置
- [x] Slack Bot (/ai コマンド) 稼働
- [x] GitHub push時Slack通知 稼働
- [ ] Anthropic APIクレジット購入 → 自動秘書実行
- [ ] 運用テスト（社長が入力 → 秘書が分類 → ファイル更新 → 通知）

## next_action
- Claude: 手動実行で秘書業務を継続。自動化はAPIクレジット追加待ち。
- 社長（ブロッカー）: https://console.anthropic.com/settings/billing でAPIクレジット購入（$5〜）すれば自動化が動く。急ぎでなければ手動でOK。

## ブロッカー
Anthropic APIクレジット不足（自動実行のみに影響。手動は問題なし）

## 判明した技術的知見
- CCR（Claude Code Remote）のBashツールは外部ネットワーク接続不可のためgit push/Slack通知が届かない
- 解決策: GitHub Actions cron + Claude API直接呼び出しがベストプラクティス

## 作業ログ
- 2026-04-20: secretary-protocol.md、全案件briefing.md、スケジュール設定を一括構築
- 2026-04-21: CCR環境の制限を確認。GitHub Actions + Python Claude API呼び出し方式に切替。Slack Bot・GitHub push通知は稼働確認済み。
