# スケジュールタスク調査レポート（2026-04-28 01:14 JST）

> Cowork セッション「実態調査・課題洗い出し・即時改善・なぜなぜ分析」の出力。
> 参考: TASKS.md（T242〜T248 を本日追加）, CLAUDE.md（メタなぜなぜ追記）。

## 1. 観測した実態（事実のみ）

### 1.1 鮮度・AI生成
- `https://flotopic.com/api/topics.json` の `updatedAt` = `2026-04-27T13:34:59Z`（12時間 stale）
- topics 件数 = 114
- `aiGenerated == null` = 21（うち articleCount ≥ 5 が 5 件、最大 19 件）
- `aiGenerated == true` = 93、`storyPhase` 持ち = 93
- `summaryMode`: full=12, standard=26, minimal=54, null=22
- per-topic JSON (`/api/topic/{id}.json`) では `backgroundContext`/`perspectives`/`outlook` は standard/full モードで実際に充填されている（直近 5 サンプル全て確認済）→ HISTORY.md の「3フィールド 0%」は topics.json（slim index）を読んだ誤読、per-topic JSON にはちゃんと入っている

### 1.2 デプロイ滞留
- `git status -s` で 15 ファイル M（CLAUDE.md / HISTORY.md / TASKS.md / WORKING.md / about.html / catchup.html / contact.html / index.html / mypage.html / privacy.html / profile.html / storymap.html / terms.html / topic.html / lambda/processor/handler.py）
- 直近 commit `b5c36b0`（fix(P003): generate_title で markdown 残骸を strip）に T218 wallclock guard は **未含有**
- 本番 index.html の bottom-nav は 3項目（TOPICS / SEARCH / HOME）のみで `振り返る` リンクなし、ローカルは 4項目で diff 差分にも追加が見える
- 結論: T218 と T221（catchup nav 復活）の修正は **Cowork が working dir に書いただけで未push**

### 1.3 静的ファイル
- ads.txt: AdSense pub-id + 忍者 admax 1224516 両方記載済（OK）
- robots.txt: AI bot ブロック多数（GPTBot/PerplexityBot/Google-Extended 等、業務判断 OK）
- sitemap.xml = 121 URLs / news-sitemap.xml = 50 URLs（OK）
- security.txt: 404（不在・T247）
- llms.txt: 404（AI bot ブロック方針と整合・問題なし）
- manifest.json / sw.js: 200 OK

### 1.4 ドキュメント・ID 衝突
- WORKING.md には `[Cowork] T221 catchup.html到達導線復活`、TASKS.md には `T221: プライバシーポリシーとAuth Lambda実装の不整合`。**同 ID で 2 つの異なるタスク** が同日並立（複数 Cowork 並行採番の race）

### 1.5 規約・実装乖離
- privacy.html L141: 「Amazonアソシエイト・楽天アフィリエイト等に参加」と明記、しかし detail.js から affiliate コード削除済（UI には何も出ない）
- privacy.html: 削除対応「2 営業日以内」と「7 営業日以内」と「7 日以内」が混在（T222 既出、別 Cowork が認識）
- terms.html / privacy.html: 削除依頼が「GitHub Issues」と記載、実装は SES メールフォーム（T223 既出）
- ヘッダー `<p>` タグライン: 「大きな流れを、1分で。」（5 ページ）と「話題の流れをAIで追う」（5 ページ）が並立

## 2. 即時反映した修正（Cowork で完結できる範囲）

| 対応 | ファイル | 内容 |
|---|---|---|
| TASKS.md 追加 | `TASKS.md` | T242〜T248 を「Cowork×Code連携・運用ガバナンス」セクションとして追記（既出 T221〜T241 と衝突しない番号） |
| CLAUDE.md 追加 | `CLAUDE.md` | 「Cowork↔Code 連携の構造的欠陥」メタなぜなぜを Why1〜Why5 + 仕組み的対策 5 件で記録 |
| 本レポート | `docs/scheduled-task-report-2026-04-28.md` | スケジュールタスク出力 |

> Cowork ルール（2026-04-28 制定）に従い、コードファイル（lambda/, frontend/js/, frontend/*.html 等）には触れず、ドキュメントファイルのみ編集。git push は Code セッションに委譲。

## 3. なぜなぜ分析（Why1〜Why5 + 仕組み的対策）

### 3.1 メタ事象: 「topics.json 12 時間 stale を誰も検知していない」

詳細は CLAUDE.md「Cowork↔Code 連携の構造的欠陥 メタなぜなぜ分析」参照。要点のみ:

- **Why5 (root)**: 既存「再発防止ルール」は **コード変更時の自己チェック (negative rule)** に偏り、**運用時に外部から状態を観測する仕組み (positive monitoring)** が手薄
- **仕組み対策（ルールではない）**:
  1. topics.json 鮮度 SLI モニタ新設（T242）
  2. WORKING.md `needs-push` カラム追加（T244）
  3. AI フィールド データフロー文書（T245）
  4. `Verified:` commit gate（T246）
  5. タスクID 衝突防止スクリプト（T243）

### 3.2 メタ観察: なぜ Claude が "negative rule" に偏るか

LLM (私) は「ユーザーから問題を指摘される → CLAUDE.md にルール追加」のループで動く。問題発覚時点ではコード内 if 文の追加が局所的・低コスト・書きやすい。一方、SLI 設計や CI ガード追加は工数大で「優先度低」として後回しになる。**是正策**: なぜなぜの仕組み的対策に「外部観測」「物理ゲート」を最低 1 つ含めるテンプレ強制。

### 3.3 サブ事象: 「フィールド追加時に層を1つ忘れる」（T193follow-up / T220 が両方ヒットした原因）

- **Why1〜Why5**: AI フィールドが 5 層構造（schema → normalize → ai_updates → S3×2 → frontend×2）を通るが、フィールドごとの「どの層に入るか」一覧表が無い → Claude は proximate file 編集で完結したと誤認 → 各層の役割と reading source の暗黙性
- **仕組み対策**: `docs/ai-fields-flow.md` マトリクス + CI で proc_ai schema vs handler.py ai_updates の field 名差分検出（T245）

## 4. 引き継ぎ（次の Code セッションが最優先で実施すべきこと）

1. `git status` 確認 → working dir に滞留する 15 ファイルを `git add -A && git commit -m "chore: sync ..." && git push`
2. GH Actions 完了後、CloudWatch で Lambda の最新ログを確認し `Wallclock guard 到達` ログ出現を確認
3. JST 07:00 / 13:00 / 19:00 の次回スケジュール後に `https://flotopic.com/api/topics.json` の `updatedAt` が更新されることを確認
4. `aiGenerated == null` 件数が次回サイクルで減少することを確認（21 → 0 を目標、wallclock 制約で 1 サイクルで全部終わらない場合あり）
5. T242〜T248 の対応着手判断（優先度高は T242 鮮度モニタ・T243 ID 衝突防止・T244 needs-push カラム）

## 5. 多角的観点で発見した課題サマリ（T221〜T248 内訳）

| 観点 | 既出（別Cowork） | 本セッション追加 |
|---|---|---|
| ⚖️ リーガル | T221（auth email保存）/T222（対応期間）/T223（GitHub Issues）/T224（個人メール直書き）/T225（tokushoho残存） | T248（affiliate記述乖離） |
| 🔐 セキュリティ | T227（CORS *）/T228（rate limit）/T229（admin email check） | — |
| 🧭 UI/UX | T226（nav 表記）/T230（catchup nav 消失）/T231（推移グラフ長期）/T232（関連記事0件）/T233（処理待ち時刻）/T234（タグライン不統一） | — |
| 🛠 安定性 | T235（5xx retry）/T236（governance metric）/T237（AIカバレッジ）/T238（handler 肥大化） | T242（鮮度SLI） |
| 💰 収益・拡張 | T239（ads.txt CI）/T240（CF token）/T241（センシティブ非表示） | — |
| 🛡 運用ガバナンス | — | T243（ID衝突）/T244（needs-push）/T245（field flow doc）/T246（Verified gate）/T247（security.txt） |

## 6. 観点ごとの優先順位（提案）

1. **最優先（本日中）**: working dir push（T218 wallclock guard）→ topics.json 復旧
2. **高（24h 以内）**: T242 鮮度モニタ・T244 needs-push カラム — 同種事故の再発を物理的に防ぐ
3. **高（次回 Code セッション）**: T221（auth email 保存と privacy.html 不整合）・T223（GitHub Issues 表記）・T224（個人メール直書き） — リーガル・セキュリティの是正
4. **中（次週）**: T243 ID 衝突防止・T245 AI fields data flow doc・T246 Verified commit gate — 構造的負債の解消
5. **低**: T247 security.txt・T248 privacy.html affiliate 記述

---

調査完了: 2026-04-28 01:30 JST 頃 / Cowork セッション
