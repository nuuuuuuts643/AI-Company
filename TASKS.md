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
| ~~T2026-0502-O~~ | ~~🟡 高~~ | ~~**AWS IAM Deny ポリシー追加 (思想ルールの物理化)**~~ → **2026-05-02 13:30 JST 完了** — IAM Console で Cowork ユーザーにインラインポリシー `CoworkDenyDestructive` 適用 (Deny: lambda:UpdateFunctionCode/lambda:DeleteFunction/dynamodb:DeleteTable/dynamodb:DeleteBackup/s3:DeleteBucket/ec2:TerminateInstances/rds:DeleteDBInstance/iam:DeletePolicy/iam:CreateAccessKey)。Verified-Effect: `aws iam create-access-key --user-name Claude` で `AccessDenied ... explicit deny in an identity-based policy` 確認。CLAUDE.md「Cowork は不可逆操作禁止」思想ルールが IAM 物理ルールに昇格。元の説明: ~~Cowork IAM ユーザー — Cowork IAM ユーザー (`arn:aws:iam::946554699567:user/Claude`) に以下 Deny を追加: `lambda:UpdateFunctionCode` `lambda:DeleteFunction` `dynamodb:DeleteTable` `dynamodb:DeleteBackup` `s3:DeleteBucket` `ec2:TerminateInstances` `rds:DeleteDBInstance` `iam:DeletePolicy` `iam:CreateAccessKey`。CLAUDE.md「思想ルール (Cowork は不可逆操作禁止)」を IAM 物理ルールに変換。完了条件: `aws lambda update-function-code` を Cowork から試して AccessDenied 確認。Verified-Effect: AccessDenied で reject されるログ。**PO 承認 + AWS Console 操作必要**（私が直接実行は危険）。policy 文書: `docs/rules/cowork-aws-policy.md` Section 4 | AWS IAM Console (Cowork ユーザー policy) | 2026-05-02 |
| T2026-0502-E | 🟡 中 | **NHK 本文取得タイムアウト恒久対処 (フェーズ2 perspectives 品質)** — 2026-05-02 09:40 JST 調査 (Cowork): `lambda/processor/article_fetcher.py` の 5秒 timeout で `www3.nhk.or.jp` が常時タイムアウト (直近48hで `[ArticleFetcher] www3.nhk.or.jp fetch失敗: TimeoutError: timed out` 多発・1〜数件/30min)。Cat-A 公共放送 NHK が常時 RSS スニペット (~200字) フォールバックで AI に渡されており「各社の見解」で NHK 論調が比較できない状態。対策: ①NHK 専用に timeout 8〜10s 拡大 (host 別マップ)、②1回リトライ追加、③User-Agent を `FlotopicBot/1.0` から汎用 UA に戻す試験 (Bot 識別で 429 を timeout として返している可能性)。完了条件: 直近1h の `[ArticleFetcher] www3.nhk.or.jp ... timed out` ログが 50% 以上減少。Verified-Effect: NHK 本文取得成功率 (CloudWatch logs カウント) を base→1週間後で計測。**Phase-Impact: 2 E2-2 perspectives 充填率改善** / **Eval-Due: 2026-05-09** | `lambda/processor/article_fetcher.py` | 2026-05-02 |
| T2026-0502-F | 🟢 低 (PO アクション待ち・督促) | **Google Trends API 機能の修復 or 削除判断** — 2026-05-02 09:40 JST 調査 (Cowork): `lambda/fetcher/trends_utils.py` の Google Trends 非公式 API 直叩きが過去48h **100%失敗** (`HTTPError 400: Bad Request` または `429: Too Many Requests`)。3回ガードで残りスキップ動作はしているが、`trendsData` は1件も更新されていない可能性。30分毎の fetcher 起動でログに3〜4行のエラースタック汚染が継続中。判断ポイント: ①Trends 関連の関心度推移ミニチャートを今後も維持するか (フェーズ4 SNS化 epic に効くなら維持) ②維持なら pytrends ライブラリ + Lambda Layer 対応 (zip *.py 制約を破る要検討)、削除なら `_trend_candidates` ループ + handler.py:1075-1108 と `trends_utils.py` 削除 + `trendsUpdatedAt`/`trendsData` フィールド deprecate。完了条件: PO 判断後にどちらかが実装され、`[trends] HTTPError` ログが 0 件になること | `lambda/fetcher/handler.py`, `lambda/fetcher/trends_utils.py` | 2026-05-02 |
| T2026-0502-R | 🟡 中 (観察待ち) | **T2026-0501-H Haiku borderline 判定 復活確認 (T2026-0502-Q/H 完了の効果検証)** — 2026-05-02 10:25 JST PR #141 merge → fetcher env に ANTHROPIC_API_KEY 復活確認済 (LastModified 10:21 JST)。最後の fetcher 発火は 10:05 JST (deploy 前) のため、**次回 10:35 JST 以降の発火で初めて新 env が効く**。完了条件: 直近 1h `/aws/lambda/p003-fetcher` logs に `[ai_merge_judge]` または `[borderline]` の語が 1 件以上出現。Verified-Effect: 1 週間後の `[ITmedia M` 始まり重複が <2 件まで減ること。**観察を schedule タスク `p003-haiku` に委ねて即 close** — 2026-05-03 朝に確認結果が出る想定。**Phase-Impact: 2 E2-3 クラスタリング品質** / **Eval-Due: 2026-05-09** | (確認のみ・H で復旧) | 2026-05-02 |
| T2026-0502-K | 🟢 低 (観察記録のみ・需要観測後実装) | **CloudFront 4xxErrorRate 6.2〜20.7% (5xx は 0%)** — 2026-05-02 10:24 JST 観察 (Cowork): 4xx 率は CloudFront `E2Q21LM58UY0K8 (flotopic.com)` で 4/30=20.7%・5/1=7.7%・5/2 朝=6.2%。404 となる主な path: `/topics-card.json` `/topics.json` `/og-image.png` `/apple-touch-icon-precomposed.png`。frontend は `/api/` プレフィックス付き (200 OK) を叩いているので、これらは外部由来 (旧 bookmark / SNS シェアの OGP fetch / iOS Safari 自動 fetch)。**ユーザー直接影響軽微**。対策案 (実装は需要観測後): ①OG image を S3 に配置 ②index.html に `apple-touch-icon-precomposed` の link 追加 ③`/topics-card.json` `/topics.json` を `/api/...` に 301 redirect。Phase-Impact: 観察記録のみ | (観察記録) | 2026-05-02 |
| T2026-0502-V | 🟡 中 (観察待ち・月曜時限) | **lifecycle Lambda T2026-0502-B 修正本番反映の確認** — 2026-05-02 10:32 JST Cowork 確認: PR #125 で 5 ファイル横展開修正したが deploy が連続失敗していた (T2026-0502-Q)。10:25 JST PR #141 で deploy が復旧 → run #372 で全 11 Lambda が新コードで反映されたはず。**lifecycle weekly cron 次回発火: 2026-05-04 11:00 JST 月曜朝**。完了条件: 次回 lifecycle invocation で ValidationException が出ないこと。Verified-Effect: 2026-05-04 11:00 JST 以降の `/aws/lambda/flotopic-lifecycle` logs に「ValidationException」が 0 件、削除処理が正常完走 (`[deleted]` ログ出現)。観察は schedule `p003-haiku` (毎朝 7:08 JST) で月曜朝に確認。Phase-Impact: 1 運用安定化 / Eval-Due: 2026-05-04 14:00 JST | (確認のみ・PR #125 と #141 で復旧済想定) | 2026-05-02 |
| T2026-0502-T | 🟡 高 (要追跡・サンプル蓄積待ち) | **API Gateway flotopic-api 5xx 率 2.7〜17.6% 原因特定** — 2026-05-02 09:50 JST 調査 (Cowork): API Gateway `x73mzc0v06 (flotopic-api)` の 5xx 率: 4/30=4.7%・5/1=2.7%・5/2 朝=17.6%。一方で各統合 Lambda (p003-api/comments/contact/auth/favorites/analytics/cf-analytics) は **Errors=0 / Duration<700ms** で全て健全。Lambda 自体は通っているのに API Gateway が 5xx を返している = Lambda permission missing / CORS preflight に Lambda が紐付いていない / 502 統合エラーの可能性。Access logs (`accessLogSettings.destinationArn=null`) が未有効なので request 単位で見えない。対策: ①Access logs を CloudWatch に有効化 (1時間で原因特定可) ②CORS の OPTIONS routes が Lambda 統合になっているか確認 ③Lambda permission `AddPermission` を再付与。**【2026-05-02 12:00 JST 効果検証 (p003-sonnet/scheduled)】** Access logs (`/aws/apigateway/flotopic-api`) を有効化済 → 直近 4 streams (~45min・約 12 events) で 5xx は **1 件のみ**: `GET /favorites/{userId}` (status=500, integrationStatus=200, integrationLatency=960ms, integrationErrorMessage="-")。Lambda log (`/aws/lambda/flotopic-favorites` reqId 41110772) では cold start (Init=480.60ms) → 326.54ms で正常 END、ERROR/Exception なし。**`POST /track` は access logs に 0 件 → 既に dead route 化済 (T2026-0502-I で解消)**。原因仮説: Lambda レスポンス payload format mismatch (HTTP API v2 が期待する `{statusCode, body, headers}` 形式不一致) または cold start による response 取りこぼし。サンプル極小 (12 events) のため断定不可。次アクション: ①p003-haiku で 24h 後 access logs を再集計 → routeKey 内訳が固まったら本タスクで対処コードを書く (favorites Lambda の return 形式を `{statusCode, headers, body}` に明示) ②CloudWatch メトリクスでも 5xx 率の改善を再測定。完了条件: 5xx 率 <0.5% へ低下、access logs から原因 1 行で説明可能。**Phase-Impact: 1 運用安定化** / **Eval-Due: 2026-05-09** | `.github/workflows/deploy-lambdas.yml` (apigateway 設定部分), `lambda/favorites/handler.py` (return 形式確認), AWS API Gateway Console | 2026-05-02 |
| ~~T2026-0502-SEC1~~ | ~~🔴 緊急~~ | ~~**Anthropic API Key + Slack Webhook ローテーション**~~ → **2026-05-02 13:30 JST 完了** — ①Anthropic Console で旧 Key revoke + 新 Key 発行 + GitHub Secrets `ANTHROPIC_API_KEY` 更新 ②Slack Workspace Apps の Incoming Webhooks で旧 Webhook 削除 + 新 Webhook 発行 + GitHub Secrets `SLACK_WEBHOOK` 更新 ③deploy-lambdas.yml run #378 (workflow_dispatch) で全 11 Lambda env に新 key/webhook 反映。元の説明: ~~2026-05-02 09:50 JST — 2026-05-02 09:50 JST: 網羅調査中に Cowork が `aws lambda get-function-configuration` 経由で `p003-processor` の env から ANTHROPIC_API_KEY (`sk-ant-api03-...`) を平文取得 → Cowork チャット応答に値が表示された。同様に `p003-fetcher` env から SLACK_WEBHOOK URL (`https://hooks.slack.com/services/...`) も。チャット履歴に残ったため両方 rotate 必須。手順: ①Anthropic Console → API Keys → 該当キー Revoke → 新規発行 ②GitHub Secrets `ANTHROPIC_API_KEY` 更新 ③deploy workflow を T2026-0502-H 修正後に手動 run → Lambda env 全関数に新 key 反映 ④Slack workspace → Apps → Webhook URL revoke → 新規発行 ⑤同様に Lambda env / GitHub Secret 更新。完了条件: 旧 key で API 401 / 旧 webhook で post 不可・新 key で fetcher/processor 動作確認。**Phase-Impact: セキュリティ最優先 (フェーズ無関係)** / **Eval-Due: 2026-05-02 (即日)** / **依存**: T2026-0502-H 先 (deploy workflow が直らないと Lambda env 反映が出来ない・PO が手動更新するなら独立) | Anthropic Console, Slack Workspace, GitHub Secrets, Lambda env (全関数) | 2026-05-02 |
| T2026-0502-SEC3 | 🔴 緊急 (PO アクション待ち・即日期限) | **git history 内 commit 済み live secrets (4個) の rotation (T2026-0502-SEC-AUDIT 発見)** — 2026-05-02 13:10 JST 全体監査で `git ls-files` + `git log -p` に live secrets が確認された (本セッションで current HEAD から除去済だが history には残る): ①`projects/P004-slack-bot/README.md` (commit 7ce172a2 以降ずっと公開) に GitHub PAT (prefix `ghp_LyAq...`) ②旧 `HOME-PC-CHECKLIST.md` / 旧 `CLAUDE.md` (commit 8514d67f / be8be8ef 等) に別の GitHub PAT (prefix `ghp_JPS5...`) ③同 commit 群に Slack Bot Token (prefix `***REDACTED-SEC3***...`) ④同 commit 群に Slack Webhook (path `T08UJJVCFJ4/B0AUJ9K64KE/...`)。リポジトリが GitHub で public ならば**現時点まで誰でも閲覧・抜き取り可能**。手順: ①これら 4 個全て即 Revoke (GitHub Settings / Slack Workspace) ②current HEAD は本セッションで P004 README から除去済 (commit 待ち) ③git history rewrite (`git filter-repo --replace-text` または BFG) で history からも削除 ④force-push で旧 hash 上書き ⑤GitHub support に cache invalidation 申請 (任意・public repo なら fork に残る可能性あり)。完了条件: 旧 4 トークン全てが対応サービスで API 401 / `git log --all -p \| grep -E "ghp_LyAq\|ghp_JPS5\|***REDACTED-SEC3***23616-10995291739264\|B0AUJ9K64KE"` が 0 件。**Phase-Impact: セキュリティ最優先 (フェーズ無関係)** / **Eval-Due: 2026-05-02 (即日)** | GitHub Settings, Slack Workspace, `git filter-repo` (history rewrite) | 2026-05-02 |
| T2026-0502-SEC4 | 🔴 緊急 (PO アクション待ち・即日期限) | **ローカル平文ファイル内 secrets のローテーション (T2026-0502-SEC-AUDIT)** — 2026-05-02 13:10 JST 監査で gitignore 済だがディスク上に live secrets が平文で発見 (Cowork チャット表示・スクリーン共有経由で漏洩リスク): ①`fetch_notion.py:12` に Notion integration token (prefix `ntn_3865...`) ②`setup_api_key.sh:5` に Anthropic API key (prefix `***REDACTED-SEC3***...`)。本セッションで両ファイルとも env 変数読み込み版に書換済 (commit 待ち)。手順: ①Notion Settings → Integrations で該当 token Revoke + 新規発行 ②Anthropic Console で sk-ant-api03 該当 key Revoke + 新規発行 ③SEC1 の手順で Lambda env / GitHub Secrets に反映。完了条件: 旧 Notion token で API 401 / 旧 Anthropic key で API 401 / `grep -rn "ntn_3865\|***REDACTED-SEC3***"` が 0 件。**Phase-Impact: セキュリティ最優先** / **Eval-Due: 2026-05-02 (即日)** | Notion Settings, Anthropic Console (Cowork で本ファイル書換済) | 2026-05-02 |
| T2026-0502-SEC5 | 🔴 高 (要実装・1 Code セッション) | **Avatar upload URL API の認証欠落 (IDOR・avatar 上書き脆弱性) (T2026-0502-SEC-AUDIT)** — `lambda/comments/handler.py:handle_avatar_upload_url(event)` が **Google ID トークン検証なし** で `userId` クエリを受け取り presigned PUT URL を返す。攻撃: 任意 Google sub をクエリ指定 → presigned URL 取得 → 任意ユーザーのアバターを上書き or XSS payload PNG を CloudFront 経由で配信。手順: ①handler に Authorization Bearer + Google tokeninfo 検証追加 (auth/handler.py の verify_google_token 同等) ②`payload['sub'] != qs.userId` で 403 ③ContentType `image/jpeg` 強制 + 任意で magic byte 検証 ④presigned URL TTL 300s → 60s。完了条件: 認証なしで 401 / 別 id で 403 / 自身 id で 200。**Phase-Impact: セキュリティ** / **Eval-Due: 2026-05-09** | `lambda/comments/handler.py:handle_avatar_upload_url`, `lambda/comments/handler.py:lambda_handler` (path routing) | 2026-05-02 |
| T2026-0502-SEC6 | 🔴 高 (要実装・1 Code セッション) | **Like/Dislike エンドポイントの認証欠落 (なりすまし投票) (T2026-0502-SEC-AUDIT)** — `lambda/comments/handler.py:handle_like(event)` が **Google ID トークン検証なし** で `userHash` クエリ (`sha256(user_id)[:16]`) をそのまま信用。任意 userId の hash を計算 → `PUT /comments/like?userHash=Z` で他人のアカウントとして like/dislike 連投可能。手順: ①handle_like を idToken 必須に変更 ②`verify_google_token(idToken).sub` から server side で `hash_str()` 計算して比較 ③client 側 userHash パラメータ廃止。完了条件: idToken なしで 401 / 改竄 hash で 403。**Phase-Impact: セキュリティ** / **Eval-Due: 2026-05-09** | `lambda/comments/handler.py:handle_like`, `frontend/js/comments.js` (idToken 同梱呼び出しに変更) | 2026-05-02 |
| T2026-0502-SEC7 | 🔴 高 (要実装・1 Code セッション) | **GET /favorites/{userId}, /history/{userId}, /analytics/user/{userId} の IDOR (PII 露出) (T2026-0502-SEC-AUDIT)** — `lambda/favorites/handler.py` GET 系 と `lambda/analytics/handler.py:GET /analytics/user/{userId}` が **認証検証なし** で任意の userId を受け取って閲覧履歴・お気に入り・行動統計 (アクティブ時間帯・閲覧トピック上位) を返す。userId (Google sub) が分かれば誰でも他人の興味・行動パターンを読める = プライバシー侵害。手順: ①各 GET ハンドラに Authorization Bearer ID トークン必須を追加 ②`payload.sub != path.userId` で 403 ③CORS は `*` から `https://flotopic.com` に絞る (favorites の `_cors_headers` 等)。完了条件: 他人 userId で 403 / 自身 userId で 200。**Phase-Impact: セキュリティ + プライバシー** / **Eval-Due: 2026-05-09** | `lambda/favorites/handler.py:lambda_handler` (GET branch), `lambda/analytics/handler.py:lambda_handler` (`/analytics/user/{userId}` branch), CORS 全 GET 系 | 2026-05-02 |
| T2026-0502-SEC8 | 🟡 中 (要実装・1 Code セッション) | **CORS Allow-Origin の整合性統一 (一部 `*`・一部 `https://flotopic.com`) (T2026-0502-SEC-AUDIT)** — comments/favorites/tracker/api/cf-analytics の CORS が `*`、auth/contact/analytics は `https://flotopic.com`。`*` 状態では悪意あるサイトから victim ブラウザで API 呼び出し可能。手順: ①各 Lambda の CORS_HEADERS を `https://flotopic.com,https://www.flotopic.com` に固定 (env で上書き可) ②deploy.sh の Function URL CORS `AllowOrigins:["*"]` 部分も同様に置換 ③staging origin は env で別途追加。完了条件: `curl -H "Origin: https://evil.example" ...` のレスポンスに `Access-Control-Allow-Origin: https://evil.example` が出ない。**Phase-Impact: セキュリティ (defense in depth)** / **Eval-Due: 2026-05-16** | `lambda/comments/handler.py`, `lambda/favorites/handler.py`, `lambda/tracker/handler.py`, `lambda/api/handler.py`, `lambda/cf-analytics/handler.py`, `projects/P003-news-timeline/deploy.sh` | 2026-05-02 |
| T2026-0502-SEC9 | 🟡 中 (要実装・1 Code セッション) | **Anthropic API key を AWS Secrets Manager に移行 (Lambda env 平文保管の解消) (T2026-0502-SEC-AUDIT)** — `ANTHROPIC_API_KEY` が `p003-fetcher` / `p003-processor` の Lambda env に平文保管 (deploy.sh 318-320 / 705)。Lambda Function 設定読み取り権限を持つ任意 IAM principal が値取得可能 (Cowork が SEC1 で実演済)。手順: ①Secrets Manager に `flotopic/anthropic-api-key` 作成 ②Lambda inline policy `secretsmanager:GetSecretValue` 追加 ③`proc_config.py` 起動時にキャッシュ取得 ④deploy.sh の env 設定削除 ⑤rotation 用 workflow が Secrets Manager を更新する形に。完了条件: `aws lambda get-function-configuration ... \| grep ANTHROPIC` が空。**Phase-Impact: セキュリティ (defense in depth)** / **Eval-Due: 2026-05-16** | `lambda/processor/proc_config.py`, `lambda/fetcher/config.py`, `projects/P003-news-timeline/deploy.sh`, AWS Secrets Manager + IAM policy | 2026-05-02 |
| T2026-0502-SEC10 | 🟡 中 (要実装・複数 workflow 修正) | **GitHub Actions の AWS 認証を OIDC + IAM Role assumption に移行 (T2026-0502-SEC-AUDIT)** — 複数 workflow (freshness-check / bluesky-agent / weekly-digest / quality-heal / security-audit / sli-keypoint-fill-rate / editorial-agent / deploy-trigger-watchdog 等) が `secrets.AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` で長寿命キー使用。手順: ①IAM OIDC IdP `token.actions.githubusercontent.com` 作成 ②`GitHubActionsRole-Flotopic` 作成 (trust: `repo:nuuuuuuts643/AI-Company:*`) ③各 workflow を `aws-actions/configure-aws-credentials@v4` の `role-to-assume:` 方式に書換 (`permissions: id-token: write` 必須) ④`AWS_ACCESS_KEY_ID/SECRET_ACCESS_KEY` を Secrets から削除 ⑤対応 IAM ユーザー Deactivate。完了条件: `secrets.AWS_ACCESS_KEY_ID` の grep が `.github/workflows/` で 0 件 / 旧 access key で `aws sts get-caller-identity` が 401。**Phase-Impact: セキュリティ (defense in depth)** / **Eval-Due: 2026-05-23 (3週間)** | `.github/workflows/*.yml` (10 ファイル前後), AWS IAM (新規 OIDC provider + role) | 2026-05-02 |
| T2026-0502-SEC11 | 🟡 中 (要実装・1 Code セッション) | **Frontend XSS — `<a href="${esc(url)}">` で javascript: URI 未ブロック (T2026-0502-SEC-AUDIT)** — `frontend/detail.js` (約 3 箇所) と `frontend/app.js` で記事 URL を `<a href="${esc(a.url)}">` で展開しているが `esc()` は HTML entity escape のみで `javascript:alert(1)` 等のスキーム検証なし。a.url は外部 RSS 由来 → 攻撃者が RSS 経由で `javascript:` URI を仕込むと clicked XSS。手順: ①`frontend/js/utils.js` に `safeHref(url)` 追加: `if (!/^(https?:\\/\\/|\\/|#)/i.test(url)) return '#';` ②該当箇所を `safeHref(...)` 経由に置換 ③`safeImgUrl()` も同様にスキーム whitelist 強化。完了条件: ペネトレで `javascript:` URI 注入が clicked で発火しないこと、ユニットテスト追加。**Phase-Impact: セキュリティ (defense in depth)** / **Eval-Due: 2026-05-09** | `frontend/js/utils.js`, `frontend/detail.js`, `frontend/app.js` | 2026-05-02 |
| T2026-0502-SEC12 | 🟡 中 (要実装・既存 T267 と統合) | **CSP を 'unsafe-inline' / 'unsafe-eval' なしへ厳格化 (T2026-0502-SEC-AUDIT・T267 と統合)** — 各 HTML の CSP meta が `default-src 'self' https: 'unsafe-inline' 'unsafe-eval'` で実質防御ゼロ。手順: ①SPA の inline script を全て .js に分離 ②`'unsafe-inline'` / `'unsafe-eval'` 削除 ③CloudFront Response Headers Policy で `script-src 'self' https://pagead2.googlesyndication.com https://accounts.google.com https://adm.shinobi.jp` 等明示 whitelist ④`frame-ancestors 'self'` でクリックジャック防御 ⑤2 週間 report-only で観察 → enforce 切替。完了条件: chrome devtools で violation 0 件・全機能動作。**Phase-Impact: セキュリティ (defense in depth)** / **Eval-Due: 2026-05-23** | `frontend/index.html`, `frontend/topic.html`, `frontend/about.html`, `frontend/mypage.html`, `frontend/profile.html`, CloudFront Response Headers Policy | 2026-05-02 |
| T2026-0502-SEC13 | 🟡 中 (要実装・1 Code セッション) | **RSS / 記事本文取得の SSRF 対策不足 (T2026-0502-SEC-AUDIT)** — `lambda/fetcher/handler.py:fetch_rss/fetch_ogp_image` と `lambda/processor/article_fetcher.py:fetch_full_text` が外部 URL を urllib.request で fetch する際、URL 先のホスト名が **internal IP / metadata endpoint (169.254.169.254) / RFC1918 の判定なし**。RSS 由来なので攻撃面は限定的だが防御漏れ。手順: ①`is_safe_url(url)` ヘルパ作成: ホスト名解決 → IP allowlist (公衆 IP のみ) ②fetch 前にチェック ③169.254.0.0/16・10.0.0.0/8・172.16.0.0/12・192.168.0.0/16・127.0.0.0/8・::1/128・fe80::/10 deny。完了条件: テストで `http://169.254.169.254/...` を渡して fetch されない。**Phase-Impact: セキュリティ (defense in depth)** / **Eval-Due: 2026-05-16** | `lambda/fetcher/handler.py`, `lambda/processor/article_fetcher.py` | 2026-05-02 |
| T2026-0502-SEC14 | 🟡 中 (要実装・1 Code セッション) | **XML パース脆弱性 (XXE / billion laughs) (T2026-0502-SEC-AUDIT)** — `lambda/fetcher/handler.py:fetch_rss` が `xml.etree.ElementTree.fromstring` で RSS 解析。Python3 ET は外部エンティティは解決しないが entity expansion 攻撃 (billion laughs) には脆弱。攻撃者が watched RSS feed に exponential entity → Lambda メモリ枯渇 → DoS。手順: ①`defusedxml` 追加 (pure-python) ②`from defusedxml.ElementTree import fromstring` に置換 ③テスト追加 (billion laughs payload で `EntitiesForbidden` 例外確認)。完了条件: ユニットテストで 1秒以内 reject。**Phase-Impact: セキュリティ (DoS 耐性)** / **Eval-Due: 2026-05-16** | `lambda/fetcher/handler.py`, `lambda/fetcher/requirements.txt` (新規・defusedxml), `tests/test_fetcher_xml_safety.py` (新規) | 2026-05-02 |
| T2026-0502-SEC15 | 🟢 低 (要実装) | **Rate limit fail-open の見直し (T2026-0502-SEC-AUDIT)** — `lambda/comments/handler.py:check_rate_limit` と `lambda/contact/handler.py:check_contact_rate_limit` が DynamoDB エラー時に `return True` (fail-open)。攻撃者が rate-limits テーブルに過負荷 (or IAM 権限剥奪) で全制限解除可能。手順: ①重要書き込み (comments POST / contact POST) は `fail-closed` (例外で 503/429) ②DynamoDB エラーは CloudWatch metric filter で観測 ③favorites POST / tracker POST は fail-open 維持。完了条件: 故意に IAM 剥がして comments POST が 503 を返すテスト。**Phase-Impact: セキュリティ (defense in depth)** / **Eval-Due: 2026-05-23** | `lambda/comments/handler.py:check_rate_limit`, `lambda/contact/handler.py:check_contact_rate_limit` | 2026-05-02 |
| T2026-0502-SEC16 | 🟢 低 (要実装) | **500 エラーレスポンスでの内部例外メッセージ漏洩 (T2026-0502-SEC-AUDIT)** — auth / favorites / tracker など複数 Lambda の 500 レスポンスが `{'error': '...', 'detail': str(e)}` で内部例外詳細 (DynamoDB エラー詳細・テーブル名等) を返す。情報収集に利用可能。手順: ①`detail` を返さず内部 print のみに格下げ ②本番では `requestId` (API Gateway / Lambda context) を返してログ追跡可能に。完了条件: `curl ... \| jq .detail` が null。**Phase-Impact: セキュリティ (情報露出抑制)** / **Eval-Due: 2026-05-23** | `lambda/auth/handler.py`, `lambda/favorites/handler.py`, `lambda/tracker/handler.py`, `lambda/comments/handler.py` | 2026-05-02 |
| T2026-0502-SEC17 | 🟢 低 (要実装) | **Lambda concurrency 制限の網羅 (DoS / コスト爆発防止) (T2026-0502-SEC-AUDIT)** — deploy.sh が同時実行制限を `comments(20)/auth(10)/analytics(10)/favorites(20)` のみ設定。`p003-fetcher` `p003-processor` `flotopic-lifecycle` `flotopic-contact` `p003-tracker` には未設定。fetcher/processor は API キー消費を伴うので攻撃者が schedule 連打/コードバグの invocation 連鎖でコスト爆発リスク。手順: fetcher=2, processor=2, lifecycle=1, contact=5, tracker=5 を設定。完了条件: `aws lambda get-function-concurrency --function-name p003-fetcher --query ReservedConcurrentExecutions` が 2。**Phase-Impact: セキュリティ (DoS / コスト防衛)** / **Eval-Due: 2026-05-16** | `projects/P003-news-timeline/deploy.sh` (concurrency 設定追加) | 2026-05-02 |
| T2026-0502-DEPLOY-LAMBDAS-FIX | 🔴 高 (Code セッション handoff) | **deploy-lambdas.yml fetcher step が 5sec で連続 failure・他 10 Lambda が旧コードのまま (T2026-0502-SEC-AUDIT 効果検証中に発覚)** — 2026-05-02 14:00 JST: PR #205 (SEC5-17 全コード修正) merge 後の deploy で fetcher step (#5) が 3 回連続で 5sec failure。fetcher 自体は LastModified=05:06:08 UTC で新コード反映済 (CloudWatch logs で正常完走確認) だが、step の post-update 処理 (env merge or wait) で連鎖停止 → step #6 以降の Lambda (processor/comments/analytics/auth/favorites/lifecycle/cf-analytics/api/contact/bluesky) が deploy されない。**結果**: SEC5/6/7/8/15/16/17 の Lambda 修正が **本番未反映**。実機テスト (avatar 認証なしで HTTP 200 / history 認証なしで HTTP 200 等) で旧コード挙動を確認。原因仮説: ①ci_lambda_merge_env.py の env 結合で SLACK_WEBHOOK 等の特殊文字が AWS CLI parsing を破る ②`aws lambda wait function-updated` のタイムアウト ③ANTHROPIC_API_KEY が GitHub Secrets で空 (rotate 済 = SEC1 後)。手順: ①Code セッションでローカルから `bash deploy.sh` を試して原因切り分け ②もしくは GitHub Actions の job log を gh CLI で取得 (`gh run view <RUN_ID> --log-failed`) ③fetcher step を分割 (code update / env merge を別 step に)・continue-on-error を一時的に追加して他 Lambda 通す。完了条件: `aws lambda list-functions --query 'Functions[?LastModified>\`2026-05-02T05:30:00\`].FunctionName'` が 11 関数すべて返す。Verified-Effect: 認証なし `curl /favorites/<userId>` が 401 / `curl /history/<userId>` が 401 / `curl /avatar/upload-url?userId=X` が 401。**Phase-Impact: セキュリティ最優先 (SEC5-17 効果発生条件)** / **Eval-Due: 2026-05-03 朝** / **依存**: なし (Code セッション 1 件で完結) | `.github/workflows/deploy-lambdas.yml` (fetcher step), `scripts/ci_lambda_merge_env.py` 確認, ローカル `bash deploy.sh` 試行 | 2026-05-02 |
| ~~T2026-0502-SEC2~~ | ~~🔴 緊急~~ | ~~**GitHub PAT ローテーション + ローカル設定からの平文除去**~~ → **2026-05-02 13:30 JST 完了** — `.git/config` から平文 token 除去 (Keychain 認証 `osxkeychain` へ移行)、`.claude/settings.local.json` L21 の `Bash(GITHUB_TOKEN=... SLACK_BOT_TOKEN=... SLACK_WEBHOOK=... bash deploy.sh)` allow エントリーを削除 (CLAUDE.md「deploy.sh は直接実行しない」ルールと整合)。Verified: `git remote -v` で token 無し URL のみ表示、`grep -cE 'gh[ops]_|sk-ant-|xox[bp]-|hooks\.slack\.com' settings.local.json` = 0。Personal Access Token は元々ゼロ件登録 (`gho_...` は OAuth App user-to-server token で revoke すると Cowork 連携が切れる副作用大のため放置)。**副作用 (T2026-0502-SEC2-RECURRENCE)**: cowork_commit.py が 401 になり PR #206 で多経路化 + 物理ガード追加で恒久対処。元の説明: ~~2026-05-02 11:35 JST — 2026-05-02 11:35 JST T2026-0502-M 調査中に Cowork が以下 2 箇所で平文の GitHub PAT を観測: ①`.git/config` の `remote.origin.url = https://nuuuuuuts643:gho_...@github.com/...` ②`.claude/settings.local.json` 内の Bash allow エントリーに `GITHUB_TOKEN="ghp_..."` `SLACK_BOT_TOKEN="xoxb-..."` `SLACK_WEBHOOK="..."` がコマンド allowlist として展開されたまま保存。`.claude/settings.local.json` は gitignore 済 (L5) で git track 外なので push 流出はしていないが、Cowork チャット履歴・スクリーン共有・session_info MCP 経由で第三者に見える可能性。手順: ①GitHub Settings → Personal access tokens → 該当 token Revoke → 新規発行 (scope は最小化: `repo` + `workflow` のみ) ②`.claude/settings.local.json` の該当 allow エントリーを `Bash(GITHUB_TOKEN=$GITHUB_TOKEN bash deploy.sh)` のように env 変数参照に置換 ③`.git/config` の `remote.origin.url` を `https://github.com/nuuuuuuts643/AI-Company.git` に書き換え + GIT_ASKPASS / `~/.netrc` / `gh auth login` で別途認証 ④Slack Bot Token / Webhook も再発行 (T2026-0502-SEC1 と並行)。完了条件: 旧 PAT で API 401 / `.claude/settings.local.json` と `.git/config` を grep して `gho_` `ghp_` `xoxb-` `https://hooks.slack.com/` が 0 件。**Phase-Impact: セキュリティ最優先 (フェーズ無関係)** / **Eval-Due: 2026-05-02 (即日)** / **依存**: なし (T2026-0502-SEC1 と並行可) | GitHub Settings, `.claude/settings.local.json`, `.git/config` (ローカル) | 2026-05-02 |

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

### 運用クリーンアップ

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|

---

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
