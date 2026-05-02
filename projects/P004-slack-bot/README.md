# P004 Slack承認ボット

CEOが毎日 `inbox/ceo-proposals.md` に書いた提案を、Slackで「承認 #XXX」と返信するだけで自動処理するループ。

---

## アーキテクチャ

```
PO（Slack）
  └─ 「承認 #001」と入力
        ↓
  Slack Events API
        ↓
  AWS Lambda（Function URL）
        ↓
  GitHub API — inbox/ceo-proposals.md のステータスを「承認済み」に更新
        ↓
  Slack — 「✅ 提案 #001 を承認済みに更新しました」と返信
```

---

## セットアップ手順

### 1. Slack App の作成

1. https://api.slack.com/apps にアクセスして「Create New App」→「From scratch」
2. App Name: `AI-Company CEO Bot` / Workspace を選んで作成

#### Bot Token Scopes を設定（OAuth & Permissions）

| Scope | 用途 |
|---|---|
| `chat:write` | チャンネルへの返信 |
| `channels:history` | チャンネルのメッセージ読み取り |
| `app_mentions:read` | メンション検知（任意） |

設定後「Install to Workspace」を押して **Bot Token（xoxb-...）** を取得する。

---

### 2. Lambda をデプロイする

プロジェクトルートで以下を実行：

```bash
cd projects/P004-slack-bot

# ⚠️ シークレットは絶対にコード/コミットに含めない。1Password / aws-vault / .envrc 等から読み込むこと。
export GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"   # GitHub PAT (repo + workflow scope のみ)
export SLACK_BOT_TOKEN="xoxb-..."                                   # 上で取得したBot Token
export SLACK_WEBHOOK="https://hooks.slack.com/services/..."         # 既存のWebhook URL

bash deploy.sh
```

> ⚠️ **セキュリティ注意 (2026-05-02 T2026-0502-SEC-AUDIT)**: 旧バージョンの本ファイルには live な GitHub PAT (`ghp_LyAq...`) が直書きされていました。当該 PAT は **必ず Revoke** してください (https://github.com/settings/tokens)。git history には残り続けるため、リポジトリ public ならば履歴の rewrite (`git filter-repo` / BFG) を検討。シークレットは必ず env 変数経由で渡し、コード/ドキュメントには絶対に直書きしないこと。

デプロイ後に表示される **Bot URL**（`https://xxxx.lambda-url.ap-northeast-1.on.aws/`）をメモしておく。

---

### 3. Slack Event Subscriptions を有効化

1. api.slack.com/apps → 作成したアプリ → **Event Subscriptions**
2. 「Enable Events」をONにする
3. **Request URL** に Lambda の Bot URL を貼り付ける
   - Slackが自動でURL verification（challenge）を送るので、Lambdaが正常に動いていれば「Verified ✓」になる
4. 「Subscribe to bot events」に以下を追加：

| Event | 用途 |
|---|---|
| `message.channels` | パブリックチャンネルのメッセージ受信 |

5. 「Save Changes」を押す

---

### 4. ボットをチャンネルに招待する

承認メッセージを送るSlackチャンネルで：

```
/invite @AI-Company CEO Bot
```

---

## 使い方

### 提案を承認する

Slackの任意のメッセージ欄で：

```
承認 #001
```

または

```
承認#001
```

Lambda が `inbox/ceo-proposals.md` を更新して、Slackに返信が来る：

```
✅ 提案 #001 を承認済みに更新しました
```

---

### /ai スラッシュコマンド（既存機能）

緊急の指示を inbox に追記したい場合：

```
/ai P003の広告枠を停止してください
```

→ `inbox/slack-messages.md` に記録され、次のCEO定期実行（毎朝8:30 JST）で処理される。

---

## 環境変数（Lambda に設定）

| 変数名 | 説明 | 例 |
|---|---|---|
| `GITHUB_TOKEN` | GitHub PAT（repo権限） | `ghp_...` |
| `SLACK_BOT_TOKEN` | Slack Bot Token | `xoxb-...` |
| `SLACK_WEBHOOK` | Incoming Webhook URL | `https://hooks.slack.com/...` |

---

## ファイル構成

```
projects/P004-slack-bot/
├── README.md          ← このファイル
├── deploy.sh          ← AWSデプロイスクリプト
└── lambda/
    └── handler.py     ← Lambda関数本体
```

---

## ステータス

- [x] Lambda関数コード実装（handler.py）
- [x] デプロイスクリプト（deploy.sh）
- [ ] AWS Lambda デプロイ（deploy.sh を実行する必要あり）
- [ ] Slack App作成・Event Subscriptions設定
- [ ] 動作テスト（承認 #001 が通るか確認）

---

## トラブルシューティング

**「提案 #001 が見つかりません」と返ってくる**
→ `inbox/ceo-proposals.md` に `## 提案#001` の行があるか確認。番号は3桁ゼロ埋め（001, 002...）で記録されている。

**URL Verification が通らない**
→ Lambda がまだ起動していない可能性がある。少し待ってからSlack側で「Retry」を押す。

**承認はできるがSlackに返信が来ない**
→ `SLACK_WEBHOOK` または `SLACK_BOT_TOKEN` が正しく設定されているか確認する。
