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
| T082 | 低 | **S3ルートのICONS-NEEDED.mdを削除** flotopic.com/ICONS-NEEDED.md が公開されている。deploy-p003.yml に .md 除外を追加 | `.github/workflows/deploy-p003.yml` | 2026-04-26 |
| T083 | 低 | **filter-weights.json未生成** fetcherが30分毎に"デフォルト値使用"警告ログ。lambda/fetcher/で初期ファイル生成 or 警告を抑制 | `lambda/fetcher/handler.py` | 2026-04-26 |
| T084 | 高 | **アフィリエイトキーワード根本修正** T079のNEWS_PATSフィルタがほぼ無効（`？`や一般的な文型を捕捉できない）。`renderAffiliate`は常にGENRE_KEYWORDを使うべき（タイトルは一切使わない）。修正: `isNewsHeadline`チェックを廃止してkeyword = GENRE_KEYWORD[topicGenres[0]]に固定。モバイルでアフィリ非表示の原因も別途要調査 | `frontend/js/affiliate.js` | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
