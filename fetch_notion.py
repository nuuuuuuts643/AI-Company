#!/usr/bin/env python3
"""
Notionページの内容を取得してファイルに保存するスクリプト
使い方:
    export NOTION_TOKEN=ntn_xxx
    export NOTION_PAGE_ID=xxx
    python3 fetch_notion.py

T2026-0502-SEC-AUDIT (2026-05-02):
    旧バージョンには live Notion integration token (`ntn_3865...`) が直書きされていた。
    必ず Notion Settings → Integrations から該当トークンを Revoke し、新規発行すること。
    新トークンは env 変数のみで管理する (本スクリプトは git ignore 済だが、Cowork チャット
    やスクリーン共有経由で第三者に見える可能性がある = 物理ガードに頼れない)。
"""

import urllib.request
import urllib.error
import json
import os
import sys

TOKEN = os.environ.get("NOTION_TOKEN", "")
PAGE_ID = os.environ.get("NOTION_PAGE_ID", "3488fff7e9cf81369f3cd09eac556ce9")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "notion_content.json")

if not TOKEN:
    print("ERROR: NOTION_TOKEN env 変数が未設定です。", file=sys.stderr)
    print("  export NOTION_TOKEN=ntn_xxxx を設定してから再実行してください。", file=sys.stderr)
    sys.exit(2)

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as res:
        return json.loads(res.read().decode("utf-8"))

def get_all_blocks(block_id):
    blocks = []
    url = f"https://api.notion.com/v1/blocks/{block_id}/children?page_size=100"
    while url:
        data = fetch(url)
        blocks.extend(data.get("results", []))
        cursor = data.get("next_cursor")
        url = f"https://api.notion.com/v1/blocks/{block_id}/children?page_size=100&start_cursor={cursor}" if cursor else None
    # 子ブロックも再帰取得
    for block in blocks:
        if block.get("has_children"):
            block["children"] = get_all_blocks(block["id"])
    return blocks

print("Notionページを取得中...")
page = fetch(f"https://api.notion.com/v1/pages/{PAGE_ID}")
blocks = get_all_blocks(PAGE_ID)

result = {"page": page, "blocks": blocks}

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"完了！保存先: {OUTPUT_FILE}")
