import 'dart:math';
import '../models/enemy_data.dart';
import '../models/stage_data.dart';
import '../constants/element_chart.dart';

/// プロシージャルステージジェネレーター
/// シード値（stageId + playerLevel）から決定論的にステージを生成する。
/// 同じシード = 常に同じステージ（バグ再現可能）。
/// プレイヤーの totalPower に応じて難易度をスケール。
class StageGenerator {
  /// ステージを生成
  /// [stageIndex] : 0始まりの通し番号（プロシージャル生成時に使う）
  /// [playerPower]: PlayerCharacter.totalPower
  static StageData generate({
    required int stageIndex,
    required int playerPower,
  }) {
    final seed = _computeSeed(stageIndex, playerPower);
    final rng = Random(seed);

    // 難易度スケール（playerPowerに線形比例）
    final difficultyScale = 1.0 + playerPower * 0.04;

    // ウェーブ数: 3〜6（stageIndexと乱数で決定）
    final waveCount = 3 + (stageIndex ~/ 2).clamp(0, 3) + rng.nextInt(2);

    // メイン属性を決定（ステージごとに特定属性が多く出る）
    final dominantElement = ElementType.values[rng.nextInt(ElementType.values.length)];

    // 背景IDを決定
    final bgId = _pickBackground(rng, dominantElement);

    // ウェーブを生成
    final waves = <WaveData>[];
    for (int w = 1; w <= waveCount; w++) {
      final isBossWave = w == waveCount;
      final wave = _generateWave(
        waveNumber: w,
        totalWaves: waveCount,
        isBossWave: isBossWave,
        dominantElement: dominantElement,
        difficultyScale: difficultyScale,
        rng: rng,
      );
      waves.add(wave);
    }

    // クリア報酬を決定
    final rewards = _generateRewards(rng, dominantElement, difficultyScale);

    // ☆3閾値（難易度に比例）
    final clearThreshold = (1000 * difficultyScale * waveCount).round();

    return StageData(
      id: 'stage_gen_${stageIndex}_p${playerPower}',
      name: _generateName(rng, dominantElement, stageIndex),
      description: _generateDescription(rng, dominantElement),
      stageNumber: stageIndex + 1,
      waves: waves,
      backgroundId: bgId,
      bgmId: _pickBgm(rng),
      clearRewards: rewards,
      clearScoreThreshold: clearThreshold,
      isUnlocked: true, // 生成ステージは常に解放済み
    );
  }

  // ---- 内部ジェネレーター ----

  static int _computeSeed(int stageIndex, int playerPower) {
    // 決定論的シード（stageIndex × 大きな素数 XOR playerPower）
    return (stageIndex * 1000003) ^ (playerPower * 999983);
  }

  static WaveData _generateWave({
    required int waveNumber,
    required int totalWaves,
    required bool isBossWave,
    required ElementType dominantElement,
    required double difficultyScale,
    required Random rng,
  }) {
    final enemies = <WaveEnemy>[];

    if (isBossWave) {
      // ボスウェーブ: 属性に対応したボスをスポーン
      final bossType = _pickBoss(dominantElement, rng);
      enemies.add(WaveEnemy(
        type: bossType,
        count: 1,
        laneIndex: 1, // 中レーン
      ));
      // ボス護衛
      final escortType = _pickNormalEnemy(dominantElement, rng);
      final escortCount = 2 + rng.nextInt(3); // 2〜4体
      enemies.add(WaveEnemy(
        type: escortType,
        count: escortCount,
        spawnDelaySeconds: 3.0,
      ));
    } else {
      // 通常ウェーブ: 1〜3グループの敵
      final groupCount = 1 + rng.nextInt(3);
      double cumulativeDelay = 0;
      for (int g = 0; g < groupCount; g++) {
        final enemyType = rng.nextDouble() < 0.7
            ? _pickNormalEnemy(dominantElement, rng) // 70%: ドミナント属性
            : _pickRandomEnemy(rng);                 // 30%: ランダム属性（運要素）

        // ±20% のランダム変動（要求仕様: ウェーブ内の敵構成ランダム変動）
        final baseCount = 2 + (waveNumber - 1);
        final variation = (rng.nextDouble() * 0.4 - 0.2); // -20%〜+20%
        final count = ((baseCount * (1 + variation)) * difficultyScale).round().clamp(1, 8);

        cumulativeDelay += g * (1.0 + rng.nextDouble() * 0.5);
        enemies.add(WaveEnemy(
          type: enemyType,
          count: count,
          laneIndex: rng.nextInt(4) - 1, // -1=random, 0/1/2 = lane
          spawnDelaySeconds: cumulativeDelay,
        ));
      }
    }

    return WaveData(
      waveNumber: waveNumber,
      enemies: enemies,
      isBossWave: isBossWave,
    );
  }

  static EnemyType _pickBoss(ElementType element, Random rng) {
    // 属性ごとにボスを対応させる
    switch (element) {
      case ElementType.dark:
        return rng.nextBool() ? EnemyType.lichKing : EnemyType.shadowLord;
      case ElementType.earth:
        return EnemyType.stoneGolem;
      default:
        return EnemyType.lichKing;
    }
  }

  static EnemyType _pickNormalEnemy(ElementType element, Random rng) {
    switch (element) {
      case ElementType.fire:
        return rng.nextBool() ? EnemyType.fireDrake : EnemyType.orcBerserker;
      case ElementType.water:
        return rng.nextBool() ? EnemyType.seaSerpent : EnemyType.orc;
      case ElementType.wind:
        return rng.nextBool() ? EnemyType.windWraith : EnemyType.goblin;
      case ElementType.earth:
        return rng.nextBool() ? EnemyType.stoneGolem : EnemyType.orc;
      case ElementType.light:
        return rng.nextBool() ? EnemyType.goblinShaman : EnemyType.windWraith;
      case ElementType.dark:
        return rng.nextBool() ? EnemyType.darkKnight : EnemyType.shadowBat;
    }
  }

  static EnemyType _pickRandomEnemy(Random rng) {
    final pool = EnemyType.values.where((e) => !e.isBoss).toList();
    return pool[rng.nextInt(pool.length)];
  }

  static String _pickBackground(Random rng, ElementType element) {
    switch (element) {
      case ElementType.fire:  return 'bg_volcano';
      case ElementType.water: return 'bg_sea';
      case ElementType.dark:  return 'bg_dark_castle';
      default:                return 'bg_forest';
    }
  }

  static String _pickBgm(Random rng) {
    const bgms = ['bgm_battle1', 'bgm_battle2', 'bgm_battle3'];
    return bgms[rng.nextInt(bgms.length)];
  }

  static Map<String, int> _generateRewards(
      Random rng, ElementType element, double scale) {
    final rewards = <String, int>{};
    rewards['mat_common'] = (3 * scale).round();

    // 属性固有素材
    switch (element) {
      case ElementType.fire:
        rewards['mat_drake_scale'] = 1 + rng.nextInt(2);
        break;
      case ElementType.water:
        rewards['mat_serpent_scale'] = 1 + rng.nextInt(2);
        break;
      case ElementType.dark:
        rewards['mat_dark_blade'] = 1 + rng.nextInt(2);
        break;
      default:
        rewards['mat_orc_hide'] = 1 + rng.nextInt(3);
    }
    return rewards;
  }

  static String _generateName(Random rng, ElementType element, int index) {
    const prefixes = ['封印の', '嵐の', '炎の', '闇の', '古の', '禁断の', '霧の'];
    const locations = ['峡谷', '要塞', '廃墟', '神殿', '洞窟', '城塞', '戦場'];
    final prefix = prefixes[rng.nextInt(prefixes.length)];
    final location = locations[rng.nextInt(locations.length)];
    return 'Ch.${index + 1}: $prefix$location';
  }

  static String _generateDescription(Random rng, ElementType element) {
    const templates = [
      '%s属性の敵が大量に押し寄せてくる。弱点を突け。',
      '強力な%s軍団が侵攻を開始した。戦略的な配置が鍵だ。',
      '%sの力を持つ敵たちとの激戦が始まる。',
    ];
    final template = templates[rng.nextInt(templates.length)];
    return template.replaceAll('%s', element.label);
  }
}
