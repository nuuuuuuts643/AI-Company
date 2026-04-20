import json
import urllib.request
import urllib.parse
import os
import datetime

GITHUB_TOKEN = os.environ['GITHUB_TOKEN']
GITHUB_REPO = "nuuuuuuts643/AI-Company"
SLACK_BOT_TOKEN = os.environ['SLACK_BOT_TOKEN']
SLACK_WEBHOOK = os.environ['SLACK_WEBHOOK']


def github_append(message: str):
    """inbox/slack-messages.md にメッセージを追記する"""
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/inbox/slack-messages.md"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    }

    # 既存ファイルを取得
    req = urllib.request.Request(api_url, headers=headers)
    try:
        res = urllib.request.urlopen(req)
        data = json.loads(res.read())
        import base64
        current = base64.b64decode(data['content']).decode('utf-8')
        sha = data['sha']
    except urllib.error.HTTPError:
        current = "# Slack Messages\n\n"
        sha = None

    # メッセージ追記
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M JST")
    new_content = current + f"\n## {now}\n{message}\n"

    import base64
    encoded = base64.b64encode(new_content.encode('utf-8')).decode('utf-8')

    body = {
        "message": f"[inbox] Slackメッセージ受信: {message[:50]}",
        "content": encoded,
    }
    if sha:
        body["sha"] = sha

    req = urllib.request.Request(api_url, data=json.dumps(body).encode(), headers=headers, method='PUT')
    urllib.request.urlopen(req)


def slack_reply(text: str):
    data = json.dumps({"text": text}).encode('utf-8')
    req = urllib.request.Request(
        SLACK_WEBHOOK,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    urllib.request.urlopen(req)


def lambda_handler(event, context):
    body_str = event.get('body', '') or ''

    # API Gateway v2はbase64エンコードすることがある
    if event.get('isBase64Encoded'):
        import base64
        body_str = base64.b64decode(body_str).decode('utf-8')

    # Slack URL verification
    try:
        body = json.loads(body_str)
        if body.get('type') == 'url_verification':
            return {'statusCode': 200, 'body': json.dumps({'challenge': body['challenge']})}
    except Exception:
        pass

    # Slash command (application/x-www-form-urlencoded)
    try:
        params = dict(urllib.parse.parse_qsl(body_str))
        message = params.get('text', '').strip()
        if not message:
            return {'statusCode': 200, 'body': 'メッセージが空です'}
        github_append(message)
        slack_reply(f"受け付けました: 「{message}」\n次の定期実行（最大4時間以内）で処理します。")
        return {'statusCode': 200, 'body': json.dumps({"response_type": "in_channel", "text": f"受け付けました: 「{message}」"})}
    except Exception as e:
        slack_reply(f"エラーが発生しました: {str(e)}")
        return {'statusCode': 500, 'body': str(e)}
