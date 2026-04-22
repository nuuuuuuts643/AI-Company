import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../game/game_state.dart';
import '../constants/strings.dart';
import 'stage_select_screen.dart';
import 'equipment_screen.dart';

/// タイトル画面（HD-2D風アニメーション背景）
class MainMenuScreen extends StatefulWidget {
  const MainMenuScreen({super.key});

  @override
  State<MainMenuScreen> createState() => _MainMenuScreenState();
}

class _MainMenuScreenState extends State<MainMenuScreen>
    with TickerProviderStateMixin {
  late AnimationController _bgController;
  late AnimationController _titleController;
  late Animation<double> _titleScale;
  late Animation<double> _titleOpacity;

  @override
  void initState() {
    super.initState();

    _bgController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 8),
    )..repeat();

    _titleController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    );

    _titleScale = Tween<double>(begin: 0.85, end: 1.0).animate(
      CurvedAnimation(parent: _titleController, curve: Curves.elasticOut),
    );
    _titleOpacity = Tween<double>(begin: 0, end: 1).animate(
      CurvedAnimation(parent: _titleController, curve: Curves.easeIn),
    );

    Future.delayed(const Duration(milliseconds: 200), () {
      if (mounted) _titleController.forward();
    });

    // セーブデータ読み込み
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<GameStateNotifier>().initialize();
    });
  }

  @override
  void dispose() {
    _bgController.dispose();
    _titleController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        children: [
          // ---- アニメーション背景 ----
          AnimatedBuilder(
            animation: _bgController,
            builder: (_, __) => _HD2DMenuBackground(
              animationValue: _bgController.value,
            ),
          ),

          // ---- コンテンツ ----
          SafeArea(
            child: Column(
              children: [
                const Spacer(flex: 2),

                // タイトルロゴ
                ScaleTransition(
                  scale: _titleScale,
                  child: FadeTransition(
                    opacity: _titleOpacity,
                    child: Column(
                      children: [
                        Text(
                          Strings.appTitle,
                          style: const TextStyle(
                            fontSize: 42,
                            color: Color(0xFFFFE082),
                            fontFamily: 'DotGothic16',
                            shadows: [
                              Shadow(
                                color: Color(0xFFFF8F00),
                                blurRadius: 20,
                              ),
                              Shadow(
                                color: Colors.black,
                                blurRadius: 4,
                                offset: Offset(2, 2),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          Strings.appSubtitle,
                          style: TextStyle(
                            fontSize: 14,
                            color: Colors.white.withOpacity(0.7),
                            fontFamily: 'DotGothic16',
                            letterSpacing: 2,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),

                const Spacer(flex: 3),

                // メニューボタン群
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 48),
                  child: Column(
                    children: [
                      _MenuButton(
                        label: Strings.btnNewGame,
                        color: const Color(0xFFE65100),
                        icon: Icons.play_arrow_rounded,
                        onTap: () => _onNewGame(context),
                      ),
                      const SizedBox(height: 12),
                      _MenuButton(
                        label: Strings.btnContinue,
                        color: const Color(0xFF1565C0),
                        icon: Icons.save_rounded,
                        onTap: () => _onContinue(context),
                      ),
                      const SizedBox(height: 12),
                      _MenuButton(
                        label: Strings.btnEquipment,
                        color: const Color(0xFF4A148C),
                        icon: Icons.shield_rounded,
                        onTap: () => _onEquipment(context),
                      ),
                    ],
                  ),
                ),

                const Spacer(flex: 2),

                // バージョン表記
                Padding(
                  padding: const EdgeInsets.only(bottom: 16),
                  child: Text(
                    'ver 0.1.0 — P002 Flutter/Flame',
                    style: TextStyle(
                      color: Colors.white.withOpacity(0.3),
                      fontSize: 10,
                      fontFamily: 'DotGothic16',
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  void _onNewGame(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const StageSelectScreen()),
    );
  }

  void _onContinue(BuildContext context) {
    // セーブデータがあればステージ選択へ
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const StageSelectScreen()),
    );
  }

  void _onEquipment(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const EquipmentScreen()),
    );
  }
}

/// メニュー用のHD-2D風背景（Canvasで手書き）
class _HD2DMenuBackground extends StatelessWidget {
  final double animationValue;

  const _HD2DMenuBackground({required this.animationValue});

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      size: MediaQuery.of(context).size,
      painter: _MenuBgPainter(animValue: animationValue),
    );
  }
}

class _MenuBgPainter extends CustomPainter {
  final double animValue;

  _MenuBgPainter({required this.animValue});

  @override
  void paint(Canvas canvas, Size size) {
    // グラデーション背景
    final bgPaint = Paint()
      ..shader = LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: const [
          Color(0xFF050510),
          Color(0xFF0D0820),
          Color(0xFF1A0A2E),
          Color(0xFF0A1A2E),
        ],
        stops: const [0, 0.3, 0.7, 1.0],
      ).createShader(Rect.fromLTWH(0, 0, size.width, size.height));
    canvas.drawRect(Rect.fromLTWH(0, 0, size.width, size.height), bgPaint);

    // 流れ星（アニメーション）
    _drawShootingStars(canvas, size);

    // 固定星
    _drawStars(canvas, size);

    // 地平線シルエット（城）
    _drawCastleSilhouette(canvas, size);

    // 空気遠近法（下部霞）
    final hazeGradient = LinearGradient(
      begin: Alignment.topCenter,
      end: Alignment.bottomCenter,
      colors: [Colors.transparent, const Color(0xFF0A1A2E).withOpacity(0.6)],
    ).createShader(Rect.fromLTWH(0, size.height * 0.6, size.width, size.height * 0.4));
    canvas.drawRect(
      Rect.fromLTWH(0, size.height * 0.6, size.width, size.height * 0.4),
      Paint()..shader = hazeGradient,
    );
  }

  void _drawStars(Canvas canvas, Size size) {
    final paint = Paint()..color = Colors.white;
    const seed = 12345;
    for (int i = 0; i < 60; i++) {
      final x = ((seed * (i + 1) * 7919) % 1000) / 1000 * size.width;
      final y = ((seed * (i + 1) * 6271) % 1000) / 1000 * size.height * 0.7;
      final r = 0.5 + ((seed * i * 3571) % 100) / 100 * 1.5;
      final flicker = 0.4 + 0.6 * ((1 + _sin(animValue * 6.28 + i.toDouble())) / 2);
      canvas.drawCircle(
        Offset(x, y),
        r,
        paint..color = Colors.white.withOpacity(flicker * 0.9),
      );
    }
  }

  void _drawShootingStars(Canvas canvas, Size size) {
    for (int i = 0; i < 2; i++) {
      final phase = (animValue + i * 0.5) % 1.0;
      if (phase > 0.15) continue; // 短時間だけ表示
      final progress = phase / 0.15;
      final startX = size.width * (0.1 + i * 0.4);
      final startY = size.height * 0.1 * (i + 1);
      final len = 60.0;
      final dx = len * progress;
      final dy = len * progress * 0.4;
      final opacity = (1 - progress).clamp(0.0, 1.0);

      canvas.drawLine(
        Offset(startX + dx, startY + dy),
        Offset(startX + dx - 20, startY + dy - 8),
        Paint()
          ..color = Colors.white.withOpacity(opacity * 0.8)
          ..strokeWidth = 1.5
          ..strokeCap = StrokeCap.round,
      );
    }
  }

  void _drawCastleSilhouette(Canvas canvas, Size size) {
    final paint = Paint()..color = const Color(0xFF0A0A1A);
    final path = Path();
    final baseY = size.height * 0.72;

    // 城壁ベース
    path.moveTo(0, baseY);
    path.lineTo(size.width, baseY);
    path.lineTo(size.width, size.height);
    path.lineTo(0, size.height);
    path.close();
    canvas.drawPath(path, paint);

    // タワー
    void drawTower(double x, double w, double h) {
      canvas.drawRect(Rect.fromLTWH(x, baseY - h, w, h + 5), paint);
      // 銃眼（ぎざぎざ）
      for (double tx = x; tx < x + w; tx += 6) {
        canvas.drawRect(Rect.fromLTWH(tx, baseY - h - 8, 4, 8), paint);
      }
    }

    drawTower(size.width * 0.2, 20, 60);
    drawTower(size.width * 0.5 - 15, 30, 90);
    drawTower(size.width * 0.8, 20, 60);
    drawTower(size.width * 0.35, 12, 40);
    drawTower(size.width * 0.65, 12, 40);

    // 城門
    final gateX = size.width * 0.5 - 16;
    final gatePath = Path()
      ..moveTo(gateX, baseY)
      ..lineTo(gateX, baseY - 30)
      ..arcToPoint(Offset(gateX + 32, baseY - 30),
          radius: const Radius.circular(16))
      ..lineTo(gateX + 32, baseY)
      ..close();
    canvas.drawPath(gatePath, const Paint()..color = Color(0xFF05050F));

    // 窓の光
    final windowGlow = Paint()
      ..color = const Color(0xFFFF8F00).withOpacity(0.3 + _sin(animValue * 6.28) * 0.1);
    canvas.drawCircle(Offset(size.width * 0.5, baseY - 65), 4, windowGlow);
    canvas.drawCircle(Offset(size.width * 0.22, baseY - 45), 3, windowGlow);
    canvas.drawCircle(Offset(size.width * 0.78, baseY - 45), 3, windowGlow);
  }

  double _sin(double x) => (x % (2 * 3.14159)).toDouble() < 3.14159
      ? (x % 3.14159) / 3.14159
      : 1 - (x % 3.14159) / 3.14159;

  @override
  bool shouldRepaint(_MenuBgPainter old) => old.animValue != animValue;
}

/// 共通メニューボタンウィジェット
class _MenuButton extends StatelessWidget {
  final String label;
  final Color color;
  final IconData icon;
  final VoidCallback onTap;

  const _MenuButton({
    required this.label,
    required this.color,
    required this.icon,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        height: 52,
        decoration: BoxDecoration(
          color: color.withOpacity(0.85),
          border: Border.all(color: color, width: 1.5),
          borderRadius: BorderRadius.circular(4),
          boxShadow: [
            BoxShadow(
              color: color.withOpacity(0.4),
              blurRadius: 12,
              spreadRadius: 1,
            ),
          ],
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, color: Colors.white, size: 20),
            const SizedBox(width: 10),
            Text(
              label,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 16,
                fontFamily: 'DotGothic16',
              ),
            ),
          ],
        ),
      ),
    );
  }
}
