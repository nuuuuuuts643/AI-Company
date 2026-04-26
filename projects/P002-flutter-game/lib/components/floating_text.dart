import 'package:flame/components.dart';
import 'package:flutter/material.dart';
import '../constants/game_constants.dart';

/// ダメージ数値・ステータスポップアップコンポーネント
/// 生成後、上昇しながらフェードアウトして消える
class FloatingTextComponent extends PositionComponent {
  final String text;
  final Color color;
  final double fontSize;

  double _elapsed = 0;
  double _opacity = 1.0;
  final double _duration;
  final double _riseSpeed;

  late final TextPaint _textPaint;

  FloatingTextComponent({
    required this.text,
    required Vector2 position,
    required this.color,
    this.fontSize = 16,
    double? duration,
    double? riseSpeed,
  })  : _duration = duration ?? GameConstants.floatingTextDuration,
        _riseSpeed = riseSpeed ?? GameConstants.floatingTextRiseSpeed,
        super(position: position);

  @override
  Future<void> onLoad() async {
    _textPaint = TextPaint(
      style: TextStyle(
        color: color,
        fontSize: fontSize,
        fontFamily: 'DotGothic16',
        fontWeight: FontWeight.bold,
        shadows: const [
          Shadow(color: Colors.black, blurRadius: 4, offset: Offset(1, 1)),
        ],
      ),
    );
  }

  @override
  void update(double dt) {
    _elapsed += dt;
    final progress = _elapsed / _duration;

    if (progress >= 1.0) {
      removeFromParent();
      return;
    }

    // 上昇
    position.y -= _riseSpeed * dt;

    // フェードアウト（後半60%から始まる）
    if (progress > 0.4) {
      _opacity = 1.0 - ((progress - 0.4) / 0.6);
    }
  }

  @override
  void render(Canvas canvas) {
    if (_opacity <= 0) return;
    canvas.save();
    canvas.translate(0, 0);

    // 不透明度を適用したペイントでテキスト描画
    final paint = Paint()..color = color.withOpacity(_opacity.clamp(0.0, 1.0));
    _textPaint.render(canvas, text, Vector2.zero());

    canvas.restore();
  }
}

/// 弱点クリティカル用の特大テキスト（スケールアニメーション付き）
class CriticalFloatingText extends FloatingTextComponent {
  double _scale = 1.8;

  CriticalFloatingText({
    required String text,
    required Vector2 position,
    required Color color,
  }) : super(
          text: text,
          position: position,
          color: color,
          fontSize: 24,
          riseSpeed: 80.0,
          duration: 1.4,
        );

  @override
  void update(double dt) {
    super.update(dt);
    // スケールが1.0に収束するアニメーション
    if (_scale > 1.0) {
      _scale = (_scale - dt * 4).clamp(1.0, 2.0);
    }
  }

  @override
  void render(Canvas canvas) {
    canvas.save();
    // 中心基準でスケール
    canvas.translate(0, 0);
    canvas.scale(_scale, _scale);
    super.render(canvas);
    canvas.restore();
  }
}
