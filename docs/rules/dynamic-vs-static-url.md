# 動的 SPA URL vs 静的 SEO URL の役割分離 (T2026-0502-BI-PERMANENT 制定)

> このプロジェクトでは **動的 `topic.html?id=X` (ユーザー UX 一次)** と **静的 `topics/X.html` (Googlebot SEO 一次)** が並走している。
> どちらか片方に統一するのは禁止 (両方を別目的で必要としている)。**役割分離を破る変更は CI で物理 reject される**。
>
> 制定経緯: 2026-05-02 PR #288 (T2026-0502-BI) で「SEO のために内部リンク 22 箇所を静的 URL に統一 + CloudFront Function で動的→静的 301 redirect」を行った結果、ユーザー導線が薄い SEO ページに飛ばされ UX を破壊。即日 revert (PR #304) + 物理ガード化 (PR #305)。

## 役割分離の原則

| 観点 | 動的 SPA `topic.html?id=X` | 静的 SEO `topics/X.html` |
|---|---|---|
| **対象** | ユーザー (人間) | Googlebot / クローラー |
| **目的** | full UX (コメント / お気に入り / 関連トピック / ストーリー分岐 / 推移グラフ) | SEO 一次 (薄い AI まとめ + 関連記事 10 件 + アフィリエイト) |
| **discover 経路** | 内部リンク (app.js / detail.js / mypage.html / profile.html / catchup.html / storymap.html) | sitemap.xml / news-sitemap.xml |
| **canonical** | JS で `topics/X.html` (静的 URL) を inject | self (`topics/X.html` 自身) |
| **rendering** | Lambda は HTML 静的テンプレートを返す → JS で動的 fetch + render | `proc_storage.py` で AI まとめ・関連記事を埋め込んだ静的 HTML を生成 |
| **更新頻度** | 即時 (DDB / S3 を JS が読む) | 1 回 / トピックライフサイクル (processor がスナップショット生成) |
| **コメント等の動的データ** | API 経由で都度取得 | 表示しない (静的なので) |

## 守るべきルール (CI で物理化済)

### Rule 5 (`scripts/check_seo_regression.sh`): 動的 SPA 内部リンク必須

`frontend/{app.js,detail.js,mypage.html,profile.html,catchup.html,storymap.html}` の `<a href="...">` で **静的 URL `topics/X.html`** を指したら CI reject。

OK パターン:
```js
// 内部リンクは動的 SPA を指す
`<a href="topic.html?id=${esc(t.topicId)}" class="topic-card">`
```

NG パターン (CI が reject):
```js
// 静的 SEO ページに送るのは UX 破壊
`<a href="topics/${esc(t.topicId)}.html" class="topic-card">`
```

例外として OK:
```js
// share/canonical 用の絶対 URL (https://flotopic.com/topics/...) は
// SEO ページへの意図的参照なので除外。Rule 5 grep は `href="topics/...` (相対 URL) のみ検出。
const sharePageUrl = `https://flotopic.com/topics/${meta.topicId}.html`;
const url = `https://flotopic.com/topics/${btn.dataset.shareId}.html`;
```

### Rule 6: `topic.html` に SPA UX 要素必須

`projects/P003-news-timeline/frontend/topic.html` から以下が消えたら CI reject:

- `id="comments-section"` — コメントエリア
- `id="topic-fav-btn"` — お気に入りボタン
- `id="related-articles"` — 関連記事
- `id="discovery-section"` — Discovery (関連トピック・親子関係)
- `id="parent-topic-link"` — 親トピックリンク (ストーリー分岐)

これらが SPA UX の本体。「SEO 改善のために UX 要素を削除する」変更を物理的にブロック。

### Rule 7: 初期 canonical が id 無し `topic.html` 禁止

`topic.html` の `<link rel="canonical">` の初期 `href` が `topic.html` (id クエリ無し) を指したら CI reject。

OK パターン:
```html
<!-- 初期 href は空。JS が topicId 確定後に topics/${id}.html を inject -->
<link rel="canonical" id="canonical-url" href="">
```

NG パターン (CI が reject):
```html
<!-- Googlebot 初回 fetch (JS rendering 前) で「全 ID が topic.html 単独 URL に統合」誤シグナル -->
<link rel="canonical" id="canonical-url" href="https://flotopic.com/topic.html">
```

JS (`detail.js` L116-118) で topicId 確定後に書き換える:
```js
const canonical = document.getElementById('canonical-url');
if (canonical && meta.topicId) {
  canonical.setAttribute('href', `https://flotopic.com/topics/${meta.topicId}.html`);
}
```

## やってはいけないこと (PR #288 で実際に起きた違反)

1. **❌ 内部リンクを静的 URL に統一する** — ユーザー導線が SEO 専用ページに飛ぶ = UX 破壊
2. **❌ CloudFront Function で動的→静的 301 redirect** — 旧 SNS シェア・bookmark もすべて UX 破壊側に流す
3. **❌ 「動的 SPA 内部リンク禁止」を CI Rule 化** — 設計違反を物理ガード化してしまう (実際に PR #288 でやった)

## やるべきこと

- **canonical 統一は別経路で**: ①動的 SPA に noindex (PV 影響を Search Console で実測してから) / ②JS なしで初期 canonical を inject (Lambda@Edge / SSR) / ③bot-only redirect (cloaking 判定リスクあり) — これらは T2026-0502-BI-REDESIGN で候補比較
- **役割分離 doc (本ファイル) を内部リンク変更 PR で必ず参照**

## 関連

- `docs/lessons-learned.md` T2026-0502-BI-REVERT セクション
- `scripts/check_seo_regression.sh` Rule 5/6/7
- PR #288 (T2026-0502-BI・UX 破壊事故) / PR #304 (T2026-0502-BI-REVERT・復旧) / PR #305 (T2026-0502-BI-PERMANENT・物理ガード化)
