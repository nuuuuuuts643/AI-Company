# AI Company — セッション記録・現状まとめ

最終更新: 2026-04-21

---

## 今日やったこと（2026-04-21）

### 秘書システム修正・稼働
- 問題: secretary_run.py がJSONパースエラーで毎回落ちていた
- 原因: Claude APIの複数行レスポンスをjson.loads()で解析できなかった
- 修正: XMLタグ形式に変更（FILE/SLACKタグ）
- apply-fixes.yml: workflows:write が無効スコープだったことを発見し削除、heredoc+Python base64構成に変更
- 結果: 秘書ワークフロー手動実行で成功・全ステップグリーン確認

### P003 ニュースタイムライン改善
- UIカードを縦長ヘッダー画像 → 横サムネイル68px + テキスト右配置に変更
- Lambda: OGP画像取得・AI要約生成・RSSメディア画像抽出を追加
- deploy-p003.yml: EventBridge 30分スケジュール設定ステップを追加

---

## 現在の自動化レベル

| 機能 | 頻度 | 担当 |
|------|------|------|
| ニュース収集・分類 | 30分ごと | Lambda |
| AIタイトル・要約生成 | トピック初回登場時 | Claude Haiku |
| OGP画像取得 | トピック初回登場時 | Lambda |
| 秘書レポート・ファイル更新 | 毎朝9時JST | Claude Haiku |
| 古いトピック自動削除（72h以上・低スコア） | Lambda実行時 | Lambda |

---

## 自動で改善されること（社長不要）

- P003のニュース内容 → 30分ごとに最新更新
- P003のAI要約・OGP画像 → Lambda実行ごとに自動蓄積
- ダッシュボードファイル → 毎朝9時に秘書が更新

## 社長のアクションが必要なこと

| やること | 理由 |
|----------|------|
| P003デプロイワークフロー実行 | UI修正をS3に反映するため |
| P002: Unity Editor操作 | AIが直接Unityを操作できないため |
| 新機能・新プロジェクトの方針決定 | 何をつくるかは社長が決める |

---

## インフラ構成

| サービス | 用途 |
|---------|------|
| AWS Lambda | p003-fetcher / p003-api / slack-bot |
| AWS DynamoDB | p003-topics |
| AWS S3 | フロントエンド + JSONデータ |
| AWS EventBridge | p003-fetcher 30分スケジュール |
| GitHub Actions | 秘書実行（毎朝9時）/ デプロイ |
| Anthropic API | secretary_run.py + Lambda内AI処理 |

---

## 既知の技術的制約

- GitHub ActionsはGITHUB_TOKENで.github/workflows/を変更できない → Web UIかPC端末から直pushが必要
- Coworkサンドボックスはgit pushが外部に繋がらない → Actions経由か社長のPC端末で実施
