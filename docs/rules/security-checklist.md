# セキュリティチェックリスト (T2026-0502-SEC-AUDIT 起源・2026-05-02 制定)

PR を作成・review する時に「この変更で攻撃面が広がっていないか？」を確認するチェックリスト。
**毎 PR で必須ではない**が、`lambda/` `frontend/` `.github/workflows/` `deploy*.sh` を触る PR では本ファイルを参照すること。

CLAUDE.md「⚡ 絶対ルール」と統合: 「PII / secrets コード直書き禁止」は本ファイルの ① でカバー。

---

## ① シークレット (Secrets / API Keys / Tokens)

| 観点 | 確認項目 |
|---|---|
| **コード直書き禁止** | `ghp_*` `gho_*` `ghs_*` `ghr_*` `github_pat_*` `xoxb-*` `xoxp-*` `xapp-*` `sk-ant-api03-*` `sk-proj-*` `ntn_*` `secret_*` `AKIA*` のいずれも tracked file に書かない (テストではダミー / 例: `***REDACTED-SEC3***`) |
| **env 経由のみ** | 値は GitHub Secrets / AWS Secrets Manager / `.env` (gitignore 済) のいずれかから読む。コード/READMEには placeholder のみ |
| **gitignore でも危険** | `.git/config` `.claude/settings.local.json` `setup_*.sh` 等の untracked ファイルでも Cowork チャット表示・スクリーン共有・session_info MCP で漏洩する。最初から env で渡す |
| **scanner** | `bash scripts/secret_scan.sh staged` で commit 前に確認。CI `.github/workflows/secret-scan.yml` が PR + push + 週次で git history も含めて scan |
| **rotate 期限** | 漏洩疑いがあれば即 Revoke。「気づいた時点で削除」では足りない (history に残るので外部利用される可能性) |

## ② 認証 (Authentication / Authorization)

| 観点 | 確認項目 |
|---|---|
| **userId を受け取る handler** | `userId` を path / query / body で受け取る handler は **必ず Authorization Bearer `<Google ID token>` を verify_google_token() で検証** し `payload.sub == userId` を強制する (T2026-0502-SEC5/6/7 学習) |
| **GET 系も認証** | 「読み取りだから認証不要」は危険。`/favorites/{userId}` `/history/{userId}` `/analytics/user/{userId}` 等は他人の閲覧履歴・行動傾向 = PII 露出 |
| **client-derived hash で承認しない** | `userHash` のような client が計算した値を承認材料にしない (server で derive する。例: `hash_str(payload.sub)`) |
| **ID トークン有効期限** | `exp` チェックする。`aud` (GOOGLE_CLIENT_ID) も突合 |
| **管理者 endpoint** | `verify_admin_token` で `email_verified` まで確認 (`email` だけでは不十分) |

## ③ 入力検証 (Input Validation)

| 観点 | 確認項目 |
|---|---|
| **URL の検証** | `<a href>` `<img src>` `<iframe>` 等にユーザー由来 URL を入れる時は `safeHref()` / `safeImgUrl()` 経由。`javascript:` `data:` `vbscript:` を `#` に潰す |
| **HTML escape** | innerHTML / template literal に変数を入れる時は `esc()` 必須。textContent で済むものは textContent を優先 |
| **Path traversal** | ファイル名生成は `re.sub(r'[^A-Za-z0-9_\-]', '_', user_id)[:N]` で英数字のみに正規化 |
| **タイプ検証** | DynamoDB に書く値は型検証。Decimal / float / list の混入で書き込み失敗する |
| **長さ制限** | 全ての文字列 input に最大長 (handle 20 / nickname 30 / body 200 等) |
| **regex 制限** | handle/topicId 等は `^[0-9a-f]{16}$` 等の anchored regex で正規化 |

## ④ SSRF / 外部 fetch

| 観点 | 確認項目 |
|---|---|
| **urllib.urlopen 前に is_safe_url** | `lambda/_/url_safety.py` の `is_safe_url(url)` で internal IP (169.254.169.254 / RFC1918 / loopback / multicast) を deny。RSS feed / OGP / 記事本文 fetch すべて (T2026-0502-SEC13 学習) |
| **DNS rebinding** | `is_safe_url` 内で getaddrinfo 結果も IP allowlist でチェック (host 名だけ見て通すと rebinding で内部に流れる) |
| **timeout 短く** | 5-10 秒以内。長時間 hang で攻撃検出を遅らせない |
| **byte 上限** | `resp.read(MAX_BYTES)` で reading 量を制限 |

## ⑤ XML / JSON parse

| 観点 | 確認項目 |
|---|---|
| **defusedxml or 同等** | `xml.etree.ElementTree.fromstring` を直接使わず `parse_xml_safely(content)` (DOCTYPE/ENTITY reject) 経由。billion laughs 攻撃対策 (T2026-0502-SEC14 学習) |
| **JSON 深さ** | `json.loads` は標準で OK だが、多重 nest payload は memory 攻撃の余地あり |

## ⑥ CORS / CSRF

| 観点 | 確認項目 |
|---|---|
| **Allow-Origin は固定値** | `*` 禁止。`https://flotopic.com` + `https://www.flotopic.com` のみ (env で staging 追加可能) (T2026-0502-SEC8 学習) |
| **Vary: Origin** | レスポンスヘッダーに含めて CDN cache poisoning 防止 |
| **Function URL CORS** | deploy.sh の `aws lambda create-function-url-config --cors '{"AllowOrigins":["https://flotopic.com"]}'` も同様に絞る |
| **OPTIONS preflight** | OPTIONS は handler で個別に return resp(200, {}) する |

## ⑦ Rate limit / DoS / コスト爆発

| 観点 | 確認項目 |
|---|---|
| **重要書き込みは fail_closed** | comments POST / contact POST 等の rate-limit は DDB エラー時に通さない (T2026-0502-SEC15 学習) |
| **Lambda concurrency 上限** | deploy.sh の `aws lambda put-function-concurrency --reserved-concurrent-executions N`。fetcher/processor は API 課金あるので 2 〜 5 (T2026-0502-SEC17 学習) |
| **honeypot field** | フォームに `<input name="website">` を hidden で置き、値が入ってたら 200 silently |
| **timeout** | wallclock guard で context.get_remaining_time_in_millis() を見て break |

## ⑧ Error / Logging / 情報露出

| 観点 | 確認項目 |
|---|---|
| **500 で `'detail': str(e)` を返さない** | 内部例外メッセージ (テーブル名・SQL/DDB エラー詳細・スタックトレース) を返さない。CloudWatch には `[ERROR]` プレフィックス付きで残し、user には generic message + requestId のみ (T2026-0502-SEC16 学習) |
| **CloudWatch Logs に PII を書かない** | userId/email を log に書く時は hash 化 (`hash_str()`) |
| **silent print 禁止** | 例外を握り潰す `print(f'... error: {e}')` で済まさず `print(f'[ERROR] ...')` プレフィックス + CloudWatch metric filter 観測対象に追加 |

## ⑨ Frontend (XSS / CSP)

| 観点 | 確認項目 |
|---|---|
| **innerHTML より textContent** | 単純な文字列差し込みは textContent 優先 |
| **template literal は esc() + safeHref** | `${esc(user_input)}` 必須。`<a href="${esc(safeHref(url))}">` パターン |
| **CSP は restrictive** | `'unsafe-inline'` `'unsafe-eval'` 禁止。inline script は外部 .js に分離。CDN は明示 whitelist (現在 SEC12 で対応中) |
| **frame-ancestors** | クリックジャック防御に `frame-ancestors 'self'` (or 'none') |
| **`target="_blank"` には `rel="noopener noreferrer"`** | tab nabbing 防止 |

## ⑩ AWS / インフラ

| 観点 | 確認項目 |
|---|---|
| **IAM 最小権限** | `*FullAccess` ポリシー禁止。Resource ARN を明示。読み取り権限と書き込み権限を分離 |
| **GitHub Actions OIDC** | `secrets.AWS_ACCESS_KEY_ID` 長寿命キー禁止。`aws-actions/configure-aws-credentials@v4` の `role-to-assume:` 形式 (現在 SEC10 で対応予定) |
| **Secrets Manager** | API key / password は Lambda env 平文より Secrets Manager 推奨。env は環境設定 / non-secret config のみ (現在 SEC9 で対応予定) |
| **S3 bucket policy** | `Principal: "*"` の `s3:GetObject` は静的サイト用途に限定。書き込み (`s3:PutObject`) は IAM Role のみ |
| **DynamoDB PITR** | 重要テーブルは Point-in-Time Recovery 有効化。deletion-protection も検討 |

---

## PR チェックリストへの組み込み (推奨)

PR description のフッターに以下を貼ると review 漏れ防止になる:

```markdown
### Security checklist (`docs/rules/security-checklist.md`)
- [ ] secret_scan.sh が green
- [ ] 新規 handler は認証チェックあり (userId を受け取るなら verify_google_token + sub 突合)
- [ ] frontend `<a href>` `<img src>` は safeHref / safeImgUrl 経由
- [ ] urllib.urlopen / 外部 fetch は is_safe_url() 通している
- [ ] xml parse は parse_xml_safely() 経由
- [ ] CORS Allow-Origin は固定値
- [ ] 重要書き込みの rate-limit は fail_closed=True
- [ ] 500 で `'detail': str(e)` を返していない
- [ ] CSP / CORS / IAM 最小権限を退化させていない
```

---

## 既知の未対処項目 (順次解消)

- **SEC1-4**: 漏洩 token rotate (PO 手動操作)
- **SEC9**: ANTHROPIC_API_KEY を AWS Secrets Manager に
- **SEC10**: GitHub Actions OIDC + IAM Role assumption
- **SEC12**: CSP 厳格化 (unsafe-inline 削除)

進捗は `TASKS.md` の `T2026-0502-SEC*` を参照。
