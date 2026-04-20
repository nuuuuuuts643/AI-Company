using UnityEngine;
using System;

namespace FortressCity
{
    [Serializable]
    public class ScoutResult
    {
        public bool   success;
        public string message;
    }

    public class ScoutManager : MonoBehaviour
    {
        public static ScoutManager Instance { get; private set; }

        [Range(0f, 1f)]
        public float baseSuccessRate = 0.35f;

        void Awake() { Instance = this; }

        public ScoutResult PerformScout(int scoutCount)
        {
            var city    = GameManager.Instance.City;
            var result  = new ScoutResult();
            float rate  = baseSuccessRate + scoutCount * 0.05f;

            if (UnityEngine.Random.value < rate)
            {
                result.success        = true;
                result.message        = "偵察成功：敵の情報を入手した";
                city.scoutResultKnown = true;
            }
            else
            {
                result.success  = false;
                int lost        = Mathf.Max(1, scoutCount);
                city.population = Mathf.Max(10, city.population - lost);
                result.message  = $"偵察失敗：偵察隊{lost}名が帰還せず";
            }

            GameManager.Instance.SaveGame();
            return result;
        }
    }
}
