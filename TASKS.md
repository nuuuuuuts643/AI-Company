# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 🔥 今週やること（メインキュー・7件）

> **選定基準**: ユーザー体験に直結・安定性・AI品質・収益に近い順。
> **運用ルール**: ここに無いタスクは「アーカイブ（将来検討）」に格納。週次レビューで再優先順位付けする。
> **整理日**: 2026-04-28 (60+件のタスクから7件に絞り込み)

| ID | 優先 | 軸 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|---|
| T212 | 🔴 高 | AI品質 | **同一事象が複数トピックに分裂している** — 北海道地震で「北海道・三陸沖後発地震注意情報発表に伴う試合開催」と「北海道で震度5強の地震　津波の心配なし」が別トピックとして並立。同じ出来事の別角度の記事がクラスタリングで分離している。根本原因: fetcher のクラスタリング閾値が低すぎるか、タイトル類似度の計算が地名・数字の一致を十分に重視していない。調査方法: `lambda/fetcher/` のクラスタリングロジックを確認し、同一事象を同一トピックにまとめる閾値・ロジックを見直す。 | `lambda/fetcher/` | 2026-04-27 |
| T2026-0428-E | 🔴 高 | AI品質 | **AI 要約プロンプトを「自分ごと感」軸に改修** — 現状の AI 要約は「何が起きたか」中心で、ユーザーが「自分にどう関係するか」を判断できない。`lambda/processor/proc_ai.py` の `_STORY_PROMPT_RULES` と各 mode のプロンプトに以下4軸を追加: ① **自分ごと感**: 読者の生活・仕事・お金・安全のどこに影響するか1行で示す。② **誰が得して誰が損か**: 利害関係者を明示 (例: 「金利上昇 → 借り手が損・預金者が得」)。③ **専門用語→平易語**: 専門用語が出たら必ず括弧書きで平易化 (例: 「FOMC（米国の金融政策を決める会議）」)。④ **状況ラベル**: トピックの現状を「観測中 / 進行中 / 沈静化 / 決着」等のラベルで示す。output schema にも `personalImpact`/`stakeholders`/`statusLabel` フィールドを追加し、frontend で表示。 | `lambda/processor/proc_ai.py`, `frontend/detail.js`, `frontend/app.js` | 2026-04-28 |
| T2026-0428-F | 🟡 中 | 安定性・拡張性 | **topics.json 日付分割 Step1 インフラ準備** — 現状 207KB の topics.json がモバイル初回表示の最大 payload。115件で207KBなので、件数増加で線形増加する設計上の天井がある。**Step1 (本タスク)**: ① `/api/topics-card.json` (一覧用 minimal: tid/title/articleCount/genres/keyPoint/storyPhase/updatedAt) と `/api/topics-full.json` (現状互換) の2系統を proc_storage.py で生成する仕組みを作る。② frontend は当面 topics-full.json を使い続ける (互換維持)。③ governance worker に「topics.json size > 250KB」アラート追加。④ Brotli 圧縮を S3+CloudFront で確認。Step2 (別タスク化): card 表示を topics-card.json に切り替え + 日付別 shard。T265 を発展。 | `lambda/processor/proc_storage.py`, `.github/workflows/governance.yml`, CloudFront 設定 | 2026-04-28 |
| T191 | 🟠 高 | 体験 | **プロダクト体験の再設計: 「ストーリーを追う」フローを最初から最後まで設計する** — 根本問題: 現状はニュースリストにストーリー機能が「追加」されている状態。ユーザーが「経緯を追う体験」を最初から最後まで一度も中断せずにできる導線が存在しない。設計ゴール: ①トップ画面でストーリーの「動き」が見える ②1タップでその経緯に入れる ③読み終わったら「続きが来たら教える」で離脱できる。この3ステップを最短で完結させる UX フローを設計してから各機能を組み直す。コード変更より先に画面遷移フロー図を作ることが必要。 | 設計フロー図（コード変更は後続タスクで） | 2026-04-27 |
| T193 | 🟠 高 | 収益・習慣化 | **習慣化の仕掛けがない — 「毎日来る理由」を設計する** — 根本問題: ニュースアプリは習慣にならないと使われない。現状は思い出したときに来るだけで、「今日も Flotopic を開こう」というルーティンにする仕掛けが一切ない。候補: ①朝の「今日のトップ3ストーリー」メール (SES で送信可能) ② Bluesky 投稿を朝8時に「今日追うべき話」として設計する (現状は投稿内容が最適化されていない) ③「昨日から大きく動いたトピック」をトップに固定表示する (SNAP の差分で計算可能)。 | `scripts/bluesky_agent.py`, `lambda/processor/`, `frontend/` | 2026-04-27 |
| T2026-0428-J | 🔴 高 | AI品質 | **keyPoint/perspectives 充填率が success-but-empty (11.5% / 26.9%)** — 2026-04-28 06:10 schedule-task で発見。aiGenerated=True なのに必須フィールドが空のトピックが articleCount>=3 のうち 88.5% (46/52)。T255 で skip 条件は修正済 (handler.py L228 `_required_full_fields`) だが、本番反映には次 cycle (07/13/19 JST) での再処理 93 件が必要。**検証**: 13:00 JST cycle 完了後 (≈14:00 JST) に `freshness-check.yml` の ai_fields step 出力 (本タスクで追加済) を観測し SLI 8 (keyPoint 70%) 達成を確認。未達なら proc_ai.py プロンプトに keyPoint 必須化を追加する追加修正。**観測**: SLI 8/9/10 (`docs/sli-slo.md`)。 | `lambda/processor/proc_ai.py` (必要なら)、検証は外部観測のみ | 2026-04-28 |
| T2026-0428-V | 🔴 高 | 安定性 | **P0-STABLE-A: CI モバイルレイアウト基本チェック (横スクロール検知)** — 「壊れないようにする努力が足りない」指摘 (2026-04-28) を受けて P0 着手。Puppeteer で `index.html` を 375px 幅でレンダリングし `document.documentElement.scrollWidth > window.innerWidth` なら CI fail。`.github/workflows/ci.yml` に `mobile-layout-check` ジョブを追加。実装は `scripts/verify_effect.sh mobile_layout`（P0-STABLE-Y）経由。**完了条件**: PR で 375px 幅 overflow を検出した時 CI が落ちることを物理確認。 | `.github/workflows/ci.yml`, `scripts/verify_effect.sh` (新規), `scripts/check_mobile_layout.js` (新規) | 2026-04-28 |
| T2026-0428-W | 🔴 高 | 安定性 | **P0-STABLE-B: SLI アラートを Slack 通知に接続** — `freshness-check.yml` 既存。SLI 8/9 (keyPoint/perspectives 充填率) が `docs/sli-slo.md` に定義済だが、閾値割れで Slack 通知が出ない。`.github/workflows/freshness-check.yml` に「ai_fields step 出力 → 60% 未満で Slack webhook へ POST」を追加。Slack webhook URL は GH Secrets `SLACK_WEBHOOK_URL`。**完了条件**: 閾値割れを意図的に発生させた時 Slack に通知が届く。 | `.github/workflows/freshness-check.yml`, GH Secrets | 2026-04-28 |
| T2026-0428-Y | 🔴 高 | 安定性 | **P0-STABLE-D: 効果検証スクリプト `scripts/verify_effect.sh`** — Verified 行が「URL:200:timestamp」だけだとページが開くことしか証明していない。修正種別ごとに検証コマンドを標準化: ① `ai_quality` → topics.json から keyPoint/perspectives 充填率を計測 (60% 以上で OK)、② `mobile_layout` → puppeteer 375px 幅で scrollWidth==innerWidth 検証、③ `freshness` → topics.json updatedAt が 90 分以内。`CLAUDE.md` 「完了 = 動作確認済み」ルールに「効果検証スクリプトの結果を Verified 行に含める」を追記。**完了条件**: 3 fix_type すべて動作 + CI mobile-layout-check が本スクリプト経由。 | `scripts/verify_effect.sh` (新規), `scripts/check_mobile_layout.js` (新規), `CLAUDE.md` | 2026-04-28 |

---

## 📦 アーカイブ（将来検討）

> 上記「今週やること」以外のタスクをここに集約。週次レビューで必要なものをメインキューに昇格させる。
> **アーカイブ整理日**: 2026-04-28

### 将来機能（ユーザー増えてから）

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T056 | 低 | **フォロー/フォロワー機能**（将来・ユーザー増えてから） | — | 2026-04-26 |
| T109 | 低 | **アフィリエイト: トピック内容に合わせた関連商品表示（将来）** — 現状はジャンル固定キーワードで検索。AI要約生成時に商品検索クエリも同時生成して DynamoDB に保存し、トピックページに関連商品として表示できれば収益性向上。AI処理コスト増になるため収益化フェーズで検討 | `lambda/processor/proc_ai.py`, `frontend/js/affiliate.js` | 2026-04-26 |
| T154 | 中 | **お気に入りトピックへの新展開を Web Push 通知** — 根本原因: お気に入り登録しても次の展開を見に戻る動機がない。修正方法: ServiceWorker に Web Push 受信を追加。fetcher が既存お気に入り tid への新記事を検知 → DynamoDB notification_queue に積む → Lambda(notifier) が1日2回処理。ユーザー増加後の優先施策。 | `frontend/sw.js`, `frontend/mypage.html`, 新Lambda | 2026-04-26 |
| T201 | 低 | **bottom-nav の「リワインド」ラベルが初訪問ユーザーに意味不明** — 「リワインド」→「まとめ読み」または「振り返り」に変更検討 (要ナオヤ判断)。 | `frontend/catchup.html`, `frontend/index.html`, `frontend/storymap.html`, `frontend/topic.html`, `frontend/mypage.html` | 2026-04-27 |
| T217 | 低 | **footer 著作権「© 2024-2026」の妥当性（ナオヤ確認）** — about.html 開発開始年は 2026 に修正済み。残るは全ページ footer 表記。要ナオヤ判断後に統一。 | 全 *.html footer | 2026-04-27 |

### プロダクト戦略（メインキュー昇格候補）

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T192 | 高 | **ジャンル戦略: 全ジャンル対応から1-2ジャンル集中に絞る検討** — SmartNews・グノシー等との全ジャンル競合では差別化できない。Flotopic が「このジャンルなら Flotopic」と言われる領域がない。現状の PV・お気に入り登録をジャンル別に集計し、最も使われているジャンルを特定。 | `CLAUDE.md`（方針決定後） | 2026-04-27 |

### リーガル・コンプライアンス

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T224a | 高 | **admin.html の `allowedEmail` フロント直書き対応** — T224 残課題。`frontend/admin.html:296` の `allowedEmail` 直書きは公開ファイルでスピアフィッシング情報として漏洩中。build 時注入機構 (env→HTMLテンプレート置換) を作る大改修。暫定運用は admin.html を CloudFront で IP 制限など。 | `frontend/admin.html` | 2026-04-28 |
| T225 | 中 | **tokushoho.html 残存** — Cowork 範囲外 (FUSE マウントで物理削除不可)。Code セッションで `git rm projects/P003-news-timeline/frontend/tokushoho.html` + CloudFront キャッシュパージ + Search Console URL 削除リクエスト + CI に「frontend に tokushoho.html が存在しないこと」チェック追加。 | `frontend/tokushoho.html`（削除）, CI チェック | 2026-04-28 |

### セキュリティ・運用堅牢性

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T229 | 低 | **admin.html フロントだけのメール突合は装飾、信頼すべきではない事の明文化** — 攻撃者が DevTools で `CONFIG.allowedEmail` を書き換えれば UI は通る。バックエンドでちゃんと検証しているので致命的ではないが、analyticsUrl / cf-analyticsUrl は認証なしで取得可能。「フロントの認証は UX のため」とコメントを残すか、analytics エンドポイントにも Bearer 検証を追加するか方針を決める。 | `frontend/admin.html`, `lambda/cf-analytics/`, `lambda/analytics/` | 2026-04-28 |
| T252 | 中 | **CSP に unsafe-inline + unsafe-eval が設定されている — XSS 攻撃面拡大** — 全 HTML の CSP meta が `default-src 'self' https: 'unsafe-inline' 'unsafe-eval'`。理由は ld+json / inline style / Google Sign-In ライブラリが eval を使うため。コメント Lambda 側で sanitize しているなら被害は限定的だが、defense-in-depth 観点では弱い。段階的に `unsafe-eval` 削除 → inline style 外部化 → nonce/hash 化 を進める。 | `frontend/*.html` 全 CSP meta | 2026-04-28 |
| T267 | 中 | **CSP meta タグはあるが HTTP Response Header に CSP が無い — meta タグの限界** — HTML meta タグの CSP は対応ブラウザ・ドメイン制限・frame-ancestors 不対応など機能制限あり。CloudFront Response Headers Policy に `content-security-policy-report-only` で report-only mode で追加 → 1-2 週間 violation を観測 → 大きな違反が無ければ enforce mode に切替。 | CloudFront Response Headers Policy, 新規 `lambda/csp_report/` | 2026-04-28 |

### UI/UX

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|

### 安定性・運用

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T236 | 中 | **governance worker の品質メトリクス実装状況棚卸し** — CLAUDE.md には「クラスタリング 2-3件トピック比率70%超で Slack 警告」「perspectives 0% 充填で Slack 警告」「processed 件数 / wallclock 残秒 / 1call 平均所要秒」が仕組み的対策として記載されているが、`scripts/_governance_check.py` で実装されているか未検証。実装されていなければ「対策3つ書いた」だけで再発防止が動いていない。 | `scripts/_governance_check.py`, `.github/workflows/governance.yml` | 2026-04-28 |
| T237 | 中 | **AI生成カバレッジの根本原因調査** — TASKS.md「P003 技術状態スナップショット」で「pending queue 優先度問題 (T213) が根本原因」と書かれているが T213 が見当たらない (既に番号衝突か履歴へ移動)。proc_storage.py の `get_pending_topics` を読み、Tier-0 (topics.json 可視 × aiGenerated=False) を最優先で返しているか・DynamoDB scan の order 保証があるか実機確認する。T218 wallclock guard が反映されれば自動解消される可能性も含めて再評価。 | `lambda/processor/proc_storage.py`, `lambda/processor/handler.py` | 2026-04-28 |
| T238 | 低 | **processor handler.py の特殊モード分岐が肥大化（300+行）** — `lambda/processor/handler.py:60-150` に `regenerateStaticHtml` / `backfillDetailJson` / `backfillArchivedTtl` / `purgeAll` / `forceRegenerateAll` / `regenerateSitemap` の6つの特殊モードが連結 if 文で並ぶ。テスト・保守・新モード追加が困難。`proc_admin_modes.py` に分離。 | `lambda/processor/handler.py` (新規ファイル) | 2026-04-28 |
| T254 | 中 | **style.css / app.js が `no-cache, must-revalidate` で CDN/ブラウザキャッシュ無効化されている** — Lighthouse スコア・帯域コスト低下。HTML は正解だが、JS/CSS は content-hash バージョニング (`app.js?v=abc123`) すれば長期キャッシュ可能。deploy-p003.yml で JS/CSS に長期キャッシュ (max-age=31536000, immutable) を設定し、`?v=${GITHUB_SHA::7}` で書き換え。 | `.github/workflows/deploy-p003.yml`, `frontend/*.html` の `<script src=>` / `<link href=>` | 2026-04-28 |
| T260 | 中 | **個別 topic JSON の `data['meta']` で aiGenerated=False の topic も生成されている** — `https://flotopic.com/api/topic/8f81be6586cbea09.json` は `aiGenerated=False` で meta が `{aiGenerated, topicId}` の 2 フィールドだけ。空の個別 JSON が量産。`update_topic_s3_file` で `aiGenerated=False` かつ generatedTitle 等が無いトピックは個別 JSON 生成をスキップ。 | `lambda/processor/proc_storage.py` update_topic_s3_file | 2026-04-28 |
| T265 | 中 | **topics.json が 207KB と肥大化 — モバイル初回表示帯域コスト** — T2026-0428-F (Step1) の発展タスク。Step2: card 表示を topics-card.json に切り替え + 日付別 shard。 | `lambda/processor/proc_storage.py`, `frontend/app.js`, CloudFront 設定 | 2026-04-28 |

### 収益・拡張

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T240 | 低 | **Cloudflare Web Analytics トークンがフロントに直書き** — index.html / topic.html 等の最後で `data-cf-beacon='{"token": "..."}'` がハードコード。これは CF 側仕様で公開するもので問題はないが、サブドメインや別環境を増やす際にビルド時 env 注入する設計が無い点だけメモ。 | `frontend/*.html` | 2026-04-28 |
| T241 | 低 | **アフィリエイトのセンシティブトピック自動非表示ロジック未実装** — CLAUDE.md「過去の設計ミスパターン」⑧で「事件・事故・医療・政治では非表示にする」とルール明記済み。affiliate.js で genre が `'社会'`/`'国際'`/`'健康'` × 記事タイトルが事件/事故/疾患キーワードを含む時は出さない実装が必要。AdSense 通過後・収益性確認後でよい。 | `frontend/js/affiliate.js`（推定）, `frontend/topic.html` | 2026-04-28 |
| T253 | 低 | **AI 学習クローラー全禁止 vs AI Visibility (AEO/GEO) のトレードオフ判断** — `robots.txt` で GPTBot / ChatGPT-User / Claude-Web / anthropic-ai / Google-Extended / PerplexityBot / Applebot-Extended / CCBot 全て Disallow。ChatGPT/Perplexity で「Flotopic」の名前を引いた時に検索結果に出てこない機会損失が発生。AI生成要約の知的財産価値 vs AEO/GEO 流入の機会値を Naoya 判断。 | `frontend/robots.txt`, `searchfit-seo:ai-visibility` | 2026-04-28 |

### 運用ガバナンス（Cowork×Code 連携）

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T256 | 中 | **AI フィールドの「層を1つ忘れる」を CI で物理検出する仕組み不在** — T249 (keyPoint・backgroundContext merge 漏れ) は手動調査で発見。`.github/workflows/ai-fields-coverage.yml` 新規。proc_ai.py の input_schema を grep して field 名一覧を抽出 → handler.py merge ループの両方に同名キーがあるか check → 欠落あれば CI ERROR。 | `.github/workflows/ai-fields-coverage.yml` 新規, `scripts/check_ai_fields_coverage.py` 新規 | 2026-04-28 |
| T258 | 中 | **「発端」storyPhase 50% 偏り (本番) — T219 修正前の旧データが残る** — 本番 topics.json で storyPhase 分布 = 拡散 23 / 発端 57 / ピーク 9 / 現在地 4 / null 21。T219 prompt 修正で「記事3件以上で発端禁止」を入れたが、aiGenerated=True 旧 topic は skip されるため反映されない。完了判定: T255 修正＋forceRegenerateAll 1-2 回後、storyPhase 分布が正規化。 | (T255 で連動解消) | 2026-04-28 |
| T259 | 低 | **`Cache-Control: max-age=60` の topics.json が 90 分後鮮度警告と整合しない** — T263 実装時に「鮮度=updatedAt フィールド差分」「Cache-Control= edge cache TTL」の違いを混同しないこと。両者は別軸。 | T263 実装時に注意点として明記 | 2026-04-28 |
| T262 | 中 | **プライバシーポリシー・利用規約が `noindex` だが SEO 上の表示・検索性は OK か再確認** — privacy.html / terms.html は `noindex` 設定なし (現在は indexable)。Search Console で `site:flotopic.com` 検索し、privacy/terms が結果に出るか確認。 | Search Console 確認 | 2026-04-28 |
| T264 | 中 | **`.claude/worktrees/` に 6 個の stale 作業ツリーが残存** — `awesome-varahamihira-c01b2e` `happy-khorana-4e3a6c` `naughty-saha-ba5901` `quirky-cohen-c1efbd` `serene-hermann-993255` `vigilant-fermi-4e0a09`。WORKING.md TTL 8h ルールはメインの WORKING.md にしか適用されていない。起動チェック script に worktree クリーンアップ候補一覧表示 + 物理スクリプト化 + `.gitignore` 追加。 | `CLAUDE.md` 起動チェック, `scripts/cleanup_stale_worktrees.sh` 新規 | 2026-04-28 |
| T2026-0428-P | 中 | **system-status.md と SLI 実測の二重管理問題 (T266 と統合)** — schedule-task 06:10 で 312KB 記載 vs 218KB 実測 (Δ94KB)・80.2% 記載 vs 79.5% 実測 (0.7pp) の数値齟齬を発見。T266 と問題本質は同じだが、本タスクは構造改善 (auto-commit 仕組み) に焦点。`docs/system-status.md` は方針スナップショット (人間更新)・`docs/sli-slo.md` の「現状実測」は機械観測値で、両者が「現状値」を抱えて二重管理。**仕組み的対策**: ① freshness-check.yml 出力で system-status.md 該当行を sed で auto-commit、② CLAUDE.md「規則の置き場所」表に責務境界明示、③ ファイル命名で `*-live.md` suffix 化検討。詳細なぜなぜ: `docs/lessons-learned.md` 2026-04-28 06。本 schedule-task で記載値は実測値に修正済 (band-aid)。 | `.github/workflows/freshness-check.yml`, `docs/system-status.md`, `CLAUDE.md` | 2026-04-28 |
| T2026-0428-Q | 中 | **success-but-empty 抽象パターンの他コンポーネント横展開スキャン** — schedule-task 06:10 で keyPoint 充填率 11.5% を「aiGenerated フラグだけ見る SLI」が素通りしたことから、他にも success-but-empty パターンが潜む箇所をスキャン。要監視リスト: ① fetcher の articleCount=0 cycle、② processor の processed=0 cycle、③ bluesky_agent の post 失敗、④ SES の bounce、⑤ CloudFront 5xx、⑥ CI green-but-skipped (テスト skip 全合格扱い)、⑦ topic 個別 JSON の meta=2フィールドだけパターン (T260 既知)。1 件ずつ「観測 SLI が存在するか」を埋めて lessons-learned に集約。詳細: `docs/lessons-learned.md` 2026-04-28 06。 | `docs/sli-slo.md`, `.github/workflows/freshness-check.yml`, `scripts/_governance_check.py` | 2026-04-28 |
| T2026-0428-R | 中 | **ai_fields step の出力で system-status.md 該当行を auto-commit** — T2026-0428-P の具体実装。`freshness-check.yml` の ai_fields step に `apply-status-update` ジョブを追加。bot user で push (committer は `flotopic-freshness-bot`)。差分が 1 行以下の場合のみ commit (大量変更で誤書き換えを防ぐ)。実装後は手動更新を廃止し「機械観測値だけが正本」に統一。 | `.github/workflows/freshness-check.yml` | 2026-04-28 |
| T266 | 低 | **`docs/system-status.md` の AI 要約カバレッジ「24.6%」が古い情報** — 04-28 17:15 時点の実測は 115 件中 aiGenerated=True 93 件 (80.9%)。各メトリクス行に `> measured: ... by curl ... | jq ...` を併記 + `scripts/refresh_system_status.sh` で毎日自動更新 (GH Actions 03:00 JST cron)。古い数字は CI 警告 (mtime > 7 日)。 | `docs/system-status.md`, `scripts/refresh_system_status.sh` 新規 | 2026-04-28 |
| T261 | 低 | **ads.txt の重複行確認 (CI 追加候補)** — T239 既存タスクと統合。CI で `index.html` の `data-ad-client=ca-pub-NNN` から AdSense pub-id 自動抽出 → ads.txt 整合性チェック。 | T239 と統合 | 2026-04-28 |
| T2026-0428-K | 🟡 中 | **環境スクリプトの dry-run CI 化** — 2026-04-28 04:15 schedule-task で session_bootstrap.sh / triage_tasks.py に session-id ハードコードと UTC を JST と誤ラベルする bug が同時露見。lessons-learned「環境スクリプトに session ID hardcode」記録。修正は同 commit で landing 済だが、再発防止として `scripts/session_bootstrap.sh --dry-run` を GH Actions 日次実行 → REPO 検出 / JST 表示 / WORKING.md 未来日付 stale 検出ロジックを物理 test。Claude が次セッションで気付くループを CI で前倒しに切り替える。 | `.github/workflows/env-scripts-dryrun.yml` 新規, `scripts/session_bootstrap.sh` (`--dry-run` 引数追加) | 2026-04-28 |
| T2026-0428-S | 🟢 低 | **contact.html が noindex 設定 — E-E-A-T 上は indexable が望ましいか再判断** — 2026-04-28 07:13 schedule-task で curl 確認、`<meta name="robots" content="noindex">` 設定。連絡先ページは Google E-E-A-T 評価で「Trust」シグナル源。AdSense 審査でも contact 有無は評価対象。**懸念**: 現状 noindex のため検索結果に出ない → 信頼性シグナルとして検索エンジンに認識されない可能性。**判断材料**: SES 受信専用フォームで spam リスクが高いから noindex にしているなら維持、純粋な連絡先表示なら indexable に変更。要ナオヤ確認後に変更検討。 | `frontend/contact.html` | 2026-04-28 |
| T2026-0428-T | 🟢 低 | **AI フィールドカタログと proc_ai.py schema の CI 突合** — T256 の具体実装。2026-04-28 07:13 で `docs/ai-fields-catalog.md` 新規作成完了。次は `scripts/check_ai_fields_catalog.py` を新規作成し、`proc_ai.py:_build_story_schema` の field 名 (mode=full) を抽出 → カタログ先頭表の field 名一覧と diff → 乖離があれば exit 1。`.github/workflows/ci.yml` で main push 時に実行。「フィールド追加したらカタログも更新」を物理ガード化。 | `scripts/check_ai_fields_catalog.py` 新規, `.github/workflows/ci.yml` | 2026-04-28 |
| T2026-0428-U | 🟢 低 | **個別 topic JSON (L4b) の AI フィールド充填率 SLI** — `_PROC_INTERNAL = {spreadReason, forecast, storyTimeline, backgroundContext}` は topics.json publish 時に除外され、これらは個別 `api/topic/{tid}.json` (L4b) でのみ観測可能。現状 SLI 8/9/10 は L4a (topics.json) のみ。`scripts/check_ai_fields_coverage.sh` を sample N=10 個別 JSON 取得 → backgroundContext / spreadReason / forecast / timeline 充填率を集計 → SLI 11/12/13 として登録。詳細: `docs/ai-fields-catalog.md`, lessons-learned 2026-04-28 07:13。 | `scripts/check_ai_fields_coverage.sh`, `.github/workflows/freshness-check.yml`, `docs/sli-slo.md` | 2026-04-28 |
| T2026-0428-L | 🟢 低 | **`scripts/security_headers_check.sh` 新設 + CI 化** — T251 検証で「2026-04-28 04:20 時点で全付与済」を確認したが、CloudFront response headers policy の drift を外部観測する仕組みが無い。GH Actions cron で毎日 `curl -sI https://flotopic.com/` を取得し HSTS / X-Frame-Options / Permissions-Policy / Referrer-Policy / X-Content-Type-Options が消えていれば Slack 警告。SLI 8 として登録。 | `scripts/security_headers_check.sh` 新規, `.github/workflows/security-headers-check.yml` 新規, `docs/sli-slo.md` SLI 8 追記 | 2026-04-28 |
| T2026-0428-M | 🟠 高 | **本番 topics.json の keyPoint 充填率 0/114 (T249/T255 修正済だが production に反映されていない)** — 2026-04-28 04:18 JST に `curl https://flotopic.com/api/topics.json` を直接 jq した結果、`keyPoint` フィールドを持つ topic が 0 件。一方で `aiGenerated=True` は 93/114 (81.5%)、`storyPhase` は 93/114 で充填済 (NULL=21 残る)。handler.py で T249 (keyPoint merge 漏れ) は L312 で修正済、T255 (必須フィールド skip 防止) は L228-232 で修正済。原因仮説: ① Lambda の deploy 反映遅延、② AI が keyPoint フィールドを返さず空のまま、③ proc_storage の merge logic が topics.json publish 前に keyPoint を strip。`_PROC_INTERNAL` には keyPoint は入っていない (L30) のため ③ は否定。要 CloudWatch ログ確認 + DynamoDB の任意 topic で keyPoint カラムが入っているか直接検証。 | `lambda/processor/handler.py`, `lambda/processor/proc_storage.py`, CloudWatch | 2026-04-28 |
| T2026-0428-N | 🟠 高 | **AI フィールド充填率 SLI 化 + 外部観測 cron 新設** — 2026-04-28 05:13 JST 観測で本番 keyPoint=8.5% / perspectives=20.5% / outlook=49.6% / relatedTopicTitles=24.8% (117件中)。`docs/sli-slo.md` には「AI 要約あり/なし」二値しか SLI 化されておらず、フィールド単位の失敗モード差が外部観測されない。仕組み: ① `scripts/check_ai_fields_coverage.sh` 新設 → 本番 topics.json を curl して keyPoint/perspectives/outlook/relatedTopicTitles 充填率を JSON 化 ② `.github/workflows/ai-fields-coverage.yml` で 6h cron 実行 ③ 閾値 (keyPoint 50%, perspectives 60%, outlook 70%) 割れで Slack 警告 ④ docs/sli-slo.md SLI 9 として登録。governance worker と並列の外部観測。 | `scripts/check_ai_fields_coverage.sh` 新規, `.github/workflows/ai-fields-coverage.yml` 新規, `docs/sli-slo.md` SLI 9 | 2026-04-28 |
| T2026-0428-O | 🟠 高 | **大規模クラスタ (articles>=10) で aiGenerated=False が放置される** — 2026-04-28 05:13 JST 観測で「福島・喜多方市で山林火災発生 (記事19件)」「後発地震の想定…M8級以上 (記事15件)」が aiGenerated=None / phase=None / mode=None のまま topics.json トップに並ぶ。T237 で起票した「Tier-0 = topics.json 可視 × aiGenerated=False」優先処理が proc_storage.get_pending_topics で実装されている (L376-420) ものの、本番では Tier-0 を消化しきれていない。仮説: ① pendingAI flag の永続化漏れ ② DynamoDB scan の order 不安定 ③ Tier-0 件数 > 1 サイクル MAX_API_CALLS。`scripts/check_ai_fields_coverage.sh` (T2026-0428-N) と並列に「articles>=10 × aiGenerated=False の件数」も SLI 化して可視化する。修正は本タスクで proc_storage に「Tier-0 を必ず先頭で取り切る」固定 budget 確保ロジックを追加 (例: 残り wallclock の 50% は Tier-0 のみに使う)。 | `lambda/processor/proc_storage.py`, `lambda/processor/handler.py` | 2026-04-28 |
| T2026-0428-S | 🟡 中 | **`generatedTitle` に markdown `# / *` 残骸が残るレガシートピック** — 2026-04-28 05:13 JST 観測で `# 鈴木誠也が佐々木朗希から本塁打、カブス連勝中の活躍続く` (full mode topic) が title 先頭に `#` を持つ。fix commit `b5c36b0: fix(P003): generate_title で markdown 残骸 (# / *) を strip` 適用前に生成された aiGenerated=True topic は再生成 skip 条件で永続。一括 sanitize: `lambda/processor/handler.py` の admin mode `forceRegenerateAll` を一度実行する or `proc_storage.py update_topic_s3_file` 呼び出し前に title から `^\s*[#*]+\s*` を strip する band-aid を入れる (band-aid は CLAUDE.md ルールで本来禁止だが「過去データ補正」用途として一時許容、補正完了後に削除)。 | `lambda/processor/proc_storage.py` or admin `forceRegenerateAll` 実行 | 2026-04-28 |
| T2026-0428-T | 🟡 中 | **`backgroundContext` が `_PROC_INTERNAL` で topics.json から除外されているが個別 topic JSON でも空の topic がある可能性** — 2026-04-28 05:13 JST 観測で topics.json の backgroundContext は 0%。これは `lambda/processor/handler.py:30` `_PROC_INTERNAL = {..., 'backgroundContext'}` で意図的に publish 時除外 (size 抑制) であり仕様通り。ただし frontend は個別 topic JSON (`/api/topic/<tid>.json`) から backgroundContext を読む設計のため、個別 JSON 側の充填率検証が必要。任意 5 topic を curl して backgroundContext 値があるか確認 → 無ければ proc_ai schema or merge ループに別の漏れあり。確認方法は SLI 9 (T2026-0428-N) の cron で個別 JSON 5 件 sampling。 | (T2026-0428-N に統合) | 2026-04-28 |
| T2026-0428-U | 🟡 中 | **storyPhase 「発端」が aiGenerated=True 中 58% (54/93) — T219 修正後も改善せず** — 本番観測 2026-04-28 05:13 JST: 拡散29 / 発端54 / ピーク5 / 現在地5 / NULL24。T219 で minimal mode を `phase=None` 化、standard/full mode は「記事3件以上で発端禁止」を prompt 強化済。しかし aiGenerated=True 旧 topic の skip 条件 (`aiGenerated=True かつ keyPoint がある or minimal`) で再生成されないため、永続的に「発端」が混入する。T255 修正は keyPoint missing を skip 対象から外したが、storyPhase は「null以外なら OK」のため発端旧topic は依然 skip。修正: skip 条件に「storyPhase=='発端' で articleCount>=3 なら再生成」を追加。 | `lambda/processor/proc_storage.py` get_pending_topics または handler skip ロジック | 2026-04-28 |

### SLI/SLO 設計

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|

---

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
