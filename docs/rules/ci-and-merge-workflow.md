# PR作成後のCI確認+マージワークフロー（2026-05-03 制定）

> このファイルが詳細。CLAUDE.md には要約のみ記載。

## ワークフロー全体

| ステップ | 実行者 | 内容 |
|---|---|---|
| 1. 実装+PR作成 | Code セッション | ブランチで実装 → PR 作成 → **即 exit** |
| 2. CI 確認+マージ | Dispatch (Haiku) | `gh pr checks NNN` で green 確認 → `gh pr merge` → 報告 |

---

## Dispatch（Haiku セッション「PR #NNN CI確認+マージ」）の責務

**PR完了報告を受け取ったら以下を実行:**

1. **状態確認**: `gh pr checks NNN` を実行
   - ✅ **green**: そのままマージへ
   - 🔴 **fail**: エラー分析 → Code セッション起動（修正は Code に委ねる）
   - ⏳ **pending**: 最大 2 分待機 → `gh pr checks NNN` 再確認（2回まで）
     - 2回の確認で pending が続く場合は Code セッション起動に handoff

2. **マージ実行**: `gh pr merge NNN --squash --admin` (green の場合のみ)
   - squash: ブランチのコミットを 1 つに統合
   - admin: branch protection override （admin 権限で push-to-merge）
   - PR完了報告を出す

3. **禁止事項**:
   - ❌ Monitor ポーリング（実施コストが高い）→ 直接 `gh pr checks` を 1〜2回確認のみ
   - ❌ 「スケジューラーに任せる」「bootstrap に任せる」→ **誰が確認するのか不明**になり CI 失敗の検出が遅延

---

## 背景（なぜ Dispatch がやるのか）

**Code セッション（実装者）がやってはいけない理由:**
- PR 作成直後の「CI pending」を確認することはコンテキスト消費。実装と関係ない待機時間が増える
- 複数の Code セッションが同時に走っている場合、「誰が CI 確認するのか」が不明になる
- GitHub Actions が green になるまでの時間が不確定（2分〜10分）のため、Monitor ポーリングは禁止（コスト規律ルール）

**Dispatch（PM 役の Haiku）がやる理由:**
- PR 完成→Report というワークフローの中で「CI確認+マージ」は自然な作業ステップ
- 複数の PR が待機している場合、Dispatch がキュー管理する
- モデル選択: Haiku で十分（やることは `gh pr checks` + `gh pr merge` という機械的操作）

---

## マージ後の実機確認（別の責務）

**ここからは実装者（Code）の責務:**
- Lambda/Frontend 変更: デプロイ完了後 flotopic.com で動作確認
- 確認完了後: `bash done.sh <task_id> flotopic.com:<url>:<status>:<JST>` を実行

詳細は `CLAUDE.md` の「完了の流れ」を参照。
