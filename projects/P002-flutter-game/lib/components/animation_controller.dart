import 'dart:math';
import 'dart:ui' show Paint, PaintingStyle;
import 'package:flame/components.dart';
import 'package:flame/effects.dart';
import 'package:flutter/material.dart' show Color, Colors, Curves;
import '../constants/game_constants.dart';
import '../components/floating_text.dart';
import '../components/particle_system.dart';
import '../components/screen_shake.dart';

/// ゲーム内アニメーションを一元管理するコントローラ
/// FlameGame.world に追加し、外部から呼び出す
class GameAnimationController extends Component {
  final ScreenShakeController shakeController;
  final _rng = Random();

  GameAnimationController({required this.shakeController});

  // ---- 敵アニメーション ----

  /// 敵の行進アニメーション（右→左 + 足踏みボブ）
  /// [enemy] に PositionComponent を渡す。
  /// 行進速度・距離は enemy.position.x を毎フレーム動かす前提のため、
  /// ここでは上下ボブ（足踏み）のみを Effect として付与する。
  void applyMarchBob(PositionComponent enemy) {
    // 上下ボブ: ±3px を 0.35秒 周期で繰り返す
    final bob = MoveEffect.by(
      Vector2(0, 3),
      EffectController(
        duration: 0.35,
        reverseDuration: 0.35,
        infinite: true,
        curve: Curves.easeInOut,
      ),
    );
    enemy.add(bob);
  }

  /// 敵の死亡アニメーション（フェードアウト + スケール縮小 + パーティクル）
  Future<void> playEnemyDeath(PositionComponent enemy, Color color) async {
    // パーティクル爆発（先に生成）
    parent?.add(BurstParticleComponent(
      position: enemy.position.clone(),
      color: color,
      count: 16,
      speed: 90.0,
      lifespan: 0.6,
    ));

    // スケール縮小 + フェード同時適用
    enemy.add(
      ScaleEffect.to(
        Vector2.all(0),
        EffectController(duration: 0.3, curve: Curves.easeIn),
        onComplete: () => enemy.removeFromParent(),
      ),
    );
    enemy.add(
      OpacityEffect.to(
        0,
        EffectController(duration: 0.3),
      ),
    );
  }

  // ---- ユニットアニメーション ----

  /// ユニットの攻撃シーケンス（前進 → ヒット → 後退）
  void playUnitAttack(PositionComponent unit, {double swingDistance = 12.0}) {
    final origin = unit.position.clone();

    // 前進
    unit.add(
      MoveEffect.by(
        Vector2(swingDistance, 0),
        EffectController(duration: 0.08, curve: Curves.easeOut),
        onComplete: () {
          // ヒット後に後退
          unit.add(
            MoveEffect.to(
              origin,
              EffectController(duration: 0.12, curve: Curves.easeIn),
            ),
          );
        },
      ),
    );
  }

  // ---- ボス演出 ----

  /// ボス登場演出（画面外右から登場 + ScreenShake + FloatingText「BOSS!」）
  void playBossEntrance(PositionComponent boss, Vector2 targetPosition) {
    // ボスを画面右外からスタート
    boss.position = Vector2(GameConstants.gameWidth + 80, targetPosition.y);

    // スライドインEffect
    boss.add(
      MoveEffect.to(
        targetPosition,
        EffectController(duration: 1.2, curve: Curves.easeOutCubic),
        onComplete: () {
          // 登場完了 → ScreenShake
          shakeController.shake(
            intensity: GameConstants.screenShakeIntensityBoss,
            duration: 0.6,
          );
          // スケールドンと揺れ
          boss.add(
            ScaleEffect.by(
              Vector2.all(1.3),
              EffectController(
                duration: 0.1,
                reverseDuration: 0.25,
                curve: Curves.easeOut,
              ),
            ),
          );
          // FloatingText「BOSS!」
          parent?.add(FloatingTextComponent(
            text: '💀 BOSS!',
            position: Vector2(
              targetPosition.x - 30,
              targetPosition.y - 50,
            ),
            color: const Color(0xFFFF1744),
            fontSize: 28,
          ));
        },
      ),
    );

    // 点滅で存在を主張（登場アニメ中）
    boss.add(
      OpacityEffect.fadeIn(
        EffectController(duration: 0.4, startDelay: 0.0),
      ),
    );
  }

  // ---- チェーン反応演出 ----

  /// チェーン波紋演出（光の波紋を中心から広げる）
  void playChainRipple(Vector2 center, int chainCount) {
    final color = _chainColor(chainCount);

    for (int ring = 0; ring < chainCount.clamp(1, 4); ring++) {
      final delay = ring * 0.08;
      Future.delayed(
        Duration(milliseconds: (delay * 1000).toInt()),
        () {
          if (parent == null) return;
          // 波紋: CircleComponent をスケール拡大 + フェードアウト
          final ripple = CircleComponent(
            radius: 10,
            position: center.clone(),
            anchor: Anchor.center,
            paint: Paint()
              ..color = color.withOpacity(0.7)
              ..style = PaintingStyle.stroke
              ..strokeWidth = 2.0,
          );
          parent!.add(ripple);

          ripple.add(ScaleEffect.to(
            Vector2.all(4.0 + ring * 1.5),
            EffectController(duration: 0.45, curve: Curves.easeOut),
          ));
          ripple.add(OpacityEffect.to(
            0,
            EffectController(duration: 0.45, startDelay: 0.1),
            onComplete: () => ripple.removeFromParent(),
          ));
        },
      );
    }

    // 画面フラッシュ（chain ×3 以上）
    if (chainCount >= 3) {
      _flashScreen(color.withOpacity(0.15));
    }
  }

  Color _chainColor(int count) {
    if (count >= 5) return const Color(0xFFFFD700); // 金
    if (count >= 3) return const Color(0xFFCE93D8); // 紫
    return const Color(0xFF42A5F5);                 // 青
  }

  void _flashScreen(Color color) {
    final flash = RectangleComponent(
      size: Vector2(GameConstants.gameWidth, GameConstants.gameHeight),
      position: Vector2.zero(),
      paint: Paint()..color = color,
    );
    parent?.add(flash);
    flash.add(OpacityEffect.to(
      0,
      EffectController(duration: 0.3),
      onComplete: () => flash.removeFromParent(),
    ));
  }

  // ---- レベルアップ演出 ----

  /// レベルアップ演出（光の柱 + 回転テキスト）
  void playLevelUp(Vector2 position, int newLevel) {
    // 光の柱: 縦長矩形を上にフェードアウト
    final pillar = RectangleComponent(
      size: Vector2(6, GameConstants.gameHeight),
      position: Vector2(position.x - 3, 0),
      paint: Paint()..color = const Color(0xAAFFE082),
    );
    parent?.add(pillar);
    pillar.add(OpacityEffect.to(
      0,
      EffectController(duration: 0.8),
      onComplete: () => pillar.removeFromParent(),
    ));

    // テキスト「LEVEL UP!」+ 上昇 + 回転（RotateEffect）
    final lvText = FloatingTextComponent(
      text: '⬆ LEVEL $newLevel!',
      position: position + Vector2(-40, -60),
      color: const Color(0xFFFFE082),
      fontSize: 20,
    );
    parent?.add(lvText);

    lvText.add(RotateEffect.by(
      2 * pi,
      EffectController(duration: 0.8, curve: Curves.easeOut),
    ));
    lvText.add(ScaleEffect.to(
      Vector2.all(1.5),
      EffectController(duration: 0.4, reverseDuration: 0.4),
    ));

    // パーティクルバースト（金色）
    parent?.add(BurstParticleComponent(
      position: position.clone(),
      color: const Color(0xFFFFD700),
      count: 24,
      speed: 120.0,
      lifespan: 1.0,
    ));
  }

  // ---- アイテム獲得演出 ----

  /// コインが弧を描いてUIのゴールド表示へ飛んでいくアニメーション
  /// [from]: コイン発生位置（ワールド座標）
  /// [to]: UIのゴールド表示位置（ワールド座標に変換済み）
  void playCoinFlyToUI({
    required Vector2 from,
    required Vector2 to,
    int coinCount = 3,
  }) {
    for (int i = 0; i < coinCount; i++) {
      final delay = i * 0.08;
      Future.delayed(Duration(milliseconds: (delay * 1000).toInt()), () {
        if (parent == null) return;

        // コイン: 小さい黄色い円
        final coin = CircleComponent(
          radius: 5,
          position: from.clone() + Vector2(_rng.nextDouble() * 20 - 10, 0),
          anchor: Anchor.center,
          paint: Paint()..color = const Color(0xFFFFD54F),
        );
        parent!.add(coin);

        // 弧を描くために2段階Moveを使う
        // 1段階: 上に弧の頂点まで移動
        final midpoint = Vector2(
          (from.x + to.x) / 2,
          from.y - 60 - _rng.nextDouble() * 30,
        );
        coin.add(
          MoveEffect.to(
            midpoint,
            EffectController(duration: 0.25, curve: Curves.easeOut),
            onComplete: () {
              // 2段階: UIへ収束
              coin.add(
                MoveEffect.to(
                  to,
                  EffectController(duration: 0.25, curve: Curves.easeIn),
                  onComplete: () {
                    coin.removeFromParent();
                    // 到着スパーク
                    parent?.add(BurstParticleComponent(
                      position: to.clone(),
                      color: const Color(0xFFFFD54F),
                      count: 6,
                      speed: 40.0,
                      lifespan: 0.3,
                    ));
                  },
                ),
              );
            },
          ),
        );

        // 到着直前に縮小
        coin.add(
          ScaleEffect.to(
            Vector2.all(0.3),
            EffectController(duration: 0.5, startDelay: 0.2),
          ),
        );
      });
    }
  }
}

// ---- Curves 型エイリアス（Flameと競合しないよう明示） ----
// Flameが flutter/material を再exportしているため、ここでは直接参照できる。
// 上部の import 'package:flutter/material.dart' で Color が取れる。

// ---- PositionComponent 拡張メソッド ----
// GameAnimationController に依存しないユーティリティ

extension AnimationShortcuts on PositionComponent {
  /// 短いバウンス演出（購入・配置成功時など）
  void bounce({double scale = 1.3, double duration = 0.15}) {
    add(ScaleEffect.to(
      Vector2.all(scale),
      EffectController(
        duration: duration,
        reverseDuration: duration,
        curve: Curves.easeOut,
      ),
    ));
  }

  /// フラッシュ（ダメージ受け時）
  void flashRed() {
    add(ColorEffect(
      const Color(0xFFFF1744),
      EffectController(duration: 0.1, reverseDuration: 0.1),
      opacityFrom: 0.0,
      opacityTo: 0.6,
    ));
  }
}
