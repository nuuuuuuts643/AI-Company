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
- 2026-05-02 T2026-0502-MU-FOLLOWUP: 下流の判定ロジック修正して上流の選定ロジックを忘れる（mode upgrade 上流補完）

---

### 横展開チェックリスト（過去仕組み的対策の landing 検証ルーチン・新設）

| 対策名 | タスク | 確認ファイル | 状態 |
|---|---|---|---|
| mode mismatch 自動検出 | T2026-0502-MU-FOLLOWUP | `scripts/quality_heal.py` | ✅ |
| quality_heal main flow 統合 | T2026-0502-MU-FOLLOWUP | `scripts/quality_heal.py` | ✅ |
| boundary test | T2026-0502-MU-FOLLOWUP | `tests/test_quality_heal_mode_upgrade.py` | ✅ |

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

1. **物理（bootstrap の git エラー観測可能化）**: `scripts/session_bootstrap.sh` の `git pull` / `git push` で `PIPESTATUS[0]` を捕捉し、非ゼロなら `BOOTSTRAP_EXIT=1` を立てて末尾で物理 exit 1。`tail -2` 撤去。FUSE noise filter (`_strip_fuse_noise`) は維持。**実装: PR #159**
2. **物理（main 直 push 物理ブロック）**: `scripts/install_hooks.sh` に `pre-push` hook を追加し、`refs/heads/main` への push を exit 1 で拒否。bypass は `git push --no-verify`（WORKING.md に理由記録必須）。**実装: PR #160**
3. **物理（滞留 commit の retroactive 救済）**: ローカル diverge 状態の commit は cowork_commit.py で salvage ブランチに退避 → PR 化して CI ・ auto-merge.yml の流れに乗せる。**実装: PR #158**
4. **観測（divergence SLI）**: bootstrap 実行ログを CloudWatch / Slack に流して、`git rev-list --count origin/main..HEAD` が 1 を超える状態が連続検出されたら ALERT。タスク化: **T2026-0502-DIVERGE-SLI**（観測）

**メタ教訓**:
- **「物理 / 観測 / 思想」の三分類を git 周辺にも適用する**: PR 側は重装備でも、ローカル → main の経路が「思想」だけになっていれば全体は「思想」と同じ強度。経路の最弱点が全体の強度を決める
- **`|| true` + `tail -N` の組み合わせは実質黙殺**: 終了コードを捨てる + 出力先頭を捨てる の二重で、エラーの観測手段が両方塞がれる。FUSE noise 除去のためにはフィルタリストで個別文字列を除く方が安全（substring 一致のみ・正規表現使わない、という現行 `_strip_fuse_noise` のポリシーを踏襲）
- **「✅ 完了」ログは実際に成功した条件下でのみ出す**: 「失敗してもセッション続行できるよう各ステップは `|| true` で吸収する」というコメントが冒頭にあったが、それと「最後に成功サマリを出す」は両立しない。失敗を吸収するなら成功サマリを出さない、成功サマリを出すなら失敗で exit するのが整合

**横展開チェックリスト**:
- [x] `scripts/session_bootstrap.sh` の git pull/push を `PIPESTATUS` で捕捉 → 失敗時 exit 1（**物理** / PR #159）
- [x] `scripts/install_hooks.sh` に pre-push hook 追加で main 直 push 物理ブロック（**物理** / PR #160）
- [x] 滞留 6 commit を salvage PR で retroactive に救済（**物理** / PR #158）
- [ ] `scripts/auto-push.sh` が main 直 push する設計を撤廃し、cowork_commit.py 経由 PR フローに置換（タスク化: **T2026-0502-AUTOPUSH-PR-FLOW**・**物理** / PR #175 進行中・PR #168 は scope 膨張で close）
- [x] 「auto-sync: session end ...」commit を生成する終了時 hook を特定して、main 直 commit を撤廃（タスク化: **T2026-0502-SESSION-END-HOOK-AUDIT**・**物理** / PR #173 — 犯人は `~/.claude/settings.json` の Stop hook）
- [x] divergence SLI（`git rev-list --count origin/main..HEAD ≥ 2` が 30 分続いたら Slack alert）（タスク化: **T2026-0502-DIVERGE-SLI**・**観測** / PR #171 / #172）
- [x] GitHub branch protection で main の direct push を server-side で拒否（PO 確認案件・タスク化: **T2026-0502-BRANCH-PROTECT**・**物理** / 2026-05-02 GitHub API 直接設定済 — required_status_checks.strict=true / enforce_admins=false / allow_force_pushes=false / allow_deletions=false）
- [x] `scripts/check_lessons_landings.sh` に PR #159 / #160 の物理ガード landing を追加（タスク化: **T2026-0502-LANDING-CHECK-M**・**物理** / PR #169）
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

## T2026-0502-MU-FOLLOWUP: 下流の判定ロジック修正して上流の選定ロジックを忘れる（2026-05-02）

**起きたこと**:
- PR #162 (T2026-0502-MU) で `lambda/processor/handler.py` の `needs_story` 判定に mode upgrade 条件を追加した
- しかし `needs_story` は「processor の処理対象に入ったトピックを再処理するか」を判定するだけ
- `pendingAI=null` のトピックは `get_pending_topics()` / `pending_ai.json` の選定段階でキャンセルされるため、`needs_story` に到達しない
- 実害: `4bf3a46568f1189c` (EU関税, ac=9, summaryMode=standard) が cnt>=6 で full 期待だが、`pendingAI=null` のまま fetcher_trigger 経路で拾われない。1日2回の全件 cron まで待つしかなく効果が遅延

**なぜなぜ**:

| Why | 答え |
|---|---|
| **Why1** なぜ下流修正だけで完了とみなした？ | PR #162 は「needs_story 判定に mode upgrade 条件を追加」という仕様書通りに実装した。上流の pending queue 選定は仕様書に書かれていなかった |
| **Why2** なぜ仕様書に上流補完が書かれていなかった？ | 問題報告者が「processor が mode 不一致を見逃している」という症状から「needs_story 判定が足りない」と診断した。「pendingAI=null で queue に入らない」という上流の制約を分析していなかった |
| **Why3** なぜ上流の制約を分析しなかった？ | 修正を「局所的なロジックバグ」と捉えた。データフロー全体（選定→判定→実行）のどのステップで詰まっているかを「フロー図で考える」習慣がなかった |
| **Why4** なぜデータフロー全体を確認しなかった？ | タスク記述が「needs_story 条件に mode upgrade を追加する」という実装レベルの指示だったため、そのまま実装した。なぜ needs_story を修正するのか？という Why を自問しなかった |
| **Why5** なぜ Why を自問しなかった？ | 「実装指示があれば実装する」が基本動作。「この修正が効果を発揮する経路」を検証しないまま「実装完了 = 問題解決」とした |

**仕組み的対策**（最低 3 つ）:

1. **物理（quality_heal に mode mismatch 検出を追加）**: `scripts/quality_heal.py:find_mode_mismatch_topics()` が DDB scan 済みの metas を再利用して upgrade 候補を発見し `pendingAI=True` にセット。質的な heal だけでなく mode upgrade rescue も同一 cron に統合。**本 PR で実装済**
2. **物理（boundary test で検出ロジック保護）**: `tests/test_quality_heal_mode_upgrade.py` が `find_mode_mismatch_topics` の全境界値を pytest でカバー。閾値変更時に CI で即検出。**本 PR で実装済**
3. **思想（データフロー確認の習慣化）**: 「判定ロジック」を修正する前に「このトピックはどの経路で判定に到達するか？」を必ず確認する。pending queue への投入経路・scan 経路・fetcher_trigger 経路の 3 パスを意識する

**横展開チェックリスト**:
| 項目 | 確認ファイル | 状態 |
|---|---|---|
| mode mismatch 自動検出 | `scripts/quality_heal.py:find_mode_mismatch_topics` | ✅ 本 PR |
| quality_heal main 統合 | `scripts/quality_heal.py` main flow | ✅ 本 PR |
| 二重キューイング防止 (pendingAI=True 除外) | `find_mode_mismatch_topics` pendingAI=True check | ✅ 本 PR |
| boundary test | `tests/test_quality_heal_mode_upgrade.py` | ✅ 本 PR |
| handler.py と論理同期コメント | `scripts/quality_heal.py` docstring | ✅ 本 PR |
