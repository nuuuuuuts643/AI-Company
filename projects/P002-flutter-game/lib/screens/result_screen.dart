import 'dart:math';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../game/game_state.dart';
import '../constants/strings.dart';
import '../services/ad_service.dart';
import 'battle_screen.dart';
import 'stage_select_screen.dart';
import 'main_menu_screen.dart';

/// クリア・ゲームオーバー画面
class ResultScreen extends StatefulWidget {
  const ResultScreen({super.key});

  @override
  State<ResultScreen> createState() => _ResultScreenState();
}

class _ResultScreenState extends State<ResultScreen>
    with TickerProviderStateMixin {
  late AnimationController _entranceController;
  late Animation<double> _scale;
  late Animation<double> _opacity;

  bool _adShown = false;
  late AnimationController _particleCtrl;

  @override
  void initState() {
    super.initState();
    _entranceController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 800),
    );
    _scale = Tween<double>(begin: 0.7, end: 1.0).animate(
      CurvedAnimation(parent: _entranceController, curve: Curves.elasticOut),
    );
    _opacity = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _entranceController, curve: Curves.easeIn),
    );
    _particleCtrl = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 4),
    )..repeat();
    _entranceController.forward();

    // クリア後広告表示（無料版のみ）
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _maybeShowAd();
    });
  }

  @override
  void dispose() {
    _entranceController.dispose();
    _particleCtrl.dispose();
    super.dispose();
  }

  Future<void> _maybeShowAd() async {
    final battle = context.read<GameStateNotifier>().battle;
    if (battle == null) return;
    final isVictory = battle.battlePhase == BattlePhase.victory;

    if (isVictory && !AdService.instance.isAdFree) {
      await AdService.instance.showInterstitial(
        onClosed: () => setState(() => _adShown = true),
      );
    } else {
      setState(() => _adShown = true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final gs = context.watch<GameStateNotifier>();
    final battle = gs.battle;
    final isVictory = battle?.battlePhase == BattlePhase.victory;

    return Scaffold(
      backgroundColor: const Color(0xFF0D0D1A),
      body: Stack(
        children: [
          // 背景グラデーション
          Container(
            decoration: BoxDecoration(
              gradient: RadialGradient(
                center: Alignment.topCenter,
                radius: 1.4,
                colors: isVictory
                    ? [
                        const Color(0xFF1A3A1A).withOpacity(0.8),
                        const Color(0xFF0D0D1A),
                      ]
                    : [
                        const Color(0xFF3A0A0A).withOpacity(0.8),
                        const Color(0xFF0D0D1A),
                      ],
              ),
            ),
          ),

          // 勝利時: パーティクル演出
          if (isVictory)
            Positioned.fill(
              child: AnimatedBuilder(
                animation: _particleCtrl,
                builder: (_, __) => CustomPaint(
                  painter: _ConfettiPainter(_particleCtrl.value),
                ),
              ),
            ),

          SafeArea(
            child: AnimatedBuilder(
              animation: _entranceController,
              builder: (_, child) => Transform.scale(
                scale: _scale.value,
                child: Opacity(opacity: _opacity.value, child: child),
              ),
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(24),
                child: Column(
                  children: [
                    const SizedBox(height: 24),

                    // タイトル
                    Text(
                      isVictory ? Strings.resultClear : Strings.resultGameOver,
                      style: TextStyle(
                        color: isVictory
                            ? const Color(0xFFFFD700)
                            : const Color(0xFFEF5350),
                        fontFamily: 'DotGothic16',
                        fontSize: 32,
                        shadows: [
                          Shadow(
                            color: isVictory
                                ? const Color(0xFFFF8F00)
                                : const Color(0xFFB71C1C),
                            blurRadius: 20,
                          ),
                        ],
                      ),
                    ),

                    // トロフィー / ドクロ
                    const SizedBox(height: 16),
                    Text(
                      isVictory ? '🏆' : '💀',
                      style: const TextStyle(fontSize: 64),
                    ),
                    const SizedBox(height: 24),

                    // スコア
                    if (battle != null) ...[
                      _ResultCard(
                        children: [
                          _ResultRow(
                            label: Strings.resultScore,
                            value: '${battle.score}',
                            highlight: true,
                          ),
                          _ResultRow(
                            label: Strings.resultWave,
                            value: '${battle.currentWave}',
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),

                      // ドロップ素材
                      if (battle.droppedMaterials.isNotEmpty) ...[
                        _ResultCard(
                          title: Strings.resultDrop,
                          children: battle.droppedMaterials.entries
                              .map((e) => _ResultRow(
                                    label: _materialLabel(e.key),
                                    value: '×${e.value}',
                                  ))
                              .toList(),
                        ),
                        const SizedBox(height: 12),
                      ],
                    ],

                    const SizedBox(height: 16),

                    // アクションボタン
                    _ActionButton(
                      label: Strings.btnRetry,
                      color: const Color(0xFF1565C0),
                      icon: Icons.replay,
                      onTap: () => _onRetry(context),
                    ),
                    const SizedBox(height: 10),
                    if (isVictory)
                      _ActionButton(
                        label: Strings.btnNextStage,
                        color: const Color(0xFF4CAF50),
                        icon: Icons.arrow_forward,
                        onTap: () => _onNextStage(context),
                      ),
                    const SizedBox(height: 10),
                    _ActionButton(
                      label: Strings.btnReturnMenu,
                      color: const Color(0xFF37474F),
                      icon: Icons.home,
                      onTap: () => _onReturnMenu(context),
                    ),

                    const SizedBox(height: 32),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  void _onRetry(BuildContext context) {
    final gs = context.read<GameStateNotifier>();
    final stageId = gs.selectedStageId;
    if (stageId == null) {
      _onReturnMenu(context);
      return;
    }
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => const BattleScreen()),
    );
  }

  void _onNextStage(BuildContext context) {
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => const StageSelectScreen()),
    );
  }

  void _onReturnMenu(BuildContext context) {
    context.read<GameStateNotifier>().goToMainMenu();
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => const MainMenuScreen()),
      (route) => false,
    );
  }

  String _materialLabel(String id) {
    const labels = {
      'mat_goblin_fang': 'ゴブリンの牙',
      'mat_orc_hide': 'オークの皮',
      'mat_drake_scale': 'ドレイクの鱗',
      'mat_berserker_axe': 'バーサーカーの斧',
      'mat_serpent_scale': '海蛇の鱗',
      'mat_wraith_essence': '風霊のエッセンス',
      'mat_golem_core': 'ゴーレムのコア',
      'mat_dark_blade': '闇の刃',
      'mat_bat_wing': '影蝙蝠の翼',
      'mat_shaman_staff': 'シャーマンの杖',
      'mat_lich_crown': 'リッチの王冠',
      'mat_shadow_heart': '影の心臓',
      'mat_common': '共通素材',
    };
    return labels[id] ?? id;
  }
}

class _ResultCard extends StatelessWidget {
  final String? title;
  final List<Widget> children;

  const _ResultCard({this.title, required this.children});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFF12121E),
        border: Border.all(color: const Color(0xFF2A2A4A)),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (title != null) ...[
            Text(
              title!,
              style: TextStyle(
                color: Colors.white.withOpacity(0.5),
                fontFamily: 'DotGothic16',
                fontSize: 12,
              ),
            ),
            const SizedBox(height: 8),
          ],
          ...children,
        ],
      ),
    );
  }
}

class _ResultRow extends StatelessWidget {
  final String label;
  final String value;
  final bool highlight;

  const _ResultRow({
    required this.label,
    required this.value,
    this.highlight = false,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: TextStyle(
              color: Colors.white.withOpacity(0.7),
              fontFamily: 'DotGothic16',
              fontSize: 13,
            ),
          ),
          Text(
            value,
            style: TextStyle(
              color: highlight ? const Color(0xFFFFD700) : Colors.white,
              fontFamily: 'DotGothic16',
              fontSize: highlight ? 18 : 13,
              fontWeight: highlight ? FontWeight.bold : FontWeight.normal,
            ),
          ),
        ],
      ),
    );
  }
}

/// 勝利時の紙吹雪パーティクル
class _ConfettiPainter extends CustomPainter {
  final double t;
  static final _rng = Random(42);
  static final _particles = List.generate(40, (i) => _Particle(_rng));

  const _ConfettiPainter(this.t);

  @override
  void paint(Canvas canvas, Size size) {
    for (final p in _particles) {
      final phase = (t + p.offset) % 1.0;
      final x = p.xFrac * size.width + sin(phase * pi * 2 + p.wobble) * 20;
      final y = phase * size.height * 1.2 - size.height * 0.1;

      final paint = Paint()
        ..color = p.color.withOpacity((1.0 - phase * 0.6).clamp(0, 1));

      canvas.save();
      canvas.translate(x, y);
      canvas.rotate(phase * pi * p.spin);
      canvas.drawRect(
        Rect.fromCenter(center: Offset.zero, width: p.size, height: p.size * 0.5),
        paint,
      );
      canvas.restore();
    }
  }

  @override
  bool shouldRepaint(_ConfettiPainter old) => old.t != t;
}

class _Particle {
  final double xFrac;
  final double offset;
  final double wobble;
  final double spin;
  final double size;
  final Color color;

  _Particle(Random rng)
      : xFrac = rng.nextDouble(),
        offset = rng.nextDouble(),
        wobble = rng.nextDouble() * pi * 2,
        spin = rng.nextDouble() * 4 + 1,
        size = rng.nextDouble() * 8 + 5,
        color = _colors[rng.nextInt(_colors.length)];

  static const _colors = [
    Color(0xFFFFD700),
    Color(0xFFFF8F00),
    Color(0xFF4CAF50),
    Color(0xFF2196F3),
    Color(0xFFE91E63),
    Color(0xFF9C27B0),
  ];
}

class _ActionButton extends StatelessWidget {
  final String label;
  final Color color;
  final IconData icon;
  final VoidCallback onTap;

  const _ActionButton({
    required this.label,
    required this.color,
    required this.icon,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      height: 50,
      child: ElevatedButton.icon(
        onPressed: onTap,
        icon: Icon(icon, size: 18),
        label: Text(label, style: const TextStyle(fontFamily: 'DotGothic16', fontSize: 15)),
        style: ElevatedButton.styleFrom(
          backgroundColor: color,
          foregroundColor: Colors.white,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
        ),
      ),
    );
  }
}

