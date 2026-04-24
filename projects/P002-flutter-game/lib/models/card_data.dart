import '../constants/element_chart.dart';
import 'terrain_data.dart';

/// カードの種別
enum CardType {
  unit,   // ユニット：フィールドに配置して自動攻撃
  spell,  // 魔法：即時発動の範囲攻撃・回復など
  trap,   // 罠：設置してその場を通った敵にダメージ
}

extension CardTypeLabel on CardType {
  String get label {
    switch (this) {
      case CardType.unit:  return 'ユニット';
      case CardType.spell: return '魔法';
      case CardType.trap:  return '罠';
    }
  }
}

/// カードを配置できるレーン
enum LanePosition { top, middle, bottom }

/// カードデータ定義
class CardData {
  final String id;
  final String name;
  final String description;
  final CardType cardType;
  final ElementType element;
  final int manaCost;      // 配置コスト（1〜5）
  final int baseAttack;    // ユニット/魔法の攻撃力
  final int baseHp;        // ユニットのHP（魔法・罠は0）
  final double attackSpeed;// 秒あたり攻撃回数
  final double attackRange;// 攻撃射程(px)
  final int aoeRadius;       // 範囲攻撃半径（0=単体）
  final String iconPath;     // プレースホルダー: 'placeholder'
  final TerrainType? terrainType; // null=通常カード、非null=地形配置カード

  const CardData({
    required this.id,
    required this.name,
    required this.description,
    required this.cardType,
    required this.element,
    required this.manaCost,
    this.baseAttack = 0,
    this.baseHp = 0,
    this.attackSpeed = 1.0,
    this.attackRange = 80.0,
    this.aoeRadius = 0,
    this.iconPath = 'placeholder',
    this.terrainType,
  });
}

/// 全カードマスターデータ
class CardMaster {
  static const List<CardData> allCards = [
    // ---- ユニット: 火属性 ----
    CardData(
      id: 'unit_swordsman_fire',
      name: '炎剣士',
      description: '近接攻撃。同レーンの敵を確実に仕留める火の戦士。',
      cardType: CardType.unit,
      element: ElementType.fire,
      manaCost: 2,
      baseAttack: 62,
      baseHp: 200,
      attackSpeed: 1.2,
      attackRange: 70.0,
    ),
    CardData(
      id: 'unit_archer_wind',
      name: '風弓兵',
      description: '遠距離攻撃。長射程で敵が近づく前に削る。',
      cardType: CardType.unit,
      element: ElementType.wind,
      manaCost: 3,
      baseAttack: 52,
      baseHp: 140,
      attackSpeed: 0.9,
      attackRange: 180.0,
    ),
    CardData(
      id: 'unit_mage_water',
      name: '水魔法使い',
      description: '範囲魔法攻撃。AOEで複数敵に水ダメージ＋鈍足。',
      cardType: CardType.unit,
      element: ElementType.water,
      manaCost: 4,
      baseAttack: 72,
      baseHp: 120,
      attackSpeed: 0.65,
      attackRange: 160.0,
      aoeRadius: 55,
    ),
    CardData(
      id: 'unit_knight_earth',
      name: '土の騎士',
      description: '超高HP壁役。敵の進行をレーン単位で完全制圧。',
      cardType: CardType.unit,
      element: ElementType.earth,
      manaCost: 3,
      baseAttack: 45,
      baseHp: 380,
      attackSpeed: 0.8,
      attackRange: 65.0,
    ),
    CardData(
      id: 'unit_priest_light',
      name: '光の聖職者',
      description: '光の連撃。素早い攻撃速度で敵を追い詰める。',
      cardType: CardType.unit,
      element: ElementType.light,
      manaCost: 3,
      baseAttack: 38,
      baseHp: 160,
      attackSpeed: 1.4,
      attackRange: 90.0,
    ),
    CardData(
      id: 'unit_necromancer_dark',
      name: '闇の死霊術師',
      description: '高火力の闇魔法。アーマー持ちにも有効。',
      cardType: CardType.unit,
      element: ElementType.dark,
      manaCost: 5,
      baseAttack: 80,
      baseHp: 130,
      attackSpeed: 0.7,
      attackRange: 140.0,
    ),
    CardData(
      id: 'unit_druid_wind',
      name: '霊樹使い',
      description: '風の連射。幅広い射程で敵を全方位に牽制。',
      cardType: CardType.unit,
      element: ElementType.wind,
      manaCost: 4,
      baseAttack: 28,
      baseHp: 150,
      attackSpeed: 1.1,
      attackRange: 220.0,
      aoeRadius: 60,
    ),
    CardData(
      id: 'unit_bomber_fire',
      name: '炎爆弾兵',
      description: '一撃必殺の爆発。ガラス砲だが集団を壊滅させる。',
      cardType: CardType.unit,
      element: ElementType.fire,
      manaCost: 2,
      baseAttack: 130,
      baseHp: 60,
      attackSpeed: 0.28,
      attackRange: 55.0,
      aoeRadius: 90,
    ),

    // ---- 魔法カード ----
    CardData(
      id: 'spell_fireball',
      name: 'ファイアボール',
      description: '着弾点に火の玉を投げ込み範囲爆発。ゴブリン集団を一掃。',
      cardType: CardType.spell,
      element: ElementType.fire,
      manaCost: 3,
      baseAttack: 160,
      aoeRadius: 65,
    ),
    CardData(
      id: 'spell_waterfall',
      name: '大瀑布',
      description: '対象レーン全体に大水ダメージ。オーク系の天敵。',
      cardType: CardType.spell,
      element: ElementType.water,
      manaCost: 4,
      baseAttack: 130,
      aoeRadius: 35,
    ),
    CardData(
      id: 'spell_tornado',
      name: '竜巻',
      description: '竜巻で敵を巻き上げ遅延＋中ダメージ。',
      cardType: CardType.spell,
      element: ElementType.wind,
      manaCost: 3,
      baseAttack: 100,
      aoeRadius: 55,
    ),
    CardData(
      id: 'spell_earthspike',
      name: '岩礁衝',
      description: '地面から岩石を突き上げ貫通大ダメージ。コスパ最強。',
      cardType: CardType.spell,
      element: ElementType.earth,
      manaCost: 2,
      baseAttack: 130,
    ),
    CardData(
      id: 'spell_holy_light',
      name: '聖なる光',
      description: 'フィールド全体の味方HPを回復する。',
      cardType: CardType.spell,
      element: ElementType.light,
      manaCost: 4,
      baseAttack: -60,
      aoeRadius: 999,
    ),
    CardData(
      id: 'spell_dark_void',
      name: '暗黒虚無',
      description: '闇のエネルギーで画面全体の敵に大ダメージ。終盤の切り札。',
      cardType: CardType.spell,
      element: ElementType.dark,
      manaCost: 5,
      baseAttack: 130,
      aoeRadius: 999,
    ),

    // ---- 罠カード ----
    CardData(
      id: 'trap_fire_mine',
      name: '炎地雷',
      description: '地面に設置。敵が踏むと爆発する。',
      cardType: CardType.trap,
      element: ElementType.fire,
      manaCost: 2,
      baseAttack: 70,
      aoeRadius: 45,
    ),
    CardData(
      id: 'trap_ice_pit',
      name: '氷穴',
      description: '水氷の罠。踏んだ敵を一定時間凍結させる。',
      cardType: CardType.trap,
      element: ElementType.water,
      manaCost: 2,
      baseAttack: 20,
    ),
    CardData(
      id: 'trap_wind_blade',
      name: '風刃陣',
      description: '風の刃が連続発射されるトリガー罠。',
      cardType: CardType.trap,
      element: ElementType.wind,
      manaCost: 3,
      baseAttack: 30,
    ),
    CardData(
      id: 'trap_earth_spike',
      name: '地棘陣',
      description: '地面に岩棘。踏んだ敵の移動速度を低下。',
      cardType: CardType.trap,
      element: ElementType.earth,
      manaCost: 1,
      baseAttack: 15,
    ),

    // ---- 地形カード（敵フィールドに設置）----
    CardData(
      id: 'terrain_mountain',
      name: '山岳',
      description: 'レーンを封鎖。敵は隣のレーンへ迂回する。ウェーブ中持続。',
      cardType: CardType.trap,
      element: ElementType.earth,
      manaCost: 3,
      terrainType: TerrainType.mountain,
    ),
    CardData(
      id: 'terrain_river',
      name: '急流',
      description: 'そのレーンの敵の移動速度を60%低下させる。18秒持続。',
      cardType: CardType.trap,
      element: ElementType.water,
      manaCost: 2,
      terrainType: TerrainType.river,
    ),
    CardData(
      id: 'terrain_swamp',
      name: '毒沼',
      description: '通過する敵に毒ダメージ15/秒。15秒持続。',
      cardType: CardType.trap,
      element: ElementType.dark,
      manaCost: 2,
      terrainType: TerrainType.swamp,
    ),
  ];

  /// IDでカードを取得
  static CardData? getById(String id) {
    try {
      return allCards.firstWhere((c) => c.id == id);
    } catch (_) {
      return null;
    }
  }

  /// 初期デッキ（チュートリアル用）
  static List<String> get starterDeckIds => [
        'unit_swordsman_fire',
        'unit_archer_wind',
        'unit_knight_earth',
        'spell_fireball',
        'trap_fire_mine',
        'unit_mage_water',
        'spell_earthspike',
        'trap_earth_spike',
        'terrain_mountain',
        'terrain_river',
        'terrain_swamp',
      ];
}
