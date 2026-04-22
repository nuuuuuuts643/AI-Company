import 'package:flame/game.dart';
import 'package:flame/components.dart';
import 'package:flame/events.dart';
import 'package:flutter/material.dart' hide Route;
import 'package:flutter/services.dart';
import '../components/hd2d_background.dart';
import '../components/enemy_component.dart';
import '../components/unit_component.dart';
import '../components/lighting_layer.dart';
import '../components/particle_system.dart';
import '../components/floating_text.dart';
import '../components/screen_shake.dart';
import '../components/chain_effect.dart';
import '../constants/game_constants.dart';
import '../constants/element_chart.dart';
import '../models/card_data.dart';
import '../models/enemy_data.dart';
import '../models/unit_data.dart';
import '../models/stage_data.dart';
import '../systems/battle_system.dart';
import '../systems/wave_system.dart';
import '../systems/card_system.dart';
import '../systems/chain_system.dart';
import '../systems/loot_system.dart';
import 'game_state.dart';

/// FlameGame メインクラス
/// 描画・アニメーション・当たり判定を担当。
/// ロジック状態は GameStateNotifier に委譲する。
class OctoBattleGame extends FlameGame
    with TapCallbacks, DragCallbacks, HasCollisionDetection {
  final GameStateNotifier gameState;

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
  late final TextComponent _waveLabel;
  late final TextComponent _wallHpText;

  // フィールド上のアクティブコンポーネント
  final List<EnemyComponent> _enemies = [];
  final List<UnitComponent> _units = [];

  // カード配置インタラクション
  String? _draggingCardId;     // 現在ドラッグ中のカードID
  Vector2? _dragPosition;

  // コールバック（Flutterレイヤーへ通知）
  final void Function(GamePhase) onPhaseChangeRequest;
  final void Function(String cardId, int laneIndex) onCardPlaced;
  final void Function(int chainCount, double damage) onChainTriggered;

  OctoBattleGame({
    required this.gameState,
    required this.onPhaseChangeRequest,
    required this.onCardPlaced,
    required this.onChainTriggered,
  });

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
    battleSystem = BattleSystem(gameState: gameState);
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

    // チェーン演出
    _chainEffect = ChainEffectComponent(
      position: Vector2(GameConstants.gameWidth / 2, 300),
    );
    world.add(_chainEffect);

    // レーン区切り線（視覚ガイド）
    _addLaneGuides();

    // HUD テキスト（Flameレイヤー）
    _waveLabel = TextComponent(
      text: 'WAVE 1 / ${_stageData?.waves.length ?? 5}',
      position: Vector2(10, 8),
      textRenderer: TextPaint(
        style: const TextStyle(
          color: Color(0xFFFFE082),
          fontSize: 14,
          fontFamily: 'DotGothic16',
        ),
      ),
    );
    camera.viewport.add(_waveLabel);

    _wallHpText = TextComponent(
      text: '城壁 HP: ${gameState.battle?.wallHp ?? 0}',
      position: Vector2(10, 26),
      textRenderer: TextPaint(
        style: const TextStyle(
          color: Color(0xFF80CBC4),
          fontSize: 12,
          fontFamily: 'DotGothic16',
        ),
      ),
    );
    camera.viewport.add(_wallHpText);

    // 最初のウェーブを準備
    waveSystem.prepareWave(gameState.battle!.currentWave);
  }

  @override
  void update(double dt) {
    super.update(dt);

    final battle = gameState.battle;
    if (battle == null) return;

    // マナ更新
    gameState.tickMana(dt);

    // ウェーブシステム更新
    waveSystem.update(dt);

    // バトルシステム: ユニット対敵のオートバトル
    battleSystem.update(dt, _units, _enemies);

    // 城壁到達判定
    for (final enemy in List.from(_enemies)) {
      if (enemy.position.x <= GameConstants.wallX + GameConstants.wallWidth) {
        _onEnemyReachedWall(enemy);
      }
    }

    // デッドユニット除去
    _units.removeWhere((u) {
      if (!u.unitInstance.isAlive) {
        u.removeFromParent();
        return true;
      }
      return false;
    });

    // デッド敵除去
    _enemies.removeWhere((e) {
      if (!e.isAlive) {
        _onEnemyDefeated(e);
        e.removeFromParent();
        return true;
      }
      return false;
    });

    // HUD更新
    _updateHUD();

    // 勝敗判定
    if (battle.isDefeated) {
      onPhaseChangeRequest(GamePhase.result);
    }
  }

  // ---- 敵スポーン（WaveSystemから呼ばれる） ----

  EnemyComponent spawnEnemy(EnemyData data, int laneIndex) {
    final laneY = _laneY(laneIndex);
    final enemy = EnemyComponent(
      enemyData: data,
      position: Vector2(GameConstants.enemySpawnX, laneY),
      onDefeated: (comp) => _onEnemyDefeated(comp),
    );
    _enemies.add(enemy);
    world.add(enemy);

    // ボスはライト追加演出
    if (data.type.isBoss) {
      _lighting.addBossAura(Vector2(GameConstants.enemySpawnX, laneY));
      _shakeController.shake(intensity: 6.0, duration: 0.4);
    }
    return enemy;
  }

  // ---- カード配置（CardSystemから呼ばれる） ----

  void placeUnit(CardData card, int laneIndex) {
    final laneY = _laneY(laneIndex);
    final placeX = GameConstants.wallX + GameConstants.wallWidth + 30.0;

    // ユニット生成
    final instance = cardSystem.createUnitInstance(card, laneIndex);
    final unitComp = UnitComponent(
      unitInstance: instance,
      position: Vector2(placeX + _units.where((u) => u.unitInstance.laneIndex == laneIndex).length * 55.0, laneY),
      onAttack: _onUnitAttack,
    );
    _units.add(unitComp);
    world.add(unitComp);

    // 配置パーティクル
    _spawnPlacementParticles(Vector2(placeX, laneY), card.element);

    // 触覚フィードバック（成功）
    HapticFeedback.mediumImpact();

    // 光源追加（魔法属性はより強い光）
    if (card.element == ElementType.light || card.element == ElementType.fire) {
      _lighting.addUnitLight(Vector2(placeX, laneY), card.element);
    }
  }

  void castSpell(CardData card, int laneIndex) {
    final targetY = _laneY(laneIndex);
    final targetX = 200.0; // 画面中央付近

    // ダメージ計算と適用
    for (final enemy in List.from(_enemies)) {
      if (enemy.unitInstance == null) continue; // 型チェック
      final dx = (enemy.position.x - targetX).abs();
      final dy = (enemy.position.y - targetY).abs();
      if (card.aoeRadius > 0) {
        if (dx < card.aoeRadius && dy < 40) {
          _applySpellDamage(card, enemy);
        }
      } else {
        if (enemy.laneIndex == laneIndex && dx < 60) {
          _applySpellDamage(card, enemy);
        }
      }
    }

    // 魔法エフェクト
    _spawnSpellEffect(Vector2(targetX, targetY), card.element, card.aoeRadius);
    HapticFeedback.heavyImpact();
  }

  void placeTrap(CardData card, int laneIndex) {
    // 罠はフィールド中央付近に設置（将来: タップ位置）
    final laneY = _laneY(laneIndex);
    final trapX = 220.0;
    _spawnTrapVisual(Vector2(trapX, laneY), card.element);
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

    // ボス撃破：大きなScreenShake
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
    gameState.damageWall(enemy.enemyData.attackPower);
    _enemies.remove(enemy);
    enemy.removeFromParent();

    // 城壁ダメージ演出
    _shakeController.shake(
      intensity: GameConstants.screenShakeIntensityNormal,
      duration: 0.25,
    );
    HapticFeedback.selectionClick();
    _spawnFloatingText(
      Vector2(GameConstants.wallX + 20, 400),
      '-${enemy.enemyData.attackPower}',
      const Color(0xFFEF5350),
      fontSize: 22,
    );
  }

  void _onUnitAttack({
    required UnitInstance attacker,
    required EnemyComponent target,
    required int damage,
    required bool isWeakness,
    required bool isChain,
  }) {
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

  double _laneY(int laneIndex) {
    return GameConstants.fieldTop +
        GameConstants.laneHeight * laneIndex +
        GameConstants.laneHeight / 2;
  }

  StageData? get _stageData {
    final id = gameState.selectedStageId;
    if (id == null) return null;
    return StageMaster.getById(id);
  }

  void _addLaneGuides() {
    for (int i = 1; i < GameConstants.laneCount.toInt(); i++) {
      final y = GameConstants.fieldTop + GameConstants.laneHeight * i;
      world.add(
        RectangleComponent(
          position: Vector2(0, y),
          size: Vector2(GameConstants.gameWidth, 1),
          paint: Paint()..color = const Color(0x22FFFFFF),
        ),
      );
    }
  }

  void _updateHUD() {
    final b = gameState.battle;
    if (b == null) return;
    _waveLabel.text =
        'WAVE ${b.currentWave} / ${_stageData?.waves.length ?? 5}';
    _wallHpText.text = '城壁 HP: ${b.wallHp}';
  }

  // ---- 外部から呼び出す（カードUI→ゲーム） ----

  /// カードをドロップした位置からレーンを判定して配置
  void handleCardDrop(String cardId, Offset screenOffset) {
    final card = CardMaster.getById(cardId);
    if (card == null) return;

    // y座標からレーン判定
    final gameY = screenOffset.dy;
    int laneIndex = 1;
    if (gameY < GameConstants.fieldTop + GameConstants.laneHeight) {
      laneIndex = 0;
    } else if (gameY > GameConstants.fieldTop + GameConstants.laneHeight * 2) {
      laneIndex = 2;
    }

    // マナ消費
    if (!gameState.spendManaAndRemoveCard(cardId, card.manaCost)) return;

    switch (card.cardType) {
      case CardType.unit:
        placeUnit(card, laneIndex);
        break;
      case CardType.spell:
        castSpell(card, laneIndex);
        break;
      case CardType.trap:
        placeTrap(card, laneIndex);
        break;
    }

    onCardPlaced(cardId, laneIndex);
  }
}
