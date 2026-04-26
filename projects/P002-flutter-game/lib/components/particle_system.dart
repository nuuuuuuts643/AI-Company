import 'dart:math';
import 'package:flame/components.dart';
import 'package:flutter/material.dart';

/// 汎用バーストパーティクル（爆発・魔法・配置エフェクト）
class BurstParticleComponent extends PositionComponent {
  final Color color;
  final int count;
  final double speed;
  final double lifespan;
  final double radius; // 初期散布半径（0なら中心から）

  final List<_Particle> _particles = [];
  final _rng = Random();
  double _elapsed = 0;
  bool _initialized = false;

  BurstParticleComponent({
    required Vector2 position,
    required this.color,
    required this.count,
    required this.speed,
    required this.lifespan,
    this.radius = 0,
  }) : super(position: position);

  @override
  Future<void> onLoad() async {
    for (int i = 0; i < count; i++) {
      final angle = (_rng.nextDouble() * 2 * pi);
      final spd = speed * (0.5 + _rng.nextDouble() * 0.8);
      final startOffset = radius > 0
          ? Vector2(
              cos(angle) * radius * _rng.nextDouble(),
              sin(angle) * radius * _rng.nextDouble(),
            )
          : Vector2.zero();
      _particles.add(_Particle(
        pos: startOffset,
        vel: Vector2(cos(angle) * spd, sin(angle) * spd),
        size: 3.0 + _rng.nextDouble() * 4.0,
        life: lifespan * (0.6 + _rng.nextDouble() * 0.4),
      ));
    }
    _initialized = true;
  }

  @override
  void update(double dt) {
    _elapsed += dt;
    if (!_initialized) return;

    bool anyAlive = false;
    for (final p in _particles) {
      if (p.elapsed >= p.life) continue;
      p.elapsed += dt;
      // 重力（下方向）
      p.vel.y += 80 * dt;
      // 摩擦
      p.vel.scale(1 - dt * 2.5);
      p.pos.x += p.vel.x * dt;
      p.pos.y += p.vel.y * dt;
      anyAlive = true;
    }

    if (!anyAlive) removeFromParent();
  }

  @override
  void render(Canvas canvas) {
    if (!_initialized) return;
    for (final p in _particles) {
      if (p.elapsed >= p.life) continue;
      final progress = p.elapsed / p.life;
      final opacity = (1.0 - progress).clamp(0.0, 1.0);
      final particleColor = color.withOpacity(opacity * 0.9);
      canvas.drawCircle(
        Offset(p.pos.x, p.pos.y),
        p.size * (1.0 - progress * 0.5),
        Paint()..color = particleColor,
      );
    }
  }
}

/// コイン・ドロップパーティクル（黄金色の輝き）
class CoinParticleComponent extends PositionComponent {
  final int count;
  final List<_CoinParticle> _coins = [];
  final _rng = Random();

  CoinParticleComponent({
    required Vector2 position,
    required this.count,
  }) : super(position: position);

  @override
  Future<void> onLoad() async {
    for (int i = 0; i < count; i++) {
      final angle = -pi / 2 + (_rng.nextDouble() - 0.5) * pi;
      final spd = 60 + _rng.nextDouble() * 60;
      _coins.add(_CoinParticle(
        pos: Vector2.zero(),
        vel: Vector2(cos(angle) * spd, sin(angle) * spd),
        life: 0.8 + _rng.nextDouble() * 0.4,
      ));
    }
  }

  @override
  void update(double dt) {
    bool anyAlive = false;
    for (final c in _coins) {
      if (c.elapsed >= c.life) continue;
      c.elapsed += dt;
      c.vel.y += 200 * dt; // 重力
      c.pos.x += c.vel.x * dt;
      c.pos.y += c.vel.y * dt;
      anyAlive = true;
    }
    if (!anyAlive) removeFromParent();
  }

  @override
  void render(Canvas canvas) {
    for (final c in _coins) {
      if (c.elapsed >= c.life) continue;
      final progress = c.elapsed / c.life;
      final opacity = (1.0 - progress * progress).clamp(0.0, 1.0);
      // 六角形コイン風（小さな黄色い丸で代用）
      canvas.drawCircle(
        Offset(c.pos.x, c.pos.y),
        5.0,
        Paint()..color = Color(0xFFFFD700).withOpacity(opacity),
      );
      // ハイライト
      canvas.drawCircle(
        Offset(c.pos.x - 1, c.pos.y - 1),
        2.0,
        Paint()..color = Colors.white.withOpacity(opacity * 0.6),
      );
    }
  }
}

/// ライトフラッシュ（ボス撃破時の白フラッシュ）
class FlashOverlayComponent extends PositionComponent {
  final Color color;
  double _elapsed = 0;
  final double duration;

  FlashOverlayComponent({
    required Vector2 size,
    this.color = Colors.white,
    this.duration = 0.3,
  }) : super(size: size);

  @override
  void update(double dt) {
    _elapsed += dt;
    if (_elapsed >= duration) removeFromParent();
  }

  @override
  void render(Canvas canvas) {
    final opacity = (1.0 - _elapsed / duration).clamp(0.0, 0.8);
    canvas.drawRect(
      Rect.fromLTWH(0, 0, size.x, size.y),
      Paint()..color = color.withOpacity(opacity),
    );
  }
}

// ---- データクラス ----

class _Particle {
  Vector2 pos;
  Vector2 vel;
  double size;
  double life;
  double elapsed = 0;

  _Particle({
    required this.pos,
    required this.vel,
    required this.size,
    required this.life,
  });
}

class _CoinParticle {
  Vector2 pos;
  Vector2 vel;
  double life;
  double elapsed = 0;

  _CoinParticle({
    required this.pos,
    required this.vel,
    required this.life,
  });
}
