# Flotopic 完了済みタスク履歴

> このファイルは CLAUDE.md から自動移動した完了タスクの記録。
> 参照専用。編集する場合は git commit を忘れずに。
> 最新の状態は CLAUDE.md の「現在着手中」「次フェーズのタスク」セクションを参照。

### 完了済み（2026-04-26 T004/T010）
- ✅ **T004 セッション自動ロール判定** — CLAUDE.md「セッション開始時」セクションに「⚡ セッション自動ロール判定」を追加。WORKING.md が空→finder / 他セッション着手中+未着手あり→implementer / 未着手なし→finderと自動判定。POが毎回ロール指定不要になった。
- ✅ **T010 tokushoho.html再リダイレクト化** — commit 56e1be6 が廃止済みページを完全版に復活させていた。noindex+meta-refresh(→privacy.html)に戻した。sw.jsキャッシュリストからも削除。CLAUDE.md に再発防止ルール追記。

### 完了済み（2026-04-25 UI修正・広告・カード高さ揃え）

#### フロントエンドUI修正
- ✅ **ネスト`<a>`バグ修正** — `branchLabel`（🌿 N件の分岐）が`<a class="topic-card">`の中に`<a>`を埋め込んでいた。HTML仕様違反でブラウザがDOMを分割→カードが2枚に割れて表示されていた。`<span data-storymap-id>`+JSナビゲーションに変更。
- ✅ **カード高さ統一** — PC（768px+）で同行カードを`height: 100%`で揃えるCSS追加。
- ✅ **「情報精査中」バッジ化** — グレーテキスト→オレンジ枠バッジ（🔍 情報精査中）に変更。
- ✅ **広告スロット改善** — 728×90スロット幅を`max-width: 728px`で制限（左右余白削減）。空の300×250スロットを3秒後に自動非表示。「広告」バッジをラベルなしに変更。
- ✅ **sw.js `no-store`ヘッダー** — SW自体がブラウザHTTPキャッシュに保存されて更新が反映されない問題を修正。`Cache-Control: no-store`で毎回フレッシュ取得するよう変更。deploy.shも修正済み。
- ✅ **sw.js v12** — キャッシュバージョンを更新し古いキャッシュを強制クリア。

#### 既知バグ
- ⚠️ **忍者AdMax 300×250・320×50フィル率が低い** — 新規サイトのためAd在庫が少なく、728×90以外は表示されないことが多い。AdSense審査通過後に改善見込み。

### 完了済み（2026-04-25 安定化・Bluesky修正・ファイル分割）

#### Processor topics.json肥大化修正
- ✅ **processor topics.json 500件キャップ** — `get_all_topics_for_s3()` に `_cap_topics()` を追加。スコア降順上位500件のみ書き込むよう修正（旧実装は6000+件書き戻していた）
- ✅ **dec_convert Float修正** — `proc_storage.py` の `dec_convert` が整数Decimalにも `int()` を返していた。`obj == obj.to_integral_value()` で判定してfloatを正しく保持

#### Bluesky自動投稿修正
- ✅ **bluesky_agent.py postIdキー修正** — `mark_as_posted()` が `topicId` キーで書き込んでいたが、DynamoDBテーブルスキーマは `postId`。ValidationExceptionで全投稿失敗していた根本原因。
- ✅ **bluesky-agent.yml ワークフロー改修** — 3ジョブ構成を1ジョブに変更。per-job `if: github.event.schedule == '...'` が原因でスケジュール起動時に全ジョブがスキップされていた。シェルスクリプトでモード判定するよう修正。

#### フロントエンドのファイル分割（AI修正ミス防止）
- ✅ **app.js 1358→816行・detail.js（545行）新規作成** — 詳細ページ（renderDetail/trackView/updateOGP/renderDiscovery等）をdetail.jsに分離。topic.htmlにdetail.jsのscriptタグ追加。app.jsのグローバル関数をdetail.jsが参照する設計（ロード順依存）

#### fetcher Lambda軽量化
- ✅ **未使用パッケージ除去（~500KB削減）** — deploy.shのZIPコマンドからfeedparser/requests/certifi/charset_normalizer/idna/urllib3/sgmllib.pyを削除。実際にimportされていないことを確認済み。ZIP: ~500KB → 33KB

#### 既知バグ修正
- ✅ **validate_topics_exist ValidationException修正** — `table.meta.client.batch_get_item()`（ローレベルAPI）が `{'S': ...}` 型記述子を要求していた。`dynamodb.batch_get_item()`（リソースAPI）に切り替えてPython native typesで解決。

### 完了済み（2026-04-25 fetcher安定化・モジュール分割）

#### バグ修正
- ✅ **DynamoDB Float型エラー修正** — velocity/velocityScoreを`Decimal(str())`変換せずput_itemしていた。全トピック保存が失敗していた根本原因。
- ✅ **RSS 1.0/RDF ネームスペース対応を正規化** — regex置換からElementTree名前空間API（`findall('{ns}item')`）に変更。mainichi 0→20件 / NHK 0→171件 / toyokeizai 0→20件。

#### Lambda安定化
- ✅ **fetcher timeout 900s・memory 512MB・retry=0** — 300s超タイムアウト連鎖（473エラー/日）を解消。
- ✅ **processor DLQ + CloudWatchアラーム** — SQS DLQ追加・メッセージ数≥1でSNSアラーム発火。
- ✅ **fetcher エラーアラーム確認** — p003-fetcher-errors OK状態。※SNSサブスクリプションがPendingConfirmation（Gmailで確認リンク要クリック）

#### コードのモジュール分割（AI修正ミス防止）
- ✅ **handler.py 812→511行** — scoring.py（純スコア関数）/ filters.py（フィルターパターン）に分離
- ✅ **text_utils.py 467行→3ファイル** — cluster_utils.py(74行) / score_utils.py(150行) / text_utils.py(253行)

#### フィード品質改善
- ✅ **dead feeds削除** — kantei.go.jp(404)・diamond.jp(redirect)を除去
- ✅ **GitHub Actions整理** — 不要3ファイル削除、devops-agentのworkflow_run二重起動トリガー修正
- ✅ **テック系フィード追加** — CNET Japan・PC Watch・ケータイWatch（動作確認済みのRSS公開フィードのみ）

#### 未解決
- ⚠️ **seen_articles.json のSSLエラー** — Lambda上でS3アクセス時にSSL証明書エラーが散発。他のS3操作は正常なため影響小。原因未特定。

### 完了済み（2026-04-25 インフラ整理・セキュリティ強化・UI刷新）

#### ゴミ掃除
- ✅ **EventBridge `p003-schedule`（rate 5分）削除** — fetcherが5分+30分の二重実行になっていた。コスト約1/6に削減。deploy.shも修正して再発防止済み。
- ✅ **DynamoDB空テーブル2つ削除** — `flotopic-notifications`・`ai-company-threads-posts`（0件・未使用）
- ✅ **孤立Lambda `p003-tracker` 削除** — フロントエンドからもEventBridgeからも参照ゼロ
- ✅ **用済みワークフロー4ファイル削除** — apply-fixes / fix-lambda-timeout / notion-cleanup / setup-lambda-apikey

#### セキュリティ・コスト
- ✅ **Lambda IAM最小権限化** — DynamoDB/S3フルアクセスを削除し、使用テーブル・バケットのみに限定したインラインポリシーに変更。deploy.shも修正して毎デプロイ時に再適用・FullAccess自動剥奪。
- ✅ **AWSコストアラート設定** — `flotopic-monthly-budget` 作成。月$21(70%)超で早期警告・$30(100%)超でアラートメールをowner643@gmail.comに送信。

#### PWAアイコン・UIブランディング
- ✅ **PWAアイコン設定** — ユーザー提供のダークネイビー×水滴デザインを192/512/apple-touch-icon各サイズにリサイズ・S3デプロイ済み
- ✅ **OGP/Twitter Card刷新** — アイコン配色（ダークネイビー背景）のOGP画像に更新
- ✅ **UIダークテーマをアイコン色に統一** — `@media prefers-color-scheme: dark` と `[data-theme="dark"]` 両方を更新。primary: 赤→青紫(#6366f1)、accent: シアン(#38bdf8)・ティール(#14b8a6)、背景: 黒系→ダークネイビー(#13141f/#1e2035)

#### その他
- ✅ **Google Search Console認証ファイルS3デプロイ** — 登録完了済み
- ✅ **Notionプロジェクト個別ページ化** — 案件ごとに個別行として同期するよう`notion_sync.py`を修正

### 完了済み（2026-04-24 フィード鮮度・ローテーション改善）

#### P003 フロントエンドのみ（Lambda変更なし）
- ✅ **`frontend/app.js`** — 「今急上昇中」セクション（`renderHotStrip()`）を追加。`lastUpdated`が2時間以内のトピックを最大5件、velocityScore降順で横スクロールストリップ表示。空の場合はDOMごと削除（`strip.remove()`）。
- ✅ **`frontend/app.js`** — `#last-updated` を「🔄 N分前に更新」形式の相対時間表示に変更（`updateFreshnessDisplay()`）。1分未満/分/時間/日の4段階粒度。60秒ごと `setInterval` でリアルタイム更新。
- ✅ **`frontend/app.js`** — トピックカードに `card-new-badge`（NEW）バッジ追加。`lastUpdated` が1時間以内かつ非nullのトピックのみ表示。
- ✅ **`frontend/app.js`** — `lastUpdated` が `null`/`undefined`/`0` のトピックを `isNewCard` と `renderHotStrip` フィルタ両方で安全にスキップするnull guard追加。
- ✅ **`frontend/app.js`** — hot-stripチップに「（N件）」の記事件数を添える（`articleCount` フィールド使用）。
- ✅ **`frontend/style.css`** — `.card-new-badge` に `@keyframes new-pulse`（2s infinite）アニメーション追加。
- ✅ **`frontend/style.css`** — `.hot-chip:hover` に `transform: translateY(-1px)` + `box-shadow` のホバーエフェクト追加。
- ✅ **`frontend/style.css`** — `.hot-strip-chips` に `-ms-overflow-style: none` 追加（IE/Edge スクロールバー非表示対応）。

**デプロイ対象**: `bash projects/P003-news-timeline/deploy.sh`（フロントのみ。S3に `app.js`/`style.css` をアップロードするだけ）

### 完了済み（2026-04-24 防御強化: 法的・技術的）

#### 法的防御・セキュリティ強化
- ✅ **`frontend/contact.html`** — 著作権侵害申告セクションをDMCA Safe Harbor相当に強化。①権利者情報 ②侵害URLの特定 ③著作物の特定 ④誠実な申告の宣言、7営業日対応フロー、GitHub Issuesへの誘導
- ✅ **`frontend/terms.html`** — バージョン管理（v1.2 / 2026-04-24）追加。AI要約の著作権帰属を明確化（独自生成コンテンツとして明記）。第6条「コンテンツポリシーと違反の通報」追加（禁止コンテンツ・スパム・なりすましの定義と通報手順）
- ✅ **`lambda/security/middleware.py`** — レートリミット強化: `check_comment_throttle()`（30秒以内の連投ブロック）・`check_api_rate_limit()`（1分60req上限）・`rate_limit_response()`（HTTP 429 + Retry-After ヘッダー）・`get_client_ip()`（X-Forwarded-For対応）を追加。CORSヘッダーにPUTを追加。py_compile通過済み。
- ✅ **`frontend/index.html` / `topic.html` / `mypage.html`** — セキュリティヘッダー3点（Content-Security-Policy・X-Content-Type-Options: nosniff・Referrer-Policy: strict-origin-when-cross-origin）を `<head>` に追加
- ✅ **`frontend/robots.txt`** — Crawl-delay: 10 を User-agent: * セクションに追加。スクレイピング系bot（Baiduspider・SemrushBot・AhrefsBot・MJ12bot・DotBot）をDisallow追加
- ✅ **`frontend/privacy.html`** — 新規セクション追加: 3-A（アバター画像のS3保存・削除タイミング）・3-B（ハンドル名/年齢層/性別の任意収集目的）・3-C（ローカルストレージに保存するデータ種類と用途）・第9条（データポータビリティ・忘れられる権利・7営業日削除対応）

**デプロイ対象**: フロント全5ファイル（contact/terms/privacy/index/mypage/topic.html, robots.txt）+ Lambda（lambda/security/middleware.py）

### 完了済み（2026-04-24 P003 ソース品質評価・信頼性シグナル）

#### fetcher ソース品質評価と記事信頼性シグナル実装
- ✅ **`lambda/fetcher/config.py`** — RSS_FEEDSの全エントリに`tier`フィールド追加
  - Tier 1: NHK・首相官邸（一次情報・権威性高）
  - Tier 2: 朝日・毎日・ITmedia・Gigazine・ASCII・東洋経済・ダイヤモンドほか（主要メディア）
  - Tier 3: Google News・ライブドアニュース（アグリゲーター）
  - `SOURCE_TIER_MAP`: ドメイン名 → tier のフォールバックマッピング
  - `TIER_WEIGHTS`: {1: 1.3, 2: 1.0, 3: 0.8}
  - `UNCERTAINTY_PATTERNS`: 不確実表現正規表現リスト14パターン
- ✅ **`lambda/fetcher/handler.py`** — 信頼性シグナル機能を実装
  - `fetch_rss`: tier情報を記事に付与（SOURCE_TIER_MAPでフォールバック解決）
  - `detect_uncertainty(text)`: 不確実表現検出 → `'unverified'|'uncertain'|'stated'`
  - `calc_topic_reliability(articles)`: トピック全体の信頼性集計
  - `detect_numeric_conflict(articles)`: 数値の食い違い検出（2倍以上乖離 → `hasConflict: true`）
  - `apply_tier_and_diversity_scoring(articles, velocity)`:
    - Tier重み平均をvelocityScoreに乗算
    - 1社60%超 → velocityScore×0.8（ソース集中ペナルティ）
    - ユニークソース4社以上 → velocityScore×1.1（多様性ボーナス）
  - DynamoDB METAに `reliability`, `hasConflict`, `uniqueSourceCount` を保存
- ✅ **`frontend/app.js`** — トピックカードに信頼性シグナルを控えめ表示
  - 「📰 N社が報道」（1社のみは薄いグレー）
  - 「⚠️ 情報確認中」（unreliable かつスコア<80 のみ・小バッジ）
  - 「情報精査中」（hasConflict: true のみ・グレー小テキスト）
- ✅ **`frontend/style.css`** — 信頼性バッジCSS追加（`.reliability-badge`, `.conflict-badge`, `.src-count-label`）
- ✅ **Python構文チェック通過** — config.py, handler.py ともに `py_compile` エラーなし
- ✅ **JS構文チェック通過** — app.js `node --check` エラーなし

**設計方針**: 「嘘を判定する」のではなく「情報の確実度の材料を可視化」のみ。断定せずユーザーに判断材料を提供する法的リスク回避設計。

**デプロイ対象**: フロント（app.js, style.css）+ Lambda（lambda/fetcher/ config.py, handler.py）
```bash
bash projects/P003-news-timeline/deploy.sh
```

---

### 完了済み（2026-04-24 processor 言葉選びルール強化）

#### processor Lambda — 生成ストーリーの言葉選び厳格化（`lambda/processor/proc_ai.py`）
- ✅ **`generate_story` systemプロンプトに「言葉選びの厳格なルール」セクションを追加**
  - 禁止表現（評価・断定・感情語・主語曖昧表現）と代替表現を明示
  - 推奨する言葉（事実ベースの動詞・不確実情報の表現形式・時系列接続詞）を指定
  - デリケートな領域（特定個人・事件事故・企業不祥事）の追加ルールを追加
- ✅ **Python構文チェック通過** — `py_compile` エラーなし確認済み
- **目的**: 名誉毀損リスク・事実断定リスクを構造的に低減。一人運営での法的問題を予防。

**デプロイ対象**: `lambda/processor/proc_ai.py`（次の `bash deploy.sh` 時に反映）

---

### 完了済み（2026-04-24 P003 processor ストーリー型AI生成）

#### processor Lambda — AIプロンプトをストーリー型に変更（`lambda/processor/`）
- ✅ **`generate_summary` → `generate_story` に置き換え** — `proc_ai.py`。1回の呼び出しで①イベント分解②フェーズ分け③タイムラインをJSON形式で返す
- ✅ **新フィールド `timeline`・`phase` を DynamoDB に保存** — `proc_storage.py`。`update_topic_with_ai` が `storyTimeline`（配列）・`storyPhase`（文字列）を書き込む
- ✅ **`handler.py` 対応** — `generate_story` 呼び出し・`ai_updates` / S3 topics.json に `storyTimeline`・`storyPhase` を反映
- ✅ **API呼び出し回数は変わらず** — タイトル生成(1回) + ストーリー生成(1回) = 従来どおり最大2回/トピック
- ✅ **Python構文チェック通過** — `py_compile` で3ファイル全てエラーなし確認済み

**DynamoDB 新フィールド仕様**
- `generatedSummary`: ストーリー本文（`aiSummary`、自然文、1段落）
- `storyTimeline`: `[{"date": "M/D", "event": "体言止めの出来事"}]`（3〜6件）
- `storyPhase`: `"発端"` / `"拡散"` / `"ピーク"` / `"現在地"` のいずれか

**デプロイ**: `bash projects/P003-news-timeline/deploy.sh` で反映（次のPO手動作業時に）

---

### 完了済み（2026-04-24 P003 X風コメントUI強化）

#### コメント機能 X風 UI リニューアル
- ✅ **`lambda/comments/handler.py`** — `PUT /comments/like` エンドポイント追加
  - `likedBy` DynamoDB String Set + ConditionalCheck で冪等性保証（二重いいね防止）
  - `handle`・`avatarUrl` フィールドをコメント投稿時に保存対応（オプション）
  - CORS Allow-Methods に PUT 追加
  - Python構文チェック通過（py_compile）
- ✅ **`frontend/js/comments.js`** — 全面X風UIに書き換え
  - アバター表示（Googleプロフィール画像 or 頭文字イニシャル）
  - `♡ いいね数` / `🔖 保存` / `↩️ 返信` アクションボタン
  - いいね: 楽観的UI更新 + DynamoDB PUT /comments/like
  - 保存: localStorage のみ（コストゼロ）
  - 返信: テキストエリアに `@handle ` を挿入
  - `@mention` サジェスト: 既存コメントからハンドル収集 → ドロップダウン表示
  - 投稿時 handle / avatarUrl を Lambda に送信
- ✅ **`frontend/style.css`** — X風コメントカードCSS追加（モバイルファースト）
  - `.cx-comment`, `.cx-avatar`, `.cx-action-btn`, `.cx-mention`
  - `@keyframes cx-pop`（いいねアニメーション）
  - `.profile-setup-overlay` / `.profile-setup-modal`（プロフィール設定モーダル）
- ✅ **`frontend/topic.html`** — コメント投稿フォームをX風レイアウトに変更
  - アバター表示エリア追加、ハンドル表示行追加、`mention-suggest` div 追加
- ✅ **`frontend/mypage.html`** — プロフィール設定フォーム追加
  - 初回ログイン時に自動表示するモーダル（ハンドル名・年齢層・性別）
  - `flotopic_profile_set` キーで設定済み管理
  - アカウントタブにハンドル名・年齢層・性別の編集フィールド追加
  - プロフィールヘッダーに `@handle` 表示

**デプロイ対象**: フロント（topic.html, mypage.html, style.css, js/comments.js）+ Lambda（lambda/comments/handler.py）

---

### 完了済み（2026-04-24 P003保守性改善・コスト削減）

#### P003 Lambda保守性改善（fetcher / lifecycle）
- ✅ **SNAP TTL 90日→7日** — DynamoDB 662K件ブロートの根本原因を修正
- ✅ **lifecycle Lambda デプロイ** — `flotopic-lifecycle`（毎週月曜12:00 JST）。archivedトピックのSNAP削除、legacy昇格、低スコア削除
- ✅ **`cleanup_stale()`削除** — SKにFilterExpressionを使う致命的バグ（動いていなかった）
- ✅ **`log_summary_pattern()`削除** — 毎実行ごとai-company-memoryに無駄書きしていた
- ✅ **`generate_title/summary/incremental_summary()`削除** — processorに移行済みのデッドコード（-830行）
- ✅ **はてなAPI並列化** — ThreadPoolExecutorで最大3件同時呼び出し・タイムアウト5s→2s（最悪ケース750s→100s）
- ✅ **`INACTIVE_LIFECYCLE_STATUSES`定数化** — `frozenset({'legacy', 'archived'})`をconfig.pyに一元化、2箇所のフィルタが参照
- ✅ **`SITE_URL`・`SNAP_TTL_DAYS`定数化** — config.pyに集約（分散ハードコードを排除）
- ✅ **ゴミファイル削除** — `handler.py.bak`、`function_backup.zip`
- ✅ **`delete_snaps`ページネーション修正** — 1MB超のSNAPも全件削除できるよう修正

#### Notion収益可視化・コスト削減
- ✅ **notion_revenue_sync.py** — 月次収益/AWS/Claude APIコストをNotion DBに自動同期
- ✅ **revenue_agent.py** — claude-opus→claude-haikuに変更、Claude API費用推定追加
- ✅ **editorial_agent.py** — claude-opus→claude-sonnetに変更
- ✅ **notion-revenue-daily.yml** — 毎日09:00 JST自動実行

### 完了済み（2026-04-22 git競合修正・MCP設定）
- ✅ **全ワークフローgit競合修正** — 8本に `concurrency: group: git-push` + `git pull --rebase` 追加。複数エージェントの同時push競合が解消
- ✅ **AWS MCP設定** — `.mcp.json`をcore(廃止)→`awslabs.aws-mcp-server`に更新。Claude DesktopConfigも修正済み。再起動後S3/Lambda/DynamoDB操作が会話内で可能に

### 完了済み（2026-04-22 home PC作業）
- ✅ **P002 Unityフォルダ削除** — `rm -rf ~/ai-company/projects/P002-unity-game/` 実行済み
- ✅ **git push** — 654ファイルをpush完了（f7cac05）
- ✅ **P003 S3デプロイ** — catchup.html・processor Lambda・X投稿エージェント全てデプロイ済み
- ✅ **P004 Lambdaデプロイ** — Bot URL: https://pqtubmsn7kfk2nojf2kqkwqiuu0obnwc.lambda-url.ap-northeast-1.on.aws/

### 完了済みタスク（2026-04-22 X投稿エージェント・processor強化・catchup.html）

#### Processor Lambda フル実装確定
- ✅ **lambda/processor/handler.py** — `MAX_API_CALLS` を30→**10**に変更（1日3回×10=最大30呼び出し/日）
- ✅ **Slack通知をエラー時のみに変更**（`notify_slack_error`に置き換え。正常完了は通知しない）
- ✅ S3再生成エラー時のみSlack通知する実装に更新

#### X（Twitter）自動投稿エージェント
- ✅ **scripts/x_agent.py** — 新規作成（347行）。日次/週次/月次の3パターン対応
  - 日次（JST 8:00）: velocityScore降順 top3 をスレッド投稿
  - 週次（月曜 JST 9:00）: 7日間のスコア降順 top5 を1ツイート
  - 月次（1日 JST 9:00）: 30日間 top3 + ジャンル傾向コメント
  - tweepy (Twitter API v2) 使用、`_governance_check.py` による自己停止対応
  - DynamoDB `ai-company-x-posts` で重複投稿防止（TTL 30日）
  - エラー時のみSlack通知
- ✅ **.github/workflows/x-agent.yml** — 新規作成。3スケジュール + workflow_dispatch対応（dry-runオプション付き）

#### 「N日ぶりに見る」モード
- ✅ **frontend/catchup.html** — 新規作成。期間セレクター（1日/3日/7日/2週間/1ヶ月）
  - 選択期間内に「新規勃発 or 急上昇」したトピックを優先ソート
  - lifecycleStatus（active/cooling/archived）フィルタ付き
  - 各カードに「いつ始まり、どう展開したか」タイムラインテキスト表示
  - URLパラメータ `?days=7` で初期期間設定可能
- ✅ **frontend/index.html** — 「🕰️ しばらくぶり？ここから」ボタンを検索バー上に追加

### 完了済みタスク（2026-04-22 Claude API削減・2段階Lambda・UTC修正）

#### P003 Claude API 大幅削減
- ✅ **fetcher/handler.py** — Claude呼び出し完全撤廃。extractive_title/extractive_summary で即時表示。`pendingAI`フラグ追加
- ✅ **lambda/processor/handler.py** — 新規作成。1日3回（JST 7:00/12:00/18:00）バッチAI処理。条件付きClaude Haiku（MAX 30呼び出し/回）
- ✅ **deploy.sh** — processor Lambda追加。fetcher schedule: rate(30 min)（※当初rate(5 min)で設定していたが2026-04-25に30分に修正済み）、processor: cron(0 22,3,9 * * ? *)
- ✅ **コスト削減見込み**: 旧 最大80回/30分 → 新 最大30回/8時間（約97%削減）

#### GitHub Actions UTC/JST修正
- ✅ **governance.yml** — `0 15 L * *` → `0 0 1 * *` に修正（GH ActionsはL構文非対応のバグ修正）
- ✅ 全ワークフローのcron値確認完了（editorial/revenue/seo は既に正しい値だった）
- ✅ 全ファイルにJST↔UTC変換コメント追記

### 完了済みタスク（2026-04-22 セッション継続分・ストーリーマップUI刷新）

#### ストーリーマップ (storymap.html) 全面リデザイン
- ✅ **旧設計（横スクロールタイムライン）→ 新設計（1画面カードグリッド）に変更**
- ✅ **パンくずナビ** — トップ > 親トピック > 現在のトピック（3層）。グランドペアレントがあれば `storymap.html?id=` へリンク
- ✅ **コンパクトHeroカード** — タイトル・サマリー2行clamp・記事数・更新中件数・ライフサイクルバッジ
- ✅ **分岐カードグリッド** — CSS Grid auto-fill 200px。最大6枚表示 → 「さらにN件 ▼」で展開。横スクロールなし
- ✅ **カードデザイン** — タイトル2行clamp・エンティティタグ（2個まで）・記事数・最終更新の相対時間。左ボーダーでactive/cooling/archived色分け
- ✅ **関連トピックピル** — relatedTopics を横スクロールピルで表示（送客）
- ✅ **ツリー接続線** — 親topic → 分岐の装飾コネクタ（赤ドット + 横線）
- ✅ **エンティティ辞書拡充** — ガザ/パレスチナ/EU/G7/国連/岸田/石破/石油/エネルギー/貿易/制裁/軍事 追加

### 完了済みタスク（2026-04-22 セッション継続分）

#### フロントエンド (frontend/)
- ✅ **SEO** — sitemap.xml自動生成（Lambda）、robots.txt、canonical tag、動的OGP meta（updateOGP関数）
- ✅ **UX** — ⭐お気に入りのみ表示トグル、読了時間目安（📄 N件 · 約N分）、「もっと見る」ページネーション20件
- ✅ **CSS** — ジャンル別ボーダーカラー、急上昇パルスアニメーション、モバイル1カラム、スケルトンローディング
- ✅ **ストーリータイムライン** — 時系列グルーピング、「全N件」サマリー、「🔗 関連記事」セクション
- ✅ **NEWバッジ** — タイムライン内6時間以内の記事に赤いNEWバッジ
- ✅ **グラフ期間拡張** — 1ヶ月/3ヶ月/半年/1年 ボタン追加
- ✅ **並び順切替** — 新しい順 / 古い順 トグル（古い順は30日ウィンドウ制限付き）
- ✅ **PWA** — manifest.json v2（ショートカット）、sw.js v2（キャッシュ戦略/プッシュ通知）、インストールバナー
- ✅ **急上昇キーワードストリップ** — 検索バー下に動的ハッシュタグチップ（横スクロール、クリックで検索）
- ✅ **関連トピック送客** — 「🌿 関連する分岐トピック」セクション（エンティティ重複でスコアリング）
- ✅ **レガシーページ** — legacy.html（アーカイブトピック一覧）
- ✅ **マイページ** — mypage.html（お気に入り・閲覧履歴・アカウント管理）
- ✅ **ICONS-NEEDED.md** — 必要アイコンサイズ一覧（素材不足の明示）

#### Lambda (lambda/)
- ✅ **analytics/handler.py** — 新規/リピーター判定（isNewViewer）、new_viewer_ratio計算、trending集計強化
- ✅ **fetcher/handler.py** — RSSソース追加（読売/毎日/朝日/ITmedia/Gizmodo/日経/ダイヤモンド）
- ✅ **fetcher/handler.py** — フレッシュネス時間減衰・ベロシティスコア・ソース独占ペナルティ
- ✅ **fetcher/handler.py** — lifecycleStatus（active/cooling/archived、記事速度ベース判定）
- ✅ **fetcher/handler.py** — extract_source_name()でnews.google.comを実際の媒体名に変換
- ✅ **fetcher/handler.py** — extract_trending_keywords()でtrendingKeywordsをtopics.jsonに追加
- ✅ **fetcher/handler.py** — find_related_topics()でエンティティ重複によるrelatedTopics生成
- ✅ **lifecycle/handler.py** — 週次トピック整理Lambda（legacy昇格/低スコア削除）

#### インフラ (deploy.sh / scripts/)
- ✅ **deploy.sh** — GOOGLE_CLIENT_ID保持、Lambda同時実行数制限、lifecycle Lambda追加
- ✅ **editorial_agent.py** — DynamoDBアナリティクス連携（先週トップPV）
- ✅ **weekly_digest.py** — dark navy テンプレート、digest/YYYY-WW.html形式
- ✅ **ceo_run.py** — 週次読者品質分析（新規率/リピーター率）追加
- ✅ **ceo-constitution.md** — 読者品質モニタリングルール追加
- ✅ **analytics-guide.md** / **react-native-roadmap.md** — docs/に追加

### 完了済みタスク（2026-04-22）
- ✅ P006 収益管理AI実装 — scripts/revenue_agent.py（310行）+ .github/workflows/revenue-agent.yml + dashboard/revenue-log.md 作成。毎週月曜09:30 JST自動実行。
- ✅ `deploy-all.sh` 実行 — CEO agent・GitHub push・P003 S3デプロイ完了
- ✅ Computer use（Claude in Chrome）有効化
- ✅ Slack webhook更新（SLACK_WEBHOOK_URL → B0AUJ9K64KE）通知到達確認済み
- ✅ CEO日次実行 Run #2（24751739955）成功・Slack通知届いた
- ✅ P005 DynamoDBメモリ統合 — `ceo_run.py` / `secretary_run.py` に load_memory / save_memory 追加
- ✅ NOTION_API_KEY GitHub Secret追加 — 秘書Notion連携が次回実行から有効
- ✅ SLACK_BOT_TOKEN GitHub Secret追加（xoxb-8970641423616-...）
- ✅ 秘書Notion統合実装 — secretary_run.pyにNotion API連携コード追加
- ✅ Cloudflare Web Analytics設置 — P003 index.html / topic.html に追加（token: 099f0d39...）
- ✅ 忍者AdMax広告設置 — P003 index.html / topic.html の ad-slot に組み込み済み
- ✅ プライバシーポリシーページ作成 — projects/P003-news-timeline/frontend/privacy.html
- ✅ P004 Slack App作成 — Bot Token取得済み（xoxb-8970641423616-...）
- ✅ P003品質改善5点完了（2026-04-22）:
  1. AI要約修正 — cnt>=3→cnt>=2、app.jsセレクタバグ修正
  2. 差分更新実装 — seen_articles.json(S3)で前回URL比較、新記事なし→即終了
  3. AIタイトル強化 — cnt>=1で生成、概念的まとめタイトルプロンプト改善
  4. 重複排除改善 — Union-Findクラスタリング、閾値0.3→0.25
  5. コメント掲示板 — lambda/comments/handler.py + DynamoDB ai-company-comments + UI実装 + deploy.sh更新

### 完了済みタスク（2026-04-22 統合ガバナンスシステム実装）
- ✅ **統合ガバナンスシステム実装** — SecurityAI / LegalAI / AuditAI + 共通モジュール + governance.yml
  - `scripts/_governance_check.py` — 全エージェント共通自己停止モジュール（DynamoDB agent-status確認）
  - `scripts/security_agent.py` — 3層セキュリティ監査AI（L1: シークレットスキャン / L2: 脆弱性・S3・IAM / L3: 週次レポート）
  - `scripts/legal_agent.py` — 3層リーガルチェックAI（L1: アセットライセンス / L2: デプロイ前確認 / L3: 月次規約変更）
  - `scripts/audit_agent.py` — 外部監査AI（全9エージェント監視・**Claude不使用・純粋Pythonルール判定**・POさん直接Slack報告）
  - `.github/workflows/governance.yml` — 統合ガバナンスワークフロー（L1→L2→Legal→Audit の直列パイプライン）
  - **設計原則**: 監査AIはClaudeを一切呼ばない（独立性の担保）。数値閾値・パターンマッチング・統計計算のみで判断。

### 完了済みタスク（2026-04-26 基盤安定化）
- ✅ **CloudWatchログ確認ルール追加** — 「最新ログストリームのみで確認する」ルールをCLAUDE.mdに追記。24時間フィルターで修正前エラーを重大バグ扱いしてしまうミスを防ぐ
- ✅ **flotopic-notifications DynamoDBテーブル作成** — PK=handle/SK=SK/TTL=30日。p003-commentsの `get_notifications` がAccessDeniedException で落ちていた問題を解消（最新実行で再現確認済み）
- ✅ **IAMポリシー更新** — `p003-lambda-role` の `flotopic-least-privilege` に `flotopic-notifications` テーブルへのDynamoDB権限を追加
- ✅ **lifecycle SK FilterExpression バグ修正確認** — 最新デプロイ後（2026-04-26）の手動実行でValidationExceptionなし。修正が適用されていることを確認
- ✅ **スナップショット更新** — CLAUDE.mdのP003技術状態スナップショットに通知テーブル・IAM修正を記録

### 完了済み（2026-04-26）
→ T012 S3差分書き込み最適化（13:30 JST）
- `proc_storage.py`: `update_topic_s3_file` に ETag(MD5)比較を追加。`get_object` の ETag と新コンテンツの MD5 が一致する場合は `put_object` をスキップ。AI処理済みトピックの再書き込みを省略し月 $1.98 のS3書き込みコスト削減
