import 'dart:math';
import 'package:flame/components.dart';
import 'package:flutter/material.dart';
import '../constants/element_chart.dart';

/// 近接斬撃エフェクト（剣士・騎士など）
class SlashEffectComponent extends PositionComponent {
  final Color color;
  final double angle; // ラジアン：敵方向
  double _t = 0;
  static const _dur = 0.28;

  SlashEffectComponent({
    required Vector2 position,
    required this.color,
    required this.angle,
  }) : super(position: position, size: Vector2(50, 50));

  @override
  void update(double dt) {
    _t += dt;
    if (_t >= _dur) removeFromParent();
  }

  @override
  void render(Canvas canvas) {
    final progress = (_t / _dur).clamp(0.0, 1.0);
    final alpha = (1.0 - progress);

    canvas.save();
    canvas.translate(25, 25);
    canvas.rotate(angle);

    // 三日月型の斬撃弧
    final arcPaint = Paint()
      ..color = color.withAlpha((alpha * 220).round())
      ..style = PaintingStyle.stroke
      ..strokeWidth = 4.5 - progress * 2
      ..strokeCap = StrokeCap.round;

    final r = 20.0 + progress * 14;
    canvas.drawArc(
      Rect.fromCenter(center: Offset.zero, width: r * 2, height: r * 2),
      -0.8,
      1.6,
      false,
      arcPaint,
    );

    // 中心から伸びる線（速度感）
    canvas.drawLine(
      Offset(-r * 0.3, 0),
      Offset(r * 0.9, 0),
      Paint()
        ..color = Colors.white.withAlpha((alpha * 150).round())
        ..strokeWidth = 2.5
        ..strokeCap = StrokeCap.round,
    );

    // 白いコア
    canvas.drawCircle(
      Offset.zero,
      4 * (1 - progress),
      Paint()..color = Colors.white.withAlpha((alpha * 200).round()),
    );

    canvas.restore();
  }
}

/// 魔法陣エフェクト（詠唱時に足元に展開）
class MagicCircleEffect extends PositionComponent {
  final Color color;
  double _t = 0;
  static const _dur = 0.5;

  MagicCircleEffect({required Vector2 position, required this.color})
      : super(position: position, size: Vector2(50, 50));

  @override
  void update(double dt) {
    _t += dt;
    if (_t >= _dur) removeFromParent();
  }

  @override
  void render(Canvas canvas) {
    final progress = (_t / _dur).clamp(0.0, 1.0);
    final alpha = progress < 0.3 ? progress / 0.3 : (1 - progress) / 0.7;
    final cx = 25.0;
    final cy = 25.0;

    canvas.save();
    canvas.translate(cx, cy);
    canvas.rotate(progress * pi * 2);

    // 外リング
    canvas.drawCircle(
      Offset.zero,
      20 * progress,
      Paint()
        ..color = color.withAlpha((alpha * 160).round())
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2,
    );
    // 内リング（逆回転）
    canvas.rotate(-progress * pi * 4);
    canvas.drawCircle(
      Offset.zero,
      10 * progress,
      Paint()
        ..color = color.withAlpha((alpha * 100).round())
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.5,
    );

    // 六角形の光の線
    if (progress > 0.1) {
      final linePaint = Paint()
        ..color = Colors.white.withAlpha((alpha * 80).round())
        ..strokeWidth = 1;
      for (int i = 0; i < 6; i++) {
        final a = i * pi / 3;
        canvas.drawLine(
          Offset(cos(a) * 5, sin(a) * 5),
          Offset(cos(a) * 18 * progress, sin(a) * 18 * progress),
          linePaint,
        );
      }
    }

    canvas.restore();
  }
}

/// 矢・弾がヒットしたときの衝撃エフェクト
class ImpactEffect extends PositionComponent {
  final Color color;
  final _ImpactStyle style;
  double _t = 0;
  static const _dur = 0.3;

  ImpactEffect({
    required Vector2 position,
    required this.color,
    required this.style,
  }) : super(position: position, size: Vector2(48, 48));

  @override
  void update(double dt) {
    _t += dt;
    if (_t >= _dur) removeFromParent();
  }

  @override
  void render(Canvas canvas) {
    final p = (_t / _dur).clamp(0.0, 1.0);
    final a = (1.0 - p);
    canvas.translate(24, 24);

    switch (style) {
      case _ImpactStyle.fire:
        // 爆発リング
        for (int i = 0; i < 6; i++) {
          final angle = i * pi / 3 + p * pi;
          final r = 8 + p * 18;
          canvas.drawCircle(
            Offset(cos(angle) * r, sin(angle) * r),
            4 * (1 - p) + 1,
            Paint()..color = Colors.orange.withAlpha((a * 200).round()),
          );
        }
        canvas.drawCircle(Offset.zero, 6 * (1 - p) + 2,
            Paint()..color = Colors.yellow.withAlpha((a * 220).round()));
        break;

      case _ImpactStyle.water:
        // 水しぶき楕円
        canvas.drawOval(
          Rect.fromCenter(
              center: Offset.zero,
              width: (10 + p * 30),
              height: (6 + p * 8)),
          Paint()
            ..color = color.withAlpha((a * 160).round())
            ..style = PaintingStyle.stroke
            ..strokeWidth = 2.5,
        );
        break;

      case _ImpactStyle.wind:
        // 螺旋
        final paint = Paint()
          ..color = color.withAlpha((a * 180).round())
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2;
        final path = Path();
        for (double t = 0; t <= 1; t += 0.05) {
          final r2 = t * 20 * p;
          final a2 = t * pi * 4;
          final x = cos(a2) * r2;
          final y = sin(a2) * r2;
          if (t == 0) path.moveTo(x, y); else path.lineTo(x, y);
        }
        canvas.drawPath(path, paint);
        break;

      case _ImpactStyle.earth:
        // 石礫散乱
        for (int i = 0; i < 5; i++) {
          final angle = i * pi * 2 / 5 + 0.3;
          final dist = p * 20;
          canvas.drawRect(
            Rect.fromCenter(
                center: Offset(cos(angle) * dist, sin(angle) * dist),
                width: 5 * (1 - p) + 2,
                height: 5 * (1 - p) + 2),
            Paint()..color = color.withAlpha((a * 200).round()),
          );
        }
        break;

      case _ImpactStyle.light:
        // 光の十字
        final lp = Paint()
          ..color = Colors.white.withAlpha((a * 230).round())
          ..strokeWidth = 3
          ..strokeCap = StrokeCap.round;
        final ext = 6 + p * 18;
        canvas.drawLine(Offset(0, -ext), Offset(0, ext), lp);
        canvas.drawLine(Offset(-ext, 0), Offset(ext, 0), lp);
        canvas.drawCircle(Offset.zero, 5 * (1 - p) + 1,
            Paint()..color = Colors.yellow.withAlpha((a * 220).round()));
        break;

      case _ImpactStyle.dark:
        // 闇の波紋
        canvas.drawCircle(
          Offset.zero,
          4 + p * 20,
          Paint()
            ..color = color.withAlpha((a * 160).round())
            ..style = PaintingStyle.stroke
            ..strokeWidth = 3,
        );
        canvas.drawCircle(Offset.zero, 3 * (1 - p) + 1,
            Paint()..color = Colors.purple.withAlpha((a * 220).round()));
        break;
    }
  }
}

enum _ImpactStyle { fire, water, wind, earth, light, dark }

_ImpactStyle impactStyleFor(ElementType e) {
  switch (e) {
    case ElementType.fire:  return _ImpactStyle.fire;
    case ElementType.water: return _ImpactStyle.water;
    case ElementType.wind:  return _ImpactStyle.wind;
    case ElementType.earth: return _ImpactStyle.earth;
    case ElementType.light: return _ImpactStyle.light;
    case ElementType.dark:  return _ImpactStyle.dark;
  }
}
