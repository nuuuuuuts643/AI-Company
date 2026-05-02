# Code セッション起動プロンプト: T2026-0502-U Phase 1→2→3→4 オーケストレーター

> **これを丸ごと Code セッションに渡してください**
> **作成**: 2026-05-02 16:30 JST (Cowork)
> **想定セッション数**: 1-3 セッション (Phase 1+2 で 1 セッション、Phase 3+4 で 1-2 セッション)
> **モデル**: Sonnet 4.6 (Phase 1 PoC は精度勝負・Sonnet 推奨)

---

## ⚡ 最初に必ずやること（コピペ可）

```bash
cd ~/ai-company/AI-COMPANY
bash scripts/session_bootstrap.sh
# 起動チェック完了の表示を確認
git log --oneline -5 -- CLAUDE.md docs/p003-embedding-migration-research.md
# 直近 commit に PR #225/#226/#227/#229 が含まれていることを確認 (Cowork 5/2 PM landing)
cat docs/session-prompts/T2026-0502-U-phase1-2.md | head -50  # Phase 1+2 詳細 prompt
cat docs/p003-embedding-migration-research.md | head -100      # 設計根拠
```

WORKING.md に着手宣言:

```bash
echo "| [Code] T2026-0502-U-ORCHESTRATOR Phase 1+2 (+continuation) | Code | docs/p003-embedding-migration-research.md, lambda/fetcher/handler.py, scripts/embedding_bench.py の実行結果 | $(date '+%Y-%m-%d %H:%M') | yes |" >> WORKING.md
git add WORKING.md && git commit -m "wip: T2026-0502-U-ORCHESTRATOR 着手" && git push
```

---

## 背景（30 秒で読める要約）

P003 Flotopic の fetcher で Haiku merge judge (月 $120) が品質効果不明のまま走っていた。
Cowork が止血 (`AI_MERGE_ENABLED=false` で Haiku call=0) → 月 $0 達成。これを **embedding
ベース (multilingual-e5-small ONNX qint8・月 $0) に置換して品質回復**するのが本タスク。

### 既に Cowork が landing 済 (PR #223/#225/#229)

```
projects/P003-news-timeline/
  lambda/fetcher/embedding_judge.py     # AIMergeJudge と互換 interface・ONNX backend + Mock backend
  tests/test_embedding_judge.py         # 8/8 PASS
scripts/
  build_embedding_layer.sh              # Lambda layer build (Mac 必須)
  embedding_bench.py                    # 6 fixture で cosine 計測
docs/
  p003-embedding-migration-research.md  # 設計・コスト試算
  session-prompts/
    T2026-0502-U-phase1-2.md            # Phase 1+2 詳細手順
    T2026-0502-U-phase3.md              # Phase 3 詳細手順
    T2026-0502-U-phase4.md              # Phase 4 詳細手順 (おまけ)
```

### 既に物理化済 (PR #226 で T2026-0502-AA landing)

`feat:`/`fix:`/`perf:` コミットには **`Verified-Effect:` か `Verified-Effect-Skip:` か `Verified-Effect-Pending:` が必須**。
commit-msg hook が自動 reject。helper コマンド: なし (手動で書く)。
PR #227 (keyPoint ジャンル例追加) で `Verified-Effect-Pending: 2026-05-09` 形式実例あり。

---

## 進行ロジック (decision tree)

```
[START]
   │
   ▼
[Phase 1: PoC bench] (10-15 分)
   │
   ├─ misses = 0 / 6 ? ──No──▶ STOP. 結果を docs に追記して報告。embedding 採用見送り。
   │
   ▼ Yes
[Phase 2: fetcher 統合] (30-45 分)
   │
   ├─ deploy 後 30 分の fetcher_health で judge_type=OnnxEmbeddingBackend かつ haiku_pairs_asked=0 ?
   │  (schedule task で 30 分後検証・Code は immediate exit)
   │
   ├─ 確認できない / NG ──▶ env で EMBEDDING_MERGE_ENABLED=false で revert・原因特定タスクを TASKS.md に積む
   │
   ▼ OK
[Phase 3: processor skip] (60-75 分)
   │
   ├─ deploy 後 24h schedule task で skip_rate >= 30% かつ keyPoint 充填率維持 ?
   │
   ├─ skip_rate < 10% ──▶ 効果薄い → 完了扱いで Phase 4 進む or 一旦 stop
   ├─ 充填率低下 ──▶ EMBEDDING_SKIP_THRESHOLD 0.95→0.97 に上げて再 deploy
   │
   ▼ OK
[Phase 4: S3 cache] (30-45 分・おまけ)
   │
   ├─ Phase 5 以降に embedding 拡張予定なし ──▶ skip OK (TASKS.md に retire)
   │
   ▼ 実装する場合
[Phase 4 完了]
   │
   ▼
[FINISH]
   - HISTORY.md に T2026-0502-U 完了記録
   - TASKS.md T2026-0502-U を取消線化
   - 次タスク (T2026-0502-Y MCP rate-limit など) の dispatch 提案
```

---

## Phase 1 着手 (まず必ずここから)

詳細は `docs/session-prompts/T2026-0502-U-phase1-2.md` を読んでください。要点だけ:

```bash
# 1. Lambda layer ビルド (model 118MB + onnxruntime + tokenizer)
bash scripts/build_embedding_layer.sh
# → /tmp/embedding_layer.zip 生成

# 2. bench 実行
WORK_DIR=/tmp/build_embedding_layer python3 scripts/embedding_bench.py
# → 6 fixture の cosine 値・misses カウント表示
```

期待出力例:
```
fixture                                   sim    expected  decision  match
same_event_geo_subset                     0.87+  True      True      ✓
same_event_paraphrase                     0.85+  True      True      ✓
different_subject_same_topic              0.55-  False     False     ✓
...
misses (high-confidence mistake): 0 / 6
```

### Phase 1 完了条件

- [ ] `tmp_logs/embedding_bench_result.json` が生成され misses=0
- [ ] `docs/p003-embedding-migration-research.md` §9 に bench 結果追記
- [ ] commit に `Verified-Effect: bench misses=0/6 (cosine_high=X cosine_low=Y :YYYY-MM-DD)` を含める

**misses ≥ 1 の場合**: 閾値を bench 出力の "推奨単一閾値" に基づいて再調整して再実行。
それでも改善しないなら voyage-3-lite API 切替検討 (`embedding_judge.py` に `VoyageEmbeddingBackend` を追加実装)。
最終的に embedding 不採用判断する場合は TASKS.md に「embedding 移行不採用 (理由)」を記録して T2026-0502-U を **取り消し線で完了**して停止。

---

## Phase 2 着手判断 (Phase 1 OK 後)

詳細は `docs/session-prompts/T2026-0502-U-phase1-2.md` Step 3-7。要点:

1. `lambda/fetcher/handler.py:790-791` の `_ai_judge` 初期化を embedding 優先・Haiku fallback 構造に変更
2. `[FETCHER_HEALTH]` ログに `judge_type` フィールド追加（観察用）
3. unit test (`tests/test_embedding_judge.py` 8/8) + 既存テスト (`tests/test_title_dedup_guard.py`) を全 PASS 確認
4. PR 作成 → auto-merge → deploy → Lambda layer publish + attach + env 切替 (`EMBEDDING_MERGE_ENABLED=true`)
5. **schedule task 登録して即セッション exit**:

```python
# scheduled task one-time fire
task_id = "p003-T2026-0502-U-phase2-verify"
fire_at = "30 minutes from now"
prompt = """
fetcher_health 直近 30 分のログを確認して以下を HISTORY.md に追記:
- judge_type が 'OnnxEmbeddingBackend' に変わってるか
- haiku_pairs_asked=0 維持か
- embedding_pairs_yes/no カウンタが正常値か (yes_rate 5-15% 想定)
- T2026-0501-M フィクスチャ (欧州 vs ドイツ駐留米軍) が同一トピックに統合されてるか
  api/admin/merge-audit/YYYY-MM-DD.jsonl で確認

結果を effect=positive/neutral/negative で記録。
positive → Phase 3 着手プロンプト dispatch 提案を WORKING.md に書く。
negative → EMBEDDING_MERGE_ENABLED=false で revert + 原因特定タスクを TASKS.md に積む。
"""
```

---

## Phase 3 着手判断 (Phase 2 OK 後)

詳細は `docs/session-prompts/T2026-0502-U-phase3.md`。要点:

- `lambda/processor/embedding_skip.py` 新設 (既存 keyPoint embedding と新 articles の cosine sim > 0.95 で AI 再生成 skip)
- `lambda/processor/handler.py` 改修 (skip 判定組込)
- `lambda/processor/proc_storage.py` 改修 (`latestKeyPointEmbedding` フィールド追加・Decimal 変換)
- Lambda layer attach + env (`EMBEDDING_SKIP_ENABLED=true`)
- **24h 後 schedule task で `skip_rate >= 30%` かつ `keyPoint 充填率維持` 確認**

期待効果: Haiku call ~140/日 → ~70-100/日 (月 $12 → $6-8)

---

## Phase 4 着手判断 (Phase 3 OK 後・おまけ)

詳細は `docs/session-prompts/T2026-0502-U-phase4.md`。

優先度低・コスト削減効果は誤差。Phase 5 (個別ユーザ向け recommendation など) を将来やる予定がある場合のみ着手。
PO に「Phase 4 やりますか？」を WORKING.md に置いて聞く形で OK。

---

## 終了条件 (orchestrator 全体)

- [ ] Phase 1 bench misses=0 を doc に landing
- [ ] Phase 2 fetcher 統合 deploy + 30 分後 effect=positive 確認
- [ ] Phase 3 processor skip deploy + 24h 後 effect=positive 確認 (skip_rate >= 30% + 充填率維持)
- [ ] Phase 4 は PO 判断 (skip OK)
- [ ] HISTORY.md に T2026-0502-U Phase 1-3 (or 1-4) 完了記録
- [ ] TASKS.md T2026-0502-U を取消線
- [ ] WORKING.md から自分の行を削除して push

---

## 失敗パターン回避 (今日 Cowork が踏んだもの一覧・回避)

| パターン | 回避策 |
|---|---|
| ❌ 「PR 出した時点で完了」誤認 | T2026-0502-AA hook が commit-msg level で reject。Verified-Effect 必須 |
| ❌ AWS API 連投 (lambda invoke / cloudwatch get-metric を 5+ 回) | 効果検証は schedule task に委譲・Code は immediate exit。CLAUDE.md「コスト規律ルール」 |
| ❌ deploy 失敗を放置 | `gh run view <run_id> --log-failed` で実エラー取得・ci_lambda_merge_env.py をローカル再現 |
| ❌ 閾値 (0.85/0.65) を実測なしで決め打ち | Phase 1 bench 結果の "推奨単一閾値" を見て根拠付ける |
| ❌ 効果検証中にセッション開いたまま polling | schedule task 委譲 + immediate exit |

---

## 緊急時の PO 確認事項 (これらは必ず聞く)

- AWS Layer publish (新規リソース作成・ストレージ課金発生・$0.05/GB/月) → 大した額ではないが念のため
- `voyage-3-lite` API 切替判断 (Phase 1 bench で multilingual-e5-small が miss する場合)
- Phase 4 (S3 cache) を実装するか skip するか
- Phase 5 以降の embedding 拡張予定があるか

---

## 参照リンク

- 既存 prompt: `docs/session-prompts/T2026-0502-U-phase1-2.md` / `phase3.md` / `phase4.md`
- 設計 doc: `docs/p003-embedding-migration-research.md`
- 関連 PR: #223 (scaffold) / #225 (phase 1+2 prompt) / #229 (phase 3+4 prompt) / #226 (Verified-Effect hook) / #227 (keyPoint examples)
- 関連 schedule: `p003-cost-quality-verify-T2026-0502-COST` (5/3 14:00 JST 発火・別系統)

---

> **今日 Cowork が果たせなかったのは Phase 1 PoC bench の実 cosine 実測のみです (sandbox の SOCKS proxy で HuggingFace download 不可)。それ以外の scaffold + prompts + hook + ジャンル例追加は landing 済。Code は Phase 1 から始めれば 1-3 セッションで Phase 4 まで到達できます。**
