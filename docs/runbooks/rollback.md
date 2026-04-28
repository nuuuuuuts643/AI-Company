# ロールバック runbook（P003 Flotopic 本番）

> **目的**: 「main が壊れた」「直近のデプロイで本番が劣化した」状況から最短で安定状態に戻すための手順。
> **想定読者**: 当番のCEO / Code セッション。Cowork セッションが手動回復をかける場合も同じ手順を辿る。
> **前提**: 復旧操作は GitHub Actions と AWS CLI の両方が動作する前提。Lambda 直叩きは GH Actions が止まっている場合の最終手段。
> **関連**: `docs/project-phases.md` フェーズ1-§B（リリース管理・ロールバック）/ T2026-0428-BA。
> **CI 物理ガード**: 本ファイルは `.github/workflows/ci.yml` の runbook check で「空でない」「`git revert` または `aws lambda update-function-code` のいずれかが含まれる」を検査する想定（T2026-0428-BA で landing 予定）。本ファイルを移動・改名する場合は CI 側を必ず更新すること。

---

## 0. 判断フロー（最初の3分でやること）

1. 何が壊れているかを 1 行で書く（例: `flotopic.com 全URLで 500`、`api/topics.json が 6h 古い`）。
2. 影響範囲を判定する（Frontend / Lambda / DynamoDB / CloudFront / 全部）。
3. 直近 24h の commit を `git log --oneline -20` で見て、疑わしい commit を 1〜3 個に絞る。
4. **ロールバック対象が明確になるまで `aws s3 sync` / `aws lambda update-function-code` を打たない**（誤回復のほうが事故を増やす）。

> ⚠️ **POを起こす前に必ず**「症状 + 影響範囲 + 疑わしい commit」を 5 行以内でまとめてから連絡する。会話を始めてから状況確認するな。

---

## 1. Frontend ロールバック（S3 / CloudFront）

S3 バケットには version history を持たせていない（コスト都合）。**正本は git 履歴**。

### 1-A. 推奨経路: `git revert` → push → GitHub Actions 自動デプロイ

```bash
# 0. 現在の状態を退避用ブランチに保全
git switch -c rollback/$(date +%Y%m%d-%H%M%S)-frontend-broken
git switch main

# 1. 壊れた commit を特定（例: HEAD と HEAD~1）
git log --oneline -10 -- 'projects/P003-news-timeline/frontend/**'

# 2. 当該 commit を revert（マージコミットの場合は -m 1）
git revert <BAD_SHA>

# 3. push して GH Actions deploy-p003.yml を起動
git push origin main

# 4. GH Actions のジョブが success まで待つ（CloudFront invalidation /* まで含めて完了）
gh run watch || open "https://github.com/<owner>/ai-company/actions"
```

検証:

```bash
# 4-1. 主要ページが 200 を返すか
for u in / /index.html /about.html /api/topics.json; do
  curl -s -o /dev/null -w "%{http_code} ${u}\n" "https://flotopic.com${u}"
done

# 4-2. 直近の sw.js CACHE_NAME が GITHUB_SHA::7 と一致するか
curl -s "https://flotopic.com/sw.js" | grep -m1 "CACHE_NAME ="
```

200 を確認したら commit message に `Verified: https://flotopic.com/:200:<JST>` を書いてクローズ。

### 1-B. 緊急時: 手動 S3 sync で前 tag に巻き戻す

GH Actions が壊れていて push が動かない場合のみ：

```bash
# 1. 直近 LIVE と同じ commit にチェックアウト（v タグがあれば優先・無ければ SHA 指定）
git switch --detach <PREV_GOOD_SHA>

# 2. 手動 S3 sync（deploy-p003.yml の処理を再現）
BUCKET="p003-news-946554699567"
REGION="ap-northeast-1"
FRONTEND="projects/P003-news-timeline/frontend"
SHORT_SHA=$(git rev-parse --short=7 HEAD)
sed -i.bak "s|const CACHE_NAME = '[^']*'|const CACHE_NAME = 'flotopic-${SHORT_SHA}'|" \
  "${FRONTEND}/sw.js"

aws s3 sync "${FRONTEND}/" "s3://${BUCKET}/" --region "${REGION}" \
  --exclude "*" --include "*.html" \
  --content-type "text/html; charset=utf-8" --cache-control "no-cache, must-revalidate"
aws s3 sync "${FRONTEND}/" "s3://${BUCKET}/" --region "${REGION}" \
  --exclude "*" --include "*.js" --exclude "sw.js" \
  --content-type "application/javascript" --cache-control "no-cache, must-revalidate"
aws s3 sync "${FRONTEND}/" "s3://${BUCKET}/" --region "${REGION}" \
  --exclude "*" --include "*.css" \
  --content-type "text/css" --cache-control "no-cache, must-revalidate"
aws s3 cp "${FRONTEND}/sw.js" "s3://${BUCKET}/sw.js" --region "${REGION}" \
  --content-type "application/javascript" --cache-control "no-store, no-cache, must-revalidate"

# 3. CloudFront invalidate
DIST_ID=$(aws cloudfront list-distributions --region us-east-1 \
  --query "DistributionList.Items[?contains(Aliases.Items, 'flotopic.com')].Id" --output text)
aws cloudfront create-invalidation --distribution-id "${DIST_ID}" --paths "/*" --region us-east-1

# 4. 元の main に戻す（detached HEAD を解消）
git switch main
mv "${FRONTEND}/sw.js.bak" "${FRONTEND}/sw.js"  # sed -i のバックアップを戻す
```

> ⚠️ 1-B を打った直後の main は CACHE_NAME が古い SHA に固定される。回復後は **必ず 1-A の `git revert` または前進する fix を push して GH Actions 経由で正規デプロイし直す**。手動 sync は「正本（git）」と「実体（S3）」をズレさせるので、2 サイクル以上引きずらない。

---

## 2. Lambda ロールバック（fetcher / processor / lifecycle / comments / cf-analytics 等）

`aws lambda update-function-code` で前 zip に直接戻せる。GH Actions が動くなら git revert を優先。

### 2-A. 推奨経路: `git revert` → push → deploy-lambdas.yml 自動再デプロイ

```bash
# 1. 直近 24h の lambda 関連 commit を特定
git log --oneline -10 -- 'projects/P003-news-timeline/lambda/**' 'scripts/bluesky_agent.py' 'scripts/_governance_check.py'

# 2. 該当 commit を revert
git revert <BAD_SHA>
git push origin main

# 3. .github/workflows/deploy-lambdas.yml の job を待つ
gh run watch
```

検証:

```bash
# 3-1. processor を手動 invoke して 200 + processed > 0 を確認（軽い試走）
aws lambda invoke --function-name p003-processor \
  --region ap-northeast-1 --invocation-type RequestResponse \
  --payload '{"source":"manual-rollback-verify","limit":1}' /tmp/proc.json
cat /tmp/proc.json | python3 -m json.tool

# 3-2. CloudWatch ログでエラーが収まっているか
aws logs filter-log-events \
  --log-group-name /aws/lambda/p003-processor \
  --region ap-northeast-1 --start-time "$(($(date +%s) * 1000 - 600000))" \
  --filter-pattern "ERROR" --max-items 20
```

### 2-B. 緊急時: 直近の zip を手動で巻き戻す

GH Actions が止まっていて、且つ「直前の動いていた zip がローカルに残っている」「S3 等にビルド成果物のバックアップを置いている」場合のみ：

```bash
# 例: fetcher を直前の動作確認済 zip に戻す
aws lambda update-function-code \
  --function-name p003-fetcher \
  --zip-file fileb://./backup/p003-fetcher-good.zip \
  --region ap-northeast-1
aws lambda wait function-updated \
  --function-name p003-fetcher \
  --region ap-northeast-1
```

> ⚠️ Lambda には version/alias を貼っていない（2026-04-28 時点）ので「2 個前の zip に戻す」は git からビルドし直す以外に手はない。手動で巻き戻したら速やかに git 側も同じ状態に揃え、push で正規ルートに戻すこと。
> ⚠️ T2026-0428-AZ（git tag v1.x.x によるリリース管理）が landing したら、`git checkout v2026.0428.3` で直前の動作確認済コードを取り出して再デプロイできるようになる予定。それまでは git 履歴と CloudWatch ログだけが頼り。

---

## 3. DynamoDB ロールバック（DBスキーマ／品質劣化）

DynamoDB の生データを「巻き戻す」のは原則やらない（PITR 復元は重く、副作用が読みきれない）。代わりに **再処理（quality_heal）で前進的に修復する**。

### 3-A. 標準経路: quality_heal で再処理キューに乗せる

```bash
# 1. dry-run でキュー候補件数を確認
APPLY=0 bash projects/P003-news-timeline/scripts/bulk_heal.sh all

# 2. 安全と判断したら APPLY=1 で pendingAI=True を投入
APPLY=1 bash projects/P003-news-timeline/scripts/bulk_heal.sh all

# 3. processor の 4x/day 自動実行で順次再生成される
#    手動で1サイクル走らせたい場合:
aws lambda invoke --function-name p003-processor \
  --region ap-northeast-1 --invocation-type Event --payload '{}' /tmp/null
```

> 想定: keyPoint 空・schemaVersion 古い・statusLabel 欠落 等の「success-but-empty」修復。
> `update_topic_with_ai` / `update_topic_s3_file` の incremental モードが既存 AI フィールドを上書きしないので、heal を二重に投入しても良い AI 要約は壊れない（T2026-0428-AO で landing 済の物理ガード）。

### 3-B. PITR 復元（最後の手段）

DynamoDB は PITR を有効化していれば 35 日まで戻せるが、本プロジェクトは現在 **PITR 未設定**（コスト都合・2026-04-28 時点）。
有効化が先に必要：

```bash
aws dynamodb update-continuous-backups \
  --table-name <TABLE> --region ap-northeast-1 \
  --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true
```

復元手順は AWS 公式 [Restoring a DynamoDB table to a point in time](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/PointInTimeRecovery.Tutorial.html) を参照。**復元中はテーブル名が変わる**ので、frontend / Lambda の参照を一時的に切り替える / atomic にバックフィルする計画を必ず立てる。これは PR 単発では絶対にやらない。

---

## 4. CloudFront 単独で詰まったとき（5xx・古いキャッシュ持続）

```bash
DIST_ID=$(aws cloudfront list-distributions --region us-east-1 \
  --query "DistributionList.Items[?contains(Aliases.Items, 'flotopic.com')].Id" --output text)
aws cloudfront create-invalidation --distribution-id "${DIST_ID}" --paths "/*" --region us-east-1
```

CloudFront Function（`flotopic-canonical-redirect`）が壊れた疑いがある場合は LIVE stage を 1 つ前のバージョンに戻す：

```bash
# DEVELOPMENT stage で旧コードを put → publish
aws cloudfront update-function ... --function-code fileb://<前のJSファイル> ...
aws cloudfront publish-function --name flotopic-canonical-redirect --if-match <ETag> --region us-east-1
```

---

## 5. ロールバック後の必須アフター（忘れると再発する）

1. **commit message に `Verified: <url>:<status>:<JST>` を必ず付ける**（pre-commit hook がブロック）。
2. **`docs/lessons-learned.md` になぜなぜ Why1〜Why5 を書く**。本ファイルの手順を「使った」なら 1 行追記でも十分（メタ教訓: ロールバック発生は監査対象）。
3. **TASKS.md / WORKING.md を見て、関連する未着手タスクの優先度を引き上げる**。例えば本ファイルが活きた = T2026-0428-AY（branch protection）/ T2026-0428-AZ（git tag）の優先度が一段上がる。
4. **同じ 24h で 2 回以上ロールバックが発生したら main へ直接 push を一時的に止める**。`session_bootstrap.sh` の `[Code]` 並走 ERROR ルール（T2026-0428-BB）と組み合わせて、流入を絞る。

---

## 6. ロールバック禁止事項（やったら更に壊れる）

- ❌ S3 バケットに `aws s3 rm --recursive` を打つ。一度消えた静的 HTML は git push が走るまで戻らない。
- ❌ `aws lambda delete-function`。再作成すると ARN が変わり、CloudWatch / EventBridge / DynamoDB Stream トリガーが切れる。
- ❌ DynamoDB に直接 `delete-item` をかけて「綺麗にしてから再生成」する。`quality_heal` の incremental モードを使う。
- ❌ ロールバックの commit に `[skip ci]` を付ける。CI / 物理ゲートを回避すると Verified 行が抜け、二次事故が起きる。
- ❌ Cowork から `git push --force`。Code セッションの作業を上書き消滅させる。push に失敗したら原因（lock / divergence）を解消してから普通の push を打つ。

---

## 7. 改訂履歴

- 2026-04-28: 初版作成（T2026-0428-BA partial / scheduled-task で起票）。
  - フェーズ1-§B「ロールバック手順の文書化」の完了条件のうち「runbook 本体」のみを landing。
  - 残作業: ① CI に `git revert` または `aws lambda update-function-code` を含むことを物理検査する step を `.github/workflows/ci.yml` に追加（T2026-0428-AX 進行中につき本セッションでは触らない）。② T2026-0428-AZ（git tag）と連動して 2-B の「直前の zip」運用を tag-based に置き換える。
