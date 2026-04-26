# Flotopic (P003) インフラ移行戦略

> 対象読者: ナオヤ（一人開発者）+ Claude Code  
> 最終更新: 2026-04-24  
> 方針: **今は変えない。でも、いつ・何を変えるかだけは決めておく。**

---

## 現状スナップショット

| レイヤー | 現構成 | 課題 |
|---|---|---|
| DB | DynamoDB `p003-topics`（META + SNAP の混在シングルテーブル） | GSIなし・スキーマ変更が本番即影響 |
| API | S3 `api/topics.json`（全件一括JSON） | 肥大化するとフロント初回ロードが重くなる |
| Compute | Lambda 4本（fetcher/processor/lifecycle/analytics） | 都度ZIPデプロイ・コールドスタート未対策 |
| Frontend | S3静的ホスティング + CloudFront | 現状問題なし |
| Auth | Google Sign-In（クライアントサイド） | ユーザーデータがDB未統合 |

---

## フェーズ定義

### Phase 1 — 〜月1,000PV（現状）

**方針: 何も変えない。コードを書くな。データを貯めろ。**

この段階でインフラに手を入れるのは時間の無駄。ユーザーが本当に何を読むかが分からない状態で最適化しても、最適化の方向が間違える。やるべきことはデータ蓄積だけ。

**この期間にやっていいこと（インフラ以外）:**
- topics.jsonのサイズを毎週確認してログに残す
- DynamoDBのアイテム数・消費RCUを週1回メモする
- CloudFrontのキャッシュヒット率を確認する
- Lambda実行時間のP99を確認する

**やってはいけないこと:**
- GSI追加（読みパターンが確定していない）
- ページネーションAPI化（トラフィックゼロで最適化は無意味）
- テーブル再設計（既存データ移行コストが見合わない）

---

### Phase 2 — 月1万PV（DAU 300〜500人規模）

**移行判断トリガー（いずれか1つ）:**
- `api/topics.json` のファイルサイズが **1MB** を超えた
- CloudFrontのキャッシュヒット率が **70%** を下回った
- Lambda fetcher の実行時間が **25秒** を超え始めた（タイムアウト30秒に近づく）
- DynamoDBの月間コストが **$10** を超えた

**この段階でやること:**

#### 2-1. topics.json の分割（最優先）

```
現状: api/topics.json（全件）
　↓
次: api/topics-active.json（activeのみ）
　　api/topics-legacy.json（legacy/archived）
　　api/topics-genre-{genre}.json（ジャンル別）
```

フロントエンドはまずactive JSONだけ読む。ユーザーがジャンルフィルタを使ったときだけ追加JSONをfetch。これだけで初回ロードの体感は大幅改善。

実装は `lifecycle/handler.py` のS3書き込み部分を分割するだけで対応可能。フロント側も `app.js` の `loadTopics()` を条件分岐するだけ。

#### 2-2. DynamoDBにGSI追加（lifecycle-index）

現状のクエリパターン:
- テーブルフルスキャン → S3 topics.json で代替（Lambda側で全件取得してS3に書く）

追加すべきGSI（Phase 2では1本だけ）:

```
GSI名: lifecycle-index
PK: lifecycleStatus（active / cooling / archived / legacy）
SK: velocityScore（数値、降順スキャン用）
```

これがあると「activeトピックをスコア順に取得」がO(n)スキャンではなくQuery一発で取れる。lifecycle Lambdaの整理処理も高速化する。

**GSI追加の安全手順:**
1. AWSコンソールまたはCLIでGSIを追加（既存データへの影響なし・オンライン追加可能）
2. Lambda側でGSIを使う新しい読み取りコードを書いて動作確認
3. 古いスキャンコードを残したままGSIコードをfeature flagで有効化
4. 数日様子を見て問題なければ古いコードを削除

#### 2-3. Lambda Provisioned Concurrency（processor のみ）

processor Lambdaは1日3回バッチ実行なのでコールドスタートは許容できるが、analytics Lambdaはユーザーの閲覧アクション起点で呼ばれる。DAU300人を超えたら analytics に Provisioned Concurrency 1〜2を設定する。コストは月$2〜4程度。

---

### Phase 3 — 月10万PV（DAU 3,000〜5,000人規模）

**移行判断トリガー（いずれか1つ）:**
- Lambda analyticsの同時実行数が **50** を超える場面が出始めた
- DynamoDBの読み取りがスロットリングされ始めた
- `api/topics-active.json` が **500KB** を超えた
- ページ読み込み（TTI）が **3秒** を超えるとCloudWatchで検知

**この段階でやること:**

#### 3-1. ページネーションAPI化

S3静的JSONから、Lambda FunctionURLベースの簡易APIに切り替える。

```
GET /api/topics?page=1&limit=20&genre=politics&sort=velocity
→ Lambda が DynamoDB GSI からQueryして返す
```

S3 topics.json は廃止ではなく「全件バックアップ用」として残す（他サービスが使う可能性があるため）。フロントエンドはエンドポイントを切り替えるだけ。

フレームワークは不要。Lambda + Function URL + CloudFront のキャッシュで十分。API GatewayはPhase 4まで不要。

#### 3-2. DynamoDBテーブル分離（ユーザーデータ）

現状はGoogleログインしてもユーザーデータがDBに入っていない（localStorage依存）。Phase 3ではユーザーの行動データを別テーブルで管理し始める。

```
テーブル: p003-users
PK: userId（Google sub）
SK: topicId
Attributes: favorited（bool）、viewedAt（timestamp）、readDuration（秒）
```

`p003-topics` とは**別テーブルで維持する**。統合しない理由:
- ユーザーデータはGDPR/個人情報対応で削除要件が違う
- アクセスパターンが完全に別（トピックは全件読み、ユーザーデータは個人単位）
- 将来的に「ユーザーデータだけS3にエクスポート」などの分離操作がしやすい

#### 3-3. GSI追加（genre-index、velocity-index）

```
GSI名: genre-index
PK: genre（politics / tech / economy / ...）
SK: velocityScore（降順）

GSI名: velocity-index
PK: lifecycleStatus
SK: updatedAt（降順、新着順クエリ用）
```

これでジャンル別ページ、新着順ページが DynamoDB Queryだけで実現できる。

#### 3-4. CloudFrontキャッシュポリシーの最適化

現状はデフォルトポリシー。Phase 3では:
- `api/topics-active.json`: TTL 60秒（processor更新間隔に合わせる）
- `api/topics-genre-*.json`: TTL 300秒
- `topic.html` などの静的ページ: TTL 86400秒（1日）
- Lambdaエンドポイント（ページネーション）: TTL 30秒

---

### Phase 4 — 月100万PV以上

**前提: このフェーズに達したら設計を一から見直す。ここに書くのはあくまで方向性。**

この段階では一人開発の限界を超えているか、少なくともインフラ管理に専任の時間が必要になる。

**検討が必要な変更:**

- **Aurora Serverless v2 への移行検討**: DynamoDBは柔軟なクエリ（「先週最もお気に入りされたトピックを genre × lifecycle × user属性でクロス集計する」など）が苦手。RDBが必要になるユースケースが出てくる可能性がある。
- **CloudFront Functions / Lambda@Edge**: パーソナライズ配信（ユーザーの閲覧履歴に基づいてトピックの順序を変える）が必要になった場合に検討。
- **DynamoDB DAX**: 読み取りが秒間数百件を超えてスロットリングが頻発し始めたら導入。それまでは不要。
- **SQS + 非同期処理**: analytics の書き込みが同期だと遅延が目立ち始める。EventBridgeまたはSQSでバッファリングする。
- **コンテナ化（ECS Fargate）**: fetcher Lambdaが30秒制限に引っかかり始めたらFargateタスクに移行。

---

## ゼロダウンタイム移行パターン

### Dual-write（新旧両方に書く期間）

スキーマ変更や新テーブル追加の際に使う基本パターン。

```
Step 1: 新フィールド/テーブルへの書き込みを追加する（読みはまだ旧）
Step 2: 既存データを新フィールドにバックフィル（Lambdaバッチで）
Step 3: 読み取りを新フィールドに切り替える（feature flagで）
Step 4: 旧フィールドへの書き込みを止める（1〜2週間後）
Step 5: 旧フィールドのデータをDynamoDB TTLで削除
```

**Flotopicでの適用例（storyTimeline追加の際にやったこと）:**
`storyTimeline` を追加するとき、既存の `aiSummary` を即削除するのではなく、新フィールドとして追加しつつ古いフィールドも残した。これがDual-writeの最小形。

### Feature Flag（Lambda環境変数で管理）

コードに `if/else` を書いてフラグで切り替える。

```python
# Lambda環境変数: USE_GSI_LIFECYCLE_INDEX = "true" | "false"
USE_GSI = os.environ.get("USE_GSI_LIFECYCLE_INDEX", "false") == "true"

if USE_GSI:
    # 新しいGSIを使うコード
    items = query_by_gsi(lifecycle_status)
else:
    # 旧来のスキャン
    items = scan_all_topics()
```

切り替えはAWSコンソールで環境変数を変えるだけ。コードデプロイ不要。問題があれば即戻せる。

**運用ルール:**
- feature flagは `FF_` プレフィックスをつけて環境変数を管理する
- 古いフラグは2週間以上経過したら削除する（負債化防止）
- フラグを追加するたびに `lambda/README.md` に記録する

### Blue-Greenデプロイ（フロントエンド）

CloudFront + S3でのフロントエンド更新に使える。

```
現状: prod バケット = 本番
　↓
Blue-Green:
　blue バケット（現本番 = p003-news-946554699567）
　green バケット（新バージョン = p003-news-green-946554699567）
　CloudFront の Origin をgreenに切り替え → 問題なければ確定
　問題あればblueに戻す（DNS変更なしで30秒以内）
```

現状のステージング環境（`p003-news-staging-946554699567`）がgreenバケット相当の役割を担っている。本番切り替えはCloudFrontの Origin を変えるだけで実現できる。

### DynamoDBスキーマ変更の安全な手順

DynamoDBはスキーマレスなので「マイグレーション」の概念が薄い。それが罠になることも多い。

**安全なパターン（後方互換フィールド追加）:**

```
1. 新フィールドを追加する（既存アイテムには存在しない）
2. Lambda側で「フィールドがない場合のデフォルト値」を必ず実装する
3. 新規書き込み時から新フィールドを含める
4. 旧アイテムはアクセスされたタイミングで新フィールドを追記（lazy migration）
5. 必要なら全件バックフィルLambdaを一回走らせる
```

**やってはいけないパターン:**

```
× フィールド名を変更する（旧名で書かれたアイテムが読めなくなる）
× PKやSKの型を変更する（テーブル再作成が必要）
× アイテムのタイプ構造（META vs SNAP）を変更する（全件バックフィル必須）
```

---

## topics.json 肥大化対策ロードマップ

### 現状（〜1MB）

全トピック一括JSON。processor Lambdaが実行のたびに全件書き直す。

**監視すること:** S3オブジェクトのサイズをLifecycle Lambdaのログに出力する（1行追加するだけ）。

```python
# lifecycle/handler.py に追加
response = s3.head_object(Bucket=BUCKET, Key='api/topics.json')
print(f"topics.json size: {response['ContentLength'] / 1024:.1f}KB")
```

### 次のステップ（1MB超えたとき）

**ステップ1: active/archived 分離**

```python
# processor/handler.py の S3書き込み部分を分割
active_topics = [t for t in all_topics if t['lifecycleStatus'] == 'active']
s3.put_object(Key='api/topics-active.json', Body=json.dumps(active_topics))
s3.put_object(Key='api/topics.json', Body=json.dumps(all_topics))  # 既存は残す（互換性）
```

フロントは `topics-active.json` を読み、「もっと見る（過去のトピック）」押下時だけ `topics.json` をfetch。

**ステップ2: ジャンル別分割（2MB超えたとき）**

```
api/topics-active.json — activeのみ（フロントデフォルト）
api/topics-genre-politics.json
api/topics-genre-tech.json
api/topics-genre-economy.json
...
```

フロント側はジャンルフィルタ時に該当JSONだけfetchする。

**ステップ3: ページネーションAPI化（5MB超えたとき）**

Lambda Function URLに切り替え。CloudFrontでキャッシュ。topics.jsonは廃止。

---

## DynamoDB拡張計画

### 現状の問題点

- GSIが1本もない → 全操作がテーブルスキャンかPK直接アクセス
- S3 topics.json が「非正規化された全件キャッシュ」として機能しており、これがGSI不在を隠蔽している
- ユーザーが増えてGSIが欲しくなっても「後から追加できる」のがDynamoDBの強み → 慌てない

### 追加すべきGSI候補（優先度順）

| GSI名 | PK | SK | 用途 | 追加タイミング |
|---|---|---|---|---|
| lifecycle-index | lifecycleStatus | velocityScore | active/cooling を速度順に取得 | Phase 2（月1万PV） |
| genre-index | genre | velocityScore | ジャンル別トップトピック取得 | Phase 3（月10万PV） |
| velocity-index | lifecycleStatus | updatedAt | 新着順クエリ | Phase 3 |
| user-activity-index | userId | viewedAt | ユーザー閲覧履歴（別テーブル） | Phase 3 |

**GSI追加コスト注意点:**
- GSIは追加のストレージとRCU/WCUを消費する
- GSIが増えると書き込みコストが増える（書き込み時に全GSI更新）
- Phase 2では1本だけ追加して様子を見る

### ユーザーデータとの統合方針

**結論: 別テーブルで維持する。統合しない。**

```
p003-topics — トピックデータ（公開情報・全ユーザー共通）
p003-users  — ユーザー行動データ（個人情報・要削除対応）
```

統合しない理由は上記Phase 3の説明通り。将来的にユーザーデータだけ別リージョンに移すケースや、GDPR対応で「このユーザーのデータを全削除」する操作が別テーブルの方が圧倒的に簡単。

---

## 移行を安全にするための今からできる準備

### 1. フィールド追加は後方互換で（削除しない）

DynamoDBのフィールドは「使わなくなっても消さない」を基本とする。消す場合は以下の手順を踏む:
1. Lambda側で「このフィールドを書かない」だけにする（既存アイテムに残っていても無害）
2. 3ヶ月後、TTLで自然消滅するか、バッチで消す

フロントエンドのJSも「フィールドがない場合のデフォルト処理」を必ず書く。

```javascript
// 悪い例
const phase = topic.storyPhase;  // undefinedになる可能性

// 良い例
const phase = topic.storyPhase ?? '不明';
```

### 2. Lambda環境変数でfeature flagを管理する習慣

新機能を実装するとき、いきなり全ユーザーに当てない。環境変数でON/OFF制御する。

環境変数命名規則:
- `FF_xxx`: feature flag（`FF_USE_PAGINATION_API`など）
- `CONFIG_xxx`: 設定値（`CONFIG_MAX_TOPICS_PER_PAGE`など）

### 3. ステージング環境との差分を最小化

現在のステージング環境はフロントエンドのみ別バケット（Lambda/DynamoDBは本番共有）。この状態で「ステージングで問題ないから本番に出す」は**DB操作のテストになっていない**ことに注意。

Lambda変更時は:
- 本番Lambdaの `$LATEST` に上書きデプロイ → すぐ本番影響
- 対策: Lambda エイリアス（`prod` / `staging`）を使って切り替える（Phase 2で検討）

### 4. DynamoDBのPoint-in-Time Recovery（PITR）を有効化

**今すぐやること（5分で終わる）:**

```bash
aws dynamodb update-continuous-backups \
  --table-name p003-topics \
  --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true \
  --region ap-northeast-1
```

コスト: ストレージ量に応じて数十円〜数百円/月。データ消失リスクに対して安すぎるので即設定する。

```bash
# 確認
aws dynamodb describe-continuous-backups \
  --table-name p003-topics \
  --region ap-northeast-1
```

### 5. S3バケットのバージョニングを有効化

topics.json などのS3オブジェクトが意図せず上書きされたとき、30秒で戻せる。

```bash
aws s3api put-bucket-versioning \
  --bucket p003-news-946554699567 \
  --versioning-configuration Status=Enabled
```

古いバージョンが溜まりすぎないようにLifecycleルールも設定:

```bash
# 30日以上前の旧バージョンを削除
aws s3api put-bucket-lifecycle-configuration \
  --bucket p003-news-946554699567 \
  --lifecycle-configuration '{
    "Rules": [{
      "ID": "delete-old-versions",
      "Status": "Enabled",
      "NoncurrentVersionExpiration": {"NoncurrentDays": 30}
    }]
  }'
```

---

## 移行判断トリガー指標（まとめ）

| 指標 | 現状 | Phase 2移行トリガー | Phase 3移行トリガー |
|---|---|---|---|
| topics.json サイズ | 数十KB | **1MB超** | **5MB超** |
| 月間PV | ほぼゼロ | **1万PV** | **10万PV** |
| Lambda analytics 同時実行数 | 1〜2 | **20超** | **50超** |
| DynamoDB 月額コスト | $1〜2 | **$10超** | **$50超** |
| CloudFrontキャッシュヒット率 | 測定中 | **70%未満** | — |
| Lambda fetcher 実行時間P99 | 数秒 | **25秒超** | **タイムアウト頻発** |
| Lambda analytics エラー率 | ほぼ0 | **1%超** | **5%超** |
| フロントTTI（初回表示時間） | 測定中 | **3秒超** | **5秒超** |

### 監視の始め方（今すぐ追加すべき）

CloudWatchに以下のカスタムメトリクスを送るLambdaを追加するか、既存Lambdaのログに出力するだけでも可。

```python
# 各Lambdaの末尾に追加するだけ
import boto3, json
cloudwatch = boto3.client('cloudwatch', region_name='ap-northeast-1')

def emit_metric(name, value, unit='Count'):
    cloudwatch.put_metric_data(
        Namespace='P003/Flotopic',
        MetricData=[{'MetricName': name, 'Value': value, 'Unit': unit}]
    )

# 例: fetcher終了時
emit_metric('TopicsProcessed', processed_count)
emit_metric('NewTopicsCreated', new_count)
```

---

## 優先アクション（今すぐやれること）

以下は移行とは別に、**今すぐコスト・リスクなしでできる準備**。

1. **DynamoDB PITR有効化** — 上記CLIコマンド1本。5分。データ消失保険。
2. **S3バージョニング有効化** — 上記CLIコマンド2本。5分。topics.json誤上書き保険。
3. **topics.jsonサイズのログ出力** — lifecycle/handler.py に3行追加。次回デプロイ時に含める。
4. **Lambda実行時間のCloudWatchアラーム設定** — fetcher が25秒を超えたらSlack通知。

---

*このドキュメントは状況が変化するたびに更新する。移行を実施したら「完了済み」に移動し、新たな課題を「未解決」に追記すること。*
