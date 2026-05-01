#!/usr/bin/env python3
"""
Cowork/Dispatch 用 GitHub API コミット + PR スクリプト
FUSE マウントでは git CLI が index.lock で詰まるため、API 経由で直接コミットする。

**物理ガード**: main 直書きは exit 1 で拒否する。必ず branch + PR 経由にする。
                理由: branch protection の required status checks (CI green まで auto-merge を待つ)
                を bypass する抜道を物理的に塞ぐため。

使い方:
  # ブランチを自動採番して branch + PR を作成（推奨デフォルト）
  python3 scripts/cowork_commit.py "fix: hoge" path/to/file1 path/to/file2

  # 明示的にブランチ指定
  python3 scripts/cowork_commit.py --branch feat/T2026-XXXX-yyy "fix: hoge" file1 file2

  # PR タイトル / body を指定
  python3 scripts/cowork_commit.py --pr-title "fix: hoge" --pr-body "詳細..." "msg" file1

  # main 直書きは禁止 (exit 1)。--branch main も拒否。

環境変数:
  GITHUB_TOKEN (または .git/config の remote.origin.url から自動取得)
  GITHUB_REPO  (例: OWNER/REPO、自動検出も可)
"""
import sys, os, json, urllib.request, subprocess, argparse, time, re


def get_token_and_repo():
    try:
        url = subprocess.check_output(
            ['git', 'config', '--get', 'remote.origin.url'],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            stderr=subprocess.DEVNULL
        ).decode().strip()
        m = re.match(r'https://[^:]+:([^@]+)@github\.com/([^/]+/[^.]+)', url)
        if m:
            return m.group(1), m.group(2)
    except Exception:
        pass
    return os.environ.get('GITHUB_TOKEN'), os.environ.get('GITHUB_REPO')


def api(method, path, token, repo, data=None):
    url = f'https://api.github.com/repos/{repo}/{path}'
    req = urllib.request.Request(url, method=method,
        headers={'Authorization': f'token {token}',
                 'Content-Type': 'application/json',
                 'User-Agent': 'cowork-commit/2.0',
                 'Accept': 'application/vnd.github+json'})
    if data is not None:
        req.data = json.dumps(data).encode()
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def commit_and_pr(message, file_paths, branch=None, pr_title=None, pr_body=None,
                  base='main'):
    token, repo = get_token_and_repo()
    if not token or not repo:
        print('ERROR: token/repo not found', file=sys.stderr)
        sys.exit(1)

    # 物理ガード: main 直書き禁止
    if branch is None:
        slug = re.sub(r'[^a-zA-Z0-9-]+', '-', message.lower())[:40].strip('-')
        branch = f'cowork/{int(time.time())}-{slug or "patch"}'
    if branch == 'main' or branch == base:
        print(f'ERROR: refusing to write to base branch "{branch}". '
              f'Use a feature branch + PR. (CLAUDE.md「PR 経由必須」)', file=sys.stderr)
        sys.exit(1)

    repo_root = subprocess.check_output(
        ['git', 'rev-parse', '--show-toplevel'],
        stderr=subprocess.DEVNULL
    ).decode().strip()

    # base branch HEAD
    base_ref = api('GET', f'git/ref/heads/{base}', token, repo)
    base_sha = base_ref['object']['sha']

    # branch 作成 (既にあれば update)
    try:
        api('POST', 'git/refs', token, repo,
            {'ref': f'refs/heads/{branch}', 'sha': base_sha})
        print(f'  branch: {branch} (created from {base} {base_sha[:8]})')
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        if e.code == 422 and 'already exists' in body.lower():
            api('PATCH', f'git/refs/heads/{branch}', token, repo,
                {'sha': base_sha, 'force': True})
            print(f'  branch: {branch} (reset to {base} {base_sha[:8]})')
        else:
            raise

    # base tree
    base_commit = api('GET', f'git/commits/{base_sha}', token, repo)
    base_tree_sha = base_commit['tree']['sha']

    # blob 群
    tree_items = []
    for fp in file_paths:
        abs_path = os.path.join(repo_root, fp)
        if not os.path.exists(abs_path):
            print(f'WARN: {fp} not found, skipping')
            continue
        with open(abs_path, 'r', encoding='utf-8') as f:
            content = f.read()
        blob = api('POST', 'git/blobs', token, repo,
                   {'content': content, 'encoding': 'utf-8'})
        tree_items.append({'path': fp, 'mode': '100644',
                           'type': 'blob', 'sha': blob['sha']})
        print(f'  blob: {fp}')

    if not tree_items:
        print('No files to commit', file=sys.stderr)
        sys.exit(1)

    tree = api('POST', 'git/trees', token, repo,
               {'base_tree': base_tree_sha, 'tree': tree_items})
    new_commit = api('POST', 'git/commits', token, repo,
                     {'message': message, 'tree': tree['sha'],
                      'parents': [base_sha]})
    api('PATCH', f'git/refs/heads/{branch}', token, repo,
        {'sha': new_commit['sha']})
    print(f'  commit: {new_commit["sha"][:8]}')

    # PR
    pr = api('POST', 'pulls', token, repo, {
        'title': pr_title or message.splitlines()[0],
        'head': branch,
        'base': base,
        'body': pr_body or message,
    })
    print(f'✅ PR #{pr["number"]}: {pr["html_url"]}')
    print('   auto-merge.yml が enable_pull_request_auto_merge を発動 → CI 全 green で squash merge')
    return pr


def main():
    p = argparse.ArgumentParser(
        description='Cowork から branch + PR を作る (main 直書き禁止)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument('--branch', help='ブランチ名 (省略時は自動採番)')
    p.add_argument('--base', default='main', help='base ブランチ (default: main)')
    p.add_argument('--pr-title', help='PR タイトル (省略時は commit message 1 行目)')
    p.add_argument('--pr-body', help='PR body (省略時は commit message 全体)')
    p.add_argument('message', help='commit message')
    p.add_argument('files', nargs='+', help='コミットするファイル (リポジトリ root からの相対パス)')
    args = p.parse_args()

    commit_and_pr(args.message, args.files,
                  branch=args.branch,
                  pr_title=args.pr_title,
                  pr_body=args.pr_body,
                  base=args.base)


if __name__ == '__main__':
    main()
