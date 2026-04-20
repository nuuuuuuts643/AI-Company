using UnityEngine;
using UnityEngine.UI;
using TMPro;

namespace FortressCity
{
    public class ManageUIController : MonoBehaviour
    {
        [Header("Upgrade")]
        [SerializeField] Button   upgradeFortButton;
        [SerializeField] Button   upgradeLifeButton;
        [SerializeField] TMP_Text fortCostText;
        [SerializeField] TMP_Text lifeCostText;

        [Header("Recruit — one Button+CostText per UnitType in enum order")]
        [SerializeField] Button[]   recruitButtons;
        [SerializeField] TMP_Text[] recruitCostTexts;

        [SerializeField] Button closeButton;

        void Start()
        {
            upgradeFortButton.onClick.AddListener(() => { CityManager.Instance.UpgradeFort(); Refresh(); });
            upgradeLifeButton.onClick.AddListener(() => { CityManager.Instance.UpgradeLife(); Refresh(); });

            for (int i = 0; i < recruitButtons.Length; i++)
            {
                int idx = i;
                recruitButtons[i].onClick.AddListener(() =>
                {
                    CityManager.Instance.RecruitUnit((UnitType)idx, 5);
                    Refresh();
                });
            }

            closeButton?.onClick.AddListener(() => {
                var ap = GetComponent<AnimatedPanel>();
                if (ap) ap.Close(); else gameObject.SetActive(false);
            });
            Refresh();
        }

        void OnEnable() { if (GameManager.Instance != null) Refresh(); }

        void Refresh()
        {
            if (GameManager.Instance == null) return;
            var city = GameManager.Instance.City;
            fortCostText.text = $"Fort Lv{city.fort}→{city.fort + 1}  {CityManager.Instance.GetUpgradeCost(city.fort)}G";
            lifeCostText.text = $"Life Lv{city.life}→{city.life + 1}  {CityManager.Instance.GetUpgradeCost(city.life)}G";

            for (int i = 0; i < recruitButtons.Length && i < recruitCostTexts.Length; i++)
            {
                var data = GameManager.Instance.GetUnitData((UnitType)i);
                if (data != null)
                    recruitCostTexts[i].text = $"x5  {data.recruitCost * 5}G";
            }
        }
    }
}
