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
| T097 | 高 | **calc_score() recency_bonus漏れ**: score_utils.py:145でparsedate_tzを直接呼び出し。T096で_parse_pubdate_tsにISO 8601対応を追加したが、この箇所は修正漏れ。NHK記事（tier=1最高品質）が6時間以内判定に失敗し×1.20ボーナスを取得できない。修正: parsedate_tz直接呼びを_parse_pubdate_tsベースのタイムスタンプ比較に変更 | fetcher/score_utils.py | 2026-04-26 |
| T098 | 中 | **imageUrl欠損トピックが永久に再処理されない**: fetcher/handler.py:350でpending_ai判定がimageUrlを考慮しない。orphan_candidates(line 601)もimageUrl欠損を対象外にしている。aiGenerated=True+良質コンテンツだがimageUrl=NoneのトピックはpendingAI=Falseになり、velocity spike(v>40)が来ない限り永久に画像なし。imageUrl coverage 68%の原因の一つ。修正: orphan_candidatesにimageUrl欠損チェックを追加 | fetcher/handler.py | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
