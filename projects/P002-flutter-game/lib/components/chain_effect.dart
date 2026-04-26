import 'package:flame/components.dart';
import 'package:flutter/material.dart';

/// チェーン反応演出コンポーネント
/// 発動時にテキスト + 光の波紋アニメーションを表示する
class ChainEffectComponent extends PositionComponent {
  bool _active = false;
  int _chainCount = 0;
  double _elapsed = 0;
  final double _duration = 1.0;
  double _ringScale = 0.2;

  ChainEffectComponent({required Vector2 position}) : super(position: position);

  /// チェーン発動時に呼ぶ
  void trigger(int chainCount) {
    _chainCount = chainCount;
    _active = true;
    _elapsed = 0;
    _ringScale = 0.2;
  }

  @override
  void update(double dt) {
    if (!_active) return;
    _elapsed += dt;
    _ringScale = 0.2 + (_elapsed / _duration) * 2.0;
    if (_elapsed >= _duration) {
      _active = false;
    }
  }

  @override
  void render(Canvas canvas) {
    if (!_active) return;
    final progress = _elapsed / _duration;
    final opacity = (1.0 - progress * progress).clamp(0.0, 1.0);

    // 波紋リング
    final ringColor = _chainColor(_chainCount).withOpacity(opacity * 0.7);
    canvas.drawCircle(
      Offset.zero,
      60 * _ringScale,
      Paint()
        ..color = ringColor
        ..style = PaintingStyle.stroke
        ..strokeWidth = 3.0,
    );
    canvas.drawCircle(
      Offset.zero,
      40 * _ringScale,
      Paint()
        ..color = ringColor.withOpacity(opacity * 0.4)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.0,
    );

    // チェーンテキスト
    final label = _chainLabel(_chainCount);
    final tp = TextPainter(
      text: TextSpan(
        text: label,
        style: TextStyle(
          color: _chainColor(_chainCount).withOpacity(opacity),
          fontSize: 18 + _chainCount * 2.0,
          fontFamily: 'DotGothic16',
          fontWeight: FontWeight.bold,
          shadows: const [
            Shadow(color: Colors.black, blurRadius: 6, offset: Offset(2, 2)),
          ],
        ),
      ),
      textDirection: TextDirection.ltr,
    );
    tp.layout();
    tp.paint(canvas, Offset(-tp.width / 2, -tp.height / 2 - 30));
  }

  String _chainLabel(int count) {
    if (count >= 4) return '⚡ MAX CHAIN!!';
    if (count == 3) return '🔗 CHAIN ×3';
    return '🔗 CHAIN ×2';
  }

  Color _chainColor(int count) {
    if (count >= 4) return const Color(0xFFFFD700);
    if (count == 3) return const Color(0xFFCE93D8);
    return const Color(0xFF64B5F6);
  }
}
