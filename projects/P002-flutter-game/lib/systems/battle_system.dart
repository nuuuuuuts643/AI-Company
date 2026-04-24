import 'dart:math';
import '../components/enemy_component.dart';
import '../components/unit_component.dart';
import '../constants/element_chart.dart';
import '../constants/game_constants.dart';
import '../game/game_state.dart';
import '../models/equipment_data.dart';
import '../models/unit_data.dart';

enum AuraType { heal, atkSpeed, atkPower }

/// オートバトルを処理するシステム
/// ユニットが射程内の敵を自動で攻撃する
class BattleSystem {
  final GameStateNotifier gameState;

  // バフ適用時のエフェクトコールバック
  final void Function(UnitComponent healer, UnitComponent target, AuraType aura)?
      onAuraApplied;

  final _rng = Random();

  // 各ユニットの攻撃クールダウン（instanceId → 残秒数）
  final Map<String, double> _attackCooldowns = {};

  // オーラのインターバルタイマー（instanceId → 残秒数）
  final Map<String, double> _auraTimers = {};

  BattleSystem({required this.gameState, this.onAuraApplied});

  /// 毎フレーム更新：ユニットvs敵のオートバトル
  void update(
    double dt,
    List<UnitComponent> units,
    List<EnemyComponent> enemies,
  ) {
    // バフタイマー更新
    for (final unit in units) {
      unit.unitInstance.tickBuffs(dt);
    }

    for (final unit in units) {
      if (!unit.unitInstance.isAlive) continue;
      final id = unit.unitInstance.instanceId;

      // 支援ユニット（オーラ型）
      if (unit.unitInstance.attackType == AttackType.support) {
        _processAura(dt, unit, units);
        continue;
      }

      // 攻撃クールダウン更新（バフ後のatkSpeedを使用）
      final cooldown = (_attackCooldowns[id] ?? 0.0) - dt;
      _attackCooldowns[id] = cooldown;
      if (cooldown > 0) continue;

      // 射程内の敵を取得
      final target = _findTarget(unit, enemies);
      if (target == null) continue;

      // 攻撃実行
      _executeAttack(unit, target);

      // クールダウンリセット（バフ + ボーンSPDバフ込み）
      _attackCooldowns[id] = 1.0 / (unit.unitInstance.effectiveAtkSpeed * gameState.boonSpdMultiplier);
    }

    // 状態異常処理
    _processStatusEffects(dt, enemies);
  }

  /// 支援ユニットのオーラ処理
  void _processAura(double dt, UnitComponent healer, List<UnitComponent> allies) {
    final id = healer.unitInstance.instanceId;
    final timer = (_auraTimers[id] ?? 0.0) - dt;
    _auraTimers[id] = timer;
    if (timer > 0) return;

    final skills = healer.unitInstance.skills;

    // ヒールオーラ：最低HP%の味方を回復
    if (skills.contains(UnitSkillId.healAura)) {
      final target = _findLowestHpAlly(healer, allies);
      if (target != null) {
        final healAmt = (healer.unitInstance.attack * 1.5).round().clamp(20, 999);
        target.unitInstance.heal(healAmt);
        onAuraApplied?.call(healer, target, AuraType.heal);
      }
      _auraTimers[id] = 3.5; // 3.5秒ごとに発動
    }

    // 加速オーラ：同レーン全体に攻撃速度バフ
    else if (skills.contains(UnitSkillId.blessingAura)) {
      for (final ally in allies) {
        if (ally == healer) continue;
        if (!ally.unitInstance.isAlive) continue;
        // 隣接レーン含む範囲
        if ((ally.unitInstance.laneIndex - healer.unitInstance.laneIndex).abs() > 1) continue;
        ally.unitInstance.atkSpeedBuff = 1.6;
        ally.unitInstance.atkSpeedBuffTimer = 5.0;
        onAuraApplied?.call(healer, ally, AuraType.atkSpeed);
      }
      _auraTimers[id] = 5.0;
    }
  }

  UnitComponent? _findLowestHpAlly(UnitComponent source, List<UnitComponent> allies) {
    UnitComponent? best;
    double bestRatio = 1.1;
    for (final ally in allies) {
      if (ally == source) continue;
      if (!ally.unitInstance.isAlive) continue;
      // 同レーン or 隣接
      if ((ally.unitInstance.laneIndex - source.unitInstance.laneIndex).abs() > 1) continue;
      final ratio = ally.unitInstance.hpRatio;
      if (ratio < bestRatio) { bestRatio = ratio; best = ally; }
    }
    return best;
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

      // 同レーンのみ攻撃（レーン防衛の戦略性を担保）
      if (enemy.laneIndex != unit.unitInstance.laneIndex) continue;

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

    // 基礎ダメージ（ボーンATKバフ適用）
    double dmg = attacker.effectiveAttack.toDouble() * gameState.boonAtkMultiplier;

    // アーマー貫通（土騎士は破壊ダメージ倍）
    if (target.hasArmor && target.armorHp > 0) {
      // アーマーへのダメージ（一部スキルで2倍）
      dmg *= 0.5;
    }

    dmg *= elementMult;

    // クリティカル計算（装備 + ボーンcritBonus 合算）
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
    return (base + gameState.boonCritBonus).clamp(0.0, 0.75); // 最大75%上限
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
