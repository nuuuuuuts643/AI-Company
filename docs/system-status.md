# AI-Company システム状態（毎セッション必読）

> このファイルはセッションをまたいで状態を引き継ぐための機械的な記録。
> Cowork/Code どちらでも、セッション開始時にここを読んでから作業を始める。
> CLAUDE.md から外出し（CLAUDE.md は規則本体に集中する）。

---

## Dispatch 引き継ぎメモ [2026-04-29 09:30 JST]

### 本セッションで完了したこと

| PR | 内容 | 状態 |
|---|---|---|
| #13 | fetcher_trigger keyPoint backfill 経路 | merged |
| #14 | T2026-0429-B セマンティック分岐プロンプト改善 | merged |
| #15 | 横断スキャン 根本原因全適用（パターン1〜6） | merged |
| #16 | T2026-0429-D 繰り返し失敗自動検出 | merged |
| #18 | fix: deploy-lambdas put-targets 構文修正 | merged |
| #19 | T225: tokushoho.html 削除 + CI 不在チェック | merged |
| #20 | T2026-0429-KP4: handler.py 48h skip に keyPoint 不十分チェック追加 | merged |

### keyPoint充填率の現在地と見通し

- 現在値: 2.2%（keyPoint≥100字 / 109件中2件）
- **根本原因2件を修正済み**:
  1. KP3: proc_ai.py minLength=100 retry 実装（merged）
  2. KP4: handler.py 48h skip バイパス（merged 21ed1a2）
- **見通し**: 次のprocessor実行サイクル（毎時）から短いkeyPointの再生成が始まる。6〜24時間後に充填率が有意に上昇するはず。コスト追加不要。

### スケジューラーが次回やること

1. **6時間後に充填率を再計測**（HTTPで topics-full.json 取得、keyPoint≥100字の件数確認）
2. 充填率が10%以上に増加していれば → 正常に機能中、継続観測
3. 充填率が変わっていなければ → `T2026-0429-KP5` として追加調査（proc_ai.pyのretryが実際に発火しているかCloudWatchログ確認）
4. **次のTASKS.mdタスク**: T2026-0429-C（分岐判定効果検証）、T224a（admin.html allowedEmail修正）

### Lambda関数名（要注意）
- 正しい関数名: `p003-processor`（`flotopic-processor`は存在しない）
- backfill用イベント: `backfillDetailJson` / `backfillArchivedTtl` / `forceRegenerateAll`（`backfill_keypoint`は未実装）

---

## 会社構造

- **出資者・取締役**: PO（承認のみ、日常運営は CEO に委任）
- **CEO**: Claude（自律的に会社を動かす）
- **方針**: 指示を待たず毎日前進する。空報告禁止。実行した証拠がないものは完了扱いしない。

---

## 現在のプロジェクト状態（最終更新: 2026-04-28）

| プロジェクト | 状態 | 備考 |
|---|---|---|
| P001 AI 自走プロダクト運営 OS | **稼働中** ✅ | `projects/P001-ai-company-os/README.md` で部署構成を言語化。P003 で自走運営の実証中。Editorial/Marketing/Revenue/SEO/DevOps Agent は schedule 停止中（API費用削減）、CEO 判断で再開可能。 |
| P002 Flutter ゲーム | **開発中** 🔧 | Flutter+Flame で実装済み（50+ ファイル）。動作確認未実施。コンセプト: オートバトル × HD-2D ドット絵 × ローグライト抽出。 |
| P003 Flotopic | **本番稼働中** ✅ | flotopic.com。AI 要約 4 セクション形式。sitemap 自動更新。CI 全テスト通過。AdSense 審査待ち。 |
| P004 Slack ボット | **保留** ⏸ | Lambda デプロイ済みだが Slash Command 未設定のため誰も使えない。優先度低。 |
| P005 メモリ DB | **保留** ⏸ | DynamoDB 稼働中だがエージェント停止中で実質未使用。インフラは残存。 |

---

## P003 技術状態スナップショット

> このテーブルはセッションをまたいで整合性を保つための機械的な記録。
> 作業完了のたびに更新する。
>
> **※`[AUTO]` 接頭辞付きの行は将来 `freshness-check.yml` (1h cron) からの実測値で自動更新する対象 (T2026-0428-AC)**。
> 手書きで嘘を書ける構造を排除するため、観測値はワークフロー出力で sed 置換する設計に移行する。
> 接頭辞なしの行は人間が方針スナップショットとして手書き更新する (CI 状態・スケジュール等)。

| コンポーネント | 状態 | 最終更新 | 備考 |
|---|---|---|---|
| CI | ✅ 全テスト通過 | 2026-04-30 | `npm test` 42 件全パス必須。T256 (AI フィールド層抜け物理検出) main で landing 確認 (run 25166642638 / 13 tests OK / Verified-Effect: ci_pass:scripts/check_ai_fields_coverage.py:main:23:01 JST) |
| processor AI 要約 | ✅ 稼働中 | 2026-05-01 | 2x/day JST 05:30/17:30 (cron(30 20,8 UTC), T2026-0429-P)。MAX_API_CALLS=200 |
| [AUTO] AI 要約カバレッジ | ✅ FRESH | 2026-04-28 07:13 | 実測: 115 件中 aiGenerated=True 93 件 (**80.9%**)。T218 wallclock guard 反映後 24.6% → 80.9%。観測コマンドは `docs/sli-slo.md` SLI 3 |
| [AUTO] keyPoint 充填率 | 🔴 半壊 | 2026-04-28 07:13 | **全体 10/115 = 8.7%**。aiGenerated=True なのに必須フィールド空 = success-but-empty。T255 修正済 (skip 条件) だが次 cycle (07/13/19 JST) 反映待ち。SLI 8 (`freshness-check.yml` ai_fields step)。フィールドカタログ: `docs/ai-fields-catalog.md` |
| [AUTO] perspectives 充填率 | 🔴 半壊 | 2026-04-28 07:13 | 23/115 = 20.0% (全体)。SLI 9 |
| [AUTO] storyPhase 偏り | ⚠️ 警告寸前 | 2026-04-28 07:13 | 「発端」 54/115 = 47.0% (閾値 50%)。クラスタ過分割 (T212) と相関。SLI 4 |
| [AUTO] topics.json 鮮度 | ✅ FRESH | 2026-04-28 07:13 | 実測 07:13 JST: updatedAt 22:05 UTC = 07:05 JST、diff 約 8 分。閾値 90 分 (`docs/sli-slo.md` SLI 1)。外部観測 `freshness-check.yml` 1h cron (T263) |
| [AUTO] topics.json サイズ | ✅ 閾値内 | 2026-04-28 07:13 | 実測 213 KB (Content-Length=213045) / アラート閾値 250 KB (T2026-0428-F)。前回 312KB 記載は誤記訂正。Step1 (topics-card.json 二系統化) 未着手 |
| DynamoDB SNAP | 📉 改善中 | 2026-04-26 | lifecycle 週次で削除中。TTL(7日) ENABLED |
| Bluesky 自動投稿 | ✅ 継続稼働 | 2026-04-27 | 1日 3 回 (JST 08:00/12:00/18:00) |
| 静的 SEO HTML 生成 | 🔴 本番断絶 | 2026-04-28 08:15 | **2026-04-28 08:15 schedule-task で発見**: news-sitemap.xml 登録 50 件サンプリング 3/3 全て **HTTP 404 (x-cache: Error from cloudfront)**。S3 に `topics/{tid}.html` が無い。手書き「500/500件」は誤記録 (T2026-0428-AC「手書き嘘記述防止」へ)。SLI 11 (`freshness-check.yml` sitemap_reach step) で再発防止。**復旧タスク**: T2026-0428-AB |
| fetcher UGC 混入防御 | ✅ 二重防御稼働 | 2026-04-27 | filters.py + handler.py uniqueSourceCount>=2 |
| お問い合わせフォーム | ✅ SES 稼働中 (sandbox) | 2026-04-26 | 実送信確認済。flotopic.com DKIM 成功 |
| 安定コンポーネント群 | ✅ 全稼働 | 2026-04-26 | sw.js・CloudFront・sitemap・Slack・filter-weights・lifecycle・アフィリエイト・ストーリー・ジャンル分類等 |

> 完了済みコンポーネント詳細は HISTORY.md を参照

---

## 専門 AI 稼働状況

**運営エージェント**: 全 8 本停止中（API 費用削減。ユーザー増加後に再開）

**ガバナンスエージェント**:
- SecurityAI (✅ push+週次→Slack)
- LegalAI (⏸ 停止中)
- AuditAI (✅ push+週次→PO直報)

共通基盤: `scripts/_governance_check.py` / `.github/workflows/governance.yml` / DynamoDB: `ai-company-agent-status`, `ai-company-audit`

---

## 残タスク（PO手動作業が必要なもの）

- **P002 動作確認**（未実施）: `cd ~/ai-company/projects/P002-flutter-game && flutter pub get && flutter run`
- **SES 本番アクセス申請**: sandbox 解除後、未検証アドレスへも送信可能になる
- **待ち**: AdSense 審査中（忍者AdMaxで代替中）

---

## 開発ルール（一人開発・事故防止）

### 基本フロー
1. コードを変更する
2. `git add / commit / push` → GH Actions が自動で本番反映（2〜4 分）
3. 動作確認したい場合は `bash projects/P003-news-timeline/deploy-staging.sh` でステージングに先行反映

### ステージング環境
- URL: http://p003-news-staging-946554699567.s3-website-ap-northeast-1.amazonaws.com
- 手動デプロイ: `bash projects/P003-news-timeline/deploy-staging.sh`
- 本番との違い: フロントエンドのみ別バケット。Lambda/DynamoDB は本番共有

### CI（自動構文チェック）
- main への push 時に自動実行（`.github/workflows/ci.yml`）
- JS 構文チェック（node --check）
- Python 構文チェック（py_compile）
- API キーのハードコード検出
- CLAUDE.md 250 行ガード（2026-04-28 追加）
- task-id 重複検出（2026-04-28 追加）

### deploy.sh は直接実行しない（2026-04-25 変更）
**デプロイは GitHub Actions が自動で行う。Claude から deploy.sh を叩かない。**

| 変更ファイル | 自動デプロイ |
|---|---|
| `projects/P003-news-timeline/frontend/**` | `.github/workflows/deploy-p003.yml` |
| `projects/P003-news-timeline/lambda/**` | `.github/workflows/deploy-lambdas.yml` |

例外: インフラ新規作成（DynamoDB テーブル作成・Lambda 新規追加等）が必要な場合のみ `deploy.sh` を使ってよい。その場合はPOに確認してから実行する。

---

## 未解決の問題 / 素材不足

- **P003 AdSense 審査待ち** — 申請済み。通過まで数週間かかる場合あり。それまでは忍者 AdMax で代替
- **P003 グラフデータ蓄積中** — 長期グラフ（1ヶ月〜1年）はデータ蓄積後に意味を持つ
- **P002 Flutter スプライト素材未作成** — AI 生成で後日追加
- **P002 BGM 本番版未作成** — Suno AI で後日生成・差し替え
- **P002 動作確認未実施** — `flutter pub get && flutter run` をローカルで実行する

---

## 次フェーズのタスク（優先度順）

1. **SEO 流入**: 静的 HTML 実装済み。次→Qiita/note 記事でリンク獲得・Bluesky 流入
2. **コンテンツ品質**: AI 要約 2x/day (JST 05:30/17:30) 自動改善中。lifecycle ARCHIVE_DAYS=7 週次整理
3. **収益化**: AdSense 審査中→通過後に切り替え。Amazon/楽天アフィリ申請（PO手動）
4. **UX**: モバイル改善・表示名分離はユーザー増加後

---

## 将来アイデア候補

詳細は **docs/operations-design.md**（運用設計）・**docs/infra-migration-strategy.md**（インフラ移行戦略）参照

- P003 拡張: トピック起点 SNS 機能（コメント lambda 実装済み。ユーザー増加後に有効化）
- P006 候補: Flotopic × 株式投資シグナル（精度向上・ユーザー基盤確立後）

---

## P002 Flutter

→ `projects/P002-flutter-game/briefing.md` 参照（コンセプト/システム/収益化/フォルダ構造）
