# Code セッション起動 prompt: T2026-0502-AUTO-MERGE-GUARDS

> 用途: auto-merge.yml が CI failure / `[DO NOT MERGE]` PR を merge してしまう構造問題を物理修正
> 関連: PR #312 / PR #317 自身も auto-merge された事案・docs/lessons-learned.md
> 推奨モデル: **Sonnet** (workflow YAML 編集 + 動作確認)
> 想定所要: 1 時間

---

## prompt 本文

```
docs/lessons-learned.md「『DO NOT MERGE』test PR が auto-merge で main に流入」を読んでください。
特に「仕組み的対策 5 件」と「横展開チェックリスト」を読み込むこと。

## 目的

auto-merge.yml の以下 2 つの構造問題を物理修正する:

1. PR タイトルに `[DO NOT MERGE]` が含まれる場合、auto-merge を enable しない
2. branch prefix `test/` の PR は auto-merge enable しない (test 用 PR は手動 merge のみ)

GitHub の "Require status checks to pass before merging" の branch protection は PO 操作必須のため別タスク (T2026-0502-BRANCH-PROTECTION-REQUIRED-CHECKS)。本タスクは auto-merge.yml 自体の修正に集中。

## 手順

1. main 同期 + 新 branch
   git checkout main && git pull --rebase origin main
   git checkout -b fix/T2026-0502-AUTO-MERGE-GUARDS

2. .github/workflows/auto-merge.yml を読む
   - PR title / branch name を取得する step を追加
   - 該当パターンなら enable_pull_request_auto_merge を skip
   - skip 時は PR にコメント or step summary に理由を記録

3. 期待実装イメージ:

   - if: |
       !contains(github.event.pull_request.title, '[DO NOT MERGE]') &&
       !startsWith(github.event.pull_request.head.ref, 'test/')

4. tests/test_auto_merge_skip_patterns.sh 新設 (既存 tests/ パターンに従う):
   - PR title に `[DO NOT MERGE]` を含む場合 skip 出力されること
   - PR head ref が `test/` で始まる場合 skip 出力されること
   - 通常 PR では従来通り enable されること

5. WORKING.md に [Code] 行追加してから push、PR、CI green、merge

6. 検証 PR (動作確認):
   - branch `test/T2026-0502-AUTO-MERGE-GUARDS-VERIFY` でタイトル `[DO NOT MERGE] verify` の PR を出す
   - auto-merge.yml が enable しないことを CI log で確認
   - PR を close

## 完了条件

- auto-merge.yml に title `[DO NOT MERGE]` skip + branch `test/` skip ロジック実装
- tests/test_auto_merge_skip_patterns.sh が CI で pass
- 検証 PR で実 CI 上で skip されることを確認
- docs/lessons-learned.md の横展開チェックリスト「T2026-0502-AUTO-MERGE-GUARD-TITLE」を [x] に更新

## 注意

- auto-merge.yml の他の挙動 (通常 PR の auto-merge) を壊さないこと
- 既存 PR への影響なし (新規 PR のみ skip)
- secrets.GITHUB_TOKEN または PAT の使い方は既存維持

## Verified-Effect

- 検証 PR で auto-merge skip 動作確認
- 1 ヶ月後の Cowork test PR 投稿で再発しないこと (passive)
```
