# RULES.md (ドラフト・採用候補)

> 採用される場合 `~/ai-company/RULES.md` として配置。CLAUDE.md からはこのファイルへリンクのみ。
> 上限 200 行。超えたら統廃合または LESSONS.md 移動を必ず行う。

## 絶対ルール 7 か条

1. **完了の定義 = 本番動作確認済み**。`done.sh <id> <verify_target>` を必ず通す。`url:<https>` `lambda:<fn>` `topic-ai:<id>` のいずれか必須。verify_target なしの完了報告は禁止
2. **依存口頭化**: ファイル変更前に「このファイルを参照している箇所」を 1 行明文化してから変更する。書けなければ変更しない
3. **同名ファイル並行編集禁止**: WORKING.md に自分の行を追記し commit & push してからコードに触る
4. **PII / secrets コード直書き禁止**: env var or AWS Secrets Manager 必須
5. **再発防止 = フルセット必須**: Why1〜5 構造化 + 仕組み対策 3 つ以上 + 物理ゲート (CI / pre-commit / 外部 SLI) 1 つ以上。テーブル 1 行追記は再発防止ではない
6. **外部観測 SLI 必須**: ユーザーが見るデータの鮮度・正常性を、コード外から測るモニタを 1 つ以上持つ
7. **長文化禁止**: このファイルが 200 行を超えたら統廃合または LESSONS.md 移動 (CI で物理ブロック)

## セッション開始時の機械的手順

```bash
# 1. git lock 削除 → 同期
rm -f ~/ai-company/.git/index.lock
cd ~/ai-company
git add -A && git commit -m "chore: sync $(date '+%F %H:%M')" 2>/dev/null
git pull --rebase origin main
git push 2>/dev/null

# 2. RULES.md 直近変更を確認 (今日の日付ヒットなら冒頭再読)
git log --oneline -5 -- RULES.md

# 3. WORKING.md の 8h 超 stale を削除
# 4. TASKS.md の未着手タスクを優先度順に着手
```

## タスク実行プロトコル

1. WORKING.md に `| <id> <name> | <role> | <変更予定ファイル> | <開始JST> |` を追記 → 即 commit & push
2. 実装
3. 完了検証: `bash done.sh <id> <verify_target>` (verify_target 省略禁止)
4. WORKING.md から自分の行を削除 → commit & push
5. HISTORY.md に完了記録を追記

## 設計時のチェックリスト (4 問)

実装前に声に出して答える。答えられないなら実装しない。

1. このユーザーは今何をしたくてこのページにいるか
2. この機能はその欲求に直接応えているか
3. この機能が無い状態と比べて体験は改善されるか
4. ラベル / 見出し / コンテンツが誤解を与えないか

## 新規外部システム統合の 3 ステップ

外部 SaaS / API / 広告ネットワーク / 認証連携を導入するときは必ず:

1. **公式ドキュメント通読** — Implementation Guide / Verification セクションを最後まで読む
2. **外部が読みに来る全ファイル列挙** — `ads.txt` `robots.txt` `sitemap.xml` `manifest.json` `.well-known/*` `所有権検証 HTML` 等
3. **外部管理画面で Verified を確認してから完了宣言** — 自社コードが動いているだけでは完了ではない

## 設計の前提を疑う (代表事例)

| よくある誤前提 | 実際 |
|---|---|
| RSS / API は期待どおりのデータを返す | 返さない。スコアが薄い時のフォールバックは「最も保守的な値」に倒す |
| LLM はプロンプト指定で JSON 出力する | 確率的に崩れる。Tool Use (function calling) で structured output 強制 |
| 同名 secret / env はセットされている | セットされていない。投稿系は最初に dry-run で実送信を確認する |
| 外部システムは scriptタグから自動で読みに来る | 別ファイル (ads.txt 等) を独立にクロールする。両方更新する |
| 再発防止ルール = テーブルに 1 行足す | 違う。Why1〜5 + 物理ゲートまでが 1 セット |

## なぜなぜ分析テンプレート (LESSONS.md に書く形式)

```
### <事象名> なぜなぜ分析 (YYYY-MM-DD)

**起きたこと**: 事実 1-2 文

| Why | 答え |
|---|---|
| Why1 | … |
| Why2 | … |
| Why3 | … |
| Why4 | … |
| Why5 | … |

**仕組み的対策** (3 つ以上 / うち 1 つは物理ゲート必須):
1. **コードルール追加** — RULES.md の対応行
2. **CI / pre-commit 物理ブロック** — スクリプト名と検出ロジック
3. **外部観測 SLI** — モニタ対象と閾値
```

## 物理ゲート (実装済み / 計画)

| 名称 | 検出対象 | 状態 |
|---|---|---|
| `check_rules_size.sh` | RULES.md > 200 行 | 計画 (pre-commit) |
| `done.sh` verify | 本番 URL / Lambda エラー / topic AI 充填 | 既存・要強化 (verify_target 必須化) |
| `freshness_check` | 主要 API の updatedAt > 90min | 計画 (EventBridge 1h) |
| `safe_format boundary test` | 0/null/undefined/NaN/範囲外 | 既存 (tests/safe_format.test.js) |
| `script tag defer/async guard` | chart.js/config.js/app.js/detail.js | 既存 (CI) |

## ファイル責任マトリクス

| 種別 | ファイル | append-only か | 更新タイミング |
|---|---|---|---|
| 現役ルール | RULES.md (このファイル) | × | 上限超過時に統廃合 |
| なぜなぜアーカイブ | LESSONS.md | ○ | 事象発生時 |
| プロジェクト現況 | projects/<id>/STATE.md | × | タスク完了時 |
| 完了履歴 | HISTORY.md | ○ | done.sh 実行時 |
| 着手中 | WORKING.md | × | 着手 / 完了時 |
| 未着手 | TASKS.md | × | 起票 / 着手 / 完了時 |
| プロジェクト固有ルール | projects/<id>/RULES.md | × | 上限超過時に統廃合 |
