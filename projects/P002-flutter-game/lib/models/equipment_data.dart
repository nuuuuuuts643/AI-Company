import '../constants/element_chart.dart';

/// 装備スロット
enum EquipmentSlot { weapon, armor, accessory }

extension EquipmentSlotLabel on EquipmentSlot {
  String get label {
    switch (this) {
      case EquipmentSlot.weapon:    return '武器';
      case EquipmentSlot.armor:     return '防具';
      case EquipmentSlot.accessory: return 'アクセサリ';
    }
  }
}

/// 装備の効果タイプ
enum EquipmentEffectType {
  attackBoost,        // 全ユニット攻撃力+%
  hpBoost,            // 全ユニットHP+%
  manaRegen,          // マナ回復速度+%
  elementBoost,       // 特定属性ダメージ+%
  chainBonus,         // チェーン反応倍率+%
  wallHpBoost,        // 城壁HP+
  critChance,         // クリティカル率+%
  dropRateBoost,      // ドロップ率+%
}

/// 装備効果1つ
class EquipmentEffect {
  final EquipmentEffectType type;
  final double value;           // 数値（倍率や固定値）
  final ElementType? element;   // elementBoost時のみ使用

  const EquipmentEffect({
    required this.type,
    required this.value,
    this.element,
  });
}

/// 装備マスターデータ
class EquipmentData {
  final String id;
  final String name;
  final String description;
  final EquipmentSlot slot;
  final List<EquipmentEffect> effects;
  final Map<String, int> upgradeCost; // 強化素材 materialId → 個数
  final int maxLevel;

  const EquipmentData({
    required this.id,
    required this.name,
    required this.description,
    required this.slot,
    required this.effects,
    this.upgradeCost = const {},
    this.maxLevel = 5,
  });
}

/// セッション内でのアイテムリスク状態
/// atRisk  = セッション中に取得（死亡でロスト対象）
/// secured = ハブ持ち込み or ボス撃破/抽出で確保済み
enum ItemState { atRisk, secured }

/// プレイヤーが所持する装備インスタンス（レベル・リスク状態付き）
class OwnedEquipment {
  final String equipmentId;
  int level; // 1〜maxLevel

  /// セッション中のリスク状態（ハブ保存時は secured 固定）
  ItemState itemState;

  OwnedEquipment({
    required this.equipmentId,
    this.level = 1,
    this.itemState = ItemState.secured,
  });

  Map<String, dynamic> toJson() => {
        'equipmentId': equipmentId,
        'level': level,
        'itemState': itemState.name,
      };

  factory OwnedEquipment.fromJson(Map<String, dynamic> json) => OwnedEquipment(
        equipmentId: json['equipmentId'] as String,
        level: json['level'] as int? ?? 1,
        itemState: ItemState.values.firstWhere(
          (s) => s.name == (json['itemState'] as String? ?? 'secured'),
          orElse: () => ItemState.secured,
        ),
      );
}

/// 全装備マスターデータ
class EquipmentMaster {
  static const List<EquipmentData> all = [
    // ---- 武器 ----
    EquipmentData(
      id: 'weapon_fire_sword',
      name: '炎の剣',
      description: '火属性ユニットの攻撃力+20%',
      slot: EquipmentSlot.weapon,
      effects: [
        EquipmentEffect(
          type: EquipmentEffectType.elementBoost,
          value: 0.20,
          element: ElementType.fire,
        ),
      ],
      upgradeCost: {'mat_drake_scale': 2, 'mat_berserker_axe': 1},
    ),
    EquipmentData(
      id: 'weapon_wind_bow',
      name: '風神の弓',
      description: '全ユニット攻撃力+10%、風属性+15%',
      slot: EquipmentSlot.weapon,
      effects: [
        EquipmentEffect(type: EquipmentEffectType.attackBoost, value: 0.10),
        EquipmentEffect(
          type: EquipmentEffectType.elementBoost,
          value: 0.15,
          element: ElementType.wind,
        ),
      ],
      upgradeCost: {'mat_wraith_essence': 3},
    ),
    EquipmentData(
      id: 'weapon_dark_staff',
      name: '闇の杖',
      description: 'チェーン反応倍率+30%、マナ回復+10%',
      slot: EquipmentSlot.weapon,
      effects: [
        EquipmentEffect(type: EquipmentEffectType.chainBonus, value: 0.30),
        EquipmentEffect(type: EquipmentEffectType.manaRegen, value: 0.10),
      ],
      upgradeCost: {'mat_lich_crown': 1, 'mat_dark_blade': 2},
    ),

    // ---- 防具 ----
    EquipmentData(
      id: 'armor_iron_wall',
      name: '鉄の城壁強化',
      description: '城壁HP+30',
      slot: EquipmentSlot.armor,
      effects: [
        EquipmentEffect(type: EquipmentEffectType.wallHpBoost, value: 30),
      ],
      upgradeCost: {'mat_golem_core': 1, 'mat_orc_hide': 3},
    ),
    EquipmentData(
      id: 'armor_light_robe',
      name: '光の法衣',
      description: '全ユニットHP+20%、クリティカル率+5%',
      slot: EquipmentSlot.armor,
      effects: [
        EquipmentEffect(type: EquipmentEffectType.hpBoost, value: 0.20),
        EquipmentEffect(type: EquipmentEffectType.critChance, value: 0.05),
      ],
      upgradeCost: {'mat_shaman_staff': 2},
    ),

    // ---- アクセサリ ----
    EquipmentData(
      id: 'acc_mana_crystal',
      name: 'マナ結晶',
      description: 'マナ回復速度+25%',
      slot: EquipmentSlot.accessory,
      effects: [
        EquipmentEffect(type: EquipmentEffectType.manaRegen, value: 0.25),
      ],
      upgradeCost: {'mat_common': 5},
    ),
    EquipmentData(
      id: 'acc_lucky_charm',
      name: '幸運のお守り',
      description: '素材ドロップ率+20%、クリティカル率+10%',
      slot: EquipmentSlot.accessory,
      effects: [
        EquipmentEffect(type: EquipmentEffectType.dropRateBoost, value: 0.20),
        EquipmentEffect(type: EquipmentEffectType.critChance, value: 0.10),
      ],
      upgradeCost: {'mat_goblin_fang': 5, 'mat_bat_wing': 3},
    ),
    EquipmentData(
      id: 'acc_chain_ring',
      name: 'チェーンリング',
      description: 'チェーン反応倍率+20%、チェーン窓+0.5秒',
      slot: EquipmentSlot.accessory,
      effects: [
        EquipmentEffect(type: EquipmentEffectType.chainBonus, value: 0.20),
      ],
      upgradeCost: {'mat_shadow_heart': 1},
    ),
  ];

  static EquipmentData? getById(String id) {
    try {
      return all.firstWhere((e) => e.id == id);
    } catch (_) {
      return null;
    }
  }
}
