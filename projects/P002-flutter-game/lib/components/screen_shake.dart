import 'dart:math';
import 'package:flame/camera.dart';
import 'package:flame/components.dart';

/// 画面揺れコントローラー
/// CameraComponent を揺らすことで全オブジェクトが揺れるように見せる
class ScreenShakeController extends Component {
  final CameraComponent camera;

  double _shakeDuration = 0;
  double _shakeIntensity = 0;
  double _shakeTimer = 0;
  final _rng = Random();

  // カメラの元位置を記憶
  Vector2 _baseOffset = Vector2.zero();
  bool _isShaking = false;

  ScreenShakeController({required this.camera});

  /// 揺れを開始する
  /// [intensity] : 揺れの振幅(px)
  /// [duration]  : 揺れの持続秒数
  void shake({required double intensity, required double duration}) {
    _shakeIntensity = intensity;
    _shakeDuration = duration;
    _shakeTimer = 0;
    _isShaking = true;
    _baseOffset = camera.viewfinder.position.clone();
  }

  @override
  void update(double dt) {
    if (!_isShaking) return;

    _shakeTimer += dt;
    final progress = _shakeTimer / _shakeDuration; // 0.0〜1.0

    if (progress >= 1.0) {
      // 揺れ終了: 元位置に戻す
      camera.viewfinder.position = _baseOffset;
      _isShaking = false;
      return;
    }

    // 減衰する揺れ（後半ほど小さく）
    final decay = 1.0 - progress;
    final amplitude = _shakeIntensity * decay;

    final offsetX = (_rng.nextDouble() * 2 - 1) * amplitude;
    final offsetY = (_rng.nextDouble() * 2 - 1) * amplitude * 0.6;

    camera.viewfinder.position = _baseOffset + Vector2(offsetX, offsetY);
  }

  bool get isShaking => _isShaking;
}
