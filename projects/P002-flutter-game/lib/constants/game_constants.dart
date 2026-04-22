/// ゲーム全体で使う数値定数
/// ここを変えるだけでゲームバランスを調整できる設計
class GameConstants {
  // ---- キャンバスサイズ（iPhone縦画面基準） ----
  static const double gameWidth = 390.0;
  static const double gameHeight = 844.0;

  // ---- バトルフィールド ----
  static const double fieldTop = 100.0;    // フィールド上端（HUD分を除く）
  static const double fieldBottom = 680.0; // カードUI上端
  static const double fieldLeft = 0.0;
  static const double fieldRight = 390.0;
  static const double laneCount = 3.0;     // 上段・中段・下段の3レーン
  static const double laneHeight = (fieldBottom - fieldTop) / laneCount; // 約193px

  // 敵スポーン・ゴール
  static const double enemySpawnX = 430.0;  // 画面右外からスポーン
  static const double enemyGoalX = -60.0;   // 画面左端を通過で城壁ダメージ

  // ---- 城壁（プレイヤーの本拠地） ----
  static const int initialWallHp = 100;
  static const double wallX = 20.0;         // 城壁描画位置
  static const double wallWidth = 24.0;
  static const double wallHeight = 120.0;

  // ---- カードシステム ----
  static const int maxHandSize = 6;
  static const int initialHandSize = 4;
  static const int maxManaCost = 5;         // カード最大コスト
  static const double manaRegenPerSecond = 1.0;
  static const double maxMana = 10.0;
  static const double cardPlacementCooldown = 0.3; // 連続配置の最小間隔(秒)

  // ---- ウェーブ ----
  static const int wavesPerStage = 5;
  static const double waveIntervalSeconds = 8.0;  // ウェーブ間インターバル
  static const double enemySpawnInterval = 1.2;   // 同ウェーブ内の敵スポーン間隔

  // ---- ユニット戦闘 ----
  static const double unitAttackRange = 80.0;      // ユニットの攻撃射程(px)
  static const double projectileSpeed = 320.0;     // 矢・魔法弾の速度
  static const double weaknessMultiplier = 1.5;    // 弱点時ダメージ倍率
  static const double resistMultiplier = 0.6;      // 耐性時ダメージ倍率
  static const double chainBonusMultiplier = 2.0;  // チェーン反応時の追加倍率
  static const int chainWindowMs = 1500;           // チェーン判定ウィンドウ(ms)

  // ---- ドロップ ----
  static const double baseDropRate = 0.4;          // 基礎ドロップ率
  static const double eliteDropBonus = 0.2;        // エリート敵の追加ドロップ率
  static const double bossDropBonus = 1.0;         // ボスは必ずドロップ

  // ---- エフェクト ----
  static const double screenShakeDuration = 0.35;   // ScreenShake持続時間(秒)
  static const double screenShakeIntensityNormal = 4.0;
  static const double screenShakeIntensityBoss = 12.0;
  static const double floatingTextDuration = 1.2;   // FloatingText表示時間
  static const double floatingTextRiseSpeed = 60.0; // FloatingTextが上昇する速度(px/s)
  static const int particleCountExplosion = 28;
  static const int particleCountChain = 16;
  static const double particleLifespan = 0.9;

  // ---- クリティカル ----
  static const double baseCritChance = 0.05;           // 基礎クリティカル率
  static const double criticalDamageMultiplier = 1.75;  // クリティカルダメージ倍率

  // ---- 装備強化 ----
  static const int maxEquipmentLevel = 5;
  static const double upgradeSuccessRateBase = 0.9; // Lv1→2の成功率
  static const double upgradeSuccessRateDecay = 0.15; // レベルごとに低下
}
