# ⚡ セッション開始時に必ず最初に実行すること

Claude Codeセッションを開始したら、何も聞かずに以下を順番に実行する。

```bash
# 1. git lockファイルがあれば削除
rm -f /Users/OWNER/ai-company/.git/index.lock

# 2. 未コミットの変更を全てコミット＆push（別セッションがpushしている場合はrebaseして追従）
cd /Users/OWNER/ai-company
git add -A
git commit -m "chore: sync Cowork session changes $(date '+%Y-%m-%d')" || echo "nothing to commit"
git pull --rebase origin main || echo "rebase failed, continuing"
git push || echo "push failed, continuing"
```

エラーが出ても止まらず最後まで実行する。完了後に「✅ 起動チェック完了」と報告してからユーザーの指示を待つ。

## ⚡ 作業前後ルール（2026-04-25 制定）

**作業開始前に必ずやること：**
1. 下記「定期状況確認コマンド」を実行する
2. `P003 技術状態スナップショット` テーブルを読む
3. これからやろうとしていることが ✅ になっていないか確認する
4. ✅ なら「すでに完了済み」として**スキップ**し、次の未完了タスクに移る
5. `現在着手中` セクションに **タスク名・開始時刻・変更予定ファイル** を記入してから作業開始

**作業完了後に必ずやること：**
1. `P003 技術状態スナップショット` テーブルを最新状態に更新する
2. `次フェーズのタスク` の完了済み項目を「完了済み」セクションに移動する
3. `現在着手中` から完了タスクを削除する
4. CLAUDE.md の変更を含めて `git add -A && git commit && git push` する

**定期状況確認コマンド（タスク開始前・30分ごとに実行）：**
```bash
cd /Users/OWNER/ai-company
git pull --rebase origin main
git log --oneline -5
grep -A 10 "現在着手中" CLAUDE.md | head -12
# メモリファイルの更新も確認（別セッションが追加したルールを把握する）
cat /Users/OWNER/.claude/projects/-Users-OWNER-ai-company/memory/MEMORY.md
```

**重複作業を避けるルール：**
- ファイルを編集するたびに PreToolUse フック（~/.claude/settings.json）が自動チェックする
  - `⚠️ 他セッションの未取り込みコミットが N 件` → 即 `git pull --rebase` してから再開
  - `📋 CLAUDE.md のルールが更新されています` → pull後に CLAUDE.md 全セクションを再読してから続行
- フックは警告のみ（ブロックしない）。でも無視せずに必ず対処する
- `現在着手中` に同じファイルが記載されていたら絶対に触らない
- 他セッションが同じ作業を完了していたら即スキップして次のタスクに移る

**「現在着手中」記入フォーマット：**
```
- **[タスク名]**（開始: YYYY-MM-DD HH:MM JST | 変更予定: path/to/file.py, path/to/file2.js）
```

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
| CI (.github/workflows/ci.yml) | ✅ 全テスト通過 | 2026-04-25 | YAML バグ修正済み（2022-04-22以来初めて通過） |
| sw.js バージョン管理 | ✅ 自動 | 2026-04-25 | git SHA 自動注入。ソースは `flotopic-dev` のまま触るな |
| deploy-p003.yml | ✅ CloudFront invalidation付き | 2026-04-25 | sw.js SHA注入ステップあり |
| processor AI要約 | ✅ 稼働中（proc_config修正済み） | 2026-04-25夜 | 4セクション形式・4回/日。proc_config.pyモジュールエラー修正・再デプロイ済み |
| sitemap.xml | ✅ 動的自動生成 | 2026-04-25 | 最新生成確認済み（2026-04-25 19:42）。202URL |
| news-sitemap.xml | ✅ 実装済み | 2026-04-25 | Google News Sitemap。processor実行時に自動生成。robots.txtに記載済み |
| rss.xml | ✅ 品質フィルタ済み | 2026-04-25 | 同一イベント重複抑制あり（最大2件/イベント）・株価ticker除外 |
| クラスタリング | ✅ 改善 | 2026-04-25 | 【中継】【速報】等のプレフィックスを除去してからJaccard比較 |
| 株価ティッカーフィルタ | ✅ 強化 | 2026-04-25 | 英数字コード(325A等)・Yahoo!ファイナンス全般を除外 |
| fetcher Float型エラー | ✅ 修正済み | 2026-04-25夜 | 旧Lambda(633行)がfloatをDynamoDBに書いていた。最新コード（Decimal変換済み）を再デプロイ |
| deploy-lambdas.yml | ✅ 全Lambda対象 | 2026-04-25夜 | analytics/auth/favorites/lifecycle/cf-analytics/api を追加（6関数が自動デプロイ対象外だった） |
| CloudFront | ✅ 自動無効化 | 2026-04-25 | push → GH Actions → S3 + CF invalidation |
| view tracking | ✅ 稼働 | 2026-04-25 | POST /analytics/event → flotopic-analytics Lambda |
| admin dashboard | ✅ グラフ強化 | 2026-04-25 | velocity分布・AIパイプライングラフ追加済み |
| lifecycle Lambda | ✅ ARCHIVE_DAYS=7 | 2026-04-25 | 30→7日に変更。filter-feedbackクリーンアップ追加 |
| lifecycle archived保護 | ✅ 修正済み | 2026-04-25夜 | fetcher が archived を上書きしないよう修正（velocity>0なら再active可） |
| SEO/OGP | ✅ 全ページ完備 | 2026-04-25夜 | Twitter Card全静的ページ・BreadcrumbList JSON-LD・privacy/terms OGP追加 |
| Bluesky 自動投稿 | ✅ 稼働 | 2026-04-25 | 毎日05:32 JST 投稿確認済み |
| Claude Code 確認ダイアログ | ✅ 対策済み | 2026-04-25 | ~/.claude/settings.json に Bash/Edit/Write を allow 追加。再起動後有効 |

## 専門AI稼働状況

### 運営エージェント（全スケジュール停止中 2026-04-24〜）
| エージェント | スクリプト | 停止理由 |
|---|---|---|
| CEO | scripts/ceo_run.py | API費用削減・ユーザーゼロ段階では不要 |
| 秘書 | scripts/secretary_run.py | 同上 |
| 開発監視AI | scripts/devops_agent.py | 同上 |
| マーケティングAI | scripts/marketing_agent.py | 同上 |
| 収益管理AI | scripts/revenue_agent.py | 同上 |
| 編集AI | scripts/editorial_agent.py | 同上 |
| SEO AI | scripts/seo_agent.py | 同上 |
| X投稿AI | scripts/x_agent.py | X API Basic Plan ($100/月) が必要なため保留 |

### ガバナンスエージェント
| エージェント | スクリプト | スケジュール | 状態 | 報告先 |
|---|---|---|---|---|
| SecurityAI | scripts/security_agent.py | push時(L1/L2) + 毎週月曜8:00 JST(L3) | ✅ 有効 | Slack（CRITICAL時はPOさん直報） |
| LegalAI | scripts/legal_agent.py | push時(L2) + 毎月1日(L3) | ⏸ 停止中 | — |
| AuditAI | scripts/audit_agent.py | push時 + 週次 | ✅ 有効 | **POさん直接報告（CEOを経由しない）** |

#### ガバナンス補助
| ファイル | 役割 |
|---|---|
| scripts/_governance_check.py | 全エージェント共通の自己停止モジュール |
| .github/workflows/governance.yml | 統合ガバナンスワークフロー（L1→L2→Legal→Audit の直列パイプライン）|
| DynamoDB: ai-company-agent-status | 各エージェントのactive/paused/stopped状態管理 |
| DynamoDB: ai-company-audit | 全監査ログの永続保存 |

## 残タスク（PO手動作業が必要なもの）

```bash
# ① Google Search Console: サイトマップ送信（最優先・SEOに直結）
# → Search Console > サイトマップ > https://flotopic.com/sitemap.xml を入力して送信

# ② P002動作確認（まだ未実施）
cd ~/ai-company/projects/P002-flutter-game && flutter pub get && flutter run
```

**待ち（何もしなくていい）**: AdSense審査中（忍者AdMaxで代替中）

### 完了済み手動タスク（記録）
- ✅ push / S3デプロイ / Lambda デプロイ → セッション開始時に自動実行
- ✅ AI要約有効化（ANTHROPIC_API_KEY設定済み・動作確認済み）
- ✅ AWSコストアラート設定（月$30超でowner643@gmail.comに通知）
- ✅ Google Search Console登録完了
- ✅ flotopic.comドメイン自動更新 → 意図的にOFF（手動管理）
- ✅ Notion自動同期 → GitHub Actions（notion-sync.yml / notion-revenue-daily.yml）が毎日09:00 JSTに自動実行

## 現在着手中（このセクションにある作業は別セッションがやらないこと）

> セッション開始時に必ずここを確認。着手中の作業があればスキップして次の未完了タスクへ。
> 作業完了したらすぐに「完了済み」セクションへ移動し、このセクションを空にする。

（なし）

## 次フェーズのタスク（優先度順）

### 優先度1: SEO・流入強化（Claude実行可能）
- **Google Search Console でサイトマップ送信**（PO手動・最優先）
- トピック別 OGP 画像生成 → Lambda で topic タイトルを canvas に描画してS3保存
- ~~Google News サイトマップ追加~~ ✅ 実装済み
- ~~株価ティッカートピックS3除去~~ ✅ 0件確認済み
- ~~Twitter Card/OGPメタタグ全ページ追加~~ ✅ 2026-04-25 完了
- ~~BreadcrumbList JSON-LD追加~~ ✅ 2026-04-25 完了

### 優先度2: コンテンツ品質（Claude実行可能）
- AI要約カバレッジ向上: 321件中68件（21%）→ pending_ai.jsonバックログ修正で自動改善中
- ~~processor Lambda メモリ 512MB~~ ✅ 確認済み（既に512MB）
- velocity=0 の停滞トピック196件 → lifecycle Lambda(ARCHIVE_DAYS=7)が次週月曜に自動整理
- ~~Bluesky 自動投稿~~ ✅ 稼働確認済み

### 優先度3: ユーザー体験（Claude実行可能）
- モバイルUX改善（現在モバイル4%・デスクトップ96%、実ユーザー獲得後に重要度UP）
- コメント・お気に入り促進UI（現在0件）→ CTAを目立たせる

### 優先度4: 運用・インフラ（Claude実行可能）
- ~~cf-analytics スケジュール確認~~ ✅ ENABLED確認済み（CF認証情報未設定は別問題）
- DynamoDB 784K件のTTL動作確認（SNAP TTL 7日が正常動作中か）
- ~~admin ダッシュボード velocity分布・AIパイプライングラフ~~ ✅ 2026-04-25 完了

### 優先度5: 収益化（待ち）
- AdSense 審査通過後の広告設定切り替え（忍者 AdMax → AdSense）→ 審査中・PO待ち
- X 投稿エージェント再開（X API Basic Plan $100/月が必要）→ 収益化後に判断

## 承認済み・実行待ちタスク

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

### 承認済み提案
- **#001**: AWS MCP接続 + P005メモリDB構築（2026-04-21承認）

## 絶対ルール（毎セッション遵守）

- `frontend/` `lambda/` `scripts/` `.github/` のコードは変更しない（CEOエージェントのルール）
- 決まったことは会話で終わらせず即ファイルに書く
- URLの確認・デプロイ確認は自分でやる（POに聞かない）
- 「書きました」「やります」の宣言は信用されない。ファイルの存在が証拠。
- 空報告禁止。実行した証拠（ファイル変更・ログ・スクリーンショット）を必ず示す

## 開発ルール（一人開発・事故防止）

### 基本フロー
1. コードを変更する
2. `bash projects/P003-news-timeline/deploy-staging.sh` でステージングに反映
3. ステージングURLで動作確認
4. 問題なければ `bash projects/P003-news-timeline/deploy.sh` で本番反映

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
- **P003 news.google.comがソースとして表示される問題** — Google Newsアグリゲーター経由の記事でソース名がnews.google.comになる。feedparserのauthor/sourceフィールドで元ソース名を取得する改善が必要。
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

### コンセプト
「リアルタイム配置オートバトル × HD-2Dドット絵 × ローグライト抽出」
- ループヒーロー × MMOの中間
- オクトパストラベラー風のビジュアル（ドット絵 + リッチな光演出）

### ゲームシステム
- 敵が右→左へ自動侵攻。カードをマップに配置するだけ、戦闘は自動
- 属性相性（火水風土光闇の6属性・三すくみ）
- チェーン反応でコンボが決まる爽快感
- ウェーブ間ショップでLoL的ビルド要素
- タルコフ的抽出リスク（atRisk/secured の2状態）
- ナイトレイン的セッション構造（ハブ→ラン→帰還）
- 運の要素6種（手札RNG・クリティカル・ドロップ・ウェーブ変動・イベント・チェーン確率）
- 乱入型協力プレイ（Phase 3）

### 収益化
- 無料版：ステージ後広告（Google Mobile Ads）
- 有料版$2.99：広告なし
- スキン追加がメインアップデート
- ステージはプロシージャル自動生成（コンテンツ追加不要）

### フォルダ構造
`projects/P002-flutter-game/`
- lib/systems/ — battle, card, chain, event, loot, save, wave, shop, extraction（9システム）
- lib/components/ — enemy, unit, projectile, hd2d_background, lighting, particle, screen_shake, floating_text, chain_effect, animation_controller（10コンポーネント）
- lib/screens/ — main_menu, battle, card_hand, equipment, result, stage_select, wave_shop, extraction（8画面）
- lib/services/ — ad_service, audio_service
- assets/audio/ — WAVプレースホルダー8種（Suno生成BGMに後で差し替え）

### Claude Codeでの作業ガイド
1. `cd ~/ai-company/projects/P002-flutter-game`
2. `flutter pub get` でパッケージ取得
3. `flutter run` でiOSシミュレータ起動
4. コードを変更 → ホットリロード（r キー）で即反映
5. `flutter analyze` で静的解析
6. 完成度・未完了箇所はbriefing.mdを参照

## セッション更新ルール

このファイルの「AI-Company CEO システム状態」セクションは以下のタイミングで更新する：
- 新しい承認が出たとき → 即座に追記
- タスクが完了したとき → 状態を更新
- 新しい問題が発覚したとき → 未解決に追記
- セッション終了前 → 必ず最新状態に更新してから終わる
