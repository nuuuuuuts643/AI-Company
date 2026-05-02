#!/bin/bash
# T2026-0502-IAM-FILTER-FIX 物理ガード回帰テスト
# scripts/install_hooks.sh が生成する pre-commit hook の IAM filter について
# (1) 真陽性: 非 exempt ファイル (lambda/*.py 等) に `aws iam put-role-policy` を含めると reject すること
# (2) 偽陰性ガード: 上記が必ず exit 1 で reject されること (誤って通過させない)
# (3) 偽陽性ガード: exempt ファイル (*.md / scripts/install_hooks.sh / infra/iam/apply.sh / tests/) では同じ文字列を含めても通過すること
# 失敗条件: いずれかが期待と逆の結果になる。
# CI 連携: .github/workflows/ci.yml から呼ばれる。

set -e
set -o pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INSTALL_HOOKS="$REPO_ROOT/scripts/install_hooks.sh"

if [ ! -f "$INSTALL_HOOKS" ]; then
    echo "FAIL: install_hooks.sh が見つかりません: $INSTALL_HOOKS"
    exit 1
fi

# install_hooks.sh の pre-commit ヒアドキュメント部分を抜き出して
# 一時 git repo に install して挙動を検証する。
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

cd "$TMP_DIR"
git init -q
git config user.email "test@local"
git config user.name "test"
git config commit.gpgsign false

# pre-commit hook をインストール (install_hooks.sh の内容を実行)
mkdir -p .git/hooks
# install_hooks.sh は cd $(dirname $0)/.. するので、scripts/ 配下に置く必要がある
mkdir -p scripts
cp "$INSTALL_HOOKS" scripts/install_hooks.sh
# install_hooks.sh が依存する check_section_sync.sh などを stub 化 (本テストは IAM filter のみ検証)
cat > scripts/check_section_sync.sh <<'STUB'
#!/bin/bash
exit 0
STUB
chmod +x scripts/check_section_sync.sh
# install を走らせて hook を配置
bash scripts/install_hooks.sh >/dev/null 2>&1 || true
if [ ! -x .git/hooks/pre-commit ]; then
    echo "FAIL: install_hooks.sh が pre-commit hook を配置しませんでした"
    exit 1
fi

# === Case 1: 偽陽性ガード - *.md ファイル内のドキュメント引用は通過すべき ===
mkdir -p docs
cat > docs/lessons-learned.md <<'EOF'
## なぜなぜ
PR #285 で `aws iam put-role-policy --policy-document` を直接実行した。
EOF
git add docs/lessons-learned.md
if .git/hooks/pre-commit >/dev/null 2>&1; then
    echo "PASS [Case 1]: *.md 内の \`aws iam put-role-policy\` 引用は通過 (期待通り)"
else
    echo "FAIL [Case 1]: *.md 内のドキュメント引用が誤って block された (false positive)"
    .git/hooks/pre-commit 2>&1 | head -5 | sed 's/^/   /'
    exit 1
fi
git rm -q --cached docs/lessons-learned.md

# === Case 2: 偽陽性ガード - tests/ 配下の fixture は通過すべき ===
mkdir -p tests
cat > tests/test_iam_fixture.sh <<'EOF'
#!/bin/bash
# fixture: aws iam put-role-policy のテストデータ
echo "aws iam put-role-policy --role-name x --policy-document file://x.json"
EOF
git add tests/test_iam_fixture.sh
if .git/hooks/pre-commit >/dev/null 2>&1; then
    echo "PASS [Case 2]: tests/ fixture 内の \`aws iam put-role-policy\` は通過 (期待通り)"
else
    echo "FAIL [Case 2]: tests/ fixture が誤って block された (false positive)"
    exit 1
fi
git rm -q --cached tests/test_iam_fixture.sh

# === Case 3: 偽陽性ガード - infra/iam/apply.sh 自体は通過すべき ===
mkdir -p infra/iam
cat > infra/iam/apply.sh <<'EOF'
#!/bin/bash
# 唯一の正しい put-role-policy 経路
aws iam put-role-policy --role-name "$ROLE" --policy-document "file://$JSON"
EOF
git add infra/iam/apply.sh
if .git/hooks/pre-commit >/dev/null 2>&1; then
    echo "PASS [Case 3]: infra/iam/apply.sh 自体は通過 (期待通り)"
else
    echo "FAIL [Case 3]: infra/iam/apply.sh が誤って block された (false positive)"
    exit 1
fi
git rm -q --cached infra/iam/apply.sh

# === Case 4: 真陽性 - 非 exempt な production shell script は block すべき ===
# 注: regex は shell-style `aws iam put-role-policy` 文字列にマッチする設計のため、
# Python の subprocess.run([list]) 形式 (要素が分割される) は対象外 (元来の設計通り)。
mkdir -p scripts
cat > scripts/some_iam_script.sh <<'EOF'
#!/bin/bash
# ← これは違反 (apply.sh 経由でなく直接呼んでいる)
aws iam put-role-policy --role-name x --policy-document file://x.json
EOF
git add scripts/some_iam_script.sh
if .git/hooks/pre-commit >/dev/null 2>&1; then
    echo "FAIL [Case 4]: 非 exempt な scripts/some_iam_script.sh の違反パターンを通過させた (false negative・物理ガード破綻)"
    exit 1
else
    echo "PASS [Case 4]: scripts/some_iam_script.sh の \`aws iam put-role-policy\` は block (期待通り)"
fi
git rm -q --cached scripts/some_iam_script.sh

# === Case 5: 真陽性 - 非 exempt な workflow YAML は block すべき ===
mkdir -p .github/workflows
cat > .github/workflows/some-workflow.yml <<'EOF'
name: Some Workflow
on: workflow_dispatch
jobs:
  apply:
    runs-on: ubuntu-latest
    steps:
      - run: aws iam put-role-policy --role-name x --policy-document file://x.json
EOF
git add .github/workflows/some-workflow.yml
if .git/hooks/pre-commit >/dev/null 2>&1; then
    echo "FAIL [Case 5]: workflow YAML 内の違反パターンを通過させた (false negative)"
    exit 1
else
    echo "PASS [Case 5]: workflow YAML 内の \`aws iam put-role-policy\` は block (期待通り)"
fi
git rm -q --cached .github/workflows/some-workflow.yml

echo ""
echo "✅ test_pre_commit_iam_filter.sh: 全 5 ケース PASS (false positive / false negative どちらも検出されず)"
exit 0
