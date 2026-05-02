# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

<!-- 自動巡回 2026-05-01 06:08 JST (flotopic-p003-continuity): WORKING.md に [Code] 行 0 件・main clean。優先キュー T2026-0429-K/M/N は全て landing 済 (commit fbdb5a9 / b063bd06 / fe058dec) のため新規実装なし。SLI 実測 (公開 topics-card.json 213件・05:30 JST processor 実行後): keyPoint>=100字 35.7% (76/213) [前回 04:10 JST 29.7%→+6.0pt]・ac>=3 サブ 39.5% (34/86) [前回 36.4%→+3.1pt]・kp 平均長 112.8字 [前回 103.8字→+9.0字]・storyPhase 発端率 (ac>=3) 0.0% (0/86) ✅・aiGenerated 75.1% (160/213)。check_sli_field_coverage.sh OK (乖離なし)。verify_branching_quality.py: branching_rate=14.1% (30/213) sample=4 で error_branch=1 / error_merge=3 (sample 不足の暫定値・閾値 fb<=20/fm<=15 FAIL だが母集団小)。フェーズ2 完了条件 (keyPoint 70%) 未達のため 17:30 JST processor 後再観測（次回 routine）。 -->

---

## 🔥 今週やること（メインキュー）

<!-- フェーズ別紐付け (詳細: docs/project-phases.md) -->
<!-- フェーズ1 (足回り安定) — Dispatch運用安定 / リリース管理 / 形骸化検出 -->
<!-- フェーズ2 (AI品質) — T212/T2026-0428-E/T2026-0428-BRANCH -->
<!-- フェーズ3 (UX・成長) — T191/T193 -->

> **選定基準**: ユーザー体験に直結・安定性・AI品質・収益に近い順。
> **整理日**: 2026-04-28 PM (T2026-0428-AX で実装済タスク除去 + フェーズ1 新規完了条件タスク追加)

### 🆘 緊急対処（Action-Required・即時着手・最優先）

<!-- 2026-05-02 01:45 JST 起票・Cowork セッション T2026-0502-F が GitHub Actions failure を発見した記録 -->

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T2026-0502-D | 🟠 高 | **auto-merge stuck watcher (フェーズ1 Dispatch運用安定化)** — 2026-05-02 セッションで PR #125 / #130 / #132 の 3 件が `auto_merge=enabled` かつ `mergeable_state=blocked` で詰まり、Cowork が手動 API merge で対処した。GitHub の internal recompute ラグで auto-merge bot が動かないケースの恒久対処。`.github/workflows/automerge-stuck-watcher.yml` を新規作成し 10 分毎に schedule 実行。条件: open PR で `auto_merge.enabled_by != null` AND `mergeable_state=blocked` AND failed check 0 AND 最終更新から 5 分以上経過。対処: API `PUT /pulls/{N}/merge` (squash) を発動し、結果を Slack notify。完了条件: 1 度発火実績あり (Slack に notify が届く or run log に「stuck PR detected → merged」が残る)。Verified-Effect: 直近 1 週間の merged PR で「auto-merge enabled だが手動介入された PR」が 0 件 (gh API で取得・初回計測値を base に追跡)。**Phase-Impact: 1 Dispatch運用安定化** / **Eval-Due: 2026-05-09 (1週間後)** | `.github/workflows/automerge-stuck-watcher.yml` (新規), `scripts/automerge_stuck_watcher.py` (新規・任意・Python ロジック分離), `docs/system-status.md` (運用追加記載) | 2026-05-02 |
| T2026-0502-C | 🟡 中 | **Bluesky 投稿系の恒久リファクタ（debut 廃止 + EventBridge 4本cron化）** — `DEBUT_MAX_PER_RUN=0` で応急対処済み(2026-05-02)。恒久対処として: ①`rate(30 minutes)` EventBridge ルール削除 → JST 08:00/12:00/18:00/22:00 の4本cronに置換 (`deploy-lambdas.yml`) ②`bluesky_agent.py` から debut 関連コード一式削除 (list_debut_pending / delete_debut_marker / post_debut / DEBUT_* 定数 / DAILY_COOLDOWN_HOURS チェック) ③`lambda/processor/handler.py:407` の `bluesky/pending/` 書き込み削除 ④S3 `bluesky/pending/` に溜まった既存マーカーをクリーンアップ。完了条件: EventBridge ルール4本のみ存在、bluesky_agent.py からdebut コード消滅、processor が pending マーカーを書かなくなること。 | `scripts/bluesky_agent.py`, `.github/workflows/deploy-lambdas.yml`, `lambda/processor/handler.py` | 2026-05-02 |
| T2026-0502-O | 🟡 高 (PO承認待ち) | **AWS IAM Deny ポリシー追加 (思想ルールの物理化)** — Cowork IAM ユーザー (`arn:aws:iam::946554699567:user/Claude`) に以下 Deny を追加: `lambda:UpdateFunctionCode` `lambda:DeleteFunction` `dynamodb:DeleteTable` `dynamodb:DeleteBackup` `s3:DeleteBucket` `ec2:TerminateInstances` `rds:DeleteDBInstance` `iam:DeletePolicy` `iam:CreateAccessKey`。CLAUDE.md「思想ルール (Cowork は不可逆操作禁止)」を IAM 物理ルールに変換。完了条件: `aws lambda update-function-code` を Cowork から試して AccessDenied 確認。Verified-Effect: AccessDenied で reject されるログ。**PO 承認 + AWS Console 操作必要**（私が直接実行は危険）。policy 文書: `docs/rules/cowork-aws-policy.md` Section 4 | AWS IAM Console (Cowork ユーザー policy) | 2026-05-02 |
| T2026-0502-E | 🟡 中 | **NHK 本文取得タイムアウト恒久対処 (フェーズ2 perspectives 品質)** — 2026-05-02 09:40 JST 調査 (Cowork): `lambda/processor/article_fetcher.py` の 5秒 timeout で `www3.nhk.or.jp` が常時タイムアウト (直近48hで `[ArticleFetcher] www3.nhk.or.jp fetch失敗: TimeoutError: timed out` 多発・1〜数件/30min)。Cat-A 公共放送 NHK が常時 RSS スニペット (~200字) フォールバックで AI に渡されており「各社の見解」で NHK 論調が比較できない状態。対策: ①NHK 専用に timeout 8〜10s 拡大 (host 別マップ)、②1回リトライ追加、③User-Agent を `FlotopicBot/1.0` から汎用 UA に戻す試験 (Bot 識別で 429 を timeout として返している可能性)。完了条件: 直近1h の `[ArticleFetcher] www3.nhk.or.jp ... timed out` ログが 50% 以上減少。Verified-Effect: NHK 本文取得成功率 (CloudWatch logs カウント) を base→1週間後で計測。**Phase-Impact: 2 E2-2 perspectives 充填率改善** / **Eval-Due: 2026-05-09** | `lambda/processor/article_fetcher.py` | 2026-05-02 |
| T2026-0502-F | 🟢 低 (プロダクト判断要) | **Google Trends API 機能の修復 or 削除判断** — 2026-05-02 09:40 JST 調査 (Cowork): `lambda/fetcher/trends_utils.py` の Google Trends 非公式 API 直叩きが過去48h **100%失敗** (`HTTPError 400: Bad Request` または `429: Too Many Requests`)。3回ガードで残りスキップ動作はしているが、`trendsData` は1件も更新されていない可能性。30分毎の fetcher 起動でログに3〜4行のエラースタック汚染が継続中。判断ポイント: ①Trends 関連の関心度推移ミニチャートを今後も維持するか (フェーズ4 SNS化 epic に効くなら維持) ②維持なら pytrends ライブラリ + Lambda Layer 対応 (zip *.py 制約を破る要検討)、削除なら `_trend_candidates` ループ + handler.py:1075-1108 と `trends_utils.py` 削除 + `trendsUpdatedAt`/`trendsData` フィールド deprecate。完了条件: PO 判断後にどちらかが実装され、`[trends] HTTPError` ログが 0 件になること | `lambda/fetcher/handler.py`, `lambda/fetcher/trends_utils.py` | 2026-05-02 |
| T2026-0502-Q | 🔴 最優先 | **Lambda デプロイ workflow が連続失敗 → 直近修正 PR が本番未反映** — 2026-05-02 09:50 JST 網羅調査 (Cowork) で発覚。最後成功 deploy `#423` 09:04 JST (sha=68c7c85e)、以降 `#369`/`#370` (09:20/09:25 JST) が `fetcher Lambda をデプロイ` step で連続失敗 → 後続全関数 skip。**未本番反映**: PR #118 (T2026-0501-M 重複検出マージ・実機で「[ITmedia M」x4・「【ドジャース】大谷翔」x3 で再現確認)、PR #125 (T2026-0502-B lifecycle SK fix)。**根本原因推定**: `p003-fetcher` の env から `ANTHROPIC_API_KEY` が欠落 (AWS API で `aws lambda get-function-configuration` 確認済)。`scripts/ci_lambda_merge_env.py` が空 secret を `ANTHROPIC_API_KEY=` として出力 → AWS `update-function-configuration` Validation Error → step failure。完了条件: 次回 deploy run が green、p003-fetcher env に ANTHROPIC_API_KEY 復活、PR #118/#125 のコードがランタイムで動いていること (logs で `[ai_merge_judge]` 出現確認)。**Phase-Impact: 1 Dispatch運用安定化** / **Eval-Due: 2026-05-03** | `.github/workflows/deploy-lambdas.yml`, `scripts/ci_lambda_merge_env.py`, GitHub Secrets `ANTHROPIC_API_KEY` 確認 | 2026-05-02 |
| T2026-0502-R | 🔴 高 | **T2026-0501-H Haiku borderline 判定が本番で無音停止 (ANTHROPIC_API_KEY 欠落の二次影響)** — 2026-05-02 09:50 JST 調査 (Cowork): `p003-fetcher` env から ANTHROPIC_API_KEY が消えており、`AIMergeJudge(api_key='')` で `ai_merge_judge.py:115` の guard により Haiku 判定が全 pair skip される設計。CloudWatch logs に `[ai_merge_judge]` も `[borderline]` の語も全く出ていない (直近6h)。重複トピック検出 (PR #84) の機能が本番で死んでいる → T2026-0501-M 重複バグ復活の直接原因。**T2026-0502-Q が完了すれば自動復旧する想定**。**完了条件**: T2026-0502-Q 完了後 1h 観察し logs に `[ai_merge_judge]` が現れ、borderline 判定で skip でなく判定が走ること。Verified-Effect: `[ITmedia M` 始まり重複が <2 件まで減ること (1週間後実測)。**Phase-Impact: 2 E2-3 クラスタリング品質** / **Eval-Due: 2026-05-09** / **依存**: T2026-0502-Q 先 | (確認のみ・Q で復旧) | 2026-05-02 |
| T2026-0502-S | 🟡 中 | **flotopic-bluesky governance check が起動以来 0 回成功** — 2026-05-02 09:50 JST 調査 (Cowork): `lambda/bluesky/handler.py:_init_table` が起動時に DynamoDB `ai-company-agent-status` テーブルを ensure するが、AWS で `aws dynamodb describe-table` が ResourceNotFoundException → テーブル未作成。Lambda IAM `dynamodb:CreateTable` 権限が無い疑い。30分毎の Lambda 起動で毎回 `[governance] ガバナンスチェック失敗（続行）` 出力 (CloudWatch logs に過去48h で50回以上、直近 09:39 JST)。「続行」設計なので致命的じゃないが、**PO 遠隔キルスイッチが完全無効化** → 万一 bot 暴走時に止められない安全機構の不全。対策: ①CloudFormation/Terraform で `ai-company-agent-status` テーブルを作成 (PK: agent_name) ②flotopic-bluesky IAM role に `dynamodb:GetItem`/`dynamodb:PutItem` 権限追加 ③auto-create を諦めて IaC で table 作成。完了条件: ResourceNotFoundException が直近1h 0件、`[governance] xxx: ステータス未登録 → active扱いで続行` ログに切り替わること | `scripts/_governance_check.py`, IAM role for flotopic-bluesky, IaC | 2026-05-02 |
| T2026-0502-T | 🟡 高 | **API Gateway flotopic-api 5xx 率 2.7〜17.6% 原因特定** — 2026-05-02 09:50 JST 調査 (Cowork): API Gateway `x73mzc0v06 (flotopic-api)` の 5xx 率: 4/30=4.7%・5/1=2.7%・5/2 朝=17.6%。一方で各統合 Lambda (p003-api/comments/contact/auth/favorites/analytics/cf-analytics) は **Errors=0 / Duration<700ms** で全て健全。Lambda 自体は通っているのに API Gateway が 5xx を返している = Lambda permission missing / CORS preflight に Lambda が紐付いていない / 502 統合エラーの可能性。Access logs (`accessLogSettings.destinationArn=null`) が未有効なので request 単位で見えない。対策: ①Access logs を CloudWatch に有効化 (1時間で原因特定可) ②CORS の OPTIONS routes が Lambda 統合になっているか確認 ③Lambda permission `AddPermission` を再付与。完了条件: 5xx 率 <0.5% へ低下、access logs から原因 1 行で説明可能。**Phase-Impact: 1 運用安定化** / **Eval-Due: 2026-05-09** | `.github/workflows/deploy-lambdas.yml` (apigateway 設定部分), AWS API Gateway Console | 2026-05-02 |
| T2026-0502-SEC1 | 🔴 緊急 | **Anthropic API Key + Slack Webhook ローテーション** — 2026-05-02 09:50 JST: 網羅調査中に `aws lambda get-function-configuration` 経由で `p003-processor` の env から ANTHROPIC_API_KEY (`sk-ant-api03-...`) が平文で AWS API 応答 → 私のチャット応答に表示。同様に `p003-fetcher` env から SLACK_WEBHOOK URL (`https://hooks.slack.com/services/T08UJJVCFJ4/B0AVBBXSR4J/...`) も。チャット履歴に残ったため両方 rotate 必須。手順: ①Anthropic Console → API Keys → 該当キー Revoke → 新規発行 ②GitHub Secrets `ANTHROPIC_API_KEY` 更新 ③Lambda env 全関数で ANTHROPIC_API_KEY 入れ替え (deploy workflow 経由) ④Slack workspace → Apps → Webhook URL revoke → 新規発行 ⑤同様に Lambda env / GitHub Secret 更新。完了条件: 旧 key で API 401 / 旧 webhook で post 不可・新 key で fetcher/processor 動作確認。**Phase-Impact: セキュリティ最優先 (フェーズ無関係)** / **Eval-Due: 2026-05-02 (即日)** | Anthropic Console, Slack Workspace, GitHub Secrets, Lambda env (全関数) | 2026-05-02 |

### フェーズ1 完了条件タスク（2026-04-28 PM 完了）

> **状態**: 全項目 landing 完了。フェーズ1 完了 → フェーズ2 着手可能。

#### ✅ 完了済（PO GitHub UI 設定 2026-04-28 PM 実施 + 本セッションで gh API 実測確認済）

| ID | 内容 | 確認方法 |
|---|---|---|

#### 残りのフェーズ1 補強タスク（コード対応）

| ID | 優先 | 軸 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|---|

### AI 品質・体験（フェーズ2/3）

> **着手条件**: フェーズ1 完了済 (2026-04-28 PM)。フェーズ2 着手可能。
> **2026-04-28 PM 実測スナップショット** (`docs/project-phases.md` 参照):
> - keyPoint 充填率 **10.02%** (107/1068) — 目標 70% 超に対し 60pt 不足
> - storyPhase 発端 articleCount≥3 **18.75%** (33/176) — 目標 10% 未満に対し 8.75pt 超過
> - PRED# 823 件あるが verdict 0 件 — judge_prediction 運用効果未発生 → ~~T2026-0428-E2-4 で根本原因 3 層特定 + 修正 (RFC2822 parser / 閾値 1d/3art / 旧 META backfill)。次回 processor run で 3 件 verdict 出る見込み~~

| ID | 優先 | 軸 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|---|
| ~~T2026-0430-C (→F)~~ | ~~🔴 高~~ | ~~観測~~ | ~~**freshness SLI に「<24h トピック比率」閾値アラート追加**~~ → **2026-04-30 20:13 JST 完了 (PR #48 merged, T2026-0430-F として実装)** — `.github/workflows/freshness-check.yml` に topics-card.json `lastArticleAt` 分布の <24h 比率計算ステップを追加。10% 未満で Slack 警告。Live実測: 14/108=13.0% (PR #46 直後で回復途中)。BUILDER_FIELDS allowlist にも `lastArticleAt` を追加 (SLI field guard CI が ERROR を出していたため)。Landing 検証は scheduled task `trig_01WnhUPiVhnvxZNVwvGS5nhU` (2026-04-30 21:43 JST) に渡してセッション close。注: 元案 ID は T2026-0430-C だが、git log 上 C は fetcher Float→Decimal (PR #46) で先に消費されていたため実装は T2026-0430-F として landing。 | .github/workflows/freshness-check.yml, scripts/check_sli_field_coverage.sh | 2026-04-30 |

---

## 📦 アーカイブ（将来検討）

> 上記「今週やること」以外のタスクをここに集約。週次レビューで必要なものをメインキューに昇格させる。
> **アーカイブ整理日**: 2026-04-28

### 将来機能（ユーザー増えてから）

<!-- フェーズ3 (UX 改善・成長) — ユーザー基盤拡大後の機能拡張 -->

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T056 | 低 | **フォロー/フォロワー機能**（将来・ユーザー増えてから） | — | 2026-04-26 |
| T109 | 低 | **アフィリエイト: トピック内容に合わせた関連商品表示（将来）** — 現状はジャンル固定キーワードで検索。AI要約生成時に商品検索クエリも同時生成して DynamoDB に保存し、トピックページに関連商品として表示できれば収益性向上。AI処理コスト増になるため収益化フェーズで検討 | `lambda/processor/proc_ai.py`, `frontend/js/affiliate.js` | 2026-04-26 |
| T154 | 中 | **お気に入りトピックへの新展開を Web Push 通知** — 根本原因: お気に入り登録しても次の展開を見に戻る動機がない。修正方法: ServiceWorker に Web Push 受信を追加。fetcher が既存お気に入り tid への新記事を検知 → DynamoDB notification_queue に積む → Lambda(notifier) が1日2回処理。ユーザー増加後の優先施策。 | `frontend/sw.js`, `frontend/mypage.html`, 新Lambda | 2026-04-26 |
| T201 | 低 | **bottom-nav の「リワインド」ラベルが初訪問ユーザーに意味不明** — 「リワインド」→「まとめ読み」または「振り返り」に変更検討 (要PO判断)。 | `frontend/catchup.html`, `frontend/index.html`, `frontend/storymap.html`, `frontend/topic.html`, `frontend/mypage.html` | 2026-04-27 |
| T217 | 低 | **footer 著作権「© 2024-2026」の妥当性（PO確認）** — about.html 開発開始年は 2026 に修正済み。残るは全ページ footer 表記。要PO判断後に統一。 | 全 *.html footer | 2026-04-27 |

### プロダクト戦略（メインキュー昇格候補）

<!-- フェーズ3 (UX 改善・成長) — ジャンル戦略・差別化 -->

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|

### リーガル・コンプライアンス

<!-- フェーズ1 (足回り安定) — 法的・規約遵守の運用品質 -->

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|

### セキュリティ・運用堅牢性

<!-- フェーズ1 (足回り安定) — セキュリティ・堅牢性の運用品質 -->

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T229 | 低 | **admin.html フロントだけのメール突合は装飾、信頼すべきではない事の明文化** — 攻撃者が DevTools で `CONFIG.allowedEmail` を書き換えれば UI は通る。バックエンドでちゃんと検証しているので致命的ではないが、analyticsUrl / cf-analyticsUrl は認証なしで取得可能。「フロントの認証は UX のため」とコメントを残すか、analytics エンドポイントにも Bearer 検証を追加するか方針を決める。 | `frontend/admin.html`, `lambda/cf-analytics/`, `lambda/analytics/` | 2026-04-28 |
| T252 | 中 | **CSP に unsafe-inline + unsafe-eval が設定されている — XSS 攻撃面拡大** — 全 HTML の CSP meta が `default-src 'self' https: 'unsafe-inline' 'unsafe-eval'`。理由は ld+json / inline style / Google Sign-In ライブラリが eval を使うため。コメント Lambda 側で sanitize しているなら被害は限定的だが、defense-in-depth 観点では弱い。段階的に `unsafe-eval` 削除 → inline style 外部化 → nonce/hash 化 を進める。 | `frontend/*.html` 全 CSP meta | 2026-04-28 |
| T267 | 中 | **CSP meta タグはあるが HTTP Response Header に CSP が無い — meta タグの限界** — HTML meta タグの CSP は対応ブラウザ・ドメイン制限・frame-ancestors 不対応など機能制限あり。CloudFront Response Headers Policy に `content-security-policy-report-only` で report-only mode で追加 → 1-2 週間 violation を観測 → 大きな違反が無ければ enforce mode に切替。 | CloudFront Response Headers Policy, 新規 `lambda/csp_report/` | 2026-04-28 |

### UI/UX

<!-- フェーズ3 (UX 改善・成長) — UI/UX 改修 -->

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|

### 安定性・運用

<!-- フェーズ1 (足回り安定) — 観測可能性・SEO 健全性・運用品質 -->

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
<!-- T2026-0428-AB (sitemap 404) は SLI 11 + processor regenerate で landing 済 (HISTORY.md 4280bf1) -->
<!-- T236 (governance worker 品質メトリクス) は freshness-check.yml SLI 8/9/10 で代替 landing 済。本来の _governance_check.py は agent-status 用で別物 -->
<!-- T2026-0428-N (AI フィールド SLI cron) は freshness-check.yml inline で landing 済 (HISTORY.md 19b272d) -->
<!-- T2026-0428-AG (backgroundContext 個別 JSON) は T2026-0428-N に統合済 -->
<!-- T2026-0428-R (system-status auto-commit) は landing 済 (HISTORY.md bb02349 + 3e188b0) -->
<!-- T261 (ads.txt 重複) は T239 と統合済 -->
<!-- T2026-0428-P (system-status 二重管理) は T2026-0428-R で構造改善 landing → 完了 -->
<!-- T266 (system-status カバレッジ古い) は T2026-0428-R で auto-commit 化済 -->
| T238 | 低 | **processor handler.py の特殊モード分岐が肥大化（300+行）** — `lambda/processor/handler.py:60-150` に `regenerateStaticHtml` / `backfillDetailJson` / `backfillArchivedTtl` / `purgeAll` / `forceRegenerateAll` / `regenerateSitemap` の6つの特殊モードが連結 if 文で並ぶ。テスト・保守・新モード追加が困難。`proc_admin_modes.py` に分離。 | `lambda/processor/handler.py` (新規ファイル) | 2026-04-28 |

### 収益・拡張

<!-- フェーズ3 (UX 改善・成長) — 収益化・SEO/AEO 機会拡張 -->

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T240 | 低 | **Cloudflare Web Analytics トークンがフロントに直書き** — index.html / topic.html 等の最後で `data-cf-beacon='{"token": "..."}'` がハードコード。これは CF 側仕様で公開するもので問題はないが、サブドメインや別環境を増やす際にビルド時 env 注入する設計が無い点だけメモ。 | `frontend/*.html` | 2026-04-28 |
| T241 | 低 | **アフィリエイトのセンシティブトピック自動非表示ロジック未実装** — CLAUDE.md「過去の設計ミスパターン」⑧で「事件・事故・医療・政治では非表示にする」とルール明記済み。affiliate.js で genre が `'社会'`/`'国際'`/`'健康'` × 記事タイトルが事件/事故/疾患キーワードを含む時は出さない実装が必要。AdSense 通過後・収益性確認後でよい。 | `frontend/js/affiliate.js`（推定）, `frontend/topic.html` | 2026-04-28 |
| T253 | 低 | **AI 学習クローラー全禁止 vs AI Visibility (AEO/GEO) のトレードオフ判断** — `robots.txt` で GPTBot / ChatGPT-User / Claude-Web / anthropic-ai / Google-Extended / PerplexityBot / Applebot-Extended / CCBot 全て Disallow。ChatGPT/Perplexity で「Flotopic」の名前を引いた時に検索結果に出てこない機会損失が発生。AI生成要約の知的財産価値 vs AEO/GEO 流入の機会値を Naoya 判断。 | `frontend/robots.txt`, `searchfit-seo:ai-visibility` | 2026-04-28 |

### 運用ガバナンス（Cowork×Code 連携）

<!-- フェーズ1 (足回り安定) — 運用ガバナンス・連携事故防止 -->

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T259 | 低 | **`Cache-Control: max-age=60` の topics.json が 90 分後鮮度警告と整合しない** — T263 実装時に「鮮度=updatedAt フィールド差分」「Cache-Control= edge cache TTL」の違いを混同しないこと。両者は別軸。 | T263 実装時に注意点として明記 | 2026-04-28 |
| T2026-0501-M | 🔴 高 | AI品質/フェーズ2 | **重複トピック検出・マージ（同一事象が複数カードに分裂）** — 例: 「トランプ大統領の欧州駐留米軍削減」と「トランプ氏がドイツ駐留米軍削減」が別カードで表示（PO実機確認 2026-05-01）。同一エンティティ・同一事象が表記揺れや地名の粒度差で別クラスタになる問題。対策: ①fetcher クラスタリング類似度閾値調整 or ②proc_storage でエンティティ重複検出→マージロジック追加。完了条件: flotopic.com で同一事象が1カードにまとまっていること（目視確認） | `lambda/fetcher/`, `lambda/processor/proc_storage.py` | 2026-05-01 |
| T2026-0501-K | 🟡 中 | AI品質/フェーズ2 | **keyPoint few-shot プロンプト改善 — エンタメ/テクノロジー充填率引き上げ** — p003-sonnet 22:11 JST 実測: 全体 61.5% (139/226、目標70%) / エンタメ 35.0% (7/20) / テクノロジー 37.5% (6/16) が低迷。proc_ai.py の `_STORY_PROMPT_RULES` に埋め込まれた良例 (◎) がエンタメ/テク向け例を含まない。genre_hint は注入済みだが短文 (10〜30字) が retry 後も残る事例あり。改善案: `_STORY_PROMPT_RULES` の keyPoint ◎例 2 件を「エンタメ: 降幡愛の首絞め件 → 150字正解版」「テック: NTT AIOWN → 150字正解版」に差し替え。完了条件: 次回 processor 実行後 エンタメ/テク 充填率が各 50% 以上になること | `lambda/processor/proc_ai.py` | 2026-05-01 |
| T2026-0501-G | 🟡 中 | 観測/自動化 | **p003-haiku コスト実測 → Claude in Chrome で Anthropic Dashboard 定期読み取り** — `console.anthropic.com/settings/usage` を Claude in Chrome で読み取り当月コストを取得する方式を採用（Case B）。完了条件: Anthropic Dashboard の当月コストを Dispatch が報告できること | （Claude in Chrome 調査） | 2026-05-01 |
| T2026-0501-L | 🟡 中 | 観測/自動化 | **Anthropicコスト+SLI 週次 Notion レポート Scheduled Task** — Claude in Chrome で `console.anthropic.com/settings/usage` を読み取り当月コスト取得 + topics-card.json SLI (keyPoint充填率・perspectives・fresh24h) + GitHub CI status + 新トピック数 を Notion ページに週次（月曜09:00 JST）自動書き込み。完了条件: Notion ページに実データが書き込まれること | `Scheduled Tasks (p003-notion-report)`, Notion MCP | 2026-05-01 |
| T2026-0428-S | 🟢 低 | **contact.html が noindex 設定 — E-E-A-T 上は indexable が望ましいか再判断** — 2026-04-28 07:13 schedule-task で curl 確認、`<meta name="robots" content="noindex">` 設定。連絡先ページは Google E-E-A-T 評価で「Trust」シグナル源。AdSense 審査でも contact 有無は評価対象。**懸念**: 現状 noindex のため検索結果に出ない → 信頼性シグナルとして検索エンジンに認識されない可能性。**判断材料**: SES 受信専用フォームで spam リスクが高いから noindex にしているなら維持、純粋な連絡先表示なら indexable に変更。要PO確認後に変更検討。 | `frontend/contact.html` | 2026-04-28 |
| T2026-0428-U | 🟢 低 | **個別 topic JSON (L4b) の AI フィールド充填率 SLI** — `_PROC_INTERNAL = {spreadReason, forecast, storyTimeline, backgroundContext}` は topics.json publish 時に除外され、これらは個別 `api/topic/{tid}.json` (L4b) でのみ観測可能。現状 SLI 8/9/10 は L4a (topics.json) のみ。`scripts/check_ai_fields_coverage.sh` を sample N=10 個別 JSON 取得 → backgroundContext / spreadReason / forecast / timeline 充填率を集計 → SLI 11/12/13 として登録。詳細: `docs/ai-fields-catalog.md`, lessons-learned 2026-04-28 07:13。 | `scripts/check_ai_fields_coverage.sh`, `.github/workflows/freshness-check.yml`, `docs/sli-slo.md` | 2026-04-28 |
<!-- T2026-0428-N (AI フィールド充填率 SLI 化) は freshness-check.yml SLI 8/9/10 として inline landing 済 (HISTORY.md 19b272d) -->
<!--   閾値: keyPoint 70% / perspectives 60% / outlook 70%。Slack 通知も実装済 -->
<!--   外部 cron は freshness-check.yml の schedule で代替 (06:10 JST 等)。本タスクは完了扱い -->
| T2026-0428-AG | 🟢 低 | **個別 topic JSON で backgroundContext / spreadReason の充填率検証** — T2026-0428-N (上記 landing 済) は topics.json (L4a) の SLI。個別 topic JSON (L4b) の `backgroundContext` 等は別観測が必要。任意 5 topic を curl サンプリングして空でないことを確認する手順を追加 | (T2026-0428-Q success-but-empty 横展開 に統合) | 2026-04-28 |
<!-- T2026-0428-AG 旧行は SLI 9 統合済のため削除 (T2026-0428-Q 横展開へ移管) -->

### SLI/SLO 設計

<!-- フェーズ1 (足回り安定) — 観測可能性の設計 -->

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|

---

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
