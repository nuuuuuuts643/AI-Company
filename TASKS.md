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
| T093 | 高 | **クラスタリング根本バグ: seen_urls混入で記事が永続誤紐付け**。`handler.py:223` の `cluster(all_articles)` が seen_urls（前回既知URL）を含む全記事でクラスタリングする。Union-Find 推移性により無関係な記事が同一トピックに永続混入し続ける。根拠: `fingerprint([Forbes グルメ記事 + Forbes 原発記事]) = c0dcf9b6db3b5f8d` = 原発トピックの実際の topicId と一致。毎30分のSNAP書き込みで同じグルメ記事が18回蓄積済み。修正案: メインループ（`handler.py:277`）に `if not any(a['url'] in new_urls for a in g): continue` を追加し、new_urls との交差がないグループの META/SNAP 書き込みをスキップ。これにより古い記事だけのクラスターは更新されなくなり cross-contamination が止まる。 | `lambda/fetcher/handler.py` | 2026-04-26 |
| T094 | 高 | **processor minimal卒業バグ: cnt 2→3 に成長したトピックの storyTimeline が永遠に生成されない**。`processor/handler.py:102` の `_is_minimal = (topic.get('summaryMode') == 'minimal' or cnt <= 2)` が DynamoDB の `summaryMode` フィールドを参照するため、cnt が 2→3 に増加しても `_is_minimal=True` のまま `needs_story=False` と判定される。fetcher が `pendingAI=True` にセットするが processor がスキップして `pendingAI=False` に戻す → 永続ループ。storyPhase カバレッジが 40% 止まりの根本原因。修正: `_is_minimal = cnt <= 2` に変更（DynamoDB の summaryMode ではなく現在の cnt で判定）。 | `lambda/processor/handler.py` | 2026-04-26 |
| T095 | 低 | **GENRE_PRIORITY 順序バグ: '科学' が 'グルメ' より低優先度**。`config.py:246` の `GENRE_PRIORITY` リストで '科学'(index 10) が 'グルメ'(index 9) より後に並んでいるため、スコア同点時に 'グルメ' が '科学' に勝つ。T093 修正後は cross-contamination がなくなるため影響は減るが、他のケースでも誤分類が起きる可能性がある。修正: `GENRE_PRIORITY` で '科学' を 'エンタメ' の前（index 8 相当）に移動。 | `lambda/fetcher/config.py` | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
