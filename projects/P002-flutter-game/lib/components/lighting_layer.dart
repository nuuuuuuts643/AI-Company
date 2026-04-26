import 'dart:math';
import 'package:flame/components.dart';
import 'package:flutter/material.dart';
import '../constants/element_chart.dart';

/// 光源データ
class LightSource {
  Vector2 position;
  Color color;
  double radius;
  double intensity;
  double _flickerTimer = 0;
  double _flickerOffset = 0;
  final bool flickers; // 松明のような揺らぎ

  LightSource({
    required this.position,
    required this.color,
    required this.radius,
    this.intensity = 0.6,
    this.flickers = false,
  });

  void update(double dt, Random rng) {
    if (flickers) {
      _flickerTimer += dt;
      if (_flickerTimer > 0.05) {
        _flickerOffset = (rng.nextDouble() - 0.5) * 0.15;
        _flickerTimer = 0;
      }
    }
  }

  double get effectiveIntensity => (intensity + _flickerOffset).clamp(0.0, 1.0);
}

/// ライティングオーバーレイ（HD-2D風の光源演出）
/// 乗算ブレンドで暗い領域に光を差し込む
class LightingLayer extends PositionComponent {
  final List<LightSource> _lights = [];
  final _rng = Random();

  // フラッシュエフェクト
  bool _flashActive = false;
  double _flashElapsed = 0;
  double _flashOpacity = 0;
  Color _flashColor = Colors.white;

  LightingLayer({required Vector2 size}) : super(size: size);

  @override
  Future<void> onLoad() async {
    // 固定の松明光源（城壁付近）
    _lights.add(LightSource(
      position: Vector2(40, 420),
      color: const Color(0xFFFF8F00),
      radius: 80,
      intensity: 0.5,
      flickers: true,
    ));
    _lights.add(LightSource(
      position: Vector2(40, 520),
      color: const Color(0xFFFF8F00),
      radius: 80,
      intensity: 0.5,
      flickers: true,
    ));
  }

  @override
  void update(double dt) {
    for (final light in _lights) {
      light.update(dt, _rng);
    }

    // フラッシュ減衰
    if (_flashActive) {
      _flashElapsed += dt;
      _flashOpacity = (1.0 - _flashElapsed / 0.3).clamp(0.0, 0.85);
      if (_flashElapsed >= 0.3) {
        _flashActive = false;
        _flashOpacity = 0;
      }
    }
  }

  @override
  void render(Canvas canvas) {
    // ダークオーバーレイ（画面全体を少し暗くする）
    canvas.drawRect(
      Rect.fromLTWH(0, 0, size.x, size.y),
      Paint()
        ..color = Colors.black.withOpacity(0.35)
        ..blendMode = BlendMode.multiply,
    );

    // 各光源をラジアルグラデーションで描画
    for (final light in _lights) {
      final gradient = RadialGradient(
        colors: [
          light.color.withOpacity(light.effectiveIntensity * 0.5),
          light.color.withOpacity(0),
        ],
      ).createShader(Rect.fromCircle(
        center: Offset(light.position.x, light.position.y),
        radius: light.radius,
      ));
      canvas.drawCircle(
        Offset(light.position.x, light.position.y),
        light.radius,
        Paint()
          ..shader = gradient
          ..blendMode = BlendMode.screen,
      );
    }

    // フラッシュオーバーレイ
    if (_flashActive && _flashOpacity > 0) {
      canvas.drawRect(
        Rect.fromLTWH(0, 0, size.x, size.y),
        Paint()..color = _flashColor.withOpacity(_flashOpacity),
      );
    }
  }

  /// ユニット配置時に一時光源を追加
  void addUnitLight(Vector2 position, ElementType element) {
    final color = Color(element.colorValue);
    final tempLight = LightSource(
      position: position.clone(),
      color: color,
      radius: 50,
      intensity: 0.8,
      flickers: false,
    );
    _lights.add(tempLight);
    // 2秒後に消去（簡易遅延削除）
    Future.delayed(const Duration(seconds: 2), () {
      _lights.remove(tempLight);
    });
  }

  /// ボスオーラ（半永久光源）
  void addBossAura(Vector2 position) {
    _lights.add(LightSource(
      position: position.clone(),
      color: const Color(0xFF9B59B6),
      radius: 120,
      intensity: 0.7,
      flickers: true,
    ));
  }

  /// 白フラッシュ（ボス撃破演出）
  void flashWhite() {
    _flashActive = true;
    _flashElapsed = 0;
    _flashOpacity = 0.85;
    _flashColor = Colors.white;
  }

  /// 属性フラッシュ
  void flashElement(ElementType element) {
    _flashActive = true;
    _flashElapsed = 0;
    _flashOpacity = 0.5;
    _flashColor = Color(element.colorValue);
  }
}
