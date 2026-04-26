import 'dart:math';
import '../game/game_state.dart';

// ---- アイテム状態 ----

/// アイテムの抽出状態（タルコフ方式）
enum ItemSecureState {
  /// 確定所持 — 死亡しても失わない
  secured,
  /// リスク中 — 抽出前に死亡するとロスト
  atRisk,
}

/// 抽出対象アイテム1つ
class ExtractionItem {
  final String itemId;
  final String displayName;
  final int goldValue;

  /// true = スキン・見た目アイテム。死亡してもロストしない
  final bool isCosmeticOnly;

  ItemSecureState state;

  ExtractionItem({
    required this.itemId,
    required this.displayName,
    required this.goldValue,
    this.isCosmeticOnly = false,
    this.state = ItemSecureState.atRisk,
  });

  /// ロスト対象かどうか（コスメのみアイテムは除外）
  bool get isAtRisk => state == ItemSecureState.atRisk && !isCosmeticOnly;

  Map<String, dynamic> toJson() => {
        'itemId': itemId,
        'displayName': displayName,
        'goldValue': goldValue,
        'isCosmeticOnly': isCosmeticOnly,
        'state': state.name,
      };

  factory ExtractionItem.fromJson(Map<String, dynamic> j) => ExtractionItem(
        itemId: j['itemId'] as String,
        displayName: j['displayName'] as String,
        goldValue: j['goldValue'] as int,
        isCosmeticOnly: j['isCosmeticOnly'] as bool? ?? false,
        state: j['state'] == 'secured'
            ? ItemSecureState.secured
            : ItemSecureState.atRisk,
      );
}

/// 抽出フェーズの状態
enum ExtractionPhase {
  /// バトル進行中（抽出選択前）
  inBattle,
  /// 選択画面表示中
  choosing,
  /// 抽出アニメーション再生中
  extracting,
  /// 抽出完了
  completed,
  /// 死亡 → atRisk ロスト確定
  failed,
}

/// 抽出システム — タルコフ的リスク管理
class ExtractionSystem {
  final GameStateNotifier gameState;
  final _rng = Random();

  /// 現在の所持アイテム（ドロップや購入で追加される）
  final List<ExtractionItem> _items = [];
  List<ExtractionItem> get items => List.unmodifiable(_items);

  /// atRisk アイテムのみ
  List<ExtractionItem> get atRiskItems =>
      _items.where((i) => i.isAtRisk).toList();

  /// secured アイテムのみ
  List<ExtractionItem> get securedItems =>
      _items.where((i) => i.state == ItemSecureState.secured).toList();

  /// 抽出進行度（0.0〜1.0）。extracting フェーズ中に更新
  double extractionProgress = 0.0;

  ExtractionPhase phase = ExtractionPhase.inBattle;

  /// 抽出にかかる時間（秒）
  static const double extractionDurationSeconds = 3.0;

  double _extractionTimer = 0.0;

  ExtractionSystem({required this.gameState});

  // ---- アイテム管理 ----

  /// ドロップ・購入でアイテムを追加（デフォルトで atRisk）
  void addItem(ExtractionItem item) {
    _items.add(item);
  }

  /// ショップ購入アイテムを atRisk で追加
  void addPurchasedItem({
    required String itemId,
    required String name,
    required int goldValue,
    bool isCosmeticOnly = false,
  }) {
    addItem(ExtractionItem(
      itemId: itemId,
      displayName: name,
      goldValue: goldValue,
      isCosmeticOnly: isCosmeticOnly,
      state: ItemSecureState.atRisk,
    ));
  }

  // ---- 昇格・ロスト処理 ----

  /// ボス撃破 or 脱出ポイント到達 → 全 atRisk を secured に昇格
  void secureAllItems({required String reason}) {
    for (final item in _items) {
      if (item.state == ItemSecureState.atRisk) {
        item.state = ItemSecureState.secured;
      }
    }
  }

  /// 特定アイテムのみ昇格（部分的なチェックポイント用）
  void secureItem(String itemId) {
    final index = _items.indexWhere((i) => i.itemId == itemId);
    if (index >= 0) {
      _items[index].state = ItemSecureState.secured;
    }
  }

  /// 死亡処理 — atRisk アイテムをロスト
  /// 返値: ロストしたアイテムリスト
  List<ExtractionItem> onPlayerDied() {
    phase = ExtractionPhase.failed;
    extractionProgress = 0.0;

    final lost = <ExtractionItem>[];
    for (int i = _items.length - 1; i >= 0; i--) {
      final item = _items[i];
      if (item.isAtRisk) {
        lost.add(item);
        _items.removeAt(i);
      }
    }
    return lost;
  }

  // ---- 抽出フロー ----

  /// 抽出選択画面を開く（ウェーブクリア後 or 手動）
  void openExtractionChoice() {
    if (phase == ExtractionPhase.inBattle) {
      phase = ExtractionPhase.choosing;
    }
  }

  /// 「脱出する」ボタン — 抽出アニメーション開始
  void beginExtraction() {
    phase = ExtractionPhase.extracting;
    extractionProgress = 0.0;
    _extractionTimer = 0.0;
  }

  /// 「続行する」ボタン — 次ウェーブへ（リスク承知）
  void continueWithRisk() {
    phase = ExtractionPhase.inBattle;
  }

  /// 毎フレーム更新（extracting 中のみ進行バー更新）
  /// 返値: 抽出完了 = true
  bool update(double dt) {
    if (phase != ExtractionPhase.extracting) return false;

    _extractionTimer += dt;
    extractionProgress =
        (_extractionTimer / extractionDurationSeconds).clamp(0.0, 1.0);

    if (extractionProgress >= 1.0) {
      _onExtractionCompleted();
      return true;
    }
    return false;
  }

  void _onExtractionCompleted() {
    // 抽出成功 → 全 atRisk を secured に昇格
    secureAllItems(reason: 'extraction_success');
    phase = ExtractionPhase.completed;

    // ゲームステートにアイテム報酬を反映
    _applyRewardsToPlayer();
  }

  void _applyRewardsToPlayer() {
    for (final item in _items) {
      if (item.isCosmeticOnly) continue;
      // ゴールド換算でプレイヤーに付与
      gameState.addGold(item.goldValue);
    }
  }

  // ---- リスク評価 ----

  /// 現在の atRisk ゴールド総額（リスクの可視化）
  int get totalAtRiskGoldValue =>
      atRiskItems.fold(0, (sum, i) => sum + i.goldValue);

  /// ランダムイベント: ウェーブクリア時にランダムで1アイテム自動昇格（5%確率）
  void rollRandomSecure() {
    final candidates = atRiskItems;
    if (candidates.isEmpty) return;
    if (_rng.nextInt(20) == 0) {
      // 5% 確率で1個ランダム昇格
      final picked = candidates[_rng.nextInt(candidates.length)];
      secureItem(picked.itemId);
    }
  }

  // ---- リセット ----

  /// バトル開始時にリセット
  void reset() {
    _items.clear();
    extractionProgress = 0.0;
    phase = ExtractionPhase.inBattle;
    _extractionTimer = 0.0;
  }
}
