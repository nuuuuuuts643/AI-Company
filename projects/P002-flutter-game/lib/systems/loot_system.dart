import 'dart:math';
import '../constants/game_constants.dart';
import '../models/enemy_data.dart';
import '../models/equipment_data.dart';
import '../game/game_state.dart';

/// ドロップ結果
class DropResult {
  final String materialId;
  final int count;

  DropResult({required this.materialId, required this.count});
}

/// 素材ドロップ計算システム
class LootSystem {
  final GameStateNotifier gameState;
  final _rng = Random();

  LootSystem({required this.gameState});

  /// 敵撃破時のドロップを判定して返す（ドロップなしの場合はnull）
  DropResult? rollDrop(EnemyData enemy) {
    final rate = _effectiveDropRate(enemy);
    if (_rng.nextDouble() > rate) return null;

    // ドロップ数（ボスは多め）
    final count = enemy.type.isBoss
        ? _rng.nextInt(3) + 2    // 2〜4個
        : enemy.isElite
            ? _rng.nextInt(2) + 1 // 1〜2個
            : 1;

    // ドロップ品質：1/10の確率でレアドロップ
    final materialId = _rng.nextDouble() < 0.10
        ? _getRareDrop(enemy)
        : enemy.dropMaterialId;

    return DropResult(materialId: materialId, count: count);
  }

  /// クリア報酬を付与（ステージクリア時）
  void applyStageRewards(Map<String, int> rewards) {
    rewards.forEach((materialId, count) {
      gameState.player.addMaterial(materialId, count);
    });
  }

  // ---- プライベート ----

  double _effectiveDropRate(EnemyData enemy) {
    double base = enemy.type.isBoss
        ? GameConstants.bossDropBonus
        : enemy.isElite
            ? GameConstants.baseDropRate + GameConstants.eliteDropBonus
            : GameConstants.baseDropRate;

    // 装備ドロップ率ボーナス
    for (final slot in gameState.player.equippedItems.values) {
      if (slot == null) continue;
      final data = EquipmentMaster.getById(slot.equipmentId);
      if (data == null) continue;
      for (final effect in data.effects) {
        if (effect.type == EquipmentEffectType.dropRateBoost) {
          base += effect.value * slot.level;
        }
      }
    }

    return base.clamp(0.0, 1.0);
  }

  String _getRareDrop(EnemyData enemy) {
    // 敵属性に応じたレアドロップ
    const rareDrops = {
      'goblin': 'mat_shaman_staff',
      'orc': 'mat_berserker_axe',
      'fireDrake': 'mat_drake_scale',
      'seaSerpent': 'mat_serpent_scale',
      'windWraith': 'mat_wraith_essence',
      'stoneGolem': 'mat_golem_core',
      'darkKnight': 'mat_dark_blade',
      'shadowBat': 'mat_bat_wing',
    };
    return rareDrops[enemy.type.name] ?? enemy.dropMaterialId;
  }
}
