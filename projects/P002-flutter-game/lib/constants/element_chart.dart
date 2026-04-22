/// 属性システム
/// 火・水・風・土・光・闇の6属性三すくみ

enum ElementType {
  fire,   // 火
  water,  // 水
  wind,   // 風
  earth,  // 土
  light,  // 光
  dark,   // 闇
}

extension ElementTypeLabel on ElementType {
  String get label {
    switch (this) {
      case ElementType.fire:  return '火';
      case ElementType.water: return '水';
      case ElementType.wind:  return '風';
      case ElementType.earth: return '土';
      case ElementType.light: return '光';
      case ElementType.dark:  return '闇';
    }
  }

  String get emoji {
    switch (this) {
      case ElementType.fire:  return '🔥';
      case ElementType.water: return '💧';
      case ElementType.wind:  return '🌪️';
      case ElementType.earth: return '🪨';
      case ElementType.light: return '✨';
      case ElementType.dark:  return '🌑';
    }
  }

  /// この属性に対応するUI色
  int get colorValue {
    switch (this) {
      case ElementType.fire:  return 0xFFE84A1B;
      case ElementType.water: return 0xFF1B8BE8;
      case ElementType.wind:  return 0xFF2ECC71;
      case ElementType.earth: return 0xFFB8860B;
      case ElementType.light: return 0xFFFFD700;
      case ElementType.dark:  return 0xFF9B59B6;
    }
  }
}

/// 属性相性テーブル
/// 三すくみ関係：
///   火 → 風 → 土 → 火（正三角形A）
///   水 → 火（水は火に有効）
///   光 ↔ 闇（互いに弱点）
///   土 → 水（大地が水を吸収）
///   風 → 光（疾風が光を分散）
///   闇 → 土（闇が大地を侵食）
class ElementChart {
  /// attacker の属性が defender に与えるダメージ倍率を返す
  /// 1.5 = 弱点（クリティカル演出）
  /// 0.6 = 耐性（減衰演出）
  /// 1.0 = 通常
  static double getMultiplier(ElementType attacker, ElementType defender) {
    return _chart[attacker]?[defender] ?? 1.0;
  }

  /// 弱点かどうか
  static bool isWeakness(ElementType attacker, ElementType defender) {
    return getMultiplier(attacker, defender) > 1.0;
  }

  /// 耐性かどうか
  static bool isResistance(ElementType attacker, ElementType defender) {
    return getMultiplier(attacker, defender) < 1.0;
  }

  /// チェーン反応が発生する属性ペア
  /// 前の攻撃がA属性だった場合、次にB属性で攻撃するとチェーン発動
  static bool triggersChain(ElementType first, ElementType second) {
    return _chainTriggers[first]?.contains(second) ?? false;
  }

  // ---- 内部テーブル ----

  static const Map<ElementType, Map<ElementType, double>> _chart = {
    ElementType.fire: {
      ElementType.wind:  1.5, // 火は風に強い（炎が風をあおる）
      ElementType.water: 0.6, // 火は水に弱い
      ElementType.earth: 1.0,
      ElementType.light: 1.0,
      ElementType.dark:  1.0,
    },
    ElementType.water: {
      ElementType.fire:  1.5, // 水は火に強い
      ElementType.earth: 1.5, // 水は土を侵食
      ElementType.wind:  0.6, // 水は風に弱い（蒸発）
      ElementType.light: 1.0,
      ElementType.dark:  1.0,
    },
    ElementType.wind: {
      ElementType.earth: 1.5, // 風は土に強い（砂嵐）
      ElementType.light: 1.5, // 風は光を分散
      ElementType.fire:  0.6, // 風は火に弱い
      ElementType.water: 1.0,
      ElementType.dark:  1.0,
    },
    ElementType.earth: {
      ElementType.fire:  1.5, // 土は火に強い（地盤が炎を抑制）
      ElementType.dark:  1.5, // 土は闇に強い（大地の力）
      ElementType.water: 0.6, // 土は水に弱い
      ElementType.wind:  0.6, // 土は風に弱い
      ElementType.light: 1.0,
    },
    ElementType.light: {
      ElementType.dark:  1.5, // 光は闇に強い
      ElementType.wind:  0.6, // 光は風に弱い
      ElementType.fire:  1.0,
      ElementType.water: 1.0,
      ElementType.earth: 1.0,
    },
    ElementType.dark: {
      ElementType.light: 1.5, // 闇は光に強い
      ElementType.earth: 0.6, // 闇は土に弱い
      ElementType.fire:  1.0,
      ElementType.water: 1.0,
      ElementType.wind:  1.0,
    },
  };

  /// チェーン反応トリガーペア
  /// key: 1発目の属性 → value: チェーンを起こす2発目の属性セット
  static const Map<ElementType, List<ElementType>> _chainTriggers = {
    ElementType.fire:  [ElementType.wind],  // 炎→風で延焼チェーン
    ElementType.water: [ElementType.earth], // 水→土で泥流チェーン
    ElementType.wind:  [ElementType.water], // 風→水で嵐チェーン
    ElementType.earth: [ElementType.fire],  // 土→火で溶岩チェーン
    ElementType.light: [ElementType.dark],  // 光→闇で聖域チェーン
    ElementType.dark:  [ElementType.light], // 闇→光で虚無チェーン
  };
}
