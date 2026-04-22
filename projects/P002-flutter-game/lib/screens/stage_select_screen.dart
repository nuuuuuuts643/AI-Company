import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../game/game_state.dart';
import '../models/stage_data.dart';
import '../constants/strings.dart';
import 'battle_screen.dart';

/// ステージ選択画面
class StageSelectScreen extends StatelessWidget {
  const StageSelectScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final player = context.watch<GameStateNotifier>().player;

    return Scaffold(
      backgroundColor: const Color(0xFF0D0D1A),
      body: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ヘッダー
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
              child: Row(
                children: [
                  IconButton(
                    icon: const Icon(Icons.arrow_back_ios, color: Colors.white70),
                    onPressed: () => Navigator.of(context).pop(),
                  ),
                  const Text(
                    Strings.stageSelectTitle,
                    style: TextStyle(
                      color: Color(0xFFFFE082),
                      fontSize: 22,
                      fontFamily: 'DotGothic16',
                    ),
                  ),
                  const Spacer(),
                  // 所持金表示
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: const Color(0xFF1A1A2E),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: const Color(0xFFFFD700).withOpacity(0.5)),
                    ),
                    child: Row(
                      children: [
                        const Text('💰', style: TextStyle(fontSize: 14)),
                        const SizedBox(width: 4),
                        Text(
                          '${player.gold}',
                          style: const TextStyle(
                            color: Color(0xFFFFD700),
                            fontFamily: 'DotGothic16',
                            fontSize: 14,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),

            // ステージリスト
            Expanded(
              child: ListView.separated(
                padding: const EdgeInsets.all(16),
                itemCount: StageMaster.stages.length,
                separatorBuilder: (_, __) => const SizedBox(height: 12),
                itemBuilder: (context, index) {
                  final stage = StageMaster.stages[index];
                  final isUnlocked = player.unlockedStageIds.contains(stage.id);
                  final bestScore = player.stageBestScores[stage.id] ?? 0;

                  return _StageCard(
                    stage: stage,
                    isUnlocked: isUnlocked,
                    bestScore: bestScore,
                    onTap: isUnlocked
                        ? () => _startBattle(context, stage.id)
                        : null,
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _startBattle(BuildContext context, String stageId) {
    final notifier = context.read<GameStateNotifier>();
    notifier.selectStage(stageId);
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const BattleScreen()),
    );
  }
}

class _StageCard extends StatelessWidget {
  final StageData stage;
  final bool isUnlocked;
  final int bestScore;
  final VoidCallback? onTap;

  const _StageCard({
    required this.stage,
    required this.isUnlocked,
    required this.bestScore,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final borderColor = isUnlocked
        ? const Color(0xFF4A7C59)
        : Colors.grey.withOpacity(0.3);

    return GestureDetector(
      onTap: onTap,
      child: Opacity(
        opacity: isUnlocked ? 1.0 : 0.5,
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: const Color(0xFF12121E),
            border: Border.all(color: borderColor, width: 1.5),
            borderRadius: BorderRadius.circular(8),
            boxShadow: isUnlocked
                ? [BoxShadow(color: borderColor.withOpacity(0.3), blurRadius: 8)]
                : null,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  // ステージ番号バッジ
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                      color: isUnlocked
                          ? const Color(0xFF4A7C59)
                          : Colors.grey.withOpacity(0.3),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      'Ch.${stage.stageNumber}',
                      style: const TextStyle(
                        color: Colors.white,
                        fontFamily: 'DotGothic16',
                        fontSize: 11,
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      stage.name,
                      style: TextStyle(
                        color: isUnlocked ? const Color(0xFFFFE082) : Colors.grey,
                        fontFamily: 'DotGothic16',
                        fontSize: 16,
                      ),
                    ),
                  ),
                  // 鍵アイコン or スコア評価
                  if (!isUnlocked)
                    const Icon(Icons.lock, color: Colors.grey, size: 18)
                  else if (bestScore > 0)
                    _StarRating(score: bestScore, threshold: stage.clearScoreThreshold),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                stage.description,
                style: TextStyle(
                  color: Colors.white.withOpacity(0.6),
                  fontFamily: 'DotGothic16',
                  fontSize: 12,
                ),
              ),
              if (isUnlocked && bestScore > 0) ...[
                const SizedBox(height: 8),
                Row(
                  children: [
                    const Icon(Icons.emoji_events, color: Color(0xFFFFD700), size: 14),
                    const SizedBox(width: 4),
                    Text(
                      '${Strings.bestScore}: $bestScore',
                      style: const TextStyle(
                        color: Color(0xFFFFD700),
                        fontFamily: 'DotGothic16',
                        fontSize: 12,
                      ),
                    ),
                    const Spacer(),
                    Text(
                      '${Strings.waveLabel} ${stage.waves.length}',
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.4),
                        fontFamily: 'DotGothic16',
                        fontSize: 11,
                      ),
                    ),
                  ],
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _StarRating extends StatelessWidget {
  final int score;
  final int threshold;

  const _StarRating({required this.score, required this.threshold});

  @override
  Widget build(BuildContext context) {
    final ratio = score / threshold;
    final stars = ratio >= 1.0 ? 3 : ratio >= 0.6 ? 2 : 1;
    return Row(
      children: List.generate(3, (i) {
        return Icon(
          Icons.star,
          size: 14,
          color: i < stars ? const Color(0xFFFFD700) : Colors.grey.withOpacity(0.3),
        );
      }),
    );
  }
}
