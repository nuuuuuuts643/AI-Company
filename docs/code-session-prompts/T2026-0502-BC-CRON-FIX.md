# Code セッション起動 prompt: T2026-0502-BC-CRON-FIX

> 用途: Cowork デスクトップから Code セッションを起動する際にコピペで使う。
> 関連: TASKS.md T2026-0502-BC-CRON-FIX、handler.py:599-608、Verified-Effect 観測実績
> 推奨モデル: **Sonnet** (1 PR 完結・EventBridge rule + Lambda permission + deploy.sh + handler.py 修正)
> 想定所要: 30〜60 分

---

## 背景 (重要・必読)

PR #281 (T2026-0502-BC) で導入した judge_prediction の gate 条件:

```python
# lambda/processor/handler.py:606
_should_judge = (source != 'fetcher_trigger') and (_utc_hour == 13)
```

これに対し EventBridge `p003-processor-schedule` の cron は:

```
cron(30 20,8 * * ? *)  # = UTC 20:30 / 08:30 = JST 05:30 / 17:30 のみ
```

**UTC 13 (JST 22:00) の scheduled invoke が存在しない**ため、過去 48h で `[Processor] judge_prediction` ログ全 87 件が **全件 skip**。本体は一度も実行されていない。

調査ログ実測 (2026-05-02 22:54 JST · Cowork CloudWatch 経由):
- `aws.events` 起源は 4 件のみ (UTC 20:30 と 08:30 = JST 05:30/17:30) → どれも UTC_hour ≠ 13 で skip
- `fetcher_trigger` 起源は 83 件 → source 判定で skip
- `[judge_prediction] eligible= ... skipped_deadline=` ログは**ゼロ件**観測

設計意図 (handler.py:598-600 コメント):
> 2026-04-29 案D: コスト削減のため、judge_prediction は 1 日 1 回 (UTC 13:00 = JST 22:00 前後) のみ実行。

→ 設計意図を満たすには **22:00 JST cron 追加**が必須。

---

## prompt 本文 (これを Code セッションに渡す)

```
TASKS.md の T2026-0502-BC-CRON-FIX を読んで実装してください。

## 目的

judge_prediction の本体実行機会を確保 + handler.py 内の古いコメント乖離を解消する。

設計意図 (handler.py:598-600): 「コスト削減のため 1日1回 (UTC 13:00 = JST 22:00 前後) のみ実行」
現状の不整合: EventBridge `p003-processor-schedule` cron(30 20,8 * * ? *) に UTC 13 起動が無く、judge_prediction 本体が一度も走っていない。

## 罠の存在

handler.py:599-600 のコメント:
> 「新スケジュール cron(30 20,8) には UTC 13 起動はないが、fetcher は 30 分毎に走るため UTC 13 台に fetcher_trigger が来た場合のみ判定が走る」

これはコードと**矛盾**している (`source != 'fetcher_trigger'` なので fetcher_trigger は時刻に関係なく skip)。同 PR でコメントも修正すること。

## 手順

1. main 同期 + 新 branch 切る
   git checkout main && git pull --rebase origin main
   git checkout -b fix/T2026-0502-BC-CRON-FIX

2. EventBridge rule + Lambda permission 用 deploy.sh を編集
   `projects/P003-news-timeline/deploy.sh` の EventBridge セクション (既存 p003-processor-schedule の create-rule 周辺) に以下を追加:

   ```bash
   # ---- judge_prediction 専用 cron (T2026-0502-BC-CRON-FIX) ----
   # 設計意図: judge_prediction は 1 日 1 回 UTC 13:00 (= JST 22:00) のみ実行 (案D・コスト削減)
   # 既存 p003-processor-schedule (UTC 20:30/08:30) には UTC 13 起動が無いため別 rule で確保
   aws events put-rule \
     --name p003-processor-judge-schedule \
     --schedule-expression "cron(0 13 * * ? *)" \
     --state ENABLED \
     --region "$AWS_REGION" \
     --description "T2026-0502-BC judge_prediction を JST 22:00 (UTC 13:00) に1日1回起動"

   aws events put-targets \
     --rule p003-processor-judge-schedule \
     --targets "Id"="1","Arn"="arn:aws:lambda:${AWS_REGION}:${ACCOUNT_ID}:function:p003-processor","Input"='{"source":"aws.events.judge"}' \
     --region "$AWS_REGION"

   aws lambda add-permission \
     --function-name p003-processor \
     --statement-id p003-processor-judge-schedule \
     --action lambda:InvokeFunction \
     --principal events.amazonaws.com \
     --source-arn "arn:aws:events:${AWS_REGION}:${ACCOUNT_ID}:rule/p003-processor-judge-schedule" \
     --region "$AWS_REGION" 2>/dev/null || true  # 冪等
   ```

3. handler.py の `_should_judge` を見直す
   `lambda/processor/handler.py:606` を以下のいずれかに変更:

   案 1 (最小変更・推奨): 現状そのまま (`source != 'fetcher_trigger') and (_utc_hour == 13)`)
     → 新 cron 起動時 source は `aws.events` で UTC_hour=13 なので条件パス。動作する。

   案 2 (より明示的): `source in ('aws.events', 'aws.events.judge')`
     → input の source による明示的判別。将来「judge cron だけ実行」を厳密化したい時に有利。

   どちらでも動く。**案 1 を採用** (最小変更原則)。

4. handler.py:598-600 のコメントを実装と整合させる
   旧:
   ```python
   # 2026-04-29 案D: コスト削減のため、judge_prediction は 1 日 1 回 (UTC 13:00 = JST 22:00 前後) のみ実行。
   # fetcher_trigger 経由 (即時処理) でも skip。新スケジュール cron(30 20,8) には UTC 13 起動はないが、
   # fetcher は 30 分毎に走るため UTC 13 台に fetcher_trigger が来た場合のみ判定が走る。
   ```

   新:
   ```python
   # 2026-04-29 案D: コスト削減のため、judge_prediction は 1 日 1 回 (UTC 13:00 = JST 22:00 前後) のみ実行。
   # fetcher_trigger 経由 (即時処理) でも skip。
   # T2026-0502-BC-CRON-FIX (2026-05-02): 専用 cron `p003-processor-judge-schedule`
   # (cron(0 13 * * ? *)) を deploy.sh で作成。これがないと judge_prediction 本体は一度も走らない。
   ```

5. ローカル構文チェック
   bash -n projects/P003-news-timeline/deploy.sh
   python3 -m py_compile lambda/processor/handler.py

6. WORKING.md に [Code] 行を追記して push
   | [Code] T2026-0502-BC-CRON-FIX EventBridge cron 追加 + handler.py コメント修正 | Code | projects/P003-news-timeline/deploy.sh, lambda/processor/handler.py | <開始JST> | yes |

7. commit + PR
   git add projects/P003-news-timeline/deploy.sh lambda/processor/handler.py WORKING.md
   git commit -m "fix: T2026-0502-BC-CRON-FIX judge_prediction 専用 22:00 JST cron 追加 + コメント乖離修正

PR #281 (BC) で導入した judge_prediction の gate 条件:
  _should_judge = (source != 'fetcher_trigger') and (_utc_hour == 13)
が要求する UTC 13 (JST 22:00) の scheduled invoke が EventBridge
p003-processor-schedule (cron(30 20,8 * * ? *)) に存在せず、
過去 48h で judge_prediction 本体が 0 回しか実行されていなかった
(全 87 ログが skip)。

実測 (Cowork 2026-05-02 22:54 JST):
- aws.events 起源: 4 件 (UTC 20/08 のみ・どれも UTC_hour ≠ 13 で skip)
- fetcher_trigger 起源: 83 件 (source 判定で skip)
- [judge_prediction] eligible= ... skipped_deadline= : 0 件

恒久対処:
- EventBridge rule p003-processor-judge-schedule (cron(0 13 * * ? *)) 新規追加
  → input='{\"source\":\"aws.events.judge\"}' で起動 (将来明示判別の余地)
- Lambda permission add-permission (冪等)
- handler.py:598-600 のコメント乖離修正 (古い案D 元設計の説明を実装に整合)

副次:
- 既存 p003-processor-schedule (05:30/17:30 JST) は影響を受けない
- judge_prediction の本体実行は 1 日 1 回に限定 (重複起動なし)

Verified-Effect-Pending: 翌日 22:00 JST (UTC 13:00) cron 後の CloudWatch logs で
[Processor] 予想判定対象: N 件 + [judge_prediction] eligible=X total=Y skipped_deadline=Z
が出ること。matched/partial/missed の発生数も観測 (期待: 0→1+ 件)。
Eval-Due: 2026-05-04"
   git push -u origin HEAD
   gh pr create --fill

8. PR auto-merge & deploy 完了を確認 (gh run list --workflow=deploy-lambdas.yml --limit=1 が success)

9. WORKING.md から自分の行を削除 + done.sh

10. **CI 待ちは即クローズ**ルールに従い、効果検証は p003-haiku (毎朝 7:08) または one-time scheduled task に委ねてセッション即終了

## 完了条件

- EventBridge rule p003-processor-judge-schedule が ENABLED で存在
- Lambda permission に該当 statement-id がある
- handler.py:598-600 のコメントが実装と整合
- PR merge + deploy success
- 翌日 22:00 JST (= 2026-05-04 22:00 JST 想定) 後の CloudWatch logs に [judge_prediction] eligible= ログが 1 件以上出ること

## 注意

- 既存 p003-processor-schedule (cron(30 20,8 * * ? *)) は **絶対に削除しない**。fetcher 補助・backfill 処理が依存している
- input='{"source":"aws.events.judge"}' を渡すことで、将来 case 2 (`source in (...)`) への切替時にも非破壊で対応可能
- IAM 変更は不要 (既存の events:PutRule / lambda:AddPermission 権限の範囲内)
- 22:00 JST 起動時に既存 fetcher (rate(30 minutes)) の 22:00 トリガーと近接する可能性あり → 同時実行は Lambda 同時実行枠 (default 1000) で問題なし
```

---

## 横展開検討 (このタスクのスコープ外・別タスク化候補)

`docs/lessons-learned.md` に「Lambda gate 条件と EventBridge rule の不整合」案件として追記済み (本 PR の同根)。次の汎用化:

- `scripts/check_lambda_cron_gate_coverage.py` を CI 化 — Lambda コード内の `_utc_hour == N` / `source ==` パターンを抽出 → 対応する EventBridge rule の存在を物理検証 → 不整合を CI で fail させる
- 別タスク `T2026-0502-LAMBDA-CRON-GATE-CI` として TASKS.md に追加候補 (本 PR とは別)
