import 'dart:math';
import 'package:flame/collisions.dart';
import 'package:flame/components.dart';
import 'package:flame/flame.dart';
import 'package:flutter/material.dart';
import '../models/enemy_data.dart';
import '../constants/element_chart.dart';
import '../constants/game_constants.dart';

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

  // スプライト（ロード成功時のみ使用）
  Sprite? _sprite;

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
    // スプライトをロード（失敗時は絵文字フォールバック）
    try {
      final img = await Flame.images.load(_spriteName);
      _sprite = Sprite(img);
    } catch (_) {}
  }

  String get _spriteName {
    switch (enemyData.type) {
      case EnemyType.goblin:        return 'enemy_goblin.png';
      case EnemyType.goblinShaman:  return 'enemy_goblin_shaman.png';
      case EnemyType.orc:           return 'enemy_orc.png';
      case EnemyType.orcBerserker:  return 'enemy_orc_berserker.png';
      case EnemyType.fireDrake:     return 'enemy_fire_drake.png';
      case EnemyType.seaSerpent:    return 'enemy_sea_serpent.png';
      case EnemyType.windWraith:    return 'enemy_wind_wraith.png';
      case EnemyType.stoneGolem:    return 'enemy_stone_golem.png';
      case EnemyType.darkKnight:    return 'enemy_dark_knight.png';
      case EnemyType.shadowBat:     return 'enemy_shadow_bat.png';
      case EnemyType.lichKing:      return 'enemy_lich_king.png';
      case EnemyType.shadowLord:    return 'enemy_shadow_lord.png';
    }
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

    // ノックバック処理（上方向に押し返す）
    if (_knockbackDistance > 0) {
      final knock = min(_knockbackDistance, 80.0 * dt);
      position.y -= knock;
      _knockbackDistance -= knock;
      return;
    }

    // 移動（上→下）
    final speed = _effectiveMoveSpeed;
    switch (enemyData.movement) {
      case MovementPattern.straight:
      case MovementPattern.tank:
      case MovementPattern.bossCharge:
        position.y += speed * dt;
        break;
      case MovementPattern.zigzag:
        position.y += speed * dt;
        position.x += sin(_elapsed * 3) * 20 * dt;
        break;
      case MovementPattern.rush:
        position.y += speed * 1.4 * dt;
        break;
      case MovementPattern.flying:
        position.y += speed * dt;
        position.x += sin(_elapsed * 2) * 12 * dt;
        break;
    }
  }

  @override
  void render(Canvas canvas) {
    if (_isDying) {
      _renderDying(canvas);
      return;
    }

    final isBoss = enemyData.type.isBoss;
    final cx = size.x / 2;
    final cy = size.y / 2;
    final wobble = sin(_elapsed * 4) * 2;

    // 地面影（楕円）
    _renderShadow(canvas, isBoss, wobble);

    if (_sprite != null) {
      _renderSprite(canvas, isBoss, wobble);
    } else {
      _renderEmoji(canvas, isBoss, wobble);
    }

    // 弱点属性バッジ（頭上に常時表示）
    _renderWeaknessBadge(canvas);

    // 状態異常アイコン
    if (_isFrozen) _drawEmoji(canvas, '❄️', 12, Offset(cx + 14, cy - 14));
    if (_isBurning) _drawEmoji(canvas, '🔥', 12, Offset(cx + 14, cy - 14));

    // アーマーバー
    if (enemyData.hasArmor && armorHp > 0) _renderArmorBar(canvas);

    // HPバー
    _renderHpBar(canvas);
  }

  void _renderWeaknessBadge(Canvas canvas) {
    final weakness = ElementChart.getWeaknessOf(enemyData.element);
    if (weakness == null) return;

    final pulse = 0.7 + sin(_elapsed * 3.0) * 0.25;
    final badgeX = size.x / 2;
    const badgeY = -20.0;

    // 背景円
    canvas.drawCircle(
      Offset(badgeX, badgeY),
      9,
      Paint()
        ..color = Color(weakness.colorValue).withAlpha((pulse * 180).round())
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 4),
    );
    canvas.drawCircle(
      Offset(badgeX, badgeY),
      7,
      Paint()..color = const Color(0xFF1A1A2E),
    );

    // 弱点属性絵文字
    _drawEmoji(canvas, weakness.emoji, 10, Offset(badgeX, badgeY));
  }

  void _renderShadow(Canvas canvas, bool isBoss, double wobble) {
    final shadowW = isBoss ? size.x * 0.85 : size.x * 0.7;
    final shadowH = isBoss ? 10.0 : 7.0;
    final shadowY = size.y + wobble * 0.3;
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(size.x / 2, shadowY),
        width: shadowW,
        height: shadowH,
      ),
      Paint()
        ..color = const Color(0x44000000)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 4),
    );
  }

  void _renderSprite(Canvas canvas, bool isBoss, double wobble) {
    final w = isBoss ? size.x * 1.15 : size.x;
    final h = isBoss ? size.y * 1.15 : size.y;
    final offsetX = (size.x - w) / 2;
    final offsetY = (size.y - h) / 2 + wobble;

    // 状態異常オーバーレイ（色フィルタ）
    final Paint spritePaint = Paint();
    if (_isFrozen) {
      spritePaint.colorFilter = const ColorFilter.mode(
        Color(0x880077FF), BlendMode.srcATop);
    } else if (_isBurning) {
      spritePaint.colorFilter = const ColorFilter.mode(
        Color(0x88FF3300), BlendMode.srcATop);
    }

    // グロー（ボス強調）
    if (isBoss) {
      final pulse = 0.5 + sin(_elapsed * 3) * 0.3;
      canvas.drawRect(
        Rect.fromLTWH(offsetX - 3, offsetY - 3, w + 6, h + 6),
        Paint()..color = Colors.red.withAlpha((pulse * 80).round()),
      );
    }

    _sprite!.render(
      canvas,
      position: Vector2(offsetX, offsetY),
      size: Vector2(w, h),
      overridePaint: spritePaint.colorFilter != null ? spritePaint : null,
    );
  }

  void _renderEmoji(Canvas canvas, bool isBoss, double wobble) {
    final radius = isBoss ? 24.0 : 18.0;
    final fontSize = isBoss ? 36.0 : 26.0;
    final cx = size.x / 2;
    final cy = size.y / 2;

    Color bgColor = const Color(0xFF1A0A2E);
    if (_isFrozen) bgColor = const Color(0xFF0D2B4A);
    if (_isBurning) bgColor = const Color(0xFF3A0A00);

    final glowColor = isBoss
        ? Colors.red.withAlpha(80)
        : Color(enemyData.element.colorValue).withAlpha(60);
    canvas.drawCircle(Offset(cx, cy + wobble), radius + 4, Paint()..color = glowColor);
    canvas.drawCircle(Offset(cx, cy + wobble), radius, Paint()..color = bgColor);
    _drawEmoji(canvas, _enemyEmoji, fontSize, Offset(cx, cy + wobble));

    if (isBoss) {
      final pulse = 0.5 + sin(_elapsed * 3) * 0.3;
      canvas.drawCircle(
        Offset(cx, cy + wobble),
        radius + 1,
        Paint()
          ..color = Colors.red.withAlpha((pulse * 200).round())
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2,
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

  String get _enemyEmoji {
    switch (enemyData.type) {
      case EnemyType.goblin:        return '👺';
      case EnemyType.goblinShaman:  return '🧙';
      case EnemyType.orc:           return '💪';
      case EnemyType.orcBerserker:  return '😤';
      case EnemyType.fireDrake:     return '🐲';
      case EnemyType.seaSerpent:    return '🐍';
      case EnemyType.windWraith:    return '👻';
      case EnemyType.stoneGolem:    return '🗿';
      case EnemyType.darkKnight:    return '🖤';
      case EnemyType.shadowBat:     return '🦇';
      case EnemyType.lichKing:      return '💀';
      case EnemyType.shadowLord:    return '🌑';
    }
  }

  void _renderDying(Canvas canvas) {
    final progress = (_dyingTimer / 0.4).clamp(0.0, 1.0);
    final scale = 1.0 + progress * 2.5;
    final opacity = (1.0 - progress);

    canvas.save();
    canvas.translate(size.x / 2, size.y / 2);
    canvas.scale(scale, scale);

    if (_sprite != null) {
      final w = size.x;
      final h = size.y;
      _sprite!.render(
        canvas,
        position: Vector2(-w / 2, -h / 2),
        size: Vector2(w, h),
        overridePaint: Paint()..color = Colors.white.withAlpha((opacity * 200).round()),
      );
    } else {
      _drawEmoji(canvas, _enemyEmoji, 26, Offset.zero);
    }
    canvas.restore();

    canvas.drawCircle(
      Offset(size.x / 2, size.y / 2),
      20 * scale,
      Paint()..color = Colors.orangeAccent.withAlpha((opacity * 120).round()),
    );
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
  int get laneIndex =>
      (position.x / GameConstants.laneWidth).floor().clamp(0, 2);

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
