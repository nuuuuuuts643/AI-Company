import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../constants/element_chart.dart';
import '../game/game_state.dart';
import '../models/card_data.dart';
import '../models/terrain_data.dart';

/// バトル画面下部のカード手札UI
class CardHandWidget extends StatelessWidget {
  final void Function(String cardId, Offset dropOffset) onCardDropped;

  const CardHandWidget({super.key, required this.onCardDropped});

  @override
  Widget build(BuildContext context) {
    final gs = context.watch<GameStateNotifier>();
    final battle = gs.battle;
    if (battle == null) return const SizedBox.shrink();

    final cards = battle.handCardIds
        .map((id) => CardMaster.getById(id))
        .whereType<CardData>()
        .toList();

    return Container(
      height: 156,
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Color(0xE6070714), Color(0xFF0A0A1A)],
        ),
        border: Border(
          top: BorderSide(color: Color(0x55FFFFFF), width: 0.5),
        ),
      ),
      child: Column(
        children: [
          _ManaBar(),
          Expanded(
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.fromLTRB(8, 4, 8, 6),
              itemCount: cards.length,
              itemBuilder: (context, i) {
                final card = cards[i];
                final playable = battle.mana >= card.manaCost;
                return Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 3),
                  child: _DraggableCard(
                    card: card,
                    isPlayable: playable,
                    onDrop: (offset) {
                      onCardDropped(card.id, offset);
                      HapticFeedback.mediumImpact();
                    },
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

class _DraggableCard extends StatefulWidget {
  final CardData card;
  final bool isPlayable;
  final void Function(Offset) onDrop;

  const _DraggableCard({
    required this.card,
    required this.isPlayable,
    required this.onDrop,
  });

  @override
  State<_DraggableCard> createState() => _DraggableCardState();
}

class _DraggableCardState extends State<_DraggableCard>
    with SingleTickerProviderStateMixin {
  late AnimationController _lift;
  late Animation<double> _liftAnim;

  @override
  void initState() {
    super.initState();
    _lift = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 150));
    _liftAnim =
        Tween<double>(begin: 0, end: -10).animate(
          CurvedAnimation(parent: _lift, curve: Curves.easeOut));
  }

  @override
  void dispose() {
    _lift.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _liftAnim,
      builder: (_, child) =>
          Transform.translate(offset: Offset(0, _liftAnim.value), child: child),
      child: Draggable<String>(
        data: widget.card.id,
        onDragStarted: () {
          _lift.forward();
          HapticFeedback.lightImpact();
        },
        onDragEnd: (details) {
          _lift.reverse();
          if (details.wasAccepted) widget.onDrop(details.offset);
        },
        feedback: Material(
          color: Colors.transparent,
          child: Transform.scale(
            scale: 1.18,
            child: _CardView(card: widget.card, isPlayable: true),
          ),
        ),
        childWhenDragging: Opacity(
          opacity: 0.25,
          child: _CardView(card: widget.card, isPlayable: false),
        ),
        child: GestureDetector(
          onTapDown: (_) => _lift.forward(),
          onTapUp: (_) => _lift.reverse(),
          onTapCancel: () => _lift.reverse(),
          child: _CardView(card: widget.card, isPlayable: widget.isPlayable),
        ),
      ),
    );
  }
}

class _CardView extends StatelessWidget {
  final CardData card;
  final bool isPlayable;

  const _CardView({required this.card, required this.isPlayable});

  @override
  Widget build(BuildContext context) {
    final elemColor = Color(card.element.colorValue);
    final borderColor = isPlayable ? elemColor : Colors.white24;

    return Opacity(
      opacity: isPlayable ? 1.0 : 0.45,
      child: Container(
        width: 74,
        height: 110,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(9),
          border: Border.all(color: borderColor, width: isPlayable ? 1.8 : 1.0),
          boxShadow: isPlayable
              ? [
                  BoxShadow(
                    color: elemColor.withOpacity(0.45),
                    blurRadius: 10,
                    spreadRadius: 1,
                  )
                ]
              : null,
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              Color.lerp(Colors.black, elemColor, 0.18)!,
              const Color(0xFF0D0D1A),
            ],
          ),
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(8),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // ─── アート部分 ───
              Expanded(
                flex: 58,
                child: Stack(
                  children: [
                    // 背景グラデ
                    Positioned.fill(
                      child: Container(
                        decoration: BoxDecoration(
                          gradient: RadialGradient(
                            center: Alignment.center,
                            radius: 0.9,
                            colors: [
                              elemColor.withOpacity(0.2),
                              Colors.black87,
                            ],
                          ),
                        ),
                      ),
                    ),
                    // スプライット or 絵文字
                    Positioned.fill(
                      child: Padding(
                        padding: const EdgeInsets.all(4),
                        child: _cardArt(),
                      ),
                    ),
                    // 属性アイコン（右上）
                    Positioned(
                      top: 3,
                      right: 3,
                      child: Container(
                        width: 16,
                        height: 16,
                        decoration: BoxDecoration(
                          color: Colors.black54,
                          shape: BoxShape.circle,
                          border: Border.all(color: elemColor, width: 1),
                        ),
                        child: Center(
                          child: Text(
                            card.element.emoji,
                            style: const TextStyle(fontSize: 9),
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),

              // ─── カード名 ───
              Container(
                color: Colors.black54,
                padding: const EdgeInsets.symmetric(horizontal: 3, vertical: 2),
                child: Text(
                  card.name,
                  textAlign: TextAlign.center,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: Colors.white,
                    fontFamily: 'DotGothic16',
                    fontSize: 8.5,
                  ),
                ),
              ),

              // ─── フッター: コスト + ステータス ───
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 3),
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [
                      elemColor.withOpacity(0.35),
                      elemColor.withOpacity(0.15),
                    ],
                  ),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    // マナコスト
                    _ManaCost(cost: card.manaCost, color: elemColor),
                    // ステータス
                    _statLabel(),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _cardArt() {
    if (card.terrainType != null) {
      return Center(
        child: Text(card.terrainType!.emoji, style: const TextStyle(fontSize: 32)),
      );
    }
    if (card.cardType == CardType.unit) {
      final assetPath = _unitAssetPath();
      if (assetPath != null) {
        return Image.asset(
          assetPath,
          fit: BoxFit.contain,
          errorBuilder: (_, __, ___) => _elementFallback(),
        );
      }
    }
    if (card.cardType == CardType.spell) {
      return Stack(
        alignment: Alignment.center,
        children: [
          Text('✨', style: const TextStyle(fontSize: 28)),
          Text(card.element.emoji, style: const TextStyle(fontSize: 16)),
        ],
      );
    }
    return _elementFallback();
  }

  Widget _elementFallback() {
    return Center(
      child: Text(card.element.emoji, style: const TextStyle(fontSize: 28)),
    );
  }

  String? _unitAssetPath() {
    switch (card.element) {
      case ElementType.fire:  return 'assets/images/unit_fire.png';
      case ElementType.water: return 'assets/images/unit_water.png';
      case ElementType.wind:  return 'assets/images/unit_wind.png';
      case ElementType.earth: return 'assets/images/unit_earth.png';
      case ElementType.light: return 'assets/images/unit_light.png';
      case ElementType.dark:  return 'assets/images/unit_dark.png';
    }
  }

  Widget _statLabel() {
    if (card.cardType == CardType.unit && card.baseAttack > 0) {
      return Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Text('⚔', style: TextStyle(fontSize: 8)),
          Text(
            '${card.baseAttack}',
            style: const TextStyle(
              color: Colors.white70,
              fontFamily: 'DotGothic16',
              fontSize: 8,
            ),
          ),
        ],
      );
    }
    if (card.cardType == CardType.spell) {
      return Text(
        'SPL',
        style: TextStyle(
          color: Color(card.element.colorValue),
          fontFamily: 'DotGothic16',
          fontSize: 8,
        ),
      );
    }
    if (card.terrainType != null) {
      return Text(
        card.terrainType!.label,
        style: const TextStyle(
          color: Colors.white54,
          fontFamily: 'DotGothic16',
          fontSize: 7,
        ),
      );
    }
    return const Text('TRP',
        style: TextStyle(
            color: Colors.white38, fontFamily: 'DotGothic16', fontSize: 8));
  }
}

class _ManaCost extends StatelessWidget {
  final int cost;
  final Color color;

  const _ManaCost({required this.cost, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 20,
      height: 20,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: RadialGradient(
          colors: [color.withOpacity(0.9), const Color(0xFF0A1A4A)],
        ),
        border: Border.all(color: color, width: 1.2),
        boxShadow: [BoxShadow(color: color.withOpacity(0.6), blurRadius: 6)],
      ),
      child: Center(
        child: Text(
          '$cost',
          style: const TextStyle(
            color: Colors.white,
            fontFamily: 'DotGothic16',
            fontSize: 10,
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
    );
  }
}

/// マナバー
class _ManaBar extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final battle = context.watch<GameStateNotifier>().battle;
    if (battle == null) return const SizedBox.shrink();

    final mana = battle.mana;
    final max = battle.maxMana;
    final manaInt = mana.floor();

    return Padding(
      padding: const EdgeInsets.fromLTRB(10, 5, 10, 0),
      child: Row(
        children: [
          // マナアイコン
          const Text('💎', style: TextStyle(fontSize: 13)),
          const SizedBox(width: 6),
          // マナドット
          Expanded(
            child: Row(
              children: List.generate(max.toInt(), (i) {
                final filled = i < manaInt;
                final partial = i == manaInt && (mana - manaInt) > 0.05;
                final partialFill = partial ? (mana - manaInt) : 0.0;
                return Expanded(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 1.5),
                    child: Stack(
                      children: [
                        // 背景
                        Container(
                          height: 12,
                          decoration: BoxDecoration(
                            color: const Color(0xFF0D1A30),
                            borderRadius: BorderRadius.circular(3),
                            border: Border.all(
                              color: const Color(0xFF1565C0).withOpacity(0.4),
                              width: 0.5,
                            ),
                          ),
                        ),
                        // フィル
                        if (filled || partial)
                          FractionallySizedBox(
                            widthFactor: filled ? 1.0 : partialFill,
                            child: Container(
                              height: 12,
                              decoration: BoxDecoration(
                                gradient: const LinearGradient(
                                  colors: [Color(0xFF1976D2), Color(0xFF42A5F5)],
                                ),
                                borderRadius: BorderRadius.circular(3),
                                boxShadow: [
                                  BoxShadow(
                                    color: const Color(0xFF2196F3).withOpacity(0.8),
                                    blurRadius: 4,
                                  ),
                                ],
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
                );
              }),
            ),
          ),
          const SizedBox(width: 6),
          Text(
            '${manaInt.toString()}/${max.toInt()}',
            style: const TextStyle(
              color: Color(0xFF64B5F6),
              fontFamily: 'DotGothic16',
              fontSize: 10,
            ),
          ),
        ],
      ),
    );
  }
}
