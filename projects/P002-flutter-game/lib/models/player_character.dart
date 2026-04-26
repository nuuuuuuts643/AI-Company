import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'equipment_data.dart';
import '../systems/save_system.dart';

/// プレイヤーキャラクターの永続データ
/// ステージをまたいで蓄積される唯一の「積み上げ」
///
/// ⚠️ スキンは死亡・セッション失敗でも絶対にロストしない。
/// セッション中の装備リスクは [session_data.dart] の ItemState で管理し、
/// このクラスには成功・確保済みのデータのみが書き込まれる。
class PlayerCharacter {
  // ---- 基礎ステータス ----
  int level;               // キャラクターレベル（経験値で上昇）
  int experience;          // 累積経験値
  int totalClears;         // 累計ステージクリア数
  int totalEnemiesKilled;  // 累計撃破数
  int totalPlaySeconds;    // 累計プレイ時間（秒）

  // ---- 外見（死亡時もロストしない） ----
  String equippedSkinId;   // 現在装備中スキンID

  // ---- 所持スキン（死亡時もロストしない） ----
  List<String> ownedSkinIds;

  // ---- ハブ確保済み装備ID一覧 ----
  // セッション抽出成功後にここへ書き込む（secured 状態の equipmentId のみ）
  List<String> securedEquipmentIds;

  // ---- フラグ ----
  bool isAdFree;           // $2.99 有料版フラグ

  // ---- DynamoDB同期用 ----
  String? playerId;        // UUID（将来のクロスデバイス同期用）
  DateTime? lastSyncedAt;  // 最終同期時刻

  PlayerCharacter({
    this.level = 1,
    this.experience = 0,
    this.totalClears = 0,
    this.totalEnemiesKilled = 0,
    this.totalPlaySeconds = 0,
    this.equippedSkinId = 'skin_default',
    List<String>? ownedSkinIds,
    List<String>? securedEquipmentIds,
    this.isAdFree = false,
    this.playerId,
    this.lastSyncedAt,
  })  : ownedSkinIds = ownedSkinIds ?? ['skin_default'],
        securedEquipmentIds = securedEquipmentIds ?? [];

  // ---- 計算プロパティ ----

  /// 次のレベルアップに必要な経験値
  int get expToNextLevel => 100 + (level - 1) * 80;

  /// キャラクターの総合戦力（ステージ難易度スケーリングに使用）
  int get totalPower => level * 10 + totalClears * 3;

  /// 現在レベルの進行度（0.0〜1.0）
  double get levelProgress => (experience % expToNextLevel) / expToNextLevel;

  // ---- 経験値・レベルアップ ----

  /// 経験値を加算しレベルアップ処理
  /// 返値: レベルアップが発生した場合は新レベル、しなければnull
  int? addExperience(int amount) {
    experience += amount;
    int? newLevel;
    while (experience >= expToNextLevel) {
      experience -= expToNextLevel;
      level++;
      newLevel = level;
    }
    return newLevel;
  }

  /// ステージクリア時に経験値を付与
  int experienceForClear({required int score, required int waveNumber}) {
    return 20 + (score ~/ 100) + waveNumber * 5;
  }

  // ---- スキン管理 ----

  bool hasSkin(String skinId) => ownedSkinIds.contains(skinId);

  void unlockSkin(String skinId) {
    if (!ownedSkinIds.contains(skinId)) {
      ownedSkinIds.add(skinId);
    }
  }

  void equipSkin(String skinId) {
    if (hasSkin(skinId)) {
      equippedSkinId = skinId;
    }
  }

  // ---- シリアライズ ----

  Map<String, dynamic> toJson() => {
        'level': level,
        'experience': experience,
        'totalClears': totalClears,
        'totalEnemiesKilled': totalEnemiesKilled,
        'totalPlaySeconds': totalPlaySeconds,
        'equippedSkinId': equippedSkinId,
        'ownedSkinIds': ownedSkinIds,
        'securedEquipmentIds': securedEquipmentIds,
        'isAdFree': isAdFree,
        'playerId': playerId,
        'lastSyncedAt': lastSyncedAt?.toIso8601String(),
      };

  factory PlayerCharacter.fromJson(Map<String, dynamic> json) {
    return PlayerCharacter(
      level: json['level'] as int? ?? 1,
      experience: json['experience'] as int? ?? 0,
      totalClears: json['totalClears'] as int? ?? 0,
      totalEnemiesKilled: json['totalEnemiesKilled'] as int? ?? 0,
      totalPlaySeconds: json['totalPlaySeconds'] as int? ?? 0,
      equippedSkinId: json['equippedSkinId'] as String? ?? 'skin_default',
      ownedSkinIds: List<String>.from(
          json['ownedSkinIds'] as List? ?? ['skin_default']),
      securedEquipmentIds: List<String>.from(
          json['securedEquipmentIds'] as List? ?? []),
      isAdFree: json['isAdFree'] as bool? ?? false,
      playerId: json['playerId'] as String?,
      lastSyncedAt: json['lastSyncedAt'] != null
          ? DateTime.tryParse(json['lastSyncedAt'] as String)
          : null,
    );
  }
}

/// キャラクターデータ管理（シングルトン的ProviderノードまたはSaveSystemと連携）
class PlayerCharacterNotifier extends ChangeNotifier {
  PlayerCharacter _character = PlayerCharacter();
  PlayerCharacter get character => _character;

  Future<void> load() async {
    final saveSystem = CharacterSaveSystem();
    _character = await saveSystem.loadCharacter();
    notifyListeners();
  }

  Future<void> save() async {
    final saveSystem = CharacterSaveSystem();
    await saveSystem.saveCharacter(_character);
  }

  /// ステージクリア時の更新
  Future<int?> onStageClear({
    required int score,
    required int waveNumber,
    required int enemiesKilled,
    required int playSeconds,
  }) async {
    _character.totalClears++;
    _character.totalEnemiesKilled += enemiesKilled;
    _character.totalPlaySeconds += playSeconds;
    final exp = _character.experienceForClear(score: score, waveNumber: waveNumber);
    final levelUp = _character.addExperience(exp);
    await save();
    notifyListeners();
    return levelUp;
  }

  /// 有料版アンロック
  Future<void> unlockAdFree() async {
    _character.isAdFree = true;
    await save();
    notifyListeners();
  }

  void equipSkin(String skinId) {
    _character.equipSkin(skinId);
    save();
    notifyListeners();
  }

  void unlockSkin(String skinId) {
    _character.unlockSkin(skinId);
    save();
    notifyListeners();
  }
}

/// キャラクター専用のセーブシステム（SaveSystemと分離）
class CharacterSaveSystem {
  static const String _key = 'octo_battle_character_v1';

  Future<void> saveCharacter(PlayerCharacter character) async {
    final prefs = await _getPrefs();
    await prefs.setString(_key, _encode(character.toJson()));
  }

  Future<PlayerCharacter> loadCharacter() async {
    try {
      final prefs = await _getPrefs();
      final json = prefs.getString(_key);
      if (json == null) return PlayerCharacter();
      return PlayerCharacter.fromJson(_decode(json));
    } catch (_) {
      return PlayerCharacter();
    }
  }

  Future<dynamic> _getPrefs() async {
    // SharedPreferences を直接インポートすると循環するので遅延
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    return prefs;
  }

  String _encode(Map<String, dynamic> map) {
    return map.entries
        .map((e) => '${Uri.encodeComponent(e.key)}=${Uri.encodeComponent(e.value.toString())}')
        .join('&');
  }

  Map<String, dynamic> _decode(String encoded) {
    // 簡易デコード: 本実装ではjsonEncodeを使う
    final map = <String, dynamic>{};
    for (final pair in encoded.split('&')) {
      final parts = pair.split('=');
      if (parts.length == 2) {
        map[Uri.decodeComponent(parts[0])] = Uri.decodeComponent(parts[1]);
      }
    }
    return map;
  }
}
