import 'dart:math';
import 'package:flame/game.dart';
import '../constants/element_chart.dart';
import '../constants/game_constants.dart';
import '../models/enemy_data.dart';
import '../models/stage_data.dart';
import '../game/game_state.dart';
import '../components/enemy_component.dart';

// 前方宣言（循環依存を避けるためtypedefを使用）
typedef SpawnEnemyFn = EnemyComponent Function(EnemyData data, int laneIndex);

/// ウェーブ生成・進行システム
class WaveSystem {
  final FlameGame game;
  final GameStateNotifier gameState;

  final _rng = Random();
  double _spawnTimer = 0;
  double _waveIntervalTimer = 0;
  int _spawnIndex = 0;           // このウェーブで次にスポーンする敵のインデックス
  List<_SpawnEntry> _spawnQueue = [];
  bool _waveInProgress = false;

  WaveSystem({required this.game, required this.gameState});

  /// ウェーブ準備（インターバル開始）
  void prepareWave(int waveNumber) {
    _waveInProgress = false;
    _waveIntervalTimer = GameConstants.waveIntervalSeconds;
    _spawnQueue = [];
    _spawnIndex = 0;

    final stageData = _currentStage;
    if (stageData == null) return;

    if (waveNumber > stageData.waves.length) {
      // 全ウェーブ完了 → 勝利
      gameState.endBattle(isVictory: true);
      return;
    }

    final wave = stageData.waves[waveNumber - 1];

    // ---- 難易度スケール ----
    // playerPower（レベル×10 + クリア数×3）に応じて敵ステータスを増強
    // ここではスポーン数に±20%のRNG変動を加える
    final playerPower = gameState.player.totalPower;
    final diffScale = 1.0 + playerPower * 0.04; // 最大でも緩やかに上昇

    // スポーンキューを構築
    double cumulativeDelay = 0;
    for (final waveEnemy in wave.enemies) {
      cumulativeDelay += waveEnemy.spawnDelaySeconds;
      // ±20% のRNG変動をスポーン数に適用
      final rngFactor = 0.8 + _rng.nextDouble() * 0.4; // 0.8〜1.2
      // 難易度スケールを加味した実際のスポーン数（最低1体保証）
      final scaledCount = ((waveEnemy.count * rngFactor * diffScale).round()).clamp(1, waveEnemy.count + 3);
      for (int i = 0; i < scaledCount; i++) {
        final laneIndex = waveEnemy.laneIndex < 0
            ? (i % 3) // ランダム → 均等に割り振り
            : waveEnemy.laneIndex;
        _spawnQueue.add(_SpawnEntry(
          enemyType: waveEnemy.type,
          laneIndex: laneIndex,
          delay: cumulativeDelay + i * GameConstants.enemySpawnInterval,
        ));
      }
    }
    // 遅延順にソート
    _spawnQueue.sort((a, b) => a.delay.compareTo(b.delay));
  }

  /// 毎フレーム更新
  void update(double dt) {
    final battle = gameState.battle;
    if (battle == null) return;
    if (battle.isDefeated) return;

    if (!_waveInProgress) {
      // インターバルカウントダウン
      _waveIntervalTimer -= dt;
      if (_waveIntervalTimer <= 0) {
        _waveInProgress = true;
        _spawnTimer = 0;
        if (battle.battlePhase == BattlePhase.preparing) {
          // ignore: invalid_use_of_protected_member
          battle.battlePhase = BattlePhase.waving;
        }
      }
      return;
    }

    // スポーンタイマー更新
    _spawnTimer += dt;

    // キューから時間が来たものをスポーン
    while (_spawnIndex < _spawnQueue.length &&
        _spawnQueue[_spawnIndex].delay <= _spawnTimer) {
      _spawnEntry(_spawnQueue[_spawnIndex]);
      _spawnIndex++;
    }

    // このウェーブのスポーンが全部終わった → ウェーブクリア監視へ
    // （全敵が倒されたかは game 側から監視）
    if (_spawnIndex >= _spawnQueue.length) {
      // 敵が残っているか？（game側の _enemies リストで判断するため別途チェック不要）
      // ここでは次ウェーブ進行はgame.update()からadvanceWave()を呼ぶ設計
    }
  }

  /// 現在ウェーブのすべての敵がスポーン済みか
  bool get isAllSpawned =>
      _spawnIndex >= _spawnQueue.length && _waveInProgress;

  /// ウェーブ開始前インターバル中か
  bool get isInInterval => !_waveInProgress && _waveIntervalTimer > 0;

  /// インターバルの残り秒数
  double get intervalCountdown => _waveIntervalTimer.clamp(0, double.infinity);

  /// 次ウェーブで登場する敵の種類（予告用）
  Set<EnemyType> get nextWaveEnemyTypes =>
      _spawnQueue.map((e) => e.enemyType).toSet();

  /// レーン別スポーン数（ウェーブ予告用）
  Map<int, int> get nextWaveEnemyCountPerLane {
    final counts = <int, int>{};
    for (final entry in _spawnQueue) {
      counts[entry.laneIndex] = (counts[entry.laneIndex] ?? 0) + 1;
    }
    return counts;
  }

  /// 次ウェーブの主要属性（最多属性）
  ElementType? get nextWaveMainElement {
    if (_spawnQueue.isEmpty) return null;
    final counts = <ElementType, int>{};
    for (final e in _spawnQueue) {
      final elem = EnemyMaster.get(e.enemyType).element;
      counts[elem] = (counts[elem] ?? 0) + 1;
    }
    return counts.entries.reduce((a, b) => a.value >= b.value ? a : b).key;
  }

  void _spawnEntry(_SpawnEntry entry) {
    final data = EnemyMaster.get(entry.enemyType);
    if (game is SpawnableGame) {
      (game as SpawnableGame).spawnEnemy(data, entry.laneIndex);
    }
  }

  StageData? get _currentStage {
    final id = gameState.selectedStageId;
    if (id == null) return null;
    return StageMaster.getById(id);
  }
}

class _SpawnEntry {
  final EnemyType enemyType;
  final int laneIndex;
  final double delay;

  _SpawnEntry({
    required this.enemyType,
    required this.laneIndex,
    required this.delay,
  });
}

/// spawnEnemyメソッドを持つゲームクラスの抽象（OctoBattleGameが実装する）
abstract class SpawnableGame {
  EnemyComponent spawnEnemy(EnemyData data, int laneIndex);
}
