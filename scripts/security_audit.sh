#!/usr/bin/env bash
# security_audit.sh — flotopic / ai-company 全体セキュリティ監査
# 使い方: bash scripts/security_audit.sh [pii|secrets|aws|all]
# 問題検知時: exit 1 で終了 (GitHub Actions を赤にする)
# 結果は AUDIT_LOG_BUCKET (env var) に JSON 保存 (設定時のみ)
# 監査結果・ログに個人情報を含めない

set -euo pipefail

MODE="${1:-all}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
EXIT_CODE=0
FINDINGS=()

# ────────────────────────────────────────────────────────────────
# ユーティリティ
# ────────────────────────────────────────────────────────────────
log_ok()   { echo "  ✅ $*"; }
log_warn() { echo "  ⚠️  $*"; FINDINGS+=("$*"); EXIT_CODE=1; }
log_info() { echo "  ℹ️  $*"; }

section() { echo ""; echo "═══ $* ═══"; }

# ────────────────────────────────────────────────────────────────
# A. PII スキャン
# ────────────────────────────────────────────────────────────────
audit_pii() {
  section "A. PII スキャン（コード内個人情報）"

  # A1. 個人名パターン（git-tracked な全ファイル — docs/script/ops/proposals 等も含む）
  log_info "A1. 個人名パターンを git-tracked 全ファイルでスキャン中..."
  cd "$REPO_ROOT"
  PII_FILES=$(git ls-files 2>/dev/null \
    | xargs grep -lE "(n[a]oya|mr[k]m|m[u]rakaminaoya|村上)" 2>/dev/null \
    | grep -v "^scripts/security_audit\.sh$" \
    | grep -v "^\.github/workflows/security-audit\.yml$" \
    | grep -v "^\.github/workflows/ci\.yml$" \
    | grep -v "^done\.sh$" \
    | grep -v "^HISTORY\.md$" \
    || true)
  PII_HITS=$(echo -n "$PII_FILES" | grep -c '^' || true)

  if [ "$PII_HITS" -gt 0 ]; then
    # 件数のみ報告（内容をログに出さない）
    log_warn "A1: 個人名パターン $PII_HITS 件のファイルで検出（git-tracked 全体スキャン）"
    echo "$PII_FILES" | head -20 | sed 's/^/     /'
  else
    log_ok "A1: 個人名パターン 検出なし"
  fi

  # A2. メールアドレスがフロントエンドHTMLにハードコードされていないか
  log_info "A2. フロントエンド HTML のメールアドレスハードコードをチェック..."
  EMAIL_HITS=$(grep -rn \
    --include="*.html" \
    -E "[a-zA-Z0-9._%+\-]+@(gmail|yahoo|hotmail|outlook|icloud)\.com" \
    "$REPO_ROOT/projects" \
    --exclude-dir=".git" \
    2>/dev/null | wc -l)

  if [ "$EMAIL_HITS" -gt 0 ]; then
    log_warn "A2: フロントエンドHTMLにメールアドレスパターン $EMAIL_HITS 件検出"
    grep -rn \
      --include="*.html" \
      -E "[a-zA-Z0-9._%+\-]+@(gmail|yahoo|hotmail|outlook|icloud)\.com" \
      "$REPO_ROOT/projects" \
      --exclude-dir=".git" \
      2>/dev/null | \
      sed 's/[a-zA-Z0-9._%+\-]*@[a-zA-Z0-9.\-]*\.[a-zA-Z]*/[EMAIL_REDACTED]/g' | head -10 || true
  else
    log_ok "A2: フロントエンドHTML メールアドレスハードコード 検出なし"
  fi

  # A3. AWS アカウントID（12桁数字）露出チェック
  log_info "A3. AWSアカウントID（12桁）のコード露出をチェック..."
  AWSID_HITS=$(grep -rn \
    --include="*.py" --include="*.js" --include="*.html" --include="*.yml" --include="*.yaml" \
    -E '[^0-9][0-9]{12}[^0-9]' \
    "$REPO_ROOT" \
    --exclude-dir=".git" \
    --exclude-dir="node_modules" \
    2>/dev/null | \
    grep -v "security_audit.sh\|security-audit.yml\|HISTORY\|TASKS\|\.md:" | \
    wc -l)

  if [ "$AWSID_HITS" -gt 0 ]; then
    log_warn "A3: 12桁数字パターン $AWSID_HITS 件（AWSアカウントIDの可能性）。要確認"
    grep -rn \
      --include="*.py" --include="*.js" --include="*.html" --include="*.yml" --include="*.yaml" \
      -E '[^0-9][0-9]{12}[^0-9]' \
      "$REPO_ROOT" \
      --exclude-dir=".git" \
      --exclude-dir="node_modules" \
      2>/dev/null | \
      grep -v "security_audit.sh\|security-audit.yml\|HISTORY\|TASKS\|\.md:" | \
      sed 's/[0-9]\{12\}/[AWSID_REDACTED]/g' | head -10 || true
  else
    log_ok "A3: AWSアカウントIDパターン 検出なし"
  fi
}

# ────────────────────────────────────────────────────────────────
# B. シークレット漏洩スキャン
# ────────────────────────────────────────────────────────────────
audit_secrets() {
  section "B. シークレット漏洩スキャン"

  # B1. 危険なキーパターン（値はログに出さない）
  log_info "B1. APIキー・パスワードパターンをスキャン中..."
  SECRET_HITS=$(grep -rn \
    --include="*.py" --include="*.js" --include="*.html" --include="*.yml" --include="*.yaml" --include="*.json" \
    -E "(ANTHROPIC_API_KEY|BLUESKY_PASSWORD|sk-ant-api03|sk-ant-[a-zA-Z0-9])" \
    "$REPO_ROOT" \
    --exclude-dir=".git" \
    --exclude-dir="node_modules" \
    2>/dev/null | \
    grep -v '"\${{' | grep -v "^.*#.*SECRET\|^.*#.*EXAMPLE\|security_audit\|security-audit" | \
    wc -l)

  if [ "$SECRET_HITS" -gt 0 ]; then
    log_warn "B1: シークレットキーパターン $SECRET_HITS 件検出（値は非表示）"
    grep -rn \
      --include="*.py" --include="*.js" --include="*.html" --include="*.yml" --include="*.yaml" --include="*.json" \
      -E "(ANTHROPIC_API_KEY|BLUESKY_PASSWORD|sk-ant-api03|sk-ant-[a-zA-Z0-9])" \
      "$REPO_ROOT" \
      --exclude-dir=".git" \
      --exclude-dir="node_modules" \
      2>/dev/null | \
      grep -v '"\${{' | grep -v "security_audit\|security-audit" | \
      sed 's/=.*/=[REDACTED]/g' | sed "s/'[^']*'/'[REDACTED]'/g" | head -10 || true
  else
    log_ok "B1: APIキー・パスワードパターン 検出なし"
  fi

  # B2. gitleaks / truffleHog による git history スキャン
  log_info "B2. git history シークレットスキャン..."
  if command -v gitleaks &>/dev/null; then
    if gitleaks detect --source "$REPO_ROOT" --redact --no-git 2>&1 | grep -q "leaks found"; then
      log_warn "B2: gitleaks でシークレット検出"
      EXIT_CODE=1
    else
      log_ok "B2: gitleaks スキャン クリア"
    fi
  elif command -v trufflehog &>/dev/null; then
    TRUFFLEHOG_OUT=$(trufflehog filesystem "$REPO_ROOT" --only-verified 2>&1 | grep -c "Found" || true)
    if [ "${TRUFFLEHOG_OUT:-0}" -gt 0 ]; then
      log_warn "B2: trufflehog で $TRUFFLEHOG_OUT 件検出"
    else
      log_ok "B2: trufflehog スキャン クリア"
    fi
  else
    log_info "B2: gitleaks/trufflehog 未インストール。パターンスキャンのみ実施"
  fi
}

# ────────────────────────────────────────────────────────────────
# C. S3 バケットポリシー確認
# ────────────────────────────────────────────────────────────────
audit_aws() {
  section "C. S3 バケットポリシー確認"

  if ! command -v aws &>/dev/null; then
    log_info "C: AWS CLI 未インストール。スキップ"
    return
  fi

  log_info "C1. flotopic-* バケットのパブリックアクセスブロック設定を確認..."
  BUCKETS=$(aws s3api list-buckets --query 'Buckets[].Name' --output text 2>/dev/null || echo "")

  if [ -z "$BUCKETS" ]; then
    log_info "C: バケット一覧取得失敗 (権限不足 or 認証情報なし)"
    return
  fi

  for bucket in $BUCKETS; do
    BLOCK=$(aws s3api get-public-access-block --bucket "$bucket" \
      --query 'PublicAccessBlockConfiguration' 2>/dev/null || echo "null")

    if echo "$bucket" | grep -q "^flotopic-"; then
      # flotopic-* は静的ホスティング用なのでパブリック読み取りが意図通り
      log_ok "C1 [$bucket]: flotopic-* バケット（パブリック配信意図あり）"
    else
      # その他バケットはパブリックでないことを確認
      BLOCK_ALL=$(echo "$BLOCK" | python3 -c \
        "import sys,json; d=json.load(sys.stdin); print(all(d.get(k) for k in ['BlockPublicAcls','BlockPublicPolicy','IgnorePublicAcls','RestrictPublicBuckets']))" \
        2>/dev/null || echo "false")
      if [ "$BLOCK_ALL" = "True" ]; then
        log_ok "C2 [$bucket]: パブリックアクセスブロック 全項目 ON"
      else
        log_warn "C2 [$bucket]: パブリックアクセスブロックが一部 OFF の可能性"
      fi
    fi
  done

  # ────────────────────────────────────────────────────────────
  section "D. Lambda 設定確認"

  log_info "D1. Lambda の env vars に ADMIN_EMAIL キーが存在するか確認..."
  FUNCTIONS=$(aws lambda list-functions --query 'Functions[].FunctionName' --output text 2>/dev/null || echo "")

  if [ -z "$FUNCTIONS" ]; then
    log_info "D: Lambda 一覧取得失敗 (権限不足 or 認証情報なし)"
    return
  fi

  for fn in $FUNCTIONS; do
    # 値は取得せず、キー存在確認のみ
    ENV_KEYS=$(aws lambda get-function-configuration --function-name "$fn" \
      --query 'Environment.Variables' 2>/dev/null | \
      python3 -c "import sys,json; d=json.load(sys.stdin); print(list(d.keys()) if d else [])" \
      2>/dev/null || echo "[]")

    if echo "$fn" | grep -qiE "admin|auth"; then
      if echo "$ENV_KEYS" | grep -q "ADMIN_EMAIL"; then
        log_ok "D1 [$fn]: ADMIN_EMAIL キー 存在確認"
      else
        log_warn "D1 [$fn]: ADMIN_EMAIL キーが Lambda env vars に見つかりません"
      fi
    fi

    # D2. IAMロールの * リソースポリシーチェック
    ROLE=$(aws lambda get-function-configuration --function-name "$fn" \
      --query 'Role' --output text 2>/dev/null || echo "")
    if [ -n "$ROLE" ]; then
      ROLE_NAME=$(basename "$ROLE")
      POLICIES=$(aws iam list-role-policies --role-name "$ROLE_NAME" \
        --query 'PolicyNames' --output text 2>/dev/null || echo "")
      for policy in $POLICIES; do
        POLICY_DOC=$(aws iam get-role-policy --role-name "$ROLE_NAME" \
          --policy-name "$policy" 2>/dev/null || echo "{}")
        STAR_RESOURCE=$(echo "$POLICY_DOC" | \
          python3 -c "import sys,json; doc=json.load(sys.stdin); stmts=doc.get('PolicyDocument',{}).get('Statement',[]); print(any(s.get('Resource')=='*' and s.get('Effect')=='Allow' for s in stmts))" \
          2>/dev/null || echo "False")
        if [ "$STAR_RESOURCE" = "True" ]; then
          log_warn "D2 [$fn / $policy]: Resource '*' + Effect 'Allow' 検出。最小権限見直しを推奨"
        fi
      done
    fi
  done

  # ────────────────────────────────────────────────────────────
  section "E. CloudFront / API Gateway 確認"

  log_info "E1. API Gateway CORS 設定確認..."
  APIS=$(aws apigatewayv2 get-apis --query 'Items[].ApiId' --output text 2>/dev/null || echo "")
  for api in $APIS; do
    CORS=$(aws apigatewayv2 get-api --api-id "$api" \
      --query 'CorsConfiguration.AllowOrigins' 2>/dev/null || echo "[]")
    if echo "$CORS" | grep -q '"*"'; then
      log_warn "E1 [API $api]: CORS AllowOrigins に '*' が設定されています"
    else
      log_ok "E1 [API $api]: CORS ワイルドカード '*' なし"
    fi
  done

  log_info "E2. CloudFront ディストリビューションの HTTPS 強制確認..."
  DISTS=$(aws cloudfront list-distributions \
    --query 'DistributionList.Items[].Id' --output text 2>/dev/null || echo "")
  for dist in $DISTS; do
    VIEWER_PROTO=$(aws cloudfront get-distribution-config --id "$dist" \
      --query 'DistributionConfig.DefaultCacheBehavior.ViewerProtocolPolicy' \
      --output text 2>/dev/null || echo "unknown")
    if [ "$VIEWER_PROTO" = "redirect-to-https" ] || [ "$VIEWER_PROTO" = "https-only" ]; then
      log_ok "E2 [CF $dist]: HTTPS 強制設定あり ($VIEWER_PROTO)"
    elif [ "$VIEWER_PROTO" = "allow-all" ]; then
      log_warn "E2 [CF $dist]: HTTPS 非強制 (allow-all)。redirect-to-https に変更推奨"
    fi
  done

  # ────────────────────────────────────────────────────────────
  section "F. SES 送信権限ドリフト確認 (T2026-0502-S)"
  # 経緯: 2026-04-26 13:13 JST に p003-contact が ses:SendEmail で AccessDenied
  # (ADMIN_EMAIL identity ARN が p003-ses-send-policy の Resource に欠けていた)。
  # その後 policy 修正済だが、再発防止として両 identity ARN が常に含まれるか CI で観測する。

  log_info "F1. p003-ses-send-policy が想定 identity ARN を網羅しているか..."
  # 想定: FROM_EMAIL のドメイン identity (flotopic.com) と TO/ADMIN identity (mrkm 個人 gmail) の両方
  EXPECTED_IDENTITIES=("flotopic.com" "mrkm.naoya643@gmail.com")
  POLICY_DOC=$(aws iam get-role-policy --role-name p003-lambda-role \
    --policy-name p003-ses-send-policy 2>/dev/null || echo "{}")
  if [ "$POLICY_DOC" = "{}" ]; then
    log_warn "F1: p003-ses-send-policy が取得できません (policy 名変更 or role 削除の可能性)"
  else
    for ident in "${EXPECTED_IDENTITIES[@]}"; do
      MATCH=$(echo "$POLICY_DOC" | python3 -c "
import sys, json
doc = json.load(sys.stdin).get('PolicyDocument', {})
target = sys.argv[1]
found = False
for s in doc.get('Statement', []):
    if 'ses:SendEmail' not in (s.get('Action') or []) and s.get('Action') != 'ses:SendEmail':
        continue
    res = s.get('Resource') or []
    if isinstance(res, str): res = [res]
    if any(target in r for r in res):
        found = True
        break
print('YES' if found else 'NO')
" "$ident" 2>/dev/null || echo "ERR")
      if [ "$MATCH" = "YES" ]; then
        log_ok "F1 [$ident]: p003-ses-send-policy.Resource に含まれる"
      else
        log_warn "F1 [$ident]: p003-ses-send-policy.Resource に含まれない (再発リスク)"
      fi
    done
  fi

  log_info "F2. SES Production Access / Sandbox 状態..."
  SES_ACCT=$(aws sesv2 get-account --region us-east-1 2>/dev/null || echo "{}")
  PROD=$(echo "$SES_ACCT" | python3 -c \
    "import sys,json; d=json.load(sys.stdin); print(d.get('ProductionAccessEnabled', False))" 2>/dev/null || echo "False")
  ENF=$(echo "$SES_ACCT" | python3 -c \
    "import sys,json; d=json.load(sys.stdin); print(d.get('EnforcementStatus', 'UNKNOWN'))" 2>/dev/null || echo "UNKNOWN")
  if [ "$PROD" = "True" ] && [ "$ENF" = "HEALTHY" ]; then
    log_ok "F2: SES Production Access GRANTED / EnforcementStatus=HEALTHY"
  else
    log_warn "F2: SES Production=$PROD EnforcementStatus=$ENF (送信不可リスク)"
  fi

  log_info "F3. flotopic.com identity が SES で Verified か..."
  VERIF=$(aws ses get-identity-verification-attributes \
    --identities flotopic.com --region us-east-1 2>/dev/null | python3 -c \
    "import sys,json; d=json.load(sys.stdin); print(d.get('VerificationAttributes',{}).get('flotopic.com',{}).get('VerificationStatus','Unknown'))" \
    2>/dev/null || echo "Unknown")
  if [ "$VERIF" = "Success" ]; then
    log_ok "F3: flotopic.com identity Verified"
  else
    log_warn "F3: flotopic.com identity = $VERIF (send-email が失敗する)"
  fi
}

# ────────────────────────────────────────────────────────────────
# 結果集計 & 出力
# ────────────────────────────────────────────────────────────────
summarize() {
  echo ""
  echo "═══════════════════════════════════════"
  echo "監査完了: $TIMESTAMP"
  if [ ${#FINDINGS[@]} -eq 0 ]; then
    echo "✅ 全項目クリア（問題なし）"
  else
    echo "🚨 ${#FINDINGS[@]} 件の問題が検出されました:"
    for f in "${FINDINGS[@]}"; do
      echo "  - $f"
    done
  fi
  echo "═══════════════════════════════════════"

  # S3 監査ログ保存（環境変数 AUDIT_LOG_BUCKET が設定されている場合）
  if [ -n "${AUDIT_LOG_BUCKET:-}" ]; then
    RESULT_JSON=$(python3 -c "
import json, sys
findings = sys.argv[1:]
status = 'PASS' if not findings else 'FAIL'
print(json.dumps({
  'timestamp': '$TIMESTAMP',
  'status': status,
  'finding_count': len(findings),
  'findings': findings,
  'mode': '$MODE'
}))
" "${FINDINGS[@]:-}" 2>/dev/null || echo '{"status":"ERROR","timestamp":"'"$TIMESTAMP"'"}')

    aws s3 cp - "s3://${AUDIT_LOG_BUCKET}/security-audit/$(date -u +%Y/%m/%d)/audit-${TIMESTAMP}.json" \
      --content-type application/json <<< "$RESULT_JSON" 2>/dev/null && \
      echo "📦 監査結果を s3://${AUDIT_LOG_BUCKET} に保存しました" || \
      echo "⚠️  S3 保存失敗（ログはActions上に残ります）"
  fi
}

# ────────────────────────────────────────────────────────────────
# メイン
# ────────────────────────────────────────────────────────────────
echo "🔍 flotopic セキュリティ監査開始 — モード: $MODE — $TIMESTAMP"

case "$MODE" in
  pii)     audit_pii ;;
  secrets) audit_secrets ;;
  aws)     audit_aws ;;
  all)     audit_pii; audit_secrets; audit_aws ;;
  *)       echo "使い方: $0 [pii|secrets|aws|all]"; exit 2 ;;
esac

summarize
exit $EXIT_CODE
