# Flotopic (P003) 運用設計ドキュメント

> 作成日: 2026-04-24  
> 対象読者: ナオヤ（一人開発者）、Claude Code  
> 目的: PVが増えても壊れないデプロイ・変更管理のルールを今のうちに決めておく

---

## 0. 基本スタンス

現状は「一人開発・ユーザーほぼゼロ」なので、プロセスを重くしすぎない。  
**「今すぐやること」と「PVが増えたらやること」を明確に分け、段階的に厳しくする。**

---

## 1. デプロイ安全基準（PVフェーズ別）

### フェーズ A：〜月1万PV（現状）

**基本方針**: 都度デプロイOK。スピード優先。

| 項目 | ルール |
|---|---|
| フロントエンド変更 | そのままデプロイOK |
| Lambda変更 | そのままデプロイOK |
| ステージング確認 | 推奨（必須ではない） |
| デプロイ時間帯 | 制限なし |
| 変更ログ | CLAUDE.mdの「完了済みタスク」に書く |

**今すぐやること**:
- [ ] ロールバック手順を一度だけ確認しておく（本項の「4. ロールバック手順」参照）
- [ ] Lambda versioning を有効にする（無料、後悔のないデプロイのため）

---

### フェーズ B：月1万〜10万PV

**基本方針**: 変更は確認してから。ただしプロセスは最小限。

| 項目 | ルール |
|---|---|
| UI変更 | **ステージング確認後**に本番デプロイ |
| Lambda変更 | 本番反映後**5分間のエラーログ監視**を必須化 |
| デプロイ時間帯 | **平日 10:00〜18:00 JST**（アクセスが集中しない時間帯） |
| 変更ログ | CLAUDE.mdの変更ログフォーマット（下記）に従い記録 |
| ロールバック | Lambda alias を使い、即切り戻し可能な状態を維持 |

**このフェーズに入ったらやること**:
- [ ] Lambda versioning + alias（`stable` エイリアス）の設定
- [ ] CloudWatch アラームのSlack通知設定（Lambda エラー率 > 5%）
- [ ] デプロイ前チェックリストを `deploy.sh` に組み込む

---

### フェーズ C：月10万PV以上

**基本方針**: ユーザー体験を守る。変更は慎重に。

| 項目 | ルール |
|---|---|
| 新機能 | フィーチャーフラグ（Lambda環境変数）でOFF状態でデプロイ → 確認後ON |
| UI大幅変更 | カナリアリリース（CloudFront関数でトラフィック分割） |
| デプロイ前 | ステージングで簡易負荷テスト（k6 or locust） |
| 変更凍結期間 | GW・年末年始・お盆の前後3日は原則デプロイ禁止 |
| インシデント対応 | 対応手順を本ドキュメントの「5. 監視・アラート設計」に従う |

**このフェーズに入ったらやること**:
- [ ] CloudFront の重み付きルーティングでカナリアリリース設定
- [ ] DynamoDB PITR（Point-in-Time Recovery）の有効化
- [ ] 変更凍結カレンダーをGitHub Issueで管理

---

## 2. UI変更の安全なやり方

### 破壊的変更 vs 非破壊的変更

| 分類 | 例 | 対応 |
|---|---|---|
| **非破壊的** | 新機能追加・CSSの微調整・文言変更・アイコン追加 | そのままデプロイOK |
| **破壊的** | ナビ構造の変更・主要UIの大幅変更・URL変更・localStorageキー変更 | 段階的に（下記手順） |

### 段階的UI変更の手順（破壊的変更の場合）

```
1. ステージング環境に反映
   bash projects/P003-news-timeline/deploy-staging.sh
   → URL: http://p003-news-staging-946554699567.s3-website-ap-northeast-1.amazonaws.com

2. 自分で最低1日使う
   → 実際に操作してみて違和感・バグを確認

3. （フェーズB以降）Cloudflare Analytics で旧UIとCLS/FCPを比較

4. 問題なければ本番反映
   bash projects/P003-news-timeline/deploy.sh

5. 本番反映後24時間はCloudflare Analyticsのエラー・直帰率を確認
```

### URL変更時の必須ルール

URL構造を変える場合は以下を**必ず同時に**実施する:

```
1. CloudFront FunctionまたはS3リダイレクトで旧URLを301リダイレクト
2. robots.txt の Disallow/Allow パスを更新
3. sitemap.xml の URL一覧を更新して S3 に再アップロード
4. CLAUDE.md に「旧URL → 新URL」の変更記録を残す
```

SEO的に旧URLのインデックスが引き継がれるまで**最低3ヶ月**はリダイレクトを維持する。

---

## 3. Lambda変更の安全な手順

### フィーチャーフラグの使い方

Lambda の環境変数で機能のON/OFFを制御する。

```bash
# 例：ストーリーモードを段階的に有効化
ENABLE_STORY_MODE=false   # まずOFFでデプロイ
ENABLE_STORY_MODE=true    # 動作確認後にON

# 設定変更（コード再デプロイ不要）
aws lambda update-function-configuration \
  --function-name p003-processor \
  --region ap-northeast-1 \
  --environment 'Variables={..., ENABLE_STORY_MODE=true}'
```

現在定義済みのフラグ候補:
- `ENABLE_STORY_MODE` — ストーリー型AI要約の有効化
- `ENABLE_AI_SUMMARY` — AI要約全体のON/OFF（ANTHROPIC_API_KEY必須）
- `MAX_API_CALLS` — Claudeへの最大呼び出し数（コスト調整用）

### Lambda変更の手順

```
1. コードを変更（ローカルで py_compile による構文チェック）
   python3 -m py_compile lambda/processor/handler.py

2. フィーチャーフラグOFFの状態でデプロイ
   bash projects/P003-news-timeline/deploy.sh

3. CloudWatch Logs で5分間エラーを確認（フェーズB以降は必須）
   aws logs tail /aws/lambda/p003-fetcher --follow --since 5m

4. 問題なければフィーチャーフラグをONに切り替え

5. さらに5分間ログ監視
```

### DynamoDBスキーマ変更ルール

| 操作 | 許可 |
|---|---|
| 新フィールドの追加 | ✅ OK（後方互換） |
| 既存フィールドの型変更 | ❌ NG（データ破損リスク） |
| 既存フィールドの削除 | ❌ NG（古いLambdaが壊れる） |
| GSI（インデックス）の追加 | ✅ OK（読み取り専用の影響なし） |
| テーブル削除・再作成 | ❌ 絶対NG（要ナオヤ承認） |

**既存フィールドは削除しない。フィールドを廃止したい場合は `_deprecated_` プレフィックスを付けて放置し、データ移行後に削除する。**

---

## 4. ロールバック手順

### フロントエンド（S3）のロールバック

S3には世代管理がないため、**デプロイ前にバックアップを取る習慣**をつける。

```bash
# デプロイ前バックアップ（deploy.sh冒頭に追加推奨）
BUCKET=p003-news-946554699567
DATE=$(date +%Y%m%d-%H%M%S)
aws s3 sync s3://${BUCKET}/ s3://${BUCKET}-backup/${DATE}/ --region ap-northeast-1

# ロールバック実行
ROLLBACK_DATE=20260424-120000  # 戻したいバックアップの日時
aws s3 sync s3://${BUCKET}-backup/${ROLLBACK_DATE}/ s3://${BUCKET}/ \
  --region ap-northeast-1 --delete

# CloudFrontキャッシュを即時クリア
aws cloudfront create-invalidation \
  --distribution-id E2Q21LM58UY0K8 \
  --paths "/*"
```

**フェーズB以降の推奨**: `deploy.sh` にバックアップステップを組み込む。

### Lambda のロールバック

Lambda versioning + alias を使うことで、コード再デプロイなしに即時切り戻しができる。

```bash
# 現在の $LATEST を新しいバージョンとして発行
aws lambda publish-version \
  --function-name p003-fetcher \
  --region ap-northeast-1

# stable エイリアスを前のバージョンに戻す
aws lambda update-alias \
  --function-name p003-fetcher \
  --name stable \
  --function-version 3   # 戻したいバージョン番号

# 確認
aws lambda get-alias --function-name p003-fetcher --name stable
```

**初期設定（今すぐやること）**:
```bash
# 各Lambdaにstableエイリアスを作成（初回のみ）
for func in p003-fetcher p003-processor p003-lifecycle; do
  aws lambda create-alias \
    --function-name $func \
    --name stable \
    --function-version '$LATEST' \
    --region ap-northeast-1
done
```

### DynamoDB のロールバック（フェーズC以降）

```bash
# PITRを有効化（月額コスト: テーブルサイズ × $0.20/GB）
aws dynamodb update-continuous-backups \
  --table-name p003-topics \
  --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true \
  --region ap-northeast-1

# ロールバック実行（指定時刻のスナップショットから新テーブルに復元）
aws dynamodb restore-table-to-point-in-time \
  --source-table-name p003-topics \
  --target-table-name p003-topics-restored \
  --restore-date-time 2026-04-24T10:00:00Z \
  --region ap-northeast-1
# ※ 復元先は別テーブル名になる。確認後に手動でデータを移行する
```

---

## 5. 監視・アラート設計

### 日次で見る指標（Cloudflare Web Analytics）

毎朝ざっくり確認する。異常があれば深掘りする。

| 指標 | 正常範囲 | 要注意 | 対応 |
|---|---|---|---|
| PV（日次） | 基準値 ±50% | 基準値の -70% 以下 | ソースURL・Lambdaエラーを確認 |
| 直帰率 | ～70% | 85%以上 | トップページのCLSやFCP確認 |
| CLS（累積レイアウトシフト） | 0.1以下 | 0.25以上 | 画像・フォントの遅延読み込みを確認 |
| FCP（初回描画） | 2秒以内 | 4秒以上 | S3 + CloudFrontのキャッシュ設定を確認 |

### Lambda エラー監視

**フェーズA（現状）**: デプロイ後に手動でログを確認。

```bash
# 直近1時間のエラーを確認
aws logs filter-log-events \
  --log-group-name /aws/lambda/p003-fetcher \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --filter-pattern "ERROR" \
  --region ap-northeast-1
```

**フェーズB以降**: CloudWatch アラームをSlack通知と連携。

```bash
# エラー率 > 5% で Slack に通知するアラーム設定例
aws cloudwatch put-metric-alarm \
  --alarm-name p003-fetcher-error-rate \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --dimensions Name=FunctionName,Value=p003-fetcher \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 5 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --alarm-actions arn:aws:sns:ap-northeast-1:946554699567:p003-alerts \
  --region ap-northeast-1
```

### 「異常」と判断するしきい値

| Lambda | 指標 | 警告 | 即対応 |
|---|---|---|---|
| p003-fetcher | エラー率 | > 5% | > 20% |
| p003-fetcher | 実行時間 | > 25秒 (timeout間近) | timeout発生 |
| p003-processor | Claudeエラー | 連続3回 | — |
| p003-lifecycle | 実行スキップ | 2週連続 | — |

### DynamoDB 消費キャパシティの確認

```bash
# テーブルのRCU/WCU消費状況を確認
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ConsumedReadCapacityUnits \
  --dimensions Name=TableName,Value=p003-topics \
  --start-time $(date -d '24 hours ago' --iso-8601=seconds) \
  --end-time $(date --iso-8601=seconds) \
  --period 3600 \
  --statistics Sum \
  --region ap-northeast-1

# テーブルサイズとアイテム数（週次確認推奨）
aws dynamodb describe-table \
  --table-name p003-topics \
  --region ap-northeast-1 \
  --query 'Table.{Items:ItemCount, SizeBytes:TableSizeBytes}'
```

p003-topics の DynamoDB 662K件ブロート問題の再発防止として、
月次でアイテム数が異常増加していないかチェックする。

---

## 6. 変更管理ルール

### CLAUDE.md 変更ログのフォーマット

`CLAUDE.md` の「完了済みタスク」セクションに以下のフォーマットで追記する。

```markdown
### 完了済み（YYYY-MM-DD フェーズA/B/C）

#### 変更タイトル（対象: fetcher / processor / frontend 等）
- ✅ **変更内容** — 具体的に何をどう変えたか
- ✅ **確認内容** — ステージング確認・ログ確認・動作確認
- ⚠️ **既知の問題** — 残った問題や制限（ある場合のみ）

**ロールバック**: `bash projects/P003-news-timeline/rollback.sh <version>` で戻せる
```

### やってはいけないこと

| NG | 理由 | 代替手段 |
|---|---|---|
| 本番DynamoDBを直接AWSconsoleで書き換える | データ整合性の破壊・追跡不能 | スクリプト経由で変更・ログを残す |
| ANTHROPIC_API_KEYをコードにハードコードする | GitHubに漏れる・CI検知対象 | 環境変数 or AWS Secrets Manager |
| `aws s3 rm s3://p003-news-*` を `--recursive` なしで実行 | 誤削除リスク | `--dryrun` で確認してから実行 |
| Lambda関数を削除してから再作成する | versioning履歴が消える | コード上書きデプロイのみ |
| p003-topics テーブルを削除する | 全データ消失 | 要ナオヤ明示承認 + PITRバックアップ後のみ |
| 深夜にデプロイする（フェーズB以降） | 問題発生時に気づかない | 平日日中の実施 |

### Claude Code への指示の出し方

**悪い例（動作確認なし）**:
```
Lambda のタイムアウトを30秒に変えて deploy.sh を実行して
```

**良い例（確認ステップを明示）**:
```
Lambda のタイムアウトを30秒に変更して deploy.sh を実行してください。
その後、CloudWatch Logs で直近5分のエラーがないことを確認し、
エラーがなければ「完了」と報告してください。エラーがあれば自力で修正してください。
```

**重要**: Claude Code に「動作確認してから完了報告」を徹底させるには、
指示の中に「確認ステップ」を明示することが最も効果的。

---

## 7. ステージング環境の使い方

```
本番URL:     https://flotopic.com
ステージングURL: http://p003-news-staging-946554699567.s3-website-ap-northeast-1.amazonaws.com
```

注意: ステージングは **フロントエンドのみ** 別環境。
Lambda・DynamoDB は本番と共有なので、Lambda変更のテストは本番に直接影響する。

**ステージングデプロイ**:
```bash
bash projects/P003-news-timeline/deploy-staging.sh
```

**ステージングで確認すべきこと**:
1. 画面が壊れていないか（レイアウト崩れ・JSエラー）
2. 主要機能が動くか（トピック一覧表示・詳細表示・検索）
3. モバイル表示が崩れていないか（Chrome DevTools の responsive モード）
4. （フェーズB以降）Cloudflare Analytics のCLS/FCP値

---

## 8. 緊急対応フロー

本番が壊れていることを検知した場合:

```
1. 状況確認（2分以内）
   - Cloudflare Analytics でエラー率急増を確認
   - CloudWatch Logs で直近のLambdaエラーを確認

2. 原因の切り分け（5分以内）
   - 直前にデプロイがあった → ロールバックを検討
   - Lambdaエラー → CloudWatch で詳細確認
   - S3/CloudFrontの問題 → AWSコンソールで確認

3. 対応（15分以内）
   - フロントエンド起因 → S3に前バージョンを再アップ + CloudFrontキャッシュクリア
   - Lambda起因 → stableエイリアスを前バージョンに切り替え
   - DynamoDB起因 → 読み取り専用モードに切り替え + PITRで復元

4. 収束確認
   - エラーログが止まっていることを確認
   - 主要機能が動くことを手動確認

5. 記録
   - CLAUDE.md の未解決の問題セクションに経緯を残す
   - 再発防止策を翌日中に実装
```

---

## 付録：今すぐやること（チェックリスト）

現在のフェーズAで今日中にやるべき最小限:

- [ ] Lambda versioning を3つの関数（fetcher/processor/lifecycle）で有効化
- [ ] `stable` エイリアスを作成（本項「4. ロールバック手順」のコマンド）
- [ ] `deploy.sh` 冒頭にS3バックアップステップを追加
- [ ] ロールバック手順を一度手元で試しておく

フェーズBに入ったらすぐやること:
- [ ] CloudWatch アラーム + SNS + Slackのエラー通知連携
- [ ] デプロイ時間帯を平日10:00〜18:00に制限するリマインダー設定
