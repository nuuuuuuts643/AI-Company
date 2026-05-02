# コンフリクト解決ルール

> 出自: `docs/lessons-learned.md` 「コンフリクト解決時に upstream 採用で CLAUDE.md を破壊（2026-05-02）」
> 物理ガード: `scripts/conflict_check.sh`（`session_bootstrap.sh` から起動時に発火）

---

## 1. 「shared docs」の定義

以下の **5 ファイル** を本ルールでは **shared docs** と呼ぶ。両セッション（Code / Cowork / Dispatch / scheduled-task）が同時に書き込む可能性があり、一方の最新変更を捨てると即事故になる。

| ファイル | 主な書き込み主体 |
|---|---|
| `CLAUDE.md` | Code / Cowork / Dispatch すべて |
| `WORKING.md` | Code / Cowork / Dispatch すべて |
| `TASKS.md` | Code / Cowork / Dispatch すべて |
| `HISTORY.md` | Code / Cowork（done.sh 経由）すべて |
| `docs/lessons-learned.md` | Code / Cowork すべて（なぜなぜ append-only） |

shared docs に該当しないファイル（`lambda/` / `frontend/` / `scripts/` / `.github/` 等のコード）は **コンフリクト発生時に状況に応じて `--ours` / `--theirs` を選んでよい**。逆に shared docs では両側採用以外の選択は禁止する。

---

## 2. shared docs での **必須** 解決手順（3-way マージ）

`git status` で `^UU <shared-doc>` を検出した場合:

1. `git diff <shared-doc>` で両側の差分を確認する
2. **両側に意味のある差分があれば、両側を残す**形で手作業マージする（`<<<<<<<` / `=======` / `>>>>>>>` マーカーを手で消し、両側の追加行をすべて残す）
3. `git diff <shared-doc>` で再確認し、conflict marker が完全に消えていることを確認
4. `git add <shared-doc>` してから commit する

### 行末・空行・空白の機械的「揃え」も禁止

両側採用後に自動 lint・整形ツール（fmt / prettier / sed の一括 trim 等）を shared docs に走らせない。「整形」を装って一方の編集を消すパターンが発生する。

---

## 3. **絶対に使ってはいけない** コマンド（shared docs に対して）

```bash
# ❌ 全部禁止 — shared docs では使うな
git checkout --theirs CLAUDE.md
git checkout --ours WORKING.md
git restore --theirs --staged TASKS.md
git restore --ours --staged HISTORY.md
```

これらはどちらか片方を完全に捨てる挙動なので、**「両側採用」原則と物理的に両立しない**。`scripts/conflict_check.sh` は UU 検出のみだが、運用ルールとして shared docs では使用禁止。

> コードファイル（`lambda/foo.py` 等）に対してはこれらを使ってよい。`-ours`/`-theirs` は use case が明確な場合（例: ローカル experimental 変更を完全に捨てたい）に限り使う。

---

## 4. `scripts/conflict_check.sh` の使い方

### 起動時自動チェック

`session_bootstrap.sh` が起動シーケンスの中で `conflict_check.sh` を発火する。shared docs が UU 状態だった場合 ERROR で停止し、bootstrap 全体を中断する。

### 手動実行

```bash
bash scripts/conflict_check.sh
echo "exit=$?"
```

- exit 0: shared docs の UU なし（コードファイルだけの conflict は OK）
- exit 1: shared docs の少なくとも 1 ファイルが UU 状態

ERROR 時の標準エラー出力例:

```
ERROR: shared docs are in conflict (UU) state.
  - WORKING.md
  - docs/lessons-learned.md
shared docs は両側マージ必須・upstream 採用禁止。
詳しくは docs/rules/conflict-resolution.md を参照。
```

### test での mock

`CONFLICT_CHECK_GIT_STATUS_OUTPUT` 環境変数に `git status --porcelain` の出力をセットすると、実 git に問い合わせず env 値で判定する。boundary test で実 git repo 不要にするためのフック。

```bash
# test スニペット例
CONFLICT_CHECK_GIT_STATUS_OUTPUT='UU CLAUDE.md' bash scripts/conflict_check.sh
echo "exit=$?"   # 1 を期待
```

---

## 5. 想定 Q&A

### Q1. shared docs の conflict が発生したらまず何をする？

A. `git status` で UU を確認 → `git diff <file>` で両側差分を確認 → エディタで両側残す形で手作業マージ → `git add <file>` → commit。「`--theirs` で逃げる」の選択肢は無い。

### Q2. 自動マージが「Auto-merging」と表示してそのまま通った場合は？

A. それは git が両側差分を競合なく合成できたケース（追加行が異なる行番号）。問題ない。`UU` まで上がった場合だけが本ルールの対象。

### Q3. 「両側残すと矛盾する」内容（例: 同一タスク ID の優先度が両側で違う）になっていたら？

A. PO に確認するか、新しい行として両方残し「(merge: 両側保持)」コメント付きで残す。**勝手にどちらか選ぶのは事故の元**。

### Q4. lessons-learned.md に append したつもりが両側で append になり、同じ事象を 2 セクション書いた場合は？

A. 両セクションを 1 つに統合する手作業マージを行う（同じ事象を 2 回書かない）。 `--ours` で片方を捨てるのではなく、両側の細部を読んで 1 つに統合する。

---

## 6. 物理ガードの限界と運用での補強

`conflict_check.sh` は **shared docs の UU 検出**しかしない。以下は物理化されておらず運用判断に依存する:

- **両側採用が「正しく」行われたか** — 単に conflict marker を消すだけで片側を捨てる操作も検出できない（marker は消えるので grep でも検出不可）
- **マージ後の commit メッセージ** — どう解決したかは人間が書く

このため、shared docs を含む PR には **diff レビューを必須化**する運用を併用する。具体的には `Verified:` 行と並んで `Verified-Merge: <how-conflict-resolved>` を任意で付ける（必須化は将来拡張）。

---

## 7. 関連ファイル

- 物理ガード: `scripts/conflict_check.sh` / `tests/test_conflict_check.sh`
- 起動時統合: `scripts/session_bootstrap.sh`
- 事故記録: `docs/lessons-learned.md` 「コンフリクト解決時に upstream 採用で CLAUDE.md を破壊（2026-05-02）」
- 親規則: `CLAUDE.md` 絶対ルール表「同名ファイル並行編集禁止」
