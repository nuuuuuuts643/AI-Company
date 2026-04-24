/// ゲーム全体で使う数値定数
class GameConstants {
  // ---- キャンバスサイズ（iPhone縦画面基準） ----
  static const double gameWidth = 390.0;
  static const double gameHeight = 844.0;

  // ---- バトルフィールド（縦スクロール：敵が上から下へ） ----
  static const double fieldTop = 70.0;       // HUD下端
  static const double fieldBottom = 790.0;   // 画面下端近く（カードUIはオーバーレイ）
  static const double fieldLeft = 0.0;
  static const double fieldRight = 390.0;

  // レーン（縦3列：左・中・右）
  static const double laneCount = 3.0;
  static const double laneWidth = fieldRight / laneCount; // 130px

  // 敵スポーン・ゴール（上から下）
  static const double enemySpawnY = -70.0;   // 画面上外からスポーン
  static const double enemyGoalY = 770.0;    // 城壁ダメージライン

  // ---- 城壁（画面下部水平ライン） ----
  static const int initialWallHp = 100;
  static const double wallY = 750.0;         // 城壁Y位置（下方向へ拡張）
  static const double wallX = 0.0;
  static const double wallWidth = 390.0;
  static const double wallHeight = 8.0;

  // ---- 陣形グリッド（将棋型 3列×4行） ----
  static const double gridTop = 540.0;    // グリッド最上行（敵フィールドとの境界）
  static const double gridBottom = 750.0; // グリッド最下行（城壁ライン）
  static const int gridRows = 4;          // 行数（0=前列, 3=後列）
  static const double cellHeight = (gridBottom - gridTop) / gridRows; // 52.5px/行
  static const double cellWidth = laneWidth; // 130px/列

  static const double unitBaseY = gridTop + cellHeight * 0.5; // 前列中心

  // ---- カードシステム ----
  static const int maxHandSize = 6;
  static const int initialHandSize = 4;
  static const int maxManaCost = 5;
  static const double manaRegenPerSecond = 0.65;
  static const double maxMana = 10.0;
  static const double cardPlacementCooldown = 0.3;

  // ---- ウェーブ ----
  static const int wavesPerStage = 5;
  static const double waveIntervalSeconds = 6.0;
  static const double enemySpawnInterval = 0.8;   // やや短くして密度アップ

  // ---- ユニット戦闘 ----
  static const double unitAttackRange = 80.0;
  static const double projectileSpeed = 320.0;
  static const double weaknessMultiplier = 1.5;
  static const double resistMultiplier = 0.6;
  static const double chainBonusMultiplier = 2.0;
  static const int chainWindowMs = 1500;

  // ---- ドロップ ----
  static const double baseDropRate = 0.4;
  static const double eliteDropBonus = 0.2;
  static const double bossDropBonus = 1.0;

  // ---- エフェクト ----
  static const double screenShakeDuration = 0.35;
  static const double screenShakeIntensityNormal = 4.0;
  static const double screenShakeIntensityBoss = 12.0;
  static const double floatingTextDuration = 1.2;
  static const double floatingTextRiseSpeed = 60.0;
  static const int particleCountExplosion = 28;
  static const int particleCountChain = 16;
  static const double particleLifespan = 0.9;

  // ---- クリティカル ----
  static const double baseCritChance = 0.05;
  static const double criticalDamageMultiplier = 1.75;

  // ---- 装備強化 ----
  static const int maxEquipmentLevel = 5;
  static const double upgradeSuccessRateBase = 0.9;
  static const double upgradeSuccessRateDecay = 0.15;
}
