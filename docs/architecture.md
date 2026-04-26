# AI-Company & Flotopic システム構成図

最終更新: 2026-04-22

---

## 全体像

```
[インターネット]
     ↓
[flotopic.com] ← DNS: Route 53（AWS）
     ↓
[CloudFront] ← HTTPS / CDN / キャッシュ
     ↓
[S3バケット] ← 静的ファイル（HTML/CSS/JS/JSON）
```

ユーザーがブラウザで `https://flotopic.com` にアクセスすると、CloudFront（CDN）経由でS3の静的ファイルが返される。すべてサーバーレス構成なのでサーバー費用はほぼゼロ。

---

## ドメイン・DNS構成

| レイヤー | サービス | 役割 |
|---|---|---|
| ドメイン登録 | Squarespace | flotopic.com を保有 |
| DNS管理 | AWS Route 53 | ネームサーバー → AWSに移管済み |
| CDN / HTTPS | AWS CloudFront | SSL証明書 + 高速配信 |
| ストレージ | AWS S3 | 静的ファイル配信 |

**なぜRoute 53を使うのか？**  
CloudFrontのSSL証明書（ACM）はAWSサービスなので、DNSもRoute 53で管理した方がシームレスに連携できる。Squarespaceのネームサーバーを変更するだけでDNS管理をAWSに委譲できる。

---

## バックエンド（Lambda）構成

```
[GitHub Actions] → 30分ごと
     ↓
[Lambda: fetcher] ← Python
     ↓ RSSフィードを取得 → Claude APIでAI要約
     ↓
[S3: api/data.json] ← フロントエンドが読み込む
[S3: api/seen_articles.json] ← 差分管理（同じ記事を再処理しない）
[S3: rss.xml] ← RSSフィード出力
```

```
[フロントエンド（ブラウザ）]
     ↓ コメント投稿・取得
[Lambda: comments] ← Python
     ↓
[DynamoDB: ai-company-comments] ← コメントDB
```

**Lambda = AWSのサーバーレス関数。**  
サーバーを常時動かさずに、必要なときだけコードを実行できる。費用は実行回数ベースなのでほぼ無料。

---

## フロントエンド構成

```
flotopic.com/
├── index.html       ← トップページ（トピック一覧）
├── topic.html       ← トピック詳細（グラフ・コメント掲示板）
├── privacy.html     ← プライバシーポリシー
├── style.css        ← デザイン
├── app.js           ← メインロジック（データ取得・描画）
├── config.js        ← API URLなどの設定
├── ogp.png          ← SNSシェア用画像
├── sitemap.xml      ← 検索エンジン用
├── robots.txt       ← クローラー制御
└── api/
    └── data.json    ← ニュースデータ（Lambdaが生成）
```

---

## AI（自律エージェント）構成

```
[GitHub Actions] ← クラウド上でCronを実行
     ↓ スケジュール通りに各Pythonスクリプトを起動
     ↓
[CEO] 毎朝8:30 JST
  → 会社全体の状況を把握してSlackに日次報告

[秘書] 毎朝9:00 JST
  → Notionに最新状態を同期

[開発監視AI] 毎時
  → flotopic.comが正常に動いているかチェック
  → 異常があればSlackにアラート

[マーケティングAI] 毎朝10:00 JST
  → 人気トピックをX（@flotopic_jp）に自動投稿

[収益管理AI] 毎週月曜 9:30 JST
  → AWSコスト・広告収入をClaudeが分析してSlack報告

[編集AI] 毎週水曜 9:00 JST
  → AI要約の品質をチェック
  → スパムコメントを自動削除
```

**なぜGitHub Actions？**  
無料枠が月2,000分あり、Cronスケジュール実行ができる。サーバーを持たずにAIを「毎朝自動起動」できる。

---

## データフロー（ニュース記事の流れ）

```
1. RSSフィード（各ニュースサイト）
     ↓ Lambda fetcher が30分ごとに取得
2. 記事をグループ化（同じトピックをまとめる）
     Union-Find アルゴリズムで類似記事を検出
     ↓
3. Claude APIでAI要約 + タイトル生成
     ↓
4. data.json をS3に保存
     ↓
5. フロントエンド（ブラウザ）がdata.jsonを読んで表示
```

---

## メモリ（AI記憶）構成

```
[DynamoDB: ai-company-memory]
  → CEOと秘書が判断履歴・会社状態を保存
  → セッションをまたいで記憶が持続する
```

---

## 収益化の仕組み

| 手段 | 状態 | 備考 |
|---|---|---|
| 忍者AdMax広告 | 設置済み | 現在HTTP→HTTPS化後に本格稼働 |
| Google AdSense | 申請待ち | HTTPS化完了後に申請 |
| A8.net アフィリエイト | 登録済み | 記事との連携今後 |

---

## まとめ：お金がかかる部分

| サービス | 月額目安 |
|---|---|
| AWS S3 + CloudFront | ほぼ無料（数円〜数十円） |
| AWS Lambda | 無料枠内 |
| DynamoDB | 無料枠内 |
| Claude API | 月1,000〜5,000円程度（使用量による） |
| GitHub Actions | 無料枠内 |
| flotopic.com ドメイン | 約175円/月（年2,100円） |

**コスト最大の懸念はClaude API。** 記事数が増えるほど費用が上がる。収益管理AIが毎週コストを監視する。
