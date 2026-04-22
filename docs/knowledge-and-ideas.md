# AI-Company ナレッジ & アイデアベース

> 将来のClaude・専門AIが参照する判断根拠と開発アイデアの蓄積。
> 新しい知見・提案が出たら即追記する。

最終更新: 2026-04-22

---

## 技術的知見

### Lambda / AWS

- **Lambda OOM回避**: handler.pyでOGP画像取得は上位20トピックに制限（`ogp_fetched < 20`）
- **差分更新の仕組み**: `api/seen_articles.json` をS3で永続化し、URLセット差分で処理をスキップ。初回実行時は`seen_urls`が空のため全件処理される
- **DynamoDB設計**: topicIdをPK、SK='META'でメタデータ、SK='SNAP#YYYYMMDDTHHmmSSZ'でスナップショット履歴
- **Union-Findでクラスタリング**: 推移的な類似（A≈B, B≈C）を正しく検出できる。Jaccard閾値0.25（下げるほど積極的にまとめる）
- **CloudFront + S3**: CloudFrontのエイリアスにACM証明書が必要。証明書は必ずus-east-1で発行すること（CloudFrontが要求）
- **Route 53 hosted zone**: ドメインレジストラのNSをAWSのNSに変更するだけでDNS管理をAWSに移管できる

### Claude API

- **モデル使い分け**: 日次判断・重要決定 → claude-sonnet-4-6。高速・安価な処理 → claude-haiku-4-5-20251001
- **AI要約品質**: 150字以内・自然文・箇条書き禁止のプロンプトが最も読みやすい要約を生成
- **AIタイトル生成**: 「12〜20文字・概念的・固有名詞必須・記事そのままコピー禁止」の制約が効果的

### Python/スクリプト

- **GitHub Actions secrets**: 環境変数名はYMLとPythonで一致させること。`os.environ.get('KEY', '')`で必ず空文字フォールバック
- **OAuth 1.0a for X API**: 標準ライブラリのみで実装可能。`hmac`+`sha1`でsignature生成。tweepyは使わない（依存関係が複雑）
- **Slack通知**: Incoming Webhookを使う。Bot Tokenは`chat.postMessage`向け（Webhookより権限範囲が広い）

---

## ビジネス知見

### Flotopic (P003) の収益化ロードマップ

```
フェーズ1（現在）: トラフィック獲得
  → SEO改善・X自動投稿・RSS配信でオーガニック流入を増やす

フェーズ2（HTTPS化後）: 広告収入
  → Google AdSense申請（月1,000PV以上が目安）
  → 忍者AdMaxは設置済み

フェーズ3（月10万PV目標）: アフィリエイト強化
  → A8.net でニュースジャンルに合った商材を配置
  → 株・金融トピックにネット証券アフィリを紐づける

フェーズ4（月100万PV）: スポンサー・有料API
  → 企業スポンサー枠
  → Flotopic APIの有料提供（法人向けニューストラッキング）
```

### コスト管理

- Claude API費用が最大コスト要因。記事数×API呼び出し回数で増える
- 既存トピックは`existing.get('generatedSummary')`で再利用しているため、毎回APIを呼ぶわけではない
- 差分更新（新記事なし→スキップ）でAPIコストを大幅削減済み

---

## 開発アイデア（未着手）

### 高優先度

#### A. トレンドスコア改善
現在のスコア = メディア数×10 + はてブ数。改善案:
- Xでの言及数をスコアに加える（X API v2 search）
- 記事の更新速度（単位時間あたりの新記事数）を加重
- ジャンル別スコア正規化（スポーツは元々記事数が多いので補正）

#### B. SEO最適化AI（実装済み: seo_agent.py）
- 毎週月曜にサイトのSEO状態をチェック
- メタディスクリプション生成・監視
- Googleサーチコンソール連携（要承認）

#### C. パーソナライズ機能
- ユーザーが「好きなジャンル」を選択するとトップに表示
- LocalStorageで設定を保存（サーバー不要）

#### D. リアルタイム通知
- 急上昇トピック（スコアが30分以内に50以上増）を検出したらプッシュ通知
- Web Push API でサービスワーカー実装

#### E. まとめ記事自動生成
- 週次で「今週の注目トピック10選」を自動生成
- マークダウン → HTMLに変換してS3に配置
- SEO効果とSNSシェアを狙う

### 中優先度

#### F. X（Twitter）連携強化
- @flotopic_jp のリプライを監視してFAQ自動回答
- スレッド形式でトピックの経緯を投稿

#### G. ニュースジャンル精度向上
- 現在はキーワードマッチ。MLモデル（fasttext/BERTJapanese）で精度向上
- ただしLambdaのメモリ制限があるためS3にモデルを置いて読み込む設計が必要

#### H. コメント掲示板の充実
- いいね機能（DynamoDBにcount追加）
- コメントへの返信（スレッド構造）
- NGワードフィルター強化（正規表現リスト）

#### I. マルチ言語対応
- 英語RSSフィードを追加して`lang='en'`タグで分類
- フロントエンドに言語フィルターを追加
- 将来の海外展開（flotopic.com）への布石

### 低優先度（将来）

#### J. 有料ダッシュボード
- 法人向け：特定キーワードのトレンド追跡
- API提供：`GET /api/trending?keyword=AI` で外部から参照可能に

#### K. ポッドキャスト自動生成
- 上位トピックのAI要約をTTS（Text-to-Speech）で音声化
- 週次ニュースポッドキャストとして配信

---

## 専門AI進化ロードマップ

### 現在の体制（6体）

```
CEO（claude-sonnet）
├── 秘書（claude-haiku）
├── 開発監視AI（claude-haiku）- 毎時
├── マーケティングAI（claude-haiku）- 毎朝
├── 収益管理AI（claude-haiku）- 毎週月
├── 編集AI（claude-haiku）- 毎週水
└── SEO AI（claude-haiku）- 毎週月（新規追加）
```

### 次に作るべきAI

1. **カスタマーサポートAI** - コメント掲示板の質問に自動回答（DynamoDBトリガー）
2. **コンテンツ戦略AI** - 月次でどのジャンルが伸びているかを分析し、RSS追加を提案
3. **競合分析AI** - 類似サービスの機能・UIを月次で調査してレポート
4. **データサイエンスAI** - ユーザー行動データを分析して改善提案

---

## 失敗と学び

### セッション越えのメモリ問題
- CLAUDE.mdへの書き込みを「セッション継続の唯一の手段」として徹底
- 口頭で「やります」「書きました」は証拠にならない。ファイルの存在が証拠
- git pushが通れば自走するが、push前はCoworkセッションが唯一の実行環境

### API Key管理
- X API: OAuth 1.0a の Access Token/Secret が必要（Bearer Tokenのみでは投稿不可）
- GitHub Secrets の名前はYMLと完全一致させること
- AWS credentials は `aws configure` で設定、MCPではまだ未接続

### コスト意識
- Claude Haiku でできる処理は Sonnet を使わない
- バッチ処理は一度にまとめてAPIを叩く（記事ごとに1回ずつ呼ばない）
- キャッシュを積極活用（`existing.get()`で既存の生成結果を再利用）
