# Code セッション起動 prompt: T2026-0502-COST-D1-INVESTIGATE

> 用途: 真の削減本命 (DynamoDB Read $4.02/月) の元を特定する深掘り調査セッション
> 関連: docs/cost-reduction-plan-2026-05-02.md §8.4 / §8.6
> 推奨モデル: **Sonnet** (コードベースの読解 + 分析)
> 想定所要: 1〜2 時間

---

## prompt 本文 (これを Code セッションに渡す)

```
docs/cost-reduction-plan-2026-05-02.md の §8 (深掘り調査結果) を読んでください。

## 背景

2026年4月の AWS 実コストは月 $11、うち DynamoDB Read $4.02 が最大。
Lambda / API Gateway / CloudFront / CloudWatch は全て無料枠内 ($0)。
真の削減ターゲットは DynamoDB Read / Write / S3 PUT の 3 つだけ。

## 目的

T2026-0502-COST-D1 (DynamoDB Read 削減) を実装可能なレベルまで掘る。
**コード変更はまだしない**。調査結果を docs/cost-reduction-plan-2026-05-02.md §9 として追記し PR を出す。

## 調査項目

1. **DynamoDB Read を発生させているコードパスを全部洗い出し**
   - lambda/ 配下で boto3 dynamodb の Scan / Query / GetItem / BatchGetItem を使っている箇所
   - 各箇所がいつ・何回・どのテーブルを読むか
   - 期待される結果: 関数別・テーブル別の読み取り頻度マトリクス

2. **既に S3 (topics-card.json 等) で同じデータを配信している経路を確認**
   - frontend/ から見える API_BASE は何で、どの URL が DynamoDB 読みを伴うか
   - CloudFront cache hit ratio がわかる仕組みがあるか

3. **削減施策の優先度付け**
   - 「読み取りが多い + S3 化が容易」を上位
   - 「読み取りは多いが書き込みも多くて整合性敏感」は中位 (例: rate-limits)
   - 「書き込みより読み取り少ない」は下位

4. **最大効果見込みの 1 候補を選んで設計案を docs に追記**
   - 例: lambda/api/handler.py の `/topics/list` を S3 直接配信に切替
   - 既存 topics-card.json をそのまま CloudFront 経由で返す方式
   - 設計案 + リスク + 実装ステップ + 推定削減 ($)

## 手順

1. 新 branch 切る
   git checkout main && git pull --rebase origin main
   git checkout -b chore/T2026-0502-COST-D1-INVESTIGATE

2. WORKING.md に [Code] 行追加
3. lambda/ 配下を grep で網羅
   grep -rn "boto3\\.resource('dynamodb')\\|boto3\\.client('dynamodb')\\|\\.Table(\\|\\.Scan(\\|\\.Query(\\|\\.GetItem(\\|\\.BatchGetItem(" lambda/

4. 関数別に呼び出しパターン整理
5. docs/cost-reduction-plan-2026-05-02.md に §9 として「DynamoDB Read 元コード分析」を追記
6. commit + PR (chore: ... 形式・ファイル変更は docs のみ)
7. WORKING.md から自分の行削除

## 完了条件

- §9 に DynamoDB Read 発生箇所の網羅リスト (関数・テーブル・呼出頻度推定)
- 1 候補の具体設計案 (実装ステップ・リスク・期待削減 $)
- PR merge 済

## 注意

- **コード変更は禁止**。lambda/ 配下を読むだけ
- 削除や設定変更も禁止 (調査のみ)
- 既存の C1 タスク (p003-topics 読取 S3 化) と重複しないようにスコープ調整
```

---

## チェックリスト

- [ ] §9 セクションが docs/cost-reduction-plan-2026-05-02.md に追記
- [ ] 関数別・テーブル別の読み取りマトリクス
- [ ] 1 候補の具体設計案
- [ ] PR URL + merge 済確認
