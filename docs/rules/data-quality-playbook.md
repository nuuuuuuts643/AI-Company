# データ品質改善プレイブック（全プロダクト共通）

> 制定: 2026-04-28（T2026-0428-AP）
> 出自: T2026-0428-AO「Flotopic 全トピック棚卸し＆一括クリーンアップ」で確立した手順を、他プロダクト（P002 Unity、将来の P006 等）に転用できる形に汎化したもの。
> 適用対象: DynamoDB / RDB / KVS にレコードを蓄積し、派生ファイル（JSON / 静的 HTML / サイトマップ）や CDN を持つ全プロダクト。

---

## 1. 問題のパターン

### 1-1. ゴミデータが慢性的に蓄積する原因

| 原因カテゴリ | 具体例 |
|---|---|
| **lifecycle バグ** | 削除条件の漏れ（`articleCount=0` だけ見て `keyPoint=null` を見逃す等） / lifecycle 自体が定期実行されていない / DB は消すが派生ファイル（topics.json / 静的HTML / sitemap）を更新しない |
| **作成ガード不足** | 低品質レコード（記事 1 件だけ・本文なし・必須フィールド欠落）が DB に書かれる。「とりあえず作って後から改善」が積み重なる |
| **schema 変更時の取り残し** | ロジック改善でフィールドが増えても、既存レコードは旧スキーマのまま放置。「正常」判定が時代によって変わるのに版管理が無い |
| **失敗時の中途半端な書き込み** | AI 生成が失敗したのに META レコードだけ作成済み → keyPoint=null が残る |
| **派生ファイルの取りこぼし** | DB は最新だが S3/CDN の JSON / 静的 HTML が古い。「DB を見れば正しい」が「ユーザーには古い情報が見える」を生む |

### 1-2. 「根本修正しても過去データが治らない」構造的問題

- 新規ロジック修正後の新規データは正常になるが、**過去に作られた壊れたレコードはそのまま残る**
- ユーザーから見える品質指標（充填率・404 率・空レコード比率）は「全レコードに対する比率」なので、過去ゴミがある限り改善しない
- 「修正したのに改善しない」現象が続くと、修正者は「もっと修正しなきゃ」と band-aid を重ねる悪循環に入る

### 1-3. 局所パッチが通用しなくなるサイン

- 同じバグが「別の入り口」から再発する（DB 直接 / fetcher / API / バッチ移行 etc）
- 「N 件治して報告したが、また N 件出てきた」が 2 回以上起こる
- 障害解析で「過去のあのデータが特殊だから」と説明する事象が増える
- 1 ファイルの修正で済まず、「ついでにこれも」と修正範囲が広がっていく

→ ここまで来たら**全件棚卸しに切り替えるサイン**。局所パッチの追加禁止。

---

## 2. 全件棚卸しアプローチ（5 ステップ）

### Step 1: 全レコードを分類する

カテゴリ例（Flotopic で実際に使ったもの）:

| カテゴリ | 意味 | 処理 |
|---|---|---|
| `GOOD` | 現行スキーマで完備 | 触らない |
| `EMPTY` | 必須フィールド欠落（articleCount=0 / keyPoint=null） | 削除 |
| `ZOMBIE_FORWARD_ORPHAN` | DB に META 存在、派生ファイルから消えている | 削除（grace 3 日） |
| `ZOMBIE_REVERSE_ORPHAN` | 派生ファイルにあるが DB に META 無し | 派生ファイルから除去 |
| `ZOMBIE_STALE` | 最終更新から N 日経過＋ articleCount<=1 | 削除 |
| `ZOMBIE_BROKEN_META` | title 等の必須欠落 | 削除 |
| `OLD_SCHEMA` (`NO_AI` / `PARTIAL_AI`) | schema_version 古い・AI フィールド欠落 | **再処理キュー投入のみ。既存フィールドは絶対に上書きしない** |

実装パターン: `scripts/cleanup_all_topics.py`（622 行）。dry-run デフォルト・`--apply` で実行・`--only CATEGORY` で絞れる。

### Step 2: ゴミを一括削除（DB + 派生ファイル全部）

- **DB**: 物理削除（DELETE）または lifecycleStatus=deleted で論理削除
- **派生ファイル**: topics.json / 静的 HTML / sitemap / pending_ai.json から同 ID を除去
- **「DB だけ消す」は禁止** — 派生ファイルが取り残されると Step 1 を再度実行した時 ZOMBIE_REVERSE_ORPHAN として再検出され堂々巡り
- **削除前のスナップショット必須** — `--dry-run` の出力をファイル保存してから `--apply`

### Step 3: 正常レコードのみで派生ファイルを再生成

- 残った GOOD レコードだけで topics.json / sitemap / 静的 HTML を再生成
- 再生成は冪等（同じ入力なら同じ出力）であること

### Step 4: CDN キャッシュを無効化

- CloudFront `create-invalidation` を派生ファイル全パスに対して実行
- 「DB と S3 は最新だが CloudFront に古いキャッシュが残る」事故を防ぐ
- 大量ファイルなら `/*` よりパス指定の方がコスト・反映時間とも有利

### Step 5: 削除漏れを物理確認

- 削除対象のサンプル URL を 5 件抜き、HTTP HEAD で 404 を確認
- sitemap.xml に削除済み ID が残っていないか grep
- DB と派生ファイルのレコード数が一致するか SLI で確認

---

## 3. 自己修復基盤パターン（Self-Healing Infrastructure）

棚卸しを 1 回やって終わりにせず、**蓄積前に治す**仕組みを置く。

### 3-1. `schema_version` フィールド

- 全レコードに `schemaVersion: <int>` を持たせる
- ロジック側に `PROCESSOR_SCHEMA_VERSION` 定数を置く（例: `proc_config.py`）
- 処理ロジックを変えたら `PROCESSOR_SCHEMA_VERSION` を 1 つ上げる
- `needs_reprocess(item)` 判定で `item.schemaVersion < PROCESSOR_SCHEMA_VERSION` を **OR 条件**に入れる
- 古いスキーマで作られたレコードは次回処理対象として自動キュー入りする

実装例: `proc_storage.py:286-313` の `needs_ai_processing()`。pendingAI=True OR schemaVersion 古い OR AI フィールド欠落、のいずれかでトリガー。

### 3-2. `needs_reprocess` フラグ（pendingAI 等）

- 処理キューを別テーブルにせず、レコード自身の boolean フラグで管理
- fetcher / 外部トリガーがフラグを立て、processor がフラグを見てクリアする
- **書き込みはアトミック update**（`UpdateExpression='SET pendingAI = :p'` で上書きしない）

### 3-3. `quality_heal.py`（品質監視 cron）

- DB 全件スキャン → 品質劣化レコード（`keyPoint` 空 / schemaVersion 古い / 必須フィールド欠落）を検出
- 検出されたレコードに **再処理フラグだけ** セット
- 既存の良いフィールドは絶対に上書きしない
- dry-run デフォルト・`--apply` で実行・`--limit N` で件数制限
- 派生ファイル（pending_ai.json 等）にも同 ID を追加して processor 側ロジックと整合させる

実装例: `scripts/quality_heal.py`（203 行）。

### 3-4. `bulk_heal.sh`（手動一括キュー投入）

- 棚卸し時 / 大規模スキーマ変更時に手で対象を絞って一括キュー投入
- モード切替: `all` / `no-keypoint` / `empty` / `old-schema`
- `APPLY=1` を立てなければ dry-run（事故防止）

実装例: `scripts/bulk_heal.sh`（57 行）→ Python 側に exec で委譲。

### 3-5. **再処理は incremental**（最重要原則）

- 既存の良いデータは絶対に上書きしない
- 空フィールドだけ補完する
- 「再処理」と「全フィールド上書き」を混同しない
- 失敗した再処理が良いデータを壊す事故を物理排除する

実装パターン: processor 側に `existing_meta` 取得 → 空フィールドのみ AI 生成 → `UpdateExpression` は埋まったフィールドだけ列挙。

---

## 4. 再発防止ゲート

### 4-1. 作成時ガード

- DB に書く前に最低品質を満たすかチェック（例: 記事数 >= 2、必須フィールド非空、本文長 >= N）
- 満たさないなら**作らない**。「あとで治す」前提の作成は禁止
- ガードは fetcher / API ハンドラの **書き込み直前** に置く（境界）

### 4-2. lifecycle での定期削除

- 毎サイクル（例: cron で 6 時間ごと）に品質基準を下回るレコードを削除
- 削除条件は cleanup スクリプトと同じ判定ロジックを共有（コピペ禁止・関数化）
- 削除と派生ファイル更新を **同 Lambda invocation 内** で行う（中途半端な状態を作らない）

### 4-3. daily cron: `quality_heal.py`

- GitHub Actions `.github/workflows/quality-heal.yml` 等で日次実行
- 蓄積を「翌日には治す」物理保証
- `--apply --limit 50` 等で 1 日の処理量を制限し、API コストを予測可能にする

### 4-4. SLI による外部観測

- 充填率・404 率・空レコード比率を毎時 / 毎日サンプリング
- 閾値を下回ったら Slack 通知
- 「治した」を主観で判定せず、**外部観測の数値で判定**する

---

## 5. 適用チェックリスト（他プロダクト転用時）

新プロダクト立ち上げ時 / 既存プロダクトへの導入時に確認する。

- [ ] レコードに `schemaVersion`（または同等のバージョンフィールド）を持たせているか
- [ ] 処理ロジックに `*_SCHEMA_VERSION` 定数があり、`needs_reprocess` 判定が `schemaVersion < CURRENT` を見ているか
- [ ] 再処理フラグ（`pendingAI` 等の boolean）でキュー管理されているか
- [ ] lifecycle / cleanup job が定期実行されているか（cron / EventBridge）
- [ ] 作成時ガードがあるか（最低記事数 / 必須フィールド非空）
- [ ] 派生ファイル（JSON / 静的 HTML / sitemap / pending_*.json）の同期削除が実装されているか
- [ ] CDN キャッシュ invalidation が自動化されているか
- [ ] `cleanup_all_*.py` 相当の全件棚卸しスクリプトが存在し、dry-run デフォルトか
- [ ] `bulk_heal.sh` 相当の手動一括キュー投入が用意されているか
- [ ] `quality_heal.py` 相当の品質監視 cron が daily で動いているか
- [ ] **再処理が incremental**（既存フィールド上書き禁止）になっているか
- [ ] SLI（充填率 / 404 率 / 空レコード比率）が外部観測されているか

12 項目すべてに ✅ が付いて初めて「データ品質基盤あり」と呼ぶ。1 つでも欠けたら蓄積が始まる。

---

## 関連ドキュメント

- `docs/rules/global-baseline.md` — 全プロダクト共通の前提条件
- `docs/rules/bug-prevention.md` — 再発防止ルール表
- `docs/lessons-learned.md` 2026-04-28 「ゴミデータ慢性蓄積の構造的欠陥」 — 本プレイブック制定の出自なぜなぜ
- `scripts/cleanup_all_topics.py` / `scripts/quality_heal.py` / `scripts/bulk_heal.sh` — Flotopic での参照実装
