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
  final String instanceId;     // 実行時ユニークID
  final String cardId;         // 元のカードID
  final ElementType element;
  final int maxHp;
  int currentHp;
  final int attack;
  final double attackSpeed;    // 秒あたり攻撃回数
  final double attackRange;
  final AttackType attackType;
  final int aoeRadius;
  final List<UnitSkillId> skills;

  // 配置位置（Flameコンポーネント側で管理するが参照用に保持）
  final int laneIndex; // 0=上, 1=中, 2=下

  // 状態異常
  bool isFrozen;
  bool isBurning;
  double burnDamagePerSec;
  bool isBlessed;
  double blessedAttackMultiplier;

  // アニメーション状態
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
    this.aoeRadius = 0,
    this.skills = const [],
    int? currentHp,
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

  /// 有効攻撃力（バフ・状態込み）
  int get effectiveAttack =>
      (attack * (isBlessed ? blessedAttackMultiplier : 1.0)).round();

  void takeDamage(int dmg) {
    currentHp = (currentHp - dmg).clamp(0, maxHp);
  }

  void heal(int amount) {
    currentHp = (currentHp + amount).clamp(0, maxHp);
  }
}
