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
- 2026-04-28 PM【複合事象】8 件 + 過去仕組み的対策の実装漏れ棚卸し（buildFilters / CI 連続失敗 / Bluesky 125 ターン / about.html ラベル不整合 / セッション並走 / フェーズ1 定義不足 / TASKS.md 冗長 / 形骸化ルール）
- 2026-04-28 PM【メタ】「仕組みを書いた ≠ 仕組みが動いている」過去対策の landing 検証ルーチン（横展開チェックリスト導入）
- 2026-04-28 E2-4 judge_prediction verdict 0 件（pubDate RFC 2822 silently drop + 7d/5art 閾値が data freshness 上届かない + 旧 META に pending flag 不在の 3 層原因）

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

## judge_prediction verdict 0 件 — 3 層原因（2026-04-28 E2-4 制定）

**起きたこと**: フェーズ 2 で AI 予想 (outlook) の自動当否判定が動いていない発覚。DynamoDB `p003-topics` の META 1068 件のうち `predictionResult=pending` 45 件、`matched/partial/missed`（verdict）は **0 件**。判定パイプラインが書かれてから 1 度も verdict を生成していない状態。

**実測で見えた 3 層原因**:

| 層 | 状態 | 影響 |
|---|---|---|
| ① 閾値 7d/5art | データ最古 outlook が 2.12 日（システム自体が新しい） | 永遠に filter 通過 0 件 |
| ② 旧 META に pending flag 不在 | T2026-0428-J/E で `predictionResult` 追加前の outlook 66 件が flag 無しのまま放置 | filter (`predictionResult==pending`) を素通りで永遠に対象外 |
| ③ pubDate RFC 2822 silently drop | `get_articles_added_after` の parser が ISO/epoch のみ。RSS 由来 `'Mon, 23 Mar 2026 07:00:00'` は `a_dt = None` で continue | 仮に filter 通過しても `len(new_titles) = 0` で skip → verdict 永遠に出ない |

3 層が同時に発生していたため、表面症状は同じ「verdict 0 件」だが、たとえ ① を緩和しても ② で 66 件が抜け、② を backfill しても ③ で全記事が drop される多段ガード状態だった。

| Why | 答え |
|---|---|
| **Why1** なぜ verdict 0 件のまま気付かなかった？ | 「pending=45 件」は SLI 化されているが「verdict 累積=0 件」の SLI が無く、判定ループが空回っているのに正常動作と区別できなかった |
| **Why2** なぜ複数原因が同時に存在した？ | 各層の修正が別タスク (T2026-0428-PRED 当初実装 / T2026-0428-J/E flag 追加) で時系列に行われ、それぞれが別の前提で書かれた。RFC 2822 は `feed_fetcher` 側でしか想定されておらず、判定ロジック側ではノーテストだった |
| **Why3** なぜ pubDate parser が silently drop した？ | except 節で `a_dt = None` にして次の article へ continue する設計。エラーログも出さず、parse 失敗率の SLI も無く、外部観測できなかった |
| **Why4** なぜ閾値 7d/5art が data freshness と乖離していた？ | 設計時にプロダクション運用想定で「予想は 1 週間後に検証する」固定値で書かれた。データが熟してくる前のブートストラップ期 (現在) は閾値を緩めて pipeline を validate するという二段階運用が想定されていなかった |
| **Why5** なぜ「機能は書いた、けど動いている証拠は無い」状態を出荷した？ | 「実装した = 機能している」と認識する LLM 性質。end-to-end に「verdict が 1 件以上発行されたか」を Verified するルールが欠けていた。`docs/rules/quality-process.md` の効果検証は AI 品質と sitemap_reach のみカバーで、judge_prediction は未紐付け |

**仕組み的対策:**
1. **`_parse_pubdate` 共通化 + RFC 2822 対応**: `email.utils.parsedate_to_datetime` を採用。同 commit で boundary test 同梱 (`tests/test_parse_pubdate.py` 15 ケース: None / 空文字 / garbage / ISO Z / ISO offset / ISO naive / epoch 秒/ms/int / 0 / 負値 / RFC2822 GMT / RFC2822 no-tz / RFC2822 +0900 / 全パスで tz-aware を返す)。CLAUDE.md「新規 formatter は boundary test 同梱」適用
2. **閾値段階運用**: handler.py:471 と proc_storage.py:646 の default を `7d/5art → 1d/3art` に下げ、ブートストラップ期で実 verdict を出してパイプラインを validate。コメントで「データが熟したら 3d/5art に戻す」と明記
3. **旧 META への backfill スクリプト**: `scripts/backfill_prediction_pending.py` を新設。outlook あり predictionResult 未設定 (66 件) と過去 backfill (predictionMadeAt=lastUpdated) の両方を対象に `predictionResult='pending'`, `predictionMadeAt = firstArticleAt - 1s` を書き込む。idempotent で再実行可能
4. **`predictionMadeAt` の semantic 修正**: backfill では `firstArticleAt - 1s` を採用（既存記事を「予測以降の証拠」として扱える）。`lastUpdated` を使うと `lastArticleAt < lastUpdated` で記事が全部 drop される pitfall を回避
5. **横展開チェックリスト追加**: 本ファイル下部の表に「pubDate RFC 2822 parser」行を追加し、`_parse_pubdate` の landing を CI 物理検証
6. **TODO (タスク化候補)**: SLI に `verdict_cumulative_count` を追加し freshness-check.yml で 24h verdict=0 を検出する。`_parse_pubdate` を `feed_fetcher.py` 側のパース処理にも横展開（同 bug が潜む可能性）

**横展開すべき他コンポーネント**:
- `feed_fetcher.py` の pubDate 取り扱い → 同パターンの silent drop 有無を grep
- `latestUpdateHeadline` 系も pubDate を読む箇所がある → `_parse_pubdate` 経由に統一すべき
- 「filter で 0 件返るとログも出ない」パターン全般 → 0 件結果の SLI 化が抜けやすい

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

## 2026-04-28 PM【複合事象】8 件まとめ + 過去仕組み的対策の landing 検証（T2026-0428-AX）

**起きたこと**:

1. **buildFilters バグ（カテゴリ消える）** — `frontend/app.js:748` の `visibleGenres = GENRES.filter(g => counts[g]>0)` 系の絞り込みで、`topics` が初期化前 (`[]`) のタイミングに呼ばれると全ジャンルが消滅する。c99baf1 で `visibleGenres = GENRES;` の hotfix。境界値テストが無かったため CI を通って本番で発覚
2. **CI 連続失敗 — 3 種類が同日重なる**:
   - (a) `security_audit.sh` 自身が `sk-ant-` / `AKIA` を grep するための定義行を持つため、ci.yml の「危険パターン検出」が自分自身を検出して落ちる（200f107 / 8d42690 で除外条件追加）
   - (b) `freshness-check.yml` の perspectives 充填率閾値 (60%) を本番が割って Slack 通知が飛び続ける（実態は本番値 20.5% で観測仕様通り、ただし aiGenerated=False バックログが原因で「警告が鳴り続ける状態」が常態化）
   - (c) `content-drift-guard` ジョブの REQUIRED キーワードが旧「AI 7セクション分析」のまま、about.html を 4 軸に書き換えた (25ba39f) ため push のたびに落ちる（本セッションで c9e9a1b 修正）
3. **Bluesky 125 ターン長期セッション** — `bluesky_agent.py` 系の Cowork セッションが 125 ターンに渡って continue を繰り返した。判断が長期化、kill / resume の往復コストが膨大
4. **about.html フェーズラベル不整合** — フェーズラベル「始まり/広まってる/急上昇/進行中/ひと段落」を内部値「発端/拡散/ピーク/現在地/収束」に書き換え（25ba39f）。CI の content-drift-guard と同期せず、CI が落ち続けた（事象 2c と同根）
5. **セッション多数並走・判断コスト増大** — WORKING.md に 3 件の needs-push:yes が滞留（L / AU / AV）、Cowork 1 件 + Code 2 件が同時走行、ナオヤが「止める？再開する？」を判断する往復が頻発
6. **フェーズ 1 完了条件の定義不足** — `docs/project-phases.md` のフェーズ 1 完了条件は「health.json 稼働」「prompt caching」「1PR1task」「session_bootstrap.sh」のみ。develop/main ブランチ分離・git tag によるリリース管理・ロールバック手順が未定義。「main が壊れたら何をすれば戻るか」が言語化されていない
7. **TASKS.md 冗長・重複** — 60+ 件 → 7 件に絞り込み済みのはずが、アーカイブに重複タスク（T2026-0428-N と SLI 9 が二重記載、T2026-0428-AG が T2026-0428-N に統合済みのまま残存、T236 が freshness-check.yml で代替実装済なのに高優先度のまま）が残る
8. **機能していないルール（形骸化）** — CLAUDE.md「変更前に副作用確認（声に出す）」「実装前に全体影響マップ必須（ナオヤに確認）」が物理ガードを伴わず、buildFilters バグ・about.html ラベル変更時のいずれにも作用しなかった。「ナオヤに確認」を Claude が自走モード（feedback_autonomy）で省略するため、テキストルールだけでは動作しない

### なぜなぜ（個別ではなく共通根本原因 1 つに集約）

| Why | 答え |
|---|---|
| **Why1** なぜ 8 種が同日に表面化した？ | 表面的には別事象だが、共通点は「**書いてあるルール / SLI / CI / hook が、実態とズレた瞬間に誰も気付かない**」。lessons-learned の対策が一度書かれてから検証されない。CI も書いた当初の前提のまま固まる |
| **Why2** なぜ書いた対策が検証されない？ | landing 後の「**外部から実行され、結果が観測される**」ループが対策ごとに作られていない。書き手（Claude）は書いた瞬間に完了とみなし、次の事象を追う。ナオヤは個別事象を通報するが、対策の永続的な実装状態は誰も見ない |
| **Why3** なぜ Claude が「書いて完了」してしまう？ | 仕組み的対策の質ゲート（global-baseline §1「外部観測 / 物理ゲート最低 1 つ」）はあるが、**個別対策の landing 検証が完了の定義に含まれていない**。「対策を書いた commit」と「対策が動いていることを観測した commit」が分離していない |
| **Why4** なぜ完了の定義が不十分？ | global-baseline §1 の「完了 = 動作確認済み + 効果検証済み」は **修正対象の「機能」** に対する完了条件で、**対策メカニズム自体** に対する完了条件ではない。「buildFilters の修正は本番 URL で確認」はやるが「対策として書いた CI ジョブが本当に発火するか」は確認しない |
| **Why5** なぜ「対策メカニズムの動作確認」が体系化されていない？ | 対策は事象が起きた直後に書かれ、書いた瞬間は意義が新鮮で動かす意識がある。だが時間が経つと「過去の対策」になり、書いた人（Claude）の context が消えるため、検証する主体がいない。**「対策の自動 health check」が無い**ため、書いたきり放置で fossilize する |

**核心**: 個別事象 (1-8) はすべて「**書いた仕組みが実際に landing しているかを定期検証する仕組みが無い**」というメタ欠陥の表出。

---

### 過去仕組み的対策の landing 検証（本セッションで実施した監査結果）

| 対策の出所（lessons-learned / TASKS） | 内容 | 実装状況 | 証跡 |
|---|---|---|---|
| schedule-task v3 commit-msg hook | `[Schedule-KPI]` 行必須 | ✅ landing | `.git/hooks/commit-msg` に 6 箇所 |
| freshness-check SLI 8/9/10 | keyPoint/perspectives/outlook 充填率閾値警告 | ✅ landing | `.github/workflows/freshness-check.yml:130-180` |
| freshness-check SLI 11 | sitemap_reach（404 検知） | ✅ landing | `.github/workflows/freshness-check.yml:283-360` |
| T236 governance worker AI 品質メトリクス | perspectives/keyPoint 充填率 → Slack | ⚠️ 部分 landing | `_governance_check.py` には実装ナシ。実体は `freshness-check.yml` 側に存在。**T236 の文脈は obsolete** |
| T2026-0428-K env-scripts CI dry-run | `session_bootstrap.sh --dry-run` を GH Actions 日次 | ❌ 未 landing | `.github/workflows/` に該当 yaml 無し |
| T256 AI フィールド層忘れ CI 検出 | input_schema vs handler.py merge ループの突合 | ❌ 未 landing | `.github/workflows/ai-fields-coverage.yml` 無し（`scripts/check_ai_fields_catalog.py` は別物 = カタログ vs schema 突合のみ） |
| T264 cleanup_stale_worktrees.sh | `.claude/worktrees/` 古い作業ツリー自動掃除 | ❌ 未 landing | スクリプト無し |
| T2026-0428-Q success-but-empty 横展開スキャン | fetcher/processor/bluesky/SES/CF 5xx/CI green-skipped 各観測 | ❌ 未 landing | TASKS.md にメモのみ、実装無し |
| 横展開チェックリスト（lessons-learned 内） | 過去対策の自動 health check 一覧 | ❌ 未 landing | 本 commit で新設 |

**気を付ける/注意する 残置検査**: `grep "気を付ける\|注意する" docs/lessons-learned.md` で 3 件のみ hit。すべて「**禁止する側**」の引用文（「『気を付ける』は答えではない」）であり、仕組み的対策に soft language は残っていない。✅ pass

---

### 仕組み的対策（最低 3 つ・物理ゲート / 外部観測 含む・本 commit で実装）

1. **物理ゲート（横展開チェックリスト の常設）**: 本ファイル下部に `### 横展開チェックリスト（過去仕組み的対策の landing 検証ルーチン）` セクションを新設。新規対策を書いたら必ず本表に行を追加し、`実装ファイル` 列にパスを書く。CI で「本表の各行に該当ファイルが repo に存在するか」を `scripts/check_lessons_landings.sh` (新設) で物理検証。**「書いた対策が物理的に存在するか」を grep で機械検証する第一歩**

2. **物理ゲート（content-drift キーワードの 4 軸化）**: 本セッション既に `c9e9a1b` で実施済。`.github/workflows/ci.yml` content-drift-guard ジョブの REQUIRED を旧 7 セクション → 新 4 軸に更新。今後 about.html を再度書き換えるときは `scripts/sync_content_drift_keywords.sh`（要検討）でキーワードを about.html から自動抽出する形に進化させる（タスク化）

3. **外部観測（CLAUDE.md フェーズ 1 完了条件の Dispatch 運用化）**: `docs/project-phases.md` フェーズ 1 完了条件に Dispatch 運用項目（コードセッション同時 1 件・並走 0 件・ナオヤ判断介入ゼロ）を追加。WORKING.md の `[Code]` 行が 2 件以上ある瞬間を `session_bootstrap.sh` が WARNING で出すゲートは既存だが、本表で「フェーズ 1 完了条件」として明示することで、満たすまで次フェーズへ行かない構造ガードを敷く

4. **物理ゲート（ロールバック手順の文書化）**: フェーズ 1 完了条件に「壊れたら何をすれば戻るか」を `docs/runbooks/rollback.md`（新設）として書き、CI で「本ファイルが空でないこと」「`git revert` または `aws lambda update-function-code --function-name <fn> --s3-bucket <prev>` のいずれかが手順に含まれること」を物理検査

5. **物理ゲート（buildFilters 系の境界値テスト）**: `tests/unit/build_filters.test.js` を新設し、`topics=[]` `topics=[{genre:'総合'}]` `counts={}` の 3 ケースで `visibleGenres` が空配列にならないことを assert。CLAUDE.md「新規 formatter は boundary test 同梱」を「新規/変更フィルタ関数」に拡張する形で適用（タスク化・実装は次回小さな PR で）

---

### 横展開チェックリスト（過去仕組み的対策の landing 検証ルーチン・新設）

> 本表は本セッション以後、**新規仕組み的対策を書いたら追記する** 永続テーブル。
> CI の `check_lessons_landings.sh`（次回タスクで実装）が本表を読み、各行の `実装ファイル` パスが repo に存在するかを物理検査する。
> ✅ = 実装済み・✗ = 未実装（タスク化済み）・⚠ = 部分実装。

| 対策名 | 出所 | 実装ファイル | 状態 | 備考 |
|---|---|---|---|---|
| pre-commit ads.txt 整合 | 2026-04-27 ads.txt 欠落 | `.git/hooks/pre-commit` (install_hooks.sh) | ✅ | clone 直後 1 回 install 必要 |
| commit-msg Verified 行 | 2026-04-27 完了の定義 | `.git/hooks/commit-msg` | ✅ | 同上 |
| commit-msg [Schedule-KPI] | 2026-04-28 schedule-task v3 | `.git/hooks/commit-msg` | ✅ | 6 箇所 |
| pre-commit section-sync | 旧 4 セクション drift | `scripts/check_section_sync.sh` | ✅ | hook から呼び出し |
| CI content-drift-guard 4 軸 | 2026-04-28 about.html 4 軸化 | `.github/workflows/ci.yml:215-248` | ✅ | c9e9a1b 修正 |
| CI 危険パターン self-exclude | 2026-04-28 security_audit.sh 誤検知 | `.github/workflows/ci.yml:120-130` | ✅ | 8d42690 |
| freshness-check SLI 1（updatedAt） | production 鮮度 SLI 不在 | `.github/workflows/freshness-check.yml` | ✅ | — |
| freshness-check SLI 8/9/10 | keyPoint 充填率 11.5% 素通り | `.github/workflows/freshness-check.yml` | ✅ | keyPoint/perspectives/outlook 充填率 |
| freshness-check SLI 11 sitemap_reach | sitemap 50/50 件 404 | `.github/workflows/freshness-check.yml` | ✅ | sitemap 到達性 |
| quality-heal 日次 cron | ゴミデータ慢性蓄積 | `.github/workflows/quality-heal.yml` | ✅ | — |
| schemaVersion による自動再処理 | ゴミデータ慢性蓄積 | `projects/P003-news-timeline/lambda/processor/proc_storage.py` | ✅ | L286-313 |
| WORKING.md 8h TTL 自動削除 | 並行タスク事故 | `scripts/session_bootstrap.sh` | ✅ | — |
| needs-push 滞留警告 | Cowork↔Code 連携 | `scripts/session_bootstrap.sh` | ✅ | — |
| env-scripts CI dry-run | 2026-04-28 環境スクリプト hardcode | `.github/workflows/env-scripts-dryrun.yml` | ✗ | T2026-0428-K |
| AI フィールド層忘れ CI 検出 | T249 keyPoint merge 漏れ | `.github/workflows/ai-fields-coverage.yml` | ✗ | T256 |
| cleanup_stale_worktrees.sh | T264 worktree 残留 | `scripts/cleanup_stale_worktrees.sh` | ✗ | T264 |
| success-but-empty 横展開スキャン | 2026-04-28 06 success-but-empty | `scripts/scan_success_but_empty.py` | ✗ | T2026-0428-Q |
| 横展開チェックリスト自動検証 | 2026-04-28 PM 本セッション | `scripts/check_lessons_landings.sh` | ✅ | T2026-0428-BC で landing (commit 1c90ad9) |
| ロールバック手順 runbook | 2026-04-28 PM フェーズ1 完了条件 | `docs/runbooks/rollback.md` | ✅ | T2026-0428-BA で CI 物理検査も landing (commit 2f45555) |
| Dispatch セッション並走 ERROR | 2026-04-28 PM Bluesky 125 ターン | `scripts/session_bootstrap.sh` | ✅ | T2026-0428-BB で WARN→ERROR+exit1 昇格 (commit a2753dd) |
| 形骸化検出 grep CI | 2026-04-28 PM フェーズ1 §D | `scripts/check_soft_language.sh` | ✅ | T2026-0428-BD で landing。仕組み的対策セクションのソフト言語混入を物理検出 |
| コードセッション名規則 WARN | 2026-04-28 PM フェーズ1 §C | `scripts/session_bootstrap.sh` | ✅ | T2026-0428-BF で landing。「作業」「調査」等の空抽象タイトルを WARN |
| buildFilters 境界値テスト | 2026-04-28 PM buildFilters バグ | `projects/P003-news-timeline/tests/unit/build_filters.test.js` | ✗ | T2026-0428-BE 次回タスク |
| keyPoint 不十分上書きガード | 2026-04-28 PM keyPoint 平均 43.8 字 | `projects/P003-news-timeline/lambda/processor/proc_storage.py` | ✅ | T2026-0428-BH で landing。`KEYPOINT_MIN_LENGTH=100` 閾値で `_can_write/_can_set/needs_ai_processing` の incremental ガードを「短すぎる値も空扱い」に拡張 |
| pubDate RFC 2822 parser | 2026-04-28 E2-4 verdict 0 件 | `projects/P003-news-timeline/lambda/processor/proc_storage.py` | ✅ | T2026-0428-E2-4 で landing。`_parse_pubdate` 共通化 + `email.utils.parsedate_to_datetime` 採用。boundary test 同梱 (`tests/test_parse_pubdate.py` 15 ケース) |

---

### メタ教訓

- **「対策を書いた」と「対策が landing している」は別物。** 仕組み的対策セクションは過去には書きっぱなしで終わり、半年後に同じ問題が起きていた。本セッションで「横展開チェックリスト」を導入し、新規対策ごとに 1 行追加 / CI で landing 物理検証する構造を敷くことで、対策の fossilize を物理的に防ぐ
- **「書いた瞬間に新鮮」と「半年後に風化」のギャップを埋めるのは外部観測しかない。** Claude は 1 セッション内に書いた対策を最も認識しているが、次のセッションで context が消える。記憶に頼らず CI / 横展開チェックリスト / lessons-learned 索引で外部から再発見できる構造を維持
- **「ナオヤに判断を仰ぐ」は仕組み的対策ではない。** CLAUDE.md「実装前に全体影響マップ必須（ナオヤに確認）」は形骸化していた。対策は CI/hook/SLI のいずれかで物理化する。「確認する」「気を付ける」「意識する」は本ファイルの仕組み的対策セクションに書かない（global-baseline §6）
- **CI の REQUIRED キーワードはコードと結合度が高い。** about.html を書き換えると CI が落ちる構造は本来「同期するための物理ガード」だが、CI 側の更新を忘れると「永続的に落ち続ける CI」を生む。次の進化は `scripts/sync_content_drift_keywords.sh` で about.html から自動抽出に切り替え、テキスト二重管理を解消する（タスク化）
- **判断コストの増大は事故の前兆。** 「止める？再開する？」と聞かれる頻度がセッションの暴走指標。Dispatch 運用ルール（1 セッション = 1 タスクで完了まで走る）を CLAUDE.md に明文化し、判断介入ゼロをフェーズ 1 完了条件にする

