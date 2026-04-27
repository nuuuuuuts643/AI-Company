# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 未着手（実装待ち）

取得手順: `git pull --rebase && cat TASKS.md` で確認後、WORKING.md に宣言して着手。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T056 | 低 | **フォロー/フォロワー機能**（将来・ユーザー増えてから） | — | 2026-04-26 |
| T109 | 低 | **アフィリエイト: トピック内容に合わせた関連商品表示（将来）** — 現状はジャンル固定キーワードで検索。AI要約生成時に商品検索クエリも同時生成してDynamoDBに保存し、トピックページに関連商品として表示できれば収益性向上。AI処理コスト増になるため収益化フェーズで検討 | `lambda/processor/proc_ai.py`, `frontend/js/affiliate.js` | 2026-04-26 |

### 🐛 バグ修正（高優先）

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T212 | 高 | **同一事象が複数トピックに分裂している**（旧T207・IDコリジョン回避のためリナンバー）— 北海道地震で「北海道・三陸沖後発地震注意情報発表に伴う試合開催」と「北海道で震度5強の地震　津波の心配なし」が別トピックとして並立。同じ出来事の別角度の記事がクラスタリングで分離している。根本原因: fetcherのクラスタリング閾値が低すぎるか、タイトル類似度の計算が地名・数字の一致を十分に重視していない。調査方法: `lambda/fetcher/` のクラスタリングロジックを確認し、同一事象を同一トピックにまとめる閾値・ロジックを見直す。 | `lambda/fetcher/` | 2026-04-27 |
| T217 | 低 | **footer著作権「© 2024-2026」の妥当性（ナオヤ確認）** — about.html 開発開始年は 2026 に修正済み(commit `30aff22`)。残るは全ページfooter「© 2024-2026 Flotopic」表記。git実装は2026-04-20開始だが、ブランド検討期間を含めるなら 2024 起点もあり得る。ナオヤ判断後に統一。 | 全 *.html footer | 2026-04-27 |
| ~~T218~~ | ~~高~~ | ~~大規模トピック AI 未生成~~ → **Cowork実装完了 (2026-04-28 01:30 JST)・Code push & 本番反映待ち**。根本原因: Lambda 900s timeout で in-flight 中断 → S3書き戻しフェーズ未実行 → aiGenerated=True が topics.json に反映されない。修正: handler.py 主ループに wallclock guard (120s残し) を追加。CLAUDE.md にWhy1〜Why5+仕組み的対策5+恒久ルール1行追記済み。検証手順: Code 起動 → push → GH Actions で Lambda 反映 → 次回スケジュール (JST 07:00/13:00/19:00) → CloudWatch で `Wallclock guard 到達` ログを確認 → topics.json で aiGenerated=False 0件 + perspectives 充填率 standard/full 80%+ を確認。完了したら HISTORY.md へ移動。 | `lambda/processor/handler.py`, `CLAUDE.md` | 2026-04-27 |
| ~~T219~~ | ~~中~~ | ~~storyPhase「発端」過剰判定~~ → **Cowork実装完了 (2026-04-28 02:50 JST)・Code push & 本番反映待ち**。修正: ①minimal mode で phase=null ②standard/full prompt 強化「記事3件以上で発端禁止、デフォルト拡散」 ③normalize 層で AI が発端を返したら拡散に矯正 (contract enforcement)。完了判定: 次回 fetcher サイクルで phase 分布が「発端 0%、null 約 50% (=minimal mode)、拡散/ピーク/現在地 約 50%」 → HISTORY.md 移動。 | `lambda/processor/proc_ai.py` | 2026-04-27 |
| ~~T220~~ | ~~中~~ | ~~3フィールド main未マージ~~ → **調査完了 (2026-04-28 01:30 JST)・Cowork判定: T218 と同根**。確認結果: lambda/processor/proc_ai.py には backgroundContext/perspectives/outlook の input_schema 定義 (Tool Use) と _normalize_story_result 反映が main にマージ済み。handler.py の ai_updates と topics.json 反映ループにも該当キー実装済み。frontend/detail.js (line 268-273, 322-431) では minimal/standard/full 全モードでレンダリング実装済み。**本当の原因は T218 (Lambda timeout で topics.json 更新が走らないため 0% 充填に見えていた)**。T218 fix の本番反映後、次回スケジュールで topics.json が再生成されれば自動的に値が入る。完了判定: T218 修正反映後、topics.json で summaryMode=standard/full の backgroundContext/perspectives/outlook が 70%+ 充填確認 → HISTORY.md 移動。 | (実装は既存・T218反映で連動解消) | 2026-04-27 |

### 🎯 使いたくなるUX（「また来たい」動線）

> 安定性改善と並行して進める。Flotopicの差別化はストーリー追跡体験にある。それが伝わる動線を作る。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T201 | 低 | **bottom-navの「リワインド」ラベルが初訪問ユーザーに意味不明** — 根本原因: bottom-navのラベルが「🕰️ リワインド」のみで、初訪問ユーザーは「リワインド」が何をする機能か分からずタップ動機が生まれない。catchup.htmlのheroには「あなたが離れていた間のニュースを時系列でお届け」と説明があるが、そこに到達するまで機能の価値が不明。競合（SmartNews等）では「おかえり」「まとめ読み」等の直感的なラベルを使う。影響: bottom-navのリワインドタップ率が低い可能性。修正方法: 「リワインド」→「まとめ読み」または「振り返り」に変更、もしくはhero内のsubラベルだけでも変更（コスト最小）。要ナオヤ判断（ブランド用語の変更）。 | `frontend/catchup.html`, `frontend/index.html`, `frontend/storymap.html`, `frontend/topic.html`, `frontend/mypage.html` | 2026-04-27 |
| T154 | 中 | **お気に入りトピックへの新展開をWeb Push通知** — 根本原因: お気に入り登録しても次の展開を見に戻る動機がない。修正方法: ServiceWorkerにWeb Push受信を追加。fetcherが既存お気に入りtidへの新記事を検知→DynamoDB notification_queueに積む→Lambda(notifier)が1日2回処理。ユーザー増加後の優先施策。 | `frontend/sw.js`, `frontend/mypage.html`, 新Lambda | 2026-04-26 |

### ⚙️ 運用・管理改善

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|

### 📈 成長・SEO施策

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|

### 🧭 プロダクト課題（体験設計）

> 技術的に動いているが、ユーザーに「刺さる」体験になっていない問題群。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T191 | 高 | **プロダクト体験の再設計: 「ストーリーを追う」フローを最初から最後まで設計する** — 根本問題: 現状はニュースリストにストーリー機能が「追加」されている状態。ユーザーが「経緯を追う体験」を最初から最後まで一度も中断せずにできる導線が存在しない。設計ゴール: ①トップ画面でストーリーの「動き」が見える ②1タップでその経緯に入れる ③読み終わったら「続きが来たら教える」で離脱できる。この3ステップを最短で完結させるUXフローを設計してから各機能を組み直す。コード変更より先に画面遷移フロー図を作ることが必要。 | 設計フロー図（コード変更は後続タスクで） | 2026-04-27 |
| T192 | 高 | **ジャンル戦略: 全ジャンル対応から1-2ジャンル集中に絞る検討** — 根本問題: SmartNews・グノシー等との全ジャンル競合では差別化できない。Flotopicが「このジャンルならFlotopic」と言われる領域がない。調査: 現状のPV・お気に入り登録をジャンル別に集計し、最も使われているジャンルを特定。そのジャンルのコンテンツ品質（AI要約カバレッジ・ソース多様性）を重点強化する。他ジャンルは維持しつつ、マーケティング・SEO施策はリード1-2ジャンルに集中。 | `CLAUDE.md`（方針決定後） | 2026-04-27 |
| T193 | 高 | **習慣化の仕掛けがない — 「毎日来る理由」を設計する** — 根本問題: ニュースアプリは習慣にならないと使われない。現状は思い出したときに来るだけで、「今日もFlotopicを開こう」というルーティンにする仕掛けが一切ない。候補: ①朝の「今日のトップ3ストーリー」メール（SESで送信可能）②Bluesky投稿を朝8時に「今日追うべき話」として設計する（現状は投稿内容が最適化されていない）③「昨日から大きく動いたトピック」をトップに固定表示する（SNAPの差分で計算可能）。 | `scripts/bluesky_agent.py`, `lambda/processor/`, `frontend/` | 2026-04-27 |

---

## 2026-04-28 多角棚卸し（Cowork スケジュール調査）

> スケジュールタスク「実態を調査し課題を洗い出してタスク化」の出力。
> 観点: リーガル・運用・保守・UI/UX・収益・拡張性・安定性。
> 調査範囲: `frontend/*.html`, `lambda/auth/`, `lambda/contact/`, `lambda/comments/`, `lambda/processor/`, `manifest.json`, `sw.js`, `app.js`。

### ⚖️ リーガル・コンプライアンス（高優先 — サービス信頼の根幹）

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| ~~T221~~ | ~~高~~ | ~~プライバシーポリシーと Auth Lambda 不整合~~ → **Cowork実装完了 (2026-04-28 02:55 JST)・Code push 待ち**。privacy.html 第2項にメールアドレス収集を明示・利用目的を「重要なお知らせ・本人確認・アカウント削除時の通知用途のみ。マーケティングメール・第三者提供なし」と限定明記。第3項「アカウントと認証」も同等表記に更新。最終更新日 2026-04-28 へ更新。完了したら HISTORY.md 移動。 | `frontend/privacy.html` | 2026-04-28 |
| ~~T222~~ | ~~高~~ | ~~削除依頼期間表記4種混在~~ → **Cowork実装完了 (2026-04-28 02:55 JST)・Code push 待ち**。2区分に統一: 「お問い合わせ全般=3営業日以内」「著作権侵害・プライバシー削除依頼=7営業日以内」。privacy.html 第8項「2営業日以内→7営業日以内」「7日以内→7営業日以内」、第9項既存の「7営業日以内」維持、terms.html 第6項「7営業日以内」維持、contact.html は基本ライン (3営業日) 維持。完了したら HISTORY.md 移動。 | `frontend/privacy.html`, `frontend/terms.html` | 2026-04-28 |
| ~~T223~~ | ~~高~~ | ~~GitHub Issues 誘導残存~~ → **Cowork実装完了 (2026-04-28 02:55 JST)・Code push 待ち**。privacy.html 第9項「GitHub Issuesから」→「お問い合わせフォームから」、terms.html 第6項「GitHub Issuesにて通報」→「お問い合わせフォームから通報」。terms.html バージョン v1.3 → v1.4 (2026-04-28) 更新。完了したら HISTORY.md 移動。 | `frontend/privacy.html`, `frontend/terms.html` | 2026-04-28 |
| T224 | 高 | **個人メールアドレス直書き** → **Lambda 側完了 (2026-04-28 02:55 JST)・admin.html は T224a に分割**。Lambda 側修正: contact/handler.py の `ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'mrkm.naoya643@gmail.com')` → default 空文字 + verify_admin_token 冒頭に空チェック追加 (env var 未設定時は admin 機能を物理的に塞ぐ二重防御)。残課題 T224a: `frontend/admin.html:296` の `allowedEmail` 直書きは公開ファイルでスピアフィッシング情報として漏洩中。build 時注入機構 (env→HTMLテンプレート置換) を作る大改修になるため別タスク化。暫定運用は admin.html を CloudFront で IP制限など。 | `frontend/admin.html` | 2026-04-28 |
| T225 | 中 | **tokushoho.html 残存** → **Cowork範囲外** (FUSEマウントで物理削除不可・Code セッションで `git rm projects/P003-news-timeline/frontend/tokushoho.html` + CloudFront キャッシュパージ + Search Console URL 削除リクエスト + CI に「frontend に tokushoho.html が存在しないこと」チェック追加)。 | `frontend/tokushoho.html`（削除）, CI チェック | 2026-04-28 |
| ~~T226~~ | ~~中~~ | ~~bottom-nav ラベル英大文字／日本語混在~~ → **Cowork実装完了 (2026-04-28 02:30 JST)・Code push 待ち**。全 9 ページ (index/topic/catchup/mypage/storymap/about/contact/profile/terms/privacy) を `🏠 TOPICS / 🕐 振り返る / 🔍 SEARCH / 👤 HOME` の 4 タブに統一。catchup へ active state を付与。CLAUDE.md vision-roadmap フェーズ2 「振り返るの再設計」の前提となる導線を復活させた。 | `frontend/*.html` 全体 | 2026-04-28 |

### 🔐 セキュリティ・運用堅牢性

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| ~~T227~~ | ~~中~~ | ~~Auth Lambda CORS `*` 全許可~~ → **Cowork実装完了 (2026-04-28 03:30 JST)・Code push 待ち**。`ALLOWED_ORIGINS` env var (default: `https://flotopic.com,https://www.flotopic.com`) + `_resolve_origin(event)` で許可リスト echo back。`Vary: Origin` ヘッダーも追加。`cors_headers(event)` 全リターンパスに event 渡しを統一。完了したら HISTORY.md 移動。 | `lambda/auth/handler.py` | 2026-04-28 |
| ~~T228~~ | ~~中~~ | ~~contact form rate limit なし~~ → **Cowork実装完了 (2026-04-28 03:35 JST)・Code push 待ち**。`flotopic-rate-limits` を再利用し、IP のソルト付き SHA-256 ハッシュ (生IP保存しない) で バースト 5分3件・デイリー 1日10件 の二段ガード。超過時は 429 + 自然な日本語。例外時 fail-open + ログ。完了したら HISTORY.md 移動。 | `lambda/contact/handler.py` | 2026-04-28 |
| T229 | 低 | **admin.html フロントだけのメール突合は装飾、信頼すべきではない事の明文化** — 現状: `frontend/admin.html:1105` で `payload.email !== CONFIG.allowedEmail` をチェックしているが、攻撃者が DevTools で `CONFIG.allowedEmail` を書き換えれば UI は通る。バックエンド (contact/handler.py の verify_admin_token) でちゃんと検証しているので致命的ではないが、admin.html の analyticsUrl / cf-analyticsUrl は認証なしで取得可能。「フロントの認証は UX のため」とコメントを残すか、analytics エンドポイントにも Bearer 検証を追加するか方針を決める。 | `frontend/admin.html`, `lambda/cf-analytics/`, `lambda/analytics/` | 2026-04-28 |

### 🧭 UI/UX

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| ~~T230~~ | ~~高~~ | ~~catchup.html bottom-nav 導線消失~~ → **Cowork実装完了 (2026-04-28 02:30 JST・別T226と同一案件で重複登録、合流処理)**。全 9 ページの bottom-nav を `🏠 TOPICS / 🕐 振り返る / 🔍 SEARCH / 👤 HOME` の 4タブに統一。catchup.html は active state を付与。manifest.json の PWA ショートカット「リワインド」と整合。完了したら HISTORY.md 移動。 | `frontend/*.html` 全体 | 2026-04-28 |
| T233 | 高 | **detail.js Discovery セクションに relatedTopicTitles 連携** → **Cowork実装完了 (2026-04-28 03:50 JST)・Code push 待ち**。CLAUDE.md vision-roadmap フェーズ2「関連する動きリンク」を実装。`renderDiscovery` で AI 生成 relatedTopicTitles をタイトル逆引きで allTopics に解決し `📡 関連する動き` バッジで Discovery カードに追加。一致しないタイトルは握りつぶす。`style.css` の `disc-badge-related` (#e0f2fe/#075985, dark:#93c5fd) も追加。 | `frontend/detail.js`, `frontend/style.css` | 2026-04-28 |
| T231 | 中 | **推移グラフの長期ボタンがデータ蓄積前から押せる — 「データ蓄積中」白画面が出る** — 根本原因: `frontend/topic.html:386-394` で `1d/3d/7d/1m/3m/6m/1y/all` ボタンが常時 active。本番運用2026-04-20開始のためデータ実測は 8 日分しかないが、`1ヶ月/3ヶ月/半年/1年/全期間` を押すと「データ蓄積中」が出るだけで、ユーザーには「壊れている」に見える。CLAUDE.md「実装前ユーザー文脈チェック」②「推移グラフの長期ボタン」で同問題が指摘済みだが未対処。修正方法: トピックの最古SNAP日時を取得し、その期間に届いていないボタンは `disabled` グレーアウト or 非表示にする。 | `frontend/topic.html`, `frontend/detail.js` | 2026-04-28 |
| T232 | 中 | **「関連記事」h2 がデータ0件でも表示される — CLAUDE.md「空コンテナ非表示」違反** — 根本原因: `frontend/topic.html:374-377` で `<div class="card"><h2>関連記事</h2><div id="related-articles"></div></div>` がデータ0件でもカード全体表示。CLAUDE.md ルール「データが0件またはロード失敗の場合、h2ヘッダーを含むカードごと `display:none` にする」に違反。修正方法: detail.js で関連記事0件時に `el.closest('.card').style.display='none'` を実行する。 | `frontend/topic.html`, `frontend/detail.js` | 2026-04-28 |
| T233 | 中 | **AI分析「処理待ち」表示に次回更新予定時刻が無い** — 根本原因: CLAUDE.md「実装前ユーザー文脈チェック」③で「いつ来れば読めるか」を必ず表示するルール明示済みだが未対応。`frontend/detail.js:340-348` の「⏳ AI分析を生成中です（1日4回更新）」のみ。修正方法: 現在時刻と JST 01/07/13/19 の境界を計算し「次の更新: 13:00 JST」を併記。1日4回スケジュールがズレた場合に備えて topics.json の `updatedAt` を見て「最終更新: ○分前」も併記。 | `frontend/detail.js` | 2026-04-28 |
| T234 | 中 | **ヘッダーキャッチコピーがページ間で微妙に違う** — 実態（再調査）: `index.html` h1+p「Flotopic / 大きな流れを、1分で。」、`about.html` 同左、`catchup.html` h1「振り返る」hero p「過去N日間に話題になったトピック…」、`topic.html` ヘッダー無し（hero別）、`privacy.html` h1「📰 Flotopic / 話題の流れをAIで追う」（絵文字付き・古いコピー）、`terms.html` 同左。privacy/terms に古いコピーが残る。修正方法: 全ページのヘッダーロゴ要素を統一テンプレート化し「Flotopic / 大きな流れを、1分で。」に揃える。 | `frontend/privacy.html`, `frontend/terms.html`, `frontend/about.html` | 2026-04-28 |

### 🛠 安定性・運用

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T235 | 中 | **Claude API 呼び出しが 5xx 時にリトライしない — Tool Use 移行で 5xx 増加リスク** — 根本原因: `lambda/processor/proc_ai.py:14-37` の `_call_claude` は HTTP 429 のみ最大3回リトライ。500/503 系は 1 回失敗で諦めて return None、当該トピックの AI フィールドが空のままになる。Tool Use 化で構造化出力が増え、Anthropic 側の generation timeout / 内部エラーが顕在化しやすい。修正方法: 5xx 系 (500, 502, 503, 504) も 429 と同等のバックオフ付きリトライ対象に追加。記録用に `[METRIC] claude_5xx_retry` ログを出して governance worker で集計。 | `lambda/processor/proc_ai.py` | 2026-04-28 |
| T236 | 中 | **governance worker の品質メトリクス実装状況棚卸し** — 根本原因: CLAUDE.md には「クラスタリング 2-3件トピック比率70%超で Slack 警告」「perspectives 0% 充填で Slack 警告」「processed件数 / wallclock残秒 / 1call平均所要秒」が仕組み的対策として記載されているが、`scripts/_governance_check.py` (推定パス) で実装されているか未検証。実装されていなければ「対策3つ書いた」だけで再発防止が動いていない。修正方法: scripts/_governance_check.py を読み、不足metricを追加。Slack警告閾値・送信先チャネルを CLAUDE.md と一致させる。 | `scripts/_governance_check.py`, `.github/workflows/governance.yml` | 2026-04-28 |
| T237 | 中 | **AI生成カバレッジ 24.6% の根本原因が pending queue 優先度問題と TASKS.md に記載済みも未着手** — 根本原因: TASKS.md「P003 技術状態スナップショット」で「pending queue 優先度問題(T213)が根本原因」と書かれているが T213 が見当たらない（既に番号衝突か履歴へ移動された）。proc_storage.py の `get_pending_topics` を読み、Tier-0 (topics.json 可視 × aiGenerated=False) を最優先で返しているか・ DynamoDB scan の order 保証があるか実機確認する。T218 wallclock guard が反映されれば自動解消される可能性も含めて再評価。 | `lambda/processor/proc_storage.py`, `lambda/processor/handler.py` | 2026-04-28 |
| T238 | 低 | **processor handler.py の特殊モード分岐が肥大化（300+行）** — 根本原因: `lambda/processor/handler.py:60-150` に `regenerateStaticHtml` / `backfillDetailJson` / `backfillArchivedTtl` / `purgeAll` / `forceRegenerateAll` / `regenerateSitemap` の6つの特殊モードが連結 if 文で並ぶ。テスト・保守・新モード追加が困難。修正方法: `proc_admin_modes.py` に分離し、`handler.py` は `if event.get('mode'): return route_admin(event)` だけにする。 | `lambda/processor/handler.py` (新規ファイル) | 2026-04-28 |

### 💰 収益・拡張

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T239 | 中 | **ads.txt と index.html pub-id の整合性 CI チェックが未実装** — 根本原因: CLAUDE.md「ads.txt 欠落 なぜなぜ分析」の仕組み的対策2「CIチェック追加候補」に明記済みだが未実装。手動更新だと再発する。修正方法: `.github/workflows/ci.yml` に shell スクリプトを追加: `index.html` から `client=ca-pub-([0-9]+)` を抽出し、`frontend/ads.txt` に `google.com, pub-\1, DIRECT, f08c47fec0942fa0` 行が存在するか grep。同様に忍者AdMaxの `data-shinobi-id` も検証。 | `.github/workflows/ci.yml`, `frontend/ads.txt` | 2026-04-28 |
| T240 | 低 | **Cloudflare Web Analytics トークンがフロントに直書き** — 観測: index.html / topic.html 等の最後で `data-cf-beacon='{"token": "35149d754c..."}'` がハードコード。これは CF 側仕様で公開するもので問題はないが、サブドメインや別環境を増やす際にビルド時 env 注入する設計が無い点だけメモ。優先度低。 | `frontend/*.html` | 2026-04-28 |
| T241 | 低 | **アフィリエイトのセンシティブトピック自動非表示ロジック未実装** — 根本原因: CLAUDE.md「過去の設計ミスパターン」⑧で「事件・事故・医療・政治では非表示にする」とルール明記済み。affiliate.js（または該当箇所）で genre が `'社会'`/`'国際'`/`'健康'` × 記事タイトルが事件/事故/疾患キーワードを含む時は出さない実装が必要。優先度は AdSense 通過後・収益性確認後でよい。 | `frontend/js/affiliate.js`（推定）, `frontend/topic.html` | 2026-04-28 |

### 🛡 Cowork×Code 連携・運用ガバナンス（2026-04-28 追加分・追跡別セッション）

> 上記 T221〜T241 は別 Cowork セッションが既に列挙済み。以下は同日 02:00 JST 以降の追加調査で発見した「Cowork↔Code 連携の構造的欠陥」と「topics.json の鮮度モニタ欠如」「タスクID 衝突」など、運用ガバナンス層の課題。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T242 | 高 | **topics.json 鮮度 SLI モニタ不在 — 「Lambda が壊れてもユーザー視点では分からない」問題** — 観測: 2026-04-28 01:14 JST 時点で `https://flotopic.com/api/topics.json` の `updatedAt` が `2026-04-27T13:34:59Z`（12時間前）。T218 の Lambda timeout を本日修正したが working dir に滞留しており、その間にも 4回（19:00/01:00/07:00/13:00 のうち過ぎたぶん）スケジュールが空振りしている。**根本原因**: 「ユーザーが見るデータが新鮮か」を直接モニタする SLI が無い。CloudWatch アラームは Lambda 個別失敗を見るが、successで終わったが topics.json は更新されなかったケース（in-flight中断パターン）を捕まえられない。**仕組み的対策（ルールではなく）**: ① 1 時間ごとに `curl https://flotopic.com/api/topics.json` を取得し `(now - updatedAt) > 90min` なら Slack 警告する独立 Lambda を新設（governance worker と別系統で走らせる—governance自身が壊れた時に検知できるよう）。② 警告 Slack には「次のスケジュール時刻」「最終 Lambda 成功時刻」を付ける。③ 警告閾値は将来 4x/day から 2x/day に削減する場合に再調整する。 | 新規 `lambda/freshness_monitor/` または `scripts/freshness_check.sh` + GH Actions 1h schedule | 2026-04-28 |
| T243 | 高 | **TASKS.md タスクID 同日衝突問題（T221 が 2用途で並立）** — 観測: WORKING.md L83 に `[Cowork] T221 catchup.html到達導線復活` がある一方、TASKS.md L68 に同じ `T221: プライバシーポリシーとAuth Lambda実装の不整合` が定義されている。**根本原因**: 別セッションがタスクIDを「最大値+1」で振る運用だが、Cowork × Cowork でも 同時刻ほぼ並列に動くため衝突する。Code セッションが起動して merge する時点では既に紛れ込んでいる。**仕組み的対策（ルールではない）**: ① タスクID を「日付+短ID」（例: `T2026-0428-A`）に変えて衝突可能性を減らす。② または `scripts/next_task_id.sh` を作り `git pull` 後に発番させる（複数セッション同時起動でも race は git pull のロックで防げる）。③ TASKS.md / WORKING.md / HISTORY.md の ID 一意性を CI で検証（重複検出すると ERROR）。 | `scripts/next_task_id.sh` 新規, `.github/workflows/ci.yml` チェック追加 | 2026-04-28 |
| T244 | 高 | **WORKING.md `needs-push` カラム追加 — Cowork 編集が滞留する問題** — 観測: 本日 T218 の wallclock guard 実装が 02:00 JST 頃に Cowork で完了したが、`git status -s` を見ると 12 時間後（14:00 JST 以降の Code 起動まで）main にマージされない構造。production の Lambda は壊れたまま 4 サイクル空振りした。**根本原因**: WORKING.md は「誰が何を編集中」を追えるが「未push の重要 fix が working dir に滞留している」を可視化できない。8時間stale ルールは push 後の片付け漏れには効くが、push 前の滞留には効かない。**仕組み的対策**: ① WORKING.md に `needs-push` カラム（yes/no）を追加し、Cowork は code ファイルを編集する時に必ず `yes` を立てる。② Code セッション起動時の起動チェックスクリプト末尾で `grep "needs-push.*yes" WORKING.md` を実行し、ヒット行があれば「⚠️ <行内容> を最優先で push してください」を表示。これは 8時間TTL とは別軸の「滞留検出」。 | `WORKING.md` 構造変更, `CLAUDE.md` 起動チェック script 拡張 | 2026-04-28 |
| T245 | 中 | **AI フィールド データフロー文書 `docs/ai-fields-flow.md` 新設** — 観測: 過去 T193follow-up で `handler.py ai_updates` への backgroundContext 追加漏れがあり、本日の T220 では「topics.json で 0%」を理由に未マージと誤読された（実態は per-topic JSON には入っていた）。**根本原因**: AI フィールドが `proc_ai.py schema → _normalize_story_result → handler.py ai_updates → S3 topics.json + S3 per-topic.json + DynamoDB → frontend (app.js card / detail.js detail) ` の 5層 を通るが、フィールドごとの「どの層に入る/入らない」の一覧が無い。**仕組み的対策**: ① `docs/ai-fields-flow.md` に「フィールド × 各層 × 表示有無」のマトリクスを書く。② 新フィールド追加時の PR テンプレートで全層チェックを必須化。③ CI で `proc_ai.py schema` と `handler.py ai_updates` の field 名差分を grep し、proc_ai 側だけ追加された未配線フィールドは ERROR。これによりフィールド追加時の「層を1つ忘れる」を構造で防ぐ。 | `docs/ai-fields-flow.md` 新規, `.github/workflows/ai-fields-coverage.yml` 新規 | 2026-04-28 |
| T246 | 中 | **`Verified:` 行を完了 commit に必須化（done.sh 拡張）** — 観測: CLAUDE.md「完了=動作確認済み」と書いてあるがテキスト規則のため形骸化しがち（T220 で再発）。**根本原因**: LLM (Claude) は文字列規則を狭く解釈する。「動作確認しました」と書けば通るが、それは verbose な自己申告であり構造的な証跡にならない。**仕組み的対策（ルール強化ではなく構造）**: ① `done.sh` を拡張し、引数 `verify_target` から URL/log/test を取得して証跡として commit message に `Verified: <url>:<status>:<timestamp>` を自動付与。② pre-commit hook で「`done:` プレフィックス commit に `Verified:` 行が無ければ reject」。③ Cowork 側はweb_fetch でURL叩いて HTTP 200 + 期待文字列 grep を verify_target にする。これで「edit + push = done」マインドを構造的に断ち切る。 | `done.sh`, `.git/hooks/pre-commit`, `CLAUDE.md`（恒久ルール 1行更新） | 2026-04-28 |
| ~~T247~~ | ~~低~~ | ~~security.txt 不在~~ → **Cowork実装完了 (2026-04-28 schedule task)・Code push 待ち**。`frontend/.well-known/security.txt` を RFC 9116 形式で作成。Contact / Expires (2027-12-31) / Preferred-Languages / Canonical / Policy の 5 行。GH Actions deploy-p003.yml の最後の sync (画像・その他) で hit して S3 配信される。完了判定: `curl -I https://flotopic.com/.well-known/security.txt` HTTP 200 → HISTORY.md 移動。 | `frontend/.well-known/security.txt` | 2026-04-28 |
| T248 | 低 | **privacy.html「アフィリエイトプログラムへの参加」記述が UI 実装と乖離** — 観測: privacy.html L141 が「Amazonアソシエイト・楽天アフィリエイト・もしもアフィリエイト等に参加」と明記しているが、`detail.js` から affiliate 表示コードは既に削除済み。topic.html にも affiliate slot 無し。**乖離の影響**: ユーザーから「PR表示があるはずなのに無い」と感じられる、または将来 affiliate を再導入する際に「(再開)」コミュニケーションが必要。**対策**: privacy.html 7.5節を「現在 affiliate プログラムは利用していない。導入時にこの記述を更新する」に書き換える（最低コスト）。または T109 と連動して再導入時に同時更新。 | `frontend/privacy.html` | 2026-04-28 |

### 🔁 2026-04-28 追加調査ラウンド2 (Cowork スケジュール 01:30 JST 起動分)

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| ~~T249~~ | ~~高~~ | ~~handler.py merge ループ keyPoint・backgroundContext 漏れ~~ → **本セッション修正済 (commit待ち)**。観測: 本番 topics.json 114件中 keyPoint=0% / backgroundContext=0% / perspectives=0% / outlook=0% (`https://flotopic.com/api/topics.json` 直接確認)。**根本原因**: `handler.py` L297-317 の merge ループに `keyPoint` `backgroundContext` の代入行が無く、`ai_updates` dict には入れているのに topics.json に出ない構造的バグ。perspectives/outlook は merge ループにあるが、AI処理 skip 条件で aiGenerated=True 旧 topic は再処理されないため埋まらない。なぜなぜ: ① 新フィールドを ai_updates に追加した時に merge ループへの追加を忘れた → ② 「proc_ai schema → ai_updates → merge → publish」の 5 層フローを 1 箇所で書いていない → ③ T245 の AI フィールド データフロー文書が無いため LLM が層を飛ばしても気づかない → ④ CI の field 名差分検出も無い → ⑤ 「動作してる」自己申告が層単位で正しいか確認できない構造。**仕組み的対策**: 本コミットで merge 行追加 + 別タスク T256 で CI 検出を実装。完了判定: 次回スケジュール後に topics.json で keyPoint/backgroundContext がそれぞれ 50%+ 充填。 | `lambda/processor/handler.py` | 2026-04-28 |
| ~~T250~~ | ~~高~~ | ~~static HTML 生成例外をサイレント握り潰し~~ → **本セッション修正済 (commit待ち)**。観測: `/topics/3d28bb46b99072e9.html` が `<title>...— スポーツニュース 経緯・最新情報まとめ</title>` を含む (実際は genre=国際の外交トピック)。topics.json では genres=['国際','政治'] と修正されているが、静的 HTML は古い genre のまま。**根本原因**: `proc_storage.py update_topic_s3_file` L803-805 で `generate_static_topic_html()` を呼ぶ try ブロックの except が `except Exception: pass` でエラーを完全に握り潰しており、CloudWatch ログにも何も出ない (典型的 silent failure)。「対症療法ではなく根本原因」CLAUDE.md ルール違反。**仕組み的対策**: 本コミットで `print(f'[TOPIC_STATIC_FAIL] tid={tid} error=...')` に書き換え。governance worker に集計用 metric 追加余地を作った。完了判定: 次回スケジュール後 CloudWatch で `[TOPIC_STATIC_FAIL]` の件数を確認 → 0 件なら正常、出てくれば根本原因を別タスクで追う。 | `lambda/processor/proc_storage.py` | 2026-04-28 |
| T251 | 高 | **HSTS / X-Frame-Options / Permissions-Policy が CloudFront response headers に無い** — 観測: `curl -I https://flotopic.com/` のヘッダに `strict-transport-security` / `x-frame-options` / `permissions-policy` が **全く無い**。HSTS 無しは HTTPS ダウングレード攻撃面、X-Frame-Options 無しはクリックジャッキング面、Permissions-Policy 無しはカメラ/マイク/位置情報の暗黙許可。CSP も HTML meta タグのみで HTTP header にない (一部の互換性問題で攻撃面が広い)。**修正方法**: CloudFront に Response headers policy を新設し、すべてのレスポンスに付与。Naoya がコンソールで設定する案件 (Lambda@Edge でも可)。**仕組み的対策**: 設定後、`scripts/security_headers_check.sh` で月次に curl でチェックし、欠落があれば Slack 警告 (将来)。 | CloudFront 設定 (Naoya確認案件), `scripts/security_headers_check.sh` 新規 | 2026-04-28 |
| T252 | 中 | **CSP に unsafe-inline + unsafe-eval が設定されている — XSS 攻撃面拡大** — 観測: 全 HTML の `Content-Security-Policy` meta タグが `default-src 'self' https: 'unsafe-inline' 'unsafe-eval'`。理由は ld+json / inline style / Google Sign-In ライブラリが eval を使うため必要。**現状の影響**: ユーザー投稿 (コメント) で innerHTML へ突っ込めば XSS が容易。コメント Lambda 側で sanitize しているなら被害は限定的だが、**defense-in-depth 観点では弱い**。**仕組み的対策**: ① `unsafe-eval` を削除し eval 使用を排除 (Google Sign-In は新版で eval 不要). ② inline style → 外部 CSS class へ移行 (style属性使ってる箇所をリファクタ). ③ CSP nonce/hash 化 で `unsafe-inline` 削除. これらは段階的に進める。短期では `script-src` だけは `'unsafe-eval'` 削除可能か検証。 | `frontend/*.html` 全 CSP meta | 2026-04-28 |
| T253 | 低 | **AI 学習クローラー全禁止 vs AI Visibility (AEO/GEO) のトレードオフ判断が必要** — 観測: `robots.txt` で GPTBot / ChatGPT-User / Claude-Web / anthropic-ai / Google-Extended / PerplexityBot / Applebot-Extended / CCBot 全て Disallow。Flotopic 自体が Anthropic Claude を使う側として「自分のAI要約を競合 AI に学習されたくない」のは筋が通るが、**ChatGPT/Perplexity で「Flotopic」の名前を引いた時に検索結果に出てこない** という機会損失が発生している。サービス成長期 (PV 240/週) では認知拡大が優先される可能性。**判断軸**: AI生成要約の知的財産価値 vs AEO/GEO 流入の機会値。**仕組み的対策**: ① `searchfit-seo:ai-visibility` skill で ChatGPT/Claude 上の Flotopic 露出を月次計測。② Flotopic オリジナル要約は禁止のままで、トピックタイトルとリンクのみ返す軽量 HTML を `/api/ai-summary/{topicId}.txt` で公開する。③ Naoya 判断後に robots.txt を段階的に開放。 | `frontend/robots.txt`, `searchfit-seo:ai-visibility` | 2026-04-28 |
| T254 | 中 | **style.css / app.js が `no-cache, must-revalidate` で CDN/ブラウザキャッシュ無効化されている — Lighthouse スコア・帯域コスト低下** — 観測: GH Actions deploy-p003.yml で HTML/JS/CSS 全部に `no-cache, must-revalidate` を設定。HTML は正解だが、JS/CSS は **content-hash バージョニング (`app.js?v=abc123`) すれば長期キャッシュ可能**。CloudFront `/*` invalidation で全 path を invalidate しているのでキャッシュバスティングは出来ているが、各ユーザーは毎回 ETag 確認往復が発生している。**仕組み的対策**: ① deploy-p003.yml で JS/CSS に長期キャッシュ (max-age=31536000, immutable) を設定。② 各 HTML から JS/CSS への参照を `?v=${GITHUB_SHA::7}` で書き換える sed パスを deploy 時に追加。③ sw.js は引き続き no-store で版管理。 | `.github/workflows/deploy-p003.yml`, `frontend/*.html` の `<script src=>` / `<link href=>` | 2026-04-28 |
| T255 | 中 | **AI 処理 skip 条件に keyPoint チェック未実装 — 既存 aiGenerated topic に古い欠損データが永久に残る** — 観測: `handler.py` L222-227 の skip 条件は `topic.get('aiGenerated') and (storyTimeline or _is_minimal) and (storyPhase or _is_minimal)` だけ確認。keyPoint プロンプトが追加 (commit `963ff61` 2026-04-25) される前に処理された aiGenerated=True topic は永久に再処理されず、keyPoint=None のまま (本番で確認済)。**修正方法**: skip 条件に `(topic.get('keyPoint') or _is_minimal)` を追加。次回スケジュールで自動再処理されるが、114 件 × 1 call = 100+ 余分 API 呼び出しが 1 回発生する (Haiku で ~$0.23)。**仕組み的対策**: ① skip 条件を「必須フィールドリスト」設定にして新フィールド追加時に追記 1 行で済むようにする。② Naoya 判断: 即時実装で短期コスト増を許容するか、forceRegenerateAll を 1-2 回手動 invoke するか。 | `lambda/processor/handler.py` skip 条件 | 2026-04-28 |
| T256 | 中 | **AI フィールドの「層を1つ忘れる」を CI で物理検出する仕組み不在** — 観測: T249 (keyPoint・backgroundContext merge 漏れ) は手動調査で発見。proc_ai.py の input_schema には全フィールドあるが handler.py merge ループだけ漏れていた。T245 の文書化案だけでは LLM が PR 時に文書を更新し忘れれば検出不可。**仕組み的対策**: ① `.github/workflows/ai-fields-coverage.yml` 新規。proc_ai.py の input_schema (`base_props['xxx']`) を grep して field 名一覧を抽出 → handler.py L260-283 (ai_updates dict 作成) と L297-317 (merge ループ) の両方に同名キーがあるか check → 欠落あれば CI ERROR。② 追加で proc_storage.py L724-784 (個別 JSON merge) も同 check に含める。③ ジェネリック化: Python AST で `ai_updates[tid] = {...}` の dict literal キーを抽出し、 merge ループの `if upd.get('xxx'):` パターンの `xxx` と diff。 | `.github/workflows/ai-fields-coverage.yml` 新規, `scripts/check_ai_fields_coverage.py` 新規 | 2026-04-28 |
| T257 | 中 | **profile.html・admin.html・mypage.html などログイン系ページが noindex のまま** — 観測: `profile.html` L9 `<meta name="robots" content="noindex">` 等。これは正解だが、**サイトマップにこれらが含まれていないか** Google Search Console で確認が必要。`api/sitemap.xml` 件数は 120 で、これは `topics/{tid}.html` + 主要静的ページ。`profile.html` `mypage.html` `admin.html` が含まれていないことを確認。 | `lambda/processor/proc_storage.py` (sitemap生成ロジック確認), Search Console | 2026-04-28 |
| T258 | 中 | **「発端」storyPhase 50% 偏り (本番) — T219 修正前の旧データが残る** — 観測: 本番 topics.json で storyPhase 分布 = 拡散 23 / 発端 57 / ピーク 9 / 現在地 4 / null 21。T219 prompt 修正 (本日) で「記事3件以上で発端禁止」を入れたが、aiGenerated=True 旧 topic は skip されるため反映されない (T255 と同根)。**完了判定**: T255 修正＋forceRegenerateAll 1-2 回後、storyPhase 分布が「拡散 35-45% / ピーク 10-15% / 現在地 5-10% / null 30-40% (minimal mode)」程度に正規化。 | (T255 で連動解消) | 2026-04-28 |
| T259 | 低 | **`Cache-Control: max-age=60` の topics.json が 90 分後鮮度警告と整合しない** — 観測: GH Actions と proc_storage.py で topics.json `Cache-Control: max-age=60`。一方 T242 SLI 警告は 90 分超で警告。Cache-Control は CloudFront edge までの TTL であり、ユーザー curl 結果の age (178分) と直接関係しない (S3 origin の最終更新時刻が反映)。**確認**: T242 実装時に「鮮度=updatedAt フィールド差分」「Cache-Control= edge cache TTL」の違いを混同しないこと。両者は別軸。topics.json の cache control は短く、updatedAt の鮮度は SLI として独立に監視する。 | `T242 実装時に注意点として明記` | 2026-04-28 |
| T260 | 中 | **個別 topic JSON の `data['meta']` で aiGenerated=False の topic も生成されている → S3 オブジェクト数増・LIST コスト増** — 観測: `https://flotopic.com/api/topic/8f81be6586cbea09.json` は `aiGenerated=False` で meta が `{aiGenerated, topicId}` の 2 フィールドだけ。空の個別 JSON が量産されている。S3 LIST/PUT コスト・CloudFront 配信トラフィックは小さいが、可視性低下。**修正方法**: `update_topic_s3_file` で `aiGenerated=False` かつ generatedTitle 等が無いトピックは個別 JSON 生成をスキップ。または別ディレクトリに分けて公開URLから外す。 | `lambda/processor/proc_storage.py` update_topic_s3_file | 2026-04-28 |
| T261 | 低 | **ads.txt の重複行確認 (CI 追加候補)** — 現状: AdSense pub-id + AdMax の 2 行。**仕組み的対策**: T239 既存タスクと統合し、CI で `index.html` の `data-ad-client=ca-pub-NNN` から AdSense pub-id 自動抽出 → ads.txt 整合性チェック。AdMax `data-shinobi-id` も同様。 | T239 と統合 | 2026-04-28 |
| T262 | 中 | **プライバシーポリシー・利用規約が `noindex` だが SEO 上の表示・検索性は OK か再確認** — 観測: privacy.html / terms.html は `noindex` 設定なし (現在は indexable)。一方 footer から各ページへリンクされており、Google が認識しているはず。**確認**: Search Console で `site:flotopic.com` 検索し、privacy/terms が結果に出るか。出ていない場合は `<meta name="robots" content="index, nofollow">` などで誘導改善。 | Search Console 確認 | 2026-04-28 |

---

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
