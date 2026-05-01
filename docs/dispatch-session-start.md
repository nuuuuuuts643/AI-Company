# Dispatch セッション開始テンプレート

> **最新プロンプトを自動生成する**: `bash scripts/gen_dispatch_prompt.sh | pbcopy`
> Mac のクリップボードにコピーされる。そのまま新しい Cowork セッションに貼り付ける。
> スクリプトが WORKING.md・TASKS.md の現在状態を自動で埋め込むため、毎回更新不要。

---

## ▼ スクリプト生成（推奨・常に最新状態が入る）

```bash
bash scripts/gen_dispatch_prompt.sh | pbcopy
```

または標準出力で確認してから貼り付ける:

```bash
bash scripts/gen_dispatch_prompt.sh
```

---

## ▼ 固定テンプレート（スクリプト使えない場合）

```
P003 Dispatch。ルール通りに動いて。

1. session_bootstrap.sh を実行して起動チェックを完了させる
2. WORKING.md の Dispatch継続性セクションで状態を把握する
3. TASKS.md で現フェーズの未着手タスクを確認し、優先順に実行する
4. 確認・報告・承認を求めず、ルールに従って前進する
5. 重大な判断（新規AWS課金・不可逆操作）のみ事前確認する
6. タスク完了後は flotopic.com で実機確認してから「完了」と報告する
```

---

## ▼ より短い版（慣れたら）

```
P003 Dispatch。ルール通り前進して。
```

---

## 備考

- CLAUDE.md に全ルールが書いてある。追加説明は不要
- 「何をすべきか」は WORKING.md Dispatch継続性 → TASKS.md → product-direction.md の順で自分で判断する
- PO からの個別指示がなければ、TASKS.md の現フェーズ優先タスクを自律実行する
- コードセッション起動・p003-sonnet 手動実行・WORKING.md 更新はすべて Dispatch 権限内
- **実機確認必須**: タスク完了を宣言する前に flotopic.com でブラウザ確認すること（2026-05-01 制定）

## ▼ ルール変更時の更新手順

1. `docs/dispatch-session-start.md`（本ファイル）の固定テンプレートを更新
2. `scripts/gen_dispatch_prompt.sh` の cat ヒアドキュメント部分を更新
3. 必要なら `CLAUDE.md` の Dispatch絶対禁止パターン表も更新
4. commit & push → 次セッションから自動反映
