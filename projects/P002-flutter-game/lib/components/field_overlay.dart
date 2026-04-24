import 'dart:math';
import 'package:flame/components.dart';
import 'package:flutter/material.dart';
import '../constants/game_constants.dart';

/// Octopath Traveler HD-2D フィールドオーバーレイ
/// - 敵ゾーン：消失点へ収束するパースペクティブグリッド + 冷たい青紫ゾーントーン
/// - プレイヤーゾーン：石畳タイル + 温かみのある琥珀色ゾーントーン + 松明グロー
/// - レーン仕切り：魔法の光柱（アニメーション）
/// - 城壁：装飾バトルメント
class FieldOverlayComponent extends PositionComponent {
  double _elapsed = 0;

  static const _vp = Offset(GameConstants.gameWidth / 2, GameConstants.fieldTop - 10);
  static const _fieldTop = GameConstants.fieldTop;
  static const _gridTop = GameConstants.gridTop;
  static const _wallY = GameConstants.wallY;
  static const _laneW = GameConstants.laneWidth;
  static const _gameW = GameConstants.gameWidth;

  FieldOverlayComponent()
      : super(
          position: Vector2.zero(),
          size: Vector2(GameConstants.gameWidth, GameConstants.gameHeight),
        );

  @override
  void update(double dt) {
    _elapsed += dt;
  }

  @override
  void render(Canvas canvas) {
    _drawEnemyZoneTint(canvas);
    _drawPerspectiveGrid(canvas);
    _drawPlayerZone(canvas);
    _drawLaneBarriers(canvas);
    _drawBattlements(canvas);
    _drawZoneBoundaryLine(canvas);
  }

  // ---- 敵ゾーン寒色オーバーレイ ----
  void _drawEnemyZoneTint(Canvas canvas) {
    final grad = const LinearGradient(
      begin: Alignment.topCenter,
      end: Alignment.bottomCenter,
      colors: [
        Color(0x2800153A),
        Color(0x1C1020B0),
        Color(0x00000000),
      ],
      stops: [0.0, 0.7, 1.0],
    ).createShader(Rect.fromLTWH(0, _fieldTop, _gameW, _gridTop - _fieldTop));

    canvas.drawRect(
      Rect.fromLTWH(0, _fieldTop, _gameW, _gridTop - _fieldTop),
      Paint()..shader = grad,
    );
  }

  // ---- パースペクティブグリッド（敵ゾーン） ----
  void _drawPerspectiveGrid(Canvas canvas) {
    final paint = Paint()
      ..color = const Color(0x22A0B8FF)
      ..strokeWidth = 0.8
      ..style = PaintingStyle.stroke;

    // 消失点から底辺へ放射する縦グリッド線
    // 底辺の等間隔ポイントを消失点につなぐ
    const cols = 8;
    for (int i = 0; i <= cols; i++) {
      final bx = _gameW * i / cols;
      canvas.drawLine(
        _vp,
        Offset(bx, _gridTop),
        paint,
      );
    }

    // 水平スキャンライン（遠近法でスペースが小さくなる）
    const rows = 7;
    for (int r = 1; r <= rows; r++) {
      // 0に近いほど消失点に近い→ 間隔を指数的に圧縮
      final t = pow(r / rows, 1.8) as double;
      final y = _fieldTop + (_gridTop - _fieldTop) * t;

      // その高さでの左右幅（消失点からの台形）
      final tLine = (y - _fieldTop) / (_gridTop - _fieldTop);
      final leftX = _lerpX(0, _vp.dx, tLine);
      final rightX = _lerpX(_gameW, _vp.dx, tLine);

      canvas.drawLine(Offset(leftX, y), Offset(rightX, y), paint);
    }
  }

  double _lerpX(double bottom, double top, double t) =>
      bottom + (top - bottom) * (1 - t);

  // ---- プレイヤーゾーン（石畳タイル + 琥珀色ライティング） ----
  void _drawPlayerZone(Canvas canvas) {
    // 温かみのある琥珀グラデーションオーバーレイ
    final grad = const LinearGradient(
      begin: Alignment.topCenter,
      end: Alignment.bottomCenter,
      colors: [
        Color(0x00000000),
        Color(0x18FF8800),
        Color(0x28FF6600),
      ],
      stops: [0.0, 0.5, 1.0],
    ).createShader(Rect.fromLTWH(0, _gridTop, _gameW, _wallY - _gridTop));

    canvas.drawRect(
      Rect.fromLTWH(0, _gridTop, _gameW, _wallY - _gridTop),
      Paint()..shader = grad,
    );

    // 石畳グリッド（横線）
    final tilePaint = Paint()
      ..color = const Color(0x25FFE082)
      ..strokeWidth = 0.7
      ..style = PaintingStyle.stroke;

    for (int r = 0; r <= GameConstants.gridRows; r++) {
      final y = _gridTop + GameConstants.cellHeight * r;
      canvas.drawLine(Offset(0, y), Offset(_gameW, y), tilePaint);
    }

    // 石畳グリッド（縦線）
    const subDivs = 3;
    final subW = _laneW / subDivs;
    for (int col = 0; col < GameConstants.laneCount.toInt(); col++) {
      for (int s = 1; s < subDivs; s++) {
        final x = col * _laneW + subW * s;
        canvas.drawLine(
          Offset(x, _gridTop),
          Offset(x, _wallY),
          Paint()
            ..color = const Color(0x14FFE082)
            ..strokeWidth = 0.5,
        );
      }
    }

    // 左右の松明グロー（サイドライティング）
    _drawTorchGlow(canvas, 0, _gridTop + (_wallY - _gridTop) * 0.3);
    _drawTorchGlow(canvas, _gameW, _gridTop + (_wallY - _gridTop) * 0.3);
  }

  void _drawTorchGlow(Canvas canvas, double x, double y) {
    final flicker = 0.7 + sin(_elapsed * 4.5 + x) * 0.15 + sin(_elapsed * 7.2 + x * 0.1) * 0.08;
    final radius = 80.0 * flicker;

    canvas.drawCircle(
      Offset(x, y),
      radius,
      Paint()
        ..color = const Color(0x18FF7700)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 32),
    );
    // 明るい中心
    canvas.drawCircle(
      Offset(x, y),
      20 * flicker,
      Paint()
        ..color = const Color(0x28FFB300)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 8),
    );
  }

  // ---- 魔法の光柱（レーン仕切り） ----
  void _drawLaneBarriers(Canvas canvas) {
    for (int i = 1; i < GameConstants.laneCount.toInt(); i++) {
      final x = _laneW * i;
      _drawBarrierPillar(canvas, x);
    }
  }

  void _drawBarrierPillar(Canvas canvas, double x) {
    final pulse = 0.5 + sin(_elapsed * 2.1 + x * 0.02) * 0.3;
    final pulse2 = 0.4 + sin(_elapsed * 3.3 + x * 0.015 + 1.0) * 0.25;

    // 敵ゾーン内の縦光柱
    final enemyHeight = _gridTop - _fieldTop;

    // 外側グロー
    canvas.drawRect(
      Rect.fromLTWH(x - 6, _fieldTop, 12, enemyHeight),
      Paint()
        ..color = Color.fromARGB((pulse * 30).round(), 100, 140, 255)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 8),
    );
    // 細い光線本体
    canvas.drawRect(
      Rect.fromLTWH(x - 0.7, _fieldTop, 1.4, enemyHeight),
      Paint()..color = Color.fromARGB((pulse2 * 120).round(), 160, 200, 255),
    );

    // プレイヤーゾーン内も細い区切り
    final playerHeight = _wallY - _gridTop;
    canvas.drawRect(
      Rect.fromLTWH(x - 4, _gridTop, 8, playerHeight),
      Paint()
        ..color = Color.fromARGB((pulse * 20).round(), 255, 200, 80)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 5),
    );
    canvas.drawRect(
      Rect.fromLTWH(x - 0.6, _gridTop, 1.2, playerHeight),
      Paint()..color = Color.fromARGB((pulse2 * 100).round(), 255, 220, 120),
    );

    // 上下の光の核（柱の端）
    for (final gy in [_fieldTop + 2.0, _gridTop - 2.0]) {
      canvas.drawCircle(
        Offset(x, gy),
        4 + pulse * 2,
        Paint()
          ..color = Color.fromARGB((pulse * 180).round(), 140, 180, 255)
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 4),
      );
    }
    // グリッド境界線上の核
    canvas.drawCircle(
      Offset(x, _gridTop),
      3 + pulse2 * 2,
      Paint()
        ..color = Color.fromARGB((pulse2 * 200).round(), 255, 210, 80)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 3),
    );
  }

  // ---- 城壁バトルメント ----
  void _drawBattlements(Canvas canvas) {
    // 城壁ライン本体
    final wallPulse = 0.8 + sin(_elapsed * 1.5) * 0.15;
    canvas.drawRect(
      Rect.fromLTWH(0, _wallY, _gameW, GameConstants.wallHeight),
      Paint()
        ..color = Color.fromARGB((wallPulse * 200).round(), 255, 143, 0),
    );

    // 外グロー
    canvas.drawRect(
      Rect.fromLTWH(0, _wallY - 4, _gameW, GameConstants.wallHeight + 8),
      Paint()
        ..color = Color.fromARGB((wallPulse * 60).round(), 255, 143, 0)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 6),
    );

    // バトルメント（銃眼）歯形
    const merlonW = 18.0;
    const merlonH = 12.0;
    const gap = 10.0;
    const step = merlonW + gap;
    final merlonPaint = Paint()..color = const Color(0xFF1E1810);
    final merlonBorderPaint = Paint()
      ..color = const Color(0xA0FF8F00)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.2;

    double cx = ((_gameW % step) / 2);
    while (cx < _gameW) {
      final rect = Rect.fromLTWH(cx, _wallY - merlonH, merlonW, merlonH);
      canvas.drawRect(rect, merlonPaint);
      canvas.drawRect(rect, merlonBorderPaint);
      cx += step;
    }
  }

  // ---- ゾーン境界ライン ----
  void _drawZoneBoundaryLine(Canvas canvas) {
    final glow = 0.6 + sin(_elapsed * 2.4) * 0.3;

    // 細い輝く境界線
    canvas.drawRect(
      Rect.fromLTWH(0, _gridTop - 1, _gameW, 3),
      Paint()
        ..color = Color.fromARGB((glow * 180).round(), 239, 83, 80)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 4),
    );
    canvas.drawRect(
      Rect.fromLTWH(0, _gridTop - 0.5, _gameW, 1.5),
      Paint()..color = Color.fromARGB((glow * 220).round(), 255, 120, 100),
    );
  }
}
