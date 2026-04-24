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

  // レーンに敵がいるか（前進システム用）
  final bool Function(int laneIndex)? laneHasEnemies;

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
  // 配置時の原点Y（前進上限の計算に使用）
  late double _originY;

  // 前進システム
  double _advanceY = 0; // 前進量（増えると上方向＝Yが減る）
  static const _maxAdvance = 72.0;
  static const _advanceSpeed = 18.0; // px/s
  static const _advanceRetreatSpeed = 30.0; // 敵出現時の後退速度
  bool _isAdvancing = false;

  UnitComponent({
    required this.unitInstance,
    required Vector2 position,
    required this.onAttack,
    this.laneHasEnemies,
  }) : super(position: position, size: Vector2(34, 42)) {
    _basePosition = position.clone();
    _originY = position.y;
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

    // ---- 前進システム ----
    if (laneHasEnemies != null) {
      final hasEnemy = laneHasEnemies!(unitInstance.laneIndex);
      if (!hasEnemy) {
        // レーンクリア → ゆっくり前進
        _advanceY = (_advanceY + _advanceSpeed * dt).clamp(0, _maxAdvance);
        _isAdvancing = true;
      } else {
        // 敵出現 → 元の位置に後退
        if (_advanceY > 0) {
          _advanceY = (_advanceY - _advanceRetreatSpeed * dt).clamp(0, _maxAdvance);
        }
        _isAdvancing = false;
      }
      _basePosition.y = _originY - _advanceY;
    }

    // idle bob: レーン位置ごとに位相をずらして自然に見せる
    final phaseOffset = _basePosition.x * 0.05;
    final bob = sin(_elapsed * 2.2 + phaseOffset) * 5.0;
    // 呼吸スケール（前進中は若干前傾）
    final breathScale = 1.0 + sin(_elapsed * 1.6 + phaseOffset + 0.8) * 0.045;
    scale = Vector2.all(breathScale);

    // 攻撃ランジ: attackAnimTimer残り率をsin波でY上方向に突進
    double lungeY = 0;
    if (_isAttacking) {
      final progress = 1.0 - (_attackAnimTimer / 0.2).clamp(0.0, 1.0);
      lungeY = sin(progress * pi) * -14.0; // 上方向へ14px突進
    }
    position.setValues(_basePosition.x, _basePosition.y + bob + lungeY);
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

    // ---- バフ中の光輪エフェクト ----
    if (unitInstance.isBuffed) {
      final buffPulse = 0.5 + sin(_elapsed * 5) * 0.4;
      // 攻撃速度バフ → 緑の輪
      if (unitInstance.atkSpeedBuffTimer > 0) {
        canvas.drawCircle(
          Offset(size.x / 2, size.y / 2),
          26 + buffPulse * 5,
          Paint()
            ..color = const Color(0xFF66BB6A).withAlpha((buffPulse * 100).round())
            ..style = PaintingStyle.stroke
            ..strokeWidth = 3
            ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 4),
        );
        // 速度の粒子（短い弧が回転）
        for (int i = 0; i < 3; i++) {
          final angle = _elapsed * 4 + i * pi * 2 / 3;
          canvas.drawArc(
            Rect.fromCenter(center: Offset(size.x / 2, size.y / 2), width: 46, height: 46),
            angle,
            0.8,
            false,
            Paint()
              ..color = const Color(0xFFA5D6A7).withAlpha(180)
              ..style = PaintingStyle.stroke
              ..strokeWidth = 2.5
              ..strokeCap = StrokeCap.round,
          );
        }
      }
    }

    // ---- 支援ユニット：常時ヒーリングオーラ ----
    if (unitInstance.attackType == AttackType.support) {
      final healPulse = 0.4 + sin(_elapsed * 2.5) * 0.35;
      canvas.drawCircle(
        Offset(size.x / 2, size.y / 2),
        30 + healPulse * 8,
        Paint()
          ..color = const Color(0xFFFFD700).withAlpha((healPulse * 60).round())
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 10),
      );
      // 十字の光
      for (int i = 0; i < 4; i++) {
        final a = _elapsed * 1.2 + i * pi / 2;
        final r = 22 + healPulse * 6;
        canvas.drawLine(
          Offset(size.x / 2 + cos(a) * 8, size.y / 2 + sin(a) * 8),
          Offset(size.x / 2 + cos(a) * r, size.y / 2 + sin(a) * r),
          Paint()
            ..color = const Color(0xFFFFE082).withAlpha((healPulse * 160).round())
            ..strokeWidth = 2
            ..strokeCap = StrokeCap.round,
        );
      }
    }

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

    // 攻撃バーストリング
    if (_isAttacking) {
      final progress = 1.0 - (_attackAnimTimer / 0.2).clamp(0.0, 1.0);
      final ringR = 18.0 + progress * 22.0;
      final ringA = ((1.0 - progress) * 180).round().clamp(0, 180);
      canvas.drawCircle(
        Offset(size.x / 2, size.y / 2),
        ringR,
        Paint()
          ..color = baseColor.withAlpha(ringA)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2.5
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 3),
      );
    }

    // フュージョンレベルスター
    if (unitInstance.fusionLevel > 1) {
      _renderFusionStars(canvas);
    }

    // 前進インジケーター（前進中：上向き三角が点滅）
    if (_isAdvancing && _advanceY > 4) {
      final advPulse = 0.5 + sin(_elapsed * 6) * 0.4;
      final path = Path()
        ..moveTo(size.x / 2, -18)
        ..lineTo(size.x / 2 - 7, -10)
        ..lineTo(size.x / 2 + 7, -10)
        ..close();
      canvas.drawPath(
        path,
        Paint()
          ..color = const Color(0xFF69F0AE).withAlpha((advPulse * 200).round())
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 2),
      );
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

  /// ダメージを受けた時の揺れ＋前進リセット
  void takeDamageVisual() {
    // 被弾時に少し後退
    _advanceY = (_advanceY - 20.0).clamp(0, _maxAdvance);
    _basePosition.y = _originY - _advanceY;
  }

}
