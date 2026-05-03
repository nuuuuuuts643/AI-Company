# 【手動作業メモ】git historyからトークンを完全削除する手順 (T2026-0502-SEC3)

> **いつやる？**: 時間ができたときでOK（トークンはすでに無効化済み・緊急性なし）
> **所要時間**: 30〜60分
> **必要なもの**: ターミナル、Homebrew、GitHubアクセス権

---

# git history rewrite — 漏洩 secret の完全消去 runbook (T2026-0502-SEC3)

> **対象**: 過去 commit に live secret が含まれ、token rotate 済 (= 旧 token は API 401) だが履歴記録としても消したいケース。
> **重要度**: 🟡 中。旧 token が利用不可なので攻撃面は既に消失。だが「過去に漏れた事実」を可視化して fork や cache に残るのを完全に消す目的なら実施。
>
> **危険性**: history rewrite + force-push は **全コラボの local clone を壊す**。実行前に必ずコラボ全員に予告すること。

---

## 🗺️ 全体の流れ（5ステップ）

```
① 事前準備（バックアップ・branch protection無効化）
② git-filter-repo インストール
③ 置換ファイル作成（トークンの実値を調べて書く）
④ historyを書き換えてforce-push
⑤ 後片付け（branch protection再有効化・ファイル削除）
```

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

## ① 実施前チェックリスト（全部チェックしてから次へ）

- [ ] **オープンPRがゼロであること** (`gh pr list` で確認。あればマージかクローズしておく)
- [ ] **バックアップを作る**（下のコマンドをそのまま実行）:

```bash
# バックアップ作成（~/ai-company-backup-20260503 みたいな名前で保存される）
git clone --mirror https://github.com/nuuuuuuts643/AI-Company.git ~/ai-company-backup-$(date +%Y%m%d)
echo "バックアップ完了: ~/ai-company-backup-$(date +%Y%m%d)"
```

- [ ] **GitHub branch protectionを一時的に無効化**:
  1. https://github.com/nuuuuuuts643/AI-Company/settings/branches を開く
  2. "main" のルールをクリック
  3. 一番下の "Delete" ではなく "Edit" → ルールを一時無効化（チェックを全部外してSave）
  4. ※ force-pushが通るようにするため。作業後に必ず再有効化する

- [ ] main の最新commit IDを控えておく（万が一のロールバック用）:

```bash
cd ~/ai-company
git rev-parse HEAD
# 出力例: a1b2c3d4e5f6... ← どこかにメモしておく
```

---

## 手順

### 2️⃣ git-filter-repo インストール

```bash
# macOS (Homebrew) ← まだ入っていない場合のみ
brew install git-filter-repo

# インストール確認（バージョン番号が出ればOK）
git filter-repo --version
```

### 3️⃣ 置換ルールファイル作成 (PO が手動で旧 token 値を埋める)

**まずgit historyに含まれるトークンの実値を調べる。** 以下のコマンドをそのまま実行すれば自動で抽出できる：

```bash
cd ~/ai-company

echo "=== Step 1: トークンの実値を抽出 ==="

echo "--- GitHub PAT (ghp_LyAq系) ---"
git show 7ce172a2:projects/P004-slack-bot/README.md 2>/dev/null | grep -oE 'ghp_[A-Za-z0-9]{36,40}'

echo "--- GitHub PAT (ghp_JPS5系) ---"
git log --all -p -- HOME-PC-CHECKLIST.md CLAUDE.md 2>/dev/null | grep -oE 'ghp_[A-Za-z0-9]{36,40}' | sort -u

echo "--- Slack Bot Token ---"
git log --all -p | grep -oE 'xoxb-[0-9-]+[A-Za-z0-9]+' | sort -u

echo "--- Slack Webhook URL ---"
git log --all -p | grep -oE 'https://hooks\.slack\.com/services/[A-Z0-9]+/[A-Z0-9]+/[A-Za-z0-9]+' | sort -u

echo "--- Notion Token ---"
git log --all -p | grep -oE 'ntn_[A-Za-z0-9]{40,}' | sort -u

echo "--- Anthropic API Key ---"
git log --all -p | grep -oE 'sk-ant-api03-[A-Za-z0-9_-]{80,}' | sort -u
```

出力された各トークンの値をコピーして、次のファイルを作る（`TOKEN_値` の部分を実値に置き換える）：

```bash
# 注意: 下の <...> を上で抽出した実際のトークン値に置き換える
# 例: ghp_LyAqXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
cat > /tmp/secrets-to-redact.txt << 'HEREDOC'
<ghp_LyAqで始まるPAT>==>***REDACTED-SEC3***
<ghp_JPS5で始まるPAT>==>***REDACTED-SEC3***
<xoxb-で始まるSlack Bot Token>==>***REDACTED-SEC3***
<2つ目のxoxb-Token（あれば）>==>***REDACTED-SEC3***
<https://hooks.slack.comのURL>==>***REDACTED-SEC3***
<ntn_で始まるNotionToken（あれば）>==>***REDACTED-SEC3***
<sk-ant-api03-で始まるAnthropicKey（あれば）>==>***REDACTED-SEC3***
HEREDOC
```

**作成後に確認（実値が入っているかチェック）:**

```bash
cat /tmp/secrets-to-redact.txt
# 各行が「実際のトークン文字列==>***REDACTED-SEC3***」形式になっていればOK
# <xxx> のプレースホルダーが残っていたら置き換え漏れ
```

⚠️ このファイルは実トークンを含むためローカルだけに置く。作業後に削除する（後述）。

### 4️⃣ historyを書き換えてforce-push

**まずdry-runで確認（何も変更しない）:**

```bash
cd ~/ai-company

# dry-runで確認（.git/filter-repo/analysis/に結果が出る）
git filter-repo --replace-text /tmp/secrets-to-redact.txt --analyze
# エラーが出なければ次へ
```

**本番実行（元に戻せないので慎重に）:**

```bash
# 本番実行 ← これでhistoryが書き換わる
git filter-repo --replace-text /tmp/secrets-to-redact.txt --force
```

**書き換わったか確認（0が出ればOK）:**

```bash
git log --all -p | grep -cE 'ghp_LyAq|ghp_JPS5|xoxb-89706414|B0AUJ9K64KE|B0AU4TV0M60|ntn_3865|sk-ant-api03-sKdL'
# → 0 なら成功 / 1以上なら置換漏れあり
```

**force-push（git filter-repoがremoteを削除するので再追加が必要）:**

```bash
# remoteを再追加
git remote add origin https://github.com/nuuuuuuts643/AI-Company.git

# 全ブランチをforce-push
git push --force --all origin

# タグも
git push --force --tags origin
```

### 5️⃣ 後片付け

**branch protectionを再有効化:**
1. https://github.com/nuuuuuuts643/AI-Company/settings/branches を開く
2. ① で無効化したルールを元に戻す（require status checks 等を再チェック → Save）

**一時ファイルを削除:**

```bash
# /tmp/secrets-to-redact.txt を完全削除（上書き削除）
shred -u /tmp/secrets-to-redact.txt 2>/dev/null || rm -f /tmp/secrets-to-redact.txt
echo "削除完了"
```

**自分のローカルcloneを最新に更新:**

```bash
cd ~/ai-company
git fetch origin
git reset --hard origin/main
```

### 6️⃣ 完了確認

```bash
# トークンが0件になっているか確認
git log --all -p | grep -cE 'ghp_LyAq|ghp_JPS5|xoxb-89706414|B0AUJ9K64KE|B0AU4TV0M60|ntn_3865|sk-ant-api03-sKdL'
# → 0 ならOK
```

GitHub WebUI でも確認:
- https://github.com/nuuuuuuts643/AI-Company/commit/7ce172a2 を開く
- `projects/P004-slack-bot/README.md` のトークンが `***REDACTED-SEC3***` になっていればOK

**TASKS.md更新（Claudeに任せてもOK）:**
```
T2026-0502-SEC3 を完了にして HISTORY.md に移動して
```

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
