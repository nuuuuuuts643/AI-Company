# Lessons Learned（なぜなぜ分析の事例集）

> このファイルは過去に発生した事件の Why1〜Why5 構造化分析と仕組み的対策の保管庫。
> CLAUDE.md から append-only で外出ししている。新規事件のなぜなぜは本ファイル末尾に追記する。
> 既存ルールの根拠を確認したい時に参照する。CLAUDE.md は規則本体に集中する。

---

## 索引（追記時はここにも追加）

- 2026-04-27 なぜなぜ分析を「忘れる」現象自体のメタなぜなぜ
- 2026-04-27 ads.txt 欠落（新規外部システム統合の必須3ステップ）
- 2026-04-27 クラスタリング過分割（品質メトリクス不在）
- 2026-04-27 Claude API JSON 構文エラー（band-aid 排除原則）
- 2026-04-27 Claude が境界値テストを書かない（フォーマッタ boundary test 必須化）
- 2026-04-27 Discovery セクション「0件 · 1/1」表示バグ
- 2026-04-27 perspectives 100% null（AI フィールド null 検出 SLI）
- 2026-04-28 Lambda Timeout で in-flight 中断（wallclock guard 必須化）
- 2026-04-28 Cowork↔Code 連携の構造的欠陥（外部観測 SLI と needs-push）
- 2026-04-28 運用ルールの仕組み化メタなぜなぜ（TASKS.md 肥大化・git lock 退避不完全・タスクID 重複・起動コスト過大）

---

## なぜなぜ分析を「忘れる」現象自体のなぜなぜ（2026-04-27 制定・メタ事象）

**起きたこと**: ads.txt 事件のなぜなぜ分析を Claude が要求された時、テーブル1行追記で済ませて Why1〜Why5 構造化分析を書かなかった。POから「ちゃんとなぜなぜやったんだろうな？」と指摘されて初めてやり直した。

| Why | 答え |
|---|---|
| **Why1** なぜテーブル1行で済ませた？ | 「再発防止ルール=表に1行追記」という浅い解釈で完了とみなした |
| **Why2** なぜそんな浅い解釈をした？ | CLAUDE.md の「再発防止ルール」テーブル形式を見て、これに1行加えれば形式的に整うと判断した。なぜなぜ分析の構造化(Why1〜Why5)が必須要件だと内面化していなかった |
| **Why3** なぜ内面化していなかった？ | 既存ルール記述が「なぜなぜ分析を実施しCLAUDE.mdに追記する」と緩く、「Why1〜Why5構造で」と明示的に書かれていなかった |
| **Why4** なぜ規則がそう緩く書かれていた？ | 過去のCLAUDE.md整備時には「なぜなぜしろ」が暗黙に「5段階で構造化しろ」を含むという前提だった。だが LLM (私) はその暗黙前提を読めず、表面的な解釈で動く |
| **Why5** なぜLLM特有の挙動への対応が漏れていた？ | CLAUDE.md は人間運用前提で書かれ、LLMが規則を文字通り狭く解釈する性質に対する明示的なガード(「形式的に1行追記は再発防止と呼ばない」など) が組み込まれていなかった |

**仕組み的対策:**
1. CLAUDE.md ルール明文化: 「再発防止ルール追記=Why1〜Why5構造+仕組み的対策が揃って初めて再発防止」「テーブル1行追記は再発防止ではない」を明記
2. 構造テンプレート提示: 既存事例を本ファイルに残しておくことで、LLMが形式を真似しやすくする
3. チェックリスト化: 再発防止 commit の前に自問する 4 項目:
   - □ Why1〜Why5 を全部書いたか
   - □ 各 Why に対して具体的な答えがあるか（「気を付ける」「注意する」は答えではない）
   - □ 仕組み的な対策を3つ以上書いたか
   - □ 「次に同じ事象が起きた時、この対策で本当に防げるか」を声に出して検証したか

---

## ads.txt 欠落 なぜなぜ分析（2026-04-27 制定）

**起きたこと**: AdSense管理画面で「ads.txt: 不明」のまま審査が止まっていた。原因は ads.txt に AdSense の pub-id 行 (`google.com, pub-XXXXXXXXXXXXXXXX, DIRECT, f08c47fec0942fa0`) が無かったこと。本番には忍者AdMaxの行のみ存在。

| Why | 答え |
|---|---|
| **Why1** なぜ AdSense ステータスが「不明」のままだった？ | ads.txt に AdSense の pub-id 行が無かった。Googleはads.txtを独立にクロールしてpub-id宣言を確認するため、行が無ければ宣言不存在 |
| **Why2** なぜ ads.txt に必要な行が無かった？ | AdSense を index.html に組み込んだ時 (script タグ追加した時)、ads.txt を一緒に更新しなかった |
| **Why3** なぜ script タグだけ追加して ads.txt を更新しなかった？ | 「pub-id を script に書けば AdSense は自動的に読みに来る」と勘違いしていた。ads.txt が独立ファイルで Google が別途クロールする仕様を理解していなかった |
| **Why4** なぜそれを理解していなかった？ | 広告ネットワーク統合の手順チェックリストが存在しなかった。新規ベンダー追加時に「①公式ドキュメントを通読 ②必要ファイル全部リスト化 ③全部実装してから完了宣言」というルールが無かった |
| **Why5** なぜそういうルールが無かった？ | 広告ネットワーク統合は P003 で初めての種類のタスクだった。「新規外部システム統合」を一般化したルールが CLAUDE.md に存在せず、その都度の場当たり対応になっていた |

**仕組み的対策:**

1. **新規外部システム統合時の必須3ステップ:**
   - STEP1: 公式ドキュメント通読 — Anthropic, AdSense, AdMax, Bluesky 等の公式統合ドキュメントを最初から最後まで読む
   - STEP2: 必須ファイル全リスト化 — 「index.html scriptタグ」「ads.txt」「robots.txt」「manifest.json」「policy.html」「security.txt」「sitemap.xml」など、外部システムが読みに来る全ファイルをリスト化
   - STEP3: 全部実装→外部管理画面で「Verified」確認してから完了宣言
2. CI チェック追加候補: `index.html` の `client=ca-pub-XXXXXX` から pub-id を抽出 → `ads.txt` に該当行があるかチェック
3. 同種の「外部システムが独立に読みに来るファイル」を一覧化:
   - 広告関連: ads.txt, app-ads.txt
   - 検索エンジン関連: robots.txt, sitemap.xml, llms.txt, llms-full.txt
   - PWA: manifest.json, sw.js
   - 検証ファイル: google-site-verification 等の所有権確認 HTML
   - セキュリティ: security.txt (RFC 9116), .well-known/

---

## クラスタリング過分割 なぜなぜ分析（2026-04-27 制定）

**起きたこと**: ユーザー指摘「追加情報がトピックになってる。ストーリーではなく」「全記事トピックにしてる感」。実測で 78%(90/114) のトピックが 2-3 件しかなく、本来 1 ストーリーで追えるべき派生記事 (例: 北海道地震本体 と JR北海道運転見合わせ) が別トピックに分裂。

| Why | 答え |
|---|---|
| **Why1** なぜ 78% が 2-3 件トピック？ | cluster_utils.py の閾値 (`JACCARD_THRESHOLD=0.35` / `_CHUNK_THRESHOLD=0.30`) が「同じ事象の派生」を別トピックと判定する |
| **Why2** なぜ閾値がそんなに厳しい？ | 過去に「異なる人名で別事件が誤マージ」事故を防ぐため高めに設定された経緯。エンティティパターン+主語チェックも入った今は緩めても安全だが再評価していない |
| **Why3** なぜ閾値の再評価がされていない？ | クラスタリング品質を「マージ過剰 vs 分割過剰」のメトリクスで定量化する仕組みがない |
| **Why4** なぜ品質メトリクスがない？ | 「正解クラスタリング」は人間判断が必要で教師データ作成が重く PoC 段階で後回しにされた |
| **Why5** なぜリビジットされない？ | 既存品質の体系的計測は「重要だが緊急ではない」枠に入り、AdSense 審査・新機能投入が常に優先される |

**仕組み的対策:**
1. fetcher 出力に observability metric: 各 fetch サイクル末尾で `[CLUSTER_QUALITY] avg_articles_per_topic=X pct_2_3_articles=Y%` を CloudWatch 出力。governance worker が weekly 集計して 70% 超なら Slack 警告
2. クラスタリング閾値変更ルール: staging で 1cycle 観測 + 粒度分布 before/after を commit メッセージに必須記載
3. post-cluster merge pass: 2-3 件トピックを近接巨大トピックに親子化する後処理
4. CI ガード: `JACCARD_THRESHOLD`/`_CHUNK_THRESHOLD` の値を変更する PR では commit メッセージに必ず "[cluster-tune]" タグと before/after 粒度分布を含める

---

## Claude API の `Expecting ',' delimiter` JSON 構文エラー なぜなぜ分析（2026-04-27 制定）

**起きたこと**: forceRegenerateAll 実行中の CloudWatch ログで `generate_story (full) error: Expecting ',' delimiter` が頻発。Claude Haiku が JSON 出力で軽微な構文ミスを起こし、`json.loads` で fail → AI 処理がスキップされて perspectives/keyPoint/background 等が空のままになる。

| Why | 答え |
|---|---|
| **Why1** なぜ Claude が malformed JSON を返す？ | プレーンテキスト生成中に長い日本語文字列・引用符・括弧を扱う際、確率的に JSON 構文を崩す。LLM の本質的特性 |
| **Why2** なぜ我々はそれを防がない？ | API 呼び出しを `messages` の自由テキスト生成モードで使い、出力形式を「プロンプトの中で頼んでいる」だけで強制していない |
| **Why3** なぜ強制していない？ | Anthropic は Tool Use (function calling) で JSON Schema による structured output を提供しているが、当初開発では「プロンプト指定で十分」と判断して実装が text-mode 止まり |
| **Why4** なぜ Tool Use 移行が遅れた？ | 動作している間は再構築コストが見合わないという判断が継続 |
| **Why5** なぜブロッキングと判定する仕組みが無かった？ | JSON parse 失敗率を測定する metric が無く、CloudWatch ログを目視するまで顕在化しなかった |

**仕組み的対策（band-aid 排除・本格対応）:**
1. Anthropic Tool Use API 移行: `_call_claude_tool` ヘルパで tool_use 経由 → input_schema で JSON Schema 厳格化 → malformed JSON は物理的に発生しない
2. JSON parse 失敗率 CloudWatch metric: `[METRIC]` ログで集計し閾値超過で Slack 警告
3. **band-aid 排除原則**: prefill による補助・lenient parsing による recovery は使わない。malformed が起きうる API 設計を放置せず Tool Use で根絶する
4. なぜなぜを書く目的の明文化: 『なぜなぜは band-aid を避けて root cause + 仕組み対策を見つけるための強制装置』

---

## Claude が境界値テストを書かないままフォーマッタを書いてしまう、メタなぜなぜ（2026-04-27 制定）

**起きたこと**: Claude が過去に書いた `fmtElapsed(0)` が `1970-01-01` 由来の `1/1` を返し本番に漏れた。fmtElapsed のような汎用フォーマッタは boundary case (0/null/undefined/NaN/未来日付) を全部試すべきだったのに書かなかった。

| Why | 答え |
|---|---|
| **Why1** なぜ Claude が boundary 漏れを見逃した？ | 編集対象の immediate な意図 (経過時間表示) しか追わず、副作用となる falsy 値の挙動を網羅検証していなかった |
| **Why2** なぜ網羅検証しない？ | 単発の関数追加・修正で「動いた」が確認できれば push する習慣で、テストファースト的に boundary を書く運用になっていなかった |
| **Why3** なぜそういう習慣になっている？ | プロンプト・ルールに「フォーマッタを書いた時は boundary unit test を同 commit で書く」が明示されていなかった |
| **Why4** なぜ明示ルールがない？ | これまでフォーマッタ系のバグが顕在化せずに済んでいたので、再発防止ルール化のトリガーが無かった |
| **Why5** なぜルール化されないと Claude は動けない？ | LLM (私) は『目の前の指示』に最適化する傾向があり、目の前の指示が「fmtElapsed を直して」だと boundary 網羅まで自発的にやらない |

**仕組み的対策:**
1. safe_format.js モジュール化: 個別プロジェクトの inline 関数ではなく汎用ライブラリに切り出す
2. boundary unit test 並走: `tests/safe_format.test.js` で 0/null/undefined/'/NaN/1989年/未来 を全部 assert
3. CI grep: `fmtElapsed.*\|\|\s*0` パターンを CI で検出
4. メタルール: 新規フォーマッタ追加時は必ず 0/null/undefined/NaN/未来 5 ケースを test ファイルにアサート

---

## Discovery セクション「0件 · 1/1」表示バグ なぜなぜ分析（2026-04-27 制定）

**起きたこと**: ユーザー指摘『なんだこれ。。』 + topic detail の「🔗 この話に繋がる別の話」カード5枚が全部「0件 · 1/1」表示。1/1 は1970-01-01 の Date 由来。

| Why | 答え |
|---|---|
| **Why1** なぜ「0件 · 1/1」が出たか | fmtElapsed(0) が `new Date(0*1000)=1970-01-01` を返し `1/1` 表示。`t.articleCount=undefined` の `\|\| 0` フォールバックで `0件` 表示 |
| **Why2** なぜ t に articleCount/lastArticleAt が無い？ | 子トピック ref `meta.childTopics: [{topicId,title}]` には articleCount/lastArticleAt が無く、tMap (topics.json由来) で見つからない場合 (子が archived 等で表示外) bare ref に fallback してしまっていた |
| **Why3** なぜ tMap で見つからない子が出る？ | topics.json には active/cooling のみ載せる仕様 (archived は除外) |
| **Why4** なぜ fmtElapsed が 0 を 1/1 にする？ | 関数が `if isoOrTs == 0` のガードを持っていなかった。NaN ガードはあるが epoch=0 は valid Date として通る |
| **Why5** なぜそういう脆弱な fallback が放置された？ | 子トピックの「title だけ持つ参照」 vs 「全フィールド持つ参照」の二種類が混在する設計が文書化されておらず、UI 側はどちらでも動くべきという暗黙前提だけで本番に出ていた |

**仕組み的対策:**
1. fmtElapsed 防御強化: `isoOrTs === 0/'0'` を early-return + 1990年以前の Date を無効化
2. disc-card フッター: 無効値は表示しない (cnt=0 は非表示、ago='' は非表示)
3. fetcher が childTopics に articleCount/lastArticleAt/lifecycleStatus を埋める
4. ルール: 「list 系 ref は最低限 articleCount・lastArticleAt・title・topicId・lifecycleStatus を含むこと」

---

## perspectives 100% null なぜなぜ分析（2026-04-27 制定）

**起きたこと**: 公開トピック 114 件すべての `perspectives` (📰 メディアの見方のズレ) フィールドが空。Flotopic の独自価値として打ち出している「メディア間ズレ可視化」が事実上未稼働。

| Why | 答え |
|---|---|
| **Why1** なぜ perspectives が常に null？ | proc_ai.py の prompt が「同じ手段を同じ結論で報じてるなら null」と明記しており、Claude Haiku が保守的に常に null を返している |
| **Why2** なぜ Claude が常に null と判定する？ | 渡されている入力が記事タイトル + 概要短文だけで、媒体ごとの編集スタンスが見抜けない |
| **Why3** なぜ記事本文を渡していない？ | コスト削減。本文を全件渡すとトークン数が 4-5 倍になり予算が約 4 倍要する |
| **Why4** なぜ本文ありを許容しない？ | 1日 200 calls (`MAX_API_CALLS=200`) の AI 予算制約 |
| **Why5** なぜ予算がきつい？ | 広告収益 (AdSense 審査中) が確立していないため |

**仕組み的対策:**
1. perspectives の null fallback: AI が null を返した場合、最低でも「主要 3 ソース名 + 報道社数」を perspectives_lite として埋める
2. prompt リライト: null を出させにくく
3. AdSense 通過後の段階的本文付き
4. **AI フィールド null 100% 検出**: `topics.json` を毎週 governance check で読み、`perspectives`/`background`/`outlook` のいずれかが 0% 充填なら Slack 警告

---

## Lambda Timeout で in-flight 中断 → topics.json に aiGenerated=True が反映されない なぜなぜ分析（2026-04-28 制定）

**起きたこと**: T218 で大規模・中規模トピック合計 21 件が `aiGenerated=None/False` のまま topics.json に残存。CloudWatch ログで `Duration: 900000.00 ms ... Status: timeout`。Tier-0 優先度ロジックは実装済みだが、処理が走り切る前に Lambda が timeout で in-flight 中断 → S3 書き戻しフェーズが走らず、processed 件の `aiGenerated=True` がユーザーに見える topics.json に反映されないまま終わる。

| Why | 答え |
|---|---|
| **Why1** なぜ aiGenerated=False が topics.json に残った？ | Lambda が 900秒 timeout で強制終了し、ループ後の S3 書き戻しフェーズが走らない |
| **Why2** なぜ Lambda が timeout した？ | MAX_API_CALLS=200 を消化しきる前に 900s 経過。Tool Use 化で 1 API call が 5-15 秒に膨張、200 × 平均 10s = 2000s |
| **Why3** なぜ API call が膨張した？ | Anthropic Tool Use の structured output は input_schema validation で server-side 処理時間が増える + max_tokens=1700 のレスポンス生成時間が長い |
| **Why4** なぜそれを処理予算に反映していなかった？ | 主ループのガードが `MAX_API_CALLS` (回数ベース) のみ。Lambda Timeout (時間ベース) との突き合わせをしていなかった |
| **Why5** なぜ単位の不整合が放置された？ | API モード変更 (text → Tool Use) が API call 時間という観測しづらい次元の制約を変えたため。「Lambda 残り時間」を測って break する wallclock guard が無いと、実装速度の変化が無音で予算超過に変わる |

**仕組み的対策:**
1. Wallclock guard 実装: `handler.py` の主ループ先頭で `context.get_remaining_time_in_millis()` を測り、残り 120 秒未満なら break
2. **CLAUDE.md ルール: Lambda 主ループ wallclock guard 必須**: Lambda Timeout 値・1 call 想定時間・上限呼び出し回数の三者整合性を変更時にコメントで明示
3. CloudWatch metric: 1 サイクルあたりの「processed 件数 / wallclock 残秒 / API call 平均所要秒」を `[METRIC]` ログで出力
4. 処理単位を時間ベースに正規化: MAX_API_CALLS を `MAX_WALLCLOCK_SECONDS` 派生にする
5. forceRegenerateAll の分割実行を仕様明記: 1 invoke で全部終わらないことを前提に、次回スケジュール (4x/day) で続きを処理する設計

---

## Cowork↔Code 連携の構造的欠陥 メタなぜなぜ分析（2026-04-28 制定）

**起きたこと**: 2026-04-28 01:14 JST のスケジュールタスクで `https://flotopic.com/api/topics.json` の `updatedAt` が 12 時間前のままだった。原因は T218 の Lambda wallclock guard 修正が `git status` で working dir に滞留しており（Cowork が作成したが push できないため）、その間 4 サイクル分のスケジュールが空振りしていた。**ユーザーから見ると本番が壊れているのに誰も気づいていなかった**。

| Why | 答え |
|---|---|
| **Why1** なぜ topics.json が 12 時間古かった？ | T218 修正が working dir に滞留し、Lambda 本体が修正前バイナリで動き続け、各サイクルで 900s timeout → in-flight 中断 → topics.json が更新されない |
| **Why2** なぜ修正が滞留した？ | 過去の制定ルール「Cowork は git を叩かない」で Cowork がコードを編集しても push できず、Code セッション起動まで本番に届かない構造になっていた |
| **Why3** なぜ Code 起動が遅れた？ | Cowork セッションが「修正完了」「あとは Code が push するだけ」とユーザーに伝えても、ユーザーが Code を開く動機（朝のメール・通知等）が無いため、ユーザーの自然な活動時間まで滞留する |
| **Why4** なぜ滞留中の障害を別経路で検知できない？ | 「Lambda 個別の成功/失敗」を見る CloudWatch アラームはあるが、「ユーザーが見るデータが新鮮か」を直接モニタする SLI が無い |
| **Why5** なぜ SLI 設計が後回し？ | これまでの「再発防止ルール」は **コード変更時の自己チェック (negative rule)** に偏り、**運用時に外部から状態を観測する仕組み (positive monitoring)** が手薄だった |

**仕組み的対策:**
1. **topics.json 鮮度 SLI モニタ新設**: 1 時間ごとに `(now - updatedAt) > 90 min` を Slack 警告。governance worker と独立に走らせる
2. WORKING.md `needs-push` カラム追加: Cowork がコードファイル編集時に `needs-push: yes` を立てる
3. AI フィールド データフロー文書: `proc_ai → ai_updates → topics.json + per-topic.json + DynamoDB → frontend` の 5 層を明示
4. **`Verified:` commit gate**: 完了 commit に `Verified: <url>:<status>:<timestamp>` を必須化。pre-commit hook で物理的に reject
5. タスクID 衝突防止: `scripts/next_task_id.sh` で日付+短ID 採番、CI で重複検出
6. **Cowork も git push する運用に転換**: 「Cowork は git 叩かない」を改訂。lock 削除→push でコードと文書が一気通貫で landing する

**メタ観察 — なぜ Claude が "negative rule" に偏るか:**
LLM (私) は「ユーザーから問題を指摘される」→「再発防止ルールを CLAUDE.md に追加する」というフィードバックループの上で動いている。問題が発覚した時点ではコード変更時の自己チェックが思いつきやすい (= 局所的・低コスト・書きやすい)。一方、SLI 設計や CI ガード追加は工数が大きく、思いついても「優先度低」として後回しになりがち。これを是正するには、**なぜなぜの仕組み的対策に「外部観測」「物理ゲート」を最低 1 つ含めることをテンプレートで強制する** のが有効。

---

## 過去の設計ミスパターン（再発させない）

| 機能 | 設計の前提（間違い） | 実際 |
|---|---|---|
| ジャンル分類 | Google News検索フィード = ジャンル精選記事 | Googleが別ジャンルの記事を混入 |
| アフィリエイト | ニュース見出し = 商品検索クエリ | 「肝臓がんリスク」でAmazon検索になる |
| Slack通知 | secret名が合っているはず | `SLACK_WEBHOOK_URL` vs `SLACK_WEBHOOK`でずっと404 |
| Bluesky投稿 | S3_BUCKETは設定済みのはず | 未設定で一度も投稿できていなかった |
| コメント削除 | 投稿直後に削除するはず | Googleトークン1時間失効後の削除を想定していなかった |
| T116 RSSフォールバック | dominant_genres()スコアなし→article.genre(RSSフィード値)をフォールバックに使った | Google NewsのRSSはジャンル混在が既知問題。テクノロジークエリで取得した政治記事がgenre='テクノロジー'を持つため、フォールバックすると誤分類が確定。→ 総合に戻すのが正解 |
| アフィリエイト配置（T206） | 「この話題をもっと知る」セクションにAmazon商品リンクを出せば収益になる | ニュース閲覧中のユーザーは商品を買いに来ていない。災害・事件記事でAmazon商品リンクが出ると信頼を損なう |
| ads.txt AdSense 行欠落（2026-04-27 発覚） | AdSenseのpub-IDがindex.htmlのscriptタグにあるからads.txtも自動で読まれるはず | ads.txt は Google が独立にクロールする別ファイル。`google.com, pub-XXXXX, DIRECT, f08c47fec0942fa0` 形式の行が無いと AdSense 審査が通らない |

---

## 文脈ミスマッチの具体例（2026-04-27 調査）

> ユーザー文脈チェックの参考事例。`docs/rules/user-context-check.md` も参照。

### ① アフィリエイト「この話題をもっと知る」 h2ラベル
- 現状: `<h2>この話題をもっと知る</h2>` の直下に Amazon/楽天/Yahoo!ショッピングのリンク
- 問題: 「もっと知る」はコンテンツを期待させる。商品リンクは期待を裏切る
- 正解: `<h2>関連商品</h2>` + 「広告」ラベル
- 追加問題: GENRE_KEYWORD マッピングで「国際」→「旅行グッズ」「社会」→「便利グッズ」「健康」→「サプリ」は、紛争・事件・疾患ニュースで不適切

### ② 推移グラフの長期ボタン
- 現状: 「1ヶ月」「3ヶ月」「半年」「1年」「全期間」のボタン
- 問題: データが蓄積されていない期間のボタンを押すと空グラフ → 「壊れている」に見える
- 判断基準: データが存在しない時間軸のボタンはグレーアウトするか非表示

### ③ AI分析「処理待ち」メッセージ
- 現状: `⏳ AI分析を生成中です（1日4回更新）。` のみ
- 問題: 「いつ来れば読めるか」がわからない
- 正解: 次回更新予定時刻（JST）を表示

### ④ リワインド機能の「パーソナライズ感」と実態の乖離
- 現状: 「あなたが離れていた間のニュース」というコピーだが、実態は「過去N日に初出したトピックの一覧」
- 判断基準: ログイン/非ログインで見せ方を変えるか、コピーを正直に変える

### ⑤ Appleサインイン「近日公開」ボタン
- 判断基準: 実装予定 = 3ヶ月以内 なら残す。それ以外は削除する

### ⑥ ヘッダーキャッチコピーの不統一
- 判断基準: コピー変更時は全ページの `<p>` タグと meta description を同時に変更する

### ⑦ 空コンテナにヘッダーだけ表示される問題
- 判断基準: コンテンツが0件のセクションはヘッダーごと非表示にする

### ⑧ アフィリエイトのジャンル別キーワードで「安全でないマッピング」を使わない
- 判断基準: センシティブなトピック（事件・事故・医療・政治）でアフィリエイトを表示する場合は、カテゴリを「書籍・教養系」のみに限定するか、セクション自体を非表示にする

---

## production 鮮度 SLI が無くて 14h 壊れに気付かなかった (2026-04-28)

**起きたこと**: 2026-04-28 17:15 JST のスケジュール調査で `https://flotopic.com/api/topics.json` の `updatedAt` を curl したところ `2026-04-27T17:04Z` で **約 15 時間更新ゼロ**。本日 07:00 / 13:00 JST のスケジュール 2 サイクルが連続で publish に失敗していた。前日 02:00 JST の Cowork セッションが T218 wallclock guard を実装したが、発見ルートが「次回スケジュールを待って CloudWatch を見る」運用任せで、ユーザーから見える鮮度は誰も観測していなかった。

| Why | 答え |
|---|---|
| **Why1** なぜ 14h 壊れに気付かなかった？ | 「ユーザーから見える壊れ方」を独立して観測する仕組み (curl + Slack) が存在しない |
| **Why2** なぜそんな独立観測が無い？ | 監視は CloudWatch / governance worker など Lambda 内部 metric ベースで構築されており、success-but-empty パターン (Lambda 完走したが topics.json 更新せず) は拾えない |
| **Why3** なぜ Lambda 内部 metric だけで設計したか？ | SLI/SLO の定義文書 (`docs/sli-slo.md` 等) が無く、何を「壊れている」と定義するかが各タスクのアドホック判断 |
| **Why4** なぜ SLI/SLO 定義が無いか？ | 一人開発・小規模本番で「動いてれば良い」マインドが続き、明示的に SLO を文書化する優先度が他作業に負けてきた |
| **Why5** なぜ「動いてれば良い」マインドのまま放置できたか？ | スケジュールタスク (本ファイルでなく Cowork の毎日棚卸し) が「ファイル単位の差分・CSS/JS 不整合・プライバシーポリシー文言比較」など static な部分を効率良く捕まえる一方、**動的に変化する production 状態**を体系的に curl で叩く手順が確立していなかった (= static analysis bias) |

**仕組み的対策（最低3つ・「外部観測」必須）**:
1. **freshness monitor 新設 (T263)** — GH Actions cron 1h 毎に `curl /api/topics.json` を取得し `(now - updatedAt) > 90min` なら Slack 警告。governance worker と別系統で走らせる (governance 自身が壊れた時に検知できる外部観測)
2. **`docs/sli-slo.md` 新設** — トップレベル SLI 5-7 個 (topics.json 鮮度・トップページ HTTP/2 200 / fetcher Lambda 成功率 / 月次 AdSense クリック率 等) を列挙。各 SLI に警告閾値・観測コマンド・再現可能 curl/jq を併記。「ユーザーから見える壊れ方」を SLI として明示。
3. **scheduled-task prompt 改修** — Cowork の毎日棚卸しタスクの先頭に「最初に 5 分間 production を curl で観察し、最重要の壊れ方を特定する」を **構造として** 注入 (テキストルール強化ではなく schedule definition の最上段に物理的に配置)。

**Claude の挙動分析 (なぜそうしたか)**:
- 過去のスケジュールタスク履歴が static analysis 中心だったため、Claude は「動作確認は別タスク」として暗黙に切り離していた
- 本日の T255 keyPoint 修正のような「すぐ効くコード fix」は applied したが、SLI 監視の不在については個別タスク (T242) として作成のみで終わり、**メタな運用不全 (= 最重要なのに後回し)** に気付くまでに 1 サイクル余分にかかった
- ルール強化 (テキスト) で再発防止すると Claude は文字列規則を狭く解釈する。代わりに「scheduled task の最上段に curl 観察を物理配置」「freshness monitor cron で外部観測」と **構造で固定する** ほうが根本対策

→ **メタ教訓**: 「ルール（テキスト）で予防」より「構造（cron / 起動チェック script / SLI 文書）で予防」のほうが Claude には効く。
