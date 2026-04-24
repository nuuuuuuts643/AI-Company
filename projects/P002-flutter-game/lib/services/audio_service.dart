import 'package:flame_audio/flame_audio.dart';

/// ゲーム内BGM・SE管理サービス
/// FlameAudio（flame_audio パッケージ）を薄くラップする。
/// アセットは assets/audio/ に配置すること。
class AudioService {
  static const double bgmVolume = 0.7;
  static const double seVolume = 1.0;

  /// 現在再生中のBGM名
  String? _currentBgm;
  bool _muted = false;

  bool get isMuted => _muted;

  // ---- BGM ----

  /// BGMを再生（ループ）。同じBGMが既に流れている場合はスキップ。
  Future<void> playBGM(String name) async {
    if (_currentBgm == name) return;
    await stopBGM();
    if (_muted) return;
    try {
      await FlameAudio.bgm.play('$name.wav', volume: bgmVolume);
      _currentBgm = name;
    } catch (_) {
      // アセット未配置の場合はサイレント失敗
    }
  }

  /// BGM停止
  Future<void> stopBGM() async {
    try {
      await FlameAudio.bgm.stop();
    } catch (_) {}
    _currentBgm = null;
  }

  /// BGM一時停止
  Future<void> pauseBGM() async {
    try {
      await FlameAudio.bgm.pause();
    } catch (_) {}
  }

  /// BGM再開
  Future<void> resumeBGM() async {
    try {
      await FlameAudio.bgm.resume();
    } catch (_) {}
  }

  // ---- SE ----

  /// SEを再生（重ね再生可能）
  Future<void> playSE(String name) async {
    if (_muted) return;
    try {
      await FlameAudio.play('$name.wav', volume: seVolume);
    } catch (_) {
      // アセット未配置の場合はサイレント失敗
    }
  }

  // ---- プリロード ----

  /// よく使うSEを事前にキャッシュに読み込む（ロード時間短縮）
  Future<void> preload() async {
    try {
      await FlameAudio.audioCache.loadAll([
        'hit_se.wav',
        'chain_se.wav',
        'purchase_se.wav',
        'levelup_se.wav',
        'victory.wav',
        'defeat.wav',
      ]);
    } catch (_) {}
  }

  // ---- ミュート ----

  void setMuted(bool value) {
    _muted = value;
    if (_muted) {
      stopBGM();
    }
  }

  void toggleMute() => setMuted(!_muted);

  // ---- 音量調整 ----

  Future<void> setBGMVolume(double vol) async {
    try {
      FlameAudio.bgm.audioPlayer.setVolume(vol.clamp(0.0, 1.0));
    } catch (_) {}
  }
}

// ---- SEの名前定数（タイポ防止） ----

class AudioSE {
  static const String hit       = 'hit_se';
  static const String chain     = 'chain_se';
  static const String purchase  = 'purchase_se';
  static const String levelUp   = 'levelup_se';
  static const String victory   = 'victory';
  static const String defeat    = 'defeat';
}

class AudioBGM {
  static const String battle    = 'battle_bgm';
  static const String hub       = 'hub_bgm';
}
