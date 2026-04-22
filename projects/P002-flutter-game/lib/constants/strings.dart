/// ゲーム内で使用する全日本語テキスト
/// UI文字列はすべてここから参照する
class Strings {
  // ---- タイトル画面 ----
  static const String appTitle = '封印の戦線';
  static const String appSubtitle = 'HD-2D リアルタイム属性バトル';
  static const String btnNewGame = 'はじめから';
  static const String btnContinue = 'つづきから';
  static const String btnEquipment = '装備・強化';
  static const String btnSettings = '設定';

  // ---- ステージ選択 ----
  static const String stageSelectTitle = 'ステージ選択';
  static const String stageLocked = '🔒 未解放';
  static const String stageCleared = '✅ クリア済み';
  static const String bestScore = 'ベストスコア';

  // ---- バトル画面 HUD ----
  static const String waveLabel = 'ウェーブ';
  static const String hpLabel = '城壁HP';
  static const String manaLabel = 'マナ';
  static const String scoreLabel = 'スコア';

  // ---- 属性名 ----
  static const String elementFire = '火';
  static const String elementWater = '水';
  static const String elementWind = '風';
  static const String elementEarth = '土';
  static const String elementLight = '光';
  static const String elementDark = '闇';

  // ---- 相性テキスト ----
  static const String effectivenessWeak = '弱点！';
  static const String effectivenessResist = '耐性';
  static const String effectivenessNormal = '';

  // ---- チェーン演出 ----
  static const String chain2x = 'チェーン ×2';
  static const String chain3x = 'チェーン ×3';
  static const String chainMax = 'MAX チェーン！';

  // ---- カード種別 ----
  static const String cardTypeUnit = 'ユニット';
  static const String cardTypeSpell = '魔法';
  static const String cardTypeTrap = '罠';

  // ---- ユニット名 ----
  static const String unitSwordsman = '剣士';
  static const String unitArcher = '弓兵';
  static const String unitMage = '魔法使い';
  static const String unitKnight = '騎士';
  static const String unitPriest = '聖職者';
  static const String unitBomber = '爆弾兵';
  static const String unitDruid = '霊樹使い';
  static const String unitNecromancer = '死霊術師';

  // ---- 魔法名 ----
  static const String spellFireball = 'ファイアボール';
  static const String spellWaterfall = '大瀑布';
  static const String spellTornado = '竜巻';
  static const String spellEarthspike = '岩礁衝';
  static const String spellHolyLight = '聖なる光';
  static const String spellDarkVoid = '暗黒虚無';
  static const String spellHeal = '回復の泉';
  static const String spellShield = '土の盾';

  // ---- 罠名 ----
  static const String trapFireMine = '炎地雷';
  static const String trapIcePit = '氷穴';
  static const String trapWindBlade = '風刃陣';
  static const String trapEarthSpike = '地棘陣';

  // ---- 敵名 ----
  static const String enemyGoblin = 'ゴブリン';
  static const String enemyOrc = 'オーク';
  static const String enemyFireDrake = 'ファイアドレイク';
  static const String enemySeaSerpent = '海蛇';
  static const String enemyWindWraith = '風霊';
  static const String enemyStoneGolem = 'ストーンゴーレム';
  static const String enemyLichKing = 'リッチキング（BOSS）';
  static const String enemyShadowLord = '影の王（BOSS）';

  // ---- リザルト画面 ----
  static const String resultClear = 'ステージクリア！';
  static const String resultGameOver = 'ゲームオーバー';
  static const String resultWave = 'ウェーブ到達';
  static const String resultScore = 'スコア';
  static const String resultDrop = '獲得素材';
  static const String btnRetry = 'リトライ';
  static const String btnNextStage = '次のステージへ';
  static const String btnReturnMenu = 'タイトルへ戻る';

  // ---- 装備・強化 ----
  static const String equipTitle = '装備・強化';
  static const String equipSlotWeapon = '武器';
  static const String equipSlotArmor = '防具';
  static const String equipSlotAccessory = 'アクセサリ';
  static const String upgradeBtn = '強化する';
  static const String upgradeSuccess = '強化成功！';
  static const String upgradeFail = '強化失敗…';
  static const String materialInsufficient = '素材が足りない';

  // ---- 共通 ----
  static const String btnOk = 'OK';
  static const String btnCancel = 'キャンセル';
  static const String btnBack = '← 戻る';
  static const String loading = '読み込み中…';
}
