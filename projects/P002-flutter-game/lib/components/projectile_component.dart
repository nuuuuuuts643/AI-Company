import 'package:flame/collisions.dart';
import 'package:flame/components.dart';
import 'package:flutter/material.dart';
import '../constants/element_chart.dart';
import '../constants/game_constants.dart';
import 'enemy_component.dart';

/// 矢・魔法弾などの飛翔体コンポーネント
class ProjectileComponent extends PositionComponent with CollisionCallbacks {
  final ElementType element;
  final int damage;
  final int aoeRadius;
  final bool isBouncing;   // 風属性の跳弾
  final EnemyComponent? target; // ホーミング対象（nullなら直線）

  Vector2 _velocity;
  double _elapsed = 0;
  double _maxLifespan;
  bool _hasHit = false;

  // ホーミング用
  int _bounceCount = 0;
  static const int _maxBounces = 2;

  ProjectileComponent({
    required Vector2 position,
    required Vector2 velocity,
    required this.element,
    required this.damage,
    this.aoeRadius = 0,
    this.isBouncing = false,
    this.target,
    double maxLifespan = 2.0,
  })  : _velocity = velocity,
        _maxLifespan = maxLifespan,
        super(position: position, size: Vector2(8, 8));

  @override
  Future<void> onLoad() async {
    add(CircleHitbox(radius: 4));
  }

  @override
  void update(double dt) {
    if (_hasHit) return;
    _elapsed += dt;
    if (_elapsed >= _maxLifespan) {
      removeFromParent();
      return;
    }

    // ホーミング（追尾型）
    if (target != null && target!.isAlive) {
      final dir = (target!.position - position).normalized();
      _velocity = dir * GameConstants.projectileSpeed;
    }

    position += _velocity * dt;

    // 画面外チェック
    if (position.x < -20 || position.x > 420) {
      removeFromParent();
    }
  }

  @override
  void render(Canvas canvas) {
    final color = Color(element.colorValue);
    final progress = _elapsed / _maxLifespan;
    final size = _projectileSize;

    switch (element) {
      case ElementType.fire:
        // 炎弾：橙色の丸 + 尾
        _drawFireball(canvas, color);
        break;
      case ElementType.water:
        // 水弾：青い楕円
        canvas.drawOval(
          Rect.fromCenter(center: Offset.zero, width: size * 1.5, height: size),
          Paint()..color = color,
        );
        break;
      case ElementType.wind:
        // 風弾：緑の螺旋
        _drawWindSpiral(canvas, color);
        break;
      case ElementType.earth:
        // 土弾：茶色い四角
        canvas.drawRect(
          Rect.fromCenter(center: Offset.zero, width: size, height: size),
          Paint()..color = color,
        );
        break;
      case ElementType.light:
        // 光弾：白い星型
        _drawLightBolt(canvas, color);
        break;
      case ElementType.dark:
        // 闇弾：紫のオーブ + ブラックホール効果
        canvas.drawCircle(Offset.zero, size / 2, Paint()..color = color);
        canvas.drawCircle(
          Offset.zero,
          size / 2 + 2,
          Paint()
            ..color = Colors.purple.withOpacity(0.4)
            ..style = PaintingStyle.stroke
            ..strokeWidth = 2,
        );
        break;
    }
  }

  void _drawFireball(Canvas canvas, Color color) {
    // 尾（速度方向と逆に長く）
    final tailEnd = _velocity.normalized() * -12;
    canvas.drawLine(
      Offset.zero,
      Offset(tailEnd.x, tailEnd.y),
      Paint()
        ..color = Colors.orange.withOpacity(0.5)
        ..strokeWidth = 4
        ..strokeCap = StrokeCap.round,
    );
    canvas.drawCircle(Offset.zero, 6, Paint()..color = color);
    canvas.drawCircle(Offset.zero, 3, Paint()..color = Colors.yellow);
  }

  void _drawWindSpiral(Canvas canvas, Color color) {
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2;
    canvas.drawArc(
      Rect.fromCenter(center: Offset.zero, width: 12, height: 12),
      _elapsed * 4,
      3.14,
      false,
      paint,
    );
  }

  void _drawLightBolt(Canvas canvas, Color color) {
    final paint = Paint()..color = color;
    canvas.drawCircle(Offset.zero, 5, paint);
    canvas.drawCircle(Offset.zero, 5, Paint()
      ..color = Colors.white.withOpacity(0.7)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2);
  }

  double get _projectileSize {
    switch (element) {
      case ElementType.earth:
        return 10.0;
      case ElementType.fire:
      case ElementType.dark:
        return 8.0;
      default:
        return 6.0;
    }
  }

  @override
  void onCollisionStart(
      Set<Vector2> intersectionPoints, PositionComponent other) {
    if (_hasHit) return;
    if (other is EnemyComponent && other.isAlive) {
      _hasHit = true;
      other.takeDamage(damage);

      // 跳弾処理（風属性）
      if (isBouncing && _bounceCount < _maxBounces) {
        _bounceCount++;
        _velocity.x = -_velocity.x * 0.7;
        _hasHit = false;
      } else {
        removeFromParent();
      }
    }
  }
}
