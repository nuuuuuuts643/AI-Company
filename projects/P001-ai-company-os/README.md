# P001 AI 自走プロダクト運営 OS

> AI が自走でプロダクトを作って運営して収益を出す。POは出資者・方針決定者。
> 「会社」というメタファーで、複数のエージェントが「部署」として役割分担し協調する。

---

## ビジョン

POの一言指示と方針 → AI 群が要件定義・実装・デプロイ・監視・改善・収益化までを完遂。
POの作業時間は「方針決定」「金が必要な意思決定」「最終ジャッジ」のみに収束させる。

**現状（2026-04-28 時点）の到達点**: P003-news-timeline (https://flotopic.com) は実装〜運営〜SLI 監視〜AI 要約品質改善まで AI 群が自走している。CI/CD・freshness check・governance pipeline・health check が物理ゲートとして機能。

**P001 は「他のプロダクトでも再現可能な OS」として汎用化する**。P003 で得た運用ノウハウを部署設計・スクリプト・ワークフロー・ルールに標準化する。

---

## 部署構成（現行のエージェント役割）

| 部署 | 主担当 | 起動経路 | 役割 |
|---|---|---|---|
| **CEO（出資者）** | PO | 直接 | 方針決定・金が動く意思決定（広告予算/契約/サブスク等）・最終ジャッジ |
| **Code（Claude Code/CLI）** | Opus 1M | ローカル CLI | コード実装・テスト・デプロイ確認・PR レビュー |
| **Cowork（Claude スマホ・デスクトップ）** | Sonnet/Opus | クラウド | POとの会話・分析・計画立案・ドキュメント更新・git push |
| **Developer Agent** | Claude API | `developer-agent.yml` (push) | `tasks/queue.md` のタスクを自動実装 |
| **Editorial Agent** | Claude API | 手動 dispatch | 記事下書き・SEO 最適化（schedule 停止中） |
| **Marketing Agent** | Claude API | 手動 dispatch | 認知拡大施策（schedule 停止中・コスト懸念） |
| **Revenue Agent** | Claude API | 手動 dispatch | 収益分析・Notion 同期（schedule 停止中） |
| **SEO Agent** | Claude API | 手動 dispatch | 内部 SEO 改善提案（schedule 停止中） |
| **DevOps Agent** | Claude API | 手動 dispatch | インフラ最適化（停止中） |
| **Bluesky Agent** | Claude API | `bluesky-agent.yml` (cron) | SNS 投稿（稼働中） |
| **Security Agent / Legal Agent / Audit Agent** | Claude API | `governance.yml` (push/PR) | コミット時のガバナンス検査（L1→L2→Legal→Audit） |
| **Self-Improvement Loop** | スクリプト + CI | `governance.yml` `meta-doc-guard.yml` `health-check.yml` `freshness-check.yml` `security-audit.yml` `weekly-digest.yml` | 物理ゲートと SLI による自己観測・自己修正 |
| **Notion Sync** | スクリプト | `notion-sync.yml` `notion-revenue-daily.yml` (cron) | タスク・収益データの外部 mirror |

> 「停止中」マークの部署は schedule をコメントアウトしているが、script は残している。コスト都合で止めているだけで、POの判断で再開可能。

---

## POの役割（出資者・方針決定者）

- プロダクトのビジョン・優先順位・撤退判断
- API クレジット・サブスク・広告予算など「金が動く」意思決定
- 大型インフラ変更（新規 AWS リソース作成等）の承認
- AI が自力解決できないブロッカーの解消
- 最終ジャッジ（プロダクト方向性・撤退・統合）

POがやらないこと: 細かい実装・デバッグ・テスト・デプロイ確認・ドキュメント更新。これらは AI が完了報告まで自走する。

---

## エージェントの協調ルール

### Code ↔ Cowork 連携
- 同一リポジトリに git push する。WORKING.md で衝突回避。
- Code = `lambda/` `frontend/` `scripts/` `.github/` 担当。
- Cowork = ドキュメント・分析・git 操作も可。
- 詳細は `CLAUDE.md` "Cowork ↔ Code 連携ルール" を参照。

### 完了の物理ゲート
1. push しただけは未完了。動作確認（フロント=本番 URL 目視 / Lambda=CloudWatch エラーなし）まで。
2. `done.sh <task_id> <verify_target>` で自動検証。
3. 効果検証も別ゲート: `bash scripts/verify_effect.sh <fix_type>` で数値改善まで確認。
4. commit に `Verified:` 行と `Verified-Effect:` 行が必要。pre-commit hook で物理ブロック。

### なぜなぜ分析と仕組み的対策
- 問題発生時 Why1〜Why5 + 仕組み的対策 3 つ以上を `docs/lessons-learned.md` に記録。
- 仕組み的対策には「外部観測」「物理ゲート」を最低 1 つ含める。

---

## 部署を増やす方法（汎用化のための設計）

新しい部署（エージェント）を追加するときは以下の 3 点セットを揃える。

1. **`scripts/<role>_agent.py`** — 役割の本体（Claude API 呼び出し + 出力先処理）
2. **`.github/workflows/<role>-agent.yml`** — 起動条件（cron / push / dispatch）
3. **`projects/<PNNN>-<product>/briefing.md`** — どのプロダクトに対して何をする部署か

既存例: `developer_agent.py` + `developer-agent.yml` + `tasks/queue.md` 入力。

---

## 今後の方向性

### 短期（〜2026-Q2）
- P003-news-timeline の収益化を AdSense / 寄付 / sponsorship のいずれかで実証。
- AI 要約品質の SLI 自動化（freshness check + ai_fields coverage）を完成させ、品質劣化を 4h 以内に検出。
- Marketing/Revenue Agent の schedule 再開（API コスト試算後）。

### 中期（〜2026-Q4）
- P001 の運営ノウハウを「テンプレート化」し、新プロダクト立ち上げ時のスケルトン生成スクリプトを用意（`scripts/spawn_product.sh PNNN <name>`）。
- 第 2 プロダクト（候補: P002-flutter-game か新規アイデア）を P001 OS 上で立ち上げ、汎用性を検証。
- POの介入頻度を「週 1 回 30 分の方針確認」まで圧縮。

### 長期
- AI 群の自己改善ループの強化: 失敗パターン検出 → ルール追記 → 物理ゲート化を AI 自身が回す。
- 出資（API クレジット）に対する ROI を数値化し、利益が出た分を再投資する自走サイクル。
- 複数プロダクトの並列運営（部署はプロダクトを跨いで再利用）。

---

## 関連ドキュメント

- `CLAUDE.md` — セッション起動チェック・絶対ルール
- `docs/rules/global-baseline.md` — 全プロダクト共通前提
- `docs/system-status.md` — プロジェクト状態スナップショット
- `docs/lessons-learned.md` — なぜなぜ事例集
- `docs/flotopic-vision-roadmap.md` — P003 ビジョン

## ステータス

- [x] 部署構成の言語化（本 README）
- [x] Code / Cowork 連携ルールの確立（CLAUDE.md）
- [x] 物理ゲート（pre-commit / verified line / verify_effect）導入
- [x] P003 で自走運営の実証
- [ ] 部署スポーンのテンプレート化（`scripts/spawn_product.sh`）
- [ ] 第 2 プロダクトでの汎用性検証
- [ ] 介入頻度「週 1 回 30 分」の達成
