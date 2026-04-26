#!/usr/bin/env python3
"""
AI-Company 状態 → Notion 同期スクリプト
実行: python3 ~/ai-company/scripts/notion_sync.py
"""
import requests
import json
import os
from datetime import datetime

import os
NOTION_API_KEY = os.environ.get("NOTION_API_KEY")
DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "3488fff7e9cf80d0a5e7cb42e8a80cf3")

HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

# 現在の状態（2026-04-24 更新）
PROJECTS = [
    {
        "name": "P001 AI-Company基盤（自走システム）",
        "status": "保留 ⏸",
        "url": "",
        "memo": "CEO・秘書・各エージェントのスケジュール停止中（API費用削減）。インフラ（DynamoDB・Lambda）は存在。ユーザー・収益が生まれたら再開。",
        "priority": "低",
    },
    {
        "name": "P002 Flutterゲーム",
        "status": "開発中 🔧",
        "url": "",
        "memo": "Flutter+Flame実装済み（50+ファイル）。動作確認待ち。コンセプト: オートバトル×HD-2Dドット絵×ローグライト抽出。スプライト素材・BGM未作成。",
        "priority": "中",
    },
    {
        "name": "P003 Flotopic",
        "status": "本番稼働中 ✅",
        "url": "https://flotopic.com",
        "memo": "HTTPS化済み。AdSense審査待ち（忍者AdMaxで代替中）。AI要約未動作（ANTHROPIC_API_KEY未設定が原因）。Bluesky自動投稿・catchup.html・X風コメントUI・信頼性シグナル・ホットストリップ実装済み。Google Search Console未登録。",
        "priority": "高",
    },
    {
        "name": "P004 Slackボット",
        "status": "保留 ⏸",
        "url": "https://pqtubmsn7kfk2nojf2kqkwqiuu0obnwc.lambda-url.ap-northeast-1.on.aws/",
        "memo": "Lambdaはデプロイ済み。Slash Command /ai 未設定のため誰も使えない状態。優先度低で保留。",
        "priority": "低",
    },
    {
        "name": "P005 メモリDB",
        "status": "保留 ⏸",
        "url": "",
        "memo": "DynamoDB ai-company-memory (ap-northeast-1)。エージェント停止中のため実質未使用。インフラは残存。",
        "priority": "低",
    },
    {
        "name": "P007 ハクスラゲーム",
        "status": "アイデア 💡",
        "url": "",
        "memo": "ガーディアンテイルズ×チョコットランド風。ビルド幅広い×ドット絵アクション×オフライン。P002完成後に着手。",
        "priority": "低",
    },
]

AGENTS = [
    # ── 停止中（スケジュールOFF・API費用削減のため）──
    {"name": "CEO", "schedule": "毎朝8:30 JST", "status": "⏸ 停止中"},
    {"name": "秘書", "schedule": "毎朝9:00 JST", "status": "⏸ 停止中"},
    {"name": "開発監視AI (DevOps)", "schedule": "デプロイ後トリガー", "status": "⏸ 停止中"},
    {"name": "マーケティングAI", "schedule": "毎朝10:00 JST", "status": "⏸ 停止中"},
    {"name": "収益管理AI", "schedule": "毎週月曜9:30 JST", "status": "⏸ 停止中"},
    {"name": "編集AI", "schedule": "毎週水曜9:00 JST", "status": "⏸ 停止中"},
    {"name": "SEO AI", "schedule": "毎週月曜10:00 JST", "status": "⏸ 停止中"},
    {"name": "X投稿AI", "schedule": "—", "status": "⏸ 停止中（X API Basic $100/月が必要）"},
    # ── 稼働中 ──
    {"name": "Bluesky投稿AI", "schedule": "毎日8:00 / 月曜9:00 / 月初9:00 JST", "status": "✅ 稼働中"},
    {"name": "SecurityAI", "schedule": "push時（Claude不使用）+ 週次", "status": "✅ 稼働中"},
    {"name": "LegalAI", "schedule": "push時（Claude少量使用）+ 月次", "status": "✅ 稼働中"},
    {"name": "AuditAI", "schedule": "push時（Claude不使用）+ 週次", "status": "✅ 稼働中"},
    {"name": "Notion同期", "schedule": "毎日9:00 JST + push時", "status": "✅ 稼働中"},
]

NEXT_ACTIONS = [
    "【最重要】p003-processor ANTHROPIC_API_KEY設定 → AI要約が動いていない（設定コマンドはCLAUDE.mdに記載）",
    "AdSense審査通過待ち（申請済み）→ 通過後に広告コード差し替え",
    "Google Search Console登録（flotopic.com を URLプレフィックスで追加・HTMLファイル認証）",
    "flotopic.comドメイン自動更新確認（登録サービスのダッシュボードでONか確認）",
    "P002 flutter pub get && flutter run で動作確認",
    "P004 Slack Slash Command /ai 設定（優先度低）",
]

FUTURE_IDEAS = [
    "P003拡張: トピック起点SNS機能 — Googleログイン前提、トピック消滅でコメントも消える「映画館型」SNS。ユーザーが集まってから実装。コメントLambdaは実装済み。",
    "P003拡張: ユーザー行動分析ダッシュボード — トピックPV・ジャンル傾向・お気に入り率・管理者ページ。Googleログイン連携済みで実装可能。",
    "P003量産: 同じ型でテック特化・経済特化・スポーツ特化版。RSSソースとドメインだけ変えれば1日で新サイトが動く。",
    "P006候補: Flotopic × 株式投資シグナル — ベロシティ・エンティティを投資シグナルに転用。「アドバイス」でなく「文脈提供」として設計。金融規制に注意。",
]


def get_title_property_name():
    """DBのタイトルプロパティ名を動的に取得"""
    res = requests.get(
        f"https://api.notion.com/v1/databases/{DATABASE_ID}",
        headers=HEADERS,
    )
    props = res.json().get("properties", {})
    for name, val in props.items():
        if val.get("type") == "title":
            print(f"  タイトルプロパティ名: {name}")
            return name
    return "Name"

def get_existing_pages():
    """既存ページ一覧取得"""
    res = requests.post(
        f"https://api.notion.com/v1/databases/{DATABASE_ID}/query",
        headers=HEADERS,
        json={},
    )
    return res.json().get("results", [])


def find_page_by_title(pages, title):
    """タイトルでページ検索"""
    for page in pages:
        props = page.get("properties", {})
        for k, v in props.items():
            if v.get("type") == "title":
                texts = v.get("title", [])
                if texts and texts[0].get("plain_text", "") == title:
                    return page["id"]
    return None


def upsert_page(title, content_blocks, existing_pages, title_prop="Name"):
    """ページ作成または更新"""
    page_id = find_page_by_title(existing_pages, title)

    properties = {
        title_prop: {
            "title": [{"text": {"content": title}}]
        }
    }

    if page_id:
        print(f"  既存ページ更新: {title} (id={page_id})")
        r = requests.patch(
            f"https://api.notion.com/v1/pages/{page_id}",
            headers=HEADERS,
            json={"properties": properties},
        )
        print(f"    PATCH page: {r.status_code}")

        children = requests.get(
            f"https://api.notion.com/v1/blocks/{page_id}/children",
            headers=HEADERS,
        ).json().get("results", [])
        print(f"    既存ブロック削除: {len(children)}件")
        for child in children:
            requests.delete(f"https://api.notion.com/v1/blocks/{child['id']}", headers=HEADERS)

        # Notion APIは1リクエスト最大100ブロック
        for i in range(0, len(content_blocks), 100):
            chunk = content_blocks[i:i+100]
            r = requests.patch(
                f"https://api.notion.com/v1/blocks/{page_id}/children",
                headers=HEADERS,
                json={"children": chunk},
            )
            print(f"    ブロック追加 {i}~{i+len(chunk)}: {r.status_code}")
            if r.status_code >= 400:
                print(f"    エラー詳細: {r.text[:300]}")
    else:
        print(f"  新規作成: {title}")
        # 最初の100ブロックのみで作成し、残りは追記
        first_chunk = content_blocks[:100]
        rest = content_blocks[100:]
        r = requests.post(
            "https://api.notion.com/v1/pages",
            headers=HEADERS,
            json={
                "parent": {"database_id": DATABASE_ID},
                "properties": properties,
                "children": first_chunk,
            },
        )
        print(f"    POST page: {r.status_code}")
        if r.status_code >= 400:
            print(f"    エラー詳細: {r.text[:300]}")
            return
        new_page_id = r.json().get("id")
        for i in range(0, len(rest), 100):
            chunk = rest[i:i+100]
            r = requests.patch(
                f"https://api.notion.com/v1/blocks/{new_page_id}/children",
                headers=HEADERS,
                json={"children": chunk},
            )
            print(f"    ブロック追記 {100+i}~: {r.status_code}")
        print(f"  作成完了: {title}")


def h2(text):
    return {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": text}}]}}

def h3(text):
    return {"object": "block", "type": "heading_3", "heading_3": {"rich_text": [{"text": {"content": text}}]}}

def para(text):
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": text}}]}}

def bullet(text):
    return {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"text": {"content": text}}]}}

def divider():
    return {"object": "block", "type": "divider", "divider": {}}


def build_status_page():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    blocks = [
        para(f"最終更新: {now}"),
        divider(),
        h2("📦 プロジェクト状態"),
    ]
    for p in PROJECTS:
        blocks.append(h3(f"{p['name']} — {p['status']}"))
        if p['url']:
            blocks.append(bullet(f"URL: {p['url']}"))
        blocks.append(bullet(f"備考: {p['memo']}"))

    blocks.append(divider())
    blocks.append(h2("🤖 エージェント稼働状況"))
    for a in AGENTS:
        blocks.append(bullet(f"{a['status']} {a['name']} ({a['schedule']})"))

    blocks.append(divider())
    blocks.append(h2("🎯 次のアクション"))
    for action in NEXT_ACTIONS:
        blocks.append(bullet(action))

    blocks.append(divider())
    blocks.append(h2("💡 将来アイデア"))
    for idea in FUTURE_IDEAS:
        blocks.append(bullet(idea))

    return blocks


def build_project_blocks(p):
    """各プロジェクトのページ内コンテンツ"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    blocks = [
        para(f"最終更新: {now}"),
        divider(),
        bullet(f"ステータス: {p['status']}"),
        bullet(f"優先度: {p['priority']}"),
    ]
    if p['url']:
        blocks.append(bullet(f"URL: {p['url']}"))
    if p['memo']:
        blocks.append(bullet(f"備考: {p['memo']}"))
    return blocks


def build_summary_blocks():
    """エージェント・アクション・アイデアのサマリーページ"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    blocks = [para(f"最終更新: {now}"), divider(), h2("🤖 エージェント稼働状況")]
    for a in AGENTS:
        blocks.append(bullet(f"{a['status']} {a['name']} ({a['schedule']})"))
    blocks += [divider(), h2("🎯 次のアクション")]
    for action in NEXT_ACTIONS:
        blocks.append(bullet(action))
    blocks += [divider(), h2("💡 将来アイデア")]
    for idea in FUTURE_IDEAS:
        blocks.append(bullet(idea))
    return blocks


def main():
    if not NOTION_API_KEY:
        print("❌ NOTION_API_KEY が未設定（環境変数に設定してください）")
        return

    print("Notion同期開始...")

    res = requests.get(f"https://api.notion.com/v1/databases/{DATABASE_ID}", headers=HEADERS)
    if res.status_code != 200:
        print(f"❌ DB接続失敗: {res.status_code} {res.text}")
        return

    print("✅ Notion DB接続成功")
    title_prop = get_title_property_name()
    existing = get_existing_pages()

    # プロジェクトを1件ずつ個別ページとして同期
    for p in PROJECTS:
        upsert_page(p['name'], build_project_blocks(p), existing, title_prop)

    # エージェント・アクション・アイデアはサマリーページへ
    upsert_page("📊 運営サマリー（エージェント・アクション）", build_summary_blocks(), existing, title_prop)

    print("✅ 同期完了")


if __name__ == "__main__":
    main()
