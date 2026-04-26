/// スキンのカテゴリ
enum SkinCategory {
  standard,   // 初期・無料
  seasonal,   // 季節限定
  premium,    // 有料 / 実績解除
  event,      // イベント報酬
}

extension SkinCategoryLabel on SkinCategory {
  String get label {
    switch (this) {
      case SkinCategory.standard: return '標準';
      case SkinCategory.seasonal: return '季節限定';
      case SkinCategory.premium:  return 'プレミアム';
      case SkinCategory.event:    return 'イベント';
    }
  }
}

/// スキンデータ定義
class SkinData {
  final String id;
  final String name;
  final String description;
  final SkinCategory category;

  /// アセットパス（将来のアセット追加で差し替え）
  /// null = プレースホルダー使用
  final String? previewImagePath;

  /// アンロック条件の説明
  final String unlockCondition;

  /// スキンが変更するキャラクター外見色（プレースホルダー用）
  final int primaryColor;
  final int accentColor;

  /// 追加効果（ゲームプレイに影響なし: 演出のみ）
  final String? specialEffect; // 例: 'particle_sakura', 'trail_fire'

  /// 価格（0=無料/実績解除）
  final double price;

  const SkinData({
    required this.id,
    required this.name,
    required this.description,
    required this.category,
    this.previewImagePath,
    required this.unlockCondition,
    required this.primaryColor,
    this.accentColor = 0xFF607D8B,
    this.specialEffect,
    this.price = 0,
  });
}

/// スキンカタログ
/// アップデートで新スキンを追加する際はこのリストに追記するだけでOK
/// （コード変更不要、アセット追加のみ）
class SkinCatalog {
  static const List<SkinData> allSkins = [
    // ---- 標準スキン ----
    SkinData(
      id: 'skin_default',
      name: 'デフォルト',
      description: '初期スキン。みんなの見慣れた姿。',
      category: SkinCategory.standard,
      unlockCondition: '最初から使用可能',
      primaryColor: 0xFF4CAF50,
      accentColor: 0xFF81C784,
    ),
    SkinData(
      id: 'skin_iron_knight',
      name: '鉄の騎士',
      description: '鎧をまとった重装騎士スタイル。',
      category: SkinCategory.standard,
      unlockCondition: 'ステージ1をクリア',
      primaryColor: 0xFF78909C,
      accentColor: 0xFFB0BEC5,
    ),
    SkinData(
      id: 'skin_arcane_mage',
      name: '秘術の魔法使い',
      description: '星をまとった魔法使いスタイル。',
      category: SkinCategory.standard,
      unlockCondition: 'ステージ2をクリア',
      primaryColor: 0xFF7E57C2,
      accentColor: 0xFFB39DDB,
      specialEffect: 'sparkle_arcane',
    ),

    // ---- 季節限定スキン ----
    SkinData(
      id: 'skin_cherry_blossom',
      name: '桜の戦士',
      description: '桜の花びらを従えた春限定スキン。',
      category: SkinCategory.seasonal,
      unlockCondition: '春イベント期間中に入手',
      primaryColor: 0xFFF48FB1,
      accentColor: 0xFFF8BBD0,
      specialEffect: 'particle_sakura',
      previewImagePath: 'assets/images/skins/skin_cherry_blossom_preview.png',
    ),
    SkinData(
      id: 'skin_summer_warrior',
      name: '夏の勇者',
      description: '炎の祭典に参加した夏限定スキン。',
      category: SkinCategory.seasonal,
      unlockCondition: '夏イベント期間中に入手',
      primaryColor: 0xFFFF8F00,
      accentColor: 0xFFFFCC02,
      specialEffect: 'trail_fire',
    ),
    SkinData(
      id: 'skin_autumn_ranger',
      name: '紅葉の射手',
      description: '秋の森に溶け込む紅葉カラー。',
      category: SkinCategory.seasonal,
      unlockCondition: '秋イベント期間中に入手',
      primaryColor: 0xFFBF360C,
      accentColor: 0xFFFF7043,
      specialEffect: 'particle_leaves',
    ),
    SkinData(
      id: 'skin_winter_mage',
      name: '雪の術師',
      description: '氷晶を纏う冬限定スキン。',
      category: SkinCategory.seasonal,
      unlockCondition: '冬イベント期間中に入手',
      primaryColor: 0xFF80DEEA,
      accentColor: 0xFFE0F7FA,
      specialEffect: 'particle_snowflake',
    ),

    // ---- プレミアムスキン ----
    SkinData(
      id: 'skin_shadow_lord',
      name: '影の覇者',
      description: '最強の敵を模した闇の姿。全ステージクリアの証。',
      category: SkinCategory.premium,
      unlockCondition: '全ステージ☆3クリア',
      primaryColor: 0xFF4A148C,
      accentColor: 0xFFCE93D8,
      specialEffect: 'aura_dark',
    ),
    SkinData(
      id: 'skin_golden_hero',
      name: '黄金の英雄',
      description: '輝く黄金の鎧。50回クリアした歴戦の勇者。',
      category: SkinCategory.premium,
      unlockCondition: '累計50回クリア',
      primaryColor: 0xFFFFD700,
      accentColor: 0xFFFFF9C4,
      specialEffect: 'aura_golden',
    ),
    SkinData(
      id: 'skin_elemental_master',
      name: '元素の主',
      description: '6属性すべてを操る伝説の姿。',
      category: SkinCategory.premium,
      unlockCondition: '6属性カードをすべて使用してクリア',
      primaryColor: 0xFF00BCD4,
      accentColor: 0xFFE0F7FA,
      specialEffect: 'cycle_elements',
    ),

    // ---- イベントスキン ----
    SkinData(
      id: 'skin_retro_8bit',
      name: '8bitレトロ',
      description: '昔懐かしい8bitドット絵スタイル。',
      category: SkinCategory.event,
      unlockCondition: '発売記念イベントで入手',
      primaryColor: 0xFF8BC34A,
      accentColor: 0xFFCDDC39,
    ),
  ];

  /// IDでスキンを取得
  static SkinData? getById(String id) {
    try {
      return allSkins.firstWhere((s) => s.id == id);
    } catch (_) {
      return null;
    }
  }

  /// カテゴリでフィルタ
  static List<SkinData> getByCategory(SkinCategory category) {
    return allSkins.where((s) => s.category == category).toList();
  }

  /// 解禁条件が自動判定可能なスキンをチェック
  /// [totalClears] に応じて自動解禁されるスキンを返す
  static List<String> checkAutoUnlocks({required int totalClears}) {
    final toUnlock = <String>[];
    if (totalClears >= 1) toUnlock.add('skin_iron_knight');
    if (totalClears >= 3) toUnlock.add('skin_arcane_mage');
    if (totalClears >= 50) toUnlock.add('skin_golden_hero');
    return toUnlock;
  }
}
