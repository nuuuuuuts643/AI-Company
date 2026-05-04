# flotopic 全体設計 (2026-05-04)

> **方針**: 設計を決めてから実装する。設計外の変更は起票してここを更新してから進める。
> 切り戻し原則: 新しい経路が本番で正常動作してから古い経路を削除する。

---

## プロダクトの目的と現在地

- 日本語ニュースをAIで整理して読者に届けるサービス
- 現在 ~78 visits/日 → Phase C 目標 500 visits/日
- AWS コスト: $11/月 → $6〜7/月 が現実的な削減目標
- Claude API コスト: AWS とは別請求。processor の 2x/day 実行分

---

## フェーズ定義

| フェーズ | 条件 | 有効にする機能 |
|---|---|---|
| **Phase A（今）** | 〜500 visits/日 | コンテンツ閲覧のみ。ログイン不要 |
| **Phase B** | AdSense 審査通過後 | 広告・SEO強化 |
| **Phase C** | 500 visits/日 + コメント削除機能実装後 | ログイン・コメント・お気に入り |

---

## 現状の正確な把握（コード調査済み）

### データフロー（実態）

```
【書き込み】
RSS → fetcher(30min) → DynamoDB p003-topics（SoT）
                  → processor(2x/day) → Claude API → DynamoDB 更新
                                               → S3 JSON 生成（配信用）

【読み取り】
ブラウザ → CloudFront → S3 api/*.json  ← 主経路（config.js: API_BASE = flotopic.com/api/）
         → (フォールバック) API Gateway → p003-api Lambda → S3（DDB フォールバック残存）

【ユーザー行動】
ブラウザ → API Gateway → tracker/analytics Lambda → DynamoDB
```

### S3 JSON ファイル（processor が生成・processor だけが書く）

| ファイル | 用途 |
|---|---|
| `api/topics-card.json` | 一覧（軽量・フロントが主に使う） |
| `api/topics.json` | 一覧（フル） |
| `api/topics-full.json` | 詳細用 |
| `api/topic/{id}.json` | 個別トピック詳細 |
| `api/health.json` | SLI・充填率 |
| `api/pending_ai.json` | AI処理キュー（processor 内部用） |
| `api/topics_visible_ids.json` | visible topic ID 一覧 |
| `api/sitemap.xml` / `rss.xml` | SEO・配信 |

### Lambda 一覧（現状）

| 関数名 | 起動 | 役割 | Phase A 必要? |
|---|---|---|---|
| p003-fetcher | 30min | RSS→DynamoDB | ✅ |
| p003-processor | 2x/day + on-demand | AI→S3生成 | ✅ |
| p003-api | API呼び出し時 | /topics・/topic/{id} | ⚠️ S3直配信で不要になる方向 |
| p003-tracker | イベント時 | 匿名閲覧ログ | ✅ |
| p003-contact | フォーム送信時 | お問い合わせ | ✅（※1） |
| flotopic-bluesky | 30min | Bluesky投稿 | ✅ ただし頻度過剰 |
| flotopic-lifecycle | 週1 | 古トピックアーカイブ | ✅ |
| flotopic-auth | ログイン時 | Google認証 | ❌ Phase C |
| flotopic-comments | コメント時 | コメントCRUD | ❌ Phase C |
| flotopic-favorites | お気に入り時 | お気に入りCRUD | ❌ Phase C |
| flotopic-analytics | API呼び出し時 | /analytics/active 等 | ⚠️（※2） |
| flotopic-cf-analytics | 毎日7:00 JST | CFログ集計 | ⚠️ 要確認 |

※1: `p003-contact` がデプロイされている（deploy-lambdas.yml 253行）。`flotopic-contact` は同時実行数設定のみ残存（旧名の残骸）
※2: `/analytics/active`（リアルタイム閲覧者数）はここにある。削除すると画面の数字が消える

### DynamoDB テーブル（現状）

| テーブル | 用途 | Phase A 必要? |
|---|---|---|
| p003-topics | メイン SoT | ✅ |
| ai-company-bluesky-posts | Bluesky重複防止 | ✅ |
| flotopic-rate-limits | レートリミット | ✅ |
| ai-company-comments | コメント | ❌ Phase C |
| flotopic-favorites | お気に入り | ❌ Phase C |
| flotopic-analytics | 行動ログ | ⚠️ analytics/active に使用 |
| flotopic-users | ユーザー管理 | ❌ Phase C |
| ai-company-audit | 用途不明 | ❌ 要確認後削除 |

### processor の Claude API スキップ条件（現状・handler.py で散在）

現在 `handler.py` のメインループに以下が散在している：
1. `articleCount < 2` → 常にスキップ
2. Tier-0 未消化中は非Tier-0をスキップ
3. `aiGenerated=True` かつタイトルあり → タイトル再生成スキップ
4. `aiGenerated=True` かつ 48h 以内 かつ新記事なし かつ keyPoint 充足 → ストーリー生成スキップ
5. `proc_storage.py`の `needs_ai_processing` フラグ（get_topics_by_ids 内）

**問題**: 条件が複数箇所にあり、どれが効いているか把握しにくい。

---

## 目標設計（変えること・変えないこと）

### 変えないもの（触らない）

- `fetcher/handler.py` およびその依存モジュール一切
- `processor/handler.py` のメインループ本体
- `processor/proc_ai.py` のプロンプト・AI呼び出し処理
- `lifecycle/handler.py`
- CloudFront・DynamoDB p003-topics のスキーマ

### ルール1: 読み取りは S3 だけ（DynamoDB フォールバックを削除）

**変更対象**:
- `api/handler.py` の `all_topics()`: S3優先・DDBフォールバックあり → S3のみに（失敗したら503）
- `api/handler.py` の `topic_detail()`: DynamoDB Query → S3 `api/topic/{id}.json` を読む
- `fetcher/storage.py` の `get_all_topics()`: S3優先・DDBフォールバックあり → S3のみに

**切り戻し**: S3直読みが安定したらDBフォールバックを削除。段階的に実施。

### ルール2: Claude API スキップ条件を一箇所に集約

`handler.py` の散在したスキップ条件を `proc_ai.py` に `should_call_claude()` として集約。
**ただし**: 既存の条件を変えるのではなく、「読める形にまとめる」だけ。動作は変えない。

### Phase A 不要コンポーネントの削除

削除する前に中身を確認する。データがあるテーブルは慎重に。

| 削除対象 | 手順 |
|---|---|
| flotopic-auth Lambda + EventBridge | Lambda削除 → EventBridgeルール削除 |
| flotopic-comments Lambda | Lambda削除 |
| flotopic-favorites Lambda | Lambda削除 |
| ai-company-comments DDB | scan で空確認 → 削除 |
| flotopic-favorites DDB | scan で空確認 → 削除 |
| flotopic-users DDB | scan で空確認 → 削除 |
| flotopic-contact（残骸） | 同時実行数設定だけ削除 |
| ai-company-audit DDB | 中身確認 → 削除 |

**flotopic-analytics と flotopic-cf-analytics は保留**: `/analytics/active` への影響を先に確認

### Bluesky 頻度変更

`deploy.sh` 353行目: `rate(30 minutes)` → `cron(0 0,8,12 * * ? *)` （JST 9:00/17:00/21:00の1日3回）

---

## 実装順序（切り戻しを意識した段階的移行）

### Step 1: スキップ条件の可視化（コスト削減・リスク低）

`proc_ai.py` に `should_call_claude()` を追加。既存ロジックは変えない。
ログ出力で何件スキップされているか見えるようにする。

### Step 2: `api/handler.py` の S3一本化（DynamoDB Read 削減）

`/topics` と `/topic/{id}` の両方を S3 から読むように変更。
DDBフォールバックは 2週間並走させてからエラーがなければ削除。

### Step 3: 不要 Lambda・テーブルの削除（Phase A クリーンアップ）

auth / comments / favorites 系。データが空なら即削除。データがあれば確認。

### Step 4: Bluesky 頻度変更

スケジュール変更のみ。

### Step 5: keyPoint 64%→70% の根本対処（フェーズ2完了）

**調査完了（2026-05-04）— コードレビューで以下を確認済み。**

---

#### 調査結果1: `[AI_FIELD_GAP] background empty` — 100% Dead Code ノイズ

**原因（行番号まで）**:

- `proc_ai.py:1117` のコメント: "削除: spreadReason, backgroundContext, background, whatChanged" — T2026-0428-J/E の設計変更で `background` フィールドはスキーマから完全削除済み。Claude はこのフィールドを一切生成しない。
- `proc_storage.py:1254–1260` に削除前の残骸が残っている:
  ```python
  if gen_story.get('background'):  # 永遠に False
      ...
  else:
      print(f"[AI_FIELD_GAP] background empty topic={tid}")  # 毎回発火
  ```
- `handler.py:37` の `_PROC_INTERNAL` に `'background'` が含まれており、S3 への配信もブロックされている

**コスト影響**: **ゼロ**。Claude API 呼び出しの無駄はない。ログが出るだけ。

**修正方針**:
- `proc_storage.py` の dead code ブロック（1254–1260）を削除するだけ
- `handler.py` の `_PROC_INTERNAL` から `'background'` と `'backgroundContext'` を削除（もう書き込まないので除外不要）
- リスク: ほぼゼロ（dead code 削除のみ）

---

#### 調査結果2: `[AI_FIELD_GAP] perspectives null/empty` — 2種類ある

**Type A（ノイズ・期待挙動）— cnt=1 トピック**:

- `proc_ai.py:1044`: cnt=1 → `_generate_story_minimal()` → cnt=1 の場合 perspectives はスキーマに追加されない (`proc_ai.py:1480–1481`: `has_perspectives = cnt >= 2`)
- `_normalize_story_result('minimal')` の line 1265: perspectives=None を返す
- `proc_storage.py:1261` のチェックが None を検知 → ログ発火
- **これは仕様通りの挙動**。API コスト無駄なし。

**Type B（実質的なギャップ）— cnt>=2 で perspectives が充填されない**:

- cnt>=2 の標準/フルモードでは `perspectives` は `required` かつ `minLength=80` だが、Tool Use API の応答が空の場合（まれ）または API エラーで `gen_story=None` の場合、perspectives は書き込まれない
- **重大なギャップ**: `proc_storage.py:1096–1167` の `_is_fully_filled()` は perspectives を**チェックしない**。同様に `needs_ai_processing()` (line 345–426) も perspectives を**チェックしない**
- 結果: perspectives が空のトピックが他のフィールドを満たすと `_is_fully_filled=True` → 永遠に再処理されない
- ただし頻度は低い（minLength=80 の schema enforcement があるため）

---

#### 調査結果3: keyPoint 空文字指示の矛盾（部分的バグ）

`_SYSTEM_PROMPT` (`proc_ai.py:1625`) と `_STORY_PROMPT_RULES` (`proc_ai.py:1552`) に以下が残存:
```
「何が変わったのか」が書けない場合は空文字 ("") を返す
```

T2026-0503-UX-NO-KEYPOINT-23 で schema description の "空文字禁止" は追加されたが、system prompt 側の「空文字を返す」指示は**削除されていない**。Claude が矛盾した指示を受け取っている。

ただし `proc_ai.py:1449–1453` の aiSummary fallback が存在:
```python
if not final_kp:
    ai_summary = str(result.get('aiSummary') or '').strip()
    if ai_summary:
        result['keyPoint'] = ai_summary  # 空 keyPoint を aiSummary で代替
```
この fallback により、空文字が最終的に保存されるケースは限定的。

---

#### 調査結果4: keyPoint 64% の直接原因

**コードバグではなく処理バックログ**:
- 可視トピック 463件中、AI未処理が163件（35%）
- 163件 = aiGenerated=False または keyPoint 欠落のトピックが pendingAI=True のまま待機中
- 2x/day の定期実行（MAX_API_CALLS=30/回）で 60件/日しか処理できないため自然に解消されるが時間がかかる
- `handler.py:287`: API呼び出し上限到達で残件は次回に回される

**background/perspectives の AI_FIELD_GAP ログは keyPoint 充填率と無関係**。

---

#### 修正方針（既存動作を壊さない最小変更）

**優先度: 高（dead code 削除）**:

1. `proc_storage.py:1254–1260` の `background` dead code 削除
   - リスク: ゼロ（ログノイズ除去のみ）
   - 効果: CloudWatch ノイズ削減・監視精度向上

2. `handler.py:37` の `_PROC_INTERNAL` から `'background'`, `'backgroundContext'` を削除
   - リスク: ゼロ（もう書き込まれないため除外は不要だが、明示的にクリーンアップ）

**優先度: 中（perspectives の永久スキップ防止）**:

3. `proc_storage.py` の `_is_fully_filled()` に perspectives チェックを追加（ac>=2 のみ）:
   ```python
   # ac>=2 では perspectives が必須 (cnt=1 は除外)
   _ac = int(item.get('articleCount', 0) or 0)
   if _ac >= 2 and not str(item.get('perspectives') or '').strip():
       return False
   ```
   - リスク: 低。perspectives=None の既存トピックが再処理キューに入る（品質改善）
   - ただし既存 aiGenerated=True の全 ac>=2 トピックが再処理対象になるため、バックログが増える可能性あり → 実装タイミングは検討

**優先度: 低（system prompt の矛盾解消）**:

4. `_SYSTEM_PROMPT` (`proc_ai.py:1625`) と `_STORY_PROMPT_RULES` (`proc_ai.py:1552`) から「空文字を返す」指示を削除し、「変化が不明確な場合は aiSummary の言い換えを使う」に変更
   - ただしこれはプロンプト変更→ cache 破棄→コスト増なので慎重に
   - aiSummary fallback が既に機能しているため緊急度は低

---

#### 実装ステップ（調査後の計画）

1. **PR-A**: `proc_storage.py` dead code 削除（修正1）+ `_PROC_INTERNAL` クリーンアップ（修正2）— 5分・リスクゼロ
2. **PR-B**: `_is_fully_filled()` に perspectives チェック追加（修正3）— 要バックログ影響確認後
3. keyPoint 充填率向上は主にバックログ消化を待つ。PR-A/B で自然に改善されるはず

### Step 6: インクリメンタル・チャプター型ストーリー（2026-05-04 再設計）

**背景**: 記事が出るたびに全文書き換えは品質的にも正しくない。事実は変わらない。起きたことを時系列で積み上げていく「チャプター型」に変える。

**根本方針**:
- チャプターは追記のみ（append-only）。過去の章は絶対に書き換えない
- 記事リンクはストーリー本文に並べない。別ページ（記事一覧ページ）に出す
- 「〜の可能性」「〜かもしれない」は禁止。断定形で書く
- スカスカな一般論の要約は不要。多少尖っていて構わない
- コスト削減はモデル変更ではなくコードで（送るトークンを減らす）
- まず政治経済カテゴリ1件で試す

#### データスキーマ（DynamoDB p003-topics に追加するフィールド）

```json
{
  "background": "（初回生成・以後変更不可）トピックが生まれた背景・文脈",
  "keyPoint": "（初回生成・以後変更不可）このトピックの最大の注目点",
  "chapters": [
    {
      "date": "2026-04-30",
      "summary": "この日/期間に起きた事実だけを1〜3文で",
      "commentary": "なぜ重要か・何が変わるか・何に影響するか（解説・AI予測）",
      "prediction": "次に何が起きるか（断定形・根拠付き）",
      "articleIds": ["article-id-1", "article-id-2"]
    }
  ],
  "outlook": "（最新チャプターから定期更新）現時点での展望",
  "relatedTopicIds": [],
  "lastChapterDate": "2026-05-03"
}
```

#### プロンプト設計方針

- `background` と `keyPoint` は初回のみ生成。再生成不可
- `chapters` への追加は「`lastChapterDate` 以降の新着記事だけ」を渡す（差分処理でコスト削減）
- 1チャプター = 同じ日付に近い記事群。記事が多い場合は週単位でまとめてよい
- `commentary` にはAIの見解・解説を必ず入れる（「関税が上がると何が困るか」レベルの説明）
- `prediction` は確信度パラメータに関わらず断定形で書く（外れる前提でよい）
- `summary` は純粋な事実のみ。意見・予想は入れない

#### 実装フェーズ

| フェーズ | 内容 | 前提 |
|---|---|---|
| **S0** | 手動設計: 政治経済カテゴリの記事数最多トピックで「正解サンプル」JSON を作る | POレビューまで |
| **POレビュー** | S0 の正解サンプルを確認してプロンプト方針を確定 | S0完了後 |
| **S1** | DynamoDB スキーマ拡張: `chapters` / `background` / `relatedTopicIds` フィールド追加。読み取り互換性確認 | POレビュー通過後 |
| **S2** | processor 変更: 差分処理・`lastChapterDate` 以降の記事のみ送る・`CHAPTER_MODE_GENRES=politics` 環境変数でジャンル限定 | S1完了後 |
| **S3** | フロントエンド変更: チャプター型タイムライン表示・記事リスト別ページ | S2完了・POレビュー後 |
| **S4** | 全ジャンル展開 | S3で政治経済の品質確認後 |

**切り戻し**: `CHAPTER_MODE_GENRES` を空にすれば既存処理に戻る（S2の時点で環境変数ゲート）。

**禁止**: S0〜POレビューの間はコードを書かない。設計と正解サンプル確定が先。

### Step 7: proc_ai.py の責務分割（コード長さ対策）

**背景**: proc_ai.py が2000行超。Phase C でコメント処理等が追加されるとさらに肥大化する。

**方針**: ロジックを変えずにファイル分割のみ行う。

| 新ファイル | 移動する内容 |
|---|---|
| `proc_prompts.py` | プロンプトテンプレート文字列 |
| `proc_genre.py` | ジャンルヒント・分類ロジック |
| `proc_formatter.py` | S3 JSON 生成・フォーマット処理 |
| `proc_ai.py`（残す） | Claude API 呼び出し・スキップ判断のみ |

**原則**: 既存の関数シグネチャ・動作は変えない。import だけ変わる。
**テスト**: boundary test（0件・null・未来日付）を各 formatter に追加。

---

## 残作業・保留事項（2026-05-04 時点）

| 項目 | 状態 | 対応 |
|---|---|---|
| `fetcher/storage.py` DDB フォールバック削除 | 未着手 | Step 2 の続き。api 側完了後に実施 |
| `flotopic-auth` Lambda 削除 | IAM権限不足で未完 | コンソール手動削除 or IAM 設定変更後 |
| `flotopic-favorites` Lambda 削除 | IAM権限不足で未完 | 同上 |
| `flotopic-analytics` / `flotopic-cf-analytics` 要否確認 | 保留 | `/analytics/active` の使用状況確認後に判断 |

---

## 今後のフェーズのための準備

Phase C で auth/comments/favorites を追加するとき：
- S3 JSON スキーマを壊さない形で追加する
- DynamoDB のテーブル設計は変えない（新テーブルを足す）
- 既存の fetcher・processor は触らない
- proc_ai.py の分割（Step 7）完了後であれば、Phase C 処理は新ファイルに追加する

---

> **更新ルール**: 実装中に「書いていない変更が必要」と気づいたら実装を止めてここを更新してから再開する。
