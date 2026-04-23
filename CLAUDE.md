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

## 現在のプロジェクト状態（最終更新: 2026-04-22 git競合修正・AWS MCP設定）

| プロジェクト | 状態 | 備考 |
|---|---|---|
| P003 Flotopic | **本番稼働中** ✅ | flotopic.com。catchup.html・processor Lambda・X投稿AI全てデプロイ済み。HTTPS化完了済み。AdSense申請が次のアクション。 |
| P002 Flutterゲーム | Flutter+Flameで再構築中 | Unity版フォルダ削除済み。`projects/P002-flutter-game/` にFlutter+Flame実装済み（50+ファイル） |
| P004 Slackボット | **デプロイ完了** ✅ | Bot URL: https://pqtubmsn7kfk2nojf2kqkwqiuu0obnwc.lambda-url.ap-northeast-1.on.aws/ Slack AppでSlash Command `/ai` 設定が必要 |
| P005 メモリDB | 稼働中 | DynamoDB ai-company-memory (ap-northeast-1) 稼働中 |

## 専門AI稼働状況

### 運営エージェント
| エージェント | スクリプト | スケジュール | 状態 |
|---|---|---|---|
| CEO | scripts/ceo_run.py | 毎朝8:30 JST | ✅ 稼働中 |
| 秘書 | scripts/secretary_run.py | 毎朝9:00 JST | ✅ 稼働中（Notion同期強化済み） |
| 開発監視AI | scripts/devops_agent.py | 毎時 | ✅ 有効（git push済み） |
| マーケティングAI | scripts/marketing_agent.py | 毎朝10:00 JST | ✅ 有効（git push済み） |
| 収益管理AI | scripts/revenue_agent.py + notion_revenue_sync.py | 毎週月曜9:30 JST | ✅ 有効（Notion同期追加済み） |
| 編集AI | scripts/editorial_agent.py | 毎週水曜9:00 JST | ✅ 有効（git push済み） |
| SEO AI | scripts/seo_agent.py | 毎週月曜10:00 JST | ✅ 有効（git push済み）|
| X投稿AI | scripts/x_agent.py | 日次8:00/週次月9:00/月次1日9:00 JST | ✅ 有効（git push済み・X API key未設定）|

### ガバナンスエージェント（CEO含む全エージェントを独立監視）
| エージェント | スクリプト | スケジュール | 状態 | 報告先 |
|---|---|---|---|---|
| SecurityAI | scripts/security_agent.py | push時(L1/L2) + 毎週月曜8:00 JST(L3) | ✅ 有効 | Slack（CRITICAL時はPOさん直報） |
| LegalAI | scripts/legal_agent.py | push時(L2) + 毎月1日(L3) | ✅ 有効 | Slack（要対応時はPOさん直報） |
| AuditAI | scripts/audit_agent.py | push時 + 週次 | ✅ 有効 | **POさん直接報告（CEOを経由しない）** |

#### ガバナンス補助
| ファイル | 役割 |
|---|---|
| scripts/_governance_check.py | 全エージェント共通の自己停止モジュール |
| .github/workflows/governance.yml | 統合ガバナンスワークフロー（L1→L2→Legal→Audit の直列パイプライン）|
| DynamoDB: ai-company-agent-status | 各エージェントのactive/paused/stopped状態管理 |
| DynamoDB: ai-company-audit | 全監査ログの永続保存 |

## 残タスク（PO手動作業必要）

### 優先度: 高
- **p003-processor ANTHROPIC_API_KEY設定** — AI要約生成に必須。`aws lambda update-function-configuration --function-name p003-processor --region ap-northeast-1 --environment 'Variables={S3_BUCKET=p003-news-946554699567,TABLE_NAME=p003-topics,REGION=ap-northeast-1,SITE_URL=https://flotopic.com,ANTHROPIC_API_KEY=sk-ant-...}'`
- **Google AdSense申請** — https://www.google.com/adsense/ からflotopic.comで申請。HTTPS化済みなので申請可能。審査に数日〜数週間かかる。
- **P004 Slash Command設定** — https://api.slack.com/apps で `/ai` コマンドのRequest URLに `https://pqtubmsn7kfk2nojf2kqkwqiuu0obnwc.lambda-url.ap-northeast-1.on.aws/` を設定
- **Claude Desktop再起動** — AWS MCP有効化のため（設定変更済み・再起動だけで完了）

### 優先度: 中
- **X API Key** — ✅ GitHub Secrets 登録済み（X_API_KEY / X_API_SECRET / X_ACCESS_TOKEN / X_ACCESS_TOKEN_SECRET）
- **Google OAuth設定** — Google Cloud Console で GOOGLE_CLIENT_ID 取得（手順: docs/google-oauth-setup.md）
- **P002 Flutter動作確認** — `cd ~/ai-company/projects/P002-flutter-game && flutter pub get && flutter run`

## 承認済み・実行待ちタスク

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
- ✅ **deploy.sh** — processor Lambda追加。fetcher schedule: rate(5 min)、processor: cron(0 22,3,9 * * ? *)
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

- **P003 ANTHROPIC_API_KEY未設定（processor Lambda）** — AI要約が生成されない。残タスクの「優先度: 高」参照。
- **P003 アイコン素材不足** — icon-192.png / icon-512.png / apple-touch-icon.png が未作成（ICONS-NEEDED.md参照）。PWAインストール時に必要。
- **P003 GOOGLE_CLIENT_ID設定済み** — ✅ config.jsに 632899056251-hmk2ap6tv98miqj8n96lig3vj7uoa057.apps.googleusercontent.com 設定済み
- **P003 AdSense審査待ち** — HTTPS化完了済み。申請後、審査通過まで数週間かかる場合あり。それまでは忍者AdMaxで代替。
- **P003 HTTPS** — ✅ 2026-04-23 CloudFront E2Q21LM58UY0K8 + ACM証明書 ISSUED。flotopic.com でHTTPS動作確認済み。
- **グラフデータ** — 現在データ蓄積中のため推移グラフは30分毎に更新。長期グラフ（1ヶ月〜1年）はデータ蓄積後に意味を持つ
- **news.google.comがソースとして表示される問題** — RSSフィードがGoogle Newsアグリゲーターを経由している場合、ソース名がnews.google.comになる。元のソース名パースが必要（feedparserのauthor/sourceフィールド活用）
- CEOの日次Slack通知 — ✅ 2026-04-22 動作確認済み。継続モニタリング中
- **P002 Unityフォルダ削除済み** — ✅ 完了
- **P002 Flutterスプライト素材未作成** — AI生成で後日追加
- **P002 BGM本番版未作成** — Suno AIで後日生成・差し替え

## 将来アイデア候補

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
