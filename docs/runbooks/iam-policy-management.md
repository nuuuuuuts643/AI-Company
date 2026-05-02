# IAM Policy 管理運用 (T2026-0502-IAM-DEPLOY-FIX 制定・恒久ルール)

## 背景と目的

2026-05-02 SEC10-CODE で OIDC 専用化 (両建て廃止) した時、role policy が AWS console / CLI 直接編集で管理されていたため、移行時に**権限漏れ** (`lambda:GetFunctionConfiguration` 欠落・`events:PutRule` の Resource ARN パターンに `flotopic-*` 不在) が発生。結果:

- Standard role: watchdog が `aws lambda get-function-configuration` で AccessDenied → 4 秒で fail (broken windows)
- Deploy role: deploy-lambdas.yml の bluesky-morning step が `events:PutRule` で `flotopic-bluesky-morning` rule 作成不可 → workflow=failure (Lambda 本体は更新済だが workflow 結論は failure → push の度に false alarm)

**恒久対処**: IAM policy を git tracked source of truth (`infra/iam/policies/*.json`) で管理し、`infra/iam/apply.sh` 経由でのみ AWS に同期する。AWS console 直接編集は禁止 (drift 検出は別途 CI で実装予定)。

## ファイル構成

```
infra/iam/
├── apply.sh                                   # 全 role を JSON 経由で sync
└── policies/
    ├── flotopic-actions-standard.json         # GitHubActionsRole-Flotopic-Standard
    └── flotopic-actions-deploy.json           # GitHubActionsRole-Flotopic-Deploy
```

各 JSON ファイルの先頭に `_meta.role_name` と `_meta.policy_name` を記載。`apply.sh` が `_meta` を strip して `aws iam put-role-policy` に渡す。

## 変更フロー (恒久ルール・例外なし)

1. **policy JSON を編集**
   - 例: `infra/iam/policies/flotopic-actions-deploy.json` の Statement に追加 / Resource に ARN パターン追加
   - Sid は **英数字のみ** (AWS の制約・ハイフン/アンダースコア不可)

2. **PR を作成**
   - `cowork_commit.py` または通常の `gh pr create`
   - PR description に「IAM 変更 (どの role に何を許可・なぜ)」を明記
   - reviewer は権限拡大の妥当性を判断

3. **PR merge 後に apply**
   - `bash infra/iam/apply.sh`
   - apply.sh は既存 policy との diff を取り、変更なしなら skip
   - 変更ありなら `aws iam put-role-policy` 実行

4. **検証**
   - 該当 workflow を試験的に dispatch して green を確認
   - もしくは次の自然な PR で deploy chain が success することを確認

## 禁止事項

- **AWS console / CLI 直接編集の禁止** (drift 検出が後手になる・git に痕跡が残らない)
- **Sid に英数字以外**を入れること (AWS が reject)
- **Resource: "\*"** の安易な使用 (権限拡大は最小限・ARN パターンを限定する)
- **複数 role に同一 Action を重複登録** (どこで誰が動いてるか特定困難になる)

## drift 検出 (将来 CI 化候補)

`apply.sh --dry-run` で diff を出力。CI 化した場合:
- 毎日 / 週次で `apply.sh --dry-run` を実行し、diff があれば Slack alert
- diff があれば「console 直接編集 or apply 漏れ」を疑い、git source を真と見なして再 apply するか、git を実態に合わせる PR を出す

## 横展開 (T2026-0502-IAM-DEPLOY-FIX 由来の lessons-learned 横展開チェックリスト)

- [x] Standard role に `lambda:GetFunctionConfiguration` 追加 (watchdog 復活)
- [x] Deploy role の EventBridgeRules Resource に `flotopic-*` 追加 (bluesky-morning step 修復)
- [x] `infra/iam/policies/*.json` を git tracked source of truth 化
- [x] `infra/iam/apply.sh` で AWS 側に sync する手順を整備
- [ ] CI で drift 検出 (`apply.sh --dry-run` 結果が空でなければ alert) を実装 (別タスク化候補)
- [ ] 他 OIDC role (将来追加分) でも同じ pattern を踏襲

## 関連

- T2026-0502-SEC10-CODE: OIDC 専用化 (今回 fix の発端)
- T2026-0502-WATCHDOG-FIX: watchdog 偽陽性対処 (本件と並列対処)
- `docs/runbooks/oidc-migration-phased.md`: OIDC 移行 phased plan
- `docs/lessons-learned.md`: SEC10 OIDC 移行漏れの why1-5
