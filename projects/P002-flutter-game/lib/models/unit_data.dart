import '../constants/element_chart.dart';

/// ユニットの攻撃タイプ
enum AttackType {
  melee,    // 近接
  ranged,   // 遠距離（射程距離から攻撃）
  aoe,      // 範囲攻撃
  support,  // 回復・バフ
}

/// ユニットのスキルID
enum UnitSkillId {
  // 火
  burnOnHit,          // 攻撃時に「燃焼」付与（持続ダメージ）
  explosiveDeath,     // 死亡時に爆発

  // 水
  slowOnHit,          // 攻撃時に「鈍足」付与
  healAura,           // 周囲味方を徐々に回復

  // 風
  doubleShot,         // 矢を2本同時発射
  knockback,          // 攻撃時にノックバック

  // 土
  taunt,              // 敵の攻撃対象を自分に引きつける
  armorBreak,         // アーマーへのダメージ2倍

  // 光
  resurrection,       // 1回だけ復活
  blessingAura,       // 周囲ユニットの攻撃力+20%

  // 闇
  lifeSteal,          // ダメージの20%をHP回復
  summonSkeleton,     // 倒した敵からスケルトン召喚
}

/// フィールド上のユニット実行時データ
class UnitInstance {
  final String instanceId;
  String cardId;
  ElementType element;
  int maxHp;
  int currentHp;
  int attack;
  double attackSpeed;
  double attackRange;
  AttackType attackType;
  int aoeRadius;
  List<UnitSkillId> skills;
  String displayName;   // 表示名（フュージョン後は変化）
  String emoji;         // 表示絵文字

  final int laneIndex; // 列 (0=左, 1=中, 2=右)
  final int rowIndex;  // 行 (0=前列/敵に近い, 3=後列)

  // フュージョン
  int fusionLevel;      // 1=通常, 2=強化, 3=超強化
  bool isFused;         // 異属性合体フラグ

  // 状態異常
  bool isFrozen;
  bool isBurning;
  double burnDamagePerSec;
  bool isBlessed;
  double blessedAttackMultiplier;

  bool isAttacking;
  bool isDying;

  UnitInstance({
    required this.instanceId,
    required this.cardId,
    required this.element,
    required this.maxHp,
    required this.attack,
    required this.attackSpeed,
    required this.attackRange,
    required this.attackType,
    required this.laneIndex,
    this.rowIndex = 0,
    required this.displayName,
    required this.emoji,
    this.aoeRadius = 0,
    this.skills = const [],
    int? currentHp,
    this.fusionLevel = 1,
    this.isFused = false,
    this.isFrozen = false,
    this.isBurning = false,
    this.burnDamagePerSec = 0,
    this.isBlessed = false,
    this.blessedAttackMultiplier = 1.0,
    this.isAttacking = false,
    this.isDying = false,
  }) : currentHp = currentHp ?? maxHp;

  bool get isAlive => currentHp > 0;
  double get hpRatio => currentHp / maxHp;

  int get effectiveAttack {
    final fusionMult = 1.0 + (fusionLevel - 1) * 0.5;
    return (attack * fusionMult * (isBlessed ? blessedAttackMultiplier : 1.0))
        .round();
  }

  /// 同属性フュージョン（パワーアップ）
  void powerUp() {
    fusionLevel = (fusionLevel + 1).clamp(1, 3);
    final hpBonus = (maxHp * 0.5).round();
    maxHp += hpBonus;
    currentHp = (currentHp + hpBonus).clamp(0, maxHp);
  }

  /// 異属性フュージョン（完全変身）
  void fuseTo({
    required ElementType newElement,
    required String newName,
    required String newEmoji,
    required int newAttack,
    required int newMaxHp,
  }) {
    element = newElement;
    displayName = newName;
    emoji = newEmoji;
    attack = newAttack;
    maxHp = newMaxHp;
    currentHp = newMaxHp;
    fusionLevel = 2;
    isFused = true;
  }

  void takeDamage(int dmg) {
    currentHp = (currentHp - dmg).clamp(0, maxHp);
  }

  void heal(int amount) {
    currentHp = (currentHp + amount).clamp(0, maxHp);
  }
}
