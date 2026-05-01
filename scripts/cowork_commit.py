#!/usr/bin/env python3
"""
Cowork/Dispatch 用 GitHub API コミットスクリプト
FUSE マウントでは git CLI が index.lock で詰まるため、API 経由で直接コミットする。

使い方:
  python3 scripts/cowork_commit.py "commit message" TASKS.md WORKING.md

環境変数:
  GITHUB_TOKEN (または .git/config の remote.origin.url から自動取得)
  GITHUB_REPO  (例: OWNER/REPO、自動検出も可)
"""
import sys, os, json, base64, urllib.request, subprocess

def get_token_and_repo():
    # .git/config の URL からトークンとリポジトリを取得
    try:
        url = subprocess.check_output(
            ['git', 'config', '--get', 'remote.origin.url'],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            stderr=subprocess.DEVNULL
        ).decode().strip()
        # https://USER:TOKEN@github.com/OWNER/REPO.git
        import re
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
                 'User-Agent': 'cowork-commit/1.0'})
    if data:
        req.data = json.dumps(data).encode()
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

def commit_files(message, file_paths, branch='main'):
    token, repo = get_token_and_repo()
    if not token or not repo:
        print('ERROR: token/repo not found', file=sys.stderr)
        sys.exit(1)

    repo_root = subprocess.check_output(
        ['git', 'rev-parse', '--show-toplevel'],
        stderr=subprocess.DEVNULL
    ).decode().strip()

    # 現在の main の SHA を取得
    ref = api('GET', f'git/ref/heads/{branch}', token, repo)
    base_sha = ref['object']['sha']

    # base tree の SHA
    commit_info = api('GET', f'git/commits/{base_sha}', token, repo)
    base_tree_sha = commit_info['tree']['sha']

    # 各ファイルを blob として登録
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
        print('No files to commit')
        return

    # tree を作成
    tree = api('POST', 'git/trees', token, repo,
               {'base_tree': base_tree_sha, 'tree': tree_items})

    # commit を作成
    new_commit = api('POST', 'git/commits', token, repo,
                     {'message': message, 'tree': tree['sha'],
                      'parents': [base_sha]})

    # ref を更新
    api('PATCH', f'git/refs/heads/{branch}', token, repo,
        {'sha': new_commit['sha']})

    print(f'✅ Committed {new_commit["sha"][:8]}: {message}')

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: cowork_commit.py "message" file1 [file2 ...]')
        sys.exit(1)
    commit_files(sys.argv[1], sys.argv[2:])
