# Code セッション起動 prompt: T2026-0502-WORKFLOW-DEP-CLEANUP-FULL

> 用途: Cowork が cowork_commit.py で commit できなかった「ファイル完全削除 (git rm)」を実施
> 関連: PR #312 auto-merge 事故・docs/lessons-learned.md「『DO NOT MERGE』test PR が auto-merge で main に流入」
> 推奨モデル: **Haiku** (単純な削除作業・10 分で済む)

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

## 手順

1. main 同期 + 新 branch
   git checkout main && git pull --rebase origin main
   git checkout -b fix/T2026-0502-WORKFLOW-DEP-CLEANUP-FULL

2. ファイル削除
   git rm .github/workflows/zz_test_missing_ref.yml

3. WORKING.md に [Code] 行を追記して push (前 push)
   | [Code] T2026-0502-WORKFLOW-DEP-CLEANUP-FULL git rm zz_test_missing_ref.yml | Code | .github/workflows/zz_test_missing_ref.yml | <開始JST> | yes |
   git add WORKING.md && git commit -m "wip: T2026-0502-CLEANUP-FULL start" && git push

4. 削除 commit
   git add -A && git commit -m "fix: T2026-0502-WORKFLOW-DEP-CLEANUP-FULL git rm zz_test_missing_ref.yml

PR #312 (DO NOT MERGE test PR) auto-merge 事故の placeholder を完全削除。
PR #317 で noop に書き換えた残骸を最終 cleanup。

Verified-Effect-Pending: merge 後 .github/workflows/ から本ファイルが消える + lint-yaml-logic.yml が success 維持
Eval-Due: 2026-05-03"

5. push & PR
   git push -u origin HEAD
   gh pr create --fill

6. PR auto-merge (本 PR は本来の単純削除なので CI green で merge OK)

7. main HEAD で .github/workflows/zz_test_missing_ref.yml が存在しないことを GitHub UI で確認
   → 完了

8. WORKING.md から自分の行削除 + done.sh

## 完了条件

- main HEAD に .github/workflows/zz_test_missing_ref.yml が存在しない
- lint-yaml-logic.yml の最新 main run が success
- PR が squash merge 済

## 注意

- bluesky-posts や iam-policy-drift-check.yml 等の本物の workflow は触らない
- zz_test_missing_ref.yml だけ削除する
```
