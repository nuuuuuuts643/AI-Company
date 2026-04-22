import 'equipment_data.dart';

/// セッション中のアイテム状態
/// atRisk  = セッション中に拾った（死亡時ロスト対象）
/// secured = ハブから持ち込んだ / ボス撃破 or 抽出で確保済み
enum ItemState { atRisk, secured }

/// セッション中に取得した装備1件の記録
class SessionEquipmentRecord {
  final OwnedEquipment equipment;
  ItemState state;

  SessionEquipmentRecord({
    required this.equipment,
    this.state = ItemState.atRisk,
  });

  /// ボス撃破 / 抽出成功で secured に昇格
  void secure() => state = ItemState.secured;

  bool get isAtRisk => state == ItemState.atRisk;
  bool get isSecured => state == ItemState.secured;

  Map<String, dynamic> toJson() => {
        'equipment': equipment.toJson(),
        'state': state.name,
      };

  factory SessionEquipmentRecord.fromJson(Map<String, dynamic> json) =>
      SessionEquipmentRecord(
        equipment: OwnedEquipment.fromJson(
            json['equipment'] as Map<String, dynamic>),
        state: ItemState.values.firstWhere(
          (s) => s.name == (json['state'] as String? ?? 'atRisk'),
          orElse: () => ItemState.atRisk,
        ),
      );
}

/// セッション終了時の結果サマリー
/// ハブ画面に渡してリザルト表示に使う
class SessionResult {
  /// セッション開始時にハブから持ち込んだ装備（常に secured）
  final List<OwnedEquipment> hubEquipments;

  /// セッション中にショップ/ドロップで取得した装備リスト（state付き）
  final List<SessionEquipmentRecord> sessionRecords;

  /// 勝利・生存で抽出成功したか（false = 死亡 → atRisk アイテムはロスト）
  final bool extracted;

  /// バトルスコア
  final int score;

  /// 到達ウェーブ数
  final int wavesCleared;

  const SessionResult({
    required this.hubEquipments,
    required this.sessionRecords,
    required this.extracted,
    required this.score,
    required this.wavesCleared,
  });

  /// 持ち帰れた（ハブに戻る）装備リスト
  List<OwnedEquipment> get keptEquipments {
    final kept = <OwnedEquipment>[...hubEquipments];
    for (final rec in sessionRecords) {
      // secured または抽出成功時の atRisk アイテムはすべて持ち帰り
      if (rec.isSecured || extracted) {
        kept.add(rec.equipment);
      }
    }
    return kept;
  }

  /// ロストした（失った）装備リスト（死亡 + atRisk のもの）
  List<OwnedEquipment> get lostEquipments {
    if (extracted) return [];
    return sessionRecords
        .where((r) => r.isAtRisk)
        .map((r) => r.equipment)
        .toList();
  }

  /// 取得済みで持ち帰れたアイテム（リザルト表示「獲得」欄）
  List<OwnedEquipment> get gainedEquipments =>
      sessionRecords.where((r) => r.isSecured || extracted).map((r) => r.equipment).toList();

  Map<String, dynamic> toJson() => {
        'hubEquipments': hubEquipments.map((e) => e.toJson()).toList(),
        'sessionRecords': sessionRecords.map((r) => r.toJson()).toList(),
        'extracted': extracted,
        'score': score,
        'wavesCleared': wavesCleared,
      };

  factory SessionResult.fromJson(Map<String, dynamic> json) => SessionResult(
        hubEquipments: (json['hubEquipments'] as List? ?? [])
            .map((e) => OwnedEquipment.fromJson(e as Map<String, dynamic>))
            .toList(),
        sessionRecords: (json['sessionRecords'] as List? ?? [])
            .map((e) => SessionEquipmentRecord.fromJson(e as Map<String, dynamic>))
            .toList(),
        extracted: json['extracted'] as bool? ?? false,
        score: json['score'] as int? ?? 0,
        wavesCleared: json['wavesCleared'] as int? ?? 0,
      );
}

/// セッション進行中の状態（バトル開始〜終了まで）
class ActiveSession {
  final String stageId;
  final List<OwnedEquipment> hubEquipments;       // ハブから持ち込み（secured）
  final List<SessionEquipmentRecord> found;       // セッション中取得分
  int score = 0;
  int wavesCleared = 0;

  ActiveSession({
    required this.stageId,
    required this.hubEquipments,
  }) : found = [];

  /// アイテムを発見（atRisk で追加）
  void addFound(OwnedEquipment equipment) {
    found.add(SessionEquipmentRecord(equipment: equipment));
  }

  /// ボス撃破など条件達成で atRisk → secured に全昇格
  void secureAllFound() {
    for (final rec in found) {
      rec.secure();
    }
  }

  /// セッション終了（抽出成功フラグを渡す）
  SessionResult finish({required bool extracted}) {
    return SessionResult(
      hubEquipments: hubEquipments,
      sessionRecords: found,
      extracted: extracted,
      score: score,
      wavesCleared: wavesCleared,
    );
  }
}
