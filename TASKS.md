# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 未着手（実装待ち）

取得手順: `git pull --rebase && cat TASKS.md` で確認後、WORKING.md に宣言して着手。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T019 | 中 | **SES本番アクセス申請後のLambda環境変数設定**（PO手動） | — | 2026-04-26 |
| T056 | 低 | **フォロー/フォロワー機能**（将来・ユーザー増えてから） | — | 2026-04-26 |
| T098 | 中 | **imageUrl欠損トピックが永久に再処理されない**: fetcher/handler.py:350でpending_ai判定がimageUrlを考慮しない。orphan_candidates(line 601)もimageUrl欠損を対象外にしている。aiGenerated=True+良質コンテンツだがimageUrl=NoneのトピックはpendingAI=Falseになり、velocity spike(v>40)が来ない限り永久に画像なし。imageUrl coverage 68%の原因の一つ。修正: orphan_candidatesにimageUrl欠損チェックを追加 | fetcher/handler.py | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
