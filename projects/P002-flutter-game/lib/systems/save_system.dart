import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';
import '../game/game_state.dart';
import '../models/session_data.dart';

/// ローカルセーブ／ロードシステム（SharedPreferences使用）
class SaveSystem {
  static const String _playerDataKey = 'octo_battle_player_v1';
  static const String _lastSessionKey = 'octo_battle_last_session_v1';

  // ---- PlayerData ----

  /// プレイヤーデータを保存
  Future<void> savePlayerData(PlayerData data) async {
    final prefs = await SharedPreferences.getInstance();
    final json = jsonEncode(data.toJson());
    await prefs.setString(_playerDataKey, json);
  }

  /// プレイヤーデータを読み込む（存在しない場合は初期値）
  Future<PlayerData> loadPlayerData() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final json = prefs.getString(_playerDataKey);
      if (json == null || json.isEmpty) return PlayerData();
      final map = jsonDecode(json) as Map<String, dynamic>;
      return PlayerData.fromJson(map);
    } catch (_) {
      // 破損セーブは初期値で上書き
      return PlayerData();
    }
  }

  // ---- SessionResult（直前のセッション結果） ----

  /// 直前のセッション結果を保存（リザルト画面用）
  Future<void> saveLastSessionResult(SessionResult result) async {
    final prefs = await SharedPreferences.getInstance();
    final json = jsonEncode(result.toJson());
    await prefs.setString(_lastSessionKey, json);
  }

  /// 直前のセッション結果を読み込む（ない場合は null）
  Future<SessionResult?> loadLastSessionResult() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final json = prefs.getString(_lastSessionKey);
      if (json == null || json.isEmpty) return null;
      final map = jsonDecode(json) as Map<String, dynamic>;
      return SessionResult.fromJson(map);
    } catch (_) {
      return null;
    }
  }

  // ---- ユーティリティ ----

  /// セーブデータを全削除（デバッグ用）
  Future<void> clearAll() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_playerDataKey);
    await prefs.remove(_lastSessionKey);
  }
}
