import '../constants/game_constants.dart';

/// 村人が得意とするタスク
enum TaskType {
  farming,    // 農業：食料生産
  building,   // 建設：木材/石材消費で建物建築速度アップ
  defense,    // 守備：夜の敵撃退率アップ
  exploration,// 探索：ランダムアイテム・イベント発見
  gathering,  // 採集：木材/石材収集
}

extension TaskTypeLabel on TaskType {
  String get label {
    switch (this) {
      case TaskType.farming:
        return '農業';
      case TaskType.building:
        return '建設';
      case TaskType.defense:
        return '守備';
      case TaskType.exploration:
        return '探索';
      case TaskType.gathering:
        return '採集';
    }
  }

  String get emoji {
    switch (this) {
      case TaskType.farming:
        return '🌾';
      case TaskType.building:
        return '🪓';
      case TaskType.defense:
        return '🛡️';
      case TaskType.exploration:
        return '🗺️';
      case TaskType.gathering:
        return '🪵';
    }
  }
}

/// 村人の隠れた個性タイプ
enum PersonalityType {
  hardworker,   // 勤勉: どのタスクも+10%
  farmer,       // 農家: 農業+40%
  craftsman,    // 職人: 建設+40%
  warrior,      // 武闘派: 守備+40%
  adventurer,   // 冒険家: 探索+40%
  forager,      // 採集家: 採集+40%
  lucky,        // 幸運児: 全タスクでランダムボーナス
  cursed,       // 呪われた: 稀に逆効果（隠れネガティブ）
}

extension PersonalityLabel on PersonalityType {
  String get label {
    switch (this) {
      case PersonalityType.hardworker:
        return '勤勉';
      case PersonalityType.farmer:
        return '農家の血';
      case PersonalityType.craftsman:
        return '職人気質';
      case PersonalityType.warrior:
        return '武闘派';
      case PersonalityType.adventurer:
        return '冒険好き';
      case PersonalityType.forager:
        return '採集の達人';
      case PersonalityType.lucky:
        return '幸運児';
      case PersonalityType.cursed:
        return '？？？';
    }
  }

  /// ループ進行でこの個性が解禁されているか
  bool isRevealedAt(int loopCount) {
    // 最初は全員「？？？」。ループを重ねることで解禁
    switch (this) {
      case PersonalityType.hardworker:
        return loopCount >= 1;
      case PersonalityType.farmer:
      case PersonalityType.craftsman:
      case PersonalityType.warrior:
        return loopCount >= 2;
      case PersonalityType.adventurer:
      case PersonalityType.forager:
        return loopCount >= 3;
      case PersonalityType.lucky:
        return loopCount >= 5;
      case PersonalityType.cursed:
        return loopCount >= 4;
    }
  }
}

/// 村人1人のデータ
class Villager {
  final String id;
  String name;
  PersonalityType personality;
  TaskType? assignedTask;   // 今日のタスク（nullは未割り当て）
  int age;
  bool isAlive;

  // ループで蓄積されるメモリ（解禁された個性情報）
  bool isPersonalityRevealed;

  // 今日のタスク効率（計算後）
  double taskEfficiency;

  // アニメーション状態
  bool isGlowing;           // 正しいタスク割り当て時のピカッ演出フラグ

  Villager({
    required this.id,
    required this.name,
    required this.personality,
    this.assignedTask,
    this.age = 20,
    this.isAlive = true,
    this.isPersonalityRevealed = false,
    this.taskEfficiency = 1.0,
    this.isGlowing = false,
  });

  /// この村人の得意タスク（個性から判定）
  TaskType get preferredTask {
    switch (personality) {
      case PersonalityType.farmer:
        return TaskType.farming;
      case PersonalityType.craftsman:
        return TaskType.building;
      case PersonalityType.warrior:
        return TaskType.defense;
      case PersonalityType.adventurer:
        return TaskType.exploration;
      case PersonalityType.forager:
        return TaskType.gathering;
      default:
        return TaskType.farming; // hardworker/lucky/cursedはfarmingをデフォルト
    }
  }

  /// 正しいタスクに割り当てられているか
  bool get isOptimallyAssigned {
    if (assignedTask == null) return false;
    if (personality == PersonalityType.hardworker) return true; // 何でもOK
    return assignedTask == preferredTask;
  }

  /// タスク効率を計算
  double calculateEfficiency() {
    if (assignedTask == null) return 0.0;
    switch (personality) {
      case PersonalityType.hardworker:
        return GameConstants.hardworkerBonus;
      case PersonalityType.lucky:
        // ランダムボーナス: 0.8〜1.8
        return 0.8 + (DateTime.now().millisecond % 100) / 100.0;
      case PersonalityType.cursed:
        return isOptimallyAssigned ? 0.6 : 0.4; // 常に低め
      default:
        return isOptimallyAssigned
            ? GameConstants.specialistBonus
            : GameConstants.mismatchPenalty;
    }
  }

  Villager copyWith({
    String? name,
    PersonalityType? personality,
    TaskType? assignedTask,
    int? age,
    bool? isAlive,
    bool? isPersonalityRevealed,
    double? taskEfficiency,
    bool? isGlowing,
  }) {
    return Villager(
      id: id,
      name: name ?? this.name,
      personality: personality ?? this.personality,
      assignedTask: assignedTask ?? this.assignedTask,
      age: age ?? this.age,
      isAlive: isAlive ?? this.isAlive,
      isPersonalityRevealed: isPersonalityRevealed ?? this.isPersonalityRevealed,
      taskEfficiency: taskEfficiency ?? this.taskEfficiency,
      isGlowing: isGlowing ?? this.isGlowing,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'personality': personality.index,
        'assignedTask': assignedTask?.index,
        'age': age,
        'isAlive': isAlive,
        'isPersonalityRevealed': isPersonalityRevealed,
      };

  factory Villager.fromJson(Map<String, dynamic> json) {
    return Villager(
      id: json['id'] as String,
      name: json['name'] as String,
      personality: PersonalityType.values[json['personality'] as int],
      assignedTask: json['assignedTask'] != null
          ? TaskType.values[json['assignedTask'] as int]
          : null,
      age: json['age'] as int,
      isAlive: json['isAlive'] as bool,
      isPersonalityRevealed: json['isPersonalityRevealed'] as bool,
    );
  }
}
