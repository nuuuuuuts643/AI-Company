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
    """
    Token と GITHUB_REPO を多経路で取得 (T2026-0502-SEC2-RECURRENCE 恒久対処).

    優先順位:
      1. .git/config URL に embed された token (旧仕様・SEC2 で除去推奨)
      2. 環境変数 GITHUB_TOKEN / GH_TOKEN
      3. gh CLI auth ファイル (~/.config/gh/hosts.yml)
      4. ~/.netrc (machine github.com)
      5. macOS Keychain (security コマンド) — Mac 環境のみ

    repo (owner/repo) は .git/config URL または 環境変数 GITHUB_REPO で取得。

    背景: 2026-05-02 T2026-0502-SEC2 で .git/config URL から PAT を除去した結果、
    cowork_commit.py が 401 Unauthorized になり Cowork から PR が作れなくなった事故。
    平文 token を保管しなくても認証できるよう多経路化する。
    """
    repo = None
    token = None
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # 経路 1: .git/config URL (token 埋め込みありの旧仕様)
    try:
        url = subprocess.check_output(
            ['git', 'config', '--get', 'remote.origin.url'],
            cwd=repo_root,
            stderr=subprocess.DEVNULL
        ).decode().strip()
        m = re.match(r'https://[^:]+:([^@]+)@github\.com/([^/]+/[^.]+)', url)
        if m:
            return m.group(1), m.group(2)
        # token なし URL から repo だけ抽出
        m_repo = re.match(r'https://github\.com/([^/]+/[^.]+)', url)
        if m_repo:
            repo = m_repo.group(1)
    except Exception:
        pass

    repo = repo or os.environ.get('GITHUB_REPO')

    # 経路 2: 環境変数 (推奨経路)
    token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    if token and repo:
        return token, repo

    # 経路 3: gh CLI auth (~/.config/gh/hosts.yml)
    try:
        gh_hosts = os.path.expanduser('~/.config/gh/hosts.yml')
        if os.path.isfile(gh_hosts):
            with open(gh_hosts, 'r') as f:
                content = f.read()
            # シンプル parse (yaml モジュール不要・regex で oauth_token: を拾う)
            m_gh = re.search(r'oauth_token:\s*(\S+)', content)
            if m_gh:
                gh_token = m_gh.group(1).strip('"\'')
                if gh_token and repo:
                    return gh_token, repo
    except Exception:
        pass

    # 経路 4: ~/.netrc (machine github.com)
    try:
        netrc_path = os.path.expanduser('~/.netrc')
        if os.path.isfile(netrc_path):
            with open(netrc_path, 'r') as f:
                content = f.read()
            m_netrc = re.search(
                r'machine\s+github\.com\s+(?:login\s+\S+\s+)?password\s+(\S+)',
                content
            )
            if m_netrc:
                netrc_token = m_netrc.group(1)
                if netrc_token and repo:
                    return netrc_token, repo
    except Exception:
        pass

    # 経路 5: macOS Keychain (Mac 環境のみ)
    try:
        if sys.platform == 'darwin':
            kc_token = subprocess.check_output(
                ['security', 'find-internet-password', '-s', 'github.com', '-w'],
                stderr=subprocess.DEVNULL
            ).decode().strip()
            if kc_token and repo:
                return kc_token, repo
    except Exception:
        pass

    # 全経路 fail → 呼び出し側で 401 にしないよう、ここで明示的にエラー出力
    if not token:
        sys.stderr.write(
            "ERROR: GitHub token not found in any of the 5 sources:\n"
            "  1. .git/config URL  2. env GITHUB_TOKEN/GH_TOKEN\n"
            "  3. ~/.config/gh/hosts.yml  4. ~/.netrc  5. macOS Keychain\n"
            "  対処: gh auth login (推奨) or export GITHUB_TOKEN=ghp_...\n"
            "  詳細: docs/lessons-learned.md「T2026-0502-SEC2-RECURRENCE」\n"
        )
    return token, repo


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


def detect_and_close_overlapping_cowork_prs(token, repo, file_paths):
    """
    open 中の cowork/* ブランチ PR が今回の file_paths と重複していないか検出し、
    重複している cowork PR を**自動で close** する。

    背景 (2026-05-02 PR #137 事故):
      旧 PR #135 (Code 起源・closed すべきだった conflict 持ち) を閉じ忘れたまま
      Cowork が同じファイル群で PR #137 を作成 → 一瞬だけ並行状態が発生し、
      `pr-conflict-guard.yml` が「コード本体多重編集」を検出して fail を返した。
      物理ルール「同名ファイル並行編集禁止」を Cowork 側で守るための物理化。

    対象:
      head ref が `cowork/` で始まる open PR のみ (Cowork が作った PR のみ)。
      Code セッション (fix/T* / claude/* / feat/T*) の PR は人間/別セッションが
      意図的に走らせている可能性があるため auto-close しない。

    返り値: 閉じた PR 番号のリスト
    """
    closed = []
    try:
        prs = api('GET', 'pulls?state=open&per_page=50', token, repo)
    except Exception as e:
        print(f'  (overlap check skipped: {e})')
        return closed
    target_set = {os.path.normpath(p) for p in file_paths}
    for pr in prs:
        head_ref = pr.get('head', {}).get('ref', '')
        if not head_ref.startswith('cowork/'):
            continue
        # PR の files 一覧
        try:
            files = api('GET', f'pulls/{pr["number"]}/files?per_page=100', token, repo)
        except Exception:
            continue
        pr_files = {os.path.normpath(f['filename']) for f in files}
        overlap = target_set & pr_files
        if not overlap:
            continue
        # 重複あり → close
        try:
            api('POST', f'issues/{pr["number"]}/comments', token, repo, {
                'body': f'cowork_commit.py により自動クローズ: 同一ファイル {sorted(overlap)} を含む新規 Cowork PR を作成するため (pr-conflict-guard.yml による多重編集 fail を予防)。'
            })
            api('PATCH', f'pulls/{pr["number"]}', token, repo, {'state': 'closed'})
            print(f'  ⚠️  closed overlapping cowork PR #{pr["number"]} (overlap: {sorted(overlap)})')
            closed.append(pr['number'])
        except Exception as e:
            print(f'  WARN: failed to close PR #{pr["number"]}: {e}')
    return closed


def commit_and_pr(message, file_paths, branch=None, pr_title=None, pr_body=None,
                  base='main', skip_overlap_close=False):
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

    # 物理ガード: 重複 cowork PR (同じファイルを触っている open cowork PR) を自動クローズ
    if not skip_overlap_close:
        detect_and_close_overlapping_cowork_prs(token, repo, file_paths)

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
    # 削除ファイル: ":rm:<path>" prefix で渡されたら tree から削除する
    # (T2026-0502-BI ゴミ掃除対応・FUSE で git rm が unlink 不可なので API 経由で消す)
    tree_items = []
    for fp in file_paths:
        if fp.startswith(':rm:'):
            target = fp[len(':rm:'):]
            tree_items.append({'path': target, 'mode': '100644',
                               'type': 'blob', 'sha': None})
            print(f'  delete: {target}')
            continue
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
    p.add_argument('--no-close-duplicates', action='store_true',
                   help='重複 cowork PR の auto-close を無効化 (デフォルトは有効)')
    p.add_argument('message', help='commit message')
    p.add_argument('files', nargs='+', help='コミットするファイル (リポジトリ root からの相対パス)')
    args = p.parse_args()

    commit_and_pr(args.message, args.files,
                  branch=args.branch,
                  pr_title=args.pr_title,
                  pr_body=args.pr_body,
                  base=args.base,
                  skip_overlap_close=args.no_close_duplicates)


if __name__ == '__main__':
    main()
