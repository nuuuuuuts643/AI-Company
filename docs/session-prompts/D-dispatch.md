# セッションプロンプト: D起動 (Dispatch 継続)

> 起動トリガー: 「D起動」

## 用途

前セッションの続きを Dispatch (Cowork) で進める汎用エントリ。
具体的な指示は `WORKING.md`「Dispatch継続性」に書いてあるので、毎回ここを起点に拾う。

## セッション本体

**モデル: Haiku（軽い判断）/ Sonnet（重い判断・コードセッション準備）**

```
P003 Dispatch セッション継続。

【手順】
1. `bash ~/ai-company/scripts/session_bootstrap.sh` 実行
2. `cat ~/ai-company/WORKING.md` で「Dispatch継続性」セクションを読む
3. `cat ~/ai-company/WORKING.md | grep "\[Code\]"` で並走中の Code セッションを確認
   → 1件以上あれば新規 Code セッション起動禁止（観測のみ）
4. WORKING.md「次セッションでやること」を順に処理
   - SLI実測・状態整理・TASKS.md整備など軽い仕事は自分で
   - コードセッション必要なら TASKS.md に [NEEDS-CODE] で積んで PO に渡す
5. 完了後: WORKING.md「Dispatch継続性」を最新化して `cowork_commit.py` で push

【複数レイヤー解釈可能用語のチェックリスト（PR #120 の教訓）】
「スケジュール」「cron」「コアタイム」「監視」など複数レイヤーで解釈できる用語が
PO 指示に出てきたら、勝手に解釈せず AskUserQuestion で対象を明示確認すること。

【ルール】
- 20往復で必ず停止（暴走防止）
- ¥発生する操作禁止（Lambda invoke / Anthropic API直叩き / paid AWS write 等）
- main 直 push 禁止（cowork_commit.py が物理ブロック）
- コード直接編集は WORKING.md に [Cowork] 行を明記してから

【参考】
- 現在のフェーズ: `docs/project-phases.md` 先頭30行
- プロダクト方針: `docs/product-direction.md`
- 規則: `CLAUDE.md`（250行以内・常時最新）
- 既存スケジュールタスク: p003-haiku (07:08 daily) / p003-dispatch-auto-v2 (4x/日 08/13/18/22 JST) / p003-sonnet (手動)
```

## 終了条件

- WORKING.md「Dispatch継続性」が最新タイムスタンプで上書きされている
- 必要なタスクが TASKS.md に積まれている or 既存 Code セッションに渡されている
- 自分の [Cowork] 行は WORKING.md から削除して push 済
