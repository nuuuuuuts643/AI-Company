# 規則・方針リライト提案 — プロダクト完成にブレない構造へ

> 作成: 2026-05-01 / 対象: CLAUDE.md / docs/rules/* / docs/product-direction.md / docs/project-phases.md / docs/flotopic-vision-roadmap.md
> 起点: 「Claude がルール違反しまくっている」「プロダクト完成に向けブレないようにして欲しい」「一タスクの完遂に囚われて変な方向に進む」
> 出力: 現状診断 → 構造問題 → リライト案 → 物理ガード追加案 → 廃止統合案 → 移行プラン

---

## 0. TL;DR（30秒で読む）

**根本問題は「ルールが多すぎる」ではなく「Claude がタスク完遂に局所最適化してプロダクト目標から離れる」。**

ルール違反は症状。原因は3つ：

1. **北極星（ビジョン・思想）が起動時に読まれない**。`product-thinking.md`(2026-05-01・最新) は CLAUDE.md からも session_bootstrap.sh からも参照されていない
2. **思想ルールが多すぎて物理ガードが弱い**。CLAUDE.md「絶対ルール」表 16件のうち思想 6件・物理 9件・観測 1件。Dispatch運用は事実上ほぼ思想で守られない
3. **タスク完遂を「成功」と定義してしまう構造**。「このタスクは現フェーズ完了条件のどこに効くか」を明示する物理ガードがない

**提案: 4層構造に再編**

```
Layer 1 不変層 (北極星)         → docs/north-star.md (新設・1ファイル統合・起動時全文表示)
Layer 2 フェーズ層 (現在地)      → docs/current-phase.md (新設・20行以内・起動時全文表示)
Layer 3 規則層 (操作)           → CLAUDE.md (100行以内) + docs/rules/*.md (役割整理)
Layer 4 状態層 (観測)           → WORKING.md / TASKS.md / system-status.md (現状維持)
```

加えて **commit-msg hook に `Phase-Impact:` 必須行**を追加。「このコミットは現フェーズ完了条件のどれを前進させるか」を 1 行で書けない feat/fix は reject。タスク完遂の局所最適化を物理ブロックする。

---

## 1. 現状診断 — 5つの違反パターン × 既存ルールのカバー

ユーザー申告の違反パターンと、現規則体系のカバー状況。**◎=物理 / ○=観測 / △=思想（テキストのみ）**。

### ① Dispatch運用の崩壊
昨日の `dispatch-reflection-2026-05-01.md` に 5 件記録：同時2セッション / コード読まずプロンプト / 実機確認なし完了報告 / CI失敗気づいて無視 / セッション長期継続。

| 症状 | 規則 | 場所 | 強度 | 評価 |
|---|---|---|---|---|
| 同時1件 | session_bootstrap.sh が `[Code]` 行 ≥2 で ERROR + exit 1 | CLAUDE.md セッション並走ルール | ◎ | 物理化済 ✅ |
| コード読まずプロンプト | 「該当ファイルを Read してから書く」 | CLAUDE.md Dispatch絶対禁止パターン (2026-05-01) | △ | 思想 — 検出機構なし |
| 実機確認なし完了 | 「flotopic.com でブラウザ確認」 / scheduler義務 | CLAUDE.md / global-baseline §11 | △ + ○ | 思想 + 観測。done.sh の verify_target は省略可能 |
| CI失敗を放置 | 「気づいたら即対処または TASKS.md に積む」 | CLAUDE.md Dispatch絶対禁止 | △ | 思想のみ |
| セッション長期継続 | 「往復20回を超えたらWORKING.mdにDispatch継続性を書き込み切り替える」 | CLAUDE.md | △ | 思想 — カウンタなし |

→ **物理ガードがあるのは1件のみ**。残り4件は「気づいたら直す」しか機構がなく、昨日の事故が起きた。

### ② 完了基準の甘さ（暫定対処・効果検証なし）

| 症状 | 規則 | 強度 | 評価 |
|---|---|---|---|
| Verified行なしで完了 | commit-msg hook で reject | ◎ | 物理 ✅ |
| 効果検証なしで完了 | done.sh + verify_effect.sh | ◎ + △ | 物理だが verify_target 省略可・fix_type 4種固定 |
| 対症療法 | 「対症療法ではなく根本原因」 | △ | 思想 — 判断は人間 |
| なぜなぜ書かない | 横展開チェックリスト + check_lessons_landings.sh | ◎ | 物理 ✅ |

→ Verified 行は通るが、`Verified-Effect` は実装あるものの新規 fix_type を追加しないと検証パターンを増やせない構造。

### ③ ファイル更新の取り違え

| 症状 | 規則 | 強度 | 評価 |
|---|---|---|---|
| WORKING.md 書き忘れ | 「記載なしでコード変更禁止 — 物理ルール」 | △（物理と書いてあるが実際は思想） | session_bootstrap が stale 削除のみ・書き忘れ検出なし |
| system-status.md 同時更新 | docs-sync-check.yml + PR テンプレ | ◎ | 物理 ✅ |
| 取消線 → HISTORY 移動 | session_bootstrap.sh | ◎ | 物理 ✅ |
| ファイル責務表 | CLAUDE.md「規則の置き場所」+ global-baseline §2 | △ | 二重記述（drift リスク） |

→ 「物理ルール」と書いてあるが実装が思想。要物理化。

### ④ プロダクト方針の逸脱（一タスク完遂に囚われて変な方向）

> **これがユーザーの指摘した「やばい」やつ。**

| 症状 | 規則 | 強度 | 評価 |
|---|---|---|---|
| 現フェーズ優先 | 「フェーズ1完了条件未達のうちはフェーズ2/3を着手しない」 | △ | 思想 — タスク着手時の自己宣言なし |
| AI 4軸キーワード保持 | content-drift-guard CI | ◎ | 物理 ✅ |
| ビジョン参照 | 「タスク開始時に5ファイル確認」 | △ | 思想 — 起動時表示は2ファイルのみ |
| 思想（北極星）参照 | product-thinking.md | △ | **CLAUDE.md からも bootstrap からも参照なし** |
| ユーザー体験への寄与 | 「タスク実装前『ユーザー体験で何が変わるか』必須確認」 | △ | 思想（bug-prevention.md） |

→ **ここが最も穴だらけ**。タスクに着手するときに「これは現フェーズ完了条件にどう効くか」を明示するゲートが一切ない。だから「とりあえず動く実装」「とりあえず SLI を上げる band-aid」が通る。

### ⑤ 修正→確認→修正の雑さ

| 症状 | 規則 | 強度 | 評価 |
|---|---|---|---|
| 1バグ→他に同パターン無いか | bug-prevention.md「1バグ発見→同類全探索」 | △ | 思想（commit にgrep結果記載が任意） |
| 横展開チェックリスト追記 | check_lessons_landings.sh | ◎ | 物理 ✅ |
| ユーザー文脈4つの問い | user-context-check.md | △ | 思想 — 起動時非表示・参照されない |
| 局所パッチサイン検出 | data-quality-playbook.md §1-3 | △ | 思想 |

---

## 2. 構造問題（規則体系そのものの欠陥）

### A. 規則の階層が無い
CLAUDE.md (224行) と global-baseline.md (188行) の両方が「規則本体」を名乗る。どちらが上位かが決まっていない。Claude は 2 ファイル分を読まされ、重複した表を 2 度パースする。

### B. 起動時に読まれないファイルが多い
session_bootstrap.sh が起動時に表示するのは `product-direction.md` 全文 + `project-phases.md` 先頭30行のみ。

**読まれていない（がCLAUDE.mdは「必要に応じて参照」と書く）**:
- `product-thinking.md`（2026-05-01・最新の思想・未参照） ★最重要漏れ
- `user-context-check.md`（4つの問い）
- `quality-process.md`（5ステップ）
- `bug-prevention.md` / `design-mistakes.md`（修正前必読のはず）
- `legal-policy.md`
- `data-quality-playbook.md`
- `scheduled-task-protocol.md`
- `story-branching-policy.md`

Claude は「必要だ」と判断しないので結局読まない。

### C. 物理 / 観測 / 思想の比率が悪い
最新追加ルールほど思想に偏る：
- 2026-04-30「CI 待ちは即クローズ」: 思想
- 2026-05-01「Dispatch絶対禁止パターン」（6項目）: ほぼ思想
- 2026-05-01「アドホックAPI呼び出し禁止」: 思想
- 2026-05-01「コードセッションのモデル選択」: 思想

「気づいたら追加」モードで物理化されないまま積み上がっている。

### D. ルール棚卸しがない
CLAUDE.md の 224 行のうち、何 % が直近 6ヶ月で実際に違反検出されたか不明。`scripts/check_soft_language.sh` で「気を付ける」混入は検出するが、**効果が観測されないルール自体を削除する仕組みがない**。

### E. ビジョン・思想・方針・フェーズが4ファイル分散
- ビジョン: `flotopic-vision-roadmap.md`（2026-04-27・古い）
- 思想: `product-thinking.md`（2026-05-01・最新・未参照）
- 方針: `product-direction.md`（2026-04-28＋2026-05-01追記）
- フェーズ: `project-phases.md`（2026-04-28）

**4ファイルでフェーズ表記がそれぞれ違う**。例: `product-direction.md` は「Ph1 ✅ほぼ完了」、`project-phases.md` は「フェーズ1 完了 (2026-04-28 PM)」、`flotopic-vision-roadmap.md` は「フェーズ1（完了）」+ 古いリスト。Claude はどれを正としていいかわからない。

### F. ファイル責務表の重複
CLAUDE.md「規則の置き場所」表 と global-baseline §2「ドキュメント構成」表が**同じ内容を別表現で**書いている。1 箇所変えると drift する典型。

---

## 3. リライト案 — 4層構造

### 設計原則

1. **Claude の起動時 1 回で「揺らがない判断軸」を必ず読ませる**
2. **思想ルールは物理ガードに変換する。変換できないなら思想層から外して「読み物」に降格**
3. **重複を排除する。1 ルール 1 ファイル**
4. **タスク完遂 ≠ 成功。フェーズ完了条件への寄与 = 成功**

### Layer 1: 不変層（北極星）— 起動時必読

#### 新設: `docs/north-star.md`（50〜80行）

統合元:
- `docs/flotopic-vision-roadmap.md` のビジョン部分（先頭20行）
- `docs/rules/product-thinking.md` 全文
- `docs/product-direction.md` の「長期ビジョン」セクション

含む内容:
- 究極のゴール（情報の地図 → 収益化 → SNS化 / コメント機能）
- プロダクト思想（「完了は存在しない」「ループが本体」「指標は手段」「全部繋がっている」）
- ブレないための判断基準（「このタスクは情報の地図の完成に近づくか」）
- AI 生成物 4要素（状況解説 / 各社見解 / 注目ポイント / 予想判定）

session_bootstrap.sh で**起動時に全文表示**。

> **Why**: ユーザー指摘「一タスクの完遂に囚われて変な方向に進む」の直接対策。タスク着手前に必ず「情報の地図」の絵が頭に入っている状態を作る。

### Layer 2: フェーズ層（現在地）— 起動時必読

#### 新設: `docs/current-phase.md`（20行以内）

抽出元: `docs/project-phases.md` の現フェーズと完了条件のみ

書式（例）:
```markdown
# 現在のフェーズ: 2 (AI品質改善)

## 完了条件（実測・最終更新 2026-05-01）
- ❌ keyPoint 充填率 70% 超 (実測 8.7%)
- ❌ keyPoint 平均長 200〜300字 (実測 43.8字)
- ❌ confidence ラベル付与率 100% (実測 46%)
- ❌ storyPhase 発端 articleCount≥3 が 10% 未満 (実測 18.75%)

## 次に着手すべき Epic
E2-2: keyPoint / perspectives 充填率改善

## このフェーズで「やらない」
- フェーズ3: UX/成長系（current-phase.md が 3 になるまで凍結）
- フェーズ4: 収益化（同上）

## 完了したら
docs/phase-archive.md に追記して current-phase.md を 3 に書き換える
```

session_bootstrap.sh で**起動時に全文表示**。

#### 新設: `docs/phase-archive.md`
過去フェーズの完了履歴。読まなくていい参照型。

### Layer 3: 規則層（操作）

#### `CLAUDE.md` を 100行以内にリライト

含めるもの（物理ガード中心）:
1. 起動コマンド（session_bootstrap.sh）
2. 北極星と現フェーズへのリンク（強調）
3. **物理ルール表のみ**（Verified 行 / 250行制約 / タスクID重複 / WORKING.md 必須カラム / commit-msg hook / etc）
4. Dispatch / Code 役割分担（責務 1 行ずつ）
5. ファイル責務表（**ここに集約**。global-baseline §2 と重複している現状を解消）

外出しするもの:
- 思想ルール（→ `docs/rules/operational.md` 新設）
- セッション並走ルール詳細（→ 同上）
- スケジューラー運用詳細（→ `docs/rules/scheduled-task-protocol.md` に集約）
- モデル選択ルール（→ `docs/rules/operational.md`）

#### 新設: `docs/rules/operational.md`（運用判断・思想ルール集約）

統合元:
- `global-baseline.md` §1（思想ルール部分） / §6 / §7 / §8
- CLAUDE.md「中断ルール」「セッション並走ルール」「モデル選択ルール」「CI 待ちは即クローズ」「アドホックAPI禁止」
- `dispatch-reflection-2026-05-01.md` の禁止パターン

#### 既存維持（役割明確化のみ）
- `docs/rules/bug-prevention.md` — バグ再発防止表（修正前必読）
- `docs/rules/design-mistakes.md` — 設計ミスパターン表（修正前必読）
- `docs/rules/quality-process.md` — 品質改善5ステップ（修正前必読）
- `docs/rules/user-context-check.md` — 4つの問い（実装前必読）
- `docs/rules/legal-policy.md` — 法的・規約
- `docs/rules/data-quality-playbook.md` — データ品質改善（参照型）
- `docs/rules/scheduled-task-protocol.md` — schedule-task専用

#### 移動: `docs/rules/story-branching-policy.md` → `docs/p003/story-branching-policy.md`
これは P003 固有の実装方針。共通規則ではないので分離。

### Layer 4: 状態層（観測）— 現状維持

`docs/system-status.md` / `WORKING.md` / `TASKS.md` / `HISTORY.md` / `docs/lessons-learned.md` — 現状維持。

### `global-baseline.md` の扱い

「全プロダクト共通の絶対ルール」を名乗っているが、実体は P003 専用ルールが大半。

**提案**: 内容を分割
- 全プロダクト共通の物理ガード仕様 → `docs/rules/global-baseline.md` に残す（80行以内）
- P003 固有運用 → `docs/rules/operational.md`（新設）に統合
- §10 §11（スケジューラー義務）→ `docs/rules/scheduled-task-protocol.md` に統合

---

## 4. 物理ガード追加案（思想ルール → 物理化）

ユーザー指摘の5パターンに対し、追加すべき物理ガード（番号 = 優先順位）。

### A. 「タスク完遂局所最適化」を物理ブロックする（最優先）

**A-1: commit-msg hook に `Phase-Impact:` 必須行追加**
- `feat:` / `fix:` / `perf:` の commit に `Phase-Impact: <フェーズN> <完了条件への寄与>` を必須化
- 例: `Phase-Impact: 2 keyPoint 充填率を 8.7% → 15% に押し上げる proc_ai 改修`
- 書けない（=現フェーズ完了条件に紐付かない）feat/fix は reject
- 例外（`docs:` `chore:` `wip:` ）はスキップ

**A-2: TASKS.md に `<!-- フェーズN -->` HTML コメント必須化**
- pre-commit で TASKS.md を編集する commit にフェーズコメントが付いているか検査
- 既存ルール「現フェーズ優先」を物理化

**A-3: current-phase.md と TASKS.md の整合 CI**
- `<!-- フェーズN -->` で `N != current-phase.md の現在フェーズ` のタスクが TASKS.md 上位にある場合 CI WARN

### B. Dispatch運用を物理化

**B-1: コードセッション起動プロンプト テンプレ強制**
- `start_code_task` のラッパースクリプト（`scripts/dispatch_code.sh`）を新設
- 必須パラメータ: `--model haiku|sonnet|opus`（明示）/ `--phase N` / `--read-files <list>` / `--verify-target <url>`
- ラッパー経由でないコードセッション起動を Cowork ルールで禁止

**B-2: 実機確認の必須化**
- `done.sh` で `verify_target` 省略を exit 1 化（既に部分実装？要確認）
- `Verified:` 行に `verify_target` 必須化（commit-msg hook 拡張）

**B-3: 往復回数カウンタ**
- Dispatch セッションが round 数を `WORKING.md Dispatch継続性` に毎ターン追記
- session_bootstrap.sh が rounds ≥ 20 を WARN

**B-4: CI 失敗の自動気づき**
- session_bootstrap.sh が `gh run list --branch main --limit 5` で red を検出したら冒頭に ERROR 表示
- 既に運用ルールにあるが物理化されていない

### C. ファイル責務違反を物理化

**C-1: WORKING.md 書き忘れ検出**
- pre-commit hook で「コードファイル変更を含む commit 時に WORKING.md に自分のセッション ID が書かれているか」を検査
- 「物理ルール」と書いてあるが実装は思想だった構造を解消

**C-2: ファイル責務表の単一化**
- CLAUDE.md「規則の置き場所」表と global-baseline §2 を統合し、1 箇所のみに置く
- CI で「同じヘッダの表が複数ファイルにないか」検出

### D. 完了基準を強化

**D-1: `Verified-Effect:` 必須化（fix:/perf:のみ）**
- 効果検証コミットでは `Verified:` に加えて `Verified-Effect: <SLI名>:<改善前→改善後>` 必須
- band-aid を物理ブロック

**D-2: verify_effect.sh の fix_type プラガブル化**
- 現状 `ai_quality / mobile_layout / freshness / empty_topics` の 4 種のみ
- 新規 fix_type を追加できる仕組み（ディレクトリベース）にする
- 「対応する fix_type なし」を理由に効果検証スキップを禁止

**D-3: なぜなぜ未追記検出（横展開チェックリストとは別）**
- `fix:` commit で `docs/lessons-learned.md` への追記が無いものを WARN
- 軽度なバグでは適用除外できるよう `Skip-Lesson: <理由>` 行で明示的にスキップ

### F. 「勝手に変なやり方で無理くり作業する」を物理ブロック

> **PO観察**: 「Claude が勝手に変なやり方で無理くり作業時たりもする」
> AI の典型失敗: 制約に当たると「別の方法で動かしてしまう」「テストを緩めて通す」「想定外のファイルまで触って整合させる」「TODOを残したまま完了扱いにする」

**F-1: 実装方針の事前明示必須（最優先）**
- `feat:` / `fix:` / `perf:` の commit-msg hook に `Approach: <採用方針> | Why: <選択理由>` 必須化
- 例: `Approach: proc_ai.py の skip 条件緩和 (既存ロジック踏襲) | Why: 新ロジック追加は副作用範囲不明のため`
- 書けない（=方針未固化）コミットは reject。「無理くり」を commit 時点で言語化させる

**F-2: 変更範囲の自動検査**
- pre-commit hook で「コミット内のファイル変更数 > 10」または「期待外ディレクトリへの波及」で WARN
- タスク種別 × 期待ディレクトリのマッピングを `docs/rules/_meta.yaml` に保持（例: `task: ai-quality → expected: lambda/processor/, lambda/fetcher/`）
- 「ついでにこれも」を検出

**F-3: 「とりあえず動く」検出**
- 新規 feat/fix で `test_*.py` を 1 行も触っていない場合 WARN
- `assert False` / `pass # TODO` / `# FIXME` / `raise NotImplementedError` を新規追加するコミットは reject
- AI プロンプト変更（`*_prompt.py` / `*prompts*.py`）は手動 sample 出力（変更後の AI が実際に返した 1 件）を commit message に貼ることを必須化

**F-4: テスト緩和の検出**
- pre-commit hook で「テストファイル変更を含む commit が `assert` 行を削除している」場合 WARN + 削除理由を commit に要求
- 「テストを直して通した」と「テストを追加して通した」を区別

**F-5: 大規模変更の PO 承認タグ**
- 変更ファイル数 ≥ 10 または 変更行数 ≥ 500 の commit には `Plan-Approved-By: PO|<理由>` 必須
- PO 承認なしの大規模変更を物理ブロック（Plan-Approved-By 行がない大規模 PR は CI reject）

**F-6: ロールバック容易性の事前宣言**
- `feat:`/`fix:`/`perf:` の commit に `Rollback: <ロールバック手順1行>` 推奨化
- 例: `Rollback: revert <SHA>; redeploy lambda` / `Rollback: 該当 PR を git revert + S3 sync`
- 書けない（=戻せない）変更を事前検出

**F-7: 暫定対処（band-aid）の物理ブロック（ユーザー指摘・最重要）**

> **PO観察**: 「恒久対処じゃなくて暫定対処？これも書いてあるのになー」
> CLAUDE.md「対症療法ではなく根本原因」は思想ルールで、グリーンに通るので守られない。

- `fix:` / `perf:` の commit に `Fix-Type: permanent | bandaid` 必須化（commit-msg hook で reject）
- `bandaid` を選んだ場合、以下を**追加で**必須化:
  - `Bandaid-Reason: <理由>`（なぜ恒久対処を後回しにするか）
  - `Permanent-Followup: T2026-XXXX-<ID>`（恒久対処タスクの ID — 存在しない場合 reject）
  - `Bandaid-Expires: <YYYY-MM-DD>`（暫定対処の許容期限・3ヶ月以内）
- pre-commit hook が `bandaid` の commit を検出したら、TASKS.md に Followup タスク行を自動追記（重複ID なら追記スキップ）
- 月次の `scheduled-task` で「期限切れ bandaid」を検査し WARN（`p003-haiku` の朝確認に追加）
- SLI: `bandaid_count / fix_count` 比率を観測（30% を超えたら警告）

→ これにより「暫定対処を選ぶこと自体は禁止しないが、選ぶたびに必ず恒久対処タスクが TASKS.md に積まれ、期限切れで督促される」構造になる。書きっぱなしを物理排除。

→ F-1 が最も即効性。F-7 が最も「書いてあるのに守られない」問題への直接対策。

### G. エラー黙殺・回避ルートの物理ブロック（ユーザー指摘・最重要）

> **PO観察**: 「エラー吐いてるのに無視する、気づいてはいるけど、放置もしくは違う道で対応、というのもかなり多い」
>
> 失敗の典型パターン: CI 赤を無視してマージ・pre-commit WARN を握りつぶす・テストを `skip` で逃げる・`try/except: pass` で例外を黙殺・CloudWatch ログを見ない・ブラウザコンソールエラーを放置・指摘された時だけ対応する。

**G-1: CI 赤の自動 push reject**
- pre-push hook で「直近の CI run が green でない場合 push を reject」（強制 push 時のみ `--no-verify` で escape 可能・ただし commit message に `CI-Bypass-Reason: <理由>` 必須）
- ローカルで CI を確認しないまま赤の上に積む文化を物理ブロック

**G-2: pre-commit WARN を reject 化**
- 現状 WARN は素通り。これを `--allow-warn` フラグなしでは reject に変更
- WARN を通すには明示フラグ必須・通したコミットは `Allowed-Warn: <ID>:<理由>` を commit-msg に必須化
- 「気づいてたけど通した」を後追いできる構造にする

**G-3: skip / xfail / TODO の数を SLI 化**
- `pytest.mark.skip` / `@unittest.skip` / `xfail` / `# TODO` / `# FIXME` の総数を月次で grep カウント
- 増加方向（`Δ ≥ 5 / month`）で WARN・「逃げの蓄積」を観測
- 削減方向は歓迎

**G-4: catch-and-ignore の物理検出（最優先）**
- CI で以下を grep して reject:
  - `except:\s*pass` / `except Exception:\s*pass`
  - `except\s+\w+\s*:\s*pass`
  - `} catch \(.*\) {\s*}` (JS / TS の空 catch)
- `bug-prevention.md` の既存ルール「エラー無視には理由の明文化必須」を物理化
- 例外を握りつぶす場合は必ず `except <Specific>: log.warning(...) + 復旧コード` を要求

**G-5: CloudWatch エラー観測の自動化（既存拡張）**
- `p003-haiku`（毎朝）の処理に「直近24時間 ERROR ログ件数を WORKING.md に出力」を追加（既存運用の物理化）
- 件数の SLI 化（SLI 12: `cw_error_count_24h`）・閾値超過で TASKS 自動追記
- 閾値（提案）: 0 が望ましい・5以上で WARN・20以上で `p003-sonnet` 自動起動

**G-6: ブラウザコンソールエラーの観測（新設）**
- 本番 `flotopic.com` を Puppeteer / Playwright で週次スキャン（scheduled-task `p003-frontend-check`）
- 観測: `console.error` / Network 4xx-5xx / JS exception
- SLI 13: `frontend_console_error_count_weekly`（閾値: 0）
- 既存の「ブラウザ実機確認必須」を物理化

**G-7: 「違う道で対応」の検出**
- F-1（`Approach:` 必須）と組み合わせ:「TASKS.md に書いた解決方針」と「PR commit の `Approach:`」が異なる場合に `Approach-Changed: <理由>` 必須化
- 検出: pre-commit hook が TASKS.md のタスク本文と commit の Approach 行を diff
- 「気づいたら違う方法で逃げた」を物理可視化

**G-8: 失敗の自動エスカレーション**
- CI 失敗・hook reject・SLI 閾値割れが3回連続発生したら、`p003-sonnet` が自動起動して「根本原因分析タスク」を TASKS.md に積む（既存の T2026-0429-D「繰り返し失敗自動検出」を Lv2 化）
- 「無視 / 回避」を選択した場合に必ず追跡される構造

→ G-4 が最も即効性（grep1本で実装可能）。G-1, G-2 は「赤を通さない」の物理化。G-7 は「違う道で対応」の構造的検出。

### H. 「実装→評価→次の改善」ループの物理化（ユーザー指摘・最重要）

> **PO観察**: 「実装して評価して次の改善に進むのも口だけでやってない」
>
> AI の典型失敗: 実装はする・「評価します」と言う・しかし時間が経つと忘れる/別タスクに進む・SLI を見ない・効果が出てなくても気づかない・改善ループが「実装→終わり」で止まる。

**H-1: 実装 PR に「評価予定日」必須化（最優先）**
- `feat:` / `fix:` / `perf:` の commit-msg hook で `Eval-Due: <YYYY-MM-DD>` 必須化
- 最大3週間後まで・空欄やはるか先（>3w）は reject
- PR merge トリガーで `scheduled-task` を自動登録（fireAt = Eval-Due 09:00 JST）
- **「評価しない実装」を物理排除**

**H-2: 評価結果の自動起票（自走 Lv1→Lv2 の核）**
- `Eval-Due` 当日の scheduled-task が以下を自動実行:
  1. 該当 PR の `Verified-Effect:` 行から SLI 名を取得・本番から再測定
  2. 結果を `lessons-learned.md` に「YYYY-MM-DD eval: PR#NN <SLI>: 改善前X → 改善後Y」として追記
  3. 改善観測 → `Eval-Result: improved` + TASKS.md に「次の改善候補」を Phase-Impact 付きで自動起票
  4. 改善なし → `Eval-Result: flat | regressed` + TASKS.md に「ロールバック検討」または「追加施策」を自動起票
  5. 結果サマリを `system-status.md` の「Eval Trail」セクションに 1 行追記
- 既存の `verify_effect.sh` を `eval_pr.sh` として汎用化・拡張

**H-3: 「次の改善」未起票の検出**
- `Eval-Due` 通過から7日以内に「該当 PR の Phase-Impact に紐付く次タスク」が TASKS.md に積まれていない場合 WARN
- ループ停止のシグナル化

**H-4: 評価サイクル SLI 化**
- SLI 14: `eval_completion_rate` = 実評価完了 PR / 総 Eval-Due 経過 PR（閾値: 90%）
- SLI 15: `improvement_chain_continuity` = 「改善 PR → 次改善 PR」の連鎖が継続している件数 / month
- 両指標を `freshness-check.yml` に追加・閾値割れで Slack 通知

**H-5: 「口だけタスク」検出**
- TASKS.md の各タスク行が「最終 commit 言及から N日経過」しているかを scheduled-task が監視
- 7日経過＋commit 0件のタスクは行末に `Stalled-7d: <理由>` を必須化（PO レビュー時に判断）
- 14日経過なら自動 WARN・21日経過なら自動「Re-evaluate」コメント追加（人間 or AI が判断）

**H-6: 「次の改善に進む」 を物理化**
- `Eval-Result: improved` の場合、scheduled-task が「次の改善候補」を以下のロジックで生成:
  1. 同じ Phase-Impact の SLI でまだ未達の項目を抽出
  2. 過去 lessons-learned から類似改善パターンを検索
  3. 候補を Phase-Impact 付きで TASKS.md に追記
- これにより「実装→評価→次施策の起票」が人手なしに連鎖（自走 Lv2 の中核機能）

→ **H-1 と H-2 がリライト案全体で最も「自走」に直結するペア**。これがあれば「実装したら勝手に評価ジョブが走り、勝手に次の改善が起票される」状態になる。Layer α（品質ループ）が Lv2 化する瞬間。

### I. 「そもそも見ない・気づかない」の物理化（ユーザー指摘・最重要）

> **PO観察**: 「そもそも気づかないか、見てないというのもある」
>
> G（気づいて無視・回避）よりさらに上流の問題。CI を開かない・CloudWatch を見ない・本番ブラウザを開かない・関連ファイルを Read しない・自分の変更が他に与える影響を認識しない・TASKS.md / lessons-learned.md を読み流す。**「見てさえいれば気づくのに、見ていない」のが大半**。

**I-1: 起動時の「見るべき要約」を自動表示（最優先・実装容易）**

`session_bootstrap.sh` を拡張し、起動時に以下を**無視できない位置に強制表示**:

```
🔴 注意: 以下の項目を必ず確認してください
─────────────────────────────────
• CloudWatch ERROR (24h):  N 件 [pX-processor / fX-fetcher]
• 直近 CI 失敗 PR:          #NN, #MM (赤のまま)
• SLI 閾値割れ:             keyPoint 充填率 8.7% (目標 70%)
• 期限切れ bandaid:         T2026-XXXX-A (Bandaid-Expires: 2026-04-01 経過)
• Stalled タスク (>7d):     T2026-XXXX-B (commit 0 件 / 9日経過)
• Eval-Due 経過 (>3d):      PR #NN (評価未実施)
─────────────────────────────────
```

→ 起動するだけで「見るべき景色」が視界に入る。「見てない」を構造的に防ぐ。

**I-2: コミット種別×必読ファイル の citation 必須化**
- `_meta.yaml` に「タスク種別 → 必読ファイル」を定義
- 例:
  ```yaml
  - task_kind: bug-fix
    must_read: [bug-prevention.md, design-mistakes.md]
  - task_kind: ai-quality
    must_read: [ai-fields-catalog.md, north-star.md#情報の地図]
  - task_kind: dispatch-change
    must_read: [operational.md#dispatch, lessons-learned.md#dispatch-mass-violations]
  ```
- commit-msg hook で `Refs: <id>, <id>, ...` を必須化・列挙が空または該当ID不在は reject
- 「読まずに通す」を物理ブロック

**I-3: PR テンプレに「観測項目」物理組込**

`.github/PULL_REQUEST_TEMPLATE.md` に必須チェックリスト:

```markdown
## 実装前に見たもの（必須・チェックなしで merge 不可）
- [ ] CloudWatch エラーログ確認（直近24時間）— 件数: N件
- [ ] 本番ブラウザで実機確認 — 確認URL: https://...
- [ ] 関連 lessons-learned 参照 — ID列挙: <ID1>, <ID2>
- [ ] 影響を受ける SLI 列挙 — SLI名: <NN>, <MM>
- [ ] 変更ファイルが import / 参照されている他ファイル — `grep -r` 結果貼付
```

CI でテンプレ未記入を検出（チェックボックスが未チェック・URLが空・ID未列挙）。

**I-4: 「ブラインドスポット」を物理可視化**
- `session_bootstrap.sh` が以下も追加表示:
  - 最近30日参照されていないルール ID（`_meta.yaml` の `current_violations_30d=0` かつ `current_refs_30d=0`）
  - 最近7日 Read されていない重要ファイル（TASKS.md / system-status.md / lessons-learned.md の最終 Read 時刻）
  - 最後に push されてから24時間以上の `[Code]` 行（stale 候補）
- 「視界に入っていなかったもの」を機械的に列挙

**I-5: 副作用への気づきを強制（pre-commit hook）**
- 変更ファイルが import されている他ファイルを grep → commit message に `Affects: <file1>, <file2>, ...` 必須
- 検出例:
  ```
  ⚠️ あなたが変更した proc_ai.py は以下から import されています:
      - lambda/processor/handler.py
      - lambda/fetcher/handler.py
      - tests/test_proc_ai.py
  これらの動作確認を済ませましたか? (Affects: 行を必須化)
  ```
- 「気づかなかった」を物理排除

**I-6: 巡回担当 scheduler の新設**
- `p003-sentinel`（毎時 or 30分間隔・低コスト Haiku）を新設:
  - health.json の鮮度確認
  - Lambda エラーログ新規発生検出
  - SLI 急変検出
  - 4xx/5xx 急増検出
- 検出したら `Action-Required: T2026-XXXX` を TASKS.md に自動追記
- 既存の `p003-haiku`（朝1回）では拾えない時間粒度の異常を捕捉

**I-7: 「読んだ証拠」のログ化**
- 重要ファイル（CLAUDE.md / north-star.md / current-phase.md / lessons-learned.md / system-status.md）の Read を session-level でログ
- セッション終了時に「今日 Read していない必読ファイル」が3件以上あれば WARN
- AI が「読んだフリ」をする構造を物理排除

→ **I-1 が最も即効性**（session_bootstrap.sh 拡張のみ）。**I-3 が最も「気づき」を強制**（PR テンプレ＝マージ前の最終ゲート）。**I-5 が「副作用への気づき」の核心**。

### J. 「気づくための仕組みを作らない」の物理化（メタ違反対策）

> **PO観察**: 「気づくための仕組みを作らないと言うのもある」
>
> I（見ない・気づかない）の上流。**「気づきたいのに気づけない場面に遭遇しても、気づき装置を新規実装する責務を果たしていない」** というメタ違反。これが累積すると「観測の死角」がどんどん広がる。

**典型例**:
- Lambda エラーが見えづらかった → SLI を増やさず放置
- 「あのとき早く気づけば」と振り返って気づくも、検出 hook を作らない
- ルール違反を発見しても CI チェックに落とさない
- 「次回も同じ事故が起きたら気づけない」状態のまま完了

**J-1: lessons-learned 末尾に「気づき装置の有無」必須化**
- なぜなぜ分析（Why1〜Why5）で「事故が起きるまで気づけなかった」と書いた場合、**仕組み的対策のうち最低 1 件は「気づき装置の追加」を含める**ことを必須化
- 例: 「CloudWatch ERROR の SLI を新設」「pre-commit に grep 追加」「scheduled-task で巡回」
- なぜなぜに「気づきが遅れた」と書いていながら気づき装置を追加していない lessons commit は CI reject

**J-2: 「観測欠損」を SLI 化**
- SLI 16: `observation_gap_count` = 「直近30日に発生した incident のうち、検出 hook / SLI で事前検出できなかったもの」の件数
- 月次で集計・閾値（提案: 1件以下）超過で `Ops Claude` が「気づき装置追加タスク」を TASKS に積む

**J-3: 月次「気づき装置レビュー」**
- `p003-ops`（月初）が以下を実行:
  1. 直近30日の lessons-learned から「気づきが遅れた」事例を抽出
  2. それぞれに対応する CI / hook / SLI / scheduled-task が landing しているか確認
  3. 未 landing なら TASKS.md に「気づき装置追加」タスクを起票
- これは 13.4 四半期メタ振り返りの月次版・観測の死角拡大を物理ブロック

**J-4: Phase-Impact に「気づき装置の追加件数」を含める**
- Ops Claude / SRE Claude の改善 PR は `Phase-Impact: <N> 観測欠損 -1件 (新設SLI: <name>)` のように、気づき装置追加そのものを成果として認める
- 「コードを増やす」だけでなく「観測を増やす」も改善として評価する文化の物理化

**J-5: 「予防的観測」を起動時に促す**
- `session_bootstrap.sh` の I-1 表示に追加:
  ```
  💡 予防観測候補: 過去30日に観測されなかった項目
     • <SLI名>: 過去観測 0 件（新設または閾値再設定検討）
     • <ファイル名>: 直近 N 日 編集なし（健全 or 死蔵か要判断）
  ```
- 「観測されない＝動いていない」のか「観測されない＝検出装置がない」のかを毎セッション意識させる

→ J は **「気づき装置を作る」こと自体を仕事として認識・評価・物理化**する。Ops Claude（Section 14）の主たる責務に組み込む。

**J-6: 既存パターンの再利用ファースト（PO 指摘・2026-05-02）**

> **PO観察**: tmp_obj_* 蓄積問題の発見時、「連続2h0件残存検知ってやつ？」と既存 `.github/workflows/fetcher-health-check.yml` パターンの再利用を即提案。
>
> **教訓**: 新たな「気づき装置」を作るときは、**まず既存の同型パターンを探す**。ゼロから作るのは最後の手段。

- 新規 SLI / アラート / 監視 hook を作る前に必ず以下を grep:
  - `.github/workflows/*health-check*.yml` `*-check*.yml` `*-audit*.yml`
  - `scripts/setup_*_alarm.sh` `scripts/*_audit.sh`
  - `docs/sli-slo.md` の既存 SLI 一覧
- 「連続 N 時間 0 件」「閾値割れ」「累積監視」「鮮度検知」等のパターンは既存実装を再利用する
- 再利用した実装の commit message には `Pattern-Reuse: <既存パターン名>:<既存ファイル>` を任意で付与（Ops Claude の「再利用率」を観測可能に）

→ 既存パターン再利用は (a) コスト最小 (b) 学習済み挙動の継承 (c) ルール体系の一貫性 ─ の 3 重に有効。「ゼロから書きたがる」AI の癖の物理対策。

**J-6 の即応用例: tmp_obj_* 蓄積 SLI**
- 既存 `fetcher-health-check.yml` のテンプレを流用
- SLI 22: `git_tmp_obj_count` を session_bootstrap で観測 → CloudWatch カスタムメトリクスに put
- `git-health-check.yml`（新設）が過去 2 時間の最大値を観測し、増加が止まらない（=減らない）場合 Slack 警告
- 1〜2 時間の実装工数（既存テンプレ流用のため）

### K. 物理ガードの「抜け道」「放置」を物理ブロック・自動マージ強制（ユーザー指摘・最重要）

> **PO観察**: 「CIでブロックされて物理ガードが効いてるのに、なぜか抜け道でやろうとしたり、そもそもほったらかしたり。自動マージしろって言ってるのに」
>
> 物理ガードを設置しても、(a) `--no-verify` / `--force` で迂回・(b) PR を放置して時間切れ狙い・(c) auto-merge 条件を揃えずに人間判断を待つ、というメタメタ違反が発生する。これを潰す。

**K-1: 抜け道使用の物理検出（最優先）**
- 以下のオペレーションは pre-push hook で検出 + commit message に `Bypass-Reason: <理由>` 必須:
  - `git push --force` / `--force-with-lease`
  - `git commit --no-verify`
  - `git commit --amend` for already-pushed commits
  - GitHub Actions の `if: always()` で skip させた job の通過
- `Bypass-Reason` 空 = reject。記入があっても月次 SLI で `bypass_count` を集計
- 「黙ってこっそり迂回」を物理可視化

**K-2: 自動マージ強制（PO 要望「自動マージしろ」の物理化）**
- 以下が**全て**揃った PR は **24時間以内に問答無用で自動マージ**する設定:
  - CI 全 green
  - `Phase-Impact:` / `Approach:` / `Verified:` / `Eval-Due:` 必須行が揃っている
  - 必須レビュアー（人間 or QA Claude）の approve があるか、QA Claude が「auto-approvable」を宣言
- branch protection の `required_pull_request_reviews` を「QA Claude approve = 1」で運用
- 24時間経過で自動マージされなかった PR は WARN・48時間経過で SRE Claude が緊急タスク化
- **人間の判断を待たない**仕組みが「自動マージしろ」の物理化

**K-3: PR 放置の自動エスカレーション**
- 開いている PR の進捗を毎日チェック:
  - 7日経過 + commit/review 0件 → WARN + `Stalled-PR: <理由>` コメント必須化
  - 14日経過 → 自動的に `[STALLED]` ラベル付与・SRE Claude が触る
  - 21日経過 → 自動 close + TASKS.md に「再起動 or 廃案」タスク起票
- 「腐らせる」を物理排除

**K-4: branch protection 設定と自動マージ運用の整合 CI**
- `gh api repos/.../branches/main/protection` の設定と `_meta.yaml` の運用方針が一致しているかを CI で突合
- 不一致なら WARN（例: 自動マージ運用なのに `required_approving_review_count=2` のまま等）
- 「設定が運用を阻む」状態を物理検出

**K-5: 抜け道提案の文書禁止**
- `operational.md` に明記: 「Claude が `--no-verify` / `--force` / テスト緩和 / `try/except: pass` を提案すること自体がルール違反」
- これらを提案した commit / PR コメントを `check_bypass_proposal.sh` で grep 検出 → reject
- 「AI が自ら抜け道を提案する」癖を物理禁止

**K-6: CI 失敗の自動リトライ + 自動ロールバック**
- CI が flaky で失敗した場合、SRE Claude が自動リトライ（最大3回）
- 3 回連続で同じパターンの失敗なら**自動ロールバック PR を起票**（merge は人間判断）
- 「失敗したまま放置」「失敗の上に積む」を物理ブロック

**K-7: 「自動マージできない理由」の毎日棚卸し**
- 開いている PR ごとに「auto-merge できていない理由」を `gh pr list --json` で毎日抽出
- 例: `Phase-Impact 行欠落 / CI red / Eval-Due 未設定 / レビュー未承認`
- SRE Claude が WORKING.md に毎朝列挙 → 「揃えれば merge できる PR」を可視化
- 「条件を揃えていないから merge できていない」を毎日見える化

→ **K-2 が PO 要望「自動マージしろ」への直接対応**。条件揃ったら問答無用で merge する設定変更 + 必須行揃えを Eng/QA Claude の責務にする。
→ **K-1 が「抜け道」の物理可視化**。
→ **K-3 が「放置」の物理排除**。

### L. PO 依頼の整合性チェック（PM Claude の責務・思いつき即実装の物理ブロック）

> **PO観察**: 「タスクの優先度や案件の進捗管理はそっちでやって欲しいのに、思いつきで言ってる俺の相談や、闇夜依頼を何も考えずに実現しようとする。整合性をとって考えてから動いて欲しい」
>
> 失敗パターン: PO が雑談で「〜してほしい」と言うと、Claude が即座に Eng Claude を起動して実装に走る。北極星 / 現フェーズ / 他タスクとの整合性チェックなし。結果として「依頼1つ実装したら別の何かが壊れた」「現フェーズ完了条件と関係ない実装が混入」が起きる。

**L-1: 新規依頼は必ず PM Claude が一次受け（最優先）**
- PO の自由記述依頼を受けたセッションは、**まず PM Claude として動作**することを起動プロンプトで強制
- PM Claude は以下のチェックレポートを WORKING.md に出すまで実装着手禁止:
  ```
  Phase-Alignment: <現フェーズ> ← どう紐付くか（紐付かないなら "out-of-phase"）
  Priority-Justification: <他の最優先タスク N 件と比較した位置>
  Conflict-Check: <既存 WORKING.md / 進行中 PR との競合有無>
  Decision: proceed | hold | reject | escalate-to-CEO
  Estimated-Cost: <推定工数 + 推定 API コスト>
  ```
- `Decision: proceed` 以外は実装着手しない・PO に逆質問する

**L-2: 「思いつき即実装」の物理ブロック**
- PO の発言から30分以内に `dispatch_eng.sh` 起動が発生する場合、L-1 のチェックレポート未記載なら起動 reject
- 「闇夜依頼」を即実装するパスを物理ブロック

**L-3: 整合性チェックの自動逆質問テンプレ**
- PM Claude は以下のいずれかが PO 依頼に明示されていない場合、**自動で逆質問**を生成して PO に返す:
  - この依頼の現フェーズ完了条件への寄与
  - 他の最優先タスクとの優先度比較理由
  - 完了の定義と評価方法
  - コスト見積もり（API / 工数）
- 揃うまで着手しない・「揃った状態」を WORKING.md に記録

**L-4: 「out-of-phase」依頼の保留制度**
- 現フェーズ完了条件に紐付かない依頼は **TASKS.md の `[Out-of-Phase]` セクション**に積む（着手しない）
- 月次で PO レビュー → 必要なら次フェーズに昇格 / 不要なら廃案
- 「やりたい気持ちはあるが今やらない」を構造化

**L-5: 進捗管理の自走化**
- PM Claude（週次）が以下を自動実行:
  - 現フェーズ完了条件の進捗％を `system-status.md` に書き込む
  - 「今週やるべき最優先 3 件」を WORKING.md に提示
  - PO 介入が必要な判断（コスト・方針）を抽出して別ファイルに集約
- PO が「今何やってる？」と聞かなくても進捗が見える状態

→ **L-1 が PO 要望「整合性をとって考えてから動いて」の直接対応**。PM Claude を物理的に間に挟む。

### M. 個人情報・シークレット・コスト事故の物理ブロック（過去事故対策）

> **PO観察**: 「git に俺の個人情報入れたり、勝手にキャッシュ消費したこともあった」
>
> 既存 CLAUDE.md「PII / secrets コード直書き禁止」は Anthropic API key / AWS Access Key の grep のみで不十分。実際に PII 漏洩・コスト暴走が起きている。

**M-1: PII 検出 grep の拡張（最優先・即実装可）**
- pre-commit hook の grep パターンを以下まで拡張:
  ```regex
  # 既存
  <ANTHROPIC_KEY_PREFIX>[a-zA-Z0-9_-]{20,}     # Anthropic API key
  <AWS_ACCESS_KEY_PREFIX>[0-9A-Z]{16}          # AWS Access Key
  # 追加
  [a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}    # Email
  \b\d{3,4}-\d{4}-\d{4}\b                            # 電話番号
  ghp_[a-zA-Z0-9]{36}|gho_[a-zA-Z0-9]{36}            # GitHub PAT
  -----BEGIN [A-Z ]*PRIVATE KEY-----                 # 秘密鍵
  \b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b         # クレカ番号パターン
  ```
- PO 個人特定情報（GitHub username / 個人メール / 本名等）は `_meta.yaml` の `pii_patterns` に列挙し grep に取り込む
- マッチした場合 reject + Slack 通知（即気づく）

**M-2: 既存コミット履歴の PII スキャン定期化**
- 月次 scheduled-task で `git log --all --diff-filter=A -p` を全 PII パターンで grep
- 検出されたら緊急タスク起票 + `BFG Repo-Cleaner` 実行手順を runbook で提示
- 「過去にコミットされた PII」を物理的に検出する仕組み

**M-3: コスト Impact 行の必須化**
- AWS API / Anthropic API / OpenAI API / その他課金 API を含む変更を検出（grep `boto3.` / `anthropic.` / `openai.` / `requests.post.*api`）
- 該当コミットには `Cost-Impact: <推定 USD/月> | <unknown - PO 確認待ち>` 必須
- `unknown` の場合は TASKS.md に「コスト試算」タスクを自動起票
- 「勝手にキャッシュ消費」を commit 段階で物理可視化

**M-4: AI API コール件数 guard の必須化**
- 全 AI API 呼び出しコードに `MAX_API_CALLS_PER_RUN` 定数を必須化
- CI で「`MAX_API_CALLS` 未設定の新規 AI API 呼び出し」を grep reject
- 既存 wallclock guard（CLAUDE.md「Lambda 主ループ wallclock guard」）と並行して件数 guard を物理化

**M-5: Cowork / Dispatch セッション内の本番 API 呼び出し禁止**
- 既存ルール「アドホック API 呼び出し禁止」を物理化
- `dispatch_<role>.sh` のラッパーで `curl https://flotopic.com/api/...` / Lambda invoke を grep し proxy 経由でのみ許可
- 直接の本番 API コールを物理 reject

**M-6: コスト SLI 化**
- SLI 17: `daily_api_cost_usd` = AWS / Anthropic 等の API コスト合計（CloudWatch / Anthropic Dashboard 経由）
- 閾値（提案）: 前月平均比 +30% で WARN・+100% で `p003-sentinel` 緊急タスク起票
- 「気づいたらコストが膨らんでいた」を物理検出

→ **M-1 と M-3 が即効性最高**。M-1 は grep 拡張1本・M-3 は commit-msg hook 拡張1本で実装可。「PII 漏洩」と「コスト暴走」は不可逆事故なので最優先で物理化。

### M-強化版（PO 指摘・2026-05-02 追記「セキュリティ監査が弱い」）

> **PO観察**: 「セキュリティ監査の部分が弱いかも、構成しかり俺の個人情報しかり」
>
> M-1〜M-6 では「git 混入の検出」中心で、構成（インフラ・設定）の常時監査・PO個人情報の特殊扱いが手薄。

**M-7: PO 個人情報の特化保護（最優先）**
- `_meta.yaml` に `pii_personal:` セクションを新設し、PO の以下を機械可読に保持:
  - GitHub username（PO 指定のもの。具体値は `_meta.yaml` 内のみで保持し、本ドキュメントには書かない）
  - 個人メール（同上・本ドキュメントには具体値を書かない）
  - 本名・nickname（PO が指定したもの）
  - 居住地・電話・SNS ハンドル等（PO が必要と判断したもの）
- これらを以下で常時 grep:
  - pre-commit hook（コミット前検出）
  - 月次の `git log --all -p` 全履歴スキャン
  - **CloudWatch Logs / S3 / DynamoDB** のサンプリング検査（外部にも漏れていないか）
- 検出されたら緊急タスク + 「BFG Repo-Cleaner / S3 オブジェクト即削除 / DynamoDB UpdateItem」runbook を即発動
- 既存履歴に既に混入している場合は最優先で除去 PR を起票

**M-8: コミット前 PII セルフチェックの強制**
- pre-commit hook で「ユーザー名 / メール / IP アドレス / hostname / ローカルパス（`/Users/<name>/`）」を grep
- マッチしたらコミット前に確認プロンプトを表示（hook 内で `read` 必要だが GitHub Actions では reject）
- 「うっかり」を物理ブロック

**M-9: secrets manager 鮮度監査**
- AWS Secrets Manager 内のシークレット最終ローテーション日を月次で取得
- N日（提案: 90日）以上回っていないシークレットを WARN
- 古いシークレットの放置を物理可視化

**M-10: ローカル開発環境の PII 流出防止**
- `.env` `.envrc` `local.env` 等を `.gitignore` で必ず除外（CI で確認）
- `~/.aws/credentials` `~/.config/gh/hosts.yml` 等を grep 検出（ローカルパスがログに混入していないか）

---

## 4-P. インフラ・構成のセキュリティ監査（新設・PO指摘対応）

> **PO観察**: 「セキュリティ監査の部分が弱いかも、構成しかり…」
>
> Section 4 M は「コードに混入した PII / シークレット」中心。本セクションは「**インフラ構成と設定**」のセキュリティ監査を扱う。**SRE Claude / Ops Claude の主要責務**として組み込む。

**P-1: AWS IAM ポリシーの最小権限監査（最優先）**
- 月次 scheduled-task で `aws iam list-policies` + `simulate-principal-policy` を実行
- 検出対象:
  - `Action: "*"` または `Resource: "*"` を含むポリシー
  - 過去90日 `LastUsed` が無い権限（不要権限）
  - Lambda 実行ロールの過剰権限
- WARN 件数を SLI 化（SLI 20: `iam_overpriv_count`）

**P-2: branch protection 設定の常時監査**
- `gh api repos/.../branches/main/protection` を月次取得
- 期待設定（`_meta.yaml` の `branch_protection_expected:`）と diff
- 不一致なら緊急タスク（K-4 と統合）
- 過去事例: 「自動マージ運用なのに required_review=2 のまま」を物理検出

**P-3: GitHub repo 設定の監査**
- `private` / `public` の設定確認・意図と一致するか
- secrets / variables の最終更新日確認
- collaborators / outside collaborators の権限監査
- 月次レポートを `Ops Claude` が起票

**P-4: CloudFront / S3 公開範囲の監査**
- S3 bucket policy の `Principal: "*"` 検出
- CloudFront origin の `Origin Access Identity` / `Origin Access Control` 設定
- 想定外公開が無いか月次 SLI（SLI 21: `s3_public_object_count`）

**P-5: WAF / レート制限の有効性確認**
- WAF rule のヒット率を CloudWatch から取得
- ヒット 0 件が3ヶ月続く rule は「効いていない or 攻撃が来ていない」のサイン
- レート制限の閾値妥当性レビュー（月次）

**P-6: secrets / API token のスコープ最小化**
- GitHub PAT / OAuth トークンのスコープを `_meta.yaml` で記録
- 過剰スコープ（`repo` 全権 vs 必要最小限）を WARN
- ローテーション計画の有無を確認

**P-7: ログの PII 流出監査**
- CloudWatch Logs / Lambda print 出力に PO 個人情報や PII が出ていないかサンプリング検査
- M-7 と連動し、検出されたら CloudWatch Logs の該当行を削除（log group の retention 短縮 + 該当 stream 削除）

**P-8: 依存ライブラリの脆弱性監査**
- `npm audit` / `pip-audit` / `Dependabot` を月次・自動実行
- High / Critical 脆弱性は緊急タスク
- 既存 CI に組み込まれているか確認・無ければ追加

**P-9: 不要リソースの棚卸し**
- 使われていない Lambda 関数・古い CloudFormation スタック・アタッチされていない EBS / EIP を月次検出
- コスト + セキュリティ面のリスク（古いコードが脆弱性を抱えたまま放置）

**P-10: 監査ログの保全**
- CloudTrail が全リージョンで有効か
- ログ保管期間（提案: 1年以上）
- 改ざん検知（log file integrity validation）

**P-11: バックアップ・リカバリーの監査**
- DynamoDB PITR（35日）有効化確認
- S3 バージョニング・MFA Delete 設定
- 月次でリストア手順を runbook 通り実行できるか dry-run（数回に1回）

**P-12: セキュリティインシデント runbook の鮮度**
- インシデント発生時の対応 runbook（`docs/runbooks/security-incident.md` 新設）の最終更新日を SLI 化
- 6ヶ月更新なし = WARN（陳腐化サイン）

→ **P-1, P-2, P-7 が最優先**。月次 scheduled-task `p003-security-audit`（新設・Ops Claude 担当）として実装し、結果を `system-status.md` に追記する。

### 4-P 実装ステップ（Section 11/16 の最短ルート追加分）

| Day | 作業 | 該当違反# | 担当 |
|---|---|---|---|
| 0.5 | M-7 PO 個人情報パターンを `_meta.yaml` 化 + grep CI 拡張 | #25 | Eng Claude |
| 0.5 | P-2 branch protection 設定 diff CI | #21 #22 | Eng Claude |
| 0.5 | P-1 IAM 過剰権限の月次監査 scheduled-task | 新設 | SRE/Ops |
| 0.5 | P-7 ログ PII サンプリング検査 | #25 | SRE Claude |
| 0.5 | M-9 + P-3 + P-4 月次監査タスク統合 | 新設 | Ops Claude |

合計 2.5 日追加で Section 4 P が立ち上がる。Section 16 の最短ルート 8.5 日 + 2.5 日 = **11 日**で「PO 個人情報保護 + 構成監査 + 規則体系再編 + Layer 1/2/3」が物理化完了。

→ **「セキュリティ監査が弱い」を構造的に解消**。月次 `p003-security-audit` がループとして回る限り、放置されない。

### N. リーガル・規約事項の物理化（既存 legal-policy.md が守られない問題）

> **PO観察**: 「リーガル、規約も何度言っても気にしなかったりする」
>
> 既存 `docs/rules/legal-policy.md` は存在するが、CLAUDE.md からの「必要に応じて参照」止まりで起動時必読ではない。Claude は「コードが動けば良い」モードで外部データソースを追加し、robots.txt も読まず・引用要件も無視・規約確認も省略する。

**N-1: 外部データソース変更の検出 + citation 必須（最優先）**
- 新規ドメイン文字列（`https?://[^/\s"]+/`）が**コード差分に追加**された PR を pre-commit hook で検出
- 該当 PR には以下を必須化:
  ```
  Legal-Reviewed: docs/rules/legal-policy.md#<section>
  Robots-Checked: <ドメイン>:<status>:<JST_timestamp>
  Terms-Checked: <利用規約 URL>:<確認内容1行>
  ```
- 空欄 reject。PO 介入なしに新規外部ソースを追加できなくする

**N-2: robots.txt 自動確認の物理化**
- fetcher が新規ドメインを叩く前に `/robots.txt` を fetch + Disallow パスを評価する関数の存在を CI で必須化（grep `def check_robots` or 同等）
- なければ reject。既存 fetcher 実装の有無確認・なければ実装必須タスク化

**N-3: 引用要件の schema 物理化**
- 記事保存スキーマに以下のフィールドを必須化（schema validation で reject）:
  - `source_name`: 出典名（必須・空 reject）
  - `source_url`: 元記事 URL（必須・http/https 検証）
  - `quote_text`: 引用テキスト（あれば原文ママ・改変なし）
  - `quote_byte_ratio`: 自前コンテンツに対する引用比率（< 30% 等の閾値）
- legal-policy.md「主従関係」を schema で物理担保

**N-4: AI パラフレーズの物理禁止検出**
- legal-policy.md「AIパラフレーズ禁止（言い換え禁止）」を grep で物理化
- AI 関数の引数に `quote_text` / `excerpt` / `original_text` 系のフィールドを渡しているコードを検出 → reject
- 「AI で言い換えた引用」の混入を物理ブロック

**N-5: 一次情報バッジ判定の改変への厳格化**
- `is_primary_source(url)` / `PRIMARY_SOURCE_DOMAINS` の変更を含む PR には `Legal-Reviewed:` 必須
- 既存テスト `test_primary_source.py` の網羅性を CI で確認（新規ドメイン追加時にテスト未追加なら reject）

**N-6: 起動時必読への昇格 + コミット種別との紐付け**
- `_meta.yaml` の `task_kind: legal-policy` に該当する PR（`fetcher/` `proc_*` などのドメイン関連）には legal-policy.md を `Refs:` 必須化（I-2 と統合）
- session_bootstrap.sh が「外部データソース変更を含む PR 進行中」を検出したら起動時に legal-policy.md を強制表示

**N-7: 法的事故の SLI 化**
- SLI 18: `legal_review_skipped_count_30d` = legal-policy citation 欠落で reject された PR / 月
- SLI 19: `robots_violation_count` = robots.txt 違反検出件数 / 月
- 増加方向で WARN

→ **N-1 が即効性最高**。grep 1本 + commit-msg hook 拡張で実装可能。「外部データソース追加」という具体行動を引き金に法務確認を物理化する。

### O. 「保守性犠牲の局所追加」「動かすためだけのパラメータ」を物理ブロック

> **PO観察**: 「保守性の高い安定な構築にしろって言ってるのに、そのまま局所最適で追加だけやって壊したり」「動かすためだけに勝手にパラメータ要らないのに」
>
> F の派生だが独立した違反パターン。失敗例:
> - 既存関数に「オプション引数」を増やして「とりあえず動かす」
> - 既存ロジックに `if x: ... else: 新挙動` を継ぎ足して分岐を増やす
> - リファクタを避けて「ついで追加」で複雑度を上げる
> - フォールバック / デフォルト値 / try-except でエラーを握りつぶして「動いた」とする

**O-1: 既存関数シグネチャ変更の理由必須化（最優先）**
- pre-commit hook で「既存関数に新規引数追加（既存呼び出しを壊さない optional 追加含む）」を検出
- 該当コミットには以下を必須化:
  ```
  Param-Justification: <なぜこの引数が必要か>
  Alternatives-Considered: <別関数化 / オーバーロード / config 化 等の代替検討>
  Caller-Updated: <すべての呼び出し元を更新したか・テストしたか>
  ```
- 空欄 reject。「とりあえず引数追加」を物理可視化

**O-2: optional パラメータの増加を SLI 化**
- 各 module の総 optional パラメータ数（`def foo(a, b=None)` の `=None` をカウント）を月次 grep
- 増加方向で WARN・**「保守性デフレ」を観測**
- 削減方向は歓迎（リファクタの兆候）

**O-3: 安易なフォールバック検出**
- `try: ... except: return None | return [] | return {}` を grep reject
- `if not x: x = default_value` の挿入を WARN（理由必須化）
- bug-prevention.md「フォールバック禁止」を物理化

**O-4: 行数増加と機能追加の比率観測**
- PR 単位で「追加行数 / Phase-Impact 行で宣言した機能数」を計算
- 機能あたり > 200 行の PR を WARN（「動かすためだけ」の付随コードが混入の可能性）

**O-5: ホットスポット検出 → リファクタ義務化**
- `git log --since="30 days ago" --name-only` で「直近30日に5回以上変更されたファイル」を抽出
- 該当ファイルを次に変更する PR には `Refactor-Considered: <検討結果>` 必須
- 「ホットスポットなのにリファクタしない」状態を可視化

**O-6: 循環的複雑度の SLI 化**
- 関数単位の cyclomatic complexity を CI で計算（`radon` 等）
- 1関数あたり閾値（提案: 10）を超える新規追加を WARN
- 既存関数の複雑度を上げる変更も WARN（「分岐ついで追加」の物理検出）

**O-7: テストカバレッジが下がる PR の reject**
- 変更ファイルのテストカバレッジが PR 前より下がる場合 reject
- 「動かすためだけに追加してテストなし」を物理ブロック

**O-8: 設計判断の事前明示**
- F-1 `Approach:` の拡張：大規模変更（Plan-Approved-By 必須レベル）の `Approach:` には以下を含める:
  - 既存設計との整合性（"既存設計踏襲" / "設計変更" / "設計見直し提案"）
  - 影響範囲（変更ファイル予定 + 影響を受ける機能）
  - 保守性への影響（"中立" / "向上" / "悪化-理由"）
- 「保守性悪化」と書ける覚悟がある変更だけ通す

→ **O-1 が PO 要望「動かすためだけにパラメータ要らない」への直接対応**。  
→ **O-3 / O-5 / O-6 が「保守性犠牲の局所追加」の物理ブロック**。

### E. 規則棚卸しの自動化

**E-1: 月次ルール棚卸しタスク**
- scheduled-task で月初に「過去30日に追加したルール × 効果が観測されたか」を検査
- 効果なしルールは削除候補として TASKS.md に積む
- 棚卸し対象: CLAUDE.md / global-baseline.md / docs/rules/* の差分

**E-2: 思想ルール総量制限**
- CLAUDE.md と global-baseline.md の「強度: 思想」表行を CI で数える
- 合計 N 行 (例: 10) を超えたら WARN
- 思想で増やすなら同数の思想を削除 or 物理化が必要

---

## 5. 廃止 / 統合提案

| 対象 | 提案 | 理由 |
|---|---|---|
| `docs/flotopic-vision-roadmap.md` | **削除 → north-star.md と phase-archive.md に分配** | 2026-04-27 で更新停止。フェーズ1〜4のリストは project-phases.md と二重 |
| `docs/product-direction.md` | **north-star.md に長期ビジョン部分を移し、本体は廃止** | 「現在のプロダクト方針」と project-phases.md「現在地」が二重 |
| `docs/rules/global-baseline.md` | **80行以内に縮小 → 共通物理仕様のみ** | 188行のうち P003 固有が多い |
| CLAUDE.md「Cowork ↔ Code 連携ルール」表 | global-baseline §「Code/Dispatch役割」と統合し1箇所に | 重複 |
| CLAUDE.md「Dispatch絶対禁止パターン」表 | docs/rules/operational.md へ移動・物理化対象を CLAUDE.md に残す | 6項目中5項目が思想で守られない |
| `docs/dispatch-reflection-2026-05-01.md` | **lessons-learned.md に追記 → 削除** | 単発反省は lessons-learned のフォーマットで残す |

---

## 6. 段階的移行プラン

POが承認したら順に着手。各ステップは 1 PR 単位・ロールバック可能。

| Step | 内容 | リスク | 効果 |
|---|---|---|---|
| 1 | `docs/north-star.md` 新設 + product-thinking.md / vision-roadmap / direction の long-vision を統合 | 低 | Claude が起動時に思想を読む |
| 2 | `docs/current-phase.md` 新設 + project-phases.md から抽出 | 低 | 現フェーズが 1 ファイルに | 
| 3 | session_bootstrap.sh が north-star.md + current-phase.md を全文表示するよう改修 | 中（既存表示が変わる） | 起動時必読が物理保証 |
| 4 | `docs/rules/operational.md` 新設 + 思想ルール集約 | 低 | CLAUDE.md が痩せる |
| 5 | CLAUDE.md を 100行以内にリライト | 中（規則本体の変更） | 物理ルール集中で違反検出力 UP |
| 6 | commit-msg hook に `Phase-Impact:` 必須化 (A-1) | 中（既存PR運用に影響） | **タスク完遂局所最適化を物理ブロック** |
| 7 | `dispatch_code.sh` ラッパー新設 + 既存 start_code_task をラップ (B-1) | 中 | プロンプトテンプレ強制 |
| 8 | WORKING.md 書き忘れ pre-commit hook (C-1) | 低 | 並行編集事故防止 |
| 9 | Verified-Effect: 必須化 (D-1) + fix_type プラガブル化 (D-2) | 中 | band-aid 物理ブロック |
| 10 | 月次ルール棚卸しタスク (E-1) | 低 | 規則の自然減 |
| 11 | flotopic-vision-roadmap.md / product-direction.md 廃止統合 | 低 | drift 排除 |
| 12 | story-branching-policy.md 移動 (rules → p003) | 低 | 共通/固有の分離 |

**Step 1〜3 だけで「ブレない」効果は大幅改善**。残りは継続的に着手。

---

## 7. このリライト案自体の自己レビュー

5 違反パターンが追加物理ガードでカバーされるか：

| パターン | カバーする物理ガード | カバー後の強度 |
|---|---|---|
| ① Dispatch運用崩壊 | B-1〜B-4 | 思想5件 → 物理4件 + 観測1件 |
| ② 完了基準甘さ | D-1〜D-3 | Verified-Effect 必須 + 棚卸しで思想ルール削減 |
| ③ ファイル取り違え | C-1, C-2 | 「物理と書いて思想」状態を解消 |
| ④ 方針逸脱（局所最適化） | **A-1〜A-3 + Layer 1, 2 起動時必読** | **思想 → 物理（Phase-Impact 必須）** |
| ⑤ 修正の雑さ | D-3 + 既存横展開チェックリスト | 既存物理ガード + Verified-Effect 連動 |

CLAUDE.md 250行制約：リライト後 100 行目標 → 余裕 150 行。安全。

---

## 8. POが「これだけは即やってほしい」を選ぶなら

以下 3 つだけで 80% の効果：

1. **Step 1〜3**: north-star.md / current-phase.md 新設 + 起動時表示
   → 「ブレない」の最低限。1日で実装可
2. **A-1**: commit-msg hook に `Phase-Impact:` 必須化
   → タスク完遂局所最適化の物理ブロック。半日で実装可
3. **B-2**: done.sh で verify_target 省略を exit 1
   → 実機確認なし完了報告の根絶。1時間で実装可

3 つすべて低リスク・小PR・即効性あり。

---

## 9. セッション継続性 — 指示駆動プロンプトジェネレータ（追補・2026-05-01 PO要望）

> **PO要望**: 「セッション切れた時に、その前提から全て消え去るのが辛い。俺からの指示出しでプロンプトを作ってできないか？」
>
> **問題の本質**: 北極星 / 現フェーズ / WORKING / TASKS / SLI スナップショット / 関連 lessons を毎回手で集めるのは現実的でない。Layer 1〜2 を起動時必読にしても、それは「セッション内の前提」であって「人と AI の会話の連続性」ではない。

### 現状の継続性インフラ（既存）

- `scripts/gen_dispatch_prompt.sh` → 静的テンプレに WORKING / TASKS の状態を埋め込んでクリップボードへ
- `WORKING.md Dispatch継続性` セクション → 前セッションの状態を引き継ぐ
- `system-status.md` Dispatch 引き継ぎメモ → 機械的記録
- 既存セッションの `dispatch-session-start.md` テンプレ

→ **限界**: 静的テンプレでは「PO の高レベル指示」を取り込めない。指示と状態を縫い合わせる仕組みがない。

### 提案: `scripts/dispatch_from_directive.sh`（Component A）

**入力**: 1〜3 行の高レベル指示文（例: 「keyPoint 充填率を 30% まで引き上げる施策を主体的に実装してフェーズ2を進める」）

**処理パイプライン**:
1. `docs/north-star.md` 全文取得（不変層）
2. `docs/current-phase.md` 全文取得（フェーズ層）
3. `WORKING.md` の `Dispatch継続性` セクション + アクティブ行
4. `TASKS.md` から現フェーズ + unblocked 上位 5 件
5. `docs/system-status.md` の SLI スナップショット（直近24時間分）
6. `docs/lessons-learned.md` から指示文の keyword で関連教訓を grep（直近30日）
7. CLAUDE.md「絶対ルール表」を物理ルールのみ抽出
8. これらを 1 つの self-contained プロンプトに織り込む
9. `pbcopy` でクリップボードへ（または `--stdout` で確認）

**出力プロンプトの骨格**:
```
P003 Dispatch (auto-generated YYYY-MM-DD HH:MM JST)

## 北極星（不変）
<north-star.md 全文>

## 現在のフェーズ（変動）
<current-phase.md 全文>

## 最新状態スナップショット
WORKING.md アクティブ: ...
TASKS.md 現フェーズ最優先 (5件): ...
SLI 直近: keyPoint=X% / perspectives=Y% / coverage=Z%

## 関連する直近の学び
- YYYY-MM-DD: <lesson 概要>
- ...

## 物理ルール（絶対遵守）
<CLAUDE.md 物理ルール表>

## POからの指示
<入力テキスト>

## 制約（このセッションで守る）
- フェーズN タスクのみ着手（Phase-Impact: N 必須）
- 同時コードセッション 1 件・Verified-Effect 必須
- 効果検証はスケジューラー委譲・実機確認必須
```

### 効果

| 改善項目 | 改善 |
|---|---|
| 起動コスト | 「5ファイル読む」→「1プロンプト読む」 |
| 前提消失 | PO が「同じ指示を再投入」で同じ前提が再構築される |
| ブレ防止 | 北極星 + 現フェーズ + 物理ルールが指示と同梱される |
| 並走防止 | WORKING.md の現状が必ず指示に同梱される |

### 既存スクリプトとの関係

`gen_dispatch_prompt.sh` は静的テンプレ。`dispatch_from_directive.sh` は動的合成。両立可能。`gen_dispatch_prompt.sh` は「定例起動」用に残し、`dispatch_from_directive.sh` を「PO 指示入り起動」用に追加する。

---

## 10. 主体的改善 × 自走（追補・2026-05-01 PO要望）

> **PO要望**: 「ルールを前提に P003 を主体的に改善させて、プロダクトをビジネスとして成立させ、自走して欲しい」
>
> **自走 = 人が指示を出さなくても、北極星 + 現フェーズ + ルール を前提に Claude が「観測 → 改善 → 効果検証 → 学び保存 → 次施策」のループを回し続ける状態**。試走（trial run）ではなく、self-driving。

### 現状の自走インフラ（既存）

- `p003-haiku`（毎朝7時・CloudWatch / 未マージPR / TASKS.md 三点確認）
- `p003-sonnet`（手動起動・SLI 実測 / 根本原因分析 / コードセッション起動判断）
- `scripts/quality_heal.py`（品質劣化レコードの再処理キュー投入）
- `freshness-check.yml`（SLI 1〜11 の外部観測）
- `docs/rules/scheduled-task-protocol.md`（探索 → 実装 → 報告の3フェーズ）

→ **限界**: 「課題発見」と「軽い実装」までは自走するが、(a) 改善 PR の自動マージ経路がない、(b) 効果検証 → 自動ロールバックがない、(c) 体験指標 / 収益指標が観測ループに含まれない。

### 自走の段階定義（PO と合意したい）

| Lv | 状態 | PO 介入頻度 | 観測対象 |
|---|---|---|---|
| **Lv0 半手動** | スケジュールタスクは存在するが、PO が手動起動 + 結果確認 | 毎日 | 充填率手動確認 |
| **Lv1 観測自走** | 観測（SLI実測・課題発見・TASKS起票）が無人化 | 週1（方針承認） | freshness-check 全SLI + TASKS自動増減 |
| **Lv2 改善自走** | 改善 PR の起票・実装・CI通過・効果検証・自動ロールバックが無人化 | 月1（北極星更新） | PR throughput + Verified-Effect 達成率 |
| **Lv3 ビジネス自走** | 体験指標（滞在時間等）+ 収益指標（CPM/CV）も自走ループに含む | フェーズ宣言時のみ | 滞在時間 / AdSense 推定収益 |
| **Lv4 完全自走** | 北極星に紐付くなら新機能の発案・優先順位決定も自走 | 北極星更新時のみ | 全レイヤー |

→ **現状は Lv0〜Lv1 の境界**。
→ **目標は Lv2 化を最短で達成、その後 Lv3 を狙う**。Lv4 は北極星の質と LLM のコスト次第で再評価。

### Lv 別 自走ループの構造

**Layer α: 品質ループ（Lv1 → Lv2 化対象）**
- 観測: keyPoint / perspectives / outlook 充填率・storyPhase 偏り・cluster 健全性
- 担当: `p003-haiku`（毎朝・観測）/ `p003-sonnet`（週次・改善PR起票）
- Lv2 化に必要: PR 自動マージ経路（branch protection 緩和 or auto-merge の限定許可）

**Layer β: 体験ループ（Lv3 立ち上げ時）**
- 観測: ページ滞在時間 / 直帰率 / 再訪率 / 1セッション内ページ数
- 計測: GA4 + CloudWatch RUM（要確認・既存があれば再利用）
- 担当: 新スケジュールタスク `p003-ux`（週次）

**Layer γ: 収益ループ（Lv3 立ち上げ時）**
- 観測: AdSense 推定収益 / 忍者 AdMax CPM / アフィリエイト CV / ページあたり推定収益
- 計測: AdSense / AdMax 管理画面 API + CloudWatch
- 担当: 新スケジュールタスク `p003-revenue`（週次）

### 自走を回すための物理ガード（Lv 上昇に必要なもの）

| Lv 上昇 | 必要な物理ガード |
|---|---|
| Lv0 → Lv1 | (a) スケジュールタスクの起動プロンプトに `north-star.md` 全文同梱（Component A 流用） / (b) 課題自動起票 — `p003-sonnet` が SLI 閾値割れを TASKS.md に Phase-Impact 付きで自動追記 |
| Lv1 → Lv2 | (a) `Phase-Impact:` 必須化（A-1） / (b) `Verified-Effect:` 必須化（D-1） / (c) 効果なし PR の自動ロールバック PR 起票 / (d) auto-merge 限定許可（条件: CI 全 green + Verified-Effect 達成 + Phase-Impact が現フェーズ完了条件に直接寄与） |
| Lv2 → Lv3 | (a) GA4 / RUM の SLI 化 / (b) AdSense API 連携 / (c) 体験ループ・収益ループのスケジュールタスク新設 |
| Lv3 → Lv4 | (a) 北極星駆動の優先順位アルゴリズム / (b) 新機能発案の LLM 駆動（要 PO 承認フロー設計） |

### 北極星 と 自走 の関係

自走しても北極星に紐付かない実装が増えると、それは「ブレ」になる。Lv2 以降で北極星照合を物理化:

- 自走タスクの起動プロンプトに `north-star.md` 全文同梱（必須）
- `Phase-Impact:` 行は北極星のどの要素に寄与するかを明示（例: `Phase-Impact: 2 keyPoint充填率 ⇒ 北極星「情報の地図の品質」`）
- 月次レビューで「北極星の各要素に紐付かない自走 PR」を抽出し、ブレ検出

→ **自走が暴走しない仕組み = 北極星の物理的同梱 + Phase-Impact 必須 + 月次レビューの3点**。これがリライト案の Layer 1 〜 Layer 3 + commit-msg hook の構造で実現される。

### 注意: フェーズ表記の食い違い解消

`product-direction.md` の「実装フェーズ」表（Ph1〜5）と `project-phases.md` の「フェーズ1〜3」と `flotopic-vision-roadmap.md` の「フェーズ1〜4」が食い違う。**north-star.md 統合時に「品質 → 地図 → 収益 → SNS化」の4段階に統一**し、「自走 Lv」とは独立した軸として整理する。

---

## 11. 拡張後の着手順（Section 6 移行プランの上書き）

| Step | 内容 | 種別 | 想定工数 |
|---|---|---|---|
| 1 | `docs/north-star.md` 新設（vision + product-thinking + direction の long-vision を統合） | Cowork | 0.5日 |
| 2 | `docs/current-phase.md` 新設（project-phases.md から抽出） | Cowork | 0.5日 |
| 3 | `session_bootstrap.sh` 改修（north-star + current-phase 全文表示） | Code (Sonnet) | 0.5日 |
| 4 | `docs/rules/operational.md` 新設（思想ルール集約） | Cowork | 0.5日 |
| 5 | CLAUDE.md を 100行以内にリライト | Cowork | 0.5日 |
| 6 | `scripts/dispatch_from_directive.sh` 新設（Component A） | Code (Sonnet) | 1日 |
| 7 | commit-msg hook に `Phase-Impact:` 必須化（A-1） | Code (Sonnet) | 0.5日 |
| 8 | `done.sh` で verify_target 省略を exit 1（B-2） | Code (Haiku) | 0.5日 |
| 9 | WORKING.md 書き忘れ pre-commit hook（C-1） | Code (Sonnet) | 0.5日 |
| 10 | `Verified-Effect:` 必須化 + fix_type プラガブル化（D-1, D-2） | Code (Sonnet) | 1日 |
| 11 | スケジュールタスクに north-star 同梱（Layer α 強化） | Cowork | 0.5日 |
| 12 | `p003-ux` スケジュールタスク設計（Layer β 立ち上げ準備） | Cowork | 0.5日 |
| 13 | 月次ルール棚卸しタスク（E-1） | Code (Haiku) | 0.5日 |
| 14 | 古い方針ドキュメント廃止統合（vision-roadmap / direction） | Cowork | 0.5日 |

合計約8日。Step 1〜5 で「ブレない構造」が完成、Step 6〜10 で「物理ガード強化」が完成、Step 11〜14 で「自走ループ強化」が完成。

**最短ルート（POが「これだけ即」を選ぶなら）**:
- Step 1〜3（北極星 + 現フェーズ + 起動時必読）= 1.5日 → 「ブレない」最低限
- Step 6（指示駆動プロンプト）= +1日 → セッション切れ問題の解決
- Step 7（Phase-Impact 必須）= +0.5日 → 局所最適化の物理ブロック
- F-1 + F-7（Approach: + Fix-Type: 必須化）= +0.5日 → 「無理くり」「暫定対処」の物理ブロック

合計4日で 90% の効果。残りは継続的に着手。

---

## 12. ルール拡張性 — これからもルールは増える前提（追補・2026-05-01 PO要望）

> **PO要望**: 「これからもルールは増えていくと思う。細かいね。そういう運用面の拡張性も考慮して欲しい」
> **AI観察**: 「細かいところまで言わないとサボる」 → ルールは具体的でないと守られない

### 12.1 ルール追加の構造化 — `_meta.yaml` 集中管理

新ルール追加時に必ず付与する**必須メタデータ**を `docs/rules/_meta.yaml` に1ファイル集約。

```yaml
- id: dispatch-no-concurrent-sessions
  added: 2026-04-28
  source: lessons-learned#dispatch-mass-violations  # incident ID 必須
  category: dispatch                                 # 分類タグ
  strength: physical                                 # physical | observation | thought
  body_file: docs/rules/operational.md#concurrent    # 規則本文の場所
  detection: scripts/session_bootstrap.sh exit 1 on [Code]>=2  # 検出方法
  effect_sli: WORKING.md [Code] 行件数（hourly）       # 効果指標
  expires: never                                     # 自動降格期限
  current_violations_30d: 1                          # 月次更新（過去30日違反数）

- id: fix-type-required
  added: 2026-05-01
  source: rewrite-proposal-2026-05-01#F-7
  category: completion-quality
  strength: physical
  body_file: CLAUDE.md#commit-msg-hooks
  detection: commit-msg hook reject pattern
  effect_sli: bandaid_count / fix_count (monthly)
  expires: never
  current_violations_30d: 0
```

**メリット**:
- ルールが100件・1000件に増えても、ID と category で整理可能
- 「強度」「効果指標」「検出方法」が必須なので、思想ルールの濫造を防ぐ
- 月次で `current_violations_30d` を機械更新 → 形骸化ルール（直近違反0件・参照0件）を自動検出

**CI ガード**:
- `_meta.yaml` のスキーマバリデーション（`detection` 空欄を reject など）
- 「規則本文が `body_file` に存在するか」を物理検査（`check_meta_landings.sh` 新設）

### 12.2 ルールのライフサイクル（自動降格・昇格）

| 遷移 | 条件 | アクション |
|---|---|---|
| **思想 → 削除候補** | 追加から3ヶ月、`current_violations_30d` ずっと 0、文書参照 0 | TASKS.md に削除PR起票（`p003-sonnet` 月次） |
| **思想 → 物理化候補** | 同じ incident が再発（lessons-learned 参照カウント≥2） | TASKS.md に物理化PR起票（実装案テンプレ付き） |
| **物理 → 観測降格** | hook が3ヶ月一度も発火していない（`current_violations_30d=0` 継続） | reject → WARN に切り替え（守られすぎ＝形骸化、もしくは状況変化のサイン） |
| **観測 → 削除** | `effect_sli` の値が3ヶ月平坦・改善なし | TASKS.md に削除PR起票 |

実装: `scripts/rule_lifecycle.py` 新設。`p003-sonnet` が月初に手動起動、結果を TASKS.md に積む。

### 12.3 ルール記述の粒度テンプレ（細かさの担保）

PO観察「細かいとこまで言わないとサボる」を踏まえ、`_meta.yaml` の `body_file` 先のルール本文は**必ず以下のテンプレ**で書く:

```
## <ルール名>

**Action（何をする/しない）**: <1〜2行で具体的な動作>
**Detection（どう検出）**: <CI スクリプトパス / hook名 / SLI名>
**Violation（違反時の挙動）**: <reject / WARN / TASKS自動追記>
**Why**: <根拠となる incident や仕組み>
**Example**:
  ✅ Good: <具体例1行>
  ❌ Bad:  <具体例1行>
```

抽象な「気を付ける」「意識する」は `check_soft_language.sh`（既存）で検出済。これに加え、**Action / Detection / Violation の3行が揃っていない規則は CI reject** する `check_rule_template.sh` を新設。

### 12.4 ファイル構造の拡張規律

| ファイル | 追加条件 | 上限 |
|---|---|---|
| `_meta.yaml` | 全ルール（行数無制限・機械処理） | — |
| `bug-prevention.md` | 物理ガード追加時のみ表に1行 | 100行（超えたらカテゴリ分割） |
| `design-mistakes.md` | 設計ミス事例追加時のみ表に1行 | 100行 |
| `operational.md`（新設） | 思想ルール追加時 | 200行（超えたら `_meta.yaml` で降格候補検査） |
| CLAUDE.md | 物理ルール変更時のみ | 100行（リライト後の上限） |

**新ルールは「既存ファイル + `_meta.yaml`」が原則**。新ファイル作成は category が既存に収まらないときのみ（PO 承認必要）。

### 12.5 ルールの「忘却」を物理担保

ルールが増えると Claude は読まなくなる。対策:

- 起動時必読は **north-star.md + current-phase.md の2ファイル全文**に絞る（Layer 1, 2）
- それ以外のルールは「タスク種別 × 必読ルール」を `_meta.yaml` で機械的にひも付け、**コミット種別を判定して該当ルールだけを commit-msg hook が citation 要求**
- 例: AI プロンプト変更コミットには「`Refs: bug-prevention#prompt-fallback, design-mistakes#new-field-distribution`」必須
- citation がないコミットは reject

→ ルール参照を Claude の毎コミットの「動作」に組み込む。読まずに通すことを物理ブロック。

---

## 13. 「書いてあるのに守られない」構造への正面攻撃（追補・2026-05-01 PO要望）

> **PO観察**: 「恒久対処じゃなくて暫定対処？これも書いてあるのになー」
>
> 「書いてある」≠「守られる」。両者の間にある構造的ギャップを正面から扱う。

### 13.1 なぜ書いてあるのに守られないか（構造的原因）

| 原因 | 例 | 対策方向 |
|---|---|---|
| **A. 起動時に読まれない** | `product-thinking.md`（最新思想）が誰からも参照されていない | Layer 1 起動時必読化（既出） |
| **B. 思想ルール（強度△）でCI に通る** | 「対症療法ではなく根本原因」は文章のみ・hook なし | 物理化（Section 4 全体・F-7） |
| **C. 抽象すぎてアクションに落ちない** | 「気を付ける」「意識する」 | テンプレ強制（12.3） |
| **D. 違反してもコストが0** | ルール違反コミットがマージされても罰則なし | violation count を SLI 化（12.1） |
| **E. 過去の incident と紐付かない** | 「なぜこのルールがあるか」の出自不明 | source 必須化（12.1） |
| **F. ルールが多すぎて読み切れない** | CLAUDE.md 224行 + global-baseline 188行 + rules/ 10ファイル | 起動時必読の絞り込み（Layer 1, 2）+ 棚卸し（12.2） |

### 13.2 「守られた」を観測する SLI

ルールごとに以下を観測（`_meta.yaml` の `current_violations_30d` 横展開）:

| SLI | 単位 | 閾値（提案） |
|---|---|---|
| ルール違反数（過去30日） | 件 / month | 0 が望ましい・1以上で WARN |
| ルール citation 数（過去30日） | 件 / month | 0 が3ヶ月続いたら形骸化候補 |
| 暫定対処率 | bandaid_fix / total_fix | 30% 超で警告 |
| Bandaid 期限切れ件数 | 件 | 0 が望ましい・1以上で TASKS 自動追記 |

これらを `freshness-check.yml` の SLI 12〜15 として追加。閾値割れは Slack 通知（既存通知パイプライン流用）。

### 13.3 「ルールが効いている」の証拠を強制する

新ルール追加 PR には**必ず**以下を含める（PR テンプレで物理化）:

```markdown
## ルール追加チェックリスト
- [ ] `_meta.yaml` に entry 追加（id / source / strength / detection / effect_sli 必須）
- [ ] 強度=思想 の場合、3ヶ月以内の物理化計画を本文に記載
- [ ] 該当する `docs/rules/*.md` 本文を 12.3 テンプレで記述
- [ ] 効果検出 SLI を 30 日後に再評価する scheduled-task を登録
- [ ] 既存の類似ルールと重複していないか `_meta.yaml` を grep で確認
```

`.github/PULL_REQUEST_TEMPLATE.md` に追加。新ルール追加 PR で1項目でも未達ならマージ不可。

### 13.4 「書いてあるのに守られない」を学習サイクルに組み込む

四半期に1回、以下を実施（`p003-sonnet` 手動起動 + PO レビュー）:

1. `_meta.yaml` の `current_violations_30d` 上位 10 ルールを抽出（=守られていない順）
2. それぞれについて「物理化できるか」「降格 / 削除すべきか」を判定
3. 物理化 PR・降格 PR・削除 PR を起票して TASKS.md に積む
4. 結果を `lessons-learned.md` に「ルール体系メタ振り返り」として記録

→ 「守られないルールが残り続ける」現状を物理的に解消する四半期サイクル。

### 13.5 究極の物理ガード — 「ルール記述の構造化」を強制する

ルール本文が**機械可読**（`_meta.yaml` + テンプレ準拠）であれば、Claude（や CI）が以下を自動実行できる:

- コミット種別 → 必読ルール一覧 を自動表示
- ルール本文の Action 部だけを抜粋して prompt に埋め込み
- 違反検出ロジックの自動生成（`detection` フィールドから hook スケルトン生成）

**長期目標**: ルールを「文章」から「データ」に近づける。文章で読み流せる規則は守られない。データで参照を強制される規則は守られる。

→ Layer 1 北極星は文章（人間の判断軸）、Layer 3 規則は限りなくデータ寄りに。これが拡張性 × 遵守率の両立解。

---

## 14. 「プログラマー Claude」から「組織として動く Claude」へ（追補・2026-05-01 PO要望）

> **PO観察**: 「俺が言ってることは人間でいう組織の開発フローそのままだと思う。でも君らプログラマーとしてしか動いてくれない」
>
> これがリライト案全体を貫く**最上位視点**。Section 1-13 は「プログラマー Claude が守るべきルールの物理化」を扱ってきた。Section 14 は「Claude を組織の複数役割に分けて連携させる」フレームを定義する。

### 14.1 現状の限界 — 役割の空白地帯

人間の組織には CEO / PM / プロデューサー / QA / SRE / エンジニア / オペレーション / デザイナー / マーケター が居る。それぞれが別の視点・別の判断軸・別の責任範囲を持つ。

現状の Claude が担っているのは:
- ✅ **エンジニア（実装）**: コードセッション
- 🔶 **ディスパッチャー（タスク仕分け）**: Cowork Dispatch
- 🔶 **観測担当（部分的）**: `p003-haiku` の朝確認

空白:
- ❌ **CEO**: 北極星の更新・フェーズ宣言・予算判断は PO 都度
- ❌ **PM**: 優先順位・Epic 紐付け・Phase-Impact 整理
- ❌ **QA**: リリース前 SLI チェック・実機確認・回帰検出
- ❌ **SRE**: 毎時の本番監視・即時異常検出（朝1回では遅い）
- ❌ **Ops**: ルール棚卸し・lessons-learned 整理・横展開
- ❌ **Designer**: UX レビュー・user-context-check 実施
- ❌ **Marketer**: 収益指標観測・収益化施策起票

→ **空白が多すぎるから、PO が「ルールに書いてあるのに守られない」「ループが口だけ」と感じる**。守らせる主体（PM / QA / SRE / Ops）が居ない。

### 14.2 役割分担モデル

| 役割 | 主たる責任 | 起動 | 主な出力 | 既存基盤 |
|---|---|---|---|---|
| **CEO Claude** | 北極星 / フェーズ宣言 / 予算判断 | 月1（PO 同席・手動） | north-star.md 更新・フェーズ移行 PR | 新設 |
| **PM Claude** | TASKS 優先順位・Phase-Impact 紐付け・Epic 管理・週次計画 | 週1（自動 `p003-pm`） | TASKS.md 整理・Epic 更新・H-6 次施策起票 | `p003-sonnet` を拡張 |
| **QA Claude** | PR レビュー・SLI 確認・実機確認・回帰検出 | PR merge 前（自動・PR ラベルトリガー） | レビューコメント・blocking 判定 | GitHub Actions 拡張 |
| **SRE Claude** | 本番監視・即時異常検出・緊急ロールバック判断 | 毎時 or 30分（自動 `p003-sentinel`） | TASKS 緊急追記・Slack 通知・I-1 表示生成 | 新設（I-6） |
| **Eng Claude** | 実装・PR 作成・テスト追加 | 都度（Dispatch 起動 `dispatch_eng.sh`） | コード PR | 既存コードセッション |
| **Ops Claude** | ルール棚卸し・`_meta.yaml` 更新・lessons 整理 | 月1（自動 `p003-ops`） | ルール降格/物理化 PR・lessons 整理 | 12.2 + 13.4 を実装 |
| **Designer Claude** | UX レビュー・user-context-check 実施 | PR 単位（フロント変更時のみ） | UX レビューコメント・改修提案 | user-context-check.md を hook 化 |
| **Marketer Claude** | 収益指標観測・収益化施策起票（Lv3 以降） | 週1（自動 `p003-revenue`） | Layer γ タスク起票 | 自走 Lv3 立ち上げ時 |

各役割は**それぞれ別のプロンプトテンプレ**で起動する。共通土台は「北極星 + 現フェーズ + Section 1-13 の物理ガード」。

### 14.3 役割の物理化 — `dispatch_<role>.sh`

Section 9 の `dispatch_from_directive.sh` を発展させ、役割別ラッパーを作る:

```
scripts/dispatch_ceo.sh        # 北極星見直し用
scripts/dispatch_pm.sh         # 週次計画用
scripts/dispatch_qa.sh         # PR レビュー用
scripts/dispatch_sre.sh        # 緊急対応用
scripts/dispatch_eng.sh        # 実装用（既存 dispatch_code.sh と統合）
scripts/dispatch_ops.sh        # 棚卸し用
scripts/dispatch_designer.sh   # UX レビュー用
scripts/dispatch_marketer.sh   # 収益化用
```

各スクリプトは:
1. 北極星 + 現フェーズ全文を埋め込む
2. その役割の **読むべきファイル**と**読むべきでないファイル**を明示
3. その役割の **判断軸**（PM なら優先順位、QA なら品質、SRE なら安定）を明示
4. その役割の **出力先**（TASKS / lessons / PR コメント等）を制約
5. 「役割を超えた行動」を禁止（QA がコードを書いてはいけない・SRE が新機能を提案してはいけない）

→ 役割が混ざると判断軸がブレる。役割を物理的に分けることで判断軸が安定する。

### 14.4 役割同士の連携フロー

```
CEO Claude (月1)
   ↓ 北極星更新
PM Claude (週1)
   ↓ Phase-Impact 紐付け・優先順位 → TASKS.md
Eng Claude (都度)
   ↓ 実装 PR + Eval-Due 設定 (H-1)
QA Claude (PR毎)
   ↓ レビュー・SLI 確認・実機確認 → 承認 or blocking
   ↓ merge
SRE Claude (毎時)
   ↓ デプロイ後監視・異常検出 → 緊急 TASKS or 通常運用
   ↓ 観測ログ
PM Claude (週1)
   ↓ Eval-Due 経過 PR の評価結果 (H-2) から次施策を起票
   ↑ ループ
Ops Claude (月1)
   ↓ ルール棚卸し・lessons 整理 → CEO Claude にレポート
   ↑ 北極星更新の材料
```

これが**組織としての自走ループ**。PO の介入ポイントは CEO Claude セッション（月1）+ 重大判断（不可逆操作 / 新規 AWS 課金）のみ。

### 14.5 段階的に役割を立ち上げる

| Step | 役割 | 既存からの移行 | 工数 | 効果 |
|---|---|---|---|---|
| 1 | **SRE Claude** | `p003-haiku` を拡張 + I-1 表示 + G-5 CW 監視 + I-6 sentinel | 1日 | 「気づかない」を物理排除 |
| 2 | **PM Claude** | `p003-sonnet` を拡張 + H-2 評価自動起票 + H-6 次施策生成 + Phase-Impact 整理 | 1.5日 | 「ループが口だけ」を物理化 |
| 3 | **QA Claude** | GitHub Actions PR チェック拡張 + I-3 PR テンプレ + 実機確認自動化 | 1日 | 「無理くり PR」を物理ブロック |
| 4 | **Eng Claude** | 既存コードセッションを `dispatch_eng.sh` 経由化（B-1） | 0.5日 | 起動プロンプトの一貫性 |
| 5 | **Ops Claude** | 月次ルール棚卸し（E-1）+ 13.4 四半期メタ振り返り | 0.5日 | ルール体系の自然減 |
| 6 | **CEO Claude** | 月1 PO セッション・north-star 更新フロー文書化 | 0.5日 | 北極星の鮮度維持 |
| 7 | **Designer Claude** | フロント変更 PR への自動 UX レビュー | 1日 | UX デフレを防止 |
| 8 | **Marketer Claude** | 自走 Lv3 到達後（フェーズ2/3 完了後） | — | Layer γ 立ち上げ |

合計約6日（Step 1-6）で「プログラマー Claude」から「組織として動く Claude」への構造転換が完了。Step 7-8 は段階的に追加。

### 14.6 Section 14 が他セクションを束ねる構造

| Section | 何の物理ガードか | 主に効く役割 |
|---|---|---|
| 1-13 | 各種違反パターンの物理化 | 全役割共通土台 |
| 4-A | Phase-Impact 必須 | PM Claude が紐付け責任 |
| 4-B | Dispatch 運用物理化 | Eng / SRE Claude |
| 4-D | Verified-Effect 必須 | QA Claude のレビュー基準 |
| 4-F | Approach / Fix-Type 必須 | QA Claude が承認基準に使う |
| 4-G | エラー黙殺ブロック | SRE Claude の検出範囲 |
| 4-H | Eval-Due 自動化 | PM Claude が回す中核 |
| 4-I | 「見ない・気づかない」物理化 | SRE Claude の責務 |
| 9 | 指示駆動プロンプト | 全役割の起動共通基盤 |
| 10 | 自走 Lv0-Lv4 | 役割連携の到達点 |
| 12 | ルール拡張性 | Ops Claude の運用対象 |
| 13 | 守られない構造 | Ops Claude が四半期で扱う |

→ **「プログラマー Claude」のための物理ガードは、すべて「組織として動く Claude」のための共通土台**。Section 1-13 を作りこめば作りこむほど、Section 14 の役割分担が成立する。逆に役割を分けないと、いくら物理ガードを足しても「プログラマー Claude が全部抱える」構造のままで限界がある。

### 14.7 北極星に「組織として動く」を明文化

`docs/north-star.md`（Layer 1）に「組織として動く Claude のあり方」セクションを追加:

```markdown
## Claude は組織として動く

このプロダクトは Claude による無人運営を前提とする。
Claude は単一の「プログラマー」ではなく、CEO / PM / QA / SRE / Eng / Ops の
役割を分担する組織として振る舞う。

役割を超えた行動（QA がコードを書く・PM が実装方針を決める）は禁止。
役割を超えた判断が必要な場合は、別の役割の Claude を起動する。

PO の役割は北極星更新（月1）と重大判断のみ。
```

→ 起動時必読の北極星に明記することで、毎セッション「自分は今どの役割で動いているか」を Claude が自問する構造になる。

### 14.8 結論 — リライト案の最終形

Section 1-13 を「プログラマー Claude のための物理ガード集」と読むのは正しいが、それは半分しか見ていない。

**真の構造はこう**:

```
Section 14 (役割分担) ← 最上位フレーム
   ↓ 役割ごとに別プロンプト
Section 9 (指示駆動プロンプト) ← 起動の共通基盤
   ↓ 起動時に必ず参照
Section 1-2 (Layer 1 北極星 + Layer 2 現フェーズ) ← 不変・変動の判断軸
   ↓ 全セッション共通の前提
Section 4 A-I (物理ガード) ← 違反防止の道具
   ↓ 役割が使う
Section 10 (自走 Lv0-4) ← 役割連携の成熟度
   ↓ 観測対象
Section 12-13 (拡張性 / 守られない問題) ← 運用継続の保証
```

リライト案を1行で言うなら:

> **「Claude が組織として動くために、北極星を起動時必読化し、役割別プロンプトを物理化し、違反パターンを CI/hook で物理ブロックし、自走 Lv2 まで持っていく」**

ここまで揃って初めて「プロダクト完成にブレない」が物理的に保証される。

---

## 15. 違反パターン総覧 — POが指摘した全27項目 × 物理ガード対応

> このセクションは Section 1-14 の集約。**POが2026-05-01セッションで言及した全違反パターン**を1表で俯瞰可能にする。

| # | 違反パターン (PO観察由来) | 該当物理ガード | 即効性 |
|---|---|---|---|
| 1 | 同時2セッション起動 | 既存: bootstrap [Code]≥2 ERROR | ✅済 |
| 2 | コード読まずプロンプト | B-1 dispatch_eng.sh + I-2 Refs必須 | 高 |
| 3 | 実機確認なし完了報告 | B-2 done.sh verify_target必須 | 高 |
| 4 | CI失敗・気づきつつ無視 | G-1 CI赤push reject + G-2 WARN reject化 | 高 |
| 5 | セッション長期継続 | B-3 round数カウンタ | 中 |
| 6 | 完了基準甘さ | D-1 Verified-Effect必須 | 高 |
| 7 | 対症療法・暫定対処 | F-7 Fix-Type permanent\|bandaid + 期限管理 | 最高 |
| 8 | ファイル更新取り違え | C-1 WORKING書き忘れpre-commit | 中 |
| 9 | 方針逸脱・一タスク完遂局所最適 | A-1 Phase-Impact必須 + Layer1/2必読 | 最高 |
| 10 | セッション切れ前提消失 | Section 9 dispatch_from_directive | 高 |
| 11 | プロダクトをビジネス化・自走できない | Section 10 Lv0→Lv2 + H-1/H-2 | 高 |
| 12 | ルールが今後増える前提なし | Section 12 `_meta.yaml` 集中管理 | 中 |
| 13 | 細かく言わないとサボる | 12.3 ルール記述テンプレ + F-1 + O-1 | 高 |
| 14 | 勝手に変なやり方で無理くり | F-1〜F-6 Approach/Plan-Approved | 高 |
| 15 | 恒久対処せず暫定 | F-7（再掲）+ Section 13 守られない構造対策 | 最高 |
| 16 | エラー黙殺・違う道で対応 | G-1〜G-8 + G-7 Approach-Changed検出 | 高 |
| 17 | 実装→評価→次が口だけ | **H-1 Eval-Due必須 + H-2 評価自動起票** | 最高 |
| 18 | そもそも見ない・気づかない | I-1 起動時注意表示 + I-3 PRテンプレ + I-5副作用grep | 高 |
| 19 | 気づきの仕組みを作らない | J-1 lessons末尾必須 + J-3 月次レビュー | 中 |
| 20 | プログラマーとしてしか動かない | **Section 14 役割分担 + dispatch_<role>.sh** | 最高 |
| 21 | 物理ガード抜け道・PR放置 | K-1 抜け道検出 + K-3 PR放置エスカレ | 高 |
| 22 | 自動マージしない | **K-2 条件揃ったら24h以内強制マージ** | 最高 |
| 23 | PO思いつき即実装・整合性チェックなし | **L-1 PM Claude一次受け** | 高 |
| 24 | 進捗管理を Claude がやらない | L-5 PM Claude 週次進捗自走 | 中 |
| 25 | PII / シークレット git 混入 | **M-1 PII grep拡張** + M-2 履歴定期スキャン | 最高 |
| 26 | コスト勝手消費 | **M-3 Cost-Impact必須** + M-4 件数guard + M-6コストSLI | 最高 |
| 27 | リーガル・規約無視 | **N-1 Legal-Reviewed/Robots-Checked citation必須** | 高 |
| 28 | 保守性犠牲・動かすためだけのパラメータ | **O-1 Param-Justification必須** + O-3 安易フォールバック検出 | 高 |

→ **「最高」即効性のもの 9 件** = #7, #9, #15, #17, #20, #22, #25, #26 + #11(下流) ─ **これらを最優先で物理化すれば違反の半分以上が消える**。

---

## 16. 確定版・最短実装ルート（合計8.5日 / 違反27パターンの主要15を物理化）

| Day | 作業 | 該当違反# | 担当役割 |
|---|---|---|---|
| 0.5 | `docs/north-star.md` 新設（vision + product-thinking + direction 統合） | #9 #10 #20 | CEO Claude（PO同席） |
| 0.5 | `docs/current-phase.md` 新設（project-phases から抽出） | #9 #11 | PM Claude |
| 0.5 | `session_bootstrap.sh` 改修（north-star + current-phase 全文表示） | #9 #10 #18 | Eng Claude |
| 0.5 | I-1 起動時注意表示（CW errors / CI 失敗 / SLI 割れ / 期限切れbandaid） | #4 #18 | Eng Claude |
| 0.5 | A-1 `Phase-Impact:` commit-msg hook | #9 #23 | Eng Claude |
| 0.5 | F-1 `Approach:` + F-7 `Fix-Type:` commit-msg hook | #7 #14 #15 | Eng Claude |
| 0.5 | G-1 CI赤 push reject + G-4 `catch-and-ignore` grep | #4 #16 | Eng Claude |
| 1.0 | **H-1 `Eval-Due:` 必須 + H-2 評価自動起票 scheduled-task** | #17 #11 | Eng Claude |
| 0.5 | **M-1 PII grep 拡張 + M-3 `Cost-Impact:` 必須** | #25 #26 | Eng Claude |
| 0.5 | N-1 `Legal-Reviewed:` `Robots-Checked:` 必須化 | #27 | Eng Claude |
| 0.5 | **K-2 自動マージ強制設定（24h以内・条件揃ったら問答無用）** | #22 #21 | Eng Claude |
| 1.0 | `scripts/dispatch_from_directive.sh` + `dispatch_<role>.sh` 6種 | #2 #10 #20 | Eng Claude |
| 0.5 | O-1 `Param-Justification:` 必須化 | #28 | Eng Claude |
| 0.5 | L-1 PM Claude 一次受け運用化（PR テンプレ + プロンプト） | #23 #24 | PM Claude設計 |
| 0.5 | CLAUDE.md 100行リライト + `docs/rules/operational.md` 新設 | 全体 | Cowork |

**合計8.5日**で違反パターン27件中15件（即効性「最高」「高」の上位）を物理化完了。

残り（自走 Lv2-Lv3 / Section 14 残役割 / Section 12 `_meta.yaml` / 古い方針ドキュメント廃止統合）は段階的に。

---

## 17. PO への確認事項（実装着手前）

着手前に以下を確認させてください:

1. **実装の起点**: 今このセッションを「PM Claude 一次受け」として動かしますか？ それとも別タイミングで PM Claude セッションを起動？
2. **コードセッション**: Day 0.5〜8.5 の Eng Claude 作業は、コードセッション 1 件を起動して連続実装します（CLAUDE.md「同時1件」遵守）。今 WORKING.md の `[Code]` 行を確認してから起動して良いですか？
3. **CEO Claude セッション（north-star.md 確定）**: PO 同席が必要です。北極星の文言（情報の地図 / 自走 Lv / 試走→自走 訂正の反映）はリライト案 Section 9-14 を下敷きで進めて良いですか？
4. **既存ルール削除**: `flotopic-vision-roadmap.md`（古い）/ `dispatch-reflection-2026-05-01.md`（吸収済）等の廃止に PO 同意ありますか？
5. **branch protection 緩和**: K-2 自動マージ強制のため `required_approving_review_count=1` を「QA Claude 自動 approve」運用に切り替える必要があります。同意ありますか？

これらが定まれば即着手します。

