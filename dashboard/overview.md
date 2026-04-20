# AI Company Overview

最終更新: 2026-04-21

## Active Projects

| ID | 名前 | ステータス | 完成度 |
|----|------|----------|----|
| P001 | AI会社 基盤構築 | GitHub Actions設置済み・API待ち | ベータ |
| P002 | Unityゲーム（要塞都市育成） | スクリプト完了・Unity組み上げ待ち | ベータ |
| P003 | ニュースタイムライン | **本番稼働中** 🟢 | 完成候補 |

## 自動化状況

| 機能 | 状態 |
|------|------|
| Slack Bot (/ai コマンド) | ✅ 稼働中 |
| GitHub push → Slack通知 | ✅ 稼働中 |
| P003 ニュース自動収集（30分） | ✅ 稼働中 |
| 秘書 定期自動実行 | ⏸ APIクレジット待ち（手動は可） |

## Next Actions

1. **社長アクション**: https://console.anthropic.com/settings/billing でAPIクレジット購入 → 秘書自動化が動く
2. **社長アクション**: Unity Editorで `FortressCity > Setup Everything` 実行 → P002プレイテスト
3. **Claude**: P002スクリプト品質チェック・改善（随時）

## ブロッカー一覧

| 案件 | ブロッカー | 担当 |
|------|-----------|------|
| P001 | Anthropic APIクレジット | 社長 |
| P002 | Unity Editor操作 | 社長 |
| P003 | なし | — |
