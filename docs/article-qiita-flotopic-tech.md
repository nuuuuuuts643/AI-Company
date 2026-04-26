# AIでニュースの「流れ」を可視化するサービスを個人で作った話（技術編）

> **投稿先**: Qiita または Zenn（技術記事）
> **目的**: SEO 被リンク獲得・Flotopic への流入促進
> **ターゲット**: Python/AWS に興味のある個人開発者

---

## はじめに

「ニュースを読んでいるはずなのに、翌日には何も残っていない」

この問題を解決するために **[Flotopic](https://flotopic.com)** を作りました。速報を届けるのではなく、同じ話題の記事を束ねて「始まり〜推移〜終息」の流れをAIで整理するサービスです。

この記事では、Flotopic の技術スタックと面白かった実装を紹介します。

---

## サービスの概要

- **URL**: https://flotopic.com
- **機能**: 国内主要メディアの RSS フィードを 30 分ごとに収集し、同じ話題の記事を自動クラスタリング。Claude AI が「何が起きたか」「なぜ広がったか」「今どの段階か」「今後どうなるか」を 4 セクションで分析
- **技術スタック**: Python (Lambda) / DynamoDB / S3 / CloudFront / Anthropic Claude API

---

## アーキテクチャ

```
RSS フィード (30+ 媒体)
    ↓ 30分ごと
p003-fetcher (Lambda)
    ↓ DynamoDB に保存
p003-processor (Lambda, 1日4回)
    ↓ Claude Haiku でAI分析
S3 (静的JSON + 静的HTML)
    ↓ CloudFront
flotopic.com
```

Lambda + DynamoDB + S3 の完全サーバーレス構成です。月額コストは約 $10〜15 程度。

---

## 実装で面白かった部分

### 1. 記事のクラスタリング（トピック判定）

同じ話題を報じる記事を束ねる処理が肝です。

```python
def cluster(articles):
    # 記事タイトルを正規化してバイグラム + 単語集合を比較
    # Jaccard 類似度が閾値を超えたら同じトピックとして Union-Find でまとめる
    ...
    # カタカナ固有名詞（5文字以上）を共有する場合は1単語でも結合
    has_strong_entity = any(_KATAKANA_LONG.match(w) for w in shared)
    min_shared = 1 if has_strong_entity else 2
    if len(shared) < min_shared:
        continue
    if len(shared) / len(wi | wj) >= JACCARD_THRESHOLD:
        union(i, j)
```

「トランプ大統領」「ゼレンスキー」「エヌビディア」など5文字以上のカタカナ固有名詞を共有する記事は、他の条件が弱くても同一トピックとして扱います。

### 2. トピックのライフサイクル管理

話題には寿命があります。Flotopic では以下のフェーズを定義しています。

| フェーズ | 説明 |
|---|---|
| 発端 | 最初の報道が出た段階 |
| 拡散 | 複数メディアが追随 |
| ピーク | 最も記事が集中 |
| 現在地 | 報道が落ち着きはじめ |
| 収束 | 話題が一段落 |

これを Claude に判定させています。また、30 日以上新しい記事が届かないトピックは強制的に `archived` 状態に移行し、トップ画面から非表示にします。

### 3. Claude API のコスト最適化

Claude Haiku を使っていますが、記事数に応じて処理を 3 段階に分けてコストを抑えています。

```python
def generate_story(articles, article_count):
    if cnt <= 2:
        return _generate_story_minimal(articles)   # 1段落のみ (max_tokens=200)
    elif cnt <= 5:
        return _generate_story_standard(articles)  # 概要+タイムライン (max_tokens=500)
    else:
        return _generate_story_full(articles)      # フル4セクション (max_tokens=900)
```

1〜2 記事のトピックにフル分析をかけても意味がないので、記事数で分岐しています。

### 4. RSS `<description>` の活用

RSS フィードには記事の概要文（100〜500文字）が `<description>` タグに入っています。これを AI プロンプトに含めることで、タイトルだけよりずっと文脈豊かな分析ができるようになりました。

```python
desc = re.sub(r'<[^>]+>', '', raw_desc).strip()
if desc and (desc == title or len(desc) < 30 or
             re.search(r'続きを読|全文表示|もっと見る', desc)):
    desc = ''  # 意味のない説明は除外
desc = desc[:200]
```

「続きを読む」「記事全文」等の無意味な説明文は除外しています。

### 5. 静的 HTML 生成で Googlebot に対応

SPA（JavaScript で描画）のページは Googlebot がコンテンツを読み取れないケースがあります。Flotopic では、AI 分析完了後に各トピックの静的 HTML を S3 に生成しています。

```
s3://flotopic-bucket/topics/{topicId}.html
```

Python の標準ライブラリだけで HTML を組み立てて S3 に put するシンプルな実装です。sitemap.xml にも `/topics/*.html` の URL を含めることで、Google が全コンテンツをインデックスできます。

---

## やってみてわかったこと

### DynamoDB の注意点

- **SK（ソートキー）は `FilterExpression` に使えない**。`KeyConditionExpression` で指定する必要があります。はまりました。
- DynamoDB の `velocityScore` は計算時点の値をそのまま保存するため、古いデータが「速度あり」のまま残ります。週次の lifecycle Lambda で 30 日超のトピックを強制 archived にして対処しました。

### Claude API の 429 対策

```python
def _call_claude(payload, timeout=25):
    delay = 5
    for attempt in range(4):
        try:
            ...
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 3:
                retry_after = e.headers.get('retry-after')
                wait = int(retry_after) if retry_after else delay
                time.sleep(wait)
                delay *= 2
            else:
                raise
```

指数バックオフで最大 3 回リトライします。Lambda のタイムアウトを考慮して、合計待ち時間が長くなりすぎないよう注意が必要です。

---

## まとめ

- RSS → クラスタリング → AI 分析 → 静的 HTML の完全自動パイプラインを Lambda で構築
- Claude Haiku を使った AI 分析は記事数に応じて 3 段階に分岐してコスト最適化
- 静的 HTML 生成で Googlebot への SEO 対応
- DynamoDB は SK の扱いに注意、ライフサイクル管理は週次バッチで自動化

**[Flotopic](https://flotopic.com)** はニュースの「流れ」を追いたい方にぜひ使ってみてください。フィードバックは [お問い合わせ](https://flotopic.com/contact.html) からどうぞ。

---

*ソースコードは非公開ですが、実装の詳細についてはコメントで質問していただければ答えます。*
