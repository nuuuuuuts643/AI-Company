import 'dart:math';
import 'package:flame/collisions.dart';
import 'package:flame/components.dart';
import 'package:flame/flame.dart';
import 'package:flutter/material.dart';
import '../constants/element_chart.dart';
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

  // スプライト
  Sprite? _sprite;

  // 配置位置（idle bobのベースとして保持）
  late Vector2 _basePosition;

  UnitComponent({
    required this.unitInstance,
    required Vector2 position,
    required this.onAttack,
  }) : super(position: position, size: Vector2(34, 42)) {
    _basePosition = position.clone();
  }

  @override
  Future<void> onLoad() async {
    add(RectangleHitbox(size: size));
    try {
      final img = await Flame.images.load(_spriteName);
      _sprite = Sprite(img);
    } catch (_) {}
  }

  String get _spriteName {
    switch (unitInstance.element) {
      case ElementType.fire:  return 'unit_fire.png';
      case ElementType.water: return 'unit_water.png';
      case ElementType.wind:  return 'unit_wind.png';
      case ElementType.earth: return 'unit_earth.png';
      case ElementType.light: return 'unit_light.png';
      case ElementType.dark:  return 'unit_dark.png';
    }
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

    // idle bob: レーン位置ごとに位相をずらして自然に見せる
    final phaseOffset = _basePosition.x * 0.05;
    final bob = sin(_elapsed * 2.2 + phaseOffset) * 5.0;
    // 呼吸スケール
    final breathScale = 1.0 + sin(_elapsed * 1.6 + phaseOffset + 0.8) * 0.045;
    scale = Vector2.all(breathScale);
    position.setValues(_basePosition.x, _basePosition.y + bob);
  }

  @override
  void render(Canvas canvas) {
    if (_isDying) {
      _renderDying(canvas);
      return;
    }

    // 地面影
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(size.x / 2, size.y + 2),
        width: size.x * 0.75,
        height: 6,
      ),
      Paint()
        ..color = const Color(0x50000000)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 3),
    );

    final baseColor = Color(unitInstance.element.colorValue);
    final phaseOff = _basePosition.x * 0.05;
    // アイドル時でもパルスする発光
    final glowPulse = _isAttacking
        ? 0.75
        : (0.22 + sin(_elapsed * 2.2 + phaseOff) * 0.16);
    final glowRadius = _isAttacking ? 30.0 : (24.0 + sin(_elapsed * 2.2 + phaseOff) * 4.0);

    // 外側の大きなぼかしグロー
    canvas.drawCircle(
      Offset(size.x / 2, size.y / 2),
      glowRadius + 10,
      Paint()
        ..color = baseColor.withAlpha((glowPulse * 0.45 * 255).round())
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 10),
    );
    // 内側リング
    canvas.drawCircle(
      Offset(size.x / 2, size.y / 2),
      glowRadius,
      Paint()..color = baseColor.withAlpha((glowPulse * 255).round()),
    );

    if (_sprite != null) {
      // スプライト描画
      final attackScale = _isAttacking ? 1.08 : 1.0;
      final w = size.x * attackScale;
      final h = size.y * attackScale;
      _sprite!.render(
        canvas,
        position: Vector2((size.x - w) / 2, (size.y - h) / 2),
        size: Vector2(w, h),
      );

      // 攻撃時フラッシュ
      if (_isAttacking) {
        canvas.drawRect(
          Rect.fromLTWH(0, 0, size.x, size.y),
          Paint()..color = baseColor.withAlpha(50),
        );
      }
    } else {
      // 絵文字フォールバック
      canvas.drawCircle(
        Offset(size.x / 2, size.y / 2 - 2),
        20,
        Paint()..color = const Color(0xFF1A1A2E),
      );
      _drawEmoji(canvas, unitInstance.emoji, 28, Offset(size.x / 2, size.y / 2 - 2));
      if (_isAttacking) {
        canvas.drawCircle(
          Offset(size.x / 2, size.y / 2 - 2),
          22,
          Paint()..color = baseColor.withAlpha(80),
        );
      }
    }

    // フュージョンレベルスター
    if (unitInstance.fusionLevel > 1) {
      _renderFusionStars(canvas);
    }

    // HPバー
    _renderHpBar(canvas);
  }

  void _drawEmoji(Canvas canvas, String emoji, double fontSize, Offset center) {
    final tp = TextPainter(
      text: TextSpan(
        text: emoji,
        style: TextStyle(fontSize: fontSize),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    tp.paint(canvas, center - Offset(tp.width / 2, tp.height / 2));
  }

  void _renderFusionStars(Canvas canvas) {
    final stars = unitInstance.fusionLevel - 1;
    final starEmoji = '⭐' * stars;
    final tp = TextPainter(
      text: TextSpan(
        text: starEmoji,
        style: const TextStyle(fontSize: 10),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    tp.paint(canvas, Offset(size.x / 2 - tp.width / 2, -14));
  }

  void _renderHpBar(Canvas canvas) {
    const barW = 36.0, barH = 4.0;
    final barX = (size.x - barW) / 2;
    const barY = -8.0;
    final ratio = unitInstance.hpRatio;

    canvas.drawRect(
      Rect.fromLTWH(barX, barY, barW, barH),
      Paint()..color = const Color(0x88000000),
    );
    canvas.drawRect(
      Rect.fromLTWH(barX, barY, barW * ratio.clamp(0, 1), barH),
      Paint()
        ..color = ratio > 0.4
            ? const Color(0xFF66BB6A)
            : const Color(0xFFEF5350),
    );
  }

  void _renderDying(Canvas canvas) {
    final progress = (_dyingTimer / 0.5).clamp(0.0, 1.0);
    final opacity = (1.0 - progress);
    final scale = 1.0 + progress * 1.5;

    canvas.save();
    canvas.translate(size.x / 2, size.y / 2);
    canvas.scale(scale, scale);
    if (_sprite != null) {
      _sprite!.render(
        canvas,
        position: Vector2(-size.x / 2, -size.y / 2),
        size: size,
        overridePaint: Paint()..color = Colors.white.withAlpha((opacity * 180).round()),
      );
    } else {
      _drawEmoji(canvas, unitInstance.emoji, 28, Offset.zero);
    }
    canvas.restore();
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

}
