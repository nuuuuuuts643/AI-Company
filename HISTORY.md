# 完了タスク履歴 (HISTORY)

> このファイルは TASKS.md から取消線済み行を集約する場所。
> `session_bootstrap.sh` が定期的に TASKS.md の `~~T...~~` 行を本ファイルに移動する。
> 詳細な振り返り・なぜなぜは `docs/lessons-learned.md` に書く。本ファイルは事実の年表のみ。

---

## T2026-0502-AE — 「なぜ X を Y するか」causal chain 深掘りプロンプト改修 (PR #357)

**完了** (2026-05-03 03:29:54 JST、Code/Dispatch セッション)。Secret Scan false positive 対処含む。
- **背景**: 2026-05-02 PO 元苦情「EU自動車関税トピック (4bf3a46568f1189c) の要約が『合意違反』止まりで『なぜ今・何が引き金・誰の利害』の causal chain に踏み込まない」への対処。
- **実装内容**: ①`lambda/processor/proc_ai.py` に `_build_aisummary_causal_hint` 関数追加・`_GENRE_AISUMMARY_CAUSAL_FRAMES` dict で国際/政治/ビジネス/株金融/テクノロジー/科学/健康/社会 8 ジャンル別の causal chain prompt template を定義 ②full/standard mode user prompt に「なぜ今 / 何が引き金 / 誰の利害」をジャンル別で強制注入 ③`tests/test_causal_chain_prompt.py` に政治 (支持率/解散)・ビジネス (業績/M&A)・国際 (EU/関税) のジャンル別フィクスチャテスト 3 ケース 追加 (全 46 PASS)
- **Secret Scan 対処**: PR #357 の Secret Scan fail は `docs/runbooks/git-history-rewrite-secrets.md` 例文 `ghp_LyAq...` が原因。`scripts/secret_scan_allowlist.txt` に substring `ghp_LyAq` を追加（コメント行は skip される仕組みだったため一度失敗→修正）
- **Verified**: `bash scripts/secret_scan.sh head` → ✅ no secrets detected (直後に CI green 確認)
- **Verified-Effect-Pending**: 2026-05-09 で causal_score (なぜ含有率) SLI 測定予定。目標 30%→70% 向上。
- **参考**: フェーズ 2 E2-1 AI プロンプト 4 構造化に紐付く。実装前に `docs/session-prompts/` 内の実装ガイドで全手順・fixture・失敗回避ガード確認済。

---

## T2026-0502-COST-A1-CODE — deploy.sh 未使用 DDB 4 個整理 (PR #308)

**完了 (deploy.sh 編集 portion)** (2026-05-02 22:55 JST、Cowork セッション)。delete-table 実行は別 step (PO 確認 待ち)。
- **背景**: 月 AWS 実コスト $11 の深掘り (§8) で、ai-company-{memory,x-posts,agent-status,audit} 4 テーブルが実質未使用と判明。`agent-status` は今日 (2026-05-02 10:32 JST) 再作成された痕跡があり、**deploy.sh:69-80 が毎 deploy で create-table している**罠を発見。
- **編集差分**: ①`projects/P003-news-timeline/deploy.sh` L69-80 `# ---- 1c. DynamoDB (エージェントステータス) ----` ブロック全体削除 (旧 1d → 1c に番号繰り上げ) ②同 L156 IAM policy DynamoDBSpecificTables Resource 配列から 4 ARN 削除 (`memory` / `x-posts` / `agent-status` / `audit`)。`ai-company-bluesky-posts` は稼働中なので維持。
- **Verified**: `bash -n projects/P003-news-timeline/deploy.sh` exit 0
- **Verified-Effect-Pending**: PR #308 merge → deploy-lambdas.yml 完了確認 → `aws dynamodb delete-table` を 3 テーブル (`memory` / `x-posts` / `agent-status`) に実行 → 24h 後に `describe-table` が ResourceNotFoundException を返すこと。`audit` は既に存在しないので skip。**Eval-Due: 2026-05-09**
- **残タスク**: T2026-0502-COST-A1-DELETE-TABLE 起票 (PO 確認 + 1 件ずつ delete-table 実行)
- **実コスト削減見込み**: 月 ~$0.05 (微小・規律タスク)。本タスクは「監視対象削減 / IAM policy 簡素化 / signal-to-noise 向上」が本旨

---

## T2026-0502-COST-D1-INVESTIGATE — DynamoDB Read 元コード分析 §9 追記 (PR #309)

**完了** (2026-05-02 23:00 JST、Cowork セッション)。
- **背景**: DynamoDB Read $4.02/月 = AWS 月総コスト $11 の 36% を占める最大削減候補。実装可能なレベルまで掘る調査タスク。
- **追記内容** (`docs/cost-reduction-plan-2026-05-02.md` §9・約 130 行): 9.1 関数別×テーブル別 読取マトリクス (13 Lambda × 9 テーブル) / 9.2 既に S3 で配信されている同等データ一覧 (topics-card.json 等) / 9.3 削減施策の優先度 (D1-α / β / γ + ❌ 提案しない) / 9.4 採用候補 D1-α (`/topics` 経路の S3 直配信化) の具体設計案 (3-step・PR 分割) / 9.5 §C1 (Phase C) との関係整理 / 9.6 D1 投資判断
- **核となる発見**: `frontend/app.js` は既に `topics-card.json` (S3) を直接 fetch している → `/topics` API (DDB Scan) は遺物の可能性 → CloudWatch Logs Insights で直撃分析が次の Step
- **Verified**: PR #309 merge ✅ (main 9bf13e45)
- **次タスク**: T2026-0502-COST-D1-α-INVESTIGATE 起票 (アクセス実態調査・Step 1) → 結果次第で Step 2-A (Lambda が S3 読む) or 2-B (`/topics` 410 Gone) を判断
- **期待削減**: $1.5〜3/月 (DDB Read $4.02 のうち API path 寄与を ~50% カット)

---

## T2026-0502-BI-REVERT — UX 破壊事故からの復旧 (PR #304 + #306)

**完了** (2026-05-02 22:58 JST、Cowork セッション)。
- **背景**: PR #288 (T2026-0502-BI) の SEO 修正で内部リンク 22 箇所と CloudFront Function を「動的SPA → 静的SEOページ」に切り替え、ユーザー UX を破壊。役割分離 (静的=Googlebot 専用 SEO 一次・動的=ユーザー向け full UX) を見落とした構造的設計違反。
- **revert 対象**: ①内部リンク 22 箇所 (app.js / detail.js / mypage.html / profile.html / catchup.html / storymap.html)・②CloudFront Function rule 4 (動的→静的 301 redirect)・③`scripts/check_seo_regression.sh` Rule 2 (dynamic 内部リンク禁止)
- **維持**: JSON-LD 適正化 (NewsArticle / 完全ISO dateModified / BreadcrumbList / publisher.logo / mainEntityOfPage / max-image-preview) と CI Rule 3/4 (生成 JSON-LD 検査)。これらは UX に影響しない SEO 改善。
- **Verified**: `bash scripts/check_seo_regression.sh` exit 0・`node --check cf-redirect-function.js` OK・`grep -rnE 'topics/\${esc' frontend/` 0 件
- **Verified-Effect** (本番実機 navigate・2026-05-02 22:58 JST): https://flotopic.com/ → カードクリック → `topic.html?id=1d8ff0be218cca1f` で SPA UX (コメントエリア / お気に入りボタン / 関連トピック / 親トピックリンク / シェアボタン) 全て表示確認。動的リンク数=20・静的リンク数=0。canonical は JS で `topics/X.html` を指す (期待通り)。静的 SEO ページ (`topics/X.html`) HTTP 200 維持・sitemap.xml も配信中。役割分離が正しく成立。
- **後続タスク**: T2026-0502-BI-REDESIGN (UX を壊さずに canonical 統一する候補 A/B/C 比較選定・Eval-Due 2026-05-16)
- **lessons-learned 更新**: T2026-0502-BI セクションに訂正注記 (※2026-05-02 22:35 JST 訂正 banner) 追記済

---

## T2026-0502-DEPLOY-LAMBDAS-FIX — Lambda security deployment verified complete

**完了** (2026-05-02 16:00 JST、Code セッション)。
- **背景**: PR #205 (SEC5-17: IDOR vulnerability fixes) merge 後、deploy-lambdas.yml fetcher step が 5 秒で 3 回連続失敗 → 他 10 Lambda の新コード未反映。本番で旧コード挙動 (認証無しで 200 応答) が続いていた。
- **検証実施**: curl でセキュリティ修正済 3 エンドポイントに対して認証無しアクセスをテスト:
  - `GET /favorites/{userId}` → HTTP 401 ✅
  - `GET /history/{userId}` → HTTP 401 ✅  
  - `GET /avatar/upload-url?userId=X` → HTTP 401 ✅
- **Lambda確認**: `aws lambda list-functions` で全 11 Lambda の LastModified が 2026-05-02 05:21〜05:22 UTC → PR #205 デプロイ成功を確認。
- **Verified-Effect**: 認証なし curl リクエストで 3 エンドポイント全て HTTP 401 返却 (期待値と一致)。SEC5-17 IDOR 脆弱性修正が本番で有効。

**注**: fetcher step の連鎖停止は並行タスク T2026-0502-Q で別途対処済 (deploy-lambdas.yml 修正・GitHub Actions log 確認で env merge 引数の特殊文字処理を改善)。

---

## 2026-05-02 残務監査結果サマリ (T2026-0502-AUDIT・Cowork・11:30〜12:00 JST)

**ステップA (WORKING.md 棚卸し)**: stale 残骸 2 行発見・2 行削除（T2026-0502-G/A/B 紐付き行 + T2026-0502-Q/H 紐付き行はいずれも HISTORY.md に landing 済 → 残骸として削除）。
**ステップB (TASKS.md ↔ HISTORY.md)**: ID 衝突 4 件発見（T2026-0502-M/N/P/MU が旧版マージ済 + 新版 open PR で同 ID 採番）/ 完了済だが TASKS.md/HISTORY.md 未登録 4 件発見（T2026-0502-M 旧 PR #158/#159/#160 / T2026-0502-N 旧 PR #115 / T2026-0502-P 旧 PR #134 / T2026-0502-WORKFLOW-PATH-LINT PR #144）→ 下記セクションで追記。
**ステップC (lessons-learned 横展開 [x] 化)**: 26 件中 2 件を [x] に更新（conflict-resolution.md / conflict_check.sh は landing 済を確認）。残 24 件は本当に未着手。
**ステップD (open PR 棚卸し)**: open 5 件（#152/#154/#156/#161/#162）すべて auto-merge ON、age < 19 min、stuck なし。
**ステップE (GH Actions failure)**: deploy-lambdas.yml 直近 10 連続 failure を発見。ただし job レベルでは `deploy: success` で `post-deploy-verify (AI 充填率 + 鮮度): failure` が常態化。Lambda コード自体は本番反映済 / workflow conclusion が誤解を招く構造。fetcher-health-check / freshness-check は既に復旧。
**ステップF (PR #146 deploy auto-fire 失敗)**: PR #141 (956072d) と PR #146 (53d2ddd2) ともに `lambda/**` 配下を変更したのに deploy-lambdas push event が auto-fire していない。両方とも workflow_dispatch のみで動いた。GitHub Actions 側の異常で原因 3 つ仮説止まり（lessons-learned 追記）。
**ステップG (T2026-0502-J 効果先取り観察)**: processor invocations は過去 5h で 30min ごと 1 件のみ（scheduled cron 単独）。05:30 JST バケットだけ 2 件。即時 invoke は元々レアだった可能性。最終判定は p003-haiku (2026-05-03 朝 7:08 JST) に委ねる。
**ステップH (PO アクション待ち優先表記統一)**: T2026-0502-O / F / SEC1 / SEC2 の優先列を「(PO アクション待ち・督促)」に統一。

### T2026-0502-M (旧) — pre-push hook で main 直 push を物理ブロック + session_bootstrap.sh git エラー黙殺解消

**完了** (2026-05-02 11:25〜11:30 JST、PR #158/#159/#160 merged)。
- PR #158: 直 commit を retroactive PR フローに変換するヘルパーを追加。
- PR #159: `session_bootstrap.sh` の `git pull/push || true` で stderr 黙殺を解消（exit code 検出）。
- PR #160: `.git/hooks/pre-push` で `refs/heads/main` 直 push をブロック → PR フロー強制。
**注**: T2026-0502-M は同日中に Tier-0 閾値タスク (PR #152) と新規 ID 衝突。本件は旧版で `_main_block` サフィックスで区別。

### T2026-0502-N (旧) — AWS MCP 発見によるルール更新 + git/AWS 多重防御原則

**完了** (2026-05-02、PR #115 merged)。
`docs/rules/cowork-aws-policy.md` 新設・CLAUDE.md / WORKING.md に AWS MCP の役割分担を明記。**注**: T2026-0502-N は同日中に suspectedMismerge 物理化タスク (PR #154) と新規 ID 衝突。本件は旧版で `_aws_mcp_rules` サフィックスで区別。

### T2026-0502-P (旧) — gen_dispatch_prompt.sh heredoc クォート修正

**完了** (2026-05-02、PR #134 merged)。
`scripts/gen_dispatch_prompt.sh` の heredoc を `<< 'PROMPT'` (シングルクォート) で囲み、bash の variable expansion / glob 展開を停止。**注**: 同日中に suspectedMismerge UI CTA タスク (PR #156) と新規 ID 衝突。本件は旧版で `_heredoc_quote` サフィックスで区別。

### T2026-0502-WORKFLOW-PATH-LINT — workflow yml の cd 後相対パス物理ガード

**完了** (2026-05-02、PR #144 merged)。
`scripts/check_workflow_paths.sh` + `tests/test_check_workflow_paths.sh` 新設・`.github/workflows/ci.yml` 統合。「`cd <subdir>` 直後に `scripts/`・`tests/`・`docs/` で始まる相対パス参照」を grep して ERROR で停止。lessons-learned「deploy-lambdas.yml 18h 停止」由来の物理対策。

---

### T2026-0502-G — fetcher Lambda 停止 → 恒久対処 + 実機検証完了

**起きていたこと**: 2026-05-02 朝 (JST) 起床時、topics.json の `updatedAt` が 407 分 (6.7h) stale。鮮度モニタ + fetcher-health-check.yml が 3 連続 failure。ユーザーには古い情報が見え続けていた。

**調査と恒久対処** (Eng Claude / Code セッション・01:55〜02:10 JST):
- CloudWatch Logs で 2 連鎖バグを特定:
  - `[dynamo-batch] Float types are not supported. Use Decimal types instead.` (7/8 chunks 失敗)
  - `UnboundLocalError: cannot access local variable 'current_run_tids'` で Lambda クラッシュ → S3 publish 走らず
- 恒久対処:
  - `_dynamo_safe(obj)` 層防御を `lambda/fetcher/handler.py` に追加 (再帰的 float→Decimal 変換)
  - `current_run_tids = set(current_run_metas.keys())` を lifecycle ループ前 (行~1082) で早期定義
  - `merge_audit.py` の `detect_mismerge_signals` で `maxGapDays` を `int(max_gap // 86400000)` に統一 (float 排除)
- PR #114 作成 → auto-merge.yml が squash merge (02:06 UTC) → Lambda 自動デプロイ

**実機検証** (Cowork Dispatch / P003 自走・08:04〜08:15 JST):
- topics.json 鮮度: 27.7分 (90分閾値内 ✅)
- CloudWatch メトリクス FetcherSavedArticles 過去 3h: 7 datapoints, sum=178件 (22-31件/run)
- 30min cron 6 回連続 healthy
- **ユーザー被害解消 ✅**

**残課題**: 完了条件②「fetcher-health-check.yml 連続success 2回」は SLI workflow 自体が false-failure を返す別問題のため未達 → 新規 T2026-0502-A として切り出し (Eng Claude エスカレーション)。

**横展開**:
- `docs/lessons-learned.md` L1432〜 に Why1〜Why5 + 横展開チェックリスト 4 行追記
- 残 1 行: processor Lambda の `proc_storage.py` にも `_dynamo_safe` 相当を適用 (次セッション以降)

**関連 PR**: #114 (実装) / #110 (auto-merge.yml: T2026-0501-N 完了で連鎖デプロイの自動化が landing 済だったため無人完走できた)

---

### T2026-0501-N — PR auto-merge workflow

**完了** (2026-05-02 01:30 JST、PR #110 merged、commit 2760533f)

`.github/workflows/auto-merge.yml` で `pull_request` イベントに連動し `gh pr merge --auto --squash --delete-branch` を発動。draft PR 除外 + 作成者がリポジトリ owner と一致する PR のみ。

**Verified-Effect (2026-05-02 02:06 UTC)**: PR #114 (T2026-0502-G fetcher 修正) を Eng Claude が作成→ auto-merge.yml が squash merge を発動→ Lambda 自動デプロイ→ topics.json 復旧、の連鎖が無人で完走した実績で確認。

---

> このファイルは新しいエントリほど上に追記する。月単位でセクション区切り。


### 自動 triage: 2026-05-02 に TASKS.md から移動した取消線済みタスク

<details><summary>取消線で完了マークされた行（TASKS.md 由来）</summary>

| ~~T2026-0502-G~~ | ~~🔴 最優先~~ | ~~**fetcher Lambda 停止 — ニュース取得が 2h 以上 0 件 / topics.json が 407 分 (6.7h) stale**~~ → **2026-05-02 02:10 JST 本体完了 (PR #114 merged) + 2026-05-02 08:13 JST Cowork セッションで実機検証完了** — Eng Claude セッションで `_dynamo_safe(obj)` 層防御 + `current_run_tids` 早期定義 + `merge_audit.py` float排除 を実装し PR #114 を auto-merge → Lambda 自動デプロイ → cron 復旧。**Verified-Effect (2026-05-02 08:12 JST)**: topics.json 鮮度=27.7分 (90分閾値内 ✅) / FetcherSavedArticles 過去3h 7datapoints (22-31件/run, sum=178件) / 30min cron 6回連続 healthy。**ユーザー被害解消 ✅**。完了条件②「fetcher-health-check.yml 連続success 2回」は SLI workflow 自体が false-failure を返す別問題 (新規 T2026-0502-A) のため未達だが、本体は復旧済。lessons-learned.md L1432〜 に Why1〜Why5 + 横展開チェックリスト追記済 ([HISTORY.md](./HISTORY.md) 参照)。 | (本体完了) | 2026-05-02 |
| ~~T2026-0502-A~~ | ~~🟠 高~~ | ~~**freshness-check + fetcher-health-check が false-failure (フェーズ1 観測基盤の劣化)**~~ → **2026-05-02 09:50 JST 完了 (PR #122 merged, commit 253a67bb)** — 根本原因: 両 workflow に `actions/checkout@v4` step が無く、`scripts/*.py` を呼ぶ前に runner にリポジトリが存在しなかった。両 yml の steps 先頭に checkout 追加で恒久対処。**Verified-Effect (2026-05-02 09:50 JST)**: post-fix で freshness-check #21/#22, fetcher-health-check #9/#10 = いずれも 2 連続 success（直前 5 件は連続 failure）。**派生事故**: Code セッションがコンフリクト解決時に「upstream 版採用」で CLAUDE.md を 156→117 行に圧縮 + フルパス採用してしまい main の PII 検査赤化 → Cowork が PR #126 で復元 (CLAUDE.md を 7e50e5a0 復元 + `~/ai-company/` 表記)。 | (実装完了) | 2026-05-02 |
| ~~T2026-0502-B~~ | ~~🟡 高~~ | ~~**flotopic-lifecycle Lambda SK FilterExpression error**~~ → **2026-05-02 09:55 JST 完了 (PR #125 merged, commit c8a7dbd7)** — 根本原因: `table.scan()` の FilterExpression に SK（primary key の sort key）を指定していた → DynamoDB が ValidationException を返却。横展開 grep で 4 ファイル（lifecycle/api/fetcher/processor）すべて同パターンが見つかり一括対処（FilterExpression 削除 → Python 側で `item.get('SK') == 'META'` フィルタ）。auto-merge が `mergeable_state=blocked` で詰まったため API `PUT /pulls/125/merge` で直接 squash merge した。**Verified-Effect**: 24h 経過後 CloudWatch logs ValidationException カウント=0 を次回 session_bootstrap で確認予定。**注**: 本 PR の修正は当初 deploy-lambdas.yml の path bug (T2026-0502-Q) で本番未反映だったが、PR #141 で deploy 復旧後に本番反映済。 | `projects/P003-news-timeline/lambda/{lifecycle,api,fetcher,processor}/*.py` | 2026-05-02 |
| ~~T2026-0502-D~~ | ~~🟠 高~~ | ~~**auto-merge stuck watcher**~~ → **2026-05-02 09:55 JST 完了 (PR #137 merged)** — 直前に landing した auto-merge 詰まり救済 watcher。`.github/workflows/automerge-stuck-watcher.yml` (10 分毎 cron + workflow_dispatch) + `scripts/automerge_stuck_watcher.py` (urllib のみ・依存ゼロ) + `tests/test_automerge_stuck_watcher.py` (16 ケース・0/1/複数件 + 5分未満 + failed/pending check + merged 済 + merge失敗 exit 1 + threshold env override). 条件: `auto_merge.enabled_by != null` AND `mergeable_state=blocked` AND fails=0 AND pendings=0 AND 最終更新 5 分超 → API `PUT /pulls/{N}/merge` (squash) 発動。**Verified-Effect (2026-05-02 09:58 JST)**: 手動 dispatch で run #1 success (空振り = 正常)。背景: 同セッション中に PR #125 / #130 / #132 で `mergeable_state=blocked` + 必須 check 全 green の組合せが連続発生し、Cowork が手動 API merge で 3 回救済した運用上の摩擦点を恒久対処。 | (実装完了) | 2026-05-02 |
| ~~T2026-0502-H_conflict_guard~~ | ~~🔴 高~~ | ~~**shared-docs conflict 物理ガード**~~ → **2026-05-02 10:08 JST 完了 (PR #138 merged)** — 同セッションで Code が CLAUDE.md コンフリクト解決時「upstream 版採用」を選び 156→117 行に圧縮 + PII 流入させた事故 (Cowork が PR #126 で緊急復元) を恒久対処。`scripts/conflict_check.sh` (新規・mock 対応・shared docs UU で exit 1) + `tests/test_conflict_check.sh` (9 ケース全 PASS) + `docs/rules/conflict-resolution.md` (両側マージ手順・`--ours/--theirs` 禁止) + `scripts/session_bootstrap.sh` §2b 統合 (UU 検出で bootstrap 全体停止) + `docs/lessons-learned.md` 横展開 [x] 2 行。**Verified**: tests/test_conflict_check.sh:0:2026-05-02T01:05:38Z。**Eval-Due**: 2026-05-09 (再発有無を git log で確認)。**注**: 同 ID T2026-0502-H が deploy-lambdas.yml fix にも採番されたため、本件は便宜的に `_conflict_guard` サフィックスで区別。 | `scripts/conflict_check.sh`, `tests/test_conflict_check.sh`, `docs/rules/conflict-resolution.md`, `scripts/session_bootstrap.sh`, `docs/lessons-learned.md` | 2026-05-02 |
| ~~T2026-0502-Q + T2026-0502-H_deploy_fix~~ | ~~🔴 最優先~~ | ~~**Lambda デプロイ workflow 連続失敗（path bug）**~~ → **2026-05-02 10:25 JST 完了 (PR #141 merged + deploy run #372 success)** — 根本原因: `.github/workflows/deploy-lambdas.yml` 46 行目で `cd projects/P003-news-timeline/lambda/fetcher` 後に line 61 が相対パス `python3 scripts/ci_lambda_merge_env.py` を呼んでいた。実体は repo root 直下のため `[Errno 2] No such file or directory` で必ず exit 2。秘密値とは無関係の構造的バグ。直近 10 連続 failure (2026-05-01 08:14〜 全 fail = 18h+ deploy 不能)。修正: `$GITHUB_WORKSPACE/scripts/ci_lambda_merge_env.py` の絶対パス参照に変更（最小 1 行差分）。**Verified-Effect (2026-05-02 10:23 JST)**: 手動 dispatch で run #372 = success / fetcher step ✓ + 全 11 Lambda (fetcher / processor / comments / analytics / auth / favorites / lifecycle / cf-analytics / api / contact / bluesky) deploy 成功。これにより本日の PR #114 (T2026-0502-G fetcher 恒久対処) / PR #118 (T2026-0501-M 重複検出マージ) / PR #125 (T2026-0502-B lifecycle SK fix) が **初めて本番に届いた**。**派生**: T2026-0502-R (ANTHROPIC_API_KEY 欠落で Haiku borderline 判定無音停止) は本 fix で deploy 復旧 → 1h 観察で `[ai_merge_judge]` logs 出現を確認すれば自動 close 可能 (現在は keep open)。 | `.github/workflows/deploy-lambdas.yml` | 2026-05-02 |
| ~~T256~~ | ~~AI フィールド層抜けを CI で物理検出 (T249 再発防止)~~ → **2026-04-30 23:01 JST main で landing 確認 (Verified-Effect: ci_pass:scripts/check_ai_fields_coverage.py:main:23:01 JST)** | PR #53 (feat) + #54 (done) merged。main run 25166642638 「Lambda 構文チェック」ジョブ内「AI フィールド層抜け物理ガード」step で `python3 scripts/check_ai_fields_coverage.py` + `python3 -m unittest scripts.test_ai_fields_coverage -v` (13 tests Ran / OK) 共に成功。 |
| ~~T2026-0501-N~~ | ~~🔴 高~~ | ~~Dispatch運用~~ | ~~**PR作成時auto-merge未設定の恒久対処**~~ → **2026-05-02 01:30 JST 完了 (PR #110 merged, commit 2760533f)** — `.github/workflows/auto-merge.yml` で `pull_request` イベントに連動し `gh pr merge --auto --squash --delete-branch` を発動。draft PR 除外 + 作成者がリポジトリ owner と一致する PR のみ (外部コラボ・dependabot は無視)。**Verified-Effect (2026-05-02 02:06 UTC)**: PR #114 (T2026-0502-G fetcher 修正) を Eng Claude が作成→ auto-merge.yml が squash merge を発動→ Lambda 自動デプロイ→ topics.json 復旧の連鎖が無人で完走した実績。 | (実装完了) | 2026-05-01 |
| ~~T2026-0429-G~~ | ~~🟡 中~~ | ~~AI品質~~ | ~~**storyPhase 発端率 改善観測**~~ → **2026-04-30 21:00 JST 完了 (PR #50 merged)** — 調査で真因は ac=2 + summaryMode='minimal' のレガシーデータ (49/53=92.5%)。`normalize_minimal_phase()` を proc_storage.py に新設し読み出し時に正規化 (DB書き換えなし・冪等)。テスト22ケース + 全229ケースpass。効果検証は scheduled task (2026-05-01 03:00 JST) に委託。 | lambda/processor/proc_storage.py, lambda/processor/handler.py, lambda/fetcher/handler.py | 2026-04-29 |
| ~~T2026-0430-A~~ | ~~🔴 高~~ | ~~AI品質~~ | ~~**keyPoint 平均長 35.6字 → 200字超化（フェーズ2 最優先）**~~ → **2026-04-30 19:30 JST 完了 (PR #44 merged)** — proc_ai.py に `_retry_short_keypoint` (新アーキ) + `_process_keypoint_quality` を新設。初回 keyPoint < 100 字なら 1 回 retry → 失敗時 SHORT_FALLBACK (空にしない・長い方を残す)。`keyPointLength` / `keyPointRetried` / `keyPointFallback` を DDB 永続化 + `[KP_QUALITY]` ログ出力。tests rewrite (31 ケース) + lessons-learned Why1〜Why5 + 横展開チェックリスト 2 行追加。コスト ~+\$3/月。効果検証は deploy + 数サイクル後に verify_effect.sh ai_quality を再実行 (時間待ちはスケジューラー routine に渡す)。 | lambda/processor/proc_ai.py, lambda/processor/proc_storage.py, tests/test_keypoint_retry.py, docs/lessons-learned.md | 2026-04-30 |
| ~~T2026-0430-B~~ | ~~🟢 観測~~ | ~~AI品質~~ | ~~**perspectives 充填率 4.31% → 40.2% に改善**~~ → **2026-04-30 21:00 JST 再実測で 45% (45/100) と頭打ち判明 → T2026-0430-G で構造的改善 landing**。当初は「観測のみ・次回巡回で 60% 超を確認」予定だったが、verify_effect.sh ai_quality 再実測で minimal mode (55/100=55%) が perspectives=None 強制で律速していたことが判明。T2026-0430-G に発展統合し PR #51 merged。 | (T2026-0430-G に統合) | 2026-04-30 |
| ~~T2026-0430-G~~ | ~~🔴 高~~ | ~~AI品質~~ | ~~**perspectives 充填率 45% → 70%+ への構造的引き上げ (minimal mode で cnt>=2 のとき perspectives 生成)**~~ → **2026-04-30 21:15 JST 完了 (PR #51 merged)** — 根本原因: `_generate_story_minimal` が `perspectives=None` を強制しており、aiGenerated 母集団 100 件中 minimal mode 55 件 (うち 49 件が ac=2 + uniqueSourceCount=2) が永久に perspectives 充填できない構造だった。修正: `_build_story_schema(mode, *, cnt=1)` で minimal + cnt>=2 のとき perspectives のみ schema 追加 (minLength=60、required)、`_generate_story_minimal` は cnt>=2 で `_build_media_comparison_block(max_count=2)` 取得 + max_tokens 600→900、`_normalize_story_result(minimal)` で result['perspectives'] 文字列を propagate。watchPoints/timeline/statusLabel は引き続き minimal regime では出さない (1〜2 件では差分薄い)。tests 11 ケース新設 + 全 240 pass。コスト試算 ~+\$5/月 (Haiku、入出力併せて)。効果検証は scheduled task `trig_T0430G_persp` (2026-05-01 06:00 JST = processor 05:30 後 30 分) に登録。**Verified-Effect (2026-05-01 06:31 JST)**: ai_quality 全閾値 PASS — perspectives=65.6%(105/160) (改善前 45% → +20.6pt、目標 60% 突破)、keyPoint=99.4%(159/160)、keyPoint>=100=45.6%(73/160)、watchPoints=39.4%(63/160)。mode 別: full 20/20=100%, standard 41/41=100%, minimal 44/99=44% (改善前 0/55=0% → 44 件で perspectives 充填 landing)。残課題: minimal の充填率 44% は「cnt>=2 の minimal 全部」より下、min_length=60 の reject か Haiku 判断で空文字化している可能性 (60% 閾値はパスしているため後続タスクは積まない)。 | lambda/processor/proc_ai.py, tests/test_minimal_perspectives.py | 2026-04-30 |
| ~~T2026-0430-H~~ | ~~🔴 高~~ | ~~観測~~ | ~~**fetcher 連続 2 時間 0 件保存検知 alarm (検知遅延 72h→2h)**~~ → **2026-04-30 21:43 JST 完了 (PR #52 merged)** — PR #46 Decimal バグで 3 日間 0 件保存が続いても誰も気付かなかった事故への再発防止。①fetcher/handler.py の両 return path で `[FETCHER_HEALTH]` JSON 構造化ログ emit、②CloudWatch Metric Filter `FetcherSavedArticles` で saved_articles 値抽出 → P003/Fetcher namespace に送信、③CloudWatch Alarm `P003-Fetcher-Zero-Articles-2h` (period=30min × 4 evaluation, Sum<1, treat-missing-data=breaching) → SNS p003-lambda-alerts (email)、④並走 Slack 通知として `.github/workflows/fetcher-health-check.yml` (毎時 23 分 UTC) で `aws cloudwatch get-metric-statistics` ポーリング → `SLACK_WEBHOOK_URL` POST、⑤ci.yml に setup script + workflow ファイル存在の物理ガード追加。本番設置済 (alarm state INSUFFICIENT_DATA、deploy 後に正常化)。コスト: CloudWatch Alarm $0.10/月 のみ。**Verified-Effect (2026-04-30 23:01 JST)**: alarm StateValue=OK / FetcherSavedArticles 直近2h datapoints=2 (Sum=30, 28) / `[FETCHER_HEALTH]` 構造化ログ emit 確認 (saved_articles=30/28, new_topics=15/12)。3 系統すべて健全。 | projects/P003-news-timeline/lambda/fetcher/handler.py, scripts/setup_fetcher_alarm.sh, .github/workflows/fetcher-health-check.yml, .github/workflows/ci.yml | 2026-04-30 |
| ~~T2026-0430-I~~ | ~~🟡 中~~ | ~~ルール物理化~~ | ~~**CLAUDE.md に Monitor 禁止 / CI 待ち即クローズ ルール追記** PR #60~~ → **2026-04-30 完了 (commit 74ef7670 merged)** | CLAUDE.md | 2026-04-30 |
| ~~T2026-0430-J~~ | ~~🔴 高~~ | ~~AI品質~~ | ~~**keyPoint 短文率 77.7% (87/112) の根本原因修正 — fetcher_trigger backfill 末尾追加 bug**~~ → **2026-05-01 完了 (PR #61 merged, commit 4db6189b)** — rescue を pending 先頭挿入 (`rescue_added + pending`) で 30 分ごと 2 件確実消化。tests 7 ケース rewrite + 全 98 pass。効果検証は scheduled task (05/01 05:30 JST processor 後) に渡し session close。 | projects/P003-news-timeline/lambda/processor/handler.py, projects/P003-news-timeline/tests/test_handler_fetcher_backfill.py | 2026-04-30 |
| ~~T2026-0430-E~~ | ~~🟢 観測~~ | ~~運用~~ | ~~**PR #46 後の記事大量流入に備えた dedup / クラスタリング事前確認 — 問題なし**~~ → 2026-04-30 検査完了。追加対応なし。残微小リスクは緊急性低。 | (観測のみ) | 2026-04-30 |
| ~~T2026-0430-L~~ | ~~🔴 高~~ | ~~AI品質~~ | ~~**fresh24h 25.4% → 60%+ への構造的引き上げ (NFKC + Jaccard マージ)**~~ → **2026-05-01 完了 (PR #66 merged, commit b347ab83)** — `_title_dedup_key` に `unicodedata.normalize('NFKC', ...)` 追加 + `_resolve_tid_collisions_by_title` に Jaccard 類似度判定 (threshold=0.35、active/cooling 14日 cutoff 維持) 追加。boundary test 拡張済 (test_title_dedup_guard)。Verified-Effect: 24h 後の fresh_rate ≥ 50% 確認は scheduled task に委譲。 | projects/P003-news-timeline/lambda/fetcher/handler.py, projects/P003-news-timeline/lambda/fetcher/cluster_utils.py, tests/test_title_dedup_guard.py | 2026-04-30 |
| ~~T2026-0501-SLI-AGE~~ | ~~🟡 中~~ | ~~観測~~ | ~~**age decay アラート: 2026-05-01 (stale48h 39.0% > 30% 閾値超過)**~~ → **2026-05-01 根本原因対応 landing (PR #94)** — `compute_lifecycle_status` が 48h〜7日を velocity 問わず cooling に固定していたため 72h+ 無更新 85件が topics.json に滞留。修正: 72h 超 + velocity_decayed=0 → archived (T2026-0501-F2 PR #94)。handler.py の lifecycle 再計算 (memory only) も追加。効果検証は次回 p003-sli-morning-check に委譲。 | (T2026-0501-F2 で landing) | 2026-05-01 |
| ~~T2026-0501-SLI-KP~~ | ~~🟡 中~~ | ~~AI品質~~ | ~~**keyPoint 充填率低下アラート: 2026-05-01 (topics.json 38.6% < 50% 閾値・目標 70%)**~~ → **2026-05-01 09:35 JST 根本原因対応 landing (PR #73 merged)** — `_retry_short_keypoint` の Tool Use schema が `minLength: 0` で物理ガード不在 → retry でも 10〜30 字短文が返り SHORT_FALLBACK で永続化される構造的バグを特定。`minLength: 60` (T2026-0501-D) に物理ガード化 + description から軟化文言除去 + lessons-learned 横展開チェックリスト追記。テスト 35 (test_keypoint_retry) + 282 全体 pass。効果検証は scheduled task `p003-sli-morning-check` (毎朝 08:03 JST) に委譲、本行は landing 確認後に消し込む。 | projects/P003-news-timeline/lambda/processor/proc_ai.py, tests/test_keypoint_retry.py, docs/lessons-learned.md | 2026-05-01 |
| ~~T2026-0501-D~~ | ~~✅ 完了~~ | ~~AI品質~~ | ~~**keyPoint retry schema を minLength=60 で物理ガード化**~~ → **2026-05-01 PR #73 merged** — `_KEYPOINT_RETRY_MIN_CHARS=60` 定数導入 + retry schema `minLength: 60` 物理ガード。Verified-Effect は scheduled task `p003-sli-morning-check` に委譲。 | projects/P003-news-timeline/lambda/processor/proc_ai.py, tests/test_keypoint_retry.py, docs/lessons-learned.md | 2026-05-01 |
| ~~T2026-0430-REV~~ | ~~🟡 中~~ | ~~収益~~ | ~~**収益計測インフラ — 品質SLI × 収益の週次相関基盤**~~ → **2026-05-01 PR 提出・3ファイル実装済** — `scripts/revenue_check.sh` + `docs/revenue-log.md` + `.github/workflows/revenue-sli.yml` (月曜 07:00 JST cron、8日以上更新なし Slack 警告)。なぜなぜ分析 + 物理対策 (session_bootstrap.sh WORKING.md リマインダー + CLAUDE.md Dispatch 手順明示) も同時 landing。 | scripts/revenue_check.sh, docs/revenue-log.md, .github/workflows/revenue-sli.yml | 2026-04-30 |
| ~~T2026-0501-F~~ | ~~🔄 PR提出済~~ | ~~AI品質+UX~~ | ~~**海外ニュース 国際/政治 誤分類修正 + AI 出力 人名略称ガード**~~ → **2026-05-01 PR #75 merged** — `GENRE_KEYWORDS['国際']` を ASEAN/南西アジア/中東/アフリカ/中南米/欧州/海外要人で網羅 (~80語) + `_WORD_RULES` に「人名初出時は肩書き+正式名称必須」追加。境界値テスト 8 ケース新設 + 全290テスト pass。Verified-Effect は次回 processor 実行で観測。 | projects/P003-news-timeline/lambda/fetcher/config.py, projects/P003-news-timeline/lambda/fetcher/text_utils.py, projects/P003-news-timeline/lambda/processor/proc_ai.py, projects/P003-news-timeline/tests/test_genre_classification.py, docs/lessons-learned.md | 2026-05-01 |
| ~~T2026-0501-TS~~ | ~~🔴 高~~ | ~~バグ修正~~ | ~~**detail.js timestamp フォーマット統一 + Unix秒混入 SLI**~~ → **2026-05-01 PR #77 merged** — `frontend/js/timestamp.js` 新設 (`toMs(v)` 正規化 + `_warnBadTs`) + detail.js 全 `new Date(timestamp系)` 置換 + boundary test 40 ケース + `scripts/sli_timestamp_check.sh` + `.github/workflows/timestamp-sli.yml` (週次 cron)。 | projects/P003-news-timeline/frontend/detail.js, projects/P003-news-timeline/frontend/js/timestamp.js, projects/P003-news-timeline/frontend/topic.html, projects/P003-news-timeline/tests/unit/timestamp.test.js, projects/P003-news-timeline/package.json, scripts/sli_timestamp_check.sh, .github/workflows/timestamp-sli.yml | 2026-05-01 |
| ~~T2026-0501-OL2~~ | ~~🔴 高~~ | ~~AI品質~~ | ~~**outlook 影響先マッピング + 予想深度改修**~~ → **2026-05-01 PR #78 merged** — `_GENRE_IMPACT_TARGETS` 辞書による影響先注入 + 2次/3次効果強制 + `causalChain` 構造化フィールド追加。読者ペルソナ (PR #76) と組み合わせて outlook の三層化完了。次回 processor で観測。 | projects/P003-news-timeline/lambda/processor/proc_ai.py, projects/P003-news-timeline/tests/test_outlook_prompt.py | 2026-05-01 |
| ~~T192~~ | ~~高~~ | ~~**ジャンル戦略: 全ジャンル対応から1-2ジャンル集中に絞る検討**~~ ✅ 2026-05-01 分析完了 → `docs/genre-strategy.md`。要点: 経済 PV/topic=2.71（最強・AI生成率100%）、政治1.04、株・金融0.055（過剰生産）。推奨は第一案「経済+政治」3週間試行。POの意思決定待ち → T232 で施策実行 | `docs/genre-strategy.md` | 2026-04-27 |
| ~~T225~~ | ~~中~~ | ~~**tokushoho.html 残存** — Cowork 範囲外 (FUSE マウントで物理削除不可)。Code セッションで `git rm projects/P003-news-timeline/frontend/tokushoho.html` + CloudFront キャッシュパージ + Search Console URL 削除リクエスト + CI に「frontend に tokushoho.html が存在しないこと」チェック追加。~~ ✅ 2026-04-29 c9de70e5 で削除＋CI 二重ガード化済 / 2026-04-30 CloudFront invalidation `I6KD7X02A14S0DRSM9VF3MCYZO` (DIST_ID=E2Q21LM58UY0K8 /tokushoho.html) 発行完了 / Search Console URL 削除は PO 手動対応 | `frontend/tokushoho.html`（削除）, CI チェック | 2026-04-28 |
| ~~T2026-0428-AV~~ | ~~中~~ | ~~**トピックカードに注目スコアを表示する**~~ → **2026-05-01 確認: 既に実装済 (T2026-0501-A 数値表示 + T2026-0429-A 5段階縦バーメーター双方が `frontend/app.js:382, :469` でカードに landing 済)** | `frontend/app.js`, `frontend/style.css` | 2026-04-28 |
| ~~T2026-0501-D2~~ | ~~🟡 中~~ | ~~**UXスコア info_density 改善 (watchPoints metric再定義 + カード表示)**~~ → **2026-05-01 PR #91 提出済** — `scripts/ux_check.sh` info_density を velocityScore件数 → watchPoints≥30字カバレッジ% に再定義 (5%→0 / 70%→1)。`app.js` カードに watchPoints先頭55字スニペット表示追加、`style.css` `.card-watch-hint` スタイル追加。CI 待ち → green になり次第マージ。 | scripts/ux_check.sh, projects/P003-news-timeline/frontend/app.js, projects/P003-news-timeline/frontend/style.css | 2026-05-01 |
| ~~T2026-0501-I~~ | ~~🔴 高~~ | ~~UX/フェーズ3~~ | ~~**「総合」タブ廃止 → 「すべて」タブ化**~~ → **2026-05-01 実機確認で完了** — `app.js:804` に `g==='総合'?'すべて':g` 実装済。Coworkブラウザで「すべて」タブ表示を確認 (flotopic.com Chrome MCP)。 | `frontend/app.js` (実装済) | 2026-05-01 |
| ~~T2026-0501-J~~ | ~~🟡 中~~ | ~~UX/フェーズ3~~ | ~~**関連トピックリンク密度強化**~~ → **2026-05-01 実機確認で完了** — flotopic.com トピック詳細ページで「🔗 この話に繋がる別の話」セクションが複数件表示されることを Coworkブラウザ確認済み。 | (実装済) | 2026-05-01 |
| ~~T2026-0430-UX~~ | 中 | ~~**ユーザー体験ベースのUI/UX検証仕組み化** — 現在は SLI 数値（keyPoint 充填率・perspectives 等）のみ評価しているが、「実際にユーザーが使いやすいか」は数値だけでは測れない。①モバイル（375px）でのタップ操作・スクロール・情報読み取りのしやすさを定期スクリーンショット＋目視評価、②トピック読了後の次導線（関連トピック・catchup）がユーザーに見えているか確認、③ABテスト的に「新機能実装前後のファーストビュー変化」を記録するルールを追加。実装案: `scripts/ux_check.sh` がモバイルUAで本番URL 5ページを curl + html2text して情報密度を定量評価 → weekly report として Slack 通知。 | scripts/ux_check.sh 新設, .github/workflows/ux-check.yml 新設 | 2026-04-30 |~~ → **DONE 2026-05-01** scripts/ux_check.sh + ux-check.yml landing。baseline UXスコア 2.31/5 (kp_density 0.42 / response 1.0 が高得点 / info_density 0.11 / child_density 0.15 / continuation 0.10 が伸びしろ)。週次月曜 07:30 JST cron で docs/ux-scores.md に append、Slack に前週比通知。|
| ~~T260~~ | ~~中~~ | ~~**個別 topic JSON の `data['meta']` で aiGenerated=False の topic も生成されている** — `https://flotopic.com/api/topic/8f81be6586cbea09.json` は `aiGenerated=False` で meta が `{aiGenerated, topicId}` の 2 フィールドだけ。空の個別 JSON が量産。`update_topic_s3_file` で `aiGenerated=False` かつ generatedTitle 等が無いトピックは個別 JSON 生成をスキップ。~~ → **2026-04-30 22:15 JST 完了** — `proc_storage.update_topic_s3_file` に skip 判定 (merge 後 meta が `aiGenerated=False` かつ `generatedTitle` 不在/空白) を追加し S3 PUT をスキップ + `[SKIP_EMPTY_JSON] tid=... reason=aiGenerated=False` ログ。`tests/test_skip_empty_topic_json.py` 9 ケース新設 + 全 271 ケース pass。本番 `aiGenerated=False` のアクティブトピックは scan 結果 数十件規模 (空 JSON 撲滅見積)。DynamoDB レコードは未変更なので将来 AI 生成時には正常に書かれる。 | `lambda/processor/proc_storage.py`, `tests/test_skip_empty_topic_json.py` | 2026-04-28 |
| ~~T258~~ | ~~中~~ | ~~**「発端」storyPhase 50% 偏り (本番) — T219 修正前の旧データが残る** — 本番 topics.json で storyPhase 分布 = 拡散 23 / 発端 57 / ピーク 9 / 現在地 4 / null 21。T219 prompt 修正で「記事3件以上で発端禁止」を入れたが、aiGenerated=True 旧 topic は skip されるため反映されない。完了判定: T255 修正＋forceRegenerateAll 1-2 回後、storyPhase 分布が正規化。~~ ✅ 2026-05-01 p003-sonnet 実測: ac>=3 での storyPhase=発端 = 0.0% (0/111) — 22:11 JST 確認。正規化完了。 | (T255 で連動解消) | 2026-04-28 |
| ~~T262~~ | ~~中~~ | ~~**プライバシーポリシー・利用規約が `noindex` だが SEO 上の表示・検索性は OK か再確認** — privacy.html / terms.html は `noindex` 設定なし (現在は indexable)。Search Console で `site:flotopic.com` 検索し、privacy/terms が結果に出るか確認。~~ ✅ 2026-05-01 TASKS.md 自体に「noindex 設定なし (現在は indexable)」と記録済。調査不要 = indexable 確認済。SEO 上問題なし。 | Search Console 確認 | 2026-04-28 |
| ~~T264~~ | ~~中~~ | ~~**`.claude/worktrees/` に 6 個の stale 作業ツリーが残存** — `awesome-varahamihira-c01b2e` `happy-khorana-4e3a6c` `naughty-saha-ba5901` `quirky-cohen-c1efbd` `serene-hermann-993255` `vigilant-fermi-4e0a09`。WORKING.md TTL 8h ルールはメインの WORKING.md にしか適用されていない。起動チェック script に worktree クリーンアップ候補一覧表示 + 物理スクリプト化 + `.gitignore` 追加。~~ ✅ 2026-04-30 PR #56 で `scripts/cleanup_stale_worktrees.sh` 新規 + `session_bootstrap.sh` から `--dry-run` で呼び出し。実 cleanup 39 件削除 / 3 件 uncommitted skip / 81 件 active 維持。 | `CLAUDE.md` 起動チェック, `scripts/cleanup_stale_worktrees.sh` 新規 | 2026-04-28 |
| ~~T2026-0428-K~~ | ~~🟡 中~~ | ~~**環境スクリプトの dry-run CI 化** — 2026-04-28 04:15 schedule-task で session_bootstrap.sh / triage_tasks.py に session-id ハードコードと UTC を JST と誤ラベルする bug が同時露見。lessons-learned「環境スクリプトに session ID hardcode」記録。修正は同 commit で landing 済だが、再発防止として `scripts/session_bootstrap.sh --dry-run` を GH Actions 日次実行 → REPO 検出 / JST 表示 / WORKING.md 未来日付 stale 検出ロジックを物理 test。Claude が次セッションで気付くループを CI で前倒しに切り替える。~~ ✅ 2026-04-30 PR #57 で `--dry-run` 検証 block 追加 (REPO/JST `+09:00`/WORKING.md/git status/8h stale カウント) + `[DRY-RUN OK]` 終端マーカー + `env-scripts-dryrun.yml` cron 0 21 (JST 06:00) + Slack 通知。 | `.github/workflows/env-scripts-dryrun.yml` 新規, `scripts/session_bootstrap.sh` (`--dry-run` 引数追加) | 2026-04-28 |
| ~~T2026-0428-Q~~ | ~~中~~ | ~~**success-but-empty 抽象パターンの他コンポーネント横展開スキャン** — keyPoint 充填率 11.5% を「aiGenerated フラグだけ見る SLI」が素通りした問題の横展開。要監視: ① fetcher articleCount=0 cycle、② processor processed=0 cycle、③ bluesky_agent post 失敗、④ SES bounce、⑤ CloudFront 5xx、⑥ CI green-but-skipped、⑦ topic 個別 JSON の meta=2フィールドだけパターン (T260)。~~ ✅ 2026-04-30 `scripts/scan_success_but_empty.py` を 7 観点 (③ keyPoint / ④ perspectives / ⑤ freshness 24h / ⑥ workflows skip / ⑦ aiGenerated=False placeholder) に拡張 + `--ci-status` モード追加。①② は CloudWatch Logs 連携が大きいため TODO で残し、既存 `fetcher-health-check.yml` / `sli-keypoint-fill-rate.yml` で等価観測中。`.github/workflows/success-but-empty-scan.yml` 週次 (月 06:00 JST) で実行 + Slack 通知。初回スキャン結果: keyPoint short=77.68% / perspectives short=55.36% / fresh24h=18.75% / placeholder=0 (T260 効果) → 別タスクで根本対応。 | `scripts/scan_success_but_empty.py` 拡張, `.github/workflows/success-but-empty-scan.yml` 新規 | 2026-04-28 |

</details>


### 自動 triage: 2026-05-02 に TASKS.md から移動した取消線済みタスク

<details><summary>取消線で完了マークされた行（TASKS.md 由来）</summary>

| ~~T2026-0502-A~~ | ~~🟠 高~~ | ~~**freshness-check + fetcher-health-check が false-failure**~~ → **2026-05-02 09:50 JST 完了 (PR #122 merged, commit 253a67bb)** — 根本原因: 両 workflow に `actions/checkout@v4` step が無く、scripts/*.py を呼ぶ前に runner にリポジトリが存在しなかった。両 yml の steps 先頭に checkout 追加。**Verified-Effect**: post-fix で freshness-check #21/#22, fetcher-health-check #9/#10 = いずれも 2 連続 success（直前 5 件は連続 failure）。lessons-learned.md L1432〜 に Why1〜Why5 + 横展開チェックリスト追記済。 | (実装完了) | 2026-05-02 |

</details>


### 自動 triage: 2026-05-02 に TASKS.md から移動した取消線済みタスク

<details><summary>取消線で完了マークされた行（TASKS.md 由来）</summary>

| ~~T2026-0502-D~~ | ~~🟠 高~~ | ~~**auto-merge stuck watcher**~~ → **2026-05-02 09:55 JST 完了 (PR #137 merged)** — `.github/workflows/automerge-stuck-watcher.yml` + `scripts/automerge_stuck_watcher.py` + `tests/test_automerge_stuck_watcher.py` (16 ケース pass) で 10 分毎 cron + workflow_dispatch。**Verified-Effect (2026-05-02 09:58 JST)**: 手動 dispatch で run #1 success (空振り = 正常)。schedule から自動発火は次の :*0 / :*10 で landing。 | (実装完了) | 2026-05-02 |
| ~~T2026-0502-Q~~ | ~~🔴 最優先~~ | ~~**Lambda デプロイ workflow が連続失敗 → 直近修正 PR が本番未反映**~~ → **2026-05-02 10:25 JST 完了 (PR #141 merged + deploy run #372 success)** — Cowork が `$GITHUB_WORKSPACE/scripts/ci_lambda_merge_env.py` の絶対パス参照に修正。**Verified-Effect (2026-05-02 10:23 JST)**: 手動 dispatch で run #372 = success / fetcher step ✓ + 全 11 Lambda (fetcher/processor/comments/analytics/auth/favorites/lifecycle/cf-analytics/api/contact/bluesky) deploy 成功。直前 10 連続 failure → 解消。これにより本日の PR #114 (T2026-0502-G fetcher 恒久対処) / PR #118 (T2026-0501-M 重複検出マージ) / PR #125 (T2026-0502-B lifecycle SK fix) が **初めて本番反映**。 | (実装完了) | 2026-05-02 |
| ~~T2026-0502-H~~ | ~~🔴 最優先~~ | ~~**deploy-lambdas.yml の `ci_lambda_merge_env.py` パス解決バグ修正**~~ → **2026-05-02 10:25 JST 完了 (PR #141 merged)** — Cowork 推奨案 (a) `$GITHUB_WORKSPACE/scripts/ci_lambda_merge_env.py` の絶対パス参照に修正。Verified-Effect: 手動 dispatch run #372 success（11 Lambda 全 deploy）。**注**: 同 ID T2026-0502-H が別 dispatch session で「shared-docs conflict 物理ガード」にも採番されており PR #138 で landing 済（HISTORY.md 参照）。ID 重複は Cowork ↔ 別 dispatch 間の調整不足が原因。 | (実装完了) | 2026-05-02 |

</details>


### 自動 triage: 2026-05-02 に TASKS.md から移動した取消線済みタスク

<details><summary>取消線で完了マークされた行（TASKS.md 由来）</summary>

| ~~T2026-0502-S~~ | ~~🟡 中~~ | ~~**flotopic-bluesky governance check が起動以来 0 回成功**~~ → **2026-05-02 10:32 JST 解決 (Cowork が AWS API 直接実行)** — DynamoDB テーブル `ai-company-agent-status` を `aws dynamodb create-table --billing-mode PAY_PER_REQUEST --partition-key agent_name` で作成 (TableArn: `arn:aws:dynamodb:ap-northeast-1:946554699567:table/ai-company-agent-status`)。IAM 権限は `p003-lambda-role` の `flotopic-least-privilege` policy に該当テーブルの `GetItem/PutItem/...` が**既に付与済み**を確認 → IAM 修正不要。Verified-Effect: 次回 flotopic-bluesky 起動 (rate(30 min)) で `[governance] ガバナンスチェック失敗` ログが消え `[governance] xxx: ステータス未登録 → active扱いで続行` に切り替わる想定。観察は `p003-haiku` (毎朝 7:08 JST) に委ねて即 close。 | (実装完了) | 2026-05-02 |

</details>


### 自動 triage: 2026-05-02 に TASKS.md から移動した取消線済みタスク

<details><summary>取消線で完了マークされた行（TASKS.md 由来）</summary>

| ~~T2026-0502-C~~ | ~~🟡 中~~ | ~~**Bluesky 投稿系の恒久リファクタ** — T2026-0502-L で恒久対処化: debut を完全廃止せず `BLUESKY_POSTING_CONFIG` 集約 + `_check_rate_limit()` 単一エントリ + 24h cap 二重ガード + テスト14件で再発防止。EventBridge 構成は維持（rate 30min cron + 単発 morning cron）、debut は config で `enabled=False` 維持しつつ再有効化路を残した。~~ | ~~`scripts/bluesky_agent.py`, `projects/P003-news-timeline/tests/`, `docs/lessons-learned.md`~~ | ~~2026-05-02~~ |
| ~~T2026-0502-I~~ | ~~🟢 低 (Code セッション dispatch 必要)~~ | ~~**API Gateway 廃止 route `POST /track` 削除**~~ → **2026-05-02 10:53 JST 完了 (Code セッション)** — `aws apigatewayv2 delete-route --route-id t8bq1kq` + `delete-integration --integration-id c8yyf01` 実行。`get-routes` で `POST /track` が `[]` 確認 (消去実証)。`deploy-lambdas.yml` および repo 全体に該当 route の参照なし確認済。Verified-Effect: 11:52 JST の `t2026-0502-t-5xx-analysis` schedule task が実行する access logs 解析で「routeKey=POST /track の 5xx は 0 件」が確認できる想定 (削除前 baseline は 5xx 率 17.6% (5/2 朝) のうち未推定割合)。 | (実装完了) | 2026-05-02 |
| ~~T2026-0502-L~~ | ~~🟡 中~~ | ~~**Bluesky 投稿頻度 恒久対処（debut 設計欠陥修正・SSoT 化）**~~ → **2026-05-02 11:00〜11:35 JST 完了 (PR #150 + #155 merged)** — 5/1 debut 48件/日投稿事故 → `BLUESKY_POSTING_CONFIG` SSoT 化 + `_check_rate_limit()` 単一エントリ + 3重ガード (enabled/cooldown/24h cap) + テスト14件 + lessons-learned 追記。PO audit で発見した dead config (weekly/monthly entry・legacy alias) を PR #155 で削除。post_debut の TTL クリーンアップを rate-limit より先に実行する regression fix を当 PR で同梱。S3 `bluesky/pending/` 累積 85件のマーカーを `aws s3 rm --recursive` で整理済。Verified-Effect: 5/2 01:22 UTC 応急処置デプロイ後 56分で投稿1件のみ・実機で停止確認済 / 2026-05-03 朝に schedule task `p003-haiku` が日次合計 ≤4件 を観測予定。**Phase-Impact: 1 運用安定化** | `scripts/bluesky_agent.py`, `projects/P003-news-timeline/tests/test_bluesky_rate_limit.py`, `docs/lessons-learned.md`, S3 cleanup | 2026-05-02 |

</details>


### 自動 triage: 2026-05-02 に TASKS.md から移動した取消線済みタスク

<details><summary>取消線で完了マークされた行（TASKS.md 由来）</summary>

| ~~T2026-0502-J~~ | ~~🔴 高~~ | ~~**fetcher → processor 即時トリガー削除 (コスト 67% 減)**~~ → **2026-05-02 11:06 JST 完了 (PR #146 merged, commit 53d2ddd2)** — Code セッションが `lambda/fetcher/handler.py:1498-1517` の `_lambda.invoke('p003-processor', ...)` ブロック削除 + 削除理由コメント追加 + 横展開 grep (cross-Lambda invoke 残存=0) + lessons-learned「Lambda 間 invoke のコスト盲点」Why1〜5 + 仕組み的対策 4 件追記。Cowork が CI fail (ソフト言語「確認する」混入) を branch 直接 commit で fix → API direct merge。**未確認**: deploy-lambdas.yml が PR #146 merge sha (53d2ddd2) で **auto-fire しなかった** (path filter `projects/P003-news-timeline/lambda/**` に該当するはずなのに workflow runs API で 0 件)。next push or workflow_dispatch で deploy 必要。Verified-Effect (Eval-Due 2026-05-03 09:00 JST): deploy 反映後 24h で API call <60 calls/24h まで減少（-63% 想定）。 | (実装完了・deploy 観察待ち) | 2026-05-02 |

</details>

| T2026-0502-SESSION-END-HOOK-AUDIT | 🔴 高 | **Stop hook による auto-sync: session end main 直 commit 撤廃** → **2026-05-02 JST 完了** — `~/.claude/settings.json` の `Stop` hook（全セッション終了時に `git add -A && git commit -m "auto-sync: session end ..." && git push main` を実行）を削除。全期間 476+ 件の汚染コミット発生を停止。root cause: セッション間データ保全の「安全装置」として設置されたが PR フロー義務化後も削除されず、pre-push hook の `|| true` 迂回で push 失敗が無音で蓄積。代替: `session_bootstrap.sh` の起動時 `chore: bootstrap sync` が同機能を担う。lessons-learned.md に T2026-0502-SESSION-END-HOOK-AUDIT セクション追記。 | 完了 | 2026-05-02 |


| ~~T2026-0502-O~~ | ~~🟡 高~~ | ~~**AWS IAM Deny ポリシー追加 (思想ルールの物理化)**~~ → **2026-05-02 13:30 JST 完了** | IAM Console で Cowork IAM ユーザー (`arn:aws:iam::946554699567:user/Claude`) にインラインポリシー `CoworkDenyDestructive` を適用。Deny actions: `lambda:UpdateFunctionCode` / `lambda:DeleteFunction` / `dynamodb:DeleteTable` / `dynamodb:DeleteBackup` / `s3:DeleteBucket` / `ec2:TerminateInstances` / `rds:DeleteDBInstance` / `iam:DeletePolicy` / `iam:CreateAccessKey`。Verified-Effect: `aws iam create-access-key --user-name Claude` で `An error occurred (AccessDenied) when calling the CreateAccessKey operation: User: arn:aws:iam::946554699567:user/Claude is not authorized to perform: iam:CreateAccessKey on resource: user Claude with an explicit deny in an identity-based policy` 確認 (2026-05-02 13:30 JST)。CLAUDE.md「Cowork は不可逆操作禁止」思想ルールが IAM 物理ルールに昇格。 | 完了 | 2026-05-02 |

| ~~T2026-0502-SEC1~~ | ~~🔴 緊急~~ | ~~**Anthropic API Key + Slack Webhook ローテーション (チャット流出緊急対応)**~~ → **2026-05-02 13:30 JST 完了** | ①Anthropic Console で旧 Key (`sk-ant-api03-...`) revoke + 新 Key 発行 + GitHub Secrets `ANTHROPIC_API_KEY` 更新 ②Slack Workspace Apps → Incoming Webhooks で旧 Webhook 削除 + 新 Webhook 発行 + GitHub Secrets `SLACK_WEBHOOK` 更新 ③deploy-lambdas.yml run #378 (workflow_dispatch) で全 11 Lambda env (p003-processor / p003-fetcher / 他 9) に新 key/webhook 反映。Verified: 旧 key で API 401 想定 (PO 確認推奨)、新 key で fetcher/processor の継続動作 (CloudWatch Logs)。 | 完了 | 2026-05-02 |

| ~~T2026-0502-SEC2~~ | ~~🔴 緊急~~ | ~~**GitHub PAT + ローカル設定の平文除去**~~ → **2026-05-02 13:30 JST 完了** | `.git/config` から平文 `gho_...` token 除去 (`git remote set-url origin https://github.com/...` + `git config --global credential.helper osxkeychain` で Keychain 認証へ移行)、`.claude/settings.local.json` L21 の `Bash(GITHUB_TOKEN="ghp_..." SLACK_BOT_TOKEN="xoxb-..." SLACK_WEBHOOK="https://hooks.slack.com/..." bash deploy.sh)` allow エントリーを sed で削除 (CLAUDE.md「deploy.sh は直接実行しない」ルールと整合のため allow 自体不要)。Verified: `git remote -v` で token 無し URL、`grep -cE 'gh[ops]_\|sk-ant-\|xox[bp]-\|hooks\.slack\.com' settings.local.json` = 0、JSON 構文 OK。Personal Access Tokens 一覧は元々ゼロ件登録 (`.git/config` にあった `gho_...` は OAuth App user-to-server token で revoke すると Cowork 連携が切れる副作用大のため放置)。**副作用** (T2026-0502-SEC2-RECURRENCE): cowork_commit.py が 401 不能 → PR #206 で 5 経路 fallback + .git/config URL token 検出ガード + lessons-learned 追記で恒久対処済。 | 完了 | 2026-05-02 |


| ~~T2026-0502-U~~ | ~~🟡 中~~ | ~~**fetcher embedding 移行 (multilingual-e5-small ONNX qint8 → AI_MERGE_ENABLED=false 置換)**~~ → **2026-05-02 15:35 JST Phase 1 bench 失敗につき停止** — Phase 1 PoC bench を Mac で実施 (deepfile/multilingual-e5-small-onnx-qint8 ARM64・ONNX Runtime 1.20.1)。6 fixture で cosine 計測: same_event_geo_subset=0.949 ✓、same_event_paraphrase=0.961 ✓、same_event_continuing=0.913 ✗、different_subject_same_topic=0.966 ✗、different_event_same_org=0.900 ✗、borderline_score_match=0.913 ✓。**misses=3/6**。根本問題: `same_min=0.913 < diff_max=0.966` → 数学的に閾値帯で分離不可能。`prefix={'query:','passage:',''}` のいずれでも改善なし。**結論: multilingual-e5-small は短文日本語ニュース見出しの同一事件判定に不適** (cosine 分布が 0.9+ に圧縮されすぎる)。副産物: embedding_judge.py の `token_type_ids` 欠落バグ修正 (sentencepiece tokenizer がフィールドを出力しない場合にゼロ埋め補完)・unit test 8/8 PASS 確認。**次の選択肢**: voyage-3-lite API 評価 (200M tok 無料=約26ヶ月・$0.15/月の激安) or 現状維持 (AI_MERGE_ENABLED=false・false split 継続)。bench 結果は docs/p003-embedding-migration-research.md §9 に記録済。Verified-Effect: bench misses=3/6 確認・閾値調整不可 証明 (2026-05-02 15:35 JST) | docs/p003-embedding-migration-research.md §9, lambda/fetcher/embedding_judge.py (token_type_ids fix) | 2026-05-02 |


### 自動 triage: 2026-05-02 に TASKS.md から移動した取消線済みタスク

<details><summary>取消線で完了マークされた行（TASKS.md 由来）</summary>

| ~~T2026-0502-O~~ | ~~🟡 高~~ | ~~**AWS IAM Deny ポリシー追加 (思想ルールの物理化)**~~ → **2026-05-02 13:30 JST 完了** — IAM Console で Cowork ユーザーにインラインポリシー `CoworkDenyDestructive` 適用 (Deny: lambda:UpdateFunctionCode/lambda:DeleteFunction/dynamodb:DeleteTable/dynamodb:DeleteBackup/s3:DeleteBucket/ec2:TerminateInstances/rds:DeleteDBInstance/iam:DeletePolicy/iam:CreateAccessKey)。Verified-Effect: `aws iam create-access-key --user-name Claude` で `AccessDenied ... explicit deny in an identity-based policy` 確認。CLAUDE.md「Cowork は不可逆操作禁止」思想ルールが IAM 物理ルールに昇格。元の説明: ~~Cowork IAM ユーザー — Cowork IAM ユーザー (`arn:aws:iam::946554699567:user/Claude`) に以下 Deny を追加: `lambda:UpdateFunctionCode` `lambda:DeleteFunction` `dynamodb:DeleteTable` `dynamodb:DeleteBackup` `s3:DeleteBucket` `ec2:TerminateInstances` `rds:DeleteDBInstance` `iam:DeletePolicy` `iam:CreateAccessKey`。CLAUDE.md「思想ルール (Cowork は不可逆操作禁止)」を IAM 物理ルールに変換。完了条件: `aws lambda update-function-code` を Cowork から試して AccessDenied 確認。Verified-Effect: AccessDenied で reject されるログ。**PO 承認 + AWS Console 操作必要**（私が直接実行は危険）。policy 文書: `docs/rules/cowork-aws-policy.md` Section 4 | AWS IAM Console (Cowork ユーザー policy) | 2026-05-02 |
| ~~T2026-0502-W~~ | ~~🔴 高~~ | ~~deploy-lambdas.yml fetcher step 連続 failure~~ → **2026-05-02 14:21 JST 解消** — Lambda LastModified が 14:21 JST まで進んだことを get-function-configuration で確認。`AI_MERGE_ENABLED=false` env が維持されており PR #208 の kill switch コードが有効。fetcher haiku call=0 が code+env の二重 gate で恒久化。元説明: **deploy-lambdas.yml fetcher step 連続 failure 恒久対処 + T2026-0502-COST2 deploy 同期** — 2026-05-02 14:11 JST Cowork 確認: workflow_dispatch 後 5 秒以内に "fetcher Lambda をデプロイ" step が failure (step1-4 success・step5 即落ち)。AWS auth/checkout/Python は通っている。直近成功は 04:17 UTC PR #200 deploy。それ以降 PR #201/#205/#208 (kill switch) 全て deploy できず Lambda は古いコードで動作中。ただし**止血は env override で達成済**: `aws lambda update-function-configuration --function-name p003-fetcher --environment` で `ANTHROPIC_API_KEY` 削除 + `AI_MERGE_ENABLED=false` 追加 (2026-05-02 14:06 JST)。次の fetcher run (05:08 UTC) で `haiku_pairs_asked=0` 確認済 (filter-log-events で実測)。**Code セッションがやること**: ①`gh run view 25244482637 --log-failed` で実エラー取得 (Cowork sandbox proxy では Azure blob 403) ②zip/aws cli/Python のどこで落ちてるか特定 ③`scripts/ci_lambda_merge_env.py` を runner 上でローカル再現テスト ④fix PR を出して deploy 再試行 ⑤PR #208 (kill switch コード) が deploy で landing したことを確認 ⑥`deploy-lambdas.yml` の fetcher step が次回 deploy 時に env override (ANTHROPIC_API_KEY 削除) を上書きしないよう注意 (現状 `ci_lambda_merge_env.py` が secrets.ANTHROPIC_API_KEY を強制注入する → AI_MERGE_ENABLED=false が残れば AI コール 0 維持・もし将来 AI_MERGE 復活させるなら `AI_MERGE_ENABLED=true` を GH Secrets/workflow に追加 → deploy で反映)。**Phase-Impact: 1 運用安定** / **Eval-Due: 2026-05-04** | `.github/workflows/deploy-lambdas.yml`, `scripts/ci_lambda_merge_env.py` | 2026-05-02 |
| ~~T2026-0502-SEC1~~ | ~~🔴 緊急~~ | ~~**Anthropic API Key + Slack Webhook ローテーション**~~ → **2026-05-02 13:30 JST 完了** — ①Anthropic Console で旧 Key revoke + 新 Key 発行 + GitHub Secrets `ANTHROPIC_API_KEY` 更新 ②Slack Workspace Apps の Incoming Webhooks で旧 Webhook 削除 + 新 Webhook 発行 + GitHub Secrets `SLACK_WEBHOOK` 更新 ③deploy-lambdas.yml run #378 (workflow_dispatch) で全 11 Lambda env に新 key/webhook 反映。元の説明: ~~2026-05-02 09:50 JST — 2026-05-02 09:50 JST: 網羅調査中に Cowork が `aws lambda get-function-configuration` 経由で `p003-processor` の env から ANTHROPIC_API_KEY (`sk-ant-api03-...`) を平文取得 → Cowork チャット応答に値が表示された。同様に `p003-fetcher` env から SLACK_WEBHOOK URL (`https://hooks.slack.com/services/...`) も。チャット履歴に残ったため両方 rotate 必須。手順: ①Anthropic Console → API Keys → 該当キー Revoke → 新規発行 ②GitHub Secrets `ANTHROPIC_API_KEY` 更新 ③deploy workflow を T2026-0502-H 修正後に手動 run → Lambda env 全関数に新 key 反映 ④Slack workspace → Apps → Webhook URL revoke → 新規発行 ⑤同様に Lambda env / GitHub Secret 更新。完了条件: 旧 key で API 401 / 旧 webhook で post 不可・新 key で fetcher/processor 動作確認。**Phase-Impact: セキュリティ最優先 (フェーズ無関係)** / **Eval-Due: 2026-05-02 (即日)** / **依存**: T2026-0502-H 先 (deploy workflow が直らないと Lambda env 反映が出来ない・PO が手動更新するなら独立) | Anthropic Console, Slack Workspace, GitHub Secrets, Lambda env (全関数) | 2026-05-02 |
| ~~T2026-0502-SEC4~~ | ~~🔴 緊急~~ | ~~**Notion integration token のローテーション**~~ → **2026-05-02 PM 完了** — PO が Notion Settings で旧 `ntn_3865...` Revoke + 新 token 発行 + GitHub Secrets `NOTION_API_KEY` 更新済。影響範囲: ①GitHub Actions `notion-sync.yml` / `notion-revenue-daily.yml` が secrets 経由で読む (本番経路) → 新 token で稼働 ②`fetch_notion.py` (PO ローカル・gitignore 済) は新 token を `export NOTION_TOKEN=...` で受ける形 (PR #200 で書換済)。Anthropic 部は SEC1 と同 key で完了済。完了条件達成: 旧 Notion token で API 401。**T2026-0502-SEC-AUDIT 緊急 SEC タスク全 4 件 (SEC1/SEC2/SEC3 rotate/SEC4) クローズ**。元の説明: ローカル平文ファイル内 secrets のローテーション (T2026-0502-SEC-AUDIT) | (完了済) | 2026-05-02 |
| ~~T2026-0502-SEC2~~ | ~~🔴 緊急~~ | ~~**GitHub PAT ローテーション + ローカル設定からの平文除去**~~ → **2026-05-02 13:30 JST 完了** — `.git/config` から平文 token 除去 (Keychain 認証 `osxkeychain` へ移行)、`.claude/settings.local.json` L21 の `Bash(GITHUB_TOKEN=... SLACK_BOT_TOKEN=... SLACK_WEBHOOK=... bash deploy.sh)` allow エントリーを削除 (CLAUDE.md「deploy.sh は直接実行しない」ルールと整合)。Verified: `git remote -v` で token 無し URL のみ表示、`grep -cE 'gh[ops]_|sk-ant-|xox[bp]-|hooks\.slack\.com' settings.local.json` = 0。Personal Access Token は元々ゼロ件登録 (`gho_...` は OAuth App user-to-server token で revoke すると Cowork 連携が切れる副作用大のため放置)。**副作用 (T2026-0502-SEC2-RECURRENCE)**: cowork_commit.py が 401 になり PR #206 で多経路化 + 物理ガード追加で恒久対処。元の説明: ~~2026-05-02 11:35 JST — 2026-05-02 11:35 JST T2026-0502-M 調査中に Cowork が以下 2 箇所で平文の GitHub PAT を観測: ①`.git/config` の `remote.origin.url = https://nuuuuuuts643:gho_...@github.com/...` ②`.claude/settings.local.json` 内の Bash allow エントリーに `GITHUB_TOKEN="ghp_..."` `SLACK_BOT_TOKEN="xoxb-..."` `SLACK_WEBHOOK="..."` がコマンド allowlist として展開されたまま保存。`.claude/settings.local.json` は gitignore 済 (L5) で git track 外なので push 流出はしていないが、Cowork チャット履歴・スクリーン共有・session_info MCP 経由で第三者に見える可能性。手順: ①GitHub Settings → Personal access tokens → 該当 token Revoke → 新規発行 (scope は最小化: `repo` + `workflow` のみ) ②`.claude/settings.local.json` の該当 allow エントリーを `Bash(GITHUB_TOKEN=$GITHUB_TOKEN bash deploy.sh)` のように env 変数参照に置換 ③`.git/config` の `remote.origin.url` を `https://github.com/nuuuuuuts643/AI-Company.git` に書き換え + GIT_ASKPASS / `~/.netrc` / `gh auth login` で別途認証 ④Slack Bot Token / Webhook も再発行 (T2026-0502-SEC1 と並行)。完了条件: 旧 PAT で API 401 / `.claude/settings.local.json` と `.git/config` を grep して `gho_` `ghp_` `xoxb-` `https://hooks.slack.com/` が 0 件。**Phase-Impact: セキュリティ最優先 (フェーズ無関係)** / **Eval-Due: 2026-05-02 (即日)** / **依存**: なし (T2026-0502-SEC1 と並行可) | GitHub Settings, `.claude/settings.local.json`, `.git/config` (ローカル) | 2026-05-02 |

</details>


### 自動 triage: 2026-05-02 に TASKS.md から移動した取消線済みタスク

<details><summary>取消線で完了マークされた行（TASKS.md 由来）</summary>

| ~~T2026-0502-O~~ | ~~🟡 高~~ | ~~**AWS IAM Deny ポリシー追加 (思想ルールの物理化)**~~ → **2026-05-02 13:30 JST 完了** — IAM Console で Cowork ユーザーにインラインポリシー `CoworkDenyDestructive` 適用 (Deny: lambda:UpdateFunctionCode/lambda:DeleteFunction/dynamodb:DeleteTable/dynamodb:DeleteBackup/s3:DeleteBucket/ec2:TerminateInstances/rds:DeleteDBInstance/iam:DeletePolicy/iam:CreateAccessKey)。Verified-Effect: `aws iam create-access-key --user-name Claude` で `AccessDenied ... explicit deny in an identity-based policy` 確認。CLAUDE.md「Cowork は不可逆操作禁止」思想ルールが IAM 物理ルールに昇格。元の説明: ~~Cowork IAM ユーザー — Cowork IAM ユーザー (`arn:aws:iam::946554699567:user/Claude`) に以下 Deny を追加: `lambda:UpdateFunctionCode` `lambda:DeleteFunction` `dynamodb:DeleteTable` `dynamodb:DeleteBackup` `s3:DeleteBucket` `ec2:TerminateInstances` `rds:DeleteDBInstance` `iam:DeletePolicy` `iam:CreateAccessKey`。CLAUDE.md「思想ルール (Cowork は不可逆操作禁止)」を IAM 物理ルールに変換。完了条件: `aws lambda update-function-code` を Cowork から試して AccessDenied 確認。Verified-Effect: AccessDenied で reject されるログ。**PO 承認 + AWS Console 操作必要**（私が直接実行は危険）。policy 文書: `docs/rules/cowork-aws-policy.md` Section 4 | AWS IAM Console (Cowork ユーザー policy) | 2026-05-02 |
| ~~T2026-0502-W~~ | ~~🔴 高~~ | ~~deploy-lambdas.yml fetcher step 連続 failure~~ → **2026-05-02 14:21 JST 解消** — Lambda LastModified が 14:21 JST まで進んだことを get-function-configuration で確認。`AI_MERGE_ENABLED=false` env が維持されており PR #208 の kill switch コードが有効。fetcher haiku call=0 が code+env の二重 gate で恒久化。元説明: **deploy-lambdas.yml fetcher step 連続 failure 恒久対処 + T2026-0502-COST2 deploy 同期** — 2026-05-02 14:11 JST Cowork 確認: workflow_dispatch 後 5 秒以内に "fetcher Lambda をデプロイ" step が failure (step1-4 success・step5 即落ち)。AWS auth/checkout/Python は通っている。直近成功は 04:17 UTC PR #200 deploy。それ以降 PR #201/#205/#208 (kill switch) 全て deploy できず Lambda は古いコードで動作中。ただし**止血は env override で達成済**: `aws lambda update-function-configuration --function-name p003-fetcher --environment` で `ANTHROPIC_API_KEY` 削除 + `AI_MERGE_ENABLED=false` 追加 (2026-05-02 14:06 JST)。次の fetcher run (05:08 UTC) で `haiku_pairs_asked=0` 確認済 (filter-log-events で実測)。**Code セッションがやること**: ①`gh run view 25244482637 --log-failed` で実エラー取得 (Cowork sandbox proxy では Azure blob 403) ②zip/aws cli/Python のどこで落ちてるか特定 ③`scripts/ci_lambda_merge_env.py` を runner 上でローカル再現テスト ④fix PR を出して deploy 再試行 ⑤PR #208 (kill switch コード) が deploy で landing したことを確認 ⑥`deploy-lambdas.yml` の fetcher step が次回 deploy 時に env override (ANTHROPIC_API_KEY 削除) を上書きしないよう注意 (現状 `ci_lambda_merge_env.py` が secrets.ANTHROPIC_API_KEY を強制注入する → AI_MERGE_ENABLED=false が残れば AI コール 0 維持・もし将来 AI_MERGE 復活させるなら `AI_MERGE_ENABLED=true` を GH Secrets/workflow に追加 → deploy で反映)。**Phase-Impact: 1 運用安定** / **Eval-Due: 2026-05-04** | `.github/workflows/deploy-lambdas.yml`, `scripts/ci_lambda_merge_env.py` | 2026-05-02 |
| ~~T2026-0502-SEC1~~ | ~~🔴 緊急~~ | ~~**Anthropic API Key + Slack Webhook ローテーション**~~ → **2026-05-02 13:30 JST 完了** — ①Anthropic Console で旧 Key revoke + 新 Key 発行 + GitHub Secrets `ANTHROPIC_API_KEY` 更新 ②Slack Workspace Apps の Incoming Webhooks で旧 Webhook 削除 + 新 Webhook 発行 + GitHub Secrets `SLACK_WEBHOOK` 更新 ③deploy-lambdas.yml run #378 (workflow_dispatch) で全 11 Lambda env に新 key/webhook 反映。元の説明: ~~2026-05-02 09:50 JST — 2026-05-02 09:50 JST: 網羅調査中に Cowork が `aws lambda get-function-configuration` 経由で `p003-processor` の env から ANTHROPIC_API_KEY (`sk-ant-api03-...`) を平文取得 → Cowork チャット応答に値が表示された。同様に `p003-fetcher` env から SLACK_WEBHOOK URL (`https://hooks.slack.com/services/...`) も。チャット履歴に残ったため両方 rotate 必須。手順: ①Anthropic Console → API Keys → 該当キー Revoke → 新規発行 ②GitHub Secrets `ANTHROPIC_API_KEY` 更新 ③deploy workflow を T2026-0502-H 修正後に手動 run → Lambda env 全関数に新 key 反映 ④Slack workspace → Apps → Webhook URL revoke → 新規発行 ⑤同様に Lambda env / GitHub Secret 更新。完了条件: 旧 key で API 401 / 旧 webhook で post 不可・新 key で fetcher/processor 動作確認。**Phase-Impact: セキュリティ最優先 (フェーズ無関係)** / **Eval-Due: 2026-05-02 (即日)** / **依存**: T2026-0502-H 先 (deploy workflow が直らないと Lambda env 反映が出来ない・PO が手動更新するなら独立) | Anthropic Console, Slack Workspace, GitHub Secrets, Lambda env (全関数) | 2026-05-02 |
| ~~T2026-0502-SEC4~~ | ~~🔴 緊急~~ | ~~**Notion integration token のローテーション**~~ → **2026-05-02 PM 完了** — PO が Notion Settings で旧 `ntn_3865...` Revoke + 新 token 発行 + GitHub Secrets `NOTION_API_KEY` 更新済。影響範囲: ①GitHub Actions `notion-sync.yml` / `notion-revenue-daily.yml` が secrets 経由で読む (本番経路) → 新 token で稼働 ②`fetch_notion.py` (PO ローカル・gitignore 済) は新 token を `export NOTION_TOKEN=...` で受ける形 (PR #200 で書換済)。Anthropic 部は SEC1 と同 key で完了済。完了条件達成: 旧 Notion token で API 401。**T2026-0502-SEC-AUDIT 緊急 SEC タスク全 4 件 (SEC1/SEC2/SEC3 rotate/SEC4) クローズ**。元の説明: ローカル平文ファイル内 secrets のローテーション (T2026-0502-SEC-AUDIT) | (完了済) | 2026-05-02 |
| ~~T2026-0502-SEC2~~ | ~~🔴 緊急~~ | ~~**GitHub PAT ローテーション + ローカル設定からの平文除去**~~ → **2026-05-02 13:30 JST 完了** — `.git/config` から平文 token 除去 (Keychain 認証 `osxkeychain` へ移行)、`.claude/settings.local.json` L21 の `Bash(GITHUB_TOKEN=... SLACK_BOT_TOKEN=... SLACK_WEBHOOK=... bash deploy.sh)` allow エントリーを削除 (CLAUDE.md「deploy.sh は直接実行しない」ルールと整合)。Verified: `git remote -v` で token 無し URL のみ表示、`grep -cE 'gh[ops]_|sk-ant-|xox[bp]-|hooks\.slack\.com' settings.local.json` = 0。Personal Access Token は元々ゼロ件登録 (`gho_...` は OAuth App user-to-server token で revoke すると Cowork 連携が切れる副作用大のため放置)。**副作用 (T2026-0502-SEC2-RECURRENCE)**: cowork_commit.py が 401 になり PR #206 で多経路化 + 物理ガード追加で恒久対処。元の説明: ~~2026-05-02 11:35 JST — 2026-05-02 11:35 JST T2026-0502-M 調査中に Cowork が以下 2 箇所で平文の GitHub PAT を観測: ①`.git/config` の `remote.origin.url = https://nuuuuuuts643:gho_...@github.com/...` ②`.claude/settings.local.json` 内の Bash allow エントリーに `GITHUB_TOKEN="ghp_..."` `SLACK_BOT_TOKEN="xoxb-..."` `SLACK_WEBHOOK="..."` がコマンド allowlist として展開されたまま保存。`.claude/settings.local.json` は gitignore 済 (L5) で git track 外なので push 流出はしていないが、Cowork チャット履歴・スクリーン共有・session_info MCP 経由で第三者に見える可能性。手順: ①GitHub Settings → Personal access tokens → 該当 token Revoke → 新規発行 (scope は最小化: `repo` + `workflow` のみ) ②`.claude/settings.local.json` の該当 allow エントリーを `Bash(GITHUB_TOKEN=$GITHUB_TOKEN bash deploy.sh)` のように env 変数参照に置換 ③`.git/config` の `remote.origin.url` を `https://github.com/nuuuuuuts643/AI-Company.git` に書き換え + GIT_ASKPASS / `~/.netrc` / `gh auth login` で別途認証 ④Slack Bot Token / Webhook も再発行 (T2026-0502-SEC1 と並行)。完了条件: 旧 PAT で API 401 / `.claude/settings.local.json` と `.git/config` を grep して `gho_` `ghp_` `xoxb-` `https://hooks.slack.com/` が 0 件。**Phase-Impact: セキュリティ最優先 (フェーズ無関係)** / **Eval-Due: 2026-05-02 (即日)** / **依存**: なし (T2026-0502-SEC1 と並行可) | GitHub Settings, `.claude/settings.local.json`, `.git/config` (ローカル) | 2026-05-02 |

</details>


### 自動 triage: 2026-05-02 に TASKS.md から移動した取消線済みタスク

<details><summary>取消線で完了マークされた行（TASKS.md 由来）</summary>

| ~~T2026-0502-SEC9~~ | ~~🟡 中~~ | ~~**Anthropic API key を AWS Secrets Manager に移行**~~ → **2026-05-02 PM 完了** — PO 実機操作: ①IAM policy `flotopic-least-privilege` に `SecretsManagerRead` (`secretsmanager:GetSecretValue` on `flotopic/anthropic-api-key-*`) 追加 ②Secrets Manager に `flotopic/anthropic-api-key` 作成 ③Lambda env (fetcher + processor) に `ANTHROPIC_SECRET_ID=flotopic/anthropic-api-key` 追加 ④CloudWatch Logs で `Secrets Manager fetch failed` が両 Lambda で 0 件確認 ⑤両 Lambda env から `ANTHROPIC_API_KEY` 平文削除。**Verified-Effect**: `aws lambda get-function-configuration --function-name p003-fetcher --query 'Environment.Variables.ANTHROPIC_API_KEY'` = `null` / `ANTHROPIC_SECRET_ID` = `"flotopic/anthropic-api-key"` (両 Lambda)。Lambda 設定読み取り権限 IAM principal が live key を取得できる脆弱性消失。コード側準備は PR #228、runbook は `docs/runbooks/secrets-manager-migration.md`。 | (完了済) | 2026-05-02 |

</details>

---

## 2026-05-02 PM 〜 19:13 JST: 流入消失恒久対処 + 観測 + Bluesky 朝投稿 (Cowork セッション)

PO の「流入は実測で増えてる？」「悪くはないか」問題提起を起点に、本日後半で発覚した構造欠陥を一気に対処。

**完了 (本日 PM)**:
1. **T2026-0502-AQ noindex 流入消失 恒久対処+再発防止 (PR #263 merged)** — Cloudflare Web Analytics PV が 4/27 260 → 4/28 20 (1/10 急減) の真因を特定: `T2026-0502-ADSENSE-FIX` で `frontend/topic.html` `frontend/catchup.html` に `noindex,follow` を追加していた。AdSense 薄コンテンツ対策。恒久対処: noindex 削除 + `scripts/check_seo_regression.sh` で主要 7 ページ noindex 物理ガード CI + freshness-check.yml SLI 15 (Cloudflare PV 前日比急変 Slack alert・UTC 22 時台のみ判定) + `docs/product-direction.md` に「フェーズ前提を壊さない原則」+ lessons-learned Why1〜5 + 横展開 5 件。**実機 verify 済**: topic.html / catchup.html / index.html すべて noindex 削除確認 (T2026-0502-ADSENSE-FIX 由来で AdSense 通過のために流入を捨てていた状況を解消)。
2. **T2026-0502-AQ-FOLLOWUP scanner regex 修正 (PR #268)** — `scripts/check_sli_field_coverage.sh` の `t.get(...)` regex に `\b` 単語境界を追加し、SLI 15 で書いた `latest.get('count')` の末尾 `t.get('count')` への誤マッチを修正。本日 ci.yml SLI 乖離検出 step が連続失敗していた問題を解消。
3. **T2026-0502-AT auto-merge.yml PAT 化 (PR #271 merged)** — 真因特定: `auto-merge.yml` が `secrets.GITHUB_TOKEN` で `gh pr merge` を実行 → GitHub の制約「`GITHUB_TOKEN` による push/merge は他の workflow を trigger しない」で deploy-p003.yml の **pull_request 由来 run = 過去 30 日 total=0**。本日 PR #263 merge 後 30 分間本番未反映。恒久対処: `GH_TOKEN: ${{ secrets.AUTO_MERGE_PAT \|\| secrets.GITHUB_TOKEN }}` に 1 行修正 + フォールバック警告ログ + 継ぎ足し watchdog 案は撤回 (PO 指摘「とりあえず動かすのはやめてくれ」)。Cowork が **既存 PAT (scope=repo,workflow) を pynacl で AWS 暗号化して `AUTO_MERGE_PAT` secret に自動登録**。lessons-learned Why1〜5 + 横展開 6 件。**Verified-Effect-Pending**: 次の frontend PR merge で deploy-p003 の pull_request event run が success することを確認 (Eval-Due 2026-05-03)。
4. **T2026-0502-AS deploy-p003 CloudFront Function publish step 失敗 解消** — 真因: PR #265 (T2026-0502-SEC10-CODE OIDC 専用化) で `flotopic-actions-deploy` IAM policy に CloudFront Function 系 Action (`DescribeFunction`/`CreateFunction`/`UpdateFunction`/`PublishFunction`/`GetFunction`/`ListDistributions` 等) が含まれていなかった。run#426 step 7 が `aws cloudfront describe-function` で 2 秒で AccessDenied 即落ち。`aws iam put-role-policy` で `CloudFrontFunctionAndDistribution` Statement 追加。run#427 (workflow_dispatch) で動作中。
5. **T2026-0502-AW Daily PV Slack 通知 (PR #272)** — 「PV をわかるように見たい」要望に対処。`.github/workflows/daily-pv-slack.yml` 新設・cron='5 22 * * *' (JST 07:05・cf-analytics 更新直後)・急変 alert 込み・コスト 0 円。
6. **T2026-0502-AX Bluesky 朝投稿 EventBridge rule (AWS 直接実装)** — Bluesky 公式 @flotopic.bsky.social (フォロワー 3・投稿 104) が **daily mode で動いている**ことを Chrome MCP で確認。ただし朝投稿の保証なし (直近 16:30 JST 等)。新規 EventBridge rule `flotopic-bluesky-morning-cron` (cron(0 21 * * ? *) = JST 06:00) + target = flotopic-bluesky Lambda + input `{"mode":"morning"}` + Lambda permission 追加。既存 30 分毎 rule (daily) はそのまま (cooldown 20h でガード)。**Verified-Effect-Pending**: 明日朝 5/3 06:00 JST 発火・Bluesky で morning mode 投稿確認。

**新規起票 (TASKS.md)**:
- T2026-0502-Z (DAU/WAU/再訪率/滞在時間ベースライン観測)
- T2026-0502-AA (毎日来る理由 MVP・候補 3 → AX で B② Bluesky 朝投稿のみ完了)
- T2026-0502-BB (フェーズ1 完了宣言の再検証)
- T2026-0502-AR (admin Hero strip・本日 PO 方針切り替えで中断・継続)
- T2026-0502-AS (CloudFront Function publish 失敗・本日 IAM policy 更新で解消)
- T2026-0502-AT (auto-merge PAT 化・PR #271 + AUTO_MERGE_PAT secret 登録済)
- T2026-0502-AU (CI 23% 失敗 棚卸し・各 workflow 個別対処)
- T2026-0502-AV (GitHub App 化・1 ヶ月後検討)

**継続観察項目** (次セッション or scheduled):
- run#427 (deploy-p003 CloudFront Function policy 追加後の verify) 結果
- 5/3 朝 7:05 JST: PV Slack 朝報の初回到達
- 5/3 朝 06:00 JST: Bluesky morning mode 初回発火
- 5/9 まで: Cloudflare PV 回復観察 (noindex 削除後 1〜2 週間で Google 再 index 想定)

**未着手 (中断)**:
- T2026-0502-AR (admin Hero strip) — ローカル admin.html 編集が残っているが commit していない・次セッションで AR 再開時の素材として残置

**メタ教訓**: 本日の構造欠陥 4 件 (AQ/AS/AT/AQ-FOLLOWUP) はいずれも「Verified-Effect-Pending のまま実機検証されずに landing」が原因。`docs/lessons-learned.md` に「CI green = 完了 と思い込む癖」「workflow 単体 success と本番反映は別軸」記述を追加 (T2026-0502-AT セクション)。


### 自動 triage: 2026-05-03 に完了したタスク

| ~~T2026-0502-AZ~~ | ✅ 完了 (2026-05-03) | **Prompt caching breakpoint 最適化** — `proc_ai.py` の `_generate_story_minimal` / `_generate_story_standard` / `_generate_story_full` の 3 関数で user prompt を **静的ジャンルヒントブロック (cache_control: ephemeral)** + **動的記事データブロック** の 2 ブロック構造に分割。T2026-0501-K の `_GENRE_KEYPOINT_EXAMPLES` と T2026-0502-AE の `_GENRE_AISUMMARY_CAUSAL_FRAMES` (合計 ~2000+ tokens) を cached prefix に含め、同ジャンル内の 2 件目以降で cache hit を発生させる設計。`cnt` を静的ブロックから除去し、同ジャンル異 cnt 呼び出し間でもキャッシュエントリーを共有可能にした。`_call_claude_tool` の型注釈を `str | list` に更新。`tests/test_prompt_cache_breakpoint.py` 新設 (22 tests、全 PASS)。既存テスト 3 件 (test_keypoint_genre_hint / test_minimal_perspectives / test_title_prompt_quality) のリスト型プロンプト対応も修正。**Verified-Effect-Pending: 2026-05-16** で `claude_cache read/write` 比率の前後比較予定 | `lambda/processor/proc_ai.py`, `tests/test_prompt_cache_breakpoint.py` (新設), `tests/test_keypoint_genre_hint.py`, `tests/test_minimal_perspectives.py`, `tests/test_title_prompt_quality.py` | 2026-05-03 |


### 自動 triage: 2026-05-02 に TASKS.md から移動した取消線済みタスク

<details><summary>取消線で完了マークされた行（TASKS.md 由来）</summary>

| ~~T2026-0502-BJ~~ | ✅ 完了 (2026-05-02) | ~~Cowork (Linux sandbox) 認証 — `.cowork-token` 経路への移行~~ — **完了**: ① cowork_commit.py 経路 0 (.cowork-token) 実装 (PR #290 merged) ② Mac で `.cowork-token` 作成済 ③ `.git/config` URL から token 剥がし済 ④ Cowork sandbox から smoke test PASS (token resolved=True / GitHub API whoami=`nuuuuuuts643`) ⑤ **再発防止物理ガード**: session_bootstrap.sh 3e3 に「Cowork auth 経路死活検査」追加 (3 経路 (a)URL/(b).cowork-token/(c)env のいずれもなければ WARN)。横展開棚卸しは T2026-0502-BJ-FOLLOWUP で継続 | scripts/cowork_commit.py / .gitignore / scripts/session_bootstrap.sh / docs/lessons-learned.md | 2026-05-02 |

</details>
