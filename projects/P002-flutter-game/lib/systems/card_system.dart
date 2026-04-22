import 'package:uuid/uuid.dart';
import '../constants/game_constants.dart';
import '../constants/element_chart.dart';
import '../models/card_data.dart';
import '../models/unit_data.dart';
import '../models/equipment_data.dart';
import '../game/game_state.dart';

/// カード手札管理・ユニットインスタンス生成システム
class CardSystem {
  final GameStateNotifier gameState;
  final _uuid = const Uuid();

  CardSystem({required this.gameState});

  /// カードデータからユニットインスタンスを生成
  UnitInstance createUnitInstance(CardData card, int laneIndex) {
    // 装備ボーナスを反映
    final attackBonus = _getAttackBonus(card);
    final hpBonus = _getHpBonus(card);

    final baseAttack = (card.baseAttack * (1 + attackBonus)).round();
    final baseHp = (card.baseHp * (1 + hpBonus)).round();

    // カード種別からAttackTypeを判定
    final AttackType attackType;
    if (card.aoeRadius > 0 && card.attackRange > 100) {
      attackType = AttackType.aoe;
    } else if (card.attackRange > 100) {
      attackType = AttackType.ranged;
    } else if (card.element == ElementType.light && card.baseAttack < 0) {
      attackType = AttackType.support;
    } else {
      attackType = AttackType.melee;
    }

    return UnitInstance(
      instanceId: _uuid.v4(),
      cardId: card.id,
      element: card.element,
      maxHp: baseHp,
      attack: baseAttack,
      attackSpeed: card.attackSpeed,
      attackRange: card.attackRange,
      attackType: attackType,
      laneIndex: laneIndex,
      aoeRadius: card.aoeRadius,
    );
  }

  /// 手札から使えるカード一覧（マナ足りるもの）
  List<CardData> getPlayableCards() {
    final battle = gameState.battle;
    if (battle == null) return [];
    return battle.handCardIds
        .map((id) => CardMaster.getById(id))
        .whereType<CardData>()
        .where((card) => battle.mana >= card.manaCost)
        .toList();
  }

  /// カードが配置可能か（マナ・配置上限チェック）
  bool canPlaceCard(CardData card, int laneIndex, int currentUnitsInLane) {
    final battle = gameState.battle;
    if (battle == null) return false;
    if (battle.mana < card.manaCost) return false;
    // 1レーンに最大4ユニット
    if (card.cardType == CardType.unit && currentUnitsInLane >= 4) return false;
    return true;
  }

  // ---- プライベート：装備ボーナス計算 ----

  double _getAttackBonus(CardData card) {
    double bonus = 0;
    final equipped = gameState.player.equippedItems;
    for (final slot in equipped.values) {
      if (slot == null) continue;
      final equipData = _getEquipData(slot.equipmentId);
      if (equipData == null) continue;
      for (final effect in equipData.effects) {
        if (effect.type == EquipmentEffectType.attackBoost) {
          bonus += effect.value * slot.level;
        }
        if (effect.type == EquipmentEffectType.elementBoost &&
            effect.element == card.element) {
          bonus += effect.value * slot.level;
        }
      }
    }
    return bonus;
  }

  double _getHpBonus(CardData card) {
    double bonus = 0;
    final equipped = gameState.player.equippedItems;
    for (final slot in equipped.values) {
      if (slot == null) continue;
      final equipData = _getEquipData(slot.equipmentId);
      if (equipData == null) continue;
      for (final effect in equipData.effects) {
        if (effect.type == EquipmentEffectType.hpBoost) {
          bonus += effect.value * slot.level;
        }
      }
    }
    return bonus;
  }

  dynamic _getEquipData(String id) {
    try {
      return EquipmentMaster.getById(id);
    } catch (_) {
      return null;
    }
  }
}

