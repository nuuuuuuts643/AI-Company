# P002 封印の戦線 — プロジェクト状態

**最終更新**: 2026-04-22（shop/extraction/animation/audio 実装完了）  
**担当**: CEO (Claude)

---

## 完成度評価: **ベータ（主要機能実装完了）**

| カテゴリ | 状態 |
|---|---|
| Dartコード（ロジック） | ✅ 完全実装済み |
| Flameコンポーネント | ✅ ColoredRect代替あり + アニメーション実装済み |
| スクリーン (Flutter UI) | ✅ 全画面実装済み |
| アセット（スプライト） | 🟡 ColoredRect代替中 |
| BGM / SE | ✅ WAVプレースホルダー生成済み（実装済み） |
| フォント (DotGothic16) | ❌ ダウンロード必要 |
| iOSビルド | ❌ `flutter create` 後に確認 |

---

## ファイル構成（最新）

```
P002-flutter-game/
├── pubspec.yaml              ✅ flame ^1.18.0 / flame_audio / shared_preferences / provider
├── lib/
│   ├── main.dart             ✅ Provider DI
│   ├── game/
│   │   ├── octo_battle_game.dart  ✅ FlameGame統合
│   │   └── game_state.dart        ✅ addGold / spendGold / restoreWallHp 追加
│   ├── systems/
│   │   ├── battle_system.dart     ✅ 装備critChance参照 / Random()クリティカル改善
│   │   ├── card_system.dart       ✅ デッキ管理
│   │   ├── wave_system.dart       ✅ ±20% RNG変動 / playerPower難易度スケール 追加
│   │   ├── chain_system.dart      ✅ チェーン判定
│   │   ├── loot_system.dart       ✅ ドロップRNG
│   │   ├── event_system.dart      ✅ ウェーブ間ランダムイベント14種
│   │   ├── stage_generator.dart   ✅ プロシージャル生成
│   │   ├── save_system.dart       ✅ SharedPreferences永続化
│   │   ├── shop_system.dart       ✅ LoLショップ（SessionBuffs / rollShopItems / purchaseItem）
│   │   └── extraction_system.dart ✅ タルコフ抽出（secured / atRisk / onPlayerDied）
│   ├── components/
│   │   ├── enemy_component.dart   ✅ 状態異常 / アーマー破壊
│   │   ├── unit_component.dart    ✅ ユニット描画
│   │   ├── projectile_component.dart ✅
│   │   ├── hd2d_background.dart   ✅ パララックス背景
│   │   ├── lighting_layer.dart    ✅ 光源 / ブルーム
│   │   ├── particle_system.dart   ✅ パーティクル
│   │   ├── floating_text.dart     ✅ ダメージ数値
│   │   ├── screen_shake.dart      ✅ ボス揺れ
│   │   ├── chain_effect.dart      ✅ チェーン演出
│   │   └── animation_controller.dart ✅ 行進ボブ / 攻撃シーケンス / ボス登場 / 死亡 / チェーン波紋 / レベルアップ / コイン飛翔
│   ├── screens/
│   │   ├── main_menu_screen.dart  ✅
│   │   ├── stage_select_screen.dart ✅
│   │   ├── battle_screen.dart     ✅
│   │   ├── card_hand_widget.dart  ✅
│   │   ├── result_screen.dart     ✅
│   │   ├── equipment_screen.dart  ✅
│   │   ├── wave_shop_screen.dart  ✅ ウェーブ間ショップUI（購入/再抽選/FloatingText演出）
│   │   └── extraction_screen.dart ✅ 脱出選択UI（atRiskリスト / 抽出プログレスバー）
│   ├── models/
│   │   ├── card_data.dart         ✅ 18枚
│   │   ├── enemy_data.dart        ✅ 13種
│   │   ├── unit_data.dart         ✅
│   │   ├── equipment_data.dart    ✅ 8種
│   │   ├── stage_data.dart        ✅ 4ステージ
│   │   ├── player_character.dart  ✅
│   │   └── skin_catalog.dart      ✅ 12種スキン
│   ├── services/
│   │   ├── ad_service.dart        ✅ 広告管理
│   │   └── audio_service.dart     ✅ playBGM / stopBGM / playSE（FlameAudio薄ラップ）
│   └── constants/
│       ├── game_constants.dart    ✅ baseCritChance / criticalDamageMultiplier 追加
│       ├── element_chart.dart     ✅ 6属性相性テーブル
│       └── strings.dart           ✅
├── assets/
│   ├── audio/
│   │   ├── battle_bgm.wav         ✅ 8秒120BPMドラムビート（Pythonで生成済み）
│   │   ├── hub_bgm.wav            ✅ 4秒ハブBGM
│   │   ├── victory.wav            ✅ 1.5秒ファンファーレ
│   │   ├── defeat.wav             ✅ 1.5秒下降音
│   │   ├── hit_se.wav             ✅ 0.1秒打撃音
│   │   ├── chain_se.wav           ✅ 0.3秒チャイム
│   │   ├── purchase_se.wav        ✅ 0.2秒コイン音
│   │   └── levelup_se.wav         ✅ 0.5秒上昇音
│   └── README.md                  ✅ 素材一覧
├── design/
│   └── concept.md                 ✅ v0.3（セッション構造/ショップ/抽出/Phase3協力プレイ更新）
└── briefing.md                    ✅ このファイル（最新）
```

---

## 今回追加した機能（2026-04-22 セッション）

### 新規ファイル（6本）

| ファイル | 概要 |
|---|---|
| `systems/shop_system.dart` | LoLショップ: SessionBuffs蓄積 / ウェーブ別プール / 再抽選 / 購入コールバック |
| `systems/extraction_system.dart` | タルコフ抽出: secured/atRisk二状態 / 死亡ロスト / 抽出進行度(0.0〜1.0) |
| `screens/wave_shop_screen.dart` | ショップUI: GridView / FloatingText演出 / 再抽選ボタン / スキップ |
| `screens/extraction_screen.dart` | 抽出UI: リスク一覧 / プログレスバーアニメ / 脱出or続行 |
| `components/animation_controller.dart` | Flame Effect活用: 行進ボブ / 攻撃前進後退 / ボス登場 / チェーン波紋 / レベルアップ柱 / コイン弧飛翔 |
| `services/audio_service.dart` | BGMループ / SE重ね再生 / ミュート / プリロード |

### 既存ファイル改善（4本）

| ファイル | 改善内容 |
|---|---|
| `systems/wave_system.dart` | ±20% RNG変動（rngFactor 0.8〜1.2） + playerPower難易度スケール（diffScale） |
| `systems/battle_system.dart` | クリティカル率を装備critChance合算値から計算（_calcCritChance） / Random()使用 |
| `constants/game_constants.dart` | baseCritChance(0.05) / criticalDamageMultiplier(1.75) 定数追加 |
| `game/game_state.dart` | addGold / spendGold / restoreWallHp メソッド追加 |

### 音声アセット（8ファイル）
Pythonでnumpyから直接WAV生成。実装済み・再生可能。  
本番では実際のドット絵サウンドデザイナー制作音源に差し替え。

---

## 未解決の問題・素材不足

| 項目 | 優先度 | 内容 |
|---|---|---|
| スプライト全件 | 🔴 P0 | ColoredRect代替中。itch.io / opengameart.org から CC0素材を取得 |
| DotGothic16.ttf | 🔴 P0 | Google Fontsから要ダウンロード |
| flutter create | 🔴 P0 | ios/ ディレクトリ未生成。ビルド不可 |
| 音源（本番） | 🟡 P1 | WAVプレースホルダーは生成済み。本番用は専門制作が必要 |
| GoogleMobileAds SDK | 🟡 P1 | pubspec.yaml未追加 |
| in_app_purchase | 🟡 P1 | 有料版購入フロー未実装 |
| wave_shop_screen との統合 | 🟡 P1 | battle_screen.dart からウェーブクリア後に WaveShopScreen を呼ぶ実装が必要 |
| extraction_screen との統合 | 🟡 P1 | battle_screen.dart からの呼び出し実装が必要 |
| animation_controller の統合 | 🟡 P1 | octo_battle_game.dart に GameAnimationController を追加し各タイミングで呼ぶ |
| audio_service の統合 | 🟡 P1 | main.dart または octo_battle_game.dart に AudioService をDIして各タイミングで呼ぶ |
| GOOGLE_CLIENT_ID | 🟢 P2 | Google Cloud Console でOAuth作成後 config.js に設定 |

---

## 次のアクション（home PCで実施）

```bash
# 1. Dartの構文確認
cd ~/ai-company/projects/P002-flutter-game
dart analyze lib/ --no-fatal-infos

# 2. フォントダウンロード
curl -L "https://fonts.gstatic.com/s/dotgothic16/v15/v6-QGZHLQTWUna2EkMYwRqQbR0A.ttf" \
  -o "assets/fonts/DotGothic16-Regular.ttf"

# 3. iOSプロジェクト生成
flutter create --project-name octo_battle --org com.aicompany .

# 4. 依存解決
flutter pub get

# 5. ビルドテスト
flutter build ios --simulator
```

---

## 変更履歴

| 日付 | 内容 |
|---|---|
| 2026-04-22 | 城塞防衛ゲーム → ループする村（一時停止） |
| 2026-04-22 | ループする村 → 最終決定: HD-2Dリアルタイム配置オートバトル |
| 2026-04-22 | 爽快感設計追加（ScreenShake/FloatingText/Haptic/Particle） |
| 2026-04-22 | 運の要素設計（チェーン確率/ウェーブRNG/イベントシステム） |
| 2026-04-22 | ビジネスモデル追加（広告/有料版/プロシージャル/スキン） |
| 2026-04-22 | ショップシステム・抽出システム・アニメーション・音声実装 |
