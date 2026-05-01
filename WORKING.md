# 着手中タスク（複数セッション間の作業競合管理）

> **このファイルのみで管理する。CLAUDE.md の「現在着手中」セクションは廃止。**
> タスク開始・完了のたびに即 `git add WORKING.md && git commit -m "wip/done: ..." && git push` する。

---

## 🟢 Dispatch 継続性 (Cowork コンテキスト引き継ぎ用)

> **目的**: Dispatch のコンテキストが切れても次のセッションが状態を引き継げるよう、
> 現在進行中フェーズ・直近のPO指示・次のアクションを常に最新化する。
> 1 セクション 5 行以内・全部書き換え可。

**直近のPO指示** (2026-05-01): 「ユーザー体験周りの評価が弱い・改善が機能してるか不明・トピックが無難・表題に惹きがない」+「正確性/リーガル制約も加味」+「ジャンル/トピック単位プロンプト分岐」+「PR放置するな」

**次のアクション（スケジューラー待ち）**: 05/01 05:30 JST→processor実行(keyPoint/perspectives効果測定) / 05/01 07:00 JST→UX/revenue-sli週次実行 / 05/01 08:03 JST→SLI朝チェック

**直近 landing**: T2026-0430-L (PR #66, fresh24h NFKC+Jaccard) / T2026-0430-J (PR #61, keyPoint backfill 先頭挿入) / T2026-0501-A (PR #68, すべてタブ+velocityScore) / T2026-0501-B (PR #70, 履歴クロスデバイス同期) / T2026-0501-C (タイトル改善+定性評価CI) — フェーズ2 高優先タスク全消化済。

**現フェーズ**: フェーズ2 (AI品質) + 収益計測基盤 — 高優先実装完了、SLI 効果測定はスケジューラー (05:30/07:00/08:03 JST) 待ち

**直近 SLI 実測 (2026-05-01 04:10 JST P003 自律巡回・公開 topics-card.json サブセット 202件)**: keyPoint>=100字 充填率 29.7% (60/202) — 04/28 ベースライン 10.02% から +19.7pt 改善 / ac>=3 サブ 36.4% (32/88) / kp 平均長 **103.8字** (04/28 43.8字 → +60字、T2026-0430-A `_retry_short_keypoint` 効果顕在化) / **storyPhase 発端率 (ac>=3) 0.0% (0/88) ✅ 完了条件 10% 未満 達成** (T2026-0429-G `normalize_minimal_phase` 効果) / aiGenerated 144件中 kp>=100字 40.3%。**フェーズ2 完了条件は keyPoint 充填率 70% のみ未達**。05:30 JST processor 実行後に再観測。

**朝SLI (2026-05-01 08:04 JST `p003-sli-morning-check` scheduled)**: topics.json 228件 / stale48h=39.0%(89/228) ⚠️>30% / official check_age_decay.sh: stale_24h+=2.2%(5) exiled_72h+=37.3%(85) top30_stale=0.0% / keyPoint>=50字=38.6%(88/228) ⚠️<50% → TASKS.md に T2026-0501-SLI-AGE / T2026-0501-SLI-KP 追記。AWS CLI 不在のため公開 topics.json で代替観測。

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
| [Code] T2026-0501-G outlook プロンプト抜本改修 (視点+条件付き予想) | feat | projects/P003-news-timeline/lambda/processor/proc_ai.py, projects/P003-news-timeline/tests/test_title_prompt_quality.py | 2026-05-01 11:15 | yes |

