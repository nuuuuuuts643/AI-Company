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
| T217 | 低 | **footer著作権「© 2024-2026」の妥当性（PO確認）** — about.html 開発開始年は 2026 に修正済み(commit `30aff22`)。残るは全ページfooter「© 2024-2026 Flotopic」表記。git実装は2026-04-20開始だが、ブランド検討期間を含めるなら 2024 起点もあり得る。PO判断後に統一。 | 全 *.html footer | 2026-04-27 |

### 🎯 使いたくなるUX（「また来たい」動線）

> 安定性改善と並行して進める。Flotopicの差別化はストーリー追跡体験にある。それが伝わる動線を作る。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T201 | 低 | **bottom-navの「リワインド」ラベルが初訪問ユーザーに意味不明** — 根本原因: bottom-navのラベルが「🕰️ リワインド」のみで、初訪問ユーザーは「リワインド」が何をする機能か分からずタップ動機が生まれない。catchup.htmlのheroには「あなたが離れていた間のニュースを時系列でお届け」と説明があるが、そこに到達するまで機能の価値が不明。競合（SmartNews等）では「おかえり」「まとめ読み」等の直感的なラベルを使う。影響: bottom-navのリワインドタップ率が低い可能性。修正方法: 「リワインド」→「まとめ読み」または「振り返り」に変更、もしくはhero内のsubラベルだけでも変更（コスト最小）。要PO判断（ブランド用語の変更）。 | `frontend/catchup.html`, `frontend/index.html`, `frontend/storymap.html`, `frontend/topic.html`, `frontend/mypage.html` | 2026-04-27 |
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
| T224 | 高 | **個人メールアドレス直書き** → **Lambda 側完了 (2026-04-28 02:55 JST)・admin.html は T224a に分割**。Lambda 側修正: contact/handler.py の `ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'owner643@gmail.com')` → default 空文字 + verify_admin_token 冒頭に空チェック追加 (env var 未設定時は admin 機能を物理的に塞ぐ二重防御)。残課題 T224a: `frontend/admin.html:296` の `allowedEmail` 直書きは公開ファイルでスピアフィッシング情報として漏洩中。build 時注入機構 (env→HTMLテンプレート置換) を作る大改修になるため別タスク化。暫定運用は admin.html を CloudFront で IP制限など。 | `frontend/admin.html` | 2026-04-28 |
| T225 | 中 | **tokushoho.html 残存** → **Cowork範囲外** (FUSEマウントで物理削除不可・Code セッションで `git rm projects/P003-news-timeline/frontend/tokushoho.html` + CloudFront キャッシュパージ + Search Console URL 削除リクエスト + CI に「frontend に tokushoho.html が存在しないこと」チェック追加)。 | `frontend/tokushoho.html`（削除）, CI チェック | 2026-04-28 |

### 🔐 セキュリティ・運用堅牢性

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T229 | 低 | **admin.html フロントだけのメール突合は装飾、信頼すべきではない事の明文化** — 現状: `frontend/admin.html:1105` で `payload.email !== CONFIG.allowedEmail` をチェックしているが、攻撃者が DevTools で `CONFIG.allowedEmail` を書き換えれば UI は通る。バックエンド (contact/handler.py の verify_admin_token) でちゃんと検証しているので致命的ではないが、admin.html の analyticsUrl / cf-analyticsUrl は認証なしで取得可能。「フロントの認証は UX のため」とコメントを残すか、analytics エンドポイントにも Bearer 検証を追加するか方針を決める。 | `frontend/admin.html`, `lambda/cf-analytics/`, `lambda/analytics/` | 2026-04-28 |

### 🧭 UI/UX

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
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
| T248 | 低 | **privacy.html「アフィリエイトプログラムへの参加」記述が UI 実装と乖離** — 観測: privacy.html L141 が「Amazonアソシエイト・楽天アフィリエイト・もしもアフィリエイト等に参加」と明記しているが、`detail.js` から affiliate 表示コードは既に削除済み。topic.html にも affiliate slot 無し。**乖離の影響**: ユーザーから「PR表示があるはずなのに無い」と感じられる、または将来 affiliate を再導入する際に「(再開)」コミュニケーションが必要。**対策**: privacy.html 7.5節を「現在 affiliate プログラムは利用していない。導入時にこの記述を更新する」に書き換える（最低コスト）。または T109 と連動して再導入時に同時更新。 | `frontend/privacy.html` | 2026-04-28 |

### 🔁 2026-04-28 追加調査ラウンド2 (Cowork スケジュール 01:30 JST 起動分)

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T251 | 高 | **HSTS / X-Frame-Options / Permissions-Policy が CloudFront response headers に無い** — 観測: `curl -I https://flotopic.com/` のヘッダに `strict-transport-security` / `x-frame-options` / `permissions-policy` が **全く無い**。HSTS 無しは HTTPS ダウングレード攻撃面、X-Frame-Options 無しはクリックジャッキング面、Permissions-Policy 無しはカメラ/マイク/位置情報の暗黙許可。CSP も HTML meta タグのみで HTTP header にない (一部の互換性問題で攻撃面が広い)。**修正方法**: CloudFront に Response headers policy を新設し、すべてのレスポンスに付与。Naoya がコンソールで設定する案件 (Lambda@Edge でも可)。**仕組み的対策**: 設定後、`scripts/security_headers_check.sh` で月次に curl でチェックし、欠落があれば Slack 警告 (将来)。 | CloudFront 設定 (Naoya確認案件), `scripts/security_headers_check.sh` 新規 | 2026-04-28 |
| T252 | 中 | **CSP に unsafe-inline + unsafe-eval が設定されている — XSS 攻撃面拡大** — 観測: 全 HTML の `Content-Security-Policy` meta タグが `default-src 'self' https: 'unsafe-inline' 'unsafe-eval'`。理由は ld+json / inline style / Google Sign-In ライブラリが eval を使うため必要。**現状の影響**: ユーザー投稿 (コメント) で innerHTML へ突っ込めば XSS が容易。コメント Lambda 側で sanitize しているなら被害は限定的だが、**defense-in-depth 観点では弱い**。**仕組み的対策**: ① `unsafe-eval` を削除し eval 使用を排除 (Google Sign-In は新版で eval 不要). ② inline style → 外部 CSS class へ移行 (style属性使ってる箇所をリファクタ). ③ CSP nonce/hash 化 で `unsafe-inline` 削除. これらは段階的に進める。短期では `script-src` だけは `'unsafe-eval'` 削除可能か検証。 | `frontend/*.html` 全 CSP meta | 2026-04-28 |
| T253 | 低 | **AI 学習クローラー全禁止 vs AI Visibility (AEO/GEO) のトレードオフ判断が必要** — 観測: `robots.txt` で GPTBot / ChatGPT-User / Claude-Web / anthropic-ai / Google-Extended / PerplexityBot / Applebot-Extended / CCBot 全て Disallow。Flotopic 自体が Anthropic Claude を使う側として「自分のAI要約を競合 AI に学習されたくない」のは筋が通るが、**ChatGPT/Perplexity で「Flotopic」の名前を引いた時に検索結果に出てこない** という機会損失が発生している。サービス成長期 (PV 240/週) では認知拡大が優先される可能性。**判断軸**: AI生成要約の知的財産価値 vs AEO/GEO 流入の機会値。**仕組み的対策**: ① `searchfit-seo:ai-visibility` skill で ChatGPT/Claude 上の Flotopic 露出を月次計測。② Flotopic オリジナル要約は禁止のままで、トピックタイトルとリンクのみ返す軽量 HTML を `/api/ai-summary/{topicId}.txt` で公開する。③ Naoya 判断後に robots.txt を段階的に開放。 | `frontend/robots.txt`, `searchfit-seo:ai-visibility` | 2026-04-28 |
| T254 | 中 | **style.css / app.js が `no-cache, must-revalidate` で CDN/ブラウザキャッシュ無効化されている — Lighthouse スコア・帯域コスト低下** — 観測: GH Actions deploy-p003.yml で HTML/JS/CSS 全部に `no-cache, must-revalidate` を設定。HTML は正解だが、JS/CSS は **content-hash バージョニング (`app.js?v=abc123`) すれば長期キャッシュ可能**。CloudFront `/*` invalidation で全 path を invalidate しているのでキャッシュバスティングは出来ているが、各ユーザーは毎回 ETag 確認往復が発生している。**仕組み的対策**: ① deploy-p003.yml で JS/CSS に長期キャッシュ (max-age=31536000, immutable) を設定。② 各 HTML から JS/CSS への参照を `?v=${GITHUB_SHA::7}` で書き換える sed パスを deploy 時に追加。③ sw.js は引き続き no-store で版管理。 | `.github/workflows/deploy-p003.yml`, `frontend/*.html` の `<script src=>` / `<link href=>` | 2026-04-28 |
| ~~T255~~ | ~~中~~ | ~~AI 処理 skip 条件に keyPoint チェック未実装~~ → **Cowork実装完了 (2026-04-28 17:25 JST・schedule task)・Code push 待ち**。`handler.py` L223-233 を「必須フィールドリスト」型に書き換え (`_required_full_fields` タプル) — 新フィールド追加時は 1 行追記で済む構造化。次回スケジュール 19:00 JST で 93 件再処理開始 (Haiku 約 $0.21・許容範囲)。完了判定: 19:00 JST 以降の topics.json で keyPoint 充填率 80%+。 | `lambda/processor/handler.py` skip 条件 | 2026-04-28 |
| T256 | 中 | **AI フィールドの「層を1つ忘れる」を CI で物理検出する仕組み不在** — 観測: T249 (keyPoint・backgroundContext merge 漏れ) は手動調査で発見。proc_ai.py の input_schema には全フィールドあるが handler.py merge ループだけ漏れていた。T245 の文書化案だけでは LLM が PR 時に文書を更新し忘れれば検出不可。**仕組み的対策**: ① `.github/workflows/ai-fields-coverage.yml` 新規。proc_ai.py の input_schema (`base_props['xxx']`) を grep して field 名一覧を抽出 → handler.py L260-283 (ai_updates dict 作成) と L297-317 (merge ループ) の両方に同名キーがあるか check → 欠落あれば CI ERROR。② 追加で proc_storage.py L724-784 (個別 JSON merge) も同 check に含める。③ ジェネリック化: Python AST で `ai_updates[tid] = {...}` の dict literal キーを抽出し、 merge ループの `if upd.get('xxx'):` パターンの `xxx` と diff。 | `.github/workflows/ai-fields-coverage.yml` 新規, `scripts/check_ai_fields_coverage.py` 新規 | 2026-04-28 |
| T257 | 中 | **profile.html・admin.html・mypage.html などログイン系ページが noindex のまま** — 観測: `profile.html` L9 `<meta name="robots" content="noindex">` 等。これは正解だが、**サイトマップにこれらが含まれていないか** Google Search Console で確認が必要。`api/sitemap.xml` 件数は 120 で、これは `topics/{tid}.html` + 主要静的ページ。`profile.html` `mypage.html` `admin.html` が含まれていないことを確認。 | `lambda/processor/proc_storage.py` (sitemap生成ロジック確認), Search Console | 2026-04-28 |
| T258 | 中 | **「発端」storyPhase 50% 偏り (本番) — T219 修正前の旧データが残る** — 観測: 本番 topics.json で storyPhase 分布 = 拡散 23 / 発端 57 / ピーク 9 / 現在地 4 / null 21。T219 prompt 修正 (本日) で「記事3件以上で発端禁止」を入れたが、aiGenerated=True 旧 topic は skip されるため反映されない (T255 と同根)。**完了判定**: T255 修正＋forceRegenerateAll 1-2 回後、storyPhase 分布が「拡散 35-45% / ピーク 10-15% / 現在地 5-10% / null 30-40% (minimal mode)」程度に正規化。 | (T255 で連動解消) | 2026-04-28 |
| T259 | 低 | **`Cache-Control: max-age=60` の topics.json が 90 分後鮮度警告と整合しない** — 観測: GH Actions と proc_storage.py で topics.json `Cache-Control: max-age=60`。一方 T242 SLI 警告は 90 分超で警告。Cache-Control は CloudFront edge までの TTL であり、ユーザー curl 結果の age (178分) と直接関係しない (S3 origin の最終更新時刻が反映)。**確認**: T242 実装時に「鮮度=updatedAt フィールド差分」「Cache-Control= edge cache TTL」の違いを混同しないこと。両者は別軸。topics.json の cache control は短く、updatedAt の鮮度は SLI として独立に監視する。 | `T242 実装時に注意点として明記` | 2026-04-28 |
| T260 | 中 | **個別 topic JSON の `data['meta']` で aiGenerated=False の topic も生成されている → S3 オブジェクト数増・LIST コスト増** — 観測: `https://flotopic.com/api/topic/8f81be6586cbea09.json` は `aiGenerated=False` で meta が `{aiGenerated, topicId}` の 2 フィールドだけ。空の個別 JSON が量産されている。S3 LIST/PUT コスト・CloudFront 配信トラフィックは小さいが、可視性低下。**修正方法**: `update_topic_s3_file` で `aiGenerated=False` かつ generatedTitle 等が無いトピックは個別 JSON 生成をスキップ。または別ディレクトリに分けて公開URLから外す。 | `lambda/processor/proc_storage.py` update_topic_s3_file | 2026-04-28 |
| T261 | 低 | **ads.txt の重複行確認 (CI 追加候補)** — 現状: AdSense pub-id + AdMax の 2 行。**仕組み的対策**: T239 既存タスクと統合し、CI で `index.html` の `data-ad-client=ca-pub-NNN` から AdSense pub-id 自動抽出 → ads.txt 整合性チェック。AdMax `data-shinobi-id` も同様。 | T239 と統合 | 2026-04-28 |
| T262 | 中 | **プライバシーポリシー・利用規約が `noindex` だが SEO 上の表示・検索性は OK か再確認** — 観測: privacy.html / terms.html は `noindex` 設定なし (現在は indexable)。一方 footer から各ページへリンクされており、Google が認識しているはず。**確認**: Search Console で `site:flotopic.com` 検索し、privacy/terms が結果に出るか。出ていない場合は `<meta name="robots" content="index, nofollow">` などで誘導改善。 | Search Console 確認 | 2026-04-28 |

### 🔁 2026-04-28 追加調査ラウンド3 (Cowork スケジュール 17:15 JST 起動分・本セッション)

> 観測の前提: 既存 T221〜T262 はほぼ実装/対処済み (T231 グラフボタン disable・T232 関連記事0件カード非表示・T233 次回更新時刻表示・T251 セキュリティヘッダ全付与 — 全て本日中の作業で本番反映済を curl/grep で確認)。本ラウンドは「既存タスクで拾えていない隙間」と「実装済タスクの actual production 影響」を中心に調べた。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T263 | 高 | **本番 topics.json が 14h 鮮度ゼロのままサイクル空振り — T242 SLI モニタを最優先で実装すべき** — 観測 (2026-04-28 17:15 JST): topics.json `updatedAt=2026-04-27T17:04Z` (=2026-04-28 02:04 JST) で **約 15 時間更新無し**。本日のスケジュール 07:00 / 13:00 JST が 2 回連続で topics.json を再生成できていない。Lambda 自体は invoke されているはず (CloudWatch 確認推奨) だが、in-flight 中断・例外サイレント握り潰し・pending queue 空打ち 等で publish 直前にコケている可能性。**根本原因 (Why1〜Why5)**: ① topics.json が古い → ② ユーザー視点で見える壊れ方を直接観測する仕組みが無い → ③ CloudWatch アラームは Lambda 失敗のみ拾い、success-but-empty パターンを取れない → ④ governance worker は「品質 metric (perspectives 充填率等)」を見るが「最終 publish 時刻」自体は監視していない → ⑤ そもそも「ユーザーから見える壊れ方を独立して観測する」という設計思想が抜けている。**仕組み的対策 (3つ)**: (a) T242 で提案済みの freshness monitor (1h 1回 curl で `now - updatedAt > 90min` なら Slack) を **最優先実装**。(b) 監視は governance/processor とは別 Lambda にし「監視自体が壊れた時に検知できる」よう外部 GH Actions cron で curl する。(c) 警告 Slack には「最終成功時刻・次回スケジュール時刻・直近 invoke ログURL」を貼る (オペレーション TTV 短縮)。**根本仕組み**: ルールではなく外部観測 (CLAUDE.md「外部観測必須」と整合)。 | 新規 `lambda/freshness_monitor/` または `.github/workflows/freshness-check.yml` | 2026-04-28 |
| T264 | 中 | **`.claude/worktrees/` に 6 個の stale 作業ツリーが残存** — 観測: `awesome-varahamihira-c01b2e` `happy-khorana-4e3a6c` `naughty-saha-ba5901` `quirky-cohen-c1efbd` `serene-hermann-993255` `vigilant-fermi-4e0a09` の 6 個。各 WORKING.md には 2026-04-26〜28 の古いエントリ (T021/サイト価値可視化 等) が残る。WORKING.md TTL 8h ルールはメインの WORKING.md にしか適用されていない。**根本原因 (Why1〜Why5)**: ① 各ツリーに WORKING.md が残る → ② Code セッションが worktree モードで終了する際の片付けが入っていない → ③ Claude Code の `isolation: worktree` 機能は agent 終了で worktree 残留 → ④ 1 worktree あたり 26 個のディレクトリ (= 数 GB の重複) を 6 個 = ストレージ圧迫 → ⑤ 「並列 agent の片付け責務はどこか」を CLAUDE.md / 起動チェック script で扱っていない。**仕組み的対策**: (a) 起動チェック script に `find .claude/worktrees -maxdepth 2 -name WORKING.md -mtime +1 -exec dirname {} \;` でクリーンアップ候補一覧を表示。(b) WORKING.md TTL ルールを worktree 配下にも適用する物理スクリプト化。(c) `.gitignore` に `.claude/worktrees/` を追加し、リポジトリ汚染を防ぐ (既に effective ignore か要確認)。 | `CLAUDE.md` 起動チェック, `scripts/cleanup_stale_worktrees.sh` 新規 | 2026-04-28 |
| T265 | 中 | **topics.json が 207KB と肥大化 — モバイル初回表示帯域コスト** — 観測: `curl -I https://flotopic.com/api/topics.json` で `content-length: 212483` (約 207KB)。115 件 × 1 件 1.8KB 平均。モバイル初回ロードで最大の payload (HTML は 16KB)。**根本原因 (Why1〜Why5)**: ① topics.json が大きい → ② 全トピックのフルデータ (storyTimeline/perspectives 抜きでも generatedSummary 120字 + sources 配列 + AI 情報) を 1 ファイルに集約 → ③ index.html の card 描画に `articleCount` `genres` `keyPoint` `storyPhase` 程度しか使わないが、API が分離されていない → ④ お気に入り表示・タイムライン描画ロジックが card データを共用するため分離コストが高く先送り → ⑤ 「実測の payload size を SLI として持つ」発想が無い。**仕組み的対策**: (a) `/api/topics-card.json` (card 表示用 minimal) と `/api/topics-full.json` (検索/特殊用途) に分離。card 用は 1 件 ~400B → 全体 ~50KB に圧縮可能。(b) Brotli 圧縮を S3+CloudFront で有効化 (現状 gzip のみか確認)。(c) governance worker に「topics.json size > 250KB」アラート追加。 | `lambda/processor/proc_storage.py`, `frontend/app.js`, CloudFront 設定 | 2026-04-28 |
| T266 | 低 | **`docs/system-status.md` の AI 要約カバレッジ「24.6%」が古い情報** — 観測: `docs/system-status.md` L37 で「実測: 可視 203 件中 aiGenerated=True 50 件 (24.6%)。pending queue 優先度問題が根本原因」と記載。本日 (04-28) 17:15 時点の実測は **115 件中 aiGenerated=True 93 件 (80.9%)** で大幅改善。T218 wallclock guard 反映で正常化したが、ステータス文書の更新が漏れている。**根本原因 (Why1〜Why5)**: ① 文書が古い → ② T218 完了時にカバレッジ実測値が更新ルーチンに入っていない → ③ system-status.md は「セッション開始時に必読」なのに「更新タイミング」が決まっていない → ④ 完了タスクが多くなると どの数字を直すか追跡しきれない → ⑤ system-status.md の各行に「最終確認日」と「数字を生成したコマンド」が併記されていないため再現性が無い。**仕組み的対策**: (a) system-status.md の各メトリクス行に `> measured: 2026-04-28 17:15 by curl ... | jq ...` の小さな procedure を併記。(b) `scripts/refresh_system_status.sh` で curl 経由の数字を毎日自動更新 (GH Actions 03:00 JST cron)。(c) 古い数字が残ると CI で警告 (mtime > 7 日)。 | `docs/system-status.md`, `scripts/refresh_system_status.sh` 新規 | 2026-04-28 |
| T267 | 中 | **CSP meta タグはあるが HTTP Response Header に CSP が無い — meta タグの限界** — 観測: `curl -I https://flotopic.com/` のヘッダに `content-security-policy` 無し。HTML meta タグの CSP は対応ブラウザ・ドメイン制限・frame-ancestors 不対応など機能制限あり。T251 でセキュリティヘッダ追加が完了したが CSP は HTTP header に未追加。**根本原因 (Why1〜Why5)**: ① CSP が meta のみ → ② T251 の CloudFront Response Headers Policy 設定で CSP を含めなかった → ③ CSP は内容が長く設定ミスでサイト崩壊リスクが高い → ④ 段階導入でまず HSTS/XFO 等を入れ CSP は後回し → ⑤ 「CSP report-only モードで段階移行する」運用が CLAUDE.md / 設計に明記されていない。**仕組み的対策**: (a) CloudFront Response Headers Policy に `content-security-policy-report-only` で **report-only mode** で追加 → 1-2 週間 violation を観測 → 大きな違反が無ければ enforce mode に切替。(b) violation report 受信エンドポイント (簡易 Lambda) を立てる。(c) CSP の inline-script を nonce 化する移行を別タスクで段階導入。 | CloudFront Response Headers Policy, 新規 `lambda/csp_report/` | 2026-04-28 |

---

### 📋 本セッション (2026-04-28 17:15-17:30 JST schedule task) のなぜなぜ振り返り

**気付き**: Cowork スケジュールタスクで「実態調査」を毎日走らせる運用が機能している (T221-T262 が前 24h で 40+ 件発見・大半が実装完了)。一方で本日 17:15 時点で **本番 topics.json が 14h 更新ゼロ** という最重要 SLI が見落とされていた。

**Why1**: なぜ 14h 鮮度ゼロが見落とされたか → CloudWatch アラームでは Lambda 個別失敗のみ拾うが「success だが publish しなかった」を取れない。
**Why2**: なぜそのパターンを取る監視がないか → 監視は Lambda 内部 metric (governance worker) ベースで構築されていて「ユーザーから見える壊れ方」を独立観測する別系統が無い。
**Why3**: なぜ別系統が無いか → SLI/SLO の定義文書 (`docs/sli-slo.md` 等) が無く、何を「壊れている」と定義するかが各タスクのアドホック判断になっている。
**Why4**: なぜ SLI/SLO 定義が無いか → 一人開発・小規模本番で「動いてれば良い」マインドが続いており、明示的に SLO を文書化する優先度が他作業に負けてきた。
**Why5**: なぜ「動いてれば良い」マインドのまま放置できたか → タスク発見プロセス (本スケジュールタスク) が「ファイル単位の差分・CSS/JS 不整合」など static な部分を効率良く捕まえる一方、**動的に変化する production 状態**を体系的に curl で叩く手順が確立していなかった。

**仕組み的対策 (3つ)**:
1. **T263 を最優先実装** (freshness monitor) — 「ユーザーから見える鮮度」を独立 cron + Slack で監視。CLAUDE.md「外部観測必須」と整合。
2. **`docs/sli-slo.md` 新設** — トップレベル SLI 5-7 個 (topics.json 鮮度・トップページ HTTP/2 200 / TTL Cache hit / fetcher Lambda 成功率 / 月次 AdSense クリック率 等) を列挙し、各 SLI の警告閾値・観測コマンド・再現可能 curl/jq を併記。
3. **本スケジュールタスクの ToDo リストに「production 動的状態 curl 確認」を必須化** — 静的 HTML/JS だけでなく、毎セッション以下を必ず実行: `curl -I https://flotopic.com/ /api/topics.json /api/sitemap.xml /.well-known/security.txt` + topics.json の updatedAt 計測。

**Claude が陥っていた挙動分析 (`なぜそうしたか`)**:
- 過去のスケジュールタスクが「ファイル grep / コードレビュー / プライバシーポリシー文言比較」中心だったため、**static analysis bias** が強かった。
- production 状態の curl は CLAUDE.md にも `done.sh` にも明示的な必須化が無く、Claude は「動作確認は別タスク」として暗黙に切り離していた。
- 本日の T255 keyPoint 修正のような「すぐ効くコード fix」は applied したが、SLI 監視の不在については個別タスク (T242) として作成のみで終わり、**メタな運用不全 (= 最重要なのに後回し)** に気付くまでに 1 サイクル余分にかかっていた。

→ 結論: スケジュールタスクの prompt に「**最初に curl で本番状態を 5 分間観察し、最重要の壊れ方を探す**」を **構造として** 入れる (テキストルールではなく、scheduled-task definition の最上段に書き込む)。

---

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
