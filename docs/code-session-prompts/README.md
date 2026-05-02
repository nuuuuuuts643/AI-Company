# Code セッション起動 prompt 集

> Cowork デスクトップから「コードセッションを起動」する際にコピペで使う prompt をここに置く。
> 1 ファイル = 1 タスク。原則 1 PR で完結する粒度。

---

## 一覧 (2026-05-02 時点)

| ファイル | タスク | 推奨モデル | 所要 | 状態 |
|---|---|---|---|---|
| [T2026-0502-COST-A1-CODE.md](T2026-0502-COST-A1-CODE.md) | 未使用 DynamoDB 4 個整理 (deploy.sh + 実 delete) | Sonnet | 30 分 | 起動待ち |
| [T2026-0502-COST-D1-INVESTIGATE.md](T2026-0502-COST-D1-INVESTIGATE.md) | DynamoDB Read $4.02/月 の元コード特定 (調査のみ) | Sonnet | 1〜2 時間 | 起動待ち |
| [T2026-0502-BC-CRON-FIX.md](T2026-0502-BC-CRON-FIX.md) | judge_prediction 専用 22:00 JST cron 追加 + コメント乖離修正 | Sonnet | 30〜60 分 | 起動待ち |

---

## 使い方

1. Cowork デスクトップで「コードセッション起動」を選択
2. このフォルダから対象 `.md` を開く
3. 「prompt 本文」セクションの ``` ブロック内をコピー
4. Code セッションに貼り付けて起動
5. 推奨モデル欄の通りに `model` パラメータを設定

## 追加ルール

- 新規 prompt を作成するときは本 README の一覧表にも追記する
- 1 prompt = 1 PR が原則。複数 PR が必要なものは分割する
- 削減プラン本体は `docs/cost-reduction-plan-2026-05-02.md` を参照
