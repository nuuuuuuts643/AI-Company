import urllib.request
import urllib.error
import json
import os

API_KEY = os.environ["NOTION_API_KEY"]
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

# 削除対象ページID
TO_ARCHIVE = [
    "34c8fff7-e9cf-8130-8cb7-c23acafcc471",  # AI-Company 現在の状態
    "34b8fff7-e9cf-811e-b47a-eac24ee806b6",  # 2026年4月
    "3488fff7-e9cf-80d2-a57f-fcac9936da12",  # ファイル構成
    "3488fff7-e9cf-810b-b4bb-d4b6a3fcbde9",  # P003 ニュースタイムライン
    "3488fff7-e9cf-80d1-9fb2-e7e7f957ab99",  # AI組織図
    "3488fff7-e9cf-8153-8c9f-e227a6cca1d7",  # P001 AI会社 基盤構築
    "3488fff7-e9cf-8124-8475-e9ec9dde41c9",  # P002 Unityゲーム
    "3488fff7-e9cf-819e-a1d5-fb85f6c51b66",  # 売り物になるレベルで自動で作る
    "3488fff7-e9cf-8141-af6a-e68757345419",  # 完全自走AI会社
    "3488fff7-e9cf-8171-8e82-c187a9cd6861",  # Unityに依存しないゲーム開発手段
    "3488fff7-e9cf-81ed-8d6a-d3b72a10d81e",  # Slackで秘書に指示を送りたい
    "3488fff7-e9cf-818d-8822-df1f232437e1",  # P001 AI会社 基盤構築（重複）
    "6b3fa108-a5c7-46dc-b091-b7ddccdb9a4e",  # 💡 アイデアバンク
    "988d26f3-73e7-4433-9e42-a4eff6d1af88",  # 📚 ナレッジベース
    "562c6a0c-1786-4d32-97f4-561bbbc2224e",  # ⚖️ リーガル・セキュリティ
]

for page_id in TO_ARCHIVE:
    data = json.dumps({"archived": True}).encode()
    req = urllib.request.Request(
        f"https://api.notion.com/v1/pages/{page_id}",
        data=data, method="PATCH"
    )
    for k, v in HEADERS.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req) as res:
            title = json.loads(res.read()).get("properties", {})
            print(f"✅ アーカイブ完了: {page_id}")
    except urllib.error.HTTPError as e:
        print(f"❌ {page_id}: {e.code} {e.read().decode()[:100]}")

print("完了")
