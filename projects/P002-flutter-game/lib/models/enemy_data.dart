import '../constants/element_chart.dart';

/// 敵の行動パターン
enum MovementPattern {
  straight,   // 直線移動（基本）
  zigzag,     // ジグザグ（回避型）
  rush,       // 突進（高速・低HP）
  tank,       // 鈍足（超高HP）
  flying,     // 空中移動（罠を無視）
  bossCharge, // ボス突進（一定HP以下で加速）
}

/// 敵の種別
enum EnemyType {
  goblin,
  goblinShaman,
  orc,
  orcBerserker,
  fireDrake,
  seaSerpent,
  windWraith,
  stoneGolem,
  darkKnight,
  shadowBat,
  lichKing,       // ボス
  shadowLord,     // ボス
}

extension EnemyTypeInfo on EnemyType {
  bool get isBoss => this == EnemyType.lichKing || this == EnemyType.shadowLord;
  bool get isElite =>
      this == EnemyType.goblinShaman ||
      this == EnemyType.orcBerserker ||
      this == EnemyType.darkKnight;
}

/// 敵1体のマスターデータ
class EnemyData {
  final EnemyType type;
  final String name;
  final ElementType element;
  final int maxHp;
  final int attackPower;      // 城壁に到達した時に与えるダメージ
  final double moveSpeed;     // px/秒
  final MovementPattern movement;
  final int scoreValue;       // 撃破スコア
  final int goldDrop;         // ドロップ金貨
  final double dropRate;      // 素材ドロップ率
  final String dropMaterialId;// ドロップ素材ID
  final bool hasArmor;        // 部位破壊（アーマー）を持つか

  // ボス特有
  final int? armorHp;         // アーマーHP（破壊後に本体攻撃が通る）
  final List<String> bossSkills; // ボススキルID一覧

  bool get isElite => type.isElite;
  bool get isBoss => type.isBoss;

  const EnemyData({
    required this.type,
    required this.name,
    required this.element,
    required this.maxHp,
    required this.attackPower,
    required this.moveSpeed,
    required this.movement,
    required this.scoreValue,
    this.goldDrop = 1,
    this.dropRate = 0.3,
    this.dropMaterialId = 'mat_common',
    this.hasArmor = false,
    this.armorHp,
    this.bossSkills = const [],
  });
}

/// 全敵マスターデータ
class EnemyMaster {
  static const Map<EnemyType, EnemyData> all = {
    EnemyType.goblin: EnemyData(
      type: EnemyType.goblin,
      name: 'ゴブリン',
      element: ElementType.earth,
      maxHp: 120,
      attackPower: 55,
      moveSpeed: 105.0,
      movement: MovementPattern.straight,
      scoreValue: 50,
      goldDrop: 1,
      dropRate: 0.25,
      dropMaterialId: 'mat_goblin_fang',
    ),
    EnemyType.goblinShaman: EnemyData(
      type: EnemyType.goblinShaman,
      name: 'ゴブリンシャーマン',
      element: ElementType.dark,
      maxHp: 180,
      attackPower: 60,
      moveSpeed: 78.0,
      movement: MovementPattern.zigzag,
      scoreValue: 120,
      goldDrop: 2,
      dropRate: 0.45,
      dropMaterialId: 'mat_shaman_staff',
    ),
    EnemyType.orc: EnemyData(
      type: EnemyType.orc,
      name: 'オーク',
      element: ElementType.earth,
      maxHp: 380,
      attackPower: 70,
      moveSpeed: 62.0,
      movement: MovementPattern.tank,
      scoreValue: 100,
      goldDrop: 2,
      dropRate: 0.35,
      dropMaterialId: 'mat_orc_hide',
    ),
    EnemyType.orcBerserker: EnemyData(
      type: EnemyType.orcBerserker,
      name: 'オークバーサーカー',
      element: ElementType.fire,
      maxHp: 260,
      attackPower: 80,
      moveSpeed: 140.0,
      movement: MovementPattern.rush,
      scoreValue: 200,
      goldDrop: 3,
      dropRate: 0.5,
      dropMaterialId: 'mat_berserker_axe',
      hasArmor: true,
      armorHp: 50,
    ),
    EnemyType.fireDrake: EnemyData(
      type: EnemyType.fireDrake,
      name: 'ファイアドレイク',
      element: ElementType.fire,
      maxHp: 200,
      attackPower: 65,
      moveSpeed: 82.0,
      movement: MovementPattern.flying,
      scoreValue: 250,
      goldDrop: 4,
      dropRate: 0.6,
      dropMaterialId: 'mat_drake_scale',
      hasArmor: true,
      armorHp: 60,
    ),
    EnemyType.seaSerpent: EnemyData(
      type: EnemyType.seaSerpent,
      name: '海蛇',
      element: ElementType.water,
      maxHp: 160,
      attackPower: 52,
      moveSpeed: 108.0,
      movement: MovementPattern.zigzag,
      scoreValue: 180,
      goldDrop: 3,
      dropRate: 0.45,
      dropMaterialId: 'mat_serpent_scale',
    ),
    EnemyType.windWraith: EnemyData(
      type: EnemyType.windWraith,
      name: '風霊',
      element: ElementType.wind,
      maxHp: 90,
      attackPower: 38,
      moveSpeed: 158.0,
      movement: MovementPattern.flying,
      scoreValue: 150,
      goldDrop: 2,
      dropRate: 0.4,
      dropMaterialId: 'mat_wraith_essence',
    ),
    EnemyType.stoneGolem: EnemyData(
      type: EnemyType.stoneGolem,
      name: 'ストーンゴーレム',
      element: ElementType.earth,
      maxHp: 550,
      attackPower: 90,
      moveSpeed: 38.0,
      movement: MovementPattern.tank,
      scoreValue: 400,
      goldDrop: 6,
      dropRate: 0.7,
      dropMaterialId: 'mat_golem_core',
      hasArmor: true,
      armorHp: 160,
    ),
    EnemyType.darkKnight: EnemyData(
      type: EnemyType.darkKnight,
      name: '闇の騎士',
      element: ElementType.dark,
      maxHp: 320,
      attackPower: 80,
      moveSpeed: 75.0,
      movement: MovementPattern.straight,
      scoreValue: 350,
      goldDrop: 5,
      dropRate: 0.65,
      dropMaterialId: 'mat_dark_blade',
      hasArmor: true,
      armorHp: 100,
    ),
    EnemyType.shadowBat: EnemyData(
      type: EnemyType.shadowBat,
      name: '影蝙蝠',
      element: ElementType.dark,
      maxHp: 100,
      attackPower: 32,
      moveSpeed: 205.0,
      movement: MovementPattern.flying,
      scoreValue: 60,
      goldDrop: 1,
      dropRate: 0.2,
      dropMaterialId: 'mat_bat_wing',
    ),

    // ---- ボス ----
    EnemyType.lichKing: EnemyData(
      type: EnemyType.lichKing,
      name: 'リッチキング',
      element: ElementType.dark,
      maxHp: 1200,
      attackPower: 50,
      moveSpeed: 40.0,
      movement: MovementPattern.bossCharge,
      scoreValue: 5000,
      goldDrop: 20,
      dropRate: 1.0,
      dropMaterialId: 'mat_lich_crown',
      hasArmor: true,
      armorHp: 300,
      bossSkills: ['skill_summon_undead', 'skill_death_ray', 'skill_dark_barrier'],
    ),
    EnemyType.shadowLord: EnemyData(
      type: EnemyType.shadowLord,
      name: '影の王',
      element: ElementType.dark,
      maxHp: 2000,
      attackPower: 80,
      moveSpeed: 50.0,
      movement: MovementPattern.bossCharge,
      scoreValue: 10000,
      goldDrop: 40,
      dropRate: 1.0,
      dropMaterialId: 'mat_shadow_heart',
      hasArmor: true,
      armorHp: 500,
      bossSkills: [
        'skill_shadow_clone',
        'skill_void_explosion',
        'skill_darkness_field',
        'skill_phase_shift',
      ],
    ),
  };

  static EnemyData get(EnemyType type) => all[type]!;
}
