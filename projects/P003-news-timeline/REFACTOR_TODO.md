# フロントエンド リファクタ候補一覧

> 作成: 2026-04-27 調査。将来ビジョン（ナレッジグラフ・縦階層・横波及・予測テキスト）に向けた保守性改善を目的とする。
> 実際のコード変更は1件ずつTASKS.mdに起票して実施する。

---

## ✅ 実施済み
- `let _nativeAdIdx = -1;`（app.js:104）を削除 — 定義のみで一切参照なしのデッドコード（2026-04-27）

---

## 1. デッドコード（JS）

### `_nativeAdIdx`（削除済み）
- **場所**: `app.js:104`（削除済み）
- **内容**: `let _nativeAdIdx = -1;` 定義のみ、app.js / detail.js / その他どこからも参照なし

---

## 2. デッドCSSクラス（優先度順）

### ① `.keyword-chip` 系 7ルール ← 最大の削除候補
- **場所**: `style.css:1869-1884, 2213-2219, 2599-2600`
- **問題**: app.jsは `.kw-chip` を生成する。`.keyword-chip` はどのHTML/JSからも参照されていない
- **削除安全性**: ✅ 完全デッド（grep全ファイルで未使用確認）
- **影響行数**: 約12行（ライト + ダーク）

### ② `.topic-status.new` / `.status-badge.new` 2ルール
- **場所**: `style.css:430, 680`
- **問題**: データモデルの status は rising/peak/declining/cooling のみ。'new' は STATUS_LABEL にも存在しない
- **削除安全性**: ✅ 完全デッド
- **影響行数**: 2行

### ③ `.card-summary` / `.card-snippet` / `.card-attribution`
- **場所**: `style.css:461-478, 539-543`
- **問題**: app.js / detail.js / HTML から参照なし
- **削除前確認**: `grep -rn "card-summary\|card-snippet\|card-attribution" frontend/` で再確認してから削除
- **影響行数**: 約20行

### ④ `.mypage-link-btn` 系（後方互換コメントあり）
- **場所**: `style.css:209-215`
- **コメント**: `/* 後方互換 */` と書いてあるが、どこからも参照なし
- **削除安全性**: △ 「後方互換」コメントがあるため要調査。grep確認後に削除
- **影響行数**: 5行

### ⑤ `.metrics-grid`
- **場所**: `style.css:1004-1010`
- **問題**: HTML / JSから参照なし
- **削除安全性**: ✅ 完全デッド
- **影響行数**: 7行

---

## 3. CSS重複定義（優先度順）

### ① `.keyword-strip` 2重定義
- **場所**: `style.css:1851-1868`（1回目）と `style.css:2476-2491`（2回目）
- **問題**: 同じセレクターが2箇所に存在。後の定義が前を部分的に上書きしているが意図が不明瞭
- **対処**: 1回目の定義を削除し、2回目（より完全な定義）に統一する

### ② `[data-theme="light"]` 2重定義
- **場所**: `style.css:2462-2469`（1回目・簡易版）と `style.css:2557-2566`（2回目・詳細版）
- **問題**: 2箇所に分散。後の定義に統合すべき
- **対処**: 1回目（6行）を削除し、2回目に不足していたプロパティをマージ

### ③ `[data-theme="dark"] .disc-card` 2重定義
- **場所**: `style.css:2281-2286`（`@media prefers-color-scheme:dark` 内）と `style.css:2325`（同一ブロック内）
- **問題**: 同じセレクターが同一 media query ブロック内に2回存在

### ④ 同値デザイントークン（整理候補）
- `--shadow` と `--shadow-sm` は値が同一（`0 2px 8px rgba(0,0,0,0.08)`）
- `--shadow-md` と `--shadow-hover` は値が同一（`0 6px 20px rgba(0,0,0,0.12)`）
- `--accent-cyan` / `--accent-blue` / `--accent-purple` がすべて `#4EC9C0`（シアン統一後の残骸）
- **対処**: 重複トークンを削除し参照箇所を統一トークン名に変更

---

## 4. ハードコードカラー（`var(--color-*)` 移行候補）

バグ再発防止ルール「CSS意味色のハードコード禁止」に基づく。

| 場所 | 現在値 | 移行先 |
|---|---|---|
| `style.css:545` `.new-articles-delta` | `#22c55e` | `var(--color-success)` ※変数新設が必要 |
| `style.css:546` `.phase-change-badge` | `#f59e0b`（bg） | `var(--color-warning)` ※変数新設が必要 |
| `style.css:2891` `.affiliate-label` | `#f59e0b`（bg） | `var(--color-warning)` |
| `style.css:338` `.filter-btn.active border` | `#4EC9C0` | `var(--primary)` |

---

## 5. HTMLボトムナビ不整合

### catchup.html に `id="bottom-nav"` が欠落
- **場所**: `catchup.html:751`
- **問題**: `initBottomNav()` が `document.getElementById('bottom-nav')` を参照するが、catchup.htmlでは id が存在しないため呼び出し不発。マイページバッジ更新が動かない
- **修正**: `<nav class="bottom-nav" aria-label="...">` → `<nav class="bottom-nav" id="bottom-nav" aria-label="...">`
- **影響**: 1文字変更、安全

### ナビアイテムの実装差異（機能的問題なし）
- index.html / topic.html: 検索 = `<button>` タグ（JSでフォーカス制御）
- catchup.html / mypage.html: 検索 = `<a href="index.html?focus=search">` タグ（リンク遷移）
- どちらの動作も意図通り機能しているが、統一したほうが保守性が上がる

---

## 6. JS分割の将来境界（将来ビジョン対応）

現在 `app.js` 1263行に全機能が集中。以下の境界で分割すると将来機能の追加が容易になる。

```
app.js（現在）
│
├── topic-filter.js ← 抽出候補
│   buildFilters(), applyGenreDiversity(), renderTrendingGenres()
│   setupSearch()
│
├── topic-render.js ← 抽出候補
│   renderTopicCard(), renderCardMeta(), renderBadges()
│   renderReliabilitySignal()
│
├── topic-strips.js ← 抽出候補
│   renderReturnStrip(), renderFavStrip(), renderQuickNews()
│   showTrendingBanner(), renderKeywordStrip()
│
├── knowledge-graph.js ← 将来新設
│   childTopics / parentTopicId の描画ロジック（現在 renderTopicCard 内に混在）
│   ナレッジグラフ表示・縦階層・横波及の入口
│
└── app.js（本体）← 残す
    DOMContentLoaded, refreshTopics(), onboarding, PWA, SW登録
    loadTopics(), updateFreshnessDisplay()
```

**分割の前提条件**（先に整備する）:
1. デッドコード・重複CSSを削除してノイズを除去
2. `topic-filter.js` の境界を先に切り出す（依存が少なく独立性が高い）
3. `knowledge-graph.js` は childTopics の renderTopicCard 内ロジックを先に抽出

---

## 7. タイトル・メタ description の不統一（コピーライティング）

CLAUDE.mdの「コード上で実際に見つかった文脈ミスマッチ」⑥と重複するが記録しておく。

| ページ | title | description |
|---|---|---|
| index.html | 話題の盛り上がりをAIで追う | 大きなニュースの流れを、1分で把握。AIがトピックをまとめ、時系列で可視化。30分ごと自動更新。 |
| topic.html | トピック詳細 | このトピックの時系列推移をAIが分析。 |
| catchup.html | 振り返る | 直近のニュースをキャッチアップ。過去N日間に話題になったトピックを一覧で確認。 |
| mypage.html | マイページ | お気に入りトピックや閲覧履歴を確認できるマイページ。 |

- topic.html の description は動的に書き換えられる（detail.jsで）ため静的 description は補完的な役割
- catchup.html の「過去N日間」が文字通り「N」のまま（プレースホルダーが残っている可能性）

---

## 優先順位付け

| 優先度 | タスク | 難易度 | リスク |
|---|---|---|---|
| ★★★ | catchup.html に `id="bottom-nav"` 追加 | 低 | 低 |
| ★★★ | `.keyword-chip` CSS 7ルール削除 | 低 | 低 |
| ★★ | `.keyword-strip` 重複定義を統合 | 中 | 低 |
| ★★ | `.topic-status.new` / `.status-badge.new` 削除 | 低 | 低 |
| ★★ | `[data-theme="light"]` 重複定義を統合 | 中 | 低 |
| ★ | ハードコードカラーを CSS 変数化（--color-success 等を新設） | 中 | 中 |
| ★ | `topic-filter.js` 抽出 | 高 | 中 |
| ★ | `knowledge-graph.js` 境界設計・抽出 | 高 | 高 |
