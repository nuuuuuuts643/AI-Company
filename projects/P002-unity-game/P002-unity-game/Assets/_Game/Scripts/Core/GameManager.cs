using UnityEngine;
using System;

namespace FortressCity
{
    public class GameManager : MonoBehaviour
    {
        public static GameManager Instance { get; private set; }

        public CityData  City         { get; private set; }
        public GamePhase CurrentPhase { get; private set; } = GamePhase.City;

        [SerializeField] private UnitData[]  unitDataList;
        [SerializeField] private EnemyData[] enemyDataList;

        public UnitData[]  UnitDataList  => unitDataList;
        public EnemyData[] EnemyDataList => enemyDataList;

        public event Action OnGameOver;
        public event Action OnVictory;

        public static int WinMonth = 12;

        void Awake()
        {
            if (Instance != null) { Destroy(gameObject); return; }
            Instance = this;
            DontDestroyOnLoad(gameObject);
            City = SaveManager.Load() ?? new CityData();
        }

        public void SetPhase(GamePhase phase) => CurrentPhase = phase;

        public UnitData GetUnitData(UnitType type)
        {
            foreach (var u in unitDataList)
                if (u.unitType == type) return u;
            return null;
        }

        public EnemyData GetEnemyData(EnemyType type)
        {
            foreach (var e in enemyDataList)
                if (e.enemyType == type) return e;
            return null;
        }

        public void SaveGame() => SaveManager.Save(City);

        public void CheckWinLose()
        {
            if (City.fortHP <= 0)
                OnGameOver?.Invoke();
            else if (City.month > WinMonth)
                OnVictory?.Invoke();
        }

        public void ResetGame()
        {
            City = new CityData();
            SaveManager.Save(City);
        }
    }
}
