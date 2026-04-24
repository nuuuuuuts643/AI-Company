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

  // 被弾フラッシュ
  bool _isHit = false;
  double _hitTimer = 0;

  // 歩行サイクル（足の位相）
  double _stepPhase = 0;

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

    // 被弾フラッシュタイマー
    if (_isHit) {
      _hitTimer -= dt;
      if (_hitTimer <= 0) _isHit = false;
    }

    // 歩行位相（凍結・ノックバック中は進めない）
    if (!_isFrozen && _knockbackDistance <= 0) {
      _stepPhase += dt * (_effectiveMoveSpeed / 45.0);
    }

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
    final stepSin = sin(_stepPhase * pi);
    final scaleX = 1.0 + stepSin * 0.08;
    final scaleY = 1.0 - stepSin * 0.06;

    final w = (isBoss ? size.x * 1.15 : size.x) * scaleX;
    final h = (isBoss ? size.y * 1.15 : size.y) * scaleY;
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

    // 被弾フラッシュ
    if (_isHit) {
      final hitAlpha = (_hitTimer / 0.12 * 180).round().clamp(0, 180);
      canvas.drawRect(
        Rect.fromLTWH(offsetX - 4, offsetY - 4, w + 8, h + 8),
        Paint()
          ..color = Colors.white.withAlpha(hitAlpha)
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 5),
      );
    }
  }

  void _renderEmoji(Canvas canvas, bool isBoss, double wobble) {
    final cx = size.x / 2;
    final cy = size.y / 2 + wobble;

    // 歩行スクワッシュ&ストレッチ
    final stepSin = sin(_stepPhase * pi);
    final scaleX = 1.0 + stepSin * 0.10;
    final scaleY = 1.0 - stepSin * 0.08;
    final bodyScale = isBoss ? 1.35 : 1.0;

    // 状態異常カラーフィルタ
    Color tint = Colors.transparent;
    if (_isFrozen) tint = const Color(0x550077FF);
    if (_isBurning) tint = const Color(0x55FF3300);

    canvas.save();
    canvas.translate(cx, cy);
    canvas.scale(scaleX * bodyScale, scaleY * bodyScale);

    // ボスグロー
    if (isBoss) {
      final pulse = 0.5 + sin(_elapsed * 3) * 0.3;
      canvas.drawCircle(
        Offset.zero,
        26,
        Paint()
          ..color = Colors.red.withAlpha((pulse * 60).round())
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 8),
      );
    }

    // 敵タイプ別ドット絵描画
    _EnemyPixelArt.draw(canvas, enemyData.type, _elapsed, _stepPhase, _isFrozen, _isBurning);

    // 状態異常カラーオーバーレイ
    if (tint != Colors.transparent) {
      canvas.drawCircle(Offset.zero, 20, Paint()..color = tint);
    }

    canvas.restore();

    // 被弾フラッシュ
    if (_isHit) {
      final hitAlpha = (_hitTimer / 0.12 * 160).round().clamp(0, 160);
      canvas.drawCircle(
        Offset(cx, cy),
        22,
        Paint()
          ..color = Colors.white.withAlpha(hitAlpha)
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 6),
      );
    }
  }

  // ドット絵ペインター（ボス含む全敵タイプ）
  static void _px(Canvas canvas, Color c, double x, double y, double s) {
    canvas.drawRect(Rect.fromLTWH(x, y, s, s), Paint()..color = c);
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
    _isHit = true;
    _hitTimer = 0.12;
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

// ============================================================
// 敵タイプ別ドット絵スタイル描画
// ============================================================
class _EnemyPixelArt {
  static void draw(Canvas c, EnemyType type, double elapsed, double stepPhase,
      bool frozen, bool burning) {
    switch (type) {
      case EnemyType.goblin:        _goblin(c, elapsed, stepPhase); break;
      case EnemyType.goblinShaman:  _shaman(c, elapsed, stepPhase); break;
      case EnemyType.orc:           _orc(c, elapsed, stepPhase); break;
      case EnemyType.orcBerserker:  _berserker(c, elapsed, stepPhase); break;
      case EnemyType.fireDrake:     _drake(c, elapsed, stepPhase); break;
      case EnemyType.seaSerpent:    _serpent(c, elapsed, stepPhase); break;
      case EnemyType.windWraith:    _wraith(c, elapsed, stepPhase); break;
      case EnemyType.stoneGolem:    _golem(c, elapsed, stepPhase); break;
      case EnemyType.darkKnight:    _darkKnight(c, elapsed, stepPhase); break;
      case EnemyType.shadowBat:     _bat(c, elapsed, stepPhase); break;
      case EnemyType.lichKing:      _lich(c, elapsed, stepPhase); break;
      case EnemyType.shadowLord:    _shadowLord(c, elapsed, stepPhase); break;
    }
  }

  static Paint _p(Color c) => Paint()..color = c;
  static void _rect(Canvas c, Color col, double x, double y, double w, double h) =>
      c.drawRect(Rect.fromLTWH(x, y, w, h), _p(col));
  static void _circ(Canvas c, Color col, Offset o, double r) =>
      c.drawCircle(o, r, _p(col));

  // --- ゴブリン: 緑の小悪魔、尖り耳、赤目 ---
  static void _goblin(Canvas c, double t, double step) {
    final legSwing = sin(step * pi) * 3;
    // 胴体
    _rect(c, const Color(0xFF3A7A3A), -7, -5, 14, 12);
    // 頭
    _circ(c, const Color(0xFF4CAF50), const Offset(0, -13), 9);
    // 耳（尖り）
    final earPath = Path()
      ..moveTo(-9, -16)..lineTo(-13, -22)..lineTo(-6, -14)..close();
    c.drawPath(earPath, _p(const Color(0xFF4CAF50)));
    final earPath2 = Path()
      ..moveTo(9, -16)..lineTo(13, -22)..lineTo(6, -14)..close();
    c.drawPath(earPath2, _p(const Color(0xFF4CAF50)));
    // 目（赤）
    _circ(c, Colors.red, const Offset(-3.5, -14), 2.5);
    _circ(c, Colors.red, const Offset(3.5, -14), 2.5);
    // 歯
    _rect(c, Colors.white, -3, -9, 2, 3);
    _rect(c, Colors.white, 1, -9, 2, 3);
    // 脚（交互）
    _rect(c, const Color(0xFF2E5E2E), -6, 7, 5, 8 + legSwing.abs() ~/ 1 * 0);
    _rect(c, const Color(0xFF2E5E2E), 1, 7, 5, 8);
    _rect(c, const Color(0xFF1B3D1B), -6, 7, 5, legSwing > 0 ? 10 : 6);
    _rect(c, const Color(0xFF1B3D1B), 1, 7, 5, legSwing < 0 ? 10 : 6);
    // 武器（短剣）
    c.drawLine(const Offset(10, -2), const Offset(16, -8),
        Paint()..color = Colors.grey..strokeWidth = 2.5);
  }

  // --- シャーマン: 紫ローブ、杖 ---
  static void _shaman(Canvas c, double t, double step) {
    final bob = sin(t * 3) * 1.5;
    // ローブ
    final robe = Path()
      ..moveTo(-10, -2)..lineTo(-8, 14)..lineTo(8, 14)..lineTo(10, -2)..close();
    c.drawPath(robe, _p(const Color(0xFF6A1B9A)));
    // 頭
    _circ(c, const Color(0xFF8BC34A), Offset(0, -13 + bob), 8);
    // 帽子
    final hat = Path()
      ..moveTo(-8, -13 + bob)..lineTo(0, -28 + bob)..lineTo(8, -13 + bob)..close();
    c.drawPath(hat, _p(const Color(0xFF4A148C)));
    // 目（黄）
    _circ(c, Colors.yellow, Offset(-3, -13 + bob), 2);
    _circ(c, Colors.yellow, Offset(3, -13 + bob), 2);
    // 杖（魔法陣のグロー付き）
    c.drawLine(Offset(12, 5 + bob), Offset(18, -15 + bob),
        Paint()..color = const Color(0xFF795548)..strokeWidth = 2.5);
    _circ(c, const Color(0xFFCE93D8), Offset(18, -17 + bob), 4);
    _circ(c, const Color(0xFFE040FB), Offset(18, -17 + bob), 2.5);
  }

  // --- オーク: 茶色い大柄、斧 ---
  static void _orc(Canvas c, double t, double step) {
    final legSwing = sin(step * pi) * 4;
    // 胴体（幅広）
    _rect(c, const Color(0xFF795548), -11, -6, 22, 15);
    // 肩パッド
    _rect(c, const Color(0xFF5D4037), -14, -8, 8, 5);
    _rect(c, const Color(0xFF5D4037), 6, -8, 8, 5);
    // 頭
    _circ(c, const Color(0xFF8D6E63), const Offset(0, -14), 10);
    // 牙
    _rect(c, Colors.white, -5, -8, 3, 5);
    _rect(c, Colors.white, 2, -8, 3, 5);
    // 目（白に黒ひとみ）
    _circ(c, Colors.white, const Offset(-4, -15), 3);
    _circ(c, Colors.white, const Offset(4, -15), 3);
    _circ(c, Colors.black, const Offset(-4, -15), 1.5);
    _circ(c, Colors.black, const Offset(4, -15), 1.5);
    // 脚
    _rect(c, const Color(0xFF4E342E), -10, 9, 8, legSwing > 0 ? 10 : 6);
    _rect(c, const Color(0xFF4E342E), 2, 9, 8, legSwing < 0 ? 10 : 6);
    // 斧
    final axePath = Path()
      ..moveTo(15, -10)..lineTo(22, -5)..lineTo(18, 3)..lineTo(15, -2)..close();
    c.drawPath(axePath, _p(Colors.blueGrey));
    c.drawLine(const Offset(15, -10), const Offset(15, 10),
        Paint()..color = const Color(0xFF795548)..strokeWidth = 2.5);
  }

  // --- バーサーカー: 赤いオーク、二刀流 ---
  static void _berserker(Canvas c, double t, double step) {
    final rage = 0.5 + sin(t * 5) * 0.4;
    // 怒りオーラ
    _circ(c, Colors.red.withAlpha((rage * 50).round()), Offset.zero, 22);
    // 胴体
    _rect(c, const Color(0xFF8B0000), -11, -6, 22, 15);
    _rect(c, const Color(0xFF5D0000), -14, -8, 8, 5);
    _rect(c, const Color(0xFF5D0000), 6, -8, 8, 5);
    // 頭（アンブレイカブルな顔）
    _circ(c, const Color(0xFF9E6060), const Offset(0, -14), 10);
    // 目（赤く怒った）
    _circ(c, const Color(0xFFFF1744), const Offset(-4, -15), 3.5);
    _circ(c, const Color(0xFFFF1744), const Offset(4, -15), 3.5);
    // 双剣
    c.drawLine(const Offset(-15, -12), const Offset(-15, 8),
        Paint()..color = Colors.grey..strokeWidth = 2);
    c.drawLine(const Offset(15, -12), const Offset(15, 8),
        Paint()..color = Colors.grey..strokeWidth = 2);
    // 脚
    _rect(c, const Color(0xFF6D0000), -10, 9, 8, 9);
    _rect(c, const Color(0xFF6D0000), 2, 9, 8, 9);
  }

  // --- ファイアドレイク: 赤い翼竜 ---
  static void _drake(Canvas c, double t, double step) {
    final wingFlap = sin(t * 4) * 6;
    // 翼
    final wL = Path()
      ..moveTo(-8, -8)..lineTo(-24, -18 + wingFlap)..lineTo(-20, -2)..lineTo(-8, 0)..close();
    final wR = Path()
      ..moveTo(8, -8)..lineTo(24, -18 + wingFlap)..lineTo(20, -2)..lineTo(8, 0)..close();
    c.drawPath(wL, _p(const Color(0xFFB71C1C)));
    c.drawPath(wR, _p(const Color(0xFFB71C1C)));
    // 胴体
    _circ(c, const Color(0xFFE53935), const Offset(0, 2), 11);
    // 頭
    _circ(c, const Color(0xFFEF5350), const Offset(0, -12), 9);
    // 角
    c.drawLine(const Offset(-4, -20), const Offset(-8, -28),
        Paint()..color = const Color(0xFF8B0000)..strokeWidth = 2.5);
    c.drawLine(const Offset(4, -20), const Offset(8, -28),
        Paint()..color = const Color(0xFF8B0000)..strokeWidth = 2.5);
    // 炎の目
    _circ(c, Colors.orange, const Offset(-3, -12), 2.5);
    _circ(c, Colors.orange, const Offset(3, -12), 2.5);
    // 尻尾
    final tail = Path()
      ..moveTo(8, 6)..quadraticBezierTo(20, 10, 22, 4);
    c.drawPath(tail, Paint()
      ..color = const Color(0xFFC62828)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3);
    // 炎ブレス（口から）
    if (sin(t * 3) > 0.3) {
      _circ(c, Colors.orange.withAlpha(120), const Offset(0, -5), 6);
      _circ(c, Colors.yellow.withAlpha(80), const Offset(0, -5), 4);
    }
  }

  // --- 海蛇: 青緑のS字 ---
  static void _serpent(Canvas c, double t, double step) {
    final wave = sin(t * 2.5);
    // 蛇のS字ボディ
    final path = Path()..moveTo(0, 14);
    for (double i = 0; i <= 1.0; i += 0.05) {
      final y = 14 - i * 36;
      final x = sin(i * pi * 2 + t * 2) * 8 * (1 - i * 0.5);
      if (i == 0) path.moveTo(x, y); else path.lineTo(x, y);
    }
    c.drawPath(path, Paint()
      ..color = const Color(0xFF006064)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 10
      ..strokeCap = StrokeCap.round);
    c.drawPath(path, Paint()
      ..color = const Color(0xFF00BCD4)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 7
      ..strokeCap = StrokeCap.round);
    // 頭
    _circ(c, const Color(0xFF00ACC1), Offset(sin(t * 2) * 8, -20 + wave * 2), 9);
    _circ(c, Colors.yellow, Offset(sin(t * 2) * 8 - 3, -21 + wave * 2), 2);
    _circ(c, Colors.yellow, Offset(sin(t * 2) * 8 + 3, -21 + wave * 2), 2);
    // 舌
    c.drawLine(
      Offset(sin(t * 2) * 8, -12 + wave * 2),
      Offset(sin(t * 2) * 8 - 3, -8 + wave * 2),
      Paint()..color = Colors.red..strokeWidth = 1.5,
    );
    c.drawLine(
      Offset(sin(t * 2) * 8, -12 + wave * 2),
      Offset(sin(t * 2) * 8 + 3, -8 + wave * 2),
      Paint()..color = Colors.red..strokeWidth = 1.5,
    );
  }

  // --- 風の亡霊: 半透明のドクロ ---
  static void _wraith(Canvas c, double t, double step) {
    final float = sin(t * 2.5) * 4;
    final alpha = (0.7 + sin(t * 3) * 0.2);
    // 裾（波うつ）
    final hemPath = Path()..moveTo(-12, 12 + float);
    for (int i = 0; i <= 24; i++) {
      final x = -12.0 + i;
      final y = 14 + float + sin((i / 24) * pi * 3 + t * 4) * 4;
      hemPath.lineTo(x, y);
    }
    hemPath.lineTo(12, -4 + float);
    hemPath.lineTo(-12, -4 + float);
    hemPath.close();
    c.drawPath(hemPath,
        _p(const Color(0xFF4A148C).withAlpha((alpha * 200).round())));
    // 胴
    _circ(c, const Color(0xFF6A1B9A).withAlpha((alpha * 220).round()),
        Offset(0, -2 + float), 10);
    // ドクロ顔
    _circ(c, Colors.white.withAlpha((alpha * 200).round()),
        Offset(0, -10 + float), 9);
    _circ(c, Colors.black.withAlpha((alpha * 160).round()),
        Offset(-3.5, -11 + float), 3);
    _circ(c, Colors.black.withAlpha((alpha * 160).round()),
        Offset(3.5, -11 + float), 3);
    _rect(c, Colors.black.withAlpha((alpha * 130).round()),
        -4, -5 + float, 8, 2);
    // 風のオーラ
    for (int i = 0; i < 3; i++) {
      final a2 = t * 3 + i * pi * 2 / 3;
      c.drawCircle(
        Offset(cos(a2) * 14, sin(a2) * 8 + float),
        3,
        Paint()..color = const Color(0xFFCE93D8).withAlpha(80),
      );
    }
  }

  // --- ストーンゴーレム: 灰色の岩塊 ---
  static void _golem(Canvas c, double t, double step) {
    final stomp = sin(step * pi).abs() * 3;
    // 体（大きな四角ブロック）
    _rect(c, const Color(0xFF546E7A), -14, -4, 28, 18 - stomp);
    _rect(c, const Color(0xFF78909C), -12, -6, 24, 8);
    // 亀裂
    c.drawLine(const Offset(-4, -6), const Offset(-6, 12),
        Paint()..color = const Color(0xFF37474F)..strokeWidth = 1.5);
    c.drawLine(const Offset(5, -2), const Offset(3, 14),
        Paint()..color = const Color(0xFF37474F)..strokeWidth = 1.5);
    // 頭（岩）
    _rect(c, const Color(0xFF607D8B), -10, -18, 20, 14);
    _rect(c, const Color(0xFF78909C), -8, -20, 16, 4);
    // 目（エメラルドに光る）
    _circ(c, const Color(0xFF00E676), const Offset(-4, -12), 3.5);
    _circ(c, const Color(0xFF00E676), const Offset(4, -12), 3.5);
    _circ(c, Colors.white.withAlpha(180), const Offset(-4, -12), 2);
    _circ(c, Colors.white.withAlpha(180), const Offset(4, -12), 2);
    // 腕
    _rect(c, const Color(0xFF546E7A), -22, -4, 8, 12);
    _rect(c, const Color(0xFF546E7A), 14, -4, 8, 12);
    // 脚
    _rect(c, const Color(0xFF455A64), -12, 14, 10, 8 + stomp);
    _rect(c, const Color(0xFF455A64), 2, 14, 10, 8 + stomp);
  }

  // --- ダークナイト: 黒鎧、魔剣 ---
  static void _darkKnight(Canvas c, double t, double step) {
    // 鎧胴体
    _rect(c, const Color(0xFF212121), -11, -6, 22, 16);
    _rect(c, const Color(0xFF37474F), -13, -8, 8, 6);
    _rect(c, const Color(0xFF37474F), 5, -8, 8, 6);
    // 兜
    _rect(c, const Color(0xFF263238), -9, -20, 18, 14);
    _rect(c, const Color(0xFF37474F), -7, -22, 14, 4);
    // 目スリット（赤）
    _rect(c, const Color(0xFFD50000), -7, -13, 14, 2.5);
    // 紋章
    _circ(c, const Color(0xFF6200EA), const Offset(0, -1), 4);
    _circ(c, const Color(0xFFD500F9), const Offset(0, -1), 2.5);
    // 脚
    _rect(c, const Color(0xFF1A1A1A), -9, 10, 8, 9);
    _rect(c, const Color(0xFF1A1A1A), 1, 10, 8, 9);
    // 大剣（暗いオーラ）
    final glow = 0.5 + sin(t * 3) * 0.4;
    c.drawLine(const Offset(-18, -22), const Offset(-18, 14),
        Paint()..color = const Color(0xFF1A1A1A)..strokeWidth = 5);
    c.drawLine(const Offset(-18, -22), const Offset(-18, 14),
        Paint()..color = const Color(0xFFAA00FF)
          ..strokeWidth = 2
          ..maskFilter = MaskFilter.blur(BlurStyle.normal, glow * 3));
  }

  // --- シャドウバット: 翼を広げた黒蝙蝠 ---
  static void _bat(Canvas c, double t, double step) {
    final flapAngle = sin(t * 8) * 0.5;
    // 左翼
    canvas_drawWing(c, flapAngle, -1);
    // 右翼
    canvas_drawWing(c, -flapAngle, 1);
    // 胴体
    _circ(c, const Color(0xFF1A1A2E), Offset.zero, 8);
    _circ(c, const Color(0xFF311B92), Offset.zero, 6);
    // 頭（小さい）
    _circ(c, const Color(0xFF1A1A2E), const Offset(0, -10), 6);
    // 耳（尖り）
    final eLPath = Path()
      ..moveTo(-5, -14)..lineTo(-8, -22)..lineTo(-2, -14)..close();
    final eRPath = Path()
      ..moveTo(5, -14)..lineTo(8, -22)..lineTo(2, -14)..close();
    c.drawPath(eLPath, _p(const Color(0xFF1A1A2E)));
    c.drawPath(eRPath, _p(const Color(0xFF1A1A2E)));
    // 目
    _circ(c, const Color(0xFFFF1744), const Offset(-2.5, -10), 2);
    _circ(c, const Color(0xFFFF1744), const Offset(2.5, -10), 2);
  }

  static void canvas_drawWing(Canvas c, double flapAngle, double side) {
    c.save();
    c.scale(side, 1);
    c.rotate(flapAngle);
    final wing = Path()
      ..moveTo(4, -4)..lineTo(22, -14)..lineTo(20, 0)..lineTo(14, 4)..lineTo(4, 6)..close();
    c.drawPath(wing, _p(const Color(0xFF0D0D1A)));
    c.drawPath(wing, Paint()
      ..color = const Color(0xFF4A148C)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1);
    c.restore();
  }

  // --- リッチキング: 黄金の骨王 ---
  static void _lich(Canvas c, double t, double step) {
    final float = sin(t * 2) * 3;
    final glow = 0.6 + sin(t * 4) * 0.3;
    // 魔法陣（足元に回転）
    c.save();
    c.rotate(t * 0.5);
    for (int i = 0; i < 6; i++) {
      final a = i * pi / 3;
      c.drawLine(
        Offset(cos(a) * 4, sin(a) * 4),
        Offset(cos(a) * 18, sin(a) * 18),
        Paint()..color = const Color(0xFFFFD700).withAlpha((glow * 100).round())..strokeWidth = 1,
      );
    }
    c.drawCircle(Offset.zero, 18,
        Paint()
          ..color = const Color(0xFFFFD700).withAlpha((glow * 80).round())
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.5);
    c.restore();
    // ローブ
    final robe = Path()
      ..moveTo(-12, -2 + float)..lineTo(-8, 16 + float)..lineTo(8, 16 + float)..lineTo(12, -2 + float)..close();
    c.drawPath(robe, _p(const Color(0xFF1A0033)));
    c.drawPath(robe, Paint()
      ..color = const Color(0xFF7B1FA2)
      ..style = PaintingStyle.stroke..strokeWidth = 1);
    // ドクロ頭
    _circ(c, const Color(0xFFF5F5F5), Offset(0, -13 + float), 9);
    _circ(c, Colors.black, Offset(-3.5, -14 + float), 3);
    _circ(c, Colors.black, Offset(3.5, -14 + float), 3);
    _circ(c, const Color(0xFFFFD700).withAlpha((glow * 220).round()),
        Offset(-3.5, -14 + float), 2);
    _circ(c, const Color(0xFFFFD700).withAlpha((glow * 220).round()),
        Offset(3.5, -14 + float), 2);
    // 王冠
    _rect(c, const Color(0xFFFFD700), -9, -24 + float, 18, 6);
    _rect(c, const Color(0xFFFFF176), -7, -28 + float, 4, 4);
    _rect(c, const Color(0xFFFFF176), -1, -28 + float, 4, 4);
    _rect(c, const Color(0xFFFFF176), 5, -28 + float, 4, 4);
    // 杖
    c.drawLine(Offset(14, 6 + float), Offset(14, -18 + float),
        Paint()..color = const Color(0xFF795548)..strokeWidth = 2.5);
    _circ(c, const Color(0xFFFFD700).withAlpha((glow * 230).round()),
        Offset(14, -20 + float), 5);
    _circ(c, Colors.white.withAlpha((glow * 200).round()),
        Offset(14, -20 + float), 3);
  }

  // --- シャドウロード: 巨大な闇の存在（ラスボス） ---
  static void _shadowLord(Canvas c, double t, double step) {
    final pulse = 0.5 + sin(t * 2) * 0.4;
    // 闇のオーラ（多重リング）
    for (int i = 3; i >= 1; i--) {
      c.drawCircle(Offset.zero, 10.0 + i * 6 + sin(t + i) * 3,
          Paint()..color = const Color(0xFF4A148C).withAlpha((pulse * 60 / i).round())
            ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 4));
    }
    // 胴体（影のかたまり）
    _circ(c, const Color(0xFF0D0020), Offset.zero, 16);
    _circ(c, const Color(0xFF1A0033), Offset.zero, 13);
    // 顔（二つの目と歪んだ口）
    _circ(c, const Color(0xFFAA00FF).withAlpha((pulse * 230).round()),
        const Offset(-5, -3), 4.5);
    _circ(c, const Color(0xFFAA00FF).withAlpha((pulse * 230).round()),
        const Offset(5, -3), 4.5);
    _circ(c, Colors.white.withAlpha((pulse * 200).round()),
        const Offset(-5, -3), 2.5);
    _circ(c, Colors.white.withAlpha((pulse * 200).round()),
        const Offset(5, -3), 2.5);
    // 歪んだ口
    final mouth = Path()
      ..moveTo(-8, 5)
      ..quadraticBezierTo(-4, 10 + sin(t * 6) * 2, 0, 6)
      ..quadraticBezierTo(4, 2, 8, 5);
    c.drawPath(mouth, Paint()
      ..color = const Color(0xFFD500F9).withAlpha((pulse * 200).round())
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2);
    // 触手
    for (int i = 0; i < 4; i++) {
      final a = t + i * pi / 2;
      final r = 15.0 + sin(t * 3 + i) * 4;
      final path = Path()
        ..moveTo(0, 0)
        ..quadraticBezierTo(
            cos(a) * r * 0.5, sin(a) * r * 0.5,
            cos(a) * r, sin(a) * r);
      c.drawPath(path, Paint()
        ..color = const Color(0xFF6A1B9A).withAlpha(150)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 3 + sin(t + i) * 1.5);
    }
  }
}
