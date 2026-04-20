using UnityEngine;
using System;

namespace FortressCity
{
    public class CityManager : MonoBehaviour
    {
        public static CityManager Instance { get; private set; }

        void Awake() { Instance = this; }

        public void ProcessWeek()
        {
            var city = GameManager.Instance.City;

            // Income
            int goldIncome = 50 + city.life * 10;
            int goldUpkeep = CalcArmyGoldCost(city.army) + city.fort * 5;
            city.gold += goldIncome - goldUpkeep;

            int foodIncome      = 30 + city.life * 5;
            int foodConsumption = city.population / 10 + CalcArmyFoodCost(city.army);
            city.food += foodIncome - foodConsumption;

            // Starvation penalty
            if (city.food < 0)
            {
                city.population = Mathf.Max(10, city.population + city.food / 10);
                city.food = 0;
            }

            // Organic growth
            if (city.life >= 3 && city.population < 500) city.population += 2;

            // Hero revive
            if (!city.heroAlive && city.heroReviveWeeksLeft > 0)
            {
                city.heroReviveWeeksLeft--;
                if (city.heroReviveWeeksLeft == 0) city.heroAlive = true;
            }

            city.gold = Mathf.Max(0, city.gold);
        }

        int CalcArmyGoldCost(ArmyData army)
        {
            int total = 0;
            foreach (UnitType t in Enum.GetValues(typeof(UnitType)))
            {
                var data = GameManager.Instance.GetUnitData(t);
                if (data != null) total += data.weeklyGoldCost * army.GetCount(t);
            }
            return total;
        }

        int CalcArmyFoodCost(ArmyData army)
        {
            int total = 0;
            foreach (UnitType t in Enum.GetValues(typeof(UnitType)))
            {
                var data = GameManager.Instance.GetUnitData(t);
                if (data != null) total += data.weeklyFoodCost * army.GetCount(t);
            }
            return total;
        }

        public bool UpgradeFort()
        {
            var city = GameManager.Instance.City;
            int cost = GetUpgradeCost(city.fort);
            if (city.gold < cost) return false;
            city.gold -= cost;
            city.fort++;
            return true;
        }

        public bool UpgradeLife()
        {
            var city = GameManager.Instance.City;
            int cost = GetUpgradeCost(city.life);
            if (city.gold < cost) return false;
            city.gold -= cost;
            city.life++;
            return true;
        }

        public int GetUpgradeCost(int currentLevel) => 100 + currentLevel * 50;

        public bool RecruitUnit(UnitType type, int count)
        {
            var city = GameManager.Instance.City;
            var data = GameManager.Instance.GetUnitData(type);
            if (data == null || city.gold < data.recruitCost * count) return false;
            if (city.population < count * 2) return false;
            city.gold -= data.recruitCost * count;
            city.army.SetCount(type, city.army.GetCount(type) + count);
            return true;
        }
    }
}
