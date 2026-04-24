import 'dart:math';
import '../game/game_state.dart';

enum BoonRarity { common, rare, epic }

enum BoonEffectType {
  atkBoost,      // 全ユニット攻撃力%
  spdBoost,      // 全ユニット攻撃速度%
  manaRegen,     // マナ回復速度%
  wallRepair,    // 城壁HP回復
  chainMulti,    // チェーン倍率%
  critChance,    // クリティカル率
  hpBoost,       // 全ユニットHP%
  drawCard,      // カード追加ドロー
  commanderCD,   // コマンダースキルCD短縮(秒)
  elemBoost,     // 特定属性ダメージ%
  allUnitPower,  // 全ユニットパワーアップ
  fullWallHeal,  // 城壁全回復
}

class BoonData {
  final String id;
  final String name;
  final String emoji;
  final String description;
  final BoonRarity rarity;
  final BoonEffectType effectType;
  final double value;

  const BoonData({
    required this.id,
    required this.name,
    required this.emoji,
    required this.description,
    required this.rarity,
    required this.effectType,
    required this.value,
  });
}

/// ボーン（ウェーブ間強化）マスターデータ
class BoonMaster {
  static const List<BoonData> all = [
    // -------- コモン --------
    BoonData(
      id: 'boon_atk_sm',
      name: '戦士の誓い',
      emoji: '⚔️',
      description: '全ユニットの攻撃力 +15%',
      rarity: BoonRarity.common,
      effectType: BoonEffectType.atkBoost,
      value: 0.15,
    ),
    BoonData(
      id: 'boon_spd_sm',
      name: '疾風の加護',
      emoji: '💨',
      description: '全ユニットの攻撃速度 +20%',
      rarity: BoonRarity.common,
      effectType: BoonEffectType.spdBoost,
      value: 0.20,
    ),
    BoonData(
      id: 'boon_mana_sm',
      name: 'マナの泉',
      emoji: '💧',
      description: 'マナ回復速度 +30%',
      rarity: BoonRarity.common,
      effectType: BoonEffectType.manaRegen,
      value: 0.30,
    ),
    BoonData(
      id: 'boon_wall_repair',
      name: '城壁修復',
      emoji: '🧱',
      description: '城壁HP +40 回復',
      rarity: BoonRarity.common,
      effectType: BoonEffectType.wallRepair,
      value: 40,
    ),
    BoonData(
      id: 'boon_hp_sm',
      name: '大地の守護',
      emoji: '🛡️',
      description: '全ユニットの最大HP +20%',
      rarity: BoonRarity.common,
      effectType: BoonEffectType.hpBoost,
      value: 0.20,
    ),
    BoonData(
      id: 'boon_crit_sm',
      name: '鷹の眼',
      emoji: '🦅',
      description: 'クリティカル率 +10%',
      rarity: BoonRarity.common,
      effectType: BoonEffectType.critChance,
      value: 0.10,
    ),
    BoonData(
      id: 'boon_atk_md',
      name: '英雄の覚醒',
      emoji: '🔥',
      description: '全ユニットの攻撃力 +25%',
      rarity: BoonRarity.common,
      effectType: BoonEffectType.atkBoost,
      value: 0.25,
    ),
    // -------- レア --------
    BoonData(
      id: 'boon_chain_rare',
      name: 'チェーンマスター',
      emoji: '🔗',
      description: 'チェーン反応ダメージ +50%',
      rarity: BoonRarity.rare,
      effectType: BoonEffectType.chainMulti,
      value: 0.50,
    ),
    BoonData(
      id: 'boon_draw_rare',
      name: '豊穣の手札',
      emoji: '🃏',
      description: '手札に追加カードを2枚引く',
      rarity: BoonRarity.rare,
      effectType: BoonEffectType.drawCard,
      value: 2,
    ),
    BoonData(
      id: 'boon_spd_rare',
      name: '時間加速',
      emoji: '⚡',
      description: '全ユニットの攻撃速度 +40%',
      rarity: BoonRarity.rare,
      effectType: BoonEffectType.spdBoost,
      value: 0.40,
    ),
    BoonData(
      id: 'boon_cmd_cd',
      name: '将の英知',
      emoji: '🎖️',
      description: 'コマンダースキルCD -15秒',
      rarity: BoonRarity.rare,
      effectType: BoonEffectType.commanderCD,
      value: 15,
    ),
    BoonData(
      id: 'boon_fire_boost',
      name: '炎帝の祝福',
      emoji: '🌋',
      description: '火属性ユニットのダメージ +50%',
      rarity: BoonRarity.rare,
      effectType: BoonEffectType.elemBoost,
      value: 0.50,
    ),
    BoonData(
      id: 'boon_chain_rare2',
      name: '共鳴の法則',
      emoji: '✨',
      description: 'チェーン反応ダメージ +80%',
      rarity: BoonRarity.rare,
      effectType: BoonEffectType.chainMulti,
      value: 0.80,
    ),
    BoonData(
      id: 'boon_wall_rare',
      name: '鉄壁の加護',
      emoji: '🏰',
      description: '城壁HP +80 回復',
      rarity: BoonRarity.rare,
      effectType: BoonEffectType.wallRepair,
      value: 80,
    ),
    // -------- エピック --------
    BoonData(
      id: 'boon_power_epic',
      name: '英雄覚醒・全軍',
      emoji: '👑',
      description: '全配置ユニットがパワーアップ！',
      rarity: BoonRarity.epic,
      effectType: BoonEffectType.allUnitPower,
      value: 1,
    ),
    BoonData(
      id: 'boon_wall_full',
      name: '奇跡の再生',
      emoji: '💫',
      description: '城壁HPを完全回復！',
      rarity: BoonRarity.epic,
      effectType: BoonEffectType.fullWallHeal,
      value: 1,
    ),
    BoonData(
      id: 'boon_god_speed',
      name: '神速の令',
      emoji: '🌪️',
      description: '全ユニットの攻撃速度 +80%',
      rarity: BoonRarity.epic,
      effectType: BoonEffectType.spdBoost,
      value: 0.80,
    ),
    BoonData(
      id: 'boon_chain_epic',
      name: '連鎖爆発',
      emoji: '💥',
      description: 'チェーン反応ダメージ +120%！',
      rarity: BoonRarity.epic,
      effectType: BoonEffectType.chainMulti,
      value: 1.20,
    ),
    BoonData(
      id: 'boon_atk_epic',
      name: '破滅の力',
      emoji: '🗡️',
      description: '全ユニットの攻撃力 +50%！',
      rarity: BoonRarity.epic,
      effectType: BoonEffectType.atkBoost,
      value: 0.50,
    ),
  ];
}

/// ボーン選択・適用を管理するシステム
class BoonSystem {
  final _rng = Random();

  // ランごとに蓄積されるボーン効果（乗算適用）
  double atkMultiplier = 1.0;
  double spdMultiplier = 1.0;
  double manaRegenMultiplier = 1.0;
  double chainMultiplier = 1.0;
  double critBonus = 0.0;
  double hpMultiplier = 1.0;
  double commanderCdReduction = 0.0; // 秒

  /// ウェーブ後に3択ボーンをランダム抽出
  List<BoonData> rollBoons({required int waveNumber}) {
    // ウェーブが進むほどレアが出やすい
    final epicChance = (waveNumber - 1) * 0.08;
    final rareChance = 0.25 + (waveNumber - 1) * 0.05;

    final candidates = List<BoonData>.from(BoonMaster.all)..shuffle(_rng);

    final selected = <BoonData>[];
    final usedIds = <String>{};

    // まず1枚を品質ロールで決める
    for (int i = 0; i < 3; i++) {
      final roll = _rng.nextDouble();
      final targetRarity = roll < epicChance
          ? BoonRarity.epic
          : roll < epicChance + rareChance
              ? BoonRarity.rare
              : BoonRarity.common;

      // ターゲット品質から選ぶ。なければ下位品質で補填
      BoonData? pick;
      for (final rarity in [targetRarity, BoonRarity.rare, BoonRarity.common]) {
        pick = candidates.firstWhere(
          (b) => b.rarity == rarity && !usedIds.contains(b.id),
          orElse: () => candidates.first,
        );
        if (!usedIds.contains(pick.id)) break;
      }
      if (pick != null && !usedIds.contains(pick.id)) {
        selected.add(pick);
        usedIds.add(pick.id);
      }
      if (selected.length >= 3) break;
    }

    return selected;
  }

  /// ボーン適用（GameStateNotifierと連携）
  void applyBoon(BoonData boon, GameStateNotifier gs) {
    switch (boon.effectType) {
      case BoonEffectType.atkBoost:
        atkMultiplier += boon.value;
        break;
      case BoonEffectType.spdBoost:
        spdMultiplier += boon.value;
        break;
      case BoonEffectType.manaRegen:
        manaRegenMultiplier += boon.value;
        gs.applyManaRegenBuff(boon.value);
        break;
      case BoonEffectType.wallRepair:
        gs.restoreWallHp(boon.value.round());
        break;
      case BoonEffectType.chainMulti:
        chainMultiplier += boon.value;
        break;
      case BoonEffectType.critChance:
        critBonus += boon.value;
        break;
      case BoonEffectType.hpBoost:
        hpMultiplier += boon.value;
        break;
      case BoonEffectType.drawCard:
        gs.drawBonusCards(boon.value.round());
        break;
      case BoonEffectType.commanderCD:
        commanderCdReduction += boon.value;
        break;
      case BoonEffectType.elemBoost:
        // 火属性ブーストは全体ATKに乗せる（簡略実装）
        atkMultiplier += boon.value * 0.5;
        break;
      case BoonEffectType.allUnitPower:
        gs.powerUpAllUnits();
        break;
      case BoonEffectType.fullWallHeal:
        gs.fullRestoreWall();
        break;
    }
  }
}
