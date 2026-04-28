# AI フィールドカタログ（proc_ai.py → frontend 5 層追跡表）

> **目的**: AI 生成フィールドが「proc_ai schema → normalize → handler ai_updates → topics.json merge / 個別 topic JSON / DynamoDB → frontend (card / detail)」の 5 層を通る間にどこで欠落・除外されるかを 1 表で把握する。
>
> **背景**: 2026-04-28 に keyPoint 充填率 11.5% (success-but-empty) を発見した際、各層を grep で照合する作業に時間がかかった。「ai_updates dict にあるが topics.json merge ループで漏れ」(T249) のような層間欠落バグを物理的に検知できる仕組みの基礎。
>
> **更新ルール**: proc_ai.py の output schema を変更したら本ファイルも同 commit で更新する。CI で proc_ai.py 内の schema field 名と本ファイル先頭表の field 名一覧を突合（T256 で実装予定）。

---

## 5 層の責務

| 層 | ファイル | 責務 |
|---|---|---|
| L1 | `lambda/processor/proc_ai.py:_build_story_schema` | Tool Use 用 JSON Schema 定義（mode 別に出力フィールドを宣言） |
| L2 | `lambda/processor/proc_ai.py:_normalize_story_result` | tool_use.input → 内部 dict 正規化（型変換・enum 矯正・空文字防御） |
| L3 | `lambda/processor/handler.py` `ai_updates[tid] = {...}` (L267-) | DynamoDB / S3 publish 用の per-topic dict を構築 |
| L4a | `lambda/processor/handler.py` topics.json merge ループ (L302-) | 一覧用 `topics.json` (card) に merge。`_PROC_INTERNAL` 集合のフィールドは publish 除外（size 抑制） |
| L4b | `lambda/processor/proc_storage.py:update_topic_s3_file` | 個別 `api/topic/{tid}.json` (detail) に merge。除外フィルタ無し |
| L5a | `frontend/app.js` カード描画 | `topics.json` から読み出し card 表示 |
| L5b | `frontend/detail.js` 詳細描画 | `api/topic/{tid}.json` + `topics.json` から読み出し detail 表示 |

`_PROC_INTERNAL` (handler.py:30) = `{'SK', 'pendingAI', 'ttl', 'spreadReason', 'forecast', 'storyTimeline', 'backgroundContext'}` は **L4a で publish 時に除外**される（size 抑制 = topics.json を 250KB 未満に保つ設計）。これらは L4b 個別 JSON / DynamoDB にのみ載る。

---

## フィールド一覧（schema mode = full 基準）

| field | L1 schema | L2 normalize | L3 ai_updates | L4a topics.json | L4b topic.json | L5a card | L5b detail | 備考 |
|---|---|---|---|---|---|---|---|---|
| `aiSummary` | ✅ | ✅ | → `generatedSummary` | ✅ | ✅ | ✅ | ✅ | カードと詳細両方で表示 |
| `keyPoint` | ✅ | ✅ (400字 cap) | ✅ | ✅ (T249 で merge 修正) | ✅ | ✅ ヒーロー枠 | ✅ ヒーロー枠 | **T2026-0428-J/E で 200〜300 字物語形式に拡張** |
| `statusLabel` | ✅ (standard/full) | ✅ (enum 矯正) | ✅ | ✅ | ✅ | ✅ chip | ✅ | T2026-0428-J/E: 発端 / 進行中 / 沈静化 / 決着 (読者向け 4 値) |
| `watchPoints` | ✅ (standard/full) | ✅ (200字 cap) | ✅ | ✅ | ✅ | — | ✅ | T2026-0428-J/E: ① ② ③ 番号付きの観察視点 |
| `outlook` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 末尾 | ✅ | 文末に [確信度:高/中/低] 必須。T2026-0428-PRED で当否自動判定 |
| `forecast` | ✅ (full のみ) | ✅ | ✅ | ⛔ `_PROC_INTERNAL` で除外 | ✅ | — | ✅ | 文末確信度ラベル必須 |
| `perspectives` | ✅ (standard/full) | ✅ | ✅ | ✅ | ✅ | — | ✅ | 各社の懸念・着目点（並列列挙） |
| `timeline` | ✅ (standard/full) | ✅ (max 6 / 3) | → `storyTimeline` | ⛔ `_PROC_INTERNAL` で除外 | ✅ | — | ✅ | 因果タイムライン (subfields: `date`/`event`/`transition`) |
| `phase` | ✅ (enum) | ✅ ('発端' 矯正) | → `storyPhase` | ✅ | ✅ | ✅ chip | ✅ | T219 で「3件以上で発端禁止」 |
| `topicTitle` | ✅ | ✅ (15字 cap) | ✅ | ✅ | ✅ | ✅ | ✅ | テーマ名（体言止め） |
| `latestUpdateHeadline` | ✅ | ✅ (40字 cap) | ✅ | ✅ | ✅ | ✅ | ✅ | 最新の動き |
| `isCoherent` | ✅ | ✅ | → `topicCoherent` | ✅ | ✅ | (filter) | (filter) | false → auto archive |
| `topicLevel` | ✅ (enum) | ✅ | ✅ | ✅ | ✅ | — | — | major/sub/detail |
| `parentTopicTitle` | ✅ | ✅ (30字 cap) | ✅ | ✅ | ✅ | — | — | 親テーマ |
| `relatedTopicTitles` | ✅ (max 3) | ✅ | ✅ | ✅ | ✅ | — | ✅ | 関連トピック |
| `genres` | ✅ (enum array) | ✅ (validate) | ✅ + `genre` | ✅ + `genre` | ✅ + `genre` | ✅ chip | ✅ | enum 違反は除外 |
| `summaryMode` | — (computed) | — | ✅ | ✅ | ✅ | — | (filter) | minimal/standard/full |

---

## 観測 SLI とフィールドの対応（2026-04-28 現在）

| SLI | 観測対象フィールド | 観測層 | 現状 | 警告閾値 |
|---|---|---|---|---|
| SLI 1 topics.json 鮮度 | `updatedAt` | L4a | FRESH (< 5 分) | > 90 分 |
| SLI 3 AI カバレッジ | `aiGenerated` | L4a | 80.9% (FRESH) | < 70% |
| SLI 4 storyPhase 偏り | `storyPhase` | L4a | 「発端」47.0% (警告寸前) | > 50% |
| SLI 8 keyPoint 充填率 | `keyPoint` | L4a | **8.7% (RED)** | < 70% |
| SLI 9 perspectives 充填率 | `perspectives` | L4a | 20.0% (RED) | < 50% |
| SLI 10 outlook 充填率 | `outlook` | L4a | 50.4% (警告寸前) | < 70% |

**カバー漏れ検出 (2026-04-28 schedule-task)**:
- L4a 除外フィールド (`backgroundContext` / `spreadReason` / `forecast` / `storyTimeline`) は L4b でのみ観測すべき。topics.json で 0% を見て「失敗」と誤判定しない。
- 充填率 SLI は L4a のみ。L4b (個別 topic JSON) でも同様に集計するスクリプトが必要 → T2026-0428-Q success-but-empty 横展開で起票済。

---

## 既知の層間欠落バグ（再発防止参照）

| 日付 | バグ ID | 欠落層 | 原因 | 修正 |
|---|---|---|---|---|
| 2026-04-28 | T249 | L3 → L4a | `keyPoint` / `backgroundContext` を `ai_updates` に入れたが topics.json merge ループ追加漏れ | handler.py L312-313 で merge 追加 |
| 2026-04-28 | T255 | L3 skip 判定 | 旧 aiGenerated topic が `keyPoint=None` のまま skip されて再生成されない | handler.py L228 `_required_full_fields` に keyPoint 追加 |

**横展開チェック**: 新フィールドを追加する PR は **L1〜L5 の各層を grep し、merge / publish ロジックに含まれているか** を確認する。CI 自動化 (T256) で物理ガード化予定。

---

## 更新履歴

- 2026-04-28 07:13 schedule-task: 初版作成。本番 `topics.json` を curl して各 SLI 数値を実測 (115 topics, AI 80.9%, keyPoint 8.7%)。`_PROC_INTERNAL` 除外仕様を明文化。T245 起票事項の主目的を実装。
