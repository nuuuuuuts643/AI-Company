"""
P004 Slack Bot — 承認ループ Lambda ハンドラー
==============================================
役割:
  1. Slack Events API から「承認 #XXX」メッセージを受け取る
  2. GitHub API 経由で inbox/ceo-proposals.md のステータスを更新する
  3. Slack に「承認しました #XXX ✅」と返信する
  4. 既存機能: /ai スラッシュコマンドで inbox/slack-messages.md に追記する

環境変数（Lambda に設定が必要）:
  GITHUB_TOKEN    — GitHub PAT（repo権限）
  SLACK_BOT_TOKEN — Slack Bot Token (xoxb-...)
  SLACK_WEBHOOK   — Slack Incoming Webhook URL

Slack App の設定（api.slack.com/apps）:
  - Event Subscriptions: ON
    - Request URL: https://<lambda-url>/
    - Subscribe to bot events: message.channels（または message.im）
  - Bot Token Scopes: chat:write, channels:history
"""

import json
import base64
import re
import urllib.request
import urllib.parse
import urllib.error
import os
import datetime

# ─────────────────────────────────────────────
# 設定
# ─────────────────────────────────────────────
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
GITHUB_REPO = "nuuuuuuts643/AI-Company"
SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN', '')
SLACK_WEBHOOK = os.environ.get('SLACK_WEBHOOK', '')

PROPOSALS_PATH = "inbox/ceo-proposals.md"
MESSAGES_PATH = "inbox/slack-messages.md"

JST = datetime.timezone(datetime.timedelta(hours=9))


def now_jst() -> str:
    return datetime.datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")


def today_jst() -> str:
    return datetime.datetime.now(JST).strftime("%Y-%m-%d")


# ─────────────────────────────────────────────
# GitHub API ヘルパー
# ─────────────────────────────────────────────
def github_get_file(path: str):
    """GitHubからファイルを取得。(content: str, sha: str) を返す。404の場合は(None, None)。"""
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    req = urllib.request.Request(api_url, headers=headers)
    try:
        res = urllib.request.urlopen(req, timeout=15)
        data = json.loads(res.read())
        content = base64.b64decode(data['content']).decode('utf-8')
        return content, data['sha']
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None, None
        raise


def github_put_file(path: str, content: str, sha: str, commit_message: str):
    """GitHubにファイルをPUT（作成または更新）する。"""
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }
    body = {
        "message": commit_message,
        "content": base64.b64encode(content.encode('utf-8')).decode('utf-8'),
    }
    if sha:
        body["sha"] = sha
    req = urllib.request.Request(
        api_url,
        data=json.dumps(body).encode('utf-8'),
        headers=headers,
        method='PUT'
    )
    urllib.request.urlopen(req, timeout=15)


# ─────────────────────────────────────────────
# Slack ヘルパー
# ─────────────────────────────────────────────
def slack_webhook_post(text: str):
    """Incoming Webhook でメッセージを投稿する。"""
    if not SLACK_WEBHOOK:
        print("SLACK_WEBHOOK 未設定 — Webhook投稿スキップ")
        return
    data = json.dumps({"text": text}).encode('utf-8')
    req = urllib.request.Request(
        SLACK_WEBHOOK,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"Slack Webhook エラー: {e}")


def slack_api_post(channel: str, text: str):
    """Bot Token を使って特定チャンネルにメッセージを投稿する。"""
    if not SLACK_BOT_TOKEN:
        print("SLACK_BOT_TOKEN 未設定 — API投稿スキップ")
        return
    data = json.dumps({"channel": channel, "text": text}).encode('utf-8')
    req = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        }
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"Slack API エラー: {e}")


# ─────────────────────────────────────────────
# コアロジック: 承認処理
# ─────────────────────────────────────────────
def approve_proposal(proposal_id: str) -> tuple:
    """
    inbox/ceo-proposals.md の 提案#proposal_id のステータスを承認済みに更新する。

    Returns:
        (success: bool, message: str)
    """
    proposal_id_padded = proposal_id.zfill(3)

    content, sha = github_get_file(PROPOSALS_PATH)
    if content is None:
        return False, f"{PROPOSALS_PATH} が見つかりません"

    lines = content.split('\n')
    in_target = False
    found = False
    already_approved = False
    new_lines = []

    for line in lines:
        # 対象提案のセクション開始を検出
        # 形式: "## 提案#001（2026-04-21）" or "## 提案#001"
        if re.match(rf'^## 提案#{re.escape(proposal_id_padded)}(\D|$)', line):
            in_target = True
            found = True

        # 次のセクション（別の提案 or ---）でターゲット区間終了
        elif in_target and (re.match(r'^## ', line) or line.strip() == '---'):
            in_target = False

        # ターゲット区間内の「ステータス:」行を書き換える
        if in_target and line.startswith('ステータス:'):
            if '承認済み' in line:
                already_approved = True
            else:
                line = f"ステータス: 承認済み（{today_jst()} PO Slack承認）"

        new_lines.append(line)

    if not found:
        return False, f"提案 #{proposal_id_padded} が見つかりません"

    if already_approved:
        return False, f"提案 #{proposal_id_padded} は既に承認済みです"

    new_content = '\n'.join(new_lines)
    github_put_file(
        PROPOSALS_PATH,
        new_content,
        sha,
        f"[P004] 提案#{proposal_id_padded} 承認済みに更新 ({today_jst()})"
    )
    return True, f"提案 #{proposal_id_padded} を承認済みに更新しました"


# ─────────────────────────────────────────────
# 既存機能: inbox/slack-messages.md への追記
# ─────────────────────────────────────────────
def github_append_message(message: str):
    """inbox/slack-messages.md にメッセージを追記する。"""
    content, sha = github_get_file(MESSAGES_PATH)
    if content is None:
        content = "# Slack Messages\n\n"
        sha = None

    new_content = content + f"\n## {now_jst()}\n{message}\n"
    github_put_file(
        MESSAGES_PATH,
        new_content,
        sha,
        f"[inbox] Slackメッセージ受信: {message[:50]}"
    )


# ─────────────────────────────────────────────
# 承認パターン検出ユーティリティ
# ─────────────────────────────────────────────
def extract_approval_id(text: str):
    """
    テキストから「承認 #XXX」パターンを検出して提案IDを返す。
    見つからない場合は None を返す。

    対応パターン例:
      "承認 #001"  "承認#001"  "承認 001"  "承認　#001"（全角スペース）
    """
    m = re.search(r'承認[\s　]*#?(\d+)', text)
    return m.group(1) if m else None


# ─────────────────────────────────────────────
# Lambda エントリーポイント
# ─────────────────────────────────────────────
def lambda_handler(event, context):
    # ─── ボディ取得 ───
    body_str = event.get('body', '') or ''
    if event.get('isBase64Encoded'):
        body_str = base64.b64decode(body_str).decode('utf-8')

    # ─── Content-Type 判定 ───
    headers_raw = event.get('headers', {}) or {}
    content_type = headers_raw.get('content-type', headers_raw.get('Content-Type', '')).lower()

    # ══════════════════════════════════════════
    # パス1: JSON Body → Slack Events API
    # ══════════════════════════════════════════
    is_json = 'application/json' in content_type or body_str.lstrip().startswith('{')
    if is_json:
        try:
            body = json.loads(body_str)
        except Exception:
            return _resp(400, 'Invalid JSON')

        # ── URL Verification ──
        if body.get('type') == 'url_verification':
            print("Slack URL verification 受信")
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'challenge': body.get('challenge', '')})
            }

        # ── Event Callback ──
        if body.get('type') == 'event_callback':
            ev = body.get('event', {})
            ev_type = ev.get('type', '')

            # message イベント（Botのメッセージ・編集は無視）
            if ev_type == 'message' and not ev.get('bot_id') and not ev.get('subtype'):
                text = ev.get('text', '').strip()
                channel = ev.get('channel', '')
                print(f"メッセージ受信: '{text}' / channel={channel}")

                proposal_id = extract_approval_id(text)
                if proposal_id:
                    print(f"承認リクエスト検出: #{proposal_id}")
                    success, msg = approve_proposal(proposal_id)
                    reply = f"✅ {msg}" if success else f"❌ {msg}"
                    print(reply)

                    # Webhook + API の両方で返信
                    slack_webhook_post(reply)
                    if channel:
                        slack_api_post(channel, reply)

            return _resp(200, 'ok')

        return _resp(200, 'ok')

    # ══════════════════════════════════════════
    # パス2: Form URL-encoded → Slack Slash Commands
    # ══════════════════════════════════════════
    try:
        params = dict(urllib.parse.parse_qsl(body_str))
        command = params.get('command', '')
        text = params.get('text', '').strip()
        print(f"Slash command: {command} / text: {text}")

        # /承認 XXX または /ai 承認 #XXX
        proposal_id = extract_approval_id(text) or extract_approval_id(command)
        if proposal_id:
            success, msg = approve_proposal(proposal_id)
            resp_text = f"✅ {msg}" if success else f"❌ {msg}"
            return _slash_resp(resp_text)

        # /ai コマンド（既存機能: slack-messages.md に追記）
        if text:
            github_append_message(f"[{command}] {text}" if command else text)
            slack_webhook_post(f"受け付けました: 「{text}」\n次の定期実行（最大4時間以内）で処理します。")
            return _slash_resp(f"受け付けました: 「{text}」")
        else:
            return _resp(200, 'メッセージが空です')

    except Exception as e:
        error_msg = f"エラーが発生しました: {str(e)}"
        print(error_msg)
        slack_webhook_post(error_msg)
        return _resp(500, error_msg)


# ─────────────────────────────────────────────
# レスポンスヘルパー
# ─────────────────────────────────────────────
def _resp(status: int, body: str) -> dict:
    return {'statusCode': status, 'body': body}


def _slash_resp(text: str) -> dict:
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({"response_type": "in_channel", "text": text})
    }
