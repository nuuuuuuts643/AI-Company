import 'package:flame/game.dart';
import 'package:flame/components.dart';
import 'package:flame/events.dart';
import 'package:flutter/material.dart';
import '../components/village_map.dart';
import '../components/day_cycle.dart';
import '../components/villager_sprite.dart';
import '../game/game_state.dart';

/// FlameGame メインクラス
/// 村の2Dマップ描画・アニメーションを担当。
/// ゲームロジックは GameStateNotifier (Provider) に委譲。
class VillageGame extends FlameGame with TapCallbacks, HasCollisionDetection {
  final GameStateNotifier gameState;

  late VillageMapComponent _villageMap;
  late DayCycleComponent _dayCycle;
  final List<VillagerSpriteComponent> _villagerSprites = [];

  // コールバック: Flutterレイヤーへのフェーズ変更通知
  final void Function(GamePhase) onPhaseChangeRequest;

  VillageGame({
    required this.gameState,
    required this.onPhaseChangeRequest,
  });

  @override
  Color backgroundColor() => const Color(0xFF1A2E1A);

  @override
  Future<void> onLoad() async {
    await super.onLoad();

    // カメラ設定 (ポートレートiPhone基準: 390×844)
    camera.viewfinder.visibleGameSize = Vector2(390, 600);
    camera.viewfinder.anchor = Anchor.topLeft;

    // 村マップ（一番下のレイヤー）
    _villageMap = VillageMapComponent(
      position: Vector2(0, 60),
      size: Vector2(390, 480),
    );
    world.add(_villageMap);

    // 昼夜サイクルオーバーレイ
    _dayCycle = DayCycleComponent(
      size: Vector2(390, 600),
    );
    world.add(_dayCycle);

    // 初期村人スプライトを生成
    _refreshVillagerSprites();
  }

  @override
  void update(double dt) {
    super.update(dt);

    // 日進行中: タイムラプス演出
    if (gameState.phase == GamePhase.dayProgress) {
      _dayCycle.advanceTime(dt * GameTimings.dayProgressSpeed);
      if (_dayCycle.isNight) {
        // 夜になったらFlutterレイヤーに通知
        onPhaseChangeRequest(GamePhase.nightEvent);
        _dayCycle.reset();
      }
    }
  }

  /// 村人スプライトを GameState に合わせて再生成
  void _refreshVillagerSprites() {
    for (final s in _villagerSprites) {
      s.removeFromParent();
    }
    _villagerSprites.clear();

    final villagers = gameState.run.villagers;
    for (int i = 0; i < villagers.length; i++) {
      final sprite = VillagerSpriteComponent(
        villager: villagers[i],
        position: _villagerPosition(i, villagers.length),
      );
      _villagerSprites.add(sprite);
      world.add(sprite);
    }
  }

  /// 村人の初期配置座標を計算
  Vector2 _villagerPosition(int index, int total) {
    const baseY = 320.0;
    const spacing = 52.0;
    final totalWidth = (total - 1) * spacing;
    final startX = (390 - totalWidth) / 2;
    return Vector2(startX + index * spacing, baseY);
  }

  /// 建物追加時にマップを更新
  void onBuildingAdded() {
    _villageMap.refreshBuildings(gameState.run.buildings);
  }

  /// タスク割り当て後に村人アニメーション更新
  void onTasksAssigned() {
    _refreshVillagerSprites();
  }
}

/// タイムラプス速度定数
class GameTimings {
  static const double dayProgressSpeed = 3.0; // 1秒→3秒分の時間経過
}
