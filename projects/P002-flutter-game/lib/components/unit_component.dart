import 'dart:math';
import 'package:flame/collisions.dart';
import 'package:flame/components.dart';
import 'package:flutter/material.dart';
import '../models/unit_data.dart';
import '../components/enemy_component.dart';

/// フィールド上のユニット1体のFlameコンポーネント
class UnitComponent extends PositionComponent with CollisionCallbacks {
  final UnitInstance unitInstance;

  // 攻撃コールバック（BattleSystemを迂回してgame層に通知）
  final void Function({
    required UnitInstance attacker,
    required EnemyComponent target,
    required int damage,
    required bool isWeakness,
    required bool isChain,
  }) onAttack;

  // アニメーション
  double _elapsed = 0;
  bool _isAttacking = false;
  double _attackAnimTimer = 0;
  bool _isDying = false;
  double _dyingTimer = 0;

  final _rng = Random();

  UnitComponent({
    required this.unitInstance,
    required Vector2 position,
    required this.onAttack,
  }) : super(position: position, size: Vector2(34, 42));

  @override
  Future<void> onLoad() async {
    add(RectangleHitbox(size: size));
  }

  @override
  void update(double dt) {
    _elapsed += dt;

    if (!unitInstance.isAlive && !_isDying) {
      _isDying = true;
    }

    if (_isDying) {
      _dyingTimer += dt;
      return;
    }

    if (_isAttacking) {
      _attackAnimTimer -= dt;
      if (_attackAnimTimer <= 0) {
        _isAttacking = false;
      }
    }
  }

  @override
  void render(Canvas canvas) {
    if (_isDying) {
      _renderDying(canvas);
      return;
    }

    final baseColor = _unitBaseColor;

    // ---- スプライトプレースホルダー ----
    // 背景ブルーム（光属性・暗属性ユニットは発光）
    _renderGlow(canvas, baseColor);

    // ボディ
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(3, 6, 28, 30),
        const Radius.circular(4),
      ),
      Paint()..color = baseColor,
    );

    // 頭
    canvas.drawCircle(
      Offset(size.x / 2, 7),
      9,
      Paint()..color = baseColor.withRed((baseColor.red * 1.2).clamp(0, 255).round()),
    );

    // 攻撃時の前傾アニメーション
    if (_isAttacking) {
      canvas.drawRect(
        Rect.fromLTWH(size.x - 6, size.y / 2 - 3, 14, 6),
        Paint()..color = Colors.white.withOpacity(0.7),
      );
    }

    // HP バー
    _renderHpBar(canvas);

    // 属性バッジ（右上に小さく表示）
    _renderElementBadge(canvas);
  }

  void _renderGlow(Canvas canvas, Color color) {
    final glowIntensity = _isAttacking ? 0.4 : 0.15;
    canvas.drawCircle(
      Offset(size.x / 2, size.y / 2),
      24,
      Paint()..color = color.withOpacity(glowIntensity),
    );
  }

  void _renderHpBar(Canvas canvas) {
    const barW = 30.0, barH = 3.0;
    final barX = (size.x - barW) / 2;
    const barY = -6.0;
    final ratio = unitInstance.hpRatio;

    canvas.drawRect(
      Rect.fromLTWH(barX, barY, barW, barH),
      Paint()..color = Colors.black.withOpacity(0.5),
    );
    canvas.drawRect(
      Rect.fromLTWH(barX, barY, barW * ratio.clamp(0, 1), barH),
      Paint()..color = ratio > 0.4 ? const Color(0xFF66BB6A) : const Color(0xFFEF5350),
    );
  }

  void _renderElementBadge(Canvas canvas) {
    canvas.drawCircle(
      Offset(size.x - 4, 4),
      5,
      Paint()..color = Color(unitInstance.element.colorValue),
    );
  }

  void _renderDying(Canvas canvas) {
    final opacity = (1.0 - _dyingTimer / 0.5).clamp(0.0, 1.0);
    canvas.drawRect(
      Rect.fromLTWH(0, 0, size.x, size.y),
      Paint()..color = Colors.white.withOpacity(opacity * 0.6),
    );
  }

  // ---- 外部からの操作 ----

  /// 攻撃アニメーションを起動（BattleSystemから呼ばれる）
  void triggerAttackAnimation() {
    _isAttacking = true;
    _attackAnimTimer = 0.2;
  }

  /// ダメージを受けた時の揺れ
  void takeDamageVisual() {
    // 将来的にダメージフラッシュを追加
  }

  // ---- ゲッター ----

  Color get _unitBaseColor {
    final elem = unitInstance.element;
    return Color(elem.colorValue);
  }
}
