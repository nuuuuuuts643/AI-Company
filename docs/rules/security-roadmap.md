# セキュリティ成熟度ロードマップ (T2026-0502-SEC-AUDIT 由来・2026-05-02 制定)

> **目的**: T2026-0502-SEC-AUDIT で見つけた脆弱性の恒久対処と、その先の組織的セキュリティ成熟度を段階的に上げる長期計画。
> **更新タイミング**: 各レベル完了時 + 四半期 review (PM Claude) + 重大脆弱性発覚時。

---

## 全体像: 4 レベル成熟度

```
レベル 1 (基本): 直接的脆弱性ゼロ                         ← ✅ 2026-05-02 完了
        ↓
レベル 2 (構造的): 長寿命 secret 全廃                    ← 🟡 SEC10-CODE/KEY-DELETE 完了で達成
        ↓
レベル 3 (defense in depth): CSP enforce + history clean ← 🟡 SEC12 part 2 + SEC3 完了で達成
        ↓
レベル 4 (組織的): rotation 自動化 + 定期 audit          ← 🔵 未着手
```

各レベルは **下位レベルが完了していなくても並行で進められる**が、優先度はレベル順。

---

## レベル 1 (基本): 直接的脆弱性ゼロ ✅ 完了 (2026-05-02)

| 内容 | 状態 |
|---|---|
| 漏洩 token 全 rotate (Anthropic / Slack / GitHub PAT × 2 / Notion) | ✅ |
| 認証欠落 fix (avatar / like / IDOR) | ✅ |
| XSS / SSRF / XXE 物理 block | ✅ |
| 物理 secret scanner (pre-commit + CI 週次) | ✅ |
| CORS 統一 (`*` → flotopic.com) | ✅ |
| Rate-limit fail-closed (重要書き込み) | ✅ |
| 500 内部例外メッセージ漏洩抑制 | ✅ |
| Lambda concurrency 制限の網羅 | ✅ |
| Secrets Manager 移行 (SEC9) | ✅ |
| CSP 部分強化 (object-src/base-uri/form-action + frame-ancestors) | ✅ |
| OIDC pilot (1 workflow) | ✅ |

**到達**: 攻撃面が現状で塞がれている = 脆弱性スキャナーが赤を出さない状態。

---

## レベル 2 (構造的): 長寿命 secret 全廃 🟡 進行中

### 達成条件
- 全 GitHub Actions が OIDC + IAM Role assumption (短期 token) のみ
- 長寿命 AWS access key が IAM から **物理削除**
- GitHub Secrets から `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` も削除

### 残タスク
| ID | 内容 | 担当 | 期限 |
|---|---|---|---|
| `T2026-0502-SEC10-CODE` | 残り 9 workflow を OIDC 化 | Code セッション 1 件 | 1 週間以内 |
| `T2026-0502-SEC10-KEY-DELETE` | 旧 access key を deactivate→delete | PO 30 分 | SEC10-CODE 完了 + 1 週間後 |

### 完了判定
```bash
grep -rE "secrets\.AWS_ACCESS_KEY_ID" .github/workflows/    # → 0 件
aws sts get-caller-identity   # 旧 key で → 401
```

---

## レベル 3 (defense in depth): CSP enforce + history clean 🟡 計画あり

### 達成条件
- CSP `unsafe-inline` / `unsafe-eval` 完全削除 (XSS が万一注入されても browser が物理 block)
- git history から旧 token 痕跡完全消去 (fork / cache 経由でも閲覧不可)

### 残タスク
| ID | 内容 | 担当 | 期限 |
|---|---|---|---|
| `T2026-0502-SEC12-PART2` | inline script 全分離 + `unsafe-inline` 削除 + 2 週間 report-only 観察 | Code セッション 1 件 + 観察 | 2026-05-23 |
| `T2026-0502-SEC3` | git filter-repo で旧 token 痕跡消去 + force-push | PO 30〜60 分 | 2026-05-16 (緊急性低) |

### 完了判定
- CSP meta から `'unsafe-inline'` `'unsafe-eval'` の文字列が grep で 0 件
- `git log --all -p | grep -cE 'ghp_LyAq|ghp_JPS5|...'` が 0
- chrome devtools で CSP violation 0 件

---

## レベル 4 (組織的): rotation 自動化 + 定期 audit 🔵 未着手

### 達成条件
- API key の自動 rotation (Lambda 経由・90 日毎)
- 依存脆弱性 scan の CI 統合 + dependabot
- SBOM 生成 + CVE 自動監視
- インシデント対応 runbook
- 年 1 ペネトレーションテスト
- ログ監査 (CloudTrail 異常検知)

### タスク (新規起票)
| ID | 内容 | 工数 | 効果 |
|---|---|---|---|
| `T2026-0502-SEC-L4-ROTATE` | Anthropic API key の Lambda 経由 90 日 auto rotate (Secrets Manager の RotateSecret + Lambda function) | Code 半日 + AWS Lambda function 新設 | 手動 rotate 忘れ防止 |
| `T2026-0502-SEC-L4-DEPS` | npm audit / pip audit を CI に統合 + 高 severity 検出時 PR block | Code 1〜2 時間 | 依存脆弱性の自動検知 |
| `T2026-0502-SEC-L4-DEPENDABOT` | GitHub Dependabot 有効化 (Settings → Code security → Dependabot) | PO 5 分 | 週次の依存更新 PR 自動生成 |
| `T2026-0502-SEC-L4-SBOM` | SBOM (CycloneDX 形式) 生成 + GitHub の dependency graph で CVE 監視 | Code 1〜2 時間 | 漏れなき依存把握 |
| `T2026-0502-SEC-L4-INCIDENT-RUNBOOK` | `docs/runbooks/incident-response.md` 新設 — token 漏洩時 / 不正アクセス疑い時の手順 (rotate → revoke → log 解析 → 通知 → 事後 review) | PO + Cowork 半日 | 緊急時の判断速度向上 |
| `T2026-0502-SEC-L4-PENTEST` | 年 1 回の ペネトレーションテスト (外部委託 or OWASP ZAP 自動 DAST 統合) | PO 数時間 + 外部費用 (or Code セッションで OWASP ZAP CI 統合) | 自分で気づけない脆弱性発見 |
| `T2026-0502-SEC-L4-CT-AUDIT` | CloudTrail logs を週次集計 — 異常 access pattern (大量 GetSecretValue / 深夜の AssumeRole 連発 / 未知 IP からのアクセス) を Slack 通知 | Code 1 日 + Lambda + EventBridge | 攻撃の早期検知 |
| `T2026-0502-SEC-L4-AWARENESS` | OWASP Top 10 / CWE / 最新攻撃手法を四半期で review → 必要なら secret_scan.sh の pattern 更新 / docs/rules/security-checklist.md 改訂 | PM Claude 四半期 1 回 | scanner pattern の継続更新 |

---

## 月次 / 四半期 メンテナンス

| 頻度 | 項目 | 担当 |
|---|---|---|
| **週次** (自動・既設定) | secret-scan.yml が git history 全 scan (月曜 02:00 UTC) | CI |
| **月次** (任意) | `docs/rules/security-checklist.md` を直近 1 ヶ月の incident に基づき改訂 | PM Claude |
| **月次** | 新規 token 種類 (例: 新規連携サービス) を `scripts/secret_scan.sh` の pattern に追加 | PM Claude |
| **四半期** | 本ファイル (security-roadmap.md) の進捗 review + 残タスクの再優先付け | PM Claude |
| **四半期** | OWASP Top 10 の最新版を読み、本プロジェクトの該当リスクを `docs/lessons-learned.md` に追記 | PM Claude |
| **半年** | TASKS.md `T2026-0502-SEC-L4-*` の Eval-Due review | PM Claude |
| **年次** | ペネトレーションテスト or 自動 DAST 結果 review | PO + PM Claude |

---

## 進捗トラッキング

このファイルの「残タスク」セクションは TASKS.md の T2026-0502-SEC* および T2026-0502-SEC-L4-* と連動。各タスクが完了したら:

1. TASKS.md のエントリーを取消線
2. 本ファイルの該当行を ✅ に更新
3. 全レベル完了時は新レベルへの移行を CEO Claude が宣言 (`docs/system-status.md` に記録)

---

## 参考

- T2026-0502-SEC-AUDIT 由来 (`docs/lessons-learned.md` 該当セクション)
- 物理ガード一覧: `docs/rules/security-checklist.md`
- runbook 集: `docs/runbooks/{secrets-manager-migration,github-actions-oidc-migration,git-history-rewrite-secrets}.md`
