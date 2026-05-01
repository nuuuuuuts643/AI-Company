# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

<!-- 自動巡回 2026-05-01 06:08 JST (flotopic-p003-continuity): WORKING.md に [Code] 行 0 件・main clean。優先キュー T2026-0429-K/M/N は全て landing 済 (commit fbdb5a9 / b063bd06 / fe058dec) のため新規実装なし。SLI 実測 (公開 topics-card.json 213件・05:30 JST processor 実行後): keyPoint>=100字 35.7% (76/213) [前回 04:10 JST 29.7%→+6.0pt]・ac>=3 サブ 39.5% (34/86) [前回 36.4%→+3.1pt]・kp 平均長 112.8字 [前回 103.8字→+9.0字]・storyPhase 発端率 (ac>=3) 0.0% (0/86) ✅・aiGenerated 75.1% (160/213)。check_sli_field_coverage.sh OK (乖離なし)。verify_branching_quality.py: branching_rate=14.1% (30/213) sample=4 で error_branch=1 / error_merge=3 (sample 不足の暫定値・閾値 fb<=20/fm<=15 FAIL だが母集団小)。フェーズ2 完了条件 (keyPoint 70%) 未達のため 17:30 JST processor 後再観測（次回 routine）。 -->

---

## 🔥 今週やること（メインキュー）

<!-- フェーズ別紐付け (詳細: docs/project-phases.md) -->
<!-- フェーズ1 (足回り安定) — Dispatch運用安定 / リリース管理 / 形骸化検出 -->
<!-- フェーズ2 (AI品質) — T212/T2026-0428-E/T2026-0428-BRANCH -->
<!-- フェーズ3 (UX・成長) — T191/T193 -->

> **選定基準**: ユーザー体験に直結・安定性・AI品質・収益に近い順。
> **整理日**: 2026-04-28 PM (T2026-0428-AX で実装済タスク除去 + フェーズ1 新規完了条件タスク追加)

### フェーズ1 完了条件タスク（2026-04-28 PM 完了）

> **状態**: 全項目 landing 完了。フェーズ1 完了 → フェーズ2 着手可能。

#### ✅ 完了済（PO GitHub UI 設定 2026-04-28 PM 実施 + 本セッションで gh API 実測確認済）

| ID | 内容 | 確認方法 |
|---|---|---|
| ~~T256~~ | ~~AI フィールド層抜けを CI で物理検出 (T249 再発防止)~~ → **2026-04-30 23:01 JST main で landing 確認 (Verified-Effect: ci_pass:scripts/check_ai_fields_coverage.py:main:23:01 JST)** | PR #53 (feat) + #54 (done) merged。main run 25166642638 「Lambda 構文チェック」ジョブ内「AI フィールド層抜け物理ガード」step で `python3 scripts/check_ai_fields_coverage.py` + `python3 -m unittest scripts.test_ai_fields_coverage -v` (13 tests Ran / OK) 共に成功。 |

#### 残りのフェーズ1 補強タスク（コード対応）

| ID | 優先 | 軸 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|---|

### AI 品質・体験（フェーズ2/3）

> **着手条件**: フェーズ1 完了済 (2026-04-28 PM)。フェーズ2 着手可能。
> **2026-04-28 PM 実測スナップショット** (`docs/project-phases.md` 参照):
> - keyPoint 充填率 **10.02%** (107/1068) — 目標 70% 超に対し 60pt 不足
> - storyPhase 発端 articleCount≥3 **18.75%** (33/176) — 目標 10% 未満に対し 8.75pt 超過
> - PRED# 823 件あるが verdict 0 件 — judge_prediction 運用効果未発生 → ~~T2026-0428-E2-4 で根本原因 3 層特定 + 修正 (RFC2822 parser / 閾値 1d/3art / 旧 META backfill)。次回 processor run で 3 件 verdict 出る見込み~~

| ID | 優先 | 軸 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|---|
| ~~T2026-0429-G~~ | ~~🟡 中~~ | ~~AI品質~~ | ~~**storyPhase 発端率 改善観測**~~ → **2026-04-30 21:00 JST 完了 (PR #50 merged)** — 調査で真因は ac=2 + summaryMode='minimal' のレガシーデータ (49/53=92.5%)。`normalize_minimal_phase()` を proc_storage.py に新設し読み出し時に正規化 (DB書き換えなし・冪等)。テスト22ケース + 全229ケースpass。効果検証は scheduled task (2026-05-01 03:00 JST) に委託。 | lambda/processor/proc_storage.py, lambda/processor/handler.py, lambda/fetcher/handler.py | 2026-04-29 |
| ~~T2026-0430-A~~ | ~~🔴 高~~ | ~~AI品質~~ | ~~**keyPoint 平均長 35.6字 → 200字超化（フェーズ2 最優先）**~~ → **2026-04-30 19:30 JST 完了 (PR #44 merged)** — proc_ai.py に `_retry_short_keypoint` (新アーキ) + `_process_keypoint_quality` を新設。初回 keyPoint < 100 字なら 1 回 retry → 失敗時 SHORT_FALLBACK (空にしない・長い方を残す)。`keyPointLength` / `keyPointRetried` / `keyPointFallback` を DDB 永続化 + `[KP_QUALITY]` ログ出力。tests rewrite (31 ケース) + lessons-learned Why1〜Why5 + 横展開チェックリスト 2 行追加。コスト ~+\$3/月。効果検証は deploy + 数サイクル後に verify_effect.sh ai_quality を再実行 (時間待ちはスケジューラー routine に渡す)。 | lambda/processor/proc_ai.py, lambda/processor/proc_storage.py, tests/test_keypoint_retry.py, docs/lessons-learned.md | 2026-04-30 |
| ~~T2026-0430-B~~ | ~~🟢 観測~~ | ~~AI品質~~ | ~~**perspectives 充填率 4.31% → 40.2% に改善**~~ → **2026-04-30 21:00 JST 再実測で 45% (45/100) と頭打ち判明 → T2026-0430-G で構造的改善 landing**。当初は「観測のみ・次回巡回で 60% 超を確認」予定だったが、verify_effect.sh ai_quality 再実測で minimal mode (55/100=55%) が perspectives=None 強制で律速していたことが判明。T2026-0430-G に発展統合し PR #51 merged。 | (T2026-0430-G に統合) | 2026-04-30 |
| ~~T2026-0430-G~~ | ~~🔴 高~~ | ~~AI品質~~ | ~~**perspectives 充填率 45% → 70%+ への構造的引き上げ (minimal mode で cnt>=2 のとき perspectives 生成)**~~ → **2026-04-30 21:15 JST 完了 (PR #51 merged)** — 根本原因: `_generate_story_minimal` が `perspectives=None` を強制しており、aiGenerated 母集団 100 件中 minimal mode 55 件 (うち 49 件が ac=2 + uniqueSourceCount=2) が永久に perspectives 充填できない構造だった。修正: `_build_story_schema(mode, *, cnt=1)` で minimal + cnt>=2 のとき perspectives のみ schema 追加 (minLength=60、required)、`_generate_story_minimal` は cnt>=2 で `_build_media_comparison_block(max_count=2)` 取得 + max_tokens 600→900、`_normalize_story_result(minimal)` で result['perspectives'] 文字列を propagate。watchPoints/timeline/statusLabel は引き続き minimal regime では出さない (1〜2 件では差分薄い)。tests 11 ケース新設 + 全 240 pass。コスト試算 ~+\$5/月 (Haiku、入出力併せて)。効果検証は scheduled task `trig_T0430G_persp` (2026-05-01 06:00 JST = processor 05:30 後 30 分) に登録。**Verified-Effect (2026-05-01 06:31 JST)**: ai_quality 全閾値 PASS — perspectives=65.6%(105/160) (改善前 45% → +20.6pt、目標 60% 突破)、keyPoint=99.4%(159/160)、keyPoint>=100=45.6%(73/160)、watchPoints=39.4%(63/160)。mode 別: full 20/20=100%, standard 41/41=100%, minimal 44/99=44% (改善前 0/55=0% → 44 件で perspectives 充填 landing)。残課題: minimal の充填率 44% は「cnt>=2 の minimal 全部」より下、min_length=60 の reject か Haiku 判断で空文字化している可能性 (60% 閾値はパスしているため後続タスクは積まない)。 | lambda/processor/proc_ai.py, tests/test_minimal_perspectives.py | 2026-04-30 |
| ~~T2026-0430-C (→F)~~ | ~~🔴 高~~ | ~~観測~~ | ~~**freshness SLI に「<24h トピック比率」閾値アラート追加**~~ → **2026-04-30 20:13 JST 完了 (PR #48 merged, T2026-0430-F として実装)** — `.github/workflows/freshness-check.yml` に topics-card.json `lastArticleAt` 分布の <24h 比率計算ステップを追加。10% 未満で Slack 警告。Live実測: 14/108=13.0% (PR #46 直後で回復途中)。BUILDER_FIELDS allowlist にも `lastArticleAt` を追加 (SLI field guard CI が ERROR を出していたため)。Landing 検証は scheduled task `trig_01WnhUPiVhnvxZNVwvGS5nhU` (2026-04-30 21:43 JST) に渡してセッション close。注: 元案 ID は T2026-0430-C だが、git log 上 C は fetcher Float→Decimal (PR #46) で先に消費されていたため実装は T2026-0430-F として landing。 | .github/workflows/freshness-check.yml, scripts/check_sli_field_coverage.sh | 2026-04-30 |
| ~~T2026-0430-H~~ | ~~🔴 高~~ | ~~観測~~ | ~~**fetcher 連続 2 時間 0 件保存検知 alarm (検知遅延 72h→2h)**~~ → **2026-04-30 21:43 JST 完了 (PR #52 merged)** — PR #46 Decimal バグで 3 日間 0 件保存が続いても誰も気付かなかった事故への再発防止。①fetcher/handler.py の両 return path で `[FETCHER_HEALTH]` JSON 構造化ログ emit、②CloudWatch Metric Filter `FetcherSavedArticles` で saved_articles 値抽出 → P003/Fetcher namespace に送信、③CloudWatch Alarm `P003-Fetcher-Zero-Articles-2h` (period=30min × 4 evaluation, Sum<1, treat-missing-data=breaching) → SNS p003-lambda-alerts (email)、④並走 Slack 通知として `.github/workflows/fetcher-health-check.yml` (毎時 23 分 UTC) で `aws cloudwatch get-metric-statistics` ポーリング → `SLACK_WEBHOOK_URL` POST、⑤ci.yml に setup script + workflow ファイル存在の物理ガード追加。本番設置済 (alarm state INSUFFICIENT_DATA、deploy 後に正常化)。コスト: CloudWatch Alarm $0.10/月 のみ。**Verified-Effect (2026-04-30 23:01 JST)**: alarm StateValue=OK / FetcherSavedArticles 直近2h datapoints=2 (Sum=30, 28) / `[FETCHER_HEALTH]` 構造化ログ emit 確認 (saved_articles=30/28, new_topics=15/12)。3 系統すべて健全。 | projects/P003-news-timeline/lambda/fetcher/handler.py, scripts/setup_fetcher_alarm.sh, .github/workflows/fetcher-health-check.yml, .github/workflows/ci.yml | 2026-04-30 |
| ~~T2026-0430-I~~ | ~~🟡 中~~ | ~~ルール物理化~~ | ~~**CLAUDE.md に Monitor 禁止 / CI 待ち即クローズ ルール追記** PR #60~~ → **2026-04-30 完了 (commit 74ef7670 merged)** | CLAUDE.md | 2026-04-30 |
| ~~T2026-0430-J~~ | ~~🔴 高~~ | ~~AI品質~~ | ~~**keyPoint 短文率 77.7% (87/112) の根本原因修正 — fetcher_trigger backfill 末尾追加 bug**~~ → **2026-05-01 完了 (PR #61 merged, commit 4db6189b)** — rescue を pending 先頭挿入 (`rescue_added + pending`) で 30 分ごと 2 件確実消化。tests 7 ケース rewrite + 全 98 pass。効果検証は scheduled task (05/01 05:30 JST processor 後) に渡し session close。 | projects/P003-news-timeline/lambda/processor/handler.py, projects/P003-news-timeline/tests/test_handler_fetcher_backfill.py | 2026-04-30 |
| ~~T2026-0430-E~~ | ~~🟢 観測~~ | ~~運用~~ | ~~**PR #46 後の記事大量流入に備えた dedup / クラスタリング事前確認 — 問題なし**~~ → 2026-04-30 検査完了。追加対応なし。残微小リスクは緊急性低。 | (観測のみ) | 2026-04-30 |
| ~~T2026-0430-L~~ | ~~🔴 高~~ | ~~AI品質~~ | ~~**fresh24h 25.4% → 60%+ への構造的引き上げ (NFKC + Jaccard マージ)**~~ → **2026-05-01 完了 (PR #66 merged, commit b347ab83)** — `_title_dedup_key` に `unicodedata.normalize('NFKC', ...)` 追加 + `_resolve_tid_collisions_by_title` に Jaccard 類似度判定 (threshold=0.35、active/cooling 14日 cutoff 維持) 追加。boundary test 拡張済 (test_title_dedup_guard)。Verified-Effect: 24h 後の fresh_rate ≥ 50% 確認は scheduled task に委譲。 | projects/P003-news-timeline/lambda/fetcher/handler.py, projects/P003-news-timeline/lambda/fetcher/cluster_utils.py, tests/test_title_dedup_guard.py | 2026-04-30 |
| T2026-0501-SLI-AGE | 🟡 中 | 観測 | **age decay アラート: 2026-05-01 (stale48h 39.0% > 30% 閾値超過 / official check_age_decay.sh: exiled_72h=85件=37.3%)** — scheduled task `p003-sli-morning-check` (08:03 JST) 自動巡回で検出。topics.json 228件中 89件が lastUpdated > 48h。次の processor サイクル後に自動再観測 → 改善傾向あれば本行を取消線・なければ T2026-0429-K 系の根本原因タスクへ昇格。 | (観測のみ) | 2026-05-01 |
| ~~T2026-0501-SLI-KP~~ | ~~🟡 中~~ | ~~AI品質~~ | ~~**keyPoint 充填率低下アラート: 2026-05-01 (topics.json 38.6% < 50% 閾値・目標 70%)**~~ → **2026-05-01 09:35 JST 根本原因対応 landing (PR #73 merged)** — `_retry_short_keypoint` の Tool Use schema が `minLength: 0` で物理ガード不在 → retry でも 10〜30 字短文が返り SHORT_FALLBACK で永続化される構造的バグを特定。`minLength: 60` (T2026-0501-D) に物理ガード化 + description から軟化文言除去 + lessons-learned 横展開チェックリスト追記。テスト 35 (test_keypoint_retry) + 282 全体 pass。効果検証は scheduled task `p003-sli-morning-check` (毎朝 08:03 JST) に委譲、本行は landing 確認後に消し込む。 | projects/P003-news-timeline/lambda/processor/proc_ai.py, tests/test_keypoint_retry.py, docs/lessons-learned.md | 2026-05-01 |
| T2026-0501-D | ✅ 完了 | AI品質 | **keyPoint retry schema を minLength=60 で物理ガード化** — T2026-0501-SLI-KP の根本原因対応として 2026-05-01 PR #73 で landing。`_KEYPOINT_RETRY_MIN_CHARS=60` 定数導入 + retry schema `minLength: 60` 物理ガード。outlook (60) / perspectives (80) / watchPoints (80) と同じ「Tool Use API がスキーマ違反を再要求 = 物理ガード」方式。メイン schema の minLength=0 は PO 指示「書けない場合は生成しない」維持。Verified-Effect は scheduled task に委譲。 | projects/P003-news-timeline/lambda/processor/proc_ai.py, tests/test_keypoint_retry.py, docs/lessons-learned.md | 2026-05-01 |
| T2026-0430-REV | 🟡 中 | 収益 | **収益計測インフラ — 品質SLI × 収益の週次相関基盤** — `scripts/revenue_check.sh` (cf-analytics.json から週間PV / DDB META 件数 / `docs/revenue-log.md` 最終転記日チェック) + 新設 `docs/revenue-log.md` (週次手動転記用 — PV / 表示回数 / クリック / CTR / 収益 / keyPoint・perspectives 充填率) + `.github/workflows/revenue-sli.yml` (月曜 07:00 JST cron, 8日以上更新が無いと Slack 警告)。dashboard/revenue-log.md (月次自動) と責務分離 — こちらは品質改善が PV → 忍者AdMax 収益に繋がってるかを観測する目的。**運用定着が完了条件**: 毎週月曜に忍者AdMax管理画面 (https://admax.ninja/) を開いて先週分を docs/revenue-log.md に転記するワークフローが習慣化すること。 | scripts/revenue_check.sh, docs/revenue-log.md, .github/workflows/revenue-sli.yml | 2026-04-30 |
| T2026-0501-F | 🔄 PR提出済 | AI品質+UX | **海外ニュース 国際/政治 誤分類修正 + AI 出力 人名略称ガード** — トピック 1017d101df11d48b (ミャンマー恩赦/スーチー氏) が genre='政治' 誤分類だった。fetcher の `GENRE_KEYWORDS['国際']` が米中露欧中東のみ → 「ミャンマー」「スーチー」「ASEAN」等が 0 ヒット → 「政府」1 ヒットの 政治 が勝つ構造的バグ。ASEAN/南西アジア/中東/アフリカ/中南米/欧州/海外要人 を網羅 (~80 語追加) + `GENRE_STRONG_KEYWORDS`/`_OVERRIDE_GENRE_RULES` 強化 + AI `_GENRES_PROMPT` の 政治=日本国内 / 国際=海外 主語境界を例示。同時に keyPoint「スーチー氏」初出が前提知識を要求していた問題を `_WORD_RULES` (cache 対象) に「人名は初出時に肩書き＋正式名称必須・略称禁止」「ASEAN→東南アジア諸国連合 (ASEAN) 形式」ルール追加 + aiSummary/keyPoint description にも inline で反映。**情報の地図**原則 (前提知識を要求した時点で地図ではなくなる) を物理化できる範囲で物理化。境界値テスト 8 ケース同梱 (`tests/test_genre_classification.py` 新規) + 全 290 テスト pass。Verified-Effect は次回 fetcher/processor 実行で対象トピックの genre 再分類 + qualitative_eval/朝 SLI で観測。 | projects/P003-news-timeline/lambda/fetcher/config.py, projects/P003-news-timeline/lambda/fetcher/text_utils.py, projects/P003-news-timeline/lambda/processor/proc_ai.py, projects/P003-news-timeline/tests/test_genre_classification.py, docs/lessons-learned.md | 2026-05-01 |

---

## 📦 アーカイブ（将来検討）

> 上記「今週やること」以外のタスクをここに集約。週次レビューで必要なものをメインキューに昇格させる。
> **アーカイブ整理日**: 2026-04-28

### 将来機能（ユーザー増えてから）

<!-- フェーズ3 (UX 改善・成長) — ユーザー基盤拡大後の機能拡張 -->

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T056 | 低 | **フォロー/フォロワー機能**（将来・ユーザー増えてから） | — | 2026-04-26 |
| T109 | 低 | **アフィリエイト: トピック内容に合わせた関連商品表示（将来）** — 現状はジャンル固定キーワードで検索。AI要約生成時に商品検索クエリも同時生成して DynamoDB に保存し、トピックページに関連商品として表示できれば収益性向上。AI処理コスト増になるため収益化フェーズで検討 | `lambda/processor/proc_ai.py`, `frontend/js/affiliate.js` | 2026-04-26 |
| T154 | 中 | **お気に入りトピックへの新展開を Web Push 通知** — 根本原因: お気に入り登録しても次の展開を見に戻る動機がない。修正方法: ServiceWorker に Web Push 受信を追加。fetcher が既存お気に入り tid への新記事を検知 → DynamoDB notification_queue に積む → Lambda(notifier) が1日2回処理。ユーザー増加後の優先施策。 | `frontend/sw.js`, `frontend/mypage.html`, 新Lambda | 2026-04-26 |
| T201 | 低 | **bottom-nav の「リワインド」ラベルが初訪問ユーザーに意味不明** — 「リワインド」→「まとめ読み」または「振り返り」に変更検討 (要PO判断)。 | `frontend/catchup.html`, `frontend/index.html`, `frontend/storymap.html`, `frontend/topic.html`, `frontend/mypage.html` | 2026-04-27 |
| T217 | 低 | **footer 著作権「© 2024-2026」の妥当性（PO確認）** — about.html 開発開始年は 2026 に修正済み。残るは全ページ footer 表記。要PO判断後に統一。 | 全 *.html footer | 2026-04-27 |

### プロダクト戦略（メインキュー昇格候補）

<!-- フェーズ3 (UX 改善・成長) — ジャンル戦略・差別化 -->

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| ~~T192~~ | ~~高~~ | ~~**ジャンル戦略: 全ジャンル対応から1-2ジャンル集中に絞る検討**~~ ✅ 2026-05-01 分析完了 → `docs/genre-strategy.md`。要点: 経済 PV/topic=2.71（最強・AI生成率100%）、政治1.04、株・金融0.055（過剰生産）。推奨は第一案「経済+政治」3週間試行。POの意思決定待ち → T232 で施策実行 | `docs/genre-strategy.md` | 2026-04-27 |

### リーガル・コンプライアンス

<!-- フェーズ1 (足回り安定) — 法的・規約遵守の運用品質 -->

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| ~~T225~~ | ~~中~~ | ~~**tokushoho.html 残存** — Cowork 範囲外 (FUSE マウントで物理削除不可)。Code セッションで `git rm projects/P003-news-timeline/frontend/tokushoho.html` + CloudFront キャッシュパージ + Search Console URL 削除リクエスト + CI に「frontend に tokushoho.html が存在しないこと」チェック追加。~~ ✅ 2026-04-29 c9de70e5 で削除＋CI 二重ガード化済 / 2026-04-30 CloudFront invalidation `I6KD7X02A14S0DRSM9VF3MCYZO` (DIST_ID=E2Q21LM58UY0K8 /tokushoho.html) 発行完了 / Search Console URL 削除は PO 手動対応 | `frontend/tokushoho.html`（削除）, CI チェック | 2026-04-28 |

### セキュリティ・運用堅牢性

<!-- フェーズ1 (足回り安定) — セキュリティ・堅牢性の運用品質 -->

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T229 | 低 | **admin.html フロントだけのメール突合は装飾、信頼すべきではない事の明文化** — 攻撃者が DevTools で `CONFIG.allowedEmail` を書き換えれば UI は通る。バックエンドでちゃんと検証しているので致命的ではないが、analyticsUrl / cf-analyticsUrl は認証なしで取得可能。「フロントの認証は UX のため」とコメントを残すか、analytics エンドポイントにも Bearer 検証を追加するか方針を決める。 | `frontend/admin.html`, `lambda/cf-analytics/`, `lambda/analytics/` | 2026-04-28 |
| T252 | 中 | **CSP に unsafe-inline + unsafe-eval が設定されている — XSS 攻撃面拡大** — 全 HTML の CSP meta が `default-src 'self' https: 'unsafe-inline' 'unsafe-eval'`。理由は ld+json / inline style / Google Sign-In ライブラリが eval を使うため。コメント Lambda 側で sanitize しているなら被害は限定的だが、defense-in-depth 観点では弱い。段階的に `unsafe-eval` 削除 → inline style 外部化 → nonce/hash 化 を進める。 | `frontend/*.html` 全 CSP meta | 2026-04-28 |
| T267 | 中 | **CSP meta タグはあるが HTTP Response Header に CSP が無い — meta タグの限界** — HTML meta タグの CSP は対応ブラウザ・ドメイン制限・frame-ancestors 不対応など機能制限あり。CloudFront Response Headers Policy に `content-security-policy-report-only` で report-only mode で追加 → 1-2 週間 violation を観測 → 大きな違反が無ければ enforce mode に切替。 | CloudFront Response Headers Policy, 新規 `lambda/csp_report/` | 2026-04-28 |

### UI/UX

<!-- フェーズ3 (UX 改善・成長) — UI/UX 改修 -->

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T2026-0428-AV | 中 | **トピックカードに注目スコアを表示する** — POフィードバック: スコアをカードに表示するアイデアが面白い。トップページのトピックカード (`frontend/app.js` の renderTopicCard 系) に、AI が計算した注目度スコア (`velocityScore` 等) を数値またはバーで表示する。フェーズ1 の足回り安定が完了してから着手 (UI 改善は後回し方針)。実装時は ①どのスコアを使うか (velocityScore / freshness / 記事数) を明確化 ②表示形式 (数値/バー/バッジ) を決定 ③モバイル 375px で崩れないこと を必須。 | `frontend/app.js`, `frontend/style.css` | 2026-04-28 |
| ~~T2026-0430-UX~~ | 中 | ~~**ユーザー体験ベースのUI/UX検証仕組み化** — 現在は SLI 数値（keyPoint 充填率・perspectives 等）のみ評価しているが、「実際にユーザーが使いやすいか」は数値だけでは測れない。①モバイル（375px）でのタップ操作・スクロール・情報読み取りのしやすさを定期スクリーンショット＋目視評価、②トピック読了後の次導線（関連トピック・catchup）がユーザーに見えているか確認、③ABテスト的に「新機能実装前後のファーストビュー変化」を記録するルールを追加。実装案: `scripts/ux_check.sh` がモバイルUAで本番URL 5ページを curl + html2text して情報密度を定量評価 → weekly report として Slack 通知。 | scripts/ux_check.sh 新設, .github/workflows/ux-check.yml 新設 | 2026-04-30 |~~ → **DONE 2026-05-01** scripts/ux_check.sh + ux-check.yml landing。baseline UXスコア 2.31/5 (kp_density 0.42 / response 1.0 が高得点 / info_density 0.11 / child_density 0.15 / continuation 0.10 が伸びしろ)。週次月曜 07:30 JST cron で docs/ux-scores.md に append、Slack に前週比通知。|

### 安定性・運用

<!-- フェーズ1 (足回り安定) — 観測可能性・SEO 健全性・運用品質 -->

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
<!-- T2026-0428-AB (sitemap 404) は SLI 11 + processor regenerate で landing 済 (HISTORY.md 4280bf1) -->
<!-- T236 (governance worker 品質メトリクス) は freshness-check.yml SLI 8/9/10 で代替 landing 済。本来の _governance_check.py は agent-status 用で別物 -->
<!-- T2026-0428-N (AI フィールド SLI cron) は freshness-check.yml inline で landing 済 (HISTORY.md 19b272d) -->
<!-- T2026-0428-AG (backgroundContext 個別 JSON) は T2026-0428-N に統合済 -->
<!-- T2026-0428-R (system-status auto-commit) は landing 済 (HISTORY.md bb02349 + 3e188b0) -->
<!-- T261 (ads.txt 重複) は T239 と統合済 -->
<!-- T2026-0428-P (system-status 二重管理) は T2026-0428-R で構造改善 landing → 完了 -->
<!-- T266 (system-status カバレッジ古い) は T2026-0428-R で auto-commit 化済 -->
| T238 | 低 | **processor handler.py の特殊モード分岐が肥大化（300+行）** — `lambda/processor/handler.py:60-150` に `regenerateStaticHtml` / `backfillDetailJson` / `backfillArchivedTtl` / `purgeAll` / `forceRegenerateAll` / `regenerateSitemap` の6つの特殊モードが連結 if 文で並ぶ。テスト・保守・新モード追加が困難。`proc_admin_modes.py` に分離。 | `lambda/processor/handler.py` (新規ファイル) | 2026-04-28 |
| ~~T260~~ | ~~中~~ | ~~**個別 topic JSON の `data['meta']` で aiGenerated=False の topic も生成されている** — `https://flotopic.com/api/topic/8f81be6586cbea09.json` は `aiGenerated=False` で meta が `{aiGenerated, topicId}` の 2 フィールドだけ。空の個別 JSON が量産。`update_topic_s3_file` で `aiGenerated=False` かつ generatedTitle 等が無いトピックは個別 JSON 生成をスキップ。~~ → **2026-04-30 22:15 JST 完了** — `proc_storage.update_topic_s3_file` に skip 判定 (merge 後 meta が `aiGenerated=False` かつ `generatedTitle` 不在/空白) を追加し S3 PUT をスキップ + `[SKIP_EMPTY_JSON] tid=... reason=aiGenerated=False` ログ。`tests/test_skip_empty_topic_json.py` 9 ケース新設 + 全 271 ケース pass。本番 `aiGenerated=False` のアクティブトピックは scan 結果 数十件規模 (空 JSON 撲滅見積)。DynamoDB レコードは未変更なので将来 AI 生成時には正常に書かれる。 | `lambda/processor/proc_storage.py`, `tests/test_skip_empty_topic_json.py` | 2026-04-28 |

### 収益・拡張

<!-- フェーズ3 (UX 改善・成長) — 収益化・SEO/AEO 機会拡張 -->

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T240 | 低 | **Cloudflare Web Analytics トークンがフロントに直書き** — index.html / topic.html 等の最後で `data-cf-beacon='{"token": "..."}'` がハードコード。これは CF 側仕様で公開するもので問題はないが、サブドメインや別環境を増やす際にビルド時 env 注入する設計が無い点だけメモ。 | `frontend/*.html` | 2026-04-28 |
| T241 | 低 | **アフィリエイトのセンシティブトピック自動非表示ロジック未実装** — CLAUDE.md「過去の設計ミスパターン」⑧で「事件・事故・医療・政治では非表示にする」とルール明記済み。affiliate.js で genre が `'社会'`/`'国際'`/`'健康'` × 記事タイトルが事件/事故/疾患キーワードを含む時は出さない実装が必要。AdSense 通過後・収益性確認後でよい。 | `frontend/js/affiliate.js`（推定）, `frontend/topic.html` | 2026-04-28 |
| T253 | 低 | **AI 学習クローラー全禁止 vs AI Visibility (AEO/GEO) のトレードオフ判断** — `robots.txt` で GPTBot / ChatGPT-User / Claude-Web / anthropic-ai / Google-Extended / PerplexityBot / Applebot-Extended / CCBot 全て Disallow。ChatGPT/Perplexity で「Flotopic」の名前を引いた時に検索結果に出てこない機会損失が発生。AI生成要約の知的財産価値 vs AEO/GEO 流入の機会値を Naoya 判断。 | `frontend/robots.txt`, `searchfit-seo:ai-visibility` | 2026-04-28 |

### 運用ガバナンス（Cowork×Code 連携）

<!-- フェーズ1 (足回り安定) — 運用ガバナンス・連携事故防止 -->

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T258 | 中 | **「発端」storyPhase 50% 偏り (本番) — T219 修正前の旧データが残る** — 本番 topics.json で storyPhase 分布 = 拡散 23 / 発端 57 / ピーク 9 / 現在地 4 / null 21。T219 prompt 修正で「記事3件以上で発端禁止」を入れたが、aiGenerated=True 旧 topic は skip されるため反映されない。完了判定: T255 修正＋forceRegenerateAll 1-2 回後、storyPhase 分布が正規化。 | (T255 で連動解消) | 2026-04-28 |
| T259 | 低 | **`Cache-Control: max-age=60` の topics.json が 90 分後鮮度警告と整合しない** — T263 実装時に「鮮度=updatedAt フィールド差分」「Cache-Control= edge cache TTL」の違いを混同しないこと。両者は別軸。 | T263 実装時に注意点として明記 | 2026-04-28 |
| T262 | 中 | **プライバシーポリシー・利用規約が `noindex` だが SEO 上の表示・検索性は OK か再確認** — privacy.html / terms.html は `noindex` 設定なし (現在は indexable)。Search Console で `site:flotopic.com` 検索し、privacy/terms が結果に出るか確認。 | Search Console 確認 | 2026-04-28 |
| ~~T264~~ | ~~中~~ | ~~**`.claude/worktrees/` に 6 個の stale 作業ツリーが残存** — `awesome-varahamihira-c01b2e` `happy-khorana-4e3a6c` `naughty-saha-ba5901` `quirky-cohen-c1efbd` `serene-hermann-993255` `vigilant-fermi-4e0a09`。WORKING.md TTL 8h ルールはメインの WORKING.md にしか適用されていない。起動チェック script に worktree クリーンアップ候補一覧表示 + 物理スクリプト化 + `.gitignore` 追加。~~ ✅ 2026-04-30 PR #56 で `scripts/cleanup_stale_worktrees.sh` 新規 + `session_bootstrap.sh` から `--dry-run` で呼び出し。実 cleanup 39 件削除 / 3 件 uncommitted skip / 81 件 active 維持。 | `CLAUDE.md` 起動チェック, `scripts/cleanup_stale_worktrees.sh` 新規 | 2026-04-28 |
| ~~T2026-0428-K~~ | ~~🟡 中~~ | ~~**環境スクリプトの dry-run CI 化** — 2026-04-28 04:15 schedule-task で session_bootstrap.sh / triage_tasks.py に session-id ハードコードと UTC を JST と誤ラベルする bug が同時露見。lessons-learned「環境スクリプトに session ID hardcode」記録。修正は同 commit で landing 済だが、再発防止として `scripts/session_bootstrap.sh --dry-run` を GH Actions 日次実行 → REPO 検出 / JST 表示 / WORKING.md 未来日付 stale 検出ロジックを物理 test。Claude が次セッションで気付くループを CI で前倒しに切り替える。~~ ✅ 2026-04-30 PR #57 で `--dry-run` 検証 block 追加 (REPO/JST `+09:00`/WORKING.md/git status/8h stale カウント) + `[DRY-RUN OK]` 終端マーカー + `env-scripts-dryrun.yml` cron 0 21 (JST 06:00) + Slack 通知。 | `.github/workflows/env-scripts-dryrun.yml` 新規, `scripts/session_bootstrap.sh` (`--dry-run` 引数追加) | 2026-04-28 |
| ~~T2026-0428-Q~~ | ~~中~~ | ~~**success-but-empty 抽象パターンの他コンポーネント横展開スキャン** — keyPoint 充填率 11.5% を「aiGenerated フラグだけ見る SLI」が素通りした問題の横展開。要監視: ① fetcher articleCount=0 cycle、② processor processed=0 cycle、③ bluesky_agent post 失敗、④ SES bounce、⑤ CloudFront 5xx、⑥ CI green-but-skipped、⑦ topic 個別 JSON の meta=2フィールドだけパターン (T260)。~~ ✅ 2026-04-30 `scripts/scan_success_but_empty.py` を 7 観点 (③ keyPoint / ④ perspectives / ⑤ freshness 24h / ⑥ workflows skip / ⑦ aiGenerated=False placeholder) に拡張 + `--ci-status` モード追加。①② は CloudWatch Logs 連携が大きいため TODO で残し、既存 `fetcher-health-check.yml` / `sli-keypoint-fill-rate.yml` で等価観測中。`.github/workflows/success-but-empty-scan.yml` 週次 (月 06:00 JST) で実行 + Slack 通知。初回スキャン結果: keyPoint short=77.68% / perspectives short=55.36% / fresh24h=18.75% / placeholder=0 (T260 効果) → 別タスクで根本対応。 | `scripts/scan_success_but_empty.py` 拡張, `.github/workflows/success-but-empty-scan.yml` 新規 | 2026-04-28 |
| T2026-0428-S | 🟢 低 | **contact.html が noindex 設定 — E-E-A-T 上は indexable が望ましいか再判断** — 2026-04-28 07:13 schedule-task で curl 確認、`<meta name="robots" content="noindex">` 設定。連絡先ページは Google E-E-A-T 評価で「Trust」シグナル源。AdSense 審査でも contact 有無は評価対象。**懸念**: 現状 noindex のため検索結果に出ない → 信頼性シグナルとして検索エンジンに認識されない可能性。**判断材料**: SES 受信専用フォームで spam リスクが高いから noindex にしているなら維持、純粋な連絡先表示なら indexable に変更。要PO確認後に変更検討。 | `frontend/contact.html` | 2026-04-28 |
| T2026-0428-U | 🟢 低 | **個別 topic JSON (L4b) の AI フィールド充填率 SLI** — `_PROC_INTERNAL = {spreadReason, forecast, storyTimeline, backgroundContext}` は topics.json publish 時に除外され、これらは個別 `api/topic/{tid}.json` (L4b) でのみ観測可能。現状 SLI 8/9/10 は L4a (topics.json) のみ。`scripts/check_ai_fields_coverage.sh` を sample N=10 個別 JSON 取得 → backgroundContext / spreadReason / forecast / timeline 充填率を集計 → SLI 11/12/13 として登録。詳細: `docs/ai-fields-catalog.md`, lessons-learned 2026-04-28 07:13。 | `scripts/check_ai_fields_coverage.sh`, `.github/workflows/freshness-check.yml`, `docs/sli-slo.md` | 2026-04-28 |
<!-- T2026-0428-N (AI フィールド充填率 SLI 化) は freshness-check.yml SLI 8/9/10 として inline landing 済 (HISTORY.md 19b272d) -->
<!--   閾値: keyPoint 70% / perspectives 60% / outlook 70%。Slack 通知も実装済 -->
<!--   外部 cron は freshness-check.yml の schedule で代替 (06:10 JST 等)。本タスクは完了扱い -->
| T2026-0428-AG | 🟢 低 | **個別 topic JSON で backgroundContext / spreadReason の充填率検証** — T2026-0428-N (上記 landing 済) は topics.json (L4a) の SLI。個別 topic JSON (L4b) の `backgroundContext` 等は別観測が必要。任意 5 topic を curl サンプリングして空でないことを確認する手順を追加 | (T2026-0428-Q success-but-empty 横展開 に統合) | 2026-04-28 |
<!-- T2026-0428-AG 旧行は SLI 9 統合済のため削除 (T2026-0428-Q 横展開へ移管) -->

### SLI/SLO 設計

<!-- フェーズ1 (足回り安定) — 観測可能性の設計 -->

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|

---

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
