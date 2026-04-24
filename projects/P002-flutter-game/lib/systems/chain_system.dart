import '../constants/element_chart.dart';
import '../constants/game_constants.dart';
import '../models/equipment_data.dart';
import '../game/game_state.dart';

/// チェーン反応の計算結果
class ChainResult {
  final ElementType firstElement;
  final ElementType triggerElement;
  final int chainCount;
  final double totalDamage;
  final double multiplier;

  ChainResult({
    required this.firstElement,
    required this.triggerElement,
    required this.chainCount,
    required this.totalDamage,
    required this.multiplier,
  });
}

/// チェーン反応システム
/// 前の攻撃属性と今の攻撃属性の組み合わせでチェーンを判定する
class ChainSystem {
  final GameStateNotifier gameState;

  // ウィンドウ内チェーン履歴（属性, 発生時刻）
  final List<_ChainEntry> _history = [];

  ChainSystem({required this.gameState});

  /// 攻撃が発生したときに呼ぶ
  /// チェーン発動した場合は ChainResult を返す。通常攻撃時は null。
  ChainResult? checkChain({
    required ElementType attackerElement,
    required double damage,
  }) {
    final now = DateTime.now();
    final windowMs = _effectiveChainWindowMs;

    // 期限切れのエントリを削除
    _history.removeWhere((e) =>
        now.difference(e.triggeredAt).inMilliseconds > windowMs);

    // チェーン判定：直前の属性と今の属性がトリガーペアか
    ChainResult? result;
    for (final entry in _history.reversed) {
      if (ElementChart.triggersChain(entry.element, attackerElement)) {
        final count = _history
                .where((e) =>
                    now.difference(e.triggeredAt).inMilliseconds <= windowMs)
                .length +
            1;

        final chainMult = _chainMultiplier(count) * gameState.boonChainMultiplier;
        final totalDamage = damage * chainMult;

        result = ChainResult(
          firstElement: entry.element,
          triggerElement: attackerElement,
          chainCount: count,
          totalDamage: totalDamage,
          multiplier: chainMult,
        );
        break;
      }
    }

    // この攻撃を履歴に追加
    _history.add(_ChainEntry(element: attackerElement, triggeredAt: now));

    // 履歴が長くなりすぎたら古いものを削除
    if (_history.length > 10) {
      _history.removeAt(0);
    }

    return result;
  }

  /// チェーンをリセット（ウェーブ間など）
  void reset() {
    _history.clear();
  }

  // ---- プライベート ----

  /// 装備による有効チェーンウィンドウ（ms）
  int get _effectiveChainWindowMs {
    int base = GameConstants.chainWindowMs;
    // チェーンリング装備時 +500ms
    final accSlot = gameState.player.equippedItems[EquipmentSlot.accessory];
    if (accSlot?.equipmentId == 'acc_chain_ring') {
      base += 500;
    }
    return base;
  }

  /// チェーン数から倍率を計算
  double _chainMultiplier(int count) {
    // 装備ボーナス
    double equipBonus = 0;
    for (final slot in gameState.player.equippedItems.values) {
      if (slot == null) continue;
      final data = EquipmentMaster.getById(slot.equipmentId);
      if (data == null) continue;
      for (final effect in data.effects) {
        if (effect.type == EquipmentEffectType.chainBonus) {
          equipBonus += effect.value * slot.level;
        }
      }
    }

    final baseMult = GameConstants.chainBonusMultiplier;
    switch (count) {
      case 2:
        return baseMult * (1 + equipBonus);
      case 3:
        return baseMult * 1.5 * (1 + equipBonus);
      default: // 4以上
        return baseMult * 2.0 * (1 + equipBonus);
    }
  }
}

class _ChainEntry {
  final ElementType element;
  final DateTime triggeredAt;

  _ChainEntry({required this.element, required this.triggeredAt});
}

