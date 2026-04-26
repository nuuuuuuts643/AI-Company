/// 建物の種類
enum BuildingType {
  // 初期解禁
  farm,         // 農場：食料生産+
  storehouse,   // 倉庫：資源上限アップ
  wall,         // 城壁：守備力+
  // ループアンロック
  well,         // 井戸：干ばつ耐性
  forge,        // 鍛冶場：守備+、武器アップ
  tavern,       // 酒場：村人士気アップ（効率+）
  watchtower,   // 見張り台：探索報酬+、夜の早期警戒
  granary,      // 穀物庫：飢饉リスク低減
  shrine,       // 祠：災厄イベント確率低下
  market,       // 市場：金の収入+
}

extension BuildingTypeInfo on BuildingType {
  String get label {
    switch (this) {
      case BuildingType.farm:
        return '農場';
      case BuildingType.storehouse:
        return '倉庫';
      case BuildingType.wall:
        return '城壁';
      case BuildingType.well:
        return '井戸';
      case BuildingType.forge:
        return '鍛冶場';
      case BuildingType.tavern:
        return '酒場';
      case BuildingType.watchtower:
        return '見張り台';
      case BuildingType.granary:
        return '穀物庫';
      case BuildingType.shrine:
        return '祠';
      case BuildingType.market:
        return '市場';
    }
  }

  String get description {
    switch (this) {
      case BuildingType.farm:
        return '農業タスクの食料生産+20%';
      case BuildingType.storehouse:
        return '全資源の上限+50';
      case BuildingType.wall:
        return '守備値+15、モンスター撃退率アップ';
      case BuildingType.well:
        return '干ばつイベント発生時の被害を半減';
      case BuildingType.forge:
        return '守備タスク効率+20%';
      case BuildingType.tavern:
        return '全村人の士気が高まり、全タスク効率+5%';
      case BuildingType.watchtower:
        return '探索で発見できるイベント種類+、夜の奇襲確率-';
      case BuildingType.granary:
        return '食料消費量-10%、飢饉イベント確率-';
      case BuildingType.shrine:
        return '疫病・呪いイベントの発生確率-25%';
      case BuildingType.market:
        return '毎日金貨+2、商人イベント報酬+';
    }
  }

  /// 建設コスト
  Map<String, int> get buildCost {
    switch (this) {
      case BuildingType.farm:
        return {'wood': 10, 'stone': 0};
      case BuildingType.storehouse:
        return {'wood': 15, 'stone': 5};
      case BuildingType.wall:
        return {'wood': 5, 'stone': 20};
      case BuildingType.well:
        return {'wood': 8, 'stone': 10};
      case BuildingType.forge:
        return {'wood': 10, 'stone': 15};
      case BuildingType.tavern:
        return {'wood': 20, 'stone': 5, 'gold': 5};
      case BuildingType.watchtower:
        return {'wood': 15, 'stone': 10};
      case BuildingType.granary:
        return {'wood': 12, 'stone': 8};
      case BuildingType.shrine:
        return {'wood': 5, 'stone': 15, 'gold': 3};
      case BuildingType.market:
        return {'wood': 10, 'stone': 5, 'gold': 10};
    }
  }

  /// ループ何周目から解禁されるか（0=初期から）
  int get requiredLoops => switch (this) {
        BuildingType.farm => 0,
        BuildingType.storehouse => 0,
        BuildingType.wall => 0,
        BuildingType.well => 1,
        BuildingType.forge => 1,
        BuildingType.tavern => 2,
        BuildingType.watchtower => 2,
        BuildingType.granary => 3,
        BuildingType.shrine => 3,
        BuildingType.market => 4,
      };

  /// このアップグレードIDが必要か（記憶の欠片で解禁）
  String? get requiredUpgradeId => switch (this) {
        BuildingType.tavern => 'unlock_tavern',
        BuildingType.watchtower => 'unlock_watchtower',
        BuildingType.granary => 'unlock_granary',
        BuildingType.shrine => 'unlock_shrine',
        BuildingType.market => 'unlock_market',
        _ => null,
      };
}

/// 建物インスタンス（マップ上に実際に建てられたもの）
class Building {
  final String id;
  final BuildingType type;
  int level;            // 1〜3（将来的な強化）
  bool isUnderConstruction;
  int constructionDaysLeft;

  Building({
    required this.id,
    required this.type,
    this.level = 1,
    this.isUnderConstruction = false,
    this.constructionDaysLeft = 0,
  });

  bool get isReady => !isUnderConstruction;

  /// 1日進行したとき建設を進める
  void advanceConstruction() {
    if (isUnderConstruction && constructionDaysLeft > 0) {
      constructionDaysLeft--;
      if (constructionDaysLeft <= 0) {
        isUnderConstruction = false;
      }
    }
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'type': type.index,
        'level': level,
        'isUnderConstruction': isUnderConstruction,
        'constructionDaysLeft': constructionDaysLeft,
      };

  factory Building.fromJson(Map<String, dynamic> json) {
    return Building(
      id: json['id'] as String,
      type: BuildingType.values[json['type'] as int],
      level: json['level'] as int,
      isUnderConstruction: json['isUnderConstruction'] as bool,
      constructionDaysLeft: json['constructionDaysLeft'] as int,
    );
  }
}
