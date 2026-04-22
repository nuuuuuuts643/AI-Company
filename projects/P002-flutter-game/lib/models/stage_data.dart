import 'enemy_data.dart';

/// ウェーブ1回分の敵構成
class WaveData {
  final int waveNumber;           // 1〜5
  final List<WaveEnemy> enemies;  // この波の敵リスト
  final bool isBossWave;

  const WaveData({
    required this.waveNumber,
    required this.enemies,
    this.isBossWave = false,
  });
}

/// ウェーブ内の敵エントリー
class WaveEnemy {
  final EnemyType type;
  final int count;
  final int laneIndex; // 0=上, 1=中, 2=下, -1=ランダム
  final double spawnDelaySeconds; // 前の敵からの追加遅延

  const WaveEnemy({
    required this.type,
    this.count = 1,
    this.laneIndex = -1,
    this.spawnDelaySeconds = 0,
  });
}

/// ステージデータ
class StageData {
  final String id;
  final String name;
  final String description;
  final int stageNumber;
  final List<WaveData> waves;
  final int initialWallHp;        // ステージ固有の初期城壁HP（0=デフォルト使用）
  final String backgroundId;      // 背景アセットID
  final String bgmId;             // BGMアセットID
  final Map<String, int> clearRewards; // クリア報酬 materialId → 個数
  final int clearScoreThreshold;  // ☆3評価のスコア閾値
  final bool isUnlocked;

  const StageData({
    required this.id,
    required this.name,
    required this.description,
    required this.stageNumber,
    required this.waves,
    this.initialWallHp = 0,
    this.backgroundId = 'bg_forest',
    this.bgmId = 'bgm_battle1',
    this.clearRewards = const {},
    this.clearScoreThreshold = 3000,
    this.isUnlocked = false,
  });
}

/// 全ステージ定義
class StageMaster {
  static const List<StageData> stages = [
    StageData(
      id: 'stage_01',
      name: '第1章：森の入口',
      description: '小規模なゴブリン部隊を撃退せよ。チュートリアル。',
      stageNumber: 1,
      backgroundId: 'bg_forest',
      bgmId: 'bgm_battle1',
      clearRewards: {'mat_goblin_fang': 3, 'mat_common': 5},
      clearScoreThreshold: 1000,
      isUnlocked: true,
      waves: [
        WaveData(waveNumber: 1, enemies: [
          WaveEnemy(type: EnemyType.goblin, count: 3, laneIndex: 1),
        ]),
        WaveData(waveNumber: 2, enemies: [
          WaveEnemy(type: EnemyType.goblin, count: 2),
          WaveEnemy(type: EnemyType.goblin, count: 2, spawnDelaySeconds: 1.5),
        ]),
        WaveData(waveNumber: 3, enemies: [
          WaveEnemy(type: EnemyType.goblin, count: 3),
          WaveEnemy(type: EnemyType.goblinShaman, count: 1),
        ]),
        WaveData(waveNumber: 4, enemies: [
          WaveEnemy(type: EnemyType.orc, count: 2),
          WaveEnemy(type: EnemyType.goblin, count: 4),
        ]),
        WaveData(waveNumber: 5, enemies: [
          WaveEnemy(type: EnemyType.goblinShaman, count: 2),
          WaveEnemy(type: EnemyType.orc, count: 2),
          WaveEnemy(type: EnemyType.goblin, count: 3, spawnDelaySeconds: 2.0),
        ]),
      ],
    ),

    StageData(
      id: 'stage_02',
      name: '第2章：火山の麓',
      description: 'ファイアドレイクと炎のバーサーカーが迫る。',
      stageNumber: 2,
      backgroundId: 'bg_volcano',
      bgmId: 'bgm_battle2',
      clearRewards: {'mat_drake_scale': 2, 'mat_berserker_axe': 1},
      clearScoreThreshold: 3000,
      waves: [
        WaveData(waveNumber: 1, enemies: [
          WaveEnemy(type: EnemyType.orc, count: 3),
        ]),
        WaveData(waveNumber: 2, enemies: [
          WaveEnemy(type: EnemyType.orcBerserker, count: 2),
          WaveEnemy(type: EnemyType.orc, count: 2),
        ]),
        WaveData(waveNumber: 3, enemies: [
          WaveEnemy(type: EnemyType.fireDrake, count: 1),
          WaveEnemy(type: EnemyType.orc, count: 3),
        ]),
        WaveData(waveNumber: 4, enemies: [
          WaveEnemy(type: EnemyType.fireDrake, count: 2),
          WaveEnemy(type: EnemyType.orcBerserker, count: 2),
        ]),
        WaveData(waveNumber: 5, isBossWave: true, enemies: [
          WaveEnemy(type: EnemyType.stoneGolem, count: 1, laneIndex: 1),
          WaveEnemy(type: EnemyType.fireDrake, count: 2, spawnDelaySeconds: 3.0),
        ]),
      ],
    ),

    StageData(
      id: 'stage_03',
      name: '第3章：海上の要塞',
      description: '海から蛇と風の幽霊が押し寄せる。',
      stageNumber: 3,
      backgroundId: 'bg_sea',
      bgmId: 'bgm_battle3',
      clearRewards: {'mat_serpent_scale': 3, 'mat_wraith_essence': 2},
      clearScoreThreshold: 6000,
      waves: [
        WaveData(waveNumber: 1, enemies: [
          WaveEnemy(type: EnemyType.windWraith, count: 4),
        ]),
        WaveData(waveNumber: 2, enemies: [
          WaveEnemy(type: EnemyType.seaSerpent, count: 2),
          WaveEnemy(type: EnemyType.windWraith, count: 3),
        ]),
        WaveData(waveNumber: 3, enemies: [
          WaveEnemy(type: EnemyType.seaSerpent, count: 3),
          WaveEnemy(type: EnemyType.shadowBat, count: 5),
        ]),
        WaveData(waveNumber: 4, enemies: [
          WaveEnemy(type: EnemyType.seaSerpent, count: 3),
          WaveEnemy(type: EnemyType.darkKnight, count: 1),
        ]),
        WaveData(waveNumber: 5, isBossWave: true, enemies: [
          WaveEnemy(type: EnemyType.lichKing, count: 1, laneIndex: 1),
          WaveEnemy(type: EnemyType.shadowBat, count: 6, spawnDelaySeconds: 2.0),
        ]),
      ],
    ),

    StageData(
      id: 'stage_04',
      name: '最終章：闇の城塞',
      description: '影の王が全軍を率いて最後の侵攻を開始した。',
      stageNumber: 4,
      backgroundId: 'bg_dark_castle',
      bgmId: 'bgm_final_boss',
      clearRewards: {'mat_shadow_heart': 1, 'mat_lich_crown': 1},
      clearScoreThreshold: 15000,
      initialWallHp: 80, // 最終章は城壁HPが低めからスタート
      waves: [
        WaveData(waveNumber: 1, enemies: [
          WaveEnemy(type: EnemyType.darkKnight, count: 3),
        ]),
        WaveData(waveNumber: 2, enemies: [
          WaveEnemy(type: EnemyType.darkKnight, count: 3),
          WaveEnemy(type: EnemyType.shadowBat, count: 6),
        ]),
        WaveData(waveNumber: 3, enemies: [
          WaveEnemy(type: EnemyType.stoneGolem, count: 1),
          WaveEnemy(type: EnemyType.darkKnight, count: 4),
        ]),
        WaveData(waveNumber: 4, enemies: [
          WaveEnemy(type: EnemyType.lichKing, count: 1),
          WaveEnemy(type: EnemyType.darkKnight, count: 3, spawnDelaySeconds: 5.0),
        ]),
        WaveData(waveNumber: 5, isBossWave: true, enemies: [
          WaveEnemy(type: EnemyType.shadowLord, count: 1, laneIndex: 1),
          WaveEnemy(type: EnemyType.shadowBat, count: 8, spawnDelaySeconds: 3.0),
          WaveEnemy(type: EnemyType.darkKnight, count: 4, spawnDelaySeconds: 6.0),
        ]),
      ],
    ),
  ];

  static StageData? getById(String id) {
    try {
      return stages.firstWhere((s) => s.id == id);
    } catch (_) {
      return null;
    }
  }
}
