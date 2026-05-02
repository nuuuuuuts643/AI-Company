# P003 embedding 移行 技術調査 (T2026-0502-U)

> **目的**: fetcher の bigram Jaccard + Haiku borderline 構成を embedding ベースに移行し、kill switch (`AI_MERGE_ENABLED=false`) で停止中の merge judge 機能を **コスト発生なしで品質維持** で復活させる。さらに processor 側の冗長 AI 生成も embedding 事前フィルタで削減。
>
> **状態**: 2026-05-02 14:45 JST 初版 (Cowork セッション中の WebSearch / WebFetch 公開情報のみで作成・実測 API 呼び出しなし)
> **次アクション**: Code セッションで PoC 実装 (sentence-transformers Lambda layer + scripts ベンチ)

---

## 1. embedding 候補比較

| 候補 | 種類 | コスト/M tok | 次元数 | レイテンシ (1記事) | 日本語精度 | Lambda 配置 |
|---|---|---|---|---|---|---|
| **voyage-3-lite** | API | $0.02 | 512 / 1024 | ~50ms (HTTP) | ◎ (multilingual・Anthropic 推奨) | 環境変数で API key | 
| voyage-4-lite | API | $0.02 | 512 / 1024 | ~50ms (HTTP) | ◎ (2025 リリース) | 同上 | 
| OpenAI text-embedding-3-small | API | $0.02 | 1536 (削減可) | ~80ms (HTTP) | ◎ | 同上 |
| **multilingual-e5-small (ONNX/qint8)** | ローカル | **$0** | 384 | **~5ms (CPU)** | ◎ (intfloat 公式・Japanese MTEB 上位) | **Lambda layer 118MB** (250MB 制限内) |
| multilingual-e5-base | ローカル | $0 | 768 | ~12ms | ◎+ | ~470MB → layer 不可・S3 ダウンロード or container image |
| Cohere embed-multilingual-light-v3 | API | $0.10 | 384 | ~80ms | ○ | 環境変数 |

**第一候補: multilingual-e5-small (ONNX qint8) ローカル実行**
- 月額コスト 完全 $0
- レイテンシも API 呼び出しより速い (5ms vs 50ms)
- 118MB → Lambda layer 1 個 (Lambda layer は最大 5 個 / 250MB / function)
- Anthropic/OpenAI と違って rate limit なし

**第二候補: voyage-3-lite (or voyage-4-lite) API**
- 5000 articles/日 × 50 token = 250K tok/日 = **7.5M tok/月**
- voyage は 200M tok/account 無料枠 → **約 26 ヶ月無料**
- 無料枠超過後でも 7.5M × $0.02 = **$0.15/月** で激安
- API 障害時のフェイルオーバー考慮するなら local 実装と組み合わせ

---

## 2. Lambda layer / zip サイズ実測 (公開情報ベース)

### multilingual-e5-small ONNX qint8

| 項目 | サイズ |
|---|---|
| HuggingFace `deepfile/multilingual-e5-small-onnx-qint8` | **118 MB** |
| onnxruntime python wheel (linux x86_64) | ~12 MB |
| sentencepiece + tokenizers | ~6 MB |
| numpy (boto3 同梱で既存) | 0 (流用) |
| **合計 (Lambda layer 1個)** | **~136 MB** |
| Lambda layer 上限 | 250 MB |
| 余裕 | 114 MB |

**結論**: Lambda layer 1 個で収まる。container image 化不要で zip ベース運用維持可能。

### sentence-transformers (フル) PyTorch ベース

| 項目 | サイズ |
|---|---|
| sentence-transformers + torch CPU | ~600 MB |
| 結論 | **NG**・layer に収まらない・container image 必須 |

→ **ONNX runtime 経由の qint8 推論一択**。`from optimum.onnxruntime import ORTModelForFeatureExtraction` で読める。

---

## 3. DynamoDB embedding ストレージコスト試算

### embedding 永続化が必要な理由

- 既存 topics (~5000件 / 30日 lookback) の merge 判定で「過去 topic との類似度」を毎 fetcher run で計算する必要あり
- 毎回再計算するとローカル推論でも 5000×5ms = 25s/run の overhead → DB に保存して再利用

### サイズ計算

| 項目 | 計算 | 値 |
|---|---|---|
| 1 embedding (384 dim × float32) | 384 × 4 bytes | 1,536 bytes |
| qint8 で保存すれば | 384 × 1 byte | 384 bytes |
| base64 で文字列化 | × 1.33 | 510 bytes (qint8) / 2,048 bytes (fp32) |
| 1 topic レコードへの追加 (qint8) | +510 bytes | |
| 5000 topics × 510 bytes | | **2.5 MB** |

### DynamoDB on-demand 料金

| 項目 | 計算 | 月額 |
|---|---|---|
| ストレージ ($0.25/GB) | 0.0025 GB × $0.25 | **$0.001/月** (誤差) |
| WCU (新 topic 書き込み 100/日) | $1.25/M write × 100×30 | $0.004/月 |
| RCU (毎 fetcher run 5000 read × 48 run/日) | 240K read/日 × 30 | 7.2M read/月 → eventually consistent → $0.25/M = $1.80/月 |

→ **DynamoDB 追加コスト合計: ~$1.80/月**

### 削減オプション (RCU 削減)

- topic embedding を **S3 object 1個 (JSON)** に集約 → fetcher 起動時に 1 回 download (~2.5MB)
- S3 GET = $0.0004/1000 req × 48 run/日 × 30 = **$0.0006/月** (誤差)
- DynamoDB 不要 → 月額 $0 に近い

**結論**: S3 集約方式採用なら追加コスト実質 0。

---

## 4. processor 側 AI 生成の embedding 部分置換

### 削減候補

| 既存処理 | embedding 置換可能性 | 月コスト削減見込み |
|---|---|---|
| `generate_title` (Haiku) | ❌ 創造的タイトル生成は LLM 必要 | 0 |
| `generate_story` (Haiku) | ❌ keyPoint/perspectives/outlook の自然言語生成は LLM 必要 | 0 |
| `judge_prediction` (Haiku) | △ outlook ⇔ new article titles の意味類似度判定なので embedding cosine sim で代替可 | $0.30/月 (1日1回 = ¢1/日) |
| **「topic に変化がなければ skip」事前判定** | ◎ 直近 articles の embedding が既存 keyPoint と cosine sim > 0.95 ならスキップ | **$3-6/月** (140 calls/日 → ~70-100 calls/日) |
| **`_generate_story_full` mode のフォールバック判定** | ◎ articles 内の意味分散 (embedding 分散) で full mode 必要性を判定。今は cnt>=8 で機械的に full | $1-2/月 (full→standard 転換) |

### 期待効果

- 現状 processor: $12/月
- embedding skip + 予算最適: **$6-8/月** (約 40-50% 削減)
- これ以下にしたければ ニュース更新頻度自体を下げる (UX に影響) しかない

---

## 5. 段階移行計画

### Phase 1: PoC (1 セッション・Code 担当)
1. `lambda/fetcher/embedding_layer/` 新設・ONNX qint8 model + onnxruntime 同梱
2. `scripts/embedding_bench.py` で benchmark: 5000 articles をローカルで embedding → cosine sim 行列計算 → 既存 Jaccard 結果と比較
3. 評価: 「欧州駐留米軍 vs ドイツ駐留米軍」が cosine sim > 0.85 で同一クラスタになるか
4. **Eval-Done**: bench 結果を `docs/p003-embedding-bench.md` に書く

### Phase 2: fetcher merge judge 置換 (1-2 セッション)
1. `fetcher/embedding_judge.py` 新設 — 既存 `ai_merge_judge.py` と同じ interface (judge_pairs)
2. embedding cosine sim > 0.85 → same event / 0.65-0.85 borderline → Haiku fallback (env で切替可) / <0.65 → different
3. 既存 borderline 1100 pairs/run のうち、embedding で **95% 以上が high-confidence で決定** されることを実測
4. `AI_MERGE_ENABLED=false` 維持 + `EMBEDDING_MERGE_ENABLED=true` で運用 → fetcher cost $0 維持しつつ品質回復

### Phase 3: processor 事前 skip 判定 (1 セッション)
1. `processor/embedding_skip.py` 新設
2. topic の `latestKeyPointEmbedding` を DynamoDB に保存
3. 新 articles の embedding が既存 keyPoint と sim > 0.95 → AI 再生成 skip → `aiGenerated=True` だけ更新
4. 評価: SLI keyPoint 充填率の維持確認 (skip しても古いまま使われるので新鮮度は下がる懸念 → SLI で監視)

### Phase 4: S3 embedding cache (おまけ・コスト削減)
1. `topics-embedding.json` を S3 に毎 processor run で更新
2. fetcher は起動時に 1 回 download → メモリ上で類似度計算
3. DynamoDB 書き込み削減

---

## 6. リスクと反対意見

### 品質劣化リスク

- **embedding cosine sim > 0.85 の閾値が外れることがある**
  - 例: 「米国 GDP 速報値 2.0%」と「日本 GDP 速報値 2.0%」が embedding 上で似て見えるかも (主体異なるのに数値類似)
  - 対策: entity gate (現状の SYNONYMS / ENTITY_PATTERNS ベース) を embedding 判定の前段に維持
- **multilingual-e5-small の日本語精度が固有名詞で弱い可能性**
  - 対策: PoC で実測。劣化したら voyage-3-lite (API) に切替

### 運用リスク

- **Lambda cold start が +500ms**
  - fetcher は 30 分間隔なのでコールドスタート発生する
  - 対策: provisioned concurrency = 1 にする ($3/月) or warm-up cron 追加
- **ONNX runtime のバイナリ互換**
  - `manylinux2014_x86_64` wheel を Lambda Linux 2023 で動作確認必要
  - 対策: PoC で確認 / 失敗したら docker image build 経由

### 巻き戻しリスク

- 思想変化 (例: 「やっぱり Haiku merge 復活したい」) 時の戻し方
- 対策: `EMBEDDING_MERGE_ENABLED` env flag で旧 Jaccard ロジックに即戻せるようにする

---

## 7. 推奨案

**短期 (今週・Phase 1+2)**:
- multilingual-e5-small ONNX qint8 を Lambda layer に同梱
- fetcher merge judge を embedding ベースに置換
- 月コスト: fetcher $0 + processor $12 = **$12 維持**
- 効果: false-split 自動マージが Haiku 不要で復活

**中期 (来月・Phase 3+4)**:
- processor の事前 skip 判定追加
- S3 embedding cache 導入
- 月コスト: fetcher $0 + processor $6-8 = **~$8/月**
- 効果: 「変化のない topic」を AI 再処理しない

**長期 (もし更に削るなら)**:
- ニュース更新頻度を 30分 → 1時間に (UX への影響を SLI 観察)
- processor 1日1回に
- 月コスト: ~$4/月

---

## 8. 参考リンク

- [Voyage AI Pricing](https://docs.voyageai.com/docs/pricing) — voyage-3-lite $0.02/M, 200M free tier
- [Multilingual E5 Technical Report (arXiv)](https://arxiv.org/abs/2402.05672)
- [intfloat/multilingual-e5-small (HuggingFace)](https://huggingface.co/intfloat/multilingual-e5-small)
- [deepfile/multilingual-e5-small-onnx-qint8 (118MB)](https://huggingface.co/deepfile/multilingual-e5-small-onnx-qint8)
- [Sentence Transformers Efficiency Guide](https://sbert.net/docs/sentence_transformer/usage/efficiency.html)
- [Embedding Models Pricing 2026](https://awesomeagents.ai/pricing/embedding-models-pricing/)

---

> **次アクション**: Code セッションで Phase 1 PoC 実装 → 結果次第で Phase 2 へ進む。本ドキュメントは Phase 1 完了時に bench 結果と推奨閾値を追記して living document として更新する。
