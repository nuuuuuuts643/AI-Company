# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 未着手（実装待ち）

取得手順: `git pull --rebase && cat TASKS.md` で確認後、WORKING.md に宣言して着手。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T019 | 中 | **SES本番アクセス申請後のLambda環境変数設定**（PO手動） | — | 2026-04-26 |
| T050 | 中 | **ノイズトピックフィルタリング強化**。livedoor経由でゲーム攻略wiki・レシピ系記事が混入（例:「ぽこあポケモン料理一覧」「鶏ささみレシピ」）。fetcherのNGキーワードリストに「攻略」「レシピ」「料理一覧」「wiki」等を追加してクラスタリング前にフィルタ。完了条件: topics.jsonにレシピ・ゲーム攻略系トピックが出なくなる | `lambda/fetcher/config.py` or `lambda/fetcher/handler.py` | 2026-04-26 |
| T051 | 低 | **storyTimelineのdetail画面表示確認と実装**。AI生成の時系列ナラティブ（storyTimeline）はDynamoDB・個別topic JSONに保存済みだが、フロントのdetail画面で表示されているか確認。未表示なら「話題の経緯」セクションとして追加。データは揃っているので表示するだけ | `frontend/detail.js` or `frontend/topic.html` | 2026-04-26 |
| T052 | 低 | **フォロー/フォロワー機能**（将来実装）。ユーザーが増えてから。DynamoDB新テーブル+Lambda+フロント全部必要。今は設計メモのみ | — | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
