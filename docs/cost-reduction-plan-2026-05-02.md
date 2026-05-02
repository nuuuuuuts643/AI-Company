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
