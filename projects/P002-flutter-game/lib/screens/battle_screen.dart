import 'package:flame/game.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../game/game_state.dart';
import '../game/octo_battle_game.dart';
import '../constants/strings.dart';
import '../models/stage_data.dart';
import '../systems/event_system.dart';
import 'card_hand_widget.dart';
import 'result_screen.dart';

/// メインバトル画面
/// FlameGame（描画）+ Flutterウィジェット（HUD・UI）の合成レイアウト
class BattleScreen extends StatefulWidget {
  const BattleScreen({super.key});

  @override
  State<BattleScreen> createState() => _BattleScreenState();
}

class _BattleScreenState extends State<BattleScreen> {
  OctoBattleGame? _game;
  final EventSystem _eventSystem = EventSystem();

  // ウェーブ間イベント表示用
  WaveEvent? _pendingEvent;
  bool _showEventModal = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_game == null) {
      final gameState = context.read<GameStateNotifier>();
      final stageId = gameState.selectedStageId;
      if (stageId != null) {
        gameState.startBattle(stageId);
        _game = OctoBattleGame(
          gameState: gameState,
          onPhaseChangeRequest: _handlePhaseChange,
          onCardPlaced: _handleCardPlaced,
          onChainTriggered: _handleChainTriggered,
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_game == null) {
      return const Scaffold(
        backgroundColor: Color(0xFF0D0D1A),
        body: Center(child: CircularProgressIndicator()),
      );
    }

    return Scaffold(
      body: Stack(
        children: [
          // ---- Flame ゲームキャンバス ----
          Positioned.fill(
            bottom: 140, // カード手札UIの高さ分だけ上
            child: GameWidget(game: _game!),
          ),

          // ---- カード手札UI（下部） ----
          Positioned(
            bottom: 0,
            left: 0,
            right: 0,
            child: CardHandWidget(
              onCardDropped: (cardId, offset) {
                _game?.handleCardDrop(cardId, offset);
              },
            ),
          ),

          // ---- HUD オーバーレイ（Flutter） ----
          SafeArea(child: _buildHUD()),

          // ---- ウェーブ間イベントモーダル ----
          if (_showEventModal && _pendingEvent != null)
            _EventModal(
              event: _pendingEvent!,
              onAccept: () => _resolveEvent(accepted: true),
              onDecline: _pendingEvent!.hasChoice
                  ? () => _resolveEvent(accepted: false)
                  : null,
            ),
        ],
      ),
    );
  }

  Widget _buildHUD() {
    return Consumer<GameStateNotifier>(
      builder: (_, gs, __) {
        final battle = gs.battle;
        if (battle == null) return const SizedBox.shrink();

        return Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
          child: Row(
            children: [
              // 城壁HPバー
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      '${Strings.hpLabel}: ${battle.wallHp}',
                      style: const TextStyle(
                        color: Color(0xFF80CBC4),
                        fontFamily: 'DotGothic16',
                        fontSize: 11,
                      ),
                    ),
                    const SizedBox(height: 2),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(2),
                      child: LinearProgressIndicator(
                        value: battle.wallHpRatio,
                        backgroundColor: const Color(0xFF1A1A2E),
                        valueColor: AlwaysStoppedAnimation(
                          battle.wallHpRatio > 0.5
                              ? const Color(0xFF66BB6A)
                              : battle.wallHpRatio > 0.25
                                  ? const Color(0xFFFFA726)
                                  : const Color(0xFFEF5350),
                        ),
                        minHeight: 6,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 12),

              // ウェーブ表示
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: const Color(0xFF1A1A2E),
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(color: const Color(0xFFFFE082).withOpacity(0.5)),
                ),
                child: Text(
                  '${Strings.waveLabel} ${battle.currentWave}',
                  style: const TextStyle(
                    color: Color(0xFFFFE082),
                    fontFamily: 'DotGothic16',
                    fontSize: 12,
                  ),
                ),
              ),
              const SizedBox(width: 8),

              // スコア
              Text(
                '${battle.score}',
                style: const TextStyle(
                  color: Color(0xFF69F0AE),
                  fontFamily: 'DotGothic16',
                  fontSize: 13,
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  void _handlePhaseChange(GamePhase phase) {
    if (!mounted) return;
    final gs = context.read<GameStateNotifier>();

    if (phase == GamePhase.result) {
      final isVictory = gs.battle?.battlePhase == BattlePhase.victory;
      gs.endBattle(isVictory: isVictory).then((_) {
        if (mounted) {
          Navigator.of(context).pushReplacement(
            MaterialPageRoute(builder: (_) => const ResultScreen()),
          );
        }
      });
    }

    // ウェーブクリア → イベント抽選
    if (phase == GamePhase.battle) {
      final battle = gs.battle;
      if (battle != null) {
        _tryRollWaveEvent(battle.currentWave);
      }
    }
  }

  void _handleCardPlaced(String cardId, int laneIndex) {
    // 将来: 配置統計・実績処理
  }

  void _handleChainTriggered(int chainCount, double damage) {
    // チェーンカウント表示はchain_effect.dartが担当
    // ここでは追加のUI処理（例: コンボカウンター表示）を行える
    setState(() {}); // 必要に応じてリビルド
  }

  void _tryRollWaveEvent(int waveNumber) {
    final stage = StageMaster.getById(
      context.read<GameStateNotifier>().selectedStageId ?? '',
    );
    if (stage == null) return;

    final event = _eventSystem.rollEvent(
      waveNumber: waveNumber,
      totalWaves: stage.waves.length,
    );
    if (event != null) {
      setState(() {
        _pendingEvent = event;
        _showEventModal = true;
      });
    }
  }

  void _resolveEvent({required bool accepted}) {
    if (_pendingEvent == null) return;
    final effect = _eventSystem.applyEvent(_pendingEvent!, playerAccepted: accepted);
    final gs = context.read<GameStateNotifier>();

    // 効果を反映
    if (effect.wallDamageImmediate > 0) {
      gs.damageWall(effect.wallDamageImmediate);
    }
    if (effect.bonusCardId != null) {
      gs.battle?.handCardIds.add(effect.bonusCardId!);
    }

    setState(() {
      _showEventModal = false;
      _pendingEvent = null;
    });
  }
}

/// ウェーブ間イベントモーダル
class _EventModal extends StatelessWidget {
  final WaveEvent event;
  final VoidCallback onAccept;
  final VoidCallback? onDecline;

  const _EventModal({
    required this.event,
    required this.onAccept,
    this.onDecline,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      color: Colors.black.withOpacity(0.7),
      child: Center(
        child: Container(
          margin: const EdgeInsets.symmetric(horizontal: 32),
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: const Color(0xFF12121E),
            border: Border.all(
              color: event.isBonus
                  ? const Color(0xFF4CAF50)
                  : const Color(0xFFEF5350),
              width: 2,
            ),
            borderRadius: BorderRadius.circular(12),
            boxShadow: [
              BoxShadow(
                color: (event.isBonus
                        ? const Color(0xFF4CAF50)
                        : const Color(0xFFEF5350))
                    .withOpacity(0.4),
                blurRadius: 20,
              ),
            ],
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // イベントアイコン
              Text(event.emoji, style: const TextStyle(fontSize: 40)),
              const SizedBox(height: 8),

              // タイトル
              Text(
                event.title,
                style: TextStyle(
                  color: event.isBonus
                      ? const Color(0xFF69F0AE)
                      : const Color(0xFFEF9A9A),
                  fontFamily: 'DotGothic16',
                  fontSize: 18,
                ),
              ),
              const SizedBox(height: 8),

              // 説明
              Text(
                event.description,
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: Colors.white.withOpacity(0.8),
                  fontFamily: 'DotGothic16',
                  fontSize: 13,
                  height: 1.5,
                ),
              ),
              const SizedBox(height: 16),

              // ボタン
              Row(
                children: [
                  if (onDecline != null) ...[
                    Expanded(
                      child: OutlinedButton(
                        onPressed: onDecline,
                        style: OutlinedButton.styleFrom(
                          side: const BorderSide(color: Colors.grey),
                        ),
                        child: const Text(
                          '断る',
                          style: TextStyle(fontFamily: 'DotGothic16'),
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                  ],
                  Expanded(
                    child: ElevatedButton(
                      onPressed: onAccept,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: event.isBonus
                            ? const Color(0xFF4CAF50)
                            : const Color(0xFFEF5350),
                      ),
                      child: Text(
                        event.hasChoice ? '受け入れる' : 'OK',
                        style: const TextStyle(fontFamily: 'DotGothic16'),
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

