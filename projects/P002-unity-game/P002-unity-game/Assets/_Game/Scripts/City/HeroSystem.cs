namespace FortressCity
{
    public static class HeroSystem
    {
        public struct SkillData
        {
            public string name;
            public string description;
        }

        public static SkillData GetData(HeroSkillType skill) => skill switch
        {
            HeroSkillType.SteelFist  => new SkillData { name = "剛力",   description = "歩兵の攻撃力 +30%" },
            HeroSkillType.EagleEye   => new SkillData { name = "鷹眼",   description = "弓兵・魔法兵 +30%" },
            HeroSkillType.IronWall   => new SkillData { name = "鉄壁",   description = "砦防御ボーナス +50%" },
            HeroSkillType.BattleCry  => new SkillData { name = "鼓舞",   description = "全兵種 攻撃力 +15%" },
            HeroSkillType.Healing    => new SkillData { name = "治癒",   description = "回復兵の効果 2倍" },
            HeroSkillType.Gale       => new SkillData { name = "疾風",   description = "騎兵の攻撃力 +40%" },
            HeroSkillType.Command    => new SkillData { name = "指揮",   description = "勇者戦力補正 1.3→1.6" },
            _                        => new SkillData { name = "???",    description = "" },
        };

        public static bool HasSkill(CityData city, HeroSkillType skill) =>
            city.heroSkills.Contains((int)skill);

        public static void AddSkill(CityData city, HeroSkillType skill)
        {
            if (!HasSkill(city, skill))
                city.heroSkills.Add((int)skill);
        }

        // Returns modifier for heroPowerMultiplier
        public static float HeroBonusMultiplier(CityData city) =>
            HasSkill(city, HeroSkillType.Command) ? 1.6f : 1.3f;

        public static float ApplySkillsToPower(CityData city, float power, UnitType unitType)
        {
            foreach (int s in city.heroSkills)
            {
                var skill = (HeroSkillType)s;
                power *= skill switch
                {
                    HeroSkillType.SteelFist when unitType == UnitType.Infantry  => 1.30f,
                    HeroSkillType.EagleEye  when unitType == UnitType.Archer    => 1.30f,
                    HeroSkillType.EagleEye  when unitType == UnitType.Mage      => 1.30f,
                    HeroSkillType.BattleCry                                     => 1.15f,
                    HeroSkillType.Healing   when unitType == UnitType.Healer    => 2.00f,
                    HeroSkillType.Gale      when unitType == UnitType.Cavalry   => 1.40f,
                    _                                                            => 1.00f,
                };
            }
            return power;
        }

        public static float ApplyIronWallToFort(CityData city, float fortPower) =>
            HasSkill(city, HeroSkillType.IronWall) ? fortPower * 1.5f : fortPower;
    }
}
