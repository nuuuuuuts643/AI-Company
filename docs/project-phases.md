# Flotopic プロジェクト・フェーズ階層（2026-04-28 制定）

> **目的**: タスク単位の管理（TASKS.md）に加えて、案件・機能要件（Epic）の階層を持たせる。
> **方針**: フェーズ1=運用優先・足回り安定。フェーズ2=AI品質。フェーズ3=UX/成長。
> **現在地**: フェーズ1 進行中（health.json 稼働済 / cache_control 完了 / 1PR1task 規律確立中）。

## 階層モデル

```
社長/役員（ビジョン: docs/flotopic-vision-roadmap.md）
  └─ 部署（プロダクト領域: P003 Flotopic）
       └─ 案件（フェーズ: 本ファイル）
            └─ 機能要件（Epic）
                 └─ 実装タスク（Task: TASKS.md）
```

## フェーズ1: 足回り安定（運用優先・現在進行中）

**完了条件（2026-04-28 PM 再定義 — T2026-0428-AX）**:

### A. 観測・自己修復基盤（既存）
- ✅ health.json が CloudWatch / 外部監視で死活確認可能（T2026-0428-AQ）
- ✅ prompt caching が proc_ai に組込まれ動作している（T2026-0428-AJ）
- ✅ session_bootstrap.sh で運用前提 5 ファイル（CLAUDE.md / global-baseline.md / system-status.md / product-direction.md / project-phases.md）が毎回確認できる
- ✅ freshness-check SLI 1〜11（updatedAt / sitemap_reach 等）外部観測

### B. リリース管理・ロールバック（新規・進行中）
- ✅ **develop / main ブランチ分離** — main は常に動く / 開発は develop でマージ → main へは「ロールバック可能な単位の commit」のみ。実装: GitHub branch protection rules で main へ直接 push 禁止 + PR 経由のみ。**2026-04-28 PM PO設定完了**（`gh api repos/nuuuuuuts643/AI-Company/branches/main/protection` で `required_pull_request_reviews.required_approving_review_count=1` 確認済）
- ✅ **git tag v1.x.x によるリリース管理** — `vYYYY.MMDD.N` 形式で push 時点の releases を tag。実装: `.github/workflows/release-tag.yml` + `scripts/tag_release.sh` で自動 tag（deploy 成功時 or 手動実行）。T2026-0428-AZ で実装済
- ✅ **ロールバック手順の文書化** — `docs/runbooks/rollback.md` (T2026-0428-AX で新設済)。「main が壊れたら何をすれば戻るか」を Lambda（`aws lambda update-function-code` で前 tag に戻す）/ Frontend（`aws s3 sync` で前 tag に戻す）/ DB（quality_heal で再処理）の 3 経路で言語化済
- ✅ **CI 全パス必須化** — main マージ前に CI 全 job 通過が必須（branch protection の required status checks）。**2026-04-28 PM PO設定完了**（required_status_checks に `lint-frontend` / `lint-lambda` / `lint-scripts` / `CLAUDE.md 250 行ガード` / `check` の 5 件登録 + `strict=true`）

### C. Dispatch 運用安定（新規・進行中 — 2026-04-28 PM 追加）
- ✅ **Dispatch から起動できるコードセッション = 同時 1 件まで**（Dispatch 自身を含めて 2 件以内）。新規タスクは前のコードセッション完了までキューに積む。WORKING.md の `[Code]` 行が 2 件以上ある瞬間は session_bootstrap.sh が物理 ERROR + exit 1 を出す。T2026-0428-BB で実装済（`scripts/session_bootstrap.sh:204-214`）
- ✅ **コードセッション並走 0 件の常態化** — `[Code]` 行 2 件以上の状態が 1 時間継続したら Slack 警告（健康指標として観測）。実装: `scripts/check_concurrent_sessions.sh` + `.github/workflows/concurrent-session-guard.yml` で 15 分ごと検出 × Slack 通知。T2026-0428-BB で実装済
- ❌ **PO判断介入ゼロ** — Dispatch が 1 回受け取った指示について「止める？再開する？」を聞かずに完了まで走る。中断は「実装の前提が根本的に変わった場合」のみ（CLAUDE.md「中断ルール」を参照）。※ 思想ルール（テキスト規則のみ）
- ✅ **コードセッション名規則の徹底** — セッション名は「何を commit するか」が一目で分かる名前（✅「CI 構文チェック fix」 ❌「調査」「作業」）。session_bootstrap.sh の出力で空抽象タイトル（"作業/調査/タスク/着手"単体等）を自動 WARN。T2026-0428-BF で実装済

### D. 規律・運用浸透（新規・進行中）
- ✅ 1PR1task の規律が確立し、WORKING.md の並行タスクが恒常的に ≤2 件 → `session_bootstrap.sh` で `[Code]` 並走 ≥2 を ERROR + exit 1 化することで物理担保（T2026-0428-BB 済）
- ✅ **横展開チェックリスト（lessons-learned）の自動検証** — `scripts/check_lessons_landings.sh` (新設) で「過去仕組み的対策の実装ファイルが repo に存在するか」を CI 物理検査。T2026-0428-BC で実装済（`.github/workflows/ci.yml:374-379`）
- ✅ **形骸化ルール棚卸しの定期化** — CLAUDE.md / global-baseline.md / lessons-learned.md の「仕組み的対策」セクションに「気を付ける/注意する/意識する/確認する」が混入していないか月次 CI で grep（テキストルール混入の検出）。T2026-0428-BD で実装済（`scripts/check_soft_language.sh` + `.github/workflows/ci.yml`）

**担当 Epic 一覧**:
- E1-1: 起動チェック整備（session_bootstrap.sh の責務拡張）— ✅ 観測項目は landing
- E1-2: タスク管理階層化（本ドキュメント整備・TASKS.md 整理）— ✅
- E1-3: 観測可能性（health.json / freshness-check / SLI 整備）— ✅ SLI 1〜11
- E1-4: 並行タスク事故防止（WORKING.md TTL / needs-push ゲート / Code 並走 ERROR 化）— ✅ T2026-0428-BB 済
- **E1-5（新設）**: リリース管理・ロールバック（develop/main 分離・tag・runbook）— ✅ 完了（branch protection 設定済 2026-04-28 PM）
- **E1-6（新設）**: Dispatch 運用安定（同時 1 件・並走 0 件・名前規則）— ✅ T2026-0428-BB/BF 済（判断介入ゼロのみ思想）
- **E1-7（新設）**: 形骸化検出（横展開チェックリスト CI / soft-language grep）— ✅ T2026-0428-BC/BD 済

**現在地**: **フェーズ1 完了** (2026-04-28 PM)。A/B/C/D 全項目 ✅。フェーズ2 着手可能。

## フェーズ2: AI品質改善

**完了条件 (2026-04-28 PM 実測値で更新)**:
- ❌ topics.json の keyPoint 充填率 70% 超（**実測 10.02%** — 1068 META トピック中 107 件のみ）
- ✅ AI 生成物の 4 構造（状況解説 / 各社見解 / 注目ポイント / 予想判定）が proc_ai.py に実装済 — **コードは landing**（`proc_ai.py:361` keyPoint, `:362` outlook, `:386` perspectives, `:678` judge_prediction）
- ⚠️ 個別 topic JSON で「背景カード」相当のフィールドが設計・実装済 — proc_ai.py のスキーマには存在 (keyPoint=状況解説 200〜300字)。ただし frontend detail.js 側の表示確認が未実施
- ❌ storyPhase 分布の正規化（「発端」が articleCount≥3 で 10% 未満） — **実測 18.75%**（storyPhase 付与済の 発端 176 件のうち articleCount≥3 が 33 件）

**実測スナップショット (2026-04-28 22:15 JST 取得)**:

| 項目 | 実測値 | 目標 | 達成 |
|---|---|---|---|
| keyPoint 充填率 | 10.02% (107/1068) | 70% 超 | ❌ |
| perspectives 充填率 | 4.31% (46/1068) | (未設定) | — |
| outlook 充填率 | 10.39% (111/1068) | (未設定) | — |
| 確信度ラベル付与率 (outlook 内) | 46% (51/111) | 100% (プロンプトで必須) | ❌ |
| storyPhase 発端 articleCount≥3 | 18.75% (33/176) | 10% 未満 | ❌ |
| storyPhase 付与トピック | 36.0% (385/1068) | (未設定) | — |
| PRED# レコード総数 | 823 件 | — | — |
| predictionResult=pending | 45 件 | — | — |
| predictionResult=matched/partial/missed | **0 件** | (運用効果) | ⚠️ judge_prediction 未稼働 |
| keyPoint 平均長 | 43.8 字 | 200〜300 字 | ❌ 短すぎ |
| keyPoint 最大長 | 293 字 | 〜300 字 | ✅ 一部は仕様通り |

**担当 Epic 一覧**:
- E2-1: AI プロンプト 4 構造化（whyNow 廃止 / 状況解説プロンプト整備）— ✅ コード landing (proc_ai.py)
- E2-2: keyPoint / perspectives 充填率改善（Tier-0 優先処理 / skip 条件見直し / 古いトピック再処理）— ❌ 充填率 10% で目標 70% から大きく未達
- E2-3: クラスタリング品質（同一事象の分裂解消 T212）— 進行中
- E2-4: 予想判定ロジック運用化（judge_prediction の精度・運用化）— ⚠️ コード実装済だが verdict 0 件 = 7日経過+5記事閾値を満たすトピックがまだ無い、または条件緩和要

**実測から見える次の改善ポイント (根拠ベース)**:
1. **keyPoint 充填率改善 (E2-2)** — 1068 件中 961 件 (90%) が空。proc_ai.py の skip 条件、または 古いトピックへの遡及適用が必要。Tier-0 優先処理は `quality_heal` 系で実装済か要確認。
2. **keyPoint 平均長 43.8 字** — プロンプトは 200〜300 字を要求するが、平均が短すぎる。生成失敗時のフォールバックで切り詰められている可能性。
3. **確信度ラベル付与率 46%** — プロンプトで必須化されているが、実際は半数以上で欠落。schema validation を追加するか、プロンプトを再強化する必要。
4. **storyPhase 発端 18.75%** — クラスタリングや phase 判定で「発端」過多。E2-3 の T212 と関連。
5. **judge_prediction 運用化 (E2-4)** — verdict が 0 件。7日経過+5記事閾値が厳しすぎるか、predictionMadeAt の取り回しに不具合の可能性。

**現在地**: フェーズ1 完了。フェーズ2 着手可能。実測ベースで E2-2 (充填率改善) が最大ギャップ。

## フェーズ3: UX 改善・成長

**完了条件**:
- 「毎日来る理由」が 1 つ以上実装され KPI で動いている（朝メール / Bluesky 朝投稿 / 動きトピック固定）
- ストーリー追体験フロー（トップ → 1タップ進入 → 「続きが来たら通知」離脱）が UX 上で完結
- 習慣化指標（DAU/WAU、再訪率）が観測可能で、ベースライン → 改善が測れる

**担当 Epic 一覧（暫定）**:
- E3-1: 習慣化仕掛け（朝メール / SNS / 動きトピック固定 — TASKS T193）
- E3-2: ストーリー体験設計（フロー図 → 実装 — TASKS T191）
- E3-3: ジャンル戦略（全ジャンル → 1-2 ジャンル集中検討 — TASKS T192）
- E3-4: 通知系（Web Push for お気に入り — TASKS T154）

**現在地**: フェーズ2 進捗を見て着手判断。アーカイブ内の T191 / T193 / T192 が骨格。

---

## 運用ルール

- 新規タスクは追加時に `フェーズ`（1/2/3）と `Epic`（任意）でタグ付けする
- TASKS.md の各セクションに `<!-- フェーズN -->` HTML コメントで紐付け（パースしやすい形）
- 週次レビュー（手動）で Epic の進捗・フェーズ昇格判定を行う
- フェーズの完了条件が満たされたら HISTORY.md に「フェーズN完了」記録を残し、次フェーズへ宣言

## 次の更新タイミング

- フェーズ1 完了条件のいずれかが達成 → 達成欄を ✅ 化
- 新規 Epic 起票時 → 該当フェーズに追記
- フェーズ昇格時 → 「現在地」更新
