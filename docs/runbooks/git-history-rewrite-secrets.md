# git history rewrite — 漏洩 secret の完全消去 runbook (T2026-0502-SEC3)

> **対象**: 過去 commit に live secret が含まれ、token rotate 済 (= 旧 token は API 401) だが履歴記録としても消したいケース。
> **重要度**: 🟡 中。旧 token が利用不可なので攻撃面は既に消失。だが「過去に漏れた事実」を可視化して fork や cache に残るのを完全に消す目的なら実施。
>
> **危険性**: history rewrite + force-push は **全コラボの local clone を壊す**。実行前に必ずコラボ全員に予告すること。

---

## 前提

このリポジトリ (`nuuuuuuts643/AI-Company`) の git history に以下 4 件の旧 token が commit されている (T2026-0502-SEC-AUDIT で発見・全て revoked 済):

| Token | 場所 | 状態 |
|---|---|---|
| GitHub PAT `ghp_LyAq...` | `projects/P004-slack-bot/README.md` (commit 7ce172a2 以降) | revoked ✓ |
| GitHub PAT `ghp_JPS5...` | `HOME-PC-CHECKLIST.md` / 旧 `CLAUDE.md` (commit 8514d67f / be8be8ef) | revoked ✓ |
| Slack Bot Token `xoxb-89706414...` | 同 commit 群 | revoked ✓ |
| Slack Webhook `T08UJJVCFJ4/B0AUJ9K64KE/...` | 同 commit 群 | revoked ✓ |

---

## 実施前チェックリスト

- [ ] 全 token が revoke 済 (rotate 完了) — `curl -H "Authorization: token ghp_LyAq..."` が 401 を返すこと
- [ ] 全コラボ (現状 PO 1 人) に「N 月 N 日 HH:MM JST に history rewrite + force-push します」を周知
- [ ] 進行中の PR を全てマージ or close (history rewrite で対応 PR が conflict を起こすため)
- [ ] main の最新 commit を控える (`git rev-parse HEAD`) — 戻す場合の参照点
- [ ] バックアップ: `git clone --mirror https://github.com/nuuuuuuts643/AI-Company.git ~/ai-company-backup-$(date +%Y%m%d)`
- [ ] GitHub branch protection を一時的に無効化 (force-push 許可・実施直後に再有効化)

---

## 手順

### 1️⃣ git-filter-repo インストール

```bash
# macOS (Homebrew)
brew install git-filter-repo

# 確認
git filter-repo --version
```

### 2️⃣ 置換ルールファイル作成 (PO が手動で旧 token 値を埋める)

旧 token の実値は **このファイルに書かない** (GitHub Push Protection で reject されるため)。
PO は password manager / git log から実値を取り出して `/tmp/secrets-to-redact.txt` を作る:

```bash
cd ~/ai-company

# テンプレ (PO がローカルで <PLACEHOLDER> を実値に置換):
cat > /tmp/secrets-to-redact.txt <<'EOF'
<OLD_GHP_LYAQ>==>***REDACTED-T2026-0502-SEC3***
<OLD_GHP_JPS5>==>***REDACTED-T2026-0502-SEC3***
<OLD_SLACK_BOT_TOKEN_1>==>***REDACTED-T2026-0502-SEC3***
<OLD_SLACK_BOT_TOKEN_2>==>***REDACTED-T2026-0502-SEC3***
<OLD_SLACK_WEBHOOK_URL_1>==>***REDACTED-T2026-0502-SEC3***
<OLD_SLACK_WEBHOOK_URL_2>==>***REDACTED-T2026-0502-SEC3***
<OLD_NOTION_TOKEN>==>***REDACTED-T2026-0502-SEC3***
<OLD_ANTHROPIC_KEY>==>***REDACTED-T2026-0502-SEC3***
EOF

# 実値の取得方法 (revoke 済なので漏れても問題ないが慎重に):
#   - <OLD_GHP_LYAQ>: 旧 P004-slack-bot/README.md commit 7ce172a2 から
#       git show 7ce172a2:projects/P004-slack-bot/README.md | grep -oE 'ghp_[A-Za-z0-9]{36}'
#   - <OLD_GHP_JPS5>: 旧 HOME-PC-CHECKLIST.md commit 8514d67f から
#       git show 8514d67f:HOME-PC-CHECKLIST.md | grep -oE 'ghp_[A-Za-z0-9]{36}'
#   - <OLD_SLACK_BOT_TOKEN_*>: git log --all -p | grep -oE 'xoxb-[0-9-]+[A-Za-z0-9]+' | sort -u
#   - <OLD_SLACK_WEBHOOK_URL_*>: git log --all -p | grep -oE 'https://hooks\.slack\.com/services/[A-Z0-9/]+/[A-Za-z0-9]+' | sort -u
#   - <OLD_NOTION_TOKEN>: git log --all -p | grep -oE 'ntn_[A-Za-z0-9]+' | sort -u
#   - <OLD_ANTHROPIC_KEY>: git log --all -p | grep -oE 'sk-ant-api03-[A-Za-z0-9_-]+' | sort -u

# 完成した /tmp/secrets-to-redact.txt の中身を sanity check
cat /tmp/secrets-to-redact.txt
# → 各行が `<実 token>==>***REDACTED-...***` 形式になっていること
# → token が ghp_xxxxx... / xoxb-... / ntn_... / sk-ant-api03-... / https://hooks... のいずれかで始まること
```

⚠️ `/tmp/secrets-to-redact.txt` は実 token を含むため、rewrite 完了後に `shred -u /tmp/secrets-to-redact.txt` で確実に消す。

### 3️⃣ history を rewrite (dry-run で先に確認)

```bash
# まず置換対象を確認 (実際の rewrite はしない・--analyze は別 dir に出力)
git filter-repo --replace-text /tmp/secrets-to-redact.txt --analyze
ls .git/filter-repo/analysis/

# 本番実行 (履歴を完全に書き換える・取り消し不可)
git filter-repo --replace-text /tmp/secrets-to-redact.txt --force
```

実行後に local の `git log` で確認 (旧 token の prefix が 0 件):

```bash
# 旧 token prefix で grep (実値ではなく prefix だけ書く)
git log --all -p | grep -cE 'ghp_LyAq|ghp_JPS5|xoxb-8970641423616|B0AUJ9K64KE|B0AU4TV0M60|ntn_3865|sk-ant-api03-sKdL'
# → 0 が表示されれば成功
```

### 4️⃣ remote 再設定 + force-push

`git filter-repo` は安全のため remote を削除する。再追加して force-push:

```bash
git remote add origin https://github.com/nuuuuuuts643/AI-Company.git

# 全 branch を force-push
git push --force-with-lease --all origin

# tags も
git push --force-with-lease --tags origin
```

### 5️⃣ GitHub branch protection を再有効化

GitHub → Settings → Branches → main → 元の rule (require status checks / require PR review / etc) を再 enable。

### 6️⃣ 全コラボに周知 + local clone 再構築指示

```bash
# 各コラボが実行
cd ~/ai-company
git fetch origin
git reset --hard origin/main

# もしくは clone から
cd ..
rm -rf ai-company
git clone https://github.com/nuuuuuuts643/AI-Company.git
```

⚠️ **stash や local branch がある場合は別 dir に退避してから reset する**。

### 7️⃣ (任意) GitHub support に cache invalidation 申請

public repo なら fork に旧 history が残っている可能性あり。GitHub support
(<support@github.com>) に「force-push で history rewrite した」と連絡して以下を依頼:
- API cache の invalidation
- 既存 fork の orphan blob を削除 (GitHub は通常 cron で自動掃除するが急ぐ場合)

---

## 完了確認

- [ ] `git log --all -p | grep -E "ghp_LyAq|ghp_JPS5|xoxb-89706414|B0AUJ9K64KE|ntn_3865|sk-ant-api03-sKdL"` が 0 件
- [ ] GitHub web UI で旧 commit (例: 7ce172a2) を開いて token が `***REDACTED***` に置換されているか確認
- [ ] `bash scripts/secret_scan.sh full` (T2026-0502-SEC-AUDIT-PROTECT) が ✅ no secrets detected
- [ ] CI workflows が全て green に戻ったか
- [ ] TASKS.md の T2026-0502-SEC3 を取消線 + HISTORY.md に移動

---

## ロールバック (緊急時のみ)

force-push で何かが壊れた場合、事前バックアップから復旧:

```bash
cd ~/ai-company-backup-YYYYMMDD
git push --mirror https://github.com/nuuuuuuts643/AI-Company.git
```

これで rewrite 前の状態に完全復元 (※ 復元後は token が再び history に現れるため、結局 token rotate 済の事実だけが救い)。

---

## 参考

- git-filter-repo 公式: https://github.com/newren/git-filter-repo
- BFG Repo-Cleaner (代替): https://rtyley.github.io/bfg-repo-cleaner/
- GitHub: removing sensitive data from a repository: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository
