# P003 ブリーフィング

## 概要
話題のニュースを時系列で追うWebアプリ。RSSを自動取得してトピックに分類、上昇中/ピーク/減衰中を判定。

## 現状
- last_run: 2026-04-22 09:00 JST
- status: **本番稼働中** ✅（4日目継続） / 品質改善フェーズ（体制確認待ち）
- done_this_run: 本番環境EventBridge 30分自動実行が正常に稼働していることを確認。Lambda handler.py コード品質レビュー完了。エラーハンドリング・OGP取得フォールバック実装が有効に機能している。セキュリティ・ライセンス確認完了（リスクなし）。品質改善の実装体制判断待ち。
- running_days: 4日（2026-04-19 本番稼働開始）

## 本番URL
- フロント: http://p003-news-946554699567.s3-website-ap-northeast-1.amazonaws.com
- API: https://hdiltmwjzm3euuod3xo2pd5kja0bfbrp.lambda-url.ap-northeast-1.on.aws/

## 構成
- `lambda/fetcher/handler.py` — RSS取得・トピック化・OGP画像取得・AI要約生成
- `frontend/` — index.html / topic.html / app.js / style.css
- `.github/workflows/deploy-p003.yml` — Lambda + S3 + EventBridgeスケジュール設定

## 実装済み機能
- [x] RSSマルチフィード（18ソース・9ジャンル）
- [x] Jaccard類似度によるトピッククラスタリング
- [x] 上昇中/ピーク/減衰中の自動ステータス判定
- [x] Claude Haiku によるAIタイトル生成・要約生成
- [x] OGP画像 / RSSメディア画像 自動取得（フォールバック実装済み）
- [x] カードUI：横サムネイル（68px）+ タイトル + メタ情報
- [x] 詳細ページ：閲覧数グラフ（昨日比・累計）・ストーリー時系列
- [x] 天気ウィジェット・検索・ジャンルフィルター
- [x] EventBridge 30分自動スケジュール ✅ 正常動作確認
- [x] DynamoDB 72時間スパムクリーンアップ

## 品質確認（本日のレビュー）
- ✅ エラーハンドリング: RSS取得失敗・API失敗時の例外処理実装済み
- ✅ トピック分類精度: Jaccard類似度アルゴリズム・重複排除ロジック安定
- ✅ セキュリティ: APIキー環境変数管理・XSS対策実装済み
- ✅ ライセンス: 全依存パッケージ（feedparser, boto3, requests）確認済み・商用利用OK
- ✅ ToS: RSS自動取得・AI生成コンテンツ利用・画像キャッシュ全て規約範囲内

## next_action
- Claude: 品質モニタリング・トピック分類精度向上（随時）
- **収益化**: 下記「収益化計画」参照 — PO承認後に順次実装

## ブロッカー
- P003品質改善の実装体制が未確認（提案#002で確認中）
- P003デプロイワークフロー実行待ち（社長アクション）

---

## 収益化計画（2026-04-22 策定）

### 現状アセスメント
| 項目 | 状況 |
|---|---|
| PV数 | 不明（計測なし） |
| プロトコル | HTTP のみ（HTTPS未対応）← AdSense必須要件を未充足 |
| ドメイン | S3デフォルトURL（独自ドメインなし） |
| 広告枠 | `<div class="ad-slot">広告枠</div>` がindex/topic両ページに実装済み |
| PVトラッカー | トピック単位のDynamoDB tracker Lambdaあり（サイト全体計測なし） |
| プライバシーポリシー | なし（AdSense必須要件） |

### 収益化ロードマップ（優先順位順）

#### 🟢 Step 1: PV計測の追加（承認後即実装可・コスト¥0）
**Cloudflare Web Analytics** を推奨（Google Analyticsより軽量・Cookie不要・無料）

`index.html` と `topic.html` の `</body>` 直前に追加するだけ：
```html
<!-- Cloudflare Web Analytics -->
<script defer src='https://static.cloudflareinsights.com/beacon.min.js'
  data-cf-beacon='{"token": "YOUR_TOKEN_HERE"}'></script>
```
→ Cloudflare アカウント作成（無料）→ Web Analytics → サイト登録 → トークン取得

**代替：Google Analytics 4**（より詳細なデータが必要な場合）
```html
<!-- Google Analytics 4 -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-XXXXXXXXXX');
</script>
```

#### 🟡 Step 2: HTTPS化（AdSense申請の前提条件・コスト¥0〜¥1,500/年）
**方法A: CloudFront追加**（コスト¥0 — 無料枠: 1TB/月 + 1000万リクエスト/月）
- S3バケットの前段にCloudFrontを置くだけでHTTPS対応
- ドメインはCloudFrontの `.cloudfront.net` URL（独自ドメインなしでも可）

**方法B: 独自ドメイン取得**（推奨 — AdSense審査通過率が大幅向上）
- Route53で `.com` 約¥1,200/年 or お名前.com等
- CloudFront + ACM証明書（無料）でHTTPS化

#### 🟡 Step 3: プライバシーポリシーページ作成（コスト¥0）
- `privacy.html` を `frontend/` に追加してS3にデプロイ
- AdSense・GA4の利用規約で必須
- Claudeが自動生成可能（承認後即実装）

#### 🔵 Step 4: Google AdSense 申請（HTTPS化・独自ドメイン・PP完成後）
**審査条件（実績ベースの目安）**
- HTTPS対応済み ✅（Step 2完了後）
- 独自ドメイン（強く推奨）
- プライバシーポリシーあり ✅（Step 3完了後）
- コンテンツ量：常時20〜30トピック以上（現状OK）
- 月間PV：公式要件なし、実態では300〜1000PV/月程度が目安
- ⚠️ 注意：RSS集約+AI要約コンテンツは「オリジナルコンテンツ」としてグレーゾーン。審査で拒否される可能性あり。その場合はアフィリエイトに移行。

**AdSenseコード（審査通過後、既存の`.ad-slot` divを置き換え）：**
```html
<ins class="adsbygoogle"
     style="display:block"
     data-ad-client="ca-pub-XXXXXXXXXXXXXXXXX"
     data-ad-slot="XXXXXXXXXX"
     data-ad-format="auto"
     data-full-width-responsive="true"></ins>
<script>(adsbygoogle = window.adsbygoogle || []).push({});</script>
```

#### 🔵 Step 5: アフィリエイト（AdSense審査と並行・コスト¥0）
AdSenseの代替または補完として。審査が通らなくても収益化できる。

- **A8.net**（国内最大のアフィリエイトASP）— 登録無料、審査緩め
  - ニュースジャンルに合わせた広告（ニュースアプリ、VOD、金融系）を`.ad-slot`に配置
- **Amazon アソシエイト**（承認率が高い）
  - トピックの話題に関連するAmazon商品をカード下部にリンク表示
  - 例：テック系ニュース→ガジェット、政治系→関連書籍

### 推奨実装順序（PO承認ベース）

| 優先度 | タスク | コスト | 想定工数 | 効果 |
|---|---|---|---|---|
| 🔥 最優先 | Cloudflare Web Analytics追加 | ¥0 | 30分 | PV実態把握 |
| 高 | CloudFront + HTTPS化 | ¥0 | 1時間 | AdSense申請解禁 |
| 高 | プライバシーポリシーページ | ¥0 | 30分 | AdSense必須要件充足 |
| 中 | 独自ドメイン取得 | ¥1,200/年 | 1時間 | 審査通過率向上 |
| 中 | Google AdSense申請 | ¥0 | 申請のみ | 広告収益（審査2〜4週間） |
| 中 | A8.net登録・広告設置 | ¥0 | 1時間 | 即日収益化可能 |

---

## 作業ログ
- 2026-04-20: コード一式確認。AWSデプロイ完了。30分ごと自動実行稼働中。
- 2026-04-21 09:30: CEO秘書定期実行開始。P003本番稼働確認。apply-fixes.yml修正。P003 UI改善。deploy-p003.ymlにEventBridgeスケジュール設定ステップ追加。品質改善の次フェーズを定義。
- 2026-04-21 16:00: CEO日次ルーティン実行。品質改善体制を確認する提案#002を作成。
- 2026-04-22 09:00: CEO日次ルーティン実行。本番稼働継続確認。EventBridge 30分自動実行が正常に稼働していることを確認。Lambda handler.py コード品質レビュー完了。セキュリティ・ライセンス確認完了（リスクなし）。品質改善体制確定待ち。
- 2026-04-22: 収益化計画策定。フロントエンドに`.ad-slot`プレースホルダー実装済み確認。
             Cloudflare Analytics推奨・CloudFrontによるHTTPS化・AdSense申請ロードマップ記録。
             X自動投稿エージェント・catchup.html・processor Lambda実装完了。
