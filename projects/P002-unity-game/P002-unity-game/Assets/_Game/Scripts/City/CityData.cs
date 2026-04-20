using System;
using System.Collections.Generic;
using UnityEngine;

namespace FortressCity
{
    [Serializable]
    public class ArmyData
    {
        public int infantry;
        public int archer;
        public int mage;
        public int cavalry;
        public int healer;
        public int artillery;

        public int GetCount(UnitType type) => type switch
        {
            UnitType.Infantry  => infantry,
            UnitType.Archer    => archer,
            UnitType.Mage      => mage,
            UnitType.Cavalry   => cavalry,
            UnitType.Healer    => healer,
            UnitType.Artillery => artillery,
            _                  => 0
        };

        public void SetCount(UnitType type, int count)
        {
            switch (type)
            {
                case UnitType.Infantry:  infantry  = count; break;
                case UnitType.Archer:    archer    = count; break;
                case UnitType.Mage:      mage      = count; break;
                case UnitType.Cavalry:   cavalry   = count; break;
                case UnitType.Healer:    healer    = count; break;
                case UnitType.Artillery: artillery = count; break;
            }
        }

        public int TotalUnits() => infantry + archer + mage + cavalry + healer + artillery;

        public ArmyData Clone() => new ArmyData
        {
            infantry  = infantry,
            archer    = archer,
            mage      = mage,
            cavalry   = cavalry,
            healer    = healer,
            artillery = artillery
        };
    }

    [Serializable]
    public class CityData
    {
        // Resources
        public int gold       = 500;
        public int food       = 300;
        public int population = 100;

        // City levels
        public int fort = 1;
        public int life = 1;

        // Fort durability (pressure system)
        public int fortHP    = 200;
        public int maxFortHP = 200;

        // Time
        public int week  = 1;
        public int month = 1;

        // Hero
        public bool heroAlive           = true;
        public int  heroReviveWeeksLeft = 0;

        // Hero progression (growth system)
        public int        heroXP     = 0;
        public int        heroLevel  = 1;
        public List<int>  heroSkills = new List<int>(); // HeroSkillType values

        // Army
        public ArmyData army = new ArmyData
            { infantry = 20, archer = 10, mage = 5, cavalry = 5, healer = 5, artillery = 2 };

        // Meta
        public int  consecutiveLosses = 0;
        public bool scoutResultKnown  = false;

        // XP threshold for each level (index = current level - 1)
        public static readonly int[] LevelXPThresholds = { 120, 250, 400, 600 };
        public static int MaxLevel => LevelXPThresholds.Length + 1; // 5

        public int XPForNextLevel =>
            heroLevel <= LevelXPThresholds.Length ? LevelXPThresholds[heroLevel - 1] : int.MaxValue;
    }
}
