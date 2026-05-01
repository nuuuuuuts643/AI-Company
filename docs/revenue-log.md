# Flotopic 収益ログ（週次）

> 毎週月曜に忍者AdMax管理画面から手動転記。SLIと突合して品質→収益の相関を確認する。
> 月次の自動レポートは `dashboard/revenue-log.md` にある（責務分離）。
> このファイルは「品質改善が収益に効いたか」を観測するための主観・客観混合ログ。

## 観測の狙い

1. **PV (Cloudflare Analytics)** — 鮮度・トピック密度・SEOの効果
2. **表示回数 / クリック / CTR (忍者AdMax)** — 広告枠の認知・関連性
3. **収益 (¥)** — 最終アウトカム
4. **品質SLI (keyPoint / perspectives 充填率)** — 改善前後の数値
5. **備考** — 大きな変更（プロンプト変更・広告位置調整など）の自由記述

CTR が品質SLIと弱相関でも、PV増 × CPM維持で収益は伸びうる。逆に CTR が落ちたら原因（広告位置・関連性）を探す。

## 転記ワークフロー

1. 毎週月曜朝、忍者AdMax管理画面 (https://admax.ninja/) を開く
2. 先週月曜〜日曜の集計を新しい行に転記する
3. PV は admin.html (https://flotopic.com/admin.html) の「Cloudflare Analytics」から取得（直近7日PV）
4. SLI は GitHub Actions の `freshness-check.yml` / `sli-keypoint-fill-rate.yml` の最新値を見る
5. 転記後 `git push`。`revenue-sli.yml` (週次CI) が `revenue_check.sh` で 8日以上更新が無いと Slack 警告を出す

## 履歴

| 週 | PV(7d) | 表示回数 | クリック数 | CTR | CPM/RPM | 収益(円) | keyPoint充填率 | perspectives充填率 | 備考 |
|---|---|---|---|---|---|---|---|---|---|
| 2026-04-W4 | 910 | - | - | - | - | - | 22.3% | 44.7% | 計測基準週 (忍者AdMax設置直後・PVはcf-analytics.json実測) |
| 2026-04-月次合計 | - | 691 | 2 | 0.29% | - | ¥0(予想¥2) | - | - | 4/1-4/30累計。表示は4/25以降に集中（グラフ確認）。AdMax設置後初月 |

## 補足

- **「-」の扱い**: その項目を取得できていない週は `-`。後日埋まったら更新可。
- **週ラベル**: ISO8601 ではなく `YYYY-MM-WN` (その月の第N週・月曜起算) を採用。
- **欠測警告**: `revenue-sli.yml` が CI で最新行の日付をチェック。8日超 → Slack 警告。
