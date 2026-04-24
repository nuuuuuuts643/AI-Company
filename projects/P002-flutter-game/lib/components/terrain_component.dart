import 'dart:math';
import 'package:flame/components.dart';
import 'package:flutter/material.dart';
import '../models/terrain_data.dart';
import '../constants/game_constants.dart';

/// フィールド上の地形を描画するコンポーネント
class TerrainComponent extends PositionComponent {
  final TerrainEntry terrain;

  double _elapsed = 0;

  TerrainComponent({required this.terrain, required Vector2 position})
      : super(
          position: position,
          size: Vector2(GameConstants.laneWidth, 50),
        );

  @override
  void update(double dt) {
    _elapsed += dt;
  }

  @override
  void render(Canvas canvas) {
    final w = size.x;
    final h = size.y;

    // 地形タイプ別の色
    final Color baseColor;
    switch (terrain.type) {
      case TerrainType.mountain:
        baseColor = const Color(0xFF795548);
        break;
      case TerrainType.river:
        baseColor = const Color(0xFF1565C0);
        break;
      case TerrainType.swamp:
        baseColor = const Color(0xFF2E7D32);
        break;
    }

    // 波打つ不透明度アニメ
    final pulse = 0.55 + sin(_elapsed * 2.5) * 0.15;

    // 背景塗り（半透明）
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(2, 2, w - 4, h - 4),
        const Radius.circular(6),
      ),
      Paint()..color = baseColor.withOpacity(pulse * 0.75),
    );

    // 枠線
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(1, 1, w - 2, h - 2),
        const Radius.circular(6),
      ),
      Paint()
        ..color = baseColor.withOpacity(0.9)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2,
    );

    // 絵文字（中央）
    _drawEmoji(canvas, terrain.type.emoji, 24, Offset(w / 2, h / 2 - 4));

    // ラベル
    _drawLabel(canvas, terrain.type.label, Offset(w / 2, h - 9));

    // 残り時間バー（durationありの場合）
    final dur = terrain.remainingDuration;
    final maxDur = terrain.type.defaultDuration;
    if (dur != null && maxDur != null && maxDur > 0) {
      final ratio = (dur / maxDur).clamp(0.0, 1.0);
      canvas.drawRect(
        Rect.fromLTWH(4, h - 4, (w - 8) * ratio, 3),
        Paint()..color = Colors.white.withOpacity(0.6),
      );
    }
  }

  void _drawEmoji(Canvas canvas, String emoji, double fontSize, Offset center) {
    final tp = TextPainter(
      text: TextSpan(text: emoji, style: TextStyle(fontSize: fontSize)),
      textDirection: TextDirection.ltr,
    )..layout();
    tp.paint(canvas, center - Offset(tp.width / 2, tp.height / 2));
  }

  void _drawLabel(Canvas canvas, String text, Offset center) {
    final tp = TextPainter(
      text: TextSpan(
        text: text,
        style: const TextStyle(
          fontSize: 9,
          color: Colors.white,
          fontWeight: FontWeight.bold,
        ),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    tp.paint(canvas, center - Offset(tp.width / 2, tp.height / 2));
  }
}
