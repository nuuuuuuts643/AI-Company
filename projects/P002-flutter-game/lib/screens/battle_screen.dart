import 'package:flame/game.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../game/game_state.dart';
import '../game/octo_battle_game.dart';
import '../constants/element_chart.dart';
import '../constants/strings.dart';
import '../models/stage_data.dart';
import '../services/audio_service.dart';
import '../systems/boon_system.dart';
import '../systems/event_system.dart';
import '../systems/extraction_system.dart';
import '../utils/app_transitions.dart';
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

  // ローグライト ボーンシステム
  final BoonSystem _boonSystem = BoonSystem();
  bool _showBoonSelect = false;
  List<BoonData> _boonChoices = [];

  // ウェーブ間イベント表示用
  WaveEvent? _pendingEvent;
  bool _showEventModal = false;

  // ウェーブクリア後のショップ・抽出UI
  bool _showShop = false;
  bool _showExtraction = false;
  int _shopWaveNumber = 1;

  // チュートリアルヒント（初回のみ）
  bool _showTutorial = false;

  // 配備フェーズ（バトル開始前）
  bool _formationPhase = true;
  int _formationCountdown = 10;

  // コマンダースキル
  static const _cmdSkillMaxCd = 35.0;
  double _cmdSkillCd = 0.0; // 0=使用可能, >0=クールダウン中
  late AnimationController _cmdSkillCtrl;

  // チェーンコンボメーター
  int _comboCount = 0;
  double _comboDecayTimer = 0.0;
  late AnimationController _comboFlashCtrl;

  // ボスHPバー
  String _bossName = '';
  int _bossMaxHp = 0;
  int _bossCurrentHp = 0;
  bool get _bossActive => _bossName.isNotEmpty && _bossMaxHp > 0;

  // 城壁ダメージフラッシュ
  late AnimationController _wallFlashCtrl;
  late Animation<double> _wallFlashOpacity;

  // ウェーブクリア演出
  bool _showWaveClear = false;
  bool _waveClearPerfect = false;
  int _clearedWaveNum = 0;
  late AnimationController _waveClearCtrl;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        final seen = context.read<GameStateNotifier>().tutorialSeen;
        if (!seen) setState(() => _showTutorial = true);
        _startFormationCountdown();
      }
    });

    _wallFlashCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 400),
      value: 1.0,
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

    // コマンダースキル アニメーション
    _cmdSkillCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 600),
    );

    // コンボフラッシュ
    _comboFlashCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 300),
    );
  }

  @override
  void dispose() {
    _wallFlashCtrl.dispose();
    _waveClearCtrl.dispose();
    _cmdSkillCtrl.dispose();
    _comboFlashCtrl.dispose();
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
        // ボーンでの全ユニットパワーアップをgameに委譲
        gameState.onPowerUpAllUnits = () => _game?.powerUpAllDeployedUnits();

        // CDタイマー（60fps相当でtick）
        Future.doWhile(() async {
          if (!mounted) return false;
          await Future.delayed(const Duration(milliseconds: 100));
          if (mounted) _tickCooldowns(0.1);
          return mounted;
        });
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
              _game?.setDraggingCard(false);
            },
            onLeave: (_) => _game?.setDraggingCard(false),
            builder: (ctx, candidateItems, _) {
              // ドラッグ状態をゲームに通知
              final dragging = candidateItems.isNotEmpty;
              WidgetsBinding.instance.addPostFrameCallback((_) {
                _game?.setDraggingCard(dragging);
              });
              return Positioned.fill(child: GameWidget(game: _game!));
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

          // ---- ウェーブ間インターバルヒント（次の敵・弱点表示） ----
          if ((_game?.isLoaded ?? false) &&
              (_game?.waveSystem.isInInterval ?? false) &&
              !_showShop && !_showExtraction && !_showBoonSelect)
            Positioned(
              top: 72,
              left: 8,
              right: 8,
              child: SafeArea(
                child: _WaveIntervalHint(game: _game!),
              ),
            ),

          // ---- チュートリアルヒント（初回のみ）----
          if (_showTutorial)
            _TutorialHint(onDismiss: () {
              setState(() => _showTutorial = false);
              context.read<GameStateNotifier>().markTutorialSeen();
            }),

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

          // ---- コマンダースキルボタン（左下、カードハンドの上） ----
          if (!_showShop && !_showExtraction && !_showBoonSelect)
            Positioned(
              left: 12,
              bottom: 148,
              child: _CommanderSkillButton(
                cooldownRatio: _cmdSkillCd / (_cmdSkillMaxCd - _boonSystem.commanderCdReduction.clamp(0, _cmdSkillMaxCd - 5)),
                onTap: _onCommanderSkillTap,
              ),
            ),

          // ---- チェーンコンボメーター ----
          if (_comboCount >= 2 && !_showShop && !_showExtraction)
            Positioned(
              right: 12,
              bottom: 148,
              child: _ComboMeter(count: _comboCount, flashCtrl: _comboFlashCtrl),
            ),

          // ---- ボーン選択画面 ----
          if (_showBoonSelect)
            Positioned.fill(
              child: _BoonSelectScreen(
                boons: _boonChoices,
                onSelected: _onBoonSelected,
              ),
            ),

          // ---- 配備フェーズオーバーレイ ----
          if (_formationPhase)
            Positioned.fill(
              child: _FormationOverlay(
                countdown: _formationCountdown,
                onStart: _endFormation,
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
            AppTransitions.scaleReveal(const ResultScreen()),
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
        // ボーン選択を先に出す → 選択後にショップへ
        final choices = _boonSystem.rollBoons(waveNumber: wave);
        setState(() {
          _boonChoices = choices;
          _showBoonSelect = true;
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
            AppTransitions.scaleReveal(const ResultScreen()),
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

  void _startFormationCountdown() {
    Future.doWhile(() async {
      await Future.delayed(const Duration(seconds: 1));
      if (!mounted || !_formationPhase) return false;
      if (_formationCountdown <= 1) {
        _endFormation();
        return false;
      }
      setState(() => _formationCountdown--);
      return true;
    });
  }

  void _endFormation() {
    if (!mounted || !_formationPhase) return;
    setState(() => _formationPhase = false);
    _game?.endFormation();
  }

  void _handleCardPlaced(String cardId, int laneIndex) {}

  void _handleChainTriggered(int chainCount, double damage) {
    setState(() {
      _comboCount += chainCount;
      _comboDecayTimer = 4.0; // 4秒操作なしでリセット
    });
    _comboFlashCtrl.forward(from: 0.0);

    // コンボ5以上でコマンダースキルCD短縮
    if (_comboCount >= 5) {
      setState(() => _cmdSkillCd = (_cmdSkillCd - 3.0).clamp(0.0, 999));
    }
  }

  void _tickCooldowns(double dt) {
    if (!mounted) return;
    bool changed = false;
    if (_cmdSkillCd > 0) {
      _cmdSkillCd = (_cmdSkillCd - dt).clamp(0.0, 999);
      changed = true;
    }
    if (_comboDecayTimer > 0) {
      _comboDecayTimer -= dt;
      if (_comboDecayTimer <= 0 && _comboCount > 0) {
        _comboCount = 0;
        changed = true;
      }
    }
    // ウェーブ間インターバル中はカウントダウン表示のため常にリビルド
    // isLoaded チェックで onLoad() 前のアクセスを防ぐ
    if ((_game?.isLoaded ?? false) && (_game?.waveSystem.isInInterval ?? false)) changed = true;
    if (changed && mounted) setState(() {});
  }

  void _onCommanderSkillTap() {
    final effectiveCd = (_cmdSkillMaxCd - _boonSystem.commanderCdReduction).clamp(5.0, _cmdSkillMaxCd);
    if (_cmdSkillCd > 0) return;
    _game?.castCommanderSkill();
    setState(() => _cmdSkillCd = effectiveCd);
    _cmdSkillCtrl.forward(from: 0.0);
  }

  void _onBoonSelected(BoonData boon) {
    final gs = context.read<GameStateNotifier>();
    _boonSystem.applyBoon(boon, gs);
    setState(() {
      _showBoonSelect = false;
      _shopWaveNumber = gs.battle?.currentWave ?? 1;
      _showShop = true;
    });
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

// =============================================================
// コマンダースキルボタン
// =============================================================
class _CommanderSkillButton extends StatelessWidget {
  final double cooldownRatio; // 0=使用可能, 1=CD満タン
  final VoidCallback onTap;
  const _CommanderSkillButton({required this.cooldownRatio, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final ready = cooldownRatio <= 0;
    return GestureDetector(
      onTap: ready ? onTap : null,
      child: Stack(
        alignment: Alignment.center,
        children: [
          // 外周CDリング
          SizedBox(
            width: 68,
            height: 68,
            child: CircularProgressIndicator(
              value: ready ? 1.0 : (1.0 - cooldownRatio),
              strokeWidth: 4,
              backgroundColor: Colors.white12,
              valueColor: AlwaysStoppedAnimation(
                ready ? const Color(0xFFFFD700) : const Color(0xFF455A64),
              ),
            ),
          ),
          // ボタン本体
          Container(
            width: 58,
            height: 58,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: RadialGradient(
                colors: ready
                    ? [const Color(0xFFFFE082), const Color(0xFFE65100)]
                    : [const Color(0xFF37474F), const Color(0xFF263238)],
              ),
              boxShadow: ready
                  ? [const BoxShadow(color: Color(0xAAFFD700), blurRadius: 16, spreadRadius: 2)]
                  : [],
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(ready ? '⚡' : '⚡', style: TextStyle(fontSize: 22, color: ready ? null : Colors.white24)),
                Text(
                  ready ? 'READY' : 'CD',
                  style: TextStyle(
                    color: ready ? const Color(0xFFFFE082) : Colors.white24,
                    fontFamily: 'DotGothic16',
                    fontSize: 8,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// =============================================================
// チェーンコンボメーター
// =============================================================
class _ComboMeter extends StatelessWidget {
  final int count;
  final AnimationController flashCtrl;
  const _ComboMeter({required this.count, required this.flashCtrl});

  @override
  Widget build(BuildContext context) {
    final color = count >= 10
        ? const Color(0xFFFF1744)
        : count >= 5
            ? const Color(0xFFFFD700)
            : const Color(0xFF69F0AE);

    return AnimatedBuilder(
      animation: flashCtrl,
      builder: (_, __) {
        final flash = flashCtrl.status == AnimationStatus.forward
            ? (1.0 - flashCtrl.value) * 0.5
            : 0.0;
        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
          decoration: BoxDecoration(
            color: Color.lerp(const Color(0xCC0D0D1A), color, flash),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: color, width: 2),
            boxShadow: [BoxShadow(color: color.withAlpha(120), blurRadius: 12)],
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                'COMBO',
                style: TextStyle(
                  color: color,
                  fontFamily: 'DotGothic16',
                  fontSize: 9,
                  letterSpacing: 2,
                ),
              ),
              Text(
                '×$count',
                style: TextStyle(
                  color: color,
                  fontFamily: 'DotGothic16',
                  fontSize: 26,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

// =============================================================
// ボーン選択画面（ウェーブ後に3択）
// =============================================================
class _BoonSelectScreen extends StatefulWidget {
  final List<BoonData> boons;
  final void Function(BoonData) onSelected;
  const _BoonSelectScreen({required this.boons, required this.onSelected});

  @override
  State<_BoonSelectScreen> createState() => _BoonSelectScreenState();
}

class _BoonSelectScreenState extends State<_BoonSelectScreen>
    with SingleTickerProviderStateMixin {
  late AnimationController _enterCtrl;
  late Animation<double> _scale;
  late Animation<double> _opacity;

  @override
  void initState() {
    super.initState();
    _enterCtrl = AnimationController(vsync: this, duration: const Duration(milliseconds: 500));
    _scale = Tween<double>(begin: 0.85, end: 1.0)
        .animate(CurvedAnimation(parent: _enterCtrl, curve: Curves.easeOutBack));
    _opacity = Tween<double>(begin: 0.0, end: 1.0)
        .animate(CurvedAnimation(parent: _enterCtrl, curve: Curves.easeIn));
    _enterCtrl.forward();
  }

  @override
  void dispose() {
    _enterCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _enterCtrl,
      builder: (_, child) => Opacity(
        opacity: _opacity.value,
        child: ScaleTransition(scale: _scale, child: child),
      ),
      child: Container(
        color: Colors.black87,
        child: SafeArea(
          child: Column(
            children: [
              const SizedBox(height: 32),
              // ヘッダー
              const Text(
                '✨ 強化を選択',
                style: TextStyle(
                  color: Color(0xFFFFE082),
                  fontFamily: 'DotGothic16',
                  fontSize: 22,
                  letterSpacing: 3,
                ),
              ),
              const SizedBox(height: 6),
              const Text(
                'ウェーブクリアボーナス — 1つ選べ',
                style: TextStyle(
                  color: Colors.white38,
                  fontFamily: 'DotGothic16',
                  fontSize: 12,
                ),
              ),
              const SizedBox(height: 32),

              // ボーンカード3枚
              Expanded(
                child: ListView.separated(
                  padding: const EdgeInsets.symmetric(horizontal: 20),
                  itemCount: widget.boons.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 16),
                  itemBuilder: (_, i) => _BoonCard(
                    boon: widget.boons[i],
                    onTap: () => widget.onSelected(widget.boons[i]),
                  ),
                ),
              ),
              const SizedBox(height: 24),
            ],
          ),
        ),
      ),
    );
  }
}

class _BoonCard extends StatelessWidget {
  final BoonData boon;
  final VoidCallback onTap;
  const _BoonCard({required this.boon, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final rarityColor = switch (boon.rarity) {
      BoonRarity.common => const Color(0xFF78909C),
      BoonRarity.rare   => const Color(0xFF7E57C2),
      BoonRarity.epic   => const Color(0xFFFFD700),
    };
    final rarityLabel = switch (boon.rarity) {
      BoonRarity.common => 'COMMON',
      BoonRarity.rare   => 'RARE',
      BoonRarity.epic   => 'EPIC',
    };

    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              rarityColor.withAlpha(30),
              Colors.black54,
            ],
          ),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: rarityColor, width: 2),
          boxShadow: [
            BoxShadow(color: rarityColor.withAlpha(60), blurRadius: 12, spreadRadius: 1),
          ],
        ),
        child: Row(
          children: [
            // 絵文字アイコン
            Container(
              width: 60,
              height: 60,
              decoration: BoxDecoration(
                color: rarityColor.withAlpha(30),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: rarityColor.withAlpha(100)),
              ),
              child: Center(
                child: Text(boon.emoji, style: const TextStyle(fontSize: 28)),
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: rarityColor.withAlpha(40),
                          borderRadius: BorderRadius.circular(4),
                          border: Border.all(color: rarityColor.withAlpha(120)),
                        ),
                        child: Text(
                          rarityLabel,
                          style: TextStyle(
                            color: rarityColor,
                            fontFamily: 'DotGothic16',
                            fontSize: 9,
                            letterSpacing: 1,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Text(
                    boon.name,
                    style: const TextStyle(
                      color: Colors.white,
                      fontFamily: 'DotGothic16',
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    boon.description,
                    style: const TextStyle(
                      color: Colors.white70,
                      fontFamily: 'DotGothic16',
                      fontSize: 12,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            Icon(Icons.chevron_right, color: rarityColor, size: 24),
          ],
        ),
      ),
    );
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
// ============================================================
// チュートリアル（ステップ式・多ページ）
// ============================================================
class _TutorialHint extends StatefulWidget {
  final VoidCallback onDismiss;
  const _TutorialHint({required this.onDismiss});

  @override
  State<_TutorialHint> createState() => _TutorialHintState();
}

class _TutorialHintState extends State<_TutorialHint>
    with SingleTickerProviderStateMixin {
  int _page = 0;
  late AnimationController _ctrl;
  late Animation<double> _fade;

  static const _pages = [
    _TutPage(
      title: 'このゲームは？',
      emoji: '🏰',
      visual: _TutVisual.castle,
      body: '敵が上から攻めてくる。\n城壁のHPがゼロになったら負け。\n全ウェーブ撃退したらクリア！',
    ),
    _TutPage(
      title: 'カードの使い方',
      emoji: '🃏',
      visual: _TutVisual.drag,
      body: '画面下のカードをドラッグして\n左・中・右の列（レーン）に置く。\nマナ💧が足りないと配置できない。',
    ),
    _TutPage(
      title: 'レーンを守れ',
      emoji: '🛡️',
      visual: _TutVisual.lanes,
      body: '同じレーンの敵しか攻撃しない！\n敵が来るレーンにユニットを置こう。\nウェーブ前に敵の数が予告される。',
    ),
    _TutPage(
      title: '属性相性',
      emoji: '🔥',
      visual: _TutVisual.elements,
      body: '有利属性で攻撃すると\nダメージが1.5倍になる！\n敵の頭上に弱点アイコンが出ている。',
    ),
    _TutPage(
      title: 'マナ管理',
      emoji: '💧',
      visual: _TutVisual.mana,
      body: 'マナは時間で自動回復する。\n強いカードほどコストが高い。\nタイミングを見て使おう！',
    ),
  ];

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: const Duration(milliseconds: 250));
    _fade = Tween<double>(begin: 0.0, end: 1.0).animate(_ctrl);
    _ctrl.forward();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  void _next() async {
    if (_page >= _pages.length - 1) {
      widget.onDismiss();
      return;
    }
    await _ctrl.reverse();
    setState(() => _page++);
    _ctrl.forward();
  }

  void _prev() async {
    if (_page <= 0) return;
    await _ctrl.reverse();
    setState(() => _page--);
    _ctrl.forward();
  }

  @override
  Widget build(BuildContext context) {
    final page = _pages[_page];
    final isLast = _page == _pages.length - 1;

    return Container(
      color: Colors.black.withAlpha(200),
      child: SafeArea(
        child: Center(
          child: FadeTransition(
            opacity: _fade,
            child: Container(
              margin: const EdgeInsets.symmetric(horizontal: 20),
              decoration: BoxDecoration(
                color: const Color(0xFF0F0F1E),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: const Color(0xFFFFE082).withAlpha(100), width: 1.5),
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  // ヘッダー
                  Container(
                    padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 20),
                    decoration: const BoxDecoration(
                      color: Color(0xFF1A1A30),
                      borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
                    ),
                    child: Row(
                      children: [
                        Text(page.emoji, style: const TextStyle(fontSize: 22)),
                        const SizedBox(width: 10),
                        Text(
                          page.title,
                          style: const TextStyle(
                            color: Color(0xFFFFE082),
                            fontFamily: 'DotGothic16',
                            fontSize: 17,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const Spacer(),
                        Text(
                          '${_page + 1} / ${_pages.length}',
                          style: TextStyle(
                            color: Colors.white.withAlpha(100),
                            fontFamily: 'DotGothic16',
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                  ),

                  // ビジュアル
                  Padding(
                    padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
                    child: _TutorialVisualWidget(page.visual),
                  ),

                  // 説明文
                  Padding(
                    padding: const EdgeInsets.fromLTRB(20, 14, 20, 16),
                    child: Text(
                      page.body,
                      style: const TextStyle(
                        color: Colors.white,
                        fontFamily: 'DotGothic16',
                        fontSize: 14,
                        height: 1.8,
                      ),
                      textAlign: TextAlign.center,
                    ),
                  ),

                  // ページドット
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: List.generate(_pages.length, (i) => Container(
                      width: i == _page ? 16 : 6,
                      height: 6,
                      margin: const EdgeInsets.symmetric(horizontal: 3),
                      decoration: BoxDecoration(
                        color: i == _page
                            ? const Color(0xFFFFE082)
                            : Colors.white.withAlpha(60),
                        borderRadius: BorderRadius.circular(3),
                      ),
                    )),
                  ),
                  const SizedBox(height: 14),

                  // ボタン行
                  Padding(
                    padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
                    child: Row(
                      children: [
                        if (_page > 0)
                          Expanded(
                            child: OutlinedButton(
                              onPressed: _prev,
                              style: OutlinedButton.styleFrom(
                                foregroundColor: Colors.white54,
                                side: const BorderSide(color: Colors.white24),
                              ),
                              child: const Text('← もどる',
                                  style: TextStyle(fontFamily: 'DotGothic16', fontSize: 13)),
                            ),
                          ),
                        if (_page > 0) const SizedBox(width: 10),
                        Expanded(
                          flex: 2,
                          child: ElevatedButton(
                            onPressed: _next,
                            style: ElevatedButton.styleFrom(
                              backgroundColor: isLast
                                  ? const Color(0xFFE65100)
                                  : const Color(0xFF1565C0),
                              padding: const EdgeInsets.symmetric(vertical: 14),
                              shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(8)),
                            ),
                            child: Text(
                              isLast ? '⚔️ バトル開始！' : 'つぎへ →',
                              style: const TextStyle(
                                  fontFamily: 'DotGothic16', fontSize: 14),
                            ),
                          ),
                        ),
                      ],
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
}

class _TutPage {
  final String title;
  final String emoji;
  final _TutVisual visual;
  final String body;
  const _TutPage({
    required this.title,
    required this.emoji,
    required this.visual,
    required this.body,
  });
}

enum _TutVisual { castle, drag, lanes, elements, mana }

class _TutorialVisualWidget extends StatelessWidget {
  final _TutVisual type;
  const _TutorialVisualWidget(this.type);

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 120,
      width: double.infinity,
      child: CustomPaint(painter: _TutVisualPainter(type)),
    );
  }
}

class _TutVisualPainter extends CustomPainter {
  final _TutVisual type;
  _TutVisualPainter(this.type);

  @override
  void paint(Canvas canvas, Size size) {
    switch (type) {
      case _TutVisual.castle: _drawCastle(canvas, size); break;
      case _TutVisual.drag:   _drawDrag(canvas, size);   break;
      case _TutVisual.lanes:  _drawLanes(canvas, size);  break;
      case _TutVisual.elements: _drawElements(canvas, size); break;
      case _TutVisual.mana:   _drawMana(canvas, size);   break;
    }
  }

  void _drawCastle(Canvas canvas, Size size) {
    final cx = size.width / 2;
    // 城壁
    canvas.drawRect(
      Rect.fromLTWH(cx - 70, size.height - 28, 140, 20),
      Paint()..color = const Color(0xFFFF8F00),
    );
    // バトルメント（歯型）
    final mPaint = Paint()..color = const Color(0xFF1A1810);
    for (int i = 0; i < 6; i++) {
      canvas.drawRect(
        Rect.fromLTWH(cx - 70 + i * 24, size.height - 42, 14, 16),
        mPaint,
      );
    }
    // HPバー
    canvas.drawRect(
      Rect.fromLTWH(cx - 60, size.height - 58, 120, 10),
      Paint()..color = Colors.black54,
    );
    canvas.drawRect(
      Rect.fromLTWH(cx - 60, size.height - 58, 100, 10),
      Paint()..color = const Color(0xFF66BB6A),
    );
    _drawTp(canvas, '🏰 HP', 11, Offset(cx - 30, size.height - 70), Colors.white70);
    // 敵矢印
    _drawTp(canvas, '👾', 28, Offset(cx - 40, 30), Colors.white);
    _drawTp(canvas, '👾', 28, Offset(cx, 15), Colors.white);
    _drawTp(canvas, '👾', 28, Offset(cx + 40, 30), Colors.white);
    // 矢印↓
    for (final x in [cx - 40, cx, cx + 40]) {
      canvas.drawLine(
        Offset(x, 50),
        Offset(x, 70),
        Paint()..color = const Color(0xFFEF5350)..strokeWidth = 2,
      );
      _drawTp(canvas, '▼', 10, Offset(x, 78), const Color(0xFFEF5350));
    }
  }

  void _drawDrag(Canvas canvas, Size size) {
    final cx = size.width / 2;
    // カード
    final cardRect = RRect.fromRectAndRadius(
      Rect.fromCenter(center: Offset(cx - 30, size.height - 30), width: 50, height: 65),
      const Radius.circular(6),
    );
    canvas.drawRRect(cardRect, Paint()..color = const Color(0xFF1A1A3A));
    canvas.drawRRect(cardRect, Paint()..color = const Color(0xFFFF7043)..style = PaintingStyle.stroke..strokeWidth = 1.5);
    _drawTp(canvas, '🔥', 18, Offset(cx - 30, size.height - 35), Colors.white);
    _drawTp(canvas, '炎剣士', 10, Offset(cx - 30, size.height - 18), Colors.white70);
    // ドラッグ矢印
    final arrowPaint = Paint()
      ..color = const Color(0xFFFFE082)
      ..strokeWidth = 2.5
      ..style = PaintingStyle.stroke;
    final path = Path()
      ..moveTo(cx - 30, size.height - 55)
      ..quadraticBezierTo(cx - 30, size.height - 120, cx + 20, 40);
    canvas.drawPath(path, arrowPaint);
    _drawTp(canvas, '↑ ドラッグ', 11, Offset(cx + 5, 25), const Color(0xFFFFE082));
    // レーン配置先
    canvas.drawRect(
      Rect.fromLTWH(cx + 5, 45, 45, 55),
      Paint()..color = const Color(0xFF0D4A1A)..style = PaintingStyle.fill,
    );
    canvas.drawRect(
      Rect.fromLTWH(cx + 5, 45, 45, 55),
      Paint()..color = const Color(0xFF66BB6A)..style = PaintingStyle.stroke..strokeWidth = 1.5,
    );
    _drawTp(canvas, '⚔️', 20, Offset(cx + 28, 75), Colors.white);
  }

  void _drawLanes(Canvas canvas, Size size) {
    const laneW = 80.0;
    final startX = (size.width - laneW * 3) / 2;
    final laneColors = [
      const Color(0xFF1A0A2E),
      const Color(0xFF0A1A2E),
      const Color(0xFF0A2E1A),
    ];
    final labels = ['左', '中', '右'];
    final enemyCounts = [2, 3, 1];
    for (int i = 0; i < 3; i++) {
      final lx = startX + laneW * i;
      canvas.drawRect(
        Rect.fromLTWH(lx + 2, 0, laneW - 4, size.height),
        Paint()..color = laneColors[i],
      );
      // 敵
      for (int j = 0; j < enemyCounts[i]; j++) {
        _drawTp(canvas, '👾', 16, Offset(lx + laneW / 2, 18 + j * 22.0), Colors.white);
      }
      // ユニット（中レーンだけ配置済み）
      if (i == 1) {
        _drawTp(canvas, '🔥', 20, Offset(lx + laneW / 2, size.height - 30), Colors.white);
      } else {
        // 空レーン警告
        canvas.drawRect(
          Rect.fromLTWH(lx + 4, size.height - 44, laneW - 8, 34),
          Paint()..color = const Color(0x33EF5350),
        );
        _drawTp(canvas, '！', 16, Offset(lx + laneW / 2, size.height - 28), const Color(0xFFEF5350));
      }
      _drawTp(canvas, labels[i], 11, Offset(lx + laneW / 2, size.height - 8), Colors.white54);
    }
    // 縦仕切り
    for (int i = 1; i < 3; i++) {
      canvas.drawLine(
        Offset(startX + laneW * i, 0),
        Offset(startX + laneW * i, size.height),
        Paint()..color = Colors.white24..strokeWidth = 1,
      );
    }
  }

  void _drawElements(Canvas canvas, Size size) {
    final cx = size.width / 2;
    final cy = size.height / 2;
    const r = 40.0;
    final elems = [
      ('🔥', '火', const Color(0xFFEF5350), 0.0),
      ('💨', '風', const Color(0xFF66BB6A), 2 * 3.14159 / 3),
      ('🌊', '水', const Color(0xFF42A5F5), 4 * 3.14159 / 3),
    ];
    // 矢印（有利関係）
    final arrowPaint = Paint()
      ..color = Colors.white30
      ..strokeWidth = 1.5
      ..style = PaintingStyle.stroke;
    for (int i = 0; i < elems.length; i++) {
      final from = i;
      final to = (i + 1) % elems.length;
      final fromAngle = elems[from].$4;
      final toAngle = elems[to].$4;
      canvas.drawLine(
        Offset(cx + (r - 8) * _cos(fromAngle), cy + (r - 8) * _sin(fromAngle)),
        Offset(cx + (r - 8) * _cos(toAngle), cy + (r - 8) * _sin(toAngle)),
        arrowPaint,
      );
    }
    // 属性アイコン
    for (final e in elems) {
      final ex = cx + r * _cos(e.$4);
      final ey = cy + r * _sin(e.$4);
      canvas.drawCircle(Offset(ex, ey), 20, Paint()..color = e.$3.withAlpha(80));
      canvas.drawCircle(Offset(ex, ey), 20,
          Paint()..color = e.$3..style = PaintingStyle.stroke..strokeWidth = 1.5);
      _drawTp(canvas, e.$1, 18, Offset(ex, ey - 2), Colors.white);
      _drawTp(canvas, e.$2, 9, Offset(ex, ey + 13), e.$3);
    }
    _drawTp(canvas, '× 1.5', 13, Offset(cx, cy), const Color(0xFFFFE082));
    _drawTp(canvas, '有利なら', 10, Offset(cx, cy + 14), Colors.white54);
  }

  void _drawMana(Canvas canvas, Size size) {
    final cx = size.width / 2;
    // マナバー背景
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromCenter(center: Offset(cx, 35), width: 200, height: 22),
        const Radius.circular(11),
      ),
      Paint()..color = Colors.black45,
    );
    // マナ（70%）
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(cx - 100, 24, 140, 22),
        const Radius.circular(11),
      ),
      Paint()..color = const Color(0xFF1565C0),
    );
    _drawTp(canvas, '💧 7.0 / 10', 12, Offset(cx, 36), Colors.white);

    // カードコスト例
    for (int i = 0; i < 3; i++) {
      final cardX = cx - 60 + i * 60.0;
      final costs = [2, 3, 5];
      final canAfford = costs[i] <= 7;
      final cardColor = canAfford ? const Color(0xFF1A1A3A) : Colors.black38;
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromCenter(center: Offset(cardX, 85), width: 50, height: 58),
          const Radius.circular(6),
        ),
        Paint()..color = cardColor,
      );
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromCenter(center: Offset(cardX, 85), width: 50, height: 58),
          const Radius.circular(6),
        ),
        Paint()
          ..color = canAfford ? Colors.white30 : Colors.white10
          ..style = PaintingStyle.stroke,
      );
      // コスト泡
      canvas.drawCircle(
        Offset(cardX + 16, 60),
        10,
        Paint()..color = const Color(0xFF1565C0),
      );
      _drawTp(canvas, '${costs[i]}', 11, Offset(cardX + 16, 60), Colors.white);
      _drawTp(canvas, canAfford ? '✓' : '✗', 11, Offset(cardX, 88),
          canAfford ? const Color(0xFF66BB6A) : const Color(0xFFEF5350));
    }
    _drawTp(canvas, '↑ コスト2・3は置ける　5は無理', 10, Offset(cx, size.height - 10), Colors.white54);
  }

  double _cos(double a) => (a == 0) ? 1.0 : (a == 3.14159 * 2 / 3) ? -0.5 : -0.5;
  double _sin(double a) => (a == 0) ? 0.0 : (a == 3.14159 * 2 / 3) ? 0.866 : -0.866;

  void _drawTp(Canvas canvas, String text, double size, Offset center, Color color) {
    final tp = TextPainter(
      text: TextSpan(text: text, style: TextStyle(fontSize: size, color: color)),
      textDirection: TextDirection.ltr,
    )..layout();
    tp.paint(canvas, center - Offset(tp.width / 2, tp.height / 2));
  }

  @override
  bool shouldRepaint(_TutVisualPainter old) => old.type != type;
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

// ---- ウェーブ間インターバルヒント ----
// 次ウェーブの敵属性と弱点を表示して戦略的な準備を促す

class _WaveIntervalHint extends StatelessWidget {
  final OctoBattleGame game;
  const _WaveIntervalHint({required this.game});

  @override
  Widget build(BuildContext context) {
    final mainElem = game.waveSystem.nextWaveMainElement;
    final weakElem = mainElem != null ? ElementChart.getWeaknessOf(mainElem) : null;
    final countdown = game.waveSystem.intervalCountdown.ceil();

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: const Color(0xE60D0D1A),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFF2A2A4A), width: 1.5),
        boxShadow: const [BoxShadow(color: Color(0xAA000000), blurRadius: 10)],
      ),
      child: Row(
        children: [
          // カウントダウン
          Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                '$countdown',
                style: const TextStyle(
                  color: Color(0xFF69F0AE),
                  fontFamily: 'DotGothic16',
                  fontSize: 22,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const Text(
                '準備',
                style: TextStyle(
                  color: Colors.white38,
                  fontFamily: 'DotGothic16',
                  fontSize: 9,
                ),
              ),
            ],
          ),

          Container(width: 1, height: 40, color: const Color(0xFF2A2A4A),
              margin: const EdgeInsets.symmetric(horizontal: 12)),

          if (mainElem != null) ...[
            // 次ウェーブの主要属性
            Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(mainElem.emoji, style: const TextStyle(fontSize: 22)),
                Text(
                  '次: ${mainElem.label}属性',
                  style: const TextStyle(
                    color: Colors.white54,
                    fontFamily: 'DotGothic16',
                    fontSize: 9,
                  ),
                ),
              ],
            ),

            if (weakElem != null) ...[
              const Padding(
                padding: EdgeInsets.symmetric(horizontal: 10),
                child: Text('→', style: TextStyle(color: Colors.white30, fontSize: 18)),
              ),
              // 弱点属性（有利候補）
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: Color(weakElem.colorValue).withAlpha(25),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(
                      color: Color(weakElem.colorValue).withAlpha(120), width: 1.5),
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(weakElem.emoji, style: const TextStyle(fontSize: 22)),
                    Text(
                      '×2.0！',
                      style: TextStyle(
                        color: Color(weakElem.colorValue),
                        fontFamily: 'DotGothic16',
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ] else ...[
            const Text(
              'ウェーブ準備中...',
              style: TextStyle(
                color: Colors.white38,
                fontFamily: 'DotGothic16',
                fontSize: 11,
              ),
            ),
          ],

          const Spacer(),

          // 右端: 配置ヒント
          const Text(
            '⬇️ カードを\nレーンに配置',
            textAlign: TextAlign.right,
            style: TextStyle(
              color: Colors.white24,
              fontFamily: 'DotGothic16',
              fontSize: 8,
            ),
          ),
        ],
      ),
    );
  }
}

// =============================================================
// 配備フェーズオーバーレイ（バトル開始前）
// =============================================================
class _FormationOverlay extends StatelessWidget {
  final int countdown;
  final VoidCallback onStart;

  const _FormationOverlay({required this.countdown, required this.onStart});

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      ignoring: false,
      child: Stack(
        children: [
            // 下半分のみ暗く（上部フィールドは見える）
            Positioned(
              bottom: 0,
              left: 0,
              right: 0,
              height: 320,
              child: Container(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.bottomCenter,
                    end: Alignment.topCenter,
                    colors: [
                      Colors.black.withOpacity(0.82),
                      Colors.transparent,
                    ],
                  ),
                ),
              ),
            ),

            // 上部の指示パネル
            Positioned(
              top: 80,
              left: 20,
              right: 20,
              child: SafeArea(
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  decoration: BoxDecoration(
                    color: const Color(0xDD0D0D1A),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: const Color(0xFFFFE082).withOpacity(0.6), width: 1.5),
                    boxShadow: [
                      BoxShadow(
                        color: const Color(0xFFFFE082).withOpacity(0.2),
                        blurRadius: 16,
                      ),
                    ],
                  ),
                  child: Row(
                    children: [
                      const Text('⚔️', style: TextStyle(fontSize: 24)),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              '配備フェーズ',
                              style: TextStyle(
                                color: Color(0xFFFFE082),
                                fontFamily: 'DotGothic16',
                                fontSize: 14,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            const SizedBox(height: 3),
                            Text(
                              'ユニットをグリッドに配置しよう\n前列・後列で役割を分担！',
                              style: TextStyle(
                                color: Colors.white.withOpacity(0.7),
                                fontFamily: 'DotGothic16',
                                fontSize: 11,
                                height: 1.5,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),

            // BATTLE STARTボタン（下部中央）
            Positioned(
              bottom: 210,
              left: 40,
              right: 40,
              child: GestureDetector(
                onTap: onStart,
                child: Container(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [Color(0xFFE65100), Color(0xFFBF360C)],
                    ),
                    borderRadius: BorderRadius.circular(12),
                    boxShadow: const [
                      BoxShadow(color: Color(0xAAE65100), blurRadius: 20, spreadRadius: 2),
                    ],
                  ),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Text(
                        '⚔️ BATTLE START!',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          color: Colors.white,
                          fontFamily: 'DotGothic16',
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                          letterSpacing: 2,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'カウントダウン: $countdown 秒',
                        style: TextStyle(
                          color: Colors.white.withOpacity(0.7),
                          fontFamily: 'DotGothic16',
                          fontSize: 11,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      );
  }
}
