import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../constants/element_chart.dart';
import '../constants/strings.dart';
import '../game/game_state.dart';
import '../models/equipment_data.dart';

/// 装備・強化画面
class EquipmentScreen extends StatefulWidget {
  const EquipmentScreen({super.key});

  @override
  State<EquipmentScreen> createState() => _EquipmentScreenState();
}

class _EquipmentScreenState extends State<EquipmentScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: EquipmentSlot.values.length, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0D0D1A),
      appBar: AppBar(
        backgroundColor: const Color(0xFF0D0D1A),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, color: Colors.white70),
          onPressed: () => Navigator.of(context).pop(),
        ),
        title: const Text(
          Strings.equipTitle,
          style: TextStyle(
            color: Color(0xFFFFE082),
            fontFamily: 'DotGothic16',
            fontSize: 20,
          ),
        ),
        bottom: TabBar(
          controller: _tabController,
          tabs: EquipmentSlot.values
              .map((s) => Tab(text: s.label))
              .toList(),
          labelStyle: const TextStyle(fontFamily: 'DotGothic16', fontSize: 12),
          labelColor: const Color(0xFFFFE082),
          unselectedLabelColor: Colors.white38,
          indicatorColor: const Color(0xFFFFE082),
        ),
      ),
      body: Column(
        children: [
          _MaterialsBar(),
          Expanded(
            child: TabBarView(
              controller: _tabController,
              children: EquipmentSlot.values
                  .map((slot) => _EquipmentSlotTab(slot: slot))
                  .toList(),
            ),
          ),
        ],
      ),
    );
  }
}

/// 所持素材一覧バー（装備画面上部）
class _MaterialsBar extends StatelessWidget {
  static const _labels = {
    'mat_goblin_fang': ('👺', 'ゴブリンの牙'),
    'mat_orc_hide': ('🐗', 'オーク革'),
    'mat_drake_scale': ('🐉', 'ドレイク鱗'),
    'mat_berserker_axe': ('⚔️', '狂戦士の斧'),
    'mat_serpent_scale': ('🐍', '海蛇鱗'),
    'mat_wraith_essence': ('💨', '風霊のエッセンス'),
    'mat_golem_core': ('⚙️', 'ゴーレムの心'),
    'mat_dark_blade': ('🗡️', '闇の刃'),
    'mat_bat_wing': ('🦇', '影蝙蝠の翼'),
    'mat_shaman_staff': ('🪄', 'シャーマンの杖'),
    'mat_lich_crown': ('👑', 'リッチの王冠'),
    'mat_shadow_heart': ('💜', '影の心臓'),
  };

  const _MaterialsBar();

  @override
  Widget build(BuildContext context) {
    final materials = context.watch<GameStateNotifier>().player.materials;
    final owned = materials.entries.where((e) => e.value > 0).toList();
    if (owned.isEmpty) {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        color: const Color(0xFF0A0A18),
        child: const Text(
          '素材なし — バトルで敵を倒すと素材がドロップします',
          style: TextStyle(color: Colors.white38, fontFamily: 'DotGothic16', fontSize: 11),
        ),
      );
    }
    return Container(
      color: const Color(0xFF0A0A18),
      padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Padding(
            padding: EdgeInsets.only(left: 8, bottom: 6),
            child: Text(
              '🎒 所持素材（強化に使用）',
              style: TextStyle(color: Color(0xFFFFE082), fontFamily: 'DotGothic16', fontSize: 11),
            ),
          ),
          SizedBox(
            height: 34,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 4),
              itemCount: owned.length,
              separatorBuilder: (_, __) => const SizedBox(width: 6),
              itemBuilder: (_, i) {
                final id = owned[i].key;
                final count = owned[i].value;
                final info = _labels[id];
                final emoji = info?.$1 ?? '📦';
                final label = info?.$2 ?? id.replaceAll('mat_', '');
                return Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: const Color(0xFF1A1A2E),
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(color: const Color(0xFF3A3A5A)),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(emoji, style: const TextStyle(fontSize: 14)),
                      const SizedBox(width: 4),
                      Text(
                        '$label ×$count',
                        style: const TextStyle(
                          color: Colors.white70,
                          fontFamily: 'DotGothic16',
                          fontSize: 10,
                        ),
                      ),
                    ],
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _EquipmentSlotTab extends StatelessWidget {
  final EquipmentSlot slot;

  const _EquipmentSlotTab({required this.slot});

  @override
  Widget build(BuildContext context) {
    final gs = context.watch<GameStateNotifier>();
    final equippedItem = gs.player.equippedItems[slot];
    final ownedItems = gs.player.ownedEquipments
        .where((e) {
          final data = EquipmentMaster.getById(e.equipmentId);
          return data?.slot == slot;
        })
        .toList();

    // 未所持装備（デモ表示用: マスターから全件）
    final allForSlot = EquipmentMaster.all.where((e) => e.slot == slot).toList();

    return Column(
      children: [
        // 現在装備中
        if (equippedItem != null) ...[
          Padding(
            padding: const EdgeInsets.all(12),
            child: _EquipmentCard(
              data: EquipmentMaster.getById(equippedItem.equipmentId)!,
              owned: equippedItem,
              isEquipped: true,
              onEquip: null,
              onUpgrade: () async {
                final success = await gs.upgradeEquipment(equippedItem);
                if (context.mounted) {
                  HapticFeedback.mediumImpact();
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text(
                        success ? Strings.upgradeSuccess : Strings.upgradeFail,
                        style: const TextStyle(fontFamily: 'DotGothic16'),
                      ),
                      backgroundColor: success
                          ? const Color(0xFF4CAF50)
                          : const Color(0xFFEF5350),
                      duration: const Duration(seconds: 2),
                    ),
                  );
                }
              },
            ),
          ),
          const Divider(color: Color(0xFF2A2A4A)),
        ],

        // 所持アイテム一覧
        Expanded(
          child: ListView.builder(
            padding: const EdgeInsets.all(12),
            itemCount: allForSlot.length,
            itemBuilder: (context, index) {
              final data = allForSlot[index];
              final owned = ownedItems.firstWhereOrNull(
                (e) => e.equipmentId == data.id,
              );
              final isCurrentlyEquipped =
                  equippedItem?.equipmentId == data.id;

              return Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: _EquipmentCard(
                  data: data,
                  owned: owned,
                  isEquipped: isCurrentlyEquipped,
                  onEquip: owned != null && !isCurrentlyEquipped
                      ? () {
                          gs.equipItem(owned);
                          HapticFeedback.selectionClick();
                        }
                      : null,
                  onUpgrade: owned != null
                      ? () async {
                          await gs.upgradeEquipment(owned);
                        }
                      : null,
                ),
              );
            },
          ),
        ),
      ],
    );
  }
}

class _EquipmentCard extends StatelessWidget {
  final EquipmentData data;
  final OwnedEquipment? owned;
  final bool isEquipped;
  final VoidCallback? onEquip;
  final VoidCallback? onUpgrade;

  const _EquipmentCard({
    required this.data,
    required this.owned,
    required this.isEquipped,
    this.onEquip,
    this.onUpgrade,
  });

  @override
  Widget build(BuildContext context) {
    final gs = context.read<GameStateNotifier>();
    final borderColor =
        isEquipped ? const Color(0xFFFFD700) : const Color(0xFF2A2A4A);
    final level = owned?.level ?? 0;
    final canAffordUpgrade = _canAffordUpgrade(gs.player);

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF12121E),
        border: Border.all(color: borderColor, width: isEquipped ? 2 : 1),
        borderRadius: BorderRadius.circular(8),
        boxShadow: isEquipped
            ? [BoxShadow(color: borderColor.withOpacity(0.3), blurRadius: 10)]
            : null,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              // 装備名
              Expanded(
                child: Row(
                  children: [
                    if (isEquipped)
                      const Icon(Icons.shield, color: Color(0xFFFFD700), size: 14),
                    if (isEquipped) const SizedBox(width: 4),
                    Flexible(
                      child: Text(
                        data.name,
                        style: TextStyle(
                          color: isEquipped
                              ? const Color(0xFFFFD700)
                              : Colors.white,
                          fontFamily: 'DotGothic16',
                          fontSize: 15,
                        ),
                      ),
                    ),
                  ],
                ),
              ),

              // レベル表示
              if (owned != null)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: const Color(0xFF4A148C),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    'Lv.$level',
                    style: const TextStyle(
                      color: Colors.white,
                      fontFamily: 'DotGothic16',
                      fontSize: 11,
                    ),
                  ),
                )
              else
                const Text('未所持', style: TextStyle(color: Colors.grey, fontFamily: 'DotGothic16', fontSize: 11)),
            ],
          ),
          const SizedBox(height: 6),

          // 説明
          Text(
            data.description,
            style: TextStyle(
              color: Colors.white.withOpacity(0.6),
              fontFamily: 'DotGothic16',
              fontSize: 12,
            ),
          ),

          // 効果一覧
          const SizedBox(height: 8),
          Wrap(
            spacing: 6,
            runSpacing: 4,
            children: data.effects.map((e) => _EffectChip(effect: e, level: level)).toList(),
          ),

          // ボタン
          if (onEquip != null || onUpgrade != null) ...[
            const SizedBox(height: 10),
            Row(
              children: [
                if (onEquip != null)
                  Expanded(
                    child: ElevatedButton(
                      onPressed: onEquip,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF1565C0),
                        padding: const EdgeInsets.symmetric(vertical: 6),
                      ),
                      child: const Text('装備する', style: TextStyle(fontFamily: 'DotGothic16', fontSize: 12)),
                    ),
                  ),
                if (onEquip != null && onUpgrade != null) const SizedBox(width: 8),
                if (onUpgrade != null && owned != null && owned!.level < data.maxLevel)
                  Expanded(
                    child: OutlinedButton(
                      onPressed: canAffordUpgrade ? onUpgrade : null,
                      style: OutlinedButton.styleFrom(
                        side: BorderSide(
                          color: canAffordUpgrade
                              ? const Color(0xFFFFD700)
                              : Colors.grey.withOpacity(0.3),
                        ),
                        padding: const EdgeInsets.symmetric(vertical: 6),
                      ),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Text(Strings.upgradeBtn,
                              style: TextStyle(fontFamily: 'DotGothic16', fontSize: 11)),
                          Text(
                            _upgradeCostText(gs.player),
                            style: const TextStyle(
                              fontFamily: 'DotGothic16',
                              fontSize: 9,
                              color: Colors.grey,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
              ],
            ),
          ],
        ],
      ),
    );
  }

  bool _canAffordUpgrade(PlayerData player) {
    for (final entry in data.upgradeCost.entries) {
      if ((player.materials[entry.key] ?? 0) < entry.value) return false;
    }
    return true;
  }

  String _upgradeCostText(PlayerData player) {
    if (data.upgradeCost.isEmpty) return '';
    return data.upgradeCost.entries
        .map((e) => '${e.key.replaceAll('mat_', '')} ×${e.value}')
        .join(' / ');
  }
}

class _EffectChip extends StatelessWidget {
  final EquipmentEffect effect;
  final int level;

  const _EffectChip({required this.effect, required this.level});

  @override
  Widget build(BuildContext context) {
    final effectiveValue = effect.value * (level > 0 ? level : 1);
    final valueStr = effect.value < 1
        ? '+${(effectiveValue * 100).round()}%'
        : '+${effectiveValue.round()}';

    Color chipColor;
    switch (effect.type) {
      case EquipmentEffectType.attackBoost:
      case EquipmentEffectType.elementBoost:
        chipColor = const Color(0xFFE65100);
        break;
      case EquipmentEffectType.hpBoost:
      case EquipmentEffectType.wallHpBoost:
        chipColor = const Color(0xFF2E7D32);
        break;
      case EquipmentEffectType.manaRegen:
        chipColor = const Color(0xFF1565C0);
        break;
      case EquipmentEffectType.chainBonus:
        chipColor = const Color(0xFF6A1B9A);
        break;
      default:
        chipColor = const Color(0xFF37474F);
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: chipColor.withOpacity(0.3),
        border: Border.all(color: chipColor.withOpacity(0.6), width: 1),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (effect.element != null) ...[
            Text(effect.element!.emoji, style: const TextStyle(fontSize: 10)),
            const SizedBox(width: 2),
          ],
          Text(
            '$valueStr ${_effectLabel(effect.type)}',
            style: const TextStyle(
              color: Colors.white,
              fontFamily: 'DotGothic16',
              fontSize: 10,
            ),
          ),
        ],
      ),
    );
  }

  String _effectLabel(EquipmentEffectType type) {
    switch (type) {
      case EquipmentEffectType.attackBoost:    return 'ATK';
      case EquipmentEffectType.hpBoost:        return 'HP';
      case EquipmentEffectType.manaRegen:      return 'MANA';
      case EquipmentEffectType.elementBoost:   return 'DMG';
      case EquipmentEffectType.chainBonus:     return 'CHAIN';
      case EquipmentEffectType.wallHpBoost:    return '城壁';
      case EquipmentEffectType.critChance:     return 'CRIT';
      case EquipmentEffectType.dropRateBoost:  return 'DROP';
    }
  }
}

// IterableExtension helper
extension IterableFirstWhereOrNull<T> on Iterable<T> {
  T? firstWhereOrNull(bool Function(T) test) {
    for (final e in this) {
      if (test(e)) return e;
    }
    return null;
  }
}
