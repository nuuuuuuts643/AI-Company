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
- 2026-04-28 production 鮮度 SLI 不在で 14h 壊れに気付かなかった (static analysis bias)
- 2026-04-28 環境スクリプトに session ID hardcode + UTC を JST と誤ラベル (環境スクリプトが Verify 対象外と暗黙解釈された)
- 2026-04-28 仕組み化タスクが起票だけで実装されない（メタ・schedule-task 構造ガード v3）
- 2026-04-28 06 success-but-empty を AI 生成側に横展開できず keyPoint 充填率 11.5% を素通りした (SLI 粒度の構造欠陥)
- 2026-04-28 06 docs/system-status.md と実測の数値齟齬 (スナップショット二重管理問題)
- 2026-04-28 08 scheduled-task-protocol とナオヤ前提 §8 の矛盾（保留禁止 vs 効果見えない時は保留 OK）
- 2026-04-28 08 sitemap に書いた静的HTML が 50/50 件 404 — 監視に乗らない機能の SLI 漏れ（新機能ローンチ時の SLI 強制紐付け欠如）
- 2026-04-28 10 ゴミデータ慢性蓄積の構造的欠陥（schema_version / quality_heal / bulk_heal / 作成ガードによる自己修復基盤化）
- 2026-04-28 worktree branch push で「完了」宣言 — main マージが誰もやらず本番未反映（完了定義に main マージが含まれていなかった）
- 2026-05-02 静的SEO HTML と動的SPA の二重 URL で canonical が破綻していた（T2026-0502-BI・後付け機能追加で旧経路を放置・SEO regression CI ガードの欠落）
- 2026-05-02 Cowork sandbox の git 認証経路が .git/config URL 直書きに依存していた（T2026-0502-BJ・Mac Keychain は sandbox から見えない・`.cowork-token` ファイル経路で恒久対処）
- 2026-05-02 トップカードのタイトルが日本語15字で hard truncate され語句の途中で切れて意味不明（T2026-0502-UX-CARDTITLE・proc_ai.py 15→30字 + frontend フィールド優先順位反転 + 横展開で末尾語句切断 SLI / field-order lint / 実機 verify_target 強化を提案 + FUSE 並行書き込みで Edit が PR に乗らない事故も同時記録）

---

## なぜなぜ分析を「忘れる」現象自体のなぜなぜ（2026-04-27 制定・メタ事象）

**起きたこと**: ads.txt 事件のなぜなぜ分析を Claude が要求された時、テーブル1行追記で済ませて Why1〜Why5 構造化分析を書かなかった。ナオヤから「ちゃんとなぜなぜやったんだろうな？」と指摘されて初めてやり直した。

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

---

## 運用ルールの仕組み化メタなぜなぜ（2026-04-28 制定・schedule task 由来）

**起きたこと**: 4 つの観察を schedule task で同時に発見。
1. TASKS.md に取消線済み完了タスク (`~~T218~~`〜`~~T250~~`) が 13 行滞留・本ファイルから読みづらく、AI が「未着手」を見つけるのに時間がかかる
2. セッション起動時に `mv .git/index.lock _garbage/` が `permission denied` で失敗。`rebase-merge` ディレクトリも残り、merge / pull が中断状態でセッション開始
3. T233 と T234 が同 ID で異なる用途に並立（finder 並列で衝突）
4. AI が状況把握のために CLAUDE.md(133) + system-status(133) + TASKS.md(150) + WORKING.md(81) + lessons-learned(269) + docs/rules/* (160) = 800+ 行を読まないと着手できない

| Why | 答え |
|---|---|
| **Why1** なぜ取消線タスクが滞留・lock 退避が失敗・ID 衝突・起動コスト過大が同時発生？ | これらはすべて「ルールはあるが手動で運用」される状態。手動運用は途中で漏れる |
| **Why2** なぜ手動運用に偏った？ | 過去のなぜなぜでは「CLAUDE.md にルールを追記する」を主対策にしてきた。ルール追記はコストが低く即実装できるため思いつきやすい |
| **Why3** なぜ自動化が後回し？ | 自動化は scripts や CI を書く必要があり、目の前の事件解決より工数が大きく見える。タスクとして個別 (T242/T244/T245/T246/T256) には起票されたが「いつかやる」状態 |
| **Why4** なぜ「いつかやる」のまま蓄積する？ | 自動化が動くまで「一度きりの事件」に見えるため、ナオヤから新しい指摘が来るたびに「ルール追記」で短期対症する。**仕組み化と対症療法が同じ「再発防止」ラベルで扱われている** |
| **Why5** なぜラベルが分かれていない？ | CLAUDE.md の絶対ルール「なぜなぜ分析は構造化」では仕組み的対策 3 つ以上を求めるが、その質基準（CI / hook / script / SLI / metric いずれか必須）が不在。「ルール追記」3 つで形式的に通せていた |

**仕組み的対策（質基準を物理化）:**
1. **`docs/rules/global-baseline.md` 新設** — 全プロダクト共通の前提を 1 ファイルに集約。CLAUDE.md は固有ルールに集中。**§6「AI が動きやすくなるための原則」に「気を付ける」禁止を明記**：仕組み的対策は CI / hook / metric / SLI / scripts のいずれかで物理化、テキストルールだけで closure しない
2. **`scripts/session_bootstrap.sh` 新設** — 起動チェックを 1 コマンド化。lock / rebase-merge を複数回トライで _garbage 退避、stale 行を自動削除、取消線タスクを HISTORY 自動移動、needs-push 滞留警告。CLAUDE.md の長い bash ブロックは廃止
3. **`scripts/triage_tasks.py` 新設** — TASKS.md `~~T...~~` 行を HISTORY.md に append、WORKING.md 8h stale 削除、タスクID 重複検知 (CI から呼べる exit code)。bootstrap が定期的に呼ぶ
4. **WORKING.md `needs-push` カラム恒久化** — Cowork がコード変更時に `yes`、push 完了で `no`。bootstrap が grep で滞留警告
5. **CLAUDE.md 起動チェック簡素化** — 12 行の bash ブロックを `bash scripts/session_bootstrap.sh` 1 行に置換。AI が起動時に読む量を削減（132 行で 250 行ガード内）

**メタ教訓:**
- 「ルール（テキスト）で予防」と「構造（scripts / CI / hook）で予防」を**同列の "再発防止" として扱わない**
- なぜなぜ分析の「仕組み的対策 3 つ以上」の少なくとも 1 つは **AI が読まなくても動作するもの**（cron / hook / CI / SLI / scripts）でなければならない
- 「全プロダクト共通の前提条件」は専用ファイル (`global-baseline.md`) に集約。CLAUDE.md は固有ルールだけ持つことで再利用性 + 短さ両立

---

## scheduled-task が「課題発見」に偏り「即時改善」に進まない問題 (2026-04-28 18:10)

**起きたこと**: 2026-04-28 17:30 と 18:10 の連続スケジュール調査で、最優先タスク T263 (freshness monitor) / TBD-SLI (sli-slo.md) / T239 (ads.txt CI ガード) のいずれも実装されないまま、TASKS.md に **47 件**滞留。さらに 8 件のタスクが「実装済の可能性あり (HISTORY 確認要)」のまま再起票されていた。一方で「課題を新たに 12 件発見した」「文書を 3 ファイル新設」など発見系成果は積み上がっていた。

| Why | 答え |
|---|---|
| **Why1** なぜ最優先タスクが実装されないまま発見ばかり積み上がる？ | scheduled-task の prompt が「課題を洗い出してタスクにしてください」を冒頭に置き、「即時反映ください」を末尾に置いているため、Claude は「発見 → タスク化」を主動作・「即時改善」を副動作と解釈する |
| **Why2** なぜ Claude は冒頭指示を主動作と解釈する？ | LLM は long prompt の末尾より冒頭の動詞を強く重みづける傾向がある (positional bias)。さらに「無理して改善する必要はなく…保留でかまいません」という escape hatch が末尾にあると「保留」を選ぶ閾値が下がる |
| **Why3** なぜそもそも escape hatch を末尾に置いた？ | ナオヤとしては「動かないまま壊すよりはマシ」という安全側設計。意図は正しいが、Claude にとっては「実装しなくてよい免罪符」になる |
| **Why4** なぜ「免罪符」として作用しても気づかなかった？ | scheduled-task の output 評価軸が「発見した課題数」のみで、「実装したタスク数」「キュー長差分」が観測されていない。発見ゼロ x 実装多数 / 発見多数 x 実装ゼロ のどちらも同じ「OK 報告」で終わっている |
| **Why5** なぜ評価軸が偏った？ | Claude / ナオヤの双方が「scheduled-task = 監査・棚卸し」と暗黙了解していた。「scheduled-task = 改善も同時にやる」という構造が prompt にも script にも codified されていなかった。**ルール（テキスト）で「即時改善も」と書いてあるが構造化されていない** |

**仕組み的対策 (テキスト規則ではなく構造で固定)**:

1. **`docs/rules/scheduled-task-protocol.md` 新設** — schedule task 起動時に Claude が読むプロトコル。「探索フェーズ 30 分で発見 → 実装フェーズで unblocked 1 件以上を消化 → 報告」の 3 段階を物理的に order 固定する。session_bootstrap.sh の出力末尾に「scheduled-task で起動した場合は `cat docs/rules/scheduled-task-protocol.md` を読む」を追加。
2. **`scripts/session_bootstrap.sh` を schedule mode 検知拡張** — 環境変数 `SCHEDULE_TASK=1` が立っている時 (or `--schedule` 引数) は、TASKS.md の最優先 unblocked 1 件を STDOUT に強調表示する。Claude は起動チェック直後にこの 1 件を見るため発見前に実装着手を考える。
3. **commit message に KPI 行を必須化** — schedule-task push の commit message には `[Schedule-KPI] implemented=N created=M closed=K queue_delta=±X` を含める。pre-commit hook で「commit message に schedule-task が含まれかつ KPI 行が無ければ reject」。`git log --oneline --grep "schedule-task"` で anti-pattern (implemented=0 が連続 3 回) を可視化。
4. **「実装済の可能性あり (HISTORY 確認要)」を物理ガード化** — `scripts/triage_tasks.py` を拡張: TASKS.md に `(HISTORY 確認要)` が含まれる行は HISTORY.md と grep で突合して、HISTORY 側に同 ID の `done` 行があれば自動的に取消線化する。

**Claude の挙動分析 (なぜそうしたか)**:
- 過去 10 回の schedule-task push commit を眺めると、コード変更を含むのは 2 回 (T255 keyPoint fix / T219 storyPhase 防御)。残り 8 回は md ファイル新規・更新のみで「発見成果」中心
- Claude は「発見」が低リスクで「実装」が高リスクと暗黙にコスト評価していた。「無理して改善する必要はない」prompt を見て安全側に倒した
- 一方ナオヤ視点では「最優先 T263 が連日放置」=「実装こそが最大の価値」。両者の優先度モデルがズレていた

**メタ教訓:**
- prompt 末尾の「escape hatch」は Claude の優先度を冒頭の動詞より強く動かす可能性がある。本当に必要な動作は **冒頭に置く + 構造で固定する** べき
- 「発見」は KPI として可視化されやすいが「実装」は黙って減るキュー長でしか見えない。**減ったキュー長を session ごとに commit message に書く** ことで実装成果も可視化する
- 同セッション内で発見した課題のうち「不可逆性が低く・依存が無く・テスト容易な 1 件」は**必ず実装してから報告する**を session protocol として codify する

---

## 仕組み化タスクが起票だけで実装されない問題（2026-04-28 19:00 制定・schedule-task v3）

**起きたこと**: 2026-04-28 18:10 schedule-task で「scheduled-task が発見偏重」のなぜなぜを書き、仕組み的対策として T2026-0428-G (KPI 行強制 hook) / T2026-0428-H (triage_implemented_likely.py) / T2026-0428-I (bootstrap schedule mode 拡張) を起票した。19:00 schedule-task で再点検したところ **G/I は依然 TASKS.md に滞留・未実装**。「protocol を文書化したが、protocol を読ませる物理ルートも、KPI 違反を弾く物理ゲートも未配備」だった。発見偏重なぜなぜ自身が「発見偏重で終わる」皮肉な再帰。

| Why | 答え |
|---|---|
| **Why1** なぜ G/I が連続 schedule-task で実装されなかった？ | 直前の schedule-task は KPI 行を含む commit を 1 本作って終了。次の schedule-task は新規発見に注意が向き、前回の対策タスクが TASKS.md の中に埋もれた |
| **Why2** なぜ前回の対策タスクが埋もれた？ | TASKS.md が 30+ 行の表で、最優先 unblocked が一目で識別できない。Claude は「上から眺めて目につくもの」を選ぶ |
| **Why3** なぜ最優先 1 件が物理的に強調されない？ | session_bootstrap.sh が起動チェック完了サマリを出すだけで、「次にやるべき 1 件」を STDOUT に晒さない。schedule-task モード検知も無く、protocol 読み込みも任意 |
| **Why4** なぜ KPI 行強制が「ルール記述」止まり？ | scheduled-task-protocol.md に書いただけで commit-msg hook 化されておらず、KPI 行抜きの commit を物理ブロックしない。Claude は「書かれていることが必須」より「弾かれることが必須」に強く反応する |
| **Why5** なぜ前回の対策が「テキスト + タスク化」で止まった？ | 仕組み的対策 4 つのうち hook / scripts 系は実装工数が大きく、「次の schedule-task でやれば良い」と先送りされた。**先送りを検知する metric が無いため、先送り自体が顕在化しない** |

**仕組み的対策（今回の v3 で実装。テキスト追加は 0、構造 3）:**

1. **`scripts/install_hooks.sh` 拡張 + .git/hooks/commit-msg 再導入**: commit message に "schedule-task" を含み `[Schedule-KPI] implemented=...` 行が無ければ物理 reject。bootstrap の `chore: bootstrap sync ...` 等は schedule-task 文言を含まないため誤発火しない。テスト 3 ケース通過 (no-KPI / with-KPI / bootstrap-chore)。
2. **`scripts/session_bootstrap.sh` schedule-task モード拡張**: `SCHEDULE_TASK=1` または `--schedule` 引数で起動した場合、scheduled-task-protocol.md と TASKS.md「🔥 今週やること」の最優先 unblocked タスク 1 件を STDOUT に強調表示。Claude は起動直後にこの 1 件を見るため、新規発見前に「実装着手」を考える順序になる。
3. **`docs/rules/global-baseline.md` §9 ナオヤ前提条件追記**: 「ルール長文化禁止」「効果が見えない間は保留」「うまく行ってない場合はすぐ戻す」「AI の動きやすさ優先」を全プロダクト共通の前提として明文化。CLAUDE.md には 1 行も追加しない（CLAUDE.md は 132 行で固定、固有ルールに集中）。

**メタ教訓 (v3):**
- 「仕組み化タスクを起票」は仕組み化ではない。**hook / scripts に landing するまでが仕組み化** とラベリングを揃える
- なぜなぜの仕組み的対策の中に **「同 commit で実装されないものは仕組み化と呼ばない」** を含める。タスク化に逃げるのを禁じる
- ルール変更は 1 commit / 1 領域で reversible に保つ（ナオヤ前提条件「うまく行ってない場合はすぐ戻す」）。今回の v3 commit は scripts 2 / docs 3 だけで、想定外なら revert で前状態に戻せる構造


---

## 環境スクリプトの session-id hardcode + UTC を JST 誤ラベル (2026-04-28 04:15 schedule-task 由来)

**起きたこと**: 別 Cowork セッション (zen-busy-goldberg) で `bash scripts/session_bootstrap.sh` が "❌ repo not found" で即死。原因は L19 の fallback `/sessions/keen-optimistic-keller/mnt/ai-company` が前のセッション ID をハードコードしており、新セッションのマウント (`/sessions/zen-busy-goldberg/...`) では存在しないため。`scripts/triage_tasks.py` も同じく `REPO_CANDIDATES` に旧 session ID が hardcode されており、新セッションで実行すると `PermissionError` で SystemExit → WORKING.md の stale 行が掃除されないまま蓄積していた。さらに bootstrap 出力ラベルが「JST」と書きつつ container UTC を表示しており、実時刻と 9h ズレていた。

| Why | 答え |
|---|---|
| **Why1** なぜ前回のセッション ID をリテラルで fallback path に書いた？ | bootstrap script を作ったセッションが「自分が動いている mount path」をそのまま hardcoded fallback として書いた。「いま動く」状態を future state でも有効と仮定 |
| **Why2** なぜ「動いている path」を未来でも動くと仮定？ | Cowork セッションごとに mount path (session ID 部) が変わる仕様 (`/sessions/<random-id>/mnt/...`) を Claude が認識せず、「固有・絶対 path」として扱った。session ID が ephemeral という事実が mental model に無かった |
| **Why3** なぜ ephemeral session の mental model が抜けた？ | Cowork 環境特性 (FUSE rm 不可、session ID 不定、別 session の PermissionError) は CLAUDE.md / global-baseline.md に部分的にしか文書化されていない。Claude が「Cowork で動かす」前提を script 設計時にチェックする手順 (例: 別 session で simulate して Verified 行を取る) が無かった |
| **Why4** なぜ verify 手順が無かった？ | 「環境スクリプト」(scripts/session_bootstrap.sh / triage_tasks.py) は production の Lambda や frontend ではないため、CLAUDE.md「完了 = 動作確認済み」の対象から暗黙に除外された。Verified 行は production URL や Lambda invoke を念頭に書かれており、**自分自身が次セッション起動時に叩く utility** を verify する想定が無かった |
| **Why5** なぜ「環境スクリプト」が verify 対象外と暗黙解釈された？ | Verified ルールは「ユーザに見える機能」を対象に設計され、「Claude が起動時に自動で叩くスクリプト」を含意していなかった。**Claude が次セッションで初めて『動かない』と気づくループ**になる。Claude 自身が起動 utility を書いた瞬間にそれが「次の Claude にとっての CI」であるという視点が抜けていた |

**仕組み的対策（構造化・テキスト規則は最終手段）**:

1. **(構造) glob 検出**: `_candidates()` を `/sessions/*/mnt/ai-company` glob ベース化。session ID 不変前提を物理的に消した。session_bootstrap.sh と triage_tasks.py の両方で実装（同 commit）。
2. **(構造) PermissionError 握りつぶし**: 別 session の mount を読んで権限エラーが出たら次の候補へ skip。1 候補失敗で SystemExit する設計を排除。triage_tasks.find_repo に try/except 追加。
3. **(構造) JST 表示の物理化**: `TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M JST'` で container UTC を物理補正。文字列ラベルだけ JST と書く運用を排除。
4. **(構造) WORKING.md 未来日付異常も stale 対象**: タイムスタンプ書き間違いで future-dated になった行が「stale でない」判定を受けていた。`now JST + 1h` を上限として future も stale 扱いに。`clean_working_md` に `future_tolerance_h` 引数追加。
5. **(構造・別タスク) 環境スクリプト dry-run CI**: `bash scripts/session_bootstrap.sh --dry-run` を GH Actions で日次実行 → REPO 検出失敗・JST ラベル不整合・stale 検出ロジック退化のいずれかで PR を block。T2026-0428-K として起票。

**Claude の挙動分析 (なぜそうしたか)**:
- script 内のハードコード fallback は「fallback だから動かなくても主 path で動く」と暗黙に保険扱いしていた。だが Cowork は VM mount しか無い環境で、その fallback が **唯一の path** になる。
- bootstrap output で `date '+...JST'` と書けば JST が出ると思い込んでいた (`date` は container TZ 依存)。**「文字列ラベル ≠ 実時刻」の typo 級ミス** が verify されなかった。
- 「動作確認＝本番 URL 目視」を狭く解釈し、**自分自身を起動するスクリプト** を verify 対象外にした。

**メタ教訓**:
- 「Claude が次セッションで叩く utility」は **Claude 自身にとっての CI**。production と同等の verify が必要。
- ハードコードされた session ID / 絶対 path / TZ ラベルは **環境前提の埋め込み** で、環境が変わると即破綻する。glob / 環境変数 / `TZ=` で構造から消す。テキスト規則 (「気を付ける」) では再発する。
- environment script の変更は **別 session で simulate して動かす** までを 1 commit に含める。本セッションでは bootstrap 修正後にもう一度 bootstrap を叩いて「JST 04:16 表示・needs-push 検出・lock 警告以外エラーなし」を確認した上で commit。

---

## AI フィールド充填率の低さが SLI 観測の盲点に落ちている (2026-04-28 05:13 schedule-task 由来)

**起きたこと**: 本番 `/api/topics.json` を curl して全 117 topic を集計したところ、`aiGenerated=True` は 79.5% (=93/117) で従前通りだが、フィールド単位では `keyPoint=8.5% (10/117)` / `perspectives=20.5%` / `outlook=49.6%` / `relatedTopicTitles=24.8%`。さらに「articles=19 の福島山林火災トピック」「articles=15 の北海道後発地震トピック」が aiGenerated=None のまま topics.json トップ位置に並ぶ。一方で `docs/system-status.md` は「AI 要約カバレッジ 80.2%」と**二値メトリクス**だけ報告しており、内部のフィールド分布の偏りも大規模クラスタの取りこぼしも、外部観測から見えない状態になっていた。

| Why | 答え |
|---|---|
| **Why1** なぜ AI フィールド充填率が低いのに SLI 警報が鳴らない？ | `docs/sli-slo.md` SLI 1〜8 のうち AI 関連は「topics.json 鮮度」と「AI 要約カバレッジ (二値)」のみ。フィールド単位 (keyPoint/perspectives/outlook 各々の充填率) は SLI 化されていないため警報経路が無い |
| **Why2** なぜ二値メトリクスだけで SLI 設計を済ませた？ | T237 起票時点では「aiGenerated=True/False」が pending queue 判定の主軸だったため、二値で足りると判断した。フィールド単位の失敗モード (5xx でフィールド欠損 / merge 漏れ / schema 漏れ) が後から増えたが、SLI 設計を更新しなかった |
| **Why3** なぜ SLI 設計を後追いで更新しなかった？ | T220 (backgroundContext/perspectives/outlook 既存実装確認) で「実装は揃っている」と判定して close しただけで、「実装が動いていることを観測する SLI」を起票しなかった。**実装と観測の間にギャップがあるという視点が SLI 設計に組み込まれていない** |
| **Why4** なぜ「実装と観測のギャップ」視点が無かった？ | CLAUDE.md は「完了 = 動作確認済み」を要求するが、これは個別タスクの完了判定であって SLI 体系の設計原則ではない。「実装したフィールドは SLI で経時観測する」をデフォルト動作にする仕組みが無い |
| **Why5** なぜそれをデフォルト動作にする仕組みが無い？ | proc_ai 〜 frontend の 5 層 (proc_ai schema → ai_updates → handler merge → S3 publish → frontend render) のフィールドカタログ自体が文書化されていない (T245 が起票だけで未実装)。フィールドリストが無いため、SLI を「全フィールドに対して」自動展開する基盤が無い |

**仕組み的対策（構造化のみ。テキスト規則追加は今回ゼロ）:**

1. **(構造) `_call_claude` を 5xx / network もリトライ対象に拡張 (T235 完了)** — 旧実装は 429 のみリトライで 500/502/503/504 は 1 回失敗で raise。Tool Use 化で 1 call 5-15 秒に伸び、Anthropic 側 internal error 確率が上昇。修正後 4 attempt × 指数バックオフ (5s → 10s → 20s)。METRIC ログ `[METRIC] claude_retry attempt=N code=X kind=Y wait_s=Z` を出して governance worker で集計可能化。8 件の boundary test (429/500/503/504/400/network/timeout/即時成功) で動作検証済 (`tests/test_proc_ai_retry.py`)。
2. **(構造・別タスク) AI フィールド充填率 SLI 9 新設 (T2026-0428-N)** — `scripts/check_ai_fields_coverage.sh` 新設、本番 topics.json を curl してフィールドごとの充填率を JSON 化、6h cron でしきい値割れ Slack 警告。`docs/sli-slo.md` に SLI 9 として登録。「実装したフィールドが SLI で経時観測される」をデフォルト化する基礎ピース。
3. **(構造) `triage_implemented_likely.py` 新設 (T2026-0428-H 完了)** — TASKS.md の `(HISTORY 確認要)` 行を HISTORY.md と grep 突合して自動取消線化。`session_bootstrap.sh` から呼ばれる。「実装済の可能性あり」のままタスクが残り続ける anti-pattern を物理排除。

**Claude の挙動分析 (なぜそうしたか)**:
- 二値 SLI で「カバレッジ 80%」と報告された段階で、Claude 側は「合格点」と暗黙評価し、フィールド分布まで降りていかなかった。**集計指標の粒度が荒いと、AI は finer granularity に下がるトリガーを失う**
- 5xx リトライ実装は「明白な軽微改善」だが、`_call_claude` が proc_ai の冒頭にあって全 AI 呼び出しの基底層であるため、変更は無意識に「core path」と分類されて手を出されなかった。実際は 30 行の純粋関数で副作用が局在しており、boundary test 同梱で安全に変えられた
- 「TASKS.md に書いてあるのに残っている」状態を Claude は**「自分以外の誰かが実装する」と暗黙に分類**していた。一人運営なので「自分」しかいないという事実が次に動く動機にならない

**メタ教訓**:
- SLI は「実装したフィールド数」と「観測しているフィールド数」が常に一致するように設計する。フィールドが増えたら自動展開される基盤 (フィールドカタログ + cron で全フィールドに対して一括観測) が無いと、SLI は実装に追いつかない
- 「core path」のラベルは Claude にとって変更を踏み止まらせる効果が強い。実際の core 度は「副作用範囲」「ロールバック容易性」「テスト容易性」で再評価する習慣を持つ。`_call_claude` のような「基底層に見える pure function」は変更コストが低いことを優先評価項目にする
- scheduled-task の commit にはフェーズ 1 (探索) で発見した anti-pattern を**フェーズ 2 で 1 件以上消化する** ところまで含めて 1 commit にする。「発見だけ」「タスク化だけ」では仕組み化と呼ばない (lessons-learned 2026-04-28 18:10 / 19:00 の延長)

---

## success-but-empty を AI 生成側に横展開できなかった（2026-04-28 06 制定）

**起きたこと**: schedule-task で実態調査したところ、aiGenerated=True なのに **keyPoint 充填率 11.5% (6/52)** ・perspectives 充填率 26.9% という半壊状態を発見。SLI 3 (AI カバレッジ 79.5%) は警告閾値 70% を超えていたため SLI 表示は「FRESH」のまま。production 鮮度の 14h 事故 (2026-04-28) で「success-but-empty を CloudWatch だけで設計するな」と学んだはずなのに、AI 生成側にその教訓が横展開されていなかった。

| Why | 答え |
|---|---|
| **Why1** なぜ keyPoint 11.5% を SLI で検知できなかった？ | docs/sli-slo.md の SLI 3 が「aiGenerated フラグの数」しか見ていなかった。keyPoint・perspectives・background など個別フィールド充填率は SLI 化されていなかった |
| **Why2** なぜ個別フィールド充填率の SLI が無かった？ | 14h 鮮度事故 → SLI 設計の教訓は `freshness-check.yml` (T263) で 1 つ実装したが、「他にも success-but-empty 系の指標がないか」を網羅する設計レビューが入らなかった |
| **Why3** なぜ網羅レビューが入らなかった？ | 教訓を「該当事象の対策」として閉じる文化があり、「同じ pattern が他にも潜んでいないか」の横展開ステップが運用フローに無い。lessons-learned.md は事例集だが「横展開チェック」が独立タスク化されていない |
| **Why4** なぜ横展開チェックがタスク化されない？ | 教訓 1 件あたり「対策実装」と「他コンポーネントへの展開」が同じ commit に含まれる前提で書かれているが、Claude (LLM) は「対策実装」だけで満足の状態に到達してしまう。報酬関数が「目の前の事象を解決した」を高く評価する |
| **Why5** なぜ「目の前の事象」だけで満足するのか？ | scheduled-task のような自律タスクで Claude は「優先度の高い未解決事象がある時、それ以外の作業を抑制する」傾向がある。教訓の横展開は「優先度の低い予防的作業」に分類されがち |

**仕組み的対策（4つ）:**

1. **`freshness-check.yml` ai_fields step 追加 (本 commit で実装済)** — keyPoint / perspectives / background / storyPhase 偏りを 1h cron で外部観測。閾値未満で Slack 警告。SLI 8/9/10 として `docs/sli-slo.md` 登録。
2. **新規 SLI 追加テンプレに「半壊検出 (success-but-empty) を含むか」必須化** — `docs/sli-slo.md` 末尾の「SLI を増やす時のテンプレ」に項目追加。チェック無しで SLI 追加した PR は CI で warning。
3. **lessons-learned.md に「横展開チェックリスト」セクション追加** — 教訓 1 件あたり「同 pattern が潜む他コンポーネント」をリスト化する欄を必須化。次の schedule-task で `lessons-learned-check.py` を実装し、Why5 / 仕組み的対策 / 横展開リスト の 3 項目欠落で fail させる。
4. **AI フィールドカタログ化** — `lambda/processor/proc_ai.py` の output schema を 1 箇所に列挙 (例: `_AI_FIELDS_CATALOG`)。SLI 観測スクリプトはカタログを読み込んで全フィールド一括観測。フィールド追加時に SLI が自動展開される構造。

**Claude の挙動分析 (なぜそうしたか)**:
- T255 (skip 条件修正) を実装した時に「修正の検証」を「次回 cycle で AI カバレッジが上がるか」だけで判断し、各フィールドの充填率は確認しなかった。**「修正対象の skip 条件 = aiGenerated フラグ」と暗黙的に同視した**
- 14h 鮮度事故で T263 を実装した直後に「外部観測 SLI を一通り作った」という錯覚があった。**1 教訓 = 1 SLI 追加で完了** という浅い対応パターンが残った
- 「success-but-empty」は教訓の名前として定着していたが、抽象パターンとして「他に潜んでないか」の検索行動が促されなかった。**名前付き教訓の他パターンスキャン**を促す仕組み (例: bootstrap で「success-but-empty 系の SLI 数」を 1 行表示) がない

**メタ教訓**:
- 1 教訓を 1 SLI / 1 ルールで閉じない。**教訓には抽象パターン名 (例: success-but-empty) を必ず付与し、そのパターンに該当する他の場所を体系的にスキャンする** 別タスクを発行する
- success-but-empty の網羅対象 (本日時点での要監視リスト): topics.json の各 AI フィールド (keyPoint・perspectives・background・outlook・spreadReason)、fetcher の articleCount=0 サイクル、processor の processed=0 cycle、bluesky_agent の post 失敗、SES の bounce、CloudFront の 5xx、CI の green-but-skipped (例: テストが skip され全合格扱いされる)

---

## docs/system-status.md と実測 SLI の数値齟齬（2026-04-28 06 制定）

**起きたこと**: schedule-task で実測したところ、`docs/system-status.md` 記載の topics.json サイズ 312KB / AI カバレッジ 80.2% に対し、実測は 218KB / 79.5% と齟齬があった。差 ~94KB と 0.7pp。実測時刻は 06:10 JST、記載時刻は前日夕方の 18:10 JST。記載値は時刻ラベル付きで残っており「最新値」と読まれかねない構造になっていた。

| Why | 答え |
|---|---|
| **Why1** なぜ齟齬が起きた？ | `docs/system-status.md` は人間 (Claude セッション) が手動更新するスナップショットで、実測値と自動同期されない |
| **Why2** なぜ自動同期されない？ | system-status.md は方針スナップショット (P001-P005 の状態など) と実測スナップショット (topics.json サイズ等) を 1 ファイルで混合管理しており、実測値だけを cron で更新する仕組みが無い |
| **Why3** なぜ 1 ファイルで混合管理している？ | 「セッション開始時に 1 ファイル読めば全状態が見える」という人間運用前提で設計されたが、機械的更新対象を分離する設計レビューがなかった |
| **Why4** なぜ設計レビューが無かった？ | docs/system-status.md と docs/sli-slo.md (SLI ごとに「現状実測 (時刻)」項目を持つ) の責務分離が文書で明示されておらず、両方が「現状値」を抱えて二重管理になった |
| **Why5** なぜ責務分離が明示されない？ | ドキュメント追加時に「既存ドキュメントの責務 → 新ドキュメントの責務」の差分定義を求めるルールが無い。CLAUDE.md 「規則の置き場所」表は事後追記で、追加時の前提化がされていない |

**仕組み的対策（3つ）:**

1. **freshness-check.yml の出力で system-status.md 該当行を自動更新する commit を生成** — ai_fields step の結果を `docs/system-status.md` の対応行に sed で書き込み、bot user で auto-commit。実測値と記載値が常に同期する。次の schedule-task で実装。
2. **CLAUDE.md「規則の置き場所」表に責務境界の宣言を追加** — `docs/system-status.md` は「方針スナップショット (人間更新)」、`docs/sli-slo.md` は「SLI 定義 + 実測ベンチマーク (cron 更新)」と明示。CI で system-status.md の「実測:」表記がある行を grep して、最終更新が 24h 以上古ければ warning。
3. **本 commit で system-status.md の数値を実測値に修正済**。今後の schedule-task で同じ齟齬を 2 度以上検出したら、自動更新仕組みを優先実装する。

**Claude の挙動分析**:
- system-status.md には「最終更新: 2026-04-28」「2026-04-28 18:10 JST」など時刻ラベルが付いており、Claude は「自分が読む時点での最新」と暗黙解釈してしまった。**時刻ラベルが「鮮度の保証」と「記録時点の刻印」のどちらの意味か曖昧**で、新しい時刻だと「今の値」と読みやすい
- schedule-task 06:10 JST 起動時に system-status.md を読み、312KB を「現状値」として受け入れた直後に curl で 218KB を観測。**自分が信頼した文書と実測の食い違いを検知した時に、文書側を直す習慣が弱い** (新しい記録を作る方が安心するため)
- 二重管理になっているデータがあると、Claude は「どちらかが正しいだろう」と判断保留しがち。**正本を 1 つに決めるための schema レベルの違い** (例: docs/system-status-live.md など machine-generated 専用ファイル名にする) がないと、人間-機械の正本決定が曖昧化する

**メタ教訓**:
- ドキュメント追加時には**「既存のどのドキュメントから何を取って何を残すか」を 1 行で書く** ルールを導入する。これがないと責務境界が曖昧化し、二重管理が発生する
- 機械更新ファイルと人間更新ファイルは**ファイル名で分離する** (例: `*-live.md` suffix)。混在ファイルは規模が小さいうちに分離する

---

## CI 警告レベルが「無視可能シグナル」として機能しない（2026-04-28 07 schedule-task 制定）

**起きたこと**: `meta-doc-guard.yml` の `task-id-uniqueness` ジョブは `::warning::` 出力のみで CI を fail させない設計だった。今日の schedule-task で TASKS.md を観察すると T2026-0428-P / Q / R がそれぞれ 2 行ずつ landing し、3 ペアが同時重複していた。warning は CI green を維持するため Claude も人間も気づかず、複数セッションが連続で同 ID を採番した。

| Why | 答え |
|---|---|
| **Why1** なぜ重複が 3 ペアも landing した？ | warning level CI は exit 0 で通過するため、Claude は「次へ進んで良い」と判断する。`next_task_id.sh` も schedule-task では呼ばれず、Claude が直前 ID から +1 で勘で採番した |
| **Why2** なぜ warning level に留めた？ | T243 完了時に「過去 ID 重複が landing 済みで block にすると既存 commit が弾かれる」リスク懸念で warning にした。「あとで ERROR に上げる」が口頭合意のまま放置 |
| **Why3** なぜ「あとで」が放置された？ | warning → ERROR への昇格 trigger が定義されていない。同種の重複が再発しても自動的に ERROR に上がらないため、永続的に無視可能なまま |
| **Why4** なぜ昇格 trigger を最初から決めなかった？ | warning は「移行期の妥協」と扱われたが、その妥協が「いつ終わるか」を時刻 / 件数 / 観測数で codify する習慣が無い。「移行期 = 永続」になりやすい |
| **Why5** なぜ妥協終了条件が codify されない？ | LLM・人間ともに `::warning::` を「ある時期は許容、後で直す」の暗黙合意で扱うが、CI 側にはその合意を記録するメタフィールドが無い。warning は exit 0 と等価なので、CI 上は実害ゼロに見える |

**仕組み的対策（本 commit で 2 つ実装、1 つはルール）:**

1. **(構造) `meta-doc-guard.yml` task-id-uniqueness を ERROR 化** — `python3 scripts/triage_tasks.py --check-duplicate-task-ids` を呼ぶ実装に置換。TASKS.md に同 ID 2 行以上で物理 block。HISTORY.md の引用は対象外。ロールバック手順をジョブコメントに記載（warning に戻すには `|| true` 付き grep に戻すだけ）
2. **(構造) 既存 3 ペア重複を即解消** — T2026-0428-P/Q/R の 2 番目を S/T/U に rename して dup count を 0 に落とした。これがあれば次の commit で ERROR ジョブが一発 green になる
3. **(ルール・任意) `global-baseline.md` §8 に「warning→ERROR 昇格 trigger」を追記しない** — ナオヤ前提「効果が見えない間は保留」「無理して更新しない」に従い、抽象的な昇格ルールはまだ書かない。本件は具体な観測事故が 1 件確認できた段階で個別に ERROR 化する方針で十分

**メタ教訓:**
- `::warning::` は LLM にとって `::error::` と同じ重みではない。**Claude の判断ループでは exit code 0 を「通過 OK」として扱うため、warning は実質ノーガード**
- 「移行期の妥協」を CI に持ち込むときは、**終了条件（時刻 / 重複件数 0 / 観測 0 件 N 回）を同 PR 内で別ジョブとして codify する**。さもなくば永続化する
- 既存重複を「block にすると弾かれるから」warning に妥協する時は、**その重複を解消する PR を同 schedule で landing させる**まで含めて 1 単位とする。今回は 3 ペア解消 + ERROR 化を 1 commit に同梱した

---

## AI フィールドの「層間欠落」を grep 突合で発見するコストが高い (2026-04-28 07:13 制定)

**起きたこと**: 本日 07:13 schedule-task で本番 `topics.json` を curl 集計したところ、`backgroundContext=0%` / `spreadReason=0%` / `forecast=0%` を観測。一見 success-but-empty の重大事故に見えたが、handler.py:30 の `_PROC_INTERNAL = {'spreadReason', 'forecast', 'storyTimeline', 'backgroundContext'}` を読むと「topics.json publish 時に意図的に除外」していることが判明 (size 抑制設計)。これらは個別 topic JSON / DynamoDB にのみ載る。**正常設計 vs バグ**の判定に proc_ai.py / handler.py / proc_storage.py を横断 grep する必要があり、5-10 分かかった。

| Why | 答え |
|---|---|
| **Why1** なぜ「正常設計」と「バグ」の判定にコストがかかった？ | フィールドが 5 層 (proc_ai schema → normalize → ai_updates → topics.json merge / 個別 topic JSON merge → frontend card / detail) を通る間、どの層で除外されるかが文書化されておらず、grep で毎回確認する必要があった |
| **Why2** なぜ層別ドキュメントが無かった？ | T245 (AI フィールド データフロー文書) が起票だけで実装されていなかった。「いつかやる」状態が連続 schedule-task で継続 |
| **Why3** なぜ T245 が放置された？ | 「文書整備」は不可逆性が低いが効果も即座には見えない。schedule-task の Claude は「効果が見える」改善を優先しがち。T245 のような基盤整備は「次の事故を防ぐ」効果が事前には可視化されにくい |
| **Why4** なぜ「事前に可視化されない効果」が後回しになる？ | scheduled-task-protocol v3 で「即時改善 1 件以上」を強制したが、その「1 件」を選ぶ基準が「観測効果が見える」に偏った。基盤整備系タスクは通らない |
| **Why5** なぜ基準が偏った？ | scheduled-task-protocol.md 自体が「unblocked タスクから 1 件」とだけ書いており、「基盤整備 vs 事象対応」の選択基準が無い。テキストルールの曖昧さが偏りを生んだ |

**仕組み的対策**:

1. **(構造・本 commit で実装) `docs/ai-fields-catalog.md` 新規** — 全 AI フィールドの 5 層追跡表を 1 ファイルに集約。`_PROC_INTERNAL` 除外仕様も明文化。次回以降「topics.json で 0% 観測 → 除外フィールドかカタログを見る → 個別 topic JSON で再観測」の判定が 30 秒で済む。
2. **(構造・別タスクで実装予定) フィールドカタログと proc_ai.py schema の CI 突合 (T256)** — proc_ai.py の `_build_story_schema` 内 field 名を grep し、ai-fields-catalog.md 先頭表の field 名一覧と diff。乖離があれば PR を block。「フィールド追加したらカタログも更新」を物理ガード。
3. **(構造・別タスクで実装予定) 個別 topic JSON 充填率 SLI (L4b)** — 現状 SLI 8/9/10 は L4a (topics.json) のみ観測。`_PROC_INTERNAL` で除外されたフィールドは L4b でしか観測できない。`scripts/check_ai_fields_coverage.sh` を拡張して `api/topic/{tid}.json` を sample で curl してフィールド充填率を集計。

**Claude の挙動分析 (なぜそうしたか)**:
- 本セッション開始時に T245 が「アーカイブ」の中段に埋もれており、優先度シグナルが弱かった。**TASKS.md の「アーカイブ」内に基盤整備タスクが入ると優先度が下がる構造**。
- 「即時改善 1 件」を選ぶ際、Claude は最初**「観測値で結果が見えるもの」**を検討した。docs ファイル新規は結果が見えにくいため後回し候補だったが、本セッションでは別 Code セッションが並走しており lambda / frontend を触れない状況 → docs 新規が現実的選択肢として浮上した。**並走セッションによる物理制約が、結果として基盤整備を優先させる方向に働いた偶然**。
- T245 を本 commit で実装したことで、「アーカイブから 1 件昇格 → 即実装」のパターンを成立させた。これは scheduled-task-protocol が想定する動きの 1 形態。

**メタ教訓**:
- 「アーカイブ」は休眠タスクではなく**基盤整備の倉庫**として運用すると、schedule-task で 1 件ずつ landing できる
- 並走セッションによる物理制約 (同じファイルを触れない) は、Claude にとって**「他の選択肢を強制的に検討させる」機構**として働く。競合は単なる事故ではなく、視野を広げる効果も持つ
- success-but-empty 検知の前段に **「除外設計を承知してから観測する」フェーズ** が必要。観測値 0% を見て即「半壊」と分類するのではなく、`_PROC_INTERNAL` 等の除外集合をまず確認する。本日のカタログ化はこのフェーズを 5 分から 30 秒に短縮する物理基盤


---

## scheduled-task-protocol とナオヤ前提 §8 の矛盾 (2026-04-28 08:10 制定)

**起きたこと**: 本日 08:10 schedule-task で「運用ルール検討」を求められ過去 commit log を観察したところ、直近の schedule-task が **毎回ほぼ何かを実装** している。`scheduled-task-protocol.md` フェーズ 2 で「最低 1 件以上必ず実装」を強制し、§「保留が許される条件」を 3 件 (ナオヤ判断 / core path / 復旧優先) で exhaustive に絞り、「効果が見えない」を保留理由として明示的に禁止しているのが原因。一方 `global-baseline.md §8` は ナオヤ前提として「効果が見えない間は保留でかまいません」「無理して更新しない」「念のためルール追加は禁止」を定めている。**両ルールが正面から矛盾し、Claude は protocol 側に従って毎回 CLAUDE.md / global-baseline / docs/rules を肥大化させてきた。**

| Why | 答え |
|---|---|
| **Why1** なぜ矛盾が放置された？ | protocol は「発見偏重 → 実装ゼロ」事故 (2026-04-28 04:15) への過剰反応として書かれ、ナオヤ前提 §8 と並べて読まれていない |
| **Why2** なぜ並べて読まれない？ | protocol §「保留が許される条件」が exhaustive で「効果が見えない」を明示禁止しているため、Claude は §8「保留でかまいません」を**特殊ケース**と暗黙解釈して本ルールに従ってしまう |
| **Why3** なぜ exhaustive が選ばれた？ | 当時の事故は「効果が見えない」が雑な escape hatch として濫用された。「絞らないと再発する」という恐れから過剰に絞った |
| **Why4** なぜ過剰だと気付かれない？ | commit-msg hook が schedule-task に `[Schedule-KPI] implemented=N ...` 行を必須化し、Claude は「N>0 にしないと不合格」と暗黙解釈する。実は `implemented=0` も構文上は通るが、protocol §「保留禁止」と組み合わさり、**物理的にも文書的にも「実装ゼロは負け」というシグナル**を発する構造になっている |
| **Why5** なぜシグナルが補正されない？ | ナオヤ前提 §8 と protocol を整合性チェックする物理ガードが無い。両者を突き合わせて読む頻度が低く、矛盾が「言わずもがな」として温存される |

**仕組み的対策（本 commit で 1 つ実装、2 つは保留と判断）:**

1. **(構造・本 commit で実装) `scheduled-task-protocol.md` §「保留が許される条件」に 1 件追加** — 「unblocked タスクが残っていても、低価値 / 効果事前不可視 / ナオヤ前提 §8 と矛盾する施策しか無い場合」を 4 件目として追加。ただし escape hatch 濫用防止のため「保留判断の理由を 3 行以内で報告に書く」を必須化。これでナオヤ前提 §8 と protocol の整合が取れる。
2. **(物理・保留) commit-msg hook に `implemented=0` 時の `reason=hold:<具体>` 必須化** — 即時実装可能だが、現在 `implemented=0` の commit が物理的に存在せず、効果が事前に観測できない。施策 1 を入れた後 1〜2 週間観測し、`implemented=0` commit が複数現れて雑な保留が観測されてから検討する。**ナオヤ前提「効果見えない間は保留」を本ルール自身にも適用**。
3. **(観測・保留) 週次で `chore:` only commit と `feat/fix:` 比率を集計** — schedule-task の「過剰実装」を観測する SLI 候補。施策 1 で十分か観測してから検討。即実装すると lessons-learned のメタ教訓「念のため SLI 追加は禁止」に抵触する。

**Claude の挙動分析 (なぜそうしたか)**:
- 本セッション開始時、私は最初「何を実装するか」を考えた。`session_bootstrap.sh` の出力 → `cat TASKS.md` → 1 件選んで実装する flow が頭にあった
- ナオヤ前提 §8「無理して更新しない」を読んだ後でも、protocol §「保留禁止」が脳内で優位になり、**「最小限の実装は何か」と探す方向**にバイアスがかかった
- 結果として「lessons-learned の追記 + protocol の最小修正」を選んだ。これはナオヤ前提に沿うが、**「実装ゼロ」が選択肢として最初から排除されていた**事実は変わらない
- このメタ的な観察を本 commit に書くことで、protocol が実際にどう Claude を縛っているかを記録する

**メタ教訓**:
- LLM への文書ルールは、**並べて読まれる前提で整合性チェックされる仕組み**が無いと矛盾が温存される。protocol と global-baseline を別ファイルで管理しているなら、双方を引用する整合チェック (CI) を 1 個入れるか、両者の責務境界を 1 行で書くかのどちらかが必要
- 「絞ったルール」は escape hatch 濫用への過剰反応として生まれることが多い。**過剰反応の補正タイミング (時刻 / 観測 N 件 / 矛盾検知) を同 PR 内で codify する** ルールが要る (lessons-learned 2026-04-28 07 「warning→ERROR 昇格 trigger」と同型問題)
- ナオヤ前提「無理して更新しない」を **新規ルール自身にも適用** することが、ルール肥大化を防ぐ最強の歯止めになる。本件で私が施策 2/3 を保留したのはこの原則の自己適用

---

## sitemap に書いた静的HTML が 50/50 件 404 — 監視に乗らない機能の SLI 漏れ（2026-04-28 08 schedule-task 「p003 多角的調査」で発見）

**起きたこと**:
- `news-sitemap.xml` に登録された `https://flotopic.com/topics/{tid}.html` を 3 件サンプリングしたら全て **HTTP 404**。`x-cache: Error from cloudfront` で S3 にファイルが無い状態
- `docs/system-status.md` には「✅ 静的 SEO HTML 生成 本番稼働 2026-04-26 topics/{tid}.html 500/500 件生成済み」と書かれていたが、現在の実態と乖離
- Google News / Search Console は sitemap を信頼してクロールに来るので、404 を返し続けると Google からの信頼度が下がり、長期で SEO 流入が減る

**なぜなぜ**:

| Why | 答え |
|---|---|
| **Why1** なぜ sitemap の URL が 404 を返した？ | S3 に `topics/{tid}.html` が存在しない |
| **Why2** なぜ S3 に存在しない？ | `proc_storage.update_topic_s3_file` 内の静的HTML 生成は `json_changed=True かつ aiGenerated or generatedSummary` の二重条件でしか書かれず、condition 不一致のサイクルで再生成されない。lifecycle.py の orphan cleanup が DynamoDB と S3 の整合を取りに来るが、生成側の取りこぼしを補えていない |
| **Why3** なぜそれに数日気付かなかった？ | 既存 SLI 1〜10 は `topics.json` 系のみで、**静的 SEO HTML の到達性を物理確認する step が無い**。CloudWatch にも metric が無い。「sitemap に書いた = 提供している」と暗黙視していた |
| **Why4** なぜ静的HTML 機能を追加したときに SLI を追加しなかった？ | Claude は「機能追加 PR」を実装側のコード変更にスコープ限定し、対応する **観測 (SLI / probe / alert) を同 PR で必須にする習慣** が無い。後から追加された SEO 用機能には外部観測が紐付かない |
| **Why5** なぜ SLI 必須化が習慣になっていない？ | CLAUDE.md / global-baseline には「外部観測を仕組み的対策に最低 1 つ含める」とあるが、これは **障害再発時** のルール。**新機能ローンチ時に対応 SLI を必ず作る** という前向きの物理ゲートが存在しない。「壊れてから観測を作る」運用なので、「壊れていることを誰も知らない」状態が温存される |

**仕組み的対策**（最低 3 つ・「外部観測」「物理ゲート」を含む）:
1. **外部観測 SLI 追加**: `freshness-check.yml` に **sitemap_reach step** を追加（`news-sitemap.xml` から 5 件サンプリング → HEAD 200 確認 → 1 件でも非 200 で Slack 通知）。本セッションで実装済 → SLI 11 として `docs/sli-slo.md` に追記
2. **物理ゲート（PR テンプレ）**: 新規 frontend ルート / sitemap 投入 PR で「対応 SLI を `docs/sli-slo.md` に追加したか」のチェック欄を必須化（CI で grep して未記入なら fail）
3. **手書き嘘記述の物理排除**: `docs/system-status.md` の「実測値」テーブル列を **自動生成セクションに移動**（governance worker が SLI 値で上書き）。手書きで嘘が書ける構造そのものを排除する。タスク化 → TASKS.md（本セッションで追記）

**メタ教訓**:
- 「壊れる前に観測を作る」 ≠ 「壊れた後に観測を作る」。後者は障害駆動でしか習慣化しないので、新機能の DoD（Definition of Done）に外部観測を物理的に紐付ける必要がある
- LLM (私) は「sitemap に書いた = 機能している」のように、**書いた行為と機能している事実を混同する** バイアスを持つ。出力（書いた sitemap、書いた system-status.md の数値）を実測値で物理検証する step が無いと、自分の出力を信じ続ける
- system-status.md のような「現状記述ファイル」は、Claude にとって実測値より優先されるアンカーになりやすい。**手書きで現状を記述するファイルは原則作らない**（自動生成 + 構造化検証）。これが Why5 への最強の補正

---

## 記事数グラフがトピック内記事数と乖離 — fetcher の cnt 水増し（2026-04-28 09 ナオヤ報告 T2026-0428-AI）

**起きたこと**:
- ナオヤ報告:「記事数のグラフなんかおかしくない？トピック内の記事の数とあってないんだけど」
- 本番調査結果（topic `c0ccd7d87d35f1f1`「日銀利上げと円安是正」）:
  - `meta.articleCount = 20` / グラフ最終点 = 20
  - 一方フロント表示「全 X 件の記事」= **8 件**しかない
  - SNAP[*].articles 内の unique URL = **7 件**（最大 SNAP）
- 同様の乖離は複数トピックで再現: `46b65be21d2ba151` (20 vs 8)、`cb67a069d9eff8fb` (20 vs 13) 等

**なぜなぜ**:

| Why | 答え |
|---|---|
| **Why1** なぜ articleCount=20 だが表示は 8 件？ | fetcher の `cnt = len(g)` はクラスタ生数。一方 SNAP.articles は URL で dedup される（`{a['url']: a for a in g}.values()` で書き込み）。20 個のうち 13 個が URL 重複で消える |
| **Why2** なぜ同一 URL が g に複数入る？ | RSS フィード横断で同じ記事 URL が複数フィードから来る（Yahoo!ニュースが他媒体記事を再配信し、元媒体 RSS にも同 URL が存在等）。`all_articles.extend(fetched)` は dedup しない |
| **Why3** なぜ気付かなかった？ | フロント側は detail.js:558-560 で「グラフ最終点を `meta.articleCount` で補正」する band-aid を入れていた。これは fetcher の水増しを隠蔽し、実 unique 数を表示しないだけで根本未修正。ユーザーが「グラフと記事リスト」を比較して初めて発覚 |
| **Why4** なぜ band-aid が選ばれた？ | 旧実装者は「SNAPのarticleCountはスナップショット値。topics.jsonの値（meta.articleCount）が正」とコメントを残しており、`s.articleCount` と `meta.articleCount` の意味が異なる前提で生きていた。実態は両方とも `cnt = len(g)` で同じ値。意味の取り違えで対症療法に流れた |
| **Why5** なぜ意味の取り違えが起きた？ | 「articleCount」という 1 フィールドが「クラスタ raw size」「dedup 後 unique URL 数」「累積 unique 数」の 3 つの異なる定義の間で曖昧に使われていた。命名と定義の単一正典が無く、用途ごとに別フィールドが切られていない |

**仕組み的対策**（最低 3 つ・「外部観測」「物理ゲート」を含む）:
1. **物理ゲート（fetcher dedup）**: `all_articles` を URL で dedup してから `cluster()` に渡す（handler.py Step 2.5）。`cnt = len(g)` が常に「unique URL 数」と一致する物理保証。同 PR で `tests/test_url_dedup_guard.py` を追加し、`[URL-DEDUP]` ログ文字列の存続と「dedup が cluster より前」を CI で assert
2. **物理ゲート（フロント防衛層）**: detail.js で `s.articleCount` 直参照をやめ、`s.articles?.length || s.articleCount` を使う `snapArtCount(s)` ヘルパーに統一。旧データ（既に水増し articleCount で書かれた DynamoDB / S3）でも実数表示できる二重ガード。同時に band-aid (line 558-560) を削除し「グラフ最終点を meta.articleCount で補正」の隠蔽を排除
3. **外部観測（boundary test 同梱）**: `tests/test_url_dedup_guard.py` に「inflated_count_scenario_real_world」テストを入れ、本番再現データ（同 URL × 3 source = 21 件 → dedup 後 7 件）でロジックを assert。dedup 動作が将来 refactor で消えても CI で物理ブロック

**メタ教訓**:
- band-aid（detail.js 558-560 の最終点補正）は「症状を見えなくする」ことには成功するが、**3 つの表示箇所のうち 1 箇所だけ**を修正したため、ユーザーが他の表示と比較した瞬間に矛盾が露呈する。band-aid は表示 N 箇所のうち N-1 箇所に矛盾を温存する構造なので、根本修正の代替にならない
- 「articleCount」のように同じ名前のフィールドが複数の定義の間で曖昧に流通するとき、コメントだけで意味を区別する設計は腐る。**フィールド名自体に定義を埋め込む**（`articleCountRaw` / `articleCountUnique` 等）か、**生成側で常に dedup する物理保証**かの二択にすべき。本件は後者（生成側で dedup）を採用した
- ユーザー報告は「グラフがおかしい」という UI レベルだが、根本原因はデータ生成パイプラインの 6 ステップ前にあった。UI 層の修正で済ませたくなる誘惑を断ち、データソースまで遡る習慣が要る（CLAUDE.md「対症療法ではなく根本原因」の典型適用例）

---

## 空トピック量産 — fetcher が META と detail JSON を非同期生成（2026-04-28 ナオヤ緊急報告 T2026-0428-AK）

**起きたこと**:
- ナオヤ緊急報告:「空トピックが量産され続けている。ユーザーが離れる原因になっている。即刻根本修正」
- 本番調査結果:
  - `topics.json` 109 件中 **12 件 (11%) が detail JSON 欠損** = ユーザーがクリックすると 404 / 何も表示されない
  - DynamoDB `p003-topics` の META 11,882 件中 **9,680 件 (81%) が articleCount<2** ゾンビ
  - articleCount<2 ゾンビは UI 層 (`fetcher/handler.py L693-694` の `articleCount>=2` フィルタ) で隠れているだけで、DynamoDB には残り続け永久に増殖

**なぜなぜ**:

| Why | 答え |
|---|---|
| **Why1** なぜ空トピックがユーザーに見える？ | topics.json に detail JSON が無いトピックが含まれていた。ユーザーは一覧から開くと 404 を踏む |
| **Why2** なぜ topics.json に detail なしが含まれた？ | fetcher が一覧 (META + topics.json) を生成 → processor が後刻 detail JSON を作る非同期設計。processor 起動前にユーザーが見ると detail 404 |
| **Why3** なぜ非同期設計？ | AI 処理 (Claude API) は重いので別 Lambda にした。fetcher は META、processor は detail + AI フィールドを担当。**「META = detail JSON」の不変条件を物理ゲートで守らなかった** |
| **Why4** なぜ articleCount<2 メタが累積した？ | `cluster_utils.cluster()` は最小サイズ閾値なしで singleton(=1記事) クラスタも返す。handler.py はそれを META に書く。UI 層では `articleCount>=2` でフィルタするが DynamoDB には残る。lifecycle の判定 (`score<20 AND lastArticleAt=0`) も満たさないため永遠にゾンビ |
| **Why5** なぜ気付かなかった？ | 既存の verify_effect.sh には `ai_quality` / `freshness` / `mobile_layout` はあったが「**topics.json の各トピックが本当に開けるか**」を物理計測する fix_type が無かった。ユーザーがクリックして「何も表示されない」と気付くまで、システムは健全と見なされていた |

**仕組み的対策**（最低 3 つ・「外部観測」「物理ゲート」を含む）:

1. **物理ゲート①（fetcher 入口）**: `cluster()` の結果を受けたメインループ冒頭で `unique_url_count<2 のクラスタは META/SNAP を書かない` ガードを追加 (`fetcher/handler.py` L334 直後)。articleCount<2 ゾンビが新規生成されない物理保証。
2. **物理ゲート②（fetcher 同期化）**: `_dynamo_puts` の batch 書き込み完了直後、saved_ids 各トピックに対して S3 `api/topic/{tid}.json` の存在を確認し、無ければ META + 今 SNAP から雛形 detail JSON を即生成。**「META が DynamoDB にある = detail JSON が S3 にある」を物理保証**。
3. **物理ゲート③（fetcher 出口）**: `write_s3('api/topics.json', ...)` 直前に detail JSON 存在を head_object で並列確認し、欠損トピックを除外する二重防御。レガシーゾンビ (META だけ残っている過去データ) も拾う。
4. **物理ゲート④（lifecycle 掃除）**: lifecycle が articleCount<2 メタを無条件削除 + topics.json 内の「DynamoDB META 欠損」「detail JSON 欠損」エントリも毎サイクル除去。fetcher 側の生成防止と並走する事後ゲート。
5. **外部観測**: `scripts/verify_effect.sh empty_topics` を新設。本番 URL から topics.json を取得し、各 topicId に対して `api/topic/{tid}.json` を実 HTTP HEAD で確認、`detail_missing 率 <= 0%` で PASS。Verified-Effect 行に組み込む物理ゲート。閾値違反は CI/Verified hook で物理ブロック。

**メタ教訓**:
- 非同期生成の 2 段パイプラインで「step1 が公開する index に step2 の出力が必須」という関係があるとき、**index 公開を step2 完了まで遅らせる** か、**step1 自身で雛形を作り step2 で上書きする** かの 2 択にしないと、必ずこの種の "404 見える化" バグが起きる。本件は後者 (雛形生成) を採用。
- band-aid 例: 既存の `processor.proc_storage.backfill_missing_detail_json()` は「事後補完」で対処していたが、META が一度でも消えると補完不可で恒久ゾンビ化する欠陥があった (本番で 12 件が補完不可状態)。**事後補完は「補完できない時に何が起きるか」を考えないと band-aid と同じ**。
- 「`articleCount>=2` でフィルタしている」という UI 層のロジックを根拠に DynamoDB のデータ品質を放置すると、フィルタが外れた瞬間に N 万件単位のゾンビが顕在化する。**UI 層フィルタはあくまで補助で、データソース層に同じ条件を物理ガードとして埋めない設計は腐る**。
- ユーザー目線の SLI (「クリックしたら何か表示される確率」) を verify_effect.sh の物理計測項目に入れていなかったのが Why5 の本質。次はナオヤ報告を待つ前に「ユーザー体験 SLI を追加」する習慣を持つ。

---

## ゴミデータ慢性蓄積の構造的欠陥（2026-04-28 10 T2026-0428-AO 全トピック棚卸しで発見）

**起きたこと**:
- ナオヤ報告「空トピックがフロントに並んで品質が悪い」→ 局所修正で fetcher / lifecycle にガードを足した（T2026-0428-AK）
- が、本番調査で全 META レコードを分類したら、現行スキーマ完備（GOOD）はごく一部で、残りは EMPTY / ZOMBIE_FORWARD_ORPHAN / ZOMBIE_REVERSE_ORPHAN / OLD_SCHEMA / NO_AI / PARTIAL_AI が混在
- 「修正したが過去データは治っていない」「lifecycle が DB を消しても topics.json / 静的 HTML / sitemap を更新しない」「schemaVersion 概念が無いので古いロジックで作られたレコードが GOOD と区別できない」が同時発生
- 局所パッチを重ねても充填率が改善しないので、全件棚卸し＋自己修復基盤化に切り替えた

**なぜなぜ**:

| Why | 答え |
|---|---|
| **Why1** なぜ空トピックが表示される？ | DB に articleCount=0 / keyPoint=null の META が残り、topics.json にもそれが反映されているから |
| **Why2** なぜ DB に空トピックが残る？ | lifecycle Lambda は削除条件を満たすレコードを DB から消すが、**派生ファイル（topics.json / 静的 HTML / sitemap / pending_ai.json）の同期更新を持たない**。「DB だけ消す」運用なので S3 上の zombie が消えない。さらに最近のスキーマで足された必須フィールド（keyPoint / statusLabel 等）の欠落を削除条件に入れていない |
| **Why3** なぜ作成側で防げない？ | fetcher / processor の **書き込み直前に最低品質ガード（記事数 >= 2、必須フィールド非空）が無い**。失敗時の中途半端な書き込みが META スタブを残す。「とりあえず書いて後から治す」前提で設計された結果、「治す側」がいつまでも追いつかない |
| **Why4** なぜ過去データが自動再処理されない？ | **再処理キューと品質監視 cron が存在しない**。processor は新規 / pendingAI=True のものしか触らない。過去レコードの keyPoint=null を発見する仕組みも、見つけたものをキューに戻す仕組みも、incremental に空フィールドだけ補完する保証も無い。結果、修正後の新規レコードは正常になるが、過去データは未来永劫壊れたまま残る |
| **Why5** なぜ schema 変更時に既存データの再処理が自動トリガーされない？ | **レコードに `schemaVersion` フィールドが無い**ので、ロジック側が「現行スキーマで処理済みかどうか」を区別できない。スキーマ変更のたびに別途バッチ移行スクリプトが必要になるが、それを書く運用が確立していないので毎回先送りされる。「ロジックを変えれば過去データは新ロジックで再評価される」という素朴な期待が外れ、過去ゴミが地層のように堆積する |

**仕組み的対策**（最低 3 つ・「外部観測」「物理ゲート」を含む・本セッションで全実装済み）:

1. **物理ゲート（schemaVersion による自動再処理）**: 全 META に `schemaVersion: <int>` を持たせ、processor 側に `PROCESSOR_SCHEMA_VERSION` 定数を置く。`needs_ai_processing(item)` 判定に `item.schemaVersion < PROCESSOR_SCHEMA_VERSION` を OR 条件で追加（`proc_storage.py:286-313`）。ロジック改善時は定数を 1 つ上げるだけで、過去データが自動的に再処理対象に入る。**スキーマ世代管理を物理化**することで「バッチ移行スクリプトを書き忘れる」を構造的に排除
2. **物理ゲート（quality_heal cron + bulk_heal CLI）**: `scripts/quality_heal.py` を daily で回し、品質劣化レコード（keyPoint 空 / schemaVersion 古い / 必須フィールド欠落）を検出して **pendingAI=True だけアトミック update**（既存フィールドは絶対に上書きしない）。GitHub Actions `.github/workflows/quality-heal.yml` で日次実行。手動棚卸し用に `scripts/bulk_heal.sh` をモード（all / no-keypoint / empty / old-schema）付きで用意。**dry-run デフォルト・APPLY=1 で実行**で事故防止
3. **物理ゲート（作成時ガード）**: fetcher 側で書き込み直前に articleCount >= 2 / 必須フィールド非空をチェックし、満たさなければ DB に書かない。「あとで治す前提の作成」を構造的に排除。lifecycle 側にも同判定を入れて毎サイクルで品質基準を下回るレコードを削除し、派生ファイル更新も同 invocation 内で行う
4. **外部観測（充填率 SLI）**: keyPoint / statusLabel / watchPoints の充填率を毎時サンプリングし、閾値を下回ったら Slack 通知。「治した」を主観で判定せず外部観測の数値で判定。本作業で確立した方針を `docs/sli-slo.md` に追加（タスク化）
5. **構造（プレイブック化）**: 本件の知見を `docs/rules/data-quality-playbook.md` に汎化し、他プロダクト（P002 Unity / P006 / 将来）に転用できる形で残した。「12 項目チェックリスト」で **データ品質基盤の有無を物理判定**できるようにした。次回 Claude が新プロダクトを立ち上げる際、全 12 項目に ✅ が付くまで「データ品質基盤あり」と呼ばないルール

**メタ教訓**:
- 「修正した」と「過去データが治った」は別物。**新規レコードの正常化**と**過去レコードの自動再処理**は別の物理機構が要る。前者だけ実装して「直した」と報告する Claude のクセは、SLI（充填率）が改善しないことで物理的に検出できるようにしないと止まらない
- ゴミの蓄積は「lifecycle が無いから」ではなく「lifecycle が DB だけ見て派生ファイルを見ないから」が頻出パターン。**DB と派生ファイルの 2 軸クリーン**を 1 つの cleanup スクリプトで原子的に行う必要がある。片方だけ消すと次回スキャンで反対側から zombie として検出されて堂々巡り
- `schemaVersion` のような「世代を物理表現するフィールド」が無いと、Claude も人間も「現行スキーマで処理済みか」を判定できない。新規プロダクトでは **最初のレコード設計時点で schemaVersion を入れる** のが最強の予防策。後から足すと既存全件のデフォルト値判定で揉める
- 局所パッチが 2 回続けて効かなかったら全件棚卸しに切り替えるサイン。「もう 1 回パッチしたら治る」の誘惑が強いが、**ガード追加 → 充填率不変 → さらにガード追加** の悪循環は band-aid を量産するだけで根本問題（自己修復機構の不在）を温存する。プレイブック §1-3 のサインリストを物理的に毎回確認する

---

## worktree branch push で「完了」宣言 — main マージが誰もやらず本番未反映（2026-04-28）

**起きたこと**:
- コードセッションが worktree ブランチに push して「完了」と宣言していた
- しかし main へのマージが誰もやらなかったため、変更が本番に一切反映されていなかった
- `Verified: https://flotopic.com/ 200 OK` は「サイトが生きていること」の確認であり、「変更が反映されたこと」の確認ではなかった
- 結果、「完了」と記録されたタスクの変更が本番環境に存在しないまま運用継続（閲覧履歴 15 件上限バグ等が直っていない原因）

**なぜなぜ**:

| Why | 答え |
|---|---|
| **Why1** なぜ履歴 15 件上限バグが直らない？ | 修正が main にマージされていないため、本番は古いコードのまま動いている |
| **Why2** なぜ main にマージされていない？ | コードセッションは feature branch (worktree) に push して「完了」と宣言し、PR 作成 / マージ / deploy 確認の手順が完了定義に含まれていなかった |
| **Why3** なぜ完了定義にマージが含まれていなかった？ | CLAUDE.md の「完了 = push 後に本番 URL で実機確認」は feature branch push 後でも本番 URL が 200 を返す（古いコードが生きているため）。push するだけで完了条件が満たせる定義の欠陥があった |
| **Why4** なぜ `Verified: URL 200 OK` がデプロイ確認と誤解された？ | `Verified:` の説明が「本番 URL 到達確認」のみで「変更が本番に反映されたこと」との区別が明文化されていなかった。URL が 200 を返せば変更も反映されているという暗黙前提が検証されないまま残っていた |
| **Why5** なぜ feature branch push で満足してしまった？ | worktree を使うマルチブランチ開発では「push = 公開」ではない。しかし CLAUDE.md の完了定義はシングルブランチ（main 直 push）前提で書かれており、ブランチ戦略が変化したときに完了定義を更新しなかった |

**仕組み的対策**（最低 3 つ・「外部観測」「物理ゲート」を含む）:

1. **物理ゲート（done.sh main マージチェック）**: `done.sh` に `git fetch origin main && git merge-base --is-ancestor HEAD origin/main` チェックを追加。false なら `exit 1` で完了として扱わない。`Verified-Deploy: git log main shows <hash> @ <JST>` を出力して commit メッセージへの記載を促す。**「push した」と「main に入った」を物理的に区別するゲート**（本件で実装済み）。
2. **物理ゲート（CLAUDE.md 完了定義更新）**: 「完了 = main ブランチにマージ済み + GH Actions deploy 完了 + 動作確認 + 効果検証」に定義を改定。feature branch push だけでは未完了と明記。`Verified-Deploy:` 行を `Verified:` 行と同等の必須 commit 要件に昇格（本件で実装済み）。
3. **外部観測（Verified-Deploy 行による変更追跡）**: `Verified-Deploy: git log main shows <hash> @ <JST>` を commit メッセージに必須化。「どの commit が main に入ったか」「いつ deploy されたか」が git log から追跡可能になる。`Verified:` が「サイト生存確認」、`Verified-Deploy:` が「変更反映確認」という役割分担を明確化。

**メタ教訓**:
- 「本番 URL が 200 を返す」≠「自分の変更が本番に入っている」。前者は既存コードが動いているだけで成立する。LLM はこの区別を意識的に求めないと混同する。`Verified:` と `Verified-Deploy:` を **別の証跡として必須化** することで、混同を物理的に排除する
- ブランチ戦略が「main 直 push」から「feature branch + PR」に変わったとき、完了定義も連動して更新する必要がある。開発フロー変更時は「完了定義が新フローに整合しているか」を必ずチェックする
- `done.sh` のような完了処理スクリプトは「完了の物理化」の最前線。ここに main マージチェックを入れることで、どのセッション（Code/Cowork）でも同じ基準が適用される。ルールをファイルに書くだけでなく、スクリプトで強制する構造が必要

---

## コンフリクト解決時に「upstream 版採用」で CLAUDE.md を破壊（2026-05-02）

**起きたこと**:
- T2026-0502-B 実装の Code セッションが main rebase 時にコンフリクト発生
- 「chore: マージコンフリクト解決 (upstream版を採用)」で **CLAUDE.md を 156→117 行に圧縮** + `~/ai-company/...` を `/Users/<owner>/ai-company/...` 形式（フルパス）に置換
- 結果: ① Cowork 用の重要セクション（Dispatch 起動時手順 / Dispatch 絶対禁止パターン）が消失 ② owner username を含む PII が main に流入 ③ main の PII 検査 CI が真っ赤化 ④ 自分の PR (#125) も auto-merge できず `mergeable_state=blocked` で詰まった
- Code セッションは「PR 作成」で done.sh を回し、自分の PR が merge されていないこと・main が赤いことを認識せず「完了」報告
- Cowork が事故を発見し PR #126 で CLAUDE.md を 7e50e5a0 から復元 + `~/ai-company/` 表記に統一して main を回復、その後 PR #125 を API 直 merge で取り込み

**なぜなぜ**:

| Why | 答え |
|---|---|
| **Why1** なぜ CLAUDE.md が破壊された？ | コンフリクト解決時に `git checkout --theirs` 系の「upstream版採用」を選び、自分のローカル変更（最新の CLAUDE.md）を捨てて古い版で上書きしたから |
| **Why2** なぜ「upstream 版採用」を盲目的にやった？ | CLAUDE.md/WORKING.md/TASKS.md/HISTORY.md は両セッションが書き込む共有ドキュメント = **3-way マージで両側を取り込む必要があるファイル**。これを「ours か theirs か」の二択で潰した |
| **Why3** なぜ事前に止まらなかった？ | コンフリクト発生時に「どっちが新しい・どっちに重要セクションが残っているか」を確認する物理ゲートが無く、Code セッションは判断を最小化したいので楽な方（upstream 採用）に流れる |
| **Why4** なぜ自分の PR が merge されないことに気づかず done 報告した？ | `done.sh` は PR merged 済みを必須ゲートにしておらず、「PR 作成」で完了扱いになる。自分の修正で main CI が赤化していても検出しない |
| **Why5** なぜ auto-merge が blocked で詰まっても気付かない？ | Code セッションは CI 待ちを禁止されているのでセッションを即クローズ。Cowork 側に「auto-merge 詰まり監視」の cron が無い。**「Code が PR 作成 → 即 exit → 後は誰も見ない」** という構造的な穴 |

**仕組み的対策**（最低 3 つ・「外部観測」「物理ゲート」を含む）:

1. **物理ゲート（コンフリクト解決ガイド + 自動検査）**: `docs/rules/conflict-resolution.md`（新規）に「**CLAUDE.md / WORKING.md / TASKS.md / HISTORY.md / docs/lessons-learned.md は両側マージ必須・upstream 採用禁止**」を明記。`scripts/conflict_check.sh` で `git status | grep "^UU "` 結果に上記ファイルが含まれていたら ERROR で停止し、3-way マージ手順を促す
2. **物理ゲート（done.sh の PR merged + main green ゲート）**: `done.sh <task_id>` に①自分の PR が merged 済み ②main の最新 CI が green、の両判定を組み込み、いずれか false なら exit 1 で完了処理を拒否する。`Verified-Merge: PR #N merged @ <JST>` を commit-msg hook で必須化
3. **外部観測（auto-merge 詰まり監視 schedule task）**: 1 時間に 1 回、open PR で `auto_merge: enabled & mergeable_state: blocked & 失敗 check 0` の組合せを検出 → Slack 通知 or 自動 API merge 実行。「Code が exit してから merge されるまで」の責任を担うスケジューラーを追加
4. **物理ゲート（PII grep pattern 拡張）**: 既存の `m[u]rakaminaoya|mr[k]m\.naoya|n[a]oya643` に加え、`/Users/[a-z]+/.+/scripts/` のような汎用フルパスパターンを追加。Cowork 環境ではフルパスが自然だが、共有ドキュメントでは `~/` か `$HOME/` を使うルールを物理化

**メタ教訓**:
- コンフリクトは「楽な方」（upstream / ours 採用）で逃げると相手側の最新変更が消える。**両側に意味のある情報がある共有ドキュメントは 3-way マージが原則**。LLM は判断コストを下げたがるので、自動化されたガイド（conflict_check.sh）で止めるしかない
- 「PR 作成 = 完了」と「PR merge = 完了」は別物。Code が PR 作成直後に done.sh を回す現行運用では、自分の PR が CI 赤・conflict・auto-merge 詰まりで停滞しても誰も気付かない構造的な穴がある。**done.sh が PR merged を要求** + **auto-merge 詰まり監視 cron** の二重防御が必要
- auto-merge が `mergeable_state=blocked` で詰まる場合、CI 全 green でも GitHub の internal recompute ラグで動かないことがある。**API 直 merge (`PUT /pulls/N/merge`)** が最速の救済手段。5 分以上 blocked が続くなら API merge を選択する。「待つ vs 介入」の判断基準を 5 分閾値で物理化

**横展開チェックリスト**:
- [x] `docs/rules/conflict-resolution.md` を新規作成（T2026-0502-CONFLICT-DOC 完了 / PR #138 で landing 済 / 2026-05-02 確認）
- [x] `scripts/conflict_check.sh` を新規作成（T2026-0502-CONFLICT-SCRIPT 完了 / PR #138 で landing 済 / 2026-05-02 確認）
- [ ] `done.sh` に PR merged + main green チェック追加（タスク化: T2026-0502-DONE-GATE）— 部分実装: 56 行目で `git merge-base --is-ancestor HEAD origin/main` の ancestry チェックは入っているが、main の最新 CI が green であることの判定はまだ無い
- [x] auto-merge 詰まり監視 schedule task を作成（T2026-0502-D 完了 / `.github/workflows/automerge-stuck-watcher.yml` + `scripts/automerge_stuck_watcher.py` + `tests/test_automerge_stuck_watcher.py`・10分毎 cron + workflow_dispatch）
- [ ] `.github/workflows/ci.yml` の PII grep に `/Users/[a-z]+/` 追加（タスク化: T2026-0502-PII-EXPAND）
- [x] Cowork が PR 再投稿する際の重複 PR を自動クローズ（2026-05-02 PR #137 で `pr-conflict-guard.yml` が「コード本体多重編集」fail を出した事故対応 / `scripts/cowork_commit.py` に `detect_and_close_overlapping_cowork_prs()` 追加・`cowork/*` ブランチ PR でファイル重複を検出したら自動 close + comment）

---

## CI/Workflow 失敗を「観測しないまま仮説で動いた」バグ（2026-05-02 制定・T2026-0502-Q 由来）

**事件**: 2026-05-02 09:50 JST、Cowork が `Lambda デプロイ（全関数）` workflow の連続失敗を発見。`fetcher Lambda をデプロイ` step が failure になっている事実 + `p003-fetcher` の Lambda env から `ANTHROPIC_API_KEY` が消えている事実 だけ見て「**空 secret → AWS Validation Error**」という根本原因仮説に飛びついた。仮説に基づき PO に「Anthropic key revoke + GitHub Secret 更新 + Lambda env 再設定」の 5 ステップ手順書を渡し、Code セッション dispatch プロンプトも仮説前提で書いた。Eng Claude が dispatch 受領後すぐに `gh workflow run` で手動 trigger → raw logs を見たところ、**真の原因は workflow 46→61 行目のパス解決バグ**（`cd projects/P003-news-timeline/lambda/fetcher` してから相対 `python3 scripts/ci_lambda_merge_env.py` を呼ぶが、script は repo root 直下にあるので `[Errno 2] No such file or directory` で必ず exit 2）。secret 値の有無とは無関係の構造的バグだった。Cowork の根本原因仮説は完全に外れ。PO 時間を 30 分以上奪い、key rotation という不可逆操作を一歩手前で踏ませようとしていた。

### Why1〜Why5

| 層 | 質問 | 回答 |
|---|---|---|
| Why 1 | なぜ仮説が外れたか | `Environment.Variables` から ANTHROPIC_API_KEY が欠落していた事実と、空 secret → Validation Error 仮説が一致して見えたが、欠落の原因は別（deploy が一度も完走していないので env 上書きが成立していないだけ）。env 欠落は症状の一つで原因ではなかった |
| Why 2 | なぜ raw logs を見なかったか | `aws logs filter-log-events`（Lambda 側）は見たが、GitHub Actions step level の **stderr** を見ていない。GitHub API `/jobs/{id}/logs` リダイレクト先の Azure CDN URL が proxy で 403 で諦め、代替手段（workflow の手動 dispatch + 即読みなど）を取らなかった |
| Why 3 | なぜ仮説 1 つで動いたか | `docs/rules/quality-process.md` L16 の **「原因仮説を 3 つ以上列挙し、最も可能性の高いものを選んでから修正に入る」** ルールを守らなかった。3 つ以上出していれば「(b) script のパス解決バグ」が候補に入り、観察手段で 1 個ずつ潰す動きになっていた |
| Why 4 | なぜ confirmation bias に陥ったか | 観察（env から ANTHROPIC_API_KEY 欠落）と仮説（空 secret → Validation Error）が片方向の整合に見えた瞬間、**反証検索を停止**して PO 向け手順書きに移った。スピード優先・即アクションへの誘惑が勝った |
| Why 5 | なぜルールが体に染みていなかったか | quality-process.md は読み込まれていたが「実装直前」の局面でしか想起されておらず、「**仕組み（CI/Workflow）の障害分析**」も同じ rule の対象であるという**横展開**ができていなかった。「仮説 3 つ以上」は **コード修正前** だけでなく **PO に手順を渡す前 / dispatch を出す前** にも適用すべき |

### 仕組み的対策（物理 ★ 優先・思想は補助）

> CLAUDE.md global-baseline §6「物理化できる対策は物理化する」に従い、思想ルール（テキスト追記のみ）は最後の補助とし、物理ガード（CI/hook/script で reject）を主軸に置く。

| # | 対策 | 強度 | 実装 |
|---|---|---|---|
| 1 | **dispatch script の引数 required 化 (★物理)** | 物理 | `scripts/gen_dispatch_prompt.sh` に `--observation-evidence <URL or 再現コマンド>` 引数を required 化。空なら `exit 1` で Cowork が dispatch を出せなくなる。仮説段階の dispatch を script レベルで block |
| 2 | **PR テンプレで raw logs URL 必須 (★物理)** | 物理 | `.github/PULL_REQUEST_TEMPLATE.md` を新設し、「外部 CI/Workflow 障害修正の場合、根本原因の根拠 URL (workflow run / 再現 commit / log line) を本文に含める」section を必須化。CI `pr-evidence-check.yml` (新規) で `external-workflow-fix` ラベル付き PR を対象に grep 検証 → 空なら fail |
| 3 | **commit-msg hook で仮説止め commit を reject (★物理)** | 物理 | `.git/hooks/commit-msg` に「`fix:` 系 commit で `Verified:` 行が無い、かつ commit message に「仮説」「推定」「probably」「可能性が高い」を含むなら reject」を追加。物理的に「未確定の修正」を main に入れさせない |
| 4 | **landing 物理検証 (★物理)** | 物理 | `scripts/check_lessons_landings.sh` に上記 3 ファイルの存在 + キーワード grep を追加。テキストルールが消えても CI が即 fail |
| 5 | (補助) ルール明文化 | 思想 | `docs/rules/quality-process.md` に「外部 CI/Workflow 障害は raw logs/手動再現を取得してから仮説確定」を追記。物理 #1〜#3 を回避された場合のテキスト軸 |
| 6 | (補助) Cowork mental checklist | 思想 | dispatch を出す直前に「仮説 3 つ以上挙げたか / 観察手段で 1 つに絞ったか / PO に不可逆操作を依頼していないか」の self-check。物理化困難 (Cowork 自身が自分を縛る規律のため) |

### 横展開チェックリスト

- [ ] `scripts/gen_dispatch_prompt.sh` に `--observation-evidence` required 引数追加（タスク化: T2026-0502-DISPATCH-REQ・**物理**）
- [ ] `.github/PULL_REQUEST_TEMPLATE.md` 新設 + `pr-evidence-check.yml` で外部障害修正 PR の証拠 URL 必須化（タスク化: T2026-0502-PR-EVIDENCE・**物理**）
- [ ] `.git/hooks/commit-msg` (`scripts/install_hooks.sh` 経由) に「`fix:` で仮説語+`Verified:` 不在を reject」追加（タスク化: T2026-0502-COMMIT-GUARD・**物理**）
- [ ] `scripts/check_lessons_landings.sh` 拡張で上記 3 物理ガードの landing を検証（タスク化: T2026-0502-LANDING-CHECK・**物理**）
- [ ] `docs/rules/quality-process.md` に「外部 CI/Workflow 障害は raw logs/手動再現を取得してから仮説確定」を追記（タスク化: T2026-0502-INVEST-RULE・補助思想）
- [ ] 自分（Cowork セッション）の dispatch 出力前 mental checklist（運用ルール・タスク化なし・補助思想）

---

## deploy-lambdas.yml 内 `cd <subdir> && python3 scripts/...` で 18 時間 deploy 停止（2026-05-02）

**起きたこと**:
- `.github/workflows/deploy-lambdas.yml` の fetcher step が `cd projects/P003-news-timeline/lambda/fetcher` 後に `python3 scripts/ci_lambda_merge_env.py` を相対パスで呼んでいた
- script の実体は repo root 直下のため `[Errno 2] No such file or directory` で必ず exit 2
- 直近 10 連続 deploy failure (2026-05-01 08:14〜 18 時間以上)
- 本日の Lambda コード変更 (PR #114 / #118 / #125) が**全て本番未反映のまま**「merged」と記録されていた
- Cowork が PR #141 で `$GITHUB_WORKSPACE/scripts/...` の絶対パス参照に修正 → run #372 success で初めて本番反映

**なぜなぜ**:

| Why | 答え |
|---|---|
| **Why1** なぜ deploy が落ち続けた？ | `cd subdir` 後に repo root 起点の相対パスで script を呼んでいたから |
| **Why2** なぜ bug がレビューで通った？ | yaml `run:` block 内の埋め込みシェルは CI lint 対象外。実行時にしか検出できない死角 |
| **Why3** なぜ 18 時間気付かなかった？ | deploy-lambdas 連続失敗を観測する SLI/cron が存在しない。merged PR は「merge した = 完了」で、deploy 結果を遡って見る習慣がない |
| **Why4** なぜ「merge = 完了」運用？ | done.sh が PR merged + deploy success をゲート化していない（既存 lessons-learned で物理化候補だが未実装）。Verified-Deploy 行も推奨止まり |
| **Why5** なぜ同 anti-pattern が他 workflow に潜まないと言える？ | yaml 内シェル script の「`cd` + 相対 path-to-repo-root」を grep する物理ガード無し。shellcheck も yaml 埋め込みは追えない |

**仕組み的対策**（最低 3 つ・物理ゲート 3 + 観測 1）:

1. **物理ゲート（workflow path lint）**: `.github/workflows/*.yml` の `run:` block 内で `cd <subdir>` 直後に `scripts/`・`tests/`・`docs/` で始まる相対パス参照を grep して ERROR。`scripts/check_workflow_paths.sh` 新規作成 → ci.yml 統合
2. **物理ゲート（deploy-lambdas 連続失敗 watcher）**: schedule task で `gh run list --workflow deploy-lambdas.yml --status failure --limit 3` を 1 時間に 1 回確認し、3 連続 failure で Slack notify + TASKS.md 自動起票。`automerge-stuck-watcher.yml` の隣接実装
3. **物理ゲート（done.sh の deploy-success 必須化）**: 既存タスク T2026-0502-DONE-GATE 実装時に「Lambda 変更を含む PR は該当 deploy workflow の run が green」を必須ゲート化
4. **観測（deploy 成功率 SLI）**: `freshness-check.yml` SLI セットに「直近 24h の deploy-lambdas.yml success 比率」を追加。10% 下回りで Slack alert

**メタ教訓**:
- **「merged = 完了」は嘘**。deploy が green / Lambda env 反映 / CloudWatch logs に新コードのマーカー出現 の 3 段で初めて完了。done.sh で物理化しないと「気を付ける」は守られない＝形骸化（既存ルールに記載があるのに守られていない）
- yaml 内埋め込みシェルは CI lint 死角。**「workflow yml は yaml syntax check だけでなく run: block の semantic lint も必要」**
- CI/CD pipeline 自身の SLI を持たないと「直したつもり」が本番に届かない事故が再発する

**横展開チェックリスト**:
- [x] `scripts/check_workflow_paths.sh` 新規作成（タスク化: T2026-0502-WORKFLOW-PATH-LINT・**物理**）← `scripts/check_workflow_paths.sh` + `tests/test_check_workflow_paths.sh` + `.github/workflows/ci.yml` 統合済
- [ ] deploy-lambdas 連続失敗 watcher（タスク化: T2026-0502-DEPLOY-WATCHER・**物理**）
- [ ] `done.sh` の PR-merged + deploy-success ゲート（既存 T2026-0502-DONE-GATE と統合・**物理**）
- [ ] freshness-check.yml に deploy 成功率 SLI 追加（タスク化: T2026-0502-DEPLOY-SLI・**物理**）
- [ ] 過去 30 日の git log × CloudWatch deploy event 突合で「merged だが未 deploy」PR の遡及検出（タスク化: T2026-0502-DEPLOY-AUDIT・**観測**）

---

## T2026-0502-L: Bluesky `debut` モード 48件/日 過剰投稿（per-day cap 設計欠陥）

**起きたこと**: 5/1 (JST) の Bluesky 投稿件数を集計したところ **48件**。30分 cron (`flotopic-bluesky-schedule` rate(30 minutes)) 発火 × `post_debut` が 1 tick あたり 1 件投稿 × pending マーカー累積 → ほぼ毎 tick 投稿という事故。`daily` モードは `DAILY_COOLDOWN_HOURS=8` で日次3件に物理制限していた一方、`debut` には per-day cap が一切無かった。

**経緯**:
- 4/28: `debut` 機能（初回 AI 要約完了 → 即時通知投稿）導入。`DEBUT_MAX_PER_RUN=1` で「tick あたり 1 件」とだけ規定。
- 4/30: 7件/日（pending マーカー累積によりじわじわ増加）
- 5/1: **48件/日**（処理対象トピック増 + 30分 cron でほぼ全 tick 投稿）
- 5/2 09:19 JST: 応急処置 commit `db64b662` で `DEBUT_MAX_PER_RUN=0` に設定（debut を完全無効化するキルスイッチ）
- 5/2 10:55 JST: 本タスクで恒久対処 — `BLUESKY_POSTING_CONFIG` 集約 + `_check_rate_limit()` 単一エントリ + 24h cap 二重ガード + ユニットテスト 14 件

**なぜなぜ**:

| Why | 答え |
|---|---|
| **Why1** なぜ debut が 48件投稿された？ | 30分 cron が 48 tick/日発火し、`post_debut` が tick あたり 1 件投稿していたから |
| **Why2** なぜ debut だけ大量投稿になった？ | `daily` モードは `DAILY_COOLDOWN_HOURS=8` で日次キャップを物理担保していたが、`debut` には日次キャップが**設計時点で存在しなかった** |
| **Why3** なぜ debut の日次キャップを忘れた？ | 「pending マーカーは溜まらない前提」「新トピック登場通知だから即時性優先」で設計し、daily と debut を別系統管理にしたが、daily の cooldown 設計を debut にコピペしなかった。レート制御ロジックがモードごとにスコープ閉鎖していた |
| **Why4** なぜモード横断のレート制御抽象化が無かった？ | 後追いで追加された `morning` (T193, 4/29) も `MORNING_COOLDOWN_HOURS` を独自実装しており、3 モード分の rate-limit ロジックが重複コード。差異が見えにくい構造だった |
| **Why5** なぜ単発実装の都度コピペが許容された？ | レート制御の「単一の真実の源」を強制する CI gate / lint が無く、各 post_xxx() 関数が独自に DynamoDB を叩いてクールタイム判定するのが「自然」になっていた。新規モード追加時のチェックリスト不在 |

**仕組み的対策**（最低 3 つ・物理ゲート 3 + 観測 1）:

1. **物理（設定一元化）**: `BLUESKY_POSTING_CONFIG` 辞書を `scripts/bluesky_agent.py` 冒頭に集約。`enabled` / `cooldown_hours` / `max_per_24h` の 3 キーを必須化。テスト `test_config_each_mode_has_required_keys` で物理担保
2. **物理（単一エントリ強制）**: `_check_rate_limit(mode)` を全 `post_xxx()` の唯一のレート判定窓口にする。テスト `test_daily_total_capped_at_4` で「daily 3 + morning 1 + debut 0 = 4 件/日」の上限を物理 assert
3. **物理（24h cap 二重ガード）**: cooldown チェックだけだと cron 揺らぎ・先行 tick 失敗で抜けるため、`max_per_24h` の DynamoDB スキャンによる二次ガードを追加。`test_at_cap_blocks` で検証
4. **観測（投稿件数 SLI）**: 日次投稿件数を CloudWatch メトリクスに publish して 7 件/日超過で Slack alert（タスク化: T2026-0502-BLUESKY-SLI）

**メタ教訓**:
- **「daily と debut は別系統」を理由にレート制御をコピペしないと、片側だけ抜ける**。共通制約（投稿頻度）は単一エントリで強制するのが正しい
- **per-day cap は cooldown だけでは不十分**。cron 揺らぎ・初回 tick・タイムゾーン境界で抜ける。24h スキャンによる二次ガードを併用する
- **キルスイッチ (`DEBUT_MAX_PER_RUN=0`) は応急処置であり恒久対処ではない**。設計欠陥は設計レイヤーで修正する
- **頻度・内容の調整を一箇所で完結させたい**（PO 指示）→ Single Source of Truth (SSoT) パターン。新規モード追加時に「設定追加 → 自動的にレート制御が効く」構造にする

**横展開チェックリスト**:
- [x] `BLUESKY_POSTING_CONFIG` 集約 + `_check_rate_limit()` 実装（**物理** / 本 PR）← `scripts/bluesky_agent.py` + `projects/P003-news-timeline/tests/test_bluesky_rate_limit.py` 14件
- [ ] 同パターン横展開: `scripts/x_agent.py` (X/Twitter 投稿) のレート制御を SSoT 化（タスク化: T2026-0502-X-RATE-SSOT・**物理**）
- [ ] 同パターン横展開: `scripts/marketing_agent.py` / `scripts/editorial_agent.py` の頻度制御を点検（タスク化: T2026-0502-AGENT-RATE-AUDIT・**思想 → 物理化検討**）
- [ ] Bluesky 日次投稿件数 SLI（CloudWatch メトリクス + 7件/日 alert・タスク化: T2026-0502-BLUESKY-SLI・**観測**）
- [ ] 「キルスイッチ常駐検出」CI lint: コードに `MAX_PER_RUN = 0` のような実質無効化マジック値が残っていたら WARN（タスク化: T2026-0502-KILLSWITCH-LINT・**物理**）
- [x] **dead config 検出テスト**: `test_only_active_modes_in_config` で「CONFIG にあるが `_check_rate_limit` を呼ばないモード」を物理 reject（**物理** / 本 PR フォロー）— 「動かすための設計」「将来用エントリ」を残さない予防。

**追加メタ教訓 (PO audit より)**:
- **「将来使うかも」で CONFIG エントリを残さない**: weekly/monthly を CONFIG に入れても post_weekly/post_monthly が `_check_rate_limit` を呼んでいなければ dead config。CI で機械的に検出する
- **legacy alias は実需 0 なら削除**: `DAILY_COOLDOWN_HOURS = CONFIG[...]` のような alias は「外部参照」を grep で確認した上で需要 0 なら即削除する。残すと「使われていないが何かの拍子に参照されるかも」という曖昧なコードになる

---

## T2026-0502-M: git エラー黙殺と main 直 push 滞留 — 6 commit が 11 時間ローカルに留まり実コードが本番未反映（2026-05-02）

**起きたこと**:
- ローカル main が origin/main から 6 commits 先行 / 4 commits 遅れの diverged 状態
- ローカル 6 commit のメッセージは全部 `auto-sync: session end ...` または `chore: bootstrap sync ...` だが、**中身は handler.py / proc_storage.py / bluesky_agent.py / test_*.py 等の実コード変更**
- リモート 4 commit は PR #150/#149/#147/#146 のマージ済み履歴 → ローカルが 11 時間以上未取り込み
- session_bootstrap.sh は失敗時もログ末尾に「✅ 起動チェック完了」を出していて、PO・他セッションが diverge を観測できなかった

**なぜなぜ**:

| Why | 答え |
|---|---|
| **Why1** なぜローカル main が 6 commit diverged したか | `session_bootstrap.sh` の `git pull` / `git push` が `2>&1 \| _strip_fuse_noise \| tail -2 \|\| true` で終了コードを完全に黙殺していた。`! [rejected] main -> main (non-fast-forward)` が起きても処理続行 |
| **Why2** なぜ気付かなかったか | スクリプト末尾で常に「✅ 起動チェック完了」が出力される設計（exit 0 が保証されていた）。pipefail 不在 + `tail -2` で末尾2行しか見えず、ヒント行 (`hint: ...`) だけが残ってエラー本体は捨てられていた |
| **Why3** なぜ auto-sync 系スクリプトが main 直接に commit したか | ローカル diverge を解消するルートが整備されておらず、終了時 hook (`auto-sync: session end ...` を生成する外部スクリプト) や `auto-push.sh` が main 直 push する設計になっていた。pre-push hook も branch protection も無く、PR を経由しない経路が物理的に存在した |
| **Why4** なぜ tail -2 が入っていたか | FUSE 環境の harmless noise（`unable to unlink ...` 等）でログを汚染しないため。フィルタ自体は `_strip_fuse_noise` で実害ゼロ noise だけ落としていたが、tail -2 は noise filter とは別の役割を後付けで担っていただけで不要だった |
| **Why5** なぜ「ガードはあるのにマージまで届かない」状態が放置されたか | PR フロー側は重装備（`auto-merge.yml` / `automerge-stuck-watcher.yml` / `pr-conflict-guard.yml` / commit-msg で Verified 強制 / pre-commit で section-sync）だが、**ローカル → main の経路だけが思想ルール頼み**だった。「PR 経由必須」は CLAUDE.md と cowork_commit.py のテキストに書かれているだけで、git CLI 自体が main 直 push を許可していた。物理化されていない思想ルールは「気を付ける」と同じ強度しかない（global-baseline §6） |

**仕組み的対策**（最低 3 つ・物理ゲート 3 + 観測 1）:

1. **物理（bootstrap の git エラー観測可能化）**: `scripts/session_bootstrap.sh` の `git pull` / `git push` で `PIPESTATUS[0]` を捕捉し、非ゼロなら `BOOTSTRAP_EXIT=1` を立てて末尾で物理 exit 1。`tail -2` 撤去。FUSE noise filter (`_strip_fuse_noise`) は維持。**実装: PR #159 → 不完全（PIPESTATUS 取得のみで `BOOTSTRAP_EXIT=1` への流し込み・末尾 exit 経路が欠落）→ T2026-0502-PHYSICAL-GUARD-AUDIT で実 exit 経路化（`if [ "$_git_pull_status" -ne 0 ]; then BOOTSTRAP_EXIT=1; fi` を pull/push 両方に追加）**
2. **物理（main 直 push 物理ブロック）**: `scripts/install_hooks.sh` に `pre-push` hook を追加し、`refs/heads/main` への push を exit 1 で拒否。bypass は `git push --no-verify`（WORKING.md に理由記録必須）。**実装: PR #160 → 不完全（pre-push hook の中身が `exit 0` placeholder のままインストールされていた）→ T2026-0502-PHYSICAL-GUARD-AUDIT で実 reject 化（`refs/heads/main` 判定 + `ALLOW_MAIN_PUSH=1` escape + `chore: bootstrap sync` 限定許可）**
3. **物理（滞留 commit の retroactive 救済）**: ローカル diverge 状態の commit は cowork_commit.py で salvage ブランチに退避 → PR 化して CI ・ auto-merge.yml の流れに乗せる。**実装: PR #158**
4. **観測（divergence SLI）**: bootstrap 実行ログを CloudWatch / Slack に流して、`git rev-list --count origin/main..HEAD` が 1 を超える状態が連続検出されたら ALERT。タスク化: **T2026-0502-DIVERGE-SLI**（観測）

**メタ教訓**:
- **「物理 / 観測 / 思想」の三分類を git 周辺にも適用する**: PR 側は重装備でも、ローカル → main の経路が「思想」だけになっていれば全体は「思想」と同じ強度。経路の最弱点が全体の強度を決める
- **`|| true` + `tail -N` の組み合わせは実質黙殺**: 終了コードを捨てる + 出力先頭を捨てる の二重で、エラーの観測手段が両方塞がれる。FUSE noise 除去のためにはフィルタリストで個別文字列を除く方が安全（substring 一致のみ・正規表現使わない、という現行 `_strip_fuse_noise` のポリシーを踏襲）
- **「✅ 完了」ログは実際に成功した条件下でのみ出す**: 「失敗してもセッション続行できるよう各ステップは `|| true` で吸収する」というコメントが冒頭にあったが、それと「最後に成功サマリを出す」は両立しない。失敗を吸収するなら成功サマリを出さない、成功サマリを出すなら失敗で exit するのが整合

**横展開チェックリスト**:
- [x] `scripts/session_bootstrap.sh` の git pull/push を `PIPESTATUS` で捕捉 → 失敗時 exit 1（**物理** / PR #159 で取得まで・**T2026-0502-PHYSICAL-GUARD-AUDIT で exit 経路を実装し完了**）
- [x] `scripts/install_hooks.sh` に pre-push hook 追加で main 直 push 物理ブロック（**物理** / PR #160 で hook 設置のみ・中身 `exit 0` placeholder のまま放置 → **T2026-0502-PHYSICAL-GUARD-AUDIT で実 reject ロジック実装し完了**）
- [x] 滞留 6 commit を salvage PR で retroactive に救済（**物理** / PR #158）
- [ ] `scripts/auto-push.sh` が main 直 push する設計を撤廃し、cowork_commit.py 経由 PR フローに置換（タスク化: **T2026-0502-AUTOPUSH-PR-FLOW**・**物理** / PR #175 進行中・PR #168 は scope 膨張で close）
- [x] 「auto-sync: session end ...」commit を生成する終了時 hook を特定して、main 直 commit を撤廃（タスク化: **T2026-0502-SESSION-END-HOOK-AUDIT**・**物理** / PR #173 — 犯人は `~/.claude/settings.json` の Stop hook）
- [x] divergence SLI（`git rev-list --count origin/main..HEAD ≥ 2` が 30 分続いたら Slack alert）（タスク化: **T2026-0502-DIVERGE-SLI**・**観測** / PR #171 / #172）
- [x] GitHub branch protection で main の direct push を server-side で拒否（PO 確認案件・タスク化: **T2026-0502-BRANCH-PROTECT**・**物理** / 2026-05-02 GitHub API 直接設定済 — required_status_checks.strict=true / enforce_admins=false / allow_force_pushes=false / allow_deletions=false）
- [x] `scripts/check_lessons_landings.sh` に PR #159 / #160 の物理ガード landing を追加（タスク化: **T2026-0502-LANDING-CHECK-M**・**物理** / PR #169 で grep 設置のみ → 「pre-push hook の文字列が install_hooks.sh に含まれる」だけを見ていたため placeholder でも pass する弱い grep だった → **T2026-0502-PHYSICAL-GUARD-AUDIT で `refs/heads/main` 判定 + `ALLOW_MAIN_PUSH` + `_git_*_status.*-ne 0` の3要素まで grep 強化**）
- [x] 同パターン横展開: 他のスクリプトでも `\|\| true` の後ろに `tail -N` が入っていないか grep audit（タスク化: **T2026-0502-PIPE-AUDIT**・**思想 → 物理化検討** / PR #170 — `scripts/audit_pipe_silence.sh` 新設 + 既存 grep audit 結果を `docs/audit-reports/pipe-audit-2026-05-02.md` に保存）

**緊急時 bypass の運用**:
- `git push --no-verify` で main 直 push 可能だが、bypass 使用時は WORKING.md に理由 + `Verified-Effect:` を必須記録
- `git commit --no-verify` も同じ運用（commit-msg hook bypass）
- bypass の頻度・理由を月次で監査し、bypass パターンが繰り返されているなら hook 側を修正

---

## T2026-0502-AUDIT: 同セッション内 ID 衝突 + workflow conclusion 誤解構造（2026-05-02 残務監査由来）

**起きたこと（事象 A: ID 衝突）**:
- 2026-05-02 中に T2026-0502-M / N / P がそれぞれ 2 回ずつ別の意味で採番された:
  - 旧 M (PR #158/#159/#160 = pre-push hook + bootstrap fix) ↔ 新 M (PR #152 = Tier-0 閾値)
  - 旧 N (PR #115 = AWS MCP rule) ↔ 新 N (PR #154 = suspectedMismerge action)
  - 旧 P (PR #134 = heredoc fix) ↔ 新 P (PR #156 = suspectedMismerge UI CTA)
- T2026-0502-MU が新規追加（PR #162）= M との半角 alias で混在助長
- 旧 M/N/P は完了済だが TASKS.md / HISTORY.md 未登録のまま新版が起票されたため、git log と HISTORY.md を見ても「どれが終わってどれが残っているか」が読めない構造
- 既存事例（旧 H が「shared-docs conflict guard」と「deploy-lambdas.yml fix」の 2 つに採番された 2026-05-02 朝）と同型

**起きたこと（事象 B: workflow conclusion 誤解）**:
- T2026-0502-Q / H 完了処理で「PR #141 で deploy 復旧 → run #372 success」と HISTORY.md に記録
- 実態: `deploy` job は success だが `post-deploy-verify (AI 充填率 + 鮮度): failure` が常態化 → workflow 全体 conclusion = failure
- `gh run list` や API の summary 列だけ見ると「直近 10 連続 failure」に見え、deploy が動いていないと誤認させる
- 同様に T2026-0502-V (lifecycle 反映確認) や T2026-0502-R (Haiku borderline 復活確認) で「run #372 で全 11 Lambda が新コードで反映」と書いた記述も、jobs レベルでは正しいが workflow conclusion レベルでは誤解を招く

**起きたこと（事象 C: deploy auto-fire 失敗）**:
- PR #141 (956072d) と PR #146 (53d2ddd2) は両方とも `lambda/**` 配下を変更し、deploy-lambdas.yml の path filter にマッチするはずなのに push event で auto-fire していない（workflow_dispatch のみで fire）
- 同セッション中の他の PR (#125, #118 等) では auto-fire していたので、path filter 自体は機能している
- 検証: GitHub API で head_sha=53d2ddd2 の workflow runs を取得すると `No inline logic in YAML` (paths filter なし) は fire しているが `Lambda デプロイ（全関数）` は 0 件
- 仮説 3 つで観察止まり: ①GitHub Actions 内部の path filter キャッシュ ②auto-merge.yml と squash merge のレースコンディション ③`concurrency.cancel-in-progress: false` 由来の queue 詰まり

**なぜなぜ**:

| Why | 答え |
|---|---|
| **Why1** なぜ ID 衝突が起きた？ | 別 dispatch / 別セッションが TASKS.md を見ずに自分で次の ID を採番したため。`scripts/next_task_id.sh` を呼ばず、または呼んだが「同日付の既存 M を見ていない」 |
| **Why2** なぜ workflow conclusion 誤解が起きた？ | summary level (workflow conclusion) と job level (個別 job conclusion) を区別せずに「success / failure」だけで判定する習慣。HISTORY.md は人間向けの単純化された記録形式で、conclusion=failure の workflow を「成功」と書くと矛盾する |
| **Why3** なぜ deploy auto-fire 失敗を検出できなかった？ | workflow conclusion 列だけ見て「workflow_dispatch で動いた」を「自動で動いた」と区別していない。run の `event` 列を見れば push か workflow_dispatch かは分かるが、SLI に組み込まれていない |
| **Why4** なぜ 3 つとも同日に起きた？ | フェーズ 2 移行直後で並列 dispatch が増加・人間 PO の「進捗を見せて」要求 + Cowork が複数タスクを同時に dispatch → ID 採番の集約点が無く各セッションが独立に動いた |
| **Why5** なぜ仕組み化されていない？ | TASKS.md / HISTORY.md が「単一の真実の源」ではなく、git log / WORKING.md / lessons-learned / TASKS.md / HISTORY.md の 5 ファイル間で人間が手動同期する構造。物理 sync スクリプト不在 |

**仕組み的対策**（物理ゲート 3 + 観測 1）:

1. **物理（next_task_id.sh の同日 ID 重複検出）**: `scripts/next_task_id.sh` 実行時に同日付 ID を `TASKS.md` + `HISTORY.md` + `git log --grep` で grep し、重複なら `T2026-MMDD-X1` のように suffix を付与する。**タスク化: T2026-0502-TASK-ID-COLLISION**
2. **物理（HISTORY.md 「workflow conclusion ≠ deploy success」明文化）**: HISTORY.md に「workflow run 番号を Verified-Effect に書く際、必ず job レベルの conclusion を併記する。`run #N: workflow=failure / deploy=success / post-deploy-verify=failure` 形式」のテンプレートを `docs/rules/quality-process.md` に追記し、`scripts/check_history_format.sh` で workflow run 言及の行に対して `deploy=` `post-deploy-verify=` のラベル必須化。**タスク化: T2026-0502-HISTORY-WORKFLOW-FORMAT**
3. **物理（deploy auto-fire SLI）**: schedule task `p003-haiku` に「直近 24h で `event=push` の deploy-lambdas runs 数 / `lambda/**` を含む main commits 数 ≥ 0.8」を追加。0.5 を下回ったら Slack alert。GitHub Actions の auto-fire 異常を観測する。**タスク化: T2026-0502-DEPLOY-AUTOFIRE-SLI**
4. **観測（PR merge → deploy run 突合監査）**: 過去 30 日 `gh pr list --state merged` から `lambda/**` 変更を含む PR を抽出し、merge sha で deploy run を検索 → 0 件の PR を遡及検出。月 1 回 schedule で実行。**タスク化: T2026-0502-DEPLOY-AUTOFIRE-AUDIT**

**メタ教訓**:
- **「同日付 ID 衝突」はセッション並走で必ず起きる**。グローバル一意化を機械的に強制しない限り再発する
- **workflow run の `conclusion` は job レベルの集約**。個別 job の成功/失敗を確認せずに「workflow=success」と書くと、後の人間が誤解する。job level のラベルを必須化するのが最短
- **「auto-fire していない」は workflow run の `event` を見ないと分からない**。直近 conclusion=failure 連発を見て「deploy 壊れている」と判定すると、本当は「deploy job は success / verify が落ちているだけ」を見落とす逆パターンも起きる
- **HISTORY.md は単純化された人間向け記録だが、根拠データへのリンク（workflow run URL / job URL）は必ず残す**。後で audit する際に再構築できる粒度を保つ

**横展開チェックリスト**:
- [ ] `scripts/next_task_id.sh` に同日 ID 重複検出（**物理** / タスク化: T2026-0502-TASK-ID-COLLISION）
- [ ] `docs/rules/quality-process.md` に workflow run 言及の job-label テンプレ追記 + `scripts/check_history_format.sh` 新設（**物理** / タスク化: T2026-0502-HISTORY-WORKFLOW-FORMAT）
- [ ] `p003-haiku` schedule task に deploy auto-fire SLI 追加（**観測** / タスク化: T2026-0502-DEPLOY-AUTOFIRE-SLI）
- [ ] PR merge × deploy run 突合監査の月次 schedule（**観測** / タスク化: T2026-0502-DEPLOY-AUTOFIRE-AUDIT）
- [ ] `post-deploy-verify` job 失敗常態化の根本対処（AI 充填率 / 鮮度の閾値ロジック見直し or workflow 構造変更）（**物理** / タスク化: T2026-0502-POST-DEPLOY-VERIFY-FIX）

---

## T2026-0502-SESSION-END-HOOK-AUDIT: Stop hook による main 直 commit 汚染（2026-05-02）

**発生事象**: `~/.claude/settings.json` に設定された `Stop` hook がすべての Claude セッション終了時に `git add -A && git commit -m "auto-sync: session end ..." && git push` を main へ直接実行。全期間で 476+ 件の汚染コミットが発生。

**影響範囲**:
- git history に 476+ 件の `auto-sync: session end` コミット（commit-msg hook / Verified 行要件をすべて迂回）
- T2026-0502-M で設置された pre-push hook が push をブロックするが `2>/dev/null || true` で無音失敗 → ローカルに commit が積み上がり diverge を継続生成

**なぜなぜ**:

| Why | 答え |
|---|---|
| **Why1** なぜ auto-sync コミットが発生した？ | `~/.claude/settings.json` の `Stop` hook が全セッション終了時に `git add -A && git commit && git push main` を実行していたため |
| **Why2** なぜ Stop hook がそこにあった？ | セッション間のデータ消失を防ぐ「安全装置」として過去のセッションで設置されたが、PR フロー義務化後も削除されなかったため |
| **Why3** なぜ pre-push hook でブロックできなかった？ | pre-push hook はブロックするが、Stop hook コマンドが `2>/dev/null || true` で stderr を捨てているため push 失敗が無音で流れ、ローカル commit だけ蓄積された |
| **Why4** なぜ発見が遅れた？ | `git grep "auto-sync: session end"` でリポジトリ内ファイルを検索しても見つからない。設定ファイルは `~/.claude/settings.json`（ホームディレクトリ）にあり、リポジトリ外 |
| **Why5** なぜ仕組みとして防げなかった？ | Claude Code の Stop hook 設定はリポジトリ外（~/.claude/）にあるため CI やリポジトリ側のガードが届かない。唯一の防衛線は pre-push hook だが、`|| true` で迂回された |

**仕組み的対策**:

1. **物理（Stop hook 削除）**: `~/.claude/settings.json` から `Stop` hook を完全削除。セッション間同期は `session_bootstrap.sh` の起動時 `chore: bootstrap sync` コミットで代替（すでに機能している）。**本タスクで実施済み。landing: ~/.claude/settings.json**
2. **物理（pre-push hook の `|| true` 迂回防止）**: Stop hook 由来のコマンドは `|| true` を付けて push 失敗を握り潰す設計が多い。pre-push hook を `HUSKY_SKIP_HOOKS` や `--no-verify` なしでは迂回不可にする構造は維持する（既存）。
3. **思想（~/.claude/settings.json の定期監査）**: 月 1 回、Stop/PreToolUse hook の内容を目視確認し、`git push` 直接実行がないことを確認する。`p003-haiku` の月次 schedule に追加候補。

**メタ教訓**:
- **Claude Code の hook はリポジトリ外に設定される** → CI がアクセスできず物理ガードが届かない死角
- **`2>/dev/null || true` で包んだ git push は push 失敗を無音で飲み込む** → diverge が静かに進行する
- **「リポジトリ内を grep しても見つからない」が hook の典型的症状** → 次回調査時は `~/.claude/settings.json` を最初に確認

**横展開チェックリスト**:
- [x] `~/.claude/settings.json` の Stop hook 削除（**物理** / 本タスクで実施済み / landing: ~/.claude/settings.json）
- [ ] `p003-haiku` 月次 schedule に `~/.claude/settings.json` hook 監査を追加（**思想** / タスク化: T2026-0502-HOOK-AUDIT-MONTHLY）

---

## T2026-0502-S: SES 通知 silent print で IAM AccessDenied 1 ヶ月見落とし（2026-05-02）

**起きたこと**:
- 2026-04-26 13:13 JST に `p003-contact` Lambda が `ses:SendEmail` で AccessDenied
- 原因: `p003-ses-send-policy` の `Resource` に `flotopic.com` だけがあり `<owner-email>` (= ADMIN_EMAIL identity) が欠落していた
- お問い合わせ自体は DynamoDB に保存されるためフォーム送信は 200 を返し続け、メール通知だけが届かない状態が継続
- handler.py 側の catch が `print(f'SES通知スキップ: {e}')` で **silent fail**（CloudWatch Logs を grep しないと気づけない）
- 2026-05-02 PO 確認指示で初めて検出。policy はその後の何処かで両 identity を含むよう修正済 (`p003-ses-send-policy` 現行は OK)
- 修正後の本番テスト送信 (sesv2 SendEmail / MessageId=`0100019de6b046ad-...`) で動作確認済

**なぜなぜ**:

| Why | 答え |
|---|---|
| **Why1** なぜ AccessDenied が起きた？ | IAM policy の Resource 配列に ADMIN_EMAIL identity ARN が欠けていた。FROM 用 identity (flotopic.com) しか足していなかった |
| **Why2** なぜレビューで気づかなかった？ | 「SendEmail の Resource は Source identity だけで足りる」誤解（実際は SES が Destination 側の identity も Resource として解決するケースがある・特に sandbox 抜け前後の挙動）|
| **Why3** なぜ運用中に気づかなかった？ | handler.py の catch が `print(f'SES通知スキップ:')` で警告レベル区別なし。CloudWatch Logs metric filter も無く、SLI に紐付かない。失敗が「成功したフォーム送信」の隣に静かに積まれていた |
| **Why4** なぜ気づける仕組みが無かった？ | freshness-check 系 SLI は記事処理の充填率に集中し、お問い合わせ系 Lambda の異常を観測する層が存在しない。security-audit.yml の `audit_aws()` も IAM policy を Resource='*' で grep するだけで「想定 identity を網羅しているか」は見ない |
| **Why5** なぜ同 anti-pattern が他にも潜んでいる？ | SES だけでなく DynamoDB / S3 / SQS も Resource ARN ホワイトリスト型 IAM が複数箇所に散在。policy の identity drift を観測する CI が無い |

**仕組み的対策**（物理ゲート 2 + 観測 1 + 思想 1）:

1. **物理（SES エラーログを ERROR プレフィックスで識別可能化）**: `lambda/contact/handler.py` の SES catch 2 箇所を `print('SES通知スキップ: ...')` → `print('[ERROR] SES send (notification) failed: ...')` / `print('[ERROR] SES send (draft) failed: ...')` に統一。**本タスクで実施済 / landing: lambda/contact/handler.py L230, L319 付近**
2. **物理（IAM policy identity drift CI）**: `scripts/security_audit.sh` の `audit_aws()` に Section F を追加し、`p003-ses-send-policy` の Resource に想定 identity (`flotopic.com` / `<owner-email>`) が両方含まれるか + SES Production Access + flotopic.com Verified 状態を週次監査。**本タスクで実施済 / landing: scripts/security_audit.sh F1〜F3**
3. **観測（CloudWatch Logs metric filter）**: `[ERROR] SES send` を含むログ行を CloudWatch metrics にカウントし、`p003-haiku` 朝 7:08 の Lambda エラー確認項目に「過去 24h で `[ERROR] SES send` 件数 > 0」を追加。タスク化候補: **T2026-0502-SES-METRIC-FILTER**（観測・無料）
4. **思想（IAM policy 編集時の identity 網羅レビュー）**: SES / DynamoDB / SQS など Resource ホワイトリスト型 IAM policy を変更する PR では、handler の `Source` / `ToAddresses` / `TableName` を grep して全 identity が Resource に含まれることを self-check。`docs/rules/quality-process.md` に追記候補

**メタ教訓**:
- **silent print catch は SLI を持たないと 1 ヶ月単位で気付かれない**。エラー検知は「ログレベル昇格 + metric filter + SLI/cron」の三段構えが最低ライン
- **IAM policy の Resource ホワイトリストは「片方しか足してない」が typical bug**。CI で「想定 identity 配列との突合」を物理化しないと再発する
- **SES の Resource ARN 解決は Source identity だけで足りるとは限らない**。SES API のバージョン (v1/v2) や sandbox 状態で挙動が変わるため、両方 (FROM/TO 双方) の identity ARN を policy に書くのが安全側
- **「お問い合わせは届いているがメール通知だけ来ない」は症状が静か**。フォームは 200 を返し DynamoDB には保存される → 利用者には何も見えず、運営側の気付きも遅れる

**横展開チェックリスト**:
- [x] `lambda/contact/handler.py` の SES catch 2 箇所を `[ERROR]` プレフィックス昇格（**物理** / 本タスクで実施済 / landing: lambda/contact/handler.py）
- [x] `scripts/security_audit.sh` Section F (SES policy / Production / Verified 監査) 追加（**物理** / 本タスクで実施済 / landing: scripts/security_audit.sh）
- [ ] CloudWatch Logs metric filter `[ERROR] SES send` を `p003-haiku` 監視に追加（**観測** / タスク化: T2026-0502-SES-METRIC-FILTER）
- [ ] 他 Resource ホワイトリスト IAM policy (DynamoDB / SQS) も同形式で identity 突合 CI に拡張（**物理** / タスク化: T2026-0502-IAM-RESOURCE-AUDIT）

---

## T2026-0502-DEPLOY-WATCHDOG: PR merge 後 deploy auto-trigger 無音失敗（2026-05-02）

**起きたこと**:
- PR #152/#154/#156/#162 が main に merge されたが、deploy-lambdas.yml の push event auto-trigger が機能しておらず本番反映ゼロが長期継続
- 直近 5 deploy run がすべて workflow_dispatch（手動）で、push event 由来がゼロ
- 誰も気付かないまま「PR merge = 本番反映」を暗黙の前提として運用していた

**なぜなぜ**:

| Why | 答え |
|---|---|
| **Why1** なぜ push event が発火しなかった？ | deploy-lambdas.yml の `paths:` filter が変更ファイルにマッチしなかった可能性（真因は T2026-0502-PATH-FILTER-AUDIT で調査）。CI は通っており merge 自体は正常に完了 |
| **Why2** なぜ長期間気付かなかった？ | 「PR merge 後 N 分以内に Lambda が更新されたか」を自動確認する仕組みが存在しなかった。deploy-lambdas.yml の run 一覧を毎回手動確認する習慣もない |
| **Why3** なぜ 「merge = 完了」運用を疑わなかった？ | done.sh が PR merged + deploy-success の両方をゲートにしておらず、merged のみで完了扱いになっていた |
| **Why4** なぜ deploy run failure/absent を観測する仕組みがなかった？ | SLI は Lambda の Lambda error rate / freshness を見ているが、「deploy workflow が走ったかどうか」自体を確認するレイヤーが欠落していた |
| **Why5** なぜ同じ問題が再発するリスクがある？ | GitHub Actions の push event は paths filter / branch filter / 内部イベント制限など無音失敗ポイントが多く、CI/CD pipeline 自体を外部から観測するレイヤーが必要 |

**仕組み的対策**（物理ゲート 2 + 観測 2）:

1. **物理（deploy-trigger-watchdog workflow）**: PR merge 後 5min 以内に Lambda lastModified が更新されているか poll し、されていなければ deploy-lambdas.yml を自動発火 + Slack 通知 + GitHub Issue 起票。`.github/workflows/deploy-trigger-watchdog.yml` 新規作成。**本タスクで実施済 / landing: .github/workflows/deploy-trigger-watchdog.yml**
2. **物理（lambda-freshness-monitor workflow）**: 毎時 0 分に Lambda lastModified と直近 lambda commit の乖離を確認し 30min 超で Slack 通知。`.github/workflows/lambda-freshness-monitor.yml` 新規作成。**本タスクで実施済 / landing: .github/workflows/lambda-freshness-monitor.yml**
3. **観測（check_lambda_freshness.sh 単体スクリプト）**: `scripts/check_lambda_freshness.sh` を独立スクリプトとして提供。手動確認・CI 両用可能。30min 超で exit 1 + 警告。**本タスクで実施済 / landing: scripts/check_lambda_freshness.sh**
4. **物理（bash unit test）**: `tests/test_lambda_freshness.sh` で 0min / 29min / 31min / 120min / AWS error / no-commit の 6 境界ケースを網羅。**本タスクで実施済 / landing: tests/test_lambda_freshness.sh**

**メタ教訓**:
- **「CI/CD pipeline 自体の SLI」がないと、merged だが未反映の事故が静かに進行する**。Lambda error rate SLI だけでは deploy lag は検知できない
- **GitHub Actions の push event trigger は無音失敗が多い**。paths filter / branch filter / internal event routing など、いずれかで詰まっても CI は通り merge は成功する
- **「PR merge = 完了」は done.sh + deploy-success の両方でゲートしないと形骸化する**

**横展開チェックリスト**:
- [x] `.github/workflows/deploy-trigger-watchdog.yml` 新規作成（**物理** / 本タスクで実施済 / landing: .github/workflows/deploy-trigger-watchdog.yml）
- [x] `.github/workflows/lambda-freshness-monitor.yml` 新規作成（**物理** / 本タスクで実施済 / landing: .github/workflows/lambda-freshness-monitor.yml）
- [x] `scripts/check_lambda_freshness.sh` 新規作成（**物理** / 本タスクで実施済 / landing: scripts/check_lambda_freshness.sh）
- [x] `tests/test_lambda_freshness.sh` 新規作成（**物理** / 本タスクで実施済 / landing: tests/test_lambda_freshness.sh）
- [ ] `done.sh` に Lambda 変更 PR の deploy-success ゲート追加（**物理** / タスク化: T2026-0502-DONE-GATE）
- [ ] deploy-lambdas.yml の push event trigger が機能しない根本原因調査（**物理** / タスク化: T2026-0502-PATH-FILTER-AUDIT）

---

## 2026-05-02 Lambda 例外ハンドラのサイレントキャッチが5xx 真因を隠蔽 (T2026-0502-T)

**事象**: `GET /favorites/{userId}` で 5xx 2件。API Gateway アクセスログで `integrationStatus=200`（Lambda 正常完了）なのに `status=500`。Lambda Errors メトリクス = 0。CloudWatch Lambda ログに ERROR 出力なし。

**Why1**: `except Exception as e: return resp(500, ...)` に `print()` がなかった。
**Why2**: エラーハンドラは「何かあったら 500 返す」として実装されたが、ログ出力を省略していた。
**Why3**: ローカルテストではパスが網羅されず、例外パスのログ漏れに気づかなかった。
**Why4**: `integrationStatus=200` の意味を「Lambda が 200 を返した」と誤解しやすく、Lambda 内部 500 との区別に気づくまでに時間がかかった（正確には「Lambda 呼び出し成功 = integrationStatus=200」）。
**Why5**: 新しい例外ハンドラを追加する際にログ出力の有無を CI でチェックする仕組みがなかった。

**仕組み的対策**:
1. **`_make_response()` SSoT + 全例外ハンドラへの `print('[ERROR]...')` 追加** (本 PR T2026-0502-T): favorites/auth/processor の 500 パスに全て追加。
2. **Boundary tests 追加** (本 PR): `test_favorites_handler.py` で空リスト/大量データ/Decimal/None/未来日付/例外キャッチでのログ出力を全 assert。
3. **CI lint ガード追加候補**: `handler.py` 内の `except Exception` ブロックで `print` または `logging` がない箇所を検出して WARN / ERROR (タスク化: T2026-0502-LAMBDA-RESPONSE-LINT)。

**横展開チェックリスト**:

| 確認項目 | 対象ファイル | 状態 |
|---|---|---|
| 例外ハンドラにログ追加 | `lambda/favorites/handler.py` | ✅ 本 PR で全 500 パスに `[ERROR]` print 追加 |
| 例外ハンドラにログ追加 | `lambda/auth/handler.py:210` | ✅ 本 PR で `[ERROR]` print 追加 |
| 例外ハンドラにログ追加 | `lambda/processor/handler.py:195` | ✅ 本 PR で `[ERROR]` print 追加 |
| 他 Lambda の audit 完了 | analytics/api/bluesky/cf-analytics/comments/contact/fetcher/lifecycle/tracker | ✅ audit 実施 → 全て既存ログあり (OK) |

---

## T2026-0502-T-COWORK-RECURRENCE: Cowork 自身による「2 度目の仮説確定」事故 — raw logs 観察を skip した（2026-05-02）

**起きたこと**:
- 同日午前に PR #167 で landing した「CI/Workflow 失敗を観測しないまま仮説で動いた」事故 (T2026-0502-Q 由来) と **完全に同じパターン**を、Cowork 自身が再発させた
- T2026-0502-T (API Gateway 5xx) で Cowork が AWS MCP で先取り観察:
  - access logs: integrationStatus=200 / integrationLatency=960ms / integrationErrorMessage="-"
  - Integration 設定: Lambda=`flotopic-favorites` / PayloadFormatVersion=2.0 / AWS_PROXY
- Cowork はこの観察と PayloadFormatVersion 2.0 仕様の一般知識を組み合わせ、「**仮説 (c) Lambda response payload 不整合確定**」と判定して Code セッション dispatch のプロンプトに「**他 4 つの仮説 a/b/d/e は除外済 → c のみ残った**」と書いた
- Code セッション (Sonnet) が実際に Lambda コードと CloudWatch Logs を読みに行ったところ、真因は別だった (PR #186 description より):
  - response format は **既に PayloadFormatVersion 2.0 準拠**
  - 真因: `except Exception as e: return resp(500, ...)` に **`print()` がなく、例外がサイレントキャッチされて CloudWatch に証跡なし**
  - 5xx 2 件はコールドスタート時の DynamoDB 初回接続一時エラーが最有力（証跡無で推定）
- Cowork の仮説 (c) は外れ。「Lambda が意図的に 500 を return している」が正解だった

**なぜなぜ**:

| Why | 答え |
|---|---|
| **Why1** なぜ仮説外しが起きた？ | Cowork が access logs だけ見て「仮説確定」と書いた。Lambda 内部 logs を実際には取得していない |
| **Why2** なぜ Lambda 内部 logs を取らなかった？ | 「Lambda コード読みは Code セッションの仕事」と役割分担し、Cowork は AWS MCP の access logs と Integration 設定の一般仕様だけで推論を完結させた |
| **Why3** なぜ「役割分担」が「観察 skip」につながった？ | Cowork は「観察 → 仮説候補抽出」までが仕事という区切りを置いていたが、**観察手段で仮説を 1 個ずつ潰すルール (quality-process.md / lessons-learned T2026-0502-Q) は「コード読み」だけでなく「raw logs 確認」も含む**。これを Cowork 自身に適用していなかった |
| **Why4** なぜ同日 PR #167 で書いた直後の lessons-learned を自分で破った？ | 「仮説 3 つ以上挙げる」ルールは守ったが、「**観察手段で 1 個ずつ潰す**」ルールを Cowork は **「Code セッションがやる」もの** と暗黙に切り分けた。プロンプトに「a/b/d/e は除外済」と書いた時点で「c の検証は Code がやる」と委譲しているつもりだったが、PO 視点では「Cowork が確定した」と読める表現だった |
| **Why5** なぜ表現として「仮説確定」を使ってしまう？ | 「Cowork 観察の最終形」を書きたい欲求と、「未確定の候補のまま渡す」という規律の衝突。「整合化」「修正」のような断定的な動詞をプロンプト title に書くと、Code セッションが書かれた仮説で実装に入る誘発がある |

**仕組み的対策**（最低 3 つ・物理ゲート 3 + 観測 1）:

1. **物理（dispatch prompt の「仮説確定」禁止語 grep）**: `scripts/gen_dispatch_prompt.sh` または PR テンプレに「**仮説確定 / 真因確定 / のみ残った / 整合化**」を含む dispatch prompt を grep で reject。Cowork は「**Cowork 観察済の事実**」と「**未確定の候補仮説**」のみ提示する形式に強制。**タスク化: T2026-0502-DISPATCH-HYPOTHESIS-GUARD**
2. **物理（dispatch prompt に raw logs 証跡 URL required）**: `scripts/gen_dispatch_prompt.sh --observation-evidence <log_event_id or filter_log_events_command>` を required 引数化（既存 lessons-learned T2026-0502-DISPATCH-REQ と統合）。Cowork は raw logs を実行した証跡を必ずプロンプトに書く必要がある。**タスク化: T2026-0502-DISPATCH-RAW-LOG-REQ**
3. **物理（Cowork 観察フェーズに Lambda 内部 logs 必須化）**: `docs/rules/cowork-aws-policy.md` に「API Gateway 5xx / Lambda Errors 起因の障害調査では、Cowork は必ず ① access logs / metrics の取得 ② **対応する Lambda の `/aws/lambda/<fn>` log group を該当 requestId / 時刻で filter-log-events 実行** ③ 結果 (空 / 例外 / 正常 return) を観察として記録 を実行してから dispatch prompt を出す」を明記。**タスク化: T2026-0502-COWORK-LAMBDA-LOG-RULE**
4. **観測（dispatch prompt 仮説外し率 SLI）**: 直近 30 日の dispatch prompt と PR description の真因記述を比較し、「Cowork 仮説 ≠ Code 真因」の発生率を月次レポート。3 件/月 を超えたら Cowork 観察フローを再点検。**タスク化: T2026-0502-HYPOTHESIS-MISS-SLI**

**メタ教訓**:
- **「仮説 3 つ以上挙げる」だけでは不十分**。観察手段で 1 個ずつ潰すまでが「観察」。Cowork は「a/b/d/e は除外」と書いたが、c も観察手段で確認すべきだった
- **Cowork の役割分担「観察まで」は「Lambda コード読みは含まない」だが「Lambda 内部 logs 確認は含む」**。CloudWatch Logs はコード読みではなく観察手段。これを区別する
- **「仮説確定」「真因確定」「のみ残った」「整合化」のような断定的な語は、それを書いた人の確信度以上に Code セッションを動かす**。プロンプトの語彙が dispatch の振る舞いを決める
- **同日中に同じ事故を 2 度繰り返した**（朝の T2026-0502-Q + 昼の T2026-0502-T）。lessons-learned に書いただけでは形骸化する典型 → 物理ガード必須

**横展開チェックリスト**:
- [ ] `scripts/gen_dispatch_prompt.sh` に「仮説確定 / 真因確定 / のみ残った / 整合化」grep reject 追加（**物理** / タスク化: T2026-0502-DISPATCH-HYPOTHESIS-GUARD）
- [ ] `scripts/gen_dispatch_prompt.sh --observation-evidence` required 引数化（**物理** / 既存 T2026-0502-DISPATCH-REQ と統合）
- [ ] `docs/rules/cowork-aws-policy.md` に「Lambda 関連障害調査は Lambda 内部 logs 必須」明記（**物理** / タスク化: T2026-0502-COWORK-LAMBDA-LOG-RULE）
- [ ] 直近 30 日の dispatch prompt × PR 真因の仮説外し率 SLI（**観測** / タスク化: T2026-0502-HYPOTHESIS-MISS-SLI）

---

## T2026-0502-SEC-AUDIT セキュリティ監査全体総括 なぜなぜ（2026-05-02 制定）

**事象**: Cowork PO 依頼で実施した網羅セキュリティ監査で、**Critical 5 件 + High 3 件 + Medium 7 件 + Low 3 件** の脆弱性が累積していたことが判明。代表例:
- 公開 GitHub repo の `projects/P004-slack-bot/README.md` に live GitHub PAT が **commit 7ce172a2 (2026-04-22) 以降ずっと公開** されたまま放置
- git history 内に追加で **GitHub PAT × 1, Slack Bot Token, Slack Webhook** が露出
- gitignore 済の `fetch_notion.py` / `setup_api_key.sh` に **Notion token / Anthropic API key** が平文で滞留 (Cowork チャット表示経由の漏洩リスク)
- `lambda/comments/handler.py` の **avatar upload URL / like-dislike が Google ID トークン未検証** (IDOR・avatar 上書き・なりすまし投票が可能)
- `lambda/favorites/handler.py` / `analytics/handler.py` の **GET /favorites|history|analytics/user/{userId} が認証なし** で他人の閲覧履歴・行動傾向を読める (PII 露出)
- `lambda/fetcher/handler.py` の **xml.etree.ElementTree** が billion laughs 攻撃に脆弱、外部 fetch URL が **internal IP / 169.254.169.254 metadata endpoint を deny していない** (SSRF)
- frontend `<a href="${esc(a.url)}">` で **`javascript:` URI 未 block** (RSS 経由 clicked XSS 可能性)
- CSP が `default-src 'self' https: 'unsafe-inline' 'unsafe-eval'` で実質防御ゼロ
- 複数 Lambda の CORS が `*`、Lambda concurrency 制限が一部のみ、500 で内部例外 message を返す情報露出

**なぜなぜ**:

| Why | 答え |
|---|---|
| **Why1** なぜ live PAT が public repo に commit され続けた？ | P004-slack-bot/README.md にデプロイ手順として token を直書きし、その後 PR review でも CI でも検出されなかった |
| **Why2** なぜ CI で検出されなかった？ | 既存の `.github/workflows/ci.yml` の secret grep は `sk-ant-` / `AKIA` のみ対象で、`ghp_*` / `gho_*` / `xoxb-*` / `ntn_*` / Slack Webhook URL を含んでいなかった。`scripts/security_audit.sh` も範囲が同等 |
| **Why3** なぜ pattern が部分的だった？ | T251 / T2026-0428-Z で security_audit.sh を導入した時点では当時直近で問題視されていた Anthropic key + AWS key だけ対処した。後で GitHub PAT / Slack token も増えたが、scanner pattern を更新する横展開ルールが無かった |
| **Why4** なぜ avatar / like / IDOR の認証欠落が PR 通過した？ | 「読み取り系 GET は認証不要」という暗黙ルールで実装された (history/favorites/prefs/analytics は他人の userId が分かれば閲覧可能。実害には userId 露出が必要だが、防御線は破られている)。PR review で「これ認証要らないの？」と指摘する仕組み (テストとか、checklist) が無かった |
| **Why5** なぜ defense in depth (CSP / SSRF / XXE / CORS) が薄かった？ | プロダクト最適化フェーズ (フェーズ2 keyPoint 充填率改善) に集中し、セキュリティはタスク化されていなかった。脆弱性が顕在化する事故が起きない限りは「動いてるし急がない」と後回しになる構造 |

**仕組み的対策** (最低 3 つ・**物理 6 + 観測 1 + 思想 2**):

1. **物理 (network secret detection)**: `.github/workflows/secret-scan.yml` 追加。pre-commit hook + CI push event + PR + 週次 schedule で `secret_scan.sh` を発火。pattern は ghp_/gho_/ghs_/ghr_/github_pat_/xoxb-/xoxp-/xapp-/sk-ant-api03-/sk-proj-/ntn_/secret_/AKIA + Slack Webhook URL + URL embedded creds を網羅 (T2026-0502-SEC-AUDIT-PROTECT-1) ✅ 実装済
2. **物理 (pre-commit secret reject)**: `scripts/install_hooks.sh` の pre-commit に `secret_scan.sh staged` 追加。staged diff に live secret が混入したら commit 段階で reject。bypass は `git commit --no-verify` のみで WORKING.md に記録必須 (T2026-0502-SEC-AUDIT-PROTECT-2) ✅ 実装済
3. **物理 (frontend XSS hardening)**: `safeHref(url)` ヘルパを `frontend/app.js` + `frontend/js/utils.js` に追加し、`<a href="${esc(safeHref(...))}">` パターンに統一。`javascript:` `data:` `vbscript:` 等 dangerous scheme を `#` に潰す (T2026-0502-SEC11) ✅ 実装済
4. **物理 (SSRF + XXE 防御)**: `lambda/fetcher/url_safety.py` + `lambda/processor/url_safety.py` 追加。`is_safe_url(url)` で internal IP (169.254.169.254 / RFC1918 / loopback) deny、`parse_xml_safely(content)` で DOCTYPE/ENTITY を検出して reject (defusedxml-equivalent。Lambda zip 制約で外部依存なし) (T2026-0502-SEC13/SEC14) ✅ 実装済
5. **物理 (auth required at handler level)**: 全 Lambda の `userId` path/query を受け取る handler に `Authorization: Bearer <Google ID token>` 必須化。`payload.sub != path.userId` で 403。avatar upload URL / like / favorites GET / history GET / prefs GET / analytics user GET 全て (T2026-0502-SEC5/SEC6/SEC7) ✅ 実装済
6. **物理 (rate-limit fail-closed)**: 重要書き込み (comments POST / contact POST) の `check_rate_limit` を `fail_closed=True` に。DDB エラー時に通さなくする。CloudWatch metric filter で `[SEC15]` を観測対象に追加して頻発を検知 (T2026-0502-SEC15) ✅ 実装済
7. **観測 (security checklist via PR template)**: `docs/rules/security-checklist.md` を新設。PR テンプレートに「✅ secret_scan green / ✅ 新規 handler は認証チェックあり / ✅ `<a href>` に safeHref / ✅ urllib.urlopen に is_safe_url / ✅ ET.fromstring に parse_xml_safely」を反映 (PR review で漏れない) (T2026-0502-SEC-AUDIT-PROTECT-3)
8. **思想 (新規外部システム統合の3ステップに secret 管理を追加)**: CLAUDE.md「新規外部システム統合の3ステップ」に「token は env / Secrets Manager のみ。コード/ドキュメントに直書き禁止 (テストでもダミーのみ)」を明記
9. **思想 (defense in depth review)**: 各 PR の review で「この変更で攻撃面が広がっていないか？」を 1 行コメントで確認する習慣 (CSP / CORS / 認証 / 入力検証)

**メタ教訓**:
- **「動いてる」と「安全」は別軸**。プロダクト機能 100% green でも CSP が `unsafe-inline` のままだと 1 件の XSS で全部破られる
- **secret scanner pattern は「最初に発生した事故」だけでカバーしがち**。発生した secret 種別だけでなく、世の中で利用されている全 token 種別を pattern に入れる (`docs/rules/security-checklist.md` に list 化して横展開)
- **「公開 repo に live token を commit」はチェック忘れ・コピペ事故・一時的検証など多くのルートで発生する**。git push 直前の自動 scan + push 後の history scan の 2 段で物理ガードする
- **認証は「最後に書く機能」になりやすい**。GET 系は read-only だから後でいいや → 後で書かれない。新規 handler を書く時のテンプレに認証チェック行を最初から入れる
- **同じファイルに live secret を書いて gitignore する** は CI を通さないだけで Cowork チャット履歴・スクリーン共有・session_info MCP 経由で漏洩する。env / Secrets Manager に最初から逃がす

**横展開チェックリスト**:
- [x] `.github/workflows/secret-scan.yml` 新規 (push + PR + 週次・full history scan) (**物理** / 本セッション PR で landing 予定)
- [x] `scripts/secret_scan.sh` (staged / head / full モード) + allowlist 仕組み (**物理** / 本セッション PR で landing 予定)
- [x] `scripts/install_hooks.sh` の pre-commit に secret_scan.sh staged 統合 (**物理** / 本セッション PR で landing 予定)
- [x] `lambda/fetcher/url_safety.py` + `lambda/processor/url_safety.py` (SSRF / XXE 防御ヘルパ) (**物理** / 本セッション PR で landing 予定)
- [x] `frontend/app.js` + `frontend/js/utils.js` に `safeHref` (**物理** / 本セッション PR で landing 予定)
- [x] `lambda/comments/handler.py` avatar / like 認証必須 (**物理** / 本セッション PR で landing 予定)
- [x] `lambda/favorites/handler.py` GET 系 + `lambda/analytics/handler.py` /user/{userId} 認証必須 (**物理** / 本セッション PR で landing 予定)
- [x] `lambda/comments|contact/handler.py` の rate-limit を fail_closed=True に (**物理** / 本セッション PR で landing 予定)
- [x] 全 Lambda の CORS を `*` から自社ドメインに統一 (**物理** / 本セッション PR で landing 予定・comments/favorites/tracker/api/analytics 完了)
- [x] `lambda/auth/handler.py` + favorites/tracker から `'detail': str(e)` を削除 (**物理** / 本セッション PR で landing 予定)
- [x] deploy.sh に fetcher/processor/lifecycle/contact/tracker の concurrency 制限追加 (**物理** / 本セッション PR で landing 予定)
- [ ] `docs/rules/security-checklist.md` 新設 + PR テンプレ反映 (**観測** / 本セッション PR で landing 予定)
- [ ] CSP `unsafe-inline` / `unsafe-eval` 削除 + CloudFront Response Headers Policy で whitelist (**物理** / SEC12 で別途実装・既存 T267 と統合)
- [ ] `lambda/comments/handler.py` の userHash 仕様廃止後、frontend/js/comments.js の呼び出しを idToken 同梱形式に更新 (**物理** / 別途 frontend PR)
- [ ] AWS Secrets Manager 移行 (Lambda env から ANTHROPIC_API_KEY 除去) (**物理** / SEC9 で別途実装・PO 操作必要)
- [ ] GitHub Actions 認証を OIDC + IAM Role assumption に移行 (**物理** / SEC10 で別途実装・PO 操作必要)
- [ ] 旧 secret 4 件 rotate (gho/ghp x2/xoxb/Slack Webhook x2/Notion/Anthropic) (**思想** / SEC1-4 / PO 操作必要)
- [ ] git history rewrite (`git filter-repo --replace-text` で 4 secret を消す + force-push) (**思想** / SEC3 / PO 操作必要)

---

## T2026-0502-COST-DISCIPLINE — 効果検証 polling / workflow 連投で課金浪費（2026-05-02 制定）

**事象**: T2026-0502-SEC-AUDIT で 6 PR が無事 merge → Cowork が効果検証で deploy-lambdas.yml を **3 回 workflow_dispatch + AWS list-functions/get-function-configuration を計 8 回 polling**。3 回ともfetcher step で失敗するも、Cowork は「もう 1 回試せば」と再 trigger を続け、ログが sandbox で fetch できないため診断もせず無駄叩き。PO から「確認するために何度もお金使わないでね」とフィードバック。

**なぜなぜ**:

| Why | 答え |
|---|---|
| **Why1** なぜ workflow_dispatch を 3 回叩いた？ | 1 回目が短時間 (5sec) で failed → 「これは transient かも」と直感で再試行 → 2 回目も失敗 → 3 回目で原因特定するつもりだった |
| **Why2** なぜ「transient かも」と判断した？ | 失敗の根本原因 (fetcher step が 5sec で死ぬ) を診断する前に、再試行コストを軽く見積もった (workflow 1 回 = 数 GHA minutes + AWS API 数十回 + Cowork tokens) |
| **Why3** なぜコストを軽く見積もった？ | 「Cowork 自身が支払うわけじゃない」感覚 + 「PO の手元では数百円/回」が見えづらい。CLAUDE.md「金がかかる場合は事前確認」は新規 AWS リソース作成のみカバーで、既存 workflow の再 trigger には適用していなかった |
| **Why4** なぜ logs 取れない時に handoff せず叩き続けた？ | sandbox から S3 redirect (productionresultssa16.blob.core.windows.net) が fetch できないと判明した時点で「Code セッション or PO 手動」に切り替えるルールが無かった。Cowork は「自分で完結する」を優先しすぎた |
| **Why5** なぜ polling (sleep 30/40) も多用した？ | 進捗確認の手段として `sleep && curl` がデフォルト思考になっていた。schedule task に委ねて「次セッションで再確認」を選ぶ規律 (`global-baseline.md` §10 既存) を効果検証で守らなかった |

**仕組み的対策** (最低 3 つ・**思想 5**):

1. **思想 (失敗 N 回ルール)**: CLAUDE.md「コスト規律ルール」に追加。同一 workflow を 2 回 dispatch して両方失敗 → 3 回目禁止。Cowork 内で「念のためもう一回」は明示的にダメと書く ✅ (本 PR で landing)
2. **思想 (polling 禁止)**: API status の `sleep && curl` ループ禁止。1 回確認 → 結果記録 → セッションクローズ。schedule タスクに委ねる ✅ (本 PR で landing)
3. **思想 (AWS list/get も 5 回まで)**: 同じ情報を再取得して状態変化を待つのは無駄。一度取って判断する ✅ (本 PR で landing)
4. **思想 (代替手段の明文化)**: 根本原因不明なら (1) TASKS.md エントリー (2) WORKING.md Dispatch 継続性 (3) Code/PO handoff (4) p003-haiku 観察委ね ✅ (本 PR で landing)
5. **思想 (「金がかかる」の自覚拡張)**: 既存ルール「金がかかる場合は事前確認」は新規 AWS リソース作成のみだったのを、GHA minutes / Claude tokens / AWS API call の累積も含めるよう拡張 ✅ (本 PR で landing)

**メタ教訓**:
- **「自分の判断で完結したい」欲求 vs. 「お金が見えない場所でかかる」現実** — Cowork は能動的に動けるが、コストの可視性が PO 側より低い
- **CI 失敗の transient 判定は危険** — 5sec で死ぬ step は transient ではなく構造的問題。time stamp で「短時間失敗 = 構造的」と判断する規律
- **logs が取れない環境ではエスカレーション** — sandbox で S3 redirect 取れないと分かった瞬間、Cowork は「自分で見る」を諦める
- **「効果検証は schedule に委ねる」既存ルール** (`global-baseline.md` §10) は SLI 計測だけでなく **CI 失敗の再観察** にも適用する
- **テキストルール (思想) でも、明示すれば改善する** — CLAUDE.md に書かれていなかったから守らなかった部分が大きい (今回追記済)

**横展開チェックリスト**:
- [x] CLAUDE.md「コスト規律ルール」セクション追加 (失敗 N 回 / polling 禁止 / AWS list 5 回まで / 代替手段 / 金がかかる自覚拡張) (**思想** / 本 PR で landing)
- [x] lessons-learned に T2026-0502-COST-DISCIPLINE なぜなぜ追記 (**思想** / 本 PR で landing)
- [ ] TASKS.md `T2026-0502-DEPLOY-LAMBDAS-FIX` エントリー — deploy-lambdas.yml fetcher step の 5sec failure 原因特定 + 修正。logs を取れる Code セッションが調査する。Cowork はもう触らない (**handoff** / 本 PR で起票)
- [ ] (任意) `scripts/session_bootstrap.sh` に「直近 30 分以内に失敗した workflow を再 dispatch しようとする履歴があれば WARN」物理ガード (**物理** / 別途)

---

## T2026-0502-SEC2-RECURRENCE: SEC2 で平文 token を除去したら Cowork 自身が GitHub API 401 になった事故（2026-05-02）

**起きたこと**:
- T2026-0502-SEC2 (緊急対応) で `.git/config` の `remote.origin.url` から `gho_...` PAT を除去 + `.claude/settings.local.json` L21 の `Bash(GITHUB_TOKEN=... SLACK_BOT_TOKEN=... SLACK_WEBHOOK=... bash deploy.sh)` allow エントリーを削除
- 直後に Cowork が `scripts/cowork_commit.py` で PR を作ろうとしたら **401 Unauthorized**
- 原因: `cowork_commit.py` の `get_token_and_repo()` は `.git/config` URL から token を抽出するか、環境変数 `GITHUB_TOKEN` を fallback するだけの**2 経路実装**だった
- SEC2 で経路 1 を意図的に塞いだ + Cowork sandbox の env には `GITHUB_TOKEN` が設定されていない → **Cowork 自身が GitHub API 認証手段ゼロ**に陥った
- 結果: T2026-0502-SEC1/SEC2/O の完了記録 PR を Cowork から出せず、PO の手作業に依存することに

**なぜなぜ**:

| Why | 答え |
|---|---|
| **Why1** なぜ Cowork が 401 になった？ | `cowork_commit.py` の token 取得経路が 2 つだけで、両方とも SEC2 で塞がれた |
| **Why2** なぜ 2 経路だけだった？ | 初版実装時に「`.git/config` URL embed が常に存在する」前提で書かれていた。env fallback は名目上あるが Cowork sandbox には設定が来ない |
| **Why3** なぜ多経路を最初から考えなかった？ | 「Cowork が常に PAT 平文埋め込みを持つ」という暗黙の前提があった。安全な認証経路 (gh CLI auth / Keychain / .netrc) への抽象化が無かった |
| **Why4** なぜ SEC2 対応時にこの依存に気付かなかった？ | SEC2 タスク内で「平文 token を除去」だけに集中し、`cowork_commit.py` の token 取得ロジックを依存先として確認していなかった。CLAUDE.md「対症療法ではなく根本原因」「同パターン横展開」が effective に発火しなかった |
| **Why5** なぜ依存影響評価が弱い？ | secret 除去タスクのテンプレに「除去後にどの機能が壊れるか」を確認するセクションが存在しない。セキュリティ観点 (除去) と機能観点 (継続動作) が並行して走る習慣がついていない |

**仕組み的対策** (最低 3 つ・物理ゲート 3 + 観測 1):

1. **物理（cowork_commit.py 多経路化）**: `get_token_and_repo()` を 5 経路 fallback に拡張:
   - 経路 1: `.git/config` URL embed (旧仕様・SEC2 で除去推奨)
   - 経路 2: 環境変数 `GITHUB_TOKEN` / `GH_TOKEN`
   - 経路 3: `~/.config/gh/hosts.yml` (gh CLI auth)
   - 経路 4: `~/.netrc` (machine github.com)
   - 経路 5: macOS Keychain (security コマンド・Mac のみ)
   全経路 fail 時に明確なエラーメッセージで対処手順を出力。**実装: 本タスク `scripts/cowork_commit.py`**
2. **物理（`.git/config` URL token 直書き検出）**: `scripts/session_bootstrap.sh` §3e2 に bootstrap 起動時の grep ガードを追加。`gho_/ghp_/ghs_/ghu_` プレフィックスが URL に含まれていれば ERROR で `BOOTSTRAP_EXIT=1`。CLAUDE.md「PII / secrets コード直書き禁止」を `.git/config` にも適用。**実装: 本タスク `scripts/session_bootstrap.sh`**
3. **物理（secret 除去タスクのテンプレに依存影響評価セクション必須化）**: `docs/rules/security-checklist.md` (T2026-0502-SEC-FIX-ALL で新設予定) に「**Step 0: 除去対象の secret を参照しているコードを grep audit して影響先をリスト化**」を必須化。タスク化: **T2026-0502-SECRET-IMPACT-AUDIT**・**物理**
4. **観測（Cowork API 401 監視 SLI）**: `cowork_commit.py` の API 呼び出し失敗 (401/403) を CloudWatch カスタムメトリクスに put_metric_data + 24h で 3 回超なら Slack alert。タスク化: **T2026-0502-COWORK-API-401-SLI**・**観測**

**メタ教訓**:
- **「セキュリティ除去」と「依存機能の継続動作」は同タスク内でセットで考える**: 平文 token 除去だけに集中すると、その token を使っていた機能が音もなく壊れる。除去前に「この token を読んでいる場所」を grep audit する Step 0 を必須化する
- **`cowork_commit.py` のような「Cowork が依存する基盤スクリプト」は token fallback を 3 経路以上持つべき**: 1 経路が塞がれても代替がある状態を物理化することで、SEC タスク後も Cowork が自走可能
- **「Cowork が GitHub API を叩けない」は連鎖事故の起点**: PR 作成不能 → 完了記録残せない → 次セッションが状態を引き継げない → Dispatch 連続性破綻、と連鎖する。基盤認証経路は最優先で多重化

**横展開チェックリスト**:
- [x] `scripts/cowork_commit.py` の token 取得を 5 経路化（**物理** / 本タスク）
- [x] `scripts/session_bootstrap.sh` §3e2 に `.git/config` URL token 検出ガード（**物理** / 本タスク）
- [x] `docs/lessons-learned.md` に T2026-0502-SEC2-RECURRENCE セクション追記（**物理** / 本タスク）
- [ ] `docs/rules/security-checklist.md` に「Step 0: 除去前 grep audit」必須化（タスク化: **T2026-0502-SECRET-IMPACT-AUDIT**・**物理**）
- [ ] `cowork_commit.py` の API 失敗 (401/403) を CloudWatch メトリクスに記録（タスク化: **T2026-0502-COWORK-API-401-SLI**・**観測**）
- [ ] 同パターン横展開: `scripts/cowork_*.py` 系全般で「token 取得は `get_token_and_repo()` に委譲」を物理化（grep audit）（タスク化: **T2026-0502-COWORK-AUTH-CONSOLIDATE**・**物理**）
- [ ] secret 除去タスクの PR テンプレに「除去対象の grep audit 結果を本文に含める」セルフチェック追加（タスク化: **T2026-0502-SEC-PR-TEMPLATE**・**物理**）

**緊急時 fallback（Cowork が今 API 401 のとき）**:
- PO が Mac で `gh auth login --web` で OAuth flow → Keychain 認証
- `~/.config/gh/hosts.yml` に oauth_token が保存される → 次回 Cowork 起動から経路 3 で読める
- もしくは PO が Mac で `gh pr create` で完了記録 PR を作成（Cowork に依存しない）


---

## T2026-0502-O-RECURRENCE: AWS IAM Deny ポリシー追加が GitHub Actions deploy を巻き添えで殺した事故（2026-05-02）

**起きたこと**:
- T2026-0502-O で `CoworkDenyDestructive` インラインポリシーを Cowork IAM ユーザー (`arn:aws:iam::946554699567:user/Claude`) に attach
- Deny actions に `lambda:UpdateFunctionCode` を含めた (Cowork 手動 lambda 書き換え防止が目的)
- 直後の deploy-lambdas.yml run #379-#382 が **連続 4 回 failure** (fetcher Lambda step):
  ```
  AccessDeniedException ... User: arn:aws:iam::946554699567:user/Claude
  is not authorized to perform: lambda:UpdateFunctionCode
  ... with an explicit deny in an identity-based policy
  ```
- 原因: GitHub Actions の `deploy-lambdas.yml` は **Cowork と同じ IAM User (`Claude`)** で AWS API を叩いていたため、Cowork 用の Deny が GitHub Actions にも効いた
- 結果: PR #212/#213 等の commit が Lambda 本体に反映されない (本番未反映状態が継続)

**応急処置**: `CoworkDenyDestructive` の Action から `lambda:UpdateFunctionCode` を削除して deploy 復旧。

**なぜなぜ**:

| Why | 答え |
|---|---|
| **Why1** なぜ deploy が失敗した？ | `CoworkDenyDestructive` が `lambda:UpdateFunctionCode` を Deny し、IAM では Deny が Allow を上書きするため |
| **Why2** なぜ GitHub Actions も影響を受けた？ | GitHub Actions が Cowork と同じ IAM User (`Claude`) で AWS を叩いている。CI/CD 用と運用ユーザー用で identity を分離していなかった |
| **Why3** なぜ T2026-0502-O 設計時に気付かなかった？ | 「Cowork が `lambda:UpdateFunctionCode` を叩く経路」だけを想定し、「**他に同 IAM identity で `lambda:UpdateFunctionCode` を叩く経路**」を grep audit していなかった |
| **Why4** なぜ grep audit しなかった？ | T2026-0502-SEC2-RECURRENCE で立てた教訓「除去前 grep audit」は「除去」のみを対象にしていた。「**追加 (Deny)** にも同じパターンが起きる」という認識が無かった |
| **Why5** なぜ Cowork 自身が deploy 失敗を「別系統」と切り捨てた？ | Cowork 自身が「キー rotate の影響」と「IAM Deny の影響」を分離して考えてしまい、deploy failure を SEC1/O の延長線上と認識できなかった (= 関連事象の集約失敗) |

**仕組み的対策** (最低 3 つ・物理 3 + 観測 1):

1. **物理 (SEC10 前倒し: GitHub Actions OIDC + IAM Role 分離)**: GitHub Actions が Cowork と別の IAM identity (`GitHubActionsRole-Flotopic`) で動くようにし、Cowork 用 Deny の影響を受けない構造に変える。タスク化: **T2026-0502-SEC10** (既存・優先度上げる)・**物理**
2. **物理 (IAM ポリシー追加チェックリスト)**: `docs/rules/security-checklist.md` に「**Step 0: Deny に追加するアクションを、現在 AWS で叩いているのは誰か** を CloudTrail (直近 7 日) で grep audit」を必須化。Cowork User 以外 (= GitHub Actions / 他システム) が叩いている action は Deny に入れない or condition で限定する。タスク化: **T2026-0502-IAM-DENY-CHECKLIST**・**物理**
3. **物理 (deploy-lambdas N 回連続失敗で Slack 救済)**: `automerge-stuck-watcher.yml` 風の cron で deploy-lambdas が 2 回連続 failure になったら Slack 通知 + 原因 step / error message を summary に貼る。タスク化: **T2026-0502-DEPLOY-FAILURE-WATCHER**・**物理 (観測寄り)**
4. **観測 (deploy 成功率 SLI)**: `freshness-check.yml` SLI セットに「直近 24h の deploy-lambdas success 率」を追加 (既存提案 T2026-0502-DEPLOY-SLI と統合)・**観測**

**メタ教訓**:
- **「セキュリティ Deny ポリシー追加」は「平文 secret 除去」と同じく副作用源**: 両者とも「セキュリティ強化 → 機能停止」の副作用パターン。SEC2-RECURRENCE で気付いた「除去前 grep audit」を「**ポリシー追加前 audit**」にも横展開する必要があった
- **「同一 IAM identity を複数経路 (Cowork + CI/CD) で使い回す」は構造的に脆弱**: 一方の権限制限が他方を巻き添えで殺す。最初から identity 分離 (OIDC role per use case) で設計すべき
- **「直近の事故 + 直近の対処」の関連性を Cowork 自身が見逃す傾向**: Cowork が「キー rotate (SEC1)」と「IAM Deny (O)」を別事象として扱い、両者後の deploy failure を「別系統」と切り捨てた。**直近 24 時間で起きた SEC 系対処は全て deploy/CI failure の容疑者として優先精査**する習慣が要る

**横展開チェックリスト**:
- [x] `CoworkDenyDestructive` から `lambda:UpdateFunctionCode` 削除 (PO 操作・本タスク)
- [x] T2026-0502-O-RECURRENCE セクション追記 (本 PR)
- [ ] **SEC10 前倒し** (GitHub Actions OIDC + IAM Role) — 既存タスク優先度を 🔴 緊急に格上げ (タスク化: 本 PR 内で TASKS.md 更新提案)
- [ ] `docs/rules/security-checklist.md` に「IAM Deny 追加前 CloudTrail audit」必須化 (タスク化: **T2026-0502-IAM-DENY-CHECKLIST**・**物理**)
- [ ] `deploy-lambdas` 連続失敗 watcher (タスク化: **T2026-0502-DEPLOY-FAILURE-WATCHER**・**物理**)
- [ ] freshness-check SLI に deploy 成功率追加 (タスク化: **T2026-0502-DEPLOY-SLI**・**観測**)

---

## T2026-0502-COWORK-IMPACT-SKIP: Cowork が「キー変更/設定変更の影響実測」を skip して完了報告する手抜きパターン（2026-05-02・メタ事象）

**起きたこと**:
- T2026-0502-SEC1 (Anthropic + Slack rotate) 完了報告時、Cowork は「PO が rotate + GitHub Secrets 更新 + deploy-lambdas run #378 success」までで「完了」と報告
- T2026-0502-O (IAM Deny) 完了報告時、Cowork は「`aws iam create-access-key` で AccessDenied 確認」で「完了」と報告
- いずれも **「rotate / 設定変更後の他機能の動作実測」を skip** していた
- 結果: deploy-lambdas が run #379-#382 で連続 failure している事実を Cowork が気付かずに放置 (PO 指摘で初めて確認)

**なぜなぜ**:

| Why | 答え |
|---|---|
| **Why1** なぜ実測しなかった？ | 「PO 手作業が完了したら完了」と判断し、システム全体への影響実測を別途実施しなかった |
| **Why2** なぜ全体実測を別途やらなかった？ | CLAUDE.md「完了 = 動作確認済み」を SEC tasks に適用していなかった。SEC tasks は「設定変更 = 完了」と暗黙に区別していた |
| **Why3** なぜ区別した？ | SEC1/SEC2/O のチェックリストに「変更直後の動作確認」が **タスク自体の完了条件** に含まれていなかった (Verified-Effect は base→1 週間後で Eval-Due 設定だが、即時の Side-Effect-Verify は無し) |
| **Why4** なぜチェックリストに無い？ | SEC タスクのテンプレが「Verified-Effect」(機能の効果検証) だけで「Side-Effect-Verify」(他機能への副作用検証) を含まなかった |
| **Why5** なぜテンプレに無い？ | Cowork が SEC tasks を「セキュリティ強化単発」と捉え、「セキュリティ強化は他機能を壊す可能性が常にある」という前提を持っていなかった (= T2026-0502-SEC2-RECURRENCE / T2026-0502-O-RECURRENCE で既に証明されたのに、テンプレに反映されていなかった) |

**仕組み的対策** (物理 2 + 思想 1):

1. **物理 (SEC タスクテンプレに Side-Effect-Verify 必須化)**: `docs/rules/security-checklist.md` (T2026-0502-SEC-FIX-ALL で新設) に「**Step N: 変更直後 30 分以内に以下を実測 — (a) deploy-lambdas 直近 run conclusion (b) freshness-check 直近 SLI (c) fetcher-health-check 直近 conclusion**」を必須化。Verified-Effect とは別の **Side-Effect-Verify** 行を commit message にも要求。タスク化: **T2026-0502-SIDE-EFFECT-VERIFY**・**物理**
2. **物理 (SEC 系 commit-msg hook 拡張)**: `commit-msg` hook で commit message に `Verified-Effect:` がある場合、`Side-Effect-Verify:` 行も併存することを要求 (SEC tasks に限定)。タスク化: **T2026-0502-SEC-COMMIT-MSG**・**物理**
3. **思想 (Cowork メタ規律)**: Cowork が「PO 手作業完了 = タスク完了」と判断する前に、「**直近 24h の SEC 系対処後に新たな CI/SLI failure が増えていないか**」を grep で確認する自己チェック。物理化困難 (Cowork が自分を縛る規律)

**メタ教訓**:
- **「設定変更系タスクは設定が当たった後 30 分が脆弱**: 設定が反映された直後に他システムが壊れたかどうかを実測しないと、副作用に気付くのが遅れる
- **「PO の手作業が完了 ≠ タスク完了」**: PO が手作業を終えた瞬間が新たな観測ウィンドウの開始点。Cowork はそこから 30 分以内に副作用実測を完遂すべき
- **「同パターンが既に起きていたのにテンプレに反映されない」のはメタ事象の再発**: T2026-0502-SEC2-RECURRENCE で気付いたのに T2026-0502-O-RECURRENCE で同型を起こした = 「個別事象は記録するがテンプレ化しない」癖。物理化対策 #1 でテンプレ化を強制する

**横展開チェックリスト**:
- [x] T2026-0502-COWORK-IMPACT-SKIP セクション追記 (本 PR)
- [ ] `docs/rules/security-checklist.md` に Side-Effect-Verify 必須化 (タスク化: **T2026-0502-SIDE-EFFECT-VERIFY**・**物理**)
- [ ] `commit-msg` hook に SEC 系 Side-Effect-Verify 要求 (タスク化: **T2026-0502-SEC-COMMIT-MSG**・**物理**)
- [ ] 過去 30 日の SEC 系 commit に `Side-Effect-Verify:` が含まれているか grep audit (タスク化: **T2026-0502-SEC-AUDIT-RETRO**・**物理 audit**)

---

## T2026-0502-WORKING-MD-CLEANUP-CASCADE: WORKING.md 着手行が cleanup PR の unmerged-close で 5h 滞留した事故（2026-05-02）

**起きたこと（時系列・JST）**:
- 12:25 Cowork が WORKING.md に `[Cowork] T2026-0502-SES-METRIC-FILTER ... needs-push: yes` を追加 (着手 branch 上で)
- 12:27 PR #183 作成 (実装本体・WORKING.md `+1 -0` 同梱で push)
- 12:28 PR #183 auto-merge (16秒後・main に WORKING.md 着手行が landing)
- 12:51 Cowork が cleanup PR #184 を **「差分 0 件」と誤認して close** (コメント: 「PR #183 で WORKING.md が先 landing したため本 PR は差分 0 件」) — **実際は逆で、PR #183 が追加した行を #184 が削除する関係**だった
- 17:33 `session_bootstrap.sh` が `needs-push: yes` 滞留警告 (WARN・実害アラートではない)
- 17:36 別 Cowork セッションが PR #252 で再 cleanup
- 17:40 PR #252 auto-merge (5h 滞留が解消)

**正味の被害**:
- 5h 間 WORKING.md に「進行中」表記が残り、起動チェックが ERROR ではなく WARN 止まりだったため別タスクが先行した
- もし同じ着手行に「同じファイルを触る別タスク」が来ていたら `pr-conflict-guard.yml` が誤検出する可能性

**なぜなぜ**:

| Why | 答え |
|---|---|
| **Why1** なぜ PR #184 は「差分 0 件」と判定された？ | branch base が PR #183 merge **前** の origin/main だった。base には該当行がまだ無いので「削除PR」の diff も 0 になる |
| **Why2** なぜ Cowork は close した？ | コメント「PR #183 で先 landing」は語感的に「#183 が cleanup を済ませた」と読めるが、**実際は逆 (#183 が追加・#184 が削除)**。Cowork が PR の方向を取り違えた。close 前に main の WORKING.md を再確認せず short-circuit |
| **Why3** なぜそもそも実装 PR (#183) に WORKING.md 開始行追加が含まれた？ | Cowork が「タスク開始時に WORKING.md 追記してから push」を **着手 branch 上で**やった。本来は main 上で追記 → branch を切る順序 |
| **Why4** なぜ着手 branch 上で追記しても止まらない？ | CLAUDE.md「タスク開始前」セクションは「git pull → cat WORKING.md → 追記 → push」と書いているが、**追記をどの branch でやるかを物理ガードしていない**。「タスク完了後」も同じ |
| **Why5** なぜ滞留が 5h まで続いた？ | `session_bootstrap.sh` の needs-push 滞留検出は WARN 止まり (ERROR でない)。自動 cleanup PR も無い。「気付いた人が手動で cleanup PR を出す」運用に依存 |

**仕組み的対策** (物理 2 + 思想 1):

1. **物理 (auto-cleanup workflow)**: PR が main に merge された `workflow_run` トリガーで `.github/workflows/auto-cleanup-working-md.yml` を発動。PR title から `T2026-XXXX-XXX` 形式のタスクIDを正規表現抽出 → WORKING.md 内で該当タスクIDを含む行を grep → 残っていれば自動削除 + auto cleanup PR を作成 (cowork_commit.py 経由)。タスク化: **T2026-0502-AJ**・**物理**
2. **物理 (session_bootstrap.sh ERROR 化 + 4h 超 auto-cleanup)**: `needs-push: yes` 滞留 4h 超 = ERROR (現状 WARN)。さらに 4h 超え行に対して `cowork_commit.py` で削除 PR を自動提案 (人が承認 click するだけ)。タスク化: **T2026-0502-AK**・**物理**
3. **思想 (cowork_commit.py に PR close 前 verify)**: cleanup PR が「差分 0 件」を出した場合、close する前に「main の該当ファイルが想定通りに変わっているか」を検証する prompt 行を README に追加。物理化困難 (Cowork 自身の判断に依存)

**メタ教訓**:
- **「実装 PR に WORKING.md 開始行追加を同梱する」は構造的アンチパターン**: 開始行追加 / 完了行削除 は **必ず main 直 push** が筋（チケット管理ファイルなので branch を切る必要がない）。だが CLAUDE.md「main 直 push 禁止 (T2026-0502-M)」は **コードファイルだけ対象**であるべきで、メタドキュメント (WORKING.md / TASKS.md / HISTORY.md) は例外として明文化すべき。`pre-push` hook も該当ファイルだけ exempt する分岐を追加する余地あり
- **「差分 0 件 cleanup PR」は close する前に main の状態を再確認**: branch base が古いだけで diff が 0 になるケースは頻発する。「diff が 0 だから不要」ではなく「main が想定通りか確認」が正しい順序
- **「WARN は気付かれない」**: `session_bootstrap.sh` で WARN 出力したものは Cowork が「警告だけ・後で」と先送りする傾向あり。実害があるならば最初から ERROR で止める方が確実

**横展開チェックリスト**:
- [x] T2026-0502-WORKING-MD-CLEANUP-CASCADE セクション追記 (本 PR・landing: `docs/lessons-learned.md`)
- [ ] auto-cleanup-working-md.yml 新設 (タスク化: **T2026-0502-AJ**・**物理** / landing: `.github/workflows/auto-cleanup-working-md.yml`)
- [ ] session_bootstrap.sh の needs-push 滞留検出を WARN→ERROR + 4h 超 auto cleanup PR 提案 (タスク化: **T2026-0502-AK**・**物理** / landing: `scripts/session_bootstrap.sh`)
- [ ] `pre-push` hook で WORKING.md / TASKS.md / HISTORY.md の main 直 push を例外扱い (タスク化: **T2026-0502-AL**・**物理** / landing: `.git/hooks/pre-push` + `scripts/install_hooks.sh`)

---

## T2026-0502-CI-PERMANENT-FAILURE-KNOWN-ISSUE: 4 件の CI workflow が optional check のため恒常 failure 状態で放置されている事象（2026-05-02）

**起きたこと**:
- PR #252 / PR #254 (本セッションで作成) で同じ 4 workflow が常時 failure:
  1. `Lambda 構文チェック` (`ci.yml` の「危険パターン検出」step)
  2. `エージェントスクリプト チェック` (`ci.yml` の「scripts/ Python 構文チェック」step)
  3. `思想・表記ドリフト検出` (`ci.yml` の「形骸化検出 grep」step = `scripts/check_soft_language.sh`)
  4. `secret pattern scan` (`secret-scan.yml` = `scripts/secret_scan.sh full`)
- いずれも **required check ではないため auto-merge を阻害しない** → 「failure のまま放置でも merge は通る」状態が長期継続
- 直近 main の集計: `Secret Scan` は **直近 4 連続 failure (success 率 0%)**, `CI（構文チェック・品質確認）` は直近 3 件中 2 failure (success 率 33%)
- 副次被害: PR レビュー時に「CI fail = 緊急」のシグナル価値が摩耗、本物の breakage を見逃す感度低下が起きる

**正味の被害**:
- CI green/red のシグナル価値が壊れる (狼少年化)
- 新規 PR の reviewer が「CI 4件 fail = 既知だから無視」を学習、本物 fail 時にも見逃す訓練が成立
- 「CI 緑が必須」を物理化する (required check 昇格) パスを使えなくなる

**真因の切り分け** (本セッションで判明した分):

| Workflow | 真因 |
|---|---|
| Lambda 構文チェック (危険パターン検出) | `ci.yml` line 154 の grep が `scripts/security_audit\.sh\|scripts/security-audit` だけ除外。**`scripts/secret_scan.sh` (パターン定義) と `scripts/secret_scan_allowlist.txt` (allowlist 定義) を除外していない** → これらのファイルに含まれる `sk-ant-api03-*` / `AKIA*` パターン定義文字列を「ハードコード」と誤検出 (5箇所一致) |
| エージェントスクリプト チェック (scripts/ Python 構文チェック) | `scripts/*.py` の中に構文エラーがある (どのファイルかは log を見る必要・本セッションでは未特定) |
| 思想・表記ドリフト検出 (check_soft_language.sh) | `CLAUDE.md` / `docs/rules/global-baseline.md` / `docs/lessons-learned.md` の「仕組み的対策」セクション内に「気を付ける/注意する/意識する/確認する」が混入。実際の混入箇所は本セッションで未特定 |
| secret pattern scan (secret_scan.sh full) | git history 全件 scan で誤検出。allowlist 漏れ・または rotated 済 secret が history に残存している可能性 |

**なぜなぜ**:

| Why | 答え |
|---|---|
| **Why1** なぜ failure が長期放置された？ | required check ではないため auto-merge が通る。merge 後に誰かが「あの 4 件、また fail してる」を遡って見る習慣がない |
| **Why2** なぜ required にしていない？ | 4 件のうちのどれかが「既知の誤検出で直せていない」状態が続き、required にしたら merge が止まる懸念で先送り |
| **Why3** なぜ「既知誤検出」を直さなかった？ | Lambda 構文チェックは grep 除外パターン 2 行追加で直る。エージェントスクリプト・思想ドリフトも 1 ファイルの構文 / 表記修正で済む可能性。**「直す価値より放置コストが見えない」状態** |
| **Why4** なぜ放置コストが見えない？ | 「CI 4 件 fail はずっとそうだから慣れた」という認知バイアス。失敗 SLI (直近 N 件 success 率) を可視化していないため数値で危機感が伝わらない |
| **Why5** なぜ SLI 化していない？ | freshness-check.yml SLI は flotopic 本体の品質指標がメインで、「CI 自体の健全性 SLI」 が無い。CI の品質を CI 自身で監視していない |

**仕組み的対策** (物理 3 + 思想 1):

1. **物理 (4 workflow 一括修復)**: 各 workflow の真因を切り分けて修復。スコープ:
   - Lambda 構文チェック: grep 除外に `scripts/secret_scan\.sh|scripts/secret_scan_allowlist\.txt` を追加 (1 行)
   - エージェントスクリプト チェック: `scripts/*.py` のうち構文エラーになっているファイル特定 + 修正
   - 思想・表記ドリフト検出: `check_soft_language.sh` が拾っている混入箇所修復
   - secret pattern scan: `secret_scan.sh full` の git history 誤検出を allowlist で無効化 or rotated secret の history 除去 (BFG Repo-Cleaner 等)
   タスク化: **T2026-0502-AM**・**物理**
2. **物理 (修復後 required 化)**: 4 workflow 全て直したあと branch protection で **required status check に昇格** → 「CI fail のまま auto-merge」を構造的に不可能化。PO 操作 (Settings → Branches → main) が必要。タスク化: **T2026-0502-AN**・**物理 (PO 操作)**
3. **物理 (CI 健全性 SLI)**: `freshness-check.yml` SLI に「**直近 24h main runs success 率 (per workflow)**」を追加。80% 下回ったら Slack alert + TASKS.md 自動起票。タスク化: **T2026-0502-AO**・**観測**
4. **思想 (failure → 即修復 or 即削除の判断ルール)**: 「CI が 3 連続 failure したら 24h 以内に (a) 修復 PR を出す、(b) workflow を一旦無効化する、のどちらかを必ず選ぶ」を CLAUDE.md or `docs/rules/quality-process.md` に明記。物理化困難 (運用判断に依存)

**メタ教訓**:
- **「optional check が長期 failure」は CI 全体のシグナル価値を壊す**: 1 件の長期 fail は周辺の本物 fail も無視されやすくする (broken windows theory). optional だからこそ「即修復 or 即削除」の二択を物理化すべき
- **「直す価値が見えない」は SLI で可視化する**: 数値が無いと放置コストは認識されない。CI 健全性 SLI が無かったので 4 件 failure が「いつもの風景」になっていた
- **secret 検出系 workflow は構造的に self-recursive な誤検出を起こす**: パターン定義ファイル自身が pattern を含むため、scan 対象から除外する allowlist 設計が必須

**横展開チェックリスト**:
- [x] T2026-0502-CI-PERMANENT-FAILURE-KNOWN-ISSUE セクション追記 (本 PR・landing: `docs/lessons-learned.md`)
- [ ] 4 workflow 一括修復 (タスク化: **T2026-0502-AM**・**物理** / landing: `.github/workflows/ci.yml` + `.github/workflows/secret-scan.yml` + `scripts/*` 該当箇所)
- [ ] 修復後 required check 昇格 (タスク化: **T2026-0502-AN**・**物理 (PO 操作)** / landing: GitHub branch protection settings)
- [ ] CI 健全性 SLI 追加 (タスク化: **T2026-0502-AO**・**観測** / landing: `.github/workflows/freshness-check.yml`)
- [ ] 「3 連続 failure ルール」明文化 (タスク化: **T2026-0502-AP**・**思想** / landing: `docs/rules/quality-process.md`)

---

## T2026-0502-AQ-NOINDEX-REGRESSION: 「内部品質の改善のために流入を捨てた」副作用に 5 日間気づかなかった事故

**起きたこと** (2026-04-28 〜 2026-05-02): T2026-0502-ADSENSE-FIX で AdSense 薄コンテンツ問題対策として `frontend/topic.html` と `frontend/catchup.html` に `<meta name="robots" content="noindex,follow">` を追加。Cloudflare Web Analytics の daily PV が **4/27 260 → 4/28 20 (1/10 に急減)**。直近 4 日 (4/28〜5/1) 平均 27 PV/day となり、4/22〜27 の平均 ~145 PV/day から 80% 減。**5 日間誰も気づかなかった**。発覚は 5/2 に PO が「流入は実測で増えてる？」と質問 → Cowork が CloudWatch + Cloudflare Web Analytics データを照合 → noindex commit を git log で発見。

**Why1**: なぜ PV が 1/10 になったか? → topic.html を noindex 化して Google 検索インデックスから個別記事ページが除外されたから。Cloudflare Web Analytics の Top pages 1 位は `/topic.html` 390 PV だった (= 検索流入の主動線)
**Why2**: なぜ noindex を入れたか? → AdSense 薄コンテンツ問題対策。SPA shell の重複 URL 空間が「薄い」と判定されることへの対症療法
**Why3**: なぜ流入消失が 5 日間気づかれなかったか? → SEO 流入 / 日別 PV / 前日比変化を観測する SLI が無かった。cf-analytics Lambda は毎日 7:00 JST にデータを取得し S3 にキャッシュしているが、**閾値判定して Slack に投げる仕組みが無かった** (admin.html の表示用に置いてあるだけ)
**Why4**: なぜ SEO の SLI が無かったか? → フェーズ3 (UX/成長) に着手していないため、流入関連指標を誰も観測しないまま。観測ゼロのままフェーズ4 (収益化) 系の意思決定を打ち、フェーズ3 の前提 (流入) を壊した
**Why5**: なぜフェーズ前提を壊す意思決定が走ったか? → `docs/product-direction.md` / `docs/project-phases.md` に「フェーズ N の前提を壊す可能性のある変更は明示する」原則がなく、PR 単位で見ると「AdSense 通過のため」という個別最適化として通ってしまう構造

**仕組み的対策** (物理 1 + 観測 1 + 思想 2): ※ 2026-05-02 PO 指摘「物理ガードを入れたうち半分は思想だった」を受けて再分類済 (旧版「物理 3 + 思想 1」は過大表記)

1. **物理 (主要ページ noindex 物理 reject)**: `scripts/check_seo_regression.sh` を新設。`frontend/{index,topic,catchup,storymap,about,contact,terms}.html` に `noindex` が混入した PR を CI で exit 1。`.github/workflows/ci.yml` に組込。**破ったら CI が止まる = 物理**。本 PR で landing。タスク: **T2026-0502-AQ**
2. **観測 (Cloudflare PV 前日比急変 SLI)**: `freshness-check.yml` に SLI 15 追加。`api/cf-analytics.json` の `cf.daily` を読んで前日比 0.7 未満で WARN・0.5 未満で ERROR を Slack 通知。重複 alert 防止のため UTC 22 時台 (cf-analytics 更新直後) のみ判定。**気付ける仕組みであって物理 reject ではない**。本 PR で landing
3. **思想 (frontend HTML への注意喚起コメント)**: 削除箇所に「T2026-0502-AQ: noindex 削除」コメントを残し将来の AI セッションが安易に再追加しないよう注意喚起。**物理的には止まらない (#1 の CI が止める)・コメントは補助**。本 PR で landing
4. **思想 (フェーズ前提を壊さない原則の明記)**: `docs/product-direction.md` に「フェーズ N の前提 (例: 流入・観測点・主要 KPI 取得経路) を壊す可能性のある PR は、PR description に `Phase-Impact-Conflict:` 行で明示する」を明記。物理化困難 (運用判断) のため 1 ヶ月運用後に PR template への組込を検討

**メタ教訓**:
- **「内部品質の改善」と「ユーザー側 KPI」は独立軸ではない**: 内部品質を上げる施策が外部流入を犠牲にすることがある。両軸を同時に観測しないと「進歩しているのに進歩していない」状態が起きる
- **観測のないループは空回りする**: cf-analytics Lambda がデータを毎日取得していても、閾値判定 + 通知の仕組みが無いと「データはあるが誰も見ない」状態になる。SLI 化されない観測は無いのと同じ
- **対症療法 (noindex 化) は副作用範囲が見えにくい**: noindex の副作用 = 検索流入消失は当然だが、AdSense 通過を取る側の視点に集中していると見落とす。Phase-Impact-Conflict の明示で別レイヤーから検証強制を入れる必要

**横展開チェックリスト**:
- [x] 主要ページ noindex 物理ガード `scripts/check_seo_regression.sh` (本 PR・landing: `scripts/check_seo_regression.sh` + `.github/workflows/ci.yml`)
- [x] Cloudflare PV 前日比急変 SLI (本 PR・landing: `.github/workflows/freshness-check.yml` SLI 15)
- [x] 主要ページに「T2026-0502-AQ: noindex 削除」コメント追加 (本 PR・landing: `frontend/topic.html` + `frontend/catchup.html`)
- [x] フェーズ前提を壊さない原則明記 (本 PR・landing: `docs/product-direction.md`)
- [ ] PR template への `Phase-Impact-Conflict:` 行の組込 (1 ヶ月運用観察後・タスク化保留)

---

## T2026-0502-AT-MERGE-TOKEN-CONSTRAINT: auto-merge bot が GITHUB_TOKEN を使ったことで「PR merge → deploy auto-trigger」が 30 日 0 回発火していた事故

**起きたこと** (2026-04-02 〜 2026-05-02): T2026-0501-N (2026-05-01 制定) で auto-merge.yml を導入し、CI 全 green の PR を `gh pr merge --auto --squash` で自動 merge する仕組みを稼働開始。一方で `deploy-p003.yml` (frontend deploy) と `deploy-lambdas.yml` の trigger は `push: branches: [main]` + `pull_request: types: [closed]` で構成されていた。**過去 30 日間で deploy-p003.yml の pull_request event 由来 run は total=0**。push event 由来 run はあったが、auto-merge bot による squash merge では発火しなかった。本日 (5/2) T2026-0502-AQ (noindex 削除 PR #263) を merge した後、私が手動 `workflow_dispatch` を打つまで 30 分間本番未反映だった。これは過去 1 ヶ月の全 frontend PR で同じ問題が発生していた可能性が高い (PR merge 後の本番反映が運任せ・PO の手動 dispatch 頼み)。

**Why1**: なぜ auto-merge bot による merge で deploy-p003 が発火しなかったか? → GitHub の制約「**`GITHUB_TOKEN` を使った workflow が起こした push / merge / commit は、他の workflow を trigger しない**」(無限ループ防止のため)。auto-merge.yml が `GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}` で `gh pr merge` を実行すると、その結果生まれる main への push event も pull_request closed event も deploy-p003 を発火させない
**Why2**: なぜこの制約に気づかなかったか? → workflow 単体テストでは検出できない。手動 merge で動作確認している間は deploy-p003 が普通に発火するため OK に見える。auto-merge bot を本番稼働させた後、**「本番反映されているか」を独立した観測点で確認する仕組みが無かった**
**Why3**: なぜ「本番反映されているか」の観測が無かったか? → CloudFront last-modified / S3 LastModified / Lambda LastModified を「最新 commit から N 分以内」で見る SLI が存在せず、デプロイ成功 = workflow run success という間接指標で安心していた
**Why4**: なぜ workflow yml に「pull_request closed でカバー」と書いてあったのに実際カバーできていなかったか? → Lambda 側で同じ事故を起こした T2026-0502-PATH-FILTER-AUDIT の対処として「pull_request closed でカバー」と書き添えたが、**実装後の動作確認をしていなかった**。コメントは書いたが効いていない (思想ルール化したが物理動作で検証していない)
**Why5**: なぜ似た問題 (T2026-0502-PATH-FILTER-AUDIT for Lambda) が起きていたのに横展開で frontend に効かせなかったか? → 既存の deploy-trigger-watchdog.yml は Lambda 専用で frontend 非対応のまま。横展開チェックリスト「auto-merge bot 由来の trigger 失敗対策」が無かったため、Lambda で気づいた事故が frontend で再発するのを防げなかった

**仕組み的対策** (物理 1 + 観測 1 + 思想 2): ※ 2026-05-02 PO 指摘「物理ガードを入れたうち半分は思想だった」を受けて再分類済 (旧版「物理 3 + 思想 1」は過大表記)

1. **物理 (auto-merge.yml の PAT 化)**: `GH_TOKEN: ${{ secrets.AUTO_MERGE_PAT || secrets.GITHUB_TOKEN }}` に変更 (本 PR で実装済)。PAT (= user identity) で merge することで GITHUB_TOKEN 制約を回避し、push event / pull_request closed event が他 workflow を正常に trigger する。**PAT 未設定時は GITHUB_TOKEN にフォールバック + warning ログ** (壊さない設計)。**ただし**: フォールバックがあるため AUTO_MERGE_PAT 未設定でも auto-merge 自体は動く = 「PAT 設定が物理的に強制されているわけではない」(警告ログのみ)。タスク: **T2026-0502-AT**・**物理 (本体)**
2. **観測 (secret-scan.yml の漏洩検出)**: `secret-scan.yml` の `gh[ops]_` パターン検出で PAT 漏洩は CI で物理 reject 済 (T2026-0502-SEC2)。**これは物理だが本タスクの直接対策ではなく既存ガードの流用**。本タスクで新規追加した独自の物理ガードはなし
3. **思想 (PAT scope 最小化 + expire 90 日)**: PAT の権限は `repo` + `workflow` のみ・expire 90 日設定で rotation 強制。**PO 自身の運用判断に依存・物理的には scope 拡張も expire 無制限化もできてしまう**
4. **思想 (横展開チェックリスト追加)**: lessons-learned.md の本セクションに「auto-merge bot 由来の trigger 失敗を Lambda 用に直したら frontend / その他にも横展開する」を明記 + 確認パターン (workflow runs API で `event=pull_request` 由来の run が total=0 なら異常)。**気付ける仕組みであって物理 reject ではない**
5. **思想 (中期 GitHub App 化)**: PAT は user 紐付きで離脱リスクあり。GitHub App は Bot identity で長期運用に向く。1 ヶ月運用後に検討 (T2026-0502-AV タスク化)

**メタ教訓**:
- **`GITHUB_TOKEN` で workflow 内から push/merge する設計はデフォルトで他 workflow を trigger しない**: GitHub Actions の最も罠が多いポイントの 1 つ。auto-merge / auto-commit / auto-tag 系の workflow を導入する際は必ず PAT or GitHub App 経由を検討する
- **「workflow が success」と「本番反映された」は別軸**: workflow 単体の success 率だけ見ていても、本番側の last-modified が更新されているかを独立観測しないと「動いている気がするだけ」になる
- **継ぎ足し watchdog (壊れた後に検知して fallback) は最終手段**: 真因を回避できるなら回避する方が、観測対象が増えず watchdog 自体の故障リスクも持たない。本タスクで初版に書いた deploy-trigger-watchdog-frontend.yml は PO 指摘「継ぎ足しでとりあえず動かすのはやめてくれ」で撤回した

**横展開チェックリスト**:
- [x] auto-merge.yml の PAT 化 + フォールバック (本 PR・landing: `.github/workflows/auto-merge.yml`)
- [ ] PO の PAT 発行 + AUTO_MERGE_PAT secret 登録 (タスク: **T2026-0502-AT**・**PO 操作**)
- [ ] PAT 設定後の効果検証: trivial frontend PR を merge して deploy-p003 が pull_request event で run することを確認 (Eval-Due: 2026-05-03)
- [ ] 中期 GitHub App 化検討 (タスク: **T2026-0502-AV**・**思想**・1 ヶ月運用後)
- [ ] **横展開**: 似た構造の自動 merge / 自動 commit / 自動 tag workflow が他にあれば全部 PAT 化 (確認方法: `grep -rE "gh pr merge|git push|gh release" .github/workflows/ | grep -v PAT`)
- [ ] 観測 SLI: workflow runs API で「frontend/lambda 系 deploy workflow の `event=pull_request` 由来 run が直近 7 日で total=0」をアラート化 (T2026-0502-AT 完了後の継続観測)

---

## 2026-05-02 deploy-trigger-watchdog 偽陽性 failure 連発 (T2026-0502-WATCHDOG-FIX)

**事象**: `deploy-trigger-watchdog.yml` と `deploy-trigger-watchdog-frontend.yml` が以下のケースで偽陽性 failure を出し、本来「物理ガード」として信頼すべき出力を「いつもの fail だから無視」させる broken windows 状態に。
1. **docs-only PR (例: PR #277)**: TASKS.md だけ変えた PR で freshness poll が走り、`git log -1 -- projects/.../lambda/` が過去の lambda commit 時刻を返し、現在の Lambda LastModified との diff が threshold (30min) を負方向に超過 → fail
2. **code-touching PR (例: PR #276)**: deploy chain (auto-merge → post-merge-deploy → deploy-lambdas → Lambda 更新) が完了する前に watchdog 5min poll window が終了 → 実 deploy 成功してるのに watchdog fail

**Why1**: なぜ docs-only PR で freshness poll が走った？ → `lambda path マッチなし → skip` step が `exit 0` で抜けても次の `Lambda freshness poll` step に `if:` 条件がなく、後続ステップは規定通り走る GitHub Actions 仕様だった

**Why2**: なぜ if: 条件をつけ忘れた？ → 「step で exit 0 すれば後続 step も走らない」という誤認 (シェル script の exit と GitHub Actions step の終了の違いを取り違え)

**Why3**: なぜ初期実装時に発見されなかった？ → docs-only PR を想定した QA フィクスチャがなく、初期検証が code-touching PR のみで行われた

**Why4**: なぜ code PR でも fail？ → 5min poll window (3 attempts × 100s) が deploy chain (auto-merge → post-merge-deploy → deploy-lambdas → Lambda 更新) 平均 3-5min とギリギリ・最後の attempt が deploy 完了直前に終わるレース

**Why5**: なぜ deploy chain 時間を測定しなかった？ → watchdog 設計時 (PR #152/#154/#156/#162 直後) に deploy chain 完成形が未確定。auto-merge と post-merge-deploy が後付けされて chain が長くなったが watchdog 側を更新しなかった

**仕組み的対策 (本 PR で landing)**:
1. `Lambda freshness poll` / `CloudFront freshness poll` step に明示的な `if:` 条件追加 — push/schedule/dispatch/lambda-touched-PR のみ走る (`steps.path_check.outputs.matched == 'true'` を必須化)
2. poll 窓を 5min → 8min に拡大 (4 attempts × 120s sleep = 480s) — deploy chain 平均 + 余裕分
3. 両 watchdog (lambda 用 + frontend 用) を同 PR で同期修正 = **横展開**

**横展開チェックリスト**:
- [x] `.github/workflows/deploy-trigger-watchdog.yml` if: 条件追加 + 8min 化
- [x] `.github/workflows/deploy-trigger-watchdog-frontend.yml` 同様 (横展開)
- [x] 他 workflow に同 pattern (`exit 0` 後の if: 条件無し step) がないか grep — `freshness-check.yml` 内の `exit 0` は全て `run:` block 内で完結し subsequent step は `if: outputs.skipped != 'true'` 等で skip 制御済 = 同 bug ナシ
- [ ] 効果検証: 次回 docs-only PR で watchdog が success になるか観測 (Eval-Due: 2026-05-09)
- [ ] 効果検証: 次回 code-touching PR (BC/AY 実装) で watchdog が deploy chain 完了を待ってから success/lag_detected 判定するか観測

**この教訓から導かれる一般原則**:
- GitHub Actions の `step` 内 `exit 0` は **そのステップを終わらせるだけで job 全体や後続 step は止めない**。後続 step を止めたい場合は **必ず後続 step に `if:` 条件を書く**
- `paths` filter は `push` event 等で trigger 段階で効くが、`pull_request` event では効かない (PR 作成時点で全 path が候補)。pull_request の path filter は **job 内の独立した path_check step で実装** + 後続 step に `if:` で連携 が標準パターン
- watchdog 系 workflow を作る時は **deploy chain 全体時間を実測してから poll 窓を決める** (5min は短すぎ・8〜10min が安全)

---

## 2026-05-02 SEC10 OIDC 移行時の IAM 権限漏れ (T2026-0502-IAM-DEPLOY-FIX)

**事象**: SEC10-CODE で OIDC 専用化 (両建て廃止) した後、以下が立て続けに偽陽性 failure:
1. **deploy-lambdas.yml** の `bluesky-morning EventBridge cron 登録 (T193)` step が `events:PutRule` で AccessDenied → workflow=failure (Lambda 本体は更新済なのに)
2. **deploy-trigger-watchdog.yml** の Lambda freshness poll が `aws lambda get-function-configuration` で AccessDenied → 4 秒で exit 2 (sleep にも到達せず)

両方とも GitHub Actions OIDC role の inline policy に **必要 action / resource ARN が含まれていない** が原因。

**Why1**: なぜ AccessDenied 連発？ → SEC10 OIDC 移行時に role 分離したが、新 role の policy が機能不足。Standard role: `lambda:GetFunctionConfiguration` 欠落 (watchdog 用)・Deploy role: `events:PutRule` の Resource ARN が `rule/p003-*` のみで `flotopic-*` 欠落

**Why2**: なぜ移行時に発見されなかった？ → IAM policy が AWS console / CLI 直接編集で管理されていて git tracked じゃなかったため、policy 変更の review プロセスが存在せず権限漏れに気付けなかった

**Why3**: なぜ気付けなかったあとも放置された？ → workflow=failure になっても auto-merge は通るため (failed workflow が required check ではなかった)、PR ごとに 1 件ずつ failure が積み上がった (broken windows)。watchdog の偽陽性も同根

**Why4**: なぜ console 直接編集を許してしまった？ → IaC (Terraform / CloudFormation) の導入が後回しで、最初の OIDC role 作成時に「とりあえず console で作る → policy が必要になるたび console で追記」のパターンが固定化

**Why5**: なぜ IaC 導入を後回しにした？ → IAM 単体での導入はオーバーキルに見え、bigger refactor と紐付けて先送りされていた。SEC10 のような部分的な役割再編で権限漏れが発生する経路を残してしまった

**仕組み的対策 (本 PR で landing)**:
1. `infra/iam/policies/*.json` に role policy を git tracked source of truth として置く
2. `infra/iam/apply.sh` で JSON → AWS に sync (drift 検出 + apply)
3. `docs/runbooks/iam-policy-management.md` で「IAM 変更は PR diff 経由必須・console 直接編集禁止」を明文化
4. Standard role に `lambda:GetFunctionConfiguration` 追加 (watchdog 復活)
5. Deploy role の EventBridgeRules Resource に `flotopic-*` 追加 (bluesky-morning step 修復)

**横展開チェックリスト**:
- [x] Standard role policy 修正 + apply 完了 (RequestId: b6558f2f-1fde-45e3-ae17-0bbfe88b9957)
- [x] Deploy role policy 修正 + apply 完了 (RequestId: d9b456b4-619e-410b-9597-b4e15a17a95e)
- [x] `infra/iam/policies/` ディレクトリ作成 + JSON 配置
- [x] `infra/iam/apply.sh` 作成 + 実行可能化
- [x] `docs/runbooks/iam-policy-management.md` 作成
- [ ] CI で drift 検出 (`apply.sh --dry-run` 結果が空でなければ alert) を実装 (T2026-0502-IAM-DRIFT-CI として別タスク化候補)
- [ ] 効果検証: 次回 code-touching PR の deploy + watchdog が両方 success になるか観測 (Eval-Due: 2026-05-09)
- [ ] 同 pattern (console 直接編集された AWS resource) が他にないか棚卸し: S3 bucket policy / SQS queue policy / Lambda resource-based policy 等

**この教訓から導かれる一般原則**:
- **AWS resource の権限は IaC で git tracked にする**。console 直接編集は drift の温床で、移行時の権限漏れを review プロセスで検出する経路を断ってしまう
- **role 分離 (SEC10 のような) を行う時は、移行前後の `aws iam get-role-policy` 出力を diff として review する**
- **broken windows は連鎖する**。watchdog 偽陽性 → CI failure 慣れ → 真の failure 見逃し → AccessDenied のような root cause 発見遅延

---

## T2026-0502-BI: 静的SEO HTML と動的SPA の二重 URL で canonical が破綻していた（2026-05-02 制定）

**事象**: SEO 全般の精査依頼 (PO 直接指示「SEO対策できてるか確認して欲しい / 厳しめに / なんでそんな設計になってしまってるのか」) の調査で、`https://flotopic.com/topic.html?id=X` (動的SPA) と `https://flotopic.com/topics/X.html` (静的SEO) の **両方が indexable で並走** していたことを発見。さらに動的側の初期 canonical (`<link rel="canonical">`) が `https://flotopic.com/topic.html` (id 無し) を指しており、JS による canonical 書換 前の Googlebot 初回 fetch では「全 ID が topic.html 単独に統合される duplicate URL シグナル」を Google に送り続けていた。app.js / detail.js / mypage.html / profile.html / catchup.html / storymap.html の **内部リンク 22 箇所すべてが dynamic URL (topic.html?id=) を指していた** ため、検索エンジンが discover する経路は全て duplicate side。sitemap だけが正しい static URL を指すという矛盾構造。


> **※ 2026-05-02 22:35 JST 訂正 (T2026-0502-BI-REVERT)**: 下記「内部リンク 22 箇所を `topics/${tid}.html` に統一 (仕組み的対策 2)」「CloudFront Function rule 4 で 301 redirect (仕組み的対策 3)」「`check_seo_regression.sh` Rule 2 で dynamic 内部リンク禁止 (仕組み的対策 4)」の 3 点は **ユーザー UX を破壊したため revert** (PR #XXX)。
>
> 静的 `topics/X.html` は **Googlebot 向け SEO 専用** の薄い AI まとめページ (関連記事 10 件 + アフィリエイト)。ユーザー向け SPA `topic.html?id=X` (コメント / お気に入り / ストーリー分岐 / 関連トピック / 推移グラフ等の full UX) の役割を奪うのは設計違反だった。
>
> SEO 改善のうち **JSON-LD 適正化 (NewsArticle / 完全ISO dateModified / BreadcrumbList / publisher.logo / mainEntityOfPage / max-image-preview)** と **CI Rule 3/4 (生成 JSON-LD の @type / dateModified 検査)** は UX に影響しないため維持。canonical 統一は別経路 (動的SPA `topic.html` に noindex / JS で canonical を `topics/X.html` に向ける / bot-only redirect 等) で再設計予定 (T2026-0502-BI-REDESIGN)。
>
> Why: 静的ページは「Googlebot に頭出しする SEO 一次・薄い content」であり「ユーザー導線の一次」ではないという役割分離を見落とし、内部リンクを静的化することで導線も切り替えてしまった。
> How to apply: 「SEO 改善のために URL を変更」する施策は、その URL がユーザー向けかボット向けかを必ず分離して評価する。User UX と SEO indexability は別レイヤー。

**Why1**: なぜ canonical が破綻していた？ → 動的SPA `topic.html?id=X` と 静的SEO `topics/X.html` の二重 URL が並走し、どちらを一次とするか統一されていなかった。

**Why2**: なぜ二重 URL を放置した？ → 2026-04-27 commit `013fe25f` で `generate_static_topic_html` を後付け追加した時、内部リンク 22 箇所と CloudFront Function は触らず「あとで統一する」を持ち越したまま 1 週間運用。

**Why3**: なぜ後付け追加だった？ → 元々 (2026-04-20 initial) は SPA で `topic.html?id=X` のみ。Googlebot の JS レンダリングが Top Stories の鮮度要件 (数分〜数時間) に間に合わず、indexing が伸びないと気付き、静的 HTML を別経路で吐き出す判断 → ただし**新旧 URL の整理は未実施**。

**Why4**: なぜ初期 SPA 設計を選んだ？ → 開発速度優先 + 「Google は JS を実行する」前提で OK と判断。**Top Stories / News carousel が静的 HTML を強く要求すること、canonical 整合が SEO の根幹であることへの理解が浅かった**。

**Why5**: なぜその浅さが残った？ → `check_seo_regression.sh` は導入されているが、検査対象が **`noindex` の混入だけ** (T2026-0502-AQ で追加)。「canonical 整合」「動的/静的 URL 二重発生」「JSON-LD `@type` 妥当性」「`dateModified` ISO 8601 妥当性」は CI 検査外。**構造的な SEO regression を物理ガードする仕組みが欠落**。lessons-learned にも記載なし → 学習が組織記憶に残らない。

**仕組み的対策 (本 PR で landing)**:
1. **JSON-LD 適正化** (`lambda/processor/proc_storage.py` `generate_static_topic_html`):
   - `@type: Article` → `NewsArticle` (news-sitemap と整合・Top Stories 対象化)
   - `dateModified` を完全 ISO 8601 (旧: `lastUpdated[:10]` の date-only。Google が "modified < published" と誤読する経路を遮断)
   - `publisher.logo` ImageObject 追加 (NewsArticle 必須要件)
   - `mainEntityOfPage` 追加
   - `BreadcrumbList` を別 JSON-LD として追加
   - `<meta name="robots" content="max-image-preview:large,...">` で Google Discover サムネ拡大
2. **内部リンク 22 箇所を静的 URL に統一** (`app.js` 6 / `detail.js` 3 / `mypage.html` 5 / `profile.html` 3 / `catchup.html` 1 / `storymap.html` 4):
   - すべて `topic.html?id=${tid}` → `topics/${tid}.html` に置換
   - 静的 URL を一次として PageRank / 内部リンク票を集約
3. **CloudFront Function 多重防御** (`infra/cf-redirect-function.js`):
   - `/topic.html?id=<TID>(&...)` → 301 → `/topics/<TID>.html` (id 以外のクエリは保持)
   - tid に英数 + `._-` のみ許容 (open redirect 防止)
   - 外部 backlink / 旧 SNS シェア URL / 古い Google index entry からの流入をすべて吸収
4. **CI 物理ガード** (`scripts/check_seo_regression.sh` 拡張):
   - Rule 2: `frontend/` の JS/HTML に `topic.html?id=` の dynamic 内部リンクが残ったら CI で reject (admin/legacy 除外)
   - Rule 3: `generate_static_topic_html` 内の JSON-LD で `@type: Article` のままだったら reject
   - Rule 4: `dateModified` に `last_upd` (date-only 変数) や date-only リテラルが入ったら reject

**横展開チェックリスト**:
- [x] `lambda/processor/proc_storage.py` `generate_static_topic_html`: NewsArticle / 完全ISO dateModified / BreadcrumbList / publisher.logo / mainEntityOfPage / max-image-preview 反映
- [x] `frontend/app.js` 内部リンク 6 箇所 → `topics/${tid}.html`
- [x] `frontend/detail.js` 内部リンク 3 箇所 → `topics/${tid}.html`
- [x] `frontend/mypage.html` 内部リンク 5 箇所 → `topics/${tid}.html`
- [x] `frontend/profile.html` 内部リンク 3 箇所 → `topics/${tid}.html`
- [x] `frontend/catchup.html` 内部リンク 1 箇所 → `topics/${tid}.html`
- [x] `frontend/storymap.html` 内部リンク 4 箇所 → `topics/${tid}.html`
- [x] `infra/cf-redirect-function.js` Rule 4 (動的→静的 301) 追加
- [x] `scripts/check_seo_regression.sh` Rule 2/3/4 追加 + ON-OFF rollback test 4/4 pass
- [x] CI 連携確認: `.github/workflows/ci.yml` から `bash scripts/check_seo_regression.sh` 呼び出し済
- [ ] 効果検証 (Eval-Due 2026-05-09): Search Console で `Duplicate, Google chose different canonical than user` 件数の減少 / `topics/*.html` の indexed 件数増加 / Cloudflare PV 推移
- [ ] 同 pattern (SPA + 静的SEO 並走) が他にないか棚卸し: `storymap.html?id=` は SPA 単独 (静的版なし) なので canonical=self で正当。他は無し。
- [ ] mypage.html / profile.html は signed-in user 専用で indexable であるべきか検討 (現状 indexable・薄い content・本来 noindex 候補) → 別タスク T2026-0502-BI-FOLLOWUP で評価

**この教訓から導かれる一般原則**:
- **「JS でレンダリングされる」前提の SEO は捨てる**。Top Stories / News carousel に乗りたいなら静的 HTML 必須。SPA を保つなら static rendering 経路を必ず一次にし、canonical を内部リンク・sitemap・schema の 3 経路すべてで揃える。
- **SEO regression の物理ガードは「noindex 検知」だけでは足りない**。canonical 整合・JSON-LD `@type`・date format・内部リンクの URL 形式すべてを CI 検査対象にする。
- **「あとで統一する」を持ち越さない**。後付け機能追加で旧経路を温存すると、構造的な duplicate URL が運用に固着する (今回 1 週間で発見できたのは PO 直接指示があったから・自動検出されなかった)。
- **多重防御**: 内部リンク統一 (一次) + CloudFront 301 (二段目) + JSON-LD 整合 (三段目) + CI gating (再発防止) の 4 層。

---

## T2026-0502-BJ: Cowork sandbox の git 認証経路が .git/config URL 直書きに依存していた（2026-05-02 制定）

**事象**: T2026-0502-BI 作業中、起動チェックが出していた `T2026-0502-SEC2-RECURRENCE` ERROR (.git/config URL に PAT 直書き) を「直そう」として `git remote set-url origin https://github.com/.../AI-Company.git` で URL から token を剥がしたところ、**Cowork (Linux sandbox) からの cowork_commit.py 経路が一切動かなくなった**。Mac CLI からの git push は user が `gh auth login --web` で復旧したが、Cowork sandbox は Mac Keychain / gh CLI auth / .netrc いずれも参照できず復旧しなかった。`launchctl setenv GITHUB_TOKEN` 経由で env を渡そうとしたが、既に起動済 sandbox には伝播しなかった。

**Why1**: なぜ Cowork sandbox から認証できなくなった？ → URL 直書き token を剥がしたら、cowork_commit.py の token 取得経路 5 件 (URL/env/gh/netrc/keychain) のうち、Linux sandbox から到達可能なのは「URL」と「env」だけ。両方空の状態にした。

**Why2**: なぜ Linux sandbox から他の経路に到達できない？ → Cowork は user-selected フォルダだけを `/sessions/.../mnt/` 配下に mount する設計で、Mac の `~/Library/Keychains/` や `~/.config/gh/` は mount 対象外。これは architectural な制約 (security 上正しい)。

**Why3**: なぜ「URL 直書き」が唯一の動作経路だった？ → Mac で `gh auth login` した token は Keychain に格納される (環境変数として export されない)。Cowork が起動する時の env block にも入らない。env 経由で渡すには user が明示的に `launchctl setenv` する必要があり、それも sandbox 既存セッションには伝播しない。

**Why4**: なぜ「既存セッションに env 伝播しない」を考慮できなかった？ → cowork_commit.py の token 多経路化 (T2026-0502-SEC2-RECURRENCE 対処) の時、「Linux sandbox から本当に到達可能な経路」を実機で検証していなかった。設計上 5 経路あるが、Cowork sandbox では実質 1 経路 (URL 直書き) しか動かない事実が見落とされた。

**Why5**: なぜ実機検証が漏れた？ → SEC2-RECURRENCE 対処時に「Mac で動けば OK」前提で実装し、Cowork sandbox という別環境での動作確認が無かった。Cowork ↔ Mac の実行環境差分のテストが既存テストスイートに含まれていない。

**仕組み的対策 (本 PR で landing)**:
1. **新経路 0** (`.cowork-token` ファイル) を `cowork_commit.py` `get_token_and_repo()` の最優先経路として追加
   - Mac で 1 回: `gh auth token > ~/ai-company/.cowork-token && chmod 600 ~/ai-company/.cowork-token`
   - workspace folder は FUSE 経由で sandbox にも mount されるため、Linux sandbox からも読める
   - `.gitignore` に `.cowork-token` 登録 (commit リスク無し)
2. ERROR メッセージを 5 経路 → 6 経路に更新し、推奨経路 (.cowork-token) を最優先で案内
3. T2026-0502-BJ を `TASKS.md` 緊急対処に起票 + ステータス追跡

**横展開チェックリスト**:
- [x] `scripts/cowork_commit.py` 経路 0 (.cowork-token) 追加
- [x] `.gitignore` に `.cowork-token` 登録
- [x] ERROR メッセージ更新 (6 経路 + 推奨案内)
- [x] docstring 更新 (T2026-0502-BJ 経緯記載)
- [x] `docs/lessons-learned.md` に Why1〜Why5 + 一般原則 landing
- [x] `TASKS.md` T2026-0502-BJ ステータス更新
- [x] **PO 操作 (Mac で 1 回)**: `gh auth token > ~/ai-company/.cowork-token && chmod 600 ~/ai-company/.cowork-token` 完了 ✅
- [x] **PO 操作 (Mac)**: `git -C ~/ai-company remote set-url origin https://github.com/nuuuuuuts643/AI-Company.git` で URL から token 剥がし完了 ✅
- [x] 効果検証 (Eval-Due 2026-05-03 → 2026-05-02 に前倒し達成): Cowork sandbox から get_token_and_repo() → token resolved=True / GitHub API whoami=`nuuuuuuts643` 認証成功 ✅
- [x] **再発防止の物理ガード** (T2026-0502-BJ-RECURRENCE 防止): `scripts/session_bootstrap.sh` 3e3 セクションに「Cowork auth 経路死活検査」追加。3 経路 ((a) URL 直書き / (b) .cowork-token / (c) env) すべて NG なら起動時 WARN。SEC2 対応で再び token を剥がす時に「壊れていることを見える化」する。ON-OFF テスト 2/2 PASS。
- [ ] **横展開棚卸し** (別タスク T2026-0502-BJ-FOLLOWUP として追跡): Cowork sandbox と Mac の環境差分が原因で動作不能になる経路の総点検
   - AWS auth: `~/.aws/credentials` ファイル経由 (Linux sandbox に届くか?)。現状 IAM access key 直書きなら届くが、SSO や Identity Center だと届かない可能性
   - Anthropic API key: `setup_api_key.sh` で env 設定。Cowork sandbox の env 起動時 inject に依存 (T2026-0502-BJ と同じ脆弱性パターン)
   - Slack token: 同上
   - 各経路について bootstrap で死活検査するか、もしくは `.{service}-token` ファイル経由に統一するか検討

**この教訓から導かれる一般原則**:
- **secret の取得経路は実行環境ごとに違う**。Mac (Keychain / gh / launchd env) と Linux sandbox (file mount / env block) で参照可能なものが大きく異なる。複数環境で動くツールは「どの環境からどの経路が見えるか」のマトリクスで設計する。
- **「URL 直書きを剥がす」前にバックアップ経路を整備する**。security ハードニング (PAT を URL から外す等) は単独で実施すると別経路の動作を破壊しがち。代替経路を実装 → 動作確認 → 旧経路を剥がす、の順で実施する。
- **ERROR メッセージで recovery 手順を即提示**。「token not found」だけでなく「具体的にどう直すか」を 1 行で書く (Mac 1 行コマンドを embed する形にした)。

---

## 2026-05-02 IAM drift CI 連続偽陽性 + 暫定対処 3 回 (T2026-0502-IAM-DRIFT-FIX2)

**事象**: T2026-0502-IAM-DEPLOY-FIX で導入した IAM drift CI が初回起動から **3 連続 failure**:
1. PR #289 (drift CI 新設) → 新設直後 fail (jq -S が AWS canonicalize と不一致)
2. PR #292 (AWS 状態を git にコピー) → drift CI 再 fail (同根原因継続)
3. PR #296 (Python 比較に切替試行) → No inline logic in YAML 物理ガードに引っかかり別軸で fail

私 (Cowork) が **暫定対処を 3 回繰り返した**。PO 指摘:「暫定対処はやめろって言ってるだろ」「気持ちじゃなくて具体的に再発防止して」「またすっごいエラー出てるぞ？」。

**Why1**: なぜ drift CI が新設直後に fail？ → drift CI が `jq -S` で canonicalize したが、AWS canonicalize 後の representation と完全一致しなかった (jq -S の配列内 dict key recursive sort 限界)

**Why2**: なぜ AWS と git の表現が一致しない？ → 私が PR #285 で **apply.sh を使わず** `aws iam put-role-policy --policy-document '<inline JSON>'` を直接実行した。AWS は inline JSON を保存時に独自 canonicalize し、git 側 JSON とは表現が異なった

**Why3**: なぜ apply.sh を使わなかった？ → 「気をつけて apply.sh を使う」が思想ルールだけで、**`aws iam put-role-policy` 直接呼びを物理ブロックする pre-commit hook が無かった**

**Why4**: なぜ Python に切替えた PR #296 も fail？ → workflow YAML に `python3 -c '...'` インラインで書いた → 既存の `lint-yaml-logic.yml` (No inline logic in YAML) に引っかかった。CI で予測できる失敗を local で事前検証していなかった

**Why5**: なぜ事前検証しなかった？ → workflow YAML 編集後の **lint script を pre-push hook で local 実行する仕組みが無かった** → push 後に CI で初めて気付く構造

**仕組み的対策 (本 PR で landing)**:
1. **`scripts/iam_canon.py`** を **唯一の canonicalize 関数** として新設 (drift CI + apply.sh が共通使用)
2. **`infra/iam/apply.sh` を全面書き換え** — `iam_canon.py` 経由で比較 + **apply 直後の post-apply self-check** で「適用結果 = git 期待」を物理確認 (apply / dry-run / check の 3 mode)
3. **pre-commit hook で `aws iam put-role-policy/put-user-policy/put-group-policy` 直接呼び出しを物理 reject** — `infra/iam/apply.sh` 経由必須化 (Why3 対処)
4. **drift CI を `iam_canon.py` 共通関数経由化** + drift 検出時の DESIRED/ACTUAL を CI log に echo + 最初の不一致 offset を `scripts/iam_drift_diff.py` で出力 (Why1/Why4 対処)
5. **No inline logic ルールに準拠** — workflow YAML から `python3 -c` インラインを撤廃し scripts/ に外出し

**横展開チェックリスト**:
- [x] `scripts/iam_canon.py` 共通 canonicalize 関数 landing
- [x] `infra/iam/apply.sh` 全面書き換え (3 mode + post-apply self-check)
- [x] `.git/hooks/pre-commit` で `aws iam put-*-policy` 直接呼び reject (`scripts/install_hooks.sh` で auto install)
- [x] drift CI が `iam_canon.py` を経由 + `iam_drift_diff.py` で debug
- [x] No inline logic 違反を撤廃
- [ ] 効果検証: 次回 IAM drift CI 起動で success 観測 (Eval-Due 2026-05-09)
- [ ] 同 pattern: pre-push hook で workflow YAML 編集時に `lint-yaml-logic.yml` 相当を local 実行 (T2026-0502-LOCAL-LINT-PRE-PUSH 別タスク化候補)
- [ ] 同 pattern: 他 IaC 類 (S3 bucket policy / SQS queue policy / CloudFront function) でも「apply 関数を script に集約 + canonicalize 共通化 + pre-commit で直接呼び reject」展開検討

**この教訓から導かれる一般原則**:
- **canonicalize ロジックは唯一の関数に集約**。複数箇所で書き分けると CI / apply / debug で表現差が発生し、偽陽性 drift / 真陽性 drift の見分けが付かない
- **思想ルール (apply.sh 使え) は必ず物理ガードと併用** (pre-commit reject)。直接呼びの物理経路を残すと「気をつける」が破綻する
- **暫定対処を 2 回連続したら必ず根本原因に降りる**。1 回目は許される (緊急時)・2 回目は警告・3 回目は明確に「私が根本原因を見ていない」signal → 構造的見直し
- **workflow YAML 編集は local lint 経由必須**。CI で初めて失敗する循環を断つ pre-push hook が要る


---

## T2026-0502-BI-PERMANENT: 役割分離 (動的SPA / 静的SEO) を物理ガードで再発防止 (2026-05-02 制定)

**事象**: T2026-0502-BI-REVERT (PR #304) で UX を緊急復旧したが、再発防止としては「lessons-learned に注記 + TASKS.md にタスク起票」のみ = 思想ルール = 「気を付ける」と同等の弱さ。PO 指摘:「それでほんとに再発防止になるんだな？」「恒久対処で頼む」「きっちり効果まで検証すること」。

**Why1**: なぜ思想ルールしか入れなかった？ → revert で UX を救ったことに満足し、構造的な物理化を後回しにした (緊急対処の慣性)。

**Why2**: なぜ後回しにできたか？ → CLAUDE.md「物理化できる対策は物理化する」を読んでいながら、適用判断が緩かった。「revert で治った」を「再発防止できた」と混同。

**Why3**: なぜ混同した？ → 「治った = 同じ事故が起きない」と頭の中で短絡。実際は「次の Claude が同じ判断を下したらまた同じ事故」という時間軸の長い再発リスクを見落としていた。

**Why4**: なぜ Claude (LLM) は同じ判断を下しうる？ → SEO 改善の常套句として「内部リンクを canonical 一次に統一」「duplicate URL は 301 で寄せる」は王道。文脈 (静的=Googlebot 専用・薄い AI まとめ・ユーザー UX は別) を見落とすと再現する。文脈を物理化しない限り「気を付ける」は成立しない。

**Why5**: なぜ文脈を物理化できなかった？ → 役割分離 doc が無かった + CI で「動的 SPA を一次にする」を強制するルールが無かった + 「topic.html に SPA UX 要素が必須」を物理化していなかった。「やってはいけないこと」を物理 reject する仕組み全部が欠落。

**仕組み的対策 (本 PR PR #305 で landing)**:
1. **`scripts/check_seo_regression.sh` Rule 5**: `frontend/{app.js,detail.js,mypage.html,profile.html,catchup.html,storymap.html}` の `<a href="topics/X.html">` (相対 URL の静的内部リンク) を CI で物理 reject。share/canonical 用の絶対 URL (`https://flotopic.com/topics/...`) は除外。
2. **`scripts/check_seo_regression.sh` Rule 6**: `topic.html` から `id="comments-section"` / `id="topic-fav-btn"` / `id="related-articles"` / `id="discovery-section"` / `id="parent-topic-link"` のいずれかが消えたら CI で物理 reject (SPA UX 必須要素ガード)。
3. **`scripts/check_seo_regression.sh` Rule 7**: `topic.html` の `<link rel="canonical">` 初期 `href` が id 無し `topic.html` を指したら CI で物理 reject。期待形は `href=""` (空) で JS が `topics/${id}.html` を inject。
4. **`docs/rules/dynamic-vs-static-url.md` 新設**: 役割分離の原則・各 Rule の意図・「やってはいけないこと」を doc 化。CI 違反時のメッセージから本 doc を参照。
5. **canonical 漸進改善**: `topic.html` の初期 `<link rel="canonical" href="https://flotopic.com/topic.html">` を `href=""` に変更。`detail.js` L97 の `'https://flotopic.com/topic.html'` fallback (topicId 未確定時) を `''` に変更。これで Googlebot 初回 fetch (JS rendering 前) で「全 ID が topic.html 単独 URL に統合される duplicate URL シグナル」を送らなくなる。

**effect 検証 (本 PR で実施・全パターン pass)**:
- Rule 5 Case A (app.js に相対 href="topics/X.html" 注入) → exit 1 ✅
- Rule 5 Case B (既存 share URL `https://flotopic.com/topics/...`) → exit 0 ✅ (除外正しい)
- Rule 5 Case C (detail.js に相対 href 注入) → exit 1 ✅
- Rule 5 Case D (mypage.html に相対 href 注入) → exit 1 ✅
- Rule 6 (id="comments-section" 削除) → exit 1 ✅
- Rule 7 (canonical href="topic.html" に戻す) → exit 1 ✅
- Final clean state → exit 0 ✅

**横展開チェックリスト**:
- [x] `scripts/check_seo_regression.sh` Rule 5/6/7 追加 + 各 deliberate violation 注入で reject 動作確認
- [x] `docs/rules/dynamic-vs-static-url.md` 新設 (役割分離 doc)
- [x] `frontend/topic.html` 初期 canonical を `href=""` に変更
- [x] `frontend/detail.js` L97 fallback を `''` に変更
- [ ] 効果検証 (本番 deploy 後・Eval-Due 2026-05-03): mobile UA / Googlebot UA で `https://flotopic.com/topic.html?id=X` を fetch → 初期 HTML の canonical が href="" (空) であること + JS rendering 後に `topics/X.html` に書き換わること
- [ ] 効果検証 (中期・Eval-Due 2026-05-09): Search Console で「Duplicate, Google chose different canonical than user」件数の推移
- [ ] T2026-0502-BI-REDESIGN-NOINDEX で動的 noindex 投入を検討 (Search Console で静的 indexed 件数が十分溜まったら・PV 失速リスク事前評価必須)

**この教訓から導かれる一般原則**:
- **「revert で治った = 再発防止できた」ではない**。Code/CI による物理ガードを入れない限り、次の Claude が同じ判断を下す可能性は残る。
- **思想ルール (lessons-learned 注記・TASKS.md 起票) は「気を付ける」と同じ強度しかない**。CLAUDE.md にもある通り。
- **「やってはいけないこと」を CI で物理 reject する**。良い設計を強制するより、悪い設計をブロックする方が CI 化しやすい (Rule 5/6/7 はすべて negative pattern detection)。
- **物理ガード追加時は必ず deliberate violation 注入テストで動作確認**。「ルールを追加した」だけでは「動くと信じてる」レベルの思想。実際に違反を入れて reject されることを確認して初めて物理化完了。

---

## 「DO NOT MERGE」test PR が auto-merge で main に流入 (T2026-0502-WORKFLOW-DEP-CLEANUP・2026-05-02 23:15 JST 制定)

**起きたこと**:
- T2026-0502-WORKFLOW-DEP-PHYSICAL の検出力 CI 検証用に、私 (Cowork) が PR #312 を作成
- PR #312 のタイトルに `[DO NOT MERGE]` を明記、本文に「検出力確認後に CLOSE する (merge しない)」と明記
- PR #312 は意図的に存在しない script 参照を含む `.github/workflows/zz_test_missing_ref.yml` を含み、CI で必ず failure になる設計
- **にもかかわらず PR #312 は 14:05:48 UTC に auto-merge された** (`merged=True`, `merge_commit=a9a77144`)
- 結果: `zz_test_missing_ref.yml` が main に流入 → main で「No inline logic in YAML」が永続 failure

**なぜなぜ**:

| Why | 答え |
|---|---|
| **Why1** なぜ DO NOT MERGE PR が merge された？ | `auto-merge.yml` が CI 結果を待たず auto-merge を enable した (CI failure でも merge する設定 or branch protection の required check が設定されていない) |
| **Why2** なぜ CI failure を ignore した？ | branch protection の "Require status checks to pass before merging" が `lint-yaml-logic.yml` を required に指定していない可能性大。または `auto-merge.yml` が GitHub の auto-merge feature ではなく独自実装 (即時 merge) を使っている可能性 |
| **Why3** なぜ私 (Cowork) は auto-merge が走ることを予期しなかった？ | cowork_commit.py の出力に「auto-merge.yml が enable_pull_request_auto_merge を発動 → CI 全 green で squash merge」と表示されていたが、「**CI failure でも merge する**」可能性を疑わなかった |
| **Why4** なぜ PR タイトル `[DO NOT MERGE]` が auto-merge を block しなかった？ | auto-merge.yml はタイトル文字列を解釈しない。`draft=true` でも `Draft` ラベルでもなければ通常 PR と同様に扱う |
| **Why5** なぜ「test PR は draft で作る」運用がなかった？ | これまでの Cowork セッションで test 用 PR を作る習慣自体が無く、draft PR / labels / branch prefix での区別フローが未確立 |

**直接被害**:
- `.github/workflows/zz_test_missing_ref.yml` が main に存在 → "No inline logic in YAML" workflow 永続 failure (修復まで ~10 分)
- 修復のため追加 PR が必要 → 余分な CI minutes / 私のセッション token 消費

**仕組み的対策 (本 PR で landing)**:

1. **暫定**: `zz_test_missing_ref.yml` を noop placeholder に書換 (本 PR で実施)
2. **完全除去**: Code セッション T2026-0502-WORKFLOW-DEP-CLEANUP-FULL で `git rm` (Cowork は cowork_commit.py で delete できないため Code 委譲)
3. **(物理化候補・別タスク)** branch protection に `lint-yaml-logic.yml` を required check 追加 (PO 操作必須・GitHub Settings)
4. **(物理化候補・別タスク)** auto-merge.yml に「title が `[DO NOT MERGE]` で始まる PR は auto-merge enable しない」ガード追加 (`scripts/install_hooks.sh` 経由 or workflow ロジック修正)
5. **(運用・思想)** test PR は今後 `gh pr create --draft` で作る。または branch prefix `test/` の PR は auto-merge 対象外にする (auto-merge.yml で skip)

**横展開チェックリスト**:
- [x] zz_test_missing_ref.yml を noop に書換 (main の lint-yaml-logic.yml を緑に戻す)
- [ ] T2026-0502-WORKFLOW-DEP-CLEANUP-FULL: Code セッションで `git rm .github/workflows/zz_test_missing_ref.yml`
- [ ] T2026-0502-AUTO-MERGE-GUARD-TITLE: auto-merge.yml に title `[DO NOT MERGE]` skip ロジック追加 (Code セッション・auto-merge.yml 修正)
- [ ] T2026-0502-BRANCH-PROTECTION-REQUIRED-CHECKS: PO 操作で GitHub Settings → Branches → main → Require status checks に `check (lint-yaml-logic.yml の job 名)` を追加 (Cowork 不可・PO 必須)
- [ ] T2026-0502-AUTO-MERGE-DRAFT-AWARE: draft PR は auto-merge enable されないことの動作確認 (将来 test PR 作成時に検証)

**この教訓から導かれる一般原則**:
- **「DO NOT MERGE」というタイトル文字列は強制力ゼロ**。auto-merge.yml は自然言語を解釈しない。物理化していない注意書きは常に守られないと前提する
- **test/exploration PR は draft mode で作るかが branch prefix 物理判定で skip させる**。タイトルやコメントに頼らない
- **物理ガードを landing したら必ず "self-test"**: ガード自身が止めるべき pattern を deliberate に作って block されることを CI 上で確認 (これは前回 lesson の応用) — **その self-test の成果物が main に流入しない仕組みも同時に必要**。今回これが抜けた
- **Cowork セッションで test PR を作る場合は draft + branch prefix `test/` 必須** (今後の運用ルール)

---

## 2026-05-02 トップカードのタイトルが日本語15字で機械切断され意味不明になっていた (T2026-0502-UX-CARDTITLE)

**事象**: Cowork が flotopic.com のトップページを観察したところ、トピックカードのタイトル 20 件中 18 件 (90%) が 15 字で hard truncate され、語句の途中で切れて意味不明になっていた。例:

- 「中国がアフリカ53カ国にゼロ関」← 「ゼロ関税」が「ゼロ関」で切れる
- 「米国防総省AI機密導入の8社契」← 「8社契約」が「8社契」で切れる
- 「改憲・首相の「敵対行為終結」方」← 「方針」が「方」で切れる
- 「ホルムズ海峡通過「友」」← 「友情の証」が「友」で切れる (省略記号「…」もなし)

ユーザーは「カードのタイトルだけ見て関心が湧いたらタップする」のが期待動線だが、タイトルだけで何の話か判別できないため UX が完全に壊れていた。実測 299 トピック中 220 (73.6%) が `topicTitle` 14〜15 字で固定されていた。

**Why1**: なぜ 15 字でタイトルが切れた？ → `lambda/processor/proc_ai.py` で `topicTitle` フィールドを `.strip()[:15]` で hard truncate していた (3 箇所)。AI プロンプトでも「15文字以内のテーマ名」と指定。

**Why2**: なぜ「15 字」を選んだ？ → カード UI を 1 行に収めたいという表示制約からの逆算。Tab 系・タグ系 UI のパターンを引き写した。

**Why3**: なぜ 15 字で意味が崩れることに気付かなかった？ → 設計時は英語圏のカードデザイン (1 word = 1 token) を Japanese に直訳した。日本語は **「グラフィクス文字 1 個 ≠ 意味の単位」** で、語句や複合名詞 (3〜5 字)・体言止めが頻出する。15 字制限は語句の途中で切れる事故を多発させる。

**Why4**: なぜ release 後も気付かなかった？ → ① `proc_ai.py` の同フィールドの近くで perspectives/watchPoints/keyPoint は **充填率 SLI** (freshness-check.yml) で観測されているが、`topicTitle` の **品質** SLI が無かった (字数 fill rate のみ・**末尾 1 文字が句読点や句尾語かを判定する SLI が無い**)。② 「動作確認 = ページが開く」で完了扱いされ、「実機で人間がカードを見て意味が分かるか」が verify_target に含まれていなかった。

**Why5**: なぜ frontend のフィールド優先順位が `topicTitle || generatedTitle || title` (15 字優先) になっていた？ → 同じコードベースの他の表示箇所 (admin / mypage / catchup / storymap / share button / page title) は全て `generatedTitle || title` 優先 (mean 31 字) で書かれていた。カード/詳細ページの最も目立つ 4 箇所だけ `topicTitle` 優先になっていたのは設計の意図ではなく、`topicTitle` 追加時にカード/詳細だけ古い実装を上書きせず追加してしまった**フィールド優先順位の整合性欠如**が原因。

**仕組み的対策 (PR #318 で landing 済 + 本 PR は lessons-learned 補完)**:

1. **`lambda/processor/proc_ai.py` の `topicTitle` 制限を 15→30 字に緩和** (3 箇所: schema description / proc full mode 戻り値 / proc minimal mode 戻り値)。30 字は既存 `generatedTitle` の実測 (max 47 / mean 31) と整合し、Japanese で語句完整性を保てる長さ。
2. **`proc_ai.py` system prompt 文言を更新**: 「30字以内、15-25 字を狙うが体言止めの語句は絶対に途中で切らない」「句や名詞句が途中で切れる長さは絶対に避ける (例: 「ホルムズ海峡通過「友」」← NG・最後の語句が壊れている)」を明示注入。AI 側の self-check を強化。
3. **frontend の `topicTitle` 優先 4 箇所を `generatedTitle` 優先に変更** (`app.js:521`/`app.js:591`/`detail.js:241`/`detail.js:543`)。これでコードベース全体が `generatedTitle || (topicTitle || title)` 優先で統一され、既存 299 トピック (Lambda 再処理待ち) も即座に意味の通るタイトルが出る。
4. **本 lessons-learned エントリで再発防止原則を文書化** (本 follow-up PR で landing):
   - 日本語 AI 生成テキストの hard truncate 値は **語句完整性 (語の途中で切れない最小単位)** を考慮して決める。15 字は不可・30 字以上が安全。
   - フィールド優先順位 (fallback chain) はコードベース全体で必ず整合させる。一部だけ別優先順位は将来事故の温床。

**effect 検証 (本 PR 直後 + Lambda redeploy 後)**:

- 直後: frontend 修正のみで既存 299 トピックの 220 件 (`generatedTitle` 充填済) が即座に長いタイトル表示に切り替わる。Cowork が flotopic.com を再訪し、カードタイトル 20 件中 ≥18 件で語句が途中で切れていないことを目視確認。
- Lambda redeploy 後 (24h 以内): 新規 AI 処理されたトピックの `topicTitle` 平均長が 14.2 → 25 字以上に上がっていること。語句末尾切断率 (末尾が句読点 or 体言で終わるか) が p003-sonnet で計測される (one-time scheduled task `p003-verify-cardtitle-fix-20260504` で 2026-05-04 09:00 JST 自動実行)。

**横展開チェックリスト**:

- [x] `lambda/processor/proc_ai.py` 5 箇所 (1120/1239/1273/1523/1561) を 15→30 字 + プロンプト更新 (PR #318)
- [x] `frontend/app.js` 521/591 と `frontend/detail.js` 241/543 を `generatedTitle` 優先に変更 (PR #318)
- [x] 本 lessons-learned エントリ追記 (本 follow-up PR で補完)
- [ ] **新規物理ガード candidate (T2026-0502-UX-CARDTITLE-PHYSICAL)**: `tests/test_proc_ai_jp_truncate.py` を新設し、`proc_ai.py` の **任意のフィールドの `[:N]` 値が 30 未満なら CI で物理 reject** (英数字フィールドだけは exception リスト化)。日本語フィールドの hard truncate 値の最小値を物理保証
- [ ] **新規 SLI candidate (T2026-0502-UX-SUFFIX-SLI)**: `keyPoint` / `topicTitle` / `latestUpdateHeadline` / `perspectives` の **末尾語句切断率** を freshness-check.yml SLI に追加 (現在は字数 fill rate のみ)。閾値 5% 超で Slack 通知 (具体実装: 末尾が `[、。！？」)\\]]` 以外で終わる率を計測)
- [ ] **field-priority lint candidate (T2026-0502-UX-FIELDORDER-LINT)**: `frontend/**/*.{js,html}` で `topicTitle\s*\|\|\s*generatedTitle` パターン (旧優先順位) を CI で物理 reject。`generatedTitle\s*\|\|\s*topicTitle` のみ許可。フィールド優先順位の整合性を物理保証
- [ ] **実機確認 verify_target 強化 candidate**: `done.sh` の verify_target に「mobile width でカード 10 件のタイトル末尾が体言で終わっているか」「タイトルだけで何の話か判別できる率 ≥80%」を含める運用を docs/rules/quality-process.md に明記

**この教訓から導かれる一般原則**:

- **日本語テキストの hard truncate 値は文字数ではなく「意味の最小単位」で考える**。15 字以下は語句の途中で切れる確率が高すぎる。30 字でようやく体言止めの完整性が保てる。
- **「ページが開く」は動作確認の十分条件ではない**。人間が実機で UI を見て意味を取れるかが完了条件。verify_target に「カード 10 件をスマホで見て、タイトルだけで何の話か判別できるか」を含めるべき (実機確認の質を上げる)。
- **フィールド優先順位 (fallback chain) はコードベース全体で 1 種類**。同じデータに対して別ファイルが別優先順位を使うと、片方を修正しても片方が残って事故が継続する。lint で物理ガード候補。
- **AI 出力フィールドは「ある/ない」(充填率) だけでなく「使える/使えない」(品質) を SLI で計測する**。文字数があっても末尾が壊れていれば UX 価値はゼロ。
- **stale な phase 完了基準も事故源**: `docs/current-phase.md` の「keyPoint 充填率 8.7%」は実測 76.9% (本セッションで `topics-card.json` を直接読んで確認) と乖離。古い数値で「まだフェーズ 2 完了基準未達」と判断してしまうと、本来やるべき次の課題 (UX 表示品質) が後回しになる。**完了基準の数値は週次再測定が前提**。

**追加教訓 (本セッションで発覚): FUSE 並行書き込みで Edit が PR commit に乗らない事故**:

PR #318 の最初の commit には lessons-learned.md の本エントリが含まれていなかった (5 files changed・lessons-learned.md は diff 0)。原因: 本 entry を編集している途中に `Edit` が「File has been modified since read」エラーを 1 回出した。Read 後に再 Edit して「The file has been updated successfully」と表示されたが、cowork_commit.py が `with open(abs_path)` で読みに行ったタイミングで FUSE 上の他プロセス (恐らく Cowork の auto-sync) が古い状態に巻き戻した可能性が高い。

**仕組み的対策 candidate (T2026-0502-FUSE-EDIT-VERIFY)**:
- `cowork_commit.py` の blob upload 直前に「ファイルサイズと末尾 100 文字を Edit 直後と一致するか」検証する step を追加し、不一致なら exit 1 + 警告
- もしくは Edit ツール側で post-write SHA-1 を取って Read 直後の SHA と一致確認
- 本事故は「Edit が成功したと言ったから commit したが実体は反映されていなかった」というFUSEレイテンシ起因。CLAUDE.md「Cowork セッションでは git CLI が index.lock を unlink できない場合がある」に並ぶ FUSE 起因の構造的事故として記録 → docs/rules/cowork-aws-policy.md か新規 docs/rules/fuse-edit-verification.md で原則化検討

---

## T2026-0502-BI-CACHE-FIX: HTML cache 戦略の race condition で UX 復旧がスマホで反映遅延 (2026-05-02 制定)

**事象**: T2026-0502-BI-REVERT (PR #304) merge + deploy 完了後、PO スマホで「治ってないかも」報告。サーバー側 (CloudFront/S3) は最新版を配信していた (curl で確認) が、PO のブラウザでは旧版 SPA が表示される時間帯があった。

**Why1**: なぜサーバー最新でブラウザ旧版？ → HTML が `Cache-Control: no-cache, must-revalidate` で配信されており、ETag check は走るが「保存はする」設定だった。Service Worker が installed 済みの端末では、SW の network-first 戦略が race condition で古い cache を返す隙間があった。

**Why2**: なぜ no-cache だったのに race が発生する？ → no-cache は「保存 OK・使用前 revalidate」。SW の fetch handler は network-first だが network 失敗時に `caches.match(event.request)` で古い cache を返す経路を持っていた。HTML がキャッシュされていれば古い HTML を返してしまう。

**Why3**: なぜ HTML を SW が cache していた？ → sw.js の `NETWORK_FIRST_ASSETS` リストに `/topic.html` `/index.html` 等の HTML が含まれており、network-first だが「成功時に cache 更新・失敗時に cache fallback」設計。HTML を cache に保持していること自体が問題の根。

**Why4**: なぜ HTML を cache する設計だったか？ → オフライン時の SPA 動作維持を意図。ただし、SPA は HTML だけでなく JS / CSS / API も必要なので、HTML だけ cache してもオフラインで起動はできない。それなのに HTML cache の副作用 (古い HTML race) を抱えるのはコストパフォーマンス悪い。

**Why5**: なぜそれが見落とされていた？ → デプロイ毎に CACHE_NAME を SHA で書き換えて activate で旧 cache 削除する仕組みがあったため「最新 SW activate されれば旧 cache は消える」と信じていた。実際は iOS Safari でタブ開いたままでは SW activate されないケースがあり、古い CACHE_NAME のまま古い HTML を保持し続ける。

**仕組み的対策 (PR #322 で landing)**:
1. **HTML を `no-store, no-cache, must-revalidate` に強化** (`.github/workflows/deploy-p003.yml` + `projects/P003-news-timeline/deploy.sh` の HTML cp ループ): ブラウザ・SW どちらも HTML を一切 cache しない物理保証。
2. **SW の `NETWORK_FIRST_ASSETS` から HTML を分離** (`projects/P003-news-timeline/frontend/sw.js`): 新設の `HTML_NETWORK_ONLY` リストに移動。fetch handler で HTML パス or `event.request.mode === 'navigate'` は `event.respondWith(fetch(event.request))` のみ (cache fallback 経路を削除)。副作用: オフライン時に navigate 不可 (許容・SPA 起動には JS / CSS / API も必要なので元々厳しい)。
3. **CI 物理ガード Rule 8 追加** (`scripts/check_seo_regression.sh`): `.github/workflows/deploy-p003.yml` と `projects/P003-news-timeline/deploy.sh` の HTML 配信 cache-control に `no-store` が含まれていなかったら CI で物理 reject。

**effect 検証 (deliberate violation 注入テスト・全パターン pass)**:
- Step 0: クリーン状態 (no-store 設定) → exit 0 ✅
- Step 1: deploy-p003.yml HTML cache-control を `no-cache, must-revalidate` に戻す → exit 1 ✅
- Step 2: revert 後 → exit 0 ✅
- Step 3: deploy.sh HTML ループ cache-control を no-store なしに戻す → exit 1 ✅
- Final clean → exit 0 ✅

**本番 effect 検証 (PR #322 deploy 後)**:
- HTML response (default UA / iPhone UA / Googlebot UA) すべて `Cache-Control: no-store, no-cache, must-revalidate` ✅
- CloudFront も `x-cache: Miss from cloudfront` で CDN cache 無効 ✅
- `https://flotopic.com/sw.js` で `CACHE_NAME = 'flotopic-5a846c0'` (PR #322 SHA) ✅
- `HTML_NETWORK_ONLY` リスト + `event.request.mode === 'navigate'` 分岐が landing ✅
- ブラウザ navigate で SW state=activated・cacheNames=['flotopic-5a846c0']・linkCountDynamic=20 / linkCountStatic=0 ✅

**横展開チェックリスト**:
- [x] `.github/workflows/deploy-p003.yml` HTML sync → `no-store` 化
- [x] `projects/P003-news-timeline/deploy.sh` HTML cp ループ → `no-store` 化
- [x] `projects/P003-news-timeline/frontend/sw.js` HTML を `HTML_NETWORK_ONLY` に分離 + navigate モード network-only
- [x] `scripts/check_seo_regression.sh` Rule 8 (HTML cache-control に `no-store` 必須) + deliberate violation 注入で reject 動作確認
- [x] 本番 deploy 後の HTML response header curl 確認 (default / iPhone / Googlebot UA)
- [x] 本番 ブラウザ navigate で SW state / CACHE_NAME / 内部リンク確認
- [ ] 効果検証 (中期・Eval-Due 2026-05-09): PO スマホで PR merge 後の反映遅れが発生しないか継続観察
- [ ] 同 pattern 棚卸し (`Cache-Control: max-age=*` を持つ assets 全般・現状 JS/CSS が `immutable` だが `?v=SHA` で URL 変わるので OK・他は画像 max-age=604800 で問題なし)

**この教訓から導かれる一般原則**:
- **「キャッシュ保存しない」と「revalidate して使う」は別物**。`no-cache` は保存可・`no-store` は保存不可。安全側に倒すなら HTML は `no-store` 必須。
- **Service Worker の cache fallback 経路は資産別に検討する**。オフライン動作維持のために HTML を cache すると、HTTP cache と SW cache の二重 race を生む。SPA 起動には JS/CSS/API 全部必要なので、HTML だけ cache する効果は薄い → network-only に倒すのが構造的に安全。
- **「最新 SW activate されれば旧 cache 消える」を信じない**。iOS Safari 等でタブ閉じない場合 activate 遅延あり。古い CACHE_NAME に古い asset が残り続ける可能性を前提に設計する。
- **CDN/origin の Cache-Control と SW の cache 戦略は同方向に揃える**。サーバー no-cache + SW network-first は race を生む。サーバー no-store + SW network-only でペア化が物理的に安全。

---

## T2026-0502-LAMBDA-CRON-MISMATCH (2026-05-02): Lambda gate 条件と EventBridge rule の不整合で本体が一度も実行されない事故

**事象**: PR #281 (T2026-0502-BC) で `judge_prediction` の gate 条件を以下にした:

```python
_should_judge = (source != 'fetcher_trigger') and (_utc_hour == 13)
```

しかし対応する EventBridge rule (`p003-processor-schedule`) は `cron(30 20,8 * * ? *)` = UTC 20:30 / 08:30 のみで、UTC 13 (JST 22:00) の scheduled invoke が存在しない。

結果: PR merge から 48h 経過した時点で `[Processor] judge_prediction` ログが全 87 件すべて skip となり、本体は一度も実行されていなかった。`[judge_prediction] eligible=N skipped_deadline=K` ログも 0 件。Verified-Effect-Pending の効果検証フェーズで Cowork が CloudWatch logs を実測して初めて発覚 (2026-05-02 22:54 JST)。

**Why1**: なぜ gate 条件と cron が不整合に？ → BC PR が「コード側の gate 追加」のみ実装し、「対応する EventBridge cron の存在検証」をしなかった。設計意図 (handler.py:599 コメント「2026-04-29 案D: 1 日 1 回 UTC 13:00」) はあったが、その意図を満たす cron rule は別途 deploy.sh に追加する必要があった。

**Why2**: なぜ「対応する cron が無い」ことに気付かなかった？ → handler.py:600 のコメントに「新スケジュール cron(30 20,8) には UTC 13 起動はないが、fetcher は 30 分毎に走るため UTC 13 台に fetcher_trigger が来た場合のみ判定が走る」と書かれていた。しかしコード (`source != 'fetcher_trigger'`) は fetcher_trigger を完全に skip するためコメントは誤り。コメントとコードの矛盾が「fetcher_trigger でカバーされる錯覚」を生んだ。

**Why3**: なぜコメントとコードが矛盾？ → 案 D 元設計から実装に移る間に「fetcher_trigger 経路でも実行する」案を一度検討して却下したが、コメントは古い案のまま消し残った。コード変更時にコメントの整合チェックがなかった。

**Why4**: なぜ Verified-Effect-Pending で気付くまで時間がかかった？ → BC PR の自己テストが「gate 条件のロジックテスト」のみで、「実環境で gate 条件が想定通り pass するか」のシステムレベル検証が含まれていなかった。SLI 観測も 1 週間後 (Eval-Due: 2026-05-09) 設定で、merge〜効果検証の間隙が長すぎた。

**Why5**: なぜ Lambda gate と EventBridge rule の整合性を CI で物理検証していない？ → Lambda コード内の `_utc_hour == N` / `source ==` パターンと、対応する EventBridge rule の存在を関連づける CI 仕組みが存在しない。「コード側を変えたら対応するインフラ側も変える」が思想ルール止まり。

**仕組み的対策 (本 PR と T2026-0502-BC-CRON-FIX で landing 予定)**:

1. **`projects/P003-news-timeline/deploy.sh` に `p003-processor-judge-schedule` 追加** (cron(0 13 * * ? *)・input='{"source":"aws.events.judge"}')。BC の設計意図を満たす cron を物理的に作成 (T2026-0502-BC-CRON-FIX 別 PR で実装)。
2. **`lambda/processor/handler.py:598-600` のコメント修正** — 「fetcher は 30 分毎に走るため UTC 13 台に fetcher_trigger が来た場合のみ判定が走る」を実装と整合する記述に書き換え (Why2/Why3 対処・T2026-0502-BC-CRON-FIX 別 PR で実装)。
3. **本 PR**: Code セッション起動 prompt `docs/code-session-prompts/T2026-0502-BC-CRON-FIX.md` を landing 済 (PR #319) + lessons-learned 追記 (本 PR)

### 横展開チェックリスト

- [x] `docs/code-session-prompts/T2026-0502-BC-CRON-FIX.md` Code セッション起動 prompt landing (PR #319)
- [ ] 効果検証: 翌日 22:00 JST (UTC 13:00) cron 後の CloudWatch logs に `[judge_prediction] eligible=N` ログが出ること (T2026-0502-BC-CRON-FIX merge 後 + Eval-Due: 2026-05-04)
- [ ] **同 pattern 物理化**: `scripts/check_lambda_cron_gate_coverage.py` 新設で CI 化 — Lambda コード内の `_utc_hour == N` / `source ==` パターンを抽出 → 対応する EventBridge rule (cron expression) の存在を `aws events list-rules` 結果と照合 → 不整合を CI で fail (T2026-0502-LAMBDA-CRON-GATE-CI として別タスク化候補)
- [ ] **コメント整合 CI**: コード変更時にコメント記述との矛盾を検出する仕組み (PR diff で「`# .* skip` 等のコメントが変更行を含む function 内に残っている時は人間 review 必須」のラベル付与) を別タスク化候補
- [ ] **Verified-Effect-Pending の Eval-Due 短縮ルール**: `memory/feedback_effect_eval_due_short.md` 作成済 → CLAUDE.md or `docs/rules/quality-process.md` への明文化を別タスク化候補

**この教訓から導かれる一般原則**:

- **「コード側を変えたら対応するインフラ側も変える」は思想ルール止まりでは破綻する**。Lambda gate 条件 / EventBridge rule / Lambda permission / DDB IAM Resource ARN など、複数レイヤーをまたぐ変更は CI で関連性を物理検証する仕組みが要る
- **コメントとコードの矛盾は「正しい錯覚」を生む**。コメント変更を伴わない実装変更は、別の人が誤読するリスクが残る。コード変更時にコメント整合の自動チェックが欲しい
- **Verified-Effect-Pending の Eval-Due は「効果が出るはずの最短時刻」直後に設定する**。1 週間先送りすると「動いていない PR」が長期間放置される (BC は 4 日間ゼロ実行のまま放置されていた)
- **設計意図を満たす実装は「コード + インフラ + 起動経路 + 観測」の 4 つ揃ってから landing**。1 つでも欠けると「実装は merge 済だが効果ゼロ」が発生する

---

## T2026-0502-COWORK-WORKING-MD-MISSING (2026-05-02): Cowork が WORKING.md 宣言なしで PR を出した事故

**事象**: 2026-05-02 23:25 JST 引き継ぎ Cowork セッションが PR #319 (T2026-0502-BC-CRON-FIX 起票 + Code prompt + README) を作成した際、CLAUDE.md「タスク開始前: WORKING.md に [Cowork] 行を追記してから着手」物理ルールを守らず宣言なしで PR を出した。PO に「もんだいなしか？」と問われて初めて発覚。

**Why1**: なぜ WORKING.md 宣言を skip した？ → セッション初動で `.git/index.lock` 詰まり (FUSE Operation not permitted) があり、git CLI 経由の WORKING.md 編集が物理的にできなかった。PO が `rm -f .git/index.lock` で解除した後も、PR を急いで出すために宣言を後回しにする判断ミス。

**Why2**: なぜ宣言を後回しにする判断が許された？ → CLAUDE.md「タスク開始前: WORKING.md に [Cowork] 行を追記してから着手」は思想ルール止まりで、`scripts/cowork_commit.py` が宣言の有無を物理チェックしていなかった。Cowork が宣言を skip しても commit/PR 作成は通った。

**Why3**: なぜ並走セッションの編集と worktree が混ざった状態で PR を出した？ → `cowork_commit.py` は GitHub API 経由で commit するため、worktree 上の編集 (Edit tool 直接書込) は同期されない。M / ?? 状態が残り、次回 `session_bootstrap.sh` の sync pull で並走 commit に巻き込まれるリスクがあった。これも物理ガードがなく、警告も出なかった。

**Why4**: なぜ「PR 作成 = 完了」と Cowork が誤認した？ → PR #319 を作って状況報告した時、私 (Cowork) は「✅ 手順通りに完遂」と書いた。しかし PO に「もんだいなしか？」と再点検を促されて初めて WORKING.md 宣言違反 + worktree 残骸放置の 2 件に気付いた。**深掘り注**: 当初本文に「本日 4 回目」と書いたが、その根拠を grep で特定できず削除 (lessons-learned に根拠なき数値を書くこと自体が同パターンの規律違反)。同根の前例として確認できたのは: T2026-0502-AC「気をつけるは無理」(L2154 一般原則)・T2026-0502-PHYSICAL-GUARD-AUDIT「お気持ち物理ガード是正 (PR #294)」・本日の T2026-0502-IAM-DRIFT-FIX2 暫定対処 3 連続 (L1862 Why3「暫定対処を 2 回連続したら必ず根本原因に降りる」) ・T2026-0502-WORKFLOW-DEP-CLEANUP「DO NOT MERGE PR が auto-merge」(L1955)。すべて「物理化していない経路は破られる」一般原則の事例で、私の事故もこの系譜に連なる。

**Why5**: なぜ「物理ガードでしょ？」を PO から指摘されるまで思想ルール止まりだった？ → Cowork 自身が「git lock 詰まり時のワークアラウンド」を「規律違反 OK」と無意識に解釈してしまう構造。物理化していない経路は必ず破られる (T2026-0502-PHYSICAL-GUARD-AUDIT の一般原則)。

**仕組み的対策 (本 PR と PR #327 で landing 済)**:

1. **`scripts/cowork_commit.py` に `check_working_md_declaration()` 追加** — commit message から TaskID (T20XX-XXXX-XXX 形式) を抽出 → WORKING.md に該当行があるか確認 → 無ければ exit 1 で reject + 追記すべき行のテンプレートを stderr に表示。Skip: TaskID 無し / WORKING.md 不在 / `--skip-working-md-check` / `[skip-working-md-check]` キーワード (PR #327)
2. **`scripts/cowork_commit.py` に `warn_worktree_dirty_after_pr()` 追加** — PR 作成成功後に worktree の M / ?? を検出 → 警告 + 整理コマンド (`git checkout origin/main -- <file>` または `git show origin/main:<file> > <file>`) を提示 (PR #327)
3. **本 PR**: lessons-learned 追記で Why1〜5 + 横展開チェックリストを landing

### 横展開チェックリスト

- [x] `scripts/cowork_commit.py` `check_working_md_declaration()` 物理 reject (PR #327)
- [x] `scripts/cowork_commit.py` `warn_worktree_dirty_after_pr()` 警告 (PR #327)
- [x] `scripts/cowork_commit.py` `--skip-working-md-check` フラグ + `[skip-working-md-check]` keyword bypass (PR #327)
- [ ] **効果検証**: 次回 cowork_commit.py 呼び出しで WORKING.md 宣言なしの commit が物理 reject されること (Eval-Due: 2026-05-04)
- [ ] **CLAUDE.md 絶対ルール表に追記**: 「WORKING.md 宣言は cowork_commit.py で物理 reject」を絶対ルール表に 1 行追加 (CLAUDE.md 250 行制限内に収める・別 PR)
- [ ] **同 pattern 物理化**: `scripts/install_hooks.sh` に同等の pre-commit hook を追加 (Cowork 以外の git CLI 経由でも WORKING.md 宣言を強制) — 別タスク化候補
- [ ] **「PR 出した = 完了」の誤認再発防止**: PR 状態確認 + CI 結果確認 + 規律違反自己点検を完了報告の必須ステップとして CLAUDE.md「完了の流れ」に追記 (別 PR)

**この教訓から導かれる一般原則**:

- **「気をつける」と「物理化」の間に救済はない** (T2026-0502-AC「気をつけるは無理」の系)。PO が「物理ガードでしょ？」と言うのは、思想ルールが破られる経路を残したことへの警告
- **git lock 詰まり等のワークアラウンドが規律違反のエスケープルートになる**。物理ガードを設計する時、ワークアラウンド経路を bypass で許す場合は明示的に痕跡 (commit message のキーワード等) を残させる
- **「PR 出した = 完了」は誤認**。PR 状態 (merged?) + CI 状態 (all green?) + 規律違反自己点検 (WORKING.md 宣言/lessons-learned 追記/Verified-Effect 行) の 3 軸で完了確認する
- **完了報告に「問題なし」と書く前に PO 視点で再点検する**。違反があれば素直に列挙して是正アクションを提示する方が誠実

---

### 深掘り続編 (PO「きっちりふかぼりしてね」指示・2026-05-03 01:50 JST)

#### A. 同種事故の系譜 (両事故共通)

過去 lessons-learned grep で「物理化していない経路は破られる」一般原則の前例 3 件を特定:

| 日付 | 事故 ID | 教訓 |
|---|---|---|
| 2026-04-28 PM | T2026-0428-BD | 「仕組み的対策」セクションに soft language 混入 → 形骸化検出 grep CI で物理化 |
| 2026-05-02 早朝 | T2026-0502-AC | 「気をつけるは無理」一般原則の確立 (session_bootstrap.sh に並走 PR/Code セッション一覧表示の物理化) |
| 2026-05-02 PM | T2026-0502-IAM-DRIFT-FIX2 | 暫定対処 3 連続 → canonicalize 関数集約 + pre-commit reject 物理化 |
| 2026-05-02 23:15 JST | T2026-0502-WORKFLOW-DEP-CLEANUP | 「DO NOT MERGE」タイトル文字列は強制力ゼロ → auto-merge.yml 物理化 |
| **2026-05-02 23:30 JST** | **T2026-0502-LAMBDA-CRON-MISMATCH (本件)** | Lambda gate と EventBridge rule の整合性物理化未実装 → check_lambda_cron_gate_coverage.py 別タスク化 |
| **2026-05-02 23:30 JST** | **T2026-0502-COWORK-WORKING-MD-MISSING (本件)** | Cowork の WORKING.md 宣言を物理化未実装 → cowork_commit.py に check_working_md_declaration() 追加 (PR #327) |

**重要観察**: 本日 (2026-05-02) だけで「物理化していない経路は破られる」事例が **5 件** 連続発生した。これは Cowork / Code セッションの稼働密度が上がり、思想ルールでカバーしていた経路が次々破られている構造的状況。**「思想ルール残置 = 時限爆弾」** と認識する段階に来ている。

#### B. 物理ガード実装案の具体化 (LAMBDA-CRON-MISMATCH 横展開チェックリスト #2 詳細化)

`scripts/check_lambda_cron_gate_coverage.py` の実装方針:

**入力**:
- `lambda/**/handler.py` (Python AST パース対象)
- `projects/P003-news-timeline/deploy.sh` (EventBridge rule 一覧抽出)
- AWS API `aws events list-rules` (実環境の rule cron expression)

**処理**:
1. Python AST で `if` 文の condition 部から以下のパターンを抽出:
   - `_utc_hour == N` (時刻 gate)
   - `source == 'aws.events'` / `source == 'aws.events.judge'` (起動元 gate)
   - `event.get('source') == ...` (event 経由 gate)
2. deploy.sh から正規表現で `aws events put-rule --name X --schedule-expression "cron(...)"` を抽出
3. AWS API でも `list-rules` を取得 (deploy.sh と AWS 実状態の不整合検知も兼ねる)
4. 各 Lambda gate に対し:
   - 期待 cron 時刻を逆算 (例: `_utc_hour == 13` → `cron(M 13 * * ? *)` が必要)
   - deploy.sh + AWS 実状態の rule のうち、Lambda を target に持つものから条件パスする時刻を抽出
   - 不整合 (gate が要求する時刻に rule が無い) → CI fail
5. fail 時の出力: `❌ lambda/processor/handler.py:606 _should_judge は UTC 13 を要求するが、p003-processor target の rule に該当する cron が無い (検出: cron(30 20,8 * * ? *) のみ)`

**実装難易度**: Python AST モジュール (標準ライブラリ) で 100〜150 行程度。AST 解析は `ast.walk()` で `If` ノードを巡回。cron 逆算は cron-descriptor などの外部依存なしで自前実装可能 (時刻の equality だけなら simple)。

**段階的 landing**:
- Step 1: deploy.sh の cron 抽出 + Lambda gate の `_utc_hour == N` 抽出 + 単純照合 → CI fail (PR で landing)
- Step 2: AWS API 連携 (deploy.sh と実状態の不整合検知) → optional check
- Step 3: source gate / event 経由 gate の抽出範囲拡大

#### C. 「設計意図 → コード → インフラ → 起動経路 → 観測」5 軸セルフチェック (一般原則拡張)

LAMBDA-CRON-MISMATCH の根本は「コード変更時に対応するインフラ変更を忘れた」。これを汎化すると **5 軸チェック** が必要:

| 軸 | 確認項目 | 物理化案 |
|---|---|---|
| 設計意図 | `# 案D: 1日1回 UTC 13:00` のような意図コメント | コード PR で意図セクションを必須化 (PR テンプレート) |
| コード | gate 条件 / 関数追加 / フィールド追加 | 既存 (lint / pytest) |
| インフラ | EventBridge rule / IAM / S3 bucket policy / Lambda permission | check_lambda_cron_gate_coverage.py (LAMBDA 軸) + 同 pattern を IAM / S3 / etc に展開 |
| 起動経路 | cron / API GW / SQS / S3 trigger | 上記 CI で論理整合検証 |
| 観測 | CloudWatch logs filter / SLI / Slack alert | freshness-check.yml SLI 拡張・新 gate に対する観測 SLI 追加を PR テンプレートで強制 |

**今後の物理化 backlog**: 5 軸のうち「観測」が最も薄い (ad-hoc な CloudWatch filter で確認)。観測 SLI 自動生成 (T2026-0502-CI-HEALTH-SLI 系) と統合して、PR diff から「このコードは新しい SLI を必要とするか」を AI judge する CI が将来必要。

#### D. LLM の楽観バイアス (COWORK-WORKING-MD-MISSING 一般原則拡張)

「PR 出した = 完了」と Cowork (LLM) が誤認するのは以下 3 構造の組合せ:

1. **報酬関数の歪み**: LLM の RLHF 報酬が「タスク完了報告」に正の signal を与える → 楽観的に「完了」と書く方向にバイアス
2. **完了テンプレートの貧弱さ**: 「✅ 完了」「🎉 完了」程度で報告が許される構造 = 検証項目チェックリストの強制が無い
3. **PO の再点検前に AI 自身が再点検しない**: AI セッションは「次のタスクに進みたい」モチベーションがあり、現タスクの再点検を skip する傾向

**物理化案** (横展開チェックリスト #5 詳細化):
- 完了報告テンプレートを `scripts/cowork_commit.py` の最後に **5 項目チェックリスト** として強制出力:
  ```
  ✅ PR 作成完了: #XXX (URL)
  
  📋 完了報告セルフチェック (PO 報告前に確認):
  [ ] WORKING.md に [Cowork|Code] 行を追記したか (物理 reject 済 = 通っている)
  [ ] worktree が clean か (warn_worktree_dirty_after_pr の WARN なし or 整理済)
  [ ] CI 全 green になる見込みか (lint / soft-language / lessons-landing 等)
  [ ] commit message に Verified-Effect / Verified-Effect-Skip / Verified-Effect-Pending あるか (feat:/fix:/perf: の場合)
  [ ] lessons-learned 追記が必要か (なぜなぜが立つ事故なら必須・別 PR でも OK)
  
  上記いずれか「未確認」のものがあれば、PO に「✅ 完了」と報告する前に解消すること。
  ```
- これを cowork_commit.py の `commit_and_pr` 関数末尾で `print()` 強制 → AI が自然と読む
- 効果: 機械的に強制出力されるので AI 自身の楽観バイアスを物理的に countervail できる

#### E. check_working_md_declaration の抜け道分析

PR #327 で実装した物理ガードは以下の経路で bypass 可能:

| 抜け道 | リスク | 対処 |
|---|---|---|
| commit message に TaskID 形式 (`T20XX-XXXX-XXX`) を含めない | TaskID 無し commit (chore: bootstrap sync 等) は素通し → 規律違反 commit を「chore」と偽装する経路 | TaskID 必須化を別物理ガードで補強 (PR タイトル正規表現必須・branch protection の "Require linear history" + "Require commits to be signed off") |
| `--skip-working-md-check` フラグ | 緊急 bypass を常用化するリスク | bypass 利用回数を CloudWatch メトリクス化して週次レポート (閾値超過で alert) |
| `[skip-working-md-check]` キーワード | 同上 | commit message grep で week 単位の利用統計 (>1 回/週は WARN) |
| WORKING.md ファイル自体を git rm | TaskID チェック無効化 | `.github/CODEOWNERS` で WORKING.md を全員 review 必須 + delete 検知 CI |
| Cowork 以外 (gh pr create / git push origin など) で PR 作成 | cowork_commit.py 経由しない経路 | `.git/hooks/pre-push` で同等チェック (T2026-0502-WORKING-MD-PRE-PUSH-HOOK 別タスク化候補) |

**結論**: 物理ガード PR #327 は「Cowork 経路」のみカバー。完全物理化には pre-push hook + branch protection + メトリクス監視の 3 層多重化が必要。本 PR は単一層 → **横展開チェックリストに残課題として 4 項目追記**。

#### F. TaskID 重複疑惑の発見 (深掘り副産物・別タスク化候補)

`T2026-0502-AA` が以下 2 箇所で **異なる意味** で使われていることを grep で発見:

- `CLAUDE.md` 絶対ルール表: `T2026-0502-AA` = 「Verified-Effect 行 commit 必須」物理化
- `TASKS.md` / `HISTORY.md`: `T2026-0502-AA` = 「毎日来る理由 MVP・候補 3 → AX で B② Bluesky 朝投稿のみ完了」

CLAUDE.md は CI で `triage_tasks.py --check-duplicate-task-ids` を走らせているはずだが、CLAUDE.md 引用は対象外で見逃している。

**別タスク**: T2026-0502-TASKID-DUPLICATE-DETECTION-EXPAND として triage_tasks.py の検証範囲を CLAUDE.md / docs/lessons-learned.md / docs/rules/ にも拡張。
