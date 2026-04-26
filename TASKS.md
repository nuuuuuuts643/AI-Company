# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 未着手（実装待ち）

取得手順: `git pull --rebase && cat TASKS.md` で確認後、WORKING.md に宣言して着手。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T056 | 低 | **フォロー/フォロワー機能**（将来・ユーザー増えてから） | — | 2026-04-26 |
| T109 | 低 | **アフィリエイト: トピック内容に合わせた関連商品表示（将来）** — 現状はジャンル固定キーワードで検索。AI要約生成時に商品検索クエリも同時生成してDynamoDBに保存し、トピックページに関連商品として表示できれば収益性向上。AI処理コスト増になるため収益化フェーズで検討 | `lambda/processor/proc_ai.py`, `frontend/js/affiliate.js` | 2026-04-26 |

### 🐛 バグ修正（高優先）

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T176 | 高 | **モバイルUI崩れ調査・修正** — ユーザー報告: z-index修正(f9777be)後もスマホUIが壊れている。根本原因: 未特定。調査ポイント: hero-story-preview/onboarding-card/keyword-stripなど直近追加要素がモバイルレイアウトに与える影響・overflow-x漏れによる横スクロール・実機スクショ取得して具体的崩れ箇所を特定。修正方法: 崩れ箇所特定後に最小限CSS修正。 | `frontend/style.css`, `frontend/index.html` | 2026-04-27 |
| T178 | 高 | **アフィリエイトリンク未表示: chart.js CDNがdetail.jsをブロック** — 根本原因: topic.htmlのscriptタグが affiliate.js → chart.js(CDN) → hammer.js(CDN) → chartjs-plugin-zoom(CDN) → detail.js の順で同期ロード。モバイルでCDNが遅いと chart.js ダウンロード完了まで detail.js が実行されずrenderAffiliateが呼ばれない。T162のtry-catch修正はCDNが「失敗」した場合のみ有効で「遅い」場合は無効。修正方法: 3つのCDN scriptタグに async を追加（buildChartsはtry-catch保護済みのため安全）。 | `frontend/topic.html` | 2026-04-27 |
| T179 | 中 | **グラフと記事数の不一致** — ユーザー報告URL: topic.html?id=4eecff3f2245992b。根本原因: グラフはDynamoDB SNAPの articleCount（スナップショット）を使い、カード表示はtopics.jsonの articleCount（最新）を使う。lifecycle整理で両者がずれる。修正方法: グラフ最終点をtopics.jsonの値で補正、またはラベルに「現在N件」を別表示。 | `frontend/detail.js` | 2026-04-27 |
| T181 | 中 | **comments/favorites Lambda — topicId形式バリデーション追加** — 根本原因: POST /comments/{topicId} がtopicId形式を未検証。任意文字列topicIdへの書き込みで幽霊METAレコードが生成される。修正方法: ハンドラ先頭に `re.match(r'^[0-9a-f]{16}$', topic_id)` バリデーションを追加。 | `lambda/comments/handler.py`, `lambda/favorites/handler.py` | 2026-04-27 |

### 🎯 使いたくなるUX（「また来たい」動線）

> 安定性改善と並行して進める。Flotopicの差別化はストーリー追跡体験にある。それが伝わる動線を作る。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T154 | 中 | **お気に入りトピックへの新展開をWeb Push通知** — 根本原因: お気に入り登録しても次の展開を見に戻る動機がない。修正方法: ServiceWorkerにWeb Push受信を追加。fetcherが既存お気に入りtidへの新記事を検知→DynamoDB notification_queueに積む→Lambda(notifier)が1日2回処理。ユーザー増加後の優先施策。 | `frontend/sw.js`, `frontend/mypage.html`, 新Lambda | 2026-04-26 |
| T180 | 高 | **AI要約の「原因深掘り」が浅い — なぜ起きたかが伝わらない** — 根本原因: 現在の4セクション構成（概要・拡散理由・今後・フェーズ）は「何が起きているか」の記述に偏り、「なぜ起きたか・背景に何があるか」の掘り下げが薄い。ユーザーが「ニュースを流し読みして終わり」になる主因。修正方法: proc_ai.py のプロンプトに「背景・構造的原因」セクションを追加（同一APIコールへの追加なのでコスト増はほぼなし）。フロントエンドは detail.js で新フィールドを表示。 | `lambda/processor/proc_ai.py`, `frontend/detail.js` | 2026-04-27 |

### ⚙️ 運用・管理改善

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T177 | 中 | **admin.html 新ジャンル対応** — グルメ・ファッション・美容ジャンルを追加したが admin.html のジャンル別集計が旧リストのまま。修正方法: admin.html のジャンル一覧を config.js の GENRES と同期させる。 | `frontend/admin.html` | 2026-04-27 |
| T182 | 高 | **Claudeセッション自体の根本原因分析が浅い — 症状対処ループに陥っている** — 問題: バグ報告を受けたセッションが「症状への対処」で完了扱いにする。例: アフィリエイト未表示→try-catch追加(T162)→根本原因(CDN同期ブロック)を見落としてT178で再発。Claude自身の運用品質の問題。修正方法: CLAUDE.mdの「品質改善の進め方 ステップ2」に「実際のユーザー環境（モバイル・低速回線・CDN遅延）を想定した原因仮説を3つ以上列挙し、最も可能性の高いものを選んでから修正に入る」を追記する。 | `CLAUDE.md` | 2026-04-27 |
| T183 | 高 | **Bluesky自動投稿の稼働継続確認** — CLAUDE.mdでは2026-04-26 JST 09:13に初投稿確認済みとあるが、その後のスケジュール実行（JST 08:00/12:00/18:00 の日次3回）が継続できているか未確認。確認方法: GitHub Actions → bluesky-agent.yml の直近実行ログを確認。成功していれば CLAUDE.md の「Bluesky自動投稿」ステータスを最終確認日時で更新。失敗していれば原因（Secrets未設定・atprotoエラー等）を特定してTASKS.mdに追記。 | `CLAUDE.md`（確認後更新） | 2026-04-27 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
