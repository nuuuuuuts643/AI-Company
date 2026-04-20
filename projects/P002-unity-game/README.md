# P002 Unityゲーム開発 — 要塞都市育成ゲーム

## 概要
スマホ縦画面向け 2Dドット 要塞都市育成 × 月末襲撃防衛 × 軽い編成戦略ゲーム

## 担当
秘書(Claude)

## 開始日
2026-04-20

## ステータス
- [x] Unityプロジェクト初期作成
- [x] フォルダ構成・スクリプト設計
- [x] Phase 1 コアスクリプト実装（ロジック層 16本）
- [x] Phase 2 演出・UI・Editorセットアップスクリプト実装（11本）
- [ ] Unity上でのScene/Prefab組み上げ（`FortressCity > Setup Everything` で自動化済み）
- [ ] 実機テスト・調整
- [ ] Phase 3 ポリッシュ・Audio・ドットアート差し替え

## 起動手順（社長の作業はこれだけ）

1. Unity Hub で `projects/P002-unity-game/P002-unity-game` を開く
2. Unityメニュー → `FortressCity > Setup Everything` をクリック
3. Console に `Setup complete!` が出たら Boot シーンを開いて **Play**

## コアループ
1週進める → 週イベント → 管理/投資 → 4週目で月末襲撃 → 偵察 → 編成 → 自動戦闘 → 結果 → 次の月

## 実装済みスクリプト一覧（27本）

### Phase 1 — ロジック層
| ファイル | 役割 |
|---|---|
| Core/GameTypes.cs | 全enum定義 |
| Core/GameManager.cs | シングルトン・状態管理 |
| Core/SaveManager.cs | JSON保存/読み込み |
| City/CityData.cs | 都市ステータス・ArmyData |
| City/CityManager.cs | 週次収支・投資・徴兵 |
| Time/TimeManager.cs | 週・月進行・イベント抽選 |
| Military/UnitData.cs | 兵種 ScriptableObject |
| Military/ArmyManager.cs | 編成プリセット4種 |
| Enemy/EnemyData.cs | 敵 ScriptableObject |
| Events/WeekEventData.cs | 週イベント ScriptableObject |
| Battle/BattleManager.cs | 戦闘計算・損耗・デススパイラル対策 |
| Battle/ScoutManager.cs | 偵察処理 |
| UI/CityUIController.cs | メイン画面UI |
| UI/ManageUIController.cs | 管理/投資画面UI |
| UI/RaidUIController.cs | 襲撃対応画面UI |
| UI/BattleResultUI.cs | 戦闘結果表示UI |

### Phase 2 — 演出・Editor自動化
| ファイル | 役割 |
|---|---|
| Core/SceneLoader.cs | フェード付きシーン遷移 |
| Core/BootController.cs | Boot → City 自動遷移 |
| Core/AudioManager.cs | BGM/SE管理 |
| City/CityRenderer.cs | Fort/Lifeレベルで街の見た目変化 |
| Battle/BattleAnimator.cs | 戦闘演出シーケンス（1〜2秒） |
| UI/CameraShake.cs | 衝突時の画面揺れ |
| UI/ButtonFeedback.cs | ボタン押下のスケールバウンス |
| UI/FloatingText.cs | 浮かび上がるダメージ/リソーステキスト |
| UI/FloatingTextSpawner.cs | FloatingTextプールマネージャー |
| **Editor/GameSetup.cs** | **シーン・SO・配線を全自動生成** |

## 次のアクション
Unity上で `FortressCity > Setup Everything` → Play で Playable 確認
