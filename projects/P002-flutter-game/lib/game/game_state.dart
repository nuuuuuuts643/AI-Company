import 'package:flutter/foundation.dart';
import '../models/card_data.dart';
import '../models/equipment_data.dart';
import '../models/session_data.dart' hide ItemState;
import '../models/stage_data.dart';
import '../systems/save_system.dart';
import '../systems/shop_system.dart';
import '../constants/game_constants.dart';
import '../constants/element_chart.dart';

/// ゲーム全体フェーズ
enum GamePhase {
  mainMenu,
  stageSelect,
  battle,
  waveShop,   // ウェーブ間ショップ
  result,
  equipment,
}

/// バトル内の状態
enum BattlePhase {
  preparing,   // ウェーブ間インターバル（カード配置準備）
  waving,      // 敵が侵攻中
  waveCleared, // ウェーブクリア演出
  bossFight,   // ボス戦
  victory,     // 全ウェーブクリア
  defeat,      // 城壁HP0
}

/// チェーン反応の記録（エフェクト表示用）
class ChainRecord {
  final ElementType firstElement;
  final ElementType secondElement;
  final int chainCount;
  final double damage;
  final DateTime triggeredAt;

  ChainRecord({
    required this.firstElement,
    required this.secondElement,
    required this.chainCount,
    required this.damage,
  }) : triggeredAt = DateTime.now();
}

/// バトル中のランタイム状態
class BattleState {
  final String stageId;
  int currentWave;
  int wallHp;
  int maxWallHp;
  double mana;
  double maxMana;
  int score;
  BattlePhase battlePhase;
  double waveTimer;         // 次のウェーブまでの秒数
  List<String> handCardIds; // 現在の手札（CardDataのid）
  List<String> deckCardIds; // デッキ残り
  Map<String, int> droppedMaterials; // ドロップ素材
  int chainCount;           // 現在のチェーンコンボ数
  ElementType? lastAttackElement; // 直前の攻撃属性（チェーン判定用）
  DateTime? lastAttackTime;
  List<ChainRecord> recentChains;
  double manaRegenRate;  // ボーンで加速（1.0=基準）

  BattleState({
    required this.stageId,
    this.currentWave = 1,
    required this.wallHp,
    required this.maxWallHp,
    this.mana = 5.0,
    this.maxMana = GameConstants.maxMana,
    this.score = 0,
    this.battlePhase = BattlePhase.preparing,
    this.waveTimer = GameConstants.waveIntervalSeconds,
    List<String>? handCardIds,
    List<String>? deckCardIds,
    Map<String, int>? droppedMaterials,
    this.chainCount = 0,
    this.lastAttackElement,
    this.lastAttackTime,
    List<ChainRecord>? recentChains,
    this.manaRegenRate = 1.0,
  })  : handCardIds = handCardIds ?? [],
        deckCardIds = deckCardIds ?? [],
        droppedMaterials = droppedMaterials ?? {},
        recentChains = recentChains ?? [];

  bool get isDefeated => wallHp <= 0;
  double get wallHpRatio => wallHp / maxWallHp;
  double get manaRatio => mana / maxMana;
}

/// プレイヤーの永続データ（セーブ対象）
class PlayerData {
  int gold;
  Map<String, int> materials;           // materialId → 所持数
  List<String> unlockedStageIds;
  Map<String, int> stageBestScores;     // stageId → ベストスコア
  List<String> deckCardIds;             // デッキのカードID（重複可）
  Map<EquipmentSlot, OwnedEquipment?> equippedItems;
  List<OwnedEquipment> ownedEquipments;

  int rank;
  int stamina;
  int maxStamina;
  int totalClearedCount; // 累計クリアステージ数（ランク計算用）
  bool tutorialSeen;     // チュートリアル表示済みフラグ

  PlayerData({
    this.gold = 0,
    this.rank = 1,
    this.stamina = 5,
    this.maxStamina = 5,
    this.totalClearedCount = 0,
    this.tutorialSeen = false,
    Map<String, int>? materials,
    List<String>? unlockedStageIds,
    Map<String, int>? stageBestScores,
    List<String>? deckCardIds,
    Map<EquipmentSlot, OwnedEquipment?>? equippedItems,
    List<OwnedEquipment>? ownedEquipments,
  })  : materials = materials ?? {},
        unlockedStageIds = unlockedStageIds ?? ['stage_01'],
        stageBestScores = stageBestScores ?? {},
        deckCardIds = deckCardIds ?? List.from(CardMaster.starterDeckIds),
        equippedItems = equippedItems ??
            {
              EquipmentSlot.weapon: OwnedEquipment(
                equipmentId: 'weapon_fire_sword',
                level: 1,
                itemState: ItemState.secured,
              ),
              EquipmentSlot.armor: OwnedEquipment(
                equipmentId: 'armor_iron_wall',
                level: 1,
                itemState: ItemState.secured,
              ),
              EquipmentSlot.accessory: OwnedEquipment(
                equipmentId: 'acc_lucky_charm',
                level: 1,
                itemState: ItemState.secured,
              ),
            },
        ownedEquipments = ownedEquipments ??
            [
              OwnedEquipment(equipmentId: 'weapon_fire_sword', level: 1, itemState: ItemState.secured),
              OwnedEquipment(equipmentId: 'armor_iron_wall', level: 1, itemState: ItemState.secured),
              OwnedEquipment(equipmentId: 'acc_lucky_charm', level: 1, itemState: ItemState.secured),
            ];

  /// 難易度スケーリング用（PlayerCharacter.totalPowerと設計統一のため暫定0固定）
  int get totalPower => 0;

  void addMaterial(String id, int count) {
    materials[id] = (materials[id] ?? 0) + count;
  }

  bool consumeMaterial(String id, int count) {
    if ((materials[id] ?? 0) < count) return false;
    materials[id] = materials[id]! - count;
    return true;
  }

  String get rankTitle {
    if (rank < 5) return '見習い冒険者';
    if (rank < 10) return '冒険者';
    if (rank < 20) return '勇者';
    if (rank < 35) return '英雄';
    return '伝説の英雄';
  }

  Map<String, dynamic> toJson() => {
        'gold': gold,
        'rank': rank,
        'stamina': stamina,
        'maxStamina': maxStamina,
        'totalClearedCount': totalClearedCount,
        'tutorialSeen': tutorialSeen,
        'materials': materials,
        'unlockedStageIds': unlockedStageIds,
        'stageBestScores': stageBestScores,
        'deckCardIds': deckCardIds,
        'ownedEquipments': ownedEquipments.map((e) => e.toJson()).toList(),
        'equippedWeapon': equippedItems[EquipmentSlot.weapon]?.toJson(),
        'equippedArmor': equippedItems[EquipmentSlot.armor]?.toJson(),
        'equippedAccessory': equippedItems[EquipmentSlot.accessory]?.toJson(),
      };

  factory PlayerData.fromJson(Map<String, dynamic> json) {
    OwnedEquipment? parseEquip(dynamic v) =>
        v == null ? null : OwnedEquipment.fromJson(v as Map<String, dynamic>);

    return PlayerData(
      gold: json['gold'] as int? ?? 0,
      rank: json['rank'] as int? ?? 1,
      stamina: json['stamina'] as int? ?? 5,
      maxStamina: json['maxStamina'] as int? ?? 5,
      totalClearedCount: json['totalClearedCount'] as int? ?? 0,
      tutorialSeen: json['tutorialSeen'] as bool? ?? false,
      materials: Map<String, int>.from(json['materials'] as Map? ?? {}),
      unlockedStageIds: List<String>.from(json['unlockedStageIds'] as List? ?? ['stage_01']),
      stageBestScores: Map<String, int>.from(json['stageBestScores'] as Map? ?? {}),
      deckCardIds: List<String>.from(json['deckCardIds'] as List? ?? CardMaster.starterDeckIds),
      ownedEquipments: (json['ownedEquipments'] as List? ?? [])
          .map((e) => OwnedEquipment.fromJson(e as Map<String, dynamic>))
          .toList(),
      equippedItems: {
        EquipmentSlot.weapon: parseEquip(json['equippedWeapon']),
        EquipmentSlot.armor: parseEquip(json['equippedArmor']),
        EquipmentSlot.accessory: parseEquip(json['equippedAccessory']),
      },
    );
  }
}

/// アプリ全体で共有するゲーム状態（ProviderでDI）
class GameStateNotifier extends ChangeNotifier {
  GamePhase _phase = GamePhase.mainMenu;
  PlayerData _player = PlayerData();
  BattleState? _battle;
  bool _isLoading = false;
  String? _selectedStageId;

  /// セッション進行状態（バトル開始〜終了まで）
  ActiveSession? _activeSession;

  /// ウェーブ間ショップシステム（バトルセッション中は同一インスタンスを保持）
  ShopSystem? _shopSystem;

  /// 直前のセッション結果（リザルト画面用）
  SessionResult? _lastSessionResult;

  /// 直前のステージクリアで解放されたカードID（リザルト画面用）
  List<String> _lastUnlockedCards = [];

  GamePhase get phase => _phase;
  PlayerData get player => _player;
  BattleState? get battle => _battle;
  bool get isLoading => _isLoading;
  String? get selectedStageId => _selectedStageId;
  ActiveSession? get activeSession => _activeSession;
  ShopSystem? get shopSystem => _shopSystem;
  SessionResult? get lastSessionResult => _lastSessionResult;
  List<String> get lastUnlockedCards => _lastUnlockedCards;
  bool get tutorialSeen => _player.tutorialSeen;

  Future<void> markTutorialSeen() async {
    _player.tutorialSeen = true;
    await _savePlayer();
  }

  /// 起動時初期化：セーブデータ読み込み
  Future<void> initialize() async {
    _isLoading = true;
    notifyListeners();
    final save = SaveSystem();
    _player = await save.loadPlayerData();
    _isLoading = false;
    notifyListeners();
  }

  // ---- フェーズ遷移 ----

  void goToStageSelect() {
    _phase = GamePhase.stageSelect;
    notifyListeners();
  }

  void goToMainMenu() {
    _phase = GamePhase.mainMenu;
    _battle = null;
    _activeSession = null;
    _shopSystem = null;
    notifyListeners();
  }

  void goToEquipment() {
    _phase = GamePhase.equipment;
    notifyListeners();
  }

  void selectStage(String stageId) {
    _selectedStageId = stageId;
    notifyListeners();
  }

  /// バトル開始：BattleState と ActiveSession を初期化
  void startBattle(String stageId) {
    // セッション開始（ハブ装備は secured 扱い）
    _activeSession = ActiveSession(
      stageId: stageId,
      hubEquipments: List.from(_player.ownedEquipments),
    );
    _shopSystem = ShopSystem();
    final stageData = StageMaster.getById(stageId)!;
    final wallHp = stageData.initialWallHp > 0
        ? stageData.initialWallHp
        : GameConstants.initialWallHp;

    // デッキをシャッフルして手札を配る
    final shuffled = List<String>.from(_player.deckCardIds)..shuffle();
    final hand = shuffled.take(GameConstants.initialHandSize).toList();
    final deck = shuffled.skip(GameConstants.initialHandSize).toList();

    _battle = BattleState(
      stageId: stageId,
      wallHp: wallHp,
      maxWallHp: wallHp,
      handCardIds: hand,
      deckCardIds: deck,
    );
    _phase = GamePhase.battle;
    notifyListeners();
  }

  // ---- バトル中の状態更新 ----

  /// マナを消費してカードを手札から除去（配置成功時）
  bool spendManaAndRemoveCard(String cardId, int cost) {
    if (_battle == null) return false;
    if (_battle!.mana < cost) return false;
    _battle!.mana -= cost;
    _battle!.handCardIds.remove(cardId);
    _drawCard();
    notifyListeners();
    return true;
  }

  /// マナを毎フレーム更新（FlameGameから呼ぶ）
  void tickMana(double dt) {
    if (_battle == null) return;
    final b = _battle!;
    if (b.battlePhase == BattlePhase.preparing || b.battlePhase == BattlePhase.waving) {
      b.mana = (b.mana + GameConstants.manaRegenPerSecond * b.manaRegenRate * dt).clamp(0, b.maxMana);
    }
  }

  /// 敵が城壁に到達したとき
  void damageWall(int damage) {
    if (_battle == null) return;
    _battle!.wallHp = (_battle!.wallHp - damage).clamp(0, _battle!.maxWallHp);
    if (_battle!.wallHp <= 0) {
      _battle!.battlePhase = BattlePhase.defeat;
    }
    notifyListeners();
  }

  /// スコア加算
  void addScore(int points) {
    if (_battle == null) return;
    _battle!.score += points;
    notifyListeners();
  }

  /// 素材ドロップ
  void addDroppedMaterial(String materialId, int count) {
    if (_battle == null) return;
    _battle!.droppedMaterials[materialId] =
        (_battle!.droppedMaterials[materialId] ?? 0) + count;
    notifyListeners();
  }

  /// ウェーブ進行
  void advanceWave() {
    if (_battle == null) return;
    _battle!.currentWave++;
    _battle!.battlePhase = BattlePhase.preparing;
    _battle!.waveTimer = GameConstants.waveIntervalSeconds;
    if (_activeSession != null) {
      _activeSession!.wavesCleared = _battle!.currentWave - 1;
    }
    notifyListeners();
  }

  // ---- ゴールド操作 ----

  /// ゴールドを加算
  void addGold(int amount) {
    _player.gold += amount;
    notifyListeners();
  }

  /// ゴールドを消費（不足時は false を返す）
  bool spendGold(int amount) {
    if (_player.gold < amount) return false;
    _player.gold -= amount;
    notifyListeners();
    return true;
  }

  // ---- 城壁修復 ----

  /// 城壁HPを回復（maxWallHp を超えない）
  void repairWall(int amount) {
    if (_battle == null) return;
    _battle!.wallHp = (_battle!.wallHp + amount).clamp(0, _battle!.maxWallHp);
    notifyListeners();
  }

  // ---- ウェーブ間ショップ ----

  /// ウェーブクリア後にショップを開く
  void openWaveShop() {
    _phase = GamePhase.waveShop;
    notifyListeners();
  }

  /// ショップを閉じてバトルに戻る
  void closeWaveShop() {
    _phase = GamePhase.battle;
    notifyListeners();
  }

  // ---- セッション管理（Tarkov的抽出リスク） ----

  /// セッション中にアイテム取得（atRisk 状態で追加）
  void addSessionItem(OwnedEquipment equipment) {
    _activeSession?.addFound(equipment);
    notifyListeners();
  }

  /// ボス撃破などで atRisk → secured に昇格
  void secureSessionItems() {
    _activeSession?.secureAllFound();
    notifyListeners();
  }

  /// バトル終了（勝利または敗北）
  Future<void> endBattle({required bool isVictory}) async {
    if (_battle == null) return;
    _battle!.battlePhase = isVictory ? BattlePhase.victory : BattlePhase.defeat;

    // セッション完了処理
    if (_activeSession != null) {
      _activeSession!.score = _battle!.score;
      _activeSession!.wavesCleared = _battle!.currentWave;

      if (isVictory) {
        // 勝利 = 全アイテムを secured に昇格
        _activeSession!.secureAllFound();
      }

      // セッション結果を生成
      final result = _activeSession!.finish(extracted: isVictory);
      _lastSessionResult = result;

      // 持ち帰り装備をハブの ownedEquipments に反映
      _player.ownedEquipments
        ..clear()
        ..addAll(
          result.keptEquipments.map((e) => OwnedEquipment(
                equipmentId: e.equipmentId,
                level: e.level,
                itemState: ItemState.secured,
              )),
        );
    }

    if (isVictory) {
      // ドロップ素材をプレイヤーデータに反映
      _battle!.droppedMaterials.forEach((id, cnt) {
        _player.addMaterial(id, cnt);
      });
      // ベストスコア更新
      final stageId = _battle!.stageId;
      if ((_player.stageBestScores[stageId] ?? 0) < _battle!.score) {
        _player.stageBestScores[stageId] = _battle!.score;
      }
      // 次のステージ解放
      final stageList = StageMaster.stages;
      final currentIdx = stageList.indexWhere((s) => s.id == stageId);
      if (currentIdx >= 0 && currentIdx + 1 < stageList.length) {
        final nextId = stageList[currentIdx + 1].id;
        if (!_player.unlockedStageIds.contains(nextId)) {
          _player.unlockedStageIds.add(nextId);
        }
      }
      // カード解放（初回クリア時のみ）
      _lastUnlockedCards = [];
      final unlockCandidates = CardMaster.stageUnlockCards[stageId] ?? [];
      for (final cardId in unlockCandidates) {
        if (!_player.deckCardIds.contains(cardId)) {
          _player.deckCardIds.add(cardId);
          _lastUnlockedCards.add(cardId);
        }
      }
      await _savePlayer();
    }

    _phase = GamePhase.result;
    notifyListeners();
  }

  /// 城壁HPを即時回復（ショップ効果等）
  void restoreWallHp(int amount) {
    if (_battle == null) return;
    _battle!.wallHp = (_battle!.wallHp + amount).clamp(0, _battle!.maxWallHp);
    notifyListeners();
  }

  /// チェーン反応を記録
  void recordChain(ChainRecord chain) {
    if (_battle == null) return;
    _battle!.recentChains.add(chain);
    _battle!.chainCount = chain.chainCount;
    notifyListeners();
  }

  // ---- 装備 ----

  void equipItem(OwnedEquipment equipment) {
    final data = EquipmentMaster.getById(equipment.equipmentId);
    if (data == null) return;
    _player.equippedItems[data.slot] = equipment;
    notifyListeners();
  }

  Future<bool> upgradeEquipment(OwnedEquipment equipment) async {
    final data = EquipmentMaster.getById(equipment.equipmentId);
    if (data == null || equipment.level >= data.maxLevel) return false;

    // コスト消費確認
    for (final entry in data.upgradeCost.entries) {
      if ((_player.materials[entry.key] ?? 0) < entry.value) return false;
    }
    for (final entry in data.upgradeCost.entries) {
      _player.consumeMaterial(entry.key, entry.value);
    }
    equipment.level++;
    await _savePlayer();
    notifyListeners();
    return true;
  }

  // ---- ボーンシステム連携 ----

  /// マナ回復速度にバフを乗せる
  void applyManaRegenBuff(double rate) {
    if (_battle == null) return;
    _battle!.manaRegenRate *= (1.0 + rate);
    notifyListeners();
  }

  /// 手札にランダムカードを追加
  void drawBonusCards(int count) {
    for (int i = 0; i < count; i++) _drawCard();
    notifyListeners();
  }

  /// 全配置済みユニットをパワーアップ（OctoBattleGameコールバック経由）
  VoidCallback? onPowerUpAllUnits;

  void powerUpAllUnits() {
    onPowerUpAllUnits?.call();
    notifyListeners();
  }

  /// 城壁HPを全回復
  void fullRestoreWall() {
    if (_battle == null) return;
    _battle!.wallHp = _battle!.maxWallHp;
    notifyListeners();
  }

  // ---- プライベートヘルパー ----

  void _drawCard() {
    if (_battle == null) return;
    final b = _battle!;
    if (b.handCardIds.length >= GameConstants.maxHandSize) return;
    if (b.deckCardIds.isEmpty) {
      // デッキ切れ：使用済みカードをシャッフルして補充
      b.deckCardIds = List.from(_player.deckCardIds)..shuffle();
    }
    if (b.deckCardIds.isNotEmpty) {
      b.handCardIds.add(b.deckCardIds.removeAt(0));
    }
  }

  Future<void> _savePlayer() async {
    final save = SaveSystem();
    await save.savePlayerData(_player);
  }
}
