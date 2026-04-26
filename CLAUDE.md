# ⚡ セッション開始時に必ず最初に実行すること

Claude Codeセッションを開始したら、何も聞かずに以下を順番に実行する。

```bash
# 1. git lockファイルがあれば削除
rm -f /Users/OWNER/ai-company/.git/index.lock

# 2. 未コミットの変更を全てコミット＆push
cd /Users/OWNER/ai-company
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

## ⚡ セッションロール（2026-04-26 制定）

`cat WORKING.md` の結果を見て自動ロール判定（PO指定が最優先）：

| WORKING.md状態 | ロール | 動き方 |
|---|---|---|
| 着手中テーブルが空 | **finder** | コード読み取り→TASKS.md未着手に問題追記（コード編集禁止） |
| 他セッション着手中+未着手あり | **implementer** | 未着手取得→WORKING.md宣言→実装→`bash done.sh T000`→HISTORY.md |
| 他セッション着手中+未着手なし | **finder** | 新改善点を探してTASKS.md追記 |

- **finder**: コード読み取り・TASKS.md追記・CloudWatch確認のみ（コード編集禁止）
- **implementer**: `done.sh` は冪等（何度実行しても同じ結果）。クラッシュ後も再実行で完了できる

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

## 完了済みタスク管理ルール
- 完了直後に HISTORY.md へ移動（時間を置かない）。CLAUDE.md には `→ HISTORY.md 移動済み HH:MM JST` の1行痕跡のみ残す
- HISTORY.md は削除禁止（唯一の完了履歴。append フォーマット: `### 完了済み（日付）` ブロック末尾追記）
- CLAUDE.md に蓄積するとコンテキスト窓圧迫で機能不全になるため即移動が必須

## ⚠️ 設計・実装の根本ルール（2026-04-26 制定）

> **「実装した」≠「動いている」。この前提がなければすべての機能は"理論上動く"状態で出荷される。**

新機能を実装したら以下を必ず実施してから完了とする：

1. **CloudWatchで実際のエラーログを確認**（エラーがないこと）
2. **ユーザー視点でUIを直接操作**（管理者画面ではなく実際の画面を触る）
3. **「時間が経ってから使う」ケースもテスト**（トークン期限切れ・キャッシュ等）
4. **設計の前提を声に出して検証する**：例：「Google News検索フィード = ジャンル精選された記事が来る」→ 本当にそうか？ → 実際にフィードを取得して確認

実装が機能の完成ではない。**実際にエンドユーザーが使えて初めて完了**。

### 過去の設計ミスパターン（再発させない）

| 機能 | 設計の前提（間違い） | 実際 |
|---|---|---|
| ジャンル分類 | Google News検索フィード = ジャンル精選記事 | Googleが別ジャンルの記事を混入 |
| アフィリエイト | ニュース見出し = 商品検索クエリ | 「肝臓がんリスク」でAmazon検索になる |
| Slack通知 | secret名が合っているはず | `SLACK_WEBHOOK_URL` vs `SLACK_WEBHOOK`でずっと404 |
| Bluesky投稿 | S3_BUCKETは設定済みのはず | 未設定で一度も投稿できていなかった |
| コメント削除 | 投稿直後に削除するはず | Googleトークン1時間失効後の削除を想定していなかった |

---

## ⚠️ バグ再発防止ルール（再発させない）

| パターン | ルール |
|---|---|
| sw.js CACHE_NAME | ソースは`flotopic-dev`のまま。CI が手動バージョン番号を検出して ERROR |
| API URL重複 | `API_BASE`は`/api/`で終わる。`+'api/topics.json'`→二重パスになる。CIが検出 |
| Lambda aiGenerated | 成功時のみ True。失敗時 True→「処理済み」誤認で永遠に再処理されない |
| DynamoDB SK | FilterExpression に使えない。KeyConditionExpression で範囲絞り込み |
| ARCHIVE_DAYS | 稼働期間の 1/3 目安（1ヶ月未満→7日, 3ヶ月→14日, 1年以上→30日） |
| ゾンビ削除 | lifecycle 週次自動（月曜 02:00 UTC）。item数がtopics.json 20倍超→手動invoke |
| CloudWatch | 最新ログストリームのみ確認。古いエラーは修正済みの可能性あり |
| tokushoho.html | 廃止済み・復活禁止。footer/sitemap/sw.jsキャッシュに追加しない |
| インフラ変更 | AWS CLI 直接可。ただしPO確認必須（deploy.sh 不要） |
| pending_ai.json | processor が自動管理（zombie ID 除外）。手動クリアは processor 停止中のみ |
| git push | 30分以上作業したら途中でも commit & push する |

---

## ⚠️ deploy.sh は直接実行しない（2026-04-25 変更）

**デプロイは GitHub Actions が自動で行う。Claude から deploy.sh を叩かないこと。**

| 変更ファイル | 自動デプロイ |
|---|---|
| `projects/P003-news-timeline/frontend/**` | `.github/workflows/deploy-p003.yml` が S3+CloudFront を自動実行 |
| `projects/P003-news-timeline/lambda/**` | `.github/workflows/deploy-lambdas.yml` が Lambda を自動実行 |

**Claude のやること**: コードを変更 → `git add / commit / push` のみ。pushしたら GH Actions が本番に反映する（2〜4分後）。

**例外**: インフラ新規作成（DynamoDB テーブル作成・Lambda 新規追加等）が必要な場合のみ `deploy.sh` を使ってよい。その場合はPOに確認してから実行する。

---

# Team Operating Rules

**完了条件**: build/compile通過 + 主要機能動作確認 + `cd projects/P003-news-timeline && npm test` 全42件パス

**完了報告ルール（必須）**: 「できた」と言う前に①エラーログ確認②動作確認③警告修正をすべて済ませること。自力で直せない場合は「ここで詰まっている」と報告する。

**共通原則**: 実装だけで完了扱いにしない。変更後は必ず検証する。UI/文言を勝手に省略しない。自力で直せるエラーは直して再実行する。

---

# AI-Company CEO システム状態（毎セッション必読）

> このセクションはセッションをまたいで状態を引き継ぐための機械的な仕組み。
> Coworkセッション開始時に必ずここを読んでから作業を始める。

## 会社構造
- **出資者・取締役**: PO（承認のみ、日常運営はCEOに委任）
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
| AI要約カバレッジ | 📈 改善中 | 2026-04-26 | summary67%(321/477)・storyPhase40%(193/477)・imageUrl61%(293/477)。新規トピック流入で%低下中。 |
| DynamoDB SNAP肥大化 | 📉 改善中 | 2026-04-26 | ~808K件。TTL(7日)ENABLED。lifecycle週次で7日超SNAP削除（月曜02:00 UTC）|
| sitemap.xml / news-sitemap.xml | ✅ 動的自動生成 | 2026-04-26 | 270URL + Google News Sitemap。processor実行時に自動更新 |
| Bluesky 自動投稿 | ✅ 動作確認済み | 2026-04-26 | T075修正後のdry-run(18:22 JST)で正常な投稿文生成確認。次スケジュール(JST 08:00/12:00/18:00)で実投稿予定 |
| 静的SEO HTML生成 | ✅ 本番稼働 | 2026-04-26 | topics/{tid}.html 976件/S3確認。NoSuchKeyはスキップ扱いに修正(detail未作成トピックは失敗ではない) |
| Slack通知 | ✅ 修正済み | 2026-04-26 | T081: SLACK_WEBHOOK_URL→SLACK_WEBHOOK + continue-on-error:true追加 |
| filter-weights.json | ✅ 初期配置済み | 2026-04-26 | T083: api/filter-weights.json S3に配置(28パターン初期値1.0)。次回fetcher実行でロード確認予定 |
| lifecycle Lambda | ✅ 週次自動実行 | 2026-04-26 | ARCHIVE_DAYS=7・ゾンビ削除・S3孤立ファイル削除 |
| アフィリエイト収益化基盤 | ✅ 実装済み | 2026-04-26 | AFFILIATE_AMAZON_TAG/RAKUTEN_IDをconfig.jsに設定するだけで稼働。ジャンルフィルタ追加済み（T050）。admin.html収益カード更新済み(T057) |
| お問い合わせフォーム | ⏳ DNS伝播待ち | 2026-04-26 | contact.html → p003-contact Lambda。flotopic.com DKIM CNAME×3追加済み・伝播待ち。Lambda環境変数設定済み。伝播後に本番アクセス申請が必要 |
| ストーリー表示 | ✅ 強化済み | 2026-04-26 | T065: フェーズ5段階進捗バー追加・beatをdot+縦線タイムライン形式に刷新・catchupバッジカラー化 |
| proc_ai ストーリープロンプト | ✅ 強化済み | 2026-04-26 | T066: event 20→40文字・transition 15→25文字。standard max_tokens 500→700 |
| ジャンル分類 | ✅ 根本修正済み | 2026-04-26 | T085: GENRE_KEYWORDS拡充(株/原発)・score=0→'総合'フォールバック・グルメ/ファッション検索フィード→genre='総合'に変更 |
| アフィリエイトKW | ✅ 根本修正済み | 2026-04-26 | T084: isNewsHeadlineチェック廃止・常にGENRE_KEYWORD使用（タイトルをキーワードにする誤動作を解消） |

> 完了済みコンポーネント詳細は HISTORY.md「T032 スナップショット棚卸し」セクションを参照

## 専門AI稼働状況

**運営エージェント**: 全8本停止中（API費用削減。ユーザー増加後に再開）

**ガバナンスエージェント**: SecurityAI(✅push+週次→Slack) / LegalAI(⏸停止中) / AuditAI(✅push+週次→PO直報)
- 共通基盤: `scripts/_governance_check.py` / `.github/workflows/governance.yml` / DynamoDB: `ai-company-agent-status`, `ai-company-audit`

## 残タスク（PO手動作業が必要なもの）

- **P002動作確認**（未実施）: `cd ~/ai-company/projects/P002-flutter-game && flutter pub get && flutter run`
- **SES メール検証**: AWSコンソール → SES → us-east-1 → `owner643@gmail.com` 検証。または DNS TXT: `_amazonses.flotopic.com` = `smy0Jk1Xcd84rc7DHAlaKGESjlab/ZxzSkRE3aw7xjw=`
- **待ち**: AdSense審査中（忍者AdMaxで代替中）


## 現在着手中

→ **[WORKING.md](./WORKING.md) を参照**（このセクションには書かない）

## 次フェーズのタスク（優先度順）
1. **SEO流入**: 静的HTML実装済み。次→Qiita/note記事でリンク獲得・Bluesky流入
2. **コンテンツ品質**: AI要約 4x/day 自動改善中。lifecycle ARCHIVE_DAYS=7 週次整理
3. **収益化**: AdSense審査中→通過後に切り替え。Amazon/楽天アフィリ申請（PO手動）
4. **UX**: モバイル改善・表示名分離はユーザー増加後

## 完了済みタスク
→ 詳細は [HISTORY.md](./HISTORY.md) を参照

## 絶対ルール（毎セッション遵守）

- `frontend/` `lambda/` `scripts/` `.github/` のコードは変更しない（CEOエージェントのルール）
- 決まったことは会話で終わらせず即ファイルに書く
- URLの確認・デプロイ確認は自分でやる（POに聞かない）
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

## 将来アイデア候補
→ 詳細は **docs/operations-design.md**（運用設計）・**docs/infra-migration-strategy.md**（インフラ移行戦略）参照
- P003拡張: トピック起点SNS機能（コメント lambda 実装済み。ユーザー増加後に有効化）
- P006候補: Flotopic × 株式投資シグナル（精度向上・ユーザー基盤確立後）

## P002 Flutter → `projects/P002-flutter-game/briefing.md` 参照（コンセプト/システム/収益化/フォルダ構造）
