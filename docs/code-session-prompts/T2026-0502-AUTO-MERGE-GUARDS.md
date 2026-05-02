# Code セッション起動 prompt: T2026-0502-AUTO-MERGE-GUARDS

> 用途: auto-merge.yml に「title `[DO NOT MERGE]` skip + branch `test/` skip」を物理ガードとして追加
> 関連: PR #312 / PR #317 自身も auto-merge された事案・docs/lessons-learned.md「『DO NOT MERGE』test PR が auto-merge で main に流入」
> 推奨モデル: **Sonnet** (workflow YAML 編集 + 動作確認・段階導入)
> リスク: **🟡 中** (CI/CD 機構を触る・rollback 可能だが要 PO 立ち会い)
> 想定所要: 1.5 時間 (段階導入 PR 2 件 + 検証 PR 各 1 件)
> 実施推奨: **明日 PO 立ち会い必須・SEC10-W5 と同レベル危険度**
> 改訂: 2026-05-02 23:55 JST (V2 — auto-merge.yml 実体読み + 段階導入 + rollback 明記 + chicken-and-egg 対処)

---

## 重要な実体 (auto-merge.yml main HEAD・改訂版で確認済)

```yaml
name: Auto-merge PRs (squash when CI green)

on:
  pull_request:
    types: [opened, reopened, synchronize, ready_for_review]

jobs:
  enable-auto-merge:
    if: >-
      github.event.pull_request.draft == false &&
      github.event.pull_request.user.login == github.repository_owner
    steps:
      - name: Enable auto-merge (squash + delete branch)
        run: |
          gh pr merge "$PR_URL" --auto --squash --delete-branch
```

- 単一 job + 単一 step 構造・**`if:` block への conditions 追加が最小修正**
- `gh pr merge --auto` は GitHub の native auto-merge を有効化するだけ (実 merge は GitHub 側が行う)
- **重要**: GitHub native auto-merge は branch protection の **required status checks** が green になるまで待つ。required checks が **未設定だと GitHub は即 merge する** = これが PR #312 / #317 で CI failure ignore された真因
- 本タスクは「auto-merge を有効化させない」ガード追加で、CI failure ignore の根本対処は別タスク (T2026-0502-BRANCH-PROTECTION-REQUIRED-CHECKS・PO 操作必須)

---

## prompt 本文

```
docs/lessons-learned.md「『DO NOT MERGE』test PR が auto-merge で main に流入」を読んでください。
特に「仕組み的対策 5 件」と「横展開チェックリスト」を読み込むこと。

## 目的 (段階導入で 2 PR・1 週間隔)

**PR-A (本セッションで実施)**: PR タイトルに `[DO NOT MERGE]` を含む場合、auto-merge を enable しない
**PR-B (1 週間 PR-A 観察後・別セッション)**: branch prefix `test/` の PR は auto-merge enable しない

段階導入の理由: 
- 1 PR で両方追加して片方バグった場合の切り分けコスト大
- PR-A だけで PR #312 同等事故は防げる (タイトル方が直接的シグナル)
- PR-B (`test/`) は防御の二重化・次の test PR 投稿時に検証可能

GitHub の "Require status checks to pass before merging" の branch protection は PO 操作必須のため別タスク (T2026-0502-BRANCH-PROTECTION-REQUIRED-CHECKS)。本タスクは auto-merge.yml の skip ガード追加のみ。

## 事前確認

1. 現 auto-merge.yml の構造確認:
   cat .github/workflows/auto-merge.yml
   → `if:` block が単一 job レベルにあること確認 (上記「重要な実体」と一致するはず)

2. 現 if 条件をバックアップ (rollback 用):
   git show main:.github/workflows/auto-merge.yml > /tmp/auto-merge.yml.backup-$(date +%Y%m%d_%H%M)
   ls -la /tmp/auto-merge.yml.backup-*
   → backup ファイル存在確認

## 手順 (PR-A: [DO NOT MERGE] skip)

1. main 同期 + 新 branch
   git checkout main && git pull --rebase origin main
   git checkout -b fix/T2026-0502-AUTO-MERGE-GUARDS-PR-A

2. WORKING.md に [Code] 行追加 (PO 立ち会い必須を明記)
   | [Code] T2026-0502-AUTO-MERGE-GUARDS-PR-A [DO NOT MERGE] skip 追加 | Code | .github/workflows/auto-merge.yml | <開始JST> | yes |

3. .github/workflows/auto-merge.yml の if block 編集

   Before:
     if: >-
       github.event.pull_request.draft == false &&
       github.event.pull_request.user.login == github.repository_owner

   After:
     if: >-
       github.event.pull_request.draft == false &&
       github.event.pull_request.user.login == github.repository_owner &&
       !contains(github.event.pull_request.title, '[DO NOT MERGE]')

   注意: GitHub Actions の `contains()` は case-sensitive。`[DO NOT MERGE]` 完全一致のみ判定。
         `[do not merge]` `[Do Not Merge]` 等の variant も block したい場合は title を toUpper して比較する step を追加。
         本タスクでは `[DO NOT MERGE]` 大文字固定で運用 (CONTRIBUTING.md / lessons-learned.md にも明記する案を T2026-0502-CONTRIBUTING で別途起票検討)

4. tests/test_auto_merge_skip_patterns.sh 新設 (skip ロジック単体テスト):
   #!/bin/bash
   # T2026-0502-AUTO-MERGE-GUARDS PR-A 単体 verifier
   # GitHub Actions の if 構文を bash で再現してロジック検証 (CI 上での実テストとは別)
   set -e
   
   # contains() 相当
   contains_dnm() {
     case "$1" in *"[DO NOT MERGE]"*) return 0;; *) return 1;; esac
   }
   
   # ケース 1: 通常 PR title → enable する (return 1 = enable)
   if contains_dnm "fix: ordinary task"; then echo "FAIL: 通常 PR が skip 判定された"; exit 1; fi
   
   # ケース 2: [DO NOT MERGE] 含む → skip (return 0 = skip)
   if ! contains_dnm "[DO NOT MERGE] verify test"; then echo "FAIL: DO NOT MERGE が skip されない"; exit 1; fi
   
   # ケース 3: 大文字小文字違いは現仕様では skip しない (制限明示)
   if contains_dnm "[do not merge] verify"; then echo "WARN: 小文字 [do not merge] が skip 判定された (仕様外動作)"; fi
   
   echo "✅ test_auto_merge_skip_patterns.sh PASS"

   chmod +x tests/test_auto_merge_skip_patterns.sh
   bash tests/test_auto_merge_skip_patterns.sh
   → "✅ test_auto_merge_skip_patterns.sh PASS"

5. (任意) ci.yml に test 実行 step を追加して CI でも回す
   - .github/workflows/ci.yml の構造確認後、適切な job に `bash tests/test_auto_merge_skip_patterns.sh` を追加

6. PR 作成 (この PR 自体は通常 PR・タイトル `[DO NOT MERGE]` を含めない)
   git add WORKING.md .github/workflows/auto-merge.yml tests/test_auto_merge_skip_patterns.sh
   git commit -m "fix: T2026-0502-AUTO-MERGE-GUARDS-PR-A auto-merge.yml に [DO NOT MERGE] skip 追加

PR #312 の [DO NOT MERGE] タイトルが auto-merge.yml で無視され main 流入した事故の物理化 (段階 1/2)。

変更:
- auto-merge.yml の if block に `!contains(github.event.pull_request.title, '[DO NOT MERGE]')` 追加
- tests/test_auto_merge_skip_patterns.sh 新設

段階 2 (branch test/ skip) は 1 週間後 PR-B で実施 (T2026-0502-AUTO-MERGE-GUARDS-PR-B)。

注意: 本ガードは「auto-merge enable しない」だけ。
CI failure ignore の根本対処は branch protection required checks が必要 (T2026-0502-BRANCH-PROTECTION-REQUIRED-CHECKS・PO 操作)。

Verified-Effect-Pending: 本 PR merge 後の検証 PR で [DO NOT MERGE] PR が auto-merge enable されないことを観察
Eval-Due: 2026-05-09 (1 週間後・PR-B 実施判断)"
   git push -u origin HEAD
   gh pr create --fill

7. **チキン&エッグ注意**: この PR 自体は **タイトルに `[DO NOT MERGE]` を含めない** ので旧 auto-merge.yml で merge される。新ロジックは merge 後の **次** PR から有効。よって:
   - PO 立ち会いで CI green 確認後 merge OK
   - 次の任意の PR で動作観察 (PR-A 検証 PR で実証)

8. 検証 PR (PR-A 動作確認):
   git checkout -b verify/T2026-0502-AUTO-MERGE-GUARDS-PR-A-CHECK
   echo "# verify" > /tmp/verify-noop.md
   cp /tmp/verify-noop.md docs/verify-noop-$(date +%s).md
   git add docs/verify-noop-*.md
   git commit -m "chore: verify auto-merge skip"
   git push -u origin HEAD
   gh pr create --title "[DO NOT MERGE] verify auto-merge skip" --body "PR-A 動作確認用・close で OK"
   
   - GitHub UI で PR の "Auto-merge" ボタン状態を確認 → enable されていなければ成功
   - workflow run の "enable squash auto-merge" job が `if conditional: false` で skip されていれば成功
   - PR を gh pr close で閉じる

## Rollback 手順 (PR-A 異常時)

PR-A merge 後に問題が発覚した場合:

オプション A (即時): 
   git checkout main && git pull
   git checkout -b revert/T2026-0502-AUTO-MERGE-GUARDS-PR-A
   git revert <PR-A merge commit sha>
   git push -u origin HEAD
   gh pr create --title "revert: T2026-0502-AUTO-MERGE-GUARDS-PR-A" --fill

オプション B (rollback 時間がないが正常な PR が止まっている場合):
   - GitHub UI で auto-merge.yml を編集して `&& !contains(...)` を削除
   - "Commit directly to main" 選択 (Cowork からは不可・PO 直 push 必要)
   - これは branch protection 設定によっては不可能・rollback PR の方が安全

## 完了条件 (PR-A)

- [ ] auto-merge.yml に `!contains(github.event.pull_request.title, '[DO NOT MERGE]')` が追加
- [ ] tests/test_auto_merge_skip_patterns.sh が CI で pass
- [ ] 検証 PR で実 CI 上で skip されることを確認 (workflow run job が "skipped" 状態)
- [ ] 検証 PR を close
- [ ] docs/lessons-learned.md の横展開チェックリスト「T2026-0502-AUTO-MERGE-GUARD-TITLE」を [x] に更新
- [ ] WORKING.md から自分の行削除
- [ ] done.sh 実行 (Verified-Effect 行に検証 PR の URL + skip 観察結果を記録)

## PR-B (本タスクでは実施しない・別セッション)

PR-A merge から 1 週間 (Eval-Due 2026-05-09) 経過し問題なければ、別 Code セッションで PR-B 実施:
- branch prefix `test/` skip を if block に追加
- 同様の段階導入手順
- prompt は本ファイルを参考に新規作成 (T2026-0502-AUTO-MERGE-GUARDS-PR-B.md)

## 注意

- 既存 PR への影響なし (新規 PR のみ skip 判定)
- secrets.AUTO_MERGE_PAT / secrets.GITHUB_TOKEN の使い方は既存維持
- chicken-and-egg: PR-A 自身は通常 PR (title に `[DO NOT MERGE]` なし) なので旧 if block で merge される・次の PR から新 if block 有効
- AUTO_MERGE_PAT が未設定の警告は無視 (T2026-0502-AT 別件)
- 検証 PR は merge せず必ず close (placeholder ファイルが残らないように)

## PO 立ち会い必須項目

- [ ] PO が起動時刻を確認・隣で観察
- [ ] PR-A merge 直前で PR diff を PO 確認
- [ ] 検証 PR の挙動を PO と同時観察
- [ ] 異常時の rollback 判断は PO が行う (Code セッションは提案のみ)
```
