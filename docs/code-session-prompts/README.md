# Code セッション起動 prompt 集

> Cowork デスクトップから「コードセッションを起動」する際にコピペで使う prompt をここに置く。
> 1 ファイル = 1 タスク。原則 1 PR で完結する粒度。

---

## 一覧 (2026-05-02 時点)

| ファイル | タスク | 推奨モデル | 所要 | 状態 |
|---|---|---|---|---|
| [T2026-0502-COST-A1-CODE.md](T2026-0502-COST-A1-CODE.md) | 未使用 DynamoDB 4 個整理 (deploy.sh + 実 delete) | Sonnet | 30 分 | 起動待ち |
| [T2026-0502-COST-D1-INVESTIGATE.md](T2026-0502-COST-D1-INVESTIGATE.md) | DynamoDB Read $4.02/月 の元コード特定 (調査のみ) | Sonnet | 1〜2 時間 | 起動待ち |
| [T2026-0502-BC-CRON-FIX.md](T2026-0502-BC-CRON-FIX.md) | judge_prediction 専用 22:00 JST cron 追加 + コメント乖離修正 | Sonnet | 30〜60 分 | 起動待ち |
| [T2026-0502-WORKFLOW-DEP-CLEANUP-FULL.md](T2026-0502-WORKFLOW-DEP-CLEANUP-FULL.md) | zz_test_missing_ref.yml を git rm で完全除去 (V2 改訂) | Haiku | 10〜15 分 | **明日 PO 立ち会いで実施** 🟢低リスク |
| [T2026-0502-AUTO-MERGE-GUARDS.md](T2026-0502-AUTO-MERGE-GUARDS.md) | auto-merge.yml に `[DO NOT MERGE]` skip 追加 (PR-A) + 1 週後 `test/` skip (PR-B) (V2 段階導入) | Sonnet | 1.5 時間 | **明日 PO 立ち会い必須** 🟡中リスク |
| [T2026-0502-CI-FAILURES-INVESTIGATE.md](T2026-0502-CI-FAILURES-INVESTIGATE.md) | main 持続 2 CI failure (PR #316 由来) **diagnosis-only** PR (V2 fix と分離) | Sonnet | 1 時間 | **明日 PO 立ち会い** 🟡診断のみ・コード変更禁止 |
| [T2026-0502-BRANCH-PROTECTION-REQUIRED-CHECKS.md](T2026-0502-BRANCH-PROTECTION-REQUIRED-CHECKS.md) | branch protection に required CI checks 追加 (CI failure ignore の根本対処) | **PO 直接** | 15〜30 分 | **明日 PO が GitHub UI で直接実施** 🟡 |

---

## 使い方

1. Cowork デスクトップで「コードセッション起動」を選択
2. このフォルダから対象 `.md` を開く
3. 「prompt 本文」セクションの ``` ブロック内をコピー
4. Code セッションに貼り付けて起動
5. 推奨モデル欄の通りに `model` パラメータを設定

## 追加ルール

- 新規 prompt を作成するときは本 README の一覧表にも追記する
- 1 prompt = 1 PR が原則。複数 PR が必要なものは分割する
- 削減プラン本体は `docs/cost-reduction-plan-2026-05-02.md` を参照

## 明日 (2026-05-03) PO 立ち会い実施推奨順

1. **CLEANUP-FULL** (Haiku 10〜15 分) — 低リスク・先頭実施で OK
2. **CI-FAILURES-INVESTIGATE** (Sonnet 1 時間・diagnosis-only) — コード変更なし・観察安全
3. **BRANCH-PROTECTION-REQUIRED-CHECKS** (PO 直接 15〜30 分) — GitHub UI 操作・上記 2 件と独立並行可
4. **AUTO-MERGE-GUARDS PR-A** (Sonnet 1 時間・段階 1/2) — `[DO NOT MERGE]` skip だけ・rollback 手順付き
5. (1 週間後) **AUTO-MERGE-GUARDS PR-B** — `test/` branch skip 追加・本日は実施しない

### 明日実施しない

- **CI-FAILURES-FIX** — INVESTIGATE の真因確定後・別 Code セッション
- **AUTO-MERGE-GUARDS PR-B** — PR-A 1 週間観察後

### V2 改訂 (2026-05-02 23:55 JST) の主な改善点

- 全 prompt に **rollback 手順** 明記
- AUTO-MERGE-GUARDS は **段階導入 (PR-A → 1 週後 PR-B)** + **chicken-and-egg 対処**
- CI-FAILURES-INVESTIGATE は **diagnosis-only と fix を 2 PR に分割** (check_lessons_landings.sh 誤改修で全 PR ブロックリスク回避)
- CLEANUP-FULL は **削除後ローカル検証 step 追加** + **done.sh 引数明確化**
- 新規 BRANCH-PROTECTION-REQUIRED-CHECKS (PO 直接操作・auto-merge.yml 修正と独立で並行可)
