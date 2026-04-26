# ⚡ セッション開始時に必ず最初に実行すること

Claude Codeセッションを開始したら、何も聞かずに以下を順番に実行する。

```bash
# 1. git lockファイルがあれば削除
rm -f /Users/murakaminaoya/ai-company/.git/index.lock

# 2. 未コミットの変更を全てコミット＆push
cd /Users/murakaminaoya/ai-company
git add -A
git commit -m "chore: sync $(date '+%Y-%m-%d %H:%M')" || echo "nothing to commit"
git pull --rebase origin main || echo "rebase failed, continuing"
git push || echo "push failed, continuing"

# 3. CLAUDE.md の変更を検知（変更あれば「再読必須」警告が出る）
git log --oneline -5 -- CLAUDE.md

# 4. 作業競合チェック
cat WORKING.md
```

- `git log --oneline -5 -- CLAUDE.md` に今日の日付のコミットが表示された場合 → **CLAUDE.md の冒頭〜「絶対ルール」セクションまでを全文再読してから続行する（スキップ禁止）**
- `WORKING.md` に自分が着手しようとするファイルが記載されている → そのタスクはスキップ
- エラーが出ても止まらず最後まで実行する
- 完了後に「✅ 起動チェック完了」と報告してからユーザーの指示を待つ。

## ⚡ セッション自動ロール判定（2026-04-26 制定）

`cat WORKING.md` の結果を見て、**ナオヤが何も言わなくても** 自動的にロールを決定する：

| WORKING.md の状態 | 判定ロール | 動き方 |
|---|---|---|
| 「現在着手中」テーブルが空 | **finder** | コード・ログ読み取り → TASKS.md 未着手テーブルに問題を追記（コードは触らない） |
| 他セッションが着手中 + TASKS.md に未着手あり | **implementer** | 未着手から1件取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動 |
| 他セッションが着手中 + TASKS.md 未着手なし | **finder** | 新しい改善点を探して TASKS.md に追記する |

> ナオヤがロールを指定した場合はその指示を優先する。

## ⚡ セッションロール（2026-04-26 制定）

複数セッションを並走させる場合、各セッションに役割を割り当てて事故を防ぐ。

| ロール | できること | できないこと |
|---|---|---|
| **finder** | コード読み取り・TASKS.md 追記・CloudWatch/DynamoDB 確認 | コードファイルの編集 |
| **implementer** | TASKS.md からタスク取得・コード編集・WORKING.md 管理 | TASKS.md への新規タスク追加 |

**finder セッションの動き方：**
1. コードを読んで問題・改善点を探す
2. `TASKS.md` の「未着手」テーブルに追記する（**コードファイルは一切触らない**）
3. 30分ごとに `git pull --rebase && cat TASKS.md` で他セッションの進捗を確認

**implementer セッションの動き方：**
1. `cat TASKS.md` で未着手タスクを確認
2. WORKING.md に宣言 → 実装
3. 完了後は **必ず `bash done.sh T000` を実行**（WORKING.md・TASKS.md削除＋commit＋pushを一括処理）
4. その後 HISTORY.md に詳細を追記する

> **done.sh を使う理由**: 手動でWORKING.md・TASKS.md・commitを個別にやるとクラッシュで途中止まる。done.shは冪等（何度実行しても同じ結果）なので再実行で確実に完了できる。

---

## ⚡ 作業前後ルール（2026-04-26 改訂）

> 着手中管理は **WORKING.md** で行う。CLAUDE.md には書かない。

**タスク開始前（必須・毎回）：**
```bash
git pull --rebase origin main
git log --oneline -5 -- CLAUDE.md   # 今日の変更があれば CLAUDE.md 全文再読（スキップ禁止）
cat WORKING.md                       # 重複ファイルがあればそのタスクはスキップ
```
→ 空きを確認したら WORKING.md に追記 → 即 `git add WORKING.md && git commit -m "wip: [タスク名]" && git push`

**タスク完了後（必須）：**
1. WORKING.md から自分の行を削除する
2. `P003 技術状態スナップショット` テーブルを最新状態に更新する
3. 完了タスクを **HISTORY.md** に移動し、CLAUDE.md には痕跡1行を残す（「完了済みタスク管理ルール」参照）
4. `git add -A && git commit && git push`

**CLAUDE.md 変更検知ルール（重要）：**
- PreToolUse フックが `📋 CLAUDE.md のルールが更新されています` を出したら → **即作業を止めて CLAUDE.md 冒頭〜「絶対ルール」を全文再読してから再開（無視禁止）**
- `⚠️ 他セッションの未取り込みコミットが N 件` → 即 `git pull --rebase` してから再開
- フックが出なくても、git pull で取り込んだコミットに CLAUDE.md の変更が含まれていれば同様に再読する

## 完了済みタスク管理ルール（2026-04-25 制定）

- **完了したらそのセッション中に即 HISTORY.md へ移動する**（時間を置かない）
- CLAUDE.md には完了済みを原則残さない。残してよいのは「同セッション内で副作用確認中のもの」だけ
- 移動後は CLAUDE.md に痕跡1行だけ残す：
  ```
  ### 完了済み（YYYY-MM-DD）
  → HISTORY.md に移動済み（HH:MM JST）
  ```
- HISTORY.md への移動フォーマット: 既存の `### 完了済み（日付）` ブロックをそのまま末尾に append する
- HISTORY.md はセッションをまたいで参照できる唯一の完了履歴。削除禁止。
- 理由: 現在の開発スピードでは1セッション中に数十件完了する。CLAUDE.md に蓄積するとコンテキスト窓を圧迫してセッションが機能しなくなる。

## ⚠️ バグ再発防止ルール（2026-04-25 制定）

過去に実際に起きたバグパターン。毎回確認すること。

### sw.js の CACHE_NAME は手動でバージョン番号を書かない
- ソースは `flotopic-dev` のままにする
- GitHub Actions deploy-p003.yml がデプロイ時に git SHA で自動置換する
- `flotopic-v14` のような手動番号を書いた場合、CI が ERROR で止める

### API URL に 'api/' を重ねない
- `config.js` の `API_BASE` は既に `/api/` で終わっている場合がある
- `API_BASE + 'api/topics.json'` → `/api/api/topics.json` になるので `API_BASE + 'topics.json'` が正しい
- CI がこのパターンを検出して ERROR で止める

### 変更したら即コミット・push する（働きっぱなしで帰らない）
- 作業途中のファイルを working tree に置いたままセッションを終えない
- 複数セッションが並走している場合、別セッションの push と競合する可能性がある
- 30分以上の作業をしたら途中でも `git add -A && git commit && git push` する

### Lambda の `aiGenerated` フラグは成功時のみ True にする
- `aiGenerated=True` はClaudeが実際に結果を返した時だけセットする
- 失敗時に True を書くと「処理済み」と誤認して永遠に再処理されなくなる

### DynamoDB の SK（ソートキー）は FilterExpression に使えない
- `FilterExpression=Attr('SK').eq('SNAP#...')` → ValidationException で落ちる
- SK の範囲絞り込みは必ず `KeyConditionExpression=DKey('SK').between(...)` を使う
- 実際に lifecycle Lambda の `delete_old_snaps` で発生して修正済み（2026-04-25）

### ARCHIVE_DAYS はサービス稼働期間に合わせる
- 稼働2週間のサービスに ARCHIVE_DAYS=30 を設定すると、lifecycle が一切発動しない
- 設定値はサービス年齢（稼働期間）の 1/3 程度を目安にする
  - 稼働1ヶ月未満 → 7日
  - 稼働3ヶ月 → 14日
  - 稼働1年以上 → 30日

### DynamoDB ゾンビトピック（lastArticleAt=0・低スコア）は lifecycle が週次削除する
- `lastArticleAt=0 かつ score < 20` のトピックは低品質ゾンビとして削除対象
- DynamoDB item count が topics.json 件数の **20倍以上** になったら lifecycle を手動実行する
  ```bash
  aws lambda invoke --function-name flotopic-lifecycle \
    --region ap-northeast-1 --invocation-type Event \
    --payload '{}' /tmp/lc.json
  # 約15分後に CloudWatch で 'Lifecycle sweep:' を確認
  ```

### CloudWatch エラーログは最新ログストリームで確認する（2026-04-26 制定）
- `aws logs filter-log-events` の `--start-time` を広く取ると、**修正前のエラーが混入**して誤診断になる
- 正しい手順：
  1. `aws logs describe-log-streams --order-by LastEventTime --descending` で最新ストリーム名を取得
  2. `aws logs get-log-events --log-stream-name <最新ストリーム名>` でその実行だけを見る
  3. 最新デプロイ（GH Actionsの`gh run list --workflow deploy-lambdas.yml`で確認）**より前**の実行のエラーは「修正済みの可能性」として扱う
  4. **新規修正は最新ログストリームで再現したものだけ**を対象にする

### tokushoho.html は廃止済み。絶対に復活させない（2026-04-26 制定）
- `tokushoho.html` は noindex+リダイレクト（→ privacy.html）に設定済み
- アフィリエイト開示は `privacy.html` に統合してある
- commit 56e1be6 がこのルールを破って完全版に復活させた → T010 で再廃止
- **このページに HTML コンテンツを追加したら、即 noindex リダイレクトに戻すこと**
- footer・sitemap・sw.js のキャッシュリストに `tokushoho.html` を追加しない

### インフラ変更（DynamoDB テーブル作成・IAM 権限追加）は deploy.sh 不要
- DynamoDB テーブル作成・IAM ポリシー更新は AWS CLI で直接行ってよい（deploy.sh は不要）
- ただし実行前にナオヤへの事前確認が必要（CLAUDE.md の「deploy.sh」ルールに準拠）
- 実際の変更例（2026-04-26）: `flotopic-notifications` テーブル作成 + IAM `flotopic-least-privilege` に権限追加

### pending_ai.json は processor が管理する。手動で全クリアしない
- `pending_ai.json` の zombie ID クリーンアップは processor が自動で行う（削除済みID = DynamoDB に存在しないIDを除外）
- 手動クリーンアップが必要なのは、processor が全く動いていない状況のみ
- fetcher は pending 件数が80件未満の場合のみ最大20件の orphan（AI未処理トピック）を追加する（2026-04-26 cap実装で肥大化バグ修正済み）
- orphan追加はtopics_deduped（公開対象500件）のみ対象。非公開トピックをqueueに入れない

---

## ⚠️ deploy.sh は直接実行しない（2026-04-25 変更）

**デプロイは GitHub Actions が自動で行う。Claude から deploy.sh を叩かないこと。**

| 変更ファイル | 自動デプロイ |
|---|---|
| `projects/P003-news-timeline/frontend/**` | `.github/workflows/deploy-p003.yml` が S3+CloudFront を自動実行 |
| `projects/P003-news-timeline/lambda/**` | `.github/workflows/deploy-lambdas.yml` が Lambda を自動実行 |

**Claude のやること**: コードを変更 → `git add / commit / push` のみ。pushしたら GH Actions が本番に反映する（2〜4分後）。

**例外**: インフラ新規作成（DynamoDB テーブル作成・Lambda 新規追加等）が必要な場合のみ `deploy.sh` を使ってよい。その場合はナオヤに確認してから実行する。

---

# Team Operating Rules

このプロジェクトでは、Claude Code は以下の順で作業する。

1. 実装担当AI
2. 検証担当AI
3. 完成チェックAI
4. 素材不足洗い出しAI

## 共通原則
- 試作ではなく完成候補として進める
- 実装だけで完了扱いにしない
- 変更後は必ず検証する
- UI、画像、音、演出、文言を勝手に省略しない
- 省略や代替を行う場合は必ず明示する
- 自力で直せるエラーは直して再実行する

## 標準フロー
1. 実装する
2. build / test / lint を実行する
3. 未完了や仮実装を洗い出す
4. 絵・音・UI・演出・文言の不足を列挙する
5. 指摘があれば修正する

## 完了条件
- build または compile が通る
- 主要機能が一通り動く
- 未完了箇所が明示されている
- 素材不足が列挙されている
- 完成度を「試作 / ベータ / 完成候補」で評価する
- `cd projects/P003-news-timeline && npm test` が全テストパスすること（42件、node:test使用）

## 完了報告ルール（必須）
- 「できた」「完了」と言う前に、必ずエラーチェックを実施する
- 具体的には以下をすべて確認してから完了を宣言する：
  1. 実行・デプロイ結果のエラーログを確認する
  2. 期待する動作が実際に確認できている（URLが開ける、関数が返す等）
  3. エラーや警告がある場合は自力で修正してから報告する
- エラーが自力で直せない場合は「完了」ではなく「ここで詰まっている」と報告する

---

# AI-Company CEO システム状態（毎セッション必読）

> このセクションはセッションをまたいで状態を引き継ぐための機械的な仕組み。
> Coworkセッション開始時に必ずここを読んでから作業を始める。

## 会社構造
- **出資者・取締役**: ナオヤ（承認のみ、日常運営はCEOに委任）
- **CEO**: Claude（自律的に会社を動かす）
- **方針**: 指示を待たず毎日前進する。空報告禁止。実行した証拠がないものは完了扱いしない。

## 現在のプロジェクト状態（最終更新: 2026-04-25 夜）

| プロジェクト | 状態 | 備考 |
|---|---|---|
| P001 AI-Company自走システム | **保留** ⏸ | エージェント群のスケジュール停止中（API費用削減のため）。インフラは存在。ユーザー・収益が生まれたら再開。 |
| P002 Flutterゲーム | **開発中** 🔧 | Flutter+Flameで実装済み（50+ファイル）。動作確認未実施。コンセプト: オートバトル×HD-2Dドット絵×ローグライト抽出。 |
| P003 Flotopic | **本番稼働中** ✅ | flotopic.com。7日間240PV(JP92%)。AI要約4セクション形式。sitemap 202URL自動更新。CI全テスト通過。AdSense審査待ち。 |
| P004 Slackボット | **保留** ⏸ | Lambdaデプロイ済みだがSlash Command未設定のため誰も使えない。優先度低。 |
| P005 メモリDB | **保留** ⏸ | DynamoDB稼働中だがエージェント停止中で実質未使用。インフラは残存。 |

## P003 技術状態スナップショット（セッション開始時に必ず確認）

> このテーブルはセッションをまたいで整合性を保つための機械的な記録。
> 作業完了のたびに更新すること。更新しないまま「完了」と言わない。

| コンポーネント | 状態 | 最終更新 | 備考 |
|---|---|---|---|
| CI (.github/workflows/ci.yml) | ✅ 全テスト通過 | 2026-04-25 | YAML バグ修正済み。`npm test` 42件全パス必須 |
| sw.js バージョン管理 | ✅ 自動 | 2026-04-25 | git SHA 自動注入。ソースは `flotopic-dev` のまま触るな |
| CloudFront | ✅ 自動無効化 | 2026-04-25 | push → GH Actions → S3 + CF invalidation（2〜4分） |
| processor AI要約 | ✅ 稼働中 | 2026-04-26 | **4x/day** (T049修正済み。JST 01:00/07:00/13:00/19:00)。MAX_API_CALLS=150。 |
| AI要約カバレッジ | 📈 改善中 | 2026-04-26 | summary69%(316/455)・storyPhase43%(199/455)・imageUrl62%(286/455)。storyTimeline=個別ファイルのみ(意図的設計) |
| DynamoDB SNAP肥大化 | 📉 改善中 | 2026-04-26 | ~742K件。TTL ENABLED。lifecycle週次で30日超SNAP削除中 |
| sitemap.xml / news-sitemap.xml | ✅ 動的自動生成 | 2026-04-26 | 270URL + Google News Sitemap。processor実行時に自動更新 |
| Bluesky 自動投稿 | ✅ 稼働 | 2026-04-25 | 毎日05:32 JST 投稿確認済み |
| 静的SEO HTML生成 | ✅ 本番稼働 | 2026-04-26 | topics/{tid}.html 500件生成済み・CF配信確認済み |
| lifecycle Lambda | ✅ 週次自動実行 | 2026-04-26 | ARCHIVE_DAYS=7・ゾンビ削除・S3孤立ファイル削除 |
| アフィリエイト収益化基盤 | ✅ 実装済み | 2026-04-26 | AFFILIATE_AMAZON_TAG/RAKUTEN_IDをconfig.jsに設定するだけで稼働。ジャンルフィルタ追加済み（T050）。admin.html収益カード更新済み(T057) |
| お問い合わせフォーム | ⏳ DNS伝播待ち | 2026-04-26 | contact.html → p003-contact Lambda。flotopic.com DKIM CNAME×3追加済み・伝播待ち。Lambda環境変数設定済み。伝播後に本番アクセス申請が必要 |
| ストーリー表示 | ✅ 強化済み | 2026-04-26 | T065: フェーズ5段階進捗バー追加・beatをdot+縦線タイムライン形式に刷新・catchupバッジカラー化 |
| proc_ai ストーリープロンプト | ✅ 強化済み | 2026-04-26 | T066: event 20→40文字・transition 15→25文字。standard max_tokens 500→700 |

> 完了済みコンポーネント詳細は HISTORY.md「T032 スナップショット棚卸し」セクションを参照

## 専門AI稼働状況

### 運営エージェント（全スケジュール停止中 2026-04-24〜）
> CEO/秘書/開発監視/マーケ/収益/編集/SEO/X投稿 — 全8本停止中（API費用削減。ユーザー増加後に再開）

### ガバナンスエージェント
| エージェント | スクリプト | スケジュール | 状態 | 報告先 |
|---|---|---|---|---|
| SecurityAI | scripts/security_agent.py | push時(L1/L2) + 毎週月曜8:00 JST(L3) | ✅ 有効 | Slack（CRITICAL時はナオヤさん直報） |
| LegalAI | scripts/legal_agent.py | push時(L2) + 毎月1日(L3) | ⏸ 停止中 | — |
| AuditAI | scripts/audit_agent.py | push時 + 週次 | ✅ 有効 | **ナオヤさん直接報告（CEOを経由しない）** |

#### ガバナンス補助
| ファイル | 役割 |
|---|---|
| scripts/_governance_check.py | 全エージェント共通の自己停止モジュール |
| .github/workflows/governance.yml | 統合ガバナンスワークフロー（L1→L2→Legal→Audit の直列パイプライン）|
| DynamoDB: ai-company-agent-status | 各エージェントのactive/paused/stopped状態管理 |
| DynamoDB: ai-company-audit | 全監査ログの永続保存 |

## 残タスク（ナオヤ手動作業が必要なもの）

- **P002動作確認**（未実施）: `cd ~/ai-company/projects/P002-flutter-game && flutter pub get && flutter run`
- **SES メール検証**: AWSコンソール → SES → us-east-1 → `mrkm.naoya643@gmail.com` 検証。または DNS TXT: `_amazonses.flotopic.com` = `smy0Jk1Xcd84rc7DHAlaKGESjlab/ZxzSkRE3aw7xjw=`
- **待ち**: AdSense審査中（忍者AdMaxで代替中）


## 現在着手中

→ **[WORKING.md](./WORKING.md) を参照**（このセクションには書かない）

## 次フェーズのタスク（優先度順）

### 優先度1: SEO・流入強化（Claude実行可能）
- **SEO強化（被リンク・流入）**: 静的HTMLは実装済み(topics/{id}.html)。次の打ち手: ①Qiita/note/Zennに技術記事を書いてFlotopicへリンク ②Bluesky/X経由でニッチトピックの流入狙い ③「〇〇 まとめ 経緯」のロングテールキーワードを意識したAIタイトル生成改善

### 優先度2: コンテンツ品質（Claude実行可能）
- AI要約カバレッジ向上（スケジュール実行 4x/day で継続改善中）
- velocity=0 の停滞トピック → lifecycle Lambda(ARCHIVE_DAYS=7)が次週月曜に自動整理

### 優先度3: ユーザー体験（Claude実行可能）
- モバイルUX改善（実ユーザー獲得後に重要度UP）
- **表示名・ハンドル名分離**（@メンション・固定プロフィールURL実装時に必要）→ コミュニティ機能が育ってから実装でOK

### 優先度4: 収益化
- AdSense 審査通過後の広告設定切り替え（忍者 AdMax → AdSense）→ 審査中・ナオヤ待ち
- **Amazonアソシエイト申請**（ナオヤ手動）→ 申請後 `config.js` の `AFFILIATE_AMAZON_TAG` は設定済み（flotopic-22）
- **楽天アフィリエイト申請**（ナオヤ手動）→ 申請後 `AFFILIATE_RAKUTEN_ID` に設定
- X 投稿エージェント再開（X API Basic Plan $100/月が必要）→ 収益化後に判断

## 完了済みタスク
→ 詳細は [HISTORY.md](./HISTORY.md) を参照

## 絶対ルール（毎セッション遵守）

- `frontend/` `lambda/` `scripts/` `.github/` のコードは変更しない（CEOエージェントのルール）
- 決まったことは会話で終わらせず即ファイルに書く
- URLの確認・デプロイ確認は自分でやる（ナオヤに聞かない）
- 「書きました」「やります」の宣言は信用されない。ファイルの存在が証拠。
- 空報告禁止。実行した証拠（ファイル変更・ログ・スクリーンショット）を必ず示す

## 開発ルール（一人開発・事故防止）

### 基本フロー
1. コードを変更する
2. `git add / commit / push` → GH Actions が自動で本番反映（2〜4分）
3. 動作確認したい場合は `bash projects/P003-news-timeline/deploy-staging.sh` でステージングに先行反映

### ステージング環境
- **URL**: http://p003-news-staging-946554699567.s3-website-ap-northeast-1.amazonaws.com
- **手動デプロイ**: `bash projects/P003-news-timeline/deploy-staging.sh`
- **本番との違い**: フロントエンドのみ別バケット。Lambda/DynamoDBは本番共有

### CI（自動構文チェック）
- mainへのpush時に自動実行（`.github/workflows/ci.yml`）
- JS構文チェック（node --check）
- Python構文チェック（py_compile）
- APIキーのハードコード検出
- **構文エラーがあれば即気づける。デプロイ前の最低限の安全網。**

## 未解決の問題 / 素材不足

- **P003 AdSense審査待ち** — 申請済み。通過まで数週間かかる場合あり。それまでは忍者AdMaxで代替。
- **P003 グラフデータ蓄積中** — 長期グラフ（1ヶ月〜1年）はデータ蓄積後に意味を持つ。
- **P002 Flutterスプライト素材未作成** — AI生成で後日追加。
- **P002 BGM本番版未作成** — Suno AIで後日生成・差し替え。
- **P002 動作確認未実施** — `flutter pub get && flutter run` をローカルで実行すること。

## 将来アイデア候補（実装タイミングは後）

> 運用設計ドキュメント作成済み → **docs/operations-design.md** 参照（デプロイ安全基準・ロールバック・監視・変更管理ルール）

> インフラ移行戦略ドキュメント作成済み → **docs/infra-migration-strategy.md** 参照  
> （Phase定義・ゼロダウンタイム移行パターン・topics.json肥大化対策・GSI拡張計画・移行判断トリガー指標を記載）

### P003拡張候補: トピック起点SNS機能
Xやインスタは「自分起点でハッシュタグを後付け」する広場型。Flotopicは「トピック起点で人が発言する」映画館型。
- Googleログイン前提（匿名排除）
- トピックページに「このトピックについてどう思う？」入力欄
- トピックがarchived/削除されたらコメントも自動消去 → 燃え広がらない設計
- モデレーションが構造に組み込まれている（人力不要）
- **実装タイミング**: ユーザーが集まってから。今は「発言ゼロの入力欄」になるリスクがある。コメント機能は既にlambda/comments/handler.pyで実装済み。

### P006候補: Flotopic × 株式投資シグナル
Flotopicが「世界の文脈を読む」精度を上げた先に、投資シグナル生成エンジンへの拡張可能性がある。
- Flotopicのベロシティ・エンティティ・トピックライフサイクルは株式シグナルと本質的に同じ情報
- プロ機関投資家はBloombergで同じ情報に月数十万払っている
- 個人投資家向けに「このトピックが急上昇、関連銘柄はこれ」という形で提供可能
- **注意**: 金融情報サービスは規制あり。「投資アドバイス」でなく「ニュース文脈の提供」として設計すること
- 実現条件: Flotopicのデータ精度向上 + ユーザー基盤確立後

## P002 Flutterゲーム 設計概要

→ 詳細は `projects/P002-flutter-game/briefing.md` 参照（174行・コンセプト/システム/収益化/フォルダ構造/作業ガイド記載）

## セッション更新ルール

このファイルの「AI-Company CEO システム状態」セクションは以下のタイミングで更新する：
- 新しい承認が出たとき → 即座に追記
- タスクが完了したとき → 状態を更新
- 新しい問題が発覚したとき → 未解決に追記
- セッション終了前 → 必ず最新状態に更新してから終わる
