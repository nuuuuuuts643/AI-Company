# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 🔥 今週やること（メインキュー）

<!-- フェーズ別紐付け (詳細: docs/project-phases.md) -->
<!-- フェーズ1 (足回り安定) — Dispatch運用安定 / リリース管理 / 形骸化検出 -->
<!-- フェーズ2 (AI品質) — T212/T2026-0428-E/T2026-0428-BRANCH -->
<!-- フェーズ3 (UX・成長) — T191/T193 -->

> **選定基準**: ユーザー体験に直結・安定性・AI品質・収益に近い順。
> **整理日**: 2026-04-28 PM (T2026-0428-AX で実装済タスク除去 + フェーズ1 新規完了条件タスク追加)

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
| T191 | 🟠 高 | 体験 | **「ストーリーを追う」フロー設計** — トップ画面で動きが見える → 1 タップで経緯 → 「続きが来たら通知」で離脱。コード変更より先に画面遷移フロー図 | 設計フロー図 | 2026-04-27 |
| T2026-0428-BRANCH | 🟡 中 | AI品質 | **ストーリー分岐はセマンティック関連性で判断する方針メモ** — 注目度（数字）ではなく内容（登場人物・因果関係・エンティティ重複）で。関連: T212 | `lambda/fetcher/`, `lambda/processor/proc_ai.py` | 2026-04-28 |

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
| T192 | 高 | **ジャンル戦略: 全ジャンル対応から1-2ジャンル集中に絞る検討** — SmartNews・グノシー等との全ジャンル競合では差別化できない。Flotopic が「このジャンルなら Flotopic」と言われる領域がない。現状の PV・お気に入り登録をジャンル別に集計し、最も使われているジャンルを特定。 | `CLAUDE.md`（方針決定後） | 2026-04-27 |

### リーガル・コンプライアンス

<!-- フェーズ1 (足回り安定) — 法的・規約遵守の運用品質 -->

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T224a | 高 | **admin.html の `allowedEmail` フロント直書き対応** — T224 残課題。`frontend/admin.html:296` の `allowedEmail` 直書きは公開ファイルでスピアフィッシング情報として漏洩中。build 時注入機構 (env→HTMLテンプレート置換) を作る大改修。暫定運用は admin.html を CloudFront で IP 制限など。 | `frontend/admin.html` | 2026-04-28 |
| T225 | 中 | **tokushoho.html 残存** — Cowork 範囲外 (FUSE マウントで物理削除不可)。Code セッションで `git rm projects/P003-news-timeline/frontend/tokushoho.html` + CloudFront キャッシュパージ + Search Console URL 削除リクエスト + CI に「frontend に tokushoho.html が存在しないこと」チェック追加。 | `frontend/tokushoho.html`（削除）, CI チェック | 2026-04-28 |

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
| T2026-0428-AV | 中 | **トピックカードに注目スコアを表示する** — POフィードバック: スコアをカードに表示するアイデアが面白い。トップページのトピックカード (`frontend/app.js` の renderTopicCard 系) に、AI が計算した注目度スコア (`velocityScore` 等) を数値またはバーで表示する。フェーズ1 の足回り安定が完了してから着手 (UI 改善は後回し方針)。実装時は ①どのスコアを使うか (velocityScore / freshness / 記事数) を明確化 ②表示形式 (数値/バー/バッジ) を決定 ③モバイル 375px で崩れないこと を必須。 | `frontend/app.js`, `frontend/style.css` | 2026-04-28 |

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
| T237 | 中 | **AI生成カバレッジの根本原因調査** — TASKS.md「P003 技術状態スナップショット」で「pending queue 優先度問題 (T213) が根本原因」と書かれているが T213 が見当たらない (既に番号衝突か履歴へ移動)。proc_storage.py の `get_pending_topics` を読み、Tier-0 (topics.json 可視 × aiGenerated=False) を最優先で返しているか・DynamoDB scan の order 保証があるか実機確認する。T218 wallclock guard が反映されれば自動解消される可能性も含めて再評価。 | `lambda/processor/proc_storage.py`, `lambda/processor/handler.py` | 2026-04-28 |
| T238 | 低 | **processor handler.py の特殊モード分岐が肥大化（300+行）** — `lambda/processor/handler.py:60-150` に `regenerateStaticHtml` / `backfillDetailJson` / `backfillArchivedTtl` / `purgeAll` / `forceRegenerateAll` / `regenerateSitemap` の6つの特殊モードが連結 if 文で並ぶ。テスト・保守・新モード追加が困難。`proc_admin_modes.py` に分離。 | `lambda/processor/handler.py` (新規ファイル) | 2026-04-28 |
| ~~T254~~ | ~~中~~ | ~~**style.css / app.js が `no-cache, must-revalidate` で CDN/ブラウザキャッシュ無効化されている** — Lighthouse スコア・帯域コスト低下。HTML は正解だが、JS/CSS は content-hash バージョニング (`app.js?v=abc123`) すれば長期キャッシュ可能。deploy-p003.yml で JS/CSS に長期キャッシュ (max-age=31536000, immutable) を設定し、`?v=${GITHUB_SHA::7}` で書き換え。~~ ✅ 2026-04-29: deploy-p003.yml に Python rewrite step + immutable max-age=31536000 追加 | `.github/workflows/deploy-p003.yml`, `frontend/*.html` の `<script src=>` / `<link href=>` | 2026-04-28 |
| T260 | 中 | **個別 topic JSON の `data['meta']` で aiGenerated=False の topic も生成されている** — `https://flotopic.com/api/topic/8f81be6586cbea09.json` は `aiGenerated=False` で meta が `{aiGenerated, topicId}` の 2 フィールドだけ。空の個別 JSON が量産。`update_topic_s3_file` で `aiGenerated=False` かつ generatedTitle 等が無いトピックは個別 JSON 生成をスキップ。 | `lambda/processor/proc_storage.py` update_topic_s3_file | 2026-04-28 |

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
| T256 | 中 | **AI フィールドの「層を1つ忘れる」を CI で物理検出する仕組み不在** — T249 (keyPoint・backgroundContext merge 漏れ) は手動調査で発見。`.github/workflows/ai-fields-coverage.yml` 新規。proc_ai.py の input_schema を grep して field 名一覧を抽出 → handler.py merge ループの両方に同名キーがあるか check → 欠落あれば CI ERROR。 | `.github/workflows/ai-fields-coverage.yml` 新規, `scripts/check_ai_fields_coverage.py` 新規 | 2026-04-28 |
| T258 | 中 | **「発端」storyPhase 50% 偏り (本番) — T219 修正前の旧データが残る** — 本番 topics.json で storyPhase 分布 = 拡散 23 / 発端 57 / ピーク 9 / 現在地 4 / null 21。T219 prompt 修正で「記事3件以上で発端禁止」を入れたが、aiGenerated=True 旧 topic は skip されるため反映されない。完了判定: T255 修正＋forceRegenerateAll 1-2 回後、storyPhase 分布が正規化。 | (T255 で連動解消) | 2026-04-28 |
| T259 | 低 | **`Cache-Control: max-age=60` の topics.json が 90 分後鮮度警告と整合しない** — T263 実装時に「鮮度=updatedAt フィールド差分」「Cache-Control= edge cache TTL」の違いを混同しないこと。両者は別軸。 | T263 実装時に注意点として明記 | 2026-04-28 |
| T262 | 中 | **プライバシーポリシー・利用規約が `noindex` だが SEO 上の表示・検索性は OK か再確認** — privacy.html / terms.html は `noindex` 設定なし (現在は indexable)。Search Console で `site:flotopic.com` 検索し、privacy/terms が結果に出るか確認。 | Search Console 確認 | 2026-04-28 |
| T264 | 中 | **`.claude/worktrees/` に 6 個の stale 作業ツリーが残存** — `awesome-varahamihira-c01b2e` `happy-khorana-4e3a6c` `naughty-saha-ba5901` `quirky-cohen-c1efbd` `serene-hermann-993255` `vigilant-fermi-4e0a09`。WORKING.md TTL 8h ルールはメインの WORKING.md にしか適用されていない。起動チェック script に worktree クリーンアップ候補一覧表示 + 物理スクリプト化 + `.gitignore` 追加。 | `CLAUDE.md` 起動チェック, `scripts/cleanup_stale_worktrees.sh` 新規 | 2026-04-28 |
| T2026-0428-Q | 中 | **success-but-empty 抽象パターンの他コンポーネント横展開スキャン** — keyPoint 充填率 11.5% を「aiGenerated フラグだけ見る SLI」が素通りした問題の横展開。要監視: ① fetcher articleCount=0 cycle、② processor processed=0 cycle、③ bluesky_agent post 失敗、④ SES bounce、⑤ CloudFront 5xx、⑥ CI green-but-skipped、⑦ topic 個別 JSON の meta=2フィールドだけパターン (T260)。1 件ずつ「観測 SLI が存在するか」を埋める | `docs/sli-slo.md`, `.github/workflows/freshness-check.yml`, `scripts/scan_success_but_empty.py` 新設 | 2026-04-28 |
| ~~T2026-0428-K~~ | ~~🟡 中~~ | ~~**環境スクリプトの dry-run CI 化** — 2026-04-28 04:15 schedule-task で session_bootstrap.sh / triage_tasks.py に session-id ハードコードと UTC を JST と誤ラベルする bug が同時露見。lessons-learned「環境スクリプトに session ID hardcode」記録。修正は同 commit で landing 済だが、再発防止として `scripts/session_bootstrap.sh --dry-run` を GH Actions 日次実行 → REPO 検出 / JST 表示 / WORKING.md 未来日付 stale 検出ロジックを物理 test。Claude が次セッションで気付くループを CI で前倒しに切り替える。~~ ✅ 2026-04-29: `--dry-run` 実装 + `env-scripts-dryrun.yml` 新規（smoke test + WORKING.md stale unit test + 負のテスト） | `.github/workflows/env-scripts-dryrun.yml` 新規, `scripts/session_bootstrap.sh` (`--dry-run` 引数追加) | 2026-04-28 |
| T2026-0428-S | 🟢 低 | **contact.html が noindex 設定 — E-E-A-T 上は indexable が望ましいか再判断** — 2026-04-28 07:13 schedule-task で curl 確認、`<meta name="robots" content="noindex">` 設定。連絡先ページは Google E-E-A-T 評価で「Trust」シグナル源。AdSense 審査でも contact 有無は評価対象。**懸念**: 現状 noindex のため検索結果に出ない → 信頼性シグナルとして検索エンジンに認識されない可能性。**判断材料**: SES 受信専用フォームで spam リスクが高いから noindex にしているなら維持、純粋な連絡先表示なら indexable に変更。要PO確認後に変更検討。 | `frontend/contact.html` | 2026-04-28 |
| T2026-0428-U | 🟢 低 | **個別 topic JSON (L4b) の AI フィールド充填率 SLI** — `_PROC_INTERNAL = {spreadReason, forecast, storyTimeline, backgroundContext}` は topics.json publish 時に除外され、これらは個別 `api/topic/{tid}.json` (L4b) でのみ観測可能。現状 SLI 8/9/10 は L4a (topics.json) のみ。`scripts/check_ai_fields_coverage.sh` を sample N=10 個別 JSON 取得 → backgroundContext / spreadReason / forecast / timeline 充填率を集計 → SLI 11/12/13 として登録。詳細: `docs/ai-fields-catalog.md`, lessons-learned 2026-04-28 07:13。 | `scripts/check_ai_fields_coverage.sh`, `.github/workflows/freshness-check.yml`, `docs/sli-slo.md` | 2026-04-28 |
| T2026-0428-L | 🟢 低 | **`scripts/security_headers_check.sh` 新設 + CI 化** — T251 検証で「2026-04-28 04:20 時点で全付与済」を確認したが、CloudFront response headers policy の drift を外部観測する仕組みが無い。GH Actions cron で毎日 `curl -sI https://flotopic.com/` を取得し HSTS / X-Frame-Options / Permissions-Policy / Referrer-Policy / X-Content-Type-Options が消えていれば Slack 警告。SLI 8 として登録。 | `scripts/security_headers_check.sh` 新規, `.github/workflows/security-headers-check.yml` 新規, `docs/sli-slo.md` SLI 8 追記 | 2026-04-28 |
<!-- T2026-0428-N (AI フィールド充填率 SLI 化) は freshness-check.yml SLI 8/9/10 として inline landing 済 (HISTORY.md 19b272d) -->
<!--   閾値: keyPoint 70% / perspectives 60% / outlook 70%。Slack 通知も実装済 -->
<!--   外部 cron は freshness-check.yml の schedule で代替 (06:10 JST 等)。本タスクは完了扱い -->
| T2026-0428-AG | 🟢 低 | **個別 topic JSON で backgroundContext / spreadReason の充填率検証** — T2026-0428-N (上記 landing 済) は topics.json (L4a) の SLI。個別 topic JSON (L4b) の `backgroundContext` 等は別観測が必要。任意 5 topic を curl サンプリングして空でないことを確認する手順を追加 | (T2026-0428-Q success-but-empty 横展開 に統合) | 2026-04-28 |
| ~~T2026-0428-AF~~ | ~~🟡 中~~ | ~~**`generatedTitle` に markdown `# / *` 残骸が残るレガシートピック** — 2026-04-28 05:13 JST 観測で `# 鈴木誠也が佐々木朗希から本塁打、カブス連勝中の活躍続く` (full mode topic) が title 先頭に `#` を持つ。fix commit `b5c36b0: fix(P003): generate_title で markdown 残骸 (# / *) を strip` 適用前に生成された aiGenerated=True topic は再生成 skip 条件で永続。一括 sanitize: `lambda/processor/handler.py` の admin mode `forceRegenerateAll` を一度実行する or `proc_storage.py update_topic_s3_file` 呼び出し前に title から `^\s*[#*]+\s*` を strip する band-aid を入れる (band-aid は CLAUDE.md ルールで本来禁止だが「過去データ補正」用途として一時許容、補正完了後に削除)。~~ ✅ 2026-04-29: proc_storage.py に `_strip_title_markdown()` ヘルパ追加 + `update_topic_with_ai` / `update_topic_s3_file` 両方の write path で適用（再保存時に自然に正規化、一括書き換え無し） | `lambda/processor/proc_storage.py` or admin `forceRegenerateAll` 実行 | 2026-04-28 |
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
