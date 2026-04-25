/// 地形タイプ（敵フィールドに設置する障害物）
enum TerrainType {
  mountain, // 山岳: レーンをブロック → 敵を隣列に誘導
  river,    // 急流: 敵の移動速度60%低下
  swamp,    // 毒沼: 継続ダメージ 15/秒
}

extension TerrainTypeInfo on TerrainType {
  String get emoji {
    switch (this) {
      case TerrainType.mountain: return '⛰️';
      case TerrainType.river:    return '🌊';
      case TerrainType.swamp:    return '☠️';
    }
  }

  String get label {
    switch (this) {
      case TerrainType.mountain: return '山岳';
      case TerrainType.river:    return '急流';
      case TerrainType.swamp:    return '毒沼';
    }
  }

  /// null = そのウェーブ終了まで持続
  double? get defaultDuration {
    switch (this) {
      case TerrainType.mountain: return null;
      case TerrainType.river:    return 18.0;
      case TerrainType.swamp:    return 15.0;
    }
  }
}

/// フィールド上の地形エントリ（ゲームロジック用）
class TerrainEntry {
  final TerrainType type;
  final int laneIndex;

  /// ゲームワールドY座標（地形の上端）
  final double y;

  double? remainingDuration;

  TerrainEntry({
    required this.type,
    required this.laneIndex,
    required this.y,
    double? duration,
    bool permanent = false,
  }) : remainingDuration = permanent ? null : (duration ?? type.defaultDuration);

  bool get expired =>
      remainingDuration != null && remainingDuration! <= 0;

  void tick(double dt) {
    if (remainingDuration != null) {
      remainingDuration = remainingDuration! - dt;
    }
  }

  /// 敵がこの地形の影響範囲にいるか
  bool overlapsEnemy(double enemyY) =>
      enemyY >= y - 10 && enemyY <= y + 50;
}
