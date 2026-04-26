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
| T093 | 高 | **クラスタリング seen_urls 混入バグ: 無関係記事が同一トピックに永続混入**。`handler.py:223` の `cluster(all_articles)` が seen_urls（前回既知URL）を含む全記事でクラスタリングするため、Union-Find 推移性で無関係な記事が同一グループに混入し続ける。証明: fingerprint([Forbes グルメ記事 + Forbes 原発記事]) = c0dcf9b6db3b5f8d = 原発トピックの実際の topicId と一致。毎30分のSNAP書き込みで同じグルメ記事が18回蓄積。修正: メインループ(handler.py:277)先頭に new_urls との交差がないグループをスキップする guard を追加。 | `lambda/fetcher/handler.py` | 2026-04-26 |
| T094 | 高 | **processor minimal 卒業バグ: cnt 2→3 成長後も storyTimeline が生成されない**。`processor/handler.py:102` の `_is_minimal = (topic.get('summaryMode') == 'minimal' or cnt <= 2)` が DynamoDB の `summaryMode` フィールドを参照するため、cnt が 3 以上に増加しても `_is_minimal=True` のまま `needs_story=False` → ストーリー生成がスキップされる。fetcher が pendingAI=True にしてもprocessor がスキップして False に戻す無限ループ。storyPhase カバレッジ 40% 止まりの根本原因。修正: `_is_minimal = cnt <= 2` に変更（現在の cnt で判定）。 | `lambda/processor/handler.py` | 2026-04-26 |
| T095 | 低 | **GENRE_PRIORITY 順序バグ: '科学' が 'グルメ' より低優先度でスコア同点時に誤分類**。`config.py:246` の GENRE_PRIORITY リストで '科学'(index 10) が 'グルメ'(index 9) より後ろのため、スコア同点時に 'グルメ' が '科学' に勝つ。T093 修正後は影響が減るが防御的に修正が必要。修正: GENRE_PRIORITY で '科学' を 'エンタメ' の前(index 8 相当)に移動。 | `lambda/fetcher/config.py` | 2026-04-26 |
| T096 | 高 | **NHK記事の published_ts=0 バグ: ISO 8601日付がパース不能で velocity/lifecycle が壊れる**。NHK は RDF(RSS 1.0)形式で `dc:date` に ISO 8601(`"2026-04-26T12:00:00+09:00"`)を使うが、`score_utils.py` の `_parse_pubdate_ts` が `email.utils.parsedate_tz`（RFC 2822専用）を使うため `None` が返り `published_ts=0` になる（Python で `parsedate_tz("2026-04-26T12:00:00+09:00") → None` を確認済み）。影響: ①NHK記事は `velocity_score` の `recent`/`prev` カウントに入らない ②NHKのみのクラスターは `last_article_ts=0` → `compute_lifecycle_status` が `hours_since≈490,000h` → `lifecycleStatus='archived'` → topics.json から除外（ブレイキングニュースが見えなくなる）③Livedoor(RDF形式)も同様の可能性。修正: `_parse_pubdate_ts` に ISO 8601 フォールバックを追加（`datetime.fromisoformat` + `.timestamp()`）。 | `lambda/fetcher/score_utils.py` | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
