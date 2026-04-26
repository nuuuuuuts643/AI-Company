import 'dart:math';
import 'package:flame/components.dart';
import 'package:flutter/material.dart';
import '../constants/game_constants.dart';

/// Octopath Traveler 風 HD-2D 多層背景
/// 1. 空グラデーション
/// 2. ボケ光球（Bokeh）パーティクル
/// 3. 山/廃墟シルエット（視差）
/// 4. 地面グラデーション
class HD2DBackground extends PositionComponent {
  final String backgroundId;
  final _rng = Random(12345);

  double _elapsed = 0;
  late List<_BokehOrb> _bokehs;
  late List<_Star> _stars;

  HD2DBackground({required Vector2 size, required this.backgroundId})
      : super(size: size);

  @override
  Future<void> onLoad() async {
    // ボケ光球を生成
    _bokehs = List.generate(18, (_) => _BokehOrb(_rng, size));
    // 星を固定シードで生成
    _stars = List.generate(55, (_) => _Star(_rng, size));
  }

  @override
  void update(double dt) {
    _elapsed += dt;
    for (final b in _bokehs) {
      b.elapsed += dt;
    }
  }

  @override
  void render(Canvas canvas) {
    final w = size.x;
    final h = size.y;

    _drawSkyGradient(canvas, w, h);
    _drawStars(canvas);
    _drawBokeh(canvas);
    _drawMountainSilhouette(canvas, w, h);
    _drawGroundFog(canvas, w, h);
  }

  void _drawSkyGradient(Canvas canvas, double w, double h) {
    final colors = _skyColors;
    final grad = LinearGradient(
      begin: Alignment.topCenter,
      end: Alignment.bottomCenter,
      colors: colors,
      stops: const [0.0, 0.35, 0.65, 1.0],
    ).createShader(Rect.fromLTWH(0, 0, w, h));

    canvas.drawRect(
      Rect.fromLTWH(0, 0, w, h),
      Paint()..shader = grad,
    );
  }

  void _drawStars(Canvas canvas) {
    final isNight = backgroundId == 'bg_dark_castle' ||
        backgroundId == 'bg_sea' ||
        backgroundId == 'bg_forest';
    if (!isNight) return;

    for (final s in _stars) {
      final twinkle = 0.5 + sin(_elapsed * s.twinkleSpeed + s.phase) * 0.4;
      canvas.drawCircle(
        Offset(s.x, s.y),
        s.radius,
        Paint()..color = Colors.white.withOpacity(twinkle * s.brightness),
      );
    }
  }

  void _drawBokeh(Canvas canvas) {
    for (final b in _bokehs) {
      final pulse = 0.3 + sin(b.elapsed * b.pulseSpeed + b.phase) * 0.25;
      final y = b.baseY + sin(b.elapsed * b.floatSpeed + b.floatPhase) * 20;

      // 外側の大きなぼかし円
      canvas.drawCircle(
        Offset(b.x, y),
        b.radius,
        Paint()
          ..color = b.color.withOpacity(pulse * 0.18)
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 12),
      );
      // 内側の明るい核
      canvas.drawCircle(
        Offset(b.x, y),
        b.radius * 0.3,
        Paint()
          ..color = b.color.withOpacity(pulse * 0.55)
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 3),
      );
    }
  }

  void _drawMountainSilhouette(Canvas canvas, double w, double h) {
    final color = _mountainColor;
    final scrollOffset = _elapsed * 8 % (w * 1.5);

    // 遠景の山（ゆっくり視差）
    _drawMountainLayer(canvas, w, h, color.withOpacity(0.55),
        h * 0.38, scrollOffset * 0.2, 80.0, 32.0);
    // 近景の山（速い視差）
    _drawMountainLayer(canvas, w, h, color.withOpacity(0.75),
        h * 0.48, scrollOffset * 0.4, 55.0, 22.0);
  }

  void _drawMountainLayer(Canvas canvas, double w, double h, Color color,
      double peakY, double offset, double peakW, double variation) {
    final paint = Paint()..color = color;
    final path = Path();
    path.moveTo(0, h);

    double x = -offset % (peakW * 2);
    path.lineTo(x, h * 0.65);

    while (x < w + peakW * 2) {
      final peak = peakY + sin(x / 70.0) * variation;
      path.lineTo(x + peakW * 0.5, peak);
      path.lineTo(x + peakW, h * 0.65);
      x += peakW;
    }
    path.lineTo(w + peakW * 2, h);
    path.close();
    canvas.drawPath(path, paint);
  }

  void _drawGroundFog(Canvas canvas, double w, double h) {
    // フィールドに向かってフォグが立ち込める（大気遠近感）
    final fogGrad = LinearGradient(
      begin: Alignment.topCenter,
      end: Alignment.bottomCenter,
      colors: [
        _fogColor.withOpacity(0.0),
        _fogColor.withOpacity(0.28),
        _fogColor.withOpacity(0.0),
      ],
      stops: const [0.0, 0.35, 1.0],
    ).createShader(Rect.fromLTWH(0, 0, w, GameConstants.fieldTop + 80));

    canvas.drawRect(
      Rect.fromLTWH(0, 0, w, GameConstants.fieldTop + 80),
      Paint()..shader = fogGrad,
    );
  }

  // ---- カラーテーマ ----

  List<Color> get _skyColors {
    switch (backgroundId) {
      case 'bg_volcano':
        return const [Color(0xFF0A0005), Color(0xFF1A0510), Color(0xFF2D0A00), Color(0xFF0E0500)];
      case 'bg_sea':
        return const [Color(0xFF020812), Color(0xFF040E1E), Color(0xFF071428), Color(0xFF040B18)];
      case 'bg_dark_castle':
        return const [Color(0xFF010108), Color(0xFF06060F), Color(0xFF0A0A18), Color(0xFF050510)];
      default: // forest
        return const [Color(0xFF020A04), Color(0xFF050E08), Color(0xFF0A1810), Color(0xFF050C08)];
    }
  }

  Color get _mountainColor {
    switch (backgroundId) {
      case 'bg_volcano':  return const Color(0xFF1A0800);
      case 'bg_sea':      return const Color(0xFF071830);
      case 'bg_dark_castle': return const Color(0xFF080818);
      default:            return const Color(0xFF081408);
    }
  }

  Color get _fogColor {
    switch (backgroundId) {
      case 'bg_volcano':  return const Color(0xFF3D1500);
      case 'bg_sea':      return const Color(0xFF0A2040);
      case 'bg_dark_castle': return const Color(0xFF120D28);
      default:            return const Color(0xFF0D1A0D);
    }
  }
}

// ---- ボケ光球パーティクル ----
class _BokehOrb {
  final double x;
  final double baseY;
  final double radius;
  final Color color;
  final double pulseSpeed;
  final double floatSpeed;
  final double phase;
  final double floatPhase;
  double elapsed;

  static const _palette = [
    Color(0xFFFFB347), Color(0xFF87CEEB), Color(0xFFDDA0DD),
    Color(0xFF98FB98), Color(0xFFFF6B6B), Color(0xFFFFD700),
    Color(0xFF4169E1), Color(0xFFFF69B4),
  ];

  _BokehOrb(Random rng, Vector2 size)
      : x = rng.nextDouble() * size.x,
        baseY = rng.nextDouble() * size.y * 0.55 + 10,
        radius = rng.nextDouble() * 28 + 12,
        color = _palette[rng.nextInt(_palette.length)],
        pulseSpeed = rng.nextDouble() * 0.8 + 0.3,
        floatSpeed = rng.nextDouble() * 0.4 + 0.15,
        phase = rng.nextDouble() * pi * 2,
        floatPhase = rng.nextDouble() * pi * 2,
        elapsed = rng.nextDouble() * 10;
}

class _Star {
  final double x, y, radius, brightness, twinkleSpeed, phase;

  _Star(Random rng, Vector2 size)
      : x = rng.nextDouble() * size.x,
        y = rng.nextDouble() * size.y * 0.45,
        radius = rng.nextDouble() * 1.4 + 0.4,
        brightness = rng.nextDouble() * 0.5 + 0.3,
        twinkleSpeed = rng.nextDouble() * 1.5 + 0.5,
        phase = rng.nextDouble() * pi * 2;
}
