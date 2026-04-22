import 'dart:math';

/// ウェーブ間に発生するランダムイベント
/// 「戦略×運」のバランス調整：有利イベント60%・不利40%
enum WaveEventType {
  // ---- ボーナスイベント（有利）----
  rareDrop,         // 次ウェーブの全ドロップがレア確定
  manaOverflow,     // マナ上限+3（このウェーブのみ）
  unitFortify,      // 現在フィールドのユニット全員HP+30%回復
  criticalSurge,    // クリティカル率+20%（次ウェーブのみ）
  chainAmplify,     // チェーン反応倍率+50%（次ウェーブのみ）
  mysteryCard,      // ランダムな強力カードを1枚手札に追加
  elementalBlessing,// 特定属性ダメージ+30%（次ウェーブのみ）

  // ---- ペナルティイベント（不利）----
  fastEnemies,      // 次ウェーブの敵の速度+20%
  extraEnemies,     // 次ウェーブに敵+2体追加
  manaDrain,        // 現在マナが半分に減少
  fogOfWar,         // 次ウェーブで敵HPバーが非表示
  wallDamage,       // 城壁に即時ダメージ10
  cursedDeck,       // 次の3枚ドローが重複カードになる

  // ---- 中立イベント ----
  elementShift,     // 次ウェーブの敵属性がランダムに変わる
  tradeOffer,       // 「マナ-2↔ユニット全回復」の交換提案
}

/// ウェーブ間イベントのデータ
class WaveEvent {
  final WaveEventType type;
  final String title;
  final String description;
  final String emoji;
  final bool isBonus;     // true=有利, false=不利, null=中立
  final bool hasChoice;   // プレイヤーが受け入れ/拒否を選べるか

  const WaveEvent({
    required this.type,
    required this.title,
    required this.description,
    required this.emoji,
    this.isBonus = true,
    this.hasChoice = false,
  });
}

/// ウェーブイベント効果の適用パラメータ
class EventEffect {
  final WaveEventType type;
  double speedMultiplier;      // 敵速度倍率
  int extraEnemyCount;         // 追加敵数
  double critRateBonus;        // クリティカル率追加
  double chainMultBonus;       // チェーン倍率追加ボーナス
  double elementDmgBonus;      // 属性ダメージ追加ボーナス
  bool rareDropGuaranteed;     // レアドロップ確定
  bool hpBarHidden;            // 敵HPバー非表示
  int wallDamageImmediate;     // 城壁即時ダメージ
  String? bonusCardId;         // 手札追加カードID
  double manaOverflow;         // マナ上限追加
  bool acceptedByPlayer;       // プレイヤーが受け入れたか

  EventEffect({
    required this.type,
    this.speedMultiplier = 1.0,
    this.extraEnemyCount = 0,
    this.critRateBonus = 0.0,
    this.chainMultBonus = 0.0,
    this.elementDmgBonus = 0.0,
    this.rareDropGuaranteed = false,
    this.hpBarHidden = false,
    this.wallDamageImmediate = 0,
    this.bonusCardId,
    this.manaOverflow = 0.0,
    this.acceptedByPlayer = true,
  });
}

/// ウェーブ間イベントシステム
class EventSystem {
  final _rng = Random();

  // 現在アクティブなイベント効果（次のウェーブが終わるまで持続）
  EventEffect? _activeEffect;
  EventEffect? get activeEffect => _activeEffect;

  /// ウェーブクリア後にランダムイベントを抽選
  /// 難易度が上がるほど不利イベントが増える
  WaveEvent? rollEvent({required int waveNumber, required int totalWaves}) {
    // 最終ウェーブ前は必ず発動
    final chance = 0.4 + (waveNumber / totalWaves) * 0.4; // 40%〜80%
    if (_rng.nextDouble() > chance) return null;

    // 難易度に応じた有利/不利比率
    final bonusWeight = (0.7 - waveNumber * 0.08).clamp(0.3, 0.7);
    final isBonus = _rng.nextDouble() < bonusWeight;

    if (isBonus) {
      return _rollBonusEvent();
    } else {
      return _rollPenaltyEvent();
    }
  }

  /// イベント効果を適用（プレイヤーが選択結果を返す）
  EventEffect applyEvent(WaveEvent event, {bool playerAccepted = true}) {
    EventEffect effect;
    switch (event.type) {
      // ---- ボーナス ----
      case WaveEventType.rareDrop:
        effect = EventEffect(type: event.type, rareDropGuaranteed: true);
        break;
      case WaveEventType.manaOverflow:
        effect = EventEffect(type: event.type, manaOverflow: 3.0);
        break;
      case WaveEventType.criticalSurge:
        effect = EventEffect(type: event.type, critRateBonus: 0.20);
        break;
      case WaveEventType.chainAmplify:
        effect = EventEffect(type: event.type, chainMultBonus: 0.50);
        break;
      case WaveEventType.elementalBlessing:
        effect = EventEffect(type: event.type, elementDmgBonus: 0.30);
        break;
      case WaveEventType.mysteryCard:
        final cards = _mysteryCards;
        effect = EventEffect(
          type: event.type,
          bonusCardId: cards[_rng.nextInt(cards.length)],
        );
        break;
      case WaveEventType.unitFortify:
        effect = EventEffect(type: event.type); // 適用はBattleSystem側
        break;

      // ---- ペナルティ ----
      case WaveEventType.fastEnemies:
        effect = EventEffect(
          type: event.type,
          speedMultiplier: 1.0 + 0.15 + _rng.nextDouble() * 0.10, // +15〜25%
        );
        break;
      case WaveEventType.extraEnemies:
        effect = EventEffect(
          type: event.type,
          extraEnemyCount: 1 + _rng.nextInt(2), // 1〜2体追加
        );
        break;
      case WaveEventType.manaDrain:
        effect = EventEffect(type: event.type); // 外部でマナ半減処理
        break;
      case WaveEventType.fogOfWar:
        effect = EventEffect(type: event.type, hpBarHidden: true);
        break;
      case WaveEventType.wallDamage:
        final dmg = 8 + _rng.nextInt(7); // 8〜14ダメージ
        effect = EventEffect(type: event.type, wallDamageImmediate: dmg);
        break;
      case WaveEventType.cursedDeck:
        effect = EventEffect(type: event.type); // デッキ処理は手札システム側

        break;

      // ---- 中立 ----
      case WaveEventType.elementShift:
      case WaveEventType.tradeOffer:
        effect = EventEffect(type: event.type, acceptedByPlayer: playerAccepted);
        break;
    }

    _activeEffect = effect;
    return effect;
  }

  /// 現在のアクティブ効果をクリア（ウェーブ終了後）
  void clearEffect() {
    _activeEffect = null;
  }

  // ---- プライベート ----

  WaveEvent _rollBonusEvent() {
    const bonusEvents = [
      WaveEvent(
        type: WaveEventType.rareDrop,
        title: '幸運の兆し',
        description: '次ウェーブの全敵から素材が必ずドロップする！',
        emoji: '🍀',
        isBonus: true,
      ),
      WaveEvent(
        type: WaveEventType.manaOverflow,
        title: 'マナの奔流',
        description: '次ウェーブ中、マナ上限が+3される。',
        emoji: '✨',
        isBonus: true,
      ),
      WaveEvent(
        type: WaveEventType.criticalSurge,
        title: '剣の冴え',
        description: '次ウェーブのクリティカル率+20%！',
        emoji: '⚡',
        isBonus: true,
      ),
      WaveEvent(
        type: WaveEventType.chainAmplify,
        title: '属性の共鳴',
        description: '次ウェーブのチェーン反応倍率+50%！',
        emoji: '🔗',
        isBonus: true,
      ),
      WaveEvent(
        type: WaveEventType.mysteryCard,
        title: '謎の旅人',
        description: '強力なカードを1枚手に入れた！',
        emoji: '🃏',
        isBonus: true,
      ),
      WaveEvent(
        type: WaveEventType.elementalBlessing,
        title: '元素の恩寵',
        description: 'ランダムな属性のダメージが+30%になる！',
        emoji: '🌟',
        isBonus: true,
      ),
      WaveEvent(
        type: WaveEventType.unitFortify,
        title: '英雄の士気',
        description: '全ユニットのHPが30%回復した！',
        emoji: '💚',
        isBonus: true,
      ),
    ];
    return bonusEvents[_rng.nextInt(bonusEvents.length)];
  }

  WaveEvent _rollPenaltyEvent() {
    const penaltyEvents = [
      WaveEvent(
        type: WaveEventType.fastEnemies,
        title: '敵の急進',
        description: '次ウェーブの敵が速くなっている…！',
        emoji: '⚠️',
        isBonus: false,
      ),
      WaveEvent(
        type: WaveEventType.extraEnemies,
        title: '増援部隊',
        description: '次ウェーブに追加の敵が現れる！',
        emoji: '👺',
        isBonus: false,
      ),
      WaveEvent(
        type: WaveEventType.manaDrain,
        title: 'マナ枯渇',
        description: '急激にマナが失われた。現在マナが半分になる。',
        emoji: '💔',
        isBonus: false,
      ),
      WaveEvent(
        type: WaveEventType.fogOfWar,
        title: '濃い霧',
        description: '次ウェーブ中、敵のHPが見えない！',
        emoji: '🌫️',
        isBonus: false,
      ),
      WaveEvent(
        type: WaveEventType.wallDamage,
        title: '崩壊の予兆',
        description: '城壁の一部が崩れた！城壁にダメージ。',
        emoji: '💥',
        isBonus: false,
      ),
      WaveEvent(
        type: WaveEventType.tradeOffer,
        title: '悪魔の取引',
        description: 'マナ-2と引き換えに全ユニットが完全回復する。受け入れるか？',
        emoji: '😈',
        isBonus: false,
        hasChoice: true,
      ),
    ];
    return penaltyEvents[_rng.nextInt(penaltyEvents.length)];
  }

  static const List<String> _mysteryCards = [
    'spell_dark_void',
    'unit_necromancer_dark',
    'spell_holy_light',
    'unit_bomber_fire',
    'unit_druid_wind',
    'spell_tornado',
  ];
}
