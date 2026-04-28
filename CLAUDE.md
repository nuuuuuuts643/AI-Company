# ⚡ セッション開始時に必ず最初に実行すること

```bash
bash /Users/murakaminaoya/ai-company/scripts/session_bootstrap.sh
```

これ 1 本で以下が走る（詳細は `docs/rules/global-baseline.md` §3）:

1. git lock / rebase-merge 退避（FUSE rm 不可対応）
2. sync commit + pull (`--no-rebase`) + push
3. `CLAUDE.md` の最近の commit を表示（変更があれば本ファイルを再読してから続行）
4. `WORKING.md` 8h 超 stale 自動削除
5. `TASKS.md` の取消線済み行を `HISTORY.md` に集約移動
6. `needs-push: yes` 滞留警告
7. 1 行サマリ出力

スクリプトが完了サマリを出したら「✅ 起動チェック完了」と報告して着手に進む。

---

## ⚡ 起動後の自動タスク実行

`cat /Users/murakaminaoya/ai-company/TASKS.md` → 状態が「未着手」のタスクを優先度順で実行する。

各タスクで以下を順守:

1. **WORKING.md の stale (8h 超) を削除**
2. **WORKING.md に自分の行を追記してから push**（記載なしでコード変更禁止 — 物理ルール）
   ```
   | [Code|Cowork] <タスクID> <タスク名> | <種別> | <変更予定ファイル> | <開始JST> |
   ```
3. **実装する**
4. **完了したら WORKING.md から自分の行を削除し commit & push**

ナオヤから新指示があれば優先。未着手なし → 「タスクなし、待機中」と報告して待機。

---

## ⚡ 絶対ルール（最低限・全プロジェクト共通）

| ルール | 内容 |
|---|---|
| **完了 = 動作確認済み + 効果検証済み** | push しただけは未完了。①フロント=本番URL目視 / Lambda=CloudWatchエラーなし。`done.sh <task_id> <verify_target>` で自動検証。②**修正の効果検証** — 「URL が開ける」だけでは不十分。修正種別に応じて `bash scripts/verify_effect.sh <fix_type>` を実行し、改善が数値で出ていることを確認。fix_type: `ai_quality` (keyPoint/perspectives 充填率)、`mobile_layout` (375px 横スクロール)、`freshness` (topics.json 鮮度)。閾値未達は未完了。 |
| **Verified 行 commit 必須** | `feat:` `fix:` `perf:` の commit には `Verified: <url>:<status>:<JST_timestamp>` 行に加え、効果検証を行った場合は `Verified-Effect: <fix_type> <metric>=<value> PASS @ <JST>` 行も含める。pre-commit hook で物理ゲート (`scripts/git-hooks/pre-commit`)。ヘルパ: `scripts/verified_line.sh <url>` (URL 到達)、`scripts/verify_effect.sh <fix_type>` (効果計測)。**「修正した」と「改善した」を区別する物理ゲート。** |
| **変更前に副作用確認** | 「このファイルが何に依存されているか」を声に出す。言えなければ変更しない |
| **同名ファイル並行編集禁止** | WORKING.md 宣言なしで触らない |
| **scriptタグ defer/async 禁止** | chart.js / config.js / app.js / detail.js。CI で物理ブロック |
| **新規 formatter は boundary test 同梱** | 0/null/undefined/NaN/未来日付を全部 assert |
| **PII / secrets コード直書き禁止** | env var か AWS Secrets Manager 必須 |
| **実装前に全体影響マップ必須** | 新機能追加・修正前に ①影響ファイル一覧 ②依存方向 ③副作用シナリオ を箇条書きで列挙し、ナオヤに確認してから着手。「とりあえず実装」禁止。調査→報告→承認→着手の順を物理ルールとする |
| **リーガル観点は都度チェック** | 外部データソース追加・コンテンツ表示変更・新機能実装のたびに `docs/rules/legal-policy.md` のチェックリストを確認する。一度良しとしても次の変更で再確認。 |
| **対症療法ではなく根本原因** | 足回りで誤魔化さない。band-aid (lenient parsing 等) より API 設計修正 |
| **なぜなぜ分析は構造化** | 問題発生時 Why1〜Why5 + 仕組み的対策 3 つ以上を `docs/lessons-learned.md` に追記。テーブル 1 行追記は再発防止と呼ばない。仕組み的対策には「外部観測」「物理ゲート」を最低 1 つ含める |
| **Lambda 主ループ wallclock guard 必須** | 外部 API 呼び出しを伴うループは `context.get_remaining_time_in_millis()` で残り時間を測り break。回数ベース上限と時間予算を整合させる |
| **新規外部システム統合の3ステップ** | ①公式ドキュメント通読 ②外部が独立に読みに来る全ファイルをリスト化 ③全部実装→外部管理画面で「Verified」確認 してから完了宣言 |
| **CLAUDE.md は 250 行以内** | CI で物理ガード。超えたら `docs/lessons-learned.md` / `docs/rules/` / `docs/system-status.md` に外出しする |
| **タスクID 採番** | `bash scripts/next_task_id.sh` で取得。日付ベース ID で衝突防止。CI で重複検出 |
| **deploy.sh は直接実行しない** | デプロイは GitHub Actions 任せ。インフラ新規作成のみ例外でナオヤ確認 |

---

## ⚡ 完了の流れ

1. 完了タスクを `HISTORY.md` に追記。CLAUDE.md には1行痕跡のみ
2. `bash done.sh <task_id> <verify_target>` で動作確認込みで完了処理
3. commit メッセージに `Verified: <url>:<status>:<timestamp>` 行を含める

---

## ⚡ 規則の置き場所（責務別ファイル）

| ファイル | 内容 |
|---|---|
| `CLAUDE.md` (本ファイル) | 起動チェック・絶対ルール（250 行以内） |
| `docs/rules/global-baseline.md` | **全プロダクト共通の前提条件**（P002/P006 等で再利用） |
| `docs/lessons-learned.md` | なぜなぜ事例集（append-only・Why1〜Why5 + 仕組み的対策） |
| `docs/system-status.md` | プロジェクト状態スナップショット（毎セッション必読） |
| `docs/rules/bug-prevention.md` | 再発防止ルール表（パターン×ルール） |
| `docs/rules/design-mistakes.md` | 設計ミスパターン集 |
| `docs/rules/quality-process.md` | 品質改善の進め方（finder/implementer 共通） |
| `docs/rules/user-context-check.md` | 実装前ユーザー文脈チェック（4つの問い） |
| `docs/rules/legal-policy.md` | 法的・規約方針（引用・クロール・一次情報バッジ） |
| `docs/flotopic-vision-roadmap.md` | プロダクトビジョン |
| `docs/product-direction.md` | 現在のプロダクト方針（毎セッション必読・session_bootstrap.sh が起動時に全文表示） |

タスク開始時に CLAUDE.md → global-baseline.md → system-status.md → product-direction.md の 4 つを確認し、必要に応じて他を参照する。

---

## ⚡ Cowork ↔ Code 連携ルール

両方が同一リポジトリに git push する。役割分担:

**Code（Claude Code/CLI）**:
- `lambda/` `frontend/` `scripts/` `.github/` のコード変更
- テスト実行・Lambda 手動 invoke・デプロイ確認
- TASKS.md ステータス更新（実装完了後）

**Cowork（スマホ/デスクトップアプリ）**:
- `CLAUDE.md` `WORKING.md` `TASKS.md` `HISTORY.md` のドキュメント更新
- CloudWatch 確認・S3 データ参照・ステータス報告
- ナオヤとの会話・分析・計画立案
- コードファイル編集も可（WORKING.md 明記してから）
- git 操作も可（push 前に lock 退避: `mv .git/*.lock .git/_garbage/`）

> Cowork が実装〜push まで完結できる構造。lock 退避で競合を回避する。

---

## ⚡ Team Operating Rules

**完了条件**: build/compile 通過 + 主要機能動作確認 + 全テストパス + フロントは本番 URL で目視 + Verified 行付き commit。

**完了報告ルール**: 「できた」の前に①エラーログ確認②動作確認③警告修正。自力で直せない場合は「ここで詰まっている」と報告する。

**共通原則**: 実装だけで完了扱いにしない。UI/文言を勝手に省略しない。自力で直せるエラーは直して再実行する。空報告禁止。証拠（ファイル変更・ログ・スクリーンショット）を必ず示す。

---

## ⚡ プロジェクト状態 → `docs/system-status.md`

> 詳細スナップショット・残タスク・将来アイデアは外出し。

**現在着手中** → `WORKING.md`
**完了済み** → `HISTORY.md`
**未着手キュー** → `TASKS.md`

---

## ⚡ 絶対ルール（毎セッション遵守）

- 決まったことは会話で終わらせず即ファイルに書く
- URL の確認・デプロイ確認は自分でやる（ナオヤに聞かない）
- 「書きました」「やります」の宣言は信用されない。ファイル存在が証拠
- 空報告禁止
- 実装した≠動いている。実際にエンドユーザーが使えて初めて完了
