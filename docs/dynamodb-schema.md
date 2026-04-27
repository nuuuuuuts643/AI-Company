# DynamoDB スキーマ設計（現状スナップショット）

> 最終更新: 2026-04-28（T2026-0428-Z）
> リージョン: `ap-northeast-1`
> アカウント: `946554699567`
> 全テーブル: `BillingMode = PAY_PER_REQUEST`（オンデマンド課金）

このドキュメントは「現状ありき」のスナップショットです。これは **理想形ではなく、いま動いているもの** を記録するドキュメントなので、後付けの違和感や設計負債もそのまま記述します。問題点は最後の「既知の負債・改善候補」に列挙します。

---

## 1. テーブル一覧

| テーブル名 | 主用途 | PK / SK | 件数 | サイズ | TTL | 備考 |
|---|---|---|---|---|---|---|
| `p003-topics` | ニューストピック本体・タイムラインビュー | `topicId` (S) / `SK` (S) | 801,064 | 365 MB | ✅ `ttl` | 最大の重テーブル |
| `ai-company-comments` | ユーザーコメント | `topicId` (S) / `SK` (S) | 1 | 364 B | ❌ | コメントは消さない |
| `flotopic-favorites` | お気に入りトピック登録 | `userId` (S) / `topicId` (S) | 17 | 3 KB | ❌ | ユーザー資産。TTL 不要 |
| `flotopic-users` | ユーザープロファイル | `userId` (S) | 1 | 278 B | ❌ | アカウント情報 |
| `flotopic-analytics` | PV / page_view イベント | `userId` (S) / `sk` (S) | 884 | 120 KB | ✅ `ttl` | sk=`event#<eventType>#<ts>` |
| `flotopic-rate-limits` | コメント・コンタクト用レート制限 | `pk` (S) | 0 | 0 | ✅ `ttl` | 短命キー（数分〜数時間） |
| `flotopic-notifications` | 通知の状態管理 | `handle` (S) / `SK` (S) | 0 | 0 | ✅ `ttl` | お気に入り通知の queue |
| `flotopic-contacts` | お問い合わせフォーム | `contactId` (S) | 1 | 197 B | ❌ | GSI: `category-createdAt-index` |
| `ai-company-x-posts` | X 投稿の重複防止 | `topic_id` (S) | 0 | 0 | ✅ `ttl` ← **本タスクで有効化** | 30 日保持。`x_agent.py` が ttl 属性を書く |
| `ai-company-bluesky-posts` | Bluesky 投稿の重複防止 | `topicId` (S) | 13 | 1 KB | ✅ `ttl` ← **本タスクで有効化** | 30 日保持。`bluesky_agent.py` が ttl 属性を書く |
| `ai-company-memory` | AI エージェント学習データ | `memory_type` (S) / `memory_id` (S) | 2 | 353 B | ❌ | 永続的に保持したい性質 |

---

## 2. 主要テーブル詳細

### `p003-topics` — トピック本体
**主キー設計**: `topicId` + `SK` の単一テーブル設計（DynamoDB Single Table Design）。

**SK パターン**:
| SK | 中身 | 書き込み元 |
|---|---|---|
| `META` | トピックのメタデータ（タイトル・要約・スコア等） | `lambda/processor/proc_storage.py` |
| `TIMELINE#<unixSec>` | タイムラインイベント（時系列発生事象） | `lambda/processor/proc_storage.py` |
| `VIEW#<viewType>` | 派生ビュー（誰が得した・専門用語訳など） | `lambda/processor/proc_ai.py` |
| `ARTICLE#<articleId>` | 関連記事メタ | `lambda/fetcher/handler.py` |

**TTL 属性**: `ttl`（Unix 秒）。デフォルト 90 日。

**読み取りパターン**:
- `topicId` 指定の Query で全 SK を取る → `lambda/api/handler.py` の `/topic/{id}` エンドポイント
- `topics.json` に集約され S3 / CloudFront にキャッシュ → ブラウザはまずこちらを叩く（DynamoDB は fallback）

### `flotopic-analytics` — page_view ログ
**主キー設計**: `userId` (HASH) + `sk` (RANGE)
- `userId`: anonymous UUID または認証済 userId
- `sk`: `event#<eventType>#<unixMillis>`

**用途**: アクティブ閲覧者数集計（`flotopic-cf-analytics` Lambda が aggregate）

**TTL 属性**: `ttl`。デフォルト 90 日。

### `flotopic-favorites` — お気に入り
**主キー設計**: `userId` (HASH) + `topicId` (RANGE)
- HASH = ユーザー単位なので、1 ユーザーの全お気に入り取得が高速
- `userId` 1 つに対して N 件の `topicId` を持つ

**TTL なし**: ユーザー資産なので保持。手動削除のみ。

### `flotopic-rate-limits` — レート制限カウンタ
**主キー設計**: `pk` のみ
- `pk` = `<endpoint>#<sourceIP>` （例: `comments#192.0.2.1`）

**TTL 属性**: `ttl`（Unix 秒）。endpoint ごとに 60〜3600 秒の短命。

### `flotopic-contacts` — お問い合わせフォーム
**主キー**: `contactId` (S)
**GSI**: `category-createdAt-index` (`category` HASH + `createdAt` RANGE)
- 管理画面でカテゴリ別・新着順に表示するため

**TTL なし**: 法的・サポート観点で保持。

---

## 3. アクセスパターン早見表

| 何をしたいか | テーブル | 操作 |
|---|---|---|
| トピック詳細を表示 | `p003-topics` | Query (`topicId = ?`) |
| トップ画面のトピック一覧 | （DynamoDB 直接ではなく） | S3 `topics.json` を fetch |
| ユーザーのお気に入り一覧 | `flotopic-favorites` | Query (`userId = ?`) |
| お気に入り追加・削除 | `flotopic-favorites` | PutItem / DeleteItem |
| 詳細ページのコメント取得 | `ai-company-comments` | Query (`topicId = ?`) |
| コメント投稿 | `ai-company-comments` + `flotopic-rate-limits` | PutItem ×2（rate-limit を先に check） |
| アクセス解析イベント記録 | `flotopic-analytics` | PutItem |
| Bluesky 重複チェック | `ai-company-bluesky-posts` | GetItem (`topicId = ?`) |

---

## 4. TTL 設定の正規化（2026-04-28 本タスクで実施）

### 修正前の問題
`x_agent.py` / `bluesky_agent.py` は item に `ttl` 属性（30 日後）を書き込んでいたが、テーブル側の TTL が **DISABLED** だった。結果、record が削除されず無限に蓄積する「**書き込み側は TTL のつもり、テーブル側は永続**」状態。

### 修正内容
```bash
aws dynamodb update-time-to-live \
  --table-name ai-company-x-posts \
  --time-to-live-specification "Enabled=true,AttributeName=ttl" \
  --region ap-northeast-1

aws dynamodb update-time-to-live \
  --table-name ai-company-bluesky-posts \
  --time-to-live-specification "Enabled=true,AttributeName=ttl" \
  --region ap-northeast-1
```

### TTL を有効化しないテーブル（意図的）
| テーブル | 理由 |
|---|---|
| `flotopic-favorites` | ユーザー資産。失うと体感的な損失が大きい |
| `flotopic-users` | アカウント情報。期限切れの概念がない |
| `flotopic-contacts` | 法的・サポート観点で保持必要 |
| `ai-company-comments` | ユーザー資産 |
| `ai-company-memory` | AI 学習成果。失うと再学習コスト発生 |

---

## 5. PITR（Point-in-Time Recovery）

| テーブル | PITR | 備考 |
|---|---|---|
| `p003-topics` | ✅ | `deploy.sh` L74 で常時オン |
| その他 | ❌ | 必要に応じて個別有効化 |

PITR は 35 日間の任意時点リストアを可能にする保険。料金は通常ストレージの ~1.0x なので主要テーブルには付ける価値がある。

---

## 6. 既知の負債・改善候補

### 6.1 命名の揺れ（後付け増設の痕跡）
`topicId` と `topic_id` が混在している:
- **camelCase**: `p003-topics`, `flotopic-favorites`, `ai-company-bluesky-posts`
- **snake_case**: `ai-company-x-posts`（topic_id）, `ai-company-memory`（memory_type, memory_id）

**影響**: lambda コード側で両方扱う羽目になる。マイグレーションのコストは高いので即時解消は不要だが、新規テーブルは `camelCase` で統一する。

### 6.2 SK 命名の揺れ
- `SK`（大文字）: `p003-topics`, `ai-company-comments`, `flotopic-notifications`
- `sk`（小文字）: `flotopic-analytics`

**影響**: 新規テーブルは `SK` で統一する。

### 6.3 IAM ポリシーに存在しないテーブルが含まれている
`projects/P003-news-timeline/deploy.sh` L143 の最小権限ポリシーに `ai-company-audit` テーブルが含まれているが、実際には未作成。
- 利用箇所: `scripts/audit_agent.py`, `scripts/legal_agent.py`, `scripts/security_agent.py`
- これらは Lambda ではなくローカル / GitHub Actions で動くスクリプト
- IAM ポリシー（Lambda 用）に置く意味は薄い → 整理候補

### 6.4 GSI の少なさ
ほぼ全テーブルが PK/SK のみで GSI を持たない（`flotopic-contacts` のみ 1 GSI）。
- 現在のアクセスパターンは PK 一発引きが中心なので問題ない
- 「ジャンル別トピック」「期間別 PV」など今後の機能追加で GSI が必要になるかも

### 6.5 件数 0 のテーブル
`flotopic-rate-limits`, `flotopic-notifications`, `ai-company-x-posts` は現状 0 件。
- レートリミット 0 は単に過去 N 分にリクエストがないだけ。正常
- 通知 0 は通知機能がまだフル稼働していないため
- x-posts 0 は X 投稿エージェントが停止していたため（最近再開）

---

## 7. 運用 Tips

### サイズ・コスト確認
```bash
aws dynamodb describe-table --table-name p003-topics --region ap-northeast-1 \
  --query 'Table.{Items:ItemCount,Bytes:TableSizeBytes}'
```

### TTL 状態確認
```bash
for t in $(aws dynamodb list-tables --region ap-northeast-1 --query 'TableNames' --output text); do
  echo "=== $t ==="
  aws dynamodb describe-time-to-live --table-name "$t" --region ap-northeast-1 --output json
done
```

### スキャンを伴う操作は最小限に
特に `p003-topics`（80 万件）は Scan するとフル課金が走る。Query で済む設計を維持すること。
