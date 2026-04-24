import 'dart:math';
import '../components/enemy_component.dart';
import '../components/unit_component.dart';
import '../constants/element_chart.dart';
import '../constants/game_constants.dart';
import '../game/game_state.dart';
import '../models/equipment_data.dart';

/// オートバトルを処理するシステム
/// ユニットが射程内の敵を自動で攻撃する
class BattleSystem {
  final GameStateNotifier gameState;

  final _rng = Random();

  // 各ユニットの攻撃クールダウン（instanceId → 残秒数）
  final Map<String, double> _attackCooldowns = {};

  BattleSystem({required this.gameState});

  /// 毎フレーム更新：ユニットvs敵のオートバトル
  void update(
    double dt,
    List<UnitComponent> units,
    List<EnemyComponent> enemies,
  ) {
    for (final unit in units) {
      if (!unit.unitInstance.isAlive) continue;

      // クールダウン更新
      final id = unit.unitInstance.instanceId;
      final cooldown = (_attackCooldowns[id] ?? 0.0) - dt;
      _attackCooldowns[id] = cooldown;
      if (cooldown > 0) continue;

      // 射程内の敵を取得（同レーン優先、次に隣接レーン）
      final target = _findTarget(unit, enemies);
      if (target == null) continue;

      // 攻撃実行
      _executeAttack(unit, target);

      // クールダウンリセット（攻撃速度に反比例）
      _attackCooldowns[id] = 1.0 / unit.unitInstance.attackSpeed;
    }

    // 燃焼ダメージなどの状態異常処理
    _processStatusEffects(dt, enemies);
  }

  /// 属性倍率計算（外部から呼べるようpublic）
  double calculateElementMultiplier(
      ElementType attacker, ElementType defender) {
    return ElementChart.getMultiplier(attacker, defender);
  }

  // ---- プライベートメソッド ----

  EnemyComponent? _findTarget(
      UnitComponent unit, List<EnemyComponent> enemies) {
    EnemyComponent? best;
    double bestY = double.negativeInfinity;

    // 前列ユニット（rowIndex=0）は射程を伸ばして敵フィールドをカバー
    // 後列ユニットは自分のセル付近に来た敵だけ攻撃
    final baseRange = unit.unitInstance.attackRange;
    final rowBonus = (3 - unit.unitInstance.rowIndex) * 30.0; // 前列ほど射程長い
    final effectiveRange = baseRange + rowBonus;

    for (final enemy in enemies) {
      if (!enemy.isAlive) continue;

      // 同列 or 隣列をカバー
      final sameLane =
          (enemy.laneIndex - unit.unitInstance.laneIndex).abs() <= 1;
      if (!sameLane) continue;

      // ユニットより上（Y値が小さい）にいる敵を対象
      final dy = unit.position.y - enemy.position.y;
      if (dy < 0 || dy > effectiveRange) continue;

      if (best == null || enemy.position.y > bestY) {
        best = enemy;
        bestY = enemy.position.y;
      }
    }
    return best;
  }

  void _executeAttack(UnitComponent unit, EnemyComponent target) {
    final attacker = unit.unitInstance;
    final enemyData = target.enemyData;

    // 属性倍率
    final elementMult =
        ElementChart.getMultiplier(attacker.element, enemyData.element);

    // 基礎ダメージ
    double dmg = attacker.effectiveAttack.toDouble();

    // アーマー貫通（土騎士は破壊ダメージ倍）
    if (target.hasArmor && target.armorHp > 0) {
      // アーマーへのダメージ（一部スキルで2倍）
      dmg *= 0.5;
    }

    dmg *= elementMult;

    // クリティカル計算（装備の critChance 合算値を参照）
    final critChance = _calcCritChance();
    final isCrit = _rng.nextDouble() < critChance;
    if (isCrit) dmg *= GameConstants.criticalDamageMultiplier;

    final finalDmg = dmg.round().clamp(1, 9999);

    // 攻撃アニメーション起動
    unit.triggerAttackAnimation();

    // 実際のダメージ適用はgame層のコールバック経由（FloatingText等と連動）
    target.takeDamage(finalDmg);

    // 状態異常付与（スキル依存）
    _applyOnHitEffects(attacker, target, attacker.element);
  }


  /// 装備から critChance を合算して返す
  double _calcCritChance() {
    double base = GameConstants.baseCritChance;
    for (final slot in gameState.player.equippedItems.values) {
      if (slot == null) continue;
      final data = EquipmentMaster.getById(slot.equipmentId);
      if (data == null) continue;
      for (final effect in data.effects) {
        if (effect.type == EquipmentEffectType.critChance) {
          base += effect.value * slot.level;
        }
      }
    }
    return base.clamp(0.0, 0.75); // 最大75%上限
  }

  void _applyOnHitEffects(
    dynamic attacker,
    EnemyComponent target,
    ElementType element,
  ) {
    switch (element) {
      case ElementType.fire:
        // 火属性：燃焼付与
        target.applyBurn(damagePerSec: 5.0, duration: 3.0);
        break;
      case ElementType.water:
        // 水属性：鈍足付与
        target.applySlow(factor: 0.5, duration: 2.0);
        break;
      case ElementType.wind:
        // 風属性：ノックバック
        target.applyKnockback(distance: 20.0);
        break;
      default:
        break;
    }
  }

  void _processStatusEffects(double dt, List<EnemyComponent> enemies) {
    for (final enemy in enemies) {
      enemy.tickStatusEffects(dt);
    }
  }
}
