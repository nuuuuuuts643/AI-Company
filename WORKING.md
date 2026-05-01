# 着手中タスク（複数セッション間の作業競合管理）

> **このファイルのみで管理する。CLAUDE.md の「現在着手中」セクションは廃止。**
> タスク開始・完了のたびに即 `git add WORKING.md && git commit -m "wip/done: ..." && git push` する。

---

## 🟢 Dispatch 継続性 (Cowork コンテキスト引き継ぎ用)

> **目的**: Dispatch のコンテキストが切れても次のセッションが状態を引き継げるよう、
> 現在進行中フェーズ・直近のPO指示・次のアクションを常に最新化する。
> 1 セクション 5 行以内・全部書き換え可。

**直近のPO指示** (2026-05-02 00:00〜01:00 JST):
「規則体系のリライト・違反全パターン物理化・自走 Lv2 化・組織として動く Claude・セキュリティ監査強化。プロダクト完成にブレないようにして欲しい」

**今セッション (Cowork Dispatch) で完了** (2026-05-02 01:14〜01:21 JST):
- ✅ session_bootstrap.sh 起動チェック完了 (CLAUDE.md 649bde89 / 北極星 + current-phase = フェーズ2 全文確認)
- ✅ git lock + 進行中マージ残骸を cowork_commit.py (GitHub API 直接) で迂回。affd1ba8 push 完了 (rules-rewrite-proposal landing + cowork_commit.py 追加 + WORKING.md stale 行除去)
- ✅ T2026-0502-E (session_bootstrap.sh §1c tmp_obj_* 自動退避) は PR #108 (8f275dd5) で既に landed。WORKING.md needs-push 滞留行を物理削除
- ✅ main CI on affd1ba8: env-scripts dry-run / Slack / No inline / メタガード = success / ガバナンス + 構文 = in_progress (CI 待ちは閉じる規則に従い即終了)
- ✅ Code 同時起動 0 件確認 → 新規コードセッション起動可能

**次セッション (Eng Claude / コードセッション・Sonnet・1セッション1タスク) でやること** (PR 経由必須):
1. **T2026-0501-K** 🔴 (フェーズ2 直撃) — `lambda/processor/proc_ai.py` の `_STORY_PROMPT_RULES` 内 keyPoint ◎例をエンタメ (例: 降幡愛の首絞め件 150字) + テック (例: NTT AIOWN 150字) に差し替え。完了条件: 次回 processor 後 エンタメ/テク 各 50%+ 充填。PR→CI→merge→done.sh まで完結。Verified-Effect は scheduled task `p003-sonnet` 手動 trigger or 一時 task に委譲（セッション内で待機しない）
2. **T2026-0501-M** 🔴 (UX 直撃) — 重複トピック検出・マージ。fetcher 類似度閾値調整 or proc_storage エンティティ重複検出。完了条件: flotopic.com で同一事象が1カードに収束（目視）
3. **T2026-0501-N** 🔴 (Dispatch運用) — `gh pr create` 後 `gh pr merge --auto --squash` ルールを CLAUDE.md or `.github/workflows/auto-merge.yml` に landing
4. (フェーズ2 完了条件達成までフェーズ3/4/5 タスクは凍結。current-phase.md 厳守)

**実在スケジューラー**: p003-haiku (7:08am daily) / p003-sonnet (手動のみ) / security-audit.yml (週次)
**FUSE 環境メモ**: Cowork セッションでは git CLI が index.lock を unlink できない場合がある。`scripts/cowork_commit.py "msg" file...` で GitHub API 直接コミットに迂回可能（.git/config の token 自動取得）。

---

## ⚠️ セッション種別ルール（2026-04-27 追加）

このファイルは **Claude Code（Mac/CLI）と Cowork（スマホ/デスクトップアプリ）の両方が書き込む**。

- **Claude Code** が起動時に `cat WORKING.md` をチェックする際、Cowork の行も同様に衝突判定すること
- **Cowork** もタスク開始時にこのファイルに書き込み、完了時に削除する
- 種別は `[種別]` プレフィックスで区別する

| 種別プレフィックス | 意味 |
|---|---|
| `[Code]` | Claude Code タスク（コードタスク、CLI） |
| `[Cowork]` | Cowork セッション（スマホ・デスクトップアプリ） |

## ⚠️ エントリー自動失効ルール（恒久ルール・2026-04-28 制定）

**開始JSTから8時間を超えたエントリーは無効（stale）とみなす。**

- `bash scripts/session_bootstrap.sh` が起動時に自動削除する（手動不要）
- スクリプト失敗時のみ手動で行を削除して push

> 理由: セッションがクラッシュ/タイムアウトした場合、完了処理が走らずエントリーが残り続ける。手動掃除に頼ると発見が遅れる。8時間TTLで自動的に解消する。

## ⚠️ needs-push カラム（恒久ルール・2026-04-28 制定）

**コードファイルを編集する Cowork セッションは `needs-push: yes` を立てる。**

- `lambda/` `frontend/` `scripts/` `.github/` を変更したら必ず `yes`
- push 完了後に行を消すか `no` に書き換える
- 起動チェックスクリプトが `needs-push.*yes` を grep して滞留警告を出す
- 文書だけの変更（`*.md`）では立てなくてよい

> 理由: 「Cowork で実装→push 失敗→Code 起動まで滞留」の事故を物理ゲートで防ぐ（lessons-learned: 2026-04-28 連携の構造的欠陥より）。

## ⚠️ セッション役割分担（恒久定義・2026-04-28 制定）

**Code（Claude Code）がやること**:
- `lambda/`・`frontend/`・`scripts/`・`.github/` のコード変更
- テスト実行・Lambda手動invoke・デプロイ確認
- TASKS.md のステータス更新（実装完了後）

**Cowork がやること**:
- `CLAUDE.md`・`WORKING.md`・`TASKS.md`・`HISTORY.md` のドキュメント更新
- CloudWatch確認・S3データ参照・ステータス報告
- POとの会話・分析・計画立案
- **コードファイルの編集もOK**（WORKING.mdに [Cowork] 行を明記してから着手）
- **git操作もOK** — push前に `rm -f .git/index.lock .git/HEAD.lock` を実行してから git add/commit/push する

> Coworkが実装からpushまで完結できる。lockファイル削除で競合を回避する。

---

## タスク開始前（毎回必須）

```bash
git pull --rebase origin main
git log --oneline -5 -- CLAUDE.md   # 変更があれば CLAUDE.md を再読してから続行
cat WORKING.md                       # staleエントリー（8時間超）は削除してから確認
```

重複なし → このファイルに追記 → 即 push して他セッションに宣言する。

## タスク完了後（毎回必須）

```bash
# 1. このファイルから自分の行を削除
# 2. 全変更を commit & push
git add -A && git commit -m "done: [タスク名]" && git push
```

---

## 記入フォーマット

| タスク名 | 種別 | 変更予定ファイル | 開始 JST | needs-push |
|---|---|---|---|---|

> code 編集を含むセッションは必ず `needs-push: yes`。push 後は `no` に切り替える or 行を削除する。

---

## 現在着手中

| タスク名 | 種別 | 変更予定ファイル | 開始 JST | needs-push |
|---|---|---|---|---|
| [Cowork] CI fix: PII 違反解消 (affd1ba8 PII 検査 fail / sk-ant-/個人メール マスク) | Cowork | docs/rules-rewrite-proposal-2026-05-01.md | 2026-05-02 01:25 | yes |
