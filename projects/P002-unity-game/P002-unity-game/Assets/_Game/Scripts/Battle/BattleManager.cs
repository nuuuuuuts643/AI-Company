using UnityEngine;
using System;

namespace FortressCity
{
    [Serializable]
    public class BattleSetup
    {
        public ArmyData  deployedArmy;
        public EnemyData enemy;
        public int       enemyPower;
        public bool      heroDeployed;
    }

    [Serializable]
    public class BattleReport
    {
        public BattleResult result;
        public ArmyData     casualties;
        public int          goldReward;
        public int          foodReward;
        public bool         heroFell;
        public float        playerPower;
        public float        enemyPower;
        public int          heroXPGained;
        public int          fortDamage;
        public bool         heroLeveledUp;
        public int          heroLevelAfter;
    }

    public class BattleManager : MonoBehaviour
    {
        public static BattleManager Instance { get; private set; }

        void Awake() { Instance = this; }

        public BattleReport ResolveBattle(BattleSetup setup)
        {
            var city   = GameManager.Instance.City;
            var report = new BattleReport();

            report.playerPower = CalcPlayerPower(setup.deployedArmy, setup.enemy, setup.heroDeployed, city);
            report.enemyPower  = setup.enemyPower;

            float ratio = report.playerPower / Mathf.Max(1f, report.enemyPower);
            bool  win   = ratio * UnityEngine.Random.Range(0.8f, 1.2f) >= 1f;
            report.result = win ? BattleResult.Victory : BattleResult.Defeat;

            float casualtyRate = win
                ? UnityEngine.Random.Range(0.1f, 0.3f)
                : UnityEngine.Random.Range(0.3f, 0.6f);

            report.casualties = CalcCasualties(setup.deployedArmy, casualtyRate);
            ApplyCasualties(city.army, report.casualties);

            if (setup.heroDeployed && city.heroAlive)
            {
                float deathChance = win ? 0.05f : 0.4f;
                if (UnityEngine.Random.value < deathChance)
                {
                    report.heroFell          = true;
                    city.heroAlive           = false;
                    city.heroReviveWeeksLeft = 3;
                }
            }

            if (win)
            {
                report.goldReward = 100 + city.month * 20;
                report.foodReward = 50  + city.month * 10;
                city.gold += report.goldReward;
                city.food += report.foodReward;
                city.consecutiveLosses = 0;
                report.fortDamage = casualtyRate > 0.25f ? 20 : 10;
            }
            else
            {
                city.consecutiveLosses++;
                city.gold = Mathf.Max(0, city.gold - 100);
                city.food = Mathf.Max(0, city.food - 50);
                ApplyDeathSpiralRelief(city);
                int rawDamage = Mathf.RoundToInt((report.enemyPower - report.playerPower) / 5f);
                report.fortDamage = Mathf.Clamp(rawDamage, 30, 80);
            }

            city.fortHP = Mathf.Max(0, city.fortHP - report.fortDamage);

            if (setup.heroDeployed && !report.heroFell)
            {
                report.heroXPGained = win ? 100 : 40;
                city.heroXP += report.heroXPGained;
                while (city.heroLevel < CityData.MaxLevel && city.heroXP >= city.XPForNextLevel)
                {
                    city.heroLevel++;
                    report.heroLeveledUp = true;
                }
            }
            report.heroLevelAfter = city.heroLevel;

            GameManager.Instance.CheckWinLose();
            GameManager.Instance.SaveGame();
            return report;
        }

        float CalcPlayerPower(ArmyData army, EnemyData enemy, bool heroDeployed, CityData city)
        {
            float fortBase = city.fort * 30f;
            float power    = HeroSystem.ApplyIronWallToFort(city, fortBase);

            foreach (UnitType t in Enum.GetValues(typeof(UnitType)))
            {
                int count = army.GetCount(t);
                if (count <= 0) continue;
                var data = GameManager.Instance.GetUnitData(t);
                if (data == null) continue;

                float unitPower = t == UnitType.Healer
                    ? count * 20f
                    : data.baseAttack * (float)count;

                if (enemy != null && enemy.weakness == t)
                    unitPower *= data.bonusMultiplier;

                if (heroDeployed && city.heroAlive)
                    unitPower = HeroSystem.ApplySkillsToPower(city, unitPower, t);

                power += unitPower;
            }

            if (heroDeployed && city.heroAlive)
                power *= HeroSystem.HeroBonusMultiplier(city);

            return power;
        }

        ArmyData CalcCasualties(ArmyData deployed, float rate) => new ArmyData
        {
            infantry  = Mathf.RoundToInt(deployed.infantry  * rate),
            archer    = Mathf.RoundToInt(deployed.archer    * rate),
            mage      = Mathf.RoundToInt(deployed.mage      * rate * 0.8f),
            cavalry   = Mathf.RoundToInt(deployed.cavalry   * rate * 1.1f),
            healer    = Mathf.RoundToInt(deployed.healer    * rate * 0.5f),
            artillery = Mathf.RoundToInt(deployed.artillery * rate * 0.7f),
        };

        void ApplyCasualties(ArmyData army, ArmyData casualties)
        {
            foreach (UnitType t in Enum.GetValues(typeof(UnitType)))
                army.SetCount(t, Mathf.Max(0, army.GetCount(t) - casualties.GetCount(t)));
        }

        void ApplyDeathSpiralRelief(CityData city)
        {
            if (city.consecutiveLosses >= 2)
            {
                city.gold          += 150;
                city.food          += 100;
                city.army.infantry += 10;
            }
        }
    }
}
