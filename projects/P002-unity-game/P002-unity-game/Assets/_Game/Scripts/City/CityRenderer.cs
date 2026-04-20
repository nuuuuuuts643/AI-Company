using UnityEngine;

namespace FortressCity
{
    // Attach to a GameObject in the City scene.
    // Activate/deactivate child GameObjects based on Fort and Life levels.
    //
    // Hierarchy example:
    //   CityRenderer
    //     Fort_Lv1  (basic wall)
    //     Fort_Lv2  (reinforced wall + gate tower)
    //     Fort_Lv3  (full castle wall + turrets)
    //     Life_Lv1  (small houses)
    //     Life_Lv2  (market + farms)
    //     Life_Lv3  (inn + park + dense housing)
    //     Army_Tier1 (few tent banners)
    //     Army_Tier2 (parade ground + lots of banners)
    //     Hero_Icon  (hero sprite / flag)

    public class CityRenderer : MonoBehaviour
    {
        [Header("Fort layers — index = required Fort level (0-based)")]
        [SerializeField] private GameObject[] fortLayers;

        [Header("Life layers — index = required Life level (0-based)")]
        [SerializeField] private GameObject[] lifeLayers;

        [Header("Army tiers — shown based on total unit count")]
        [SerializeField] private GameObject[] armyTiers;
        [SerializeField] private int[]        armyThresholds = { 0, 30, 80 };

        [Header("Hero")]
        [SerializeField] private GameObject heroObject;

        void OnDestroy()
        {
            if (TimeManager.Instance != null)
            {
                TimeManager.Instance.OnWeekAdvanced -= Refresh;
                TimeManager.Instance.OnMonthEnd     -= Refresh;
            }
        }

        void Start()
        {
            TimeManager.Instance.OnWeekAdvanced += Refresh;
            TimeManager.Instance.OnMonthEnd     += Refresh;
            Refresh();
        }

        public void Refresh()
        {
            var city = GameManager.Instance.City;

            // Fort: show layers up to current fort level
            for (int i = 0; i < fortLayers.Length; i++)
                if (fortLayers[i]) fortLayers[i].SetActive(i < city.fort);

            // Life: show layers up to current life level
            for (int i = 0; i < lifeLayers.Length; i++)
                if (lifeLayers[i]) lifeLayers[i].SetActive(i < city.life);

            // Army tiers
            int total = city.army.TotalUnits();
            int tier  = 0;
            for (int i = 0; i < armyThresholds.Length; i++)
                if (total >= armyThresholds[i]) tier = i;

            for (int i = 0; i < armyTiers.Length; i++)
                if (armyTiers[i]) armyTiers[i].SetActive(i <= tier);

            // Hero
            if (heroObject) heroObject.SetActive(city.heroAlive);
        }
    }
}
