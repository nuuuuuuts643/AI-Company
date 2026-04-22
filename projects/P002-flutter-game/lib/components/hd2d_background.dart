import 'dart:math';
import 'package:flame/components.dart';
import 'package:flutter/material.dart';

/// HD-2D風パララックス多層背景コンポーネント
/// スプライトが用意されるまではシンプルな手書き背景で代替
class HD2DBackground extends PositionComponent {
  final String backgroundId;
  final List<_BgLayer> _layers = [];

  // 視差スクロール速度（各レイヤー）
  double _scrollX = 0;

  HD2DBackground({
    required Vector2 size,
    required this.backgroundId,
  }) : super(size: size);

  @override
  Future<void> onLoad() async {
    _buildLayers();
  }

  @override
  void update(double dt) {
    // 背景をゆっくりスクロール（雰囲気演出）
    _scrollX += dt * 10;
  }

  @override
  void render(Canvas canvas) {
    _renderBackground(canvas);
  }

  void _buildLayers() {
    switch (backgroundId) {
      case 'bg_volcano':
        _layers.addAll([
          _BgLayer(color: const Color(0xFF1A0800), depth: 0),   // 遠景: 暗い空
          _BgLayer(color: const Color(0xFF3D0C00), depth: 1),   // 中景: 火山
          _BgLayer(color: const Color(0xFF5C1A00), depth: 2),   // 近景: 溶岩地帯
        ]);
        break;
      case 'bg_sea':
        _layers.addAll([
          _BgLayer(color: const Color(0xFF0A1628), depth: 0),
          _BgLayer(color: const Color(0xFF0D2340), depth: 1),
          _BgLayer(color: const Color(0xFF153354), depth: 2),
        ]);
        break;
      case 'bg_dark_castle':
        _layers.addAll([
          _BgLayer(color: const Color(0xFF050508), depth: 0),
          _BgLayer(color: const Color(0xFF0A0A14), depth: 1),
          _BgLayer(color: const Color(0xFF12121E), depth: 2),
        ]);
        break;
      default: // bg_forest
        _layers.addAll([
          _BgLayer(color: const Color(0xFF0A1A0A), depth: 0),
          _BgLayer(color: const Color(0xFF122412), depth: 1),
          _BgLayer(color: const Color(0xFF1A3A1A), depth: 2),
        ]);
    }
  }

  void _renderBackground(Canvas canvas) {
    if (_layers.isEmpty) return;

    final w = size.x;
    final h = size.y;

    // 最遠景: グラデーション空
    final skyGradient = LinearGradient(
      begin: Alignment.topCenter,
      end: Alignment.bottomCenter,
      colors: [_layers[0].color, _layers[1].color],
    ).createShader(Rect.fromLTWH(0, 0, w, h));
    canvas.drawRect(
      Rect.fromLTWH(0, 0, w, h),
      Paint()..shader = skyGradient,
    );

    // 星（暗い背景時のみ）
    if (backgroundId == 'bg_dark_castle' || backgroundId == 'bg_sea') {
      _renderStars(canvas, w, h);
    }

    // 山シルエット（中景）
    _renderMountains(canvas, w, h);

    // 地面
    _renderGround(canvas, w, h);

    // フィールドライン（レーン境界）
    _renderFieldLines(canvas, w, h);
  }

  void _renderStars(Canvas canvas, double w, double h) {
    final starPaint = Paint()..color = Colors.white.withOpacity(0.6);
    // シードベースの固定星配置
    final rng = Random(42);
    for (int i = 0; i < 40; i++) {
      final x = rng.nextDouble() * w;
      final y = rng.nextDouble() * (h * 0.5);
      final r = 0.8 + rng.nextDouble() * 1.2;
      canvas.drawCircle(Offset(x, y), r, starPaint);
    }
  }

  void _renderMountains(Canvas canvas, double w, double h) {
    final color = _layers.length > 1 ? _layers[1].color : const Color(0xFF1A2A1A);
    final paint = Paint()..color = color.withOpacity(0.8);
    final path = Path();

    // 視差スクロール（奥の山はゆっくり）
    final offset = _scrollX * 0.3 % (w * 2);

    path.moveTo(-offset, h * 0.55);
    for (double x = -offset; x < w + offset + 60; x += 60) {
      path.lineTo(x + 30, h * 0.35 + sin(x / 40) * 30);
      path.lineTo(x + 60, h * 0.55);
    }
    path.lineTo(w + offset, h);
    path.lineTo(-offset, h);
    path.close();
    canvas.drawPath(path, paint);
  }

  void _renderGround(Canvas canvas, double w, double h) {
    final groundColor = _layers.isNotEmpty ? _layers.last.color : const Color(0xFF0A140A);
    final groundGradient = LinearGradient(
      begin: Alignment.topCenter,
      end: Alignment.bottomCenter,
      colors: [groundColor, groundColor.withRed((groundColor.red * 0.7).round())],
    ).createShader(Rect.fromLTWH(0, h * 0.6, w, h * 0.4));
    canvas.drawRect(
      Rect.fromLTWH(0, h * 0.6, w, h * 0.4),
      Paint()..shader = groundGradient,
    );
  }

  void _renderFieldLines(Canvas canvas, double w, double h) {
    // 城壁
    const wallX = 20.0;
    const wallH = 120.0;
    final wallTop = h * 0.5 - wallH / 2;

    canvas.drawRect(
      Rect.fromLTWH(wallX, wallTop, 24, wallH),
      Paint()..color = const Color(0xFF78909C),
    );
    // 城壁の石目
    final stonePaint = Paint()
      ..color = const Color(0xFF546E7A)
      ..strokeWidth = 1;
    for (int i = 0; i < 6; i++) {
      canvas.drawLine(
        Offset(wallX, wallTop + i * 20),
        Offset(wallX + 24, wallTop + i * 20),
        stonePaint,
      );
    }
    // 城壁ハイライト
    canvas.drawRect(
      Rect.fromLTWH(wallX, wallTop, 3, wallH),
      Paint()..color = Colors.white.withOpacity(0.3),
    );
  }
}

class _BgLayer {
  final Color color;
  final int depth;

  _BgLayer({required this.color, required this.depth});
}
