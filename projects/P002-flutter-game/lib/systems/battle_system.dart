import 'dart:math';
import 'package:flame/components.dart';
import 'package:flutter/material.dart';
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

  // 攻撃ヒット時の視覚エフェクトコールバック（既にダメージ適用済み）
  final void Function(UnitComponent unit, EnemyComponent target, int damage, bool isWeakness)?
      onAttackVisual;

  // スキル発動時のフローティングテキストコールバック
  final void Function(String text, Color color, Vector2 pos)? onSkillProc;

  final _rng = Random();

  // 各ユニットの攻撃クールダウン（instanceId → 残秒数）
  final Map<String, double> _attackCooldowns = {};

  // オーラのインターバルタイマー（instanceId → 残秒数）
  final Map<String, double> _auraTimers = {};

  // 敵の近接攻撃インターバルタイマー（1秒ごとに一括処理）
  double _enemyMeleeTimer = 1.0;

  BattleSystem({
    required this.gameState,
    this.onAuraApplied,
    this.onAttackVisual,
    this.onSkillProc,
  });

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

    // 挑発オーラ（tauntスキル持ちが近くの敵を減速）
    _processTauntAura(units, enemies);

    // 敵の近接攻撃（ユニットとの接触ダメージ・0.5秒インターバル）
    _enemyMeleeTimer -= dt;
    if (_enemyMeleeTimer <= 0) {
      _enemyMeleeTimer = 1.0;
      _processEnemyMelee(units, enemies);
    }
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

    // アーマー軽減（armorBreakスキルがあれば貫通）
    if (target.hasArmor && target.armorHp > 0) {
      if (!attacker.skills.contains(UnitSkillId.armorBreak)) {
        dmg *= 0.5;
      }
    }

    dmg *= elementMult;

    // クリティカル計算（装備 + ボーンcritBonus 合算）
    final critChance = _calcCritChance();
    final isCrit = _rng.nextDouble() < critChance;
    if (isCrit) dmg *= GameConstants.criticalDamageMultiplier;

    final finalDmg = dmg.round().clamp(1, 9999);

    // 攻撃アニメーション起動
    unit.triggerAttackAnimation();

    target.takeDamage(finalDmg);

    // 攻撃視覚コールバック（スラッシュ・プロジェクタイル・ダメージ数値）
    onAttackVisual?.call(unit, target, finalDmg, elementMult >= 2.0);

    // lifeSteal: ダメージの22%をHP回復
    if (attacker.skills.contains(UnitSkillId.lifeSteal)) {
      final healed = (finalDmg * 0.22).round().clamp(1, 80);
      attacker.heal(healed);
      onSkillProc?.call(
        '+$healed 🩸',
        const Color(0xFF66BB6A),
        unit.position.clone() + Vector2(0, -30),
      );
    }

    // doubleShot: 70%威力の2発目
    if (attacker.skills.contains(UnitSkillId.doubleShot) && target.isAlive) {
      final secondDmg = (finalDmg * 0.7).round().clamp(1, 9999);
      target.takeDamage(secondDmg);
      onSkillProc?.call(
        '💫 $secondDmg',
        const Color(0xFF80DEEA),
        target.position.clone() + Vector2(10, -35),
      );
    }

    // 状態異常付与（スキル依存）
    _applyOnHitEffects(attacker, target, attacker.element);
  }

  /// 挑発オーラ: tauntスキル持ちユニットの近くにいる敵を強力に減速させる
  void _processTauntAura(List<UnitComponent> units, List<EnemyComponent> enemies) {
    for (final unit in units) {
      if (!unit.unitInstance.isAlive) continue;
      if (!unit.unitInstance.skills.contains(UnitSkillId.taunt)) continue;
      for (final enemy in enemies) {
        if (!enemy.isAlive) continue;
        if (enemy.laneIndex != unit.unitInstance.laneIndex) continue;
        final dist = (unit.position.y - enemy.position.y).abs();
        if (dist < 90) {
          enemy.applySlow(factor: 0.35, duration: 0.6);
        }
      }
    }
  }

  /// 敵の近接攻撃: 敵ユニットとの接触でユニットにダメージ（1秒ごとに一括処理）
  void _processEnemyMelee(List<UnitComponent> units, List<EnemyComponent> enemies) {
    for (final enemy in enemies) {
      if (!enemy.isAlive) continue;
      for (final unit in units) {
        if (!unit.unitInstance.isAlive) continue;
        if (enemy.laneIndex != unit.unitInstance.laneIndex) continue;
        final dist = (unit.position.y - enemy.position.y).abs();
        if (dist < 45) {
          final dmg = (enemy.enemyData.attackPower * 0.10).round().clamp(1, 999);
          unit.unitInstance.takeDamage(dmg);

          // resurrection: HP0になったとき1度だけ50%で復活
          if (!unit.unitInstance.isAlive &&
              unit.unitInstance.skills.contains(UnitSkillId.resurrection)) {
            unit.unitInstance.skills.remove(UnitSkillId.resurrection);
            unit.unitInstance.heal((unit.unitInstance.maxHp * 0.5).round());
          }
        }
      }
    }
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
        target.applyBurn(damagePerSec: 5.0, duration: 3.0);
        onSkillProc?.call(
          '🔥燃焼',
          const Color(0xFFFF7043),
          target.position.clone() + Vector2(-10, -28),
        );
        break;
      case ElementType.water:
        target.applySlow(factor: 0.5, duration: 2.0);
        onSkillProc?.call(
          '❄スロー',
          const Color(0xFF64B5F6),
          target.position.clone() + Vector2(-10, -28),
        );
        break;
      case ElementType.wind:
        target.applyKnockback(distance: 20.0);
        onSkillProc?.call(
          '💨ノックバック',
          const Color(0xFF80CBC4),
          target.position.clone() + Vector2(-14, -28),
        );
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
