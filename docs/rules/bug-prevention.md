# バグ再発防止ルール（再発させない）

> このファイルを参照するタイミング: タスク記述前（finder）・修正実装前（implementer）に必ず全行確認する。

| パターン | ルール |
|---|---|
| **ジャンル分類RSSフォールバック禁止** | `dominant_genres()`のキーワード不一致時に`article.genre`(RSS由来)を使ってはいけない。Google NewsのRSSは「テクノロジー」クエリで政治記事を返すことが既知。スコアなし→`['総合']`のみ許容。この規則を破ると特定ジャンルフィルターが汚染される |
| sw.js CACHE_NAME | ソースは`flotopic-dev`のまま。CI が手動バージョン番号を検出して ERROR |
| API URL重複 | `API_BASE`は`/api/`で終わる。`+'api/topics.json'`→二重パスになる。CIが検出 |
| Lambda aiGenerated | 成功時のみ True。失敗時 True→「処理済み」誤認で永遠に再処理されない |
| DynamoDB SK | FilterExpression に使えない。KeyConditionExpression で範囲絞り込み |
| ARCHIVE_DAYS | 稼働期間の 1/3 目安（1ヶ月未満→7日, 3ヶ月→14日, 1年以上→30日） |
| ゾンビ削除 | lifecycle 週次自動（月曜 02:00 UTC）。item数がtopics.json 20倍超→手動invoke |
| CloudWatch | 最新ログストリームのみ確認。古いエラーは修正済みの可能性あり |
| tokushoho.html | 廃止済み・復活禁止。footer/sitemap/sw.jsキャッシュに追加しない |
| インフラ変更 | AWS CLI 直接可。ただしナオヤ確認必須（deploy.sh 不要） |
| pending_ai.json | processor が自動管理（zombie ID 除外）。手動クリアは processor 停止中のみ |
| git push | 30分以上作業したら途中でも commit & push する |
| **CSS意味色のハードコード禁止** | `#ef4444`(danger)・`#f43f5e`(heart)をCSSに直書きしない。`var(--color-danger)`・`var(--color-heart)` を使う。根本原因: 変数なしのハードコードは「どのカラーがどの意味か」が追跡できず、後から違う用途(badge→accent等)に誤用されても気づけない |
| **新CSS追加→ダークモード目視確認必須** | `background`/`color`/`border-color` の新規CSSルールを書いたら、必ずダークモードでも視覚確認する。`[data-theme="dark"]` オーバーライドが存在しない場合、ダークモードで黒塗り・白塗り・不可視になる可能性がある。確認しないと「ライトモードでは正常、ダークモードで黒い空白」が本番に出る |
| **UIプレースホルダー3ヶ月ルール** | 「近日公開」「準備中」「Coming Soon」等のラベルは実装予定が3ヶ月以内でなければ削除する。放置するとユーザーに「開発が止まっている」印象を与える。grep定期確認: `grep -rn "近日公開\|Coming Soon\|準備中" frontend/` |
| **空コンテナ非表示ルール** | データが0件またはロード失敗の場合、h2ヘッダーを含むカードごと`display:none`にする。「関連記事（0件）」のような空見出しを絶対にユーザーに見せない。JS実装パターン: `if(!data.length){ el.closest('.card').style.display='none'; }` |
| **1バグ発見→同類全探索ルール** | バグを1件修正したら「同じパターンが他にないか」をコードベース全体で grep してから止まる。例: `keyPoint`の書き込みバグを直したら`outlook`/`perspectives`/`situation`も同じロジックを通るか確認。確認した証拠（grep結果 or 「確認済み・他には存在しない」）を commit メッセージか PR説明に必ず書く。1件直して完了にしない |
| **再発防止策は「他でも起きないか」横断確認必須** | 修正後のなぜなぜ分析で「仕組み的対策」を書くとき、同じ根本原因が別ファイル・別Lambda・別フロントエンドにも潜在しないか確認する。横展開チェックリスト（`docs/lessons-learned.md` 末尾の表）への追記は `check_lessons_landings.sh` で CI 物理検査済み。「このファイルだけ直した」で終わらない |
