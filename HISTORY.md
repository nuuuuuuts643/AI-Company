# Flotopic 完了済みタスク履歴

> このファイルは CLAUDE.md から自動移動した完了タスクの記録。
> 参照専用。編集する場合は git commit を忘れずに。
> 最新の状態は CLAUDE.md の「現在着手中」「次フェーズのタスク」セクションを参照。

### 完了済み（2026-04-26 T105 通知既読認証）
- ✅ **T105 PUT /notifications/{handle}/read 認証追加** — コメント backend で idToken+userId が body に含まれる場合のみ verify_google_token + handle一致確認を実施。frontend (mypage.html) を同時更新して token/userId を body に含めるように変更。認証情報なしの呼び出しは後方互換のためスルー（段階移行）。

### 完了済み（2026-04-26 T103/T104）
- ✅ **T103 RSS link非canonical修正** — `proc_storage.py` line 425の`link`を`topic.html?id={tid}`（SPAリンク）から`topics/{tid}.html`（canonical静的URL）に変更。RSSリーダーからのPageRankが正規URLに集約される。
- ✅ **T104 lifecycle rstrip修正** — `lifecycle/handler.py` line 237の`key.rstrip('.json')`（文字集合除去）を`key[len('api/topic/'):-len('.json')]`（明示的サフィックス除去）に変更。UUID topicIdでは実害なかったが意味的に正しい実装に修正。

### 完了済み（2026-04-26 T098/T099/T100/T101/T102）
- ✅ **T098 imageUrl欠損トピック再処理** — `fetcher/handler.py` の `orphan_candidates` フィルタに `and t.get('imageUrl')` を追加。imageUrlなしトピックが「処理済み」と誤判定されて永久に pending_ai に入らない問題を修正。
- ✅ **T099 contact name未保存** — `contact/handler.py` の `save_to_dynamodb()` の put_item に `'name': data['name']` を追加。管理画面で送信者名が表示されるようになった。
- ✅ **T100 analytics S3バケット誤デフォルト** — `analytics/handler.py` 行25の `S3_BUCKET` デフォルトを `'flotopic-data'`（存在しない）から `'p003-news-946554699567'` に修正。Lambda環境変数未設定時のキャッシュ書き込み失敗を解消。
- ✅ **T101 tokeninfo aud未チェック** — `auth/handler.py`・`comments/handler.py`・`favorites/handler.py` の `verify_google_token()` に `aud == GOOGLE_CLIENT_ID` チェックを追加。他アプリ向けトークンでのログインを防止。`GOOGLE_CLIENT_ID` 環境変数未設定時はチェックをスキップ（後方互換）。
- ✅ **T102 comments scan Limit問題** — `comments/handler.py` の `get_user_comments()` で `Limit=500`（スキャン上限）を外してLastEvaluatedKeyページネーションに変更。ユーザーのコメントがテーブルの後半にあっても正しく取得できるようになった。

### 完了済み（2026-04-26 T079/T080）
- ✅ **T079 アフィリエイトキーワード品質フィルタ** — affiliate.js に NEWS_PATS チェック追加。20文字超かつ報道パターン含むタイトルはジャンル名フォールバックへ切り替え。
- ✅ **T080 topic.html 重複広告修正** — 同一admaxIDが2スロットで重複。2つ目（グラフ直前）を削除。SPで同じバナーが2回表示される問題を解消。

### 完了済み（2026-04-26 T077）
- ✅ **T077 静的HTML JSON-LD に datePublished・author 追加** — `proc_storage.py` の `generate_static_topic_html()` で生成する Article 構造化データに `datePublished`（lastArticleAt Unix秒→ISO文字列）と `author`（Organization: Flotopic）を追加。Google Search Console のリッチリザルト対応。次回 processor 実行時から新規生成ファイルに反映。

### 完了済み（2026-04-26 T075）
- ✅ **T075 Bluesky自動投稿 S3_BUCKET修正** — `bluesky-agent.yml` の `env:` に `S3_BUCKET: p003-news-946554699567` が未設定で、スクリプトのデフォルト `flotopic-public`（存在しないバケット）を参照して毎回失敗していた。正しいバケット名を追加して修正。JST 08:00/12:00/18:00 スケジュールが次回から正常動作するはず。

### 完了済み（2026-04-26 T074）
- ✅ **T074 admin.html サービス管理セクション追加** — AWS Console・Anthropic Console・GitHub・Google AdSense・忍者AdMax・もしもアフィリエイト・楽天アフィリエイトの7リンクカードを「サービス管理」セクションとして追加。各カードにサービスカラーのドットインジケーターとホバー時のボーダー変色を実装。`renderServiceLinks()` 関数 + `Dashboard.load()` からの呼び出し。

### 完了済み（2026-04-27 catchup.htmlバグ修正）
- ✅ **catchup.html createdAt/updatedAt フィールドバグ修正** — `topic.createdAt`/`topic.updatedAt`はtopics.jsonに存在しないフィールド。`topic.firstArticleAt`(Unix秒→ISOString)/`topic.lastUpdated`(ISO)に修正。NEWバッジ・更新時刻・期間テキストが正しく表示されるようになった。

### 完了済み（2026-04-27 T063/T064）
- ✅ **T063 CLAUDE.md肥大化対策** — 「次フェーズのタスク」の~~完了済み~~13件・解決済み未解決1件を削除。約40行削減。
- ✅ **T064 config.js コメント修正** — `// 例: 'flotopic-22'` など設定済みなのに「例：」と書いてある誤解コメントを削除。

### 完了済み（2026-04-27 T059/T061/T062）
- ✅ **T059 auth.js ログインモーダル文言修正** — 「@メンション通知」→「ジャンル設定をどのデバイスでも引き継ぎ」に変更。未実装機能を特典として宣伝するのをやめた。
- ✅ **T061 app.js ?filter URLパラメータ対応** — `?filter=rising` を初期化時に解析してcurrentStatusにセット。manifest.jsonのPWAショートカット「急上昇トピック」が正常動作するようになった。
- ✅ **T062 robots.txt Disallow: /js/auth.js 削除** — Googlebot が JS をDisallowされると CSRレンダリング不可でSEO低下するため削除。

### 完了済み（2026-04-27 T057/T058/T059確認/T060）
- ✅ **T057 admin.html 収益管理パネル追加** — 「収益管理」セクションを追加。忍者AdMax(稼働中)/AdSense(審査中)/Amazon/楽天 の4カードで各ダッシュボードへのリンク + ステータスバッジ表示。AdSense審査通過後に切り替えやすい設計。
- ✅ **T058 ICONS-NEEDED.md 削除** — `frontend/ICONS-NEEDED.md` を削除。開発ドキュメントが本番S3に公開配信されていた問題を解消。
- ✅ **T059 auth.js 確認** — 前セッション実装済み。「コメント返信・@メンション通知を受け取る」に修正済み。追加実装不要。
- ✅ **T060 twitter-card.png 削除** — ogp.pngと同一ファイル(MD5一致)。全HTMLのtwitter:imageはogp.pngを参照済みのため安全に削除。

### 完了済み（2026-04-27 T050新/T048新/T054/T055確認）
- ✅ **T050 ノイズトピックフィルタリング強化** — `lambda/fetcher/filters.py` の `_DIGEST_SKIP_PATS` にゲーム攻略wiki・レシピ系パターン9件追加。「レシピ$」「料理一覧」「攻略wiki」「キャラ編成一覧」「入手方法」「スキル一覧」「育成方法」など。fetcher 次回実行から有効。
- ✅ **T048 ファビコン修正（SVG→PNG優先）** — 全10HTMLファイルから `<link rel="icon" type="image/svg+xml" href="/icon-flotopic.svg">` を削除。PNG（dropletロゴ）のみ残し、ブラウザタブに正しいアイコン表示。
- ✅ **T054 Admin「AI要約%」誤表示修正** — `admin.html` L348 の `aiDone` 計算を `generatedSummary || generatedTitle` → `generatedSummary` のみに修正。タイトルだけ生成済みのトピックが100%に誤カウントされるバグ解消。
- ✅ **T055 storyTimeline実装確認** — detail.js に既実装済み。`meta.storyTimeline` beats を「③ 今どの段階か」セクション（ai-analysis内）に日付+イベント形式でレンダリング。追加実装不要。

### 完了済み（2026-04-26 T047残件+T048）
- ✅ **T047残件 リワインド統一** — sw.jsから`/legacy.html`を削除。legacy.htmlは既にnoindex+catchup.htmlリダイレクト済み。クロニクル→リワインド統一完了。
- ✅ **T048残件 ジャンル表記** — DynamoDB確認0件。topics.jsonの8件は旧キャッシュ。次processor実行で自動解消。

### 完了済み（2026-04-26 T050）
- ✅ **T050 アフィリエイトジャンルフィルタ** — `frontend/js/affiliate.js` に `AFFILIATE_GENRES` リストを追加。政治/国際/社会/株・金融ジャンルではウィジェット非表示。対象ジャンル: テクノロジー/グルメ/ファッション/スポーツ/エンタメ/健康/ビジネス/科学/くらし。160/434件の不適切表示を解消。

### 完了済み（2026-04-26 T048/T049）
- ✅ **T048 ジャンル表記揺れ修正** — DynamoDB p003-topics テーブル内の `genre='ファッション・美容'` / `genres=['ファッション・美容']` を144件一括修正 → `'ファッション'` に統一。残件数0確認済み。fetcher/processor は既に 'ファッション' を使用しているので再発しない。次の processor 実行で topics.json にも反映される。
- ✅ **T049 processor 4x/day化** — EventBridge `p003-processor-schedule` を `cron(0 22,10 * * ? *)` (2x/day) → `cron(0 22,16,10,4 * * ? *)` (JST 07:00/13:00/19:00/01:00 = 4x/day) に変更。CLAUDE.md 記載の「4x/day」と実態を一致させた。MAX_API_CALLS=150との組み合わせで 600 API calls/day まで処理能力向上。

### 完了済み（2026-04-26 T044/T045）
- ✅ **T044 MAX_API_CALLS 35→150復元** — proc_config.py。storyPhase 46.1% / summary 70.5% でカバレッジ80%を下回ったため150に戻す。pending 291件を4回/dayで約2日で消化見込み。
- ✅ **T045 minimal mode storyPhase='発端'デフォルト** — proc_ai.py の `_generate_story_minimal` で `'phase': ''` → `'phase': '発端'` に変更。1〜2件記事のトピックは始まったばかりの発端と判定するのが適切。

### 完了済み（2026-04-26 T028/T029-partial）
- ✅ **T028 グルメ・ファッションGENRESフィルター追加** — app.js L72とlegacy.html L189にグルメ/ファッションを追加。GENRE_EMOJIも対応（🍽️/👗）。
- ✅ **T029-partial legacy.html・catchup.htmlに広告追加** — shinobiスクリプト+ad-728-scale-wrapper（728×90 PC + 320×50 SP）追加。mypage.htmlは残作業。

### 完了済み（2026-04-26 T022/T023/T024/T025）
- ✅ **T022 モバイル広告320×50追加** — topic.html・index.htmlの728×90をPC専用（ad-pc-only）に変更し、モバイル用320×50スロット（ad-sp-only）を追加。同admax-idで320×50を試みる。効果確認後にナオヤがAdMaxで専用ID発行（T027）。
- ✅ **T023 UIコピー「ふりかえり→クロニクル」** — 12ファイル（mypage.html除く）でボトムナビ・JSON-LD・タイトルを一括変更。catchup.htmlのヒーロー: 「しばらくぶりですね👋」→「クロニクル ✦」・title/OGP/descも更新。manifest.jsonのショートカット名も変更。
- ✅ **T024 閲覧履歴クラウド同期** — favorites/handler.pyにGET/POST/DELETE /history/{userId}を追加（flotopic-favoritesテーブルPK=userId/SK=HISTORY#{topicId}・TTL30日）。frontend/js/history.jsを新規作成（ローカルとクラウドのマージ・topic.html/mypage.htmlで読み込み）。
- ✅ **T025 privacy.htmlアフィリエイト記載更新** — 「Amazonアソシエイト・プログラムおよび楽天アフィリエイト等」→「Amazonアソシエイト・プログラム、楽天アフィリエイト、もしもアフィリエイト（Amazon・楽天市場・Yahoo!ショッピング対応）等」に更新。景表法対応。

### 完了済み（2026-04-26 T021/T026）
- ✅ **T021 fetcher 384s→高速化** — cluster()でnormalize()/regex呼び出しをO(n²)→O(n)に削減（4.3M回→2070回）。_chunk_sim用チャンクも事前計算。DynamoDB書き込みを2970件逐次→batch_writer並列(20workers)に変更。S3 topic書き込み218件を並列化。各フェーズに[TIMING]ログ追加。
- ✅ **T026 MAX_API_CALLS設定根拠コメント** — proc_config.py に「35×4=140calls/day。カバレッジ80%未満になったら150に戻す」コメント追加。設定値35は変更なし。

### 完了済み（2026-04-26 T017）
- ✅ **T017 fetcher O(n²)削減** — handler.py の `topics_active` 上限を `[:1000]` → `[:500]` に変更。`find_related_topics()` は転置インデックス方式で既実装済み。`detect_topic_hierarchy()` も O(n²) → O(n·k) に inverted-index 変換（entity→topicId集合の積集合で候補絞り込み）。CloudWatch推定: 229秒→60秒以下へ改善見込み。

### 完了済み（2026-04-26 T015/T016）
- ✅ **T015 広告表記（景品表示法対応）** — topic.htmlのアフィリエイトウィジェットラベルを `PR` → `広告` に変更。privacy.htmlのアフィリエイト開示（第5条）は既実装確認。tokushoho.html氏名記入はナオヤ手動タスクとして残存。
- ✅ **T016 Blueskyジャンルハッシュタグ追加** — bluesky_agent.py の GENRE_HASHTAGS に `くらし`/`社会`/`グルメ`/`ファッション` を追加。

### 完了済み（2026-04-26 T004/T010）
- ✅ **T004 セッション自動ロール判定** — CLAUDE.md「セッション開始時」セクションに「⚡ セッション自動ロール判定」を追加。WORKING.md が空→finder / 他セッション着手中+未着手あり→implementer / 未着手なし→finderと自動判定。ナオヤが毎回ロール指定不要になった。
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
- ✅ **AWSコストアラート設定** — `flotopic-monthly-budget` 作成。月$21(70%)超で早期警告・$30(100%)超でアラートメールをmrkm.naoya643@gmail.comに送信。

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

**デプロイ**: `bash projects/P003-news-timeline/deploy.sh` で反映（次のナオヤ手動作業時に）

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
- ✅ SLACK_BOT_TOKEN GitHub Secret追加（***REDACTED-SEC3***23616-...）
- ✅ 秘書Notion統合実装 — secretary_run.pyにNotion API連携コード追加
- ✅ Cloudflare Web Analytics設置 — P003 index.html / topic.html に追加（token: 099f0d39...）
- ✅ 忍者AdMax広告設置 — P003 index.html / topic.html の ad-slot に組み込み済み
- ✅ プライバシーポリシーページ作成 — projects/P003-news-timeline/frontend/privacy.html
- ✅ P004 Slack App作成 — Bot Token取得済み（***REDACTED-SEC3***23616-...）
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
  - `scripts/audit_agent.py` — 外部監査AI（全9エージェント監視・**Claude不使用・純粋Pythonルール判定**・ナオヤさん直接Slack報告）
  - `.github/workflows/governance.yml` — 統合ガバナンスワークフロー（L1→L2→Legal→Audit の直列パイプライン）
  - **設計原則**: 監査AIはClaudeを一切呼ばない（独立性の担保）。数値閾値・パターンマッチング・統計計算のみで判断。

### 完了済みタスク（2026-04-26 基盤安定化）
- ✅ **CloudWatchログ確認ルール追加** — 「最新ログストリームのみで確認する」ルールをCLAUDE.mdに追記。24時間フィルターで修正前エラーを重大バグ扱いしてしまうミスを防ぐ
- ✅ **flotopic-notifications DynamoDBテーブル作成** — PK=handle/SK=SK/TTL=30日。p003-commentsの `get_notifications` がAccessDeniedException で落ちていた問題を解消（最新実行で再現確認済み）
- ✅ **IAMポリシー更新** — `p003-lambda-role` の `flotopic-least-privilege` に `flotopic-notifications` テーブルへのDynamoDB権限を追加
- ✅ **lifecycle SK FilterExpression バグ修正確認** — 最新デプロイ後（2026-04-26）の手動実行でValidationExceptionなし。修正が適用されていることを確認
- ✅ **スナップショット更新** — CLAUDE.mdのP003技術状態スナップショットに通知テーブル・IAM修正を記録

### 完了済み（2026-04-26）
→ T017 fetcher O(n²)削減（12:40 JST）
- `lambda/fetcher/handler.py` L433: `[:1000]` → `[:500]`（処理対象を半減）
- `lambda/fetcher/text_utils.py` `find_related_topics()`: 転置インデックス実装（entity/kw/bigram → topicId集合）により O(n²) → O(n·k) に削減
- `lambda/fetcher/text_utils.py` `detect_topic_hierarchy()`: entity_to_tids 転置インデックスで候補トピックの積集合絞り込みを追加
- CloudWatchで確認済み：Duration 229秒 → 目標60秒以下

→ T012 S3差分書き込み最適化（13:30 JST）
- `proc_storage.py`: `update_topic_s3_file` に ETag(MD5)比較を追加。`get_object` の ETag と新コンテンツの MD5 が一致する場合は `put_object` をスキップ。AI処理済みトピックの再書き込みを省略し月 $1.98 のS3書き込みコスト削減
- ✅ **T014 processor 4x/day → 2x/day** — EventBridge `cron(0 22,10 * * ? *)` (JST 7:00/19:00) が既に設定済み確認。別セッションで適用済み。Claude API 月$1.2節約。

→ T027 モバイル専用広告枠追加（14:30 JST）
- `index.html` と `topic.html` の `ad-sp-only`（320×50）スロットを PC 用 ID(`6b65a9c9ba3c1c898e167bbf103830d7`) から モバイル専用 ID(`570fe6c87677ba7c5417119c60ca979d`) に切り替え
- PC 728×90 は `ad-pc-only`（768px以上のみ表示）のまま変更なし
- shinobi スクリプトはページ1回のみ（`<head>` に既存）。重複なし確認済み
- テスト: `npm test` 42件全パス

→ T035 位置情報ダイアログをログインユーザー限定（14:40 JST）
- `app.js` L988 の `loadWeather()` 呼び出しを `if (typeof currentUser !== 'undefined' && currentUser) loadWeather();` に変更
- 未ログインユーザーが index.html を開いたときにブラウザの位置情報許可ダイアログが出る問題を修正
- ログイン済みユーザーは従来通り天気ウィジェットが動作する
- テスト: `npm test` 42件全パス

→ T030 トレンド可視化強化（14:50 JST）
- `app.js` `renderTopicCard()` に velocityScore を視覚化する velocity バーを追加
- `rising`/`peak` ステータスのカードにのみ表示。幅は `min(100, velocity*5)%`（velocity=20→100%）
- `rising` = 赤グラデーション、`peak` = 琥珀グラデーション
- `style.css` に `.velocity-bar-wrap` / `.velocity-bar` 追加。ダークモード対応済み
- declining/cooling カードには表示しない（トレンドでないトピックをクリーンに維持）
- テスト: `npm test` 42件全パス

### 完了済み（2026-04-26）T032 スナップショット棚卸し - CLAUDE.md から移動

以下のコンポーネントはすべて本番稼働中・安定済み（変動なし）

| コンポーネント | 完了内容 |
|---|---|
| deploy-p003.yml | CloudFront invalidation付き・sw.js SHA注入ステップあり |
| news-sitemap.xml | Google News Sitemap。robots.txtに記載済み |
| rss.xml | 品質フィルタ済み。同一イベント重複抑制（最大2件/イベント）・株価ticker除外 |
| クラスタリング | 【中継】【速報】プレフィックス除去でJaccard比較。SYNONYMS拡充。転置インデックス化（O(n²)→O(n·k)） |
| 株価ティッカーフィルタ | 英数字コード(325A等)・Yahoo!ファイナンス全般除外 |
| fetcher Float型エラー | floatをDynamoDBに書いていたバグ修正・Decimal変換済み |
| deploy-lambdas.yml | analytics/auth/favorites/lifecycle/cf-analytics/api の全Lambda対象 |
| view tracking | POST /analytics/event → flotopic-analytics Lambda 稼働中 |
| admin dashboard | velocity分布・AIパイプライングラフ追加済み |
| lifecycle Lambda各種修正 | archived保護・SK修正・S3孤立ファイル削除・ARCHIVE_DAYS=7・週次自動実行 |
| pending_ai.json ゾンビ蓄積 | fetcher が topics_deduped 外をqueue追加していたバグ修正。1613→245件 |
| 検索機能 | タイトル→タイトル+AI要約+ジャンルに拡張 |
| SEO/OGP | JSON-LD全静的ページ追加（legacy=CollectionPage, catchup/privacy/terms=WebPage+BreadcrumbList） |
| trendingKeywords | processorが毎回_extract_trending_keywords()で再生成。ストップワード強化 |
| processor スループット | MAX_API_CALLS 30→150（15件→75件/回） |
| fetcher S3コスト | 1605件→~194件の個別S3書き込みに削減（公開対象のみ） |
| Claude Code 確認ダイアログ | ~/.claude/settings.json に Bash/Edit/Write を allow 追加 |
| topics.json 内部フィールド除去 | SK/pendingAI/ttlをfetcher・processor両方でpublicJSONから除去 |
| fetcher _core_key重複防止 | 【中継】【速報】等プレフィックス除去でデdup精度向上 |
| コメント/お気に入りCTA | 空状態改善+モバイルスティッキーCTAバー追加 |
| processor タイトル再生成スキップ | aiGenerated=True+title既存→タイトルAPI省略 |
| Google Newsソース名 | （）/()パターン追加・フォールバック→'Google News' |
| UIボトムナビ統一 | profile.html・storymap.html修正 |
| processor _dedup_topics | topics.json再生成時のAIタイトル生成後重複防止 |
| fetcher orphan storyTimeline欠如 | generatedSummary+aiGeneratedあり但しstoryTimeline欠如のトピックをorphan追加対象に修正 |
| モバイル広告ラッパー | position:relative追加でiframeクリッピング確実化 |
| flotopic-notifications テーブル | PK=handle/SK=SK/TTL=30日。IAMポリシー(flotopic-least-privilege)に権限追加済み |
| p003-comments 通知権限 | AccessDeniedException解消 |
| 通知タブ(mypage) | 🔔 通知パネル追加。loadNotifications()で /notifications/{handle} API呼び出し |
| catchup.htmlサムネイル | imageUrlがあるトピックにサムネイル表示（80px×80px） |
| ダークモード漏れ修正 | legacy.html・storymap.htmlにtheme.js追加 |
| proc_ai.py日付パース | Unixタイムスタンプ整数に対応 |
| はてなスコア偏重修正 | 対数スケール+上限30点 |
| 急上昇ストリップ条件 | velocityScore>=3 必須条件追加（新着=急上昇バグ修正） |
| Googleディスプレイネーム非表示 | ニックネーム未設定時は「ユーザー#XXXX」(Google ID末尾4文字)表示 |
| storyTimeline繋がり強化 | transition(因果テキスト)追加・記事数で要約深さ分岐・Jaccard関連トピックリンク |
| ジャンル グルメ/ファッション追加 | GENRE_KEYWORDS追加・RSSフィード追加・app.js/legacy.html GENRESリスト追加 |
| NHKフィード削減 | 8本→6本・ソース多様性スコア強化 |
| tokushoho.html廃止 | リダイレクト化(noindex)・全フッターリンク削除・sitemap除外 |
| アフィリエイト Yahoo!ショッピング | もしもAFF経由でAmazon/楽天/Yahoo!の3店舗対応 |
| AI拒否応答フィルタ | generate_titleで40文字超・拒否語句を含む無効応答を除外 |
| モバイル広告CSS修正 | transform-origin:top center+flexbox centeringで広告左はみ出し修正（T005） |
| AIサマリー固有名詞文脈説明 | 全3プロンプトに「初出時括弧説明」ルール追加（T007） |
| 広告記事フィルタ強化 | ランキング/徹底比較/アフィリエイト/PRパターン追加（T009） |
| 長期停滞トピックarchived化 | lifecycle: 30日超lastArticleAtは強制inactive（T008） |
| get_topic_detail無制限クエリ修正 | get_item(META)+query(Limit=30/90)に分割（T011） |
| Bluesky 3問題修正 | S3 topics.json読み取り・velocityScore float化・静的URL（T013） |
| S3 ETag差分書き込み | proc_storage.py: MD5 ETag比較でスキップ。月$1.98コスト削減（T012） |
| fetcher O(n²)削減 | topics_active[:500]・転置インデックス化（T017） |
| アフィリエイト収益化基盤 | privacy.html更新・topic.htmlウィジェット枠 |
| mypage.html 広告追加 | shinobiスクリプト追加・ad-728（PC）+ ad-sp（SP）スロット追加（T029） |

→ T034 SEO内部リンク強化（15:00 JST）
- `detail.js` 関連トピック上限を5件→6件に増加（relatedTopics/childTopics両方）
- `disc-card` にサムネイル画像を追加（52×52px。imageUrlがあるトピックのみ表示）
- `.disc-card` を `display:flex` に変更、`.disc-card-body` と `.disc-card-thumb` スタイル追加
- テスト: `npm test` 42件全パス

→ T036 閲覧済みカードの視覚化（15:10 JST）
- `loadViewedTopics()` を改修: `flotopic_viewed` に加えて `flotopic_history`（閲覧履歴）のtopicIdもマージ
- これによりflotopic_historyにデータがあるユーザーのカードも正しくopacity:0.65のグレー表示になる
- `.topic-card.viewed` CSSは既存のまま（opacity:0.65/muted title/hover:0.85）
- テスト: `npm test` 42件全パス

→ T035 天気ウィジェット→急上昇ジャンル表示（15:20 JST）
- 天気取得コード（WMO定数・loadWeather関数・geolocation/Nominatim API呼び出し）を完全削除
- `renderTrendingGenres()` を追加: allTopicsのrising/peakトピックからジャンル別最大velocityを集計し、「🔥 今日は〇〇が急上昇 +N件」を1行表示
- `refreshTopics()` 内で毎回呼び出すため未ログインでも表示
- CSS: `.weather-widget` をrow方向flex・`.trend-genre-label/.count` 追加
- テスト: `npm test` 42件全パス

→ T038 ジャンル設定クラウド同期（15:30 JST）
- **Lambda** (handler.py): PREFS_SK_GENRE='PREFS#genre' 追加、get_prefs/save_prefs関数追加、GET /prefs/{userId}・PUT /prefs エンドポイント追加（idToken認証あり）
- **favorites.js**: syncGenreToCloud(genre) / loadGenreFromCloud() 追加（PUT /prefs・GET /prefs/{userId} を呼ぶ）
- **app.js**: ジャンル選択時に syncGenreToCloud() 呼び出し追加、ログイン後の初期化時に loadGenreFromCloud() で保存ジャンルを復元してfilterとrenderTopcis再適用
- テスト: `npm test` 42件全パス・Python構文チェックOK

→ T031 ファイル分割・保守性向上（15:45 JST）
- `renderAffiliate()` を `detail.js` から `frontend/js/affiliate.js` へ分離（61行）
- `topic.html` に `<script src="js/affiliate.js">` を追加（app.js の後、detail.js の前）
- detail.js は 867→806行に削減
- テスト: `npm test` 42件全パス・構文チェックOK

→ T042 モバイルキーボード表示時のレイアウト崩れ修正（16:10 JST）
- `style.css` body の `min-height: 100vh` の直後に `min-height: 100dvh` を追加
- `100dvh`（dynamic viewport height）はモバイル仮想キーボード表示時に動的に変動し、bottom-navやスティッキーCTAバーが隠れる問題を防ぐ
- `100vh` は古いブラウザ向けフォールバックとして残存

→ T040 APIエラー黙殺修正（16:15 JST）
- `loadTopics()` で `r.ok` チェックを追加（`throw new Error('topics fetch failed: HTTP ${r.status}')`）
- 非200レスポンス時に `refreshTopics()` の catch で `showErrorBanner()` が呼ばれるようになり、空白画面でユーザーが原因不明になるバグを解消
- テスト: `npm test` 42件全パス

→ T041 フィルター変更時の検索キーワード残存バグ修正（16:15 JST）
- ステータスフィルター・ジャンルフィルターのクリックハンドラに `currentSearch = ''; search-input.value = '';` を追加
- フィルター変更後に検索キーワードが残ったまま二重絞り込みされるバグを修正
- テスト: `npm test` 42件全パス

→ T043 トップページOGP動的更新（16:15 JST）
- `updateIndexOGP(genre)` 関数を追加（`buildFilters()` の直前に定義）
- ジャンルが「総合」以外の場合は「${genre}のニュースをAIがまとめて時間軸で可視化…」という説明に変更
- `meta[name="description"]` / `meta[property="og:description"]` / `meta[name="twitter:description"]` を querySelectorAll で一括更新
- ジャンルボタンクリック時に `updateIndexOGP(currentGenre)` を呼び出し
- テスト: `npm test` 42件全パス・構文チェックOK

→ T040/T041/T043 APIエラー修正・フィルターバグ修正・OGP動的更新（16:20 JST）
- T040: `app.js` topic詳細フォールバックのsilent catchを除去。renderDetail失敗時はshowError()呼び出し、fetch失敗時はconsole.errorでログ記録。空白画面バグを防止
- T041: `app.js` ジャンルフィルター変更時に`currentSearch=''`と`searchInput.value=''`をリセット。フィルター切り替え後に検索キーワードが残存していた動作を修正
- T043: `app.js` `updateIndexOGP(genre)`関数を追加。ジャンル変更時にog:description/twitter:descriptionを動的書き換え

→ T042 モバイルキーボード表示時のレイアウト崩れ修正（16:10 JST）
- `style.css` body `min-height: 100vh` の次行に `min-height: 100dvh` を追加（dynamic viewport height対応）

→ T040追加修正: detail.js r.ok対応・fallback r.ok対応・favorites CORS PUT追加（16:20 JST）
- `detail.js` の `fetchAllTopicsOnce()` に `if (!r.ok) return [];` を追加
- `app.js` の topic detail fallback（topics.json最終手段）に `if (!r3.ok) { showError(); return; }` を追加
- `lambda/favorites/handler.py` の `cors_headers()` の `Access-Control-Allow-Methods` に `PUT` を追加（T038で追加した PUT /prefs エンドポイントのCORSプリフライトが通るように）

→ UX改善: visibilitychange によるタブ復帰時自動更新（16:25 JST）
- `app.js` に `document.addEventListener('visibilitychange', ...)` を追加
- タブから離れて5分以上経過後に戻ってきた場合、即 `refreshTopics()` を呼んで古いデータを更新
- これにより長時間別タブを見た後にFlotopicに戻ったときに自動で最新情報が表示される

### 完了済み（2026-04-26 finder→implementer追加分）

→ 全fetchにr.okチェック追加（包括修正）（16:30 JST）
- `storymap.html` の topics.json/per-topic JSON fetch 2箇所に r.ok チェック追加
- `legacy.html` の topics.json fetch に r.ok チェック追加
- `mypage.html` の topics.json(×2) / notifications fetch に r.ok チェック追加
- `admin.html` の topics.json (allSettled内) に !topicsRes.value.ok チェック追加
- `comments.js` の loadComments fetch に r.ok チェック追加
- 統一的なエラーハンドリング: 全主要fetchでHTTPエラーが適切に通知されるように

→ ジャンル名ミスマッチ修正（16:35 JST）
- `lambda/fetcher/config.py` の RSS_FEEDS にて「ファッション・美容」→「ファッション」に修正（2件）
- フロントエンドの GENRES リスト（app.js）と一致していなかったため、ファッションフィルターが無効だったバグを修正

→ キーワードチップクリック時のジャンルリセット（16:40 JST）
- `app.js` の kw-chip クリックハンドラに `currentGenre = '総合'; buildFilters();` を追加
- キーワードストリップはサイト全体の急上昇ワードなので、ジャンルフィルターをリセットして全ジャンルから検索する動作に改善

→ URLパラメータ?qからの検索クエリ初期化（16:45 JST）
- `app.js` のindex.html初期化ブロックに `new URLSearchParams(location.search).get('q')` を追加
- SearchAction JSON-LDの `?q={search_term_string}` が実際に動作するように実装
- Google検索結果からサイト内検索を直接実行できるようになった

→ sw.js に affiliate.js を追加（16:50 JST）
- `sw.js` の NETWORK_FIRST_ASSETS リストに `/js/affiliate.js` を追加
- 前セッションで作成したファイルがSWキャッシュ対象外だったため、オフライン時にaffiliate機能が壊れるバグを修正

→ タブ復帰時自動更新（visibilitychange）（16:55 JST）
- `app.js` に `document.addEventListener('visibilitychange', ...)` を追加
- タブ非表示後5分以上経過して復帰した場合に `refreshTopics()` を自動実行
- 別タブで作業中に戻ってきたとき、古いデータが表示されたままにならない

→ favorites Lambda CORS PUT追加（17:00 JST）
- `lambda/favorites/handler.py` の cors_headers() `Access-Control-Allow-Methods` に `PUT` を追加
- T038で追加した `PUT /prefs` エンドポイントのCORSプリフライトが通らなかったバグを修正

→ T019 お問い合わせフォーム SES有効化（16:30 JST）
- SES検証状況: mrkm.naoya643@gmail.com = Success ✅ / flotopic.com = Pending（DNS未設定）
- SES sandbox mode のため FROM_EMAIL を未検証の contact@flotopic.com から検証済み mrkm.naoya643@gmail.com に変更
- Lambda環境変数: FROM_EMAIL=mrkm.naoya643@gmail.com, TO_EMAIL=mrkm.naoya643@gmail.com
- 実テスト送信確認済み（「送信しました」レスポンス）
- flotopic.com ドメインのDNS TXT レコード追加で contact@flotopic.com からの送信も可能になる

### 完了済み（2026-04-26）
→ HISTORY.md に移動済み（セッション継続）

#### T045 アバター保存「保存中...」のまま固まるバグ修正
- `frontend/mypage.html` `uploadAvatarBlob()` に AbortController + 30秒タイムアウト追加
- ネットワーク障害時・S3無応答時に保存ボタンが永遠にdisabledのまま固まるバグを修正
- AbortError は既存のcatchブロックで処理されsaveBtnがリセットされる

#### T046 ログインモーダルの通知文言修正
- `frontend/js/auth.js` L131: 「急上昇・続報の通知を受け取る」→「コメント返信・@メンション通知を受け取る」
- Web Push（pushManager.subscribe）は未実装なので実装済み機能に合わせた正確な文言に修正

#### profile.html r.ok チェック追加
- `loadTopicTitleMap()` 内の topics.json fetch に `if (!r.ok) throw new Error(...)` を追加

#### T046 検索時ジャンルフィルター自動リセット
- `frontend/app.js` `setupSearch()` inputハンドラに `currentGenre !== '総合'` チェックを追加
- 検索テキスト入力時にジャンルを総合にリセット → buildFilters() でUI更新 → クラウド同期
- ジャンルを選択した状態で検索すると結果ゼロになるバグを修正

#### contact Lambda auto-archive DynamoDB キー修正
- `lambda/contact/handler.py` `check_auto_archive()` の p003-topics テーブル更新キーを修正
- `Key={'PK': 'TOPIC#...', 'SK': 'META'}` → `Key={'topicId': ..., 'SK': 'META'}` (テーブルのPKは topicId)
- `ConditionExpression=Attr('PK').exists()` → `Attr('topicId').exists()` も合わせて修正
- このバグにより著作権・プライバシー申告3件以上でのトピック自動archived化が機能していなかった（silent fail）

#### T047 「クロニクル/しばらくぶり」→「リワインド」統一 + legacy.html廃止
- catchup.html: title/h1/OGP/JSON-LD「クロニクル」→「リワインド」統一
- legacy.html: noindex+catchup.htmlへのリダイレクト（旧アーカイブページ廃止）
- 全ページナビ（index/about/contact/topic/mypage/profile/storymap/catchup/privacy/terms）:
  「クロニクル」→「リワインド」、フッターの「アーカイブ(legacy.html)」リンク削除
- about.html: 機能名「しばらくぶりモード」→「リワインド」、FAQ更新
- sw.js: NETWORK_FIRST_ASSETS から重複 `/legacy.html` エントリを削除

### 完了済み（2026-04-26）T065 ストーリー表示強化
→ HISTORY.mdに記録 14:35 JST
- detail.js: storyPhase全5段階の横進捗バー（発端→拡散→ピーク→現在地→収束）を実装。現在地を明輝化、過去ステップ半透明。
- detail.js: beats を dot+縦ライン付きカード形式に刷新（ai-beat-dot-col / ai-beat-vline / ai-beat-content 構造）。最後のdotは緑色。
- style.css: ai-phase-bar / ai-phase-step / ai-beat-dot-col 等の新規スタイル追加。旧ai-beat-connector削除。
- catchup.html: storyPhaseバッジをフェーズ固有色（🌱黄/📡青/🔥赤/📍緑/✅グレー）の塗りつぶしに変更。

### 完了済み（2026-04-26）

#### T053 CloudFlare Analytics設定
- ワークフローファイル `.github/workflows/cf-analytics-setup.yml` が削除されていたため git 履歴から復元・push
- GitHub Secrets（CF_API_TOKEN・CF_ACCOUNT_ID）は2日前に登録済みだった
- `gh workflow run cf-analytics-setup.yml --field action=both` でワークフロー実行
- Lambda `flotopic-cf-analytics` の環境変数に CF_API_TOKEN・CF_ACCOUNT_ID・CF_SITE_TAG が設定済み
- `https://flotopic.com/api/cf-analytics.json` の更新確認済み（users=1, comments=2）
- CF PV=0 は RUM ビーコンのデータが蓄積中のため（構造的には正常動作）

### 完了済み（2026-04-26）T066 proc_ai.pyストーリー生成プロンプト強化
→ HISTORY.mdに記録 14:45 JST
- standard/full両モードのtimeline[].event: 20文字→40文字に拡大
- standard/full両モードのtimeline[].transition: 15文字→25文字に拡大
- standard mode max_tokens: 500→700（長いeventを切り詰めないよう）
- event/transitionルールの説明文を詳細化（体言止め・具体的固有名詞等）

### 完了済み（2026-04-26）T057 admin.html収益カード更新
→ HISTORY.mdに記録 14:55 JST
- もしもアフィリエイト（a_id=1188659）を稼働中として追加（Amazon/楽天/Yahoo! 3店舗一括）
- Amazon アソシエイト: 未申請→稼働中（flotopic-22設定済み）に修正
- Amazon リンクをdashboard URLに変更（/home/reportsへ直接リンク）
- 楽天: 引き続き未申請（AFFILIATE_RAKUTEN_ID未設定）

### 完了済み（2026-04-26）T058/T060 開発ファイル削除
→ HISTORY.mdに記録 14:55 JST
- ICONS-NEEDED.md / twitter-card.pngはすでに存在しておらず実質完了済みを確認

### 完了済み（2026-04-26）T067 CLAUDE.mdスナップショット更新
→ HISTORY.mdに記録 17:10 JST
- AI要約カバレッジを実測値に更新: summary69%(316/455)・storyPhase43%(199/455)・imageUrl62%(286/455)
- storyTimeline=0%(topics.json) → 個別ファイルにのみ存在（意図的設計）と注記追加

### 完了済み（2026-04-26）T067 CLAUDE.mdスナップショット更新
→ HISTORY.mdに記録 15:10 JST
- AI要約カバレッジ行: 既に最新値（summary69%/phase43%/imageUrl62%）が反映されていたことを確認
- T065/T066/T057の完了をスナップショットテーブルに追記
- TASKS.mdからT067削除済み

### 完了済み（2026-04-26）T058/T060 開発ファイル確認
→ HISTORY.mdに記録 15:10 JST  
- ICONS-NEEDED.md / twitter-card.pngはすでにリポジトリに存在しないことを確認（別セッションで削除済み or 未追跡）

### 完了済み（2026-04-26）T067 CLAUDE.mdスナップショット更新
→ HISTORY.mdに記録 15:15 JST
- AI要約カバレッジ行は既に最新値(summary69%/phase43%/imageUrl62%)確認済み
- T065/T066/T057の完了をスナップショットテーブルに追記
- _sanitize_timeline event[:30]→[:40] バグ修正（T066プロンプトと不一致だった）を同時修正

### 完了済み（2026-04-26）api Lambda バグ修正2件
→ HISTORY.mdに記録 15:25 JST
- dec()関数: Decimal→int変換がfloat値(velocityScore等)を切り捨てていたバグ修正（int(f) if f==int(f) else f）
- topic_detail応答: SK/pendingAI/ttlの内部フィールドをpub_metaフィルタで除去（S3プライマリパスと同様の動作に統一）

### 完了済み（2026-04-26）comments Lambda Decimal修正
→ HISTORY.mdに記録 15:30 JST
- comments/handler.py: `default=str` → `_json_serial` に変更
- likeCount/dislikeCount などDecimal値が文字列で返ってきていたバグ修正（DynamoDB返却時のDecimal→文字列→数値型不一致）
- favorites/auth/analyticsは返す値に数値Decimalなしため変更不要を確認

### 完了済み（2026-04-26）admin.html storyTimeline→storyPhase修正
→ HISTORY.mdに記録 15:40 JST
- hasTimeline: `t.storyTimeline && t.storyTimeline.length > 0` → `t.storyPhase` に変更
- storyTimelineはtopics.jsonに含まれず常に0%の無意味なメトリクスだった
- 表示ラベルも「storyTimeline 有」→「storyPhase 有」に統一

### 完了済み（2026-04-26）T068 ジャンル分類精度改善
→ HISTORY.mdに記録
- ファッションから過広キーワード(ダイエット/健康法/トレンド)削除→健康ジャンルへ移動
- GENRE_STRONG_KEYWORDS追加: 国際(北朝鮮/ミサイル/NATO等)・スポーツ(五輪/ボクシング等)は1件ヒットで強制分類
- GENRE_PRIORITY追加: 同スコア時に国際>スポーツ>ファッション優先でタイブレーク
- スポーツにボクシング/格闘技/UFC/MMA追加、国際にミサイル/核/軍事/爆撃/戦争追加

### 完了済み（2026-04-26）T069 pendingAI無限再キュー修正
→ HISTORY.mdに記録
- cnt<=2(minimal mode)はstoryTimeline不要なのに要求していたバグ
- _needs_timeline = cnt > 2 フラグ追加、pending_ai条件で(not _needs_timeline or _has_timeline)に変更
- 164件のmini-modeトピックが毎回pendingAI=Trueになる無限ループ解消
- MAX_API_CALLS=150に対してqueue=322件→実効処理量改善

### 完了済み（2026-04-26）T070 minimalモードorphanループ完全修正
→ HISTORY.mdに記録
- T069の修正に抜け穴: orphan候補ループがstoryTimeline=[]のminimalトピックを毎回再追加
- fetcher handler.py: orphan candidates条件にsummaryMode='minimal'またはarticleCount<=2を追加
- processor proc_storage.py: needs_ai_processingでis_minimal判定追加、timeline有無を問わず処理済みとみなす
- processor handler.py: needs_storyでis_minimal判定追加、minimal+aiGenerated済みなら再生成不要

### 完了済み（2026-04-26 DynamoDB肥大化対策）
- ✅ **lifecycle SNAPカットオフ 30日→7日** — fetcher の SNAP_TTL_DAYS=7 と整合。TTL属性未設定の古いSNAPも lifecycle 週次削除（月曜 02:00 UTC）で除去できるようになった。808K件 → 次週から大幅減見込み。
- ✅ **T071 tracker VIEW#アイテムにTTL 90日追加** — VIEW#{date}が無期限蓄積していた問題を修正。新規書き込み時に `ttl = now + 90*86400` を設定。DynamoDB が自動削除する。

### 完了済み（2026-04-26 T073調査）
- ✅ **T073 ファッション・美容フィルタ調査** — app.js L410 の `_GENRE_ALIAS = {'ファッション':'ファッション・美容'}` で既に対応済み。DynamoDBも0件修正済み（T048完了）。topics.jsonは次回processor実行で自動更新。実装不要と判断。

### 完了済み（2026-04-26 T078 コメント削除UX修正）
- ✅ **T078** — コメント削除時にトークン期限切れ（401）を検出
- `deleteComment()` の 401 分岐で `window._pendingCommentDelete = { topicId, commentId }` を保存
- toast: 「セッションが切れました。再ログイン後に削除を自動実行します」（5秒表示）
- `auth.js::handleGoogleCredentialResponse` に `_retryPendingDelete()` ヘルパーを追加
- 再ログイン成功後に `deleteComment()` を自動呼び出し → ユーザーが削除ボタンを再クリック不要

### 完了済み（2026-04-26 T081 Slack通知修正）
- ✅ **T081** — slack-notify.yml のシークレット名ミスマッチ修正
- workflow が `secrets.SLACK_WEBHOOK_URL` を参照していたが設定済みシークレット名は `SLACK_WEBHOOK`
- `SLACK_WEBHOOK_URL` → `SLACK_WEBHOOK` に変更（env 参照はそのまま `SLACK_WEBHOOK_URL` で問題なし）
- `continue-on-error: true` を追加して Webhook 設定なし環境でも CI がブロックされないように改善
- 全 push で HTTP 404 失敗していた問題を解消

### 完了済み（2026-04-26 T082 開発ファイル公開除去）
- ✅ **T082** — S3バケットから ICONS-NEEDED.md を削除 + 今後の混入防止
- `aws s3 rm s3://p003-news-946554699567/ICONS-NEEDED.md` で即時削除
- `deploy-p003.yml` の画像・その他同期ステップに `--exclude "*.md"` を追加
- flotopic.com/ICONS-NEEDED.md が 404 になることを確認（CF invalidation は次回 push 時に自動実行）

### 完了済み（2026-04-26 T082・T083）
→ HISTORY.mdに記録

#### T082 S3バケット開発ファイル公開除去
- `aws s3 rm s3://p003-news-946554699567/ICONS-NEEDED.md` で即時削除
- `deploy-p003.yml` の画像その他同期ステップに `--exclude "*.md"` を追加、今後の再混入を防止

#### T083 filter-weights.json 初期ファイル配置
- `api/filter-weights.json` を S3 にアップロード（28パターン全て初期値1.0）
- fetcher が毎回出していた「filter-weights.json 未作成 → デフォルト値使用」ログを解消
- lifecycle Lambda が週次で最適化する設計は維持（ファイルが存在すれば上書き読み込みされる）

### 完了済み（2026-04-26 T084 アフィリエイトキーワード修正）
- ✅ **T084** — `isNewsHeadline` チェックを廃止、常に `GENRE_KEYWORD[genre]` を使用
- 変更前: NEWS_PATSフィルタが「：」「について」等の汎用パターンでほぼ無効 → タイトルをそのまま検索キーワードに使用
- 変更後: ジャンル固定キーワード（例: テクノロジー→「ガジェット 最新」）のみ使用
- 効果: Amazonで「〇〇大臣の汚職疑惑」で検索する無意味な状態を解消、購買意図のある商品検索に統一
- コード12行削減（rawTitle取得・NEWS_PATS定義・isNewsHeadline判定・else分岐を全て削除）

### 完了済み（2026-04-26 GC/クリーンアップ・Bluesky修正）

#### 未使用import削除（fetcher/storage.py）
- `from datetime import datetime, timezone, timedelta` → `timedelta` は未使用のため削除

#### CLAUDE.md 圧縮（319→301行）
- 完了済みタスク管理ルールを12→3行に圧縮
- P002 Flutterゲーム設計概要セクション削除（briefing.md へのポインタのみに）
- セッション更新ルールセクション削除（自明なため）

#### batch_generate_static_html バグ修正
- 問題: `api/topic/*.json` の先頭500件(辞書順)を読んでいた → 5014件中の先頭500は大半が廃止IDで現在のtopicsに含まれない
- 修正: `api/topics.json` を読んで現在のアクティブ500件のIDから逆引きして生成
- 結果: topics.json/topics/{tid}.html の一致率 8% → 97%（489/500件）、Top50速度トピックの静的HTML 2/50 → 49/50

#### Bluesky自動投稿 復旧確認
- T075 S3_BUCKETバグ修正・静的HTML 97%生成により dry-run で正常投稿文生成を確認
- 投稿例: 「🔥 急上昇: 秋田県、職員を岩手県大槌町へ派遣 山林火災受け」(166文字)

### 完了済み（2026-04-26 T085 ジャンル分類根本修正）
- ✅ **T085** — ジャンル分類の設計欠陥3つを同時修正

**Fix 1: GENRE_KEYWORDS拡充**
- `'株・金融'` に `'株'` を追加（「株が上がった」等でヒットするように）
- `'科学'` に `'原子炉'`, `'原発'`, `'核融合'`, `'物理'` を追加

**Fix 2: dominant_genres() score=0フォールバック修正**
- 変更前: キーワード不一致時 → `Counter(a['genre']).most_common(1)[0][0]` = ソースフィードのジャンルを継承
- 変更後: キーワード不一致時 → `['総合']`（汎用ラベルで妥当）
- 理由: スコア0はどのジャンルにも当てはまらない記事群。フィードジャンルは検索クエリ≠ジャンル精選のため信頼できない

**Fix 3: グルメ/ファッション検索フィード genre='総合' に変更**
- 変更前: `'genre': 'グルメ'`, `'genre': 'ファッション'`
- 変更後: `'genre': '総合'`（4フィード）
- 理由: Google検索フィードはクエリマッチ記事を返すが別ジャンルの記事が混入する。ソースジャンルを'総合'にしてキーワード分類に委ねることで誤分類を防ぐ
- 効果: グルメ/ファッションキーワードを含む記事は正しく分類され、含まない記事は'総合'になる（フィード強制よりも正確）

### 完了済み（2026-04-26 T087 detail JSON欠損補完）
- ✅ **T087** — `proc_storage.py`に`backfill_missing_detail_json()`を追加し`handler.py`に`{"backfillDetailJson": true}`ルートを追加。`topics.json`の11件がapi/topic/{tid}.jsonを持たずStatic HTML生成で毎回スキップされていた。DynamoDB METAとSNAPから補完して全500件がStatic HTML生成に成功（500/500）。Bluesky OGPリンクカードも全件対応。

### 完了済み（2026-04-26 T086/T088/T089/T091 バグ修正4件）
- ✅ **T086** — `config.js`に`const _GW = _APIGW;`を追加。`app.js:992`が`_GW`参照するが未定義でDynamoDBフォールバックが無効だった。S3に存在しない古いトピック詳細ページで正常フォールバックするようになった。
- ✅ **T088** — `proc_storage.py`の`except s3.exceptions.NoSuchKey`が実際のClientErrorをキャッチできていなかった。`except Exception as e: if hasattr(e,'response') and e.response['Error']['Code']=='NoSuchKey'`に変更。StaticHTML生成で毎回11件が「失敗」と誤記録されるログノイズ解消。
- ✅ **T089** — `bluesky_agent.py`の`make_link_embed`で`client is None`のときに`fetch_image_blob`をスキップするよう修正。dry-run時にAttributeErrorが発生していたが本番投稿には影響なかった。
- ✅ **T091** — `lifecycle/handler.py`に`topics/*.html`孤立ファイル削除ブロックを追加。`s3-topic-cleanup`と同様のDynamoDB batch_get_itemで有効トピック確認→孤立HTML削除。500件超の削除済みトピックHTMLがGooglebotにクロールされ続けるSEO品質問題を週次自動修正。

### 完了済み（2026-04-26 T090/T092 API実装・ルート追加）
- ✅ **T090** — `GET /contacts`・`POST /contacts/resolve` ルートは API GW に既存。真因: Lambda invoke 権限が `POST /contact` のみで `GET /contacts` と `POST /contacts/resolve` パスが許可されていなかった。`lambda add-permission` で2ルートを追加 → 403（要管理者token）で正常動作確認。
- ✅ **T092** — `GET /prefs/{userId}` と `PUT /prefs` ルートは既に API GW に存在（RouteId: l2xib69, 14b64mq）。実際には動作していた（curl 200確認）。finder の誤検知。

### 完了済み（2026-04-26 T087 detail JSON欠損自動補完）
- ✅ **T087** — `processor/handler.py` の通常フローに `backfill_missing_detail_json()` 呼び出しを追加。この関数は既に `proc_storage.py` に実装済みだったが `event.get('backfillDetailJson')` の手動トリガーのみで自動実行されていなかった。processor 4x/day の各実行末尾で topics.json に存在するが S3 に `api/topic/{tid}.json` が無いトピックを DynamoDB から自動補完するようになった。`head_object` で存在確認 → なければ DynamoDB から META + SNAP を読んで S3 に書く。

### 完了済み（2026-04-26 T093/T094/T095/T096 バグ修正4件）
- ✅ **T093** — `fetcher/handler.py` メインループ冒頭に `if not any(a['url'] in new_urls for a in g): continue` を追加。Union-Find推移性でseen_urls記事が別トピックに混入し続ける根本バグを修正。古い記事のみのクラスターはMETA/SNAP書き込みをスキップするようになり、cross-contamination停止。
- ✅ **T094** — `processor/handler.py:102` の `_is_minimal = (topic.get('summaryMode') == 'minimal' or cnt <= 2)` を `_is_minimal = cnt <= 2` に変更。DynamoDBの古いsummaryModeフィールドに引きずられてcnt=3+のトピックが永遠にstoryTimeline未生成になる永続ループを修正。storyPhaseカバレッジ40%→改善見込み。
- ✅ **T095** — `fetcher/config.py` の `GENRE_PRIORITY` で '科学' を 'エンタメ' より前（index 8）に移動。スコア同点時にグルメがサイエンス記事に勝つ誤分類を修正。
- ✅ **T096** — `fetcher/score_utils.py` の `_parse_pubdate_ts()` に ISO 8601 フォールバックを追加。`parsedate_tz`（RFC 2822専用）がNHK/Livedoorの`"2026-04-26T12:00:00+09:00"`形式をNoneと返す → `published_ts=0` → `lifecycle='archived'` → トピック非表示になる問題を修正。`datetime.fromisoformat()`でパース成功するようになった。

### 完了済み（2026-04-26 T097 + favorites バグ修正2件）
- ✅ **T097** — `fetcher/score_utils.py:calc_score()` の recency_bonus 判定が `parsedate_tz` 直接呼び出しだったため ISO 8601 形式の NHK 記事で ×1.20 ボーナスが取れなかった問題を修正。`published_ts`（`_parse_pubdate_ts()`で既解析済み）を直接使うよう変更。`sort_by_pubdate()` も同様に `published_ts`/`publishedAt` を使うよう修正。
- ✅ **favorites GET バグ** — `favorites/handler.py:get_favorites()` が全ユーザー行（`HISTORY#*`・`PREFS#genre` も含む）を返していた問題を修正。`FilterExpression=~(Attr('topicId').begins_with('HISTORY#') | Attr('topicId').begins_with('PREFS#'))` を追加。また `delete_all_user_data()` でアカウント削除時に `PREFS#genre` アイテムが残留する問題も修正（`batch.delete_item(Key=..., PREFS_SK_GENRE)` を追加）。

### 完了済み（2026-04-26 T098 imageUrl欠損修正）
- ✅ **T098** — `fetcher/handler.py:orphan_candidates` の除外条件に `and t.get('imageUrl')` を追加。aiGenerated=True+全AI要素済みでも imageUrl が空のトピックを orphan_candidates に含め、次回 processor 実行時に OGP 画像を自動生成させるようにした。imageUrl coverage 68% 改善に向けた修正。

### 完了済み（2026-04-26 cf-analytics favorites バグ修正）
- ✅ **cf-analytics favorites stats 修正** — `cf-analytics/handler.py:fetch_favorites_stats()` がフルスキャンで `HISTORY#*` / `PREFS#genre` アイテムをお気に入りとしてカウントしていた問題を修正。post-scan filter を追加して実際のお気に入りのみを集計するようにした。

### 完了済み（2026-04-26 T099/T100/T101/T102 バグ修正4件）
- ✅ **T099** — `contact/handler.py:save_to_dynamodb()` に `'name': data['name']` を追加。お問い合わせ送信者名がDynamoDBに保存されず管理画面で確認できなかった問題を修正。
- ✅ **T100** — `analytics/handler.py:25` の `S3_BUCKET` デフォルトを `'flotopic-data'`（存在しないバケット）→ `'p003-news-946554699567'` に修正。Lambda環境変数未設定時にキャッシュ書き込みが全件失敗してDynamoDBフルスキャンが毎回走っていた。
- ✅ **T101** — `auth/handler.py`・`comments/handler.py`・`favorites/handler.py` の `verify_google_token()` に `aud == GOOGLE_CLIENT_ID` チェックを追加。他アプリ向けGoogleトークンでもログインできるセキュリティ問題を修正。
- ✅ **T102** — `comments/handler.py:get_user_comments()` の `table.scan(Limit=500)` を削除し `ExclusiveStartKey` ページネーションで全件スキャンに変更。Limitはスキャン上限であり500件目以降のコメントがヒットしない問題を修正。
