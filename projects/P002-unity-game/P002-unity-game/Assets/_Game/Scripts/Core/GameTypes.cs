namespace FortressCity
{
    public enum UnitType        { Infantry, Archer, Mage, Cavalry, Healer, Artillery }
    public enum EnemyType       { GoblinHorde, OrcHeavy, Flying, Giant }
    public enum FormationPreset { Full, Balanced, Reserve, WeaknessSpecialized }
    public enum GamePhase       { City, Raid, Battle, Result }
    public enum BattleResult    { Victory, Defeat }

    public enum WeeklyAction
    {
        Train,   // 訓練: 歩兵+15, 食-25
        Tax,     // 徴税: Gold+130
        Repair,  // 修繕: 城HP+80, Gold-100
        Scout,   // 偵察: 無料偵察
        Govern,  // 民政: 人口+25, 食+20
    }

    public enum HeroSkillType
    {
        SteelFist,  // 剛力: 歩兵ATK +30%
        EagleEye,   // 鷹眼: 弓・魔ATK +30%
        IronWall,   // 鉄壁: Fort防御 +50%
        BattleCry,  // 鼓舞: 全兵ATK +15%
        Healing,    // 治癒: 回復兵効果 x2
        Gale,       // 疾風: 騎兵ATK +40%
        Command,    // 指揮: 勇者補正 x1.5
    }
}
