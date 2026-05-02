# Code セッション起動 prompt: T2026-0502-WORKFLOW-DEP-CLEANUP-FULL

> 用途: Cowork が cowork_commit.py で commit できなかった「ファイル完全削除 (git rm)」を実施
> 関連: PR #312 auto-merge 事故・docs/lessons-learned.md「『DO NOT MERGE』test PR が auto-merge で main に流入」
> 推奨モデル: **Haiku** (単純な削除作業・10〜15 分)
> リスク: **🟢 低** (placeholder ファイル削除のみ)
> 実施推奨: **明日 PO 立ち会い前提・先頭で実施 OK**
> 改訂: 2026-05-02 23:55 JST (V2 — Step 統合 + 検証追加 + done.sh 引数明確化)

---

## prompt 本文

```
docs/lessons-learned.md「『DO NOT MERGE』test PR が auto-merge で main に流入」セクションを読んでください。

## 目的

main に残存する placeholder ファイル `.github/workflows/zz_test_missing_ref.yml` を完全に git rm で削除する。

## 背景

2026-05-02 23:00 JST、Cowork セッションが T2026-0502-WORKFLOW-DEP-PHYSICAL の検出力 CI 検証用に PR #312 を作成。
タイトルに `[DO NOT MERGE]` を明記したが auto-merge.yml が CI failure を待たずに merge → main 汚染。
Cowork は cowork_commit.py で noop placeholder に書き換える応急処置 (PR #317) しかできなかった。
本タスクで完全に git rm して片付ける。

## 事前確認 (起動直後に必ず実行)

1. ファイル存在確認
   test -f .github/workflows/zz_test_missing_ref.yml && echo "EXISTS" || echo "ALREADY GONE"
   → "EXISTS" であれば手順続行。"ALREADY GONE" なら本タスクは既に他で完了済 → done.sh で close

2. 削除対象が placeholder であることを 1 度確認 (typing 防止)
   head -10 .github/workflows/zz_test_missing_ref.yml
   → "T2026-0502-WORKFLOW-DEP-CLEANUP" コメントが先頭にあれば本物 placeholder

3. 他 workflow が誤って触らないこと
   grep -l "zz_test_missing_ref" .github/workflows/ scripts/ 2>/dev/null
   → 結果が `.github/workflows/zz_test_missing_ref.yml` 1 件のみであれば孤立ファイル = 安全に削除

## 手順

1. main 同期 + 新 branch
   git checkout main && git pull --rebase origin main
   git checkout -b fix/T2026-0502-WORKFLOW-DEP-CLEANUP-FULL

2. WORKING.md に [Code] 行追加 + git rm を 1 commit に統合
   - WORKING.md の「現在着手中」テーブルに以下を追記:
     | [Code] T2026-0502-WORKFLOW-DEP-CLEANUP-FULL git rm zz_test_missing_ref.yml | Code | .github/workflows/zz_test_missing_ref.yml | <開始JST> | yes |
   - git rm .github/workflows/zz_test_missing_ref.yml

3. 削除後ローカル検証 (ガード自身に effect 確認)
   bash scripts/ci_check_workflow_script_refs.sh
   → "✅ Workflow YAML が参照する scripts/* / infra/* は全て repo に存在 (51 workflows checked)" であれば OK
   bash scripts/ci_check_yaml_no_inline_logic.sh
   → "✅ YAMLインラインロジックなし"
   bash scripts/check_lessons_landings.sh
   → 全 ✅ (本タスクで CI-FAILURES-INVESTIGATE が未着手の場合は元々 failure している可能性あり・許容)

4. 1 commit 化 + push
   git add WORKING.md
   # zz_test_missing_ref.yml は git rm で既に staged
   git commit -m "fix: T2026-0502-WORKFLOW-DEP-CLEANUP-FULL git rm zz_test_missing_ref.yml

PR #312 (DO NOT MERGE test PR) auto-merge 事故の placeholder を完全削除。
PR #317 で noop に書き換えた残骸を最終 cleanup。

ローカル検証 (削除後):
- bash scripts/ci_check_workflow_script_refs.sh → ✅ (51 workflows)
- bash scripts/ci_check_yaml_no_inline_logic.sh → ✅

Verified-Effect-Pending: merge 後 .github/workflows/ から本ファイルが消える + lint-yaml-logic.yml が success 維持
Eval-Due: 2026-05-03"
   git push -u origin HEAD

5. PR 作成 (タイトル + 本文)
   gh pr create --title "fix: T2026-0502-WORKFLOW-DEP-CLEANUP-FULL git rm zz_test_missing_ref.yml" \
                 --body "PR #312 auto-merge 事故残骸 (zz_test_missing_ref.yml noop placeholder) を git rm で完全除去。
                  詳細: docs/lessons-learned.md「『DO NOT MERGE』test PR が auto-merge で main に流入」"

6. CI green 確認 + auto-merge による squash merge
   - CI 待ちは即 close (Monitor 禁止・CLAUDE.md ルール)
   - auto-merge.yml が CI 全 green 時に native auto-merge で squash merge

7. main HEAD で削除確認 (PR merge 後の最終チェック)
   git fetch origin main && git log --oneline origin/main -1
   curl -sS https://api.github.com/repos/nuuuuuuts643/AI-Company/contents/.github/workflows/zz_test_missing_ref.yml?ref=main
   → "Not Found" 404 が返れば成功

8. WORKING.md から自分の行削除 + done.sh
   # WORKING.md cleanup
   git checkout main && git pull --rebase origin main
   # WORKING.md 編集して [Code] T2026-0502-WORKFLOW-DEP-CLEANUP-FULL 行を削除
   git add WORKING.md
   git commit -m "chore: WORKING.md cleanup after T2026-0502-WORKFLOW-DEP-CLEANUP-FULL done"
   git push origin HEAD:main || (git checkout -b chore/working-cleanup && git push -u origin HEAD && gh pr create --fill)
   
   # done.sh (verify_target は単一 URL 指定不要なので main HEAD sha を渡す)
   bash done.sh T2026-0502-WORKFLOW-DEP-CLEANUP-FULL https://github.com/nuuuuuuts643/AI-Company/commits/main

## Rollback 手順 (異常時)

何か問題があった場合:
git revert <merge_commit_sha>
→ noop placeholder が復元される (PR #317 の状態に戻る)

zz_test_missing_ref.yml は元々 placeholder であり、`on: workflow_dispatch` のため誰も触らなければ何も起きない。
最悪のケースでも他 workflow に影響なし。

## 完了条件

- [ ] main HEAD に .github/workflows/zz_test_missing_ref.yml が存在しない (404)
- [ ] lint-yaml-logic.yml の最新 main run が success (新 step 含む)
- [ ] PR が squash merge 済
- [ ] WORKING.md から該当 [Code] 行が削除されている
- [ ] done.sh 実行で commit に Verified-Effect 行が含まれる

## 注意

- iam-policy-drift-check.yml / lint-yaml-logic.yml / その他本物 workflow は触らない
- 削除対象は zz_test_missing_ref.yml だけ
- chmod / file mode は変更しない
- 本タスクは独立で他タスクの merge を待たずに即実施可能
```
