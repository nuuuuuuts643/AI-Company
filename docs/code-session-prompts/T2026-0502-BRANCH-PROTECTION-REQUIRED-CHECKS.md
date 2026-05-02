# PO 操作 prompt: T2026-0502-BRANCH-PROTECTION-REQUIRED-CHECKS

> 用途: GitHub branch protection に required status checks を設定し、auto-merge が CI failure を ignore できないようにする
> 関連: PR #312 / PR #317 が CI failure と共に auto-merge された事案・auto-merge.yml は GitHub native auto-merge を使うため、required checks 未設定だと CI failure があっても即 merge される
> 推奨実行者: **PO 直接** (Code セッション/Cowork から GitHub Settings は触れない)
> リスク: **🟡 中** (一度設定すれば全 PR が必須 CI を待つ・誤った check 名指定で全 PR が永遠に未 merge になる可能性)
> 想定所要: **15〜30 分** (GitHub UI 操作 + 数 PR で動作観察)
> 実施推奨: **明日 PO 立ち会いで自身が操作・Code セッション不要**
> 改訂: 2026-05-02 23:55 JST (V1 — 新規)

---

## 背景

T2026-0502-AUTO-MERGE-GUARDS で「`[DO NOT MERGE]` PR の auto-merge skip」を物理化するが、これだけでは **通常 PR の CI failure を ignore する問題** は解決しない (PR #317 自身も CI failure と共に auto-merge された)。

GitHub の native auto-merge は branch protection で **Require status checks to pass before merging** が設定されていれば、required checks が green になるまで merge を待つ。
現状この設定が無い (or 不十分) ため、`gh pr merge --auto` が enable された瞬間 = 即 merge になっている。

本タスクで required checks を branch protection に設定し、CI failure 時の merge を物理 reject する。

## PO 操作手順

### Step 1: 現状確認

GitHub にログイン → AI-Company リポジトリ → Settings → Branches

- "Branch protection rules" の `main` rule が存在するか確認
- 存在する場合: 現在の "Require status checks to pass before merging" 設定を控える (rollback 用)
- 存在しない場合: 新規作成

### Step 2: 必須 CI check 名の特定

以下の workflow を required にすべき (今日の事故で気付いた重要なもの):

1. **No inline logic in YAML** (workflow file: lint-yaml-logic.yml / job name: `check`)
   - PR #314 で導入した workflow YAML 物理ガード
   - check_workflow_script_refs.sh + check_yaml_no_inline_logic.sh
   - これが green でないと missing ref が main 流入する

2. **CI（構文チェック・品質確認）** (workflow file: ci.yml / job names: 各種)
   - frontend / lambda / agent script syntax check
   - 横展開 landing 検証
   - 思想ドリフト検出
   - SLI フィールドカバレッジ
   - workflow path lint
   - 主要ページ noindex 物理ガード
   等多数

3. **メタドキュメント物理ガード** (workflow file: meta-doc-guard.yml)
   - CLAUDE.md 250 行ガード
   - 横展開チェックリスト fossilize 検出
   - rollback runbook 物理検査

最低限 1〜2 番は required に含める。3 番は現状 main で failure 持続中 (T2026-0502-CI-FAILURES-INVESTIGATE で診断中) なので**修復後に追加**する方が安全。

### Step 3: branch protection 設定

GitHub Settings → Branches → main → Edit rule:

- ☑ **Require a pull request before merging**
- ☑ **Require status checks to pass before merging**
  - ☑ **Require branches to be up to date before merging** (推奨)
  - "Status checks that are required" にチェック名を入力:
    - `check` (lint-yaml-logic.yml の job)
    - `CI（構文チェック・品質確認）` の各 job (frontend syntax / lambda syntax / etc)
  - **注意**: GitHub の "Status checks that are required" 入力欄は workflow run **job 名** を入力する。run 全体ではなく個別 job レベル。
  - **検索でヒットしない場合**: 過去に main で 1 度 success した job だけが候補に出る。先に該当 workflow を main で 1 度走らせてから設定 (push or workflow_dispatch)。

### Step 4: 動作確認

設定後、テスト用 PR を作って観察:

1. 通常 PR (CI green): 従来通り auto-merge → 問題なし期待
2. CI failure を含む PR (例: わざと frontend 構文エラーを入れた PR): auto-merge enable はされるが GitHub が merge しない (waiting for required checks)
3. 検証完了したら test PR を close

### Step 5: 影響観察 (1〜3 日)

設定後 1〜3 日間:
- 通常 PR が滞留してないか観察
- 必須 check が誤って指定されていて全 PR が止まる事故が無いか確認

### Rollback 手順 (異常時)

GitHub UI で:
- Settings → Branches → main → Edit rule
- "Require status checks to pass before merging" のチェックを外す
- または "Status checks that are required" から問題のある check を削除
- 即時反映

PR は API か Code セッションでなく PO 直接 GitHub UI 操作。

## 完了条件

- [ ] branch protection rule `main` に "Require status checks to pass before merging" が ON
- [ ] 必須 check に最低 `lint-yaml-logic.yml` の job が含まれる
- [ ] テスト PR で CI failure 含む PR が auto-merge されないことを観察済
- [ ] docs/lessons-learned.md「『DO NOT MERGE』test PR が auto-merge で main に流入」横展開チェックリストの「T2026-0502-BRANCH-PROTECTION-REQUIRED-CHECKS」を [x] に更新

## 注意

- **Code セッション / Cowork から GitHub Settings は触れない** — PO 直接操作必須
- 設定変更直後はテスト PR で動作観察してから実 PR を投下
- **必須 check の指定ミスで全 PR が永遠に止まる**事故に注意 (rollback は Step 5 の手順で 1 分で戻せる)
- 既存の AUTO_MERGE_PAT / GITHUB_TOKEN 設定は触らない

## 関連タスク

- T2026-0502-AUTO-MERGE-GUARDS (auto-merge.yml の `[DO NOT MERGE]` skip): 本タスクと **独立で並行実施可能**
- T2026-0502-CI-FAILURES-INVESTIGATE (main 持続 CI failure 診断): meta-doc-guard.yml 系を required に含める前に修復が必要
