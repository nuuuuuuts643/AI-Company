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
| T227 | 中 | **Auth Lambda CORS が `*` で全 Origin 許可 — CSRF 増幅リスク** — 根本原因: `lambda/auth/handler.py:38` の CORS は `Access-Control-Allow-Origin: '*'`。POST `/auth` を任意の悪性サイトから送信可能。Google ID トークンは検証しているので即座のなりすましリスクは低いが、ユーザーが攻撃ページに誘導されると意図しないユーザー登録・プロフィール更新（handle/avatar/interests）が走り、不正データで DynamoDB を汚染できる。修正方法: `Access-Control-Allow-Origin` を `https://flotopic.com` のみに固定（contact/handler.py の実装を踏襲）。 | `lambda/auth/handler.py` | 2026-04-28 |
| T228 | 中 | **contact form のレートリミットなし — スパム送信耐性が honeypot のみ** — 根本原因: `lambda/contact/handler.py` の POST `/contact` はハニーポット (`website` フィールド) のみで rate limit 機能がない。同一 IP / 同一メールから連続送信されると DynamoDB `flotopic-contacts` 増殖 + SES 配信コスト増 + 管理画面ノイズが発生する。修正方法: comments Lambda に倣い、IP ハッシュ単位で `flotopic-rate-limits` に記録（5分に3件 / 1日10件など）。または API Gateway 側で usage plan を導入。 | `lambda/contact/handler.py` | 2026-04-28 |
| T229 | 低 | **admin.html フロントだけのメール突合は装飾、信頼すべきではない事の明文化** — 現状: `frontend/admin.html:1105` で `payload.email !== CONFIG.allowedEmail` をチェックしているが、攻撃者が DevTools で `CONFIG.allowedEmail` を書き換えれば UI は通る。バックエンド (contact/handler.py の verify_admin_token) でちゃんと検証しているので致命的ではないが、admin.html の analyticsUrl / cf-analyticsUrl は認証なしで取得可能。「フロントの認証は UX のため」とコメントを残すか、analytics エンドポイントにも Bearer 検証を追加するか方針を決める。 | `frontend/admin.html`, `lambda/cf-analytics/`, `lambda/analytics/` | 2026-04-28 |

### 🧭 UI/UX

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T230 | 高 | **catchup.html(リワインド)への bottom-nav 導線が消失 — 機能が事実上 dead** — 根本原因: index.html・topic.html・privacy.html・contact.html の bottom-nav に `bn-catchup` リンクが存在しない（「TOPICS / SEARCH / HOME」の3項目のみ）。`app.js:1135` には `isCatchup = path.includes('catchup.html')` の判定ロジックが残ったままで、`items['bn-catchup']` を active にする dead code 化している。catchup.html は `sw.js` キャッシュ・`manifest.json` PWAショートカット「リワインド」に登録があり、PWA 起動か直接 URL 知っている人のみアクセス可能。Flotopicの差別化機能 (catchup) を運用上消した状態。判断: ①機能継続するなら bottom-nav に `bn-catchup` を復活、②廃止するなら manifest shortcut・sw.js キャッシュ・catchup.html ファイル・app.js dead code を一斉削除。CLAUDE.md「UIプレースホルダー3ヶ月ルール」に近い問題: 機能を作ったが導線が消えてユーザーが見つけられない。 | `frontend/*.html`, `frontend/manifest.json`, `frontend/sw.js`, `frontend/app.js` | 2026-04-28 |
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
| T247 | 低 | **security.txt (RFC 9116) 不在** — `https://flotopic.com/.well-known/security.txt` が 404。脆弱性報告ルートを明示する標準ファイル。bug bounty hunter / 善意の探索者から SNS 公開前に運営者へ報告するルートを与え、リスクを下げる。コンテンツ最小例: `Contact: mailto:contact@flotopic.com\nExpires: 2027-12-31\nPreferred-Languages: ja, en`。 | `frontend/.well-known/security.txt` 新規 | 2026-04-28 |
| T248 | 低 | **privacy.html「アフィリエイトプログラムへの参加」記述が UI 実装と乖離** — 観測: privacy.html L141 が「Amazonアソシエイト・楽天アフィリエイト・もしもアフィリエイト等に参加」と明記しているが、`detail.js` から affiliate 表示コードは既に削除済み。topic.html にも affiliate slot 無し。**乖離の影響**: ユーザーから「PR表示があるはずなのに無い」と感じられる、または将来 affiliate を再導入する際に「(再開)」コミュニケーションが必要。**対策**: privacy.html 7.5節を「現在 affiliate プログラムは利用していない。導入時にこの記述を更新する」に書き換える（最低コスト）。または T109 と連動して再導入時に同時更新。 | `frontend/privacy.html` | 2026-04-28 |

---

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
