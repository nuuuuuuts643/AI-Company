# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 未着手（実装待ち）

取得手順: `git pull --rebase && cat TASKS.md` で確認後、WORKING.md に宣言して着手。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T019 | 中 | **SES本番アクセス申請後のLambda環境変数設定**（ナオヤ手動） | — | 2026-04-26 |
| T053 | 中 | **CloudFlare Analytics設定（ナオヤ手動）**。cf-analytics LambdaにCF_API_TOKEN・CF_ACCOUNT_IDを設定するとadmin PVグラフが動く。手順: ①Cloudflare→My Profile→API Tokens→Create Token（Analytics:Read権限）②AWS Lambda `flotopic-cf-analytics` の環境変数に`CF_API_TOKEN`と`CF_ACCOUNT_ID`を追加（アカウントIDはCloudflareダッシュボードURLの/accounts/以降） | — | 2026-04-26 |
| T056 | 低 | **フォロー/フォロワー機能**（将来・ユーザー増えてから） | — | 2026-04-26 |
| T057 | 中 | **admin.htmlに収益データ表示追加**。忍者AdMax/Amazon/楽天のダッシュボードリンクカード一覧。AdSense審査通過後も拡張可 | `frontend/admin.html` | 2026-04-26 |
| T058 | 低 | **frontend/ICONS-NEEDED.md削除**。開発ドキュメントがS3公開配信中 | `frontend/ICONS-NEEDED.md` | 2026-04-26 |
| T060 | 低 | **twitter-card.pngを削除（ogp.pngと同一・各148KB）** | `frontend/twitter-card.png` | 2026-04-26 |
| T065 | 高 | **ストーリー表示強化**。①detail.jsでstoryPhase横ライン進捗バー（発端→拡散→ピーク→収束の全5段階を表示、現在地を強調）②storyTimeline beatsをドット+縦線付きカード形式に改善③catchup.htmlでstoryPhaseバッジを目立てる。注: storyTimelineはtopics.jsonに含まれず個別APIファイルのみ（意図的設計） | `frontend/detail.js`, `frontend/style.css`, `frontend/catchup.html` | 2026-04-26 |
| T066 | 中 | **proc_ai.pyのストーリー生成プロンプト強化**。timeline[].eventの最大文字数を20→40文字に拡大、transition15→25文字に拡大。fuller storyモードでSonnet使用の検討 | `lambda/processor/proc_ai.py` | 2026-04-26 |
| T067 | 低 | **CLAUDE.md スナップショットテーブル更新**。現在のカバレッジ実測値に更新: generatedSummary=69%(316/455), storyPhase=43%(199/455), imageUrl=62%(286/455), storyTimeline=0%(topics.json)→個別ファイルにのみ存在(意図的) | `CLAUDE.md` | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
