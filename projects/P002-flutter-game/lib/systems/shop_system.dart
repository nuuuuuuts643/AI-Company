import 'dart:math';
import '../constants/element_chart.dart';

/// ショップアイテムの効果タイプ
enum ShopEffectType {
  attackBoost,       // 全ユニット攻撃力+%
  attackSpeedBoost,  // 全ユニット攻撃速度+%
  elementBoost,      // 特定属性ダメージ+%
  chainChanceBoost,  // チェーン確率+%
  chainMultBoost,    // チェーン倍率+%
  manaRegenBoost,    // マナ回復速度+%
  wallRepair,        // 城壁HP即時回復（固定値）
  maxManaBoost,      // 最大マナ+
  critBoost,         // クリティカル率+%
  goldBonus,         // 以降ウェーブのゴールド獲得+%
  cardDraw,          // 手札追加枚数+1
  waveGoldBonus,     // このウェーブ限定ゴールドボーナス（即時）
}

/// ショップアイテム1種
class ShopItem {
  final String id;
  final String name;
  final String description;
  final String emoji;
  final int cost;
  final ShopEffectType effectType;
  final double effectValue;
  final ElementType? element; // elementBoost時のみ使用

  const ShopItem({
    required this.id,
    required this.name,
    required this.description,
    required this.emoji,
    required this.cost,
    required this.effectType,
    required this.effectValue,
    this.element,
  });
}

/// セッション中に蓄積されるアップグレード効果
class SessionBuffs {
  double attackBoost = 0.0;
  double attackSpeedBoost = 0.0;
  double chainChanceBoost = 0.0;
  double chainMultBoost = 0.0;
  double manaRegenBoost = 0.0;
  double critBoost = 0.0;
  double goldBonusRate = 0.0;
  int maxManaBonusFlat = 0;
  int extraCardDraw = 0;
  Map<ElementType, double> elementBoosts = {};

  double getElementBoost(ElementType element) =>
      elementBoosts[element] ?? 0.0;

  Map<String, dynamic> toJson() => {
        'attackBoost': attackBoost,
        'attackSpeedBoost': attackSpeedBoost,
        'chainChanceBoost': chainChanceBoost,
        'chainMultBoost': chainMultBoost,
        'manaRegenBoost': manaRegenBoost,
        'critBoost': critBoost,
        'goldBonusRate': goldBonusRate,
        'maxManaBonusFlat': maxManaBonusFlat,
        'extraCardDraw': extraCardDraw,
        'elementBoosts': elementBoosts.map((k, v) => MapEntry(k.name, v)),
      };
}

/// ウェーブクリア後のゴールド計算・ショップ管理
class ShopSystem {
  final _rng = Random();

  /// セッション中に蓄積されたバフ
  final SessionBuffs sessionBuffs = SessionBuffs();

  /// ウェーブクリア時のゴールド計算
  int calcWaveGold({
    required int waveNumber,
    required int score,
    double bonusRate = 0.0,
  }) {
    final base = waveNumber * 8 + (score ~/ 50);
    final variation = 0.8 + _rng.nextDouble() * 0.4;
    final total = (base * variation * (1.0 + bonusRate + sessionBuffs.goldBonusRate)).round();
    return total.clamp(5, 999);
  }

  /// ウェーブ間ショップに並べるアイテムをランダムに選ぶ
  List<ShopItem> rollShopItems({required int waveNumber, int count = 4}) {
    final pool = _buildItemPool(waveNumber);
    pool.shuffle(_rng);
    return pool.take(count.clamp(3, 5)).toList();
  }

  /// ショップアイテムを購入し SessionBuffs に効果を適用する
  bool purchaseItem({
    required ShopItem item,
    required int currentGold,
    required void Function(int spent) onSpend,
    void Function(int hp)? onWallRepair,
  }) {
    if (currentGold < item.cost) return false;
    onSpend(item.cost);
    _applyBuff(item, onWallRepair: onWallRepair);
    return true;
  }

  // ---- プライベート ----

  void _applyBuff(ShopItem item, {void Function(int hp)? onWallRepair}) {
    final v = item.effectValue;
    switch (item.effectType) {
      case ShopEffectType.attackBoost:
        sessionBuffs.attackBoost += v;
      case ShopEffectType.attackSpeedBoost:
        sessionBuffs.attackSpeedBoost += v;
      case ShopEffectType.elementBoost:
        final el = item.element;
        if (el != null) {
          sessionBuffs.elementBoosts[el] =
              (sessionBuffs.elementBoosts[el] ?? 0.0) + v;
        }
      case ShopEffectType.chainChanceBoost:
        sessionBuffs.chainChanceBoost += v;
      case ShopEffectType.chainMultBoost:
        sessionBuffs.chainMultBoost += v;
      case ShopEffectType.manaRegenBoost:
        sessionBuffs.manaRegenBoost += v;
      case ShopEffectType.critBoost:
        sessionBuffs.critBoost += v;
      case ShopEffectType.goldBonus:
        sessionBuffs.goldBonusRate += v;
      case ShopEffectType.maxManaBoost:
        sessionBuffs.maxManaBonusFlat += v.toInt();
      case ShopEffectType.cardDraw:
        sessionBuffs.extraCardDraw += v.toInt();
      case ShopEffectType.wallRepair:
        onWallRepair?.call(v.toInt());
      case ShopEffectType.waveGoldBonus:
        break;
    }
  }

  List<ShopItem> _buildItemPool(int waveNumber) {
    final pool = <ShopItem>[..._commonItems];
    if (waveNumber >= 3) pool.addAll(_midItems);
    if (waveNumber >= 6) pool.addAll(_lateItems);
    return pool;
  }

  // ---- アイテムプール ----

  static const List<ShopItem> _commonItems = [
    ShopItem(
      id: 'shop_atk_boost_s',
      name: '戦士の訓練',
      description: '全ユニット攻撃力+15%',
      emoji: '⚔️',
      cost: 30,
      effectType: ShopEffectType.attackBoost,
      effectValue: 0.15,
    ),
    ShopItem(
      id: 'shop_speed_s',
      name: '迅速の鼓動',
      description: '全ユニット攻撃速度+10%',
      emoji: '⚡',
      cost: 25,
      effectType: ShopEffectType.attackSpeedBoost,
      effectValue: 0.10,
    ),
    ShopItem(
      id: 'shop_mana_s',
      name: 'マナ結晶片',
      description: 'マナ回復速度+20%',
      emoji: '💠',
      cost: 20,
      effectType: ShopEffectType.manaRegenBoost,
      effectValue: 0.20,
    ),
    ShopItem(
      id: 'shop_wall_repair_s',
      name: '城壁修復（小）',
      description: '城壁HP+15即時回復',
      emoji: '🧱',
      cost: 20,
      effectType: ShopEffectType.wallRepair,
      effectValue: 15,
    ),
    ShopItem(
      id: 'shop_gold_bonus_s',
      name: '商人の縁',
      description: '以降ゴールド獲得+20%',
      emoji: '🪙',
      cost: 15,
      effectType: ShopEffectType.goldBonus,
      effectValue: 0.20,
    ),
    ShopItem(
      id: 'shop_fire_boost_s',
      name: '炎の結晶',
      description: '火属性ダメージ+25%',
      emoji: '🔥',
      cost: 30,
      effectType: ShopEffectType.elementBoost,
      effectValue: 0.25,
      element: ElementType.fire,
    ),
    ShopItem(
      id: 'shop_water_boost_s',
      name: '水の結晶',
      description: '水属性ダメージ+25%',
      emoji: '💧',
      cost: 30,
      effectType: ShopEffectType.elementBoost,
      effectValue: 0.25,
      element: ElementType.water,
    ),
    ShopItem(
      id: 'shop_wind_boost_s',
      name: '風の結晶',
      description: '風属性ダメージ+25%',
      emoji: '🌪️',
      cost: 30,
      effectType: ShopEffectType.elementBoost,
      effectValue: 0.25,
      element: ElementType.wind,
    ),
    ShopItem(
      id: 'shop_earth_boost_s',
      name: '土の結晶',
      description: '土属性ダメージ+25%',
      emoji: '🌿',
      cost: 30,
      effectType: ShopEffectType.elementBoost,
      effectValue: 0.25,
      element: ElementType.earth,
    ),
    ShopItem(
      id: 'shop_card_draw',
      name: '予備の書物',
      description: '手札1枚追加で引ける',
      emoji: '📖',
      cost: 35,
      effectType: ShopEffectType.cardDraw,
      effectValue: 1,
    ),
    ShopItem(
      id: 'shop_crit_s',
      name: '鋭利な石',
      description: 'クリティカル率+8%',
      emoji: '💥',
      cost: 25,
      effectType: ShopEffectType.critBoost,
      effectValue: 0.08,
    ),
  ];

  static const List<ShopItem> _midItems = [
    ShopItem(
      id: 'shop_chain_chance',
      name: 'チェーン触媒',
      description: 'チェーン発動確率+15%',
      emoji: '🔗',
      cost: 40,
      effectType: ShopEffectType.chainChanceBoost,
      effectValue: 0.15,
    ),
    ShopItem(
      id: 'shop_atk_boost_m',
      name: '勇者の誓い',
      description: '全ユニット攻撃力+25%',
      emoji: '🗡️',
      cost: 55,
      effectType: ShopEffectType.attackBoost,
      effectValue: 0.25,
    ),
    ShopItem(
      id: 'shop_wall_repair_m',
      name: '城壁修復（中）',
      description: '城壁HP+30即時回復',
      emoji: '🏰',
      cost: 40,
      effectType: ShopEffectType.wallRepair,
      effectValue: 30,
    ),
    ShopItem(
      id: 'shop_light_boost',
      name: '聖なる光',
      description: '光属性ダメージ+30%',
      emoji: '✨',
      cost: 40,
      effectType: ShopEffectType.elementBoost,
      effectValue: 0.30,
      element: ElementType.light,
    ),
    ShopItem(
      id: 'shop_dark_boost',
      name: '闇の囁き',
      description: '闇属性ダメージ+30%',
      emoji: '🌑',
      cost: 40,
      effectType: ShopEffectType.elementBoost,
      effectValue: 0.30,
      element: ElementType.dark,
    ),
    ShopItem(
      id: 'shop_max_mana',
      name: '魔力拡張',
      description: '最大マナ+2',
      emoji: '🔮',
      cost: 50,
      effectType: ShopEffectType.maxManaBoost,
      effectValue: 2,
    ),
  ];

  static const List<ShopItem> _lateItems = [
    ShopItem(
      id: 'shop_chain_mult',
      name: 'チェーン共鳴石',
      description: 'チェーン倍率+40%',
      emoji: '⚗️',
      cost: 80,
      effectType: ShopEffectType.chainMultBoost,
      effectValue: 0.40,
    ),
    ShopItem(
      id: 'shop_atk_boost_l',
      name: '伝説の訓練',
      description: '全ユニット攻撃力+40%',
      emoji: '🏹',
      cost: 90,
      effectType: ShopEffectType.attackBoost,
      effectValue: 0.40,
    ),
    ShopItem(
      id: 'shop_speed_m',
      name: '嵐の加護',
      description: '全ユニット攻撃速度+25%',
      emoji: '🌩️',
      cost: 70,
      effectType: ShopEffectType.attackSpeedBoost,
      effectValue: 0.25,
    ),
    ShopItem(
      id: 'shop_wall_repair_l',
      name: '大修復魔法',
      description: '城壁HP+60即時回復',
      emoji: '🌟',
      cost: 75,
      effectType: ShopEffectType.wallRepair,
      effectValue: 60,
    ),
    ShopItem(
      id: 'shop_crit_m',
      name: '覇者の眼',
      description: 'クリティカル率+20%',
      emoji: '👁️',
      cost: 70,
      effectType: ShopEffectType.critBoost,
      effectValue: 0.20,
    ),
  ];
}
