# P002 ブリーフィング

## 概要
要塞都市育成ゲーム（Unity）。スマホ縦画面、日本語UI、波ごとに敵が攻めてくる防衛ゲーム。

## 現状
- last_run: 2026-04-20
- status: C#スクリプト一式完了・Unity Editor上での組み上げ待ち
- done_this_run: 既存スクリプトの状態確認

## Unity プロジェクトパス
```
/Users/murakaminaoya/ai-company/projects/P002-unity-game/P002-unity-game/
```

## 完了条件（Phase 1 Playable）
- [x] Phase1 コアスクリプト16本
- [x] Phase2 スクリプト10本
- [x] 日本語フォント自動検出
- [x] 敵データ（ScriptableObject）作成済み
- [ ] Unity Editor上でシーン組み上げ（GameSetupウィザード実行）
- [ ] プレイテスト（Play → 波が来る → 防衛できる）
- [ ] UI表示確認（HUD、フローティングテキスト、EnemySide）

## next_action
- Claude: スクリプトのエラー・TODO・未実装箇所を精査して修正できるものは修正する
- 社長（ブロッカー）: Unity Editorを開いて `FortressCity > Setup Everything` を実行 → Playボタン押してテスト

## ブロッカー
**Unity Editor操作が必要**
Unity上でのシーン組み立て・動作確認はClaudeが代替できない。
社長がUnity Editorを開いてセットアップウィザードを実行する必要がある。

## 素材不足リスト（確認済み）
- BGM・SE: 未用意
- キャラクタースプライト: 未用意（Unityデフォルト図形で代替中）
- エフェクト: 未用意（FloatingText等はコードのみ）

## 作業ログ
- 2026-04-20: Phase1(16本)・Phase2(10本)スクリプト実装完了。HeroToggle/FloatingTextSpawner/EnemySideバグ修正済み。日本語フォント自動検出追加。
