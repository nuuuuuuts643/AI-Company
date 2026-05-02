# AWS コスト削減プラン (2026-05-02 PO 指示・Cowork 起票)

> **PO 指示**: 「AWS 側のコストを下げて欲しい。理想は 0。品質は上げる方向で」(2026-05-02 20:50 JST)
> **方針確認**: ① AWS 内で限界まで削減 (脱 AWS は今回はしない) ② 全品質方向 (フェーズ 2 / フェーズ 1 / フェーズ 3) ③ アーキ移行も視野
> **起案**: Cowork セッション (Sonnet)・本ドキュメントを TASKS.md `T2026-0502-COST-*` シリーズで実装に分解する

---

## 1. 現状アーキテクチャ (棚卸し: 2026-05-02 20:50 JST)

### Lambda 関数 (13 個)

| 関数名 | 用途 | 起動頻度 | Memory / Timeout | コスト Tier |
|---|---|---|---|---|
| `p003-fetcher` | RSS 取得 + 新規トピック検出 | rate(30 min) = 48 回/日 | 512MB / 900s | **大** |
| `p003-processor` | AI 要約生成 (Anthropic Claude API) | cron(30 20,8) = 2 回/日 (5:30/17:30 JST) | 512MB / 900s | **大** (Anthropic 従量) |
| `p003-api` | REST API (topics/health) | API Gateway 経由 | 128MB / 30s | 中 |
| `p003-comments` | コメント CRUD | API Gateway 経由 | 128MB / 10s | 小 |
| `p003-tracker` | アクセス・行動トラッキング | API Gateway 経由 | 128MB / 10s | 中 |
| `p003-contact` | お問い合わせ送信 | API Gateway 経由 | 128MB / 10s | 小 |
| `flotopic-auth` | Google ID トークン検証 | API Gateway 経由 | 128MB / 10s | 小 |
| `flotopic-favorites` | お気に入り CRUD | API Gateway 経由 | 128MB / 10s | 小 |
| `flotopic-analytics` | ユーザー行動集計 | API Gateway 経由 | 128MB / 10s | 中 |
| `flotopic-cf-analytics` | CloudFront ログ集計 | cron(0 22 * * ? *) = 1 回/日 | 128MB / 60s | 中 |
| `flotopic-bluesky` | Bluesky 自動投稿 | rate(30 minutes) = 48 回/日 | 128MB / 60s | **大** (頻度過剰) |
| `flotopic-lifecycle` | 古いトピックの S3 アーカイブ | cron(0 2 ? * MON *) = 週 1 | 128MB / 60s | 小 |
| `flotopic-contact` | (重複疑い・要確認) | - | - | 要確認 |

### DynamoDB テーブル (11 個)

| テーブル名 | 用途 | 状態 | 削減候補 |
|---|---|---|---|
| `p003-topics` | メイン (記事・AI 要約) | 稼働中 ✅ | 維持 |
| `ai-company-comments` | コメント | 稼働中 ✅ | 維持 |
| `ai-company-bluesky-posts` | Bluesky 投稿履歴 | 稼働中 ✅ | 維持 |
| `flotopic-favorites` | お気に入り | 稼働中 ✅ | 維持 |
| `flotopic-analytics` | 行動ログ | 稼働中 ✅ | 維持 |
| `flotopic-rate-limits` | レートリミット | 稼働中 ✅ | 維持 |
| `flotopic-users` | ユーザー (Google ID 連携) | 稼働中 ✅ | 維持 |
| `ai-company-memory` | P005 メモリ DB | **未使用** (system-status.md「保留」) | **削除候補 A1** |
| `ai-company-x-posts` | X (Twitter) agent 投稿履歴 | **未使用** (system-status.md「Editorial/Marketing/Revenue/SEO/DevOps Agent は schedule 停止中」) | **削除候補 A1** |
| `ai-company-agent-status` | エージェント状態 | **未使用** (同上) | **削除候補 A1** |
| `ai-company-audit` | (用途不明・要確認) | 要確認 | **要確認 → 削除候補** |

### EventBridge スケジュール

| ルール名 | スケジュール | 起動先 | 月間 invocation |
|---|---|---|---|
| `p003-fetcher-schedule` | rate(30 minutes) | p003-fetcher | ~1,440 |
| `p003-processor-schedule` | cron(30 20,8 * * ? *) | p003-processor | ~60 |
| `flotopic-bluesky-schedule` | rate(30 minutes) | flotopic-bluesky | ~1,440 ⚠️ **過剰** |
| `flotopic-cf-analytics-daily` | cron(0 22 * * ? *) | flotopic-cf-analytics | ~30 |
| `flotopic-lifecycle-weekly` | cron(0 2 ? * MON *) | flotopic-lifecycle | ~4 |

### その他 (確認できた範囲)

- **API Gateway**: `flotopic-api` (HTTP API・x73mzc0v06) — 全 API トラフィックを集約
- **CloudFront**: `E2Q21LM58UY0K8` (flotopic.com) — 静的アセット配信
- **S3**: バケット 1〜2 個 (frontend assets + topic JSON ストレージ)
- **CloudWatch Logs**: 各 Lambda の log group (デフォルト無期限保存と推測)

---

## 2. 削減候補 (品質影響 × 効果 × 実装コストで分類)

### ✅ Phase A: 即時削減 (品質影響ゼロ・実装コスト低・1〜3 日)

| ID | 内容 | 期待削減 (月額) | リスク | 実装ファイル |
|---|---|---|---|---|
| **COST-A1** | 未使用 DynamoDB テーブル削除 (`ai-company-memory` / `-x-posts` / `-agent-status` / `-audit` 計 4 個・**事前 scan で書き込み 0 件確認後**) | $1〜3 (PROVISIONED の場合) / Storage 分は微 | 低 (scan 実証必須・誤削除なら戻せない) | AWS CLI `delete-table` (Cowork) + IAM policy 該当 ARN 削除 |
| **COST-A2** | CloudWatch Logs 全 log group の `retention-in-days` を **30 日**に統一 (現在は無期限のものが大半と推測) | $2〜5 (累積ログ量に依存) | ゼロ (古いログは debug にしか使わない・必要なら S3 export) | `scripts/set_log_retention.sh` 新設 + Cowork で全 log group に適用 |
| **COST-A3** | `flotopic-bluesky` schedule を **rate(30 minutes) → cron(0 21,3,8 * * ? *) (1 日 3 回・朝 6 / 昼 12 / 夕 17 JST)** に変更 | $1〜2 (Lambda invoke + Anthropic API 呼出減) | ゼロ (1 日 48 投稿は過剰・読者の Bluesky TL 汚染要因にもなる) | `projects/P003-news-timeline/deploy.sh` の bluesky schedule 部分 |
| **COST-A4** | 各 Lambda の **Reserved Concurrency** を SEC17 で設定済 (fetcher=2, processor=2 等) → コスト爆発防止 ✅ 既に対処済 | (T2026-0502-SEC17 に統合・本タスクで重複起票しない) | - | (確認のみ) |
| **COST-A5** | S3 バケットの **Lifecycle Policy** で 90 日超の non-current version を削除 (バケットが versioning 有効化されてれば) | $1〜3 (累積に依存) | ゼロ | `aws s3api put-bucket-lifecycle-configuration` |

**Phase A 期待合計: 月 $5〜13 削減 / 実装 1〜3 日**

### 🟡 Phase B: 中期削減 (アーキ簡素化・1〜2 週間)

| ID | 内容 | 期待削減 (月額) | リスク | 実装ファイル |
|---|---|---|---|---|
| **COST-B1** | **API Gateway HTTP API → Lambda Function URL 移行**。flotopic-api を構成する 8 ルートを各 Lambda 直接 (Function URL + CORS) に切替 → API Gateway 廃止 | $5〜15 (HTTP API 1M req $1.00 + Function URL は無料) | 中 (CORS 再設定・auth Lambda チェーン要確認・Frontend の API ベース URL 変更) | 各 Lambda + `frontend/js/config.js` の `API_BASE` |
| **COST-B2** | **CloudFront キャッシュ TTL 拡張** (静的アセット 24h → 7 日 / topics-card.json は短くキープ) → オリジン (S3 / API Gateway) リクエスト削減 | $2〜8 (CloudFront origin request 削減) | 低 (デプロイ時に `aws cloudfront create-invalidation` で対処可能) | CloudFront Cache Policy + `deploy-p003.yml` の invalidation |
| **COST-B3** | `flotopic-cf-analytics` の必要性再評価 — 既に CloudFront access logs に記録あり / Notion 集計とも重複しているなら廃止 | $1〜3 (Lambda invoke + DynamoDB 書込) | 低 (実利用要確認) | (要調査タスク) |
| **COST-B4** | `flotopic-contact` と `p003-contact` の重複解消 (どちらか 1 つに統合) | $0.5 | 低 | 該当 Lambda のどちらかを廃止 |
| **COST-B5** | DynamoDB を **Provisioned Capacity 1WCU/1RCU + Auto Scaling** に切替 (低トラフィックなら On-Demand より安い) — `flotopic-rate-limits` `flotopic-favorites` 等 | $1〜5 (使用量による・要 CloudWatch メトリクス確認) | 低 (Auto Scaling で振れに耐える) | `aws dynamodb update-table` |

**Phase B 期待合計: 月 $9〜31 削減 / 実装 1〜2 週間**

### 🟠 Phase C: アーキ移行 (中長期・1 ヶ月超・要設計)

| ID | 内容 | 期待削減 (月額) | リスク | 実装ファイル |
|---|---|---|---|---|
| **COST-C1** | `p003-topics` の **読み取りパス**を S3 JSON 直配信に切替 (CloudFront キャッシュ前提)。書き込みは引き続き DynamoDB → 読込時に S3 へ snapshot して配信 | $5〜15 (DynamoDB read capacity 大幅減) | 中 (整合性遅延・既に topics-card.json として S3 配信していれば一部実装済) | `lambda/api/handler.py` (read 経路除去) + `lambda/processor/handler.py` (snapshot 出力) |
| **COST-C2** | `p003-tracker` を **CloudFront Functions** に移行 (CF Functions は $0.10 / 1M req と Lambda の 1/6) | $2〜5 | 中 (機能制約・JS のみ・100ms timeout) | `infra/cf-tracker-function.js` 新設 |
| **COST-C3** | `flotopic-analytics` の集計ロジックを **CloudFront access logs + Athena** に置換 (Lambda 廃止) | $1〜3 | 中 (集計の遅延化・現在の即時統計を諦める必要あり) | (要設計) |

**Phase C 期待合計: 月 $8〜23 削減 / 実装 1 ヶ月超**

### ⚠️ 品質と相反するため**提案しない**もの

| 候補 | 削減効果 | なぜ却下するか |
|---|---|---|
| `p003-processor` 頻度削減 (2 回/日 → 1 回/日) | 月 $5〜10 | フェーズ 2 完了条件「keyPoint 充填率 70%」に直撃。8.7% から 70% に持っていく途中で逆行 |
| `p003-fetcher` 頻度削減 (30 min → 60 min) | 月 $2〜5 | 鮮度 SLI (freshness) 悪化リスク。フェーズ 2 で AI 4 軸の鮮度を上げてる流れと相反 |
| Anthropic Claude API モデル降格 (Sonnet → Haiku) | API 従量 50%減 | keyPoint 平均長が現状 43.8 字で短すぎて品質問題 → 更にモデル降格は逆効果 |

### ⚠️ 別タスクで先に決着が必要

| 候補 | 状態 | 紐付くタスク |
|---|---|---|
| Google Trends API 機能の維持 / 削除判断 | PO 判断待ち (T2026-0502-F) | T2026-0502-F が決着すれば trends_utils.py + 関連 Lambda 経路を削除して `p003-fetcher` invoke 時間も短縮 |

---

## 3. 期待削減量サマリ

| Phase | 期待削減 (月額) | 実装期間 | 品質影響 |
|---|---|---|---|
| A (即時) | $5〜13 | 1〜3 日 | ゼロ |
| B (中期) | $9〜31 | 1〜2 週間 | 低 (再構成リスクのみ) |
| C (アーキ移行) | $8〜23 | 1 ヶ月超 | 中 (機能制約あり) |
| **合計上限** | **月 $22〜67** | 1〜2 ヶ月 | (詳細は各 Phase 参照) |

> **理想ゼロ**は AWS から脱出 (Cloudflare Workers / Pages / R2 / D1 等) しない限り不可能。本プランは AWS 内残留前提のため**月数千円〜1 万円台**の最小化を目指す。
> 真にゼロにしたい場合は**別プラン (脱 AWS)** を起票する必要があり、移行コスト 1〜2 ヶ月 + 不安定期を許容するなら可能。本ドキュメントの方針確認時点では「AWS 内残留」を選択。

---

## 4. 品質向上との両立 (PO 確認: 「全方向」)

本プランは品質を犠牲にしない。むしろ以下の点で**コスト削減と品質改善が両立**する:

1. **フェーズ 1 (運用安定)**: 不要 Lambda / テーブル削除で監視対象が減る → CI / SLI 観測の信号比 (signal-to-noise ratio) 向上
2. **フェーズ 2 (AI 品質)**: processor / fetcher の頻度は維持。Anthropic API コスト最大要因も維持 → 品質追加余裕も維持
3. **フェーズ 3 (UX)**: CloudFront キャッシュ拡張 (B2) は読み込み速度 → 滞在時間 → DAU 改善に直結。コスト削減と UX 改善が同方向

---

## 5. 実装タスクキュー (TASKS.md に追加)

本プランの各候補を以下の ID で起票する (本 PR で TASKS.md に追記):

- `T2026-0502-COST-A1`: 未使用 DynamoDB テーブル削除 (Cowork セッション・scan 実証 → delete-table)
- `T2026-0502-COST-A2`: CloudWatch Logs retention 30 日統一 (Code セッション・スクリプト追加 + 適用)
- `T2026-0502-COST-A3`: flotopic-bluesky schedule 30min → 1 日 3 回 (Code セッション・deploy.sh 編集)
- `T2026-0502-COST-A5`: S3 Lifecycle Policy 追加 (Cowork セッション・1 回限り設定)
- `T2026-0502-COST-B1`: API Gateway → Lambda Function URL 移行 (Code セッション・要設計レビュー)
- `T2026-0502-COST-B2`: CloudFront キャッシュ TTL 拡張 (Code セッション)
- `T2026-0502-COST-B3`: flotopic-cf-analytics 廃止判断 (Cowork セッション・利用調査)
- `T2026-0502-COST-B4`: flotopic-contact / p003-contact 重複解消 (Code セッション)
- `T2026-0502-COST-B5`: DynamoDB On-Demand → Provisioned 切替 (Cowork セッション・メトリクス確認後)
- `T2026-0502-COST-C1`: p003-topics 読取 S3 化 (Code セッション・要設計)
- `T2026-0502-COST-C2`: p003-tracker → CloudFront Functions 移行 (Code セッション・要設計)
- `T2026-0502-COST-C3`: flotopic-analytics → Athena 化 (Code セッション・中長期)

各タスクは **`Verified-Effect:` 行で実測コスト変化 (CloudWatch Cost Explorer or `aws ce get-cost-and-usage`) を 30 日後に検証** すること。

---

## 6. 実装順序の推奨

1. **Phase A 全件 (1 週間)** — リスクゼロ・即効性。COST-A1 → A2 → A5 → A3 の順
2. **Phase B 中で COST-B2 (CloudFront キャッシュ) と COST-B3 (cf-analytics 廃止判断) を先行** — 影響範囲が小さい
3. **COST-B1 (API Gateway 廃止) は要設計レビュー** — Frontend の API_BASE 変更が必要・本番停止リスクを慎重に
4. **Phase C は Phase A/B 完了後に再評価** — 期待削減額が小さければ実装コストに見合わない可能性

---

## 7. リスクと撤退基準

| リスク | 対策 | 撤退基準 |
|---|---|---|
| 削除した DynamoDB テーブルが実は使われていた | 削除前に `aws dynamodb scan` で書き込み 0 件 + IAM policy で参照 ARN 検索 | 24 時間で書き込み発生 → 即 restore (point-in-time recovery が有効なら) |
| API Gateway 廃止後の Frontend API 呼び出し失敗 | Function URL 並走稼働期間を 1 週間設けて切替 | エラー率 0.5% 超で 5 分以内に Frontend 設定 revert |
| CloudFront キャッシュ拡張後に古い JSON が配信される | invalidation を deploy-p003.yml に組み込み | ユーザー報告 1 件で max-age を半分に戻す |

---

> **次のステップ**: 本ドキュメントを PR で merge → TASKS.md に T2026-0502-COST-A1〜C3 を追記 → Phase A から実装開始。
> 各 Phase 完了時に `aws ce get-cost-and-usage` で実測値を取得して本ドキュメントに追記する。

---

## 8. 深掘り調査結果 (2026-05-02 21:30 JST・Cowork セッション・Cost Explorer 実測)

### 8.1 実コスト内訳 (2026年4月・確定値)

`aws ce get-cost-and-usage --granularity MONTHLY` の実測:

| サービス | 2026年4月 USD | 全体比 | 削減余地 |
|---|---|---|---|
| **Amazon DynamoDB** | **$6.42** | **58%** | あり (本命) |
| **Amazon S3** | **$2.22** | **20%** | あり |
| Route 53 | $1.01 | 9% | 不可 (HostedZone $0.50/zone × 2 = 固定) |
| Tax | $0.98 | 9% | 不可 (連動) |
| AWS Cost Explorer | $0.18 | 2% | 削減候補 ($0.01/API call) |
| AWS Secrets Manager | $0.0000 | 0% | - |
| AWS Lambda | $0.00002 | **ほぼゼロ** | **無料枠内・削減効果ゼロ** |
| Amazon API Gateway | **$0** | 0% | **無料枠内・削減効果ゼロ** |
| Amazon CloudFront | **$0** | 0% | **無料枠内・削減効果ゼロ** |
| AmazonCloudWatch | **$0** | 0% | **無料枠内・削減効果ゼロ** |
| **合計** | **約 $11/月** | 100% | 固定費 ~$2 を除き ~$9 が変動 |

### 8.2 USAGE_TYPE 別 (DynamoDB / S3 の内訳)

| USAGE_TYPE | USD | 意味 |
|---|---|---|
| **APN1-ReadRequestUnits** (DynamoDB Read) | **$4.02** | **最大ターゲット** |
| **APN1-WriteRequestUnits** (DynamoDB Write) | **$2.39** | 第 2 ターゲット |
| **APN1-Requests-Tier1** (S3 PUT/POST/LIST/COPY) | **$2.17** | 第 3 ターゲット (processor の PutObject 大半) |
| HostedZone (Route 53) | $1.00 | 固定 |
| USE1-APIRequest (Cost Explorer) | $0.18 | 微小 |
| APN1-Requests-Tier2 (S3 GET/SELECT) | $0.047 | 微小 |
| APN1-TimedPITRStorage-ByteHrs (DynamoDB PITR backup) | $0.0098 | 微小 |
| APN1-TimedStorage-ByteHrs (DynamoDB / S3 storage) | $0 | 無料枠内 |

### 8.3 当初プランの再評価 — **多くの候補が実コストゼロ削減**

Phase A/B/C プランを実コストで再評価した結果、**期待削減量を大幅下方修正**:

| 元 ID | 当初の期待削減 | **実コスト削減** | 判定 |
|---|---|---|---|
| COST-A1 (未使用 DynamoDB 4 個削除) | $1〜3 | **~$0.05** (ストレージ無料枠内・PITR も微小) | ⚠️ **規律タスクとして残す**: 監視対象削減・IAM 整理 |
| COST-A2 (CloudWatch Logs retention) | $2〜5 | **$0** (CloudWatch コスト全体ゼロ) | ❌ **降格**: 規律のみ・コスト効果なし |
| COST-A3 (Bluesky schedule 削減) | $1〜2 | **$0** (Lambda コスト全体ゼロ) | ⚠️ **品質タスクに再分類**: TL 汚染抑制 (UX) |
| COST-A5 (S3 Lifecycle Policy) | $1〜3 | **~$0** (ストレージ無料枠内) | ❌ **降格**: 効果なし |
| COST-B1 (API GW → Function URL) | $5〜15 | **$0** (API GW コストゼロ) | ❌ **撤回**: 移行コスト>削減 |
| COST-B2 (CloudFront キャッシュ拡張) | $2〜8 | **$0** (CloudFront コストゼロ・既に効いてる) | ❌ **撤回**: UX 改善は別タスクで |
| COST-B3 (cf-analytics 廃止) | $1〜3 | **~$0** | ❌ **降格**: 規律のみ |
| COST-B4 (contact 重複解消) | $0.5 | **$0** | ❌ **降格**: 規律のみ |
| COST-B5 (DynamoDB Provisioned 切替) | $1〜5 | 要計測 (低トラフィック前提崩れる可能性) | ⚠️ **慎重**: PAY_PER_REQUEST のままが正解の可能性 |
| **COST-C1 (p003-topics 読取 S3 化)** | $5〜15 | **$1.5〜3** (DDB Read $4.02 の 30〜50% 削減見込み) | ✅ **昇格**: **最大の本命** |
| COST-C2 (tracker → CF Functions) | $2〜5 | **$0** (Lambda コストゼロ) | ❌ **撤回** |
| COST-C3 (analytics → Athena) | $1〜3 | **$0** (Lambda コストゼロ) | ❌ **撤回** |

### 8.4 真の削減候補 (実コストベース・新規追加)

| 新 ID | 内容 | 期待削減/月 | 実装コスト |
|---|---|---|---|
| **COST-D1** | **DynamoDB Read 削減** (`lambda/api/handler.py` の DDB Scan/Query 呼出パターン分析 → S3 JSON キャッシュ拡張・既存 `topics-card.json` 経路の活用) | **$1.5〜3** | 中 (要設計・コード変更) |
| **COST-D2** | **DynamoDB Write 削減** (`lambda/processor/handler.py` の PutItem 頻度確認 → バッチ書き込み・差分のみ書込) | **$0.5〜1.2** | 中 (要設計) |
| **COST-D3** | **S3 PutObject 削減** (`lambda/processor/handler.py` `lambda/fetcher/handler.py` の PutObject 頻度・冪等性チェック → 同一データの上書き回避) | **$0.5〜1** | 中 (要設計) |
| **COST-D4** | **PITR 必要性再評価** (`p003-topics` 以外で PITR 有効化されているテーブル特定 → 重要テーブル以外で無効化) | **$0.005〜0.02** | 低 (微小だが規律) |

### 8.5 改訂後の総削減見立て

| Phase | 改訂後 (実コスト) | 当初見立て | 差分 |
|---|---|---|---|
| A 即時 (規律タスクとして残す) | $0.05 | $5〜13 | -98% (ほぼ規律) |
| B 中期 (大半撤回) | $0 | $9〜31 | -100% |
| C アーキ移行 (C1 のみ残し) | $1.5〜3 | $8〜23 | -85% |
| **D 新規 (実コストターゲット)** | **$2.5〜5.2** | (新規) | (新規) |
| **改訂後合計** | **月 $4〜8** | 月 $22〜67 | -82% |

### 8.6 結論 — 削減余地の絶対値が小さい

- **月総コスト ~$11 のうち、固定費 (Route 53 HostedZone $1.00 + Tax $0.98) を除いた変動費は ~$9**
- このうち **DynamoDB Read $4.02 + Write $2.39 + S3 PUT $2.17 = $8.58** がほぼ全変動費
- **理論最大削減量 ≈ $8.58**。実際には書き込み・読み込みパターン最適化で 30〜60% カット = **月 $2.5〜5.2 削減見込み**
- **「理想ゼロ」は AWS 内残留前提では不可能**。Route 53 + Tax の固定費 ~$2/月は脱 AWS しない限り消えない
- **「品質を上げる方向で」との両立**: フェーズ 2 (AI 品質) には Anthropic Claude API コスト ($AWS 外・別請求) が大きいので、AWS 削減はフェーズ 2 に副作用しない

### 8.7 PO への提言

1. **A1 (未使用テーブル削除) は実施する**が「コスト削減」ではなく**規律タスク**として位置付ける (監視対象削減・IAM 整理)
2. **A2/A3/A5/B1/B2/B3/B4/C2/C3 は全部撤回または降格** — 実コストゼロのため工数対効果が悪い
3. **D1〜D4 を新規優先タスク化** — DynamoDB / S3 の操作回数削減が真の本命
4. **「真の削減目標」: 月 $11 → $7 (約 36% カット)** が現実的。**理想ゼロ**を目指すなら Cloudflare Workers / R2 への脱 AWS 移行が必要 (別プラン)
5. **Anthropic Claude API コスト**は AWS 請求と別 → AWS 削減と独立して別タスクで管理 (フェーズ 2 進行に直結)

---

## 9. DynamoDB Read 元コード分析 (T2026-0502-COST-D1-INVESTIGATE・2026-05-02 23:00 JST)

> 範囲: `projects/P003-news-timeline/lambda/` 配下の全 boto3 DynamoDB Read 呼出 (Scan / Query / GetItem / BatchGetItem) を網羅。コード変更はせず、削減候補設計案 1 件を提示する。
> 関連: §8.4 D1 候補定義・§2 Phase C COST-C1 (`lambda/api/handler.py` 読取パス除去) との重複回避。

### 9.1 関数別 × テーブル別 読取マトリクス

| Lambda | テーブル | 操作種別 | 月間呼出推定 | 備考 |
|---|---|---|---|---|
| **api/handler.py** | `p003-topics` | `scan` (`all_topics` META 全件) + `query` (`topic_detail`) | API 呼出依存 (CloudFront cache miss 時のみ Lambda 起動) | **最有力 D1 ターゲット** — 既に `api/topics-card.json` (S3) で同じ minimal payload を配信済 |
| **processor/handler.py** | `p003-topics` | `scan` (pending fallback L120/L134) | proc 月 ~60 回 × N items | rate-limit fallback 経路。S3 化困難 (内部状態管理) |
| **processor/proc_storage.py** | `p003-topics` | `scan` × 多数 + `query` × 多数 + `get_item` × 多数 + `batch_get_item` × 2 | proc 1日2回 (08/20 JST) × 全 visible topic | 内部処理ロジック中核。`get_pending_topics` / `get_topics_by_ids` / `_backfill_ai_fields_from_ddb` 等。S3 化困難 (DDB が SoT) |
| **fetcher/handler.py** | `p003-topics` | `get_item` (META lookup L216) | rate(30 min) × N topics = 月 ~1,440 × N | 鮮度判定で META 必読・整合性必須 |
| **fetcher/storage.py** | `p003-topics` | `scan` + `query` × 4 + `batch_get_item` | 30 min × 数百件 | `_load_visible_topic_ids` 経由・`api/topics_visible_ids.json` で代替可能性あり |
| **lifecycle/handler.py** | `p003-topics` | `query` × 4 + `scan` + `batch_get_item` × 3 | 週次 (月 4 回) | バッチ削除・低頻度。削減余地小 |
| **comments/handler.py** | `ai-company-comments` `flotopic-users` `flotopic-rate-limits` `flotopic-analytics` `p003-topics` | `query` `scan` `get_item` 多数 | UGC イベント時 (低〜中) | UGC 整合性必須・S3 化不適 |
| **contact/handler.py** | `flotopic-contacts` `p003-topics` `flotopic-rate-limits` | `query` + `scan` | 低 (問い合わせ時) | 低頻度・整合性必須 |
| **auth/handler.py** | `flotopic-users` | `get_item` | login 時 | UGC 整合性必須・S3 化不適 |
| **favorites/handler.py** | `flotopic-favorites` `p003-topics` | `query` × 2 + `get_item` × 2 | favorite アクション時 | UGC 整合性必須 |
| **analytics/handler.py** | `flotopic-analytics` `flotopic-users` | `scan` × 4 + `query` + `get_item` | 集計時 (1日数回) | 集計系・S3 化検討余地あるが優先度低 |
| **cf-analytics/handler.py** | `flotopic-favorites` | `scan` | daily | 低頻度 (月 ~30 回) |
| **tracker/handler.py** | `p003-topics` | (Table 取得のみ・読み無し) | tracking | UGC tracking |

### 9.2 既に S3 で配信されている同等データ

| S3 key | 中身 | 由来 | frontend 利用 |
|---|---|---|---|
| `api/topics.json` | 全件 META | `processor` 出力 | (旧経路) |
| `api/topics-full.json` | full payload | `processor` 出力 | 詳細画面 |
| **`api/topics-card.json`** | **モバイル用 minimal payload** | **`processor` 出力** | **`frontend/app.js` L233 が `apiUrl('topics-card')` で取得** |
| `api/health.json` | 充填率 SLI | `processor` 出力 | health page |
| `api/pending_ai.json` | pending tid 一覧 | `processor` 内部用 | (内部) |
| `api/topics_visible_ids.json` | visible tid 一覧 | `processor` 出力 | tracker/fetcher が参照 |

**重要観測**: `frontend/app.js` は既に `topics-card.json` (S3) を直接 fetch している。**`api/handler.py` の `/topics` エンドポイント (DDB Scan) は旧経路で誰も呼んでいない可能性が高い**。CloudWatch access log で 7 日分の hit を確認する必要あり。

### 9.3 削減施策の優先度

**🎯 最高 (D1-α) — `api/handler.py` `/topics` 経路の S3 直配信化**
- DDB Scan (META 全件・数百件) → 月 RCU 大量消費の主犯候補
- frontend が既に `topics-card.json` を見ているため、`/topics` API は遺物の可能性 → アクセスログ確認で実効を判断
- 期待削減: $1.5〜3/月 (DDB Read $4.02 のうち API path 寄与を ~50% カット仮定)

**🟡 中 (D1-β) — `fetcher/storage.py` の `_load_visible_topic_ids` 系**
- 30 min × 数百 topic で頻度高
- 既に `api/topics_visible_ids.json` (S3) が存在 → S3 直読で DDB scan を回避できる可能性
- 期待削減: $0.3〜0.8/月

**🟢 低 (D1-γ) — `lifecycle/handler.py`**
- weekly のみ・効果僅か → 後回し

**❌ 提案しない**
- `processor/proc_storage.py` 系: DDB が State of Record。書換は §C1/C2 のアーキ移行に統合する話で、§D1 のスコープ外
- UGC 系 (comments/auth/favorites): 整合性必須・S3 化不適

### 9.4 採用候補の具体設計案 — D1-α: `/topics` 経路の S3 直配信化

#### 現状
```
client → CloudFront → API GW → Lambda(api/handler.py) → DynamoDB Scan(p003-topics META)
```
- `all_topics()` が `ProjectionExpression` で META のみ全件 Scan
- 毎回 META 全件 → 数百 RCU 消費
- CloudFront cache miss 時に毎回発火

#### 提案 (3 ステップ・段階的)

**Step 1: アクセス実態調査 (コード変更なし・3 日)**
- CloudWatch Logs Insights で `/topics` への直接 hit (CloudFront cache miss + 異なる Source IP) を 7 日分集計
- 結果次第で Step 2 を 2 系統に分岐

**Step 2-A: 直撃が多い場合 — Lambda が S3 を読んで返す (要コード変更)**
```python
# lambda/api/handler.py 改修案
import boto3
s3 = boto3.client('s3', region_name=REGION)
S3_BUCKET = os.environ.get('S3_BUCKET', 'p003-news-946554699567')

def lambda_handler(event, context):
    path = event.get('rawPath', '/')
    if path in ('/', '/topics'):
        try:
            obj = s3.get_object(Bucket=S3_BUCKET, Key='api/topics-card.json')
            payload = json.loads(obj['Body'].read())
            return resp(200, {'topics': payload.get('topics', [])}, event)
        except Exception:
            # フォールバック: 旧 DDB 経路 (緊急時のみ)
            return resp(200, {'topics': all_topics()}, event)
    # ... topic_detail は据え置き
```

**Step 2-B: 直撃がほぼゼロ (frontend のみ・全 cache hit) の場合 — `/topics` ルート自体を 410 Gone に**
- API 経路自体を撤去 → Lambda invocation も DDB Scan も完全にゼロ

**Step 3: SLI 計測 + 撤退基準**
- 計測項目: `DynamoDB ConsumedReadCapacityUnits` (p003-topics) before/after・CloudFront cache hit ratio
- 撤退基準: S3 直配信に切替後、frontend で表示崩れまたは 5xx が 1% 超で即 revert
- 評価期限: 切替 PR merge 後 7 日 (`Eval-Due:`)

#### リスク

| リスク | 影響 | 対策 |
|---|---|---|
| processor 書込から S3 反映まで cache TTL (5 min) 遅延 | frontend topics 一覧が最大 5 分古い | 現状 `topics-card.json` も同じ TTL で運用済 → 体感差なし |
| `topics-card.json` schema が `/topics` API と微妙に違う | 直撃クライアントで JSON parse error | Step 1 のログ確認で外部直撃の有無を先に確認・schema 揃える Adapter を Lambda に挟む |
| S3 read failure (バケット障害) | API 全断 | フォールバック (Step 2-A の except 節) で旧 DDB 経路を残す |
| CloudFront cache invalidation が必要 | 切替時に古い payload 配信 | `processor` 出力時の既存 invalidation 機構を流用 |

#### 実装ステップ (PR を分ける)
1. **PR-1 (調査)**: CloudWatch Logs Insights クエリ + アクセス分析を別 doc に出す (コード変更なし)
2. **PR-2 (Step 2-A or 2-B 採否)**: 結果に応じて Lambda 改修 or `/topics` ルート削除。SLI ベースラインを取る
3. **PR-3 (Verified-Effect)**: 7 日後 SLI 再測定 → DDB Read 削減 / cache hit ratio 改善 を確認

#### 期待削減
- **保守的見積もり**: $1.0/月 (`/topics` 直撃が想定より少なく Cache hit が高い場合)
- **中央値見積もり**: $1.5〜2.0/月 (`/topics` Lambda invocation の DDB Scan を半減)
- **楽観見積もり**: $3.0/月 (`/topics` ルート完全撤去で API path 寄与をほぼゼロ化)

### 9.5 §C1 (Phase C) との関係整理

§2 Phase C の **COST-C1** が「`p003-topics` 読み取りパス全体を S3 直配信」と広い設計、本 §9.4 D1-α は **`/topics` API 単一エンドポイントに限定**した先行スコープ。

- C1 は `topic_detail` (`/topic/{id}`) も S3 化する大きな話 (個別 topic ごとに `topic-{id}.json` を書く設計が必要・別タスク)
- D1-α は `/topics` 一覧のみ・既存 `topics-card.json` を流用する小さな先行 PR
- **D1-α が成功した時点で C1 を「`topic_detail` を残課題」として再定義し直す**

### 9.6 D1 投資判断

- **やる価値**: $1.5〜3/月 = 月支出の 14〜27%。1 PR で段階的に投入できる (Step 2-A or 2-B)
- **やらない理由なし**: 既に S3 payload があるので追加生成は不要・Lambda コード変更も小さい
- **次タスク**: `T2026-0502-COST-D1-α-INVESTIGATE` を起票 (Step 1 のアクセス実態調査) → 結果次第で `T2026-0502-COST-D1-α-CODE` で Step 2 実装

