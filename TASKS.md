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
| T098 | 中 | **imageUrl欠損トピックが永久に再処理されない** — `orphan_candidates`の除外条件に`imageUrl`チェックがなく、AI生成済み+要約あり+画像なしのトピックが`pending_ai`に入らない。`fetcher/handler.py`の`orphan_candidates`フィルタに`and not topic.get('imageUrl')`を追加する。 | `lambda/fetcher/handler.py` | 2026-04-26 |
| T099 | 低 | **お問い合わせのsenderNameがDynamoDBに保存されない** — `contact/handler.py`の`save_to_dynamodb()`で`data['name']`がput_itemに含まれていない。管理画面で送信者名が見えない。`'name': data['name']`を追加。 | `lambda/contact/handler.py` | 2026-04-26 |
| T100 | 低 | **analytics LambdaのS3バケットデフォルト値が誤り** — `analytics/handler.py`行25で`S3_BUCKET`デフォルトが`'flotopic-data'`（存在しないバケット）になっている。Lambda環境変数未設定時はキャッシュ書き込みが全件失敗し毎回DynamoDBフルスキャンが走る。デフォルトを`'p003-news-946554699567'`に修正。 | `lambda/analytics/handler.py` | 2026-04-26 |
| T101 | 低 | **Google tokeninfo検証でaud（対象者）未チェック** — `auth/handler.py`・`comments/handler.py`・`favorites/handler.py`の`verify_google_token()`がtokeninfoの`aud`フィールドを検証していない。他アプリ向けに発行されたGoogle IDトークンでもログインできる。`aud == GOOGLE_CLIENT_ID`チェックを追加。 | `lambda/auth/handler.py`, `lambda/comments/handler.py`, `lambda/favorites/handler.py` | 2026-04-26 |
| T102 | 低 | **コメント履歴取得でscanのLimitが結果上限でなくスキャン上限** — `comments/handler.py`の`get_user_comments()`で`table.scan(Limit=500)`はDynamoDB scan上限を500件に制限するもので、ユーザーのコメントが500件目以降に存在する場合にヒットしない。テーブル成長後に履歴が欠落する。Limitを外すかGSIでqueryに変更。 | `lambda/comments/handler.py` | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
