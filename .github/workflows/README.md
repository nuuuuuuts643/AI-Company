# GitHub Actions Workflows 一覧

このディレクトリに含まれるワークフロー（CI/CD/自動化）の目的・トリガー・依存関係を記載します。

## コア CI/CD

| ワークフロー | 目的 | トリガー | 依存関係 |
|---|---|---|---|
| `ci.yml` | Python/JavaScript linter・テスト・型チェック | push・PR | なし |
| `deploy-p003.yml` | P003 News Timeline の Lambda・frontend デプロイ | main push・manual | `ci.yml` 成功 |
| `deploy-lambdas.yml` | Lambda 関数の更新・デプロイ | manual | `ci.yml` 成功 |
| `deploy-staging.yml` | ステージング環境へのデプロイ | manual | `ci.yml` 成功 |
| `post-merge-deploy.yml` | PR マージ後の自動デプロイ | main merge | `ci.yml` 成功 |

## 観測・監視（SLI）

| ワークフロー | 目的 | トリガー | 依存関係 |
|---|---|---|---|
| `freshness-check.yml` | 記事鮮度・AI充填率・トピック品質 SLI 測定 | 30分間隔 cron | なし |
| `fetcher-health-check.yml` | fetcher Lambda の死活確認・エラーログ検査 | 10分間隔 cron | CloudWatch Logs 読み取り権限 |
| `health-check.yml` | API・frontend の生存確認・HTTP ステータス確認 | 5分間隔 cron | なし |
| `lambda-freshness-monitor.yml` | Lambda cold start・duration 監視 | 毎時 cron | CloudWatch Metrics |
| `timestamp-sli.yml` | タイムスタンプ SLI（記事 pubDate・トピック updatedAt） | 毎時 cron | DynamoDB・S3 アクセス |
| `sli-keypoint-fill-rate.yml` | keyPoint 充填率 SLI 測定 | 毎日 08:30 JST cron | S3・DynamoDB |
| `revenue-sli.yml` | 収益ページビュー・AdSense・アフィリエイト SLI | 毎日 09:00 JST cron | Google Analytics・Adsense API |

## セキュリティ・コンプライアンス

| ワークフロー | 目的 | トリガー | 依存関係 |
|---|---|---|---|
| `security-audit.yml` | IAM ポリシー・secrets・脆弱性スキャン | 週1・manual | AWS CLI・git |
| `secret-scan.yml` | コード内に埋め込まれた API キー・トークン検出 | push・PR | なし |
| `iam-policy-drift-check.yml` | IAM ポリシーと deploy.sh の整合性確認 | 週1 cron | AWS IAM API |
| `security-headers-check.yml` | HTTP セキュリティヘッダー確認 | 毎日 10:00 JST cron | なし |
| `meta-doc-guard.yml` | CLAUDE.md / docs の構造・内容チェック | push・cron | なし |

## 品質保証・テスト

| ワークフロー | 目的 | トリガー | 依存関係 |
|---|---|---|---|
| `lint-yaml-logic.yml` | ワークフロー YAML 構文・logic チェック | push | なし |
| `docs-sync-check.yml` | ドキュメント（docs/）と実装の不整合検出 | push・30日ごと cron | なし |
| `pr-scope-check.yml` | PR が適切なスコープ・形式か検証 | PR created・synchronize | なし |
| `pr-conflict-guard.yml` | PR のコンフリクト自動検出・警告 | PR created・edited | なし |
| `success-but-empty-scan.yml` | CI 成功してもテスト実行なし・カバレッジ 0% 検出 | push | なし |
| `ux-check.yml` | フロントエンド UX（表示崩れ・フォント・レスポンシブ） | push・PR | なし |

## 自動化・運用

| ワークフロー | 目的 | トリガー | 依存関係 |
|---|---|---|---|
| `post-deploy-verify.yml` | デプロイ後の機能確認・smoke test | deploy 成功後 | HTTP リクエスト |
| `auto-merge.yml` | 条件を満たした PR を自動マージ | PR ready・CI success | `ci.yml` 成功 |
| `auto-update-branches.yml` | 親ブランチの更新を自動反映（rebase） | main push | git |
| `automerge-stuck-watcher.yml` | auto-merge がスタックした PR を検出 | 毎時 cron | なし |
| `cleanup-merged-branches.yml` | マージ済みブランチの自動削除 | 日1回 cron | git |
| `concurrent-session-guard.yml` | 複数の Code セッション並走を検出・警告 | push（WORKING.md） | なし |
| `audit-pipe-silence.yml` | 監視ワークフロー（freshness-check 等）が沈黙したら Slack 通知 | 6時間無エラー継続時 cron | Slack Webhook |

## エージェント・リモート実行

| ワークフロー | 目的 | トリガー | 依存関係 |
|---|---|---|---|
| `developer-agent.yml` | Code セッション自動起動（バグ修正提案） | manual / dispatch | Anthropic API |
| `devops-agent.yml` | インフラ修正・AWS リソース最適化 | manual / dispatch | AWS CLI・Anthropic API |
| `editorial-agent.yml` | AI 記事品質評価・フィードバック生成 | manual / dispatch | Anthropic API |
| `marketing-agent.yml` | SNS 投稿・ブログ更新・分析レポート | manual / dispatch | Anthropic API・SNS API |
| `revenue-agent.yml` | 収益改善提案・AdSense 最適化 | manual / dispatch | Google Analytics・Anthropic API |
| `seo-agent.yml` | SEO 品質改善・キーワード戦略 | manual / dispatch | Anthropic API |
| `qualitative-eval.yml` | 手動品質評価・ユーザーフィードバック収集 | manual | Notion API |
| `x-agent.yml` | X (Twitter) 投稿・エンゲージメント分析 | manual / dispatch | X API・Anthropic API |
| `bluesky-agent.yml` | Bluesky への記事配信・フィード投稿 | manual / dispatch | Bluesky API・Anthropic API |

## スケジュール・リマインダー

| ワークフロー | 目的 | トリガー | 依存関係 |
|---|---|---|---|
| `deploy-trigger-watchdog.yml` | デプロイトリガーの停止を監視・自動再起動 | 毎15分 cron | GitHub API |
| `deploy-trigger-watchdog-frontend.yml` | フロントエンド デプロイトリガー監視 | 毎15分 cron | GitHub API |
| `governance.yml` | 月次ガバナンスチェック・ルール遵守状況 | 毎月1日 cron | Notion・git |
| `schedule-consistency-check.yml` | scheduled-tasks と cron スケジュール整合性確認 | 週1 cron | なし |
| `weekly-digest.yml` | 週次ダイジェスト・進捗レポート生成 | 毎週金曜 cron | CloudWatch・git |
| `notion-sync.yml` | Notion DB との同期（issues・tasks） | manual | Notion API |
| `notion-revenue-daily.yml` | 日次収益レポートを Notion に記録 | 毎日 09:30 JST cron | Google Analytics・Notion API |
| `env-scripts-dryrun.yml` | 環境スクリプト（bootstrap・deploy 等）を dry-run | 毎日深夜 cron | なし |
| `quality-heal.yml` | CI 失敗原因の自動診断・修正提案 | CI failure | Anthropic API |

## 開発者向け・デバッグ

| ワークフロー | 目的 | トリガー | 依存関係 |
|---|---|---|---|
| `zz_test_missing_ref.yml` | テスト用・ワークフロー参照チェック | manual | なし |
| `release-tag.yml` | リリースタグ生成・バージョン管理 | manual | git tag |

---

**使い方**:

### デプロイ実行
```bash
# P003 News Timeline 全体
gh workflow run deploy-p003.yml

# 特定 Lambda 関数のみ
gh workflow run deploy-lambdas.yml -f function_name=p003-processor
```

### SLI 即時確認
```bash
gh workflow run freshness-check.yml --ref main
```

### PR チェック（CI が遅い場合の手動トリガー）
```bash
gh workflow run ci.yml --ref <branch-name>
```

---

**注意**:
- 直接 `workflow_dispatch` で invoke しない。`gh workflow run` を使用すること（`scripts/gh_workflow_dispatch.sh` wrapper で二重実行防止）
- `ci.yml` 以外のワークフロー は `ci.yml` 成功を前提としているため、先に `ci.yml` を実行すること
- セキュリティワークフロー（`security-audit.yml`）は `main` ブランチでのみ実行される
