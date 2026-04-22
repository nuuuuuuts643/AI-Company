import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../constants/element_chart.dart';
import '../constants/strings.dart';
import '../game/game_state.dart';
import '../models/card_data.dart';

/// バトル画面下部のカード手札UI
/// ドラッグ&ドロップでフィールドにカードを配置する
class CardHandWidget extends StatefulWidget {
  final void Function(String cardId, Offset dropOffset) onCardDropped;

  const CardHandWidget({super.key, required this.onCardDropped});

  @override
  State<CardHandWidget> createState() => _CardHandWidgetState();
}

class _CardHandWidgetState extends State<CardHandWidget> {
  String? _draggingCardId;
  Offset? _dragOffset;

  @override
  Widget build(BuildContext context) {
    final battle = context.watch<GameStateNotifier>().battle;
    if (battle == null) return const SizedBox.shrink();

    final cards = battle.handCardIds
        .map((id) => CardMaster.getById(id))
        .whereType<CardData>()
        .toList();

    return Container(
      height: 140,
      decoration: BoxDecoration(
        color: const Color(0xFF0A0A18).withOpacity(0.95),
        border: const Border(
          top: BorderSide(color: Color(0xFF2A2A4A), width: 1.5),
        ),
      ),
      child: Column(
        children: [
          // マナバー
          _ManaBar(),
          const SizedBox(height: 4),

          // カード一覧
          Expanded(
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              itemCount: cards.length,
              itemBuilder: (context, index) {
                final card = cards[index];
                final isPlayable = battle.mana >= card.manaCost;
                return Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 3),
                  child: _DraggableCard(
                    card: card,
                    isPlayable: isPlayable,
                    onDrop: (offset) {
                      widget.onCardDropped(card.id, offset);
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

/// ドラッグ可能なカードウィジェット
class _DraggableCard extends StatefulWidget {
  final CardData card;
  final bool isPlayable;
  final void Function(Offset dropOffset) onDrop;

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
  late AnimationController _hoverController;
  late Animation<double> _hoverAnim;
  bool _isDragging = false;

  @override
  void initState() {
    super.initState();
    _hoverController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 200),
    );
    _hoverAnim = Tween<double>(begin: 0, end: -8).animate(
      CurvedAnimation(parent: _hoverController, curve: Curves.easeOut),
    );
  }

  @override
  void dispose() {
    _hoverController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final color = Color(widget.card.element.colorValue);

    return AnimatedBuilder(
      animation: _hoverAnim,
      builder: (_, child) => Transform.translate(
        offset: Offset(0, _hoverAnim.value),
        child: child,
      ),
      child: Draggable<String>(
        data: widget.card.id,
        onDragStarted: () {
          setState(() => _isDragging = true);
          HapticFeedback.lightImpact();
        },
        onDragEnd: (details) {
          setState(() => _isDragging = false);
          if (details.wasAccepted) {
            widget.onDrop(details.offset);
          }
        },
        feedback: _CardView(
          card: widget.card,
          color: color,
          isPlayable: widget.isPlayable,
          isGhost: false,
          scale: 1.15,
        ),
        childWhenDragging: Opacity(
          opacity: 0.3,
          child: _CardView(
            card: widget.card,
            color: color,
            isPlayable: false,
          ),
        ),
        child: GestureDetector(
          onTapDown: (_) => _hoverController.forward(),
          onTapUp: (_) => _hoverController.reverse(),
          onTapCancel: () => _hoverController.reverse(),
          child: _CardView(
            card: widget.card,
            color: color,
            isPlayable: widget.isPlayable,
          ),
        ),
      ),
    );
  }
}

/// カードのビジュアル本体
class _CardView extends StatelessWidget {
  final CardData card;
  final Color color;
  final bool isPlayable;
  final bool isGhost;
  final double scale;

  const _CardView({
    required this.card,
    required this.color,
    required this.isPlayable,
    this.isGhost = false,
    this.scale = 1.0,
  });

  @override
  Widget build(BuildContext context) {
    return Transform.scale(
      scale: scale,
      child: Opacity(
        opacity: isPlayable ? 1.0 : 0.5,
        child: Container(
          width: 68,
          height: 96,
          decoration: BoxDecoration(
            color: const Color(0xFF12121E),
            border: Border.all(
              color: isPlayable ? color : Colors.grey.withOpacity(0.3),
              width: 1.5,
            ),
            borderRadius: BorderRadius.circular(6),
            boxShadow: isPlayable
                ? [BoxShadow(color: color.withOpacity(0.3), blurRadius: 8)]
                : null,
          ),
          child: Column(
            children: [
              // カードアート（プレースホルダー）
              Expanded(
                flex: 3,
                child: Container(
                  decoration: BoxDecoration(
                    color: color.withOpacity(0.15),
                    borderRadius: const BorderRadius.vertical(
                      top: Radius.circular(5),
                    ),
                  ),
                  child: Center(
                    child: Text(
                      card.element.emoji,
                      style: const TextStyle(fontSize: 22),
                    ),
                  ),
                ),
              ),

              // カード名
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 2, vertical: 2),
                child: Text(
                  card.name,
                  textAlign: TextAlign.center,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: Colors.white,
                    fontFamily: 'DotGothic16',
                    fontSize: 8,
                    height: 1.2,
                  ),
                ),
              ),

              // フッター: コスト + 種別
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
                decoration: BoxDecoration(
                  color: color.withOpacity(0.2),
                  borderRadius: const BorderRadius.vertical(
                    bottom: Radius.circular(5),
                  ),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    // マナコスト
                    Container(
                      width: 18,
                      height: 18,
                      decoration: BoxDecoration(
                        color: const Color(0xFF1565C0),
                        shape: BoxShape.circle,
                        border: Border.all(color: Colors.blue.shade300, width: 1),
                      ),
                      child: Center(
                        child: Text(
                          '${card.manaCost}',
                          style: const TextStyle(
                            color: Colors.white,
                            fontFamily: 'DotGothic16',
                            fontSize: 9,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                    ),

                    // 種別バッジ
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 2),
                      child: Text(
                        _typeShort(card.cardType),
                        style: TextStyle(
                          color: color,
                          fontFamily: 'DotGothic16',
                          fontSize: 8,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _typeShort(CardType type) {
    switch (type) {
      case CardType.unit:  return 'UNT';
      case CardType.spell: return 'SPL';
      case CardType.trap:  return 'TRP';
    }
  }
}

/// マナバーウィジェット
class _ManaBar extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final battle = context.watch<GameStateNotifier>().battle;
    if (battle == null) return const SizedBox.shrink();

    final manaRatio = (battle.mana / battle.maxMana).clamp(0.0, 1.0);
    final manaCount = battle.mana.floor();

    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 6, 12, 0),
      child: Row(
        children: [
          // マナアイコン
          const Text('💎', style: TextStyle(fontSize: 12)),
          const SizedBox(width: 6),
          // マナドット表示（0〜10個）
          Expanded(
            child: Row(
              children: List.generate(10, (i) {
                final filled = i < manaCount;
                final partial = i == manaCount && (battle.mana - manaCount) > 0;
                return Expanded(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 1),
                    child: Container(
                      height: 10,
                      decoration: BoxDecoration(
                        color: filled
                            ? const Color(0xFF1565C0)
                            : partial
                                ? const Color(0xFF1565C0).withOpacity(
                                    battle.mana - manaCount)
                                : const Color(0xFF1A1A2E),
                        borderRadius: BorderRadius.circular(2),
                        border: Border.all(
                          color: const Color(0xFF1565C0).withOpacity(0.5),
                          width: 0.5,
                        ),
                      ),
                    ),
                  ),
                );
              }),
            ),
          ),
          const SizedBox(width: 6),
          Text(
            '${manaCount.toString()}/${battle.maxMana.toInt()}',
            style: const TextStyle(
              color: Color(0xFF64B5F6),
              fontFamily: 'DotGothic16',
              fontSize: 11,
            ),
          ),
        ],
      ),
    );
  }
}
