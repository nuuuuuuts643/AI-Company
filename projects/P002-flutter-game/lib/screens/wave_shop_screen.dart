import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../game/game_state.dart';
import '../systems/shop_system.dart';
import '../constants/element_chart.dart';

/// ウェーブクリア後に自動表示されるショップUI
class WaveShopScreen extends StatefulWidget {
  final int waveNumber;
  final VoidCallback onProceed; // 「次のウェーブへ」or スキップ後に呼ぶ

  const WaveShopScreen({
    super.key,
    required this.waveNumber,
    required this.onProceed,
  });

  @override
  State<WaveShopScreen> createState() => _WaveShopScreenState();
}

class _WaveShopScreenState extends State<WaveShopScreen>
    with SingleTickerProviderStateMixin {
  late final ShopSystem _shop;
  late List<ShopItem> _items;
  late final AnimationController _slideCtrl;
  late final Animation<Offset> _slideAnim;

  // 購入済みID集合
  final Set<String> _purchased = {};

  // フローティングメッセージ
  final List<_FMsg> _msgs = [];

  @override
  void initState() {
    super.initState();
    _shop = ShopSystem();

    // ウェーブクリアゴールドを即計算して付与
    final gs = context.read<GameStateNotifier>();
    final earned = _shop.calcWaveGold(
      waveNumber: widget.waveNumber,
      score: gs.battle?.score ?? 0,
      bonusRate: _shop.sessionBuffs.goldBonusRate,
    );
    gs.addGold(earned);
    _items = _shop.rollShopItems(waveNumber: widget.waveNumber);

    _slideCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 420),
    );
    _slideAnim = Tween<Offset>(begin: const Offset(0, 1.2), end: Offset.zero)
        .animate(CurvedAnimation(parent: _slideCtrl, curve: Curves.easeOutCubic));
    _slideCtrl.forward();
  }

  @override
  void dispose() {
    _slideCtrl.dispose();
    super.dispose();
  }

  // ---- ビルド ----

  @override
  Widget build(BuildContext context) {
    return Consumer<GameStateNotifier>(
      builder: (ctx, gs, _) => SlideTransition(
        position: _slideAnim,
        child: Material(
          color: Colors.transparent,
          child: Container(
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [Color(0xF0050510), Color(0xF5080820)],
              ),
            ),
            child: SafeArea(
              child: Stack(
                children: [
                  Column(
                    children: [
                      _header(gs),
                      const Divider(color: Color(0x22FFFFFF), height: 1),
                      Expanded(child: _itemGrid(gs)),
                      _footer(gs),
                    ],
                  ),
                  ..._msgs.map(_msgWidget),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _header(GameStateNotifier gs) => Padding(
        padding: const EdgeInsets.fromLTRB(14, 10, 14, 8),
        child: Row(
          children: [
            _badge('WAVE ${widget.waveNumber} クリア！', 0xFF1B5E20, 0xFF69F0AE),
            const SizedBox(width: 8),
            const Text(
              'ショップ',
              style: TextStyle(
                  color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const Spacer(),
            _goldBadge(gs.player.gold),
          ],
        ),
      );

  Widget _badge(String t, int bg, int fg) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
        decoration: BoxDecoration(
          color: Color(bg),
          borderRadius: BorderRadius.circular(6),
        ),
        child: Text(t,
            style: TextStyle(
                color: Color(fg), fontSize: 11, fontWeight: FontWeight.bold)),
      );

  Widget _goldBadge(int gold) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
        decoration: BoxDecoration(
          color: const Color(0xFF1A1A2E),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: const Color(0xFFFFD54F), width: 1.5),
        ),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          const Text('🪙', style: TextStyle(fontSize: 14)),
          const SizedBox(width: 4),
          Text('$gold G',
              style: const TextStyle(
                  color: Color(0xFFFFD54F),
                  fontWeight: FontWeight.bold,
                  fontSize: 14)),
        ]),
      );

  Widget _itemGrid(GameStateNotifier gs) => GridView.builder(
        padding: const EdgeInsets.all(10),
        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: 2,
          childAspectRatio: 0.76,
          mainAxisSpacing: 10,
          crossAxisSpacing: 10,
        ),
        itemCount: _items.length,
        itemBuilder: (_, i) {
          final item = _items[i];
          final bought = _purchased.contains(item.id);
          final canAfford = gs.player.gold >= item.cost;
          return _ItemCard(
            item: item,
            isPurchased: bought,
            canAfford: canAfford,
            onTap: bought ? null : () => _buy(item, gs),
          );
        },
      );

  Widget _footer(GameStateNotifier gs) => Padding(
        padding: const EdgeInsets.fromLTRB(14, 6, 14, 14),
        child: Row(children: [
          // 再抽選
          Expanded(
            child: OutlinedButton.icon(
              onPressed: () => _refresh(gs),
              icon: const Icon(Icons.refresh, size: 16),
              label: const Text('再抽選 (20G)', style: TextStyle(fontSize: 12)),
              style: OutlinedButton.styleFrom(
                foregroundColor: const Color(0xFFFFD54F),
                side: const BorderSide(color: Color(0xFFFFD54F)),
                padding: const EdgeInsets.symmetric(vertical: 11),
              ),
            ),
          ),
          const SizedBox(width: 10),
          // スキップ / 次ウェーブ
          Expanded(
            child: ElevatedButton(
              onPressed: widget.onProceed,
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF1565C0),
                padding: const EdgeInsets.symmetric(vertical: 11),
              ),
              child: const Text('次のウェーブへ →',
                  style: TextStyle(fontWeight: FontWeight.bold)),
            ),
          ),
        ]),
      );

  // ---- ハンドラ ----

  void _buy(ShopItem item, GameStateNotifier gs) {
    final success = _shop.purchaseItem(
      item: item,
      currentGold: gs.player.gold,
      onSpend: (spent) => gs.spendGold(spent),
      onWallRepair: (hp) => gs.restoreWallHp(hp),
    );
    if (success) {
      _purchased.add(item.id);
      _push('${item.name} 購入！', const Color(0xFF69F0AE));
    } else {
      _push('ゴールド不足', const Color(0xFFEF5350));
    }
    setState(() {});
  }

  void _refresh(GameStateNotifier gs) {
    if (gs.player.gold < 20) {
      _push('ゴールド不足', const Color(0xFFEF5350));
      return;
    }
    gs.spendGold(20);
    _purchased.clear();
    setState(() {
      _items = _shop.rollShopItems(waveNumber: widget.waveNumber);
    });
    _push('ラインナップ更新！', const Color(0xFFFFE082));
  }

  // ---- FloatingMessage ----

  void _push(String text, Color color) {
    final m = _FMsg(text: text, color: color, id: DateTime.now().microsecondsSinceEpoch);
    setState(() => _msgs.add(m));
    Future.delayed(const Duration(milliseconds: 1200), () {
      if (mounted) setState(() => _msgs.remove(m));
    });
  }

  Widget _msgWidget(_FMsg m) => Positioned(
        top: 110,
        left: 0,
        right: 0,
        child: Center(
          child: _FloatingText(key: ValueKey(m.id), text: m.text, color: m.color),
        ),
      );
}

// ---- ItemCard ----

class _ItemCard extends StatelessWidget {
  final ShopItem item;
  final bool isPurchased;
  final bool canAfford;
  final VoidCallback? onTap;

  const _ItemCard({
    required this.item,
    required this.isPurchased,
    required this.canAfford,
    required this.onTap,
  });

  static const _typeColors = <ShopEffectType, int>{
    ShopEffectType.attackBoost: 0xFFEF5350,
    ShopEffectType.attackSpeedBoost: 0xFFFF7043,
    ShopEffectType.elementBoost: 0xFF42A5F5,
    ShopEffectType.chainChanceBoost: 0xFFCE93D8,
    ShopEffectType.chainMultBoost: 0xFFAB47BC,
    ShopEffectType.manaRegenBoost: 0xFF26C6DA,
    ShopEffectType.wallRepair: 0xFF66BB6A,
    ShopEffectType.maxManaBoost: 0xFF5C6BC0,
    ShopEffectType.critBoost: 0xFFFFCA28,
    ShopEffectType.goldBonus: 0xFFFFD54F,
    ShopEffectType.cardDraw: 0xFF78909C,
    ShopEffectType.waveGoldBonus: 0xFFFFD54F,
  };

  @override
  Widget build(BuildContext context) {
    final borderColor = Color(_typeColors[item.effectType] ?? 0xFF607D8B);
    return GestureDetector(
      onTap: onTap,
      child: AnimatedOpacity(
        opacity: isPurchased ? 0.4 : 1.0,
        duration: const Duration(milliseconds: 250),
        child: Container(
          decoration: BoxDecoration(
            color: const Color(0xFF0D0D1E),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(
              color: isPurchased || \!canAfford ? Colors.white24 : borderColor,
              width: 1.5,
            ),
          ),
          padding: const EdgeInsets.all(10),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Emoji アイコン
              Text(item.emoji, style: const TextStyle(fontSize: 28)),
              const SizedBox(height: 6),
              // 名称
              Text(item.name,
                  style: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.bold,
                      fontSize: 13),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis),
              const SizedBox(height: 4),
              Expanded(
                child: Text(item.description,
                    style: TextStyle(
                        color: Colors.white.withOpacity(0.6), fontSize: 10),
                    maxLines: 3,
                    overflow: TextOverflow.ellipsis),
              ),
              const SizedBox(height: 6),
              // 価格行
              Row(children: [
                const Text('🪙', style: TextStyle(fontSize: 12)),
                const SizedBox(width: 3),
                Text('${item.cost} G',
                    style: TextStyle(
                        color: canAfford && \!isPurchased
                            ? const Color(0xFFFFD54F)
                            : Colors.white38,
                        fontWeight: FontWeight.bold,
                        fontSize: 13)),
                const Spacer(),
                if (isPurchased)
                  const Text('購入済',
                      style: TextStyle(color: Colors.white38, fontSize: 10))
                else if (\!canAfford)
                  const Text('G不足',
                      style: TextStyle(color: Color(0xFFEF5350), fontSize: 10)),
              ]),
            ],
          ),
        ),
      ),
    );
  }
}

// ---- FloatingText ----

class _FMsg {
  final String text;
  final Color color;
  final int id;
  _FMsg({required this.text, required this.color, required this.id});
}

class _FloatingText extends StatefulWidget {
  final String text;
  final Color color;
  const _FloatingText({super.key, required this.text, required this.color});

  @override
  State<_FloatingText> createState() => _FloatingTextState();
}

class _FloatingTextState extends State<_FloatingText>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Animation<double> _opacity;
  late final Animation<Offset> _slide;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: const Duration(milliseconds: 1100));
    _opacity = TweenSequence([
      TweenSequenceItem(tween: Tween(begin: 0.0, end: 1.0), weight: 15),
      TweenSequenceItem(tween: ConstantTween(1.0), weight: 65),
      TweenSequenceItem(tween: Tween(begin: 1.0, end: 0.0), weight: 20),
    ]).animate(_ctrl);
    _slide = Tween<Offset>(begin: const Offset(0, 0.5), end: const Offset(0, -0.3))
        .animate(CurvedAnimation(parent: _ctrl, curve: Curves.easeOut));
    _ctrl.forward();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => SlideTransition(
        position: _slide,
        child: FadeTransition(
          opacity: _opacity,
          child: Text(widget.text,
              style: TextStyle(
                  color: widget.color,
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                  shadows: const [Shadow(blurRadius: 8, color: Colors.black)])),
        ),
      );
}
