# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 未着手（実装待ち）

取得手順: `git pull --rebase && cat TASKS.md` で確認後、WORKING.md に宣言して着手。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T019 | 中 | **SES本番アクセス申請後のLambda環境変数設定**（ナオヤ手動） | — | 2026-04-26 |
| T071 | 低 | **tracker Lambda VIEW#アイテムにTTL追加**。現在VIEW#{date}がDynamoDB p003-topicsに無期限蓄積。lifecycle Lambdaが削除しない。90日後に500トピック×90件≒45,000行になる。lifecycle対象に追加 or trackerでTTL=90日設定するだけ。 | lambda/tracker/handler.py or lambda/lifecycle/handler.py | 2026-04-26 |
| T072 | 低 | **processor fallback scanのstoryTimeline=[]フィルタ最適化**。L130 `Attr('storyTimeline').eq([])` がminimalトピックを無駄にスキャンしている（L144のneeds_ai_processingで除外されるので正確性は問題なし）。スキャンコスト削減のため条件を削除検討。 | lambda/processor/proc_storage.py | 2026-04-26 |
| T056 | 低 | **フォロー/フォロワー機能**（将来・ユーザー増えてから） | — | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
