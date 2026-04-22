import 'dart:math';
import 'package:flame/collisions.dart';
import 'package:flame/components.dart';
import 'package:flutter/material.dart';
import '../models/enemy_data.dart';
import '../constants/element_chart.dart';

/// フィールド上の敵1体を表すFlameコンポーネント
class EnemyComponent extends PositionComponent with CollisionCallbacks {
  final EnemyData enemyData;
  final void Function(EnemyComponent) onDefeated;

  // 動的HP（アーマー含む）
  late int _currentHp;
  int armorHp;
  bool isArmorJustBroken = false;

  // 状態異常
  bool _isFrozen = false;
  double _frozenTimer = 0;
  bool _isBurning = false;
  double _burnTimer = 0;
  double _burnDps = 0;
  double _slowFactor = 1.0;
  double _slowTimer = 0;

  // ノックバック
  double _knockbackDistance = 0;

  // アニメーション
  double _elapsed = 0;
  bool _isDying = false;
  double _dyingTimer = 0;

  final _rng = Random();

  EnemyComponent({
    required this.enemyData,
    required Vector2 position,
    required this.onDefeated,
  })  : armorHp = enemyData.armorHp ?? 0,
        super(position: position, size: Vector2(36, 44));

  @override
  Future<void> onLoad() async {
    _currentHp = enemyData.maxHp;
    add(RectangleHitbox(size: size));
  }

  @override
  void update(double dt) {
    if (_isDying) {
      _dyingTimer += dt;
      if (_dyingTimer >= 0.4) {
        onDefeated(this);
        removeFromParent();
      }
      return;
    }

    _elapsed += dt;

    // 状態異常タイマー
    if (_isFrozen) {
      _frozenTimer -= dt;
      if (_frozenTimer <= 0) _isFrozen = false;
    }
    if (_slowTimer > 0) {
      _slowTimer -= dt;
      if (_slowTimer <= 0) _slowFactor = 1.0;
    }
    if (_isBurning) {
      _burnTimer -= dt;
      if (_burnTimer <= 0) {
        _isBurning = false;
      } else {
        _applyBurnTick(dt);
      }
    }

    if (_isFrozen) return;

    // ノックバック処理
    if (_knockbackDistance > 0) {
      final knock = min(_knockbackDistance, 80.0 * dt);
      position.x += knock;
      _knockbackDistance -= knock;
      return;
    }

    // 移動
    final speed = _effectiveMoveSpeed;
    switch (enemyData.movement) {
      case MovementPattern.straight:
      case MovementPattern.tank:
      case MovementPattern.bossCharge:
        position.x -= speed * dt;
        break;
      case MovementPattern.zigzag:
        position.x -= speed * dt;
        position.y += sin(_elapsed * 3) * 20 * dt;
        break;
      case MovementPattern.rush:
        position.x -= speed * 1.4 * dt;
        break;
      case MovementPattern.flying:
        position.x -= speed * dt;
        position.y += sin(_elapsed * 2) * 12 * dt;
        break;
    }
  }

  @override
  void render(Canvas canvas) {
    if (_isDying) {
      _renderDying(canvas);
      return;
    }

    final bodyColor = _isFrozen
        ? const Color(0xFF90CAF9)
        : _isBurning
            ? Color.lerp(Color(enemyData.element.colorValue), const Color(0xFFFF8F00), 0.5)!
            : Color(enemyData.element.colorValue);

    // ---- スプライトプレースホルダー ----
    // 将来はスプライトシートに差し替え
    if (enemyData.type.isBoss) {
      _renderBossPlaceholder(canvas, bodyColor);
    } else {
      _renderNormalPlaceholder(canvas, bodyColor);
    }

    // アーマー表示
    if (enemyData.hasArmor && armorHp > 0) {
      _renderArmorBar(canvas);
    }

    // HP バー
    _renderHpBar(canvas);

    // 状態異常アイコン
    if (_isFrozen) {
      canvas.drawCircle(
        Offset(size.x / 2, -8),
        5,
        Paint()..color = const Color(0xFF64B5F6),
      );
    }
    if (_isBurning) {
      canvas.drawCircle(
        Offset(size.x / 2, -8),
        5,
        Paint()..color = const Color(0xFFFF8F00),
      );
    }
  }

  void _renderNormalPlaceholder(Canvas canvas, Color color) {
    // ボディ（キャラクターシルエット風の矩形）
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(4, 8, 28, 30),
        const Radius.circular(4),
      ),
      Paint()..color = color,
    );
    // 頭
    canvas.drawCircle(
      Offset(size.x / 2, 8),
      10,
      Paint()..color = color.withRed((color.red * 1.2).clamp(0, 255).round()),
    );
    // ハイライト
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(4, 8, 6, 30),
        const Radius.circular(3),
      ),
      Paint()..color = Colors.white.withOpacity(0.2),
    );
    // 歩行アニメーション（足）
    final walkOffset = sin(_elapsed * 6) * 3;
    canvas.drawRect(
      Rect.fromLTWH(6, 35 + walkOffset, 8, 6),
      Paint()..color = color.withOpacity(0.8),
    );
    canvas.drawRect(
      Rect.fromLTWH(18, 35 - walkOffset, 8, 6),
      Paint()..color = color.withOpacity(0.8),
    );
  }

  void _renderBossPlaceholder(Canvas canvas, Color color) {
    // ボスはひと回り大きく描画
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(-4, 4, 44, 36),
        const Radius.circular(6),
      ),
      Paint()..color = color,
    );
    // 頭（大きめ）
    canvas.drawCircle(
      Offset(size.x / 2, 6),
      14,
      Paint()..color = color.withRed((color.red * 1.3).clamp(0, 255).round()),
    );
    // 目（光る）
    final eyeGlow = 0.5 + sin(_elapsed * 4) * 0.3;
    canvas.drawCircle(
      Offset(size.x / 2 - 6, 4),
      3,
      Paint()..color = Colors.red.withOpacity(eyeGlow),
    );
    canvas.drawCircle(
      Offset(size.x / 2 + 6, 4),
      3,
      Paint()..color = Colors.red.withOpacity(eyeGlow),
    );
    // 影
    canvas.drawOval(
      Rect.fromCenter(center: Offset(size.x / 2, 44), width: 40, height: 8),
      Paint()..color = Colors.black.withOpacity(0.4),
    );
  }

  void _renderDying(Canvas canvas) {
    final opacity = (1.0 - _dyingTimer / 0.4).clamp(0.0, 1.0);
    final scale = 1.0 + _dyingTimer * 2.0;
    canvas.save();
    canvas.translate(size.x / 2, size.y / 2);
    canvas.scale(scale, scale);
    canvas.translate(-size.x / 2, -size.y / 2);
    canvas.drawRect(
      Rect.fromLTWH(0, 0, size.x, size.y),
      Paint()..color = Colors.white.withOpacity(opacity * 0.8),
    );
    canvas.restore();
  }

  void _renderHpBar(Canvas canvas) {
    const barW = 32.0, barH = 4.0;
    final barX = (size.x - barW) / 2;
    const barY = -10.0;
    final ratio = _currentHp / enemyData.maxHp;

    canvas.drawRect(
      Rect.fromLTWH(barX, barY, barW, barH),
      Paint()..color = Colors.black.withOpacity(0.5),
    );
    final hpColor = ratio > 0.5
        ? const Color(0xFF66BB6A)
        : ratio > 0.25
            ? const Color(0xFFFFA726)
            : const Color(0xFFEF5350);
    canvas.drawRect(
      Rect.fromLTWH(barX, barY, barW * ratio, barH),
      Paint()..color = hpColor,
    );
  }

  void _renderArmorBar(Canvas canvas) {
    const barW = 32.0, barH = 3.0;
    final barX = (size.x - barW) / 2;
    const barY = -15.0;
    final ratio = armorHp / (enemyData.armorHp ?? 1);
    canvas.drawRect(
      Rect.fromLTWH(barX, barY, barW * ratio, barH),
      Paint()..color = const Color(0xFF78909C),
    );
  }

  // ---- 外部からの操作 ----

  void takeDamage(int damage) {
    isArmorJustBroken = false;
    if (armorHp > 0) {
      armorHp -= damage;
      if (armorHp <= 0) {
        armorHp = 0;
        isArmorJustBroken = true;
      }
      return; // アーマーが残っている間は本体にダメージなし
    }
    _currentHp -= damage;
    if (_currentHp <= 0) {
      _currentHp = 0;
      _isDying = true;
    }
  }

  void applyBurn({required double damagePerSec, required double duration}) {
    _isBurning = true;
    _burnDps = damagePerSec;
    _burnTimer = duration;
  }

  void applySlow({required double factor, required double duration}) {
    _slowFactor = factor;
    _slowTimer = duration;
  }

  void applyKnockback({required double distance}) {
    _knockbackDistance += distance;
  }

  // ---- ゲッター ----

  bool get isAlive => _currentHp > 0 && !_isDying;
  bool get hasArmor => armorHp > 0;
  int get currentHp => _currentHp;
  int get laneIndex => 1; // game側でposition.yから計算して上書きされる前提

  double get _effectiveMoveSpeed {
    var spd = enemyData.moveSpeed * _slowFactor;
    // ボスチャージ（HP50%以下で加速）
    if (enemyData.movement == MovementPattern.bossCharge) {
      if (_currentHp < enemyData.maxHp * 0.5) spd *= 1.5;
    }
    return spd;
  }

  void _applyBurnTick(double dt) {
    final burnDmg = (_burnDps * dt).round().clamp(1, 100);
    _currentHp -= burnDmg;
    if (_currentHp <= 0) {
      _currentHp = 0;
      _isDying = true;
    }
  }

  void tickStatusEffects(double dt) {
    // update()内で処理済みだが外部から呼べるようにしておく
  }
}
