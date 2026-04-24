import 'package:flame/game.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../game/game_state.dart';
import '../game/octo_battle_game.dart';
import '../constants/strings.dart';
import '../models/stage_data.dart';
import '../services/audio_service.dart';
import '../systems/event_system.dart';
import '../systems/extraction_system.dart';
import 'card_hand_widget.dart';
import 'extraction_screen.dart';
import 'result_screen.dart';
import 'wave_shop_screen.dart';

/// メインバトル画面
/// FlameGame（描画）+ Flutterウィジェット（HUD・UI）の合成レイアウト
class BattleScreen extends StatefulWidget {
  const BattleScreen({super.key});

  @override
  State<BattleScreen> createState() => _BattleScreenState();
}

class _BattleScreenState extends State<BattleScreen>
    with TickerProviderStateMixin {
  OctoBattleGame? _game;
  final EventSystem _eventSystem = EventSystem();
  late ExtractionSystem _extractionSystem;

  // ウェーブ間イベント表示用
  WaveEvent? _pendingEvent;
  bool _showEventModal = false;

  // ウェーブクリア後のショップ・抽出UI
  bool _showShop = false;
  bool _showExtraction = false;
  int _shopWaveNumber = 1;

  // チュートリアルヒント（初回のみ）
  bool _showTutorial = true;

  // ---- 新機能: ボスHPバー ----
  String _bossName = '';
  int _bossMaxHp = 0;
  int _bossCurrentHp = 0;
  bool get _bossActive => _bossName.isNotEmpty && _bossMaxHp > 0;

  // ---- 新機能: 城壁ダメージフラッシュ ----
  late AnimationController _wallFlashCtrl;
  late Animation<double> _wallFlashOpacity;

  // ---- 新機能: ウェーブクリア演出 ----
  bool _showWaveClear = false;
  bool _waveClearPerfect = false;
  int _clearedWaveNum = 0;
  late AnimationController _waveClearCtrl;

  @override
  void initState() {
    super.initState();
    _wallFlashCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 400),
      value: 1.0, // 初期値=1 → opacity=0（透明）から始める
    );
    _wallFlashOpacity = Tween<double>(begin: 0.38, end: 0.0).animate(
      CurvedAnimation(parent: _wallFlashCtrl, curve: Curves.easeOut),
    );

    _waveClearCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1800),
    );
    _waveClearCtrl.addStatusListener((s) {
      if (s == AnimationStatus.completed && mounted) {
        setState(() => _showWaveClear = false);
      }
    });
  }

  @override
  void dispose() {
    _wallFlashCtrl.dispose();
    _waveClearCtrl.dispose();
    super.dispose();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_game == null) {
      final gameState = context.read<GameStateNotifier>();
      final audio = context.read<AudioService>();
      final stageId = gameState.selectedStageId;
      if (stageId != null) {
        _extractionSystem = ExtractionSystem(gameState: gameState);
        _game = OctoBattleGame(
          gameState: gameState,
          audio: audio,
          onPhaseChangeRequest: _handlePhaseChange,
          onCardPlaced: _handleCardPlaced,
          onChainTriggered: _handleChainTriggered,
          onBossHpUpdate: _handleBossHpUpdate,
          onWallDamaged: _handleWallDamaged,
        );
        // ビルドフェーズ中に notifyListeners を呼ばないよう次フレームに延期
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) gameState.startBattle(stageId);
        });
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
          // ---- ゲームが画面全体を埋める ----
          DragTarget<String>(
            onAcceptWithDetails: (details) {
              _game?.handleCardDrop(details.data, details.offset);
            },
            builder: (ctx, candidateItems, _) {
              return Stack(
                children: [
                  Positioned.fill(child: GameWidget(game: _game!)),
                  if (candidateItems.isNotEmpty)
                    Positioned.fill(
                      child: Container(
                        decoration: BoxDecoration(
                          border: Border.all(
                            color: Colors.white.withOpacity(0.3),
                            width: 2,
                          ),
                        ),
                      ),
                    ),
                ],
              );
            },
          ),

          // ---- カードハンド（下部オーバーレイ） ----
          Positioned(
            left: 0, right: 0, bottom: 0,
            child: CardHandWidget(
              onCardDropped: (cardId, offset) {},
            ),
          ),

          // ---- HUD オーバーレイ（Flutter） ----
          SafeArea(child: _buildHUD()),

          // ---- チュートリアルヒント（初回のみ）----
          if (_showTutorial)
            _TutorialHint(onDismiss: () => setState(() => _showTutorial = false)),

          // ---- ウェーブ間イベントモーダル ----
          if (_showEventModal && _pendingEvent != null)
            _EventModal(
              event: _pendingEvent!,
              onAccept: () => _resolveEvent(accepted: true),
              onDecline: _pendingEvent!.hasChoice
                  ? () => _resolveEvent(accepted: false)
                  : null,
            ),

          // ---- ウェーブクリアショップ ----
          if (_showShop)
            Positioned.fill(
              child: WaveShopScreen(
                waveNumber: _shopWaveNumber,
                onProceed: _onShopProceed,
              ),
            ),

          // ---- 抽出選択画面 ----
          if (_showExtraction)
            Positioned.fill(
              child: Builder(
                builder: (ctx) {
                  final gs = ctx.read<GameStateNotifier>();
                  final stage = StageMaster.getById(
                    gs.selectedStageId ?? '',
                  );
                  return ExtractionScreen(
                    extractionSystem: _extractionSystem,
                    totalWaves: stage?.waves.length ?? 5,
                    currentWave: _shopWaveNumber,
                    onExtract: _onExtractionExtract,
                    onContinue: _onExtractionContinue,
                  );
                },
              ),
            ),

          // ---- ボスHPバー（ボス戦中のみ） ----
          if (_bossActive && !_showShop && !_showExtraction)
            Positioned(
              top: 64,
              left: 12,
              right: 12,
              child: _BossHPBar(
                name: _bossName,
                maxHp: _bossMaxHp,
                currentHp: _bossCurrentHp,
              ),
            ),

          // ---- 城壁ダメージフラッシュ ----
          AnimatedBuilder(
            animation: _wallFlashOpacity,
            builder: (_, __) => _wallFlashOpacity.value > 0
                ? Positioned.fill(
                    child: IgnorePointer(
                      child: Container(
                        color: const Color(0xFFFF0000)
                            .withOpacity(_wallFlashOpacity.value),
                      ),
                    ),
                  )
                : const SizedBox.shrink(),
          ),

          // ---- ウェーブクリア演出 ----
          if (_showWaveClear)
            Positioned.fill(
              child: IgnorePointer(
                child: _WaveClearOverlay(
                  waveNumber: _clearedWaveNum,
                  isPerfect: _waveClearPerfect,
                  animation: _waveClearCtrl,
                ),
              ),
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

        final hpRatio = battle.wallHpRatio;
        final hpColor = hpRatio > 0.5
            ? const Color(0xFF66BB6A)
            : hpRatio > 0.25
                ? const Color(0xFFFFA726)
                : const Color(0xFFEF5350);

        return Container(
          margin: const EdgeInsets.fromLTRB(8, 4, 8, 0),
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          decoration: BoxDecoration(
            color: Colors.black.withOpacity(0.65),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: Colors.white.withOpacity(0.1)),
          ),
          child: Row(
            children: [
              // 🏰 城壁HP
              const Text('🏰', style: TextStyle(fontSize: 16)),
              const SizedBox(width: 6),
              Expanded(
                flex: 3,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Row(
                      children: [
                        Text(
                          '${battle.wallHp}',
                          style: TextStyle(
                            color: hpColor,
                            fontFamily: 'DotGothic16',
                            fontSize: 12,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 2),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(3),
                      child: LinearProgressIndicator(
                        value: hpRatio,
                        backgroundColor: Colors.white12,
                        valueColor: AlwaysStoppedAnimation(hpColor),
                        minHeight: 5,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 10),

              // WAVE インジケーター
              _WaveIndicator(
                current: battle.currentWave,
                total: _stageWaves,
              ),
              const SizedBox(width: 10),

              // スコア
              Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  const Text('SCORE', style: TextStyle(
                    color: Colors.white38,
                    fontFamily: 'DotGothic16',
                    fontSize: 7,
                  )),
                  Text(
                    '${battle.score}',
                    style: const TextStyle(
                      color: Color(0xFF69F0AE),
                      fontFamily: 'DotGothic16',
                      fontSize: 12,
                    ),
                  ),
                ],
              ),
            ],
          ),
        );
      },
    );
  }

  int get _stageWaves {
    final gs = context.read<GameStateNotifier>();
    final id = gs.selectedStageId ?? '';
    return StageMaster.getById(id)?.waves.length ?? 5;
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

    // ウェーブクリア → ショップ表示
    if (phase == GamePhase.waveShop) {
      _onWaveCleared();
    }

    // 新ウェーブ開始 → イベント抽選
    if (phase == GamePhase.battle) {
      final battle = gs.battle;
      if (battle != null) {
        _tryRollWaveEvent(battle.currentWave);
      }
    }
  }

  void _onWaveCleared() {
    if (!mounted) return;
    final gs = context.read<GameStateNotifier>();
    final wave = gs.battle?.currentWave ?? 1;
    final breachCount = _game?.lastWaveBreachCount ?? 0;

    // ドロップ素材を抽出システムに登録
    final drops = gs.battle?.droppedMaterials ?? {};
    drops.forEach((id, count) {
      _extractionSystem.addItem(ExtractionItem(
        itemId: id,
        displayName: id,
        goldValue: count * 10,
        state: ItemSecureState.atRisk,
      ));
    });

    // ウェーブクリア演出を先に見せてからショップへ
    setState(() {
      _clearedWaveNum = wave;
      _waveClearPerfect = breachCount == 0;
      _showWaveClear = true;
    });
    _waveClearCtrl.forward(from: 0.0);

    Future.delayed(const Duration(milliseconds: 1200), () {
      if (mounted) {
        setState(() {
          _shopWaveNumber = wave;
          _showShop = true;
          _showExtraction = false;
        });
      }
    });
  }

  void _onShopProceed() {
    setState(() {
      _showShop = false;
      _showExtraction = true;
    });
  }

  void _onExtractionContinue() {
    if (!mounted) return;
    final gs = context.read<GameStateNotifier>();
    gs.advanceWave();
    final nextWave = gs.battle?.currentWave ?? 1;
    _game?.prepareNextWave(nextWave);

    setState(() {
      _showExtraction = false;
    });

    // 全ウェーブ完了（waveSystem.prepareWaveが内部でendBattleを呼んだ場合）
    if (gs.phase == GamePhase.result) {
      gs.endBattle(isVictory: true).then((_) {
        if (mounted) {
          Navigator.of(context).pushReplacement(
            MaterialPageRoute(builder: (_) => const ResultScreen()),
          );
        }
      });
    }
  }

  void _onExtractionExtract() {
    if (!mounted) return;
    final gs = context.read<GameStateNotifier>();
    gs.endBattle(isVictory: true).then((_) {
      if (mounted) {
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => const ResultScreen()),
        );
      }
    });
  }

  void _handleCardPlaced(String cardId, int laneIndex) {
    // 将来: 配置統計・実績処理
  }

  void _handleChainTriggered(int chainCount, double damage) {
    setState(() {});
  }

  void _handleBossHpUpdate(String name, int maxHp, int currentHp) {
    if (!mounted) return;
    setState(() {
      _bossName = name;
      _bossMaxHp = maxHp;
      _bossCurrentHp = currentHp;
    });
  }

  void _handleWallDamaged(int damage) {
    if (!mounted) return;
    _wallFlashCtrl.forward(from: 0.0);
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

/// ウェーブ進行インジケーター（ドット＋現在波数）
class _WaveIndicator extends StatelessWidget {
  final int current;
  final int total;

  const _WaveIndicator({required this.current, required this.total});

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Text(
          'WAVE $current/$total',
          style: const TextStyle(
            color: Color(0xFFFFE082),
            fontFamily: 'DotGothic16',
            fontSize: 10,
          ),
        ),
        const SizedBox(height: 3),
        Row(
          mainAxisSize: MainAxisSize.min,
          children: List.generate(total, (i) {
            final done = i < current;
            final active = i == current - 1;
            return Padding(
              padding: const EdgeInsets.symmetric(horizontal: 1.5),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 300),
                width: active ? 8 : 5,
                height: 5,
                decoration: BoxDecoration(
                  color: done
                      ? const Color(0xFFFFE082)
                      : Colors.white24,
                  borderRadius: BorderRadius.circular(2),
                  boxShadow: active
                      ? [const BoxShadow(
                          color: Color(0xFFFFE082),
                          blurRadius: 4,
                        )]
                      : null,
                ),
              ),
            );
          }),
        ),
      ],
    );
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

/// 初回バトル時に表示する操作説明オーバーレイ
class _TutorialHint extends StatelessWidget {
  final VoidCallback onDismiss;

  const _TutorialHint({required this.onDismiss});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onDismiss,
      child: Container(
        color: Colors.black.withOpacity(0.75),
        child: SafeArea(
          child: Center(
            child: Container(
              margin: const EdgeInsets.symmetric(horizontal: 24),
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: const Color(0xFF12121E),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: const Color(0xFFFFE082).withOpacity(0.6)),
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text(
                    '⚔️ 遊び方',
                    style: TextStyle(
                      color: Color(0xFFFFE082),
                      fontSize: 20,
                      fontFamily: 'DotGothic16',
                    ),
                  ),
                  const SizedBox(height: 14),
                  _hint('👾', '敵が上から下へ自動侵攻してくる'),
                  _hint('🃏', '下のカードをドラッグして配置（左・中・右の列を選ぶ）'),
                  _hint('⚡', 'ユニットが自動で戦闘。属性有利で強くなる'),
                  _hint('🏰', '城壁HP（左上）をゼロにされたら敗北'),
                  _hint('💧', 'マナ（青バー）が溜まるとカードを置ける'),
                  _hint('🌊', '全敵を倒してウェーブクリア→ショップへ'),
                  const SizedBox(height: 16),
                  ElevatedButton(
                    onPressed: onDismiss,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFFE65100),
                    ),
                    child: const Text(
                      'バトル開始！',
                      style: TextStyle(fontFamily: 'DotGothic16'),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _hint(String emoji, String text) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Text(emoji, style: const TextStyle(fontSize: 18)),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 13,
                fontFamily: 'DotGothic16',
                height: 1.4,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ============================================================
// ボスHPバー
// ============================================================
class _BossHPBar extends StatelessWidget {
  final String name;
  final int maxHp;
  final int currentHp;

  const _BossHPBar({
    required this.name,
    required this.maxHp,
    required this.currentHp,
  });

  @override
  Widget build(BuildContext context) {
    final ratio = maxHp > 0 ? (currentHp / maxHp).clamp(0.0, 1.0) : 0.0;
    final hpColor = ratio > 0.5
        ? const Color(0xFFFF5252)
        : ratio > 0.25
            ? const Color(0xFFFF8A00)
            : const Color(0xFFFFCC00);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.black.withOpacity(0.85),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFFFF5252).withOpacity(0.7), width: 1.5),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFFFF0000).withOpacity(0.4),
            blurRadius: 16,
            spreadRadius: 2,
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              const Text('💀', style: TextStyle(fontSize: 14)),
              const SizedBox(width: 6),
              Text(
                name,
                style: const TextStyle(
                  color: Color(0xFFFF5252),
                  fontFamily: 'DotGothic16',
                  fontSize: 13,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 1,
                ),
              ),
              const Spacer(),
              Text(
                '$currentHp / $maxHp',
                style: TextStyle(
                  color: hpColor,
                  fontFamily: 'DotGothic16',
                  fontSize: 11,
                ),
              ),
            ],
          ),
          const SizedBox(height: 5),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: ratio,
              minHeight: 8,
              backgroundColor: Colors.white12,
              valueColor: AlwaysStoppedAnimation(hpColor),
            ),
          ),
        ],
      ),
    );
  }
}

// ============================================================
// ウェーブクリア演出オーバーレイ
// ============================================================
class _WaveClearOverlay extends StatelessWidget {
  final int waveNumber;
  final bool isPerfect;
  final Animation<double> animation;

  const _WaveClearOverlay({
    required this.waveNumber,
    required this.isPerfect,
    required this.animation,
  });

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: animation,
      builder: (_, __) {
        final t = animation.value;
        final opacity = t < 0.3
            ? t / 0.3
            : t > 0.75
                ? (1.0 - t) / 0.25
                : 1.0;
        final scale = 0.7 + t * 0.3;

        final mainColor = isPerfect ? const Color(0xFF69F0AE) : const Color(0xFFFFD700);
        final clearText = isPerfect ? 'P E R F E C T !!' : 'C L E A R !';
        final subText = isPerfect ? '全敵撃破！城壁無傷' : 'WAVE $waveNumber';

        return Opacity(
          opacity: opacity.clamp(0.0, 1.0),
          child: Center(
            child: Transform.scale(
              scale: scale,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (!isPerfect)
                    Text(
                      subText,
                      style: const TextStyle(
                        color: Color(0xFFFFD700),
                        fontFamily: 'DotGothic16',
                        fontSize: 18,
                        letterSpacing: 4,
                      ),
                    ),
                  Text(
                    clearText,
                    style: TextStyle(
                      color: Colors.white,
                      fontFamily: 'DotGothic16',
                      fontSize: isPerfect ? 32 : 36,
                      fontWeight: FontWeight.bold,
                      letterSpacing: 5,
                      shadows: [
                        Shadow(color: mainColor, blurRadius: 28),
                        Shadow(color: mainColor, blurRadius: 12),
                      ],
                    ),
                  ),
                  if (isPerfect)
                    Text(
                      subText,
                      style: TextStyle(
                        color: mainColor,
                        fontFamily: 'DotGothic16',
                        fontSize: 15,
                        letterSpacing: 2,
                      ),
                    ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}
