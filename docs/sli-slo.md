# Flotopic SLI / SLO 一覧（外部観測ベース）

> **このファイルの位置づけ**: 「ユーザーから見える壊れ方」を 1 ファイルで定義する。
> 各 SLI には **再現可能な curl/jq コマンド** を併記して「Lambda 内部 metric だけで設計するな」を物理化する。
>
> **背景**: 2026-04-28 の 14h 鮮度ゼロ事故 (lessons-learned 参照) で「success-but-empty」を CloudWatch では拾えないことが判明。
> 外部観測 SLI を体系化することで「動いてる気になっていた」を技術的に防ぐ。

---

## トップレベル SLI（最低限のユーザー体験）

| # | SLI | 観測コマンド | 警告閾値 | 監視ファイル | 担当層 |
|---|---|---|---|---|---|
| 1 | **topics.json 鮮度** | `curl -s https://flotopic.com/api/topics.json \| jq -r .updatedAt` と現在時刻の差 | 90 分超で stale | `.github/workflows/freshness-check.yml` (1h cron) | 外部観測 (T263) |
| 2 | **トップページ HTTP/2 200** | `curl -sI https://flotopic.com/ \| head -1` | 5xx / 4xx で警告 | (未実装・TBD) | 外部観測 |
| 3 | **AI 要約カバレッジ** | `curl -s .../topics.json \| jq '[.topics[] \| select(.aiGenerated)] \| length / ([.topics[]] \| length) * 100'` | 70% 未満で警告 | (未実装・TBD) | 外部観測 |
| 4 | **storyPhase 分布の偏り** | `curl -s .../topics.json \| jq '[.topics[].storyPhase] \| group_by(.) \| map({phase:.[0], n:length})'` | 「発端」が 50% 超で警告 | T258 (T255 連動解消後に再評価) | 外部観測 |
| 5 | **fetcher Lambda 成功率** | CloudWatch `Errors` metric / `Invocations` metric | 24h で 5% 超失敗 | governance worker | 内部 metric |
| 6 | **AdSense ads.txt 整合** | `curl -s https://flotopic.com/ads.txt` と index.html の `ca-pub-` 突合 | 不整合で CI fail | `.github/workflows/ci.yml` content-drift-guard (T239) | CI 物理ガード |
| 7 | **セキュリティヘッダ** | `curl -sI https://flotopic.com/ \| grep -iE "strict-transport\|x-frame\|csp\|permissions-policy"` | 必須ヘッダ欠落で警告 | (未実装・TBD `scripts/security_headers_check.sh`) | 外部観測 |
| 8 | **keyPoint 充填率 (success-but-empty 検出)** | `curl -s .../topics.json \| jq '[.topics[] \| select(.articleCount>=3) \| select(.keyPoint != null)] \| length'` ÷ `[.articleCount>=3]` 件数 | 70% 未満で警告 | `freshness-check.yml` ai_fields step (2026-04-28 追加) | 外部観測 |
| 9 | **perspectives 充填率** | 同 SLI 8 で `.perspectives` を対象 | 60% 未満で警告 | `freshness-check.yml` ai_fields step | 外部観測 |
| 10 | **background 充填率** | 同 SLI 8 で `.background` または `.backgroundContext` を対象 | 60% 未満で警告 | `freshness-check.yml` ai_fields step | 外部観測 |
| 11 | **sitemap URL 到達性** | `news-sitemap.xml` から topics/{tid}.html を抽出し HEAD 200 を 5 件サンプリング | 1 件でも非 200 で警告 | `freshness-check.yml` sitemap_reach step (2026-04-28 schedule-task で追加) | 外部観測 |

---

## SLI 1: topics.json 鮮度（実装済み）

**定義**: `https://flotopic.com/api/topics.json` の `updatedAt` が現在時刻から 90 分以内であること。

**根拠 (Why this SLI)**: スケジュール (JST 01/07/13/19) は 6h 間隔。1 サイクル飛ばしても 90 分閾値なら次サイクル前には警告される設計。

**観測:**
```bash
curl -s https://flotopic.com/api/topics.json \
  | python3 -c "
import json, sys, datetime as dt
d = json.load(sys.stdin)
ua = d.get('updatedAt','')
t = dt.datetime.fromisoformat(ua.replace('Z','+00:00'))
diff = (dt.datetime.now(dt.timezone.utc) - t).total_seconds() / 60
print(f'updatedAt={ua} diff={diff:.1f}min status={\"FRESH\" if diff<=90 else \"STALE\"}')
"
```

**警告ルート:**
1. GH Actions cron (`freshness-check.yml`) が毎時 07 分 UTC に実行
2. stale なら Slack `:warning:` + GH Actions UI に赤エラー
3. governance worker と別系統のため governance 自身が壊れた時にも検知できる

**閾値根拠**: 90 分 < スケジュール間隔 6h × 0.25。1 サイクル空振りまでは許容、2 サイクル空振りで stale 確定。

---

## SLI 2: トップページ HTTP ステータス（未実装・TBD）

**定義**: `https://flotopic.com/` および `/api/topics.json` が HTTP/2 200 を返すこと。

**実装案**: `freshness-check.yml` を拡張し、ステータスコードもチェック。

**観測:**
```bash
curl -sI https://flotopic.com/ | head -1
# HTTP/2 200 を期待
```

---

## SLI 3: AI 要約カバレッジ（未実装・TBD）

**定義**: topics.json の可視 (lifecycleStatus != archived) トピックのうち aiGenerated=True が 70% 以上。

**根拠**: 70% 未満は「pending queue が処理しきれていない」シグナル。T237 / T218 wallclock guard のリグレッション検出。

**観測:**
```bash
curl -s https://flotopic.com/api/topics.json \
  | python3 -c "
import json, sys
d = json.load(sys.stdin)
visible = [t for t in d.get('topics', []) if t.get('lifecycleStatus') != 'archived']
ai = [t for t in visible if t.get('aiGenerated')]
ratio = len(ai) * 100 / max(len(visible), 1)
print(f'visible={len(visible)} ai={len(ai)} ratio={ratio:.1f}%')
"
```

**現状実測 (2026-04-28 06:10 JST)**: 117 件中 93 件 = 79.5% (FRESH)

---

## SLI 8/9/10: 必須 AI フィールド充填率（実装済み・2026-04-28 schedule-task で追加）

**定義**: `articleCount>=3` のフル要約対象トピックのうち、必須 AI フィールド (keyPoint / perspectives / background) が埋まっている割合。

**根拠 (Why this SLI)**: 2026-04-28 schedule-task で `aiGenerated=True` でも keyPoint 充填率 11.5% (6/52) という半壊状態を発見。SLI 3 (AI カバレッジ 79.5%) は通るが、ユーザーから見た品質は壊れていた。「success-but-empty」を AI 生成側にも横展開した SLI。

**観測:**
```bash
curl -s https://flotopic.com/api/topics.json | python3 -c "
import json, sys
d = json.load(sys.stdin)
full = [t for t in d['topics'] if t.get('articleCount',0) >= 3]
kp = sum(1 for t in full if t.get('keyPoint'))
persp = sum(1 for t in full if t.get('perspectives'))
bg = sum(1 for t in full if t.get('background') or t.get('backgroundContext'))
n = max(len(full), 1)
print(f'full={len(full)} kp={kp*100/n:.1f}% persp={persp*100/n:.1f}% bg={bg*100/n:.1f}%')
"
```

**警告ルート**: `freshness-check.yml` の `ai_fields` step が 1h cron で観測 → 閾値未満で Slack 警告 + GH Actions warning。

**閾値根拠**:
- keyPoint 70%: 必須中の必須。一覧画面の要約として表示される。
- perspectives 60%: 詳細画面のみで使用。少し緩く。
- background 60%: 同上。

**現状実測 (2026-04-28 06:10 JST)**: keyPoint 11.5%・perspectives 26.9%・background は要 grep。**全 SLI 警告中**。T255 修正後の cycle がまだ反映されていないため、次回 13:00 JST cycle 完了後に再観測必要。

---

## SLI 6: ads.txt と pub-id 整合（実装済み）

**定義**: `frontend/ads.txt` と `frontend/index.html` の `ca-pub-` が一致していること。

**根拠**: 2026-04-27 に AdSense 行欠落で審査が止まった事故 (lessons-learned 参照)。

**実装**: `.github/workflows/ci.yml` content-drift-guard ジョブで pre-merge ガード (T239)。

---

## 参考: SLI を増やす時のテンプレ

新しい SLI を追加する時は **必ず再現可能な curl/jq コマンドを併記する**。Lambda metric だけで設計しない (lessons-learned「production 鮮度 SLI が無くて 14h 壊れに気付かなかった」を再発させない)。

```markdown
## SLI N: <名前>

**定義**: <数値ベースの判定条件>
**根拠**: <なぜこの SLI が必要か。どんな事故を防ぐか>
**観測:**
\`\`\`bash
<コマンド>
\`\`\`
**警告ルート**: <CI / cron / Slack / governance のどこ>
**閾値根拠**: <数字の出所>
```
