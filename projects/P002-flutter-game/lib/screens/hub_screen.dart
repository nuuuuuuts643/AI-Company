import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../game/game_state.dart';
import '../models/card_data.dart';
import '../constants/element_chart.dart';
import '../utils/app_transitions.dart';
import 'stage_select_screen.dart';
import 'equipment_screen.dart';

/// パズドラ風ハブ画面（メインメニュー代替）
/// ボトムナビ: ホーム / 出撃 / 装備 / ランク
class HubScreen extends StatefulWidget {
  const HubScreen({super.key});

  @override
  State<HubScreen> createState() => _HubScreenState();
}

class _HubScreenState extends State<HubScreen>
    with TickerProviderStateMixin {
  int _tab = 0;
  late AnimationController _bgCtrl;

  @override
  void initState() {
    super.initState();
    _bgCtrl = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 8),
    )..repeat();

    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<GameStateNotifier>().initialize();
    });
  }

  @override
  void dispose() {
    _bgCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0D0D1A),
      body: IndexedStack(
        index: _tab,
        children: [
          _HomeTab(bgCtrl: _bgCtrl),
          const _DeckTab(),
          const EquipmentScreen(),
          const _ForgeTab(),
        ],
      ),
      bottomNavigationBar: _buildBottomNav(),
    );
  }

  Widget _buildBottomNav() {
    return Container(
      decoration: const BoxDecoration(
        color: Color(0xFF0A0A18),
        border: Border(top: BorderSide(color: Color(0xFF2A2A4A), width: 1)),
      ),
      child: SafeArea(
        top: false,
        child: Row(
          children: [
            _NavItem(icon: '🏠', label: 'ホーム', selected: _tab == 0,
                onTap: () => setState(() => _tab = 0)),
            _NavItem(icon: '🃏', label: 'デッキ', selected: _tab == 1,
                onTap: () => setState(() => _tab = 1)),
            _NavItem(icon: '⚔️', label: '出撃', selected: false,
                onTap: () {
                  Navigator.of(context).push(
                    AppTransitions.slideRight(const StageSelectScreen()),
                  );
                }),
            _NavItem(icon: '🛡️', label: '装備', selected: _tab == 2,
                onTap: () => setState(() => _tab = 2)),
            _NavItem(icon: '⚒️', label: '鍛冶場', selected: _tab == 3,
                onTap: () => setState(() => _tab = 3)),
          ],
        ),
      ),
    );
  }
}

// ---- ホームタブ ----

class _HomeTab extends StatelessWidget {
  final AnimationController bgCtrl;
  const _HomeTab({required this.bgCtrl});

  @override
  Widget build(BuildContext context) {
    return Consumer<GameStateNotifier>(
      builder: (_, gs, __) {
        final p = gs.player;
        return Stack(
          children: [
            // 背景アニメーション
            AnimatedBuilder(
              animation: bgCtrl,
              builder: (_, __) => CustomPaint(
                size: MediaQuery.of(context).size,
                painter: _HubBgPainter(bgCtrl.value),
              ),
            ),
            SafeArea(
              child: Column(
                children: [
                  // ── トップバー ──
                  _TopBar(player: p),
                  const Spacer(flex: 2),

                  // ── キャラクター表示 ──
                  _CharacterDisplay(),
                  const SizedBox(height: 24),

                  // ── 出撃ボタン ──
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 32),
                    child: _DeployButton(onTap: () {
                      Navigator.of(context).push(
                        AppTransitions.slideRight(const StageSelectScreen()),
                      );
                    }),
                  ),
                  const Spacer(flex: 1),

                  // ── 直近の記録 ──
                  _LastRecord(player: p),
                  const SizedBox(height: 12),
                ],
              ),
            ),
          ],
        );
      },
    );
  }
}

class _TopBar extends StatelessWidget {
  final PlayerData player;
  const _TopBar({required this.player});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.black.withOpacity(0.5),
        border: const Border(
            bottom: BorderSide(color: Color(0xFF2A2A4A), width: 1)),
      ),
      child: Row(
        children: [
          // ランクバッジ
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFFFF8F00), Color(0xFFE65100)],
              ),
              borderRadius: BorderRadius.circular(4),
            ),
            child: Text(
              'Rank ${player.rank}',
              style: const TextStyle(
                color: Colors.white,
                fontFamily: 'DotGothic16',
                fontSize: 12,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
          const SizedBox(width: 8),
          Text(
            player.rankTitle,
            style: TextStyle(
              color: Colors.white.withOpacity(0.7),
              fontFamily: 'DotGothic16',
              fontSize: 11,
            ),
          ),
          const Spacer(),

          // スタミナ
          const Text('❤️', style: TextStyle(fontSize: 14)),
          const SizedBox(width: 4),
          Text(
            '${player.stamina}/${player.maxStamina}',
            style: const TextStyle(
              color: Color(0xFFEF5350),
              fontFamily: 'DotGothic16',
              fontSize: 12,
            ),
          ),
          const SizedBox(width: 12),

          // ゴールド
          const Text('💰', style: TextStyle(fontSize: 14)),
          const SizedBox(width: 4),
          Text(
            '${player.gold}',
            style: const TextStyle(
              color: Color(0xFFFFE082),
              fontFamily: 'DotGothic16',
              fontSize: 12,
            ),
          ),
        ],
      ),
    );
  }
}

class _CharacterDisplay extends StatefulWidget {
  @override
  State<_CharacterDisplay> createState() => _CharacterDisplayState();
}

class _CharacterDisplayState extends State<_CharacterDisplay>
    with SingleTickerProviderStateMixin {
  late AnimationController _glow;

  static const _sprites = [
    'assets/images/unit_fire.png',
    'assets/images/unit_water.png',
    'assets/images/unit_wind.png',
    'assets/images/unit_earth.png',
    'assets/images/unit_light.png',
  ];

  static const _colors = [
    Color(0xFFEF5350),
    Color(0xFF42A5F5),
    Color(0xFF66BB6A),
    Color(0xFFFF8F00),
    Color(0xFFFFE082),
  ];

  @override
  void initState() {
    super.initState();
    _glow = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 3),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _glow.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // ゲームタイトル
        ShaderMask(
          shaderCallback: (bounds) => const LinearGradient(
            colors: [Color(0xFFFFE082), Color(0xFFFF8F00), Color(0xFFEF5350)],
          ).createShader(bounds),
          child: const Text(
            '封印の戦線',
            style: TextStyle(
              color: Colors.white,
              fontFamily: 'DotGothic16',
              fontSize: 28,
              fontWeight: FontWeight.bold,
              letterSpacing: 4,
            ),
          ),
        ),
        const SizedBox(height: 4),
        const Text(
          'SEAL FRONT',
          style: TextStyle(
            color: Colors.white24,
            fontFamily: 'DotGothic16',
            fontSize: 11,
            letterSpacing: 8,
          ),
        ),
        const SizedBox(height: 24),

        // スプライット横一列
        AnimatedBuilder(
          animation: _glow,
          builder: (_, child) {
            return Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: List.generate(_sprites.length, (i) {
                final offset = (i / _sprites.length);
                final t = (_glow.value + offset) % 1.0;
                final glowAmt = (1.0 - (t - 0.5).abs() * 2).clamp(0.0, 1.0);

                return Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  child: _UnitCard(
                    assetPath: _sprites[i],
                    color: _colors[i],
                    glowIntensity: glowAmt,
                  ),
                );
              }),
            );
          },
        ),
      ],
    );
  }
}

class _UnitCard extends StatelessWidget {
  final String assetPath;
  final Color color;
  final double glowIntensity;

  const _UnitCard({
    required this.assetPath,
    required this.color,
    required this.glowIntensity,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 58,
      height: 72,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: color.withOpacity(0.4 + glowIntensity * 0.6),
          width: 1.5,
        ),
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            color.withOpacity(0.15 + glowIntensity * 0.1),
            Colors.black87,
          ],
        ),
        boxShadow: [
          BoxShadow(
            color: color.withOpacity(glowIntensity * 0.5),
            blurRadius: 12,
            spreadRadius: 2,
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(7),
        child: Image.asset(
          assetPath,
          fit: BoxFit.contain,
          errorBuilder: (_, __, ___) => const SizedBox.shrink(),
        ),
      ),
    );
  }
}

class _DeployButton extends StatelessWidget {
  final VoidCallback onTap;
  const _DeployButton({required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        height: 60,
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [Color(0xFFE65100), Color(0xFFBF360C)],
          ),
          borderRadius: BorderRadius.circular(8),
          boxShadow: [
            BoxShadow(
              color: const Color(0xFFE65100).withOpacity(0.5),
              blurRadius: 16,
              spreadRadius: 2,
            ),
          ],
        ),
        child: const Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text('⚔️', style: TextStyle(fontSize: 22)),
            SizedBox(width: 10),
            Text(
              '出撃する',
              style: TextStyle(
                color: Colors.white,
                fontFamily: 'DotGothic16',
                fontSize: 20,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _LastRecord extends StatelessWidget {
  final PlayerData player;
  const _LastRecord({required this.player});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 24),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF12121E).withOpacity(0.8),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFF2A2A4A)),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceAround,
        children: [
          _StatCell(label: 'クリア数', value: '${player.totalClearedCount}'),
          _Divider(),
          _StatCell(
              label: 'ステージ解放',
              value: '${player.unlockedStageIds.length}'),
          _Divider(),
          _StatCell(
              label: 'デッキ枚数',
              value: '${player.deckCardIds.length}'),
        ],
      ),
    );
  }
}

class _StatCell extends StatelessWidget {
  final String label;
  final String value;
  const _StatCell({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(value,
            style: const TextStyle(
                color: Color(0xFF69F0AE),
                fontFamily: 'DotGothic16',
                fontSize: 18,
                fontWeight: FontWeight.bold)),
        const SizedBox(height: 2),
        Text(label,
            style: const TextStyle(
                color: Colors.white54, fontFamily: 'DotGothic16', fontSize: 10)),
      ],
    );
  }
}

class _Divider extends StatelessWidget {
  @override
  Widget build(BuildContext context) =>
      Container(width: 1, height: 36, color: const Color(0xFF2A2A4A));
}

// ---- デッキタブ ----

class _DeckTab extends StatelessWidget {
  const _DeckTab();

  @override
  Widget build(BuildContext context) {
    return Consumer<GameStateNotifier>(
      builder: (_, gs, __) {
        final ids = gs.player.deckCardIds;
        final cards = ids
            .map((id) => CardMaster.getById(id))
            .whereType<CardData>()
            .toList();

        // 属性ごとに集計
        final elemCount = <ElementType, int>{};
        for (final c in cards) {
          elemCount[c.element] = (elemCount[c.element] ?? 0) + 1;
        }

        // ソート: 属性順 → 名前順
        final sorted = List<CardData>.from(cards)
          ..sort((a, b) {
            final ei = a.element.index - b.element.index;
            return ei != 0 ? ei : a.name.compareTo(b.name);
          });

        return Scaffold(
          backgroundColor: const Color(0xFF0D0D1A),
          body: SafeArea(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // ヘッダー
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
                  child: Row(
                    children: [
                      const Text(
                        '🃏 デッキ',
                        style: TextStyle(
                          color: Color(0xFFFFE082),
                          fontFamily: 'DotGothic16',
                          fontSize: 20,
                        ),
                      ),
                      const Spacer(),
                      Text(
                        '${cards.length}枚',
                        style: const TextStyle(
                          color: Colors.white54,
                          fontFamily: 'DotGothic16',
                          fontSize: 14,
                        ),
                      ),
                    ],
                  ),
                ),

                // 属性分布バー
                if (elemCount.isNotEmpty) ...[
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    child: _ElementDistBar(elemCount: elemCount, total: cards.length),
                  ),
                  const SizedBox(height: 12),
                ],

                // カード一覧
                Expanded(
                  child: sorted.isEmpty
                      ? const Center(
                          child: Text(
                            'カードがありません\nステージをクリアすると解放されます',
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              color: Colors.white38,
                              fontFamily: 'DotGothic16',
                              fontSize: 13,
                            ),
                          ),
                        )
                      : ListView.builder(
                          padding: const EdgeInsets.symmetric(horizontal: 12),
                          itemCount: sorted.length,
                          itemBuilder: (_, i) => _DeckCardRow(card: sorted[i]),
                        ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _ElementDistBar extends StatelessWidget {
  final Map<ElementType, int> elemCount;
  final int total;
  const _ElementDistBar({required this.elemCount, required this.total});

  @override
  Widget build(BuildContext context) {
    final entries = elemCount.entries.toList()
      ..sort((a, b) => a.key.index - b.key.index);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          '属性分布',
          style: TextStyle(color: Colors.white38, fontFamily: 'DotGothic16', fontSize: 10),
        ),
        const SizedBox(height: 4),
        // セグメントバー
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: Row(
            children: entries.map((e) {
              return Flexible(
                flex: e.value,
                child: Container(
                  height: 10,
                  color: Color(e.key.colorValue),
                ),
              );
            }).toList(),
          ),
        ),
        const SizedBox(height: 6),
        // 凡例
        Wrap(
          spacing: 10,
          runSpacing: 4,
          children: entries.map((e) {
            return Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 8,
                  height: 8,
                  decoration: BoxDecoration(
                    color: Color(e.key.colorValue),
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
                const SizedBox(width: 4),
                Text(
                  '${e.key.emoji} ${e.value}',
                  style: const TextStyle(
                    color: Colors.white70,
                    fontFamily: 'DotGothic16',
                    fontSize: 10,
                  ),
                ),
              ],
            );
          }).toList(),
        ),
      ],
    );
  }
}

class _DeckCardRow extends StatelessWidget {
  final CardData card;
  const _DeckCardRow({required this.card});

  @override
  Widget build(BuildContext context) {
    final elemColor = Color(card.element.colorValue);
    final typeLabel = card.cardType == CardType.unit
        ? 'UNIT'
        : card.cardType == CardType.spell
            ? 'SPELL'
            : 'TRAP';

    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: const Color(0xFF12121E),
        borderRadius: BorderRadius.circular(6),
        border: Border(left: BorderSide(color: elemColor, width: 3)),
      ),
      child: Row(
        children: [
          Text(card.element.emoji, style: const TextStyle(fontSize: 18)),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  card.name,
                  style: const TextStyle(
                    color: Colors.white,
                    fontFamily: 'DotGothic16',
                    fontSize: 13,
                  ),
                ),
                Text(
                  card.description,
                  style: const TextStyle(
                    color: Colors.white38,
                    fontFamily: 'DotGothic16',
                    fontSize: 10,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          // マナコスト
          Container(
            width: 26,
            height: 26,
            decoration: BoxDecoration(
              color: const Color(0xFF1565C0),
              borderRadius: BorderRadius.circular(13),
            ),
            child: Center(
              child: Text(
                '${card.manaCost}',
                style: const TextStyle(
                  color: Colors.white,
                  fontFamily: 'DotGothic16',
                  fontSize: 12,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ),
          const SizedBox(width: 6),
          // タイプバッジ
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
            decoration: BoxDecoration(
              color: elemColor.withAlpha(40),
              borderRadius: BorderRadius.circular(3),
              border: Border.all(color: elemColor.withAlpha(80)),
            ),
            child: Text(
              typeLabel,
              style: TextStyle(
                color: elemColor,
                fontFamily: 'DotGothic16',
                fontSize: 9,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ---- ランクタブ ----

class _RankTab extends StatelessWidget {
  static const _tiers = [
    (1, '見習い冒険者', '🌱'),
    (5, '冒険者', '⚔️'),
    (10, '勇者', '🗡️'),
    (20, '英雄', '👑'),
    (35, '伝説の英雄', '🌟'),
  ];

  @override
  Widget build(BuildContext context) {
    return Consumer<GameStateNotifier>(
      builder: (_, gs, __) {
        final p = gs.player;
        return Scaffold(
          backgroundColor: const Color(0xFF0D0D1A),
          body: SafeArea(
            child: Column(
              children: [
                const Padding(
                  padding: EdgeInsets.all(16),
                  child: Text(
                    'ランク',
                    style: TextStyle(
                        color: Color(0xFFFFE082),
                        fontFamily: 'DotGothic16',
                        fontSize: 20),
                  ),
                ),
                // 現在のランク強調表示
                Container(
                  margin: const EdgeInsets.symmetric(horizontal: 24),
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    color: const Color(0xFF12121E),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: const Color(0xFFFFE082).withOpacity(0.5)),
                  ),
                  child: Row(
                    children: [
                      const Text('👑', style: TextStyle(fontSize: 40)),
                      const SizedBox(width: 16),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Rank ${p.rank}',
                              style: const TextStyle(
                                  color: Color(0xFFFFE082),
                                  fontFamily: 'DotGothic16',
                                  fontSize: 24)),
                          Text(p.rankTitle,
                              style: const TextStyle(
                                  color: Colors.white70,
                                  fontFamily: 'DotGothic16',
                                  fontSize: 14)),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 24),
                // 段位一覧
                Expanded(
                  child: ListView(
                    padding: const EdgeInsets.symmetric(horizontal: 24),
                    children: _tiers.map((t) {
                      final isReached = p.rank >= t.$1;
                      final isCurrent = p.rankTitle == t.$2;
                      return Container(
                        margin: const EdgeInsets.only(bottom: 8),
                        padding: const EdgeInsets.symmetric(
                            horizontal: 16, vertical: 12),
                        decoration: BoxDecoration(
                          color: isCurrent
                              ? const Color(0xFF1A2A1A)
                              : const Color(0xFF12121E),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(
                            color: isCurrent
                                ? const Color(0xFF69F0AE)
                                : isReached
                                    ? const Color(0xFF2A4A2A)
                                    : const Color(0xFF2A2A4A),
                          ),
                        ),
                        child: Row(
                          children: [
                            Text(t.$3,
                                style: const TextStyle(fontSize: 20)),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(t.$2,
                                      style: TextStyle(
                                          color: isReached
                                              ? Colors.white
                                              : Colors.white38,
                                          fontFamily: 'DotGothic16',
                                          fontSize: 14)),
                                  Text('Rank ${t.$1}から',
                                      style: const TextStyle(
                                          color: Colors.white38,
                                          fontFamily: 'DotGothic16',
                                          fontSize: 10)),
                                ],
                              ),
                            ),
                            if (isCurrent)
                              const Text('◀ NOW',
                                  style: TextStyle(
                                      color: Color(0xFF69F0AE),
                                      fontFamily: 'DotGothic16',
                                      fontSize: 11)),
                            if (isReached && !isCurrent)
                              const Text('✓',
                                  style: TextStyle(
                                      color: Color(0xFF69F0AE), fontSize: 16)),
                          ],
                        ),
                      );
                    }).toList(),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

// ---- ナビゲーションアイテム ----

class _NavItem extends StatelessWidget {
  final String icon;
  final String label;
  final bool selected;
  final VoidCallback onTap;

  const _NavItem({
    required this.icon,
    required this.label,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(icon,
                  style: TextStyle(
                      fontSize: selected ? 22 : 18)),
              const SizedBox(height: 2),
              Text(
                label,
                style: TextStyle(
                  color: selected
                      ? const Color(0xFFFFE082)
                      : Colors.white38,
                  fontFamily: 'DotGothic16',
                  fontSize: 10,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ---- 背景パターン ----

class _HubBgPainter extends CustomPainter {
  final double t;
  _HubBgPainter(this.t);

  @override
  void paint(Canvas canvas, Size size) {
    final bg = Paint()
      ..shader = const LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [Color(0xFF050510), Color(0xFF0D0820), Color(0xFF1A0A2E)],
      ).createShader(Rect.fromLTWH(0, 0, size.width, size.height));
    canvas.drawRect(Rect.fromLTWH(0, 0, size.width, size.height), bg);

    // 流れる粒子
    final paint = Paint()..color = Colors.white;
    for (int i = 0; i < 30; i++) {
      final seed = i * 7919;
      final x = (seed % 1000) / 1000 * size.width;
      final baseY = (seed * 3 % 1000) / 1000 * size.height;
      final y = (baseY + t * size.height * 0.2) % size.height;
      final r = 0.5 + (seed % 10) / 10 * 1.5;
      final opacity = 0.2 + (seed % 100) / 100 * 0.4;
      canvas.drawCircle(Offset(x, y), r, paint..color = Colors.white.withOpacity(opacity));
    }
  }

  @override
  bool shouldRepaint(_HubBgPainter old) => old.t != t;
}
