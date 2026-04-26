import 'package:flame/game.dart';
import 'package:flame/components.dart';
import 'package:flame/events.dart';
import 'package:flutter/material.dart' hide Route;
import 'package:flutter/services.dart';
import '../components/animation_controller.dart';
import '../components/hd2d_background.dart';
import '../components/enemy_component.dart';
import '../components/unit_component.dart';
import '../components/lighting_layer.dart';
import '../components/particle_system.dart';
import '../components/floating_text.dart';
import '../components/screen_shake.dart';
import '../components/chain_effect.dart';
import '../components/attack_effect.dart';
import '../components/projectile_component.dart';
import '../components/terrain_component.dart';
import '../components/field_overlay.dart';
import '../constants/game_constants.dart';
import '../constants/element_chart.dart';
import '../models/card_data.dart';
import '../models/enemy_data.dart';
import '../models/unit_data.dart';
import '../models/stage_data.dart';
import '../models/terrain_data.dart';
import '../services/audio_service.dart';
import '../systems/battle_system.dart' show BattleSystem, AuraType;
import '../systems/wave_system.dart';
import '../systems/card_system.dart';
import '../systems/chain_system.dart';
import '../systems/loot_system.dart';
import 'game_state.dart';

/// FlameGame メインクラス
/// 描画・アニメーション・当たり判定を担当。
/// ロジック状態は GameStateNotifier に委譲する。
class OctoBattleGame extends FlameGame
    with TapCallbacks, DragCallbacks, HasCollisionDetection
    implements SpawnableGame {
  final GameStateNotifier gameState;
  final AudioService _audio;

  // ---- システム ----
  late final BattleSystem battleSystem;
  late final WaveSystem waveSystem;
  late final CardSystem cardSystem;
  late final ChainSystem chainSystem;
  late final LootSystem lootSystem;

  // ---- コンポーネント ----
  late final HD2DBackground _background;
  late final LightingLayer _lighting;
  late final ScreenShakeController _shakeController;
  late final ChainEffectComponent _chainEffect;
  late final GameAnimationController _animController;
  late final TextComponent _waveLabel;
  late final TextComponent _wallHpText;

  // フィールドオーバーレイ（ウェーブ予告制御用）
  late final FieldOverlayComponent _fieldOverlay;
  bool _wavePreviewShown = false;

  // フィールド上のアクティブコンポーネント
  final List<EnemyComponent> _enemies = [];
  final List<UnitComponent> _units = [];

  // 陣形グリッド: (col, row) → UnitComponent
  final Map<(int, int), UnitComponent> _grid = {};

  // 地形リスト（敵フィールドに配置した障害物）
  final List<TerrainEntry> _terrains = [];

  // カード配置インタラクション
  String? _draggingCardId;
  Vector2? _dragPosition;

  // フェーズ制御フラグ
  bool _waveClearHandled = false;
  bool _resultHandled = false;
  bool _waveStarted = false; // battle が利用可能になったら最初のウェーブを開始
  bool _formationPhase = true; // 配備フェーズ中はウェーブを開始しない

  // ウェーブ内の城壁到達数（0=PERFECT）
  int _waveBreachCount = 0;
  int get lastWaveBreachCount => _waveBreachCount;

  // コールバック（Flutterレイヤーへ通知）
  final void Function(GamePhase) onPhaseChangeRequest;
  final void Function(String cardId, int laneIndex) onCardPlaced;
  final void Function(int chainCount, double damage) onChainTriggered;
  final void Function(String bossName, int maxHp, int currentHp)? onBossHpUpdate;
  final void Function(int damage)? onWallDamaged;

  // ボス追跡
  EnemyComponent? _activeBoss;

  // ---- コマンダースキル ----
  final void Function(double progress)? onCommanderSkillReady;

  OctoBattleGame({
    required this.gameState,
    required this.onPhaseChangeRequest,
    required this.onCardPlaced,
    required this.onChainTriggered,
    this.onBossHpUpdate,
    this.onWallDamaged,
    this.onCommanderSkillReady,
    required AudioService audio,
  }) : _audio = audio;

  @override
  Color backgroundColor() => const Color(0xFF080818);

  @override
  Future<void> onLoad() async {
    await super.onLoad();

    // カメラ：固定解像度 390×844
    camera.viewfinder.visibleGameSize =
        Vector2(GameConstants.gameWidth, GameConstants.gameHeight);
    camera.viewfinder.anchor = Anchor.topLeft;

    // システム初期化
    battleSystem = BattleSystem(
      gameState: gameState,
      onAuraApplied: _onAuraApplied,
      onAttackVisual: (unit, target, damage, isWeakness) {
        _onUnitAttackVisual(
          unit: unit,
          target: target,
          damage: damage,
          isWeakness: isWeakness,
        );
      },
      onSkillProc: (text, color, pos) {
        _spawnFloatingText(pos, text, color, fontSize: 13);
      },
    );
    waveSystem = WaveSystem(game: this, gameState: gameState);
    cardSystem = CardSystem(gameState: gameState);
    chainSystem = ChainSystem(gameState: gameState);
    lootSystem = LootSystem(gameState: gameState);

    // 背景（最下層）
    _background = HD2DBackground(
      size: Vector2(GameConstants.gameWidth, GameConstants.gameHeight),
      backgroundId: _stageData?.backgroundId ?? 'bg_forest',
    );
    world.add(_background);

    // 光源レイヤー（背景の上）
    _lighting = LightingLayer(
      size: Vector2(GameConstants.gameWidth, GameConstants.gameHeight),
    );
    world.add(_lighting);

    // 画面揺れコントローラ
    _shakeController = ScreenShakeController(camera: camera);
    world.add(_shakeController);

    // アニメーションコントローラ
    _animController = GameAnimationController(shakeController: _shakeController);
    world.add(_animController);

    // チェーン演出
    _chainEffect = ChainEffectComponent(
      position: Vector2(GameConstants.gameWidth / 2, GameConstants.gameHeight / 2),
    );
    world.add(_chainEffect);

    // オーディオ初期化
    await _audio.preload();
    await _audio.playBGM(AudioBGM.battle);

    // レーン区切り線（視覚ガイド）
    _addLaneGuides();

    // HUDはFlutterレイヤー（battle_screen.dart）に統合済み。Flameレイヤーのテキストは不要。
    _waveLabel = TextComponent(text: '');
    _wallHpText = TextComponent(text: '');

    // 最初のウェーブは battle が初期化されてから update() で開始する

    // ステージ固有の地形をフィールドに配置
    _spawnStageTerrain();
  }

  /// ステージデータの地形を永続配置する
  void _spawnStageTerrain() {
    final stage = _stageData;
    if (stage == null) return;
    for (final entry in stage.terrainLayout) {
      final laneLeft = GameConstants.laneWidth * entry.laneIndex;
      final terrain = TerrainEntry(
        type: entry.type,
        laneIndex: entry.laneIndex,
        y: entry.y,
        permanent: true,
      );
      _terrains.add(terrain);
      world.add(TerrainComponent(
        terrain: terrain,
        position: Vector2(laneLeft, entry.y),
      ));
    }
  }

  @override
  void update(double dt) {
    super.update(dt);

    final battle = gameState.battle;
    if (battle == null) return;

    // battle が初めて利用可能になったら最初のウェーブを開始
    // （配備フェーズが終わるまで待機）
    if (!_waveStarted && !_formationPhase) {
      _waveStarted = true;
      waveSystem.prepareWave(battle.currentWave);
    }

    // マナ更新
    gameState.tickMana(dt);

    // ウェーブ予告表示（インターバル中のみ）
    if (waveSystem.isInInterval && !_wavePreviewShown) {
      _wavePreviewShown = true;
      _fieldOverlay.showWavePreview(waveSystem.nextWaveEnemyCountPerLane);
    } else if (!waveSystem.isInInterval) {
      if (_wavePreviewShown) {
        _wavePreviewShown = false;
        _fieldOverlay.hideWavePreview();
      }
    }

    // ウェーブシステム更新
    waveSystem.update(dt);

    // バトルシステム: ユニット対敵のオートバトル
    battleSystem.update(dt, _units, _enemies);

    // 地形エフェクト（敵への速度・ダメージ・誘導）
    _applyTerrainEffects(dt);

    // 城壁到達判定（下端に到達）
    for (final enemy in List.from(_enemies)) {
      if (enemy.position.y >= GameConstants.wallY) {
        _onEnemyReachedWall(enemy);
      }
    }

    // デッドユニット除去（グリッドからも削除）
    _units.removeWhere((u) {
      if (!u.unitInstance.isAlive) {
        u.removeFromParent();
        _grid.removeWhere((_, v) => identical(v, u));
        return true;
      }
      return false;
    });

    // デッド敵をリストから除去（EnemyComponentの死亡アニメーション完了後にonDefeatedで本体除去）
    _enemies.removeWhere((e) => !e.isAlive);

    // ウェーブクリア判定（全スポーン完了 & 敵全滅 & まだ処理してない）
    if (waveSystem.isAllSpawned &&
        _enemies.isEmpty &&
        !_waveClearHandled &&
        !battle.isDefeated) {
      _waveClearHandled = true;
      onPhaseChangeRequest(GamePhase.waveShop);
    }

    // ボスHP更新（Flutterレイヤーに通知）
    if (_activeBoss != null) {
      if (!_activeBoss!.isAlive) {
        _activeBoss = null;
        onBossHpUpdate?.call('', 0, 0); // ボス消滅
      } else {
        onBossHpUpdate?.call(
          _activeBoss!.enemyData.name,
          _activeBoss!.enemyData.maxHp,
          _activeBoss!.currentHp,
        );
      }
    }

    // HUD更新
    _updateHUD();

    // 敗北判定
    if (battle.isDefeated && !_resultHandled) {
      _resultHandled = true;
      _audio.playSE(AudioSE.defeat);
      onPhaseChangeRequest(GamePhase.result);
    }
  }

  // ---- 敵スポーン（WaveSystemから呼ばれる） ----

  EnemyComponent spawnEnemy(EnemyData data, int laneIndex) {
    final laneX = _laneX(laneIndex);
    final enemy = EnemyComponent(
      enemyData: data,
      position: Vector2(laneX, GameConstants.enemySpawnY),
      onDefeated: (comp) => _onEnemyDefeated(comp),
    );
    _enemies.add(enemy);
    world.add(enemy);

    // ボスは登場演出（スライドイン + ScreenShake）
    if (data.type.isBoss) {
      final spawnPos = Vector2(laneX, GameConstants.enemySpawnY);
      _lighting.addBossAura(spawnPos);
      _animController.playBossEntrance(enemy, spawnPos);
      _activeBoss = enemy;
      onBossHpUpdate?.call(data.name, data.maxHp, data.maxHp);
    }
    return enemy;
  }

  // ---- カード配置（CardSystemから呼ばれる） ----

  void placeUnit(CardData card, int col, {int row = -1}) {
    // 行が指定されていない場合は空いてる前列から埋める
    if (row < 0) {
      row = _findFrontEmptyRow(col);
      if (row < 0) return; // 満杯
    }

    if (_grid.containsKey((col, row))) return; // 占有済み

    final laneX = _laneX(col);
    final placeY = _gridCellCenterY(row);

    final instance = cardSystem.createUnitInstance(card, col, rowIndex: row);
    final unitComp = UnitComponent(
      unitInstance: instance,
      position: Vector2(laneX - 17, placeY - 21),
      onAttack: _onUnitAttack,
      laneHasEnemies: (laneIdx) =>
          _enemies.any((e) => e.isAlive && e.laneIndex == laneIdx),
    );
    _grid[(col, row)] = unitComp;
    _units.add(unitComp);
    world.add(unitComp);

    _spawnPlacementParticles(Vector2(laneX, placeY), card.element);
    HapticFeedback.mediumImpact();
    if (card.element == ElementType.light || card.element == ElementType.fire) {
      _lighting.addUnitLight(Vector2(laneX, placeY), card.element);
    }
  }

  int _findFrontEmptyRow(int col) {
    for (int r = 0; r < GameConstants.gridRows; r++) {
      if (!_grid.containsKey((col, r))) return r;
    }
    return -1; // 満杯
  }

  double _gridCellCenterY(int row) {
    return GameConstants.gridTop +
        GameConstants.cellHeight * row +
        GameConstants.cellHeight / 2;
  }

  void castSpell(CardData card, int laneIndex) {
    final targetX = _laneX(laneIndex);
    final targetY = GameConstants.fieldTop +
        (GameConstants.fieldBottom - GameConstants.fieldTop) / 2;

    // ダメージ計算と適用
    for (final enemy in List.from(_enemies)) {
      final dx = (enemy.position.x - targetX).abs();
      if (card.aoeRadius > 0) {
        if (dx < card.aoeRadius) {
          _applySpellDamage(card, enemy);
        }
      } else {
        if (enemy.laneIndex == laneIndex) {
          _applySpellDamage(card, enemy);
        }
      }
    }

    // 魔法エフェクト
    _spawnSpellEffect(Vector2(targetX, targetY), card.element, card.aoeRadius);
    HapticFeedback.heavyImpact();
  }

  void placeTrap(CardData card, int laneIndex, {double? dropY}) {
    if (card.terrainType != null) {
      _placeTerrain(card, laneIndex, dropY: dropY);
      return;
    }
    final trapX = _laneX(laneIndex);
    final trapY = dropY ??
        (GameConstants.fieldTop +
            (GameConstants.fieldBottom - GameConstants.fieldTop) * 0.4);
    _spawnTrapVisual(Vector2(trapX, trapY), card.element);
  }

  void _placeTerrain(CardData card, int laneIndex, {double? dropY}) {
    final terrainType = card.terrainType!;
    final terrainY = dropY?.clamp(GameConstants.fieldTop, GameConstants.gridTop - 50) ??
        (GameConstants.fieldTop + 80.0 + laneIndex * 30.0);

    final entry = TerrainEntry(
      type: terrainType,
      laneIndex: laneIndex,
      y: terrainY,
    );
    _terrains.add(entry);

    // 視覚コンポーネントをフィールドに追加
    final laneLeft = GameConstants.laneWidth * laneIndex;
    final comp = TerrainComponent(
      terrain: entry,
      position: Vector2(laneLeft, terrainY),
    );
    world.add(comp);

    // エフェクト
    _spawnPlacementParticles(Vector2(_laneX(laneIndex), terrainY + 25), card.element);
    _spawnFloatingText(
      Vector2(_laneX(laneIndex), terrainY - 20),
      '${terrainType.emoji} ${terrainType.label}設置！',
      Color(card.element.colorValue),
      fontSize: 13,
    );
  }

  void _applyTerrainEffects(double dt) {
    // 期限切れ地形を除去
    _terrains.removeWhere((t) {
      t.tick(dt);
      return t.expired;
    });

    for (final terrain in _terrains) {
      for (final enemy in _enemies) {
        if (!enemy.isAlive) continue;
        if (!terrain.overlapsEnemy(enemy.position.y)) continue;
        if (enemy.laneIndex != terrain.laneIndex) continue;

        switch (terrain.type) {
          case TerrainType.mountain:
            // 隣列へ誘導（左優先、端なら右）
            final targetLane = terrain.laneIndex > 0
                ? terrain.laneIndex - 1
                : terrain.laneIndex < 2
                    ? terrain.laneIndex + 1
                    : terrain.laneIndex;
            final targetX = _laneX(targetLane);
            final dx = targetX - enemy.position.x;
            final slide = dx.sign * (dx.abs().clamp(0, 160.0 * dt));
            enemy.position.x += slide;
            break;
          case TerrainType.river:
            enemy.applySlow(factor: 0.4, duration: 1.2);
            break;
          case TerrainType.swamp:
            enemy.applyBurn(damagePerSec: 15.0, duration: 1.5);
            break;
        }
      }
    }
  }

  /// ウェーブクリア後に地形をリセット
  void clearTerrains() {
    _terrains.clear();
    // TerrainComponentはworld.childrenから自動削除されないので手動対応
    world.children.whereType<TerrainComponent>().toList().forEach((c) => c.removeFromParent());
  }

  // ---- イベントハンドラ ----

  void _onEnemyDefeated(EnemyComponent enemy) {
    final data = enemy.enemyData;
    gameState.addScore(data.scoreValue);

    // ドロップ判定
    final drop = lootSystem.rollDrop(data);
    if (drop != null) {
      gameState.addDroppedMaterial(drop.materialId, drop.count);
      _spawnCoinEffect(enemy.position, drop.count);
    }

    // 撃破SE
    _audio.playSE(AudioSE.hit);

    // ボス撃破
    if (data.type.isBoss) {
      _shakeController.shake(
        intensity: GameConstants.screenShakeIntensityBoss,
        duration: GameConstants.screenShakeDuration,
      );
      HapticFeedback.heavyImpact();
      _spawnBossDeathExplosion(enemy.position);
      _lighting.flashWhite();
    } else if (data.isElite) {
      _shakeController.shake(
        intensity: GameConstants.screenShakeIntensityNormal,
        duration: 0.2,
      );
    }

    // FloatingText: スコア
    _spawnFloatingScore(enemy.position, data.scoreValue);
  }

  void _onEnemyReachedWall(EnemyComponent enemy) {
    final dmg = enemy.enemyData.attackPower;
    gameState.damageWall(dmg);
    _enemies.remove(enemy);
    enemy.removeFromParent();
    _waveBreachCount++;

    // 城壁ダメージ演出（強め）
    _shakeController.shake(
      intensity: GameConstants.screenShakeIntensityNormal * 1.6,
      duration: 0.35,
    );
    HapticFeedback.heavyImpact();
    _spawnFloatingText(
      Vector2(GameConstants.gameWidth / 2, GameConstants.wallY - 30),
      '城壁 -$dmg',
      const Color(0xFFEF5350),
      fontSize: 26,
    );
    onWallDamaged?.call(dmg);
  }

  /// BattleSystemからのコールバック: 視覚エフェクトのみ（ダメージは適用済み）
  void _onUnitAttackVisual({
    required UnitComponent unit,
    required EnemyComponent target,
    required int damage,
    required bool isWeakness,
  }) {
    final attacker = unit.unitInstance;
    final unitCenter = unit.position + Vector2(17, 21);
    final targetCenter = target.position + Vector2(18, 22);
    final elemColor = Color(attacker.element.colorValue);
    final isMelee = attacker.attackRange <= 90;

    if (isMelee) {
      final dir = (targetCenter - unitCenter);
      final angle = dir.angleTo(Vector2(1, 0)) * -1;
      world.add(SlashEffectComponent(
        position: unitCenter + Vector2(-25, -25),
        color: elemColor,
        angle: angle,
      ));
      if (attacker.element == ElementType.earth || attacker.element == ElementType.light) {
        world.add(MagicCircleEffect(position: unitCenter + Vector2(-25, 10), color: elemColor));
      }
    } else {
      world.add(MagicCircleEffect(position: unitCenter + Vector2(-25, 5), color: elemColor));
      final vel = (targetCenter - unitCenter).normalized() * 350;
      world.add(ProjectileComponent(
        position: unitCenter.clone(),
        velocity: vel,
        element: attacker.element,
        damage: 0,
        target: target,
        maxLifespan: 0.5,
      ));
    }

    world.add(ImpactEffect(
      position: targetCenter + Vector2(-24, -24),
      color: elemColor,
      style: impactStyleFor(attacker.element),
    ));

    // チェーン判定（ボーナスダメージも適用）
    final chainResult = chainSystem.checkChain(
      attackerElement: attacker.element,
      damage: damage.toDouble(),
    );

    if (chainResult != null && chainResult.chainCount >= 2 && target.isAlive) {
      final bonusDmg = (chainResult.totalDamage - damage).round().clamp(0, 9999);
      if (bonusDmg > 0) target.takeDamage(bonusDmg);
    }

    final displayDmg = chainResult?.totalDamage.round() ?? damage;

    if (isWeakness) {
      _spawnFloatingText(
        target.position + Vector2(-20, -30),
        '⚡ $displayDmg',
        const Color(0xFFFFD700),
        fontSize: 20,
      );
      HapticFeedback.lightImpact();
    } else if (chainResult != null && chainResult.chainCount >= 2) {
      _spawnFloatingText(
        target.position + Vector2(-20, -30),
        '🔗 $displayDmg',
        const Color(0xFFCE93D8),
        fontSize: 20,
      );
    } else {
      _spawnFloatingText(
        target.position + Vector2(-10, -20),
        '$damage',
        const Color(0xFFFFFFFF),
        fontSize: 16,
      );
    }

    if (chainResult != null && chainResult.chainCount >= 2) {
      _chainEffect.trigger(chainResult.chainCount);
      _animController.playChainRipple(target.position, chainResult.chainCount);
      _audio.playSE(AudioSE.chain);
      gameState.recordChain(ChainRecord(
        firstElement: chainResult.firstElement,
        secondElement: attacker.element,
        chainCount: chainResult.chainCount,
        damage: chainResult.totalDamage,
      ));
      onChainTriggered(chainResult.chainCount, chainResult.totalDamage);
      if (chainResult.chainCount >= 3) {
        _shakeController.shake(intensity: 3.0, duration: 0.2);
      }
    }

    if (target.isArmorJustBroken) {
      _spawnFloatingText(
        target.position + Vector2(0, -50),
        '🛡 アーマー破壊！',
        const Color(0xFFFF8F00),
        fontSize: 14,
      );
      HapticFeedback.mediumImpact();
    }
  }

  void _onUnitAttack({
    required UnitInstance attacker,
    required EnemyComponent target,
    required int damage,
    required bool isWeakness,
    required bool isChain,
  }) {
    // ---- 攻撃エフェクト ----
    // UnitComponentの位置を取得
    final unitComp = _units.cast<UnitComponent?>().firstWhere(
      (u) => u?.unitInstance == attacker,
      orElse: () => null,
    );
    if (unitComp != null) {
      final unitCenter = unitComp.position + Vector2(17, 21);
      final targetCenter = target.position + Vector2(18, 22);
      final elemColor = Color(attacker.element.colorValue);
      final isMelee = attacker.attackRange <= 90;

      if (isMelee) {
        // 近接：斬撃エフェクト（ユニット前方）
        final dir = (targetCenter - unitCenter);
        final angle = dir.angleTo(Vector2(1, 0)) * -1;
        world.add(SlashEffectComponent(
          position: unitCenter + Vector2(-25, -25),
          color: elemColor,
          angle: angle,
        ));
        // 詠唱陣（土・光は魔法寄り）
        if (attacker.element == ElementType.earth ||
            attacker.element == ElementType.light) {
          world.add(MagicCircleEffect(
            position: unitCenter + Vector2(-25, 10),
            color: elemColor,
          ));
        }
      } else {
        // 遠距離・魔法：詠唱陣 + 飛翔プロジェクタイル
        world.add(MagicCircleEffect(
          position: unitCenter + Vector2(-25, 5),
          color: elemColor,
        ));
        // 速度ベクトル（ユニット→ターゲット）
        final vel = (targetCenter - unitCenter).normalized() * 350;
        world.add(ProjectileComponent(
          position: unitCenter.clone(),
          velocity: vel,
          element: attacker.element,
          damage: 0, // ダメージはすでに適用済み（視覚専用）
          target: target,
          maxLifespan: 0.5,
        ));
      }

      // ヒット時インパクト（ターゲット位置）
      world.add(ImpactEffect(
        position: targetCenter + Vector2(-24, -24),
        color: elemColor,
        style: impactStyleFor(attacker.element),
      ));
    }

    // チェーン判定
    final chainResult = chainSystem.checkChain(
      attackerElement: attacker.element,
      damage: damage.toDouble(),
    );

    final finalDamage = chainResult?.totalDamage.round() ?? damage;
    target.takeDamage(finalDamage);

    // FloatingText（弱点は大きく・金色で表示）
    if (isWeakness) {
      _spawnFloatingText(
        target.position + Vector2(-20, -30),
        '⚡ $finalDamage',
        const Color(0xFFFFD700),
        fontSize: 20,
      );
      HapticFeedback.lightImpact();
    } else if (isChain) {
      _spawnFloatingText(
        target.position + Vector2(-20, -30),
        '🔗 $finalDamage',
        const Color(0xFFCE93D8),
        fontSize: 20,
      );
    } else {
      _spawnFloatingText(
        target.position + Vector2(-10, -20),
        '$finalDamage',
        const Color(0xFFFFFFFF),
        fontSize: 16,
      );
    }

    // チェーン演出
    if (chainResult != null && chainResult.chainCount >= 2) {
      _chainEffect.trigger(chainResult.chainCount);
      _animController.playChainRipple(target.position, chainResult.chainCount);
      _audio.playSE(AudioSE.chain);
      gameState.recordChain(ChainRecord(
        firstElement: chainResult.firstElement,
        secondElement: attacker.element,
        chainCount: chainResult.chainCount,
        damage: chainResult.totalDamage,
      ));
      onChainTriggered(chainResult.chainCount, chainResult.totalDamage);

      if (chainResult.chainCount >= 3) {
        _shakeController.shake(intensity: 3.0, duration: 0.2);
      }
    }

    // アーマー破壊演出
    if (target.isArmorJustBroken) {
      _spawnFloatingText(
        target.position + Vector2(0, -50),
        '🛡 アーマー破壊！',
        const Color(0xFFFF8F00),
        fontSize: 14,
      );
      HapticFeedback.mediumImpact();
    }
  }

  // ---- オーラ（バフ）エフェクト ----

  void _onAuraApplied(
      UnitComponent healer, UnitComponent target, AuraType aura) {
    final healerCenter = healer.position + Vector2(17, 21);
    final targetCenter = target.position + Vector2(17, 21);

    switch (aura) {
      case AuraType.heal:
        // 黄金のビームが癒す
        world.add(_BuffBeam(
          from: healerCenter,
          to: targetCenter,
          color: const Color(0xFFFFD700),
        ));
        // ターゲットに回復数値フロート
        final healAmt = (healer.unitInstance.attack * 1.5).round();
        _spawnFloatingText(
          targetCenter + Vector2(-10, -30),
          '💛 +$healAmt',
          const Color(0xFFFFD700),
          fontSize: 15,
        );
        break;
      case AuraType.atkSpeed:
        // 緑のビームで加速
        world.add(_BuffBeam(
          from: healerCenter,
          to: targetCenter,
          color: const Color(0xFF66BB6A),
        ));
        _spawnFloatingText(
          targetCenter + Vector2(-10, -28),
          '⚡ SPD+',
          const Color(0xFF66BB6A),
          fontSize: 13,
        );
        break;
      case AuraType.atkPower:
        world.add(_BuffBeam(
          from: healerCenter,
          to: targetCenter,
          color: const Color(0xFFFF8F00),
        ));
        break;
    }
  }

  // ---- パーティクル・エフェクトヘルパー ----

  void _spawnPlacementParticles(Vector2 pos, ElementType element) {
    final color = Color(element.colorValue);
    world.add(BurstParticleComponent(
      position: pos,
      color: color,
      count: 12,
      speed: 80.0,
      lifespan: 0.5,
    ));
  }

  void _spawnSpellEffect(Vector2 pos, ElementType element, int radius) {
    final color = Color(element.colorValue);
    world.add(BurstParticleComponent(
      position: pos,
      color: color,
      count: GameConstants.particleCountExplosion,
      speed: 150.0,
      lifespan: GameConstants.particleLifespan,
      radius: radius > 0 ? radius.toDouble() : 60.0,
    ));
    _shakeController.shake(
      intensity: GameConstants.screenShakeIntensityNormal,
      duration: 0.2,
    );
  }

  void _spawnTrapVisual(Vector2 pos, ElementType element) {
    final color = Color(element.colorValue).withOpacity(0.6);
    world.add(BurstParticleComponent(
      position: pos,
      color: color,
      count: 8,
      speed: 40.0,
      lifespan: 0.4,
    ));
  }

  void _spawnCoinEffect(Vector2 pos, int count) {
    world.add(CoinParticleComponent(
      position: pos,
      count: count.clamp(1, 6),
    ));
  }

  void _spawnBossDeathExplosion(Vector2 pos) {
    for (int i = 0; i < 3; i++) {
      Future.delayed(Duration(milliseconds: i * 180), () {
        world.add(BurstParticleComponent(
          position: pos + Vector2((i - 1) * 30.0, 0),
          color: const Color(0xFFFF6F00),
          count: GameConstants.particleCountExplosion,
          speed: 200.0,
          lifespan: 1.2,
        ));
      });
    }
  }

  void _spawnFloatingScore(Vector2 pos, int score) {
    _spawnFloatingText(pos + Vector2(0, -40), '+$score', const Color(0xFF69F0AE), fontSize: 18);
  }

  void _spawnFloatingText(
    Vector2 pos,
    String text,
    Color color, {
    double fontSize = 16,
  }) {
    world.add(FloatingTextComponent(
      text: text,
      position: pos.clone(),
      color: color,
      fontSize: fontSize,
    ));
  }

  void _applySpellDamage(CardData card, EnemyComponent enemy) {
    final mult = battleSystem.calculateElementMultiplier(
      card.element,
      enemy.enemyData.element,
    );
    final dmg = (card.baseAttack * mult).round();
    enemy.takeDamage(dmg);
    _spawnFloatingText(
      enemy.position + Vector2(0, -30),
      '$dmg',
      Color(card.element.colorValue),
      fontSize: 18,
    );
  }

  // ---- ユーティリティ ----

  double _laneX(int laneIndex) {
    return GameConstants.fieldLeft +
        GameConstants.laneWidth * laneIndex +
        GameConstants.laneWidth / 2;
  }

  StageData? get _stageData {
    final id = gameState.selectedStageId;
    if (id == null) return null;
    return StageMaster.getById(id);
  }

  void _addLaneGuides() {
    _fieldOverlay = FieldOverlayComponent();
    world.add(_fieldOverlay);
  }

  void _updateHUD() {
    final b = gameState.battle;
    if (b == null) return;
    _waveLabel.text =
        'WAVE ${b.currentWave} / ${_stageData?.waves.length ?? 5}';
    _wallHpText.text = '城壁 HP: ${b.wallHp}';
  }

  // ---- 外部から呼び出す（カードUI→ゲーム） ----

  /// コマンダースキル発動（全レーンに属性バーストを放つ）
  void castCommanderSkill() {
    const lanes = 3;
    for (int i = 0; i < lanes; i++) {
      final laneX = _laneX(i);
      // 各レーンの中心に強力なAoEバースト
      final burstPos = Vector2(laneX, GameConstants.fieldTop + 80);

      world.add(BurstParticleComponent(
        position: burstPos,
        color: const Color(0xFFFFD700),
        count: 30,
        speed: 200.0,
        lifespan: 0.9,
        radius: 80.0,
      ));
      world.add(MagicCircleEffect(
        position: burstPos + Vector2(-25, -25),
        color: const Color(0xFFFFD700),
      ));

      // 各レーンの敵に大ダメージ
      for (final enemy in List.from(_enemies)) {
        if (!enemy.isAlive) continue;
        if (enemy.laneIndex != i) continue;
        final dmg = (200 + (enemy.enemyData.maxHp * 0.35)).round();
        enemy.takeDamage(dmg);
        world.add(ImpactEffect(
          position: enemy.position + Vector2(-24, -24),
          color: const Color(0xFFFFD700),
          style: impactStyleFor(ElementType.light),
        ));
        _spawnFloatingText(
          enemy.position + Vector2(0, -40),
          '⚡ $dmg',
          const Color(0xFFFFD700),
          fontSize: 22,
        );
      }
    }

    // 全体フラッシュ＋強いシェイク
    _lighting.flashWhite();
    _shakeController.shake(intensity: 8.0, duration: 0.5);
    HapticFeedback.heavyImpact();
    _audio.playSE(AudioSE.chain);
  }

  /// ボーンで全配置ユニットをパワーアップ
  void powerUpAllDeployedUnits() {
    for (final unit in _units) {
      if (!unit.unitInstance.isAlive) continue;
      unit.unitInstance.powerUp();
      _spawnFusionEffect(unit.position, unit.unitInstance.element, powerUp: true);
    }
    _spawnFloatingText(
      Vector2(GameConstants.gameWidth / 2, GameConstants.gameHeight / 2 - 60),
      '👑 全軍パワーアップ！',
      const Color(0xFFFFE082),
      fontSize: 20,
    );
    _shakeController.shake(intensity: 4.0, duration: 0.4);
  }

  /// 配備フェーズ終了（バトル開始）
  void endFormation() {
    _formationPhase = false;
  }

  bool get isFormationPhase => _formationPhase;

  /// ドラッグ状態をフィールドオーバーレイに伝える（onLoad前は無視）
  void setDraggingCard(bool isDragging) {
    if (!isLoaded) return;
    _fieldOverlay.setDragging(isDragging);
  }

  /// ショップ・抽出画面完了後に呼ぶ（次ウェーブを準備してクリアフラグをリセット）
  void prepareNextWave(int waveNumber) {
    _waveClearHandled = false;
    _waveBreachCount = 0;
    clearTerrains();
    waveSystem.prepareWave(waveNumber);
  }

  /// カードをドロップした位置からレーンを判定して配置
  void handleCardDrop(String cardId, Offset screenOffset) {
    final card = CardMaster.getById(cardId);
    if (card == null) return;

    // x座標からレーン（列）判定
    final gameX = screenOffset.dx;
    int laneIndex;
    if (gameX < GameConstants.laneWidth) {
      laneIndex = 0;
    } else if (gameX < GameConstants.laneWidth * 2) {
      laneIndex = 1;
    } else {
      laneIndex = 2;
    }

    // マナ消費
    if (!gameState.spendManaAndRemoveCard(cardId, card.manaCost)) return;

    final gameY = screenOffset.dy;
    final inGrid = gameY >= GameConstants.gridTop && gameY <= GameConstants.gridBottom;
    final row = inGrid
        ? ((gameY - GameConstants.gridTop) / GameConstants.cellHeight)
            .floor()
            .clamp(0, GameConstants.gridRows - 1)
        : -1;

    if (card.cardType == CardType.unit) {
      if (inGrid) {
        // グリッド内: 指定セルに配置 or フュージョン
        final existing = _grid[(laneIndex, row)];
        if (existing != null) {
          _fuseUnit(existing, card, laneIndex);
        } else {
          placeUnit(card, laneIndex, row: row);
        }
      } else {
        placeUnit(card, laneIndex);
      }
    } else if (card.cardType == CardType.spell) {
      castSpell(card, laneIndex);
    } else {
      // 罠・地形: ドロップY座標を渡す（地形はグリッド外＝敵フィールドに設置）
      placeTrap(card, laneIndex, dropY: gameY);
    }

    onCardPlaced(cardId, laneIndex);
  }

  UnitComponent? _findUnitInLane(int laneIndex) {
    UnitComponent? best;
    double bestY = double.negativeInfinity;
    for (final u in _units) {
      if (!u.unitInstance.isAlive) continue;
      if (u.unitInstance.laneIndex != laneIndex) continue;
      if (u.position.y > bestY) {
        bestY = u.position.y;
        best = u;
      }
    }
    return best;
  }

  void _fuseUnit(UnitComponent existing, CardData newCard, int laneIndex) {
    final inst = existing.unitInstance;
    if (inst.element == newCard.element) {
      // 同属性: パワーアップ
      inst.powerUp();
      _spawnFusionEffect(existing.position, inst.element, powerUp: true);
      _spawnFloatingText(
        existing.position + Vector2(0, -40),
        '⭐ パワーアップ！',
        const Color(0xFFFFE082),
        fontSize: 16,
      );
      HapticFeedback.mediumImpact();
    } else {
      // 異属性: 合体変身
      final result = _fusionTable(inst.element, newCard.element);
      inst.fuseTo(
        newElement: result.element,
        newName: result.name,
        newEmoji: result.emoji,
        newAttack: ((inst.attack + newCard.baseAttack) * 0.8).round(),
        newMaxHp: ((inst.maxHp + newCard.baseHp) * 0.8).round(),
      );
      _spawnFusionEffect(existing.position, result.element, powerUp: false);
      _spawnFloatingText(
        existing.position + Vector2(0, -40),
        '🌀 ${result.name}に変身！',
        const Color(0xFFCE93D8),
        fontSize: 14,
      );
      HapticFeedback.heavyImpact();
    }
  }

  void _spawnFusionEffect(Vector2 pos, ElementType element, {required bool powerUp}) {
    world.add(BurstParticleComponent(
      position: pos,
      color: Color(element.colorValue),
      count: powerUp ? 16 : 28,
      speed: powerUp ? 100.0 : 180.0,
      lifespan: 0.8,
    ));
    _shakeController.shake(intensity: 3.0, duration: 0.2);
  }

  ({ElementType element, String name, String emoji}) _fusionTable(
      ElementType a, ElementType b) {
    final pair = {a, b};
    if (pair.containsAll([ElementType.fire, ElementType.water]))
      return (element: ElementType.wind, name: '蒸気騎士', emoji: '💨');
    if (pair.containsAll([ElementType.fire, ElementType.wind]))
      return (element: ElementType.fire, name: '爆炎士', emoji: '🌋');
    if (pair.containsAll([ElementType.fire, ElementType.earth]))
      return (element: ElementType.earth, name: '溶岩守', emoji: '🌄');
    if (pair.containsAll([ElementType.fire, ElementType.light]))
      return (element: ElementType.light, name: '聖炎師', emoji: '☀️');
    if (pair.containsAll([ElementType.fire, ElementType.dark]))
      return (element: ElementType.dark, name: '邪炎使', emoji: '🔴');
    if (pair.containsAll([ElementType.water, ElementType.wind]))
      return (element: ElementType.water, name: '嵐射手', emoji: '⛈️');
    if (pair.containsAll([ElementType.water, ElementType.earth]))
      return (element: ElementType.earth, name: '大地守', emoji: '🌊');
    if (pair.containsAll([ElementType.water, ElementType.light]))
      return (element: ElementType.light, name: '聖水師', emoji: '💫');
    if (pair.containsAll([ElementType.water, ElementType.dark]))
      return (element: ElementType.dark, name: '深淵使', emoji: '🌀');
    if (pair.containsAll([ElementType.wind, ElementType.earth]))
      return (element: ElementType.wind, name: '砂嵐士', emoji: '🌪️');
    if (pair.containsAll([ElementType.wind, ElementType.light]))
      return (element: ElementType.light, name: '雷光師', emoji: '⚡');
    if (pair.containsAll([ElementType.wind, ElementType.dark]))
      return (element: ElementType.dark, name: '影風使', emoji: '🌫️');
    if (pair.containsAll([ElementType.earth, ElementType.light]))
      return (element: ElementType.light, name: '聖岩守', emoji: '💎');
    if (pair.containsAll([ElementType.earth, ElementType.dark]))
      return (element: ElementType.dark, name: '呪岩使', emoji: '🪨');
    // light + dark
    return (element: ElementType.fire, name: '混沌士', emoji: '🌈');
  }
}

// ============================================================
// バフビームエフェクト（支援ユニット → 対象ユニット）
// ============================================================
class _BuffBeam extends Component {
  final Vector2 from;
  final Vector2 to;
  final Color color;
  double _t = 0;
  static const _dur = 0.5;

  _BuffBeam({required this.from, required this.to, required this.color});

  @override
  void update(double dt) {
    _t += dt;
    if (_t >= _dur) removeFromParent();
  }

  @override
  void render(Canvas canvas) {
    final progress = (_t / _dur).clamp(0.0, 1.0);
    final alpha = progress < 0.3
        ? (progress / 0.3)
        : (1.0 - (progress - 0.3) / 0.7);

    // メインライン
    canvas.drawLine(
      Offset(from.x, from.y),
      Offset(to.x, to.y),
      Paint()
        ..color = color.withAlpha((alpha * 180).round())
        ..strokeWidth = 3.5
        ..strokeCap = StrokeCap.round
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 3),
    );
    // 白いコアライン
    canvas.drawLine(
      Offset(from.x, from.y),
      Offset(to.x, to.y),
      Paint()
        ..color = Colors.white.withAlpha((alpha * 120).round())
        ..strokeWidth = 1.5
        ..strokeCap = StrokeCap.round,
    );
    // ターゲット側のバーストリング
    canvas.drawCircle(
      Offset(to.x, to.y),
      8 + progress * 20,
      Paint()
        ..color = color.withAlpha((alpha * 100).round())
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.5,
    );
  }
}
