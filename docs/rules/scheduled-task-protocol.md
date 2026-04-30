# scheduled-task プロトコル（Cowork 自動起動セッション専用）

> このファイルは Cowork のスケジュール機能から自動起動された Claude セッションの動作プロトコル。
> 普通の対話セッションでは読まなくてよい。
> **lessons-learned「scheduled-task が "課題発見" に偏り "即時改善" に進まない問題」(2026-04-28) の構造的対策。**

---

## 起動時に読む順序（順序を変えるな）

1. `cat ~/ai-company/CLAUDE.md` — 絶対ルール
2. `bash ~/ai-company/scripts/session_bootstrap.sh` — 起動チェック
3. `cat ~/ai-company/docs/system-status.md` — 現状スナップショット
4. **本ファイル** — schedule-task の動作プロトコル
5. `cat ~/ai-company/TASKS.md` — 最優先 unblocked タスク

---

## 動作プロトコル（3 フェーズ・順序固定）

### フェーズ 1: 探索 (最大 30 分相当の操作)

- production を curl で観察 (topics.json updatedAt / トップページ HTTP / ads.txt)
- TASKS.md の「実装済の可能性あり」行を HISTORY.md と突合
- WORKING.md の stale 行確認
- 新たな課題候補を洗い出す

**禁止**: このフェーズで実装しない。発見と仮説立てだけ。

### フェーズ 2: 実装 (探索の後・必須・最低 1 件)

**ルール**: 探索で見つかった課題のうち、以下の条件を **すべて満たす 1 件以上** を必ずこのフェーズで実装する。

1. 不可逆性が低い（rollback 容易・production を壊さない）
2. 他タスクへの依存が無い（unblocked）
3. テストが容易（YAML lint / shell sanity check / curl で確認可能）
4. 副作用が他コンポーネントに波及しない（lambda 主ループ等の core path に触らない）

候補が無い場合のみ「保留」を選択できる。**「無理して改善する必要はない」を免罪符として使うのは禁止。**

実装後は必ず:
- WORKING.md から自分の行を削除
- commit message に `[Schedule-KPI] implemented=N created=M closed=K queue_delta=±X` を含める
- `Verified:` 行も付ける（CI / curl / 手動確認のうちどれかの証跡）

### フェーズ 3: 報告

報告内容は **必ずこの順番** で書く：

1. **実装したもの** (実装成果ファースト)
2. **発見した課題** (起票成果セカンド)
3. **保留した理由** (該当する場合のみ・なぜ実装しなかったか具体的に)
4. **次に着手すべき優先タスク** (次の schedule-task への引き継ぎ)

---

## anti-pattern（やってはいけない動作）

| パターン | なぜ NG | 代替 |
|---|---|---|
| 課題を 12 件発見 + 実装ゼロ | キューを膨らませるだけ | 1 件以上必ず実装 |
| 「実装済の可能性あり」のままタスクを再起票 | HISTORY 確認の手間を後ろに送るだけ | 起動時に必ず突合 |
| 「無理して改善する必要はない」を冒頭判断材料に使う | escape hatch の濫用 | フェーズ 2 の 4 条件で機械的に判定 |
| ルール（テキスト）追加だけで再発防止と称する | lessons-learned のメタ教訓違反 | CI / cron / hook / SLI のいずれかを 1 つ以上含める |
| schedule-task 履歴を見ずに動作する | 過去の anti-pattern を繰り返す | 起動時に `git log --oneline --grep "schedule-task" \| head -5` を必ず実行 |

---

## 「保留」が許される条件（exhaustive）

以下のいずれかに該当する場合のみ、フェーズ 2 をスキップして報告に進める：

1. ナオヤの判断が必要なタスクしか残っていない (T251 CloudFront 設定 / T192 ジャンル戦略など)
2. 全ての unblocked タスクが「core path 改修」(lambda 主ループ・本番 DB スキーマ等) で副作用が読みきれない
3. 起動チェック script で stale / lock 退避失敗が発生し、まず復旧が必要
4. **unblocked タスクは残っているが、いずれも「効果が事前に可視化できない / 低価値 / `global-baseline.md` §8 (ナオヤ前提) と矛盾する」施策しかなく、無理に実装するとルール肥大化や対症療法を生む場合** — 例: 「念のため SLI 追加」「念のためルール追加」「観測効果が見えない docs 追記」

「他にやることがある」「複雑そう」「依存が読みきれない」は **保留理由として不可**。

> 4. を選択する場合は escape hatch 濫用防止のため、報告の §3「保留した理由」に **「保留と判断した具体的根拠を 3 行以内」** で書くこと（どのタスクが、なぜ事前可視化不能 / 低価値 / §8 矛盾なのか）。`[Schedule-KPI] implemented=0 created=N closed=K queue_delta=±X` で commit してよい（commit-msg hook の構文上 implemented=0 は許容）。
>
> **整合性メモ**: 4. はナオヤ前提 §8「効果が見えない間は保留でかまいません」「無理して更新しない」との整合のため追加 (lessons-learned 2026-04-28 08 「protocol vs §8 矛盾」由来)。escape hatch 濫用が観測されたら 4. を再度絞る。
