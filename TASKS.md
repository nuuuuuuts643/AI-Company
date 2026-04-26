# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 未着手（実装待ち）

取得手順: `git pull --rebase && cat TASKS.md` で確認後、WORKING.md に宣言して着手。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T019 | 中 | **SES本番アクセス申請後のLambda環境変数設定**（ナオヤ手動） | — | 2026-04-26 |
| T056 | 低 | **フォロー/フォロワー機能**（将来・ユーザー増えてから） | — | 2026-04-26 |
| T068 | 高 | **ジャンル分類精度改善**。「ファッション」ジャンルにスポーツ（井上尚弥VS中谷潤人）・国際（北朝鮮ミサイル）が混入するバグ。原因: GENRE_KEYWORDSの「ダイエット・健康法・トレンド」が過広。対応: ①ファッションから過広キーワード削除②スポーツ等の強固キーワード（五輪・野球等）の閾値を1に下げる③ユーザー希望「主語ベースで振り分け」→generatedTitle生成後に再分類するロジック追加。ambiguousな場合は2ジャンル可（現在max_genres=2対応済み） | `lambda/fetcher/text_utils.py`, `lambda/fetcher/config.py` | 2026-04-26 |
| T069 | 中 | **pendingAI無限再キューバグ修正**。1-2記事のmini-modeトピック（164件）がstoryTimeline未生成のため毎回pendingAI=Trueになる。MAX_API_CALLS=150に対してqueue=322件で実効処理量が半減。修正: fetcher の `pending_ai` 条件でarticleCount<=2の場合はtimeline不要として除外（`not _needs_timeline or _has_timeline`） | `lambda/fetcher/handler.py` | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
