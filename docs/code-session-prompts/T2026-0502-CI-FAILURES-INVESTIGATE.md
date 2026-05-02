# Code セッション起動 prompt: T2026-0502-CI-FAILURES-INVESTIGATE

> 用途: PR #316 (T2026-0502-IAM-FILTER-FIX) merge 後から main で持続している 2 件の CI failure を診断
> 関連: 横展開チェックリスト landing 検証 / 思想・表記ドリフト検出 — どちらも `bash scripts/check_lessons_landings.sh` を呼んで failure
> 推奨モデル: **Sonnet** (調査分析)
> リスク: **🟡 中** (調査のみは安全だが、誤った fix で check_lessons_landings.sh が壊れると全 PR ブロック)
> 想定所要: 1 時間 (diagnosis-only PR) + 後日別セッションで fix PR
> 実施推奨: **明日 PO 立ち会い前提・diagnosis-only PR は Code セッション 1 件で完結・fix は PO レビュー後**
> 改訂: 2026-05-02 23:55 JST (V2 — diagnosis と fix を 2 PR に分割 + CI 環境差分チェックリスト)

---

## 重要な制約 (V2 で追加)

**本タスクは diagnosis-only**。check_lessons_landings.sh / install_hooks.sh / lessons-learned.md 等の **コード変更は禁止**。
診断結果のみ docs/lessons-learned.md に新セクションとして追記する PR で完結する。

修復 (fix) は本 PR merge 後に PO がレビューし、別 Code セッション (T2026-0502-CI-FAILURES-FIX) で実施する。
これは check_lessons_landings.sh が CI で全 PR を gate しており、誤った fix が全 PR をブロックするリスクがあるため。

---

## prompt 本文

```
## 状況

main HEAD (2026-05-02 時点) で以下 2 つの CI が継続的に failure:
- 横展開チェックリスト landing 検証（過去対策の fossilize 検出）— meta-doc-guard.yml
- 思想・表記ドリフト検出（守らないと進めない仕組み）— ci.yml の step「横展開チェックリスト landing 検証 (T2026-0428-BC)」

両方とも `bash scripts/check_lessons_landings.sh` を実行して failure。

## ローカル動作との差分 (2026-05-02 23:20 JST Cowork セッション実証)

```
$ bash scripts/check_lessons_landings.sh
⚠️  チェックリスト表が見つかりません
✅ PR #159: session_bootstrap.sh landing verified (PIPESTATUS + exit 経路)
✅ PR #160: install_hooks.sh + .git/hooks/pre-push landing verified ...
✅ T2026-0502-DEPLOY-WATCHDOG: ... (4 件)
✅ T2026-0502-MU-FOLLOWUP: ... (2 件)
✅ T2026-0502-WORKFLOW-DEP-PHYSICAL: workflow ref check landed (script + workflow step)
exit 0
```

ローカル exit 0、CI exit 1。CI 環境固有の何かが違う。

## 失敗が始まった commit

- adfaad48 (PR #313 BI-PERMANENT 物理ガード): success
- b5f9d84e (PR #316 T2026-0502-IAM-FILTER-FIX) **以降** failure 持続

PR #316 が変更したファイル:
- .github/workflows/ci.yml
- docs/lessons-learned.md
- scripts/install_hooks.sh
- tests/test_pre_commit_iam_filter.sh (added)

## 本 PR で実施する範囲 (diagnosis-only)

**コード変更禁止**。以下のみを行う:

1. CI 失敗の **真因** を特定する (確証ベース・推測ではなく)
2. 真因 + 仮説検証ログを `docs/lessons-learned.md` に新セクション「main 持続 CI failure (T2026-0502-IAM-FILTER-FIX 由来) 診断結果」として追記
3. fix の方針案を提案 (実装は別 PR)

## 調査手順

### Step 1: CI raw log 取得

```bash
# 最新 main HEAD で 2 つの failing workflow の run id を取得
gh run list --workflow=meta-doc-guard.yml --branch main --limit 1 --json databaseId,conclusion
gh run list --workflow=ci.yml --branch main --limit 1 --json databaseId,conclusion
```

両 run の log を取得:
```bash
gh run view <run_id> --log-failed > /tmp/run_<id>.log
```

または job log 直接:
```bash
gh run view --job <job_id> --log > /tmp/job_<id>.log
```

→ どの行で何が exit 1 を発生させたか特定

### Step 2: ローカル vs CI 環境差分仮説 (1 つずつ検証)

| 仮説 | 検証コマンド | 期待 |
|---|---|---|
| H1. bash version 違い (regex / set -e 挙動) | CI log で `bash --version` 出力確認 | mac: bash 3.2 / Linux: bash 5.x |
| H2. file permission 違い (chmod +x 順序) | git config core.fileMode 値・git ls-files -s scripts/check_lessons_landings.sh のモード | mode 100755 期待 |
| H3. CRLF / LF 改行 (PR #316 の install_hooks.sh が CRLF 混入) | `file scripts/install_hooks.sh` / `od -c | head` で改行確認 | LF only 期待 |
| H4. check_lessons_landings.sh の Python regex が PR #316 lessons-learned.md 改修後 break | `python3 -c "..."` で regex match を確認 (本 PR では `python3 -c` を使わずスクリプト経由で) | regex match 確認 |
| H5. install_hooks.sh の必須 grep パターン (pre-push/refs/heads/main/ALLOW_MAIN_PUSH) が PR #316 後にも grep ヒット | grep -c で確認 | 各 1 件以上ヒット |
| H6. CI runner の locale / LANG 違い (日本語含む正規表現で UTF-8/LATIN1 差) | log で `locale` 出力確認 | UTF-8 期待 |
| H7. test_pre_commit_iam_filter.sh が check_lessons_landings.sh をベースに追加されていて干渉 | grep "check_lessons_landings" tests/ で参照確認 | 直接参照無し期待 |

### Step 3: 真因確定

Step 2 の仮説で 1 つに絞れたら、`docs/lessons-learned.md` の新セクションに以下を記録:

```markdown
## main 持続 CI failure (T2026-0502-IAM-FILTER-FIX 由来) 診断結果 (T2026-0502-CI-FAILURES-INVESTIGATE)

**真因**: H<N>. 〇〇

**証拠**:
- CI log: <gist URL or 直接貼り付け>
- ローカル再現コマンド: <command>
- 期待 vs 実測の差分: <diff>

**fix 方針 (本 PR では実装しない)**:
1. 〇〇
2. 〇〇

**fix の実装は別 Code セッション** (T2026-0502-CI-FAILURES-FIX) で実施。
```

## 手順

1. main 同期 + 新 branch
   git checkout main && git pull --rebase origin main
   git checkout -b chore/T2026-0502-CI-FAILURES-INVESTIGATE

2. WORKING.md に [Code] 行追加
   | [Code] T2026-0502-CI-FAILURES-INVESTIGATE 真因診断 (コード変更なし) | Code | docs/lessons-learned.md | <開始JST> | yes |

3. Step 1〜3 を実施

4. lessons-learned.md に診断結果追記 (上記テンプレート使用)

5. commit + push + PR
   git add docs/lessons-learned.md WORKING.md
   git commit -m "chore: T2026-0502-CI-FAILURES-INVESTIGATE 真因診断結果

main 持続 2 CI failure (横展開 landing 検証 / 思想ドリフト) の真因を特定。
PR #316 (T2026-0502-IAM-FILTER-FIX) merge 後から発生。

検証した仮説 7 件 → 真因: H<N>. <一行サマリ>

fix の実装は別 Code セッション T2026-0502-CI-FAILURES-FIX で
PO レビュー後に実施 (check_lessons_landings.sh が全 PR を gate しており
誤った fix で全 PR ブロックリスクあり)。

Verified-Effect-Pending: 真因が docs/lessons-learned.md に記録される
Eval-Due: 2026-05-09 (1 週間以内に fix セッション実施)"
   git push -u origin HEAD
   gh pr create --title "chore: T2026-0502-CI-FAILURES-INVESTIGATE 真因診断" --fill

6. PR は **コード変更含まないので CI passes は確認のみ** (本 PR 自身も既存の 2 failure を継承するが、この PR では治さない・OK)

7. PR merge 後、TASKS.md に T2026-0502-CI-FAILURES-FIX を追加 (fix 実装の別タスク)

8. WORKING.md cleanup + done.sh

## fix PR (本タスクでは実施しない)

本 PR merge + PO レビュー後、別 Code セッション (T2026-0502-CI-FAILURES-FIX) で実施:
- 真因に応じた最小修正 (check_lessons_landings.sh の 1〜数行変更想定)
- 修正前後で deliberate test (現 main commit + fix で CI 上で success に転じることを観測)
- 検証 PR で実 CI 上での修復確認

prompt は本ファイルを参考に新規作成 (T2026-0502-CI-FAILURES-FIX.md・診断結果が判明後に書ける)。

## 完了条件 (本タスク)

- [ ] docs/lessons-learned.md に「main 持続 CI failure ... 診断結果」セクションが追記
- [ ] 真因が H1〜H7 のいずれかに confidently 絞られている (証拠付き)
- [ ] fix 方針が proposal レベルで記載 (実装は別タスク)
- [ ] 本 PR が squash merge 済 (本 PR 自身の CI failure は既存 2 件継承で許容)
- [ ] TASKS.md に T2026-0502-CI-FAILURES-FIX エントリ追加
- [ ] WORKING.md cleanup
- [ ] done.sh 実行

## 注意 (V2 で追加)

- **コード変更禁止** (本 PR では check_lessons_landings.sh / install_hooks.sh / etc を一切編集しない)
- gh CLI が CI raw log を取得する手順は **gh run view --log-failed** が基本・job 単位で見る場合は --job
- log 取得時に PII / secrets が含まれていないか確認 (env vars が漏れる可能性あるので gist 化前にチェック)
- 仮説 H4 で `python3 -c` を使う場合、本 PR で workflow YAML には書かないこと (CI lint で reject される)
```
