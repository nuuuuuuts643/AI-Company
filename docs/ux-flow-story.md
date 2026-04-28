# 「ストーリーを追う」フロー設計（T191）

> 制定: 2026-04-29 / オーナー: P003 Flotopic
> 出典: TASKS.md T191「トップ画面で動きが見える → 1 タップで経緯 → 続きが来たら通知で離脱」

## 1. 目的

**Flotopic に毎日来る理由を「動いているストーリーを追える」一点に絞る。**
ユーザーが日常的に再訪する設計上の前提:

- 来訪 → 30 秒で「**何が動いている？**」が分かる
- 興味あれば 1 タップで「**どういう経緯？**」が分かる
- 興味維持なら「**続きが来たら知らせる**」で離脱（再訪トリガー化）

**これがフェーズ3 (UX/成長) の中核仮説**であり、本ドキュメントが詳細フローを規定する。

---

## 2. 現状フロー（2026-04-29 調査結果）

調査ファイル: `frontend/index.html`, `frontend/app.js`, `frontend/topic.html`, `frontend/detail.js`, `frontend/storymap.html`, `frontend/mypage.html`

### 2.1 トップ画面（`frontend/index.html` + `frontend/app.js`）

**実装済**:
- トピックカード (`<a class="topic-card">`、`app.js:436`) — `href="topic.html?id=${topicId}"` で遷移
- カード内表示 (`renderCardMeta()`、`app.js:314–363`):
  - `📄 ${articleCount}件 · 約${readMins}分`
  - `📈 +${articleCountDelta}件`（過去 24h 増分、`app.js:349`）
  - `📰 ${srcCount}社が報道` または媒体名
  - `🔖 ${hatenaCount}`（10 以上時のみ）
  - `🌿 ${childCount}件の分岐` → `storymap.html?id=${topicId}` へ
  - `↳ 派生`（親トピック指示）
  - `🌱/📡/🔥/📍/✅` storyPhase バッジ（`app.js:410–411`）
  - **絶対日時**（`fmtDate(t.lastUpdated)`、`app.js:362`）
- サイト全体の「最終更新」表示 (`updateFreshnessDisplay()`、`app.js:881–891`、要素 `#last-updated`、30秒間隔)

**未実装ギャップ（T191 で実装対象）**:
- ❌ **カード単位の相対時刻バッジ** — 「3時間前更新」のような fresh 感の即時可視化が現状 `fmtDate()` の絶対日時のみ。動いているか止まっているかが一目で判別できない。

### 2.2 トピック詳細（`frontend/topic.html` + `frontend/detail.js`）

**実装済**:
- `topic.html?id=${topicId}` に遷移 (`topic.html:516` で `detail.js` を読込)
- AI 分析セクション (`detail.js:333–348`):
  - **状況解説**: `meta.keyPoint` (`detail.js:413–425`)
  - **複数の見方** (perspectives): `detail.js:426–433`
  - **注目ポイント** (watchPoints): `detail.js:434–441`
- **記事タイムライン** (`<h2>記事の流れ</h2>`、`#story-timeline`、`topic.html:350–362`)
- **お気に入りボタン**:
  - ヒーロー内 `#topic-fav-btn`「<i>♥</i> お気に入り」(`topic.html:319`、`detail.js:233`)
  - スティッキー CTA バー `.scb-fav` (モバイル専用、`topic.html:468`)
- **ストーリーマップリンク** (`detail.js:880–885`): 子トピックあれば「🗺 このストーリーの分岐を見る」、なければ「📖 このストーリーを始まりから追う →」

**未実装ギャップ（T191 で実装対象）**:
- ❌ **「続きが来たら通知」ボタン** — お気に入り≠通知。お気に入り押下時に「動きがあったら通知する？」の誘導が無い。
- ❌ **「動いているか止まっているか」の即時表示** — 詳細ページ内でも最終更新時刻の相対表示が弱い。

### 2.3 ストーリーマップ（`frontend/storymap.html`）

**実装済**:
- 親トピック+子トピック（分岐）の時系列ビュー
- 「発端 → 拡散 → ピーク → 現在地 → 収束」の storyPhase 可視化
- 「次に読むトピック」推薦 (`storymap.html:547–587`)
- 記事日時の相対表示 (`fmtAgo()`、`storymap.html:290–300`)

**ギャップ**: storymap は親子分岐を持つトピックでしか意味を持たない。普通のトピック詳細→「ストーリーを追う」体験には不足。

### 2.4 マイページ（`frontend/mypage.html`）

**実装済**:
- お気に入りタブ (`mypage.html:1408, 1415–1417`)
  - 「🔔 新着あり (${count}件)」/「変化なし」の 2 区分
  - localStorage `flotopic_favs` + DynamoDB `users` テーブル同期
  - 各行に「分前更新」「時間前更新」「日前更新」(`mypage.html:1308–1312`)
- 通知タブ — メンション通知のみ (`mypage.html:1204–1246`、`${_APIGW}/notifications/${handle}`)

**未実装ギャップ（T191 で実装対象）**:
- ❌ **トピック購読通知** — 「このトピックが動いたら通知」を受け取る仕組みが無い。お気に入りの「新着あり」表示はマイページ閲覧時しか機能しない（プッシュ性ゼロ）。

---

## 3. 目標フロー（T191 完成形）

```
[トップ画面]
   │ カード上に「3時間前 / 動き中」即時可視化（NEW）
   │ velocityScore は色とバッジで暗黙表示（既存）
   ▼
[トピック詳細 topic.html]
   │ 状況解説 / 各社見解 / 注目ポイント（既存）
   │ 記事タイムライン（既存）
   │ ♥ お気に入り（既存）
   │ 🔔 動いたら通知 ←追加（NEW）
   ▼
[離脱]
   │ → 次回プッシュ通知 or マイページ「新着」で再訪
   ▼
[再訪 → トップ or 詳細へ戻る]
```

### 3.1 トップ画面で実装すべきこと

| 項目 | 実装場所 | 優先度 | T191 内 / 別タスク |
|---|---|---|---|
| カード単位「N時間前」相対時刻バッジ | `app.js:renderCardMeta()` | 🟢 高 | T191 内（本セッション実装） |
| 「動き中／停滞」の判定バッジ（過去 24h で記事追加あり） | `app.js:renderCardMeta()` | 🟡 中 | T191 内（本セッション実装可） |
| velocityScore のグラフ表示 | 別タスク | 🟠 低 | 別タスク化（T191-A 提案） |

### 3.2 トピック詳細で実装すべきこと

| 項目 | 実装場所 | 優先度 | T191 内 / 別タスク |
|---|---|---|---|
| 「動いたら通知」ボタン文言追加 | `detail.js` `topic.html` | 🟢 高 | 別タスク（T191-B）— 通知バックエンド要設計 |
| お気に入り押下時に「通知も ON にする？」誘導 | `detail.js` | 🟡 中 | 別タスク（T191-B）と同時実装 |

### 3.3 通知バックエンド（T191-B として分離）

「お気に入り = 通知 ON」とするか、「お気に入り≠通知、別 toggle」とするかは UX 方針判断。
**推奨**: お気に入り押下時に初回のみ「動いたら通知も ON」モーダル → 同意で push 通知購読。

**実装スコープ（要別タスク）**:
1. Web Push 通知購読 (Service Worker `sw.js` 拡張、VAPID キー、subscription エンドポイント保存)
2. Lambda 側 `velocity_score` 急変・新記事追加時に push 配信
3. mypage.html「通知設定」タブで購読トピック ON/OFF 一覧

→ これは **T191-B「トピック購読通知（Web Push）」** として別タスク登録。

---

## 4. 本セッション（T191）の実装範囲

**設計ドキュメント** = 本ファイル（完了）

**コード実装**（小スコープに限定 — 設計合意なしに通知バックエンドへ進まない）:
- ✅ `app.js:renderCardMeta()` にカード単位「N分前 / N時間前 / N日前更新」相対時刻バッジを追加
- ✅ 過去 24h で記事増加あり (`articleCountDelta > 0`) のカードに「🔥 動き中」バッジ追加（既存 `📈 +N件` と差別化）

**別タスクへ分離**:
- T191-A「カード velocityScore グラフ可視化」(優先度: 中、フェーズ3 後半)
- T191-B「トピック購読通知 Web Push」(優先度: 高、フェーズ3 中盤、要設計)

---

## 5. 完了条件

- [x] 本ドキュメント (`docs/ux-flow-story.md`) を `main` に commit
- [x] `app.js` に相対時刻バッジ実装、本番 URL で目視確認
- [x] T191-A / T191-B を `TASKS.md` に新規 ID で登録
- [x] commit に `Verified: <url>:<status>:<timestamp>` 行
- [x] T191 を TASKS.md で取消線 → HISTORY.md 集約は次回 session_bootstrap で自動

---

## 6. 関連

- フェーズ3 (UX/成長): `docs/project-phases.md`
- ストーリー分岐の AI 判断方針: `docs/rules/story-branching-policy.md`（T2026-0428-BRANCH）
- 通知（メンション）既存実装: `frontend/mypage.html:1204–1246`
- お気に入り既存実装: `frontend/mypage.html:1408, 1415–1417`
