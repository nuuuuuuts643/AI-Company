# OIDC 段階移行 runbook (T2026-0502-SEC10-PHASED・2026-05-02 制定)

> **目的**: 残り 19 workflow を OIDC 専用に移行する際、本番を壊さずに段階的に進める。
> **背景**: T2026-0502-SEC10-CODE (PR #265) で 9 workflow を一括編集したが、`permissions: id-token: write` 不足 + `env:` block AWS_ACCESS_KEY_ID 残存 で OIDC が実は動いていない可能性。さらにスコープ漏れ 10 workflow も access key 使用中。
> **重要原則**: 一括移行禁止。1 batch 完了後に必ず動作確認してから次へ。

---

## 前提

- IAM OIDC IdP / Standard Role / Deploy Role / GitHub Secrets は全て設定済 (T2026-0502-SEC10 pilot 完了時)
- pilot workflow `freshness-check.yml` SLI 14 step は OIDC で動作確認済
- legacy access key (`secrets.AWS_ACCESS_KEY_ID`) はまだ active = 移行中もそれが fallback として動く

---

## 事前準備 (1 回のみ・PO 操作)

### A. Standard Role の権限が全 workflow で十分か検証

現在の `flotopic-actions-standard` policy は Lambda の `flotopic-least-privilege` をコピー。これで全 workflow の AWS 操作をカバーできるか確認:

```bash
# 各 workflow が呼ぶ AWS API を grep
for wf in .github/workflows/*.yml; do
  echo "--- $wf ---"
  grep -oE 'aws\s+(lambda|s3|dynamodb|cloudwatch|sts|iam|secretsmanager|cloudfront|events)\s+[a-z-]+' "$wf" 2>/dev/null | sort -u
done
```

**追加が必要な可能性のある権限**:
- `cloudfront:CreateInvalidation` (deploy-p003.yml で frontend deploy 時)
- `events:PutRule` / `events:PutTargets` (deploy 系で EventBridge 設定)
- `iam:GetRole` (lambda-freshness-monitor.yml 等)
- `lambda:InvokeFunction` (governance.yml 等で発火)

不足判明時は `flotopic-actions-standard` policy に追加:
```bash
aws iam put-role-policy \
  --role-name GitHubActionsRole-Flotopic-Standard \
  --policy-name flotopic-actions-standard \
  --policy-document file:///tmp/updated-policy.json
```

### B. 各 workflow の cron schedule 確認 (動作確認タイミングの予測)

```bash
for wf in .github/workflows/{bluesky-agent,weekly-digest,quality-heal,security-audit,sli-keypoint-fill-rate,editorial-agent,deploy-trigger-watchdog,deploy-lambdas,deploy-p003,cf-analytics-setup,deploy-staging,fetcher-health-check,governance,health-check,lambda-freshness-monitor,notion-revenue-daily,revenue-agent,revenue-sli,x-agent}.yml; do
  echo "$(basename $wf): $(grep -oE 'cron:.*' $wf 2>/dev/null | head -1)"
done
```

→ 各 workflow が次に発火するタイミングを把握 → 移行直後のその時刻に異常が無いか CloudWatch / Slack で監視。

---

## 移行バッチ (低リスク → 高リスクの順)

### バッチ 1: read-only 系 (3 workflow・低リスク)

| workflow | リスク | 影響 (壊れた場合) |
|---|---|---|
| `sli-keypoint-fill-rate.yml` | 低 | SLI 計測 fail (Slack 通知のみ・本番影響なし) |
| `lambda-freshness-monitor.yml` | 低 | freshness 観測 fail (Slack 通知のみ) |
| `fetcher-health-check.yml` | 低 | health check fail (Slack 通知のみ) |

**手順** (各 workflow):
1. `permissions:` block (workflow root) に `id-token: write` 追加
2. `aws-actions/configure-aws-credentials@v4` step を OIDC 専用に書換 (or 追加)
3. `run:` step の `env:` block から `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` 削除 (`AWS_DEFAULT_REGION` は残す)
4. PR (1 ファイルだけ・小さく)
5. merge 後に手動 dispatch:
   ```bash
   bash scripts/gh_workflow_dispatch.sh sli-keypoint-fill-rate.yml
   ```
6. 5 分待って結果確認:
   ```bash
   gh run list --workflow=sli-keypoint-fill-rate.yml --limit 1
   ```
7. ✓ success ならバッチ進行 / ❌ failure なら revert + 原因究明

**完了条件 (バッチ 1)**:
- 3 workflow 全て手動 dispatch で success
- CloudTrail で各 workflow が AssumeRoleWithWebIdentity していること確認:
  ```bash
  aws cloudtrail lookup-events \
    --lookup-attributes AttributeKey=EventName,AttributeValue=AssumeRoleWithWebIdentity \
    --max-results 10 \
    --query 'Events[].[EventTime,Resources[?ResourceType==`AWS::IAM::Role`].ResourceName | [0]]' \
    --output table
  ```

### バッチ 2: agent 系 (4 workflow・中リスク)

| workflow | リスク | 影響 (壊れた場合) |
|---|---|---|
| `bluesky-agent.yml` | 中 | Bluesky 投稿停止 (フェーズ 4 影響) |
| `notion-revenue-daily.yml` | 中 | Notion 収益 sync 停止 |
| `revenue-agent.yml` | 中 | 収益 SLI 計測停止 |
| `x-agent.yml` | 低 | X 投稿停止 (現在 dry_run 中なら影響軽微) |

バッチ 1 と同じ手順。各 workflow の Notion / Bluesky API 呼出は AWS と関係ない (env で渡している secret は別系統) なので env 削除時は AWS_* のみ削除 (BLUESKY_*  / NOTION_API_KEY 等は残す)。

**完了条件**: 各 workflow 動作確認 + Slack エラー通知が 24h 出ない。

### バッチ 3: governance + health 系 (5 workflow・中リスク)

| workflow | リスク |
|---|---|
| `governance.yml` (7 access keys!) | 中 — 多数の AWS service を読む |
| `health-check.yml` | 低 |
| `cf-analytics-setup.yml` | 低 |
| `deploy-staging.yml` | 中 (staging 環境のみ・production 影響なし) |
| `deploy-trigger-watchdog.yml` | 低 |

**注意**: `governance.yml` は 7 occurrences あるので慎重に。CloudTrail 観察で governance が読む全 AWS service を特定 → Standard Role policy に必要な権限を**事前**追加してから移行。

### バッチ 4: deploy 系 (3 workflow・高リスク)

| workflow | リスク | 影響 |
|---|---|---|
| `deploy-lambdas.yml` | **高** | Lambda update 停止 = 今後の deploy 全停止 |
| `deploy-p003.yml` | **高** | frontend deploy 停止 |
| `editorial-agent.yml` | 中 | 編集 AI 停止 |
| `quality-heal.yml` | 中 | 品質自動修復停止 |
| `security-audit.yml` | 低 | セキュリティ監査 (週次) のみ |
| `weekly-digest.yml` | 低 | 週次 digest のみ |

**deploy 系は Deploy Role (`AWS_ROLE_ARN_DEPLOY`) を使う**。Standard Role と権限が違うので、role-to-assume の値を `${{ secrets.AWS_ROLE_ARN_DEPLOY }}` にする。

**特別手順** (`deploy-lambdas.yml`):
1. 移行 PR を merge する**前**に、Deploy Role policy が `lambda:UpdateFunctionCode` を含んでいることを再確認
2. merge 後、即手動 dispatch (今後の deploy が動くか確認)
3. fail なら **即 revert** (Lambda deploy が止まると緊急修正できなくなる)

---

## バッチ単位の安全装置

### 各 PR 作成時の checklist

- [ ] 1 PR = 1 ファイル (or 関連性の高い 2-3 ファイルまで)
- [ ] `permissions: id-token: write` 追加済
- [ ] `env:` block から `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` 削除済 (`AWS_DEFAULT_REGION` は残す)
- [ ] `configure-aws-credentials@v4` step が `role-to-assume` のみ (access-key 系を含まない)
- [ ] commit message に `Verified: yaml syntax + 移行前後の grep diff:<JST>` 含む
- [ ] commit message に `Verified-Effect-Pending: 手動 dispatch で動作確認:<Eval-Due 日付>` 含む

### バッチ完了後の確認

- [ ] 各 workflow 1 回手動 dispatch (`bash scripts/gh_workflow_dispatch.sh ...`)
- [ ] CloudTrail で該当 workflow から `AssumeRoleWithWebIdentity` 確認
- [ ] CloudWatch / Slack で 24h エラー通知 0 件
- [ ] **fail があれば即 revert** (`git revert <commit>`) して原因究明

### ロールバック手順 (1 workflow が壊れた場合)

```bash
# 該当 PR の commit を identify
gh pr list --state merged --limit 5

# revert PR を作成
git revert -m 1 <merge-commit-sha>
git push origin main

# または GitHub UI で「Revert」ボタンでも OK
```

revert 後は legacy access key (まだ active) で workflow が再び動くようになる。

---

## 全バッチ完了後 (= SEC10-CODE 完了)

最終確認:
```bash
# access key 参照ゼロ確認
grep -rE "secrets\.AWS_ACCESS_KEY_ID|secrets\.AWS_SECRET_ACCESS_KEY" .github/workflows/
# → 出力 0 行

# id-token: write が必要な workflow 全てに含まれているか
for f in $(grep -lE "configure-aws-credentials" .github/workflows/*.yml); do
  grep -q "id-token: write" "$f" || echo "MISSING: $f"
done
# → 出力 0 行
```

→ T2026-0502-SEC10-CODE 取消線 → T2026-0502-SEC10-KEY-DELETE に移行 (1 週間観察後 access key delete)。

---

## 月単位スケジュール (推奨)

| 週 | バッチ | 担当 |
|---|---|---|
| 2026-05-W1 (今週) | 静観 (PR #265 の effect を観察) | 自動 (cron) |
| 2026-05-W2 | バッチ 1 (3 workflow read-only) | Code セッション (1 PR/workflow) |
| 2026-05-W3 | バッチ 2 (4 workflow agent) | Code セッション |
| 2026-05-W4 | バッチ 3 (5 workflow governance/health) | Code セッション |
| 2026-06-W1 | バッチ 4 (3 workflow deploy・最高リスク) | Code セッション + PO 立ち会い |
| 2026-06-W2 | 1 週間観察 + SEC10-KEY-DELETE | PO |

各週 30〜60 分・全 6 週間。急がない。

---

## 参考

- pilot 実装: PR #258 (freshness-check.yml SLI 14 step)
- 失敗の事例: PR #265 (一括 9 workflow 編集・3 つの不備で incomplete)
- security-roadmap: `docs/rules/security-roadmap.md` レベル 2 達成条件
